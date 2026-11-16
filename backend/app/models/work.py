"""Tasks, document requests, compliance events and support requests."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantScoped, Timestamps, UUIDPk
from app.models.client import Client
from app.models.enums import (
    DocumentRequestStatus,
    RequestItemStatus,
    ServiceType,
    SupportRequestStatus,
    TaskPriority,
    TaskStatus,
)
from app.models.user import User


class Task(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "tasks"
    __table_args__ = (
        Index("ix_tasks_org_status_due", "organization_id", "status", "due_date"),
        Index("ix_tasks_org_assignee", "organization_id", "assigned_employee_id"),
        Index("ix_tasks_org_client", "organization_id", "client_id"),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("clients.id", ondelete="CASCADE"))
    assigned_employee_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    service_type: Mapped[str] = mapped_column(String(32), default=ServiceType.OTHER)
    financial_year: Mapped[str | None] = mapped_column(String(9))
    priority: Mapped[str] = mapped_column(String(16), default=TaskPriority.MEDIUM)
    status: Mapped[str] = mapped_column(String(32), default=TaskStatus.NEW_REQUEST)
    due_date: Mapped[date | None] = mapped_column(Date)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    filed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    filing_reference: Mapped[str | None] = mapped_column(String(100))

    client: Mapped[Client] = relationship(lazy="joined")
    assigned_employee: Mapped[User | None] = relationship(foreign_keys=[assigned_employee_id], lazy="joined")


class DocumentRequest(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "document_requests"
    __table_args__ = (Index("ix_docreq_org_status", "organization_id", "status"),)

    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(255))
    instructions: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default=DocumentRequestStatus.PENDING)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    reminders_sent: Mapped[int] = mapped_column(Integer, default=0)
    last_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    client: Mapped[Client] = relationship(lazy="joined")
    items: Mapped[list[DocumentRequestItem]] = relationship(
        back_populates="request", lazy="selectin", order_by="DocumentRequestItem.position", cascade="all, delete-orphan"
    )


class DocumentRequestItem(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "document_request_items"

    request_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("document_requests.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    document_type: Mapped[str | None] = mapped_column(String(40))
    is_required: Mapped[bool] = mapped_column(Boolean, default=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=RequestItemStatus.PENDING)
    document_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("documents.id", ondelete="SET NULL"))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    request: Mapped[DocumentRequest] = relationship(back_populates="items")


class ComplianceEvent(UUIDPk, Timestamps, TenantScoped, Base):
    """A compliance deadline. Never invented by the system: always admin-configured or from
    a verified/official source, with the source recorded."""

    __tablename__ = "compliance_events"
    __table_args__ = (Index("ix_compliance_org_due", "organization_id", "due_date"),)

    category: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[date] = mapped_column(Date)
    period: Mapped[str | None] = mapped_column(String(32))  # e.g. "Oct-2026", "FY2025-26"
    source: Mapped[str] = mapped_column(String(32))
    source_reference: Mapped[str | None] = mapped_column(String(500))
    verified_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    applies_to_client_types: Mapped[list[Any]] = mapped_column(default=lambda: [])
    client_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("clients.id", ondelete="CASCADE"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    reminder_days_before: Mapped[int] = mapped_column(Integer, default=3)


class SupportRequest(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "support_requests"

    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("conversations.id", ondelete="SET NULL"))
    request_type: Mapped[str] = mapped_column(String(32))
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default=SupportRequestStatus.OPEN)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    client: Mapped[Client] = relationship(lazy="joined")
