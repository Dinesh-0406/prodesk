"""Role/permission catalogue synchronisation and lookups."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFound
from app.core.permissions import DEFAULT_ROLE_PERMISSIONS, PERMISSION_DESCRIPTIONS, Perm, RoleName
from app.models import Permission, Role, User


def sync_system_roles(db: Session) -> None:
    """Idempotently ensure the permission catalogue and system roles exist and match code."""
    existing = {p.code: p for p in db.execute(select(Permission)).scalars()}
    for perm in Perm:
        if perm.value not in existing:
            p = Permission(code=perm.value, description=PERMISSION_DESCRIPTIONS[perm])
            db.add(p)
            existing[perm.value] = p
    db.flush()
    roles = {r.name: r for r in db.execute(select(Role).where(Role.organization_id.is_(None))).scalars()}
    for role_name, perms in DEFAULT_ROLE_PERMISSIONS.items():
        role = roles.get(role_name.value)
        if role is None:
            role = Role(name=role_name.value, description=role_name.value.replace("_", " ").title(), is_system=True)
            db.add(role)
        role.permissions = [existing[p.value] for p in sorted(perms)]
    db.flush()


def get_system_role(db: Session, name: RoleName) -> Role:
    role = db.execute(select(Role).where(Role.organization_id.is_(None), Role.name == name.value)).scalar_one_or_none()
    if role is None:
        sync_system_roles(db)
        role = db.execute(select(Role).where(Role.organization_id.is_(None), Role.name == name.value)).scalar_one()
    return role


def assignable_role(db: Session, name: str) -> Role:
    if name in (RoleName.SUPER_ADMIN, RoleName.CLIENT):
        raise NotFound("Role not found")
    try:
        return get_system_role(db, RoleName(name))
    except ValueError:
        raise NotFound("Role not found") from None


def user_permissions(user: User) -> frozenset[str]:
    return frozenset(p.code for p in user.role.permissions)
