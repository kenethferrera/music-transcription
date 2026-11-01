"""
Unit Tests for FastAPI API Functions
"""
import os
import shutil
import tempfile
import pytest

from backend.app.api.health import health_check
from backend.app.api.projects import (
    create_project,
    delete_project,
    get_project,
    list_projects,
)
from backend.app.main import root
from backend.app.models.project_store import ProjectStore, get_project_store
from backend.app.schemas.project import ProjectCreateRequest
from backend.app.storage import get_storage_service


@pytest.fixture(autouse=True)
def setup_test_env():
    temp_dir = tempfile.mkdtemp(prefix="api_test_")
    os.environ["STORAGE_PROVIDER"] = "local"
    os.environ["LOCAL_STORAGE_DIR"] = temp_dir
    os.environ["STT_PROVIDER"] = "mock"

    # Clean table for test
    from backend.app.models.database import SessionLocal, ProjectModel
    db = SessionLocal()
    db.query(ProjectModel).delete()
    db.commit()
    db.close()

    yield temp_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_root_and_health():
    res = root()
    assert "health" in res

    h_res = health_check()
    assert h_res["status"] == "healthy"
    assert "gpu" in h_res
    assert "storage" in h_res
    assert h_res["storage"]["connected"] is True


def test_project_crud():
    req = ProjectCreateRequest(
        title="Direct API Song",
        artist="Test Artist",
        filename="song.wav",
        content_type="audio/wav",
    )
    res = create_project(req)
    proj_id = res.project_id
    assert res.title == "Direct API Song"
    assert "uploads/" in res.upload_key

    # List
    projects = list_projects()
    assert len(projects) == 1
    assert projects[0].id == proj_id

    # Get
    single = get_project(proj_id)
    assert single.title == "Direct API Song"

    # Delete
    del_res = delete_project(proj_id)
    assert del_res["status"] == "deleted"

    # Verify empty
    assert len(list_projects()) == 0
