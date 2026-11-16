from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, File, UploadFile
from sqlalchemy import select

from app.api.deps import DB, Staff, SuperAdmin
from app.models import Organization
from app.schemas.org import (
    InviteUserRequest,
    OrganizationOut,
    OrganizationSettingsOut,
    OrganizationUpdate,
    UpdateUserRequest,
    UserOut,
)
from app.services import orgs, users

router = APIRouter(tags=["organizations"])


def _org_out(org: Organization, with_settings: bool = False) -> OrganizationOut:
    base: dict[str, Any] = dict(
        id=org.id,
        name=org.name,
        slug=org.slug,
        email=org.email,
        phone=org.phone,
        address=org.address,
        timezone=org.timezone,
        status=org.status,
        onboarding_step=org.onboarding_step,
        has_logo=bool(org.logo_storage_key),
        created_at=org.created_at,
    )
    if with_settings:
        s = org.merged_settings()
        s["faqs"] = (org.settings or {}).get("faqs", [])
        return OrganizationSettingsOut(**base, settings=s)
    return OrganizationOut(**base)


@router.get("/organizations/current", response_model=OrganizationSettingsOut)
def current_org(principal: Staff, db: DB) -> OrganizationOut:
    return _org_out(orgs.get_org(db, principal), with_settings=True)


@router.patch("/organizations/current", response_model=OrganizationSettingsOut)
def update_current_org(body: OrganizationUpdate, principal: Staff, db: DB) -> OrganizationOut:
    return _org_out(orgs.update_org(db, principal, body), with_settings=True)


@router.post("/organizations/current/logo", response_model=OrganizationOut)
async def upload_logo(principal: Staff, db: DB, file: UploadFile = File(...)) -> OrganizationOut:
    content = await file.read(2 * 1024 * 1024 + 1)
    return _org_out(orgs.upload_logo(db, principal, content, file.content_type or ""))


@router.get("/organizations", response_model=list[OrganizationOut])
def list_orgs(_: SuperAdmin, db: DB) -> list[OrganizationOut]:
    """Platform administration (SUPER_ADMIN only): organisation directory, no tenant data."""
    return [_org_out(o) for o in db.execute(select(Organization).order_by(Organization.created_at.desc())).scalars()]


@router.post("/organizations/{org_id}/status", response_model=OrganizationOut)
def set_org_status(org_id: uuid.UUID, status: str, _: SuperAdmin, db: DB) -> OrganizationOut:
    from app.core.errors import NotFound, ValidationFailed

    org = db.get(Organization, org_id)
    if org is None:
        raise NotFound("Organization not found")
    if status not in ("ACTIVE", "SUSPENDED"):
        raise ValidationFailed("Invalid status")
    org.status = status
    db.commit()
    return _org_out(org)


@router.get("/users", response_model=list[UserOut])
def list_users(principal: Staff, db: DB) -> list[UserOut]:
    return [users.to_out(u) for u in users.list_users(db, principal)]


@router.post("/users", response_model=UserOut, status_code=201)
def invite_user(body: InviteUserRequest, principal: Staff, db: DB) -> UserOut:
    return users.to_out(users.invite_user(db, principal, body))


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: uuid.UUID, body: UpdateUserRequest, principal: Staff, db: DB) -> UserOut:
    return users.to_out(users.update_user(db, principal, user_id, body))


@router.get("/roles")
def list_roles(principal: Staff) -> list[dict[str, object]]:
    from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, RoleName

    return [
        {"name": r.value, "permissions": sorted(p.value for p in DEFAULT_ROLE_PERMISSIONS[r])}
        for r in RoleName
        if r not in (RoleName.SUPER_ADMIN, RoleName.CLIENT)
    ]
