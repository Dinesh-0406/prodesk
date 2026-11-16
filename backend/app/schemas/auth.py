from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORM


class RegisterFirmRequest(BaseModel):
    firm_name: str = Field(min_length=2, max_length=200)
    admin_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    phone: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    refresh_token: str | None = None


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    new_password: str = Field(min_length=10, max_length=128)


class ActivateAccountRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=10, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=10, max_length=128)


class MeResponse(ORM):
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None
    organization_id: uuid.UUID | None
    organization_name: str | None = None
    organization_slug: str | None = None
    role: str
    permissions: list[str]
    is_verified: bool


class OtpRequest(BaseModel):
    org_slug: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=10, max_length=20)


class OtpRequestResponse(BaseModel):
    ok: bool = True
    message: str
    dev_otp: str | None = None  # only in development with mock WhatsApp


class OtpVerify(BaseModel):
    org_slug: str = Field(min_length=2, max_length=80)
    phone: str = Field(min_length=10, max_length=20)
    code: str = Field(min_length=4, max_length=8, pattern=r"^\d+$")


class ClientSessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    client_id: uuid.UUID
    client_name: str
    organization_name: str


class VerifyEmailRequest(BaseModel):
    token: str = Field(min_length=10, max_length=200)
