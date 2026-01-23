"""
Speech Recognition using SpeechRecognition library.

Uses Google Speech Recognition (free tier) by default. Provides reliable
speech-to-text as a fallback when MLX-Whisper is unavailable.
"""
import logging
import asyncio
import tempfile
import wave
from pathlib import Path
from typing import Optional

from .provider import STTProvider
from ..conversation.state import TranscriptionResult

logger = logging.getLogger(__name__)


class AppleSTT(STTProvider):
    """
    Speech-to-text using the SpeechRecognition library.

    Uses Google's free speech recognition API by default.
    Named "AppleSTT" for backwards compatibility but uses Google API.
    """

    def __init__(self, language: str = "en-US", use_google: bool = True):
        """
        Initialize STT.

        Args:
            language: Language code (e.g., "en-US", "en-GB")
            use_google: Use Google Speech Recognition (requires internet)
        """
        self.language = language
        self.use_google = use_google
        self._available = False
        self._recognizer = None
        self._init_recognizer()

    def _init_recognizer(self):
        """Initialize the speech recognizer."""
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._available = True
            logger.info(f"SpeechRecognition STT initialized for {self.language}")
        except ImportError as e:
            logger.warning(f"SpeechRecognition not installed: {e}")
            self._available = False
        except Exception as e:
            logger.error(f"Failed to initialize STT: {e}")
            self._available = False

    async def transcribe(
        self,
        audio: bytes,
        sample_rate: int = 16000
    ) -> TranscriptionResult:
        """
        Transcribe audio using speech recognition.

        Args:
            audio: Raw PCM audio data (16-bit mono)
            sample_rate: Audio sample rate in Hz

        Returns:
            TranscriptionResult with transcribed text
        """
        if not self._available:
            logger.warning("STT not available")
            return TranscriptionResult(text="", confidence=0.0, is_final=True)

        if len(audio) < 1000:
            return TranscriptionResult(text="", confidence=0.0, is_final=True)

        try:
            # Write audio to temp WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                temp_path = f.name

            self._write_wav(temp_path, audio, sample_rate)

            # Run recognition in executor (blocking operation)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                self._recognize_file,
                temp_path
            )

            # Cleanup
            Path(temp_path).unlink(missing_ok=True)

            return result

        except Exception as e:
            logger.error(f"STT transcription failed: {e}")
            return TranscriptionResult(text="", confidence=0.0, is_final=True)

    def _write_wav(self, path: str, audio: bytes, sample_rate: int):
        """Write raw PCM to WAV file."""
        with wave.open(path, 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)  # 16-bit
            wav.setframerate(sample_rate)
            wav.writeframes(audio)

    def _recognize_file(self, file_path: str) -> TranscriptionResult:
        """Recognize speech from audio file."""
        try:
            import speech_recognition as sr

            with sr.AudioFile(file_path) as source:
                audio_data = self._recognizer.record(source)

            if self.use_google:
                # Use Google Speech Recognition (free, requires internet)
                try:
                    text = self._recognizer.recognize_google(
                        audio_data,
                        language=self.language
                    )
                    return TranscriptionResult(
                        text=text,
                        confidence=0.9,  # Google doesn't return confidence
                        is_final=True
                    )
                except sr.UnknownValueError:
                    logger.debug("Could not understand audio")
                    return TranscriptionResult(text="", confidence=0.0, is_final=True)
                except sr.RequestError as e:
                    logger.error(f"Google API error: {e}")
                    return TranscriptionResult(text="", confidence=0.0, is_final=True)
            else:
                # Use Sphinx (offline, less accurate)
                try:
                    text = self._recognizer.recognize_sphinx(audio_data)
                    return TranscriptionResult(
                        text=text,
                        confidence=0.7,
                        is_final=True
                    )
                except sr.UnknownValueError:
                    return TranscriptionResult(text="", confidence=0.0, is_final=True)

        except Exception as e:
            logger.error(f"File recognition failed: {e}")
            return TranscriptionResult(text="", confidence=0.0, is_final=True)

    def is_available(self) -> bool:
        return self._available

    def get_name(self) -> str:
        if self._available:
            backend = "Google" if self.use_google else "Sphinx"
            return f"Speech Recognition ({backend}, {self.language})"
        return "Speech Recognition (unavailable)"


class MockSTT(STTProvider):
    """
    Mock STT for testing without audio hardware.

    Returns predefined responses for testing the voice pipeline.
    """

    def __init__(self, default_text: str = "Hello Luna"):
        self.default_text = default_text
        self._available = True

    async def transcribe(
        self,
        audio: bytes,
        sample_rate: int = 16000
    ) -> TranscriptionResult:
        """Return mock transcription."""
        if len(audio) < 1000:  # Very short audio = silence
            return TranscriptionResult(text="", confidence=0.0, is_final=True)

        return TranscriptionResult(
            text=self.default_text,
            confidence=0.95,
            is_final=True
        )

    def is_available(self) -> bool:
        return self._available

    def get_name(self) -> str:
        return "Mock STT (testing)"
