"""Background jobs. Each task records its status in `background_jobs` and retries with
exponential backoff on transient failures."""

from __future__ import annotations

import uuid
from typing import Any

from celery import Task
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.logging import correlation_id_var, get_logger
from app.core.security import now_utc
from app.db.session import SessionLocal, session_scope
from app.models import BackgroundJob
from app.models.enums import JobStatus
from app.workers.celery_app import celery_app

log = get_logger("worker")


def _job_update(task_id: str, name: str, status: JobStatus, *, error: str | None = None, attempts: int | None = None) -> None:
    try:
        with session_scope() as db:
            values: dict[str, Any] = {"status": status}
            if status == JobStatus.RUNNING:
                values["started_at"] = now_utc()
            if status in (JobStatus.SUCCEEDED, JobStatus.FAILED):
                values["finished_at"] = now_utc()
            if error is not None:
                values["last_error"] = error[:1000]
            if attempts is not None:
                values["attempts"] = attempts
            db.execute(
                pg_insert(BackgroundJob)
                .values(id=uuid.uuid4(), task_id=task_id, name=name, **values)
                .on_conflict_do_update(index_elements=["task_id"], set_=values)
            )
    except Exception:
        log.warning("job_status_update_failed", extra={"task": name})


class TrackedTask(Task):  # type: ignore[misc]
    autoretry_for = ()
    max_retries = 5

    def before_start(self, task_id: str, args: Any, kwargs: Any) -> None:
        cid = (self.request.headers or {}).get("correlation_id") if self.request.headers else None
        correlation_id_var.set(cid or task_id)
        _job_update(task_id, self.name, JobStatus.RUNNING, attempts=self.request.retries + 1)

    def on_success(self, retval: Any, task_id: str, args: Any, kwargs: Any) -> None:
        _job_update(task_id, self.name, JobStatus.SUCCEEDED)

    def on_retry(self, exc: Exception, task_id: str, args: Any, kwargs: Any, einfo: Any) -> None:
        _job_update(task_id, self.name, JobStatus.RETRYING, error=str(exc))

    def on_failure(self, exc: Exception, task_id: str, args: Any, kwargs: Any, einfo: Any) -> None:
        log.error("job_failed", extra={"task": self.name, "error_type": type(exc).__name__})
        _job_update(task_id, self.name, JobStatus.FAILED, error=f"{type(exc).__name__}: {exc}")


def _backoff(retries: int, base: int = 10, cap: int = 900) -> int:
    return int(min(cap, base * (2**retries)))


@celery_app.task(name="whatsapp.send_message", base=TrackedTask, bind=True, max_retries=6)
def send_whatsapp_message(self: Task, message_id: str) -> str:
    from app.services.messaging import RetryableSendError, send_queued_message

    db = SessionLocal()
    try:
        msg = send_queued_message(db, uuid.UUID(message_id))
        return str(msg.status) if msg else "missing"
    except RetryableSendError as e:
        db.rollback()
        raise self.retry(exc=e, countdown=e.countdown) from e
    finally:
        db.close()


@celery_app.task(name="whatsapp.mark_read", base=TrackedTask, bind=True, max_retries=2)
def mark_read(self: Task, org_id: str, provider_message_id: str) -> None:
    from app.integrations.whatsapp import get_whatsapp_provider
    from app.services.messaging import get_account

    with session_scope() as db:
        try:
            get_whatsapp_provider(get_account(db, uuid.UUID(org_id))).mark_as_read(provider_message_id)
        except Exception as e:
            log.warning("mark_read_failed", extra={"error_type": type(e).__name__})


@celery_app.task(name="webhooks.process_whatsapp", base=TrackedTask, bind=True, max_retries=5)
def process_whatsapp_event(self: Task, event_id: str) -> None:
    from app.services.whatsapp_webhook import process_event

    db = SessionLocal()
    try:
        process_event(db, uuid.UUID(event_id))
    except Exception as e:
        raise self.retry(exc=e, countdown=_backoff(self.request.retries)) from e
    finally:
        db.close()


@celery_app.task(name="webhooks.retry_stuck", base=TrackedTask)
def retry_stuck_webhooks() -> int:
    from datetime import timedelta

    from sqlalchemy import select

    from app.models import WebhookEvent
    from app.models.enums import WebhookStatus
    from app.workers.dispatch import enqueue

    with session_scope() as db:
        cutoff = now_utc() - timedelta(minutes=5)
        ids = (
            db.execute(
                select(WebhookEvent.id)
                .where(
                    WebhookEvent.provider == "whatsapp",
                    WebhookEvent.status.in_([WebhookStatus.RECEIVED, WebhookStatus.FAILED]),
                    WebhookEvent.attempts < 5,
                    WebhookEvent.updated_at < cutoff,
                )
                .limit(100)
            )
            .scalars()
            .all()
        )
    for i in ids:
        enqueue("webhooks.process_whatsapp", event_id=str(i))
    return len(ids)


@celery_app.task(name="documents.deliver", base=TrackedTask, bind=True, max_retries=3)
def deliver_document(self: Task, document_id: str, initiated_by: str | None = None, version_id: str | None = None) -> None:
    from sqlalchemy import select

    from app.models import Document
    from app.services.delivery import deliver_document as _deliver

    db = SessionLocal()
    try:
        org_id = db.execute(select(Document.organization_id).where(Document.id == uuid.UUID(document_id))).scalar_one_or_none()
        if org_id is None:
            return
        _deliver(
            db,
            org_id,
            uuid.UUID(document_id),
            initiated_by=uuid.UUID(initiated_by) if initiated_by else None,
            version_id=uuid.UUID(version_id) if version_id else None,
        )
    except Exception as e:
        db.rollback()
        raise self.retry(exc=e, countdown=_backoff(self.request.retries, base=30)) from e
    finally:
        db.close()


@celery_app.task(name="documents.process", base=TrackedTask, bind=True, max_retries=3)
def process_document(self: Task, version_id: str) -> None:
    from app.services.misc import process_document_version

    db = SessionLocal()
    try:
        process_document_version(db, uuid.UUID(version_id))
    except Exception as e:
        db.rollback()
        raise self.retry(exc=e, countdown=_backoff(self.request.retries, base=30)) from e
    finally:
        db.close()


@celery_app.task(name="documents.purge_storage", base=TrackedTask, bind=True, max_retries=5)
def purge_storage(self: Task, document_id: str) -> int:
    from app.services.misc import purge_document_storage

    db = SessionLocal()
    try:
        return purge_document_storage(db, uuid.UUID(document_id))
    except Exception as e:
        raise self.retry(exc=e, countdown=_backoff(self.request.retries, base=60)) from e
    finally:
        db.close()


@celery_app.task(name="notifications.send_email", base=TrackedTask, bind=True, max_retries=5)
def send_email(self: Task, notification_id: str) -> None:
    from app.integrations.email import get_email_provider
    from app.models import Notification, User
    from app.models.enums import NotificationStatus

    with session_scope() as db:
        n = db.get(Notification, uuid.UUID(notification_id))
        if n is None or n.status != NotificationStatus.PENDING:
            return
        user = db.get(User, n.user_id) if n.user_id else None
        if user is None:
            n.status = NotificationStatus.FAILED
            n.error = "No recipient"
            return
        try:
            get_email_provider().send(user.email, n.title, (n.body or "") + (f"\n\n{n.link}" if n.link else ""))
            n.status, n.sent_at = NotificationStatus.SENT, now_utc()
        except Exception as e:
            n.error = str(e)[:300]
            raise self.retry(exc=e, countdown=_backoff(self.request.retries, base=60)) from e


@celery_app.task(name="reminders.run", base=TrackedTask)
def run_reminders() -> dict[str, Any]:
    from app.services.reminders import run_reminders as _run

    db = SessionLocal()
    try:
        return _run(db)
    finally:
        db.close()


@celery_app.task(name="maintenance.mark_overdue", base=TrackedTask)
def mark_overdue() -> int:
    from app.services.invoices import mark_overdue as _mark

    db = SessionLocal()
    try:
        return _mark(db)
    finally:
        db.close()


@celery_app.task(name="payments.reconcile", base=TrackedTask)
def reconcile_payments() -> int:
    from app.services.payments import reconcile_pending

    db = SessionLocal()
    try:
        return reconcile_pending(db)
    finally:
        db.close()


@celery_app.task(name="maintenance.retention_purge", base=TrackedTask)
def retention_purge() -> int:
    from app.services.misc import retention_purge as _purge

    db = SessionLocal()
    try:
        return _purge(db)
    finally:
        db.close()
