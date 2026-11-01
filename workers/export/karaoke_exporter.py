"""
Karaoke MIDI (.kar) Exporter.
Outputs standard Type 1 MIDI with karaoke text events synchronized to vocal notes.
"""
import io
from typing import Optional
import mido
from mido import MidiFile, MidiTrack, Message, MetaMessage

from shared.music_schema.arrangement import Arrangement, SyllableType


class KaraokeExporter:
    """Exports canonical Arrangement to Karaoke MIDI (.kar)."""

    def __init__(self, ticks_per_beat: int = 480):
        self.ticks_per_beat = ticks_per_beat

    def export(self, arrangement: Arrangement, output_path: Optional[str] = None) -> bytes:
        mid = MidiFile(type=1, ticks_per_beat=self.ticks_per_beat)

        # Track 0: Conductor & Karaoke Info
        conductor = MidiTrack()
        mid.tracks.append(conductor)

        conductor.append(MetaMessage("text", text=f"@T{arrangement.metadata.title}", time=0))
        conductor.append(MetaMessage("text", text=f"@T{arrangement.metadata.artist or 'Unknown'}", time=0))
        conductor.append(MetaMessage("text", text="@KMIDI KARAOKE FILE", time=0))
        conductor.append(MetaMessage("text", text="@LENGL", time=0))

        bpm = arrangement.tempo_map[0].bpm if arrangement.tempo_map else 120.0
        tempo_val = mido.bpm2tempo(bpm)
        conductor.append(MetaMessage("set_tempo", tempo=tempo_val, time=0))
        conductor.append(MetaMessage("time_signature", numerator=4, denominator=4, time=0))
        conductor.append(MetaMessage("end_of_track", time=0))

        # Vocal Melody & Synchronized Lyrics Track
        vocal_track_obj = arrangement.get_vocal_track()
        vocal_track = MidiTrack()
        mid.tracks.append(vocal_track)
        vocal_track.append(MetaMessage("track_name", name="Vocal Melody & Lyrics", time=0))
        vocal_track.append(Message("program_change", channel=0, program=54, time=0))

        # Build combined note and lyric events timeline
        timed_events = []

        if vocal_track_obj:
            for note in vocal_track_obj.notes:
                timed_events.append((note.start_time, "note_on", note.pitch, note.velocity))
                timed_events.append((note.end_time, "note_off", note.pitch, 0))

        # Interleave lyrics
        for idx, lyric in enumerate(arrangement.lyrics):
            # Format text: prefix '/' on line beginnings or spaces for word breaks
            text = lyric.text
            if lyric.syllable_type in (SyllableType.SINGLE, SyllableType.BEGIN):
                prefix = "/" if idx % 8 == 0 else " "
                text = prefix + text
            timed_events.append((lyric.start_time, "lyric", text, 0))

        timed_events.sort(key=lambda x: (x[0], 0 if x[1] == "note_off" else (1 if x[1] == "lyric" else 2)))

        last_time = 0.0
        for ev_time, ev_type, val, extra in timed_events:
            delta_seconds = max(0.0, ev_time - last_time)
            delta_ticks = int(round(mido.second2tick(delta_seconds, self.ticks_per_beat, tempo_val)))

            if ev_type == "lyric":
                vocal_track.append(MetaMessage("lyrics", text=str(val), time=delta_ticks))
            elif ev_type in ("note_on", "note_off"):
                vocal_track.append(Message(ev_type, channel=0, note=int(val), velocity=int(extra), time=delta_ticks))

            last_time = ev_time

        vocal_track.append(MetaMessage("end_of_track", time=0))

        # Add remaining accompaniment tracks (Piano, Bass, Drums, etc.)
        channel_alloc = 1
        for track_id, track in arrangement.tracks.items():
            if track_id == "vocals" or not track.notes:
                continue

            midi_track = MidiTrack()
            mid.tracks.append(midi_track)
            midi_track.append(MetaMessage("track_name", name=track.name, time=0))

            if track.is_percussion or track_id == "drums":
                channel = 9
            else:
                if channel_alloc == 9:
                    channel_alloc += 1
                channel = channel_alloc % 16
                channel_alloc += 1

            if not track.is_percussion:
                midi_track.append(Message("program_change", channel=channel, program=track.midi_program, time=0))

            raw_events = []
            for note in track.notes:
                raw_events.append((note.start_time, "note_on", note.pitch, note.velocity))
                raw_events.append((note.end_time, "note_off", note.pitch, 0))
            raw_events.sort(key=lambda x: (x[0], 0 if x[1] == "note_off" else 1))

            last_t = 0.0
            for ev_time, ev_type, pitch, vel in raw_events:
                d_sec = max(0.0, ev_time - last_t)
                d_ticks = int(round(mido.second2tick(d_sec, self.ticks_per_beat, tempo_val)))
                midi_track.append(Message(ev_type, channel=channel, note=pitch, velocity=vel, time=d_ticks))
                last_t = ev_time

            midi_track.append(MetaMessage("end_of_track", time=0))

        if output_path:
            mid.save(output_path)

        bio = io.BytesIO()
        mid.save(file=bio)
        return bio.getvalue()

