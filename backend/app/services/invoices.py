"""Invoices: creation with GST line items, sending, overdue tracking, cancellation."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import Select, or_, select, update
from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.errors import NotFound, ValidationFailed
from app.core.permissions import Perm
from app.core.security import now_utc
from app.models import Client, Invoice, InvoiceItem, Organization, Task
from app.models.enums import InvoiceStatus, TemplateKey
from app.repositories.base import paginate
from app.schemas.billing import InvoiceCreate
from app.services import audit, messaging
from app.services.audit import AuditAction
from app.services.scope import get_visible_client, scope_by_client

CENT = Decimal("0.01")
OPEN = [InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]


def q2(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


def _scoped(principal: Principal) -> Select[Any]:
    stmt = scope_by_client(select(Invoice), Invoice, principal)
    if principal.is_client:
        stmt = stmt.where(Invoice.status != InvoiceStatus.DRAFT)
    return stmt


def get_invoice(db: Session, principal: Principal, invoice_id: uuid.UUID, *, for_update: bool = False) -> Invoice:
    if principal.is_staff:
        principal.require(Perm.INVOICE_VIEW)
    stmt = _scoped(principal).where(Invoice.id == invoice_id)
    if for_update:
        stmt = stmt.with_for_update(of=Invoice)
    inv = db.execute(stmt).unique().scalar_one_or_none()
    if inv is None:
        raise NotFound("Invoice not found")
    return inv


def list_invoices(
    db: Session,
    principal: Principal,
    *,
    status: str | None = None,
    client_id: uuid.UUID | None = None,
    q: str | None = None,
    open_only: bool = False,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Invoice], int]:
    if principal.is_staff:
        principal.require(Perm.INVOICE_VIEW)
    stmt = _scoped(principal)
    if status:
        stmt = stmt.where(Invoice.status == status)
    if open_only:
        stmt = stmt.where(Invoice.status.in_(OPEN))
    if client_id:
        stmt = stmt.where(Invoice.client_id == client_id)
    if q:
        stmt = stmt.join(Client, Client.id == Invoice.client_id).where(
            or_(Invoice.invoice_number.ilike(f"%{q[:50]}%"), Client.name.ilike(f"%{q[:100]}%"))
        )
    stmt = stmt.order_by(Invoice.issue_date.desc(), Invoice.invoice_number.desc())
    rows, total = paginate(db, stmt, page, page_size)
    return list(rows), total


def _next_number(db: Session, org: Organization) -> str:
    org_locked = db.execute(select(Organization).where(Organization.id == org.id).with_for_update()).scalar_one()
    org_locked.invoice_seq += 1
    today = date.today()
    fy_start = today.year if today.month >= 4 else today.year - 1
    prefix = org_locked.get_setting("invoice", "prefix") or "INV"
    return f"{prefix}/{fy_start}-{str(fy_start + 1)[-2:]}/{org_locked.invoice_seq:05d}"


def create_invoice(db: Session, principal: Principal, data: InvoiceCreate) -> Invoice:
    principal.require(Perm.INVOICE_CREATE)
    client = get_visible_client(db, principal, data.client_id)
    if (
        data.task_id
        and not db.execute(
            select(Task.id).where(Task.id == data.task_id, Task.organization_id == principal.org_id, Task.client_id == client.id)
        ).first()
    ):
        raise ValidationFailed("Task not found for this client")
    org = db.get(Organization, principal.org_id)
    assert org is not None
    issue = data.issue_date or date.today()
    due = data.due_date or issue + timedelta(days=int(org.get_setting("invoice", "payment_terms_days") or 15))
    if due < issue:
        raise ValidationFailed("Due date cannot be before issue date")
    inv = Invoice(
        organization_id=principal.org_id,
        client_id=client.id,
        task_id=data.task_id,
        invoice_number=_next_number(db, org),
        issue_date=issue,
        due_date=due,
        notes=data.notes,
        created_by=principal.user_id,
        status=InvoiceStatus.DRAFT,
    )
    subtotal = tax = Decimal("0")
    for it in data.items:
        amount = q2(it.quantity * it.unit_price)
        tax_amount = q2(amount * it.tax_rate / Decimal("100"))
        subtotal += amount
        tax += tax_amount
        inv.items.append(
            InvoiceItem(
                organization_id=principal.org_id,
                description=it.description,
                sac_code=it.sac_code,
                quantity=it.quantity,
                unit_price=it.unit_price,
                tax_rate=it.tax_rate,
                amount=amount,
                tax_amount=tax_amount,
            )
        )
    inv.subtotal, inv.tax, inv.total, inv.amount_paid = q2(subtotal), q2(tax), q2(subtotal + tax), Decimal("0")
    if inv.total <= 0:
        raise ValidationFailed("Invoice total must be greater than zero")
    db.add(inv)
    db.flush()
    audit.record(
        db,
        principal,
        AuditAction.INVOICE_CREATED,
        resource="invoice",
        resource_id=inv.id,
        client_id=client.id,
        metadata={"number": inv.invoice_number, "total": str(inv.total)},
    )
    db.commit()
    db.refresh(inv)
    return inv


def send_invoice(db: Session, principal: Principal, invoice_id: uuid.UUID) -> Invoice:
    principal.require(Perm.INVOICE_CREATE)
    inv = get_invoice(db, principal, invoice_id, for_update=True)
    if inv.status not in (InvoiceStatus.DRAFT, InvoiceStatus.SENT, InvoiceStatus.OVERDUE, InvoiceStatus.PARTIALLY_PAID):
        raise ValidationFailed(f"Cannot send an invoice in status {inv.status}")
    if inv.status == InvoiceStatus.DRAFT:
        inv.status = InvoiceStatus.SENT
    inv.sent_at = now_utc()
    client = db.get(Client, inv.client_id)
    assert client is not None
    messaging.send_template_to_client(
        db,
        client,
        TemplateKey.INVOICE_CREATED,
        [
            client.name,
            messaging.firm_name(db, principal.org_id),
            inv.invoice_number,
            f"{inv.total:,.2f}",
            inv.due_date.strftime("%d %b %Y"),
        ],
        url_suffix="invoices",
    )
    audit.record(db, principal, AuditAction.INVOICE_SENT, resource="invoice", resource_id=inv.id, client_id=inv.client_id)
    db.commit()
    db.refresh(inv)
    return inv


def cancel_invoice(db: Session, principal: Principal, invoice_id: uuid.UUID) -> Invoice:
    principal.require(Perm.INVOICE_CREATE)
    inv = get_invoice(db, principal, invoice_id, for_update=True)
    if inv.amount_paid > 0:
        raise ValidationFailed("Invoices with payments cannot be cancelled")
    inv.status = InvoiceStatus.CANCELLED
    audit.record(db, principal, AuditAction.INVOICE_CANCELLED, resource="invoice", resource_id=inv.id, client_id=inv.client_id)
    db.commit()
    return inv


def apply_payment_to_invoice(inv: Invoice, amount: Decimal) -> None:
    inv.amount_paid = q2((inv.amount_paid or Decimal("0")) + amount)
    if inv.amount_paid >= inv.total:
        inv.status = InvoiceStatus.PAID
        inv.paid_at = now_utc()
    elif inv.amount_paid > 0:
        inv.status = InvoiceStatus.PARTIALLY_PAID


def mark_overdue(db: Session, today: date | None = None) -> int:
    today = today or date.today()
    res = db.execute(
        update(Invoice)
        .where(Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID]), Invoice.due_date < today)
        .values(status=InvoiceStatus.OVERDUE)
    )
    db.commit()
    return int(res.rowcount or 0)  # type: ignore[attr-defined]
