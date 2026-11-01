"""
Persistence & Restart Tests for Database-Backed Store.
Verifies that projects and job states survive process/instance restarts.
"""
import os
import shutil
import tempfile
import pytest

from backend.app.models.database import Base, ProjectModel, SessionLocal, engine
from backend.app.models.project_store import ProjectStore, get_project_store
from shared.processing_contracts.jobs import JobProgressEvent, JobStage, JobStatus


@pytest.fixture
def clean_db():
    temp_dir = tempfile.mkdtemp(prefix="persist_test_")
    db_file = os.path.join(temp_dir, "test.db").replace("\\", "/")
    os.environ["DATABASE_URL"] = f"sqlite:///{db_file}"

    # Recreate tables in test db
    from sqlalchemy import create_engine
    test_engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=test_engine)

    # Patch engine and SessionLocal in database module
    import backend.app.models.database as db_mod
    orig_engine = db_mod.engine
    orig_session = db_mod.SessionLocal
    db_mod.engine = test_engine
    db_mod.SessionLocal = type(orig_session)(bind=test_engine)

    yield temp_dir

    # Restore
    db_mod.engine = orig_engine
    db_mod.SessionLocal = orig_session
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_project_survives_store_restart(clean_db):
    # Instance 1: Create project
    store1 = ProjectStore()
    p1 = store1.create_project(title="Persistent Song", artist="Rockers", filename="song.wav")
    proj_id = p1.project_id

    # Update progress
    ev = JobProgressEvent(
        project_id=proj_id,
        stage=JobStage.DEMUCS_SEPARATION,
        status=JobStatus.PROCESSING,
        progress_percent=35.0,
        current_step=3,
        total_steps=9,
        stage_name="Demucs Separation",
        message="Separating stems...",
        timestamp="",
    )
    store1.update_progress(ev)

    # "Simulate Server Restart" -> destroy store1 and instantiate fresh store2
    del store1

    store2 = ProjectStore()
    recovered = store2.get_project(proj_id)

    assert recovered is not None
    assert recovered.project_id == proj_id
    assert recovered.title == "Persistent Song"
    assert recovered.artist == "Rockers"
    assert recovered.stage == JobStage.DEMUCS_SEPARATION
    assert recovered.status == JobStatus.PROCESSING
    assert recovered.progress_percent == 35.0

    # Test deletion
    deleted = store2.delete_project(proj_id)
    assert deleted is True

    # Fresh store3 verifies deletion persisted
    store3 = ProjectStore()
    assert store3.get_project(proj_id) is None

