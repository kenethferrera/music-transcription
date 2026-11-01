"""
Cloudflare R2 Adapter Unit & Mocked Integration Tests
Verifies presigned PUT/GET URLs, S3 client configuration, headers, and error handling.
"""
from unittest.mock import MagicMock, patch
import pytest
from botocore.exceptions import ClientError

from backend.app.storage.r2_storage import CloudflareR2Storage


@pytest.fixture
def r2_storage():
    return CloudflareR2Storage(
        account_id="mock_acc_123",
        bucket_name="production-music-bucket",
        access_key_id="mock_access_key",
        secret_access_key="mock_secret_key",
        endpoint_url="https://mock_acc_123.r2.cloudflarestorage.com",
    )


def test_r2_endpoint_configuration(r2_storage):
    assert r2_storage.endpoint_url == "https://mock_acc_123.r2.cloudflarestorage.com"
    assert r2_storage.bucket_name == "production-music-bucket"


def test_r2_presigned_upload_url(r2_storage):
    with patch.object(r2_storage, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://mock_acc_123.r2.cloudflarestorage.com/production-music-bucket/uploads/test.wav?X-Amz-Signature=xyz"
        mock_get_client.return_value = mock_client

        url = r2_storage.generate_presigned_upload_url("uploads/test.wav", "audio/wav", expires_in_seconds=900)

        assert "X-Amz-Signature" in url
        mock_client.generate_presigned_url.assert_called_once_with(
            "put_object",
            Params={
                "Bucket": "production-music-bucket",
                "Key": "uploads/test.wav",
                "ContentType": "audio/wav",
            },
            ExpiresIn=900,
            HttpMethod="PUT",
        )


def test_r2_presigned_download_url(r2_storage):
    with patch.object(r2_storage, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.generate_presigned_url.return_value = "https://mock_acc_123.r2.cloudflarestorage.com/production-music-bucket/exports/score.pdf?X-Amz-Signature=abc"
        mock_get_client.return_value = mock_client

        url = r2_storage.generate_presigned_download_url("exports/score.pdf", filename="score.pdf")

        assert "score.pdf" in url
        mock_client.generate_presigned_url.assert_called_once_with(
            "get_object",
            Params={
                "Bucket": "production-music-bucket",
                "Key": "exports/score.pdf",
                "ResponseContentDisposition": 'attachment; filename="score.pdf"',
            },
            ExpiresIn=3600,
            HttpMethod="GET",
        )


def test_r2_object_exists(r2_storage):
    with patch.object(r2_storage, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client

        # Case 1: Object exists
        mock_client.head_object.return_value = {"ContentLength": 1024}
        assert r2_storage.object_exists("stems/proj/vocals.wav") is True

        # Case 2: Object does not exist
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "HeadObject"
        )
        assert r2_storage.object_exists("stems/proj/missing.wav") is False


def test_r2_health_check_healthy(r2_storage):
    with patch.object(r2_storage, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.head_bucket.return_value = {}
        mock_get_client.return_value = mock_client

        health = r2_storage.check_health()
        assert health["status"] == "healthy"
        assert health["provider"] == "cloudflare_r2"
        assert health["connected"] is True


def test_r2_health_check_unhealthy(r2_storage):
    with patch.object(r2_storage, "_get_client") as mock_get_client:
        mock_client = MagicMock()
        mock_client.head_bucket.side_effect = Exception("Connection refused / Bad credentials")
        mock_get_client.return_value = mock_client

        health = r2_storage.check_health()
        assert health["status"] == "unhealthy"
        assert health["connected"] is False
        assert "Bad credentials" in health["error"]

