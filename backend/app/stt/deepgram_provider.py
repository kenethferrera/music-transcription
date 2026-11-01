"""
Deepgram External Speech-to-Text Provider Adapter.
"""
import logging
import os
import time
from typing import List, Optional
import httpx

from backend.app.stt.base import STTProvider, STTResult, STTSegment, STTWord

logger = logging.getLogger(__name__)


class DeepgramSTTProvider(STTProvider):
    """Deepgram cloud speech recognition adapter."""

    def __init__(self, api_key: Optional[str] = None, timeout_seconds: float = 120.0):
        self.api_key = api_key or os.getenv("DEEPGRAM_API_KEY")
        self.timeout_seconds = timeout_seconds

    def transcribe(self, audio_file_path: str, language: Optional[str] = None) -> STTResult:
        if not self.api_key:
            raise ValueError("Deepgram API key not provided. Set DEEPGRAM_API_KEY.")

        url = "https://api.deepgram.com/v1/listen?model=nova-2&smart_format=true&punctuate=true&utterances=true"
        if language:
            url += f"&language={language}"

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "audio/wav",
        }

        with open(audio_file_path, "rb") as f:
            audio_data = f.read()

        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(url, headers=headers, content=audio_data)
            response.raise_for_status()
            res_json = response.json()

        results = res_json.get("results", {})
        channels = results.get("channels", [{}])
        first_channel = channels[0] if channels else {}
        alternatives = first_channel.get("alternatives", [{}])
        alt = alternatives[0] if alternatives else {}

        full_text = alt.get("transcript", "")
        words: List[STTWord] = []
        for w in alt.get("words", []):
            words.append(
                STTWord(
                    word=w.get("word", ""),
                    start_time=float(w.get("start", 0.0)),
                    end_time=float(w.get("end", 0.0)),
                    confidence=float(w.get("confidence", 1.0)),
                )
            )

        segments: List[STTSegment] = []
        utterances = results.get("utterances", [])
        for idx, u in enumerate(utterances):
            u_start = float(u.get("start", 0.0))
            u_end = float(u.get("end", 0.0))
            seg_words = [w for w in words if u_start <= w.start_time <= u_end]
            segments.append(
                STTSegment(
                    id=idx,
                    text=u.get("transcript", ""),
                    start_time=u_start,
                    end_time=u_end,
                    words=seg_words,
                )
            )

        return STTResult(
            text=full_text,
            language=language or "en",
            duration_seconds=float(res_json.get("metadata", {}).get("duration", 0.0)),
            segments=segments,
            words=words,
            provider="deepgram",
        )

