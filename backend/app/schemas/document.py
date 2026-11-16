from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import ORM


class DocumentVersionOut(ORM):
    id: uuid.UUID
    version_number: int
    file_name: str
    mime_type: str
    file_size: int
    checksum_sha256: str
    status: str
    uploaded_by: uuid.UUID | None
    reviewed_by: uuid.UUID | None
    reviewed_at: datetime | None
    review_note: str | None
    created_at: datetime


class ClientRef(ORM):
    id: uuid.UUID
    name: str


class DocumentOut(ORM):
    id: uuid.UUID
    client_id: uuid.UUID
    client: ClientRef
    task_id: uuid.UUID | None
    uploaded_by: uuid.UUID | None
    source: str
    file_name: str
    mime_type: str
    file_size: int
    document_type: str
    financial_year: str | None
    assessment_year: str | None
    description: str | None
    version: int
    status: str
    approved_version_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class DeliveryOut(ORM):
    id: uuid.UUID
    version_id: uuid.UUID
    channel: str
    status: str
    sent_at: datetime | None
    delivered_at: datetime | None
    read_at: datetime | None
    downloaded_at: datetime | None
    download_count: int
    expires_at: datetime
    error: str | None
    created_at: datetime


class AccessLogOut(BaseModel):
    action: str
    actor_type: str
    user_id: uuid.UUID | None
    client_id: uuid.UUID | None
    timestamp: datetime
    ip: str | None
    metadata: dict[str, Any]


class DocumentDetail(DocumentOut):
    versions: list[DocumentVersionOut]
    deliveries: list[DeliveryOut] = []
    access_history: list[AccessLogOut] = []
    extracted_metadata: dict[str, Any] = {}


class DocumentUpdate(BaseModel):
    document_type: str | None = None
    financial_year: str | None = Field(default=None, pattern=r"^20\d{2}-\d{2}$")
    assessment_year: str | None = Field(default=None, pattern=r"^20\d{2}-\d{2}$")
    description: str | None = Field(default=None, max_length=2000)
    task_id: uuid.UUID | None = None


class ReviewRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)
    deliver: bool | None = None  # None = follow org setting


class RejectRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=2000)


class DownloadUrlResponse(BaseModel):
    url: str
    expires_at: datetime
    file_name: str


class DeliverRequest(BaseModel):
    version_id: uuid.UUID | None = None
