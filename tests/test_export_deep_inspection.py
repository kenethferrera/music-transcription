"""
Deep Inspection Tests for Generated Export Files.
Validates exact binary and textual formats for MIDI, KAR, MusicXML, and PDF.
"""
import io
import xml.etree.ElementTree as ET
import mido

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


def build_complex_arrangement() -> Arrangement:
    meta = ProjectMetadata(
        project_id="deep_inspect_proj",
        title="Symphonic Rock",
        artist="Deep Inspector",
        original_filename="rock.wav",
        audio_format="wav",
        duration_seconds=12.0,
        created_at="2026-11-01T00:00:00Z",
    )
    vocals = Track(
        id="vocals",
        name="Lead Vocals",
        family=InstrumentFamily.VOCALS,
        midi_program=54,
        notes=[
            NoteEvent(id="v1", track_id="vocals", pitch=60, start_time=1.0, duration=0.8, velocity=90),
            NoteEvent(id="v2", track_id="vocals", pitch=62, start_time=2.0, duration=0.8, velocity=85),
            NoteEvent(id="v3", track_id="vocals", pitch=64, start_time=3.0, duration=0.8, velocity=95),
            NoteEvent(id="v4", track_id="vocals", pitch=65, start_time=4.0, duration=1.2, velocity=92),
        ],
    )
    piano = Track(
        id="piano",
        name="Grand Piano",
        family=InstrumentFamily.PIANO,
        midi_program=0,
        notes=[
            NoteEvent(id="p1", track_id="piano", pitch=48, start_time=0.0, duration=4.0, velocity=75),
            NoteEvent(id="p2", track_id="piano", pitch=52, start_time=0.0, duration=4.0, velocity=70),
            NoteEvent(id="p3", track_id="piano", pitch=55, start_time=0.0, duration=4.0, velocity=72),
        ],
    )
    drums = Track(
        id="drums",
        name="Drum Kit",
        family=InstrumentFamily.DRUMS,
        midi_program=0,
        is_percussion=True,
        notes=[
            NoteEvent(id="d1", track_id="drums", pitch=36, start_time=0.0, duration=0.2, velocity=100),  # Kick
            NoteEvent(id="d2", track_id="drums", pitch=38, start_time=1.0, duration=0.2, velocity=100),  # Snare
            NoteEvent(id="d3", track_id="drums", pitch=36, start_time=2.0, duration=0.2, velocity=100),  # Kick
            NoteEvent(id="d4", track_id="drums", pitch=38, start_time=3.0, duration=0.2, velocity=100),  # Snare
        ],
    )
    lyrics = [
        LyricEvent(id="l1", text="We", start_time=1.0, duration=0.8, note_id="v1", syllable_type=SyllableType.SINGLE),
        LyricEvent(id="l2", text="will", start_time=2.0, duration=0.8, note_id="v2", syllable_type=SyllableType.SINGLE),
        LyricEvent(id="l3", text="rock", start_time=3.0, duration=0.8, note_id="v3", syllable_type=SyllableType.SINGLE),
        LyricEvent(id="l4", text="you", start_time=4.0, duration=1.2, note_id="v4", syllable_type=SyllableType.SINGLE),
    ]
    chords = [
        ChordEvent(id="c1", symbol="C", root="C", quality="maj", start_time=0.0, duration=2.0),
        ChordEvent(id="c2", symbol="Am", root="A", quality="min", start_time=2.0, duration=2.0),
        ChordEvent(id="c3", symbol="F", root="F", quality="maj", start_time=4.0, duration=2.0),
        ChordEvent(id="c4", symbol="G", root="G", quality="maj", start_time=6.0, duration=2.0),
    ]

    return Arrangement(
        metadata=meta,
        tempo_map=[TempoEvent(start_time=0.0, bpm=128.0)],
        time_signatures=[TimeSignatureEvent(start_time=0.0, numerator=4, denominator=4)],
        key_signatures=[KeySignatureEvent(start_time=0.0, key="C", mode="major")],
        chords=chords,
        lyrics=lyrics,
        tracks={"vocals": vocals, "piano": piano, "drums": drums},
    )


def test_deep_midi_inspection():
    arr = build_complex_arrangement()
    midi_bytes = MidiExporter().export(arr)
    mid = mido.MidiFile(file=io.BytesIO(midi_bytes))

    assert mid.type == 1
    assert mid.ticks_per_beat == 480
    assert len(mid.tracks) == 4  # Conductor + Vocals + Piano + Drums

    # Verify Conductor Track
    conductor = mid.tracks[0]
    tempo_msgs = [m for m in conductor if m.type == "set_tempo"]
    assert len(tempo_msgs) >= 1
    assert round(mido.tempo2bpm(tempo_msgs[0].tempo)) == 128

    # Verify Drums is on Channel 9 (MIDI Ch 10)
    drum_track = [t for t in mid.tracks if any(m.type == "track_name" and "Drum" in m.name for m in t)][0]
    drum_notes = [m for m in drum_track if m.type == "note_on"]
    assert all(m.channel == 9 for m in drum_notes)

    # Verify no raw audio header embedded (no ID3, no RIFF header in MIDI bytes)
    assert not midi_bytes.startswith(b"ID3")
    assert not midi_bytes.startswith(b"RIFF")
    assert midi_bytes.startswith(b"MThd")


def test_deep_karaoke_kar_inspection():
    arr = build_complex_arrangement()
    kar_bytes = KaraokeExporter().export(arr)
    mid = mido.MidiFile(file=io.BytesIO(kar_bytes))

    assert mid.type == 1
    # Check headers in track 0
    track0_texts = [m.text for m in mid.tracks[0] if m.type == "text"]
    assert any("@T" in t for t in track0_texts)
    assert any("@K" in t for t in track0_texts)

    # Check lyrics in vocal melody track
    vocal_track = mid.tracks[1]
    lyric_msgs = [m for m in vocal_track if m.type == "lyrics"]
    assert len(lyric_msgs) == 4
    words = [m.text.strip().lstrip("/").lstrip("\\") for m in lyric_msgs]
    assert words == ["We", "will", "rock", "you"]

    # Verify lyric events have non-zero delta times (synchronized with notes, not all at 0)
    assert any(m.time > 0 for m in lyric_msgs)


def test_deep_musicxml_inspection():
    arr = build_complex_arrangement()
    xml_exporter = MusicXMLExporter()

    # 1. Full score
    full_xml = xml_exporter.export_full_score(arr)
    root = ET.fromstring(full_xml)
    assert root.tag == "score-partwise"
    assert root.attrib.get("version") == "4.0"

    parts = root.findall("part")
    assert len(parts) == 3  # Vocals, Piano, Drums

    # Check drum part has percussion clef
    drum_part = parts[2]
    first_measure = drum_part.find("measure")
    clef = first_measure.find(".//clef")
    assert clef.find("sign").text == "percussion"

    # 2. Lead sheet
    lead_xml = xml_exporter.export_lead_sheet(arr)
    lead_root = ET.fromstring(lead_xml)
    lead_parts = lead_root.findall("part")
    assert len(lead_parts) == 1

    # Check chord symbols (harmony elements)
    harmonies = lead_root.findall(".//harmony")
    assert len(harmonies) >= 4
    roots = [h.find(".//root-step").text for h in harmonies]
    assert "C" in roots
    assert "A" in roots
    assert "F" in roots
    assert "G" in roots


def test_deep_pdf_inspection():
    arr = build_complex_arrangement()
    xml_str = MusicXMLExporter().export_lead_sheet(arr)
    pdf_bytes = PDFExporter().render_musicxml_to_pdf(xml_str, title=arr.metadata.title, subtitle="Lead Sheet")

    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert b"%%EOF" in pdf_bytes
    assert b"/Catalog" in pdf_bytes
    assert b"/Pages" in pdf_bytes
    assert b"Symphonic Rock" in pdf_bytes

