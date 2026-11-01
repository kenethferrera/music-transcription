"""
End-to-End Pipeline Integration Test
Tests all 9 stages of the ProjectJobOrchestrator:
1. UPLOAD_COMPLETE
2. AUDIO_PREPROCESSING
3. DEMUCS_SEPARATION
4. MUSCRIPTOR_TRANSCRIPTION
5. EXTERNAL_LYRICS_RECOGNITION
6. LYRIC_TO_NOTE_ALIGNMENT
7. CHORD_AND_MUSIC_ANALYSIS
8. ARRANGEMENT_GENERATION
9. EXPORT_PREPARATION
"""
import math
import os
import shutil
import tempfile
import numpy as np
import soundfile as sf
import pytest

from backend.app.jobs.orchestrator import ProjectJobOrchestrator
from backend.app.storage import get_storage_service
from shared.processing_contracts.jobs import JobProgressEvent, JobStage, JobStatus


@pytest.fixture
def test_env():
    temp_dir = tempfile.mkdtemp(prefix="e2e_test_")
    os.environ["STORAGE_PROVIDER"] = "local"
    os.environ["LOCAL_STORAGE_DIR"] = temp_dir
    os.environ["STT_PROVIDER"] = "mock"

    yield temp_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_full_pipeline_orchestrator(test_env):
    storage = get_storage_service(force_local=True)
    project_id = "test_e2e_proj"
    original_fn = "synthetic_song.wav"
    upload_key = f"uploads/{project_id}/original.wav"

    # 1. Synthesize a 3-second test WAV audio file (440Hz A4 sine tone + harmonic)
    sr = 44100
    duration = 3.0
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)
    # A4 note (440Hz) and E5 (660Hz)
    audio = 0.5 * np.sin(2 * np.pi * 440 * t) + 0.3 * np.sin(2 * np.pi * 660 * t)
    audio_stereo = np.stack([audio, audio], axis=-1)

    local_wav_path = os.path.join(test_env, original_fn)
    sf.write(local_wav_path, audio_stereo, sr, subtype="PCM_16")

    # Upload to storage
    storage.upload_file(local_wav_path, upload_key, content_type="audio/wav")
    assert storage.object_exists(upload_key)

    events_received: list[JobProgressEvent] = []

    def on_progress(event: JobProgressEvent):
        events_received.append(event)

    orchestrator = ProjectJobOrchestrator(
        project_id=project_id,
        title="Synthetic Song",
        upload_object_key=upload_key,
        original_filename=original_fn,
        status_callback=on_progress,
    )

    # Execute complete pipeline
    arrangement = orchestrator.run()

    # Assertions on arrangement
    assert arrangement is not None
    assert arrangement.metadata.project_id == project_id
    assert arrangement.metadata.duration_seconds > 0
    assert len(events_received) >= 9

    # Verify final status
    final_event = events_received[-1]
    assert final_event.stage == JobStage.COMPLETED
    assert final_event.status == JobStatus.SUCCESS

    # Verify all 4 stems were generated and uploaded to storage
    for stem in ("vocals", "drums", "bass", "other"):
        stem_key = f"stems/{project_id}/{stem}.wav"
        assert storage.object_exists(stem_key), f"Stem {stem} missing in storage"

    # Verify canonical arrangement was uploaded
    assert storage.object_exists(f"arrangements/{project_id}/canonical.json")

    # Verify all exports were generated in storage
    assert storage.object_exists(f"exports/{project_id}/multitrack.mid")
    assert storage.object_exists(f"exports/{project_id}/karaoke.kar")
    assert storage.object_exists(f"exports/{project_id}/full_score.musicxml")
    assert storage.object_exists(f"exports/{project_id}/lead_sheet.musicxml")
    assert storage.object_exists(f"exports/{project_id}/full_score.pdf")
    assert storage.object_exists(f"exports/{project_id}/lead_sheet.pdf")

