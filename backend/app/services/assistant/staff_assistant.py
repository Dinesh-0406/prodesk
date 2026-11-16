"""Professional (dashboard) AI assistant.

Questions are mapped by the AI to one of a fixed set of pre-built, parameterised,
tenant-scoped queries. The AI never writes SQL and only sees what the asking user can see.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.permissions import Perm
from app.core.rate_limit import hit
from app.integrations.ai import get_ai_provider
from app.integrations.ai.base import StaffQueryName
from app.models import Client, DocumentRequest, DocumentRequestItem, Invoice, Task, User
from app.models.enums import TASK_DONE_STATUSES, InvoiceStatus
from app.schemas.messaging import AIChatResponse
from app.services import audit
from app.services.audit import AuditAction
from app.services.reports import OPEN_INV, OPEN_REQ
from app.services.scope import scope_by_client, visible_client_ids_subquery

DONE = [s.value for s in TASK_DONE_STATUSES]
DISCLAIMER = "Results come directly from ProDesk records you have access to. This is data retrieval, not professional advice."
SUPPORTED = [
    "Which clients have pending documents?",
    "Show overdue ITR tasks.",
    "Which invoices are unpaid?",
    "Which tasks are due this week?",
    "Which clients are assigned to <employee>?",
    "Which clients haven't submitted bank statements?",
]


def answer(db: Session, principal: Principal, question: str, today: date | None = None) -> AIChatResponse:
    principal.require(Perm.CLIENT_VIEW)
    hit(f"ai_staff:{principal.user_id}", 30, 60)
    today = today or date.today()
    sq = get_ai_provider().classify_staff_query(question)
    cols: list[str] = []
    rows: list[dict[str, Any]] = []
    q = sq.query

    if q == StaffQueryName.CLIENTS_WITH_PENDING_DOCUMENTS:
        reqs = (
            db.execute(scope_by_client(select(DocumentRequest), DocumentRequest, principal).where(DocumentRequest.status.in_(OPEN_REQ)))
            .unique()
            .scalars()
        )
        cols = ["client", "request", "pending", "due_date", "status"]
        rows = [
            {
                "client": r.client.name,
                "request": r.title,
                "pending": ", ".join(i.name for i in r.items if i.status == "PENDING"),
                "due_date": r.due_date.isoformat() if r.due_date else "",
                "status": r.status,
            }
            for r in reqs
        ]
        summary = f"{len({r['client'] for r in rows})} client(s) have pending documents."
    elif q in (StaffQueryName.OVERDUE_TASKS, StaffQueryName.TASKS_DUE_THIS_WEEK):
        principal.require(Perm.TASK_VIEW)
        stmt = scope_by_client(select(Task), Task, principal).where(Task.status.not_in(DONE))
        if q == StaffQueryName.OVERDUE_TASKS:
            stmt = stmt.where(Task.due_date < today)
        else:
            stmt = stmt.where(Task.due_date >= today, Task.due_date <= today + timedelta(days=6 - today.weekday()))
        if sq.service_type:
            stmt = stmt.where(Task.service_type == sq.service_type.value)
        tasks = db.execute(stmt.order_by(Task.due_date)).unique().scalars().all()
        cols = ["client", "task", "service", "due_date", "assigned_to", "status"]
        rows = [
            {
                "client": t.client.name,
                "task": t.title,
                "service": t.service_type,
                "due_date": t.due_date.isoformat() if t.due_date else "",
                "assigned_to": t.assigned_employee.full_name if t.assigned_employee else "",
                "status": t.status,
            }
            for t in tasks
        ]
        label = "overdue" if q == StaffQueryName.OVERDUE_TASKS else "due this week"
        summary = f"{len(rows)} {sq.service_type.value + ' ' if sq.service_type else ''}task(s) {label}."
    elif q == StaffQueryName.UNPAID_INVOICES:
        principal.require(Perm.INVOICE_VIEW)
        invs = (
            db.execute(scope_by_client(select(Invoice), Invoice, principal).where(Invoice.status.in_(OPEN_INV)).order_by(Invoice.due_date))
            .unique()
            .scalars()
            .all()
        )
        cols = ["invoice", "client", "balance_due", "due_date", "status"]
        rows = [
            {
                "invoice": i.invoice_number,
                "client": i.client.name,
                "balance_due": f"{i.balance_due:.2f}",
                "due_date": i.due_date.isoformat(),
                "status": i.status,
            }
            for i in invs
        ]
        total = sum((i.balance_due for i in invs), start=0)
        n_overdue = sum(1 for i in invs if i.status == InvoiceStatus.OVERDUE)
        summary = f"{len(rows)} unpaid invoice(s), Rs. {total:,.2f} outstanding ({n_overdue} overdue)."
    elif q == StaffQueryName.CLIENTS_BY_EMPLOYEE and sq.employee_name:
        users = (
            db.execute(select(User).where(User.organization_id == principal.org_id, User.full_name.ilike(f"%{sq.employee_name[:60]}%")))
            .unique()
            .scalars()
            .all()
        )
        ids = [u.id for u in users]
        clients: Sequence[Any] = (
            db.execute(
                select(Client)
                .where(
                    Client.id.in_(visible_client_ids_subquery(principal)), Client.assigned_employee_id.in_(ids), Client.status != "ARCHIVED"
                )
                .order_by(Client.name)
            )
            .unique()
            .scalars()
            .all()
            if ids
            else []
        )
        cols = ["client", "phone", "type", "assigned_to"]
        rows = [
            {
                "client": c.name,
                "phone": c.phone,
                "type": c.client_type,
                "assigned_to": c.assigned_employee.full_name if c.assigned_employee else "",
            }
            for c in clients
        ]
        summary = (
            f"{len(rows)} client(s) assigned to {', '.join(u.full_name for u in users)}."
            if users
            else f"No employee matching '{sq.employee_name}'."
        )
    elif q == StaffQueryName.CLIENTS_MISSING_DOCUMENT and sq.document_name:
        name = sq.document_name.rstrip("s")[:60]
        pending_item = exists().where(
            DocumentRequestItem.request_id == DocumentRequest.id,
            DocumentRequestItem.status == "PENDING",
            DocumentRequestItem.name.ilike(f"%{name}%"),
        )
        missing: Sequence[Any] = (
            db.execute(
                scope_by_client(select(DocumentRequest), DocumentRequest, principal).where(
                    DocumentRequest.status.in_(OPEN_REQ), pending_item
                )
            )
            .unique()
            .scalars()
            .all()
        )
        cols = ["client", "request", "due_date", "status"]
        rows = [
            {"client": r.client.name, "request": r.title, "due_date": r.due_date.isoformat() if r.due_date else "", "status": r.status}
            for r in missing
        ]
        summary = f"{len({r['client'] for r in rows})} client(s) haven't submitted '{sq.document_name}'."
    else:
        q = StaffQueryName.UNSUPPORTED
        summary = "I can answer questions like: " + "; ".join(SUPPORTED)

    audit.record(db, principal, AuditAction.AI_QUERY, resource="ai", metadata={"query": q.value, "rows": len(rows)})
    db.commit()
    return AIChatResponse(query=q.value, answer=summary, columns=cols, rows=rows[:200], disclaimer=DISCLAIMER)
