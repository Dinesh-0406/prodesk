"""Dashboard, reports (+CSV), AI assistant, search, notifications, audit log, job status."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import Response
from sqlalchemy import select

from app.api.deps import DB, Staff
from app.core.errors import NotFound
from app.core.permissions import Perm
from app.models import BackgroundJob
from app.schemas.common import OkResponse
from app.schemas.messaging import AIChatRequest, AIChatResponse
from app.services import audit, misc, reports
from app.services.assistant import staff_assistant
from app.services.audit import AuditAction

router = APIRouter(tags=["insights"])


@router.get("/reports/dashboard")
def dashboard(principal: Staff, db: DB) -> dict[str, Any]:
    return reports.dashboard(db, principal)


@router.get("/reports")
def list_reports(principal: Staff) -> list[str]:
    principal.require(Perm.REPORT_VIEW)
    return list(reports.REPORTS)


@router.get("/reports/{name}")
def run_report(name: str, principal: Staff, db: DB) -> dict[str, Any]:
    return reports.run_report(db, principal, name)


@router.get("/reports/{name}/csv")
def export_report(name: str, principal: Staff, db: DB) -> Response:
    data = reports.run_report(db, principal, name)
    audit.record(db, principal, AuditAction.REPORT_EXPORTED, resource="report", resource_id=None, metadata={"report": name})
    db.commit()
    return Response(
        content=reports.to_csv(data), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="prodesk-{name}.csv"'}
    )


@router.post("/ai/assistant", response_model=AIChatResponse)
def ai_assistant(body: AIChatRequest, principal: Staff, db: DB) -> AIChatResponse:
    return staff_assistant.answer(db, principal, body.question)


@router.get("/search")
def search(principal: Staff, db: DB, q: str = Query(..., min_length=2, max_length=100)) -> dict[str, list[dict[str, Any]]]:
    return misc.global_search(db, principal, q)


@router.get("/notifications")
def notifications(principal: Staff, db: DB, unread_only: bool = False) -> list[dict[str, Any]]:
    return [
        {
            "id": str(n.id),
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "link": n.link,
            "read_at": n.read_at,
            "created_at": n.created_at,
        }
        for n in misc.list_notifications(db, principal, unread_only)
    ]


@router.post("/notifications/read", response_model=OkResponse)
def mark_read(principal: Staff, db: DB, ids: list[uuid.UUID] | None = None) -> OkResponse:
    misc.mark_notifications_read(db, principal, ids)
    return OkResponse()


@router.get("/audit-logs")
def audit_logs(
    principal: Staff,
    db: DB,
    action: str | None = None,
    resource: str | None = None,
    resource_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
) -> dict[str, Any]:
    rows, total = misc.list_audit(db, principal, action=action, resource=resource, resource_id=resource_id, page=page, page_size=page_size)
    return {
        "items": [
            {
                "id": str(a.id),
                "action": a.action,
                "resource": a.resource,
                "resource_id": a.resource_id,
                "user_id": a.user_id,
                "client_id": a.client_id,
                "actor_type": a.actor_type,
                "timestamp": a.timestamp,
                "ip": a.ip,
                "metadata": a.metadata_,
            }
            for a in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/jobs/{task_id}")
def job_status(task_id: str, principal: Staff, db: DB) -> dict[str, Any]:
    principal.require(Perm.SETTINGS_MANAGE)
    job = db.execute(select(BackgroundJob).where(BackgroundJob.task_id == task_id)).scalar_one_or_none()
    if job is None or (job.organization_id and job.organization_id != principal.org_id):
        raise NotFound("Job not found")
    return {
        "task_id": job.task_id,
        "name": job.name,
        "status": job.status,
        "attempts": job.attempts,
        "last_error": job.last_error,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }
