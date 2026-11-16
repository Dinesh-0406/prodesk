from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, File, Query, UploadFile

from app.api.deps import DB, Staff
from app.schemas.client import ClientCreate, ClientOut, ClientSummary, ClientUpdate, ConsentIn, ImportResult
from app.schemas.common import Page
from app.services import clients as svc
from app.services import misc

router = APIRouter(prefix="/clients", tags=["clients"])


@router.get("", response_model=Page[ClientOut])
def list_clients(
    principal: Staff,
    db: DB,
    q: str | None = None,
    status: str | None = None,
    client_type: str | None = None,
    assigned_employee_id: uuid.UUID | None = None,
    sort: str = Query("name", pattern="^(name|created_at|updated_at)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
) -> Page[ClientOut]:
    rows, total = svc.list_clients(
        db,
        principal,
        q=q,
        status=status,
        client_type=client_type,
        assigned_employee_id=assigned_employee_id,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )
    return Page(items=[ClientOut.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=ClientOut, status_code=201)
def create_client(body: ClientCreate, principal: Staff, db: DB) -> ClientOut:
    return ClientOut.model_validate(svc.create_client(db, principal, body))


@router.post("/import", response_model=ImportResult)
async def import_clients(principal: Staff, db: DB, file: UploadFile = File(...)) -> ImportResult:
    return svc.import_csv(db, principal, await file.read(5 * 1024 * 1024 + 1))


@router.get("/import/template")
def import_template() -> dict[str, Any]:
    return {
        "columns": svc.CSV_FIELDS,
        "example": "Rahul Sharma,9876543210,rahul@example.com,INDIVIDUAL,ABCDE1234F,,Pune,employee@firm.in,yes,",
    }


@router.get("/{client_id}", response_model=ClientOut)
def get_client(client_id: uuid.UUID, principal: Staff, db: DB) -> ClientOut:
    return ClientOut.model_validate(svc.get_client(db, principal, client_id))


@router.get("/{client_id}/summary", response_model=ClientSummary)
def client_summary(client_id: uuid.UUID, principal: Staff, db: DB) -> ClientSummary:
    return svc.client_summary(db, principal, client_id)


@router.get("/{client_id}/timeline")
def client_timeline(client_id: uuid.UUID, principal: Staff, db: DB) -> list[dict[str, Any]]:
    return svc.client_timeline(db, principal, client_id)


@router.patch("/{client_id}", response_model=ClientOut)
def update_client(client_id: uuid.UUID, body: ClientUpdate, principal: Staff, db: DB) -> ClientOut:
    return ClientOut.model_validate(svc.update_client(db, principal, client_id, body))


@router.post("/{client_id}/archive", response_model=ClientOut)
def archive_client(client_id: uuid.UUID, principal: Staff, db: DB) -> ClientOut:
    return ClientOut.model_validate(svc.archive_client(db, principal, client_id))


@router.post("/{client_id}/consents", status_code=201)
def record_consent(client_id: uuid.UUID, body: ConsentIn, principal: Staff, db: DB) -> dict[str, Any]:
    rec = svc.record_consent(db, principal, client_id, body)
    return {"id": str(rec.id), "purpose": rec.purpose, "granted": rec.granted, "created_at": rec.created_at}


@router.post("/{client_id}/whatsapp/welcome", status_code=202)
def send_welcome(client_id: uuid.UUID, principal: Staff, db: DB) -> dict[str, str]:
    from app.core.permissions import Perm

    principal.require(Perm.WHATSAPP_SEND)
    svc.send_welcome(db, svc.get_client(db, principal, client_id))
    return {"status": "queued"}


@router.get("/{client_id}/export")
def export_client(client_id: uuid.UUID, principal: Staff, db: DB) -> dict[str, Any]:
    """Data export for the client's access/portability requests."""
    return misc.export_client_data(db, principal, client_id)


@router.post("/{client_id}/erase", status_code=202)
def erase_client(client_id: uuid.UUID, principal: Staff, db: DB) -> dict[str, str]:
    misc.erase_client(db, principal, client_id)
    return {"status": "erasure_scheduled"}
