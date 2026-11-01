"""
Canonical Shared Music Representation
Source of truth for all exports (MIDI, KAR, MusicXML, PDF).
"""
from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class InstrumentFamily(str, Enum):
    PIANO = "piano"
    GUITAR = "guitar"
    BASS = "bass"
    DRUMS = "drums"
    VOCALS = "vocals"
    STRINGS = "strings"
    BRASS = "brass"
    REED = "reed"
    ORGAN = "organ"
    SYNTH = "synth"
    OTHER = "other"


class SyllableType(str, Enum):
    SINGLE = "single"
    BEGIN = "begin"
    MIDDLE = "middle"
    END = "end"


class NoteEvent(BaseModel):
    id: str = Field(..., description="Unique note event identifier")
    track_id: str = Field(..., description="Track ID this note belongs to")
    pitch: int = Field(..., ge=0, le=127, description="MIDI pitch (0-127)")
    start_time: float = Field(..., ge=0.0, description="Onset time in seconds")
    duration: float = Field(..., gt=0.0, description="Duration in seconds")
    velocity: int = Field(default=64, ge=1, le=127, description="MIDI velocity (1-127)")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Transcription confidence")
    source_stem: Optional[str] = Field(default=None, description="Demucs stem reference if isolated")
    is_edited: bool = Field(default=False, description="Whether manually edited")

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration


class LyricEvent(BaseModel):
    id: str = Field(..., description="Unique lyric event identifier")
    text: str = Field(..., description="Word or syllable text")
    start_time: float = Field(..., ge=0.0, description="Start time in seconds")
    duration: float = Field(..., ge=0.0, description="Duration in seconds")
    note_id: Optional[str] = Field(default=None, description="Associated vocal note ID")
    syllable_type: SyllableType = Field(default=SyllableType.SINGLE)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_edited: bool = Field(default=False)

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration


class ChordEvent(BaseModel):
    id: str = Field(..., description="Unique chord identifier")
    symbol: str = Field(..., description="Harmonic symbol (e.g. C, Am7, G/B)")
    root: str = Field(..., description="Chord root note (e.g. C, F#)")
    quality: str = Field(default="maj", description="Chord quality (maj, min, 7, m7, dim, aug)")
    start_time: float = Field(..., ge=0.0)
    duration: float = Field(..., gt=0.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    is_edited: bool = Field(default=False)

    @property
    def end_time(self) -> float:
        return self.start_time + self.duration


class TempoEvent(BaseModel):
    start_time: float = Field(default=0.0, ge=0.0)
    bpm: float = Field(..., gt=10.0, le=300.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class TimeSignatureEvent(BaseModel):
    start_time: float = Field(default=0.0, ge=0.0)
    numerator: int = Field(default=4, ge=1, le=32)
    denominator: int = Field(default=4, ge=1, le=32)


class KeySignatureEvent(BaseModel):
    start_time: float = Field(default=0.0, ge=0.0)
    key: str = Field(default="C", description="Key root note (e.g. C, G, Eb)")
    mode: str = Field(default="major", description="major or minor")


class Track(BaseModel):
    id: str = Field(..., description="Track identifier (e.g. vocals, piano, bass)")
    name: str = Field(..., description="Display name")
    family: InstrumentFamily = Field(default=InstrumentFamily.OTHER)
    midi_program: int = Field(default=0, ge=0, le=127, description="General MIDI program number")
    is_percussion: bool = Field(default=False, description="Channel 10 percussion track")
    color: str = Field(default="#3B82F6", description="Hex color for UI display")
    volume: float = Field(default=1.0, ge=0.0, le=2.0)
    pan: float = Field(default=0.0, ge=-1.0, le=1.0)
    muted: bool = Field(default=False)
    solo: bool = Field(default=False)
    notes: List[NoteEvent] = Field(default_factory=list)


class ProjectMetadata(BaseModel):
    project_id: str
    title: str
    artist: Optional[str] = "Unknown Artist"
    original_filename: str
    audio_format: str
    duration_seconds: float
    sample_rate: int = 44100
    channels: int = 2
    created_at: str
    model_version_demucs: str = "htdemucs"
    model_version_muscriptor: str = "MuScriptor/muscriptor-large"
    stt_provider: str = "external"


class Arrangement(BaseModel):
    metadata: ProjectMetadata
    tempo_map: List[TempoEvent] = Field(default_factory=list)
    time_signatures: List[TimeSignatureEvent] = Field(default_factory=list)
    key_signatures: List[KeySignatureEvent] = Field(default_factory=list)
    chords: List[ChordEvent] = Field(default_factory=list)
    lyrics: List[LyricEvent] = Field(default_factory=list)
    tracks: Dict[str, Track] = Field(default_factory=dict)
    stem_references: Dict[str, str] = Field(
        default_factory=dict,
        description="Map of stem names to R2 object keys (e.g. {'vocals': 'stems/...'})",
    )

    def get_track(self, track_id: str) -> Optional[Track]:
        return self.tracks.get(track_id)

    def get_vocal_track(self) -> Optional[Track]:
        for track in self.tracks.values():
            if track.family == InstrumentFamily.VOCALS:
                return track
        return None

    def total_notes_count(self) -> int:
        return sum(len(t.notes) for t in self.tracks.values())

