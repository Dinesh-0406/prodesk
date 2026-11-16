"""Client authentication: phone + OTP. A phone number alone never grants access."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import client_principal
from app.core.errors import Unauthorized
from app.core.logging import get_logger
from app.core.phone import normalize_indian_phone
from app.core.rate_limit import hit
from app.core.security import create_access_token, generate_otp, hash_token, now_utc
from app.models import Client, ClientOtp, Organization
from app.models.enums import ClientStatus, MessageStatus, TemplateKey
from app.services import audit, messaging
from app.services.audit import AuditAction

log = get_logger(__name__)
GENERIC_MSG = "If this number is registered with the firm, a verification code has been sent on WhatsApp."


@dataclass
class OtpRequestResult:
    message: str
    dev_otp: str | None = None


@dataclass
class ClientSession:
    access_token: str
    expires_at: datetime
    client: Client
    org: Organization


def _find(db: Session, org_slug: str, phone: str) -> tuple[Organization | None, Client | None]:
    org = db.execute(
        select(Organization).where(Organization.slug == org_slug.lower().strip(), Organization.status == "ACTIVE")
    ).scalar_one_or_none()
    if org is None:
        return None, None
    client = (
        db.execute(select(Client).where(Client.organization_id == org.id, Client.phone == phone, Client.status != ClientStatus.ARCHIVED))
        .unique()
        .scalar_one_or_none()
    )
    return org, client


def request_otp(db: Session, *, org_slug: str, phone: str, ip: str) -> OtpRequestResult:
    e164 = normalize_indian_phone(phone)
    hit(f"otp_req_phone:{e164}", 3, 600, fail_closed=True)
    hit(f"otp_req_ip:{ip}", 10, 600, fail_closed=True)
    org, client = _find(db, org_slug, e164)
    if org is None or client is None:
        return OtpRequestResult(message=GENERIC_MSG)  # no enumeration of registered numbers
    code = generate_otp(6)
    db.execute(update(ClientOtp).where(ClientOtp.client_id == client.id, ClientOtp.consumed_at.is_(None)).values(consumed_at=now_utc()))
    db.add(
        ClientOtp(
            organization_id=org.id,
            client_id=client.id,
            code_hash=hash_token(f"{client.id}:{code}"),
            expires_at=now_utc() + timedelta(seconds=settings.OTP_TTL_SECONDS),
        )
    )
    # Meta authentication templates take the code in the body AND as the copy-code button parameter.
    msg = messaging.send_template_to_client(db, client, TemplateKey.OTP, [code], url_suffix=code, bypass_opt_in=True)
    if msg.status == MessageStatus.FAILED and client.email:
        from app.integrations.email import get_email_provider

        get_email_provider().send(
            client.email,
            f"{org.name}: your verification code",
            f"{code} is your verification code. It expires in {settings.OTP_TTL_SECONDS // 60} minutes.",
        )
    db.commit()
    dev = code if (settings.dev_tools_enabled and settings.WHATSAPP_PROVIDER == "mock") else None
    return OtpRequestResult(message=GENERIC_MSG, dev_otp=dev)


def verify_otp(db: Session, *, org_slug: str, phone: str, code: str, ip: str) -> ClientSession:
    e164 = normalize_indian_phone(phone)
    hit(f"otp_verify_ip:{ip}", 20, 600, fail_closed=True)
    org, client = _find(db, org_slug, e164)
    if org is None or client is None:
        raise Unauthorized("Invalid or expired code", code="INVALID_OTP")
    otp = (
        db.execute(
            select(ClientOtp)
            .where(ClientOtp.client_id == client.id, ClientOtp.consumed_at.is_(None))
            .order_by(ClientOtp.created_at.desc())
            .with_for_update()
        )
        .scalars()
        .first()
    )
    now = now_utc()
    if otp is None or otp.expires_at < now or otp.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise Unauthorized("Invalid or expired code", code="INVALID_OTP")
    if otp.code_hash != hash_token(f"{client.id}:{code}"):
        otp.attempts += 1
        if otp.attempts >= settings.OTP_MAX_ATTEMPTS:
            otp.consumed_at = now
        audit.record(
            db,
            None,
            AuditAction.CLIENT_OTP_FAILED,
            resource="client",
            resource_id=client.id,
            organization_id=org.id,
            client_id=client.id,
            ip=ip,
        )
        db.commit()
        raise Unauthorized("Invalid or expired code", code="INVALID_OTP")
    otp.consumed_at = now
    token, _, exp = create_access_token(
        subject=str(client.id), typ="client", org_id=str(org.id), ttl=timedelta(minutes=settings.CLIENT_SESSION_TTL_MINUTES)
    )
    audit.record(db, client_principal(org.id, client.id), AuditAction.CLIENT_LOGIN, resource="client", resource_id=client.id, ip=ip)
    db.commit()
    return ClientSession(access_token=token, expires_at=exp, client=client, org=org)
