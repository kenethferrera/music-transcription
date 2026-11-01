"""
Local Filesystem Storage Adapter for local development and offline unit testing.
"""
import mimetypes
import os
import shutil
from typing import Any, Dict, Optional

from backend.app.storage.storage_service import StorageService


class LocalStorage(StorageService):
    """Local storage adapter satisfying the StorageService interface."""

    def __init__(self, base_directory: str = "storage_data"):
        self.base_dir = os.path.abspath(base_directory)
        os.makedirs(self.base_dir, exist_ok=True)

    def _full_path(self, object_key: str) -> str:
        clean_key = object_key.replace("/", os.sep).lstrip(os.sep)
        return os.path.join(self.base_dir, clean_key)

    def generate_presigned_upload_url(
        self,
        object_key: str,
        content_type: str,
        expires_in_seconds: int = 900,
    ) -> str:
        # In local mode, return an upload endpoint URI
        return f"/api/storage/local-upload?key={object_key}"

    def generate_presigned_download_url(
        self,
        object_key: str,
        expires_in_seconds: int = 3600,
        filename: Optional[str] = None,
    ) -> str:
        fn_arg = f"&filename={filename}" if filename else ""
        return f"/api/storage/local-download?key={object_key}{fn_arg}"

    def upload_file(
        self,
        local_path: str,
        object_key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        dest_path = self._full_path(object_key)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copyfile(local_path, dest_path)
        return object_key

    def upload_bytes(
        self,
        data: bytes,
        object_key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        dest_path = self._full_path(object_key)
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            f.write(data)
        return object_key

    def download_file(self, object_key: str, local_path: str) -> str:
        src_path = self._full_path(object_key)
        if not os.path.exists(src_path):
            raise FileNotFoundError(f"Object {object_key} does not exist in local storage.")
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        shutil.copyfile(src_path, local_path)
        return local_path

    def download_bytes(self, object_key: str) -> bytes:
        src_path = self._full_path(object_key)
        if not os.path.exists(src_path):
            raise FileNotFoundError(f"Object {object_key} does not exist in local storage.")
        with open(src_path, "rb") as f:
            return f.read()

    def object_exists(self, object_key: str) -> bool:
        return os.path.exists(self._full_path(object_key))

    def get_object_metadata(self, object_key: str) -> Dict[str, Any]:
        path = self._full_path(object_key)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Object {object_key} does not exist in local storage.")
        stat = os.stat(path)
        content_type, _ = mimetypes.guess_type(path)
        return {
            "key": object_key,
            "size": stat.st_size,
            "content_type": content_type or "application/octet-stream",
            "last_modified": str(stat.st_mtime),
            "etag": f"local-{stat.st_mtime}",
            "metadata": {},
        }

    def delete_object(self, object_key: str) -> bool:
        path = self._full_path(object_key)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def delete_prefix(self, prefix: str) -> int:
        target_dir = self._full_path(prefix)
        deleted = 0
        if os.path.exists(target_dir):
            if os.path.isdir(target_dir):
                for root, _, files in os.walk(target_dir):
                    deleted += len(files)
                shutil.rmtree(target_dir)
            else:
                os.remove(target_dir)
                deleted = 1
        return deleted

    def check_health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "provider": "local_filesystem",
            "directory": self.base_dir,
            "connected": True,
        }

