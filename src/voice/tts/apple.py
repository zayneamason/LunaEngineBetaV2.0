"""
Apple TTS using macOS 'say' command.

Zero-setup option - uses macOS built-in voices.
Serves as fallback when Piper is unavailable.
"""
import logging
import asyncio
from typing import List, Optional
import subprocess
from pathlib import Path

from .provider import TTSProvider
from ..conversation.state import AudioBuffer, VoiceInfo

logger = logging.getLogger(__name__)


class AppleTTS(TTSProvider):
    """
    macOS native TTS using the 'say' command.

    Simple but effective. Uses system voices.
    Good fallback when neural TTS (Piper) is unavailable.
    """

    def __init__(self, voice: str = "Samantha", rate: int = 200):
        """
        Initialize Apple TTS.

        Args:
            voice: Voice name (run 'say -v ?' to list available voices)
            rate: Words per minute (default 200)
        """
        self.voice = voice
        self.rate = rate
        self._available = self._check_available()
        self._voices_cache: Optional[List[VoiceInfo]] = None

    def _check_available(self) -> bool:
        """Check if 'say' command is available (macOS only)."""
        try:
            result = subprocess.run(
                ["which", "say"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    async def synthesize(self, text: str, voice_id: Optional[str] = None) -> AudioBuffer:
        """
        Convert text to audio using macOS 'say' command.

        Args:
            text: Text to speak
            voice_id: Optional voice name override

        Returns:
            AudioBuffer with AIFF audio data
        """
        if not self._available:
            logger.error("Apple TTS not available (not on macOS?)")
            return AudioBuffer(data=b"", sample_rate=22050)

        voice = voice_id or self.voice

        try:
            import tempfile

            # Create temp file for audio output
            with tempfile.NamedTemporaryFile(suffix=".aiff", delete=False) as f:
                temp_path = f.name

            # Run 'say' command to generate audio file
            cmd = [
                "say",
                "-v", voice,
                "-r", str(self.rate),
                "-o", temp_path,
                text
            ]

            # Run async
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.wait()

            if process.returncode != 0:
                stderr = await process.stderr.read()
                logger.error(f"say command failed: {stderr.decode()}")
                return AudioBuffer(data=b"", sample_rate=22050)

            # Read the audio file
            audio_data = Path(temp_path).read_bytes()

            # Clean up temp file
            Path(temp_path).unlink(missing_ok=True)

            return AudioBuffer(
                data=audio_data,
                sample_rate=22050,  # Default for 'say' output
                channels=1,
                format="aiff"
            )

        except Exception as e:
            logger.error(f"TTS synthesis failed: {e}")
            return AudioBuffer(data=b"", sample_rate=22050)

    def get_voices(self) -> List[VoiceInfo]:
        """List available macOS voices."""
        if self._voices_cache is not None:
            return self._voices_cache

        if not self._available:
            return []

        try:
            # Run 'say -v ?' to get voice list
            result = subprocess.run(
                ["say", "-v", "?"],
                capture_output=True,
                text=True,
                timeout=10
            )

            voices = []
            for line in result.stdout.strip().split("\n"):
                if not line.strip():
                    continue
                # Format: "Name    language  # description"
                parts = line.split()
                if len(parts) >= 2:
                    name = parts[0]
                    lang = parts[1] if len(parts) > 1 else "en-US"
                    voices.append(VoiceInfo(
                        id=name,
                        name=name,
                        language=lang
                    ))

            self._voices_cache = voices
            return voices

        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            return []

    def is_available(self) -> bool:
        return self._available

    def get_name(self) -> str:
        return f"Apple TTS ({self.voice})"
