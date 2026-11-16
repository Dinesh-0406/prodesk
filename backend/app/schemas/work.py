from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import ComplianceCategory, ComplianceSource, ServiceType, TaskPriority, TaskStatus
from app.schemas.common import ORM
from app.schemas.document import ClientRef


class EmployeeRef(ORM):
    id: uuid.UUID
    full_name: str


class TaskCreate(BaseModel):
    client_id: uuid.UUID
    title: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    service_type: ServiceType = ServiceType.OTHER
    financial_year: str | None = Field(default=None, pattern=r"^20\d{2}-\d{2}$")
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.NEW_REQUEST
    due_date: date | None = None
    assigned_employee_id: uuid.UUID | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    service_type: ServiceType | None = None
    financial_year: str | None = Field(default=None, pattern=r"^20\d{2}-\d{2}$")
    priority: TaskPriority | None = None
    status: TaskStatus | None = None
    due_date: date | None = None
    assigned_employee_id: uuid.UUID | None = None
    filing_reference: str | None = Field(default=None, max_length=100)
    notify_client: bool = False


class TaskOut(ORM):
    id: uuid.UUID
    client_id: uuid.UUID
    client: ClientRef
    assigned_employee_id: uuid.UUID | None
    assigned_employee: EmployeeRef | None
    title: str
    description: str | None
    service_type: str
    financial_year: str | None
    priority: str
    status: str
    due_date: date | None
    created_by: uuid.UUID | None
    completed_at: datetime | None
    filed_at: datetime | None
    filing_reference: str | None
    created_at: datetime
    updated_at: datetime


class RequestItemIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    document_type: str | None = None
    is_required: bool = True


class DocumentRequestCreate(BaseModel):
    client_id: uuid.UUID
    task_id: uuid.UUID | None = None
    title: str = Field(min_length=2, max_length=255)
    instructions: str | None = Field(default=None, max_length=5000)
    due_date: date | None = None
    items: list[RequestItemIn] = Field(min_length=1, max_length=50)
    notify_client: bool = True


class RequestItemOut(ORM):
    id: uuid.UUID
    name: str
    document_type: str | None
    is_required: bool
    status: str
    document_id: uuid.UUID | None
    received_at: datetime | None


class DocumentRequestOut(ORM):
    id: uuid.UUID
    client_id: uuid.UUID
    client: ClientRef
    task_id: uuid.UUID | None
    title: str
    instructions: str | None
    due_date: date | None
    status: str
    reminders_sent: int
    last_reminder_at: datetime | None
    notified_at: datetime | None
    completed_at: datetime | None
    items: list[RequestItemOut]
    created_at: datetime


class ComplianceEventIn(BaseModel):
    category: ComplianceCategory
    title: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    due_date: date
    period: str | None = Field(default=None, max_length=32)
    source: ComplianceSource = ComplianceSource.ADMIN_CONFIGURED
    source_reference: str | None = Field(default=None, max_length=500)
    applies_to_client_types: list[str] = []
    client_id: uuid.UUID | None = None
    reminder_days_before: int = Field(default=3, ge=0, le=60)


class ComplianceEventOut(ORM):
    id: uuid.UUID
    category: str
    title: str
    description: str | None
    due_date: date
    period: str | None
    source: str
    source_reference: str | None
    verified_by: uuid.UUID | None
    applies_to_client_types: list[Any]
    client_id: uuid.UUID | None
    reminder_days_before: int
    created_at: datetime


class SupportRequestOut(ORM):
    id: uuid.UUID
    client_id: uuid.UUID
    client: ClientRef
    request_type: str
    message: str | None
    status: str
    scheduled_at: datetime | None
    created_at: datetime


class SupportRequestIn(BaseModel):
    request_type: str = Field(pattern="^(CALLBACK|APPOINTMENT|QUERY)$")
    message: str = Field(min_length=2, max_length=2000)


class SupportRequestUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(OPEN|IN_PROGRESS|RESOLVED)$")
    scheduled_at: datetime | None = None
    assigned_to: uuid.UUID | None = None
