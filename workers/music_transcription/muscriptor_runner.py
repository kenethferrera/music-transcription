"""
MuScriptor Large Music Transcription Runner.
Implements the verified MuScriptor API:
- model = TranscriptionModel.load_model("large")
- events = model.transcribe(audio_path)
- Processes NoteStartEvent, NoteEndEvent, and ProgressEvent
- Normalizes MT3_FULL_PLUS instrument classes to canonical tracks
- Estimates velocity from local audio onset energy
"""
import logging
import math
import os
import uuid
from typing import Callable, Dict, Generator, List, Optional
import numpy as np
import soundfile as sf
try:
    import torch
except ImportError:
    torch = None

from shared.music_schema.arrangement import InstrumentFamily, NoteEvent

logger = logging.getLogger(__name__)

# Map MT3_FULL_PLUS 36 classes to InstrumentFamily & default MIDI program
INSTRUMENT_MAPPING: Dict[str, tuple[InstrumentFamily, int, str]] = {
    "acoustic_piano": (InstrumentFamily.PIANO, 0, "Acoustic Grand Piano"),
    "bright_acoustic_piano": (InstrumentFamily.PIANO, 1, "Bright Acoustic Piano"),
    "electric_grand_piano": (InstrumentFamily.PIANO, 2, "Electric Grand Piano"),
    "honky_tonk_piano": (InstrumentFamily.PIANO, 3, "Honky-tonk Piano"),
    "electric_piano_1": (InstrumentFamily.PIANO, 4, "Electric Piano 1"),
    "electric_piano_2": (InstrumentFamily.PIANO, 5, "Electric Piano 2"),
    "harpsichord": (InstrumentFamily.PIANO, 6, "Harpsichord"),
    "clavi": (InstrumentFamily.PIANO, 7, "Clavinet"),
    "drawbar_organ": (InstrumentFamily.ORGAN, 16, "Drawbar Organ"),
    "percussive_organ": (InstrumentFamily.ORGAN, 17, "Percussive Organ"),
    "rock_organ": (InstrumentFamily.ORGAN, 18, "Rock Organ"),
    "church_organ": (InstrumentFamily.ORGAN, 19, "Church Organ"),
    "acoustic_guitar_nylon": (InstrumentFamily.GUITAR, 24, "Acoustic Guitar (nylon)"),
    "acoustic_guitar_steel": (InstrumentFamily.GUITAR, 25, "Acoustic Guitar (steel)"),
    "electric_guitar_jazz": (InstrumentFamily.GUITAR, 26, "Electric Guitar (jazz)"),
    "electric_guitar_clean": (InstrumentFamily.GUITAR, 27, "Electric Guitar (clean)"),
    "electric_guitar_muted": (InstrumentFamily.GUITAR, 28, "Electric Guitar (muted)"),
    "overdriven_guitar": (InstrumentFamily.GUITAR, 29, "Overdriven Guitar"),
    "distortion_guitar": (InstrumentFamily.GUITAR, 30, "Distortion Guitar"),
    "acoustic_bass": (InstrumentFamily.BASS, 32, "Acoustic Bass"),
    "electric_bass_finger": (InstrumentFamily.BASS, 33, "Electric Bass (finger)"),
    "electric_bass_pick": (InstrumentFamily.BASS, 34, "Electric Bass (pick)"),
    "fretless_bass": (InstrumentFamily.BASS, 35, "Fretless Bass"),
    "slap_bass_1": (InstrumentFamily.BASS, 36, "Slap Bass 1"),
    "synth_bass_1": (InstrumentFamily.BASS, 38, "Synth Bass 1"),
    "violin": (InstrumentFamily.STRINGS, 40, "Violin"),
    "viola": (InstrumentFamily.STRINGS, 41, "Viola"),
    "cello": (InstrumentFamily.STRINGS, 42, "Cello"),
    "string_ensemble_1": (InstrumentFamily.STRINGS, 48, "String Ensemble 1"),
    "choir_aahs": (InstrumentFamily.VOCALS, 52, "Voice / Choir"),
    "voice_oohs": (InstrumentFamily.VOCALS, 53, "Voice / Choir"),
    "synth_voice": (InstrumentFamily.VOCALS, 54, "Voice / Synth Voice"),
    "voice": (InstrumentFamily.VOCALS, 54, "Vocal Melody"),
    "trumpet": (InstrumentFamily.BRASS, 56, "Trumpet"),
    "trombone": (InstrumentFamily.BRASS, 57, "Trombone"),
    "brass_section": (InstrumentFamily.BRASS, 61, "Brass Section"),
    "soprano_sax": (InstrumentFamily.REED, 64, "Soprano Sax"),
    "alto_sax": (InstrumentFamily.REED, 65, "Alto Sax"),
    "tenor_sax": (InstrumentFamily.REED, 66, "Tenor Sax"),
    "flute": (InstrumentFamily.REED, 73, "Flute"),
    "lead_1_square": (InstrumentFamily.SYNTH, 80, "Lead 1 (square)"),
    "lead_2_sawtooth": (InstrumentFamily.SYNTH, 81, "Lead 2 (sawtooth)"),
    "pad_1_new_age": (InstrumentFamily.SYNTH, 88, "Pad 1 (new age)"),
    "drums": (InstrumentFamily.DRUMS, 0, "Drums / Percussion"),
}


class MuScriptorRunner:
    """Wrapper around MuScriptor Large model inference."""

    def __init__(
        self,
        model_name: str = "large",
        device: Optional[str] = None,
        checkpoint_dir: Optional[str] = None,
    ):
        self.model_name = model_name
        self.device = device or ("cuda" if (torch and torch.cuda.is_available()) else "cpu")
        self.checkpoint_dir = checkpoint_dir or os.getenv("MUSCRIPTOR_CACHE_DIR")
        self._model = None
        self._load_attempted = False

    def _load_model(self):
        if self._model is None and not self._load_attempted:
            self._load_attempted = True
            try:
                from muscriptor import TranscriptionModel
                logger.info(f"Loading MuScriptor '{self.model_name}' on {self.device}...")
                dtype = torch.float16 if (torch and self.device == "cuda") else torch.float32
                try:
                    self._model = TranscriptionModel.load_model(self.model_name, device=self.device, dtype=dtype)
                except (torch.cuda.OutOfMemoryError if torch else Exception) as oom_err:
                    is_prod = os.getenv("ENVIRONMENT", "development").lower() == "production"
                    if is_prod:
                        logger.error(f"Production GPU out of memory on {self.device}: {oom_err}")
                        raise RuntimeError(f"RunPod GPU OOM during MuScriptor Large loading on {self.device}: {oom_err}")
                    logger.warning(f"CUDA memory limit reached on {self.device} ({oom_err}). Retrying MuScriptor on CPU...")
                    if torch and torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    self.device = "cpu"
                    self._model = TranscriptionModel.load_model(self.model_name, device="cpu", dtype=torch.float32)
            except Exception as e:
                logger.warning(f"Could not load official muscriptor model ({e}). Will use fallback parser if needed.")

    def transcribe_audio(
        self,
        audio_path: str,
        source_stem: Optional[str] = None,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> List[NoteEvent]:
        """
        Transcribe an audio file to a list of NoteEvent objects.
        Extracts notes, start times, durations, pitches, instruments,
        and computes estimated velocity from onset audio energy.
        """
        # Load audio data for velocity calculation and fallback
        audio_data, sample_rate = sf.read(audio_path)
        if audio_data.ndim > 1:
            audio_mono = np.mean(audio_data, axis=1)
        else:
            audio_mono = audio_data

        notes: List[NoteEvent] = []

        try:
            self._load_model()
            if self._model is not None:
                from muscriptor.events import NoteStartEvent, NoteEndEvent, ProgressEvent

                active_notes: Dict[int, tuple[NoteStartEvent, float]] = {}

                for event in self._model.transcribe(audio_path):
                    if isinstance(event, ProgressEvent):
                        pct = (event.completed / max(1, event.total)) * 100.0
                        if progress_callback:
                            progress_callback(pct, f"Transcribing {source_stem or 'audio'}: chunk {event.completed}/{event.total}")
                    elif isinstance(event, NoteStartEvent):
                        active_notes[event.index] = (event, event.start_time)
                    elif isinstance(event, NoteEndEvent):
                        start_tuple = active_notes.pop(event.start_event.index, None)
                        if start_tuple:
                            start_evt, start_time = start_tuple
                            duration = max(0.05, event.end_time - start_time)
                            vel = self._estimate_velocity(audio_mono, sample_rate, start_time)

                            track_id = self._map_instrument_to_track_id(start_evt.instrument, source_stem)

                            notes.append(
                                NoteEvent(
                                    id=str(uuid.uuid4()),
                                    track_id=track_id,
                                    pitch=int(start_evt.pitch),
                                    start_time=round(float(start_time), 3),
                                    duration=round(float(duration), 3),
                                    velocity=vel,
                                    confidence=0.9,
                                    source_stem=source_stem,
                                )
                            )

                if torch and torch.cuda.is_available():
                    torch.cuda.empty_cache()

                return notes
        except Exception as e:
            logger.warning(f"MuScriptor model inference encountered error or model not loaded: {e}. Running non-AI pitch tracking fallback.")

        # Robust non-AI pitch tracking fallback for development / offline environments
        return self._fallback_pitch_transcription(audio_mono, sample_rate, source_stem)

    def _estimate_velocity(self, audio_mono: np.ndarray, sample_rate: int, onset_time: float) -> int:
        """Estimate MIDI velocity from local audio RMS energy around the onset."""
        idx = int(onset_time * sample_rate)
        window = int(0.05 * sample_rate)  # 50ms window
        start_idx = max(0, idx - int(0.01 * sample_rate))
        end_idx = min(len(audio_mono), idx + window)

        if start_idx >= end_idx:
            return 64

        segment = audio_mono[start_idx:end_idx]
        rms = np.sqrt(np.mean(segment**2) + 1e-9)

        # Map log RMS dB to MIDI velocity range 30-110
        db = 20 * math.log10(rms + 1e-6)
        # Assuming nominal range -45dB to -5dB
        norm = (db + 45.0) / 40.0
        norm = max(0.0, min(1.0, norm))
        velocity = int(30 + norm * 80)
        return max(1, min(127, velocity))

    def _map_instrument_to_track_id(self, instrument_str: str, source_stem: Optional[str]) -> str:
        clean_name = instrument_str.lower().replace(" ", "_")
        if source_stem == "vocals" or "vocal" in clean_name or "choir" in clean_name or "voice" in clean_name:
            return "vocals"
        elif source_stem == "drums" or "drum" in clean_name or "percussion" in clean_name:
            return "drums"
        elif source_stem == "bass" or "bass" in clean_name:
            return "bass"
        elif "piano" in clean_name:
            return "piano"
        elif "guitar" in clean_name:
            return "guitar"
        elif "string" in clean_name:
            return "strings"
        elif "brass" in clean_name:
            return "brass"
        elif source_stem:
            return source_stem
        return "other"

    def _fallback_pitch_transcription(
        self,
        audio_mono: np.ndarray,
        sample_rate: int,
        source_stem: Optional[str],
    ) -> List[NoteEvent]:
        """
        Deterministic onset/pitch detection fallback using autocorrelation/FFT
        for testing and verification without full 1.3B model weights downloaded.
        """
        notes: List[NoteEvent] = []
        hop_length = int(sample_rate * 0.1)  # 100ms frames
        frame_length = int(sample_rate * 0.2)  # 200ms window

        total_frames = len(audio_mono) // hop_length
        track_id = source_stem or "vocals"

        prev_pitch = -1
        note_start = 0.0

        for frame_idx in range(min(total_frames, 300)):  # Up to 30 seconds
            start_sample = frame_idx * hop_length
            end_sample = min(len(audio_mono), start_sample + frame_length)
            if end_sample - start_sample < frame_length:
                break

            chunk = audio_mono[start_sample:end_sample]
            rms = np.sqrt(np.mean(chunk**2) + 1e-9)

            if rms < 0.02:
                # Silence
                if prev_pitch != -1:
                    notes.append(
                        NoteEvent(
                            id=str(uuid.uuid4()),
                            track_id=track_id,
                            pitch=prev_pitch,
                            start_time=round(note_start, 2),
                            duration=round(max(0.1, (frame_idx * hop_length) / sample_rate - note_start), 2),
                            velocity=64,
                            confidence=0.7,
                            source_stem=source_stem,
                        )
                    )
                    prev_pitch = -1
                continue

            # Estimate fundamental frequency via autocorrelation
            autocorr = np.correlate(chunk, chunk, mode="full")[len(chunk) - 1 :]
            # Search pitch range: 60 Hz (MIDI 36) to 1000 Hz (MIDI 84)
            min_lag = int(sample_rate / 1000)
            max_lag = int(sample_rate / 60)

            if max_lag < len(autocorr):
                peak_lag = min_lag + np.argmax(autocorr[min_lag:max_lag])
                if autocorr[peak_lag] > 0.3 * autocorr[0]:
                    freq = sample_rate / peak_lag
                    midi_pitch = int(round(69 + 12 * math.log2(freq / 440.0)))
                    midi_pitch = max(24, min(108, midi_pitch))

                    if prev_pitch == -1:
                        prev_pitch = midi_pitch
                        note_start = start_sample / sample_rate
                    elif abs(midi_pitch - prev_pitch) >= 1:
                        # Pitch changed
                        notes.append(
                            NoteEvent(
                                id=str(uuid.uuid4()),
                                track_id=track_id,
                                pitch=prev_pitch,
                                start_time=round(note_start, 2),
                                duration=round(max(0.1, start_sample / sample_rate - note_start), 2),
                                velocity=self._estimate_velocity(audio_mono, sample_rate, note_start),
                                confidence=0.75,
                                source_stem=source_stem,
                            )
                        )
                        prev_pitch = midi_pitch
                        note_start = start_sample / sample_rate

        if prev_pitch != -1:
            notes.append(
                NoteEvent(
                    id=str(uuid.uuid4()),
                    track_id=track_id,
                    pitch=prev_pitch,
                    start_time=round(note_start, 2),
                    duration=0.3,
                    velocity=64,
                    confidence=0.75,
                    source_stem=source_stem,
                )
            )

        return notes

