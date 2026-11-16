"""WhatsApp template configuration. Template approval is tracked explicitly per org;
nothing assumes Meta has approved a template."""

from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import MessageTemplate
from app.models.enums import TemplateCategory, TemplateKey, TemplateStatus

DEFAULT_TEMPLATES: dict[TemplateKey, dict[str, Any]] = {
    TemplateKey.DOCUMENT_READY: {
        "name": "prodesk_document_ready",
        "category": TemplateCategory.UTILITY,
        "has_url_button": True,
        "variables": ["client_name", "document_label", "financial_year", "firm_name"],
        "body": "Hello {{1}}, your {{2}} for FY {{3}} from {{4}} is ready. Tap the button below to view it securely.",
    },
    TemplateKey.DOCUMENT_REQUEST: {
        "name": "prodesk_document_request",
        "category": TemplateCategory.UTILITY,
        "has_url_button": True,
        "variables": ["client_name", "firm_name", "request_title", "documents", "due_date"],
        "body": "Hello {{1}}, {{2}} needs the following documents for {{3}}: {{4}}. Please share them by {{5}}.",
    },
    TemplateKey.DOCUMENT_REMINDER: {
        "name": "prodesk_document_reminder",
        "category": TemplateCategory.UTILITY,
        "has_url_button": True,
        "variables": ["client_name", "request_title", "documents", "due_date"],
        "body": "Reminder: {{1}}, documents for {{2}} are still pending: {{3}}. Due: {{4}}.",
    },
    TemplateKey.PAYMENT_REMINDER: {
        "name": "prodesk_payment_reminder",
        "category": TemplateCategory.UTILITY,
        "has_url_button": True,
        "variables": ["client_name", "invoice_number", "amount", "due_date"],
        "body": "Hello {{1}}, invoice {{2}} for Rs. {{3}} is due on {{4}}. You can view and pay it securely.",
    },
    TemplateKey.INVOICE_CREATED: {
        "name": "prodesk_invoice_created",
        "category": TemplateCategory.UTILITY,
        "has_url_button": True,
        "variables": ["client_name", "firm_name", "invoice_number", "amount", "due_date"],
        "body": "Hello {{1}}, {{2}} has issued invoice {{3}} for Rs. {{4}}, due {{5}}.",
    },
    TemplateKey.TASK_COMPLETED: {
        "name": "prodesk_task_update",
        "category": TemplateCategory.UTILITY,
        "has_url_button": False,
        "variables": ["client_name", "task_title", "status", "firm_name"],
        "body": 'Hello {{1}}, your work "{{2}}" has been updated to: {{3}} by {{4}}.',
    },
    TemplateKey.WELCOME: {
        "name": "prodesk_welcome",
        "category": TemplateCategory.UTILITY,
        "has_url_button": False,
        "variables": ["client_name", "firm_name"],
        "body": "Welcome {{1}}! You will receive updates from {{2}} on this number. Reply STOP to opt out.",
    },
    TemplateKey.OTP: {
        "name": "prodesk_otp",
        "category": TemplateCategory.AUTHENTICATION,
        "has_url_button": False,
        "variables": ["code"],
        "body": "{{1}} is your verification code. For your security, do not share this code.",
    },
    TemplateKey.HUMAN_HANDOFF: {
        "name": "prodesk_human_handoff",
        "category": TemplateCategory.UTILITY,
        "has_url_button": False,
        "variables": ["client_name", "firm_name"],
        "body": "Hello {{1}}, a member of {{2}} will reply to you shortly.",
    },
}


def ensure_default_templates(db: Session, org_id: uuid.UUID) -> None:
    existing = {t.key for t in db.execute(select(MessageTemplate).where(MessageTemplate.organization_id == org_id)).scalars()}
    # With the mock provider there is no Meta review, so templates are usable immediately.
    initial = TemplateStatus.APPROVED if settings.WHATSAPP_PROVIDER == "mock" else TemplateStatus.NOT_SUBMITTED
    for key, spec in DEFAULT_TEMPLATES.items():
        if key.value in existing:
            continue
        db.add(
            MessageTemplate(
                organization_id=org_id,
                key=key.value,
                name=spec["name"],
                language="en",
                category=spec["category"],
                status=initial,
                body_preview=spec["body"],
                variables=spec["variables"],
                has_url_button=spec["has_url_button"],
            )
        )
    db.flush()


def get_template(db: Session, org_id: uuid.UUID, key: TemplateKey | str) -> MessageTemplate | None:
    return db.execute(
        select(MessageTemplate).where(MessageTemplate.organization_id == org_id, MessageTemplate.key == str(key))
    ).scalar_one_or_none()


def render_preview(body: str, params: list[str]) -> str:
    def sub(m: re.Match[str]) -> str:
        i = int(m.group(1)) - 1
        return params[i] if 0 <= i < len(params) else m.group(0)

    return re.sub(r"\{\{(\d+)\}\}", sub, body)
