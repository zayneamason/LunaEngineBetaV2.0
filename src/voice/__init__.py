# Luna Engine Voice System
#
# Migrated from Eclissi Hub with key changes:
# - Piper TTS replaces Kokoro (no Docker required)
# - PersonaAdapter replaces HubClient (direct integration)
# - Full offline operation for sovereignty

from .conversation.state import (
    AudioBuffer,
    VoiceInfo,
    TranscriptionResult,
    ConversationPhase,
    Speaker,
    Turn,
    Message,
    ConversationState,
)
from .conversation.manager import ConversationManager
from .tts import TTSManager, TTSProviderType, TTSProvider
from .stt import STTManager, STTProviderType, STTProvider
from .audio.capture import AudioCapture
from .audio.playback import AudioPlayback
from .prosody import ProsodyMapper, ProsodyParameters
from .persona_adapter import PersonaAdapter, VoiceResponse
from .backend import VoiceBackend, VoiceActivityDetector

__all__ = [
    # Data types
    "AudioBuffer",
    "VoiceInfo",
    "TranscriptionResult",
    "ConversationPhase",
    "ConversationState",
    "Speaker",
    "Turn",
    "Message",
    "VoiceResponse",
    # Managers
    "ConversationManager",
    "TTSManager",
    "STTManager",
    # Provider types
    "TTSProviderType",
    "STTProviderType",
    # Protocols
    "TTSProvider",
    "STTProvider",
    # Audio
    "AudioCapture",
    "AudioPlayback",
    # Prosody
    "ProsodyMapper",
    "ProsodyParameters",
    # Adapters
    "PersonaAdapter",
    # Backend
    "VoiceBackend",
    "VoiceActivityDetector",
]
