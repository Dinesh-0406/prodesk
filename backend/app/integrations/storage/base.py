from __future__ import annotations

import re
import uuid
from abc import ABC, abstractmethod
from collections.abc import Iterator

from app.core.errors import ValidationFailed

_KEY_RE = re.compile(r"^[a-f0-9\-]{36}/[a-z0-9_]{1,32}/[a-f0-9]{32}$")


def new_storage_key(org_id: uuid.UUID, namespace: str = "documents") -> str:
    """Randomised, tenant-prefixed key. Never derived from user-supplied file names."""
    return f"{org_id}/{namespace}/{uuid.uuid4().hex}"


def validate_key(key: str) -> str:
    if not _KEY_RE.match(key):
        raise ValidationFailed("Invalid storage key")
    return key


class StorageProvider(ABC):
    name: str

    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def stream(self, key: str, chunk_size: int = 64 * 1024) -> Iterator[bytes]: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def signed_url(self, key: str, *, file_name: str, content_type: str, ttl_seconds: int, inline: bool) -> str | None:
        """Return a provider-native short-lived URL, or None if the provider serves via the API."""

    def healthcheck(self) -> bool:
        return True
