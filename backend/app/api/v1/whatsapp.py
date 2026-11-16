"""WhatsApp: webhook (Meta), account settings, templates, inbox/conversations, dev simulator."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import PlainTextResponse

from app.api.deps import DB, Staff
from app.core.config import settings
from app.core.errors import Forbidden, NotFound, ValidationFailed
from app.core.logging import get_logger
from app.core.permissions import Perm
from app.core.phone import normalize_indian_phone, to_wa_id
from app.core.rate_limit import client_ip, limiter
from app.core.security import constant_time_equals
from app.models import Client
from app.models.enums import MessageType
from app.schemas.common import Page
from app.schemas.messaging import (
    AgentReply,
    ConversationOut,
    HandoverAction,
    MessageOut,
    SendTemplateRequest,
    SimulateInbound,
)
from app.schemas.org import TemplateOut, TemplateUpdate, WhatsAppAccountOut, WhatsAppAccountUpdate
from app.services import audit, conversations, messaging, orgs
from app.services import whatsapp_webhook as wh
from app.services.audit import AuditAction
from app.services.scope import get_visible_client
from app.workers.dispatch import enqueue

log = get_logger("whatsapp.api")
webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])
router = APIRouter(tags=["whatsapp"])


@webhook_router.get("/whatsapp", response_class=PlainTextResponse)
def verify_webhook(
    hub_mode: str = Query("", alias="hub.mode"),
    hub_verify_token: str = Query("", alias="hub.verify_token"),
    hub_challenge: str = Query("", alias="hub.challenge"),
) -> str:
    """Meta webhook verification handshake."""
    if (
        hub_mode == "subscribe"
        and settings.WHATSAPP_VERIFY_TOKEN
        and constant_time_equals(hub_verify_token, settings.WHATSAPP_VERIFY_TOKEN)
    ):
        return hub_challenge
    raise Forbidden("Verification failed")


@webhook_router.post("/whatsapp", dependencies=[Depends(limiter("wh_whatsapp", 3000, 60))])
async def receive_webhook(request: Request, db: DB) -> dict[str, Any]:
    """Validate signature, persist events idempotently, queue processing, return immediately."""
    body = await request.body()
    if len(body) > 1_000_000:
        raise ValidationFailed("Payload too large")
    try:
        data = wh.verify_request(db, body, request.headers.get("x-hub-signature-256"))
    except Exception:
        audit.record(db, None, AuditAction.WEBHOOK_REJECTED, resource="webhook", ip=client_ip(request), metadata={"provider": "whatsapp"})
        db.commit()
        log.warning("whatsapp_webhook_rejected")
        raise
    ids = wh.ingest(db, data)
    for eid in ids:
        enqueue("webhooks.process_whatsapp", event_id=str(eid))
    log.info("whatsapp_webhook_accepted", extra={"new_events": len(ids)})
    return {"status": "ok", "accepted": len(ids)}


# --- settings ------------------------------------------------------------------------


@router.get("/whatsapp/account", response_model=WhatsAppAccountOut)
def get_account(principal: Staff, db: DB) -> WhatsAppAccountOut:
    principal.require(Perm.WHATSAPP_VIEW)
    return orgs.whatsapp_account_out(orgs.get_whatsapp_account(db, principal.org_id))


@router.put("/whatsapp/account", response_model=WhatsAppAccountOut)
def put_account(body: WhatsAppAccountUpdate, principal: Staff, db: DB) -> WhatsAppAccountOut:
    return orgs.whatsapp_account_out(orgs.upsert_whatsapp_account(db, principal, body))


@router.post("/whatsapp/account/verify", response_model=WhatsAppAccountOut)
def verify_account(principal: Staff, db: DB) -> WhatsAppAccountOut:
    return orgs.whatsapp_account_out(orgs.verify_whatsapp_account(db, principal))


@router.get("/whatsapp/templates", response_model=list[TemplateOut])
def list_templates(principal: Staff, db: DB) -> list[TemplateOut]:
    return [TemplateOut.model_validate(t) for t in orgs.list_templates(db, principal)]


@router.patch("/whatsapp/templates/{template_id}", response_model=TemplateOut)
def update_template(template_id: uuid.UUID, body: TemplateUpdate, principal: Staff, db: DB) -> TemplateOut:
    return TemplateOut.model_validate(orgs.update_template(db, principal, template_id, body))


@router.post("/whatsapp/templates/sync", response_model=list[TemplateOut])
def sync_templates(principal: Staff, db: DB) -> list[TemplateOut]:
    return [TemplateOut.model_validate(t) for t in orgs.sync_templates_from_meta(db, principal)]


@router.post("/whatsapp/send-template", response_model=MessageOut, dependencies=[Depends(limiter("wa_send", 60, 60))])
def send_template(body: SendTemplateRequest, principal: Staff, db: DB) -> MessageOut:
    from app.models.enums import TemplateKey

    principal.require(Perm.WHATSAPP_SEND)
    client = get_visible_client(db, principal, body.client_id)
    try:
        key = TemplateKey(body.template_key)
    except ValueError:
        raise ValidationFailed("Unknown template") from None
    if key == TemplateKey.OTP:
        raise ValidationFailed("OTP template cannot be sent manually")
    msg = messaging.send_template_to_client(db, client, key, body.body_params)
    db.commit()
    return MessageOut.model_validate(msg)


# --- inbox ---------------------------------------------------------------------------


def _conv_out(c: Any) -> ConversationOut:
    out = ConversationOut.model_validate(c)
    out.service_window_open = messaging.service_window_open(c.contact)
    return out


@router.get("/conversations", response_model=Page[ConversationOut])
def list_conversations(
    principal: Staff,
    db: DB,
    q: str | None = None,
    handover_state: str | None = None,
    unread_only: bool = False,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
) -> Page[ConversationOut]:
    rows, total = conversations.list_conversations(
        db, principal, q=q, handover_state=handover_state, unread_only=unread_only, status=status, page=page, page_size=page_size
    )
    return Page(items=[_conv_out(c) for c in rows], total=total, page=page, page_size=page_size)


@router.get("/conversations/{conv_id}", response_model=ConversationOut)
def get_conversation(conv_id: uuid.UUID, principal: Staff, db: DB) -> ConversationOut:
    return _conv_out(conversations.get_conversation(db, principal, conv_id))


@router.get("/conversations/{conv_id}/messages", response_model=Page[MessageOut])
def list_messages(
    conv_id: uuid.UUID, principal: Staff, db: DB, page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=200)
) -> Page[MessageOut]:
    rows, total = conversations.list_messages(db, principal, conv_id, page=page, page_size=page_size)
    items = []
    for m in rows:
        o = MessageOut.model_validate(m)
        if (m.payload or {}).get("sensitive"):
            o.payload = {"sensitive": True}
        items.append(o)
    return Page(items=items, total=total, page=page, page_size=page_size)


@router.post("/conversations/{conv_id}/messages", response_model=MessageOut, status_code=201)
def reply(conv_id: uuid.UUID, body: AgentReply, principal: Staff, db: DB) -> MessageOut:
    conv = conversations.get_conversation(db, principal, conv_id)
    msg = messaging.agent_reply(db, principal, conv, body.body)
    if msg.status == "FAILED":
        raise ValidationFailed(msg.error or "Message could not be sent", code=msg.error_code or "SEND_FAILED")
    return MessageOut.model_validate(msg)


@router.post("/conversations/{conv_id}/handover", response_model=ConversationOut)
def handover(conv_id: uuid.UUID, body: HandoverAction, principal: Staff, db: DB) -> ConversationOut:
    return _conv_out(conversations.handover_action(db, principal, conv_id, body.action, body.agent_id))


# --- dev simulator -------------------------------------------------------------------


@router.post("/whatsapp/simulate/inbound", status_code=202)
def simulate_inbound(body: SimulateInbound, principal: Staff, db: DB) -> dict[str, Any]:
    """Development only (mock provider): simulate a client sending a WhatsApp message.
    Goes through the exact same signed-webhook → queue → worker pipeline."""
    if not settings.dev_tools_enabled or settings.WHATSAPP_PROVIDER != "mock":
        raise NotFound("Not available")
    principal.require(Perm.WHATSAPP_SEND)
    acc = orgs.get_whatsapp_account(db, principal.org_id)
    if acc is None:
        raise ValidationFailed("Configure a (mock) WhatsApp account in Settings first")
    phone = normalize_indian_phone(body.phone)
    media = None
    if body.media_base64:
        media = (wh.decode_media(body.media_base64), body.media_mime or "application/pdf", body.media_filename)
    profile = body.profile_name
    if profile is None:
        from sqlalchemy import select

        c = (
            db.execute(select(Client).where(Client.organization_id == principal.org_id, Client.phone == phone))
            .unique()
            .scalar_one_or_none()
        )
        profile = c.name if c else "Unknown"
    raw = wh.build_simulated_payload(
        acc.phone_number_id, to_wa_id(phone), text=body.text, profile_name=profile, media=media, caption=body.caption
    )
    # Sign exactly like Meta would, so the simulator exercises the real verification path.
    data = wh.verify_request(db, raw, wh.simulated_signature(raw)) if settings.WHATSAPP_APP_SECRET else json.loads(raw)
    ids = wh.ingest(db, data)
    for eid in ids:
        enqueue("webhooks.process_whatsapp", event_id=str(eid))
    return {"status": "accepted", "events": len(ids)}


@router.get("/whatsapp/message-types")
def message_types(_: Staff) -> list[str]:
    return [t.value for t in MessageType]
