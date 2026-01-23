"""
Piper TTS - Fast local neural text-to-speech for Luna Engine.

Piper is a lightweight neural TTS system that runs locally without Docker.
Quality is close to cloud TTS but fully offline and fast enough for real-time.

Setup:
    pip install piper-tts

Features:
    - 50+ voices across multiple languages
    - Real-time inference on CPU
    - Streaming support for low latency
    - Fully offline, no API calls
    - Models auto-download on first use (~20-50MB each)

Note:
    Piper synthesis is synchronous, so we wrap it in run_in_executor()
    for async compatibility. Models are cached after first download.
"""
import logging
import asyncio
import io
import wave
from typing import List, Optional, AsyncIterator
from concurrent.futures import ThreadPoolExecutor

from .provider import TTSProvider
from ..conversation.state import AudioBuffer, VoiceInfo

logger = logging.getLogger(__name__)

# Female voices for Luna (American and British English)
# Format: voice_id -> (display_name, language_code)
PIPER_FEMALE_VOICES = {
    # US Female voices
    "en_US-lessac-medium": ("Lessac (US)", "en-US"),      # Recommended default - natural sounding
    "en_US-amy-medium": ("Amy (US)", "en-US"),            # Clear and articulate
    "en_US-libritts-high": ("LibriTTS (US)", "en-US"),    # Best quality, slower

    # UK Female voices
    "en_GB-alba-medium": ("Alba (UK)", "en-GB"),
    "en_GB-jenny_dioco-medium": ("Jenny (UK)", "en-GB"),

    # Additional quality options
    "en_US-lessac-high": ("Lessac High (US)", "en-US"),   # Higher quality, slower
}

DEFAULT_VOICE = "en_US-lessac-medium"


class PiperTTS(TTSProvider):
    """
    Piper TTS provider - Fast local neural TTS.

    Uses the piper-tts Python package for high-quality offline synthesis.
    Models are automatically downloaded on first use.
    """

    def __init__(self, voice: str = DEFAULT_VOICE, speed: float = 1.0):
        """
        Initialize Piper TTS.

        Args:
            voice: Voice ID (e.g., "en_US-lessac-medium")
            speed: Speech rate multiplier (0.5-2.0, default 1.0)
        """
        self.voice = voice
        self.speed = max(0.5, min(2.0, speed))  # Clamp to valid range
        self._piper = None
        self._available = False
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="piper")

        # Try to initialize Piper
        self._init_piper()

    def _init_piper(self):
        """Initialize Piper TTS engine."""
        try:
            from piper import PiperVoice

            # Get model path - Piper auto-downloads models
            model_name = self._get_model_name(self.voice)

            logger.info(f"Initializing Piper TTS with voice: {self.voice}")
            logger.info(f"Model will be downloaded if not cached: {model_name}")

            # PiperVoice.load() handles model download and caching
            # Models are stored in ~/.local/share/piper/voices/
            self._piper = PiperVoice.load(model_name)
            self._available = True

            logger.info(f"Piper TTS initialized successfully: {self.voice}")

        except ImportError:
            logger.warning(
                "Piper TTS not available. Install with: pip install piper-tts"
            )
            self._available = False
        except Exception as e:
            logger.error(f"Failed to initialize Piper TTS: {e}")
            self._available = False

    def _get_model_name(self, voice_id: str) -> str:
        """
        Convert voice ID to Piper model name.

        Voice IDs follow pattern: language-voice-quality
        e.g., en_US-lessac-medium -> en_US/lessac/medium
        """
        # Piper expects model names like "en_US-lessac-medium"
        # The library handles path resolution internally
        return voice_id

    def _synthesize_sync(self, text: str) -> bytes:
        """
        Synchronous synthesis - runs in executor.

        Returns:
            WAV audio bytes
        """
        if not self._piper:
            return b""

        # Create in-memory WAV file
        wav_buffer = io.BytesIO()

        # Piper synthesize_to_file can write to file-like objects
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(22050)  # Piper default sample rate

            # Synthesize - yields audio chunks
            for audio_bytes in self._piper.synthesize_stream_raw(text):
                wav_file.writeframes(audio_bytes)

        return wav_buffer.getvalue()

    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None
    ) -> AudioBuffer:
        """
        Generate complete audio for text.

        Args:
            text: Text to synthesize
            voice_id: Optional voice override (not used - would require model reload)

        Returns:
            AudioBuffer with synthesized audio
        """
        if not self._available:
            logger.error("Piper TTS not available")
            return AudioBuffer(data=b"", sample_rate=22050)

        if not text.strip():
            return AudioBuffer(data=b"", sample_rate=22050)

        # Warn if voice_id differs (would need model reload)
        if voice_id and voice_id != self.voice:
            logger.warning(
                f"Voice override '{voice_id}' ignored - Piper requires model reload. "
                f"Using loaded voice: {self.voice}"
            )

        try:
            # Run synchronous synthesis in thread pool
            loop = asyncio.get_event_loop()
            audio_data = await loop.run_in_executor(
                self._executor,
                self._synthesize_sync,
                text
            )

            if not audio_data:
                logger.error("Piper synthesis returned empty audio")
                return AudioBuffer(data=b"", sample_rate=22050)

            return AudioBuffer(
                data=audio_data,
                sample_rate=22050,  # Piper default
                channels=1,
                format="wav"
            )

        except Exception as e:
            logger.error(f"Piper TTS synthesis failed: {e}", exc_info=True)
            return AudioBuffer(data=b"", sample_rate=22050)

    async def stream_synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None
    ) -> AsyncIterator[AudioBuffer]:
        """
        Stream audio chunks as they're generated.

        Piper supports streaming - yields chunks for lower latency.
        Each chunk is a raw PCM audio buffer.

        Args:
            text: Text to synthesize
            voice_id: Optional voice override (not used)

        Yields:
            AudioBuffer chunks
        """
        if not self._available or not self._piper:
            logger.error("Piper TTS not available for streaming")
            return

        if not text.strip():
            return

        try:
            # Stream synthesis - yields raw PCM chunks
            for audio_chunk in self._piper.synthesize_stream_raw(text):
                yield AudioBuffer(
                    data=audio_chunk,
                    sample_rate=22050,
                    channels=1,
                    format="pcm_s16le"  # Raw 16-bit PCM
                )

        except Exception as e:
            logger.error(f"Piper streaming synthesis failed: {e}", exc_info=True)

    def get_voices(self) -> List[VoiceInfo]:
        """Get available Piper voices (pre-defined female voices for Luna)."""
        voices = []
        for voice_id, (name, lang) in PIPER_FEMALE_VOICES.items():
            voices.append(VoiceInfo(
                id=voice_id,
                name=name,
                language=lang,
                gender="female"
            ))
        return voices

    def is_available(self) -> bool:
        """Check if Piper is available."""
        return self._available

    def get_name(self) -> str:
        """Get provider name."""
        return f"Piper ({self.voice})"

    def set_speed(self, speed: float):
        """
        Set speech rate.

        Args:
            speed: Rate multiplier (0.5-2.0)
        """
        self.speed = max(0.5, min(2.0, speed))

    def __del__(self):
        """Clean up executor on deletion."""
        if hasattr(self, '_executor'):
            self._executor.shutdown(wait=False)
