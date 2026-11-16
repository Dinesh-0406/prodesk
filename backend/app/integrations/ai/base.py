"""AI provider interface.

The AI layer only *classifies* and *extracts*. It never authorises, never queries the
database, and never produces facts. Facts come from backend tools; replies are rendered
from those facts.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import DocumentType, ServiceType


class ClientIntentName(StrEnum):
    GET_ITR_STATUS = "GET_ITR_STATUS"
    GET_DOCUMENT = "GET_DOCUMENT"
    GET_PENDING_DOCUMENTS = "GET_PENDING_DOCUMENTS"
    GET_TASK_STATUS = "GET_TASK_STATUS"
    GET_INVOICE = "GET_INVOICE"
    GET_PAYMENT_STATUS = "GET_PAYMENT_STATUS"
    UPLOAD_DOCUMENT = "UPLOAD_DOCUMENT"
    APPOINTMENT_REQUEST = "APPOINTMENT_REQUEST"
    FAQ = "FAQ"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"
    UNKNOWN = "UNKNOWN"


FY_RE = re.compile(r"^20\d{2}-\d{2}$")


class ClientIntent(BaseModel):
    intent: ClientIntentName = ClientIntentName.UNKNOWN
    document_type: DocumentType | None = None
    financial_year: str | None = None
    service_type: ServiceType | None = None
    relative_year: int | None = Field(default=None, description="0=current FY, -1=last FY")
    confidence: float = 0.0
    language: str = "en"

    @field_validator("financial_year")
    @classmethod
    def _fy(cls, v: str | None) -> str | None:
        return v if v and FY_RE.match(v) else None


class StaffQueryName(StrEnum):
    CLIENTS_WITH_PENDING_DOCUMENTS = "CLIENTS_WITH_PENDING_DOCUMENTS"
    OVERDUE_TASKS = "OVERDUE_TASKS"
    UNPAID_INVOICES = "UNPAID_INVOICES"
    TASKS_DUE_THIS_WEEK = "TASKS_DUE_THIS_WEEK"
    CLIENTS_BY_EMPLOYEE = "CLIENTS_BY_EMPLOYEE"
    CLIENTS_MISSING_DOCUMENT = "CLIENTS_MISSING_DOCUMENT"
    UNSUPPORTED = "UNSUPPORTED"


class StaffQuery(BaseModel):
    query: StaffQueryName = StaffQueryName.UNSUPPORTED
    service_type: ServiceType | None = None
    employee_name: str | None = Field(default=None, max_length=100)
    document_name: str | None = Field(default=None, max_length=100)


class DocumentSuggestion(BaseModel):
    document_type: DocumentType | None = None
    financial_year: str | None = None
    confidence: float = 0.0

    @field_validator("financial_year")
    @classmethod
    def _fy(cls, v: str | None) -> str | None:
        return v if v and FY_RE.match(v) else None


class AIProvider(ABC):
    name: str

    @abstractmethod
    def classify_client_message(self, text: str) -> ClientIntent: ...

    @abstractmethod
    def classify_staff_query(self, text: str) -> StaffQuery: ...

    @abstractmethod
    def match_faq(self, text: str, faqs: list[dict[str, Any]]) -> int | None:
        """Return the index of the best-matching configured FAQ, or None. Never generates answers."""

    @abstractmethod
    def suggest_document_metadata(self, file_name: str, text_excerpt: str) -> DocumentSuggestion: ...
