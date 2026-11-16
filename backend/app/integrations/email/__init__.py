"""Email provider abstraction: console (development) and SMTP (production)."""

from __future__ import annotations

import smtplib
import threading
from abc import ABC, abstractmethod
from email.message import EmailMessage
from functools import lru_cache

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger("email")


class EmailProvider(ABC):
    @abstractmethod
    def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailProvider(EmailProvider):
    """Development only: keeps an in-memory outbox (used by tests) and logs the subject."""

    def __init__(self) -> None:
        self.outbox: list[dict[str, str]] = []
        self._lock = threading.Lock()

    def send(self, to: str, subject: str, body: str) -> None:
        with self._lock:
            self.outbox.append({"to": to, "subject": subject, "body": body})
            del self.outbox[:-200]
        log.info("email_sent_console", extra={"subject": subject})
        if settings.APP_ENV == "development":
            # Dev convenience so reset/activation links can be followed locally.
            print(f"\n--- DEV EMAIL to {to} ---\n{subject}\n\n{body}\n--- END ---\n", flush=True)


class SmtpEmailProvider(EmailProvider):
    def send(self, to: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["From"] = settings.SMTP_FROM
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as s:
            if settings.SMTP_USE_TLS:
                s.starttls()
            if settings.SMTP_USERNAME:
                s.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            s.send_message(msg)


@lru_cache
def get_email_provider() -> EmailProvider:
    return SmtpEmailProvider() if settings.EMAIL_PROVIDER == "smtp" else ConsoleEmailProvider()
