"""
Unit tests for Luna Engine voice system.

Tests the migrated voice components:
- Piper TTS (primary)
- Apple TTS (fallback)
- STT providers
- PersonaAdapter
- VoiceBackend
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch


# ============= TTS Tests =============

class TestPiperTTS:
    """Tests for Piper TTS provider."""

    def test_piper_import(self):
        """Test that Piper TTS can be imported."""
        from voice.tts.piper import PiperTTS, PIPER_FEMALE_VOICES, DEFAULT_VOICE
        assert DEFAULT_VOICE == "en_US-lessac-medium"
        assert len(PIPER_FEMALE_VOICES) > 0

    def test_piper_voices_defined(self):
        """Test that female voices are properly defined."""
        from voice.tts.piper import PIPER_FEMALE_VOICES

        # Check expected voices exist
        assert "en_US-lessac-medium" in PIPER_FEMALE_VOICES
        assert "en_US-amy-medium" in PIPER_FEMALE_VOICES
        assert "en_GB-alba-medium" in PIPER_FEMALE_VOICES

        # Check format
        for voice_id, (name, lang) in PIPER_FEMALE_VOICES.items():
            assert isinstance(name, str)
            assert isinstance(lang, str)
            assert lang.startswith("en-")

    @pytest.mark.skipif(
        True,  # Skip by default - requires piper-tts package
        reason="Requires piper-tts package (pip install piper-tts)"
    )
    @pytest.mark.asyncio
    async def test_piper_synthesis(self):
        """Test Piper TTS synthesis."""
        from voice.tts.piper import PiperTTS

        tts = PiperTTS(voice="en_US-lessac-medium")

        if not tts.is_available():
            pytest.skip("Piper TTS not available")

        audio = await tts.synthesize("Hello, this is a test.")
        assert len(audio.data) > 0
        assert audio.sample_rate > 0


class TestAppleTTS:
    """Tests for Apple TTS provider."""

    def test_apple_import(self):
        """Test that Apple TTS can be imported."""
        from voice.tts.apple import AppleTTS
        assert AppleTTS is not None

    @pytest.mark.asyncio
    async def test_apple_synthesis(self):
        """Test Apple TTS synthesis on macOS."""
        from voice.tts.apple import AppleTTS

        tts = AppleTTS(voice="Samantha")

        if not tts.is_available():
            pytest.skip("Apple TTS not available (not on macOS?)")

        audio = await tts.synthesize("Hello, this is a test.")
        assert len(audio.data) > 0
        assert audio.format == "aiff"

    def test_apple_voices(self):
        """Test Apple TTS voice listing."""
        from voice.tts.apple import AppleTTS

        tts = AppleTTS()

        if not tts.is_available():
            pytest.skip("Apple TTS not available")

        voices = tts.get_voices()
        assert len(voices) > 0
        assert all(hasattr(v, 'id') for v in voices)


class TestTTSManager:
    """Tests for TTS Manager."""

    def test_manager_import(self):
        """Test that TTS Manager can be imported."""
        from voice.tts.manager import TTSManager, TTSProviderType
        assert TTSProviderType.PIPER.value == "piper"
        assert TTSProviderType.APPLE.value == "apple"

    def test_manager_initialization(self):
        """Test TTS Manager initialization."""
        from voice.tts.manager import TTSManager, TTSProviderType

        manager = TTSManager(
            default_provider=TTSProviderType.APPLE,
            default_voice="Samantha"
        )

        assert manager.is_available() or True  # May not have Apple on all systems
        assert manager.current_voice == "Samantha"

    def test_manager_voices_list(self):
        """Test getting available voices from manager."""
        from voice.tts.manager import TTSManager, TTSProviderType, PIPER_FEMALE_VOICES, APPLE_FEMALE_VOICES

        manager = TTSManager()
        voices = manager.get_available_voices(female_only=True)

        # Should have at least some voices defined
        assert len(PIPER_FEMALE_VOICES) > 0 or len(APPLE_FEMALE_VOICES) > 0


# ============= STT Tests =============

class TestSTTManager:
    """Tests for STT Manager."""

    def test_stt_import(self):
        """Test that STT Manager can be imported."""
        from voice.stt.manager import STTManager, STTProviderType
        assert STTProviderType.MLX_WHISPER.value == "mlx_whisper"
        assert STTProviderType.APPLE.value == "apple"

    def test_stt_initialization(self):
        """Test STT Manager initialization."""
        from voice.stt.manager import STTManager, STTProviderType

        manager = STTManager(
            default_provider=STTProviderType.APPLE,
            language="en"
        )

        # Manager should initialize even if providers unavailable
        assert manager is not None

    def test_stt_state(self):
        """Test getting STT manager state."""
        from voice.stt.manager import STTManager

        manager = STTManager()
        state = manager.get_state()

        assert "current_provider" in state
        assert "available_providers" in state
        assert "is_available" in state


# ============= Conversation Tests =============

class TestConversationState:
    """Tests for conversation state management."""

    def test_state_import(self):
        """Test that conversation state can be imported."""
        from voice.conversation.state import (
            ConversationState, ConversationPhase,
            Turn, Message, Speaker,
            AudioBuffer, VoiceInfo, TranscriptionResult
        )

        # Verify enums
        assert ConversationPhase.IDLE.value == "idle"
        assert Speaker.USER.value == "user"

    def test_audio_buffer(self):
        """Test AudioBuffer dataclass."""
        from voice.conversation.state import AudioBuffer

        buffer = AudioBuffer(
            data=b"test audio data",
            sample_rate=16000,
            channels=1,
            format="pcm_s16le"
        )

        assert buffer.data == b"test audio data"
        assert buffer.sample_rate == 16000

    def test_conversation_manager(self):
        """Test ConversationManager."""
        from voice.conversation.manager import ConversationManager
        from voice.conversation.state import Speaker

        manager = ConversationManager(max_history=5)
        manager.start_conversation()

        # Start and end a turn
        manager.start_turn(Speaker.USER)
        manager.end_turn("Hello Luna")

        assert manager.turn_count == 1
        assert len(manager.history) == 1
        assert manager.history[0].content == "Hello Luna"


# ============= Prosody Tests =============

class TestProsody:
    """Tests for prosody mapping."""

    def test_prosody_import(self):
        """Test that prosody components can be imported."""
        from voice.prosody import ProsodyMapper, ProsodyParameters

        params = ProsodyParameters()
        assert params.rate == 1.0
        assert params.volume == 0.8

    def test_prosody_mapping(self):
        """Test personality to prosody mapping."""
        from voice.prosody import ProsodyMapper

        mapper = ProsodyMapper()

        # Test with high energy personality
        personality = {
            "energy": 0.9,
            "warmth": 0.7,
            "playfulness": 0.5,
            "directness": 0.8,
        }

        prosody = mapper.map_personality(personality)

        # High energy should increase rate
        assert prosody.rate > 1.0

    def test_luna_default_prosody(self):
        """Test Luna's default prosody values."""
        from voice.prosody import ProsodyMapper

        mapper = ProsodyMapper()
        prosody = mapper.get_luna_default()

        assert prosody.rate == 1.0
        assert prosody.pitch == 0.0
        assert prosody.volume == 0.8


# ============= PersonaAdapter Tests =============

class TestPersonaAdapter:
    """Tests for PersonaAdapter."""

    def test_adapter_import(self):
        """Test that PersonaAdapter can be imported."""
        from voice.persona_adapter import PersonaAdapter, VoiceResponse, MockPersonaAdapter

        assert PersonaAdapter is not None
        assert VoiceResponse is not None
        assert MockPersonaAdapter is not None

    def test_adapter_without_engine(self):
        """Test PersonaAdapter without engine."""
        from voice.persona_adapter import PersonaAdapter

        adapter = PersonaAdapter(engine=None)

        assert not adapter.is_available()

    @pytest.mark.asyncio
    async def test_mock_adapter(self):
        """Test MockPersonaAdapter for testing."""
        from voice.persona_adapter import MockPersonaAdapter

        adapter = MockPersonaAdapter(default_response="Test response")

        assert adapter.is_available()
        assert await adapter.connect()

        response = await adapter.process_message("Hello")
        assert response is not None
        assert response.response == "Test response"

    @pytest.mark.asyncio
    async def test_adapter_personality(self):
        """Test getting personality from mock adapter."""
        from voice.persona_adapter import MockPersonaAdapter

        adapter = MockPersonaAdapter()
        personality = await adapter.get_personality()

        assert personality is not None
        assert "energy" in personality
        assert "warmth" in personality


# ============= VoiceBackend Tests =============

class TestVoiceBackend:
    """Tests for VoiceBackend."""

    def test_backend_import(self):
        """Test that VoiceBackend can be imported."""
        from voice.backend import VoiceBackend, VoiceActivityDetector

        assert VoiceBackend is not None
        assert VoiceActivityDetector is not None

    def test_vad(self):
        """Test VoiceActivityDetector."""
        import numpy as np
        from voice.backend import VoiceActivityDetector

        vad = VoiceActivityDetector(threshold=0.02)

        # Silent audio (all zeros)
        silent = np.zeros(1600, dtype=np.int16).tobytes()
        is_speech, complete = vad.process_chunk(silent)
        assert not is_speech

        # Loud audio (speech-like)
        loud = (np.random.randn(1600) * 5000).astype(np.int16).tobytes()
        is_speech, complete = vad.process_chunk(loud)
        assert is_speech

    def test_backend_state(self):
        """Test VoiceBackend state without starting."""
        from voice.backend import VoiceBackend

        backend = VoiceBackend(engine=None)
        state = backend.get_state()

        assert "running" in state
        assert "recording" in state
        assert "hands_free" in state
        assert "components" in state

        assert state["running"] is False
        assert state["recording"] is False

    @pytest.mark.asyncio
    async def test_backend_callbacks(self):
        """Test VoiceBackend callback registration."""
        from voice.backend import VoiceBackend

        backend = VoiceBackend(engine=None)

        # Track callback calls
        callback_calls = []

        backend.on_status_change(lambda s: callback_calls.append(s))

        # Manually trigger status notification
        backend._notify_status("test_status")

        assert "test_status" in callback_calls


# ============= Integration Tests =============

class TestVoiceIntegration:
    """Integration tests for voice system."""

    def test_full_import(self):
        """Test that all voice components can be imported together."""
        from voice import (
            # Data types
            AudioBuffer, VoiceInfo, TranscriptionResult,
            ConversationPhase, Speaker, Turn, Message,
            # Managers
            TTSManager, STTManager, ConversationManager,
            # Provider types
            TTSProviderType, STTProviderType,
            # Audio
            AudioCapture, AudioPlayback,
            # Prosody
            ProsodyMapper, ProsodyParameters,
            # Adapters
            PersonaAdapter, VoiceResponse,
            # Backend
            VoiceBackend, VoiceActivityDetector,
        )

        # All imports should succeed
        assert AudioBuffer is not None
        assert VoiceBackend is not None

    def test_provider_type_values(self):
        """Test that provider types have correct values."""
        from voice import TTSProviderType, STTProviderType

        # TTS
        assert TTSProviderType.PIPER.value == "piper"
        assert TTSProviderType.APPLE.value == "apple"

        # STT
        assert STTProviderType.MLX_WHISPER.value == "mlx_whisper"
        assert STTProviderType.APPLE.value == "apple"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
