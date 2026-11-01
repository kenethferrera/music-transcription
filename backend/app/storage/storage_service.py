"""
Storage Service Abstraction
"""
from abc import ABC, abstractmethod
from typing import BinaryIO, Dict, Optional


class StorageService(ABC):
    @abstractmethod
    def generate_presigned_upload_url(
        self,
        object_key: str,
        content_type: str,
        expires_in_seconds: int = 900,
    ) -> str:
        """Generate short-lived presigned PUT URL for client upload."""
        pass

    @abstractmethod
    def generate_presigned_download_url(
        self,
        object_key: str,
        expires_in_seconds: int = 3600,
        filename: Optional[str] = None,
    ) -> str:
        """Generate short-lived presigned GET URL for authorized client download."""
        pass

    @abstractmethod
    def upload_file(
        self,
        local_path: str,
        object_key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Upload a local file to storage. Returns the object key."""
        pass

    @abstractmethod
    def upload_bytes(
        self,
        data: bytes,
        object_key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        """Upload raw bytes to storage. Returns the object key."""
        pass

    @abstractmethod
    def download_file(self, object_key: str, local_path: str) -> str:
        """Download an object to a local file path."""
        pass

    @abstractmethod
    def download_bytes(self, object_key: str) -> bytes:
        """Download an object as raw bytes."""
        pass

    @abstractmethod
    def object_exists(self, object_key: str) -> bool:
        """Verify whether an object exists in storage."""
        pass

    @abstractmethod
    def get_object_metadata(self, object_key: str) -> Dict[str, any]:
        """Retrieve object metadata (size, content_type, checksum, etc.)."""
        pass

    @abstractmethod
    def delete_object(self, object_key: str) -> bool:
        """Delete a single object."""
        pass

    @abstractmethod
    def delete_prefix(self, prefix: str) -> int:
        """Delete all objects with given prefix (e.g. for project cleanup)."""
        pass

    @abstractmethod
    def check_health(self) -> Dict[str, any]:
        """Health check for storage connectivity without exposing credentials."""
        pass

