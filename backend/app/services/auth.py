"""Staff authentication: registration, login, refresh rotation, logout, reset, activation."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

import redis
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.context import Principal
from app.core.errors import Conflict, Unauthorized, ValidationFailed
from app.core.logging import get_logger
from app.core.permissions import RoleName
from app.core.redis import get_redis
from app.core.security import (
    create_access_token,
    generate_opaque_token,
    hash_password,
    hash_token,
    now_utc,
    validate_password_strength,
    verify_password,
)
from app.integrations.email import get_email_provider
from app.models import ActionToken, Organization, RefreshToken, User
from app.services import audit, rbac
from app.services.audit import AuditAction

log = get_logger(__name__)
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15


@dataclass
class IssuedTokens:
    access_token: str
    expires_at: datetime
    refresh_token: str


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s[:60] or "firm"


def unique_slug(db: Session, name: str) -> str:
    base = slugify(name)
    slug, n = base, 1
    while db.execute(select(Organization.id).where(Organization.slug == slug)).first():
        n += 1
        slug = f"{base}-{n}"
    return slug


def issue_tokens(
    db: Session, user: User, *, ip: str | None = None, user_agent: str | None = None, family_id: uuid.UUID | None = None
) -> IssuedTokens:
    access, _, exp = create_access_token(
        subject=str(user.id),
        typ="staff",
        org_id=str(user.organization_id) if user.organization_id else None,
        extra={"ver": user.token_version, "role": user.role.name},
    )
    raw_refresh = generate_opaque_token(48)
    rt = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(raw_refresh),
        family_id=family_id or uuid.uuid4(),
        expires_at=now_utc() + timedelta(days=settings.REFRESH_TOKEN_TTL_DAYS),
        ip=ip,
        user_agent=(user_agent or "")[:255],
    )
    db.add(rt)
    return IssuedTokens(access_token=access, expires_at=exp, refresh_token=raw_refresh)


def register_firm(
    db: Session, *, firm_name: str, admin_name: str, email: str, password: str, phone: str | None, ip: str | None
) -> tuple[Organization, User, IssuedTokens]:
    from app.services import templates

    validate_password_strength(password)
    email = email.lower().strip()
    if db.execute(select(User.id).where(User.email == email)).first():
        raise Conflict("An account with this email already exists", code="EMAIL_TAKEN")
    org = Organization(
        name=firm_name.strip(), slug=unique_slug(db, firm_name), email=email, phone=phone, onboarding_step="FIRM_PROFILE", settings={}
    )
    db.add(org)
    db.flush()
    admin = User(
        organization_id=org.id,
        email=email,
        password_hash=hash_password(password),
        full_name=admin_name.strip(),
        phone=phone,
        role_id=rbac.get_system_role(db, RoleName.FIRM_ADMIN).id,
        is_verified=False,
    )
    db.add(admin)
    db.flush()
    db.refresh(admin)
    templates.ensure_default_templates(db, org.id)
    p = Principal(kind="staff", organization_id=org.id, user_id=admin.id, ip=ip)
    audit.record(db, p, AuditAction.ORG_CREATED, resource="organization", resource_id=org.id)
    _send_action_email(
        db,
        admin,
        "VERIFY_EMAIL",
        "Verify your ProDesk email",
        "Welcome to ProDesk. Verify your email address:\n{link}",
        "/activate?verify=1&token=",
    )
    tokens = issue_tokens(db, admin, ip=ip)
    return org, admin, tokens


def login(db: Session, *, email: str, password: str, ip: str | None, user_agent: str | None) -> IssuedTokens:
    email = email.lower().strip()
    user = db.execute(select(User).where(User.email == email)).unique().scalar_one_or_none()
    now = now_utc()
    if user and user.locked_until and user.locked_until > now:
        raise Unauthorized("Account temporarily locked due to failed logins. Try again later.", code="ACCOUNT_LOCKED")
    if not user or not verify_password(password, user.password_hash) or not user.is_active:
        if user:
            user.failed_login_count += 1
            if user.failed_login_count >= MAX_FAILED_LOGINS:
                user.locked_until = now + timedelta(minutes=LOCKOUT_MINUTES)
                user.failed_login_count = 0
            audit.record(
                db,
                None,
                AuditAction.LOGIN_FAILED,
                resource="user",
                resource_id=user.id,
                organization_id=user.organization_id,
                user_id=user.id,
                ip=ip,
            )
            db.commit()
        raise Unauthorized("Invalid email or password", code="INVALID_CREDENTIALS")
    if user.organization_id:
        org = db.get(Organization, user.organization_id)
        if org is None or org.status != "ACTIVE":
            raise Unauthorized("Organization is not active", code="ORG_INACTIVE")
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = now
    tokens = issue_tokens(db, user, ip=ip, user_agent=user_agent)
    audit.record(
        db, None, AuditAction.LOGIN, resource="user", resource_id=user.id, organization_id=user.organization_id, user_id=user.id, ip=ip
    )
    db.commit()
    return tokens


def refresh(db: Session, *, raw_token: str, ip: str | None, user_agent: str | None) -> IssuedTokens:
    """Rotate refresh tokens. Reuse of a revoked token revokes the whole family (theft signal)."""
    rt = db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_token)).with_for_update()).scalar_one_or_none()
    now = now_utc()
    if rt is None:
        raise Unauthorized("Invalid refresh token", code="INVALID_TOKEN")
    if rt.revoked_at is not None:
        db.execute(
            update(RefreshToken).where(RefreshToken.family_id == rt.family_id, RefreshToken.revoked_at.is_(None)).values(revoked_at=now)
        )
        audit.record(db, None, AuditAction.REFRESH_TOKEN_REUSE, resource="user", resource_id=rt.user_id, user_id=rt.user_id, ip=ip)
        db.commit()
        raise Unauthorized("Refresh token reuse detected; please log in again", code="TOKEN_REUSED")
    if rt.expires_at < now:
        raise Unauthorized("Refresh token expired", code="TOKEN_EXPIRED")
    user = db.get(User, rt.user_id)
    if user is None or not user.is_active:
        raise Unauthorized("Invalid refresh token", code="INVALID_TOKEN")
    tokens = issue_tokens(db, user, ip=ip, user_agent=user_agent, family_id=rt.family_id)
    rt.revoked_at = now
    db.flush()
    new_rt = db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_token(tokens.refresh_token))).scalar_one()
    rt.replaced_by_id = new_rt.id
    db.commit()
    return tokens


def denylist_access_token(jti: str, exp: int | float) -> None:
    ttl = max(1, int(exp - now_utc().timestamp()))
    try:
        get_redis().setex(f"jti_deny:{jti}", ttl, "1")
    except redis.RedisError:
        log.warning("token_denylist_unavailable")


def is_access_token_denied(jti: str | None) -> bool:
    if not jti:
        return False
    try:
        return bool(get_redis().exists(f"jti_deny:{jti}"))
    except redis.RedisError:
        return False


def logout(db: Session, principal: Principal, *, raw_refresh: str | None, jti: str | None, exp: float | None) -> None:
    if raw_refresh:
        rt = db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw_refresh))).scalar_one_or_none()
        if rt and rt.user_id == principal.user_id and rt.revoked_at is None:
            rt.revoked_at = now_utc()
    if jti and exp:
        denylist_access_token(jti, exp)
    audit.record(db, principal, AuditAction.LOGOUT, resource="user", resource_id=principal.user_id)
    db.commit()


def _send_action_email(db: Session, user: User, purpose: str, subject: str, template: str, path: str) -> None:
    raw = generate_opaque_token(32)
    ttl = (
        timedelta(minutes=settings.PASSWORD_RESET_TTL_MINUTES)
        if purpose == "PASSWORD_RESET"
        else timedelta(hours=settings.ACTIVATION_TTL_HOURS)
    )
    db.execute(
        update(ActionToken)
        .where(ActionToken.user_id == user.id, ActionToken.purpose == purpose, ActionToken.used_at.is_(None))
        .values(used_at=now_utc())
    )
    db.add(ActionToken(user_id=user.id, purpose=purpose, token_hash=hash_token(raw), expires_at=now_utc() + ttl))
    link = f"{settings.FRONTEND_URL}{path}{raw}"
    get_email_provider().send(user.email, subject, template.format(link=link, name=user.full_name))


def request_password_reset(db: Session, *, email: str, ip: str | None) -> None:
    """Always succeeds from the caller's perspective (no account enumeration)."""
    user = db.execute(select(User).where(User.email == email.lower().strip())).unique().scalar_one_or_none()
    if user and user.is_active and user.password_hash:
        _send_action_email(
            db,
            user,
            "PASSWORD_RESET",
            "Reset your ProDesk password",
            "Hello {name},\nReset your password (valid 30 minutes):\n{link}\nIf you didn't request this, ignore this email.",
            "/reset-password?token=",
        )
        audit.record(
            db,
            None,
            AuditAction.PASSWORD_RESET_REQUESTED,
            resource="user",
            resource_id=user.id,
            organization_id=user.organization_id,
            user_id=user.id,
            ip=ip,
        )
    db.commit()


def _consume_action_token(db: Session, raw: str, purposes: tuple[str, ...]) -> tuple[User, ActionToken]:
    at = db.execute(select(ActionToken).where(ActionToken.token_hash == hash_token(raw)).with_for_update()).scalar_one_or_none()
    if at is None or at.purpose not in purposes or at.used_at is not None or at.expires_at < now_utc():
        raise ValidationFailed("This link is invalid or has expired", code="INVALID_ACTION_TOKEN")
    user = db.get(User, at.user_id)
    if user is None:
        raise ValidationFailed("This link is invalid or has expired", code="INVALID_ACTION_TOKEN")
    at.used_at = now_utc()
    return user, at


def _revoke_all_sessions(db: Session, user: User) -> None:
    user.token_version += 1
    db.execute(update(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)).values(revoked_at=now_utc()))


def reset_password(db: Session, *, token: str, new_password: str, ip: str | None) -> None:
    validate_password_strength(new_password)
    user, _ = _consume_action_token(db, token, ("PASSWORD_RESET",))
    user.password_hash = hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    _revoke_all_sessions(db, user)
    audit.record(
        db,
        None,
        AuditAction.PASSWORD_RESET,
        resource="user",
        resource_id=user.id,
        organization_id=user.organization_id,
        user_id=user.id,
        ip=ip,
    )
    db.commit()


def activate_account(db: Session, *, token: str, password: str | None, ip: str | None) -> None:
    user, at = _consume_action_token(db, token, ("ACTIVATION", "VERIFY_EMAIL"))
    if at.purpose == "ACTIVATION":
        if not password:
            raise ValidationFailed("Password is required to activate your account")
        validate_password_strength(password)
        user.password_hash = hash_password(password)
        user.is_active = True
    user.is_verified = True
    audit.record(
        db,
        None,
        AuditAction.ACCOUNT_ACTIVATED,
        resource="user",
        resource_id=user.id,
        organization_id=user.organization_id,
        user_id=user.id,
        ip=ip,
    )
    db.commit()


def change_password(db: Session, principal: Principal, *, current: str, new: str) -> None:
    user = db.get(User, principal.user_id)
    if user is None or not verify_password(current, user.password_hash):
        raise Unauthorized("Current password is incorrect", code="INVALID_CREDENTIALS")
    validate_password_strength(new)
    user.password_hash = hash_password(new)
    _revoke_all_sessions(db, user)
    audit.record(db, principal, AuditAction.PASSWORD_RESET, resource="user", resource_id=user.id, metadata={"via": "change"})
    db.commit()


def send_activation(db: Session, user: User) -> None:
    _send_action_email(
        db,
        user,
        "ACTIVATION",
        "You're invited to ProDesk",
        "Hello {name},\nYou've been invited to ProDesk. Set your password to activate your account:\n{link}",
        "/activate?token=",
    )
