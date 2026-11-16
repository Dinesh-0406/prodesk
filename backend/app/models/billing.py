from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TenantScoped, Timestamps, UUIDPk
from app.models.client import Client
from app.models.enums import InvoiceStatus, PaymentAttemptStatus, PaymentStatus

Money = Numeric(14, 2)


class Invoice(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        UniqueConstraint("organization_id", "invoice_number"),
        Index("ix_invoices_org_status_due", "organization_id", "status", "due_date"),
    )

    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("tasks.id", ondelete="SET NULL"))
    invoice_number: Mapped[str] = mapped_column(String(40))
    issue_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date)
    subtotal: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    tax: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    amount_paid: Mapped[Decimal] = mapped_column(Money, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(20), default=InvoiceStatus.DRAFT)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reminders_sent: Mapped[int] = mapped_column(default=0)
    last_reminder_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    payment_link_url: Mapped[str | None] = mapped_column(String(500))

    client: Mapped[Client] = relationship(lazy="joined")
    items: Mapped[list[InvoiceItem]] = relationship(back_populates="invoice", lazy="selectin", cascade="all, delete-orphan")

    @property
    def balance_due(self) -> Decimal:
        return (self.total or Decimal("0")) - (self.amount_paid or Decimal("0"))


class InvoiceItem(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "invoice_items"

    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    description: Mapped[str] = mapped_column(String(255))
    sac_code: Mapped[str | None] = mapped_column(String(10))
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("1"))
    unit_price: Mapped[Decimal] = mapped_column(Money)
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"))
    amount: Mapped[Decimal] = mapped_column(Money)
    tax_amount: Mapped[Decimal] = mapped_column(Money)

    invoice: Mapped[Invoice] = relationship(back_populates="items")


class PaymentAttempt(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "payment_attempts"

    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("clients.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(20))
    provider_order_id: Mapped[str] = mapped_column(String(100), unique=True)
    amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(20), default=PaymentAttemptStatus.CREATED)
    raw: Mapped[dict[str, Any]] = mapped_column(default=lambda: {})


class Payment(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "payments"

    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("invoices.id", ondelete="CASCADE"), index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("clients.id", ondelete="CASCADE"), index=True)
    attempt_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("payment_attempts.id", ondelete="SET NULL"))
    provider: Mapped[str] = mapped_column(String(20))
    provider_payment_id: Mapped[str] = mapped_column(String(100), unique=True)
    provider_order_id: Mapped[str | None] = mapped_column(String(100))
    amount: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    method: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default=PaymentStatus.CAPTURED)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_via: Mapped[str] = mapped_column(String(20))  # SIGNATURE | WEBHOOK | RECONCILIATION | MANUAL
    recorded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))
    raw: Mapped[dict[str, Any]] = mapped_column(default=lambda: {})

    client: Mapped[Client] = relationship(lazy="joined")


class Receipt(UUIDPk, Timestamps, TenantScoped, Base):
    __tablename__ = "receipts"
    __table_args__ = (UniqueConstraint("organization_id", "receipt_number"),)

    payment_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("payments.id", ondelete="CASCADE"), unique=True)
    invoice_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("invoices.id", ondelete="CASCADE"))
    receipt_number: Mapped[str] = mapped_column(String(40))
    amount: Mapped[Decimal] = mapped_column(Money)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
