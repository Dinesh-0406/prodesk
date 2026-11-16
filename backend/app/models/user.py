from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Table, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPk

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", Uuid, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", Uuid, ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(UUIDPk, Base):
    __tablename__ = "permissions"
    code: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")


class Role(UUIDPk, Timestamps, Base):
    """System roles have organization_id NULL and are shared; custom roles are tenant-owned."""

    __tablename__ = "roles"
    __table_args__ = (UniqueConstraint("organization_id", "name"),)

    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(64))
    description: Mapped[str] = mapped_column(String(255), default="")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    permissions: Mapped[list[Permission]] = relationship(secondary=role_permissions, lazy="selectin")


class User(UUIDPk, Timestamps, Base):
    __tablename__ = "users"

    organization_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(20))
    role_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("roles.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    role: Mapped[Role] = relationship(lazy="joined")


class RefreshToken(UUIDPk, Timestamps, Base):
    __tablename__ = "refresh_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid, default=uuid.uuid4, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replaced_by_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    ip: Mapped[str | None] = mapped_column(String(64))
    user_agent: Mapped[str | None] = mapped_column(String(255))


class ActionToken(UUIDPk, Timestamps, Base):
    """Single-use tokens for password reset and account activation (stored hashed)."""

    __tablename__ = "action_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(32))
    token_hash: Mapped[str] = mapped_column(String(128), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
