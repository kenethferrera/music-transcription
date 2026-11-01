"""
Storage Service Factory
"""
import os
from backend.app.storage.storage_service import StorageService
from backend.app.storage.r2_storage import CloudflareR2Storage
from backend.app.storage.local_storage import LocalStorage

_storage_instance = None


def get_storage_service(force_local: bool = False) -> StorageService:
    global _storage_instance
    if _storage_instance is not None and not force_local:
        return _storage_instance

    storage_provider = os.getenv("STORAGE_PROVIDER", "r2").lower()
    has_r2_keys = bool(
        os.getenv("R2_ACCOUNT_ID")
        and os.getenv("R2_ACCESS_KEY_ID")
        and os.getenv("R2_SECRET_ACCESS_KEY")
        and os.getenv("R2_BUCKET_NAME")
    )

    if storage_provider == "r2" and has_r2_keys and not force_local:
        _storage_instance = CloudflareR2Storage()
    else:
        local_dir = os.getenv("LOCAL_STORAGE_DIR", "storage_data")
        _storage_instance = LocalStorage(base_directory=local_dir)

    return _storage_instance


__all__ = [
    "StorageService",
    "CloudflareR2Storage",
    "LocalStorage",
    "get_storage_service",
]

