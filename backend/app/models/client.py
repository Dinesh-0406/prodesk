from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantScoped, Timestamps, UUIDPk
from app.models.enums import ClientStatus, ClientType
from app.models.user import User


class Client(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "clients"
    __table_args__ = (
        UniqueConstraint("organization_id", "phone"),
        Index("ix_clients_org_status", "organization_id", "status"),
        Index("ix_clients_org_assigned", "organization_id", "assigned_employee_id"),
    )

    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(Text)
    client_type: Mapped[str] = mapped_column(String(32), default=ClientType.INDIVIDUAL)
    pan: Mapped[str | None] = mapped_column(String(10), index=True)
    gstin: Mapped[str | None] = mapped_column(String(15))
    assigned_employee_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), default=ClientStatus.ACTIVE)
    notes: Mapped[str | None] = mapped_column(Text)
    whatsapp_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)
    whatsapp_opt_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    whatsapp_opt_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminders_opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    assigned_employee: Mapped[User | None] = relationship(lazy="joined")

    @property
    def can_receive_whatsapp(self) -> bool:
        return self.whatsapp_opt_in and self.whatsapp_opt_out_at is None and self.status != ClientStatus.ARCHIVED


class ClientOtp(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "client_otps"

    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    code_hash: Mapped[str] = mapped_column(String(128))
    purpose: Mapped[str] = mapped_column(String(32), default="PORTAL_LOGIN")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConsentRecord(UUIDPk, Timestamps, TenantScoped, Base):
    """Notice/consent ledger (append-only) to support privacy obligations."""

    __tablename__ = "consent_records"

    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(64))  # e.g. WHATSAPP_COMMUNICATION, DOCUMENT_PROCESSING
    granted: Mapped[bool] = mapped_column(Boolean)
    channel: Mapped[str] = mapped_column(String(32))  # STAFF_RECORDED, WHATSAPP, PORTAL
    notice_version: Mapped[str] = mapped_column(String(32))
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    evidence: Mapped[str | None] = mapped_column(Text)
