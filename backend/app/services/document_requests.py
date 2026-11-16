"""Document collection: CA requests documents, client uploads (portal/WhatsApp), status tracked."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.core.context import Principal, system_principal
from app.core.errors import NotFound, ValidationFailed
from app.core.permissions import Perm
from app.core.security import now_utc
from app.models import Client, Document, DocumentRequest, DocumentRequestItem, Task
from app.models.enums import (
    DocumentRequestStatus,
    DocumentSource,
    RequestItemStatus,
    TaskStatus,
    TemplateKey,
)
from app.repositories.base import paginate
from app.schemas.work import DocumentRequestCreate
from app.services import audit, messaging, notifications
from app.services.audit import AuditAction
from app.services.scope import get_visible_client, scope_by_client

OPEN_STATUSES = [DocumentRequestStatus.PENDING, DocumentRequestStatus.PARTIAL, DocumentRequestStatus.OVERDUE]


def _scoped(principal: Principal) -> Select[Any]:
    return scope_by_client(select(DocumentRequest), DocumentRequest, principal)


def get_request(db: Session, principal: Principal, request_id: uuid.UUID) -> DocumentRequest:
    r = db.execute(_scoped(principal).where(DocumentRequest.id == request_id)).unique().scalar_one_or_none()
    if r is None:
        raise NotFound("Document request not found")
    return r


def list_requests(
    db: Session,
    principal: Principal,
    *,
    status: str | None = None,
    client_id: uuid.UUID | None = None,
    q: str | None = None,
    open_only: bool = False,
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[DocumentRequest], int]:
    if principal.is_staff:
        principal.require(Perm.TASK_VIEW)
    stmt = _scoped(principal)
    if status:
        stmt = stmt.where(DocumentRequest.status == status)
    if open_only:
        stmt = stmt.where(DocumentRequest.status.in_(OPEN_STATUSES))
    if client_id:
        stmt = stmt.where(DocumentRequest.client_id == client_id)
    if q:
        stmt = stmt.join(Client, Client.id == DocumentRequest.client_id).where(
            or_(DocumentRequest.title.ilike(f"%{q[:100]}%"), Client.name.ilike(f"%{q[:100]}%"))
        )
    stmt = stmt.order_by(DocumentRequest.due_date.asc().nulls_last(), DocumentRequest.created_at.desc())
    rows, total = paginate(db, stmt, page, page_size)
    return list(rows), total


def pending_item_names(req: DocumentRequest) -> list[str]:
    return [i.name for i in req.items if i.status == RequestItemStatus.PENDING]


def create_request(db: Session, principal: Principal, data: DocumentRequestCreate) -> DocumentRequest:
    principal.require(Perm.DOCUMENT_REQUEST_CREATE)
    client = get_visible_client(db, principal, data.client_id)
    task = None
    if data.task_id:
        task = (
            db.execute(select(Task).where(Task.id == data.task_id, Task.organization_id == principal.org_id, Task.client_id == client.id))
            .unique()
            .scalar_one_or_none()
        )
        if task is None:
            raise ValidationFailed("Task not found for this client")
    req = DocumentRequest(
        organization_id=principal.org_id,
        client_id=client.id,
        task_id=data.task_id,
        title=data.title,
        instructions=data.instructions,
        due_date=data.due_date,
        created_by=principal.user_id,
        status=DocumentRequestStatus.PENDING,
    )
    req.items = [
        DocumentRequestItem(
            organization_id=principal.org_id, name=i.name, document_type=i.document_type, is_required=i.is_required, position=n
        )
        for n, i in enumerate(data.items)
    ]
    db.add(req)
    db.flush()
    if task and task.status in (TaskStatus.NEW_REQUEST,):
        task.status = TaskStatus.DOCUMENTS_PENDING
    audit.record(
        db,
        principal,
        AuditAction.DOCUMENT_REQUEST_CREATED,
        resource="document_request",
        resource_id=req.id,
        client_id=client.id,
        metadata={"items": len(data.items)},
    )
    if data.notify_client:
        notify_client(db, req, client)
    db.commit()
    db.refresh(req)
    return req


def notify_client(db: Session, req: DocumentRequest, client: Client) -> None:
    due = req.due_date.strftime("%d %b %Y") if req.due_date else "at the earliest"
    msg = messaging.send_template_to_client(
        db,
        client,
        TemplateKey.DOCUMENT_REQUEST,
        [client.name, messaging.firm_name(db, req.organization_id), req.title, ", ".join(pending_item_names(req))[:500], due],
        url_suffix="requests",
    )
    if msg.status != "FAILED":
        req.notified_at = now_utc()


def recompute_status(req: DocumentRequest, today: date | None = None) -> str:
    today = today or date.today()
    required = [i for i in req.items if i.is_required] or req.items
    received = [i for i in required if i.status == RequestItemStatus.RECEIVED]
    if req.status == DocumentRequestStatus.CANCELLED:
        return req.status
    if len(received) == len(required):
        req.status = DocumentRequestStatus.COMPLETE
        req.completed_at = req.completed_at or now_utc()
    elif req.due_date and req.due_date < today:
        req.status = DocumentRequestStatus.OVERDUE
    elif received or any(i.status == RequestItemStatus.RECEIVED for i in req.items):
        req.status = DocumentRequestStatus.PARTIAL
    else:
        req.status = DocumentRequestStatus.PENDING
    return req.status


def _on_complete(db: Session, req: DocumentRequest) -> None:
    if req.task_id:
        task = db.get(Task, req.task_id)
        if task and task.status in (TaskStatus.NEW_REQUEST, TaskStatus.DOCUMENTS_PENDING):
            task.status = TaskStatus.DOCUMENTS_RECEIVED
    client = db.get(Client, req.client_id)
    notifications.notify_client_owner(
        db,
        req.organization_id,
        client.assigned_employee_id if client else None,
        fallback_perm=Perm.DOCUMENT_REQUEST_MANAGE,
        type_="DOCUMENT_REQUEST_COMPLETE",
        title=f"All documents received: {req.title}",
        body=f"{client.name if client else 'Client'} has submitted all requested documents.",
        link=f"/document-requests/{req.id}",
    )


def attach_document(db: Session, req: DocumentRequest, doc: Document, item_id: uuid.UUID | None = None) -> DocumentRequestItem | None:
    """Mark a request item received with the given document. Picks the first matching pending
    item (by document type, then first pending) if no item is specified."""
    if req.status in (DocumentRequestStatus.COMPLETE, DocumentRequestStatus.CANCELLED):
        return None
    pending = [i for i in req.items if i.status == RequestItemStatus.PENDING]
    item = None
    if item_id:
        item = next((i for i in req.items if i.id == item_id), None)
        if item is None:
            raise NotFound("Request item not found")
    elif pending:
        item = next((i for i in pending if i.document_type and i.document_type == doc.document_type), pending[0])
    if item is None:
        return None
    item.status = RequestItemStatus.RECEIVED
    item.document_id = doc.id
    item.received_at = now_utc()
    before = req.status
    recompute_status(req)
    if req.status == DocumentRequestStatus.COMPLETE and before != DocumentRequestStatus.COMPLETE:
        _on_complete(db, req)
    audit.record(
        db,
        system_principal(req.organization_id),
        AuditAction.DOCUMENT_REQUEST_UPDATED,
        resource="document_request",
        resource_id=req.id,
        client_id=req.client_id,
        metadata={"item": item.name, "document_id": str(doc.id), "status": req.status},
    )
    return item


def client_upload_for_request(
    db: Session, principal: Principal, request_id: uuid.UUID, item_id: uuid.UUID | None, file_name: str, content: bytes
) -> DocumentRequestItem | None:
    from app.services.documents import upload_document

    req = get_request(db, principal, request_id)
    item = next((i for i in req.items if i.id == item_id), None) if item_id else None
    if item_id and item is None:
        raise NotFound("Request item not found")
    doc = upload_document(
        db,
        principal,
        client_id=req.client_id,
        file_name=file_name,
        content=content,
        document_type=(item.document_type if item and item.document_type else "OTHER"),
        description=f"Uploaded for request: {req.title}" + (f" — {item.name}" if item else ""),
        task_id=req.task_id,
        source=DocumentSource.CLIENT_PORTAL if principal.is_client else DocumentSource.STAFF,
        commit=False,
    )
    result = attach_document(db, req, doc, item_id)
    db.commit()
    return result


def mark_item(db: Session, principal: Principal, request_id: uuid.UUID, item_id: uuid.UUID, received: bool) -> DocumentRequest:
    principal.require(Perm.DOCUMENT_REQUEST_MANAGE)
    req = get_request(db, principal, request_id)
    item = next((i for i in req.items if i.id == item_id), None)
    if item is None:
        raise NotFound("Request item not found")
    item.status = RequestItemStatus.RECEIVED if received else RequestItemStatus.PENDING
    item.received_at = now_utc() if received else None
    before = req.status
    if not received and req.status == DocumentRequestStatus.COMPLETE:
        req.status = DocumentRequestStatus.PARTIAL
        req.completed_at = None
    recompute_status(req)
    if req.status == DocumentRequestStatus.COMPLETE and before != DocumentRequestStatus.COMPLETE:
        _on_complete(db, req)
    audit.record(
        db,
        principal,
        AuditAction.DOCUMENT_REQUEST_UPDATED,
        resource="document_request",
        resource_id=req.id,
        client_id=req.client_id,
        metadata={"item": item.name, "received": received},
    )
    db.commit()
    return req


def cancel_request(db: Session, principal: Principal, request_id: uuid.UUID) -> DocumentRequest:
    principal.require(Perm.DOCUMENT_REQUEST_MANAGE)
    req = get_request(db, principal, request_id)
    req.status = DocumentRequestStatus.CANCELLED
    audit.record(
        db,
        principal,
        AuditAction.DOCUMENT_REQUEST_UPDATED,
        resource="document_request",
        resource_id=req.id,
        client_id=req.client_id,
        metadata={"status": "CANCELLED"},
    )
    db.commit()
    return req


def resend_notification(db: Session, principal: Principal, request_id: uuid.UUID) -> DocumentRequest:
    principal.require(Perm.DOCUMENT_REQUEST_MANAGE)
    req = get_request(db, principal, request_id)
    client = db.get(Client, req.client_id)
    assert client is not None
    notify_client(db, req, client)
    db.commit()
    return req


def open_requests_for_client(db: Session, org_id: uuid.UUID, client_id: uuid.UUID) -> list[DocumentRequest]:
    return list(
        db.execute(
            select(DocumentRequest)
            .where(
                DocumentRequest.organization_id == org_id, DocumentRequest.client_id == client_id, DocumentRequest.status.in_(OPEN_STATUSES)
            )
            .order_by(DocumentRequest.due_date.asc().nulls_last())
        )
        .unique()
        .scalars()
    )
