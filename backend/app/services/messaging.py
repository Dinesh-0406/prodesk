"""WhatsApp messaging: contacts, conversations, outbound policy, sending and status tracking.

Policy (WhatsApp Business Platform rules, enforced before anything is queued):
* Clients who opted out never receive messages (only an opt-out confirmation).
* Business-initiated messages must use an APPROVED template and require client opt-in.
* Free-form messages (text/document/image/interactive) only inside the 24h customer
  service window that opens when the client messages the firm.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import Principal, system_principal
from app.core.logging import get_logger
from app.core.permissions import Perm
from app.core.phone import to_wa_id
from app.core.rate_limit import hit
from app.core.security import now_utc
from app.integrations.whatsapp import TemplateComponentParams, WAErrorCategory, get_whatsapp_provider
from app.models import Client, Conversation, DocumentDelivery, Message, Organization, WhatsAppAccount, WhatsAppContact
from app.models.enums import (
    ConversationStatus,
    DeliveryStatus,
    MessageDirection,
    MessageSender,
    MessageStatus,
    MessageType,
    TemplateKey,
    TemplateStatus,
    WhatsAppAccountStatus,
)
from app.services import audit, notifications, templates
from app.services.audit import AuditAction
from app.workers.dispatch import enqueue_on_commit

log = get_logger("whatsapp.service")
SERVICE_WINDOW = timedelta(hours=24)
MAX_SEND_ATTEMPTS = 5
_STATUS_RANK = {MessageStatus.QUEUED: 0, MessageStatus.SENT: 1, MessageStatus.DELIVERED: 2, MessageStatus.READ: 3}


class RetryableSendError(Exception):
    def __init__(self, message: str, countdown: int = 30) -> None:
        super().__init__(message)
        self.countdown = countdown


@dataclass
class Outbound:
    kind: MessageType
    body: str | None = None
    template_key: TemplateKey | None = None
    params: list[str] = field(default_factory=list)
    url_suffix: str | None = None
    link: str | None = None
    file_name: str | None = None
    buttons: list[tuple[str, str]] = field(default_factory=list)
    bypass_opt_in: bool = False  # user-requested transactional (OTP)


# --- contacts & conversations -------------------------------------------------------


def get_account(db: Session, org_id: uuid.UUID) -> WhatsAppAccount | None:
    return (
        db.execute(select(WhatsAppAccount).where(WhatsAppAccount.organization_id == org_id).order_by(WhatsAppAccount.created_at))
        .scalars()
        .first()
    )


def get_or_create_contact(
    db: Session, org_id: uuid.UUID, wa_id: str, *, phone: str | None = None, client: Client | None = None, profile_name: str | None = None
) -> WhatsAppContact:
    contact = (
        db.execute(select(WhatsAppContact).where(WhatsAppContact.organization_id == org_id, WhatsAppContact.wa_id == wa_id))
        .unique()
        .scalar_one_or_none()
    )
    if contact is None:
        contact = WhatsAppContact(
            organization_id=org_id, wa_id=wa_id, phone=phone, client_id=client.id if client else None, profile_name=profile_name
        )
        db.add(contact)
        db.flush()
    else:
        if client and contact.client_id != client.id:
            contact.client_id = client.id
        if profile_name:
            contact.profile_name = profile_name[:200]
    return contact


def get_or_create_conversation(db: Session, org_id: uuid.UUID, contact: WhatsAppContact) -> Conversation:
    conv = (
        db.execute(
            select(Conversation)
            .where(Conversation.organization_id == org_id, Conversation.contact_id == contact.id)
            .order_by(Conversation.created_at.desc())
        )
        .unique()
        .scalars()
        .first()
    )
    if conv is None:
        conv = Conversation(organization_id=org_id, contact_id=contact.id, client_id=contact.client_id, context={})
        db.add(conv)
        db.flush()
    elif conv.status == ConversationStatus.CLOSED:
        conv.status = ConversationStatus.OPEN
    if contact.client_id and conv.client_id != contact.client_id:
        conv.client_id = contact.client_id
    return conv


def conversation_for_client(db: Session, client: Client) -> Conversation:
    contact = get_or_create_contact(db, client.organization_id, to_wa_id(client.phone), phone=client.phone, client=client)
    return get_or_create_conversation(db, client.organization_id, contact)


def service_window_open(contact: WhatsAppContact | None, at: datetime | None = None) -> bool:
    if contact is None or contact.last_inbound_at is None:
        return False
    return (at or now_utc()) - contact.last_inbound_at < SERVICE_WINDOW


# --- outbound ----------------------------------------------------------------------


def _policy_error(
    db: Session, org_id: uuid.UUID, client: Client | None, contact: WhatsAppContact, spec: Outbound
) -> tuple[str, str] | None:
    account = get_account(db, org_id)
    if account is None and settings.WHATSAPP_PROVIDER != "mock":
        return "NOT_CONFIGURED", "WhatsApp is not configured for this firm"
    if account is not None and account.status == WhatsAppAccountStatus.INACTIVE:
        return "NOT_CONFIGURED", "WhatsApp account is inactive"
    if contact.opted_out or (client is not None and client.whatsapp_opt_out_at is not None):
        return "OPTED_OUT", "Client has opted out of WhatsApp messages"
    if spec.kind == MessageType.TEMPLATE:
        tpl = templates.get_template(db, org_id, spec.template_key) if spec.template_key else None
        if tpl is None:
            return WAErrorCategory.TEMPLATE_INVALID.value, "Template is not configured"
        if tpl.status != TemplateStatus.APPROVED:
            return WAErrorCategory.TEMPLATE_NOT_APPROVED.value, f"Template '{tpl.name}' is not approved (status {tpl.status})"
        if not spec.bypass_opt_in and client is not None and not client.whatsapp_opt_in:
            return "NO_OPT_IN", "Client has not opted in to WhatsApp messages"
    elif not service_window_open(contact):
        return WAErrorCategory.OUTSIDE_SERVICE_WINDOW.value, "24-hour service window is closed; an approved template is required"
    return None


def queue_message(
    db: Session,
    org_id: uuid.UUID,
    spec: Outbound,
    *,
    client: Client | None = None,
    conversation: Conversation | None = None,
    sender: MessageSender = MessageSender.SYSTEM,
    sender_user_id: uuid.UUID | None = None,
) -> Message:
    """Validate policy and persist an outbound message. Sending happens in a worker after commit.

    Policy failures are persisted as FAILED messages (visible in the inbox and audit trail)
    rather than raised, so automated flows degrade gracefully.
    """
    if conversation is None:
        if client is None:
            raise ValueError("client or conversation required")
        conversation = conversation_for_client(db, client)
    contact = conversation.contact
    if client is None and conversation.client_id:
        client = db.get(Client, conversation.client_id)

    body = spec.body
    if spec.kind == MessageType.TEMPLATE and spec.template_key:
        tpl = templates.get_template(db, org_id, spec.template_key)
        body = templates.render_preview(tpl.body_preview, spec.params) if tpl else f"[{spec.template_key}]"
        if spec.template_key == TemplateKey.OTP:
            body = templates.render_preview(tpl.body_preview, ["••••••"]) if tpl else "[OTP]"

    now = now_utc()
    payload: dict[str, Any] = {
        "kind": spec.kind.value,
        "params": spec.params,
        "url_suffix": spec.url_suffix,
        "link": spec.link,
        "file_name": spec.file_name,
        "buttons": spec.buttons,
        "text": spec.body,
    }
    if spec.template_key == TemplateKey.OTP:
        payload["sensitive"] = True
    msg = Message(
        organization_id=org_id,
        conversation_id=conversation.id,
        direction=MessageDirection.OUTBOUND,
        message_type=spec.kind,
        sender=sender,
        sender_user_id=sender_user_id,
        recipient=contact.wa_id,
        body=body,
        template_key=spec.template_key.value if spec.template_key else None,
        status=MessageStatus.QUEUED,
        payload=payload,
        timestamp=now,
    )
    err = _policy_error(db, org_id, client, contact, spec)
    if err:
        msg.status = MessageStatus.FAILED
        msg.error_code, msg.error = err
        db.add(msg)
        db.flush()
        audit.record(
            db,
            system_principal(org_id),
            AuditAction.WHATSAPP_FAILED,
            resource="message",
            resource_id=msg.id,
            client_id=client.id if client else None,
            metadata={"reason": err[0]},
        )
        return msg
    db.add(msg)
    db.flush()
    if spec.kind != MessageType.TEMPLATE or spec.template_key != TemplateKey.OTP:
        conversation.last_message_at = now
        conversation.last_message_preview = (body or "")[:255]
    enqueue_on_commit(db, "whatsapp.send_message", message_id=str(msg.id))
    return msg


def send_template_to_client(
    db: Session, client: Client, key: TemplateKey, params: list[str], *, url_suffix: str | None = None, bypass_opt_in: bool = False
) -> Message:
    return queue_message(
        db,
        client.organization_id,
        Outbound(kind=MessageType.TEMPLATE, template_key=key, params=params, url_suffix=url_suffix, bypass_opt_in=bypass_opt_in),
        client=client,
    )


def agent_reply(db: Session, principal: Principal, conversation: Conversation, body: str) -> Message:
    from app.models.enums import HandoverState

    principal.require(Perm.WHATSAPP_SEND)
    hit(f"wa_send:{principal.org_id}", settings.WHATSAPP_SEND_RATE_PER_MINUTE, 60)
    msg = queue_message(
        db,
        principal.org_id,
        Outbound(kind=MessageType.TEXT, body=body),
        conversation=conversation,
        sender=MessageSender.AGENT,
        sender_user_id=principal.user_id,
    )
    if msg.status != MessageStatus.FAILED and conversation.handover_state in (HandoverState.HUMAN_REQUESTED, HandoverState.AGENT_ASSIGNED):
        conversation.handover_state = HandoverState.HUMAN_ACTIVE
        conversation.assigned_agent_id = conversation.assigned_agent_id or principal.user_id
    conversation.unread_count = 0
    db.commit()
    return msg


def _dispatch(provider: Any, msg: Message, tpl_name: str | None, tpl_lang: str) -> Any:
    p = msg.payload or {}
    kind = MessageType(msg.message_type)
    to = msg.recipient or ""
    if kind == MessageType.TEXT:
        return provider.send_text(to, p.get("text") or msg.body or "", preview_url=bool(p.get("preview_url")))
    if kind == MessageType.TEMPLATE:
        return provider.send_template(
            to,
            tpl_name or "",
            tpl_lang,
            TemplateComponentParams(body=[str(x) for x in p.get("params", [])], url_button_suffix=p.get("url_suffix")),
        )
    if kind == MessageType.DOCUMENT:
        return provider.send_document(to, link=p["link"], file_name=p.get("file_name") or "document", caption=msg.body)
    if kind == MessageType.IMAGE:
        return provider.send_image(to, link=p["link"], caption=msg.body)
    if kind == MessageType.INTERACTIVE:
        return provider.send_interactive_message(to, body=msg.body or "", buttons=[tuple(b) for b in p.get("buttons", [])])
    raise ValueError(f"Unsupported outbound type {kind}")


def send_queued_message(db: Session, message_id: uuid.UUID) -> Message:
    """Worker entrypoint: deliver one queued message via the org's provider."""
    msg = db.execute(select(Message).where(Message.id == message_id).with_for_update()).scalar_one_or_none()
    if msg is None or msg.status != MessageStatus.QUEUED:
        return msg  # type: ignore[return-value]  # idempotent: already processed
    org_id = msg.organization_id
    account = get_account(db, org_id)
    tpl = templates.get_template(db, org_id, msg.template_key) if msg.template_key else None
    try:
        hit(f"wa_out:{org_id}", settings.WHATSAPP_SEND_RATE_PER_MINUTE * 4, 60)
    except Exception:
        raise RetryableSendError("Org send rate exceeded", countdown=60) from None
    msg.attempts += 1
    err_text = ""
    try:
        provider = get_whatsapp_provider(account)
        result = _dispatch(provider, msg, tpl.name if tpl else None, tpl.language if tpl else "en")
    except Exception as e:
        log.exception("whatsapp_send_exception")
        result = None
        err_text = str(e)[:300]
    if result is not None and result.ok:
        msg.status = MessageStatus.SENT
        msg.provider_message_id = result.provider_message_id
        msg.sent_at = now_utc()
        msg.error = msg.error_code = None
        if msg.payload.get("sensitive"):
            msg.payload = {**msg.payload, "params": ["[REDACTED]"], "url_suffix": None}
        _update_delivery_for_message(db, msg, DeliveryStatus.SENT)
        audit.record(
            db,
            system_principal(org_id),
            AuditAction.WHATSAPP_SENT,
            resource="message",
            resource_id=msg.id,
            metadata={"type": msg.message_type, "template": msg.template_key},
        )
        log.info("whatsapp_sent", extra={"message_id": str(msg.id), "wa_type": msg.message_type})
        db.commit()
        return msg

    category = result.category if result is not None else WAErrorCategory.TRANSIENT
    code = result.error_code if result is not None else "EXCEPTION"
    text = result.error_message if result is not None else err_text
    if category in (WAErrorCategory.RATE_LIMITED, WAErrorCategory.TRANSIENT) and msg.attempts < MAX_SEND_ATTEMPTS:
        msg.error_code, msg.error = code, text
        db.commit()
        raise RetryableSendError(text or "retry", countdown=min(900, 15 * (2**msg.attempts)))

    msg.status = MessageStatus.FAILED
    msg.error_code, msg.error = code, text
    if msg.payload.get("sensitive"):
        msg.payload = {**msg.payload, "params": ["[REDACTED]"], "url_suffix": None}
    _handle_terminal_failure(db, msg, account, tpl, category)
    _update_delivery_for_message(db, msg, DeliveryStatus.FAILED, error=text)
    audit.record(
        db,
        system_principal(org_id),
        AuditAction.WHATSAPP_FAILED,
        resource="message",
        resource_id=msg.id,
        metadata={"code": code, "category": str(category)},
    )
    db.commit()
    return msg


def _handle_terminal_failure(
    db: Session, msg: Message, account: WhatsAppAccount | None, tpl: Any, category: WAErrorCategory | None
) -> None:
    org_id = msg.organization_id
    if category in (WAErrorCategory.TEMPLATE_NOT_APPROVED, WAErrorCategory.TEMPLATE_INVALID) and tpl is not None:
        tpl.status = TemplateStatus.REJECTED if category == WAErrorCategory.TEMPLATE_NOT_APPROVED else tpl.status
        tpl.last_error = msg.error
        notifications.notify_permission(
            db,
            org_id,
            Perm.WHATSAPP_MANAGE,
            type_="WHATSAPP_TEMPLATE_ERROR",
            title=f"WhatsApp template '{tpl.name}' failed",
            body=msg.error,
            link="/settings/whatsapp",
        )
    elif category == WAErrorCategory.AUTH_EXPIRED and account is not None:
        account.status = WhatsAppAccountStatus.ERROR
        account.last_error = "Access token expired or invalid. Update it in Settings → WhatsApp."
        notifications.notify_permission(
            db,
            org_id,
            Perm.WHATSAPP_MANAGE,
            type_="WHATSAPP_AUTH_ERROR",
            title="WhatsApp access token expired",
            body=account.last_error,
            link="/settings/whatsapp",
        )


def _update_delivery_for_message(db: Session, msg: Message, status: DeliveryStatus, error: str | None = None) -> None:
    delivery = db.execute(select(DocumentDelivery).where(DocumentDelivery.message_id == msg.id)).scalar_one_or_none()
    if delivery is None:
        return
    now = now_utc()
    if status == DeliveryStatus.SENT:
        delivery.status = DeliveryStatus.SENT
        delivery.sent_at = now
        from app.models import Document
        from app.models.enums import DocumentStatus

        doc = db.get(Document, delivery.document_id)
        if doc and doc.status == DocumentStatus.APPROVED:
            doc.status = DocumentStatus.DELIVERED
    elif status == DeliveryStatus.FAILED:
        delivery.status = DeliveryStatus.FAILED
        delivery.error = error
        audit.record(
            db,
            system_principal(msg.organization_id),
            AuditAction.DOCUMENT_DELIVERY_FAILED,
            resource="document",
            resource_id=delivery.document_id,
            client_id=delivery.client_id,
            metadata={"error": (error or "")[:200]},
        )
        client = db.get(Client, delivery.client_id)
        notifications.notify_client_owner(
            db,
            msg.organization_id,
            client.assigned_employee_id if client else None,
            fallback_perm=Perm.DOCUMENT_APPROVE,
            type_="DELIVERY_FAILED",
            title="Document delivery failed",
            body=f"WhatsApp delivery to {client.name if client else 'client'} failed: {error}",
            link=f"/documents/{delivery.document_id}",
        )


def apply_status_update(
    db: Session, org_id: uuid.UUID, provider_message_id: str, status: str, ts: datetime, errors: list[dict[str, Any]] | None = None
) -> bool:
    msg = db.execute(
        select(Message).where(Message.organization_id == org_id, Message.provider_message_id == provider_message_id)
    ).scalar_one_or_none()
    if msg is None:
        return False
    new = {
        "sent": MessageStatus.SENT,
        "delivered": MessageStatus.DELIVERED,
        "read": MessageStatus.READ,
        "failed": MessageStatus.FAILED,
    }.get(status)
    if new is None:
        return False
    delivery = db.execute(select(DocumentDelivery).where(DocumentDelivery.message_id == msg.id)).scalar_one_or_none()
    if new == MessageStatus.FAILED:
        msg.status = MessageStatus.FAILED
        e = (errors or [{}])[0]
        msg.error_code = str(e.get("code", ""))
        msg.error = str(e.get("title") or e.get("message") or "Delivery failed")[:500]
        if delivery:
            delivery.status = DeliveryStatus.FAILED
            delivery.error = msg.error
        return True
    if _STATUS_RANK.get(MessageStatus(msg.status), -1) < _STATUS_RANK[new]:
        msg.status = new
    if new == MessageStatus.DELIVERED:
        msg.delivered_at = msg.delivered_at or ts
    if new == MessageStatus.READ:
        msg.read_at = msg.read_at or ts
        msg.delivered_at = msg.delivered_at or ts
    if delivery:
        if new in (MessageStatus.DELIVERED, MessageStatus.READ):
            delivery.delivered_at = delivery.delivered_at or ts
        if new == MessageStatus.READ:
            delivery.read_at = delivery.read_at or ts
        rank = {DeliveryStatus.SENT: 1, DeliveryStatus.DELIVERED: 2, DeliveryStatus.READ: 3, DeliveryStatus.DOWNLOADED: 4}
        target = {MessageStatus.DELIVERED: DeliveryStatus.DELIVERED, MessageStatus.READ: DeliveryStatus.READ}.get(new)
        if target and rank.get(DeliveryStatus(delivery.status), 0) < rank[target]:
            delivery.status = target
    return True


def firm_name(db: Session, org_id: uuid.UUID) -> str:
    org = db.get(Organization, org_id)
    return org.name if org else "your CA firm"
