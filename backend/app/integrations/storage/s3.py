from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from app.core.errors import NotFound
from app.core.logging import get_logger
from app.integrations.storage.base import StorageProvider, validate_key

log = get_logger(__name__)


def _safe_filename(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in "._- ")[:150] or "document"


class S3StorageProvider(StorageProvider):
    """AWS S3 storage. The bucket must block all public access; objects are encrypted with
    SSE-KMS (if a key is configured) or SSE-S3. Downloads use presigned GET URLs."""

    name = "s3"

    def __init__(self, bucket: str, region: str, endpoint_url: str | None = None, kms_key_id: str | None = None) -> None:
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.kms_key_id = kms_key_id or None
        self.client = boto3.client(
            "s3",
            region_name=region,
            endpoint_url=endpoint_url or None,
            config=Config(signature_version="s3v4", retries={"max_attempts": 3, "mode": "standard"}),
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        validate_key(key)
        extra: dict[str, Any] = {"ContentType": content_type}
        if self.kms_key_id:
            extra.update(ServerSideEncryption="aws:kms", SSEKMSKeyId=self.kms_key_id)
        else:
            extra["ServerSideEncryption"] = "AES256"
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, **extra)

    def get(self, key: str) -> bytes:
        validate_key(key)
        try:
            obj = self.client.get_object(Bucket=self.bucket, Key=key)
        except self.client.exceptions.NoSuchKey as e:
            raise NotFound("File not found") from e
        return obj["Body"].read()  # type: ignore[no-any-return]

    def stream(self, key: str, chunk_size: int = 64 * 1024) -> Iterator[bytes]:
        validate_key(key)
        obj = self.client.get_object(Bucket=self.bucket, Key=key)
        yield from obj["Body"].iter_chunks(chunk_size)

    def delete(self, key: str) -> None:
        validate_key(key)
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key: str) -> bool:
        validate_key(key)
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def signed_url(self, key: str, *, file_name: str, content_type: str, ttl_seconds: int, inline: bool) -> str | None:
        validate_key(key)
        disp = "inline" if inline else "attachment"
        return self.client.generate_presigned_url(  # type: ignore[no-any-return]
            "get_object",
            Params={
                "Bucket": self.bucket,
                "Key": key,
                "ResponseContentDisposition": f'{disp}; filename="{_safe_filename(file_name)}"',
                "ResponseContentType": content_type,
            },
            ExpiresIn=ttl_seconds,
        )

    def healthcheck(self) -> bool:
        try:
            self.client.head_bucket(Bucket=self.bucket)
            return True
        except Exception:
            log.warning("s3_healthcheck_failed")
            return False
