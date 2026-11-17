from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from app.core.errors import NotFound, ValidationFailed
from app.integrations.storage.base import StorageProvider, validate_key


class LocalStorageProvider(StorageProvider):
    """Development storage on the local filesystem. Files are served only through the
    API's signed-token download endpoint, never as static files."""

    name = "local"

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        validate_key(key)
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise ValidationFailed("Invalid storage path")  # path traversal guard
        return p

    def put(self, key: str, data: bytes, content_type: str) -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            f.write(data)
        os.chmod(tmp, 0o600)
        tmp.replace(p)

    def get(self, key: str) -> bytes:
        p = self._path(key)
        if not p.exists():
            raise NotFound("File not found")
        return p.read_bytes()

    def stream(self, key: str, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
        p = self._path(key)
        if not p.exists():
            raise NotFound("File not found")
        with open(p, "rb") as f:
            while chunk := f.read(chunk_size):
                yield chunk

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            # Best-effort overwrite before unlink (secure-ish deletion on non-COW filesystems).
            size = p.stat().st_size
            with open(p, "r+b") as f:
                f.write(b"\0" * size)
            p.unlink()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def signed_url(self, key: str, *, file_name: str, content_type: str, ttl_seconds: int, inline: bool) -> str | None:
        return None

    def healthcheck(self) -> bool:
        return os.access(self.root, os.W_OK)
