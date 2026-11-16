"""Password hashing, JWTs, opaque tokens, HMAC signing and field encryption."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.errors import Unauthorized

_hasher = PasswordHasher()
JWT_ALG = "HS256"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        # Constant-ish time: still run a hash to blunt user enumeration via timing.
        _hasher.hash(password)
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def validate_password_strength(password: str) -> None:
    from app.core.errors import ValidationFailed

    if len(password) < 10:
        raise ValidationFailed("Password must be at least 10 characters")
    if password.isalpha() or password.isdigit():
        raise ValidationFailed("Password must contain letters and numbers or symbols")


def now_utc() -> datetime:
    return datetime.now(UTC)


def create_access_token(
    *, subject: str, typ: str, org_id: str | None, extra: dict[str, Any] | None = None, ttl: timedelta | None = None
) -> tuple[str, str, datetime]:
    jti = uuid.uuid4().hex
    exp = now_utc() + (ttl or timedelta(minutes=settings.ACCESS_TOKEN_TTL_MINUTES))
    claims: dict[str, Any] = {"sub": subject, "typ": typ, "org": org_id, "jti": jti, "iat": now_utc(), "exp": exp}
    if extra:
        claims.update(extra)
    return jwt.encode(claims, settings.SECRET_KEY, algorithm=JWT_ALG), jti, exp


def decode_token(token: str, *, expected_typ: str | None = None) -> dict[str, Any]:
    try:
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[JWT_ALG], options={"require": ["exp", "sub", "typ"]})
    except jwt.ExpiredSignatureError as e:
        raise Unauthorized("Token expired", code="TOKEN_EXPIRED") from e
    except jwt.PyJWTError as e:
        raise Unauthorized("Invalid token", code="INVALID_TOKEN") from e
    if expected_typ and claims.get("typ") != expected_typ:
        raise Unauthorized("Invalid token type", code="INVALID_TOKEN")
    return claims


def generate_opaque_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Deterministic keyed hash for storing opaque tokens (never store raw tokens)."""
    return hmac.new(settings.SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()


def generate_otp(length: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


def hmac_sha256_hex(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def constant_time_equals(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


# --- Signed short-lived URLs (local storage downloads) --------------------------------


def create_signed_download_token(*, version_id: str, org_id: str, disposition: str, ttl_seconds: int | None = None) -> str:
    exp = now_utc() + timedelta(seconds=ttl_seconds or settings.SIGNED_URL_TTL_SECONDS)
    claims = {"sub": version_id, "org": org_id, "typ": "file", "disp": disposition, "exp": exp, "jti": uuid.uuid4().hex}
    return jwt.encode(claims, settings.SECRET_KEY + ":file", algorithm=JWT_ALG)


def decode_signed_download_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.SECRET_KEY + ":file", algorithms=[JWT_ALG], options={"require": ["exp", "sub"]})
    except jwt.ExpiredSignatureError as e:
        raise Unauthorized("Download link expired", code="LINK_EXPIRED") from e
    except jwt.PyJWTError as e:
        raise Unauthorized("Invalid download link", code="INVALID_LINK") from e


# --- Encryption for per-tenant integration secrets ------------------------------------


def _fernet() -> Fernet:
    return Fernet(settings.fernet_key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(value: str | None) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode()).decode()
    except InvalidToken:
        return ""


def mask_secret(value: str | None) -> str | None:
    if not value:
        return None
    return "••••" + value[-4:] if len(value) > 8 else "••••"
