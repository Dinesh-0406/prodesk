from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import DB, Staff
from app.core.rate_limit import client_ip, limiter
from app.schemas.billing import InvoiceCreate, InvoiceOut, ManualPaymentIn, PaymentOut
from app.schemas.common import Page
from app.services import audit, invoices, payments
from app.services.audit import AuditAction

router = APIRouter(tags=["billing"])
webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/invoices", response_model=Page[InvoiceOut])
def list_invoices(
    principal: Staff,
    db: DB,
    status: str | None = None,
    client_id: uuid.UUID | None = None,
    q: str | None = None,
    open_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> Page[InvoiceOut]:
    rows, total = invoices.list_invoices(
        db, principal, status=status, client_id=client_id, q=q, open_only=open_only, page=page, page_size=page_size
    )
    return Page(items=[InvoiceOut.model_validate(i) for i in rows], total=total, page=page, page_size=page_size)


@router.post("/invoices", response_model=InvoiceOut, status_code=201)
def create_invoice(body: InvoiceCreate, principal: Staff, db: DB) -> InvoiceOut:
    return InvoiceOut.model_validate(invoices.create_invoice(db, principal, body))


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def get_invoice(invoice_id: uuid.UUID, principal: Staff, db: DB) -> InvoiceOut:
    return InvoiceOut.model_validate(invoices.get_invoice(db, principal, invoice_id))


@router.post("/invoices/{invoice_id}/send", response_model=InvoiceOut)
def send_invoice(invoice_id: uuid.UUID, principal: Staff, db: DB) -> InvoiceOut:
    return InvoiceOut.model_validate(invoices.send_invoice(db, principal, invoice_id))


@router.post("/invoices/{invoice_id}/cancel", response_model=InvoiceOut)
def cancel_invoice(invoice_id: uuid.UUID, principal: Staff, db: DB) -> InvoiceOut:
    return InvoiceOut.model_validate(invoices.cancel_invoice(db, principal, invoice_id))


@router.post("/invoices/{invoice_id}/payments", response_model=PaymentOut, status_code=201)
def record_manual_payment(invoice_id: uuid.UUID, body: ManualPaymentIn, principal: Staff, db: DB) -> PaymentOut:
    return PaymentOut.model_validate(payments.record_manual_payment(db, principal, invoice_id, body))


@router.get("/payments", response_model=Page[PaymentOut])
def list_payments(
    principal: Staff,
    db: DB,
    client_id: uuid.UUID | None = None,
    invoice_id: uuid.UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> Page[PaymentOut]:
    rows, total = payments.list_payments(db, principal, client_id=client_id, invoice_id=invoice_id, page=page, page_size=page_size)
    return Page(items=[PaymentOut.model_validate(p) for p in rows], total=total, page=page, page_size=page_size)


@webhook_router.post("/razorpay", dependencies=[Depends(limiter("wh_razorpay", 600, 60))])
async def razorpay_webhook(request: Request, db: DB) -> dict[str, str]:
    body = await request.body()
    try:
        new = payments.handle_webhook(db, body, request.headers.get("x-razorpay-signature"))
    except Exception:
        db.rollback()
        audit.record(db, None, AuditAction.WEBHOOK_REJECTED, resource="webhook", ip=client_ip(request), metadata={"provider": "razorpay"})
        db.commit()
        raise
    return {"status": "ok" if new else "duplicate"}
