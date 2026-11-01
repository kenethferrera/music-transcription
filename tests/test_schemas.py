"""
Unit Tests for Canonical Music Schema & Processing Contracts
"""
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
from shared.processing_contracts.jobs import JobProgressEvent, JobStage, JobStatus


def test_note_event_properties():
    note = NoteEvent(
        id="n1",
        track_id="piano",
        pitch=60,
        start_time=1.5,
        duration=0.75,
        velocity=80,
    )
    assert note.pitch == 60
    assert note.end_time == 2.25
    assert not note.is_edited


def test_lyric_event_properties():
    lyr = LyricEvent(
        id="l1",
        text="Hello",
        start_time=1.0,
        duration=0.5,
        syllable_type=SyllableType.SINGLE,
    )
    assert lyr.text == "Hello"
    assert lyr.end_time == 1.5


def test_arrangement_roundtrip():
    meta = ProjectMetadata(
        project_id="proj_123",
        title="Test Song",
        original_filename="song.wav",
        audio_format="wav",
        duration_seconds=120.0,
        created_at="2026-11-01T00:00:00Z",
    )
    piano_track = Track(
        id="piano",
        name="Piano",
        family=InstrumentFamily.PIANO,
        midi_program=0,
        notes=[
            NoteEvent(id="n1", track_id="piano", pitch=60, start_time=0.0, duration=1.0),
            NoteEvent(id="n2", track_id="piano", pitch=64, start_time=1.0, duration=1.0),
        ],
    )
    arr = Arrangement(
        metadata=meta,
        tempo_map=[TempoEvent(start_time=0.0, bpm=120.0)],
        time_signatures=[TimeSignatureEvent(start_time=0.0, numerator=4, denominator=4)],
        key_signatures=[KeySignatureEvent(start_time=0.0, key="C", mode="major")],
        tracks={"piano": piano_track},
    )

    json_str = arr.model_dump_json()
    loaded = Arrangement.model_validate_json(json_str)

    assert loaded.metadata.title == "Test Song"
    assert loaded.total_notes_count() == 2
    assert loaded.get_track("piano") is not None
    assert loaded.get_track("piano").notes[0].pitch == 60


def test_job_progress_event():
    event = JobProgressEvent(
        project_id="proj_1",
        stage=JobStage.DEMUCS_SEPARATION,
        status=JobStatus.PROCESSING,
        progress_percent=35.0,
        current_step=3,
        total_steps=9,
        stage_name="Demucs Separation",
        message="Separating stems",
        timestamp="2026-11-01T00:00:00Z",
    )
    assert event.current_step == 3
    assert event.stage == JobStage.DEMUCS_SEPARATION

