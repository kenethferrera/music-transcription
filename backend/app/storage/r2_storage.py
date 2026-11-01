"""
Cloudflare R2 Storage Adapter using S3-compatible API.
"""
import logging
import os
from typing import Any, Dict, Optional
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError

from backend.app.storage.storage_service import StorageService

logger = logging.getLogger(__name__)


class CloudflareR2Storage(StorageService):
    """Production Cloudflare R2 implementation."""

    def __init__(
        self,
        account_id: Optional[str] = None,
        bucket_name: Optional[str] = None,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        region: str = "auto",
    ):
        self.account_id = account_id or os.getenv("R2_ACCOUNT_ID", "")
        self.bucket_name = bucket_name or os.getenv("R2_BUCKET_NAME", "")
        self.access_key_id = access_key_id or os.getenv("R2_ACCESS_KEY_ID", "")
        self.secret_access_key = secret_access_key or os.getenv("R2_SECRET_ACCESS_KEY", "")
        self.region = region or os.getenv("R2_REGION", "auto")

        if endpoint_url:
            self.endpoint_url = endpoint_url
        elif os.getenv("R2_ENDPOINT_URL"):
            self.endpoint_url = os.getenv("R2_ENDPOINT_URL")
        elif self.account_id:
            self.endpoint_url = f"https://{self.account_id}.r2.cloudflarestorage.com"
        else:
            self.endpoint_url = ""

        if not (self.bucket_name and self.access_key_id and self.secret_access_key and self.endpoint_url):
            logger.warning("Cloudflare R2 is not fully configured with credentials.")

        self._client = None

    def _get_client(self):
        if self._client is None:
            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name=self.region,
                config=Config(
                    signature_version="s3v4",
                    s3={"addressing_style": "path"},
                    retries={"max_attempts": 3, "mode": "standard"},
                ),
            )
        return self._client

    def generate_presigned_upload_url(
        self,
        object_key: str,
        content_type: str,
        expires_in_seconds: int = 900,
    ) -> str:
        client = self._get_client()
        return client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in_seconds,
            HttpMethod="PUT",
        )

    def generate_presigned_download_url(
        self,
        object_key: str,
        expires_in_seconds: int = 3600,
        filename: Optional[str] = None,
    ) -> str:
        client = self._get_client()
        params = {
            "Bucket": self.bucket_name,
            "Key": object_key,
        }
        if filename:
            params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'

        return client.generate_presigned_url(
            "get_object",
            Params=params,
            ExpiresIn=expires_in_seconds,
            HttpMethod="GET",
        )

    def upload_file(
        self,
        local_path: str,
        object_key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        client = self._get_client()
        extra_args: Dict[str, Any] = {}
        if content_type:
            extra_args["ContentType"] = content_type
        if metadata:
            extra_args["Metadata"] = metadata

        client.upload_file(
            Filename=local_path,
            Bucket=self.bucket_name,
            Key=object_key,
            ExtraArgs=extra_args or None,
        )
        return object_key

    def upload_bytes(
        self,
        data: bytes,
        object_key: str,
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None,
    ) -> str:
        client = self._get_client()
        params: Dict[str, Any] = {
            "Bucket": self.bucket_name,
            "Key": object_key,
            "Body": data,
        }
        if content_type:
            params["ContentType"] = content_type
        if metadata:
            params["Metadata"] = metadata

        client.put_object(**params)
        return object_key

    def download_file(self, object_key: str, local_path: str) -> str:
        os.makedirs(os.path.dirname(os.path.abspath(local_path)), exist_ok=True)
        client = self._get_client()
        client.download_file(self.bucket_name, object_key, local_path)
        return local_path

    def download_bytes(self, object_key: str) -> bytes:
        client = self._get_client()
        response = client.get_object(Bucket=self.bucket_name, Key=object_key)
        return response["Body"].read()

    def object_exists(self, object_key: str) -> bool:
        client = self._get_client()
        try:
            client.head_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            logger.error("Failed to check object existence for %s: %s", object_key, e)
            raise

    def get_object_metadata(self, object_key: str) -> Dict[str, Any]:
        client = self._get_client()
        response = client.head_object(Bucket=self.bucket_name, Key=object_key)
        return {
            "key": object_key,
            "size": response.get("ContentLength", 0),
            "content_type": response.get("ContentType", ""),
            "last_modified": str(response.get("LastModified", "")),
            "etag": response.get("ETag", "").strip('"'),
            "metadata": response.get("Metadata", {}),
        }

    def delete_object(self, object_key: str) -> bool:
        client = self._get_client()
        try:
            client.delete_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError as e:
            logger.error("Failed to delete object %s: %s", object_key, e)
            return False

    def delete_prefix(self, prefix: str) -> int:
        client = self._get_client()
        paginator = client.get_paginator("list_objects_v2")
        deleted_count = 0

        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=prefix):
            objects_to_delete = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
            if objects_to_delete:
                client.delete_objects(
                    Bucket=self.bucket_name,
                    Delete={"Objects": objects_to_delete},
                )
                deleted_count += len(objects_to_delete)

        return deleted_count

    def check_health(self) -> Dict[str, Any]:
        try:
            client = self._get_client()
            client.head_bucket(Bucket=self.bucket_name)
            return {
                "status": "healthy",
                "provider": "cloudflare_r2",
                "bucket": self.bucket_name,
                "connected": True,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "provider": "cloudflare_r2",
                "bucket": self.bucket_name,
                "connected": False,
                "error": str(e),
            }

