"""
STT Manager - Provider switching with fallback support for Luna Engine.

Allows runtime switching between STT providers with automatic fallback.
Default cascade: MLX-Whisper → Apple/Google → (fail gracefully)
"""
import logging
from typing import Dict, Optional
from enum import Enum

from .provider import STTProvider
from .mlx_whisper import MLXWhisperSTT
from .apple import AppleSTT
from ..conversation.state import TranscriptionResult

logger = logging.getLogger(__name__)


class STTProviderType(Enum):
    """Available STT provider types."""
    MLX_WHISPER = "mlx_whisper"  # Primary - local, Apple Silicon optimized
    APPLE = "apple"              # Fallback - Google Speech Recognition


class STTManager:
    """
    Manages multiple STT providers with fallback support.

    Features:
    - Runtime provider switching
    - Automatic fallback cascade
    - Provider availability detection

    Default cascade:
    1. MLX-Whisper (local, fast, Apple Silicon)
    2. Apple STT (Google Speech Recognition, requires internet)
    """

    def __init__(
        self,
        default_provider: STTProviderType = STTProviderType.MLX_WHISPER,
        language: str = "en"
    ):
        """
        Initialize STT Manager.

        Args:
            default_provider: Initial provider to use
            language: Language code for transcription
        """
        self._providers: Dict[STTProviderType, STTProvider] = {}
        self._current_type = default_provider
        self._language = language

        # Initialize providers
        self._init_providers()

        logger.info(f"STTManager initialized with {self._current_type.value}")

    def _init_providers(self):
        """Initialize all available STT providers."""
        # MLX-Whisper - primary (local, Apple Silicon)
        try:
            mlx = MLXWhisperSTT(language=self._language)
            if mlx.is_available():
                self._providers[STTProviderType.MLX_WHISPER] = mlx
                logger.info("MLX-Whisper STT initialized (primary)")
            else:
                logger.warning("MLX-Whisper not available")
        except Exception as e:
            logger.warning(f"Failed to initialize MLX-Whisper: {e}")

        # Apple/Google STT - fallback
        try:
            apple = AppleSTT(
                language=f"{self._language}-US" if "-" not in self._language else self._language
            )
            if apple.is_available():
                self._providers[STTProviderType.APPLE] = apple
                logger.info("Apple/Google STT initialized (fallback)")
            else:
                logger.warning("Apple STT not available")
        except Exception as e:
            logger.warning(f"Failed to initialize Apple STT: {e}")

    @property
    def current_provider(self) -> STTProviderType:
        """Get current provider type."""
        return self._current_type

    @current_provider.setter
    def current_provider(self, provider_type: STTProviderType):
        """Set current provider type."""
        if provider_type in self._providers:
            self._current_type = provider_type
            logger.info(f"Switched STT provider to {provider_type.value}")
        else:
            logger.warning(
                f"Provider {provider_type.value} not available, "
                f"keeping {self._current_type.value}"
            )

    def set_provider(self, provider_name: str) -> bool:
        """
        Set provider by name string.

        Args:
            provider_name: "mlx_whisper" or "apple"

        Returns:
            True if switch was successful
        """
        try:
            provider_type = STTProviderType(provider_name.lower())
            if provider_type in self._providers:
                self._current_type = provider_type
                logger.info(f"Switched STT provider to {provider_name}")
                return True
            else:
                logger.warning(f"Provider {provider_name} not available")
                return False
        except ValueError:
            logger.warning(f"Unknown provider: {provider_name}")
            return False

    def _get_provider(self) -> Optional[STTProvider]:
        """Get current provider, falling back if needed."""
        # Try current provider
        provider = self._providers.get(self._current_type)
        if provider and provider.is_available():
            return provider

        # Fall back through providers
        for ptype in STTProviderType:
            if ptype != self._current_type:
                fallback = self._providers.get(ptype)
                if fallback and fallback.is_available():
                    logger.warning(
                        f"{self._current_type.value} unavailable, "
                        f"falling back to {ptype.value}"
                    )
                    return fallback

        return None

    async def transcribe(
        self,
        audio: bytes,
        sample_rate: int = 16000
    ) -> TranscriptionResult:
        """
        Transcribe audio using current provider with fallback.

        Args:
            audio: Raw PCM audio data (16-bit mono)
            sample_rate: Audio sample rate in Hz

        Returns:
            TranscriptionResult with transcribed text
        """
        provider = self._get_provider()

        if not provider:
            logger.error("No STT provider available")
            return TranscriptionResult(text="", confidence=0.0, is_final=True)

        try:
            return await provider.transcribe(audio, sample_rate)
        except Exception as e:
            logger.error(f"STT transcription failed with {provider.get_name()}: {e}")

            # Try fallback
            for ptype in STTProviderType:
                if ptype != self._current_type:
                    fallback = self._providers.get(ptype)
                    if fallback:
                        try:
                            logger.info(f"Attempting fallback to {ptype.value}")
                            return await fallback.transcribe(audio, sample_rate)
                        except Exception as e2:
                            logger.error(f"Fallback {ptype.value} also failed: {e2}")

            return TranscriptionResult(text="", confidence=0.0, is_final=True)

    def is_available(self) -> bool:
        """Check if any STT provider is available."""
        return len(self._providers) > 0

    def get_name(self) -> str:
        """Get current provider name."""
        provider = self._get_provider()
        if provider:
            return provider.get_name()
        return "No STT available"

    def get_state(self) -> dict:
        """Get manager state for API/UI."""
        available = []
        for ptype, provider in self._providers.items():
            available.append({
                "id": ptype.value,
                "name": provider.get_name(),
                "available": provider.is_available(),
                "current": ptype == self._current_type
            })

        return {
            "current_provider": self._current_type.value,
            "available_providers": available,
            "is_available": self.is_available()
        }
