from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery("prodesk", broker=settings.REDIS_URL, backend=settings.REDIS_URL, include=["app.workers.tasks"])
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    result_expires=86400,
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_always_eager=settings.CELERY_TASK_ALWAYS_EAGER,
    task_eager_propagates=False,
    task_default_queue="default",
    task_routes={
        "whatsapp.*": {"queue": "whatsapp"},
        "webhooks.*": {"queue": "webhooks"},
        "documents.*": {"queue": "documents"},
    },
    beat_schedule={
        "reminders-every-30-min": {"task": "reminders.run", "schedule": crontab(minute="*/30")},
        "mark-overdue-hourly": {"task": "maintenance.mark_overdue", "schedule": crontab(minute=5)},
        "payments-reconcile-15-min": {"task": "payments.reconcile", "schedule": crontab(minute="*/15")},
        "retry-stuck-webhooks-10-min": {"task": "webhooks.retry_stuck", "schedule": crontab(minute="*/10")},
        "retention-purge-daily": {"task": "maintenance.retention_purge", "schedule": crontab(hour=2, minute=30)},
    },
)
