"""
Project API Schemas
"""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from shared.processing_contracts.jobs import JobProgressEvent, JobStage, JobStatus


class ProjectCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    artist: Optional[str] = "Unknown Artist"
    filename: str
    content_type: str = "audio/wav"


class ProjectCreateResponse(BaseModel):
    project_id: str
    title: str
    upload_url: str
    upload_key: str


class ProjectSummary(BaseModel):
    id: str
    title: str
    artist: Optional[str] = None
    original_filename: str
    created_at: str
    status: JobStatus = JobStatus.PENDING
    stage: JobStage = JobStage.QUEUED
    progress_percent: float = 0.0
    duration_seconds: Optional[float] = None
    total_notes: Optional[int] = None
    tracks_count: Optional[int] = None


class StemUrlsResponse(BaseModel):
    project_id: str
    stems: Dict[str, str]  # stem_name -> download URL


class ExportResponse(BaseModel):
    project_id: str
    format: str
    download_url: str
    filename: str

