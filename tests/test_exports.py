"""
Unit Tests for Exports (MIDI, KAR, MusicXML, PDF)
"""
import io
import mido
import xml.etree.ElementTree as ET

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
from workers.export.karaoke_exporter import KaraokeExporter
from workers.export.midi_exporter import MidiExporter
from workers.export.musicxml_exporter import MusicXMLExporter
from workers.export.pdf_exporter import PDFExporter


def sample_arrangement() -> Arrangement:
    meta = ProjectMetadata(
        project_id="test_exp",
        title="Export Anthem",
        artist="Test Artist",
        original_filename="anthem.wav",
        audio_format="wav",
        duration_seconds=8.0,
        created_at="2026-11-01T00:00:00Z",
    )
    vocals = Track(
        id="vocals",
        name="Vocals",
        family=InstrumentFamily.VOCALS,
        midi_program=54,
        notes=[
            NoteEvent(id="v1", track_id="vocals", pitch=60, start_time=1.0, duration=0.8, velocity=90),
            NoteEvent(id="v2", track_id="vocals", pitch=62, start_time=2.0, duration=0.8, velocity=85),
            NoteEvent(id="v3", track_id="vocals", pitch=64, start_time=3.0, duration=1.0, velocity=95),
        ],
    )
    piano = Track(
        id="piano",
        name="Piano",
        family=InstrumentFamily.PIANO,
        midi_program=0,
        notes=[
            NoteEvent(id="p1", track_id="piano", pitch=48, start_time=0.0, duration=2.0, velocity=70),
            NoteEvent(id="p2", track_id="piano", pitch=55, start_time=2.0, duration=2.0, velocity=70),
        ],
    )
    lyrics = [
        LyricEvent(id="l1", text="Do", start_time=1.0, duration=0.8, note_id="v1", syllable_type=SyllableType.SINGLE),
        LyricEvent(id="l2", text="Re", start_time=2.0, duration=0.8, note_id="v2", syllable_type=SyllableType.SINGLE),
        LyricEvent(id="l3", text="Mi", start_time=3.0, duration=1.0, note_id="v3", syllable_type=SyllableType.SINGLE),
    ]
    chords = [
        ChordEvent(id="c1", symbol="C", root="C", quality="maj", start_time=0.0, duration=2.0),
        ChordEvent(id="c2", symbol="G", root="G", quality="maj", start_time=2.0, duration=2.0),
    ]
    return Arrangement(
        metadata=meta,
        tempo_map=[TempoEvent(start_time=0.0, bpm=120.0)],
        time_signatures=[TimeSignatureEvent(start_time=0.0, numerator=4, denominator=4)],
        key_signatures=[KeySignatureEvent(start_time=0.0, key="C", mode="major")],
        chords=chords,
        lyrics=lyrics,
        tracks={"vocals": vocals, "piano": piano},
    )


def test_midi_export():
    arr = sample_arrangement()
    exporter = MidiExporter()
    midi_bytes = exporter.export(arr)

    assert len(midi_bytes) > 0
    # Re-open and validate generated MIDI file
    mid = mido.MidiFile(file=io.BytesIO(midi_bytes))
    assert mid.type == 1
    assert len(mid.tracks) >= 2  # Conductor track + instrument tracks


def test_karaoke_kar_export():
    arr = sample_arrangement()
    exporter = KaraokeExporter()
    kar_bytes = exporter.export(arr)

    assert len(kar_bytes) > 0
    mid = mido.MidiFile(file=io.BytesIO(kar_bytes))
    assert mid.type == 1

    # Verify presence of @T header and lyrics meta messages
    found_header = False
    found_lyric = False
    for track in mid.tracks:
        for msg in track:
            if msg.type == "text" and "@T" in msg.text:
                found_header = True
            elif msg.type == "lyrics":
                found_lyric = True

    assert found_header
    assert found_lyric


def test_musicxml_full_score_and_lead_sheet():
    arr = sample_arrangement()
    exporter = MusicXMLExporter()

    # 1. Full Score
    full_xml = exporter.export_full_score(arr)
    assert len(full_xml) > 0
    root = ET.fromstring(full_xml)
    assert root.tag == "score-partwise"
    parts = root.findall("part")
    assert len(parts) == 2  # Vocals and Piano

    # 2. Lead Sheet
    lead_xml = exporter.export_lead_sheet(arr)
    assert len(lead_xml) > 0
    lead_root = ET.fromstring(lead_xml)
    lead_parts = lead_root.findall("part")
    assert len(lead_parts) == 1  # Melody only
    harmonies = lead_root.findall(".//harmony")
    assert len(harmonies) >= 1  # Chords present


def test_pdf_export():
    arr = sample_arrangement()
    xml_exporter = MusicXMLExporter()
    lead_xml = xml_exporter.export_lead_sheet(arr)

    pdf_exporter = PDFExporter()
    pdf_bytes = pdf_exporter.render_musicxml_to_pdf(lead_xml, title="Export Anthem", subtitle="Lead Sheet")

    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF")

