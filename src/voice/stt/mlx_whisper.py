"""
MLX-Whisper STT provider for ultra-fast local transcription on Apple Silicon.

Uses MLX-optimized Whisper models for real-time transcription with minimal latency.
Runs entirely on-device, no internet required.
"""
import logging
import asyncio
import tempfile
import wave
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Optional

from .provider import STTProvider
from ..conversation.state import TranscriptionResult

logger = logging.getLogger(__name__)

# Module-level function for ProcessPoolExecutor (must be picklable)
def _transcribe_in_process(file_path: str, model_name: str, language: str) -> dict:
    """Run MLX-Whisper transcription in a separate process to avoid GIL blocking."""
    import mlx_whisper
    result = mlx_whisper.transcribe(
        file_path,
        path_or_hf_repo=model_name,
        language=language
    )
    if isinstance(result, dict):
        text = result.get("text", "").strip()
    else:
        text = str(result).strip()
    return {"text": text}


class MLXWhisperSTT(STTProvider):
    """
    Speech-to-text using MLX-Whisper (optimized for Apple Silicon).

    Provides ultra-fast local transcription using Metal acceleration.
    No internet required, all processing happens on-device.
    """

    def __init__(
        self,
        model: str = "mlx-community/whisper-tiny-mlx",
        language: str = "en"
    ):
        """
        Initialize MLX-Whisper STT.

        Args:
            model: Model identifier (tiny, base, small, medium, large)
            language: Language code (e.g., "en", "es", "fr")
        """
        self.model_name = model
        self.language = language
        self._available = False
        self._model = None
        self._process_pool = ProcessPoolExecutor(max_workers=1)
        self._init_model()

    def _init_model(self):
        """Initialize the MLX-Whisper model."""
        try:
            import mlx_whisper

            # MLX-Whisper lazy-loads models on first use
            # We just verify the library is available
            self._mlx_whisper = mlx_whisper
            self._available = True
            logger.info(
                f"MLX-Whisper STT initialized "
                f"(model: {self.model_name}, language: {self.language})"
            )

        except ImportError as e:
            logger.warning(f"MLX-Whisper not installed: {e}")
            self._available = False
        except Exception as e:
            logger.error(f"Failed to initialize MLX-Whisper: {e}")
            self._available = False

    async def transcribe(
        self,
        audio: bytes,
        sample_rate: int = 16000
    ) -> TranscriptionResult:
        """
        Transcribe audio using MLX-Whisper.

        Args:
            audio: Raw PCM audio data (16-bit mono)
            sample_rate: Audio sample rate in Hz (MLX-Whisper expects 16kHz)

        Returns:
            TranscriptionResult with transcribed text
        """
        if not self._available:
            logger.warning("MLX-Whisper not available")
            return TranscriptionResult(text="", confidence=0.0, is_final=True)

        # Minimum ~0.3 seconds of audio (16kHz * 2 bytes * 0.3s = ~9600 bytes)
        if len(audio) < 9600:
            logger.warning(f"Audio too short for transcription: {len(audio)} bytes ({len(audio)/(16000*2):.2f}s)")
            return TranscriptionResult(text="", confidence=0.0, is_final=True)

        try:
            # Write audio to temp WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name

            self._write_wav(temp_path, audio, sample_rate)

            # Run in a separate process — MLX Metal ops hold the GIL,
            # which blocks the asyncio event loop if run in a thread.
            loop = asyncio.get_event_loop()
            raw = await loop.run_in_executor(
                self._process_pool,
                _transcribe_in_process,
                temp_path,
                self.model_name,
                self.language
            )

            # Cleanup
            Path(temp_path).unlink(missing_ok=True)

            text = raw.get("text", "")
            if not text:
                logger.debug("MLX-Whisper returned empty transcription")
                return TranscriptionResult(text="", confidence=0.0, is_final=True)

            return TranscriptionResult(text=text, confidence=0.95, is_final=True)

        except Exception as e:
            logger.error(f"MLX-Whisper transcription failed: {e}")
            return TranscriptionResult(text="", confidence=0.0, is_final=True)

    def _write_wav(self, path: str, audio: bytes, sample_rate: int):
        """Write raw PCM to WAV file."""
        with wave.open(path, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(sample_rate)
            wav.writeframes(audio)

    def is_available(self) -> bool:
        return self._available

    def get_name(self) -> str:
        if self._available:
            return f"MLX-Whisper ({self.model_name}, {self.language})"
        return "MLX-Whisper (unavailable)"
