"""Document vault: validated uploads, versioning, review/approval, authorisation, signed URLs.

Download authorisation always checks, in order:
  authenticated principal → same organization → client visibility/ownership →
  permission → document & version status.
"""

from __future__ import annotations

import hashlib
import io
import re
import uuid
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import Principal
from app.core.errors import Forbidden, NotFound, ValidationFailed
from app.core.permissions import Perm
from app.core.rate_limit import hit
from app.core.security import create_signed_download_token, now_utc
from app.integrations.storage import get_storage, new_storage_key
from app.models import AuditLog, Document, DocumentDelivery, DocumentVersion, Organization, Task
from app.models.enums import DocumentSource, DocumentStatus, DocumentType, VersionStatus
from app.repositories.base import paginate
from app.services import audit
from app.services.audit import AuditAction
from app.services.scope import get_visible_client, scope_by_client
from app.workers.dispatch import enqueue_on_commit

PDF, PNG, JPEG = "application/pdf", "image/png", "image/jpeg"
DOC, XLS = "application/msword", "application/vnd.ms-excel"
DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
ALLOWED_EXT: dict[str, str] = {
    ".pdf": PDF,
    ".png": PNG,
    ".jpg": JPEG,
    ".jpeg": JPEG,
    ".doc": DOC,
    ".xls": XLS,
    ".docx": DOCX,
    ".xlsx": XLSX,
}
INLINE_PREVIEWABLE = {PDF, PNG, JPEG}
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._\- ()&]+")


def safe_filename(name: str) -> str:
    base = name.replace("\\", "/").split("/")[-1].strip()
    base = _SAFE_NAME_RE.sub("_", base).strip("._ ") or "document"
    if len(base) > 150:
        stem, dot, ext = base.rpartition(".")
        base = (stem[:140] + dot + ext) if dot else base[:150]
    return base


def sniff_mime(content: bytes) -> str | None:
    head = content[:8]
    if head.startswith(b"%PDF-"):
        return PDF
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if head.startswith(b"\xff\xd8\xff"):
        return JPEG
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        return "application/x-ole-storage"
    if head.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as z:
                names = set(z.namelist())
        except zipfile.BadZipFile:
            return None
        if any(n.lower().endswith("vbaproject.bin") for n in names):
            return "application/x-macro-enabled"  # rejected: macro-enabled Office files
        if "word/document.xml" in names:
            return DOCX
        if "xl/workbook.xml" in names:
            return XLSX
    return None


@dataclass
class ValidatedFile:
    file_name: str
    mime_type: str
    size: int
    sha256: str


def validate_upload(file_name: str, content: bytes) -> ValidatedFile:
    if not content:
        raise ValidationFailed("File is empty")
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    if len(content) > max_bytes:
        raise ValidationFailed(f"File exceeds {settings.MAX_UPLOAD_MB} MB limit", code="FILE_TOO_LARGE")
    name = safe_filename(file_name or "document")
    ext = ("." + name.rsplit(".", 1)[-1].lower()) if "." in name else ""
    expected = ALLOWED_EXT.get(ext)
    if expected is None:
        raise ValidationFailed("Unsupported file type. Allowed: PDF, JPG, PNG, DOC/DOCX, XLS/XLSX", code="UNSUPPORTED_FILE")
    sniffed = sniff_mime(content)
    ok = sniffed == expected or (sniffed == "application/x-ole-storage" and expected in (DOC, XLS))
    if not ok:
        raise ValidationFailed("File content does not match its extension", code="FILE_TYPE_MISMATCH")
    return ValidatedFile(file_name=name, mime_type=expected, size=len(content), sha256=hashlib.sha256(content).hexdigest())


def _store(org_id: uuid.UUID, content: bytes, vf: ValidatedFile) -> str:
    key = new_storage_key(org_id)
    get_storage().put(key, content, vf.mime_type)
    return key


def _get_doc(db: Session, principal: Principal, doc_id: uuid.UUID | str, *, for_update: bool = False) -> Document:
    try:
        did = doc_id if isinstance(doc_id, uuid.UUID) else uuid.UUID(str(doc_id))
    except ValueError:
        raise NotFound("Document not found") from None
    stmt = scope_by_client(select(Document), Document, principal).where(Document.id == did, Document.deleted_at.is_(None))
    if for_update:
        stmt = stmt.with_for_update(of=Document)
    doc = db.execute(stmt).unique().scalar_one_or_none()
    if doc is None:
        raise NotFound("Document not found")
    return doc


def get_document(db: Session, principal: Principal, doc_id: uuid.UUID) -> Document:
    principal.require(Perm.DOCUMENT_VIEW) if principal.is_staff else None
    return _get_doc(db, principal, doc_id)


def list_documents(
    db: Session,
    principal: Principal,
    *,
    q: str | None = None,
    client_id: uuid.UUID | None = None,
    document_type: str | None = None,
    financial_year: str | None = None,
    status: str | None = None,
    source: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Document], int]:
    if principal.is_staff:
        principal.require(Perm.DOCUMENT_VIEW)
    stmt: Select[Any] = scope_by_client(select(Document), Document, principal).where(Document.deleted_at.is_(None))
    if principal.is_client:
        stmt = stmt.where(
            or_(Document.approved_version_id.is_not(None), Document.source != DocumentSource.STAFF),
            Document.status != DocumentStatus.ARCHIVED,
        )
    if q:
        term = f"%{q.strip()[:100]}%"
        stmt = stmt.where(or_(Document.file_name.ilike(term), Document.description.ilike(term)))
    if client_id:
        stmt = stmt.where(Document.client_id == client_id)
    if document_type:
        stmt = stmt.where(Document.document_type == document_type)
    if financial_year:
        stmt = stmt.where(Document.financial_year == financial_year)
    if status:
        stmt = stmt.where(Document.status == status)
    elif principal.is_staff:
        stmt = stmt.where(Document.status != DocumentStatus.ARCHIVED)
    if source:
        stmt = stmt.where(Document.source == source)
    col = {
        "created_at": Document.created_at,
        "file_name": Document.file_name,
        "financial_year": Document.financial_year,
        "updated_at": Document.updated_at,
    }.get(sort, Document.created_at)
    stmt = stmt.order_by(col.desc() if order == "desc" else col.asc(), Document.id)
    rows, total = paginate(db, stmt, page, page_size)
    return list(rows), total


def upload_document(
    db: Session,
    principal: Principal,
    *,
    client_id: uuid.UUID,
    file_name: str,
    content: bytes,
    document_type: str = DocumentType.OTHER,
    financial_year: str | None = None,
    assessment_year: str | None = None,
    description: str | None = None,
    task_id: uuid.UUID | None = None,
    source: DocumentSource = DocumentSource.STAFF,
    commit: bool = True,
) -> Document:
    if principal.is_staff:
        principal.require(Perm.DOCUMENT_UPLOAD)
        source = DocumentSource.STAFF
    client = get_visible_client(db, principal, client_id)
    if document_type not in DocumentType.__members__:
        raise ValidationFailed("Invalid document type")
    for fy in (financial_year, assessment_year):
        if fy and not re.match(r"^20\d{2}-\d{2}$", fy):
            raise ValidationFailed("Financial/assessment year must look like 2025-26")
    if (
        task_id
        and not db.execute(
            select(Task.id).where(Task.id == task_id, Task.organization_id == principal.org_id, Task.client_id == client.id)
        ).first()
    ):
        raise ValidationFailed("Task not found for this client")
    vf = validate_upload(file_name, content)
    key = _store(principal.org_id, content, vf)
    try:
        doc = Document(
            organization_id=principal.org_id,
            client_id=client.id,
            task_id=task_id,
            uploaded_by=principal.user_id,
            source=source,
            file_name=vf.file_name,
            storage_key=key,
            mime_type=vf.mime_type,
            file_size=vf.size,
            document_type=document_type,
            financial_year=financial_year,
            assessment_year=assessment_year,
            description=description,
            version=1,
            status=DocumentStatus.UPLOADED,
            extracted_metadata={},
        )
        db.add(doc)
        db.flush()
        ver = DocumentVersion(
            organization_id=principal.org_id,
            document_id=doc.id,
            version_number=1,
            storage_key=key,
            file_name=vf.file_name,
            mime_type=vf.mime_type,
            file_size=vf.size,
            checksum_sha256=vf.sha256,
            uploaded_by=principal.user_id,
            status=VersionStatus.UPLOADED,
        )
        db.add(ver)
        db.flush()
        doc.current_version_id = ver.id
        audit.record(
            db,
            principal,
            AuditAction.DOCUMENT_UPLOADED,
            resource="document",
            resource_id=doc.id,
            client_id=client.id,
            metadata={"file_name": vf.file_name, "size": vf.size, "type": document_type, "source": str(source)},
        )
        enqueue_on_commit(db, "documents.process", version_id=str(ver.id))
        if commit:
            db.commit()
            db.refresh(doc)
    except Exception:
        db.rollback()
        get_storage().delete(key)
        raise
    return doc


def upload_new_version(db: Session, principal: Principal, doc_id: uuid.UUID, *, file_name: str, content: bytes) -> Document:
    principal.require(Perm.DOCUMENT_UPLOAD)
    doc = _get_doc(db, principal, doc_id, for_update=True)
    if doc.status == DocumentStatus.ARCHIVED:
        raise ValidationFailed("Archived documents cannot be replaced")
    vf = validate_upload(file_name, content)
    key = _store(principal.org_id, content, vf)
    try:
        for v in doc.versions:
            if v.status in (VersionStatus.UPLOADED, VersionStatus.APPROVED):
                v.status = VersionStatus.SUPERSEDED
        n = max(v.version_number for v in doc.versions) + 1
        ver = DocumentVersion(
            organization_id=doc.organization_id,
            document_id=doc.id,
            version_number=n,
            storage_key=key,
            file_name=vf.file_name,
            mime_type=vf.mime_type,
            file_size=vf.size,
            checksum_sha256=vf.sha256,
            uploaded_by=principal.user_id,
            status=VersionStatus.UPLOADED,
        )
        db.add(ver)
        db.flush()
        doc.version = n
        doc.current_version_id = ver.id
        doc.approved_version_id = None  # stale approvals are never auto-delivered
        doc.status = DocumentStatus.UPLOADED
        doc.file_name, doc.storage_key, doc.mime_type, doc.file_size = vf.file_name, key, vf.mime_type, vf.size
        audit.record(
            db,
            principal,
            AuditAction.DOCUMENT_VERSION_UPLOADED,
            resource="document",
            resource_id=doc.id,
            client_id=doc.client_id,
            metadata={"version": n, "file_name": vf.file_name},
        )
        enqueue_on_commit(db, "documents.process", version_id=str(ver.id))
        db.commit()
    except Exception:
        db.rollback()
        get_storage().delete(key)
        raise
    db.refresh(doc)
    return doc


def update_metadata(db: Session, principal: Principal, doc_id: uuid.UUID, data: dict[str, Any]) -> Document:
    principal.require(Perm.DOCUMENT_UPLOAD)
    doc = _get_doc(db, principal, doc_id)
    if "document_type" in data and data["document_type"] and data["document_type"] not in DocumentType.__members__:
        raise ValidationFailed("Invalid document type")
    for k, v in data.items():
        setattr(doc, k, v)
    audit.record(
        db,
        principal,
        AuditAction.CLIENT_UPDATED,
        resource="document",
        resource_id=doc.id,
        client_id=doc.client_id,
        metadata={"fields": sorted(data)},
    )
    db.commit()
    db.refresh(doc)
    return doc


def submit_for_review(db: Session, principal: Principal, doc_id: uuid.UUID) -> Document:
    principal.require(Perm.DOCUMENT_UPLOAD)
    doc = _get_doc(db, principal, doc_id)
    if doc.status != DocumentStatus.UPLOADED:
        raise ValidationFailed(f"Cannot submit a document in status {doc.status}")
    doc.status = DocumentStatus.UNDER_REVIEW
    audit.record(db, principal, AuditAction.DOCUMENT_SUBMITTED, resource="document", resource_id=doc.id, client_id=doc.client_id)
    db.commit()
    return doc


def _current_version(doc: Document) -> DocumentVersion:
    v = next((v for v in doc.versions if v.id == doc.current_version_id), None)
    if v is None:
        raise NotFound("Document version not found")
    return v


def approve_document(
    db: Session, principal: Principal, doc_id: uuid.UUID, *, note: str | None = None, deliver: bool | None = None
) -> Document:
    principal.require(Perm.DOCUMENT_APPROVE)
    doc = _get_doc(db, principal, doc_id, for_update=True)
    if doc.status not in (DocumentStatus.UPLOADED, DocumentStatus.UNDER_REVIEW):
        raise ValidationFailed(f"Cannot approve a document in status {doc.status}")
    ver = _current_version(doc)
    ver.status = VersionStatus.APPROVED
    ver.reviewed_by, ver.reviewed_at, ver.review_note = principal.user_id, now_utc(), note
    doc.status = DocumentStatus.APPROVED
    doc.approved_version_id = ver.id
    audit.record(
        db,
        principal,
        AuditAction.DOCUMENT_APPROVED,
        resource="document",
        resource_id=doc.id,
        client_id=doc.client_id,
        metadata={"version": ver.version_number},
    )
    org = db.get(Organization, principal.org_id)
    auto = bool(org.get_setting("notifications", "auto_deliver_on_approval")) if org else True
    should_deliver = auto if deliver is None else deliver
    if should_deliver and doc.source == DocumentSource.STAFF:
        enqueue_on_commit(db, "documents.deliver", document_id=str(doc.id), initiated_by=str(principal.user_id))
    db.commit()
    db.refresh(doc)
    return doc


def reject_document(db: Session, principal: Principal, doc_id: uuid.UUID, *, reason: str) -> Document:
    principal.require(Perm.DOCUMENT_APPROVE)
    doc = _get_doc(db, principal, doc_id, for_update=True)
    if doc.status not in (DocumentStatus.UPLOADED, DocumentStatus.UNDER_REVIEW):
        raise ValidationFailed(f"Cannot reject a document in status {doc.status}")
    ver = _current_version(doc)
    ver.status = VersionStatus.REJECTED
    ver.reviewed_by, ver.reviewed_at, ver.review_note = principal.user_id, now_utc(), reason
    doc.status = DocumentStatus.REJECTED
    audit.record(
        db,
        principal,
        AuditAction.DOCUMENT_REJECTED,
        resource="document",
        resource_id=doc.id,
        client_id=doc.client_id,
        metadata={"reason": reason[:200]},
    )
    db.commit()
    return doc


def archive_document(db: Session, principal: Principal, doc_id: uuid.UUID) -> Document:
    principal.require(Perm.DOCUMENT_UPLOAD)
    doc = _get_doc(db, principal, doc_id)
    doc.status = DocumentStatus.ARCHIVED
    doc.archived_at = now_utc()
    audit.record(db, principal, AuditAction.DOCUMENT_ARCHIVED, resource="document", resource_id=doc.id, client_id=doc.client_id)
    db.commit()
    return doc


def delete_document(db: Session, principal: Principal, doc_id: uuid.UUID) -> None:
    """Soft-delete immediately (inaccessible), then securely delete stored objects in a worker."""
    principal.require(Perm.DOCUMENT_DELETE)
    doc = _get_doc(db, principal, doc_id)
    doc.deleted_at = now_utc()
    doc.status = DocumentStatus.ARCHIVED
    audit.record(
        db,
        principal,
        AuditAction.DOCUMENT_DELETED,
        resource="document",
        resource_id=doc.id,
        client_id=doc.client_id,
        metadata={"file_name": doc.file_name, "versions": len(doc.versions)},
    )
    enqueue_on_commit(db, "documents.purge_storage", document_id=str(doc.id))
    db.commit()


# --- authorisation & signed URLs ----------------------------------------------------


def authorize_download(principal: Principal, doc: Document, version: DocumentVersion, *, inline: bool) -> None:
    if version.document_id != doc.id or version.organization_id != principal.org_id or doc.organization_id != principal.org_id:
        raise NotFound("Document not found")
    if doc.deleted_at is not None or version.storage_deleted_at is not None:
        raise NotFound("Document not found")
    if principal.is_staff or principal.kind == "system":
        principal.require(Perm.DOCUMENT_VIEW if inline else Perm.DOCUMENT_DOWNLOAD)
        return
    if principal.is_client:
        if doc.client_id != principal.client_id:
            raise NotFound("Document not found")
        own_upload = doc.source != DocumentSource.STAFF
        if own_upload:
            return
        if doc.status not in (DocumentStatus.APPROVED, DocumentStatus.DELIVERED):
            raise Forbidden("This document is not available yet")
        if version.status != VersionStatus.APPROVED or doc.approved_version_id != version.id:
            raise Forbidden("This version is not available")
        return
    raise Forbidden("Not allowed")


def signed_url_for_version(version: DocumentVersion, *, inline: bool, ttl: int | None = None) -> tuple[str, datetime]:
    ttl = ttl or settings.SIGNED_URL_TTL_SECONDS
    expires = now_utc() + timedelta(seconds=ttl)
    native = get_storage().signed_url(
        version.storage_key, file_name=version.file_name, content_type=version.mime_type, ttl_seconds=ttl, inline=inline
    )
    if native:
        return native, expires
    token = create_signed_download_token(
        version_id=str(version.id), org_id=str(version.organization_id), disposition="inline" if inline else "attachment", ttl_seconds=ttl
    )
    return f"{settings.PUBLIC_API_URL}/api/v1/files/{token}", expires


def create_download_url(
    db: Session, principal: Principal, doc_id: uuid.UUID, *, version_id: uuid.UUID | None = None, inline: bool = False
) -> tuple[str, datetime, str]:
    hit(f"download:{principal.user_id or principal.client_id}", 60, 60)
    doc = _get_doc(db, principal, doc_id)
    if version_id is None:
        if principal.is_client and doc.source == DocumentSource.STAFF:
            version_id = doc.approved_version_id
        else:
            version_id = doc.current_version_id
    version = next((v for v in doc.versions if v.id == version_id), None)
    if version is None:
        raise NotFound("Document version not found")
    if inline and version.mime_type not in INLINE_PREVIEWABLE:
        raise ValidationFailed("Preview is only available for PDF and images")
    authorize_download(principal, doc, version, inline=inline)
    url, exp = signed_url_for_version(version, inline=inline)
    audit.record(
        db,
        principal,
        AuditAction.DOCUMENT_VIEWED if inline else AuditAction.DOCUMENT_DOWNLOADED,
        resource="document",
        resource_id=doc.id,
        client_id=doc.client_id,
        metadata={"version": version.version_number, "via": "portal" if principal.is_client else "dashboard"},
    )
    db.commit()
    return url, exp, version.file_name


def document_detail_extras(db: Session, principal: Principal, doc: Document) -> dict[str, Any]:
    deliveries = (
        db.execute(
            select(DocumentDelivery)
            .where(DocumentDelivery.organization_id == principal.org_id, DocumentDelivery.document_id == doc.id)
            .order_by(DocumentDelivery.created_at.desc())
        )
        .scalars()
        .all()
    )
    logs = (
        db.execute(
            select(AuditLog)
            .where(AuditLog.organization_id == principal.org_id, AuditLog.resource == "document", AuditLog.resource_id == str(doc.id))
            .order_by(AuditLog.timestamp.desc())
            .limit(100)
        )
        .scalars()
        .all()
    )
    return {
        "deliveries": deliveries,
        "access_history": [
            {
                "action": a.action,
                "actor_type": a.actor_type,
                "user_id": a.user_id,
                "client_id": a.client_id,
                "timestamp": a.timestamp,
                "ip": a.ip,
                "metadata": a.metadata_,
            }
            for a in logs
        ],
    }
