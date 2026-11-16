"""WhatsApp provider interface (official Meta WhatsApp Cloud API semantics)."""

from __future__ import annotations

import hashlib
import hmac
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class WAErrorCategory(StrEnum):
    TEMPLATE_NOT_APPROVED = "TEMPLATE_NOT_APPROVED"
    TEMPLATE_INVALID = "TEMPLATE_INVALID"
    OUTSIDE_SERVICE_WINDOW = "OUTSIDE_SERVICE_WINDOW"
    RATE_LIMITED = "RATE_LIMITED"
    AUTH_EXPIRED = "AUTH_EXPIRED"
    INVALID_PARAMS = "INVALID_PARAMS"
    RECIPIENT_UNAVAILABLE = "RECIPIENT_UNAVAILABLE"
    CONFIGURATION = "CONFIGURATION"
    POLICY_BLOCKED = "POLICY_BLOCKED"
    TRANSIENT = "TRANSIENT"
    UNKNOWN = "UNKNOWN"


RETRYABLE = {WAErrorCategory.RATE_LIMITED, WAErrorCategory.TRANSIENT}


@dataclass
class SendResult:
    ok: bool
    provider_message_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    category: WAErrorCategory | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def retryable(self) -> bool:
        return self.category in RETRYABLE


@dataclass
class TemplateComponentParams:
    body: list[str] = field(default_factory=list)
    url_button_suffix: str | None = None  # dynamic part of a URL button
    header_document_link: str | None = None


@dataclass
class MediaDownload:
    content: bytes
    mime_type: str
    file_name: str | None = None


class WhatsAppProvider(ABC):
    name: str

    @abstractmethod
    def send_text(self, to: str, body: str, *, preview_url: bool = False) -> SendResult: ...

    @abstractmethod
    def send_template(self, to: str, template_name: str, language: str, params: TemplateComponentParams) -> SendResult: ...

    @abstractmethod
    def send_document(self, to: str, *, link: str, file_name: str, caption: str | None = None) -> SendResult: ...

    @abstractmethod
    def send_image(self, to: str, *, link: str, caption: str | None = None) -> SendResult: ...

    @abstractmethod
    def send_interactive_message(self, to: str, *, body: str, buttons: list[tuple[str, str]]) -> SendResult:
        """Reply buttons: list of (id, title), max 3 per Meta's rules."""

    @abstractmethod
    def mark_as_read(self, provider_message_id: str) -> SendResult: ...

    @abstractmethod
    def download_media(self, media_id: str) -> MediaDownload: ...

    def healthcheck(self) -> bool:
        return True


def verify_meta_signature(app_secret: str, body: bytes, header_value: str | None) -> bool:
    """Validate X-Hub-Signature-256 = 'sha256=' + HMAC_SHA256(app_secret, raw_body)."""
    if not app_secret or not header_value or not header_value.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header_value.removeprefix("sha256="))


def sign_meta_payload(app_secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
