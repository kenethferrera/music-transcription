"""
Processing Job Contracts & Pipeline Stage Definitions
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class JobStage(str, Enum):
    QUEUED = "queued"
    UPLOAD_COMPLETE = "upload_complete"
    AUDIO_PREPROCESSING = "audio_preprocessing"
    DEMUCS_SEPARATION = "demucs_separation"
    MUSCRIPTOR_TRANSCRIPTION = "muscriptor_transcription"
    EXTERNAL_LYRICS_RECOGNITION = "external_lyrics_recognition"
    LYRIC_TO_NOTE_ALIGNMENT = "lyric_to_note_alignment"
    CHORD_AND_MUSIC_ANALYSIS = "chord_and_music_analysis"
    ARRANGEMENT_GENERATION = "arrangement_generation"
    EXPORT_PREPARATION = "export_preparation"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageProgress(BaseModel):
    stage: JobStage
    status: JobStatus = JobStatus.PENDING
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    message: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class JobProgressEvent(BaseModel):
    project_id: str
    stage: JobStage
    status: JobStatus
    progress_percent: float = Field(default=0.0, ge=0.0, le=100.0)
    current_step: int = 1
    total_steps: int = 9
    stage_name: str
    message: str
    timestamp: str
    details: Optional[Dict[str, Any]] = None

