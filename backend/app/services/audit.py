"""Audit logging. Metadata is always redacted; secrets/passwords are never stored."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.logging import redact, request_id_var
from app.models import AuditLog


class AuditAction(StrEnum):
    LOGIN = "LOGIN"
    LOGIN_FAILED = "LOGIN_FAILED"
    LOGOUT = "LOGOUT"
    PASSWORD_RESET_REQUESTED = "PASSWORD_RESET_REQUESTED"
    PASSWORD_RESET = "PASSWORD_RESET"
    ACCOUNT_ACTIVATED = "ACCOUNT_ACTIVATED"
    REFRESH_TOKEN_REUSE = "REFRESH_TOKEN_REUSE"
    CLIENT_LOGIN = "CLIENT_LOGIN"
    CLIENT_OTP_FAILED = "CLIENT_OTP_FAILED"
    ORG_CREATED = "ORG_CREATED"
    SETTINGS_UPDATED = "SETTINGS_UPDATED"
    USER_INVITED = "USER_INVITED"
    USER_PERMISSION_CHANGED = "USER_PERMISSION_CHANGED"
    USER_DEACTIVATED = "USER_DEACTIVATED"
    CLIENT_CREATED = "CLIENT_CREATED"
    CLIENT_UPDATED = "CLIENT_UPDATED"
    CLIENT_ARCHIVED = "CLIENT_ARCHIVED"
    CLIENT_IMPORTED = "CLIENT_IMPORTED"
    CLIENT_DATA_EXPORTED = "CLIENT_DATA_EXPORTED"
    CLIENT_ERASED = "CLIENT_ERASED"
    CONSENT_RECORDED = "CONSENT_RECORDED"
    DOCUMENT_UPLOADED = "DOCUMENT_UPLOADED"
    DOCUMENT_VERSION_UPLOADED = "DOCUMENT_VERSION_UPLOADED"
    DOCUMENT_SUBMITTED = "DOCUMENT_SUBMITTED"
    DOCUMENT_VIEWED = "DOCUMENT_VIEWED"
    DOCUMENT_DOWNLOADED = "DOCUMENT_DOWNLOADED"
    DOCUMENT_APPROVED = "DOCUMENT_APPROVED"
    DOCUMENT_REJECTED = "DOCUMENT_REJECTED"
    DOCUMENT_ARCHIVED = "DOCUMENT_ARCHIVED"
    DOCUMENT_DELETED = "DOCUMENT_DELETED"
    DOCUMENT_DELIVERY_CREATED = "DOCUMENT_DELIVERY_CREATED"
    DOCUMENT_DELIVERY_FAILED = "DOCUMENT_DELIVERY_FAILED"
    TASK_CREATED = "TASK_CREATED"
    TASK_UPDATED = "TASK_UPDATED"
    DOCUMENT_REQUEST_CREATED = "DOCUMENT_REQUEST_CREATED"
    DOCUMENT_REQUEST_UPDATED = "DOCUMENT_REQUEST_UPDATED"
    WHATSAPP_SENT = "WHATSAPP_SENT"
    WHATSAPP_FAILED = "WHATSAPP_FAILED"
    WHATSAPP_RECEIVED = "WHATSAPP_RECEIVED"
    WHATSAPP_CONFIGURED = "WHATSAPP_CONFIGURED"
    WHATSAPP_OPT_OUT = "WHATSAPP_OPT_OUT"
    WHATSAPP_OPT_IN = "WHATSAPP_OPT_IN"
    HANDOVER_CHANGED = "HANDOVER_CHANGED"
    INVOICE_CREATED = "INVOICE_CREATED"
    INVOICE_SENT = "INVOICE_SENT"
    INVOICE_CANCELLED = "INVOICE_CANCELLED"
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED"
    PAYMENT_VERIFICATION_FAILED = "PAYMENT_VERIFICATION_FAILED"
    WEBHOOK_REJECTED = "WEBHOOK_REJECTED"
    AI_QUERY = "AI_QUERY"
    COMPLIANCE_EVENT_CREATED = "COMPLIANCE_EVENT_CREATED"
    REPORT_EXPORTED = "REPORT_EXPORTED"


def record(
    db: Session,
    principal: Principal | None,
    action: AuditAction | str,
    *,
    resource: str | None = None,
    resource_id: uuid.UUID | str | None = None,
    metadata: dict[str, Any] | None = None,
    organization_id: uuid.UUID | None = None,
    client_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    ip: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        organization_id=organization_id or (principal.organization_id if principal else None),
        user_id=user_id or (principal.user_id if principal else None),
        client_id=client_id or (principal.client_id if principal else None),
        actor_type=principal.actor_type if principal else "SYSTEM",
        action=str(action),
        resource=resource,
        resource_id=str(resource_id) if resource_id else None,
        ip=ip or (principal.ip if principal else None),
        request_id=request_id_var.get(),
        metadata_=redact(metadata or {}),
    )
    db.add(entry)
    return entry
