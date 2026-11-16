"""Dashboard metrics and reports (all scoped to the caller's organization and visibility)."""

from __future__ import annotations

import csv
import io
from datetime import date, timedelta
from typing import Any

from sqlalchemy import Date, and_, case, cast, func, select
from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.errors import NotFound
from app.core.permissions import Perm
from app.core.security import now_utc
from app.models import (
    Client,
    ComplianceEvent,
    Conversation,
    Document,
    DocumentDelivery,
    DocumentRequest,
    Invoice,
    Message,
    Payment,
    Task,
    User,
)
from app.models.enums import (
    TASK_DONE_STATUSES,
    ClientStatus,
    DocumentRequestStatus,
    DocumentStatus,
    InvoiceStatus,
)
from app.services.scope import scope_by_client, visible_client_ids_subquery

OPEN_REQ = [DocumentRequestStatus.PENDING, DocumentRequestStatus.PARTIAL, DocumentRequestStatus.OVERDUE]
OPEN_INV = [InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]
DONE = [s.value for s in TASK_DONE_STATUSES]


def _count(db: Session, stmt: Any) -> int:
    return int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one())


def dashboard(db: Session, principal: Principal, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    clients = select(Client.id).where(Client.id.in_(visible_client_ids_subquery(principal)))
    tasks_open = scope_by_client(select(Task.id), Task, principal).where(Task.status.not_in(DONE))
    return {
        "total_clients": _count(db, clients.where(Client.status != ClientStatus.ARCHIVED)),
        "active_clients": _count(db, clients.where(Client.status == ClientStatus.ACTIVE)),
        "pending_documents": _count(
            db, scope_by_client(select(DocumentRequest.id), DocumentRequest, principal).where(DocumentRequest.status.in_(OPEN_REQ))
        ),
        "documents_awaiting_approval": _count(
            db,
            scope_by_client(select(Document.id), Document, principal).where(
                Document.status.in_([DocumentStatus.UPLOADED, DocumentStatus.UNDER_REVIEW]),
                Document.source == "STAFF",
                Document.deleted_at.is_(None),
            ),
        ),
        "documents_delivered": _count(
            db, scope_by_client(select(DocumentDelivery.id), DocumentDelivery, principal).where(DocumentDelivery.sent_at.is_not(None))
        ),
        "open_tasks": _count(db, tasks_open),
        "overdue_tasks": _count(db, tasks_open.where(Task.due_date < today)),
        "pending_invoices": _count(db, scope_by_client(select(Invoice.id), Invoice, principal).where(Invoice.status.in_(OPEN_INV))),
        "outstanding_amount": str(
            db.execute(
                scope_by_client(select(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0)), Invoice, principal).where(
                    Invoice.status.in_(OPEN_INV)
                )
            ).scalar_one()
        ),
        "upcoming_deadlines": _count(
            db,
            select(ComplianceEvent.id).where(
                ComplianceEvent.organization_id == principal.org_id,
                ComplianceEvent.due_date >= today,
                ComplianceEvent.due_date <= today + timedelta(days=30),
            ),
        ),
        "whatsapp_conversations": _count(
            db,
            select(Conversation.id).where(
                Conversation.organization_id == principal.org_id, Conversation.last_message_at >= now_utc() - timedelta(days=7)
            ),
        )
        if principal.has(Perm.WHATSAPP_VIEW)
        else 0,
        "human_handoffs_waiting": _count(
            db,
            select(Conversation.id).where(
                Conversation.organization_id == principal.org_id, Conversation.handover_state == "HUMAN_REQUESTED"
            ),
        ),
    }


def _months_back(n: int) -> date:
    d = date.today().replace(day=1)
    for _ in range(n - 1):
        d = (d - timedelta(days=1)).replace(day=1)
    return d


def client_growth(db: Session, p: Principal) -> dict[str, Any]:
    month = func.date_trunc("month", Client.created_at)
    rows = db.execute(
        select(month.label("m"), func.count())
        .where(Client.id.in_(visible_client_ids_subquery(p)), Client.created_at >= _months_back(12))
        .group_by(month)
        .order_by(month)
    ).all()
    return {"columns": ["month", "new_clients"], "rows": [{"month": m.strftime("%Y-%m"), "new_clients": c} for m, c in rows]}


def pending_documents(db: Session, p: Principal) -> dict[str, Any]:
    reqs = (
        db.execute(
            scope_by_client(select(DocumentRequest), DocumentRequest, p)
            .where(DocumentRequest.status.in_(OPEN_REQ))
            .order_by(DocumentRequest.due_date.asc().nulls_last())
        )
        .unique()
        .scalars()
    )
    return {
        "columns": ["client", "request", "pending_items", "due_date", "status", "reminders_sent"],
        "rows": [
            {
                "client": r.client.name,
                "request": r.title,
                "pending_items": ", ".join(i.name for i in r.items if i.status == "PENDING"),
                "due_date": r.due_date.isoformat() if r.due_date else "",
                "status": r.status,
                "reminders_sent": r.reminders_sent,
            }
            for r in reqs
        ],
    }


def document_delivery(db: Session, p: Principal) -> dict[str, Any]:
    since = now_utc() - timedelta(days=90)
    rows = db.execute(
        scope_by_client(  # type: ignore[type-var]
            select(
                cast(DocumentDelivery.created_at, Date).label("day"),
                func.count().label("created"),
                func.count(DocumentDelivery.sent_at).label("sent"),
                func.count(DocumentDelivery.delivered_at).label("delivered"),
                func.count(DocumentDelivery.read_at).label("read"),
                func.count(DocumentDelivery.downloaded_at).label("downloaded"),
                func.sum(case((DocumentDelivery.status == "FAILED", 1), else_=0)).label("failed"),
            ),
            DocumentDelivery,
            p,
        )
        .where(DocumentDelivery.created_at >= since)
        .group_by("day")
        .order_by("day")
    ).all()
    return {
        "columns": ["day", "created", "sent", "delivered", "read", "downloaded", "failed"],
        "rows": [dict(r._mapping) | {"day": r.day.isoformat()} for r in rows],
    }


def task_completion(db: Session, p: Principal) -> dict[str, Any]:
    m_created = func.date_trunc("month", Task.created_at)
    created = dict(
        db.execute(
            scope_by_client(select(m_created, func.count()), Task, p).where(Task.created_at >= _months_back(6)).group_by(m_created)
        ).all()
    )
    m_done = func.date_trunc("month", Task.completed_at)
    done = dict(
        db.execute(
            scope_by_client(select(m_done, func.count()), Task, p).where(Task.completed_at >= _months_back(6)).group_by(m_done)
        ).all()
    )
    months = sorted(set(created) | set(done))
    return {
        "columns": ["month", "created", "completed"],
        "rows": [{"month": m.strftime("%Y-%m"), "created": created.get(m, 0), "completed": done.get(m, 0)} for m in months],
    }


def whatsapp_activity(db: Session, p: Principal) -> dict[str, Any]:
    p.require(Perm.WHATSAPP_VIEW)
    day = cast(Message.timestamp, Date)
    rows = db.execute(
        select(
            day.label("day"),
            func.sum(case((Message.direction == "INBOUND", 1), else_=0)).label("inbound"),
            func.sum(case((Message.direction == "OUTBOUND", 1), else_=0)).label("outbound"),
            func.sum(case((Message.status == "FAILED", 1), else_=0)).label("failed"),
        )
        .where(Message.organization_id == p.org_id, Message.timestamp >= now_utc() - timedelta(days=30))
        .group_by(day)
        .order_by(day)
    ).all()
    return {
        "columns": ["day", "inbound", "outbound", "failed"],
        "rows": [
            {"day": r.day.isoformat(), "inbound": int(r.inbound or 0), "outbound": int(r.outbound or 0), "failed": int(r.failed or 0)}
            for r in rows
        ],
    }


def invoice_collection(db: Session, p: Principal) -> dict[str, Any]:
    p.require(Perm.INVOICE_VIEW)
    m_i = func.date_trunc("month", Invoice.issue_date)
    invoiced = dict(
        db.execute(
            scope_by_client(select(m_i, func.sum(Invoice.total)), Invoice, p)
            .where(Invoice.status != InvoiceStatus.CANCELLED, Invoice.status != InvoiceStatus.DRAFT, Invoice.issue_date >= _months_back(12))
            .group_by(m_i)
        ).all()
    )
    m_p = func.date_trunc("month", Payment.paid_at)
    collected = dict(
        db.execute(
            scope_by_client(select(m_p, func.sum(Payment.amount)), Payment, p).where(Payment.paid_at >= _months_back(12)).group_by(m_p)
        ).all()
    )
    months = sorted(set(invoiced) | set(collected))
    return {
        "columns": ["month", "invoiced", "collected"],
        "rows": [
            {"month": m.strftime("%Y-%m"), "invoiced": str(invoiced.get(m, 0) or 0), "collected": str(collected.get(m, 0) or 0)}
            for m in months
        ],
    }


def employee_workload(db: Session, p: Principal) -> dict[str, Any]:
    p.require(Perm.REPORT_VIEW)
    today = date.today()
    rows = db.execute(
        select(
            User.full_name,
            func.count(Task.id).filter(Task.status.not_in(DONE)).label("open_tasks"),
            func.count(Task.id).filter(and_(Task.status.not_in(DONE), Task.due_date < today)).label("overdue_tasks"),
            func.count(Task.id).filter(Task.status.in_(DONE)).label("completed_tasks"),
        )
        .select_from(User)
        .outerjoin(Task, and_(Task.assigned_employee_id == User.id, Task.organization_id == p.org_id))
        .where(User.organization_id == p.org_id, User.is_active.is_(True))
        .group_by(User.id, User.full_name)
        .order_by(User.full_name)
    ).all()
    clients = dict(
        db.execute(
            select(Client.assigned_employee_id, func.count())
            .where(Client.organization_id == p.org_id, Client.status != ClientStatus.ARCHIVED)
            .group_by(Client.assigned_employee_id)
        ).all()
    )
    users = {u.full_name: u.id for u in db.execute(select(User).where(User.organization_id == p.org_id)).unique().scalars()}
    return {
        "columns": ["employee", "clients", "open_tasks", "overdue_tasks", "completed_tasks"],
        "rows": [
            {
                "employee": r.full_name,
                "clients": clients.get(users.get(r.full_name), 0),
                "open_tasks": r.open_tasks,
                "overdue_tasks": r.overdue_tasks,
                "completed_tasks": r.completed_tasks,
            }
            for r in rows
        ],
    }


def overdue_tasks(db: Session, p: Principal) -> dict[str, Any]:
    rows = (
        db.execute(
            scope_by_client(select(Task), Task, p).where(Task.status.not_in(DONE), Task.due_date < date.today()).order_by(Task.due_date)
        )
        .unique()
        .scalars()
    )
    return {
        "columns": ["client", "task", "service", "due_date", "days_overdue", "assigned_to", "status"],
        "rows": [
            {
                "client": t.client.name,
                "task": t.title,
                "service": t.service_type,
                "due_date": t.due_date.isoformat() if t.due_date else "",
                "days_overdue": (date.today() - t.due_date).days if t.due_date else 0,
                "assigned_to": t.assigned_employee.full_name if t.assigned_employee else "",
                "status": t.status,
            }
            for t in rows
        ],
    }


REPORTS = {
    "client-growth": client_growth,
    "pending-documents": pending_documents,
    "document-delivery": document_delivery,
    "task-completion": task_completion,
    "whatsapp-activity": whatsapp_activity,
    "invoice-collection": invoice_collection,
    "employee-workload": employee_workload,
    "overdue-tasks": overdue_tasks,
}


def run_report(db: Session, p: Principal, name: str) -> dict[str, Any]:
    p.require(Perm.REPORT_VIEW)
    fn = REPORTS.get(name)
    if fn is None:
        raise NotFound("Report not found")
    return fn(db, p)


def to_csv(report: dict[str, Any]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=report["columns"], extrasaction="ignore")
    w.writeheader()
    for row in report["rows"]:
        # Neutralise spreadsheet formula injection
        w.writerow({k: ("'" + v if isinstance(v, str) and v[:1] in ("=", "+", "-", "@") else v) for k, v in row.items()})
    return buf.getvalue()
