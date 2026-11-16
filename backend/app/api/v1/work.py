"""Tasks, document requests, compliance calendar and support requests."""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, File, Query, UploadFile

from app.api.deps import DB, Staff
from app.api.v1.documents import read_upload
from app.schemas.common import Page
from app.schemas.work import (
    ComplianceEventIn,
    ComplianceEventOut,
    DocumentRequestCreate,
    DocumentRequestOut,
    SupportRequestOut,
    SupportRequestUpdate,
    TaskCreate,
    TaskOut,
    TaskUpdate,
)
from app.services import document_requests as dr
from app.services import misc
from app.services import tasks as task_svc

router = APIRouter(tags=["work"])


@router.get("/tasks", response_model=Page[TaskOut])
def list_tasks(
    principal: Staff,
    db: DB,
    bucket: str | None = Query(None, pattern="^(overdue|today|week|mine|completed|open)$"),
    q: str | None = None,
    status: str | None = None,
    client_id: uuid.UUID | None = None,
    assigned_employee_id: uuid.UUID | None = None,
    service_type: str | None = None,
    sort: str = Query("due_date", pattern="^(due_date|created_at|priority|title)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> Page[TaskOut]:
    rows, total = task_svc.list_tasks(
        db,
        principal,
        bucket=bucket,
        q=q,
        status=status,
        client_id=client_id,
        assigned_employee_id=assigned_employee_id,
        service_type=service_type,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )
    return Page(items=[TaskOut.model_validate(t) for t in rows], total=total, page=page, page_size=page_size)


@router.get("/tasks/buckets")
def task_buckets(principal: Staff, db: DB) -> dict[str, int]:
    return task_svc.bucket_counts(db, principal)


@router.post("/tasks", response_model=TaskOut, status_code=201)
def create_task(body: TaskCreate, principal: Staff, db: DB) -> TaskOut:
    return TaskOut.model_validate(task_svc.create_task(db, principal, body))


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: uuid.UUID, principal: Staff, db: DB) -> TaskOut:
    return TaskOut.model_validate(task_svc.get_task(db, principal, task_id))


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: uuid.UUID, body: TaskUpdate, principal: Staff, db: DB) -> TaskOut:
    return TaskOut.model_validate(task_svc.update_task(db, principal, task_id, body))


# --- document requests --------------------------------------------------------------


@router.get("/document-requests", response_model=Page[DocumentRequestOut])
def list_requests(
    principal: Staff,
    db: DB,
    status: str | None = None,
    client_id: uuid.UUID | None = None,
    q: str | None = None,
    open_only: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> Page[DocumentRequestOut]:
    rows, total = dr.list_requests(
        db, principal, status=status, client_id=client_id, q=q, open_only=open_only, page=page, page_size=page_size
    )
    return Page(items=[DocumentRequestOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.post("/document-requests", response_model=DocumentRequestOut, status_code=201)
def create_request(body: DocumentRequestCreate, principal: Staff, db: DB) -> DocumentRequestOut:
    return DocumentRequestOut.model_validate(dr.create_request(db, principal, body))


@router.get("/document-requests/{request_id}", response_model=DocumentRequestOut)
def get_request(request_id: uuid.UUID, principal: Staff, db: DB) -> DocumentRequestOut:
    return DocumentRequestOut.model_validate(dr.get_request(db, principal, request_id))


@router.post("/document-requests/{request_id}/items/{item_id}", response_model=DocumentRequestOut)
def mark_item(request_id: uuid.UUID, item_id: uuid.UUID, received: bool, principal: Staff, db: DB) -> DocumentRequestOut:
    return DocumentRequestOut.model_validate(dr.mark_item(db, principal, request_id, item_id, received))


@router.post("/document-requests/{request_id}/items/{item_id}/upload", response_model=DocumentRequestOut)
async def staff_upload_item(
    request_id: uuid.UUID, item_id: uuid.UUID, principal: Staff, db: DB, file: UploadFile = File(...)
) -> DocumentRequestOut:
    content = await read_upload(file)
    dr.client_upload_for_request(db, principal, request_id, item_id, file.filename or "document", content)
    return DocumentRequestOut.model_validate(dr.get_request(db, principal, request_id))


@router.post("/document-requests/{request_id}/remind", response_model=DocumentRequestOut)
def remind(request_id: uuid.UUID, principal: Staff, db: DB) -> DocumentRequestOut:
    return DocumentRequestOut.model_validate(dr.resend_notification(db, principal, request_id))


@router.post("/document-requests/{request_id}/cancel", response_model=DocumentRequestOut)
def cancel(request_id: uuid.UUID, principal: Staff, db: DB) -> DocumentRequestOut:
    return DocumentRequestOut.model_validate(dr.cancel_request(db, principal, request_id))


# --- compliance calendar ------------------------------------------------------------


@router.get("/compliance", response_model=list[ComplianceEventOut])
def list_compliance(
    principal: Staff, db: DB, start: date | None = None, end: date | None = None, category: str | None = None
) -> list[ComplianceEventOut]:
    return [ComplianceEventOut.model_validate(e) for e in misc.list_compliance(db, principal, start=start, end=end, category=category)]


@router.post("/compliance", response_model=ComplianceEventOut, status_code=201)
def create_compliance(body: ComplianceEventIn, principal: Staff, db: DB) -> ComplianceEventOut:
    return ComplianceEventOut.model_validate(misc.create_compliance(db, principal, body))


@router.delete("/compliance/{event_id}", status_code=204)
def delete_compliance(event_id: uuid.UUID, principal: Staff, db: DB) -> None:
    misc.delete_compliance(db, principal, event_id)


# --- support requests --------------------------------------------------------------


@router.get("/support-requests", response_model=Page[SupportRequestOut])
def list_support(
    principal: Staff, db: DB, status: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)
) -> Page[SupportRequestOut]:
    rows, total = misc.list_support(db, principal, status=status, page=page, page_size=page_size)
    return Page(items=[SupportRequestOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.patch("/support-requests/{sr_id}", response_model=SupportRequestOut)
def update_support(sr_id: uuid.UUID, body: SupportRequestUpdate, principal: Staff, db: DB) -> SupportRequestOut:
    return SupportRequestOut.model_validate(misc.update_support(db, principal, sr_id, body))
