"""
OpenAI, Groq & OpenRouter External Speech-to-Text Provider Adapter.
Uses standard /v1/audio/transcriptions endpoint with verbose_json and word timestamps.
Automatically compresses vocal stems to 16kHz mono MP3 to prevent HTTP 413 Payload Too Large.
"""
import logging
import os
import subprocess
import tempfile
import time
from typing import List, Optional, Tuple
import httpx

from backend.app.stt.base import STTProvider, STTResult, STTSegment, STTWord

logger = logging.getLogger(__name__)


def _prepare_stt_audio(audio_file_path: str) -> Tuple[str, str, bool]:
    """
    Downsamples audio to 16kHz mono 64kbps MP3 (or 16-bit PCM WAV) for external STT APIs.
    Reduces payload size by ~95% (e.g. from 110MB to ~2.5MB for a 5-min vocal stem),
    preventing HTTP 413 (Payload Too Large) errors from cloud Whisper providers.
    
    Returns:
        (prepared_path, mime_type, is_temp)
    """
    if not os.path.exists(audio_file_path):
        return audio_file_path, "audio/wav", False

    # Try ffmpeg compression to 16kHz mono MP3
    try:
        tmp_mp3 = tempfile.NamedTemporaryFile(suffix="_stt.mp3", delete=False)
        tmp_mp3.close()
        cmd = [
            "ffmpeg",
            "-y",
            "-i", audio_file_path,
            "-ar", "16000",
            "-ac", "1",
            "-b:a", "64k",
            tmp_mp3.name,
        ]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0 and os.path.getsize(tmp_mp3.name) > 0:
            logger.info(
                f"Compressed vocal stem for STT: {os.path.getsize(audio_file_path):,} bytes -> "
                f"{os.path.getsize(tmp_mp3.name):,} bytes"
            )
            return tmp_mp3.name, "audio/mpeg", True
        else:
            if os.path.exists(tmp_mp3.name):
                os.unlink(tmp_mp3.name)
    except Exception as e:
        logger.debug(f"ffmpeg compression for STT skipped: {e}")

    # Fallback to soundfile if available
    try:
        import soundfile as sf
        import numpy as np
        data, sr = sf.read(audio_file_path)
        if data.ndim > 1:
            data = np.mean(data, axis=1)
        tmp_wav = tempfile.NamedTemporaryFile(suffix="_stt.wav", delete=False)
        tmp_wav.close()
        sf.write(tmp_wav.name, data, sr, subtype="PCM_16")
        return tmp_wav.name, "audio/wav", True
    except Exception as e:
        logger.debug(f"soundfile preparation skipped: {e}")

    return audio_file_path, "audio/wav", False


class OpenAICompatibleSTTProvider(STTProvider):
    """
    Adapter for OpenAI, Groq, and OpenRouter Whisper Cloud API.
    Does NOT use local models - calls the remote cloud endpoint.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout_seconds: float = 120.0,
        max_retries: int = 3,
    ):
        self.api_key = (
            api_key
            or os.getenv("STT_API_KEY")
            or os.getenv("OPENROUTER_API_KEY")
            or os.getenv("GROQ_API_KEY")
            or os.getenv("OPENAI_API_KEY")
        )
        default_base = "https://api.openai.com/v1"
        if os.getenv("OPENROUTER_API_KEY") or os.getenv("STT_PROVIDER") == "openrouter":
            default_base = "https://openrouter.ai/api/v1"
        elif os.getenv("GROQ_API_KEY") or os.getenv("STT_PROVIDER") == "groq":
            default_base = "https://api.groq.com/openai/v1"

        self.base_url = base_url or os.getenv("STT_BASE_URL") or default_base

        if "openrouter" in self.base_url:
            default_model = "openai/whisper-large-v3-turbo"
        elif "groq" in self.base_url:
            default_model = "whisper-large-v3"
        else:
            default_model = "whisper-1"

        self.model = model or os.getenv("STT_MODEL") or default_model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    def transcribe(self, audio_file_path: str, language: Optional[str] = None) -> STTResult:
        if not self.api_key:
            raise ValueError("STT API key is not configured. Set STT_API_KEY, OPENROUTER_API_KEY, or GROQ_API_KEY.")

        url = f"{self.base_url.rstrip('/')}/audio/transcriptions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        # Compress/prepare audio to avoid HTTP 413 Payload Too Large
        stt_path, mime_type, is_temp = _prepare_stt_audio(audio_file_path)

        last_error = None
        try:
            for attempt in range(1, self.max_retries + 1):
                try:
                    data = {
                        "model": self.model,
                        "response_format": "verbose_json",
                        "timestamp_granularities[]": ["word", "segment"],
                    }
                    if language:
                        data["language"] = language

                    with open(stt_path, "rb") as f:
                        files = {"file": (os.path.basename(stt_path), f, mime_type)}
                        with httpx.Client(timeout=self.timeout_seconds) as client:
                            response = client.post(url, headers=headers, data=data, files=files)
                            response.raise_for_status()
                            res_json = response.json()
                            return self._parse_response(res_json)
                except Exception as e:
                    last_error = e
                    logger.warning(f"STT request failed (attempt {attempt}/{self.max_retries}): {e}")
                    if attempt < self.max_retries:
                        time.sleep(2**attempt)

            raise RuntimeError(f"STT API transcription failed after {self.max_retries} attempts: {last_error}")
        finally:
            if is_temp and os.path.exists(stt_path):
                try:
                    os.unlink(stt_path)
                except Exception:
                    pass

    def _parse_response(self, data: dict) -> STTResult:
        full_text = data.get("text", "").strip()
        duration = float(data.get("duration", 0.0))
        language = data.get("language", "en")

        segments: List[STTSegment] = []
        words: List[STTWord] = []

        raw_words = data.get("words", [])
        for w in raw_words:
            w_text = w.get("word", "").strip()
            if w_text:
                words.append(
                    STTWord(
                        word=w_text,
                        start_time=float(w.get("start", 0.0)),
                        end_time=float(w.get("end", 0.0)),
                        confidence=float(w.get("confidence", 1.0) or 1.0),
                    )
                )

        raw_segments = data.get("segments", [])
        for seg in raw_segments:
            seg_start = float(seg.get("start", 0.0))
            seg_end = float(seg.get("end", 0.0))
            seg_text = seg.get("text", "").strip()

            seg_words = [w for w in words if seg_start <= w.start_time <= seg_end]

            segments.append(
                STTSegment(
                    id=int(seg.get("id", len(segments))),
                    start_time=seg_start,
                    end_time=seg_end,
                    text=seg_text,
                    words=seg_words,
                )
            )

        # Refine word timings if degenerate or if provider only gave segment-level timestamps
        for seg in segments:
            swords = [w for w in words if seg.start_time - 0.05 <= w.start_time <= seg.end_time + 0.05]
            if not swords:
                continue
            starts = [w.start_time for w in swords]
            # If all words have the same start time or 0 duration, distribute evenly across segment
            if len(set(starts)) <= 1 or any(w.end_time <= w.start_time for w in swords):
                seg_dur = max(0.2, seg.end_time - seg.start_time)
                step = seg_dur / len(swords)
                for idx, w in enumerate(swords):
                    w.start_time = round(seg.start_time + idx * step, 3)
                    w.end_time = round(w.start_time + step, 3)

        return STTResult(
            text=full_text,
            language=language,
            duration_seconds=duration,
            words=words,
            segments=segments,
            provider="openai_compatible",
        )
