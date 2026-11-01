"""
Note Reconciler and Arrangement Assembler.
Combines note transcriptions from mix and separated stems,
eliminates duplicate notes, assigns tracks, and builds the canonical Arrangement.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from shared.music_schema.arrangement import (
    Arrangement,
    ChordEvent,
    InstrumentFamily,
    KeySignatureEvent,
    LyricEvent,
    NoteEvent,
    ProjectMetadata,
    TempoEvent,
    TimeSignatureEvent,
    Track,
)

TRACK_DEFINITIONS: Dict[str, tuple[str, InstrumentFamily, int, bool, str]] = {
    "vocals": ("Vocals (Melody)", InstrumentFamily.VOCALS, 54, False, "#EC4899"),
    "piano": ("Piano", InstrumentFamily.PIANO, 0, False, "#3B82F6"),
    "guitar": ("Guitar", InstrumentFamily.GUITAR, 25, False, "#F59E0B"),
    "bass": ("Bass", InstrumentFamily.BASS, 33, False, "#10B981"),
    "drums": ("Drums", InstrumentFamily.DRUMS, 0, True, "#8B5CF6"),
    "strings": ("Strings", InstrumentFamily.STRINGS, 48, False, "#6366F1"),
    "other": ("Other Instruments", InstrumentFamily.OTHER, 80, False, "#64748B"),
}


class ArrangementReconciler:
    """Reconciles note events from mix and stems into canonical tracks."""

    def __init__(self, time_tolerance_seconds: float = 0.04):
        self.time_tolerance = time_tolerance_seconds

    def reconcile(
        self,
        project_id: str,
        title: str,
        original_filename: str,
        audio_format: str,
        duration_seconds: float,
        mix_notes: List[NoteEvent],
        stem_notes: Dict[str, List[NoteEvent]],
        stt_lyrics: List[LyricEvent],
        tempo_map: List[TempoEvent],
        time_signatures: List[TimeSignatureEvent],
        key_signatures: List[KeySignatureEvent],
        chords: List[ChordEvent],
        stem_references: Optional[Dict[str, str]] = None,
    ) -> Arrangement:
        """
        Produce a canonical Arrangement object.
        """
        all_notes: List[NoteEvent] = []

        # If we have isolated vocal stem notes, use them for the vocal track
        vocal_stem_notes = stem_notes.get("vocals", [])
        if vocal_stem_notes:
            for n in vocal_stem_notes:
                n.track_id = "vocals"
                n.source_stem = "vocals"
                all_notes.append(n)
        else:
            # Extract vocal notes from mix
            vocal_mix = [n for n in mix_notes if n.track_id == "vocals"]
            all_notes.extend(vocal_mix)

        # Isolated bass stem notes
        bass_stem_notes = stem_notes.get("bass", [])
        if bass_stem_notes:
            for n in bass_stem_notes:
                n.track_id = "bass"
                n.source_stem = "bass"
                all_notes.append(n)
        else:
            bass_mix = [n for n in mix_notes if n.track_id == "bass"]
            all_notes.extend(bass_mix)

        # Isolated drum stem notes
        drum_stem_notes = stem_notes.get("drums", [])
        if drum_stem_notes:
            for n in drum_stem_notes:
                n.track_id = "drums"
                n.source_stem = "drums"
                all_notes.append(n)
        else:
            drum_mix = [n for n in mix_notes if n.track_id == "drums"]
            all_notes.extend(drum_mix)

        # Accompaniment / harmonic notes from mix & other stem
        for n in mix_notes:
            if n.track_id not in ("vocals", "bass", "drums"):
                all_notes.append(n)

        other_stem_notes = stem_notes.get("other", [])
        for n in other_stem_notes:
            all_notes.append(n)

        # De-duplicate notes per track
        deduped_notes = self._deduplicate_notes(all_notes)

        # Group notes into tracks
        tracks: Dict[str, Track] = {}
        for track_id, (name, family, prog, is_perc, color) in TRACK_DEFINITIONS.items():
            track_notes = [n for n in deduped_notes if n.track_id == track_id]
            # Only create track if it has notes, or if it is vocals/piano/bass/drums
            if track_notes or track_id in ("vocals", "piano", "bass", "drums"):
                tracks[track_id] = Track(
                    id=track_id,
                    name=name,
                    family=family,
                    midi_program=prog,
                    is_percussion=is_perc,
                    color=color,
                    notes=sorted(track_notes, key=lambda n: n.start_time),
                )

        metadata = ProjectMetadata(
            project_id=project_id,
            title=title,
            original_filename=original_filename,
            audio_format=audio_format,
            duration_seconds=duration_seconds,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        return Arrangement(
            metadata=metadata,
            tempo_map=tempo_map,
            time_signatures=time_signatures,
            key_signatures=key_signatures,
            chords=chords,
            lyrics=stt_lyrics,
            tracks=tracks,
            stem_references=stem_references or {},
        )

    def _deduplicate_notes(self, notes: List[NoteEvent]) -> List[NoteEvent]:
        """
        Removes duplicate/conflicting notes on the same pitch within time tolerance.
        """
        sorted_notes = sorted(notes, key=lambda n: (n.track_id, n.pitch, n.start_time))
        deduped: List[NoteEvent] = []

        for note in sorted_notes:
            if not deduped:
                deduped.append(note)
                continue

            last = deduped[-1]
            if (
                last.track_id == note.track_id
                and last.pitch == note.pitch
                and abs(last.start_time - note.start_time) <= self.time_tolerance
            ):
                # Duplicate note - keep the one with higher confidence or longer duration
                if note.confidence > last.confidence or note.duration > last.duration:
                    deduped[-1] = note
            else:
                deduped.append(note)

        return deduped

