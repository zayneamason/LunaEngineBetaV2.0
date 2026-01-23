"""
Text-to-Speech provider protocol for Luna Engine.
"""
from typing import Protocol, List, Optional, runtime_checkable

from ..conversation.state import AudioBuffer, VoiceInfo


@runtime_checkable
class TTSProvider(Protocol):
    """Abstract interface for text-to-speech providers."""

    async def synthesize(self, text: str, voice_id: Optional[str] = None) -> AudioBuffer:
        """Convert text to audio."""
        ...

    def get_voices(self) -> List[VoiceInfo]:
        """List available voices."""
        ...

    def is_available(self) -> bool:
        """Check if provider is ready."""
        ...

    def get_name(self) -> str:
        """Provider name for logging."""
        ...
