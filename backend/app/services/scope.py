"""Data-scope rules: who can see which clients.

* Every query is limited to the principal's organization.
* Staff without CLIENT_VIEW_ALL only see clients assigned to them (and their related data).
* Client principals only see themselves.
"""

from __future__ import annotations

import uuid
from typing import Any, TypeVar

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.context import Principal
from app.core.errors import NotFound
from app.models import Client


def visible_client_ids_subquery(principal: Principal) -> Select[Any]:
    stmt = select(Client.id).where(Client.organization_id == principal.org_id)
    if principal.is_client:
        stmt = stmt.where(Client.id == principal.client_id)
    elif not principal.sees_all_clients:
        stmt = stmt.where(Client.assigned_employee_id == principal.user_id)
    return stmt


SelectT = TypeVar("SelectT", bound=Select[Any])


def scope_by_client(stmt: SelectT, model: Any, principal: Principal) -> SelectT:
    """Apply org + client-visibility scope to any model that has organization_id + client_id."""
    stmt = stmt.where(model.organization_id == principal.org_id)
    if principal.is_client:
        return stmt.where(model.client_id == principal.client_id)
    if not principal.sees_all_clients:
        return stmt.where(model.client_id.in_(visible_client_ids_subquery(principal)))
    return stmt


def get_visible_client(db: Session, principal: Principal, client_id: uuid.UUID | str) -> Client:
    try:
        cid = client_id if isinstance(client_id, uuid.UUID) else uuid.UUID(str(client_id))
    except ValueError:
        raise NotFound("Client not found") from None
    stmt = select(Client).where(Client.id == cid, Client.id.in_(visible_client_ids_subquery(principal)))
    client = db.execute(stmt).unique().scalar_one_or_none()
    if client is None:
        raise NotFound("Client not found")
    return client


def can_see_client(db: Session, principal: Principal, client_id: uuid.UUID) -> bool:
    try:
        get_visible_client(db, principal, client_id)
        return True
    except NotFound:
        return False
