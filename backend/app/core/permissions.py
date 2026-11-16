"""Permission catalogue and default role → permission mapping.

Business code checks *permissions*, never role names. Roles are data (DB rows) seeded
from this mapping, so firms can later get custom roles without code changes.
"""

from __future__ import annotations

from enum import StrEnum


class Perm(StrEnum):
    CLIENT_VIEW = "CLIENT_VIEW"
    CLIENT_VIEW_ALL = "CLIENT_VIEW_ALL"  # without it, staff only see clients assigned to them
    CLIENT_CREATE = "CLIENT_CREATE"
    CLIENT_UPDATE = "CLIENT_UPDATE"
    CLIENT_DELETE = "CLIENT_DELETE"
    DOCUMENT_VIEW = "DOCUMENT_VIEW"
    DOCUMENT_UPLOAD = "DOCUMENT_UPLOAD"
    DOCUMENT_APPROVE = "DOCUMENT_APPROVE"
    DOCUMENT_DOWNLOAD = "DOCUMENT_DOWNLOAD"
    DOCUMENT_DELETE = "DOCUMENT_DELETE"
    DOCUMENT_SHARE = "DOCUMENT_SHARE"
    TASK_VIEW = "TASK_VIEW"
    TASK_CREATE = "TASK_CREATE"
    TASK_ASSIGN = "TASK_ASSIGN"
    TASK_UPDATE = "TASK_UPDATE"
    DOCUMENT_REQUEST_CREATE = "DOCUMENT_REQUEST_CREATE"
    DOCUMENT_REQUEST_MANAGE = "DOCUMENT_REQUEST_MANAGE"
    INVOICE_VIEW = "INVOICE_VIEW"
    INVOICE_CREATE = "INVOICE_CREATE"
    PAYMENT_VIEW = "PAYMENT_VIEW"
    WHATSAPP_VIEW = "WHATSAPP_VIEW"
    WHATSAPP_SEND = "WHATSAPP_SEND"
    WHATSAPP_MANAGE = "WHATSAPP_MANAGE"
    USER_MANAGE = "USER_MANAGE"
    REPORT_VIEW = "REPORT_VIEW"
    SETTINGS_MANAGE = "SETTINGS_MANAGE"
    AUDIT_VIEW = "AUDIT_VIEW"
    COMPLIANCE_MANAGE = "COMPLIANCE_MANAGE"
    ORG_MANAGE = "ORG_MANAGE"  # platform-level (super admin)
    # Client principal permissions (portal)
    PORTAL_ACCESS = "PORTAL_ACCESS"


class RoleName(StrEnum):
    SUPER_ADMIN = "SUPER_ADMIN"
    FIRM_ADMIN = "FIRM_ADMIN"
    PARTNER = "PARTNER"
    MANAGER = "MANAGER"
    EMPLOYEE = "EMPLOYEE"
    CLIENT = "CLIENT"


ALL_STAFF: set[Perm] = {p for p in Perm if p not in (Perm.ORG_MANAGE, Perm.PORTAL_ACCESS)}

DEFAULT_ROLE_PERMISSIONS: dict[RoleName, set[Perm]] = {
    RoleName.SUPER_ADMIN: {Perm.ORG_MANAGE, Perm.AUDIT_VIEW},
    RoleName.FIRM_ADMIN: set(ALL_STAFF),
    RoleName.PARTNER: set(ALL_STAFF) - {Perm.SETTINGS_MANAGE},
    RoleName.MANAGER: set(ALL_STAFF)
    - {Perm.SETTINGS_MANAGE, Perm.USER_MANAGE, Perm.WHATSAPP_MANAGE, Perm.CLIENT_DELETE, Perm.DOCUMENT_DELETE, Perm.AUDIT_VIEW},
    RoleName.EMPLOYEE: {
        Perm.CLIENT_VIEW,
        Perm.CLIENT_UPDATE,
        Perm.DOCUMENT_VIEW,
        Perm.DOCUMENT_UPLOAD,
        Perm.DOCUMENT_DOWNLOAD,
        Perm.DOCUMENT_SHARE,
        Perm.TASK_VIEW,
        Perm.TASK_CREATE,
        Perm.TASK_UPDATE,
        Perm.DOCUMENT_REQUEST_CREATE,
        Perm.DOCUMENT_REQUEST_MANAGE,
        Perm.INVOICE_VIEW,
        Perm.WHATSAPP_VIEW,
        Perm.WHATSAPP_SEND,
    },
    RoleName.CLIENT: {Perm.PORTAL_ACCESS},
}

PERMISSION_DESCRIPTIONS: dict[Perm, str] = {p: p.value.replace("_", " ").title() for p in Perm}
