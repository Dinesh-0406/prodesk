"""Audit logs, notifications, reminder logs and background job records."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TenantScoped, Timestamps, UUIDPk
from app.models.enums import JobStatus, NotificationStatus


class AuditLog(UUIDPk, Base):
    """Append-only. Never stores passwords, tokens, or API secrets (metadata is redacted)."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_org_ts", "organization_id", "timestamp"),
        Index("ix_audit_resource", "resource", "resource_id"),
    )

    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    client_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("clients.id", ondelete="SET NULL"))
    actor_type: Mapped[str] = mapped_column(String(16))  # STAFF | CLIENT | SYSTEM
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource: Mapped[str | None] = mapped_column(String(64))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ip: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(64))
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", default=lambda: {})


class Notification(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "notifications"
    __table_args__ = (Index("ix_notif_user_status", "user_id", "status"),)

    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    client_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("clients.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(16))
    type: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), default=NotificationStatus.PENDING)
    data: Mapped[dict[str, Any]] = mapped_column(default=lambda: {})
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class ReminderLog(UUIDPk, Timestamps, TenantScoped, Base):
    """One row per reminder sent; `dedupe_key` prevents duplicate reminders for the same slot."""

    __tablename__ = "reminder_logs"
    __table_args__ = (UniqueConstraint("organization_id", "dedupe_key"),)

    kind: Mapped[str] = mapped_column(String(40))
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    client_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("clients.id", ondelete="CASCADE"))
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    channel: Mapped[str] = mapped_column(String(16))
    dedupe_key: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16))
    detail: Mapped[str | None] = mapped_column(Text)


class BackgroundJob(UUIDPk, Timestamps, Base):
    __tablename__ = "background_jobs"
    __table_args__ = (Index("ix_jobs_status", "status"),)

    task_id: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default=JobStatus.QUEUED)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
