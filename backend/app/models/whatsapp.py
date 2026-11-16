from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantScoped, Timestamps, UUIDPk
from app.models.client import Client
from app.models.enums import (
    ConversationStatus,
    HandoverState,
    TemplateCategory,
    TemplateStatus,
    WebhookStatus,
    WhatsAppAccountStatus,
)
from app.models.user import User


class WhatsAppAccount(UUIDPk, Timestamps, TenantScoped, Base):
    """A firm's WhatsApp Business phone number. Secrets are Fernet-encrypted at rest and never
    returned to the frontend."""

    __tablename__ = "whatsapp_accounts"

    provider: Mapped[str] = mapped_column(String(20), default="mock")
    display_phone_number: Mapped[str | None] = mapped_column(String(32))
    phone_number_id: Mapped[str] = mapped_column(String(64), unique=True)
    business_account_id: Mapped[str | None] = mapped_column(String(64))
    access_token_encrypted: Mapped[str | None] = mapped_column(Text)
    app_secret_encrypted: Mapped[str | None] = mapped_column(Text)
    api_version: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(20), default=WhatsAppAccountStatus.ACTIVE)
    last_error: Mapped[str | None] = mapped_column(Text)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WhatsAppContact(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "whatsapp_contacts"
    __table_args__ = (UniqueConstraint("organization_id", "wa_id"),)

    wa_id: Mapped[str] = mapped_column(String(32))
    phone: Mapped[str | None] = mapped_column(String(20))
    profile_name: Mapped[str | None] = mapped_column(String(200))
    client_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("clients.id", ondelete="SET NULL"), index=True)
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)

    client: Mapped[Client | None] = relationship(lazy="joined")


class Conversation(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("ix_conv_org_last", "organization_id", "last_message_at"),)

    contact_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("whatsapp_contacts.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("clients.id", ondelete="SET NULL"), index=True)
    status: Mapped[str] = mapped_column(String(20), default=ConversationStatus.OPEN)
    handover_state: Mapped[str] = mapped_column(String(32), default=HandoverState.BOT)
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_message_preview: Mapped[str | None] = mapped_column(String(255))
    unread_count: Mapped[int] = mapped_column(Integer, default=0)
    context: Mapped[dict[str, Any]] = mapped_column(default=lambda: {})
    handover_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    contact: Mapped[WhatsAppContact] = relationship(lazy="joined")
    client: Mapped[Client | None] = relationship(lazy="joined")
    assigned_agent: Mapped[User | None] = relationship(lazy="joined")


class Message(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_conv_ts", "conversation_id", "timestamp"),)

    conversation_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("conversations.id", ondelete="CASCADE"))
    provider_message_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    direction: Mapped[str] = mapped_column(String(10))
    message_type: Mapped[str] = mapped_column(String(20))
    sender: Mapped[str] = mapped_column(String(10))
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    recipient: Mapped[str | None] = mapped_column(String(32))
    body: Mapped[str | None] = mapped_column(Text)
    template_key: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))
    payload: Mapped[dict[str, Any]] = mapped_column(default=lambda: {})
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)
    error_code: Mapped[str | None] = mapped_column(String(32))
    attempts: Mapped[int] = mapped_column(Integer, default=0)


class MessageTemplate(UUIDPk, Timestamps, TenantScoped, Base):
    """Maps a ProDesk template key to a Meta-approved template name. Approval status is
    tracked explicitly — never assumed."""

    __tablename__ = "message_templates"
    __table_args__ = (UniqueConstraint("organization_id", "key"),)

    key: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(128))
    language: Mapped[str] = mapped_column(String(10), default="en")
    category: Mapped[str] = mapped_column(String(20), default=TemplateCategory.UTILITY)
    status: Mapped[str] = mapped_column(String(20), default=TemplateStatus.NOT_SUBMITTED)
    body_preview: Mapped[str] = mapped_column(Text, default="")
    variables: Mapped[list[Any]] = mapped_column(default=lambda: [])
    has_url_button: Mapped[bool] = mapped_column(Boolean, default=False)
    last_error: Mapped[str | None] = mapped_column(Text)


class WebhookEvent(UUIDPk, Timestamps, Base):
    """Raw inbound webhook events; (provider, event_key) is unique for idempotency."""

    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("provider", "event_key"), Index("ix_webhook_status", "status"))

    provider: Mapped[str] = mapped_column(String(20))
    event_key: Mapped[str] = mapped_column(String(200))
    event_type: Mapped[str] = mapped_column(String(40))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(default=lambda: {})
    status: Mapped[str] = mapped_column(String(20), default=WebhookStatus.RECEIVED)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
