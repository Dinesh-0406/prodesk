"""Compliance calendar, support requests, global search, notifications inbox, audit viewer,
privacy (export / erasure / retention) and document intelligence."""

from __future__ import annotations

import io
import uuid
from datetime import date, timedelta
from typing import Any

from sqlalchemy import false as sa_false
from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.core.context import Principal, system_principal
from app.core.errors import NotFound, ValidationFailed
from app.core.logging import get_logger
from app.core.permissions import Perm
from app.core.security import now_utc
from app.integrations.ai import get_ai_provider
from app.integrations.storage import get_storage
from app.models import (
    AuditLog,
    Client,
    ComplianceEvent,
    ConsentRecord,
    Conversation,
    Document,
    DocumentVersion,
    Invoice,
    Message,
    Notification,
    Organization,
    Payment,
    SupportRequest,
    Task,
    WhatsAppContact,
)
from app.models.enums import ClientStatus, ComplianceSource, NotificationStatus
from app.repositories.base import paginate
from app.schemas.work import ComplianceEventIn, SupportRequestUpdate
from app.services import audit
from app.services.audit import AuditAction
from app.services.scope import get_visible_client, scope_by_client, visible_client_ids_subquery

log = get_logger(__name__)


# --- Compliance calendar ------------------------------------------------------------


def list_compliance(
    db: Session, principal: Principal, *, start: date | None = None, end: date | None = None, category: str | None = None
) -> list[ComplianceEvent]:
    principal.require(Perm.TASK_VIEW)
    start = start or date.today() - timedelta(days=7)
    end = end or start + timedelta(days=120)
    stmt = select(ComplianceEvent).where(
        ComplianceEvent.organization_id == principal.org_id, ComplianceEvent.due_date >= start, ComplianceEvent.due_date <= end
    )
    if category:
        stmt = stmt.where(ComplianceEvent.category == category)
    return list(db.execute(stmt.order_by(ComplianceEvent.due_date)).scalars())


def create_compliance(db: Session, principal: Principal, data: ComplianceEventIn) -> ComplianceEvent:
    """ProDesk never invents deadlines: events are admin-configured or carry a verified source."""
    principal.require(Perm.COMPLIANCE_MANAGE)
    if data.source in (ComplianceSource.VERIFIED_SOURCE, ComplianceSource.OFFICIAL_INTEGRATION) and not data.source_reference:
        raise ValidationFailed("A source reference (e.g. official notification/circular URL) is required for verified dates")
    if data.client_id:
        get_visible_client(db, principal, data.client_id)
    ev = ComplianceEvent(
        organization_id=principal.org_id,
        category=data.category,
        title=data.title,
        description=data.description,
        due_date=data.due_date,
        period=data.period,
        source=data.source,
        source_reference=data.source_reference,
        verified_by=principal.user_id if data.source != ComplianceSource.ADMIN_CONFIGURED else None,
        applies_to_client_types=data.applies_to_client_types,
        client_id=data.client_id,
        created_by=principal.user_id,
        reminder_days_before=data.reminder_days_before,
    )
    db.add(ev)
    db.flush()
    audit.record(
        db,
        principal,
        AuditAction.COMPLIANCE_EVENT_CREATED,
        resource="compliance_event",
        resource_id=ev.id,
        metadata={"category": data.category, "source": data.source},
    )
    db.commit()
    return ev


def delete_compliance(db: Session, principal: Principal, event_id: uuid.UUID) -> None:
    principal.require(Perm.COMPLIANCE_MANAGE)
    ev = db.execute(
        select(ComplianceEvent).where(ComplianceEvent.id == event_id, ComplianceEvent.organization_id == principal.org_id)
    ).scalar_one_or_none()
    if ev is None:
        raise NotFound("Event not found")
    db.delete(ev)
    db.commit()


# --- Support requests ----------------------------------------------------------------


def list_support(
    db: Session, principal: Principal, *, status: str | None = None, page: int = 1, page_size: int = 25
) -> tuple[list[SupportRequest], int]:
    if principal.is_staff:
        principal.require(Perm.CLIENT_VIEW)
    stmt = scope_by_client(select(SupportRequest), SupportRequest, principal)
    if status:
        stmt = stmt.where(SupportRequest.status == status)
    rows, total = paginate(db, stmt.order_by(SupportRequest.created_at.desc()), page, page_size)
    return list(rows), total


def create_support_from_portal(db: Session, principal: Principal, request_type: str, message: str) -> SupportRequest:
    sr = SupportRequest(organization_id=principal.org_id, client_id=principal.client_id, request_type=request_type, message=message)
    db.add(sr)
    client = db.get(Client, principal.client_id)
    from app.services import notifications

    notifications.notify_client_owner(
        db,
        principal.org_id,
        client.assigned_employee_id if client else None,
        fallback_perm=Perm.CLIENT_VIEW_ALL,
        type_="SUPPORT_REQUEST",
        title=f"New {request_type.lower()} request from {client.name if client else 'client'}",
        body=message[:200],
        link="/support",
    )
    db.commit()
    return sr


def update_support(db: Session, principal: Principal, sr_id: uuid.UUID, data: SupportRequestUpdate) -> SupportRequest:
    principal.require(Perm.CLIENT_UPDATE)
    sr = (
        db.execute(scope_by_client(select(SupportRequest), SupportRequest, principal).where(SupportRequest.id == sr_id))
        .unique()
        .scalar_one_or_none()
    )
    if sr is None:
        raise NotFound("Request not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(sr, k, v)
    if data.status == "RESOLVED":
        sr.resolved_at = now_utc()
    db.commit()
    return sr


# --- Global search -------------------------------------------------------------------


def global_search(db: Session, principal: Principal, q: str, limit: int = 5) -> dict[str, list[dict[str, Any]]]:
    principal.require(Perm.CLIENT_VIEW)
    q = q.strip()[:100]
    if len(q) < 2:
        return {"clients": [], "documents": [], "tasks": [], "invoices": [], "conversations": []}
    term = f"%{q}%"
    digits = "".join(c for c in q if c.isdigit())
    vis = visible_client_ids_subquery(principal)
    cconds = [Client.name.ilike(term), Client.pan.ilike(term), Client.gstin.ilike(term), Client.email.ilike(term)]
    if len(digits) >= 4:
        cconds.append(Client.phone.ilike(f"%{digits}%"))
    clients = (
        db.execute(select(Client).where(Client.id.in_(vis), Client.status != ClientStatus.ARCHIVED, or_(*cconds)).limit(limit))
        .unique()
        .scalars()
    )
    out: dict[str, list[dict[str, Any]]] = {
        "clients": [{"id": str(c.id), "title": c.name, "subtitle": c.phone} for c in clients],
        "documents": [],
        "tasks": [],
        "invoices": [],
        "conversations": [],
    }
    if principal.has(Perm.DOCUMENT_VIEW):
        docs = (
            db.execute(
                scope_by_client(select(Document), Document, principal)
                .where(Document.deleted_at.is_(None), or_(Document.file_name.ilike(term), Document.description.ilike(term)))
                .limit(limit)
            )
            .unique()
            .scalars()
        )
        out["documents"] = [{"id": str(d.id), "title": d.file_name, "subtitle": d.client.name} for d in docs]
    if principal.has(Perm.TASK_VIEW):
        tasks = db.execute(scope_by_client(select(Task), Task, principal).where(Task.title.ilike(term)).limit(limit)).unique().scalars()
        out["tasks"] = [{"id": str(t.id), "title": t.title, "subtitle": t.client.name} for t in tasks]
    if principal.has(Perm.INVOICE_VIEW):
        invs = (
            db.execute(scope_by_client(select(Invoice), Invoice, principal).where(Invoice.invoice_number.ilike(term)).limit(limit))
            .unique()
            .scalars()
        )
        out["invoices"] = [{"id": str(i.id), "title": i.invoice_number, "subtitle": i.client.name} for i in invs]
    if principal.has(Perm.WHATSAPP_VIEW):
        convs = (
            db.execute(
                select(Conversation)
                .join(WhatsAppContact, WhatsAppContact.id == Conversation.contact_id)
                .where(
                    Conversation.organization_id == principal.org_id,
                    or_(
                        Conversation.client_id.in_(vis),
                        Conversation.client_id.is_(None) if principal.sees_all_clients else sa_false(),
                    ),
                    or_(
                        WhatsAppContact.profile_name.ilike(term),
                        WhatsAppContact.wa_id.ilike(term),
                        Conversation.last_message_preview.ilike(term),
                    ),
                )
                .limit(limit)
            )
            .unique()
            .scalars()
        )
        out["conversations"] = [
            {
                "id": str(c.id),
                "title": c.client.name if c.client else (c.contact.profile_name or c.contact.wa_id),
                "subtitle": c.last_message_preview or "",
            }
            for c in convs
        ]
    return out


# --- Notifications inbox -------------------------------------------------------------


def list_notifications(db: Session, principal: Principal, unread_only: bool = False, limit: int = 50) -> list[Notification]:
    stmt = select(Notification).where(
        Notification.organization_id == principal.org_id, Notification.user_id == principal.user_id, Notification.channel == "IN_APP"
    )
    if unread_only:
        stmt = stmt.where(Notification.read_at.is_(None))
    return list(db.execute(stmt.order_by(Notification.created_at.desc()).limit(limit)).scalars())


def mark_notifications_read(db: Session, principal: Principal, ids: list[uuid.UUID] | None) -> None:
    stmt = update(Notification).where(
        Notification.organization_id == principal.org_id, Notification.user_id == principal.user_id, Notification.read_at.is_(None)
    )
    if ids:
        stmt = stmt.where(Notification.id.in_(ids))
    db.execute(stmt.values(read_at=now_utc(), status=NotificationStatus.READ))
    db.commit()


# --- Audit viewer --------------------------------------------------------------------


def list_audit(
    db: Session,
    principal: Principal,
    *,
    action: str | None = None,
    resource: str | None = None,
    resource_id: str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[AuditLog], int]:
    principal.require(Perm.AUDIT_VIEW)
    stmt = select(AuditLog).where(AuditLog.organization_id == principal.org_id)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource:
        stmt = stmt.where(AuditLog.resource == resource)
    if resource_id:
        stmt = stmt.where(AuditLog.resource_id == resource_id)
    rows, total = paginate(db, stmt.order_by(AuditLog.timestamp.desc()), page, page_size)
    return list(rows), total


# --- Privacy: export, erasure, retention ---------------------------------------------


def export_client_data(db: Session, principal: Principal, client_id: uuid.UUID) -> dict[str, Any]:
    """Machine-readable export of a client's personal data held by the firm (access/portability)."""
    principal.require(Perm.CLIENT_VIEW, Perm.DOCUMENT_VIEW)
    c = get_visible_client(db, principal, client_id)

    def rows(model: Any, *cols: str) -> list[dict[str, Any]]:
        objs = db.execute(select(model).where(model.organization_id == principal.org_id, model.client_id == c.id)).unique().scalars()
        return [{k: (str(getattr(o, k)) if getattr(o, k) is not None else None) for k in cols} for o in objs]

    data = {
        "generated_at": now_utc().isoformat(),
        "organization_id": str(principal.org_id),
        "client": {
            k: (str(getattr(c, k)) if getattr(c, k) is not None else None)
            for k in (
                "id",
                "name",
                "phone",
                "email",
                "address",
                "client_type",
                "pan",
                "gstin",
                "status",
                "whatsapp_opt_in",
                "whatsapp_opt_in_at",
                "whatsapp_opt_out_at",
                "created_at",
            )
        },
        "consents": rows(ConsentRecord, "purpose", "granted", "channel", "notice_version", "created_at"),
        "documents": rows(Document, "id", "file_name", "document_type", "financial_year", "status", "created_at"),
        "tasks": rows(Task, "id", "title", "service_type", "status", "due_date", "created_at"),
        "invoices": rows(Invoice, "id", "invoice_number", "total", "amount_paid", "status", "issue_date"),
        "payments": rows(Payment, "id", "amount", "method", "paid_at"),
        "messages": [
            {"direction": m.direction, "type": m.message_type, "body": m.body, "timestamp": m.timestamp.isoformat()}
            for m in db.execute(
                select(Message)
                .join(Conversation, Conversation.id == Message.conversation_id)
                .where(Conversation.organization_id == principal.org_id, Conversation.client_id == c.id)
                .order_by(Message.timestamp)
            ).scalars()
        ],
    }
    audit.record(db, principal, AuditAction.CLIENT_DATA_EXPORTED, resource="client", resource_id=c.id)
    db.commit()
    return data


def erase_client(db: Session, principal: Principal, client_id: uuid.UUID) -> None:
    """Secure deletion: removes stored files and anonymises personal fields. Financial records
    (invoices/payments) are kept but de-linked from personal identifiers where possible —
    firms must check their own statutory record-keeping obligations before erasing."""
    principal.require(Perm.CLIENT_DELETE, Perm.DOCUMENT_DELETE)
    c = get_visible_client(db, principal, client_id)
    for d in (
        db.execute(select(Document).where(Document.organization_id == principal.org_id, Document.client_id == c.id)).unique().scalars()
    ):
        d.deleted_at = d.deleted_at or now_utc()
        from app.workers.dispatch import enqueue_on_commit

        enqueue_on_commit(db, "documents.purge_storage", document_id=str(d.id))
    db.execute(
        update(Message)
        .where(
            Message.organization_id == principal.org_id,
            Message.conversation_id.in_(select(Conversation.id).where(Conversation.client_id == c.id)),
        )
        .values(body="[erased]", payload={})
    )
    c.name = "Erased client"
    c.email = c.address = c.pan = c.gstin = c.notes = None
    c.phone = f"+erased{uuid.uuid4().hex[:8]}"
    c.status = ClientStatus.ARCHIVED
    c.whatsapp_opt_in = False
    audit.record(db, principal, AuditAction.CLIENT_ERASED, resource="client", resource_id=c.id)
    db.commit()


def purge_document_storage(db: Session, document_id: uuid.UUID) -> int:
    doc = db.get(Document, document_id)
    if doc is None or doc.deleted_at is None:
        return 0
    n = 0
    for v in db.execute(
        select(DocumentVersion).where(DocumentVersion.document_id == doc.id, DocumentVersion.storage_deleted_at.is_(None))
    ).scalars():
        get_storage().delete(v.storage_key)
        v.storage_deleted_at = now_utc()
        n += 1
    db.commit()
    return n


def retention_purge(db: Session) -> int:
    """Delete stored files of documents archived longer than the org's retention period."""
    total = 0
    for org in db.execute(select(Organization)).scalars().all():
        days = int(org.get_setting("privacy", "document_retention_days") or 0)
        if days <= 0:
            continue
        cutoff = now_utc() - timedelta(days=days)
        docs = (
            db.execute(
                select(Document).where(
                    Document.organization_id == org.id,
                    Document.archived_at.is_not(None),
                    Document.archived_at < cutoff,
                    Document.deleted_at.is_(None),
                )
            )
            .unique()
            .scalars()
            .all()
        )
        for d in docs:
            d.deleted_at = now_utc()
            audit.record(
                db,
                system_principal(org.id),
                AuditAction.DOCUMENT_DELETED,
                resource="document",
                resource_id=d.id,
                client_id=d.client_id,
                metadata={"reason": "retention_policy"},
            )
            db.commit()
            total += purge_document_storage(db, d.id)
    return total


# --- Document intelligence -----------------------------------------------------------


def process_document_version(db: Session, version_id: uuid.UUID) -> dict[str, Any]:
    """Verify checksum, extract text from PDFs, and ask the AI provider for a suggested
    type/financial year. Suggestions are stored as metadata only — never auto-applied."""
    import hashlib

    v = db.get(DocumentVersion, version_id)
    if v is None:
        return {}
    content = get_storage().get(v.storage_key)
    result: dict[str, Any] = {
        "checksum_ok": hashlib.sha256(content).hexdigest() == v.checksum_sha256,
        "processed_at": now_utc().isoformat(),
    }
    text = ""
    if v.mime_type == "application/pdf":
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            result["pages"] = len(reader.pages)
            text = "\n".join((p.extract_text() or "") for p in reader.pages[:5])[:5000]
        except Exception as e:
            result["extract_error"] = type(e).__name__
    elif v.mime_type.startswith("image/"):
        result["ocr"] = "not_configured"  # plug an OCR provider (e.g. AWS Textract) here
    s = get_ai_provider().suggest_document_metadata(v.file_name, text)
    result["suggestion"] = s.model_dump(mode="json")
    result["text_chars"] = len(text)
    doc = db.get(Document, v.document_id)
    if doc is not None:
        doc.extracted_metadata = {**(doc.extracted_metadata or {}), f"v{v.version_number}": result}
    db.commit()
    return result
