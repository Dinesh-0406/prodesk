"""Organization profile/settings, WhatsApp account configuration and templates."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import Principal
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.permissions import Perm
from app.core.phone import normalize_indian_phone
from app.core.security import encrypt_secret, mask_secret, now_utc
from app.integrations.storage import get_storage, new_storage_key
from app.models import MessageTemplate, Organization, WhatsAppAccount
from app.models.enums import TemplateStatus, WhatsAppAccountStatus
from app.schemas.org import OrganizationUpdate, TemplateUpdate, WhatsAppAccountOut, WhatsAppAccountUpdate
from app.services import audit
from app.services.audit import AuditAction

ONBOARDING_STEPS = ["FIRM_PROFILE", "WHATSAPP_SETUP", "INVITE_EMPLOYEES", "ADD_CLIENTS", "READY"]
SETTINGS_SECTIONS = ("working_hours", "notifications", "reminders", "invoice", "privacy")


def get_org(db: Session, principal: Principal) -> Organization:
    org = db.get(Organization, principal.org_id)
    if org is None:
        raise NotFound("Organization not found")
    return org


def update_org(db: Session, principal: Principal, data: OrganizationUpdate) -> Organization:
    principal.require(Perm.SETTINGS_MANAGE)
    org = get_org(db, principal)
    payload = data.model_dump(exclude_unset=True)
    for field in ("name", "email", "address", "timezone"):
        if field in payload and payload[field] is not None:
            setattr(org, field, payload[field])
    if payload.get("phone"):
        org.phone = normalize_indian_phone(payload["phone"])
    if payload.get("timezone"):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(payload["timezone"])
        except (ZoneInfoNotFoundError, ValueError):
            raise ValidationFailed("Unknown timezone") from None
    new_settings: dict[str, Any] = dict(org.settings or {})
    for section in SETTINGS_SECTIONS:
        if payload.get(section) is not None:
            new_settings[section] = {**new_settings.get(section, {}), **payload[section]}
    if payload.get("faqs") is not None:
        faqs = [
            {
                "question": str(f.get("question", ""))[:300],
                "answer": str(f.get("answer", ""))[:1000],
                "keywords": [str(k)[:40] for k in f.get("keywords", [])][:10],
            }
            for f in payload["faqs"][:50]
        ]
        new_settings["faqs"] = faqs
    org.settings = new_settings
    if payload.get("onboarding_step"):
        if payload["onboarding_step"] not in ONBOARDING_STEPS:
            raise ValidationFailed("Invalid onboarding step")
        org.onboarding_step = payload["onboarding_step"]
    audit.record(
        db,
        principal,
        AuditAction.SETTINGS_UPDATED,
        resource="organization",
        resource_id=org.id,
        metadata={"fields": sorted(payload.keys())},
    )
    db.commit()
    return org


def upload_logo(db: Session, principal: Principal, content: bytes, mime: str) -> Organization:
    principal.require(Perm.SETTINGS_MANAGE)
    if mime not in ("image/png", "image/jpeg") or len(content) > 2 * 1024 * 1024:
        raise ValidationFailed("Logo must be a PNG or JPEG under 2 MB")
    from app.services.documents import sniff_mime

    if sniff_mime(content) != mime:
        raise ValidationFailed("File content does not match its type")
    org = get_org(db, principal)
    key = new_storage_key(org.id, "branding")
    get_storage().put(key, content, mime)
    org.logo_storage_key = key
    db.commit()
    return org


# --- WhatsApp account --------------------------------------------------------------


def get_whatsapp_account(db: Session, org_id: Any) -> WhatsAppAccount | None:
    return (
        db.execute(select(WhatsAppAccount).where(WhatsAppAccount.organization_id == org_id).order_by(WhatsAppAccount.created_at))
        .scalars()
        .first()
    )


def whatsapp_account_out(acc: WhatsAppAccount | None) -> WhatsAppAccountOut:
    from app.core.security import decrypt_secret

    token = decrypt_secret(acc.access_token_encrypted) if acc else ""
    return WhatsAppAccountOut(
        id=acc.id if acc else None,
        provider=acc.provider if acc else settings.WHATSAPP_PROVIDER,
        display_phone_number=acc.display_phone_number if acc else None,
        phone_number_id=acc.phone_number_id if acc else None,
        business_account_id=acc.business_account_id if acc else None,
        api_version=(acc.api_version if acc else None) or settings.WHATSAPP_API_VERSION,
        status=acc.status if acc else WhatsAppAccountStatus.INACTIVE,
        access_token_set=bool(token),
        access_token_hint=mask_secret(token),
        app_secret_set=bool(acc and acc.app_secret_encrypted),
        last_error=acc.last_error if acc else None,
        last_verified_at=acc.last_verified_at if acc else None,
        webhook_url=f"{settings.PUBLIC_API_URL}/api/v1/webhooks/whatsapp",
        verify_token_configured=bool(settings.WHATSAPP_VERIFY_TOKEN),
    )


def upsert_whatsapp_account(db: Session, principal: Principal, data: WhatsAppAccountUpdate) -> WhatsAppAccount:
    principal.require(Perm.WHATSAPP_MANAGE)
    clash = db.execute(select(WhatsAppAccount).where(WhatsAppAccount.phone_number_id == data.phone_number_id)).scalar_one_or_none()
    if clash and clash.organization_id != principal.org_id:
        raise Conflict("This phone number ID is already connected to another organization")
    acc = get_whatsapp_account(db, principal.org_id)
    if acc is None:
        acc = WhatsAppAccount(organization_id=principal.org_id, phone_number_id=data.phone_number_id)
        db.add(acc)
    acc.provider = data.provider
    acc.phone_number_id = data.phone_number_id
    acc.display_phone_number = data.display_phone_number
    acc.business_account_id = data.business_account_id
    acc.api_version = data.api_version
    if data.access_token:
        acc.access_token_encrypted = encrypt_secret(data.access_token)
    if data.app_secret:
        acc.app_secret_encrypted = encrypt_secret(data.app_secret)
    if data.provider == "meta" and not (acc.access_token_encrypted or settings.WHATSAPP_ACCESS_TOKEN):
        acc.status = WhatsAppAccountStatus.INACTIVE
        acc.last_error = "Access token not configured"
    else:
        acc.status = WhatsAppAccountStatus.ACTIVE
        acc.last_error = None
    org = get_org(db, principal)
    if org.onboarding_step == "WHATSAPP_SETUP":
        org.onboarding_step = "INVITE_EMPLOYEES"
    audit.record(
        db,
        principal,
        AuditAction.WHATSAPP_CONFIGURED,
        resource="whatsapp_account",
        metadata={"provider": data.provider, "token_updated": bool(data.access_token)},
    )
    db.commit()
    return acc


def verify_whatsapp_account(db: Session, principal: Principal) -> WhatsAppAccount:
    principal.require(Perm.WHATSAPP_MANAGE)
    from app.integrations.whatsapp import get_whatsapp_provider

    acc = get_whatsapp_account(db, principal.org_id)
    if acc is None:
        raise NotFound("WhatsApp is not configured")
    try:
        ok = get_whatsapp_provider(acc).healthcheck()
    except Exception as e:  # provider construction errors (missing token)
        ok = False
        acc.last_error = str(e)[:300]
    acc.status = WhatsAppAccountStatus.ACTIVE if ok else WhatsAppAccountStatus.ERROR
    if ok:
        acc.last_verified_at = now_utc()
        acc.last_error = None
    elif not acc.last_error:
        acc.last_error = "Could not reach WhatsApp Cloud API with these credentials (token expired or invalid?)"
    db.commit()
    return acc


# --- Templates -----------------------------------------------------------------------


def list_templates(db: Session, principal: Principal) -> list[MessageTemplate]:
    principal.require(Perm.WHATSAPP_VIEW)
    from app.services.templates import ensure_default_templates

    ensure_default_templates(db, principal.org_id)
    db.commit()
    return list(
        db.execute(
            select(MessageTemplate).where(MessageTemplate.organization_id == principal.org_id).order_by(MessageTemplate.key)
        ).scalars()
    )


def update_template(db: Session, principal: Principal, template_id: Any, data: TemplateUpdate) -> MessageTemplate:
    principal.require(Perm.WHATSAPP_MANAGE)
    t = db.execute(
        select(MessageTemplate).where(MessageTemplate.organization_id == principal.org_id, MessageTemplate.id == template_id)
    ).scalar_one_or_none()
    if t is None:
        raise NotFound("Template not found")
    if data.name is not None:
        t.name = data.name
    if data.language is not None:
        t.language = data.language
    if data.body_preview is not None:
        t.body_preview = data.body_preview
    if data.status is not None:
        if data.status not in TemplateStatus.__members__:
            raise ValidationFailed("Invalid template status")
        t.status = data.status
        if data.status == TemplateStatus.APPROVED:
            t.last_error = None
    audit.record(
        db,
        principal,
        AuditAction.SETTINGS_UPDATED,
        resource="message_template",
        resource_id=t.id,
        metadata={"status": t.status, "name": t.name},
    )
    db.commit()
    return t


def sync_templates_from_meta(db: Session, principal: Principal) -> list[MessageTemplate]:
    """Pull real approval status from Meta for configured template names."""
    principal.require(Perm.WHATSAPP_MANAGE)
    import httpx

    from app.core.security import decrypt_secret

    acc = get_whatsapp_account(db, principal.org_id)
    if acc is None or acc.provider != "meta" or not acc.business_account_id:
        raise ValidationFailed("Template sync requires a Meta WhatsApp account with a Business Account ID")
    token = decrypt_secret(acc.access_token_encrypted) or settings.WHATSAPP_ACCESS_TOKEN
    version = acc.api_version or settings.WHATSAPP_API_VERSION
    resp = httpx.get(
        f"https://graph.facebook.com/{version}/{acc.business_account_id}/message_templates",
        params={"limit": 200, "fields": "name,status,language,category"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    if resp.status_code >= 300:
        acc.last_error = f"Template sync failed (HTTP {resp.status_code})"
        db.commit()
        raise ValidationFailed(acc.last_error)
    remote = {(t["name"], t.get("language")): t for t in resp.json().get("data", [])}
    status_map = {"APPROVED": "APPROVED", "REJECTED": "REJECTED", "PENDING": "PENDING", "PAUSED": "PAUSED", "DISABLED": "DISABLED"}
    templates = list_templates(db, principal)
    for t in templates:
        r = remote.get((t.name, t.language))
        t.status = status_map.get(r["status"], "PENDING") if r else TemplateStatus.NOT_SUBMITTED
    db.commit()
    return templates
