"""Enqueue background jobs only after the surrounding DB transaction commits.

This prevents workers from racing ahead of uncommitted data, and guarantees that a
rolled-back request never triggers side effects (e.g. a WhatsApp message).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.core.logging import correlation_id_var, get_logger

log = get_logger(__name__)
_KEY = "prodesk_after_commit"


def enqueue(task_name: str, **kwargs: Any) -> str | None:
    from app.workers import tasks as _tasks  # noqa: F401  (task registry is needed for eager mode)
    from app.workers.celery_app import celery_app

    headers = {"correlation_id": correlation_id_var.get()}
    try:
        res = (
            celery_app.send_task(task_name, kwargs=kwargs, headers=headers)
            if not celery_app.conf.task_always_eager
            else celery_app.tasks[task_name].apply(kwargs=kwargs, headers=headers)
        )
        return str(res.id)
    except Exception:
        log.exception("enqueue_failed", extra={"task": task_name})
        return None


def on_commit(db: Session, fn: Callable[[], Any]) -> None:
    db.info.setdefault(_KEY, []).append(fn)


def enqueue_on_commit(db: Session, task_name: str, **kwargs: Any) -> None:
    on_commit(db, lambda: enqueue(task_name, **kwargs))


@event.listens_for(Session, "after_commit")
def _run_after_commit(session: Session) -> None:
    callbacks = session.info.pop(_KEY, [])
    for cb in callbacks:
        try:
            cb()
        except Exception:
            log.exception("after_commit_callback_failed")


@event.listens_for(Session, "after_rollback")
def _clear_after_rollback(session: Session) -> None:
    session.info.pop(_KEY, None)
