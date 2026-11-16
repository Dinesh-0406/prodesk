"""Tenant-aware repository base.

Every query built here is filtered by ``organization_id``. Cross-tenant lookups return
``NotFound`` (never ``Forbidden``) so that the existence of another tenant's records is
not leaked.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.core.errors import NotFound

T = TypeVar("T")


class TenantRepository(Generic[T]):
    model: type[T]

    def __init__(self, db: Session, org_id: uuid.UUID) -> None:
        if org_id is None:
            raise ValueError("org_id is required for tenant repositories")
        self.db = db
        self.org_id = org_id

    def query(self) -> Select[Any]:
        return select(self.model).where(self.model.organization_id == self.org_id)  # type: ignore[attr-defined]

    def get(self, id_: uuid.UUID | str, *, for_update: bool = False) -> T:
        try:
            uid = id_ if isinstance(id_, uuid.UUID) else uuid.UUID(str(id_))
        except ValueError:
            raise NotFound(f"{self.model.__name__} not found") from None
        stmt = self.query().where(self.model.id == uid)  # type: ignore[attr-defined]
        if for_update:
            stmt = stmt.with_for_update(of=self.model)
        obj = self.db.execute(stmt).unique().scalar_one_or_none()
        if obj is None:
            raise NotFound(f"{self.model.__name__} not found")
        return obj  # type: ignore[no-any-return]

    def add(self, obj: T) -> T:
        if getattr(obj, "organization_id", None) is None:
            obj.organization_id = self.org_id  # type: ignore[attr-defined]
        elif obj.organization_id != self.org_id:  # type: ignore[attr-defined]
            raise ValueError("Refusing to add an object belonging to another organization")
        self.db.add(obj)
        return obj


def paginate(db: Session, stmt: Select[Any], page: int, page_size: int) -> tuple[Sequence[Any], int]:
    total = db.execute(select(func.count()).select_from(stmt.order_by(None).subquery())).scalar_one()
    rows = db.execute(stmt.limit(page_size).offset((page - 1) * page_size)).unique().scalars().all()
    return rows, int(total)


def repo_for(model: type[T]) -> type[TenantRepository[T]]:
    return type(f"{model.__name__}Repository", (TenantRepository,), {"model": model})  # type: ignore[return-value]
