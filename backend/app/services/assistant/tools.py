"""Safe backend tools callable from AI flows.

The AI never touches the database. It produces a structured intent; the backend selects a
tool; every tool validates organization, client identity, permission and ownership before
returning *facts* from the database.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.errors import Forbidden, NotFound
from app.core.permissions import Perm
from app.models import Client, Document, DocumentRequest, Invoice, SupportRequest, Task
from app.models.enums import (
    DocumentRequestStatus,
    DocumentStatus,
    InvoiceStatus,
    RequestItemStatus,
    SupportRequestType,
)


@dataclass(frozen=True)
class ToolContext:
    principal: Principal
    conversation_id: uuid.UUID | None = None

    @property
    def org_id(self) -> uuid.UUID:
        return self.principal.org_id

    @property
    def client_id(self) -> uuid.UUID:
        if self.principal.client_id is None:
            raise Forbidden("Tool requires an identified client")
        return self.principal.client_id


def _validate(ctx: ToolContext, *, staff_perm: Perm | None = None) -> None:
    p = ctx.principal
    if p.organization_id is None:
        raise Forbidden("No organization context")
    if p.is_client:
        if not p.has(Perm.PORTAL_ACCESS) or p.client_id is None:
            raise Forbidden("Client is not authorised")
        return
    if staff_perm is not None:
        p.require(staff_perm)
    if ctx.principal.client_id is None:
        raise Forbidden("Tool requires a client context")


def current_financial_year(today: date | None = None) -> str:
    today = today or date.today()
    start = today.year if today.month >= 4 else today.year - 1
    return f"{start}-{str(start + 1)[-2:]}"


def shift_fy(fy: str, delta: int) -> str:
    start = int(fy[:4]) + delta
    return f"{start}-{str(start + 1)[-2:]}"


def get_client_profile(db: Session, ctx: ToolContext) -> dict[str, Any]:
    _validate(ctx, staff_perm=Perm.CLIENT_VIEW)
    c = db.execute(select(Client).where(Client.organization_id == ctx.org_id, Client.id == ctx.client_id)).unique().scalar_one_or_none()
    if c is None:
        raise NotFound("Client not found")
    return {"name": c.name, "client_type": c.client_type, "pan_masked": f"{c.pan[:2]}XXXXX{c.pan[-3:]}" if c.pan else None}


def _available_docs_stmt(ctx: ToolContext) -> Any:
    return select(Document).where(
        Document.organization_id == ctx.org_id,
        Document.client_id == ctx.client_id,
        Document.deleted_at.is_(None),
        Document.approved_version_id.is_not(None),
        Document.status.in_([DocumentStatus.APPROVED, DocumentStatus.DELIVERED]),
    )


def list_client_documents(
    db: Session, ctx: ToolContext, *, document_type: str | None = None, financial_year: str | None = None, limit: int = 10
) -> list[Document]:
    _validate(ctx, staff_perm=Perm.DOCUMENT_VIEW)
    stmt = _available_docs_stmt(ctx)
    if document_type:
        stmt = stmt.where(Document.document_type == document_type)
    if financial_year:
        stmt = stmt.where(Document.financial_year == financial_year)
    stmt = stmt.order_by(Document.financial_year.desc().nulls_last(), Document.updated_at.desc()).limit(limit)
    return list(db.execute(stmt).unique().scalars())


def get_document(
    db: Session,
    ctx: ToolContext,
    *,
    document_type: str,
    financial_year: str | None = None,
    relative_year: int | None = None,
    today: date | None = None,
) -> Document | None:
    """Most recent approved document of a type for THIS client only."""
    _validate(ctx, staff_perm=Perm.DOCUMENT_VIEW)
    fy = financial_year
    if fy is None and relative_year is not None:
        fy = shift_fy(current_financial_year(today), relative_year)
    docs = list_client_documents(db, ctx, document_type=document_type, financial_year=fy, limit=1)
    return docs[0] if docs else None


def get_pending_documents(db: Session, ctx: ToolContext) -> list[dict[str, Any]]:
    _validate(ctx, staff_perm=Perm.TASK_VIEW)
    reqs = (
        db.execute(
            select(DocumentRequest)
            .where(
                DocumentRequest.organization_id == ctx.org_id,
                DocumentRequest.client_id == ctx.client_id,
                DocumentRequest.status.in_([DocumentRequestStatus.PENDING, DocumentRequestStatus.PARTIAL, DocumentRequestStatus.OVERDUE]),
            )
            .order_by(DocumentRequest.due_date.asc().nulls_last())
        )
        .unique()
        .scalars()
    )
    out = []
    for r in reqs:
        pending = [i.name for i in r.items if i.status == RequestItemStatus.PENDING]
        if pending:
            out.append({"request_id": str(r.id), "title": r.title, "due_date": r.due_date, "pending": pending, "status": r.status})
    return out


def get_task_status(
    db: Session, ctx: ToolContext, *, service_type: str | None = None, financial_year: str | None = None, limit: int = 5
) -> list[Task]:
    _validate(ctx, staff_perm=Perm.TASK_VIEW)
    stmt = select(Task).where(Task.organization_id == ctx.org_id, Task.client_id == ctx.client_id)
    if service_type:
        stmt = stmt.where(Task.service_type == service_type)
    if financial_year:
        stmt = stmt.where(Task.financial_year == financial_year)
    stmt = stmt.order_by(Task.updated_at.desc()).limit(limit)
    return list(db.execute(stmt).unique().scalars())


def get_invoice(db: Session, ctx: ToolContext, *, open_only: bool = True, limit: int = 5) -> list[Invoice]:
    _validate(ctx, staff_perm=Perm.INVOICE_VIEW)
    stmt = select(Invoice).where(
        Invoice.organization_id == ctx.org_id,
        Invoice.client_id == ctx.client_id,
        Invoice.status != InvoiceStatus.DRAFT,
        Invoice.status != InvoiceStatus.CANCELLED,
    )
    if open_only:
        stmt = stmt.where(Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]))
    return list(db.execute(stmt.order_by(Invoice.due_date.asc()).limit(limit)).unique().scalars())


def get_payment_status(db: Session, ctx: ToolContext) -> dict[str, Any]:
    _validate(ctx, staff_perm=Perm.PAYMENT_VIEW)
    invoices = get_invoice(db, ctx, open_only=True, limit=50)
    outstanding = sum((i.balance_due for i in invoices), Decimal("0"))
    return {
        "outstanding": outstanding.quantize(Decimal("0.01")),
        "open_invoices": len(invoices),
        "overdue": sum(1 for i in invoices if i.status == InvoiceStatus.OVERDUE),
        "invoices": [
            {"number": i.invoice_number, "balance": i.balance_due, "due_date": i.due_date, "status": i.status} for i in invoices[:5]
        ],
    }


def create_document_request(
    db: Session, ctx: ToolContext, *, title: str, items: list[str], due_date: date | None = None
) -> DocumentRequest:
    """Staff-only (requires DOCUMENT_REQUEST_CREATE). Clients cannot create requests for themselves."""
    if ctx.principal.is_client:
        raise Forbidden("Clients cannot create document requests")
    _validate(ctx, staff_perm=Perm.DOCUMENT_REQUEST_CREATE)
    from app.schemas.work import DocumentRequestCreate, RequestItemIn
    from app.services.document_requests import create_request

    return create_request(
        db,
        ctx.principal,
        DocumentRequestCreate(client_id=ctx.client_id, title=title, due_date=due_date, items=[RequestItemIn(name=n) for n in items]),
    )


def create_support_request(db: Session, ctx: ToolContext, *, request_type: SupportRequestType, message: str) -> SupportRequest:
    _validate(ctx)
    sr = SupportRequest(
        organization_id=ctx.org_id,
        client_id=ctx.client_id,
        conversation_id=ctx.conversation_id,
        request_type=request_type,
        message=message[:2000],
    )
    db.add(sr)
    db.flush()
    return sr
