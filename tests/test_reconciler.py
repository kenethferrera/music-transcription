"""
Unit Tests for Arrangement Reconciler and Note Deduplication
"""
from shared.music_schema.arrangement import (
    ChordEvent,
    InstrumentFamily,
    KeySignatureEvent,
    NoteEvent,
    TempoEvent,
    TimeSignatureEvent,
)
from workers.arrangement.reconciler import ArrangementReconciler


def test_note_deduplication():
    reconciler = ArrangementReconciler(time_tolerance_seconds=0.05)

    notes = [
        NoteEvent(id="1", track_id="piano", pitch=60, start_time=1.00, duration=0.5, confidence=0.7),
        NoteEvent(id="2", track_id="piano", pitch=60, start_time=1.02, duration=0.6, confidence=0.9),  # Duplicate
        NoteEvent(id="3", track_id="piano", pitch=64, start_time=1.00, duration=0.5, confidence=0.8),  # Different pitch
        NoteEvent(id="4", track_id="piano", pitch=60, start_time=2.00, duration=0.5, confidence=0.8),  # Distinct time
    ]

    deduped = reconciler._deduplicate_notes(notes)
    assert len(deduped) == 3
    # Check that highest confidence duplicate was preserved
    piano_c4 = [n for n in deduped if n.pitch == 60 and n.start_time < 1.5][0]
    assert piano_c4.confidence == 0.9


def test_reconcile_full_arrangement():
    reconciler = ArrangementReconciler()

    mix_notes = [
        NoteEvent(id="m1", track_id="piano", pitch=60, start_time=0.5, duration=0.5),
        NoteEvent(id="m2", track_id="guitar", pitch=67, start_time=0.5, duration=0.5),
    ]
    stem_notes = {
        "vocals": [
            NoteEvent(id="v1", track_id="vocals", pitch=72, start_time=1.0, duration=0.8),
        ],
        "bass": [
            NoteEvent(id="b1", track_id="bass", pitch=36, start_time=0.0, duration=1.0),
        ],
    }

    arr = reconciler.reconcile(
        project_id="p1",
        title="Test Song",
        original_filename="song.wav",
        audio_format="wav",
        duration_seconds=10.0,
        mix_notes=mix_notes,
        stem_notes=stem_notes,
        stt_lyrics=[],
        tempo_map=[TempoEvent(start_time=0.0, bpm=120.0)],
        time_signatures=[TimeSignatureEvent(start_time=0.0, numerator=4, denominator=4)],
        key_signatures=[KeySignatureEvent(start_time=0.0, key="C", mode="major")],
        chords=[ChordEvent(id="c1", symbol="C", root="C", quality="maj", start_time=0.0, duration=2.0)],
    )

    assert arr.metadata.title == "Test Song"
    assert "vocals" in arr.tracks
    assert "bass" in arr.tracks
    assert "piano" in arr.tracks
    assert len(arr.tracks["vocals"].notes) == 1
    assert arr.tracks["vocals"].notes[0].pitch == 72

