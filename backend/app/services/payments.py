"""Payments. The frontend never decides that a payment succeeded.

A payment is recorded only after (a) the checkout signature verifies with the provider
secret AND (b) the provider API confirms the payment is captured for the expected order and
amount — or a signed webhook says so. Recording is idempotent on provider_payment_id.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import Principal, system_principal
from app.core.errors import NotFound, ValidationFailed
from app.core.logging import get_logger
from app.core.permissions import Perm
from app.core.security import now_utc
from app.integrations.payments import get_payment_provider
from app.integrations.payments.base import ProviderPayment
from app.models import Invoice, Organization, Payment, PaymentAttempt, Receipt, WebhookEvent
from app.models.enums import InvoiceStatus, PaymentAttemptStatus, PaymentStatus, WebhookStatus
from app.repositories.base import paginate
from app.schemas.billing import ManualPaymentIn, VerifyPaymentRequest
from app.services import audit, notifications
from app.services.audit import AuditAction
from app.services.invoices import apply_payment_to_invoice, get_invoice
from app.services.scope import scope_by_client

log = get_logger("payments")


def to_paise(amount: Decimal) -> int:
    return int((amount * 100).quantize(Decimal("1")))


def create_checkout(db: Session, principal: Principal, invoice_id: uuid.UUID) -> tuple[PaymentAttempt, Invoice, str]:
    inv = get_invoice(db, principal, invoice_id, for_update=True)
    if inv.status not in (InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE):
        raise ValidationFailed("This invoice is not payable")
    balance = inv.balance_due
    if balance <= 0:
        raise ValidationFailed("Nothing to pay on this invoice")
    provider = get_payment_provider()
    order = provider.create_order(
        amount_paise=to_paise(balance),
        currency=inv.currency,
        receipt=inv.invoice_number,
        notes={"invoice_id": str(inv.id), "org_id": str(inv.organization_id)},
    )
    attempt = PaymentAttempt(
        organization_id=inv.organization_id,
        invoice_id=inv.id,
        client_id=inv.client_id,
        provider=provider.name,
        provider_order_id=order.order_id,
        amount=balance,
        currency=inv.currency,
        raw=order.raw,
    )
    db.add(attempt)
    db.commit()
    return attempt, inv, order.key_id


def _record_payment(db: Session, attempt: PaymentAttempt, pp: ProviderPayment, *, via: str) -> Payment | None:
    """Idempotent: INSERT ... ON CONFLICT DO NOTHING on provider_payment_id."""
    amount = (Decimal(pp.amount_paise) / 100).quantize(Decimal("0.01"))
    pid = uuid.uuid4()
    row = db.execute(
        pg_insert(Payment)
        .values(
            id=pid,
            organization_id=attempt.organization_id,
            invoice_id=attempt.invoice_id,
            client_id=attempt.client_id,
            attempt_id=attempt.id,
            provider=attempt.provider,
            provider_payment_id=pp.payment_id,
            provider_order_id=attempt.provider_order_id,
            amount=amount,
            currency=pp.currency,
            method=pp.method,
            status=PaymentStatus.CAPTURED,
            paid_at=now_utc(),
            verified_via=via,
            raw=pp.raw,
        )
        .on_conflict_do_nothing(index_elements=["provider_payment_id"])
        .returning(Payment.id)
    ).first()
    if row is None:
        return None  # already recorded
    attempt.status = PaymentAttemptStatus.PAID
    inv = db.execute(select(Invoice).where(Invoice.id == attempt.invoice_id).with_for_update(of=Invoice)).unique().scalar_one()
    apply_payment_to_invoice(inv, amount)
    _issue_receipt(db, inv, pid, amount)
    audit.record(
        db,
        system_principal(attempt.organization_id),
        AuditAction.PAYMENT_RECEIVED,
        resource="invoice",
        resource_id=inv.id,
        client_id=inv.client_id,
        metadata={"amount": str(amount), "provider": attempt.provider, "via": via, "payment_id": pp.payment_id},
    )
    notifications.notify_permission(
        db,
        attempt.organization_id,
        Perm.PAYMENT_VIEW,
        type_="PAYMENT_RECEIVED",
        title=f"Payment received: Rs. {amount:,.2f}",
        body=f"Invoice {inv.invoice_number}",
        link=f"/invoices/{inv.id}",
    )
    log.info("payment_recorded", extra={"invoice_id": str(inv.id), "via": via})
    return db.get(Payment, pid)


def _issue_receipt(db: Session, inv: Invoice, payment_id: uuid.UUID, amount: Decimal) -> None:
    org = db.execute(select(Organization).where(Organization.id == inv.organization_id).with_for_update()).scalar_one()
    n = (org.settings or {}).get("receipt_seq", 0) + 1
    org.settings = {**(org.settings or {}), "receipt_seq": n}
    db.add(
        Receipt(
            organization_id=inv.organization_id,
            payment_id=payment_id,
            invoice_id=inv.id,
            receipt_number=f"RCPT-{n:06d}",
            amount=amount,
            issued_at=now_utc(),
        )
    )


def _confirm_with_provider(attempt: PaymentAttempt, payment_id: str) -> ProviderPayment:
    pp = get_payment_provider().get_payment_status(payment_id)
    if pp.order_id != attempt.provider_order_id:
        raise ValidationFailed("Payment does not belong to this order", code="PAYMENT_MISMATCH")
    if pp.status != "captured":
        raise ValidationFailed(f"Payment is not captured (status: {pp.status})", code="PAYMENT_NOT_CAPTURED")
    if pp.amount_paise != to_paise(attempt.amount):
        raise ValidationFailed("Payment amount mismatch", code="PAYMENT_MISMATCH")
    return pp


def verify_checkout(db: Session, principal: Principal, data: VerifyPaymentRequest) -> Invoice:
    attempt = db.execute(
        select(PaymentAttempt)
        .where(PaymentAttempt.provider_order_id == data.razorpay_order_id, PaymentAttempt.organization_id == principal.org_id)
        .with_for_update()
    ).scalar_one_or_none()
    if attempt is None or (principal.is_client and attempt.client_id != principal.client_id):
        raise NotFound("Payment order not found")
    provider = get_payment_provider()
    if not provider.verify_payment(order_id=data.razorpay_order_id, payment_id=data.razorpay_payment_id, signature=data.razorpay_signature):
        audit.record(
            db,
            principal,
            AuditAction.PAYMENT_VERIFICATION_FAILED,
            resource="invoice",
            resource_id=attempt.invoice_id,
            metadata={"reason": "bad_signature"},
        )
        db.commit()
        raise ValidationFailed("Payment verification failed", code="INVALID_PAYMENT_SIGNATURE")
    pp = _confirm_with_provider(attempt, data.razorpay_payment_id)
    _record_payment(db, attempt, pp, via="SIGNATURE")
    db.commit()
    inv = db.get(Invoice, attempt.invoice_id)
    assert inv is not None
    db.refresh(inv)
    return inv


def handle_webhook(db: Session, body: bytes, signature: str | None) -> bool:
    provider = get_payment_provider()
    wh = provider.process_webhook(body, signature)  # raises Unauthorized on bad signature
    import json

    row = db.execute(
        pg_insert(WebhookEvent)
        .values(
            id=uuid.uuid4(),
            provider="razorpay" if provider.name == "razorpay" else "payments_mock",
            event_key=wh.event_id[:200],
            event_type=wh.event[:40],
            payload=json.loads(body),
            status=WebhookStatus.RECEIVED,
            attempts=0,
        )
        .on_conflict_do_nothing(index_elements=["provider", "event_key"])
        .returning(WebhookEvent.id)
    ).first()
    if row is None:
        db.commit()
        return False  # duplicate
    ev = db.get(WebhookEvent, row[0])
    assert ev is not None
    if wh.event in ("payment.captured", "order.paid") and wh.payment and wh.payment.order_id:
        attempt = db.execute(
            select(PaymentAttempt).where(PaymentAttempt.provider_order_id == wh.payment.order_id).with_for_update()
        ).scalar_one_or_none()
        if attempt is not None:
            ev.organization_id = attempt.organization_id
            if wh.payment.amount_paise == to_paise(attempt.amount) and wh.payment.status == "captured":
                _record_payment(db, attempt, wh.payment, via="WEBHOOK")
                ev.status = WebhookStatus.PROCESSED
            else:
                ev.status = WebhookStatus.FAILED
                ev.error = "Amount/status mismatch"
        else:
            ev.status = WebhookStatus.IGNORED
    elif wh.event == "payment.failed" and wh.payment and wh.payment.order_id:
        attempt = db.execute(select(PaymentAttempt).where(PaymentAttempt.provider_order_id == wh.payment.order_id)).scalar_one_or_none()
        if attempt and attempt.status == PaymentAttemptStatus.CREATED:
            attempt.status = PaymentAttemptStatus.FAILED
        ev.status = WebhookStatus.PROCESSED
    else:
        ev.status = WebhookStatus.IGNORED
    ev.processed_at = now_utc()
    db.commit()
    return True


def reconcile_pending(db: Session, older_than_minutes: int = 10) -> int:
    """Catch payments whose browser callback and webhook were both lost."""
    cutoff = now_utc() - timedelta(minutes=older_than_minutes)
    attempts = (
        db.execute(
            select(PaymentAttempt)
            .where(PaymentAttempt.status == PaymentAttemptStatus.CREATED, PaymentAttempt.created_at < cutoff)
            .limit(200)
        )
        .scalars()
        .all()
    )
    recorded = 0
    provider = get_payment_provider()
    for a in attempts:
        try:
            pays = provider.get_order_payments(a.provider_order_id)
        except Exception:
            log.warning("reconcile_fetch_failed")
            continue
        captured = [p for p in pays if p.status == "captured" and p.amount_paise == to_paise(a.amount)]
        if captured:
            if _record_payment(db, a, captured[0], via="RECONCILIATION"):
                recorded += 1
        elif a.created_at < now_utc() - timedelta(days=2):
            a.status = PaymentAttemptStatus.EXPIRED
    db.commit()
    return recorded


def record_manual_payment(db: Session, principal: Principal, invoice_id: uuid.UUID, data: ManualPaymentIn) -> Payment:
    principal.require(Perm.INVOICE_CREATE)
    inv = get_invoice(db, principal, invoice_id, for_update=True)
    if inv.status in (InvoiceStatus.DRAFT, InvoiceStatus.CANCELLED, InvoiceStatus.PAID):
        raise ValidationFailed(f"Cannot record payment for invoice in status {inv.status}")
    if data.amount > inv.balance_due:
        raise ValidationFailed("Amount exceeds balance due")
    ref = f"manual:{inv.organization_id}:{data.reference.strip()}"
    if db.execute(select(Payment.id).where(Payment.provider_payment_id == ref)).first():
        raise ValidationFailed("A payment with this reference is already recorded")
    p = Payment(
        organization_id=inv.organization_id,
        invoice_id=inv.id,
        client_id=inv.client_id,
        provider="manual",
        provider_payment_id=ref,
        amount=data.amount,
        currency=inv.currency,
        method=data.method,
        status=PaymentStatus.CAPTURED,
        paid_at=data.paid_at or now_utc(),
        verified_via="MANUAL",
        recorded_by=principal.user_id,
        raw={},
    )
    db.add(p)
    db.flush()
    apply_payment_to_invoice(inv, data.amount)
    _issue_receipt(db, inv, p.id, data.amount)
    audit.record(
        db,
        principal,
        AuditAction.PAYMENT_RECEIVED,
        resource="invoice",
        resource_id=inv.id,
        client_id=inv.client_id,
        metadata={"amount": str(data.amount), "via": "MANUAL", "method": data.method},
    )
    db.commit()
    return p


def list_payments(
    db: Session,
    principal: Principal,
    *,
    client_id: uuid.UUID | None = None,
    invoice_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Payment], int]:
    if principal.is_staff:
        principal.require(Perm.PAYMENT_VIEW)
    stmt = scope_by_client(select(Payment), Payment, principal)
    if client_id:
        stmt = stmt.where(Payment.client_id == client_id)
    if invoice_id:
        stmt = stmt.where(Payment.invoice_id == invoice_id)
    rows, total = paginate(db, stmt.order_by(Payment.paid_at.desc()), page, page_size)
    return list(rows), total


def mock_complete_checkout(order_id: str, succeed: bool = True) -> dict[str, Any]:
    """Dev-only: plays the payment gateway's role in mock mode."""
    from app.integrations.payments.mock import MockPaymentProvider

    provider = get_payment_provider()
    if not isinstance(provider, MockPaymentProvider) or not settings.dev_tools_enabled:
        raise NotFound("Not available")
    return provider.complete_checkout(order_id, succeed=succeed)
