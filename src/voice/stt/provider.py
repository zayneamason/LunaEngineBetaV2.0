"""
Speech-to-Text provider protocol for Luna Engine.
"""
from typing import Protocol, runtime_checkable

from ..conversation.state import TranscriptionResult


@runtime_checkable
class STTProvider(Protocol):
    """Abstract interface for speech-to-text providers."""

    async def transcribe(self, audio: bytes, sample_rate: int = 16000) -> TranscriptionResult:
        """
        Transcribe audio to text.

        Args:
            audio: Raw PCM audio data (16-bit mono)
            sample_rate: Audio sample rate in Hz

        Returns:
            TranscriptionResult with transcribed text
        """
        ...

    def is_available(self) -> bool:
        """Check if provider is ready."""
        ...

    def get_name(self) -> str:
        """Provider name for logging."""
        ...
