"""Structured JSON logging with request/correlation IDs and secret redaction."""

from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
correlation_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("correlation_id", default=None)

SENSITIVE_KEY_RE = re.compile(r"(pass(word)?|secret|token|authorization|api[_-]?key|otp|signature|cookie)", re.I)
BEARER_RE = re.compile(r"(Bearer\s+)[A-Za-z0-9\-_.=]+", re.I)


def redact(value: Any, depth: int = 0) -> Any:
    """Recursively redact values whose keys look sensitive."""
    if depth > 6:
        return "…"
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if isinstance(k, str) and SENSITIVE_KEY_RE.search(k) else redact(v, depth + 1)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact(v, depth + 1) for v in value]
    if isinstance(value, str):
        return BEARER_RE.sub(r"\1[REDACTED]", value)
    return value


class JsonFormatter(logging.Formatter):
    RESERVED = set(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": BEARER_RE.sub(r"\1[REDACTED]", record.getMessage()),
        }
        if rid := request_id_var.get():
            payload["request_id"] = rid
        if cid := correlation_id_var.get():
            payload["correlation_id"] = cid
        extras = {k: v for k, v in record.__dict__.items() if k not in self.RESERVED}
        if extras:
            payload.update(redact(extras))
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class PlainFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        rid = request_id_var.get()
        base = super().format(record)
        return f"{base} [rid={rid}]" if rid else base


def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_logs else PlainFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    for noisy in ("httpx", "httpcore", "botocore", "urllib3"):
        logging.getLogger(noisy).setLevel("WARNING")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
