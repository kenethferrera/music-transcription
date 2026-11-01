"""
Arrangement Editing & Export Regeneration Tests
Tests that user modifications in the editor update the canonical arrangement
and immediately regenerate all 6 export files (MIDI, KAR, MusicXML, PDF).
"""
import os
import shutil
import tempfile
import pytest

from backend.app.api.projects import update_arrangement
from backend.app.storage import get_storage_service
from shared.music_schema.arrangement import (
    Arrangement,
    ChordEvent,
    InstrumentFamily,
    KeySignatureEvent,
    LyricEvent,
    NoteEvent,
    ProjectMetadata,
    SyllableType,
    TempoEvent,
    TimeSignatureEvent,
    Track,
)


@pytest.fixture
def edit_env():
    temp_dir = tempfile.mkdtemp(prefix="edit_test_")
    os.environ["STORAGE_PROVIDER"] = "local"
    os.environ["LOCAL_STORAGE_DIR"] = temp_dir

    yield temp_dir

    shutil.rmtree(temp_dir, ignore_errors=True)


def test_arrangement_edit_and_export_regeneration(edit_env):
    storage = get_storage_service(force_local=True)
    project_id = "test_edit_proj"

    # Initial arrangement
    meta = ProjectMetadata(
        project_id=project_id,
        title="Editable Song",
        original_filename="song.wav",
        audio_format="wav",
        duration_seconds=10.0,
        created_at="2026-11-01T00:00:00Z",
    )
    vocal_track = Track(
        id="vocals",
        name="Vocals",
        family=InstrumentFamily.VOCALS,
        notes=[
            NoteEvent(id="n1", track_id="vocals", pitch=60, start_time=1.0, duration=1.0),
        ],
    )
    arr = Arrangement(
        metadata=meta,
        tempo_map=[TempoEvent(start_time=0.0, bpm=120.0)],
        time_signatures=[TimeSignatureEvent(start_time=0.0, numerator=4, denominator=4)],
        key_signatures=[KeySignatureEvent(start_time=0.0, key="C", mode="major")],
        tracks={"vocals": vocal_track},
    )

    # 1. Perform User Edits:
    # - Change pitch from 60 (C4) to 67 (G4)
    # - Add a new note at 2.0s
    # - Add a chord: G Major
    # - Add a lyric syllable
    arr.tracks["vocals"].notes[0].pitch = 67
    arr.tracks["vocals"].notes[0].is_edited = True

    new_note = NoteEvent(id="n2", track_id="vocals", pitch=72, start_time=2.0, duration=0.8, is_edited=True)
    arr.tracks["vocals"].notes.append(new_note)

    arr.chords.append(ChordEvent(id="c1", symbol="G", root="G", quality="maj", start_time=0.0, duration=2.0))
    arr.lyrics.append(LyricEvent(id="l1", text="Sing", start_time=1.0, duration=1.0, note_id="n1", syllable_type=SyllableType.SINGLE))

    # 2. Call update_arrangement API endpoint
    updated = update_arrangement(project_id, arr)

    assert updated.tracks["vocals"].notes[0].pitch == 67
    assert len(updated.tracks["vocals"].notes) == 2
    assert len(updated.chords) == 1
    assert len(updated.lyrics) == 1

    # 3. Verify canonical JSON was saved to storage
    arr_key = f"arrangements/{project_id}/canonical.json"
    assert storage.object_exists(arr_key)
    saved_bytes = storage.download_bytes(arr_key)
    saved_arr = Arrangement.model_validate_json(saved_bytes)
    assert saved_arr.tracks["vocals"].notes[0].pitch == 67

    # 4. Verify all exports were regenerated in storage
    assert storage.object_exists(f"exports/{project_id}/multitrack.mid")
    assert storage.object_exists(f"exports/{project_id}/karaoke.kar")
    assert storage.object_exists(f"exports/{project_id}/full_score.musicxml")
    assert storage.object_exists(f"exports/{project_id}/lead_sheet.musicxml")
    assert storage.object_exists(f"exports/{project_id}/full_score.pdf")
    assert storage.object_exists(f"exports/{project_id}/lead_sheet.pdf")

