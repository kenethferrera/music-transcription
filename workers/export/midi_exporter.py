"""
Multitrack MIDI Exporter (Standard MIDI File Type 1).
Builds separate tracks for Vocals, Piano, Guitar, Bass, Drums, etc.
"""
import io
import math
from typing import Dict, Optional
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

from shared.music_schema.arrangement import Arrangement, Track


class MidiExporter:
    """Exports canonical Arrangement to Standard MIDI File Type 1."""

    def __init__(self, ticks_per_beat: int = 480):
        self.ticks_per_beat = ticks_per_beat

    def export(self, arrangement: Arrangement, output_path: Optional[str] = None) -> bytes:
        mid = MidiFile(type=1, ticks_per_beat=self.ticks_per_beat)

        # Track 0: Conductor Track (Tempo, Time Signature, Key Signature, Markers)
        conductor = MidiTrack()
        mid.tracks.append(conductor)
        conductor.append(MetaMessage("track_name", name=f"{arrangement.metadata.title} - Tempo Map", time=0))

        # Tempo events
        bpm = arrangement.tempo_map[0].bpm if arrangement.tempo_map else 120.0
        tempo_val = mido.bpm2tempo(bpm)
        conductor.append(MetaMessage("set_tempo", tempo=tempo_val, time=0))

        # Time signature
        if arrangement.time_signatures:
            ts = arrangement.time_signatures[0]
            conductor.append(
                MetaMessage(
                    "time_signature",
                    numerator=ts.numerator,
                    denominator=ts.denominator,
                    clocks_per_click=24,
                    notated_32nd_notes_per_beat=8,
                    time=0,
                )
            )
        else:
            conductor.append(MetaMessage("time_signature", numerator=4, denominator=4, time=0))

        # Key signature
        if arrangement.key_signatures:
            ks = arrangement.key_signatures[0]
            key_name = f"{ks.key}m" if ks.mode == "minor" else ks.key
            try:
                conductor.append(MetaMessage("key_signature", key=key_name, time=0))
            except Exception:
                pass

        conductor.append(MetaMessage("end_of_track", time=0))

        # Instrument Tracks
        channel_alloc = 0
        for track_id, track in arrangement.tracks.items():
            if not track.notes:
                continue

            midi_track = MidiTrack()
            mid.tracks.append(midi_track)

            midi_track.append(MetaMessage("track_name", name=track.name, time=0))

            # Channel allocation (Drums must be channel 9, i.e., 10 in 1-based indexing)
            if track.is_percussion or track_id == "drums":
                channel = 9
            else:
                if channel_alloc == 9:
                    channel_alloc += 1
                channel = channel_alloc % 16
                channel_alloc += 1

            # Program Change
            if not track.is_percussion:
                midi_track.append(
                    Message("program_change", channel=channel, program=track.midi_program, time=0)
                )

            # Build delta-timed MIDI events
            raw_events = []
            for note in track.notes:
                raw_events.append((note.start_time, "note_on", note.pitch, note.velocity))
                raw_events.append((note.end_time, "note_off", note.pitch, 0))

            # Sort events: note_off before note_on at same timestamp
            raw_events.sort(key=lambda x: (x[0], 0 if x[1] == "note_off" else 1))

            last_time = 0.0
            for ev_time, ev_type, pitch, vel in raw_events:
                delta_seconds = max(0.0, ev_time - last_time)
                delta_ticks = int(round(mido.second2tick(delta_seconds, self.ticks_per_beat, tempo_val)))
                midi_track.append(
                    Message(ev_type, channel=channel, note=pitch, velocity=vel, time=delta_ticks)
                )
                last_time = ev_time

            midi_track.append(MetaMessage("end_of_track", time=0))

        # Output
        if output_path:
            mid.save(output_path)

        bio = io.BytesIO()
        mid.save(file=bio)
        return bio.getvalue()

