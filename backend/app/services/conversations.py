"""WhatsApp inbox and human handover state machine.

    BOT → HUMAN_REQUESTED → AGENT_ASSIGNED → HUMAN_ACTIVE → BOT_RESUMED
While in a human state, the AI never auto-replies.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.errors import NotFound, ValidationFailed
from app.core.permissions import Perm
from app.core.security import now_utc
from app.models import Client, Conversation, Message, User, WhatsAppContact
from app.models.enums import HUMAN_MODES, ConversationStatus, HandoverState, MessageType
from app.repositories.base import paginate
from app.services import audit, messaging, notifications
from app.services.audit import AuditAction
from app.services.scope import visible_client_ids_subquery


def _scoped(principal: Principal) -> Select[Any]:
    principal.require(Perm.WHATSAPP_VIEW)
    stmt = select(Conversation).where(Conversation.organization_id == principal.org_id)
    if not principal.sees_all_clients:
        stmt = stmt.where(Conversation.client_id.in_(visible_client_ids_subquery(principal)))
    return stmt


def list_conversations(
    db: Session,
    principal: Principal,
    *,
    q: str | None = None,
    handover_state: str | None = None,
    unread_only: bool = False,
    status: str | None = None,
    page: int = 1,
    page_size: int = 30,
) -> tuple[list[Conversation], int]:
    stmt = _scoped(principal)
    if q:
        term = f"%{q[:100]}%"
        stmt = (
            stmt.join(WhatsAppContact, WhatsAppContact.id == Conversation.contact_id)
            .outerjoin(Client, Client.id == Conversation.client_id)
            .where(
                or_(
                    WhatsAppContact.profile_name.ilike(term),
                    WhatsAppContact.wa_id.ilike(term),
                    Client.name.ilike(term),
                    Conversation.last_message_preview.ilike(term),
                )
            )
        )
    if handover_state == "HUMAN":
        stmt = stmt.where(Conversation.handover_state.in_([s.value for s in HUMAN_MODES]))
    elif handover_state:
        stmt = stmt.where(Conversation.handover_state == handover_state)
    if unread_only:
        stmt = stmt.where(Conversation.unread_count > 0)
    if status:
        stmt = stmt.where(Conversation.status == status)
    stmt = stmt.order_by(Conversation.last_message_at.desc().nulls_last(), Conversation.id)
    rows, total = paginate(db, stmt, page, page_size)
    return list(rows), total


def get_conversation(db: Session, principal: Principal, conv_id: uuid.UUID) -> Conversation:
    conv = db.execute(_scoped(principal).where(Conversation.id == conv_id)).unique().scalar_one_or_none()
    if conv is None:
        raise NotFound("Conversation not found")
    return conv


def list_messages(
    db: Session, principal: Principal, conv_id: uuid.UUID, *, page: int = 1, page_size: int = 100
) -> tuple[list[Message], int]:
    conv = get_conversation(db, principal, conv_id)
    stmt = (
        select(Message)
        .where(Message.organization_id == principal.org_id, Message.conversation_id == conv.id)
        .order_by(Message.timestamp.desc(), Message.id)
    )
    rows, total = paginate(db, stmt, page, page_size)
    if conv.unread_count:
        conv.unread_count = 0
        db.commit()
    return list(reversed(list(rows))), total


def request_handover(db: Session, conv: Conversation, *, reason: str) -> None:
    if conv.handover_state in HUMAN_MODES:
        return
    conv.handover_state = HandoverState.HUMAN_REQUESTED
    conv.handover_requested_at = now_utc()
    client = db.get(Client, conv.client_id) if conv.client_id else None
    name = client.name if client else (conv.contact.profile_name or conv.contact.wa_id)
    notifications.notify_client_owner(
        db,
        conv.organization_id,
        client.assigned_employee_id if client else None,
        fallback_perm=Perm.WHATSAPP_SEND,
        type_="HUMAN_HANDOFF",
        title=f"{name} wants to talk to the team",
        body=reason[:300],
        link=f"/whatsapp?conversation={conv.id}",
    )
    audit.record(
        db,
        None,
        AuditAction.HANDOVER_CHANGED,
        resource="conversation",
        resource_id=conv.id,
        organization_id=conv.organization_id,
        client_id=conv.client_id,
        metadata={"to": conv.handover_state},
    )


def handover_action(db: Session, principal: Principal, conv_id: uuid.UUID, action: str, agent_id: uuid.UUID | None = None) -> Conversation:
    principal.require(Perm.WHATSAPP_SEND)
    conv = get_conversation(db, principal, conv_id)
    before = conv.handover_state
    if action == "take":
        conv.handover_state = HandoverState.AGENT_ASSIGNED
        conv.assigned_agent_id = principal.user_id
    elif action == "assign":
        if agent_id is None:
            raise ValidationFailed("agent_id is required")
        agent = (
            db.execute(select(User).where(User.id == agent_id, User.organization_id == principal.org_id, User.is_active.is_(True)))
            .unique()
            .scalar_one_or_none()
        )
        if agent is None:
            raise ValidationFailed("Agent not found")
        conv.handover_state = HandoverState.AGENT_ASSIGNED
        conv.assigned_agent_id = agent.id
        notifications.notify_users(
            db,
            principal.org_id,
            [agent.id],
            type_="CONVERSATION_ASSIGNED",
            title="A WhatsApp conversation was assigned to you",
            link=f"/whatsapp?conversation={conv.id}",
        )
    elif action == "resume_bot":
        conv.handover_state = HandoverState.BOT_RESUMED
        conv.assigned_agent_id = None
        if messaging.service_window_open(conv.contact):
            messaging.queue_message(
                db,
                principal.org_id,
                messaging.Outbound(
                    kind=MessageType.TEXT,
                    body='You\'re now chatting with the assistant again. Reply "CA se baat karni hai" anytime to reach the team.',
                ),
                conversation=conv,
            )
    elif action == "close":
        conv.status = ConversationStatus.CLOSED
        conv.handover_state = HandoverState.BOT
        conv.assigned_agent_id = None
    audit.record(
        db,
        principal,
        AuditAction.HANDOVER_CHANGED,
        resource="conversation",
        resource_id=conv.id,
        client_id=conv.client_id,
        metadata={"from": before, "to": conv.handover_state, "action": action},
    )
    db.commit()
    db.refresh(conv)
    return conv
