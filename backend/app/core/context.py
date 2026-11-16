"""The authenticated principal and data-scope helpers used by every service."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal

from app.core.errors import Forbidden
from app.core.permissions import Perm


@dataclass(frozen=True)
class Principal:
    kind: Literal["staff", "client", "system"]
    organization_id: uuid.UUID | None
    user_id: uuid.UUID | None = None
    client_id: uuid.UUID | None = None
    role: str = ""
    permissions: frozenset[str] = field(default_factory=frozenset)
    ip: str | None = None
    token_jti: str | None = None

    def has(self, perm: Perm | str) -> bool:
        return str(perm) in self.permissions

    def require(self, *perms: Perm) -> None:
        missing = [p for p in perms if not self.has(p)]
        if missing:
            raise Forbidden("You do not have permission to perform this action", details={"missing": missing})

    @property
    def org_id(self) -> uuid.UUID:
        if self.organization_id is None:
            raise Forbidden("No organization context")
        return self.organization_id

    @property
    def is_staff(self) -> bool:
        return self.kind == "staff"

    @property
    def is_client(self) -> bool:
        return self.kind == "client"

    @property
    def sees_all_clients(self) -> bool:
        return self.kind == "system" or (self.is_staff and self.has(Perm.CLIENT_VIEW_ALL))

    @property
    def actor_type(self) -> str:
        return {"staff": "STAFF", "client": "CLIENT", "system": "SYSTEM"}[self.kind]


def system_principal(org_id: uuid.UUID | None) -> Principal:
    """Used by background workers. Has full scope within ONE organization only."""
    from app.core.permissions import ALL_STAFF

    return Principal(kind="system", organization_id=org_id, role="SYSTEM", permissions=frozenset(p.value for p in ALL_STAFF))


def client_principal(org_id: uuid.UUID, client_id: uuid.UUID) -> Principal:
    return Principal(
        kind="client", organization_id=org_id, client_id=client_id, role="CLIENT", permissions=frozenset({Perm.PORTAL_ACCESS.value})
    )
