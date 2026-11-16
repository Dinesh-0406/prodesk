"""Client portal API. Every route is bound to the authenticated client principal."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import DB, ClientUser
from app.api.v1.documents import read_upload
from app.core.phone import mask_phone
from app.core.rate_limit import client_ip, limiter
from app.models import Client, Conversation, Message, Organization
from app.schemas.auth import ClientSessionResponse, OtpRequest, OtpRequestResponse, OtpVerify
from app.schemas.billing import CheckoutResponse, InvoiceOut, PaymentOut, VerifyPaymentRequest
from app.schemas.common import Page
from app.schemas.document import DocumentOut, DownloadUrlResponse
from app.schemas.work import DocumentRequestOut, SupportRequestIn, SupportRequestOut
from app.services import delivery, document_requests, documents, invoices, misc, payments, portal_auth, tasks
from app.services.tasks import STATUS_LABELS

router = APIRouter(prefix="/portal", tags=["client-portal"])


class PortalTask(BaseModel):
    id: uuid.UUID
    title: str
    service_type: str
    financial_year: str | None
    status: str
    status_label: str
    due_date: date | None
    filed_at: datetime | None
    updated_at: datetime


@router.post("/auth/request-otp", response_model=OtpRequestResponse, dependencies=[Depends(limiter("portal_otp", 20, 600))])
def request_otp(body: OtpRequest, request: Request, db: DB) -> OtpRequestResponse:
    r = portal_auth.request_otp(db, org_slug=body.org_slug, phone=body.phone, ip=client_ip(request))
    return OtpRequestResponse(message=r.message, dev_otp=r.dev_otp)


@router.post("/auth/verify-otp", response_model=ClientSessionResponse)
def verify_otp(body: OtpVerify, request: Request, db: DB) -> ClientSessionResponse:
    s = portal_auth.verify_otp(db, org_slug=body.org_slug, phone=body.phone, code=body.code, ip=client_ip(request))
    return ClientSessionResponse(
        access_token=s.access_token, expires_at=s.expires_at, client_id=s.client.id, client_name=s.client.name, organization_name=s.org.name
    )


@router.get("/link/{token}", dependencies=[Depends(limiter("portal_link", 60, 60))])
def link_info(token: str, db: DB) -> dict[str, Any]:
    """Public: only what's needed to start login. No document details are revealed."""
    d = delivery.resolve_delivery(db, token)
    org = db.get(Organization, d.organization_id)
    client = db.get(Client, d.client_id)
    return {
        "organization_name": org.name if org else "",
        "org_slug": org.slug if org else "",
        "phone_hint": mask_phone(client.phone if client else None),
        "expires_at": d.expires_at,
    }


@router.post("/link/{token}/download", response_model=DownloadUrlResponse, dependencies=[Depends(limiter("portal_link_dl", 30, 60))])
def link_download(token: str, principal: ClientUser, db: DB) -> DownloadUrlResponse:
    from datetime import timedelta

    from app.core.config import settings
    from app.core.security import now_utc

    url, name = delivery.download_via_delivery(db, principal, token)
    return DownloadUrlResponse(url=url, file_name=name, expires_at=now_utc() + timedelta(seconds=settings.SIGNED_URL_TTL_SECONDS))


@router.get("/me")
def me(principal: ClientUser, db: DB) -> dict[str, Any]:
    c = db.get(Client, principal.client_id)
    org = db.get(Organization, principal.org_id)
    assert c is not None and org is not None
    return {
        "id": str(c.id),
        "name": c.name,
        "phone": c.phone,
        "email": c.email,
        "address": c.address,
        "client_type": c.client_type,
        "pan": c.pan,
        "gstin": c.gstin,
        "whatsapp_opt_in": c.whatsapp_opt_in,
        "organization": {"name": org.name, "phone": org.phone, "email": org.email, "address": org.address},
    }


@router.get("/dashboard")
def dashboard(principal: ClientUser, db: DB) -> dict[str, Any]:
    _, n_docs = documents.list_documents(db, principal, page=1, page_size=1)
    reqs, n_reqs = document_requests.list_requests(db, principal, open_only=True, page=1, page_size=5)
    open_inv, n_inv = invoices.list_invoices(db, principal, open_only=True, page=1, page_size=50)
    t, _ = tasks.list_tasks(db, principal, bucket="open", page=1, page_size=5)
    return {
        "documents": n_docs,
        "pending_requests": n_reqs,
        "open_invoices": n_inv,
        "outstanding": str(sum((i.balance_due for i in open_inv), start=0)),
        "requests": [DocumentRequestOut.model_validate(r).model_dump(mode="json") for r in reqs],
        "tasks": [{"title": x.title, "status": STATUS_LABELS.get(x.status, x.status)} for x in t],
    }


@router.get("/documents", response_model=Page[DocumentOut])
def my_documents(
    principal: ClientUser,
    db: DB,
    document_type: str | None = None,
    financial_year: str | None = None,
    q: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> Page[DocumentOut]:
    rows, total = documents.list_documents(
        db, principal, q=q, document_type=document_type, financial_year=financial_year, page=page, page_size=page_size
    )
    return Page(items=[DocumentOut.model_validate(d) for d in rows], total=total, page=page, page_size=page_size)


@router.post("/documents/{doc_id}/download-url", response_model=DownloadUrlResponse)
def my_document_url(doc_id: uuid.UUID, principal: ClientUser, db: DB, inline: bool = False) -> DownloadUrlResponse:
    url, exp, name = documents.create_download_url(db, principal, doc_id, inline=inline)
    return DownloadUrlResponse(url=url, expires_at=exp, file_name=name)


@router.get("/document-requests", response_model=Page[DocumentRequestOut])
def my_requests(
    principal: ClientUser, db: DB, open_only: bool = False, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)
) -> Page[DocumentRequestOut]:
    rows, total = document_requests.list_requests(db, principal, open_only=open_only, page=page, page_size=page_size)
    return Page(items=[DocumentRequestOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.post(
    "/document-requests/{request_id}/upload", response_model=DocumentRequestOut, dependencies=[Depends(limiter("portal_upload", 30, 600))]
)
async def upload_for_request(
    request_id: uuid.UUID, principal: ClientUser, db: DB, file: UploadFile = File(...), item_id: uuid.UUID | None = Form(None)
) -> DocumentRequestOut:
    content = await read_upload(file)
    document_requests.client_upload_for_request(db, principal, request_id, item_id, file.filename or "document", content)
    return DocumentRequestOut.model_validate(document_requests.get_request(db, principal, request_id))


@router.get("/tasks", response_model=list[PortalTask])
def my_tasks(principal: ClientUser, db: DB) -> list[PortalTask]:
    rows, _ = tasks.list_tasks(db, principal, page=1, page_size=100, sort="created_at", order="desc")
    return [
        PortalTask(
            id=t.id,
            title=t.title,
            service_type=t.service_type,
            financial_year=t.financial_year,
            status=t.status,
            status_label=STATUS_LABELS.get(t.status, t.status),
            due_date=t.due_date,
            filed_at=t.filed_at,
            updated_at=t.updated_at,
        )
        for t in rows
    ]


@router.get("/invoices", response_model=Page[InvoiceOut])
def my_invoices(principal: ClientUser, db: DB, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)) -> Page[InvoiceOut]:
    rows, total = invoices.list_invoices(db, principal, page=page, page_size=page_size)
    return Page(items=[InvoiceOut.model_validate(i) for i in rows], total=total, page=page, page_size=page_size)


@router.get("/invoices/{invoice_id}", response_model=InvoiceOut)
def my_invoice(invoice_id: uuid.UUID, principal: ClientUser, db: DB) -> InvoiceOut:
    return InvoiceOut.model_validate(invoices.get_invoice(db, principal, invoice_id))


@router.post(
    "/invoices/{invoice_id}/checkout", response_model=CheckoutResponse, dependencies=[Depends(limiter("portal_checkout", 20, 600))]
)
def checkout(invoice_id: uuid.UUID, principal: ClientUser, db: DB) -> CheckoutResponse:
    attempt, inv, key_id = payments.create_checkout(db, principal, invoice_id)
    org = db.get(Organization, principal.org_id)
    return CheckoutResponse(
        provider=attempt.provider,
        order_id=attempt.provider_order_id,
        amount_paise=payments.to_paise(attempt.amount),
        currency=attempt.currency,
        key_id=key_id,
        invoice_number=inv.invoice_number,
        firm_name=org.name if org else "",
    )


@router.post("/payments/verify", response_model=InvoiceOut, dependencies=[Depends(limiter("portal_verify", 30, 600))])
def verify_payment(body: VerifyPaymentRequest, principal: ClientUser, db: DB) -> InvoiceOut:
    """Server-side verification: signature + provider status/amount. The frontend's 'success'
    callback alone never marks an invoice paid."""
    return InvoiceOut.model_validate(payments.verify_checkout(db, principal, body))


class MockComplete(BaseModel):
    order_id: str
    succeed: bool = True


@router.post("/payments/mock-complete")
def mock_complete(body: MockComplete, principal: ClientUser, db: DB) -> dict[str, Any]:
    """Development only: acts as the mock payment gateway's hosted checkout."""
    from app.core.errors import NotFound
    from app.models import PaymentAttempt

    attempt = db.execute(
        select(PaymentAttempt).where(PaymentAttempt.provider_order_id == body.order_id, PaymentAttempt.client_id == principal.client_id)
    ).scalar_one_or_none()
    if attempt is None:
        raise NotFound("Order not found")
    return payments.mock_complete_checkout(body.order_id, body.succeed)


@router.get("/payments", response_model=Page[PaymentOut])
def my_payments(principal: ClientUser, db: DB, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)) -> Page[PaymentOut]:
    rows, total = payments.list_payments(db, principal, page=page, page_size=page_size)
    return Page(items=[PaymentOut.model_validate(p) for p in rows], total=total, page=page, page_size=page_size)


@router.get("/messages")
def my_messages(principal: ClientUser, db: DB) -> list[dict[str, Any]]:
    conv = (
        db.execute(
            select(Conversation).where(Conversation.organization_id == principal.org_id, Conversation.client_id == principal.client_id)
        )
        .unique()
        .scalars()
        .first()
    )
    if conv is None:
        return []
    msgs = db.execute(select(Message).where(Message.conversation_id == conv.id).order_by(Message.timestamp.desc()).limit(100)).scalars()
    return [
        {"direction": m.direction, "sender": m.sender, "body": m.body, "timestamp": m.timestamp, "status": m.status}
        for m in reversed(list(msgs))
    ]


@router.get("/support", response_model=Page[SupportRequestOut])
def my_support(principal: ClientUser, db: DB) -> Page[SupportRequestOut]:
    rows, total = misc.list_support(db, principal, page=1, page_size=50)
    return Page(items=[SupportRequestOut.model_validate(r) for r in rows], total=total, page=1, page_size=50)


@router.post("/support", response_model=SupportRequestOut, status_code=201, dependencies=[Depends(limiter("portal_support", 10, 600))])
def create_support(body: SupportRequestIn, principal: ClientUser, db: DB) -> SupportRequestOut:
    sr = misc.create_support_from_portal(db, principal, body.request_type, body.message)
    db.refresh(sr)
    return SupportRequestOut.model_validate(sr)
