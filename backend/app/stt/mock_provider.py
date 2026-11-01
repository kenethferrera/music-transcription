"""
Deterministic Mock STT Provider for unit and integration testing.
"""
from typing import List, Optional
from backend.app.stt.base import STTProvider, STTResult, STTSegment, STTWord


class MockSTTProvider(STTProvider):
    """
    Mock STT provider for offline test suites.
    Generates predictable lyrics and timestamps matching provided test durations.
    """

    def __init__(self, sample_lyrics: Optional[str] = None):
        self.sample_lyrics = sample_lyrics or "Hello darkness my old friend I have come to talk with you again"

    def transcribe(self, audio_file_path: str, language: Optional[str] = None) -> STTResult:
        tokens = self.sample_lyrics.split()
        duration = 10.0
        step = duration / (len(tokens) + 1)

        words: List[STTWord] = []
        for i, token in enumerate(tokens):
            start = 0.5 + i * step
            end = start + step * 0.8
            words.append(STTWord(word=token, start_time=round(start, 2), end_time=round(end, 2), confidence=0.95))

        segment = STTSegment(
            id=0,
            text=self.sample_lyrics,
            start_time=words[0].start_time,
            end_time=words[-1].end_time,
            words=words,
        )

        return STTResult(
            text=self.sample_lyrics,
            language=language or "en",
            duration_seconds=duration,
            segments=[segment],
            words=words,
            provider="mock",
        )

