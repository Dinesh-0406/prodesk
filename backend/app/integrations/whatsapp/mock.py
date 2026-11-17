"""In-process mock WhatsApp provider for local development and tests.

Behaves like the Cloud API: returns `wamid.*` ids and fails templates whose names start
with ``rejected_`` (to exercise graceful template-rejection handling). Simulated inbound
media is held in Redis so both API and worker processes can read it.
"""

from __future__ import annotations

import base64
import json
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.core.errors import NotFound
from app.core.logging import get_logger
from app.integrations.whatsapp.base import (
    LIST_MAX_ROWS,
    ListSection,
    MediaDownload,
    SendResult,
    TemplateComponentParams,
    WAErrorCategory,
    WhatsAppProvider,
)

log = get_logger("whatsapp.mock")


@dataclass
class MockOutbox:
    messages: list[dict[str, Any]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def record(self, item: dict[str, Any]) -> None:
        with self.lock:
            self.messages.append(item)
            del self.messages[:-500]

    def clear(self) -> None:
        with self.lock:
            self.messages.clear()


OUTBOX = MockOutbox()


def store_mock_media(content: bytes, mime_type: str, file_name: str | None) -> str:
    from app.core.redis import get_redis

    media_id = f"mockmedia_{uuid.uuid4().hex}"
    get_redis().setex(
        f"mock_media:{media_id}", 3600, json.dumps({"b64": base64.b64encode(content).decode(), "mime": mime_type, "name": file_name})
    )
    return media_id


class MockWhatsAppProvider(WhatsAppProvider):
    name = "mock"

    def __init__(self, phone_number_id: str = "mock-phone-number-id") -> None:
        self.phone_number_id = phone_number_id

    def _ok(self, kind: str, to: str, **data: Any) -> SendResult:
        mid = f"wamid.MOCK{uuid.uuid4().hex}"
        OUTBOX.record({"id": mid, "type": kind, "to": to, **data})
        log.info("mock_whatsapp_send", extra={"wa_type": kind, "provider_message_id": mid})
        return SendResult(ok=True, provider_message_id=mid, raw={"mock": True})

    def send_text(self, to: str, body: str, *, preview_url: bool = False) -> SendResult:
        return self._ok("text", to, body=body)

    def send_template(self, to: str, template_name: str, language: str, params: TemplateComponentParams) -> SendResult:
        if template_name.startswith("rejected_"):
            return SendResult(
                ok=False,
                error_code="132015",
                error_message="Template is paused or rejected",
                category=WAErrorCategory.TEMPLATE_NOT_APPROVED,
            )
        return self._ok(
            "template", to, template=template_name, language=language, body_params=params.body, url_suffix=params.url_button_suffix
        )

    def send_document(self, to: str, *, link: str, file_name: str, caption: str | None = None) -> SendResult:
        return self._ok("document", to, link=link, file_name=file_name, caption=caption)

    def send_image(self, to: str, *, link: str, caption: str | None = None) -> SendResult:
        return self._ok("image", to, link=link, caption=caption)

    def send_interactive_message(self, to: str, *, body: str, buttons: list[tuple[str, str]]) -> SendResult:
        return self._ok("interactive", to, body=body, buttons=buttons[:3])

    def send_interactive_list(self, to: str, *, body: str, button_text: str, sections: list[ListSection]) -> SendResult:
        rows = [{"id": r.id, "title": r.title[:24], "description": r.description} for sec in sections for r in sec.rows]
        return self._ok("interactive_list", to, body=body, button=button_text[:20], rows=rows[:LIST_MAX_ROWS])

    def mark_as_read(self, provider_message_id: str) -> SendResult:
        return SendResult(ok=True, raw={"mock": True})

    def download_media(self, media_id: str) -> MediaDownload:
        from app.core.redis import get_redis

        raw = get_redis().get(f"mock_media:{media_id}")
        if not raw:
            raise NotFound("Media not found")
        data = json.loads(raw)
        return MediaDownload(content=base64.b64decode(data["b64"]), mime_type=data["mime"], file_name=data.get("name"))
