"""Task management with dashboard buckets (overdue / today / this week / mine / completed)."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.errors import NotFound, ValidationFailed
from app.core.permissions import Perm
from app.core.security import now_utc
from app.models import Client, Task, User
from app.models.enums import TASK_DONE_STATUSES, TaskStatus, TemplateKey
from app.repositories.base import paginate
from app.schemas.work import TaskCreate, TaskUpdate
from app.services import audit, messaging
from app.services.audit import AuditAction
from app.services.scope import get_visible_client, visible_client_ids_subquery

STATUS_LABELS = {
    "NEW_REQUEST": "Received",
    "DOCUMENTS_PENDING": "Waiting for your documents",
    "DOCUMENTS_RECEIVED": "Documents received",
    "WORK_IN_PROGRESS": "Work in progress",
    "UNDER_REVIEW": "Under review by CA",
    "FILED": "Filed",
    "COMPLETED": "Completed",
    "DELIVERED": "Completed and delivered",
}


def _scoped(principal: Principal) -> Select[Any]:
    stmt = select(Task).where(Task.organization_id == principal.org_id)
    if principal.is_client:
        return stmt.where(Task.client_id == principal.client_id)
    if not principal.sees_all_clients:
        stmt = stmt.where(or_(Task.assigned_employee_id == principal.user_id, Task.client_id.in_(visible_client_ids_subquery(principal))))
    return stmt


def get_task(db: Session, principal: Principal, task_id: uuid.UUID) -> Task:
    if principal.is_staff:
        principal.require(Perm.TASK_VIEW)
    t = db.execute(_scoped(principal).where(Task.id == task_id)).unique().scalar_one_or_none()
    if t is None:
        raise NotFound("Task not found")
    return t


def list_tasks(
    db: Session,
    principal: Principal,
    *,
    bucket: str | None = None,
    q: str | None = None,
    status: str | None = None,
    client_id: uuid.UUID | None = None,
    assigned_employee_id: uuid.UUID | None = None,
    service_type: str | None = None,
    sort: str = "due_date",
    order: str = "asc",
    page: int = 1,
    page_size: int = 25,
    today: date | None = None,
) -> tuple[list[Task], int]:
    if principal.is_staff:
        principal.require(Perm.TASK_VIEW)
    today = today or date.today()
    stmt = _scoped(principal)
    open_ = Task.status.not_in([s.value for s in TASK_DONE_STATUSES])
    if bucket == "overdue":
        stmt = stmt.where(open_, Task.due_date < today)
    elif bucket == "today":
        stmt = stmt.where(open_, Task.due_date == today)
    elif bucket == "week":
        stmt = stmt.where(open_, Task.due_date >= today, Task.due_date <= today + timedelta(days=6 - today.weekday()))
    elif bucket == "mine":
        stmt = stmt.where(open_, Task.assigned_employee_id == principal.user_id)
    elif bucket == "completed":
        stmt = stmt.where(Task.status.in_([s.value for s in TASK_DONE_STATUSES]))
    elif bucket == "open":
        stmt = stmt.where(open_)
    if q:
        stmt = stmt.join(Client, Client.id == Task.client_id).where(
            or_(Task.title.ilike(f"%{q[:100]}%"), Client.name.ilike(f"%{q[:100]}%"))
        )
    if status:
        stmt = stmt.where(Task.status == status)
    if client_id:
        stmt = stmt.where(Task.client_id == client_id)
    if assigned_employee_id:
        stmt = stmt.where(Task.assigned_employee_id == assigned_employee_id)
    if service_type:
        stmt = stmt.where(Task.service_type == service_type)
    col = {"due_date": Task.due_date, "created_at": Task.created_at, "priority": Task.priority, "title": Task.title}.get(
        sort, Task.due_date
    )
    stmt = stmt.order_by(col.desc().nulls_last() if order == "desc" else col.asc().nulls_last(), Task.id)
    rows, total = paginate(db, stmt, page, page_size)
    return list(rows), total


def bucket_counts(db: Session, principal: Principal, today: date | None = None) -> dict[str, int]:
    out = {}
    for b in ("overdue", "today", "week", "mine", "completed", "open"):
        _, total = list_tasks(db, principal, bucket=b, page=1, page_size=1, today=today)
        out[b] = total
    return out


def _validate_assignee(db: Session, principal: Principal, user_id: uuid.UUID | None) -> None:
    if (
        user_id
        and not db.execute(
            select(User.id).where(User.id == user_id, User.organization_id == principal.org_id, User.is_active.is_(True))
        ).first()
    ):
        raise ValidationFailed("Assignee not found in this organization")


def create_task(db: Session, principal: Principal, data: TaskCreate) -> Task:
    principal.require(Perm.TASK_CREATE)
    client = get_visible_client(db, principal, data.client_id)
    assignee = data.assigned_employee_id
    if assignee and assignee != principal.user_id:
        principal.require(Perm.TASK_ASSIGN)
    assignee = assignee or client.assigned_employee_id or principal.user_id
    _validate_assignee(db, principal, assignee)
    t = Task(
        organization_id=principal.org_id,
        client_id=client.id,
        assigned_employee_id=assignee,
        title=data.title,
        description=data.description,
        service_type=data.service_type,
        financial_year=data.financial_year,
        priority=data.priority,
        status=data.status,
        due_date=data.due_date,
        created_by=principal.user_id,
    )
    db.add(t)
    db.flush()
    audit.record(db, principal, AuditAction.TASK_CREATED, resource="task", resource_id=t.id, client_id=client.id)
    db.commit()
    db.refresh(t)
    return t


def set_status(task: Task, status: TaskStatus) -> None:
    task.status = status
    if status in TASK_DONE_STATUSES and task.completed_at is None:
        task.completed_at = now_utc()
    if status not in TASK_DONE_STATUSES:
        task.completed_at = None
    if status == TaskStatus.FILED and task.filed_at is None:
        task.filed_at = now_utc()


def update_task(db: Session, principal: Principal, task_id: uuid.UUID, data: TaskUpdate) -> Task:
    principal.require(Perm.TASK_UPDATE)
    t = get_task(db, principal, task_id)
    payload = data.model_dump(exclude_unset=True)
    notify = payload.pop("notify_client", False)
    if "assigned_employee_id" in payload and payload["assigned_employee_id"] != t.assigned_employee_id:
        principal.require(Perm.TASK_ASSIGN)
        _validate_assignee(db, principal, payload["assigned_employee_id"])
    old_status = t.status
    status = payload.pop("status", None)
    for k, v in payload.items():
        setattr(t, k, v)
    if status and status != t.status:
        set_status(t, TaskStatus(status))
    audit.record(
        db,
        principal,
        AuditAction.TASK_UPDATED,
        resource="task",
        resource_id=t.id,
        client_id=t.client_id,
        metadata={"fields": sorted(payload), "status": [old_status, t.status] if status else None},
    )
    if notify and status and status != old_status and status in (TaskStatus.FILED, TaskStatus.COMPLETED, TaskStatus.DELIVERED):
        client = db.get(Client, t.client_id)
        if client:
            messaging.send_template_to_client(
                db,
                client,
                TemplateKey.TASK_COMPLETED,
                [client.name, t.title, STATUS_LABELS[t.status], messaging.firm_name(db, principal.org_id)],
            )
    db.commit()
    db.refresh(t)
    return t


def task_counts_by_status(db: Session, principal: Principal) -> dict[str, int]:
    stmt = _scoped(principal).with_only_columns(Task.status, func.count()).group_by(Task.status)
    return {s: int(c) for s, c in db.execute(stmt).all()}
