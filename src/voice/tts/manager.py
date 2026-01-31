"""
TTS Manager - Provider switching with fallback support for Luna Engine.

Allows runtime switching between TTS providers (Piper, Apple, Edge)
with automatic fallback to Apple if the selected provider fails.
Includes voice selection with female-only filtering for Luna.

Key difference from Eclissi: Uses Piper (no Docker) instead of Kokoro (Docker).
"""
import logging
from typing import Dict, List, Optional
from enum import Enum

from typing import TYPE_CHECKING

from .provider import TTSProvider
from .apple import AppleTTS
from .piper import PiperTTS, PIPER_FEMALE_VOICES
from .preprocessing import TextPreprocessor, PreprocessingConfig
from ..conversation.state import AudioBuffer, VoiceInfo

if TYPE_CHECKING:
    from luna.services.performance_state import VoiceKnobs

logger = logging.getLogger(__name__)

# Female voices for Apple TTS (macOS)
APPLE_FEMALE_VOICES = {
    "Samantha": "en-US",      # Luna default fallback
    "Karen": "en-AU",
    "Moira": "en-IE",
    "Tessa": "en-ZA",
    "Fiona": "en-GB",
    "Victoria": "en-US",
    "Allison": "en-US",
    "Ava": "en-US",
    "Susan": "en-US",
    "Zoe": "en-US",
    "Serena": "en-GB",
    "Kate": "en-GB",
}


class TTSProviderType(Enum):
    """Available TTS provider types."""
    PIPER = "piper"     # Primary - local neural TTS (no Docker)
    APPLE = "apple"     # Fallback - macOS built-in
    # KOKORO removed - requires Docker


class TTSManager:
    """
    Manages multiple TTS providers with fallback support.

    Features:
    - Runtime provider switching
    - Voice selection within each provider
    - Female-only voice filtering for Luna
    - Automatic fallback to Apple TTS if Piper fails
    - Settings persistence ready (exposes current_provider, current_voice)

    Default stack:
    1. Piper (primary) - High quality neural TTS, runs locally
    2. Apple (fallback) - Always available on macOS
    """

    def __init__(
        self,
        default_provider: TTSProviderType = TTSProviderType.PIPER,
        default_voice: str = "en_US-amy-medium",
        preprocessing_config: PreprocessingConfig = None
    ):
        """
        Initialize TTS Manager.

        Args:
            default_provider: Initial provider to use (default: Piper)
            default_voice: Initial voice to use (default: Piper's lessac)
            preprocessing_config: Config for text preprocessing (default: strip markdown/specials)
        """
        self._providers: Dict[TTSProviderType, TTSProvider] = {}
        self._current_type = default_provider
        self._current_voice = default_voice
        self._fallback_type = TTSProviderType.APPLE

        # Text preprocessor to clean special characters before synthesis
        self._preprocessor = TextPreprocessor(preprocessing_config)

        # Initialize providers
        self._init_providers()

        logger.info(
            f"TTSManager initialized with {self._current_type.value}, "
            f"voice: {self._current_voice}"
        )

    def _init_providers(self):
        """Initialize all available TTS providers."""
        # Apple TTS - always available on macOS (fallback)
        try:
            # Use Samantha for Apple (maps well from Piper voices)
            apple_voice = "Samantha"
            if self._current_voice in APPLE_FEMALE_VOICES:
                apple_voice = self._current_voice

            apple = AppleTTS(voice=apple_voice)
            if apple.is_available():
                self._providers[TTSProviderType.APPLE] = apple
                logger.info("Apple TTS initialized (fallback)")
        except Exception as e:
            logger.warning(f"Failed to initialize Apple TTS: {e}")

        # Piper TTS - local neural (PRIMARY)
        try:
            # Determine Piper voice
            piper_voice = self._current_voice
            if not piper_voice.startswith("en_"):
                # If current voice is Apple-style, use default Piper voice
                piper_voice = "en_US-amy-medium"

            piper = PiperTTS(voice=piper_voice)
            if piper.is_available():
                self._providers[TTSProviderType.PIPER] = piper
                logger.info(f"Piper TTS initialized (primary): {piper_voice}")
            else:
                logger.warning("Piper TTS not available - will use Apple fallback")
        except Exception as e:
            logger.warning(f"Failed to initialize Piper TTS: {e}")

    @property
    def current_provider(self) -> TTSProviderType:
        """Get current provider type."""
        return self._current_type

    @current_provider.setter
    def current_provider(self, provider_type: TTSProviderType):
        """Set current provider type."""
        if provider_type in self._providers:
            self._current_type = provider_type
            logger.info(f"Switched TTS provider to {provider_type.value}")
        else:
            logger.warning(
                f"Provider {provider_type.value} not available, "
                f"keeping {self._current_type.value}"
            )

    @property
    def current_voice(self) -> str:
        """Get current voice."""
        return self._current_voice

    @current_voice.setter
    def current_voice(self, voice_id: str):
        """Set current voice."""
        self._current_voice = voice_id

        # Update Apple TTS provider if it's the current one
        if self._current_type == TTSProviderType.APPLE:
            provider = self._providers.get(TTSProviderType.APPLE)
            if provider and isinstance(provider, AppleTTS):
                provider.voice = voice_id

        logger.info(f"Switched voice to {voice_id}")

    def set_provider(self, provider_name: str) -> bool:
        """
        Set provider by name string.

        Args:
            provider_name: "piper" or "apple"

        Returns:
            True if switch was successful
        """
        try:
            provider_type = TTSProviderType(provider_name.lower())
            if provider_type in self._providers:
                self._current_type = provider_type
                logger.info(f"Switched TTS provider to {provider_name}")
                return True
            else:
                logger.warning(f"Provider {provider_name} not available")
                return False
        except ValueError:
            logger.warning(f"Unknown provider: {provider_name}")
            return False

    def set_voice(self, voice_id: str) -> bool:
        """
        Set voice by ID.

        Args:
            voice_id: Voice identifier

        Returns:
            True if switch was successful
        """
        self.current_voice = voice_id
        return True

    def get_available_providers(self) -> List[Dict]:
        """
        Get list of available providers for UI dropdown.

        Returns:
            List of provider info dicts
        """
        all_providers = [
            {
                "id": "piper",
                "name": "Piper",
                "description": "Local neural TTS (no Docker)"
            },
            {
                "id": "apple",
                "name": "Apple TTS",
                "description": "macOS built-in voices"
            },
        ]

        result = []
        for p in all_providers:
            try:
                provider_type = TTSProviderType(p["id"])
                available = provider_type in self._providers
                provider = self._providers.get(provider_type)

                result.append({
                    "id": p["id"],
                    "name": provider.get_name() if provider else p["name"],
                    "description": p["description"],
                    "available": available,
                    "current": provider_type == self._current_type
                })
            except ValueError:
                pass  # Skip invalid provider types

        return result

    def get_available_voices(self, female_only: bool = True) -> List[Dict]:
        """
        Get list of available voices for UI dropdown.

        Args:
            female_only: If True, only return female voices (for Luna)

        Returns:
            List of voice info dicts
        """
        voices = []

        # Piper voices (primary)
        if TTSProviderType.PIPER in self._providers:
            for voice_id, (name, lang) in PIPER_FEMALE_VOICES.items():
                voices.append({
                    "id": voice_id,
                    "name": name,
                    "provider": "piper",
                    "language": lang,
                    "current": (
                        self._current_type == TTSProviderType.PIPER and
                        self._current_voice == voice_id
                    )
                })

        # Apple voices (fallback)
        if TTSProviderType.APPLE in self._providers:
            for voice_name, lang in APPLE_FEMALE_VOICES.items():
                voices.append({
                    "id": voice_name,
                    "name": voice_name,
                    "provider": "apple",
                    "language": lang,
                    "current": (
                        self._current_type == TTSProviderType.APPLE and
                        self._current_voice == voice_name
                    )
                })

        return voices

    def _get_provider(self) -> Optional[TTSProvider]:
        """Get current provider, falling back if needed."""
        # Try current provider
        provider = self._providers.get(self._current_type)
        if provider and provider.is_available():
            return provider

        # Fall back to Apple
        if self._current_type != self._fallback_type:
            logger.warning(
                f"{self._current_type.value} unavailable, falling back to Apple TTS"
            )
            fallback = self._providers.get(self._fallback_type)
            if fallback and fallback.is_available():
                return fallback

        return None

    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        skip_preprocessing: bool = False,
        voice_knobs: Optional["VoiceKnobs"] = None,
    ) -> AudioBuffer:
        """
        Synthesize text using current provider with fallback.

        Text is preprocessed to remove special characters and markdown
        that TTS engines would otherwise read aloud (e.g., "asterisk").

        Args:
            text: Text to synthesize
            voice_id: Optional voice override (uses current_voice if not specified)
            skip_preprocessing: If True, skip text preprocessing (default: False)
            voice_knobs: Optional voice modulation parameters (from PerformanceOrchestrator)

        Returns:
            AudioBuffer with audio data
        """
        provider = self._get_provider()
        voice = voice_id or self._current_voice

        if not provider:
            logger.error("No TTS provider available")
            return AudioBuffer(data=b"", sample_rate=22050)

        # Preprocess text to remove special characters
        if not skip_preprocessing:
            text = self._preprocessor.preprocess(text)

        if not text.strip():
            logger.debug("Text empty after preprocessing, skipping synthesis")
            return AudioBuffer(data=b"", sample_rate=22050)

        # Check if we're using fallback provider - need to use appropriate voice
        is_using_fallback = (
            self._current_type == TTSProviderType.PIPER and
            isinstance(provider, AppleTTS)
        )

        # If falling back to Apple, use a valid Apple voice
        if is_using_fallback and voice.startswith("en_"):
            voice = "Samantha"  # Default Apple voice for Luna

        try:
            # Pass voice_knobs to Piper if available
            if isinstance(provider, PiperTTS) and voice_knobs is not None:
                return await provider.synthesize(text, voice, voice_knobs)
            return await provider.synthesize(text, voice)
        except Exception as e:
            logger.error(f"TTS synthesis failed with {provider.get_name()}: {e}")

            # Try fallback
            if self._current_type != self._fallback_type:
                fallback = self._providers.get(self._fallback_type)
                if fallback:
                    logger.info("Attempting fallback to Apple TTS")
                    # Use Apple voice for fallback (doesn't support voice_knobs)
                    fallback_voice = "Samantha" if voice.startswith("en_") else voice
                    try:
                        return await fallback.synthesize(text, fallback_voice)
                    except Exception as e2:
                        logger.error(f"Fallback also failed: {e2}")

            return AudioBuffer(data=b"", sample_rate=22050)

    def get_voices(self) -> List[VoiceInfo]:
        """Get voices from current provider."""
        provider = self._get_provider()
        if provider:
            return provider.get_voices()
        return []

    def is_available(self) -> bool:
        """Check if any TTS provider is available."""
        return len(self._providers) > 0

    def get_name(self) -> str:
        """Get current provider name."""
        provider = self._get_provider()
        if provider:
            return provider.get_name()
        return "No TTS available"

    def get_state(self) -> dict:
        """Get manager state for API/UI."""
        return {
            "current_provider": self._current_type.value,
            "current_voice": self._current_voice,
            "available_providers": self.get_available_providers(),
            "available_voices": self.get_available_voices(female_only=True),
            "is_available": self.is_available()
        }
