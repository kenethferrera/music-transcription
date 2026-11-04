"""
Music Transcription Job Pipeline Orchestrator.
Sequentially executes the 9 stages:
1. UPLOAD_COMPLETE
2. AUDIO_PREPROCESSING
3. DEMUCS_SEPARATION
4. MUSCRIPTOR_TRANSCRIPTION
5. EXTERNAL_LYRICS_RECOGNITION
6. LYRIC_TO_NOTE_ALIGNMENT
7. CHORD_AND_MUSIC_ANALYSIS
8. ARRANGEMENT_GENERATION
9. EXPORT_PREPARATION
"""
import asyncio
from datetime import datetime, timezone
import json
import logging
import os
import shutil
import tempfile
from typing import Callable, Dict, List, Optional
import soundfile as sf
try:
    import torch
except ImportError:
    torch = None

from backend.app.services.gpu_manager import GPUManager
from backend.app.storage import get_storage_service
from backend.app.stt import get_stt_provider
from shared.music_schema.arrangement import Arrangement
from shared.processing_contracts.jobs import (
    JobProgressEvent,
    JobStage,
    JobStatus,
    StageProgress,
)
from workers.audio_separation import DemucsRunner
from workers.arrangement import (
    ArrangementReconciler,
    LyricAligner,
    MusicAnalyzer,
)
from workers.export import (
    KaraokeExporter,
    MidiExporter,
    MusicXMLExporter,
    PDFExporter,
)
from workers.music_transcription import MuScriptorRunner

logger = logging.getLogger(__name__)


class ProjectJobOrchestrator:
    """Manages the full transcription workflow for a project."""

    def __init__(
        self,
        project_id: str,
        title: str,
        upload_object_key: str,
        original_filename: str,
        status_callback: Optional[Callable[[JobProgressEvent], None]] = None,
    ):
        self.project_id = project_id
        self.title = title
        self.upload_object_key = upload_object_key
        self.original_filename = original_filename
        self.status_callback = status_callback
        self.storage = get_storage_service()
        self.stt_provider = get_stt_provider()

        self.scratch_dir = tempfile.mkdtemp(prefix=f"transcription_{project_id}_")

    def _emit_progress(
        self,
        stage: JobStage,
        status: JobStatus,
        progress_pct: float,
        step_num: int,
        stage_name: str,
        message: str,
        details: Optional[Dict] = None,
    ):
        event = JobProgressEvent(
            project_id=self.project_id,
            stage=stage,
            status=status,
            progress_percent=round(progress_pct, 1),
            current_step=step_num,
            total_steps=9,
            stage_name=stage_name,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            details=details,
        )
        logger.info(f"[{self.project_id}] Step {step_num}/9 ({stage.value}): {message}")
        if self.status_callback:
            self.status_callback(event)

    def run(self) -> Arrangement:
        """Execute all stages synchronously or inside a background worker."""
        try:
            # Enforce production GPU requirements if in production mode
            GPUManager.verify_production_gpu()
            gpu_status = GPUManager.get_gpu_status()
            logger.info(f"[{self.project_id}] Target Execution Platform: {gpu_status['platform']} | GPU: {gpu_status['device_name']}")

            # 1. UPLOAD_COMPLETE
            self._emit_progress(
                JobStage.UPLOAD_COMPLETE,
                JobStatus.PROCESSING,
                10.0,
                1,
                "Upload Verification",
                "Verifying uploaded audio file in object storage...",
            )
            if not self.storage.object_exists(self.upload_object_key):
                raise FileNotFoundError(f"Upload key {self.upload_object_key} not found in storage.")

            local_input = os.path.join(self.scratch_dir, f"original_{self.original_filename}")
            self.storage.download_file(self.upload_object_key, local_input)

            # 2. AUDIO_PREPROCESSING
            self._emit_progress(
                JobStage.AUDIO_PREPROCESSING,
                JobStatus.PROCESSING,
                20.0,
                2,
                "Audio Preprocessing",
                "Analyzing audio format, duration, channels, and sample rate...",
            )
            info = sf.info(local_input)
            duration_sec = float(info.duration)
            sample_rate = int(info.samplerate)
            channels = int(info.channels)
            audio_format = str(info.format).lower()

            # 3. DEMUCS_SEPARATION
            self._emit_progress(
                JobStage.DEMUCS_SEPARATION,
                JobStatus.PROCESSING,
                35.0,
                3,
                "Source Separation (Demucs)",
                "Separating vocals, drums, bass, and other audio using Demucs...",
            )
            demucs = DemucsRunner()
            stems_dir = os.path.join(self.scratch_dir, "stems")
            stem_paths = demucs.separate(local_input, stems_dir)

            # Upload stems to storage and record references
            stem_refs: Dict[str, str] = {}
            for stem_name, stem_file in stem_paths.items():
                stem_key = f"stems/{self.project_id}/{stem_name}.wav"
                self.storage.upload_file(stem_file, stem_key, content_type="audio/wav")
                stem_refs[stem_name] = stem_key

            # Release VRAM between Demucs and MuScriptor Large
            GPUManager.release_vram()

            # 4. MUSCRIPTOR_TRANSCRIPTION
            self._emit_progress(
                JobStage.MUSCRIPTOR_TRANSCRIPTION,
                JobStatus.PROCESSING,
                50.0,
                4,
                "Musical Transcription (MuScriptor Large)",
                "Transcribing musical notes using MuScriptor Large...",
            )
            muscriptor = MuScriptorRunner()

            # Transcribe original mix
            mix_notes = muscriptor.transcribe_audio(local_input, source_stem="mix")

            # Transcribe isolated stems for specific track isolation
            stem_notes: Dict[str, List] = {}
            for stem_name in ("vocals", "bass", "drums", "other"):
                if stem_name in stem_paths and os.path.exists(stem_paths[stem_name]):
                    notes = muscriptor.transcribe_audio(stem_paths[stem_name], source_stem=stem_name)
                    stem_notes[stem_name] = notes

            # Release VRAM after transcription
            GPUManager.release_vram()

            # 5. EXTERNAL_LYRICS_RECOGNITION
            self._emit_progress(
                JobStage.EXTERNAL_LYRICS_RECOGNITION,
                JobStatus.PROCESSING,
                65.0,
                5,
                "Lyrics Recognition (External STT)",
                "Recognizing lyrics and timestamps from vocal stem via external STT API...",
            )
            vocal_stem_path = stem_paths.get("vocals", local_input)
            try:
                stt_result = self.stt_provider.transcribe(vocal_stem_path)
            except Exception as e:
                logger.error(f"External STT transcription error: {e}. Falling back to instrumental lyrics.")
                from backend.app.stt.base import STTResult
                stt_result = STTResult(
                    text="",
                    language="en",
                    duration_seconds=0.0,
                    words=[],
                    segments=[],
                    provider="fallback",
                )

            # 6. LYRIC_TO_NOTE_ALIGNMENT
            self._emit_progress(
                JobStage.LYRIC_TO_NOTE_ALIGNMENT,
                JobStatus.PROCESSING,
                75.0,
                6,
                "Lyric-to-Note Alignment",
                "Aligning recognized lyrics and syllables with vocal melody notes...",
            )
            aligner = LyricAligner()
            vocal_melody_notes = stem_notes.get("vocals") or [n for n in mix_notes if n.track_id == "vocals"]
            aligned_lyrics = aligner.align(stt_result, vocal_melody_notes)

            # 7. CHORD_AND_MUSIC_ANALYSIS
            self._emit_progress(
                JobStage.CHORD_AND_MUSIC_ANALYSIS,
                JobStatus.PROCESSING,
                82.0,
                7,
                "Musical Analysis",
                "Estimating chords, tempo, key, and time signature using signal processing...",
            )
            analyzer = MusicAnalyzer(sample_rate=sample_rate)
            tempo_map, time_sigs, key_sigs, chords = analyzer.analyze_audio(local_input, mix_notes)

            # 8. ARRANGEMENT_GENERATION
            self._emit_progress(
                JobStage.ARRANGEMENT_GENERATION,
                JobStatus.PROCESSING,
                90.0,
                8,
                "Arrangement Generation",
                "Reconciling notes, tracks, chords, and lyrics into canonical arrangement...",
            )
            reconciler = ArrangementReconciler()
            arrangement = reconciler.reconcile(
                project_id=self.project_id,
                title=self.title,
                original_filename=self.original_filename,
                audio_format=audio_format,
                duration_seconds=duration_sec,
                mix_notes=mix_notes,
                stem_notes=stem_notes,
                stt_lyrics=aligned_lyrics,
                tempo_map=tempo_map,
                time_signatures=time_sigs,
                key_signatures=key_sigs,
                chords=chords,
                stem_references=stem_refs,
            )

            # Save canonical arrangement JSON to object storage
            arr_json_bytes = arrangement.model_dump_json(indent=2).encode("utf-8")
            arr_key = f"arrangements/{self.project_id}/canonical.json"
            self.storage.upload_bytes(arr_json_bytes, arr_key, content_type="application/json")

            # 9. EXPORT_PREPARATION
            self._emit_progress(
                JobStage.EXPORT_PREPARATION,
                JobStatus.PROCESSING,
                95.0,
                9,
                "Export Preparation",
                "Generating Multitrack MIDI, Karaoke MIDI, and Sheet Music PDFs...",
            )
            self._generate_default_exports(arrangement, stt_result=stt_result)

            # COMPLETE
            self._emit_progress(
                JobStage.COMPLETED,
                JobStatus.SUCCESS,
                100.0,
                9,
                "Completed",
                "Project processing successfully finished! Exports ready for download.",
                details={"total_notes": arrangement.total_notes_count(), "tracks": list(arrangement.tracks.keys())},
            )

            return arrangement

        except Exception as e:
            logger.exception(f"Processing failed in project {self.project_id}: {e}")
            self._emit_progress(
                JobStage.FAILED,
                JobStatus.FAILED,
                0.0,
                0,
                "Failed",
                f"Processing error: {str(e)}",
                details={"error": str(e)},
            )
            raise
        finally:
            # Clean up local scratch directory
            shutil.rmtree(self.scratch_dir, ignore_errors=True)

    def _generate_default_exports(self, arrangement: Arrangement, stt_result: Optional[Any] = None):
        """Prepares default export artifacts and uploads them to object storage."""
        # 1. Multitrack MIDI (.mid)
        midi_exp = MidiExporter()
        midi_bytes = midi_exp.export(arrangement)
        self.storage.upload_bytes(
            midi_bytes,
            f"exports/{self.project_id}/multitrack.mid",
            content_type="audio/midi",
        )

        # 2. Karaoke MIDI (.kar)
        kar_exp = KaraokeExporter()
        kar_bytes = kar_exp.export(arrangement)
        self.storage.upload_bytes(
            kar_bytes,
            f"exports/{self.project_id}/karaoke.kar",
            content_type="audio/midi",
        )

        # 3. MusicXML Full Score
        xml_exp = MusicXMLExporter()
        full_score_xml = xml_exp.export_full_score(arrangement)
        self.storage.upload_bytes(
            full_score_xml.encode("utf-8"),
            f"exports/{self.project_id}/full_score.musicxml",
            content_type="application/vnd.recordare.musicxml+xml",
        )

        # 4. MusicXML Lead Sheet
        lead_sheet_xml = xml_exp.export_lead_sheet(arrangement)
        self.storage.upload_bytes(
            lead_sheet_xml.encode("utf-8"),
            f"exports/{self.project_id}/lead_sheet.musicxml",
            content_type="application/vnd.recordare.musicxml+xml",
        )

        # 5. Full Score PDF
        pdf_exp = PDFExporter()
        full_pdf_bytes = pdf_exp.render_musicxml_to_pdf(
            full_score_xml,
            title=arrangement.metadata.title,
            subtitle="Full Score",
        )
        self.storage.upload_bytes(
            full_pdf_bytes,
            f"exports/{self.project_id}/full_score.pdf",
            content_type="application/pdf",
        )

        # 6. Lead Sheet PDF
        lead_pdf_bytes = pdf_exp.render_musicxml_to_pdf(
            lead_sheet_xml,
            title=arrangement.metadata.title,
            subtitle="Lead Sheet (Melody, Chords, Lyrics)",
        )
        self.storage.upload_bytes(
            lead_pdf_bytes,
            f"exports/{self.project_id}/lead_sheet.pdf",
            content_type="application/pdf",
        )

        # 7. Plain Text Lyrics Transcript (.txt)
        lyrics_text = ""
        if stt_result and getattr(stt_result, "text", ""):
            lyrics_text = stt_result.text.strip()
        elif arrangement.lyrics:
            lyrics_text = " ".join([l.text for l in arrangement.lyrics if l.text]).strip()

        if lyrics_text:
            self.storage.upload_bytes(
                lyrics_text.encode("utf-8"),
                f"exports/{self.project_id}/lyrics.txt",
                content_type="text/plain; charset=utf-8",
            )

        # 8. Synchronized Lyrics (.lrc)
        lrc_lines = []
        if stt_result and getattr(stt_result, "segments", None):
            for seg in stt_result.segments:
                seg_text = getattr(seg, "text", "").strip()
                if seg_text:
                    m = int(seg.start_time // 60)
                    s = seg.start_time % 60
                    lrc_lines.append(f"[{m:02d}:{s:05.2f}] {seg_text}")
        elif arrangement.lyrics:
            current_words: List[str] = []
            line_start = 0.0
            last_end = 0.0
            for lyr in arrangement.lyrics:
                if not current_words:
                    line_start = lyr.start_time
                elif (lyr.start_time - last_end > 1.2) or len(current_words) >= 10:
                    m = int(line_start // 60)
                    s = line_start % 60
                    lrc_lines.append(f"[{m:02d}:{s:05.2f}] {' '.join(current_words)}")
                    current_words = []
                    line_start = lyr.start_time
                current_words.append(lyr.text)
                last_end = lyr.end_time
            if current_words:
                m = int(line_start // 60)
                s = line_start % 60
                lrc_lines.append(f"[{m:02d}:{s:05.2f}] {' '.join(current_words)}")

        if lrc_lines:
            lrc_bytes = "\n".join(lrc_lines).encode("utf-8")
            self.storage.upload_bytes(
                lrc_bytes,
                f"exports/{self.project_id}/lyrics.lrc",
                content_type="text/plain; charset=utf-8",
            )

