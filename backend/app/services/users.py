from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.errors import Conflict, NotFound, ValidationFailed
from app.core.permissions import Perm, RoleName
from app.core.phone import normalize_indian_phone
from app.models import Organization, User
from app.schemas.org import InviteUserRequest, UpdateUserRequest, UserOut
from app.services import audit, auth, rbac
from app.services.audit import AuditAction


def to_out(u: User) -> UserOut:
    return UserOut(
        id=u.id,
        email=u.email,
        full_name=u.full_name,
        phone=u.phone,
        role_name=u.role.name,
        is_active=u.is_active,
        is_verified=u.is_verified,
        last_login_at=u.last_login_at,
        created_at=u.created_at,
    )


def list_users(db: Session, principal: Principal, *, include_inactive: bool = True) -> list[User]:
    # Any staff with CLIENT_VIEW can see colleague names (needed for assignment pickers).
    principal.require(Perm.CLIENT_VIEW)
    stmt = select(User).where(User.organization_id == principal.org_id).order_by(User.full_name)
    if not include_inactive:
        stmt = stmt.where(User.is_active.is_(True))
    return list(db.execute(stmt).unique().scalars())


def get_user(db: Session, principal: Principal, user_id: uuid.UUID) -> User:
    u = db.execute(select(User).where(User.id == user_id, User.organization_id == principal.org_id)).unique().scalar_one_or_none()
    if u is None:
        raise NotFound("User not found")
    return u


def invite_user(db: Session, principal: Principal, data: InviteUserRequest) -> User:
    principal.require(Perm.USER_MANAGE)
    email = data.email.lower()
    if db.execute(select(User.id).where(User.email == email)).first():
        raise Conflict("A user with this email already exists", code="EMAIL_TAKEN")
    role = rbac.assignable_role(db, data.role)
    user = User(
        organization_id=principal.org_id,
        email=email,
        full_name=data.full_name,
        phone=normalize_indian_phone(data.phone) if data.phone else None,
        role_id=role.id,
        is_active=True,
        is_verified=False,
        password_hash=None,
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    auth.send_activation(db, user)
    org = db.get(Organization, principal.org_id)
    if org and org.onboarding_step == "INVITE_EMPLOYEES":
        org.onboarding_step = "ADD_CLIENTS"
    audit.record(db, principal, AuditAction.USER_INVITED, resource="user", resource_id=user.id, metadata={"role": role.name})
    db.commit()
    return user


def update_user(db: Session, principal: Principal, user_id: uuid.UUID, data: UpdateUserRequest) -> User:
    principal.require(Perm.USER_MANAGE)
    user = get_user(db, principal, user_id)
    if data.full_name is not None:
        user.full_name = data.full_name
    if data.phone is not None:
        user.phone = normalize_indian_phone(data.phone) if data.phone else None
    if data.role is not None and data.role != user.role.name:
        if user.id == principal.user_id:
            raise ValidationFailed("You cannot change your own role")
        if user.role.name == RoleName.FIRM_ADMIN and _admin_count(db, principal.org_id) <= 1:
            raise ValidationFailed("At least one firm admin is required")
        old = user.role.name
        user.role_id = rbac.assignable_role(db, data.role).id
        user.token_version += 1  # force re-login with new permissions
        audit.record(
            db,
            principal,
            AuditAction.USER_PERMISSION_CHANGED,
            resource="user",
            resource_id=user.id,
            metadata={"from": old, "to": data.role},
        )
    if data.is_active is not None and data.is_active != user.is_active:
        if user.id == principal.user_id:
            raise ValidationFailed("You cannot deactivate yourself")
        user.is_active = data.is_active
        user.token_version += 1
        audit.record(
            db,
            principal,
            AuditAction.USER_DEACTIVATED if not data.is_active else AuditAction.USER_PERMISSION_CHANGED,
            resource="user",
            resource_id=user.id,
            metadata={"is_active": data.is_active},
        )
    db.commit()
    db.refresh(user)
    return user


def _admin_count(db: Session, org_id: uuid.UUID) -> int:
    role = rbac.get_system_role(db, RoleName.FIRM_ADMIN)
    return len(db.execute(select(User.id).where(User.organization_id == org_id, User.role_id == role.id, User.is_active.is_(True))).all())
