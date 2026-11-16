from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import DB, CurrentPrincipal
from app.core.config import settings
from app.core.errors import Unauthorized
from app.core.rate_limit import client_ip, limiter
from app.models import Organization, User
from app.schemas.auth import (
    ActivateAccountRequest,
    ChangePasswordRequest,
    LoginRequest,
    MeResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    RegisterFirmRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.schemas.common import OkResponse
from app.services import auth as auth_service
from app.services.auth import IssuedTokens
from app.services.rbac import user_permissions

router = APIRouter(prefix="/auth", tags=["auth"])
REFRESH_COOKIE = "prodesk_refresh"


def _set_refresh_cookie(resp: Response, token: str) -> None:
    secure = settings.REFRESH_COOKIE_SECURE or settings.is_production
    samesite = "none" if secure else "lax"
    resp.set_cookie(
        REFRESH_COOKIE,
        token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        max_age=settings.REFRESH_TOKEN_TTL_DAYS * 86400,
        path="/api/v1/auth",
    )


def _token_response(resp: Response, t: IssuedTokens) -> TokenResponse:
    _set_refresh_cookie(resp, t.refresh_token)
    return TokenResponse(access_token=t.access_token, expires_at=t.expires_at, refresh_token=t.refresh_token)


@router.post(
    "/register", response_model=TokenResponse, status_code=201, dependencies=[Depends(limiter("register", 5, 3600, fail_closed=True))]
)
def register(body: RegisterFirmRequest, request: Request, response: Response, db: DB) -> TokenResponse:
    """Firm onboarding: creates the Organization and its first FIRM_ADMIN."""
    _, _, tokens = auth_service.register_firm(
        db,
        firm_name=body.firm_name,
        admin_name=body.admin_name,
        email=body.email,
        password=body.password,
        phone=body.phone,
        ip=client_ip(request),
    )
    db.commit()
    return _token_response(response, tokens)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(limiter("login", 10, 60, fail_closed=True))])
def login(body: LoginRequest, request: Request, response: Response, db: DB) -> TokenResponse:
    tokens = auth_service.login(
        db, email=body.email, password=body.password, ip=client_ip(request), user_agent=request.headers.get("user-agent")
    )
    return _token_response(response, tokens)


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(limiter("refresh", 30, 60))])
def refresh(request: Request, response: Response, db: DB, body: RefreshRequest | None = None) -> TokenResponse:
    raw = (body.refresh_token if body else None) or request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise Unauthorized("Refresh token required", code="AUTH_REQUIRED")
    tokens = auth_service.refresh(db, raw_token=raw, ip=client_ip(request), user_agent=request.headers.get("user-agent"))
    return _token_response(response, tokens)


@router.post("/logout", response_model=OkResponse)
def logout(principal: CurrentPrincipal, request: Request, response: Response, db: DB, body: RefreshRequest | None = None) -> OkResponse:
    raw = (body.refresh_token if body else None) or request.cookies.get(REFRESH_COOKIE)
    if principal.is_staff:
        auth_service.logout(db, principal, raw_refresh=raw, jti=principal.token_jti, exp=getattr(request.state, "token_exp", None))
    else:
        auth_service.denylist_access_token(principal.token_jti or "", getattr(request.state, "token_exp", 0) or 0)
    secure = settings.REFRESH_COOKIE_SECURE or settings.is_production
    samesite = "none" if secure else "lax"
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth", secure=secure, samesite=samesite)
    return OkResponse(message="Logged out")


@router.get("/me", response_model=MeResponse)
def me(principal: CurrentPrincipal, db: DB) -> MeResponse:
    if not principal.is_staff:
        raise Unauthorized("Staff session required", code="INVALID_TOKEN")
    user = db.get(User, principal.user_id)
    assert user is not None
    org = db.get(Organization, user.organization_id) if user.organization_id else None
    return MeResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        phone=user.phone,
        organization_id=user.organization_id,
        organization_name=org.name if org else None,
        organization_slug=org.slug if org else None,
        role=user.role.name,
        permissions=sorted(user_permissions(user)),
        is_verified=user.is_verified,
    )


@router.post("/password-reset/request", response_model=OkResponse, dependencies=[Depends(limiter("pwreset", 5, 900, fail_closed=True))])
def password_reset_request(body: PasswordResetRequest, request: Request, db: DB) -> OkResponse:
    auth_service.request_password_reset(db, email=body.email, ip=client_ip(request))
    return OkResponse(message="If an account exists for this email, a reset link has been sent.")


@router.post(
    "/password-reset/confirm", response_model=OkResponse, dependencies=[Depends(limiter("pwreset_confirm", 10, 900, fail_closed=True))]
)
def password_reset_confirm(body: PasswordResetConfirm, request: Request, db: DB) -> OkResponse:
    auth_service.reset_password(db, token=body.token, new_password=body.new_password, ip=client_ip(request))
    return OkResponse(message="Password updated. Please log in.")


@router.post("/activate", response_model=OkResponse, dependencies=[Depends(limiter("activate", 10, 900))])
def activate(body: ActivateAccountRequest, request: Request, db: DB) -> OkResponse:
    auth_service.activate_account(db, token=body.token, password=body.password, ip=client_ip(request))
    return OkResponse(message="Account activated")


@router.post("/verify-email", response_model=OkResponse, dependencies=[Depends(limiter("activate", 10, 900))])
def verify_email(body: VerifyEmailRequest, request: Request, db: DB) -> OkResponse:
    auth_service.activate_account(db, token=body.token, password=None, ip=client_ip(request))
    return OkResponse(message="Email verified")


@router.post("/change-password", response_model=OkResponse)
def change_password(body: ChangePasswordRequest, principal: CurrentPrincipal, db: DB) -> OkResponse:
    auth_service.change_password(db, principal, current=body.current_password, new=body.new_password)
    return OkResponse(message="Password changed. Please log in again.")
