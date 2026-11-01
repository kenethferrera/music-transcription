"""
OpenAI & Groq External Speech-to-Text Provider Adapter.
Uses standard /v1/audio/transcriptions endpoint with verbose_json and word timestamps.
"""
import base64
import logging
import os
import time
from typing import List, Optional
import httpx

from backend.app.stt.base import STTProvider, STTResult, STTSegment, STTWord

logger = logging.getLogger(__name__)


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

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                if "openrouter" in self.base_url:
                    # OpenRouter expects base64 JSON payload
                    with open(audio_file_path, "rb") as f:
                        b64_audio = base64.b64encode(f.read()).decode("utf-8")
                    payload = {
                        "model": self.model,
                        "input_audio": {"data": b64_audio, "format": "wav"},
                        "response_format": "verbose_json",
                        "timestamp_granularities": ["word", "segment"],
                    }
                    if language:
                        payload["language"] = language
                    with httpx.Client(timeout=self.timeout_seconds) as client:
                        response = client.post(url, headers=headers, json=payload)
                        response.raise_for_status()
                        res_json = response.json()
                        return self._parse_response(res_json)
                else:
                    # Standard multipart/form-data for OpenAI & Groq
                    data = {
                        "model": self.model,
                        "response_format": "verbose_json",
                        "timestamp_granularities[]": ["word", "segment"],
                    }
                    if language:
                        data["language"] = language

                    with open(audio_file_path, "rb") as f:
                        files = {"file": (os.path.basename(audio_file_path), f, "audio/wav")}
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
                    text=seg_text,
                    start_time=seg_start,
                    end_time=seg_end,
                    words=seg_words,
                )
            )

        # If provider returned segments but no word list, synthesize coarse words from segments
        if not words and segments:
            for seg in segments:
                tokens = seg.text.split()
                if not tokens:
                    continue
                step = (seg.end_time - seg.start_time) / len(tokens)
                for idx, token in enumerate(tokens):
                    w_start = seg.start_time + idx * step
                    w_end = w_start + step
                    words.append(
                        STTWord(
                            word=token,
                            start_time=w_start,
                            end_time=w_end,
                            confidence=0.8,
                        )
                    )

        return STTResult(
            text=full_text,
            language=language,
            duration_seconds=duration,
            segments=segments,
            words=words,
            provider="openai_compatible",
        )

