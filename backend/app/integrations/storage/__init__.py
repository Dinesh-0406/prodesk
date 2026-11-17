from functools import lru_cache

from app.core.config import settings
from app.integrations.storage.base import StorageProvider, new_storage_key


@lru_cache
def get_storage() -> StorageProvider:
    if settings.STORAGE_PROVIDER == "s3":
        from app.integrations.storage.s3 import S3StorageProvider

        return S3StorageProvider(settings.S3_BUCKET, settings.S3_REGION, settings.S3_ENDPOINT_URL, settings.S3_KMS_KEY_ID)
    from app.integrations.storage.local import LocalStorageProvider

    return LocalStorageProvider(settings.LOCAL_STORAGE_PATH)


__all__ = ["StorageProvider", "get_storage", "new_storage_key"]
