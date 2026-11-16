"""Reminder engine. Anti-spam controls: per-org frequency, max reminders, quiet hours,
client opt-out, per-slot de-duplication (ReminderLog unique key) and a full audit trail."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.core.permissions import Perm
from app.core.security import now_utc
from app.models import Client, ComplianceEvent, DocumentRequest, Invoice, Organization, ReminderLog, SupportRequest, Task
from app.models.enums import (
    TASK_DONE_STATUSES,
    MessageStatus,
    MessageType,
    SupportRequestStatus,
    SupportRequestType,
    TemplateKey,
)
from app.services import messaging, notifications
from app.services.document_requests import OPEN_STATUSES, pending_item_names, recompute_status
from app.services.invoices import OPEN as OPEN_INVOICES

log = get_logger("reminders")


def _parse_hm(v: str) -> time:
    h, m = v.split(":")
    return time(int(h), int(m))


def in_quiet_hours(org: Organization, now: datetime) -> bool:
    cfg = org.merged_settings()["reminders"]
    tz = ZoneInfo(org.timezone or "Asia/Kolkata")
    local = now.astimezone(tz).time()
    start, end = _parse_hm(cfg["quiet_hours_start"]), _parse_hm(cfg["quiet_hours_end"])
    if start <= end:
        return start <= local < end
    return local >= start or local < end  # window wraps midnight


def _claim(
    db: Session,
    org_id: uuid.UUID,
    *,
    kind: str,
    target_type: str,
    target_id: uuid.UUID,
    dedupe: str,
    channel: str,
    client_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
) -> bool:
    row = db.execute(
        pg_insert(ReminderLog)
        .values(
            id=uuid.uuid4(),
            organization_id=org_id,
            kind=kind,
            target_type=target_type,
            target_id=target_id,
            client_id=client_id,
            user_id=user_id,
            channel=channel,
            dedupe_key=dedupe[:200],
            status="SENT",
        )
        .on_conflict_do_nothing(index_elements=["organization_id", "dedupe_key"])
        .returning(ReminderLog.id)
    ).first()
    return row is not None


def _client_ok(client: Client | None) -> bool:
    return bool(client and client.can_receive_whatsapp and not client.reminders_opt_out)


def run_for_org(db: Session, org: Organization, now: datetime, today: date) -> dict[str, int]:
    cfg = org.merged_settings()["reminders"]
    freq = timedelta(hours=int(cfg["frequency_hours"]))
    max_n = int(cfg["max_reminders"])
    quiet = in_quiet_hours(org, now)
    counts = {"document_requests": 0, "invoices": 0, "tasks": 0, "compliance": 0, "appointments": 0, "overdue_marked": 0}

    # Document requests: status upkeep + client reminders
    for req in (
        db.execute(select(DocumentRequest).where(DocumentRequest.organization_id == org.id, DocumentRequest.status.in_(OPEN_STATUSES)))
        .unique()
        .scalars()
    ):
        before = req.status
        recompute_status(req, today)
        if req.status != before and req.status == "OVERDUE":
            counts["overdue_marked"] += 1
        if quiet or not cfg.get("document_reminders_enabled", True) or req.reminders_sent >= max_n:
            continue
        last = req.last_reminder_at or req.notified_at or req.created_at
        client = db.get(Client, req.client_id)
        if now - last < freq or not _client_ok(client):
            continue
        n = req.reminders_sent + 1
        if not _claim(
            db,
            org.id,
            kind="DOCUMENT_REMINDER",
            target_type="document_request",
            target_id=req.id,
            dedupe=f"docreq:{req.id}:{n}",
            channel="WHATSAPP",
            client_id=req.client_id,
        ):
            continue
        assert client is not None
        due = req.due_date.strftime("%d %b %Y") if req.due_date else "as soon as possible"
        msg = messaging.send_template_to_client(
            db,
            client,
            TemplateKey.DOCUMENT_REMINDER,
            [client.name, req.title, ", ".join(pending_item_names(req))[:500], due],
            url_suffix="requests",
        )
        if msg.status != MessageStatus.FAILED:
            req.reminders_sent = n
            req.last_reminder_at = now
            counts["document_requests"] += 1

    # Invoices due within 3 days or overdue
    if not quiet and cfg.get("invoice_reminders_enabled", True):
        for inv in (
            db.execute(
                select(Invoice).where(
                    Invoice.organization_id == org.id,
                    Invoice.status.in_(OPEN_INVOICES),
                    Invoice.due_date <= today + timedelta(days=3),
                    Invoice.reminders_sent < max_n,
                )
            )
            .unique()
            .scalars()
        ):
            last = inv.last_reminder_at or inv.sent_at or inv.created_at
            client = db.get(Client, inv.client_id)
            if now - last < freq or not _client_ok(client):
                continue
            n = inv.reminders_sent + 1
            if not _claim(
                db,
                org.id,
                kind="PAYMENT_REMINDER",
                target_type="invoice",
                target_id=inv.id,
                dedupe=f"invoice:{inv.id}:{n}",
                channel="WHATSAPP",
                client_id=inv.client_id,
            ):
                continue
            assert client is not None
            msg = messaging.send_template_to_client(
                db,
                client,
                TemplateKey.PAYMENT_REMINDER,
                [client.name, inv.invoice_number, f"{inv.balance_due:,.2f}", inv.due_date.strftime("%d %b %Y")],
                url_suffix="invoices",
            )
            if msg.status != MessageStatus.FAILED:
                inv.reminders_sent = n
                inv.last_reminder_at = now
                counts["invoices"] += 1

    # Task deadlines → staff (in-app), once per due date
    for t in (
        db.execute(
            select(Task).where(
                Task.organization_id == org.id,
                Task.due_date.is_not(None),
                Task.due_date <= today + timedelta(days=1),
                Task.status.not_in([s.value for s in TASK_DONE_STATUSES]),
            )
        )
        .unique()
        .scalars()
    ):
        if t.assigned_employee_id and _claim(
            db,
            org.id,
            kind="TASK_DEADLINE",
            target_type="task",
            target_id=t.id,
            dedupe=f"task:{t.id}:{t.due_date}",
            channel="IN_APP",
            user_id=t.assigned_employee_id,
        ):
            overdue = t.due_date < today  # type: ignore[operator]
            notifications.notify_users(
                db,
                org.id,
                [t.assigned_employee_id],
                type_="TASK_DEADLINE",
                title=("Overdue: " if overdue else "Due soon: ") + t.title,
                body=f"Due {t.due_date:%d %b %Y}",
                link=f"/tasks/{t.id}",
            )
            counts["tasks"] += 1

    # Compliance deadlines (admin-configured / verified only) → staff
    for ce in db.execute(
        select(ComplianceEvent).where(
            ComplianceEvent.organization_id == org.id,
            ComplianceEvent.due_date >= today,
            ComplianceEvent.due_date <= today + timedelta(days=60),
        )
    ).scalars():
        if (ce.due_date - today).days <= ce.reminder_days_before and _claim(
            db,
            org.id,
            kind="COMPLIANCE_DEADLINE",
            target_type="compliance_event",
            target_id=ce.id,
            dedupe=f"compliance:{ce.id}",
            channel="IN_APP",
        ):
            notifications.notify_permission(
                db,
                org.id,
                Perm.TASK_VIEW,
                type_="COMPLIANCE_DEADLINE",
                title=f"{ce.category}: {ce.title}",
                body=f"Due {ce.due_date:%d %b %Y}",
                link="/compliance",
            )
            counts["compliance"] += 1

    # Appointments in the next 24h → client (only inside service window) + staff
    for sr in (
        db.execute(
            select(SupportRequest).where(
                SupportRequest.organization_id == org.id,
                SupportRequest.request_type == SupportRequestType.APPOINTMENT,
                SupportRequest.status != SupportRequestStatus.RESOLVED,
                SupportRequest.scheduled_at.is_not(None),
                SupportRequest.scheduled_at > now,
                SupportRequest.scheduled_at <= now + timedelta(hours=24),
            )
        )
        .unique()
        .scalars()
    ):
        if not _claim(
            db,
            org.id,
            kind="APPOINTMENT",
            target_type="support_request",
            target_id=sr.id,
            dedupe=f"appt:{sr.id}:{sr.scheduled_at}",
            channel="WHATSAPP",
            client_id=sr.client_id,
        ):
            continue
        assert sr.scheduled_at is not None
        client = db.get(Client, sr.client_id)
        if client and not quiet and _client_ok(client):
            conv = messaging.conversation_for_client(db, client)
            if messaging.service_window_open(conv.contact):
                tz = ZoneInfo(org.timezone or "Asia/Kolkata")
                messaging.queue_message(
                    db,
                    org.id,
                    messaging.Outbound(
                        kind=MessageType.TEXT,
                        body=f"Reminder: your appointment with {org.name} is on {sr.scheduled_at.astimezone(tz):%d %b %Y at %I:%M %p}.",
                    ),
                    conversation=conv,
                )  # type: ignore[union-attr]
        if sr.assigned_to:
            notifications.notify_users(
                db,
                org.id,
                [sr.assigned_to],
                type_="APPOINTMENT",
                title=f"Appointment with {client.name if client else 'client'}",
                body=f"{sr.scheduled_at:%d %b %Y %H:%M}",
                link="/support",
            )  # type: ignore[union-attr]
        counts["appointments"] += 1
    db.commit()
    return counts


def run_reminders(db: Session, now: datetime | None = None, today: date | None = None) -> dict[str, Any]:
    now = now or now_utc()
    today = today or date.today()
    totals: dict[str, Any] = {}
    for org in db.execute(select(Organization).where(Organization.status == "ACTIVE")).scalars().all():
        try:
            for k, v in run_for_org(db, org, now, today).items():
                totals[k] = totals.get(k, 0) + v
        except Exception:
            db.rollback()
            log.exception("reminders_failed_for_org", extra={"org_id": str(org.id)})
    log.info("reminders_run", extra={"totals": totals})
    return totals
