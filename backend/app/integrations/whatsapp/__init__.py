from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import settings
from app.core.security import decrypt_secret
from app.integrations.whatsapp.base import (
    SendResult,
    TemplateComponentParams,
    WAErrorCategory,
    WhatsAppProvider,
    verify_meta_signature,
)

if TYPE_CHECKING:
    from app.models.whatsapp import WhatsAppAccount


def get_whatsapp_provider(account: WhatsAppAccount | None) -> WhatsAppProvider:
    """Resolve the provider for an organization's WhatsApp account.

    Per-account credentials (encrypted in DB) take precedence over the global environment
    defaults. Business logic never needs to know which provider is active.
    """
    provider = (account.provider if account else None) or settings.WHATSAPP_PROVIDER
    if provider == "meta":
        from app.integrations.whatsapp.meta import MetaWhatsAppProvider

        token = decrypt_secret(account.access_token_encrypted) if account else ""
        return MetaWhatsAppProvider(
            access_token=token or settings.WHATSAPP_ACCESS_TOKEN,
            phone_number_id=(account.phone_number_id if account else "") or settings.WHATSAPP_PHONE_NUMBER_ID,
            api_version=(account.api_version if account else None) or settings.WHATSAPP_API_VERSION,
        )
    from app.integrations.whatsapp.mock import MockWhatsAppProvider

    return MockWhatsAppProvider(account.phone_number_id if account else "mock-phone-number-id")


def app_secret_for(account: WhatsAppAccount | None) -> str:
    if account and account.app_secret_encrypted:
        return decrypt_secret(account.app_secret_encrypted)
    return settings.WHATSAPP_APP_SECRET


__all__ = [
    "SendResult",
    "TemplateComponentParams",
    "WAErrorCategory",
    "WhatsAppProvider",
    "app_secret_for",
    "get_whatsapp_provider",
    "verify_meta_signature",
]
