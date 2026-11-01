"""
Project State & Persistence Store using SQLAlchemy Database Engine.
Provides ACID transactions, multi-instance concurrency, and API restart survival.
"""
from datetime import datetime, timezone
import json
import logging
import os
from typing import Dict, List, Optional
import uuid

from backend.app.models.database import Base, ProjectModel, SessionLocal, engine
from shared.processing_contracts.jobs import JobProgressEvent, JobStage, JobStatus

logger = logging.getLogger(__name__)


class ProjectRecord:
    def __init__(
        self,
        project_id: str,
        title: str,
        artist: str,
        original_filename: str,
        upload_object_key: str,
        status: JobStatus = JobStatus.PENDING,
        stage: JobStage = JobStage.QUEUED,
        progress_percent: float = 0.0,
        created_at: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        total_notes: Optional[int] = None,
        tracks_count: Optional[int] = None,
        error_message: Optional[str] = None,
    ):
        self.project_id = project_id
        self.title = title
        self.artist = artist
        self.original_filename = original_filename
        self.upload_object_key = upload_object_key
        self.status = status
        self.stage = stage
        self.progress_percent = progress_percent
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.duration_seconds = duration_seconds
        self.total_notes = total_notes
        self.tracks_count = tracks_count
        self.error_message = error_message
        self.latest_event: Optional[JobProgressEvent] = None

    def to_dict(self) -> Dict:
        return {
            "project_id": self.project_id,
            "title": self.title,
            "artist": self.artist,
            "original_filename": self.original_filename,
            "upload_object_key": self.upload_object_key,
            "status": self.status.value,
            "stage": self.stage.value,
            "progress_percent": self.progress_percent,
            "created_at": self.created_at,
            "duration_seconds": self.duration_seconds,
            "total_notes": self.total_notes,
            "tracks_count": self.tracks_count,
            "error_message": self.error_message,
        }

    @classmethod
    def from_model(cls, model: ProjectModel) -> "ProjectRecord":
        return cls(
            project_id=model.project_id,
            title=model.title,
            artist=model.artist or "Unknown Artist",
            original_filename=model.original_filename,
            upload_object_key=model.upload_object_key,
            status=JobStatus(model.status),
            stage=JobStage(model.stage),
            progress_percent=float(model.progress_percent or 0.0),
            created_at=model.created_at,
            duration_seconds=model.duration_seconds,
            total_notes=model.total_notes,
            tracks_count=model.tracks_count,
            error_message=model.error_message,
        )


class ProjectStore:
    """Database-backed persistent store for projects."""

    def __init__(self):
        self._listeners: Dict[str, List] = {}
        # Ensure schema exists
        Base.metadata.create_all(bind=engine)

    def create_project(self, title: str, artist: str, filename: str) -> ProjectRecord:
        project_id = str(uuid.uuid4())
        ext = os.path.splitext(filename)[1] or ".wav"
        upload_key = f"uploads/{project_id}/original{ext}"
        created_at = datetime.now(timezone.utc).isoformat()

        db = SessionLocal()
        try:
            model = ProjectModel(
                project_id=project_id,
                title=title,
                artist=artist,
                original_filename=filename,
                upload_object_key=upload_key,
                status=JobStatus.PENDING.value,
                stage=JobStage.QUEUED.value,
                progress_percent=0.0,
                created_at=created_at,
            )
            db.add(model)
            db.commit()
            db.refresh(model)
            return ProjectRecord.from_model(model)
        finally:
            db.close()

    def get_project(self, project_id: str) -> Optional[ProjectRecord]:
        db = SessionLocal()
        try:
            model = db.query(ProjectModel).filter(ProjectModel.project_id == project_id).first()
            if model:
                return ProjectRecord.from_model(model)
            return None
        finally:
            db.close()

    def list_projects(self) -> List[ProjectRecord]:
        db = SessionLocal()
        try:
            models = db.query(ProjectModel).order_by(ProjectModel.created_at.desc()).all()
            return [ProjectRecord.from_model(m) for m in models]
        finally:
            db.close()

    def delete_project(self, project_id: str) -> bool:
        db = SessionLocal()
        try:
            model = db.query(ProjectModel).filter(ProjectModel.project_id == project_id).first()
            if model:
                db.delete(model)
                db.commit()
                return True
            return False
        finally:
            db.close()

    def update_progress(self, event: JobProgressEvent):
        db = SessionLocal()
        try:
            model = db.query(ProjectModel).filter(ProjectModel.project_id == event.project_id).first()
            if model:
                model.stage = event.stage.value
                model.status = event.status.value
                model.progress_percent = event.progress_percent
                if event.status == JobStatus.FAILED:
                    model.error_message = event.message
                elif event.details and "total_notes" in event.details:
                    model.total_notes = event.details.get("total_notes")
                    model.tracks_count = len(event.details.get("tracks", []))
                db.commit()
        except Exception as e:
            logger.error(f"Error updating project progress in DB: {e}")
            db.rollback()
        finally:
            db.close()

        # Notify event listeners (SSE queues)
        listeners = self._listeners.get(event.project_id, [])
        for q in list(listeners):
            try:
                q.put_nowait(event)
            except Exception:
                pass

    def add_listener(self, project_id: str, queue):
        if project_id not in self._listeners:
            self._listeners[project_id] = []
        self._listeners[project_id].append(queue)

    def remove_listener(self, project_id: str, queue):
        if project_id in self._listeners:
            try:
                self._listeners[project_id].remove(queue)
            except ValueError:
                pass


_store_instance = None


def get_project_store() -> ProjectStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = ProjectStore()
    return _store_instance
