"""Import every model so Alembic autogenerate and relationship resolution see them."""

from app.models.billing import Invoice, InvoiceItem, Payment, PaymentAttempt, Receipt
from app.models.client import Client, ClientOtp, ConsentRecord
from app.models.document import Document, DocumentDelivery, DocumentVersion
from app.models.organization import Organization
from app.models.system import AuditLog, BackgroundJob, Notification, ReminderLog
from app.models.user import ActionToken, Permission, RefreshToken, Role, User, role_permissions
from app.models.whatsapp import (
    Conversation,
    Message,
    MessageTemplate,
    WebhookEvent,
    WhatsAppAccount,
    WhatsAppContact,
)
from app.models.work import ComplianceEvent, DocumentRequest, DocumentRequestItem, SupportRequest, Task

__all__ = [
    "ActionToken",
    "AuditLog",
    "BackgroundJob",
    "Client",
    "ClientOtp",
    "ComplianceEvent",
    "ConsentRecord",
    "Conversation",
    "Document",
    "DocumentDelivery",
    "DocumentRequest",
    "DocumentRequestItem",
    "DocumentVersion",
    "Invoice",
    "InvoiceItem",
    "Message",
    "MessageTemplate",
    "Notification",
    "Organization",
    "Payment",
    "PaymentAttempt",
    "Permission",
    "Receipt",
    "RefreshToken",
    "ReminderLog",
    "Role",
    "SupportRequest",
    "Task",
    "User",
    "WebhookEvent",
    "WhatsAppAccount",
    "WhatsAppContact",
    "role_permissions",
]
