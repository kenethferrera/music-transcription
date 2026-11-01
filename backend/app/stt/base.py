"""
External STT API Provider Interface
Strict rule: Uses external API only. No local Whisper weights.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from pydantic import BaseModel, Field


class STTWord(BaseModel):
    word: str
    start_time: float
    end_time: float
    confidence: float = 1.0


class STTSegment(BaseModel):
    id: int
    text: str
    start_time: float
    end_time: float
    words: List[STTWord] = Field(default_factory=list)


class STTResult(BaseModel):
    text: str
    language: Optional[str] = "en"
    duration_seconds: float
    segments: List[STTSegment] = Field(default_factory=list)
    words: List[STTWord] = Field(default_factory=list)
    provider: str


class STTProvider(ABC):
    @abstractmethod
    def transcribe(self, audio_file_path: str, language: Optional[str] = None) -> STTResult:
        """
        Transcribe the audio using external STT API.
        Extracts words and segment timestamps.
        """
        pass

