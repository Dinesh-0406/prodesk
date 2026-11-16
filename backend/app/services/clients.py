"""Client CRM: CRUD, search, assignment, CSV import, consent, WhatsApp enablement, privacy export."""

from __future__ import annotations

import csv
import io
import uuid
from decimal import Decimal
from typing import Any

from pydantic import ValidationError
from sqlalchemy import Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.permissions import Perm
from app.core.phone import normalize_indian_phone
from app.core.security import now_utc
from app.models import (
    AuditLog,
    Client,
    ConsentRecord,
    Conversation,
    Document,
    DocumentRequest,
    Invoice,
    Message,
    Organization,
    Task,
    User,
)
from app.models.enums import (
    TASK_DONE_STATUSES,
    ClientStatus,
    DocumentRequestStatus,
    InvoiceStatus,
    TemplateKey,
)
from app.repositories.base import paginate
from app.schemas.client import ClientCreate, ClientOut, ClientSummary, ClientUpdate, ConsentIn, ImportResult
from app.services import audit, messaging
from app.services.audit import AuditAction
from app.services.scope import get_visible_client, visible_client_ids_subquery

SORTABLE = {"name": Client.name, "created_at": Client.created_at, "updated_at": Client.updated_at}


def _validate_assignee(db: Session, principal: Principal, user_id: uuid.UUID | None) -> None:
    if user_id is None:
        return
    u = db.execute(select(User.id).where(User.id == user_id, User.organization_id == principal.org_id, User.is_active.is_(True))).first()
    if u is None:
        raise ValidationFailed("Assigned employee not found in this organization")


def list_clients(
    db: Session,
    principal: Principal,
    *,
    q: str | None = None,
    status: str | None = None,
    client_type: str | None = None,
    assigned_employee_id: uuid.UUID | None = None,
    sort: str = "name",
    order: str = "asc",
    page: int = 1,
    page_size: int = 25,
) -> tuple[list[Client], int]:
    principal.require(Perm.CLIENT_VIEW)
    stmt: Select[Any] = select(Client).where(Client.id.in_(visible_client_ids_subquery(principal)))
    if q:
        term = f"%{q.strip()[:100]}%"
        digits = "".join(c for c in q if c.isdigit())
        conds = [Client.name.ilike(term), Client.email.ilike(term), Client.pan.ilike(term), Client.gstin.ilike(term)]
        if len(digits) >= 4:
            conds.append(Client.phone.ilike(f"%{digits[-10:]}%"))
        stmt = stmt.where(or_(*conds))
    if status:
        stmt = stmt.where(Client.status == status)
    else:
        stmt = stmt.where(Client.status != ClientStatus.ARCHIVED)
    if client_type:
        stmt = stmt.where(Client.client_type == client_type)
    if assigned_employee_id:
        stmt = stmt.where(Client.assigned_employee_id == assigned_employee_id)
    col = SORTABLE.get(sort, Client.name)
    stmt = stmt.order_by(col.desc() if order == "desc" else col.asc(), Client.id)
    rows, total = paginate(db, stmt, page, page_size)
    return list(rows), total


def get_client(db: Session, principal: Principal, client_id: uuid.UUID) -> Client:
    principal.require(Perm.CLIENT_VIEW)
    return get_visible_client(db, principal, client_id)


def create_client(db: Session, principal: Principal, data: ClientCreate, *, commit: bool = True) -> Client:
    principal.require(Perm.CLIENT_CREATE)
    phone = normalize_indian_phone(data.phone)
    if db.execute(select(Client.id).where(Client.organization_id == principal.org_id, Client.phone == phone)).first():
        raise Conflict("A client with this phone number already exists", code="DUPLICATE_PHONE")
    assignee = data.assigned_employee_id
    if assignee is None and not principal.sees_all_clients:
        assignee = principal.user_id  # employees own the clients they create
    _validate_assignee(db, principal, assignee)
    client = Client(
        organization_id=principal.org_id,
        name=data.name.strip(),
        phone=phone,
        email=data.email,
        address=data.address,
        client_type=data.client_type,
        pan=data.pan,
        gstin=data.gstin,
        assigned_employee_id=assignee,
        notes=data.notes,
        status=ClientStatus.ACTIVE,
    )
    db.add(client)
    db.flush()
    if data.whatsapp_opt_in:
        _set_opt_in(db, principal, client, True, channel="STAFF_RECORDED", evidence="Recorded at client creation")
    audit.record(db, principal, AuditAction.CLIENT_CREATED, resource="client", resource_id=client.id, client_id=None)
    org = db.get(Organization, principal.org_id)
    if org and org.onboarding_step == "ADD_CLIENTS":
        org.onboarding_step = "READY"
    if commit:
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise Conflict("A client with this phone number already exists", code="DUPLICATE_PHONE") from None
        if client.whatsapp_opt_in:
            send_welcome(db, client)
    return client


def update_client(db: Session, principal: Principal, client_id: uuid.UUID, data: ClientUpdate) -> Client:
    principal.require(Perm.CLIENT_UPDATE)
    client = get_visible_client(db, principal, client_id)
    payload = data.model_dump(exclude_unset=True)
    changed: list[str] = []
    if payload.get("phone"):
        phone = normalize_indian_phone(payload["phone"])
        if phone != client.phone:
            if db.execute(
                select(Client.id).where(Client.organization_id == principal.org_id, Client.phone == phone, Client.id != client.id)
            ).first():
                raise Conflict("A client with this phone number already exists", code="DUPLICATE_PHONE")
            client.phone = phone
            changed.append("phone")
        payload.pop("phone")
    if "assigned_employee_id" in payload:
        principal.require(Perm.TASK_ASSIGN)
        _validate_assignee(db, principal, payload["assigned_employee_id"])
    if "whatsapp_opt_in" in payload:
        val = payload.pop("whatsapp_opt_in")
        if val is not None and val != client.whatsapp_opt_in:
            _set_opt_in(db, principal, client, bool(val), channel="STAFF_RECORDED", evidence="Updated by staff")
            changed.append("whatsapp_opt_in")
    if payload.get("status") == ClientStatus.ARCHIVED:
        principal.require(Perm.CLIENT_DELETE)
        client.archived_at = now_utc()
    for k, v in payload.items():
        if getattr(client, k) != v:
            setattr(client, k, v)
            changed.append(k)
    audit.record(db, principal, AuditAction.CLIENT_UPDATED, resource="client", resource_id=client.id, metadata={"fields": changed})
    db.commit()
    db.refresh(client)
    return client


def archive_client(db: Session, principal: Principal, client_id: uuid.UUID) -> Client:
    principal.require(Perm.CLIENT_DELETE)
    client = get_visible_client(db, principal, client_id)
    client.status = ClientStatus.ARCHIVED
    client.archived_at = now_utc()
    audit.record(db, principal, AuditAction.CLIENT_ARCHIVED, resource="client", resource_id=client.id)
    db.commit()
    return client


def _set_opt_in(db: Session, principal: Principal, client: Client, granted: bool, *, channel: str, evidence: str) -> None:
    org = db.get(Organization, principal.org_id)
    notice = org.get_setting("privacy", "notice_version") if org else "unknown"
    client.whatsapp_opt_in = granted
    if granted:
        client.whatsapp_opt_in_at = now_utc()
        client.whatsapp_opt_out_at = None
    else:
        client.whatsapp_opt_out_at = now_utc()
    db.flush()
    db.add(
        ConsentRecord(
            organization_id=principal.org_id,
            client_id=client.id,
            purpose="WHATSAPP_COMMUNICATION",
            granted=granted,
            channel=channel,
            notice_version=str(notice),
            recorded_by=principal.user_id,
            evidence=evidence,
        )
    )
    audit.record(
        db,
        principal,
        AuditAction.WHATSAPP_OPT_IN if granted else AuditAction.WHATSAPP_OPT_OUT,
        resource="client",
        resource_id=client.id,
        metadata={"channel": channel},
    )


def record_consent(db: Session, principal: Principal, client_id: uuid.UUID, data: ConsentIn) -> ConsentRecord:
    principal.require(Perm.CLIENT_UPDATE)
    client = get_visible_client(db, principal, client_id)
    if data.purpose == "WHATSAPP_COMMUNICATION":
        _set_opt_in(db, principal, client, data.granted, channel="STAFF_RECORDED", evidence=data.evidence or "")
        db.commit()
        if data.granted:
            send_welcome(db, client)
        latest = (
            db.execute(select(ConsentRecord).where(ConsentRecord.client_id == client.id).order_by(ConsentRecord.created_at.desc()))
            .scalars()
            .first()
        )
        assert latest is not None
        return latest
    org = db.get(Organization, principal.org_id)
    rec = ConsentRecord(
        organization_id=principal.org_id,
        client_id=client.id,
        purpose=data.purpose,
        granted=data.granted,
        channel="STAFF_RECORDED",
        notice_version=str(org.get_setting("privacy", "notice_version")) if org else "",
        recorded_by=principal.user_id,
        evidence=data.evidence,
    )
    db.add(rec)
    audit.record(
        db,
        principal,
        AuditAction.CONSENT_RECORDED,
        resource="client",
        resource_id=client.id,
        metadata={"purpose": data.purpose, "granted": data.granted},
    )
    db.commit()
    return rec


def send_welcome(db: Session, client: Client) -> None:
    messaging.send_template_to_client(db, client, TemplateKey.WELCOME, [client.name, messaging.firm_name(db, client.organization_id)])
    db.commit()


def client_summary(db: Session, principal: Principal, client_id: uuid.UUID) -> ClientSummary:
    client = get_client(db, principal, client_id)
    cid = client.id

    def count(stmt: Any) -> int:
        return int(db.execute(select(func.count()).select_from(stmt.subquery())).scalar_one())

    open_tasks = (
        db.execute(
            select(Task)
            .where(Task.organization_id == principal.org_id, Task.client_id == cid, Task.status.not_in(list(TASK_DONE_STATUSES)))
            .order_by(Task.due_date.asc().nulls_last())
            .limit(10)
        )
        .unique()
        .scalars()
        .all()
    )
    pending_reqs = (
        db.execute(
            select(DocumentRequest).where(
                DocumentRequest.organization_id == principal.org_id,
                DocumentRequest.client_id == cid,
                DocumentRequest.status.in_([DocumentRequestStatus.PENDING, DocumentRequestStatus.PARTIAL, DocumentRequestStatus.OVERDUE]),
            )
        )
        .unique()
        .scalars()
        .all()
    )
    outstanding = db.execute(
        select(func.coalesce(func.sum(Invoice.total - Invoice.amount_paid), 0)).where(
            Invoice.organization_id == principal.org_id,
            Invoice.client_id == cid,
            Invoice.status.in_([InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE]),
        )
    ).scalar_one()
    conv = (
        db.execute(select(Conversation).where(Conversation.organization_id == principal.org_id, Conversation.client_id == cid))
        .unique()
        .scalars()
        .first()
    )
    if client.whatsapp_opt_out_at:
        wa = "OPTED_OUT"
    elif client.whatsapp_opt_in:
        wa = "OPTED_IN"
    else:
        wa = "NOT_OPTED_IN"
    return ClientSummary(
        client=ClientOut.model_validate(client),
        counts={
            "documents": count(
                select(Document.id).where(
                    Document.organization_id == principal.org_id, Document.client_id == cid, Document.deleted_at.is_(None)
                )
            ),
            "open_tasks": len(open_tasks),
            "pending_requests": len(pending_reqs),
            "invoices": count(select(Invoice.id).where(Invoice.organization_id == principal.org_id, Invoice.client_id == cid)),
            "messages": count(
                select(Message.id)
                .join(Conversation, Conversation.id == Message.conversation_id)
                .where(Conversation.organization_id == principal.org_id, Conversation.client_id == cid)
            ),
        },
        outstanding_amount=str(Decimal(outstanding).quantize(Decimal("0.01"))),
        whatsapp_status=wa,
        last_message_at=conv.last_message_at if conv else None,
        pending_requests=[
            {
                "id": str(r.id),
                "title": r.title,
                "status": r.status,
                "due_date": r.due_date.isoformat() if r.due_date else None,
                "pending_items": [i.name for i in r.items if i.status == "PENDING"],
            }
            for r in pending_reqs
        ],
        open_tasks=[
            {
                "id": str(t.id),
                "title": t.title,
                "status": t.status,
                "service_type": t.service_type,
                "due_date": t.due_date.isoformat() if t.due_date else None,
            }
            for t in open_tasks
        ],
    )


def client_timeline(db: Session, principal: Principal, client_id: uuid.UUID, limit: int = 50) -> list[dict[str, Any]]:
    """Unified communication/document/task/invoice history from the audit trail + messages."""
    client = get_client(db, principal, client_id)
    logs = (
        db.execute(
            select(AuditLog)
            .where(
                AuditLog.organization_id == principal.org_id,
                or_(AuditLog.client_id == client.id, (AuditLog.resource == "client") & (AuditLog.resource_id == str(client.id))),
            )
            .order_by(AuditLog.timestamp.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [
        {
            "action": a.action,
            "resource": a.resource,
            "resource_id": a.resource_id,
            "timestamp": a.timestamp,
            "actor_type": a.actor_type,
            "user_id": a.user_id,
        }
        for a in logs
    ]


CSV_FIELDS = ["name", "phone", "email", "client_type", "pan", "gstin", "address", "assigned_employee_email", "whatsapp_opt_in", "notes"]


def import_csv(db: Session, principal: Principal, content: bytes) -> ImportResult:
    principal.require(Perm.CLIENT_CREATE)
    if len(content) > 5 * 1024 * 1024:
        raise ValidationFailed("CSV file too large (max 5 MB)")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValidationFailed("CSV must be UTF-8 encoded") from None
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "name" not in reader.fieldnames or "phone" not in reader.fieldnames:
        raise ValidationFailed("CSV must include 'name' and 'phone' columns", details={"expected": CSV_FIELDS})
    users = {u.email.lower(): u.id for u in db.execute(select(User).where(User.organization_id == principal.org_id)).unique().scalars()}
    created, skipped, errors = 0, 0, []
    for i, row in enumerate(reader, start=2):
        if i > 5002:
            errors.append({"row": i, "error": "Row limit (5000) reached"})
            break
        try:
            email_assignee = (row.get("assigned_employee_email") or "").strip().lower()
            data = ClientCreate(
                name=(row.get("name") or "").strip(),
                phone=(row.get("phone") or "").strip(),
                email=(row.get("email") or "").strip() or None,
                client_type=(row.get("client_type") or "INDIVIDUAL").strip().upper(),  # type: ignore[arg-type]
                pan=(row.get("pan") or "").strip() or None,
                gstin=(row.get("gstin") or "").strip() or None,
                address=(row.get("address") or "").strip() or None,
                notes=(row.get("notes") or "").strip() or None,
                assigned_employee_id=users.get(email_assignee) if email_assignee else None,
                whatsapp_opt_in=(row.get("whatsapp_opt_in") or "").strip().lower() in ("yes", "true", "1", "y"),
            )
            with db.begin_nested():
                create_client(db, principal, data, commit=False)
            created += 1
        except Conflict:
            skipped += 1
            errors.append({"row": i, "error": "Duplicate phone number"})
        except ValidationError as e:
            skipped += 1
            errors.append({"row": i, "error": "; ".join(err["msg"] for err in e.errors())[:300]})
        except (ValidationFailed, NotFound) as e:
            skipped += 1
            errors.append({"row": i, "error": e.message})
    audit.record(db, principal, AuditAction.CLIENT_IMPORTED, resource="client", metadata={"created": created, "skipped": skipped})
    db.commit()
    return ImportResult(created=created, skipped=skipped, errors=errors[:200])
