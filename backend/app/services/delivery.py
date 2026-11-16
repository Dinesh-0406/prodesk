"""Automatic document delivery over WhatsApp via secure, client-bound links.

The WhatsApp message never contains the document itself or a storage URL. It contains a
link to the ProDesk portal with an opaque delivery token. Opening it still requires the
client to authenticate (OTP to the phone on file); only then is a short-lived signed URL
issued for the specific approved version.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import Principal, system_principal
from app.core.errors import Forbidden, NotFound, ValidationFailed
from app.core.logging import get_logger
from app.core.permissions import Perm
from app.core.security import generate_opaque_token, hash_token, now_utc
from app.models import Client, Document, DocumentDelivery, DocumentVersion, Organization
from app.models.enums import DeliveryStatus, DocumentSource, DocumentStatus, MessageStatus, MessageType, TemplateKey, VersionStatus
from app.services import audit, messaging, notifications
from app.services.audit import AuditAction
from app.services.documents import authorize_download, signed_url_for_version

log = get_logger(__name__)

DOC_LABELS = {
    "ITR_ACKNOWLEDGEMENT": "ITR Acknowledgement",
    "ITR_COMPUTATION": "ITR Computation",
    "BALANCE_SHEET": "Balance Sheet",
    "PROFIT_LOSS": "Profit & Loss Statement",
    "GST_RETURN": "GST Return",
    "GST_CERTIFICATE": "GST Certificate",
    "TDS_DOCUMENT": "TDS Document",
    "AUDIT_REPORT": "Audit Report",
    "INVOICE": "Invoice",
    "RECEIPT": "Receipt",
    "PAN": "PAN",
    "AADHAAR": "Aadhaar",
    "BANK_STATEMENT": "Bank Statement",
    "OTHER": "Document",
}


def portal_link(raw_token: str) -> str:
    return f"{settings.FRONTEND_URL}/portal/link/{raw_token}"


def create_delivery(
    db: Session, doc: Document, version: DocumentVersion, *, initiated_by: uuid.UUID | None, channel: str = "WHATSAPP"
) -> tuple[DocumentDelivery, str]:
    raw = generate_opaque_token(32)
    d = DocumentDelivery(
        organization_id=doc.organization_id,
        document_id=doc.id,
        version_id=version.id,
        client_id=doc.client_id,
        channel=channel,
        token_hash=hash_token(raw),
        status=DeliveryStatus.PENDING,
        initiated_by=initiated_by,
        expires_at=now_utc() + timedelta(hours=settings.DELIVERY_LINK_TTL_HOURS),
    )
    db.add(d)
    db.flush()
    return d, raw


def deliver_document(
    db: Session, org_id: uuid.UUID, document_id: uuid.UUID, *, initiated_by: uuid.UUID | None = None, version_id: uuid.UUID | None = None
) -> DocumentDelivery | None:
    """Notification job: send DOCUMENT_READY for the current approved version (or an explicitly
    selected approved version)."""
    doc = (
        db.execute(select(Document).where(Document.id == document_id, Document.organization_id == org_id, Document.deleted_at.is_(None)))
        .unique()
        .scalar_one_or_none()
    )
    if doc is None or doc.status not in (DocumentStatus.APPROVED, DocumentStatus.DELIVERED):
        log.info("delivery_skipped_not_approved", extra={"document_id": str(document_id)})
        return None
    vid = version_id or doc.approved_version_id
    version = next((v for v in doc.versions if v.id == vid), None)
    if version is None or version.status != VersionStatus.APPROVED:
        raise ValidationFailed("Only approved versions can be delivered")
    client = db.get(Client, doc.client_id)
    assert client is not None
    delivery, raw = create_delivery(db, doc, version, initiated_by=initiated_by)
    org = db.get(Organization, org_id)
    label = DOC_LABELS.get(doc.document_type, "Document")
    params = [client.name, label, doc.financial_year or "-", org.name if org else ""]
    msg = messaging.send_template_to_client(db, client, TemplateKey.DOCUMENT_READY, params, url_suffix=f"link/{raw}")
    if msg.status == MessageStatus.FAILED and messaging.service_window_open(_contact(db, msg)):  # type: ignore[arg-type]
        # Template unavailable but the client messaged us in the last 24h: a free-form reply is allowed.
        msg = messaging.queue_message(
            db,
            org_id,
            messaging.Outbound(
                kind=MessageType.TEXT,
                body=f"Hello {client.name}, your {label} for FY {doc.financial_year or '-'} is ready. Open securely: {portal_link(raw)}",
            ),
            client=client,
        )
    delivery.message_id = msg.id
    if msg.status == MessageStatus.FAILED:
        delivery.status = DeliveryStatus.FAILED
        delivery.error = f"{msg.error_code}: {msg.error}"
        audit.record(
            db,
            system_principal(org_id),
            AuditAction.DOCUMENT_DELIVERY_FAILED,
            resource="document",
            resource_id=doc.id,
            client_id=client.id,
            metadata={"reason": msg.error_code},
        )
        notifications.notify_client_owner(
            db,
            org_id,
            client.assigned_employee_id,
            fallback_perm=Perm.DOCUMENT_APPROVE,
            type_="DELIVERY_FAILED",
            title=f"Could not deliver {label} to {client.name}",
            body=msg.error,
            link=f"/documents/{doc.id}",
        )
    else:
        audit.record(
            db,
            system_principal(org_id),
            AuditAction.DOCUMENT_DELIVERY_CREATED,
            resource="document",
            resource_id=doc.id,
            client_id=client.id,
            user_id=initiated_by,
            metadata={"delivery_id": str(delivery.id), "version": version.version_number},
        )
    db.commit()
    return delivery


def _contact(db: Session, msg: object) -> object:
    from app.models import Conversation

    conv = db.get(Conversation, msg.conversation_id)  # type: ignore[attr-defined]
    return conv.contact if conv else None


def manual_deliver(db: Session, principal: Principal, document_id: uuid.UUID, version_id: uuid.UUID | None) -> DocumentDelivery:
    principal.require(Perm.DOCUMENT_SHARE)
    from app.services.documents import get_document

    doc = get_document(db, principal, document_id)
    if doc.source != DocumentSource.STAFF:
        raise ValidationFailed("Client-uploaded documents are not delivered back")
    delivery = deliver_document(db, principal.org_id, doc.id, initiated_by=principal.user_id, version_id=version_id)
    if delivery is None:
        raise ValidationFailed("Document must be approved before delivery")
    return delivery


def resolve_delivery(db: Session, raw_token: str) -> DocumentDelivery:
    d = db.execute(select(DocumentDelivery).where(DocumentDelivery.token_hash == hash_token(raw_token))).scalar_one_or_none()
    if d is None:
        raise NotFound("This link is invalid")
    if d.expires_at < now_utc():
        raise NotFound("This link has expired. Ask your CA to resend it.", code="LINK_EXPIRED")
    return d


def download_via_delivery(db: Session, principal: Principal, raw_token: str) -> tuple[str, str]:
    """Client opened the WhatsApp link and authenticated: issue a short-lived URL."""
    d = resolve_delivery(db, raw_token)
    if not principal.is_client or d.organization_id != principal.org_id or d.client_id != principal.client_id:
        # Same response as a bad token to avoid confirming the link exists for someone else.
        raise NotFound("This link is invalid")
    doc = db.get(Document, d.document_id)
    version = db.get(DocumentVersion, d.version_id)
    if doc is None or version is None:
        raise NotFound("This link is invalid")
    if version.status != VersionStatus.APPROVED:
        raise Forbidden("This document has been replaced. Ask your CA for the latest version.")
    authorize_download(principal, doc, version, inline=False)
    url, _ = signed_url_for_version(version, inline=False)
    now = now_utc()
    d.downloaded_at = d.downloaded_at or now
    d.download_count += 1
    d.status = DeliveryStatus.DOWNLOADED
    audit.record(
        db,
        principal,
        AuditAction.DOCUMENT_DOWNLOADED,
        resource="document",
        resource_id=doc.id,
        client_id=doc.client_id,
        metadata={"delivery_id": str(d.id), "version": version.version_number, "via": "whatsapp_link"},
    )
    db.commit()
    return url, version.file_name
