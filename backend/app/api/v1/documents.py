from __future__ import annotations

import uuid

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import StreamingResponse

from app.api.deps import DB, Staff
from app.core.config import settings
from app.core.errors import NotFound, ValidationFailed
from app.core.security import decode_signed_download_token
from app.integrations.storage import get_storage
from app.models import Document, DocumentVersion
from app.schemas.common import Page
from app.schemas.document import (
    AccessLogOut,
    DeliverRequest,
    DeliveryOut,
    DocumentDetail,
    DocumentOut,
    DocumentUpdate,
    DownloadUrlResponse,
    RejectRequest,
    ReviewRequest,
)
from app.services import delivery
from app.services import documents as svc

router = APIRouter(prefix="/documents", tags=["documents"])
files_router = APIRouter(tags=["files"])


async def read_upload(file: UploadFile) -> bytes:
    data = await file.read(settings.MAX_UPLOAD_MB * 1024 * 1024 + 1)
    if len(data) > settings.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationFailed(f"File exceeds {settings.MAX_UPLOAD_MB} MB limit", code="FILE_TOO_LARGE")
    return data


def _detail(db: DB, principal: Staff, doc: Document) -> DocumentDetail:
    extras = svc.document_detail_extras(db, principal, doc)
    out = DocumentDetail.model_validate(doc)
    out.deliveries = [DeliveryOut.model_validate(d) for d in extras["deliveries"]]
    out.access_history = [AccessLogOut(**a) for a in extras["access_history"]]
    return out


@router.get("", response_model=Page[DocumentOut])
def list_documents(
    principal: Staff,
    db: DB,
    q: str | None = None,
    client_id: uuid.UUID | None = None,
    document_type: str | None = None,
    financial_year: str | None = None,
    status: str | None = None,
    source: str | None = None,
    sort: str = Query("created_at", pattern="^(created_at|updated_at|file_name|financial_year)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> Page[DocumentOut]:
    rows, total = svc.list_documents(
        db,
        principal,
        q=q,
        client_id=client_id,
        document_type=document_type,
        financial_year=financial_year,
        status=status,
        source=source,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )
    return Page(items=[DocumentOut.model_validate(d) for d in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    principal: Staff,
    db: DB,
    file: UploadFile = File(...),
    client_id: uuid.UUID = Form(...),
    document_type: str = Form("OTHER"),
    financial_year: str | None = Form(None),
    assessment_year: str | None = Form(None),
    description: str | None = Form(None),
    task_id: uuid.UUID | None = Form(None),
) -> DocumentOut:
    content = await read_upload(file)
    doc = svc.upload_document(
        db,
        principal,
        client_id=client_id,
        file_name=file.filename or "document",
        content=content,
        document_type=document_type,
        financial_year=financial_year or None,
        assessment_year=assessment_year or None,
        description=description,
        task_id=task_id,
    )
    return DocumentOut.model_validate(doc)


@router.get("/{doc_id}", response_model=DocumentDetail)
def get_document(doc_id: uuid.UUID, principal: Staff, db: DB) -> DocumentDetail:
    return _detail(db, principal, svc.get_document(db, principal, doc_id))


@router.patch("/{doc_id}", response_model=DocumentOut)
def update_document(doc_id: uuid.UUID, body: DocumentUpdate, principal: Staff, db: DB) -> DocumentOut:
    return DocumentOut.model_validate(svc.update_metadata(db, principal, doc_id, body.model_dump(exclude_unset=True)))


@router.post("/{doc_id}/versions", response_model=DocumentOut, status_code=201)
async def upload_version(doc_id: uuid.UUID, principal: Staff, db: DB, file: UploadFile = File(...)) -> DocumentOut:
    content = await read_upload(file)
    return DocumentOut.model_validate(svc.upload_new_version(db, principal, doc_id, file_name=file.filename or "document", content=content))


@router.post("/{doc_id}/submit", response_model=DocumentOut)
def submit(doc_id: uuid.UUID, principal: Staff, db: DB) -> DocumentOut:
    return DocumentOut.model_validate(svc.submit_for_review(db, principal, doc_id))


@router.post("/{doc_id}/approve", response_model=DocumentOut)
def approve(doc_id: uuid.UUID, principal: Staff, db: DB, body: ReviewRequest | None = None) -> DocumentOut:
    body = body or ReviewRequest()
    return DocumentOut.model_validate(svc.approve_document(db, principal, doc_id, note=body.note, deliver=body.deliver))


@router.post("/{doc_id}/reject", response_model=DocumentOut)
def reject(doc_id: uuid.UUID, body: RejectRequest, principal: Staff, db: DB) -> DocumentOut:
    return DocumentOut.model_validate(svc.reject_document(db, principal, doc_id, reason=body.reason))


@router.post("/{doc_id}/deliver", response_model=DeliveryOut)
def deliver(doc_id: uuid.UUID, principal: Staff, db: DB, body: DeliverRequest | None = None) -> DeliveryOut:
    d = delivery.manual_deliver(db, principal, doc_id, body.version_id if body else None)
    return DeliveryOut.model_validate(d)


@router.post("/{doc_id}/archive", response_model=DocumentOut)
def archive(doc_id: uuid.UUID, principal: Staff, db: DB) -> DocumentOut:
    return DocumentOut.model_validate(svc.archive_document(db, principal, doc_id))


@router.delete("/{doc_id}", status_code=204)
def delete(doc_id: uuid.UUID, principal: Staff, db: DB) -> None:
    svc.delete_document(db, principal, doc_id)


@router.post("/{doc_id}/download-url", response_model=DownloadUrlResponse)
def download_url(
    doc_id: uuid.UUID, principal: Staff, db: DB, version_id: uuid.UUID | None = None, inline: bool = False
) -> DownloadUrlResponse:
    url, exp, name = svc.create_download_url(db, principal, doc_id, version_id=version_id, inline=inline)
    return DownloadUrlResponse(url=url, expires_at=exp, file_name=name)


@files_router.get("/files/{token}", include_in_schema=False)
def serve_file(token: str, db: DB) -> StreamingResponse:
    """Serves local-storage files for a valid, unexpired signed token only."""
    claims = decode_signed_download_token(token)
    try:
        vid = uuid.UUID(claims["sub"])
        oid = uuid.UUID(claims["org"])
    except (KeyError, ValueError):
        raise NotFound("File not found") from None
    v = db.get(DocumentVersion, vid)
    if v is None or v.organization_id != oid or v.storage_deleted_at is not None:
        raise NotFound("File not found")
    doc = db.get(Document, v.document_id)
    if doc is None or doc.deleted_at is not None:
        raise NotFound("File not found")
    disp = "inline" if claims.get("disp") == "inline" and v.mime_type in svc.INLINE_PREVIEWABLE else "attachment"
    headers = {
        "Content-Disposition": f'{disp}; filename="{svc.safe_filename(v.file_name)}"',
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
        "Content-Security-Policy": "default-src 'none'; sandbox",
    }
    return StreamingResponse(get_storage().stream(v.storage_key), media_type=v.mime_type, headers=headers)
