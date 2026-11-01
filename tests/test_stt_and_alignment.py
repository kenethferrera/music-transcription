"""
Unit Tests for External STT Adapter and Lyric-to-Note Alignment
"""
from backend.app.stt.base import STTResult, STTWord
from backend.app.stt.mock_provider import MockSTTProvider
from shared.music_schema.arrangement import NoteEvent
from workers.arrangement.lyric_aligner import LyricAligner


def test_mock_stt_transcription():
    provider = MockSTTProvider(sample_lyrics="We will rock you")
    result = provider.transcribe("dummy.wav")

    assert result.text == "We will rock you"
    assert len(result.words) == 4
    assert result.words[0].word == "We"
    assert result.words[0].start_time < result.words[0].end_time


def test_lyric_syllabification():
    aligner = LyricAligner()
    # Single syllable
    assert aligner._syllabify("rock") == ["rock"]
    # Multi syllable
    sylls = aligner._syllabify("harmony")
    assert len(sylls) >= 2


def test_lyric_to_note_alignment():
    aligner = LyricAligner(timing_tolerance_seconds=0.5)

    words = [
        STTWord(word="Hello", start_time=1.0, end_time=1.4),
        STTWord(word="World", start_time=2.0, end_time=2.4),
    ]
    stt_res = STTResult(
        text="Hello World",
        duration_seconds=5.0,
        words=words,
        provider="mock",
    )

    vocal_notes = [
        NoteEvent(id="n1", track_id="vocals", pitch=60, start_time=1.05, duration=0.4),
        NoteEvent(id="n2", track_id="vocals", pitch=62, start_time=1.35, duration=0.3),
        NoteEvent(id="n3", track_id="vocals", pitch=64, start_time=2.02, duration=0.5),
    ]

    lyric_events = aligner.align(stt_res, vocal_notes)

    assert len(lyric_events) >= 2
    # Check that note_id has been associated
    matched = [l for l in lyric_events if l.note_id is not None]
    assert len(matched) >= 1

