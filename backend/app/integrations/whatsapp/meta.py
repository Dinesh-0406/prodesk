"""Official Meta WhatsApp Cloud API provider (Graph API). No unofficial libraries."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.errors import ProviderError
from app.core.logging import get_logger
from app.integrations.whatsapp.base import (
    MediaDownload,
    SendResult,
    TemplateComponentParams,
    WAErrorCategory,
    WhatsAppProvider,
)

log = get_logger("whatsapp.meta")
GRAPH_BASE = "https://graph.facebook.com"
# Media URLs returned by Graph API are on Meta-owned hosts. Anything else is refused (SSRF guard).
ALLOWED_MEDIA_HOST_SUFFIXES = (".fbcdn.net", ".fbsbx.com", ".facebook.com", ".whatsapp.net")

# https://developers.facebook.com/docs/whatsapp/cloud-api/support/error-codes
_ERROR_MAP: dict[int, WAErrorCategory] = {
    0: WAErrorCategory.AUTH_EXPIRED,
    190: WAErrorCategory.AUTH_EXPIRED,
    10: WAErrorCategory.CONFIGURATION,
    200: WAErrorCategory.CONFIGURATION,
    4: WAErrorCategory.RATE_LIMITED,
    80007: WAErrorCategory.RATE_LIMITED,
    130429: WAErrorCategory.RATE_LIMITED,
    131056: WAErrorCategory.RATE_LIMITED,
    131047: WAErrorCategory.OUTSIDE_SERVICE_WINDOW,
    131026: WAErrorCategory.RECIPIENT_UNAVAILABLE,
    131051: WAErrorCategory.INVALID_PARAMS,
    131008: WAErrorCategory.INVALID_PARAMS,
    131009: WAErrorCategory.INVALID_PARAMS,
    100: WAErrorCategory.INVALID_PARAMS,
    132000: WAErrorCategory.TEMPLATE_INVALID,
    132001: WAErrorCategory.TEMPLATE_INVALID,
    132005: WAErrorCategory.TEMPLATE_INVALID,
    132007: WAErrorCategory.TEMPLATE_INVALID,
    132012: WAErrorCategory.TEMPLATE_INVALID,
    132015: WAErrorCategory.TEMPLATE_NOT_APPROVED,
    132016: WAErrorCategory.TEMPLATE_NOT_APPROVED,
    131031: WAErrorCategory.POLICY_BLOCKED,
    368: WAErrorCategory.POLICY_BLOCKED,
    131000: WAErrorCategory.TRANSIENT,
    131016: WAErrorCategory.TRANSIENT,
    1: WAErrorCategory.TRANSIENT,
    2: WAErrorCategory.TRANSIENT,
}


class MetaWhatsAppProvider(WhatsAppProvider):
    name = "meta"

    def __init__(self, *, access_token: str, phone_number_id: str, api_version: str, timeout: float = 15.0) -> None:
        if not access_token or not phone_number_id:
            raise ProviderError("WhatsApp is not configured for this organization", code="WHATSAPP_NOT_CONFIGURED")
        self.phone_number_id = phone_number_id
        self.api_version = api_version
        self._client = httpx.Client(
            base_url=f"{GRAPH_BASE}/{api_version}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=timeout,
        )

    # -- internals -------------------------------------------------------------------
    def _post_message(self, payload: dict[str, Any]) -> SendResult:
        body = {"messaging_product": "whatsapp", "recipient_type": "individual", **payload}
        try:
            resp = self._client.post(f"/{self.phone_number_id}/messages", json=body)
        except httpx.TimeoutException:
            return SendResult(ok=False, error_code="TIMEOUT", error_message="Meta API timeout", category=WAErrorCategory.TRANSIENT)
        except httpx.HTTPError as e:
            return SendResult(ok=False, error_code="NETWORK", error_message=str(e)[:300], category=WAErrorCategory.TRANSIENT)
        return self._parse(resp)

    @staticmethod
    def _parse(resp: httpx.Response) -> SendResult:
        try:
            data = resp.json()
        except ValueError:
            data = {}
        if resp.status_code < 300 and data.get("messages"):
            return SendResult(ok=True, provider_message_id=data["messages"][0]["id"], raw=data)
        if resp.status_code < 300 and data.get("success"):
            return SendResult(ok=True, raw=data)
        err = data.get("error", {}) if isinstance(data, dict) else {}
        code = int(err.get("code", 0) or 0)
        category = _ERROR_MAP.get(code)
        if category is None:
            category = WAErrorCategory.TRANSIENT if resp.status_code >= 500 else WAErrorCategory.UNKNOWN
        if resp.status_code == 429:
            category = WAErrorCategory.RATE_LIMITED
        message = (err.get("error_data", {}) or {}).get("details") or err.get("message") or f"HTTP {resp.status_code}"
        log.warning("whatsapp_api_error", extra={"wa_error_code": code, "http_status": resp.status_code, "category": str(category)})
        return SendResult(
            ok=False,
            error_code=str(code or resp.status_code),
            error_message=str(message)[:500],
            category=category,
            raw={"error": {"code": code, "type": err.get("type")}},
        )

    # -- API -------------------------------------------------------------------------
    def send_text(self, to: str, body: str, *, preview_url: bool = False) -> SendResult:
        return self._post_message({"to": to, "type": "text", "text": {"body": body[:4096], "preview_url": preview_url}})

    def send_template(self, to: str, template_name: str, language: str, params: TemplateComponentParams) -> SendResult:
        components: list[dict[str, Any]] = []
        if params.header_document_link:
            components.append({"type": "header", "parameters": [{"type": "document", "document": {"link": params.header_document_link}}]})
        if params.body:
            components.append({"type": "body", "parameters": [{"type": "text", "text": str(v)[:1024]} for v in params.body]})
        if params.url_button_suffix:
            components.append(
                {"type": "button", "sub_type": "url", "index": "0", "parameters": [{"type": "text", "text": params.url_button_suffix}]}
            )
        return self._post_message(
            {"to": to, "type": "template", "template": {"name": template_name, "language": {"code": language}, "components": components}}
        )

    def send_document(self, to: str, *, link: str, file_name: str, caption: str | None = None) -> SendResult:
        doc: dict[str, Any] = {"link": link, "filename": file_name}
        if caption:
            doc["caption"] = caption[:1024]
        return self._post_message({"to": to, "type": "document", "document": doc})

    def send_image(self, to: str, *, link: str, caption: str | None = None) -> SendResult:
        img: dict[str, Any] = {"link": link}
        if caption:
            img["caption"] = caption[:1024]
        return self._post_message({"to": to, "type": "image", "image": img})

    def send_interactive_message(self, to: str, *, body: str, buttons: list[tuple[str, str]]) -> SendResult:
        return self._post_message(
            {
                "to": to,
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": body[:1024]},
                    "action": {
                        "buttons": [{"type": "reply", "reply": {"id": bid[:256], "title": title[:20]}} for bid, title in buttons[:3]]
                    },
                },
            }
        )

    def mark_as_read(self, provider_message_id: str) -> SendResult:
        return self._post_message({"status": "read", "message_id": provider_message_id})

    def download_media(self, media_id: str) -> MediaDownload:
        meta = self._client.get(f"/{media_id}")
        if meta.status_code >= 300:
            raise ProviderError("Unable to fetch media metadata", code="WHATSAPP_MEDIA_ERROR")
        info = meta.json()
        url = info.get("url", "")
        host = urlparse(url).hostname or ""
        if urlparse(url).scheme != "https" or not host.endswith(ALLOWED_MEDIA_HOST_SUFFIXES):
            raise ProviderError("Refusing to fetch media from untrusted host", code="WHATSAPP_MEDIA_UNTRUSTED")
        resp = self._client.get(url, follow_redirects=False)
        if resp.status_code >= 300:
            raise ProviderError("Unable to download media", code="WHATSAPP_MEDIA_ERROR")
        return MediaDownload(content=resp.content, mime_type=info.get("mime_type", "application/octet-stream"))

    def healthcheck(self) -> bool:
        try:
            return self._client.get(f"/{self.phone_number_id}", params={"fields": "id"}).status_code < 300
        except httpx.HTTPError:
            return False
