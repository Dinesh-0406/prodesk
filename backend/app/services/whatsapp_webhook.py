"""WhatsApp Cloud API webhook: verify → parse → persist (idempotent) → queue → return 200.

Processing (AI, media download, replies) always happens in a worker, never in the HTTP
request. Duplicate deliveries (Meta retries, replays) hit the unique (provider, event_key)
constraint and are dropped; message rows are also unique on provider_message_id.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import client_principal, system_principal
from app.core.errors import AppError, Unauthorized
from app.core.logging import get_logger
from app.core.phone import from_wa_id
from app.core.security import now_utc
from app.integrations.whatsapp import app_secret_for, get_whatsapp_provider, verify_meta_signature
from app.integrations.whatsapp.base import sign_meta_payload
from app.models import Client, Conversation, Message, Organization, WebhookEvent, WhatsAppAccount
from app.models.enums import (
    HUMAN_MODES,
    ClientStatus,
    DocumentSource,
    MessageDirection,
    MessageSender,
    MessageStatus,
    MessageType,
    WebhookStatus,
)
from app.services import audit, messaging, notifications
from app.services.audit import AuditAction

log = get_logger("whatsapp.webhook")
STOP_WORDS = {"stop", "unsubscribe", "opt out", "optout", "band karo"}
START_WORDS = {"start", "subscribe", "opt in", "optin"}


def _account_for_phone_number_id(db: Session, phone_number_id: str | None) -> WhatsAppAccount | None:
    if not phone_number_id:
        return None
    return db.execute(select(WhatsAppAccount).where(WhatsAppAccount.phone_number_id == phone_number_id)).scalar_one_or_none()


def verify_request(db: Session, body: bytes, signature: str | None) -> dict[str, Any]:
    """Validate the X-Hub-Signature-256 header. Tries the platform app secret first, then the
    per-tenant app secret of the account named in the payload (for firms using their own Meta app)."""
    if settings.WHATSAPP_APP_SECRET and verify_meta_signature(settings.WHATSAPP_APP_SECRET, body, signature):
        return json.loads(body)
    try:
        data = json.loads(body)
    except ValueError:
        raise Unauthorized("Invalid webhook", code="INVALID_SIGNATURE") from None
    for entry in data.get("entry", []) if isinstance(data, dict) else []:
        for change in entry.get("changes", []):
            pnid = (change.get("value", {}).get("metadata") or {}).get("phone_number_id")
            acc = _account_for_phone_number_id(db, pnid)
            secret = app_secret_for(acc) if acc and acc.app_secret_encrypted else ""
            if secret and verify_meta_signature(secret, body, signature):
                return data  # type: ignore[no-any-return]
    raise Unauthorized("Invalid webhook signature", code="INVALID_SIGNATURE")


def ingest(db: Session, data: dict[str, Any]) -> list[uuid.UUID]:
    """Persist one event per message/status. Returns IDs of NEW events to process."""
    if data.get("object") != "whatsapp_business_account":
        return []
    new_ids: list[uuid.UUID] = []
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            if change.get("field") != "messages":
                continue
            value = change.get("value", {})
            pnid = (value.get("metadata") or {}).get("phone_number_id")
            acc = _account_for_phone_number_id(db, pnid)
            org_id = acc.organization_id if acc else None
            contacts = value.get("contacts", [])
            for m in value.get("messages", []):
                ev = {"phone_number_id": pnid, "message": m, "contacts": contacts}
                new_ids += _insert_event(db, f"msg:{m.get('id')}", "message", org_id, ev)
            for s in value.get("statuses", []):
                ev = {"phone_number_id": pnid, "status": s}
                new_ids += _insert_event(db, f"status:{s.get('id')}:{s.get('status')}", "status", org_id, ev)
            for e in value.get("errors", []):
                log.warning("whatsapp_webhook_error_payload", extra={"wa_error_code": e.get("code")})
    db.commit()
    return new_ids


def _insert_event(db: Session, key: str, event_type: str, org_id: uuid.UUID | None, payload: dict[str, Any]) -> list[uuid.UUID]:
    eid = uuid.uuid4()
    stmt = (
        pg_insert(WebhookEvent)
        .values(
            id=eid,
            provider="whatsapp",
            event_key=key[:200],
            event_type=event_type,
            organization_id=org_id,
            payload=payload,
            status=WebhookStatus.RECEIVED if org_id else WebhookStatus.IGNORED,
            attempts=0,
        )
        .on_conflict_do_nothing(index_elements=["provider", "event_key"])
        .returning(WebhookEvent.id)
    )
    row = db.execute(stmt).first()
    if row is None:
        log.info("webhook_duplicate_ignored", extra={"event_key": key[:60]})
        return []
    if org_id is None:
        log.warning("webhook_unknown_phone_number_id")
        return []
    return [row[0]]


def process_event(db: Session, event_id: uuid.UUID) -> None:
    ev = db.execute(select(WebhookEvent).where(WebhookEvent.id == event_id).with_for_update(skip_locked=True)).scalar_one_or_none()
    if ev is None or ev.status in (WebhookStatus.PROCESSED, WebhookStatus.IGNORED):
        return
    ev.status = WebhookStatus.PROCESSING
    ev.attempts += 1
    db.commit()
    try:
        acc = _account_for_phone_number_id(db, ev.payload.get("phone_number_id"))
        if acc is None or ev.organization_id is None:
            ev.status = WebhookStatus.IGNORED
        elif ev.event_type == "message":
            _handle_inbound(db, acc, ev.payload["message"], ev.payload.get("contacts", []))
            ev.status = WebhookStatus.PROCESSED
        elif ev.event_type == "status":
            s = ev.payload["status"]
            ts = datetime.fromtimestamp(int(s.get("timestamp", now_utc().timestamp())), tz=UTC)
            messaging.apply_status_update(db, acc.organization_id, s.get("id", ""), s.get("status", ""), ts, s.get("errors"))
            ev.status = WebhookStatus.PROCESSED
        ev.processed_at = now_utc()
        ev.error = None
        db.commit()
    except Exception as e:
        db.rollback()
        ev = db.get(WebhookEvent, event_id)
        if ev:
            ev.status = WebhookStatus.FAILED
            ev.error = f"{type(e).__name__}: {str(e)[:500]}"
            db.commit()
        raise


def _text_of(m: dict[str, Any]) -> tuple[MessageType, str | None]:
    t = m.get("type")
    if t == "text":
        return MessageType.TEXT, (m.get("text") or {}).get("body")
    if t == "button":
        return MessageType.BUTTON, (m.get("button") or {}).get("text")
    if t == "interactive":
        i = m.get("interactive") or {}
        reply = i.get("button_reply") or i.get("list_reply") or {}
        return MessageType.INTERACTIVE, reply.get("title")
    if t == "document":
        return MessageType.DOCUMENT, (m.get("document") or {}).get("caption")
    if t == "image":
        return MessageType.IMAGE, (m.get("image") or {}).get("caption")
    return MessageType.UNSUPPORTED, None


def _handle_inbound(db: Session, acc: WhatsAppAccount, m: dict[str, Any], contacts: list[dict[str, Any]]) -> None:
    org_id = acc.organization_id
    pmid = m.get("id")
    if pmid and db.execute(select(Message.id).where(Message.provider_message_id == pmid)).first():
        return  # idempotent
    wa_id = str(m.get("from", ""))
    phone = from_wa_id(wa_id)
    client = None
    if phone:
        client = (
            db.execute(
                select(Client).where(Client.organization_id == org_id, Client.phone == phone, Client.status != ClientStatus.ARCHIVED)
            )
            .unique()
            .scalar_one_or_none()
        )
    profile = next((c.get("profile", {}).get("name") for c in contacts if c.get("wa_id") == wa_id), None)
    contact = messaging.get_or_create_contact(db, org_id, wa_id, phone=phone, client=client, profile_name=profile)
    ts = datetime.fromtimestamp(int(m.get("timestamp", now_utc().timestamp())), tz=UTC)
    contact.last_inbound_at = max(contact.last_inbound_at or ts, ts)
    conv = messaging.get_or_create_conversation(db, org_id, contact)
    mtype, text = _text_of(m)
    msg = Message(
        organization_id=org_id,
        conversation_id=conv.id,
        provider_message_id=pmid,
        direction=MessageDirection.INBOUND,
        message_type=mtype,
        sender=MessageSender.CLIENT,
        recipient=acc.phone_number_id,
        body=text,
        status=MessageStatus.RECEIVED,
        payload={k: m.get(k) for k in ("type", "document", "image", "context") if m.get(k) is not None},
        timestamp=ts,
    )
    db.add(msg)
    db.flush()
    conv.last_message_at = ts
    conv.last_message_preview = (text or f"[{mtype.value.lower()}]")[:255]
    conv.unread_count += 1
    audit.record(
        db,
        system_principal(org_id),
        AuditAction.WHATSAPP_RECEIVED,
        resource="message",
        resource_id=msg.id,
        client_id=client.id if client else None,
        metadata={"type": mtype.value, "identified": client is not None},
    )
    from app.workers.dispatch import enqueue_on_commit

    if pmid:
        enqueue_on_commit(db, "whatsapp.mark_read", org_id=str(org_id), provider_message_id=pmid)

    normalized = (text or "").strip().lower()
    if normalized in STOP_WORDS:
        _opt_out(db, org_id, contact, client, conv)
        return
    if normalized in START_WORDS and client is not None:
        _opt_in(db, org_id, client, conv)
        return

    if conv.handover_state in HUMAN_MODES:
        target = [conv.assigned_agent_id] if conv.assigned_agent_id else None
        if target:
            notifications.notify_users(
                db,
                org_id,
                target,
                type_="WHATSAPP_MESSAGE",  # type: ignore[arg-type]
                title=f"New message from {client.name if client else wa_id}",
                body=(text or "")[:200],
                link=f"/whatsapp?conversation={conv.id}",
            )
        return  # AI must not auto-reply while a human is handling the chat

    org = db.get(Organization, org_id)
    assert org is not None
    if client is None:
        _reply(
            db,
            org_id,
            conv,
            f"Hello! This number is not registered with {org.name}. Please contact the office to link your WhatsApp number.",
        )
        return

    if mtype in (MessageType.DOCUMENT, MessageType.IMAGE):
        _intake_media(db, org, client, conv, m, mtype, text)
        return
    if mtype == MessageType.UNSUPPORTED:
        _reply(db, org_id, conv, "Sorry, I can only read text messages and documents (PDF, images, Word, Excel).")
        return

    from app.services.assistant.client_assistant import handle_client_message
    from app.services.conversations import request_handover

    reply = handle_client_message(db, org=org, client=client, conversation=conv, text=text or "")
    if reply.handoff:
        request_handover(db, conv, reason=text or "Client requested a human")
    if conv.handover_state == "BOT_RESUMED":
        conv.handover_state = "BOT"
    out = _reply(db, org_id, conv, reply.text, preview_url="http" in reply.text)
    if reply.delivery is not None:
        reply.delivery.message_id = out.id  # delivery timestamps follow this message's status webhooks


def _reply(db: Session, org_id: uuid.UUID, conv: Conversation, text: str, *, preview_url: bool = False) -> Message:
    msg = messaging.queue_message(
        db, org_id, messaging.Outbound(kind=MessageType.TEXT, body=text), conversation=conv, sender=MessageSender.BOT
    )
    if preview_url:
        msg.payload = {**msg.payload, "preview_url": True}
    return msg


def _opt_out(db: Session, org_id: uuid.UUID, contact: Any, client: Client | None, conv: Conversation) -> None:
    from app.services.clients import _set_opt_in

    _reply(db, org_id, conv, "You've been unsubscribed from WhatsApp updates. Reply START to subscribe again.")
    contact.opted_out = True
    if client is not None:
        _set_opt_in(db, client_principal(org_id, client.id), client, False, channel="WHATSAPP", evidence="Client sent STOP")


def _opt_in(db: Session, org_id: uuid.UUID, client: Client, conv: Conversation) -> None:
    from app.services.clients import _set_opt_in

    conv.contact.opted_out = False
    _set_opt_in(db, client_principal(org_id, client.id), client, True, channel="WHATSAPP", evidence="Client sent START")
    _reply(db, org_id, conv, "You're subscribed to WhatsApp updates again. Reply STOP anytime to opt out.")


def _intake_media(
    db: Session, org: Organization, client: Client, conv: Conversation, m: dict[str, Any], mtype: MessageType, caption: str | None
) -> None:
    from app.services import document_requests as dr
    from app.services.documents import upload_document

    media = m.get("document") if mtype == MessageType.DOCUMENT else m.get("image")
    media = media or {}
    account = messaging.get_account(db, org.id)
    try:
        dl = get_whatsapp_provider(account).download_media(str(media.get("id")))
        fname = media.get("filename") or dl.file_name or ("photo.jpg" if mtype == MessageType.IMAGE else "document.pdf")
        principal = client_principal(org.id, client.id)
        doc = upload_document(
            db,
            principal,
            client_id=client.id,
            file_name=fname,
            content=dl.content,
            description=(caption or "Received on WhatsApp")[:500],
            source=DocumentSource.WHATSAPP,
            commit=False,
        )
    except AppError as e:
        _reply(db, org.id, conv, f"Sorry, I couldn't accept that file: {e.message}")
        return
    attached = None
    for req in dr.open_requests_for_client(db, org.id, client.id):
        attached = dr.attach_document(db, req, doc)
        if attached:
            remaining = dr.pending_item_names(req)
            text = f'Received "{doc.file_name}" for {req.title} ({attached.name}). Thank you!'
            text += (" Still pending: " + ", ".join(remaining)) if remaining else " All requested documents are now received."
            _reply(db, org.id, conv, text)
            break
    if not attached:
        _reply(db, org.id, conv, f'Received "{doc.file_name}". Your CA team has been notified. Thank you!')
        notifications.notify_client_owner(
            db,
            org.id,
            client.assigned_employee_id,
            type_="CLIENT_UPLOAD",
            title=f"{client.name} sent a document on WhatsApp",
            body=doc.file_name,
            link=f"/documents/{doc.id}",
        )
    conv.context = {k: v for k, v in (conv.context or {}).items() if k != "awaiting_upload"}


# --- Dev simulator (mock provider only) ---------------------------------------------


def build_simulated_payload(
    phone_number_id: str,
    wa_id: str,
    *,
    text: str | None,
    profile_name: str | None,
    media: tuple[bytes, str, str | None] | None,
    caption: str | None,
) -> bytes:
    msg: dict[str, Any] = {"from": wa_id, "id": f"wamid.SIM{uuid.uuid4().hex}", "timestamp": str(int(now_utc().timestamp()))}
    if media:
        from app.integrations.whatsapp.mock import store_mock_media

        content, mime, name = media
        media_id = store_mock_media(content, mime, name)
        if mime.startswith("image/"):
            msg.update(type="image", image={"id": media_id, "mime_type": mime, "caption": caption})
        else:
            msg.update(type="document", document={"id": media_id, "mime_type": mime, "filename": name, "caption": caption})
    else:
        msg.update(type="text", text={"body": text or ""})
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "SIMULATED",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "SIM", "phone_number_id": phone_number_id},
                            "contacts": [{"profile": {"name": profile_name or "Client"}, "wa_id": wa_id}],
                            "messages": [msg],
                        },
                    }
                ],
            }
        ],
    }
    return json.dumps(payload).encode()


def simulated_signature(body: bytes) -> str:
    return sign_meta_payload(settings.WHATSAPP_APP_SECRET or "dev-only", body)


def decode_media(b64: str) -> bytes:
    return base64.b64decode(b64, validate=True)
