import os
from backend.app.stt.base import STTProvider, STTResult, STTSegment, STTWord
from backend.app.stt.openai_provider import OpenAICompatibleSTTProvider
from backend.app.stt.deepgram_provider import DeepgramSTTProvider
from backend.app.stt.mock_provider import MockSTTProvider


def get_stt_provider(force_mock: bool = False) -> STTProvider:
    if force_mock:
        return MockSTTProvider()

    provider_name = os.getenv("STT_PROVIDER", "").lower()
    if provider_name == "mock":
        return MockSTTProvider()
    elif provider_name == "deepgram" or os.getenv("DEEPGRAM_API_KEY"):
        return DeepgramSTTProvider()
    elif (
        provider_name in ("openai", "groq", "openrouter")
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("GROQ_API_KEY")
        or os.getenv("OPENAI_API_KEY")
        or os.getenv("STT_API_KEY")
    ):
        return OpenAICompatibleSTTProvider()

    # Default to mock provider if no cloud keys configured
    return MockSTTProvider()


__all__ = [
    "STTProvider",
    "STTResult",
    "STTSegment",
    "STTWord",
    "OpenAICompatibleSTTProvider",
    "DeepgramSTTProvider",
    "MockSTTProvider",
    "get_stt_provider",
]

