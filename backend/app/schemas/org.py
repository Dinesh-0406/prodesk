from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORM


class OrganizationOut(ORM):
    id: uuid.UUID
    name: str
    slug: str
    email: str | None
    phone: str | None
    address: str | None
    timezone: str
    status: str
    onboarding_step: str
    has_logo: bool = False
    created_at: datetime


class OrganizationSettingsOut(OrganizationOut):
    settings: dict[str, Any]


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    email: EmailStr | None = None
    phone: str | None = None
    address: str | None = Field(default=None, max_length=1000)
    timezone: str | None = None
    working_hours: dict[str, Any] | None = None
    notifications: dict[str, Any] | None = None
    reminders: dict[str, Any] | None = None
    invoice: dict[str, Any] | None = None
    privacy: dict[str, Any] | None = None
    faqs: list[dict[str, Any]] | None = None
    onboarding_step: str | None = None


class UserOut(ORM):
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    role_name: str
    is_active: bool
    is_verified: bool
    last_login_at: datetime | None
    created_at: datetime


class InviteUserRequest(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    phone: str | None = None
    role: str = "EMPLOYEE"


class UpdateUserRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: str | None = None
    role: str | None = None
    is_active: bool | None = None


class WhatsAppAccountOut(BaseModel):
    id: uuid.UUID | None
    provider: str
    display_phone_number: str | None
    phone_number_id: str | None
    business_account_id: str | None
    api_version: str | None
    status: str
    access_token_set: bool
    access_token_hint: str | None
    app_secret_set: bool
    last_error: str | None
    last_verified_at: datetime | None
    webhook_url: str
    verify_token_configured: bool


class WhatsAppAccountUpdate(BaseModel):
    provider: str = Field(pattern="^(mock|meta)$")
    display_phone_number: str | None = None
    phone_number_id: str = Field(min_length=3, max_length=64)
    business_account_id: str | None = None
    api_version: str | None = Field(default=None, pattern=r"^v\d+\.\d+$")
    access_token: str | None = Field(default=None, max_length=1000)  # write-only
    app_secret: str | None = Field(default=None, max_length=200)  # write-only


class TemplateOut(ORM):
    id: uuid.UUID
    key: str
    name: str
    language: str
    category: str
    status: str
    body_preview: str
    variables: list[Any]
    has_url_button: bool
    last_error: str | None


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, pattern=r"^[a-z0-9_]{1,128}$")
    language: str | None = Field(default=None, max_length=10)
    status: str | None = None
    body_preview: str | None = Field(default=None, max_length=1024)
