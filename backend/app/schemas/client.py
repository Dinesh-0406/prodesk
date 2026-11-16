from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.models.enums import ClientStatus, ClientType
from app.schemas.common import ORM

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


class _ClientFields(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: str | None = None
    email: EmailStr | None = None
    address: str | None = Field(default=None, max_length=1000)
    client_type: ClientType | None = None
    pan: str | None = None
    gstin: str | None = None
    assigned_employee_id: uuid.UUID | None = None
    status: ClientStatus | None = None
    notes: str | None = Field(default=None, max_length=5000)
    whatsapp_opt_in: bool | None = None

    @field_validator("pan")
    @classmethod
    def _pan(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        v = v.strip().upper()
        if not PAN_RE.match(v):
            raise ValueError("Invalid PAN format")
        return v

    @field_validator("gstin")
    @classmethod
    def _gstin(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        v = v.strip().upper()
        if not GSTIN_RE.match(v):
            raise ValueError("Invalid GSTIN format")
        return v


class ClientCreate(_ClientFields):
    name: str = Field(min_length=2, max_length=200)
    phone: str
    client_type: ClientType = ClientType.INDIVIDUAL


class ClientUpdate(_ClientFields):
    pass


class EmployeeRef(ORM):
    id: uuid.UUID
    full_name: str


class ClientOut(ORM):
    id: uuid.UUID
    name: str
    phone: str
    email: str | None
    address: str | None
    client_type: str
    pan: str | None
    gstin: str | None
    assigned_employee_id: uuid.UUID | None
    assigned_employee: EmployeeRef | None
    status: str
    notes: str | None
    whatsapp_opt_in: bool
    whatsapp_opt_out_at: datetime | None
    reminders_opt_out: bool
    created_at: datetime
    updated_at: datetime


class ClientSummary(BaseModel):
    client: ClientOut
    counts: dict[str, int]
    outstanding_amount: str
    whatsapp_status: str
    last_message_at: datetime | None
    pending_requests: list[dict[str, object]]
    open_tasks: list[dict[str, object]]


class ConsentIn(BaseModel):
    purpose: str = Field(pattern=r"^[A-Z_]{3,64}$")
    granted: bool
    evidence: str | None = Field(default=None, max_length=1000)


class ImportResult(BaseModel):
    created: int
    skipped: int
    errors: list[dict[str, object]]
