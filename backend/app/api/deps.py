"""Authentication dependencies: resolve the Principal from a bearer token."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.context import Principal, client_principal
from app.core.errors import Forbidden, Unauthorized
from app.core.permissions import Perm
from app.core.rate_limit import client_ip
from app.core.security import decode_token
from app.db.session import get_db
from app.models import Client, Organization, User
from app.models.enums import ClientStatus
from app.services.auth import is_access_token_denied
from app.services.rbac import user_permissions

bearer = HTTPBearer(auto_error=False)
DB = Annotated[Session, Depends(get_db)]


def _claims(creds: HTTPAuthorizationCredentials | None) -> dict:  # type: ignore[type-arg]
    if creds is None or creds.scheme.lower() != "bearer":
        raise Unauthorized("Authentication required", code="AUTH_REQUIRED")
    claims = decode_token(creds.credentials)
    if is_access_token_denied(claims.get("jti")):
        raise Unauthorized("Session has been logged out", code="TOKEN_REVOKED")
    return claims


def get_principal(request: Request, db: DB, creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
    claims = _claims(creds)
    ip = client_ip(request)
    typ = claims.get("typ")
    if typ == "staff":
        try:
            user = db.get(User, uuid.UUID(claims["sub"]))
        except ValueError:
            raise Unauthorized("Invalid token", code="INVALID_TOKEN") from None
        if user is None or not user.is_active or user.token_version != claims.get("ver"):
            raise Unauthorized("Session is no longer valid", code="INVALID_TOKEN")
        if user.organization_id:
            org = db.get(Organization, user.organization_id)
            if org is None or org.status != "ACTIVE":
                raise Unauthorized("Organization is not active", code="ORG_INACTIVE")
        p = Principal(
            kind="staff",
            organization_id=user.organization_id,
            user_id=user.id,
            role=user.role.name,
            permissions=user_permissions(user),
            ip=ip,
            token_jti=claims.get("jti"),
        )
    elif typ == "client":
        try:
            cid, oid = uuid.UUID(claims["sub"]), uuid.UUID(claims["org"])
        except (ValueError, TypeError, KeyError):
            raise Unauthorized("Invalid token", code="INVALID_TOKEN") from None
        client = db.get(Client, cid)
        if client is None or client.organization_id != oid or client.status == ClientStatus.ARCHIVED:
            raise Unauthorized("Session is no longer valid", code="INVALID_TOKEN")
        base = client_principal(oid, cid)
        p = Principal(
            kind="client",
            organization_id=oid,
            client_id=cid,
            role="CLIENT",
            permissions=base.permissions,
            ip=ip,
            token_jti=claims.get("jti"),
        )
    else:
        raise Unauthorized("Invalid token type", code="INVALID_TOKEN")
    request.state.token_exp = claims.get("exp")
    return p


CurrentPrincipal = Annotated[Principal, Depends(get_principal)]


def get_staff(p: CurrentPrincipal) -> Principal:
    if not p.is_staff or p.organization_id is None:
        raise Forbidden("Staff access required")
    return p


def get_client_principal(p: CurrentPrincipal) -> Principal:
    if not p.is_client:
        raise Forbidden("Client portal access required")
    return p


def get_super_admin(p: CurrentPrincipal) -> Principal:
    if not p.is_staff or not p.has(Perm.ORG_MANAGE):
        raise Forbidden("Platform administrator access required")
    return p


Staff = Annotated[Principal, Depends(get_staff)]
ClientUser = Annotated[Principal, Depends(get_client_principal)]
SuperAdmin = Annotated[Principal, Depends(get_super_admin)]
