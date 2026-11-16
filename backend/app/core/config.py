"""Application configuration loaded from environment variables.

All secrets come from the environment. Nothing secret is hardcoded here; defaults are
development-only placeholders and the app refuses to start in production with them.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET_PLACEHOLDER = "dev-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "ProDesk"
    APP_ENV: Literal["development", "test", "staging", "production"] = "development"
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True

    SECRET_KEY: str = DEV_SECRET_PLACEHOLDER
    ENCRYPTION_KEY: str = ""  # Fernet key; derived from SECRET_KEY in development if empty

    DATABASE_URL: str = "postgresql+psycopg://prodesk:prodesk@localhost:5432/prodesk"
    REDIS_URL: str = "redis://localhost:6379/0"

    CORS_ORIGINS: str = "http://localhost:5173"  # comma-separated
    FRONTEND_URL: str = "http://localhost:5173"
    PUBLIC_API_URL: str = "http://localhost:8000"

    ACCESS_TOKEN_TTL_MINUTES: int = 15
    REFRESH_TOKEN_TTL_DAYS: int = 14
    CLIENT_SESSION_TTL_MINUTES: int = 60
    SIGNED_URL_TTL_SECONDS: int = 300
    DELIVERY_LINK_TTL_HOURS: int = 72
    OTP_TTL_SECONDS: int = 300
    OTP_MAX_ATTEMPTS: int = 5
    PASSWORD_RESET_TTL_MINUTES: int = 30
    ACTIVATION_TTL_HOURS: int = 72
    REFRESH_COOKIE_SECURE: bool = False

    MAX_UPLOAD_MB: int = 25

    STORAGE_PROVIDER: Literal["local", "s3"] = "local"
    LOCAL_STORAGE_PATH: str = "./storage"
    S3_BUCKET: str = ""
    S3_REGION: str = "ap-south-1"
    S3_ENDPOINT_URL: str = ""
    S3_KMS_KEY_ID: str = ""

    WHATSAPP_PROVIDER: Literal["mock", "meta"] = "mock"
    WHATSAPP_ACCESS_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_BUSINESS_ACCOUNT_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_APP_SECRET: str = ""
    WHATSAPP_API_VERSION: str = "v21.0"
    WHATSAPP_SEND_RATE_PER_MINUTE: int = 60

    AI_PROVIDER: Literal["mock", "openai"] = "mock"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT_SECONDS: float = 20.0

    PAYMENT_PROVIDER: Literal["mock", "razorpay"] = "mock"
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""
    MOCK_PAYMENT_SECRET: str = "mock-payment-secret"

    EMAIL_PROVIDER: Literal["console", "smtp"] = "console"
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "ProDesk <no-reply@example.com>"
    SMTP_USE_TLS: bool = True

    CELERY_TASK_ALWAYS_EAGER: bool = False
    RATE_LIMIT_ENABLED: bool = True
    ENABLE_DEV_TOOLS: bool = True

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def _secret_default(cls, v: object) -> object:
        # An empty SECRET_KEY= line in .env falls back to the dev placeholder (refused in production).
        return v or DEV_SECRET_PLACEHOLDER

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_database_url(cls, v: object) -> object:
        if isinstance(v, str):
            if v.startswith("postgres://"):
                return "postgresql+psycopg://" + v[len("postgres://"):]
            elif v.startswith("postgresql://") and not v.startswith("postgresql+"):
                return "postgresql+psycopg://" + v[len("postgresql://"):]
        return v

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV in ("production", "staging")

    @property
    def fernet_key(self) -> bytes:
        if self.ENCRYPTION_KEY:
            return self.ENCRYPTION_KEY.encode()
        digest = hashlib.sha256(("fernet:" + self.SECRET_KEY).encode()).digest()
        return base64.urlsafe_b64encode(digest)

    @property
    def dev_tools_enabled(self) -> bool:
        return self.ENABLE_DEV_TOOLS and not self.is_production

    def validate_for_runtime(self) -> None:
        """Fail fast on unsafe production configuration."""
        if not self.is_production:
            return
        problems: list[str] = []
        if self.SECRET_KEY == DEV_SECRET_PLACEHOLDER or len(self.SECRET_KEY) < 32:
            problems.append("SECRET_KEY must be set to a strong random value (>=32 chars)")
        if not self.ENCRYPTION_KEY:
            problems.append("ENCRYPTION_KEY (Fernet key) must be set")
        if self.WHATSAPP_PROVIDER == "meta" and not (self.WHATSAPP_APP_SECRET and self.WHATSAPP_VERIFY_TOKEN):
            problems.append("WHATSAPP_APP_SECRET and WHATSAPP_VERIFY_TOKEN are required for meta provider")
        if self.PAYMENT_PROVIDER == "razorpay" and not (self.RAZORPAY_KEY_ID and self.RAZORPAY_KEY_SECRET):
            problems.append("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are required for razorpay provider")
        if self.STORAGE_PROVIDER == "s3" and not self.S3_BUCKET:
            problems.append("S3_BUCKET is required for s3 storage")
        if self.AI_PROVIDER == "openai" and not self.OPENAI_API_KEY:
            problems.append("OPENAI_API_KEY is required for openai provider")
        if problems:
            raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
