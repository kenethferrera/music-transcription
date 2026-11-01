"""
Unit Tests for Storage Service Abstraction
"""
import os
import shutil
import tempfile
import pytest

from backend.app.storage.local_storage import LocalStorage


@pytest.fixture
def temp_storage():
    temp_dir = tempfile.mkdtemp(prefix="test_storage_")
    storage = LocalStorage(base_directory=temp_dir)
    yield storage
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_storage_upload_download_bytes(temp_storage):
    key = "test/song.txt"
    content = b"audio file payload test"

    temp_storage.upload_bytes(content, key, content_type="text/plain")
    assert temp_storage.object_exists(key)

    downloaded = temp_storage.download_bytes(key)
    assert downloaded == content

    meta = temp_storage.get_object_metadata(key)
    assert meta["size"] == len(content)


def test_storage_presigned_urls(temp_storage):
    upload_url = temp_storage.generate_presigned_upload_url("uploads/song.wav", "audio/wav")
    assert "uploads/song.wav" in upload_url

    download_url = temp_storage.generate_presigned_download_url("exports/out.mid", filename="multitrack.mid")
    assert "exports/out.mid" in download_url
    assert "filename=multitrack.mid" in download_url


def test_storage_delete_prefix(temp_storage):
    temp_storage.upload_bytes(b"data1", "proj1/stem1.wav")
    temp_storage.upload_bytes(b"data2", "proj1/stem2.wav")
    temp_storage.upload_bytes(b"data3", "proj2/stem1.wav")

    assert temp_storage.object_exists("proj1/stem1.wav")
    assert temp_storage.object_exists("proj2/stem1.wav")

    deleted = temp_storage.delete_prefix("proj1/")
    assert deleted == 2
    assert not temp_storage.object_exists("proj1/stem1.wav")
    assert temp_storage.object_exists("proj2/stem1.wav")

