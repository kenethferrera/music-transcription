"""
MusicXML Exporter.
Generates clean, well-formed MusicXML 3.1 / 4.0 for:
- Full Score (all transcribed parts with appropriate clefs and staves)
- Lead Sheet (vocal melody + lyrics + chord symbols)
"""
import math
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET
from xml.dom import minidom

from shared.music_schema.arrangement import (
    Arrangement,
    ChordEvent,
    InstrumentFamily,
    LyricEvent,
    NoteEvent,
    SyllableType,
    Track,
)

PITCH_STEPS = ["C", "C", "D", "D", "E", "F", "F", "G", "G", "A", "A", "B"]
PITCH_ALTERS = [0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0]


class MusicXMLExporter:
    """Exports canonical Arrangement to MusicXML."""

    def __init__(self, divisions: int = 4):
        self.divisions = divisions  # 4 divisions per quarter note = 16th note resolution

    def export_full_score(self, arrangement: Arrangement) -> str:
        """Export full score with all transcribed instrument parts."""
        return self._generate_musicxml(arrangement, is_lead_sheet=False)

    def export_lead_sheet(self, arrangement: Arrangement) -> str:
        """Export lead sheet with vocal melody, lyrics, and chord symbols."""
        return self._generate_musicxml(arrangement, is_lead_sheet=True)

    def _generate_musicxml(self, arrangement: Arrangement, is_lead_sheet: bool = False) -> str:
        root = ET.Element("score-partwise", version="4.0")

        # Movement title
        work = ET.SubElement(root, "work")
        ET.SubElement(work, "work-title").text = (
            f"{arrangement.metadata.title} (Lead Sheet)" if is_lead_sheet else arrangement.metadata.title
        )

        # Identification
        ident = ET.SubElement(root, "identification")
        creator = ET.SubElement(ident, "creator", type="composer")
        creator.text = arrangement.metadata.artist or "Unknown Artist"

        # Part list
        part_list = ET.SubElement(root, "part-list")

        active_tracks: List[tuple[str, Track]] = []
        if is_lead_sheet:
            vocal_track = arrangement.get_vocal_track()
            if vocal_track:
                active_tracks.append(("P1", vocal_track))
            elif arrangement.tracks:
                # Use first available track as lead melody
                first_k = next(iter(arrangement.tracks))
                active_tracks.append(("P1", arrangement.tracks[first_k]))
            else:
                empty_vocal = Track(
                    id="vocals",
                    name="Melody",
                    family=InstrumentFamily.VOCALS,
                    notes=[],
                )
                active_tracks.append(("P1", empty_vocal))
        else:
            p_idx = 1
            for track_id, track in arrangement.tracks.items():
                if track.notes:
                    active_tracks.append((f"P{p_idx}", track))
                    p_idx += 1

        for part_id, track in active_tracks:
            score_part = ET.SubElement(part_list, "score-part", id=part_id)
            ET.SubElement(score_part, "part-name").text = track.name

        # Calculate measure metrics
        bpm = arrangement.tempo_map[0].bpm if arrangement.tempo_map else 120.0
        ts = arrangement.time_signatures[0] if arrangement.time_signatures else None
        num_beats = ts.numerator if ts else 4
        beat_type = ts.denominator if ts else 4

        seconds_per_beat = 60.0 / bpm
        seconds_per_measure = seconds_per_beat * (num_beats * (4.0 / beat_type))
        total_duration = max(arrangement.metadata.duration_seconds, 4.0)
        num_measures = max(1, int(math.ceil(total_duration / seconds_per_measure)))

        # Build lyrics map: note_id -> LyricEvent
        lyrics_by_note: Dict[str, LyricEvent] = {}
        for lyr in arrangement.lyrics:
            if lyr.note_id:
                lyrics_by_note[lyr.note_id] = lyr

        # Render each part
        for part_id, track in active_tracks:
            part_elem = ET.SubElement(root, "part", id=part_id)

            for m_idx in range(num_measures):
                measure_elem = ET.SubElement(part_elem, "measure", number=str(m_idx + 1))
                m_start = m_idx * seconds_per_measure
                m_end = m_start + seconds_per_measure

                # Measure 1 attributes
                if m_idx == 0:
                    attrs = ET.SubElement(measure_elem, "attributes")
                    ET.SubElement(attrs, "divisions").text = str(self.divisions)

                    # Key signature
                    key_elem = ET.SubElement(attrs, "key")
                    fifths = 0
                    if arrangement.key_signatures:
                        fifths = self._key_to_fifths(arrangement.key_signatures[0].key)
                    ET.SubElement(key_elem, "fifths").text = str(fifths)

                    # Time signature
                    time_elem = ET.SubElement(attrs, "time")
                    ET.SubElement(time_elem, "beats").text = str(num_beats)
                    ET.SubElement(time_elem, "beat-type").text = str(beat_type)

                    # Clef
                    clef_elem = ET.SubElement(attrs, "clef")
                    if track.family == InstrumentFamily.BASS:
                        ET.SubElement(clef_elem, "sign").text = "F"
                        ET.SubElement(clef_elem, "line").text = "4"
                    elif track.family == InstrumentFamily.DRUMS:
                        ET.SubElement(clef_elem, "sign").text = "percussion"
                    else:
                        ET.SubElement(clef_elem, "sign").text = "G"
                        ET.SubElement(clef_elem, "line").text = "2"

                # If lead sheet and measure has chords, add harmony
                if is_lead_sheet:
                    for ch in arrangement.chords:
                        if m_start <= ch.start_time < m_end:
                            self._append_harmony(measure_elem, ch)

                # Get notes within this measure
                m_notes = [n for n in track.notes if m_start <= n.start_time < m_end]
                m_notes.sort(key=lambda n: n.start_time)

                if not m_notes:
                    # Insert a whole measure rest
                    note_elem = ET.SubElement(measure_elem, "note")
                    ET.SubElement(note_elem, "rest", measure="yes")
                    ET.SubElement(note_elem, "duration").text = str(self.divisions * num_beats)
                else:
                    curr_time = m_start
                    for note in m_notes:
                        # Insert rest if there is a gap before note
                        gap = note.start_time - curr_time
                        if gap >= (seconds_per_beat / self.divisions):
                            gap_divisions = max(1, int(round((gap / seconds_per_beat) * self.divisions)))
                            rest_elem = ET.SubElement(measure_elem, "note")
                            ET.SubElement(rest_elem, "rest")
                            ET.SubElement(rest_elem, "duration").text = str(gap_divisions)
                            ET.SubElement(rest_elem, "voice").text = "1"
                            curr_time += (gap_divisions / self.divisions) * seconds_per_beat

                        note_duration_divs = max(
                            1, int(round((note.duration / seconds_per_beat) * self.divisions))
                        )
                        note_elem = ET.SubElement(measure_elem, "note")
                        pitch_elem = ET.SubElement(note_elem, "pitch")

                        pc_idx = note.pitch % 12
                        step = PITCH_STEPS[pc_idx]
                        alter = PITCH_ALTEFS = PITCH_ALTERS[pc_idx]
                        octave = (note.pitch // 12) - 1

                        ET.SubElement(pitch_elem, "step").text = step
                        if alter != 0:
                            ET.SubElement(pitch_elem, "alter").text = str(alter)
                        ET.SubElement(pitch_elem, "octave").text = str(octave)

                        ET.SubElement(note_elem, "duration").text = str(note_duration_divs)
                        ET.SubElement(note_elem, "voice").text = "1"
                        ET.SubElement(note_elem, "type").text = self._divisions_to_note_type(note_duration_divs)

                        # Check for lyric
                        lyr = lyrics_by_note.get(note.id)
                        if lyr:
                            lyric_elem = ET.SubElement(note_elem, "lyric", number="1")
                            s_text = (
                                "single"
                                if lyr.syllable_type == SyllableType.SINGLE
                                else (
                                    "begin"
                                    if lyr.syllable_type == SyllableType.BEGIN
                                    else (
                                        "middle"
                                        if lyr.syllable_type == SyllableType.MIDDLE
                                        else "end"
                                    )
                                )
                            )
                            ET.SubElement(lyric_elem, "syllabic").text = s_text
                            ET.SubElement(lyric_elem, "text").text = lyr.text

                        curr_time = note.end_time

        rough_string = ET.tostring(root, "utf-8")
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")

    def _append_harmony(self, measure_elem: ET.Element, chord: ChordEvent):
        harm = ET.SubElement(measure_elem, "harmony")
        root_elem = ET.SubElement(harm, "root")
        root_step = chord.root[0]
        ET.SubElement(root_elem, "root-step").text = root_step
        if len(chord.root) > 1 and chord.root[1] == "#":
            ET.SubElement(root_elem, "root-alter").text = "1"
        elif len(chord.root) > 1 and chord.root[1] == "b":
            ET.SubElement(root_elem, "root-alter").text = "-1"

        kind_map = {
            "maj": "major",
            "min": "minor",
            "7": "dominant",
            "m7": "minor-seventh",
            "maj7": "major-seventh",
            "dim": "diminished",
            "aug": "augmented",
        }
        ET.SubElement(harm, "kind").text = kind_map.get(chord.quality, "major")

    def _key_to_fifths(self, key_root: str) -> int:
        fifths_map = {
            "C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6,
            "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6,
        }
        return fifths_map.get(key_root, 0)

    def _divisions_to_note_type(self, divs: int) -> str:
        ratio = divs / self.divisions
        if ratio >= 4.0:
            return "whole"
        elif ratio >= 2.0:
            return "half"
        elif ratio >= 1.0:
            return "quarter"
        elif ratio >= 0.5:
            return "eighth"
        return "16th"

