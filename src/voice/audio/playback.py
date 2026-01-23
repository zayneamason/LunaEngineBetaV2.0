"""
Audio playback to speaker using afplay (macOS).

Provides async audio output with format auto-detection.
"""
import logging
import asyncio
import tempfile
from pathlib import Path
from typing import Optional

from ..conversation.state import AudioBuffer

logger = logging.getLogger(__name__)


class AudioPlayback:
    """
    Plays audio to speaker using macOS afplay command.

    Features:
    - Async playback with non-blocking interface
    - Multiple format support (aiff, wav, mp3)
    - Playback state tracking
    - Interrupt/stop capability
    """

    def __init__(self):
        """Initialize audio playback."""
        self._process: Optional[asyncio.subprocess.Process] = None
        self._playing = False
        self._available = self._check_available()

    def _check_available(self) -> bool:
        """Check if afplay is available (macOS only)."""
        import subprocess
        try:
            result = subprocess.run(
                ["which", "afplay"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception:
            return False

    def is_available(self) -> bool:
        """Check if playback is available."""
        return self._available

    @property
    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._playing

    async def play(self, audio: AudioBuffer):
        """
        Play audio buffer.

        Args:
            audio: AudioBuffer containing audio data
        """
        if not self._available:
            logger.error("Audio playback not available (not on macOS?)")
            return

        if not audio.data:
            logger.warning("Empty audio buffer, nothing to play")
            return

        # Determine file extension from format
        ext_map = {
            "aiff": ".aiff",
            "wav": ".wav",
            "mp3": ".mp3",
            "pcm_s16le": ".wav",  # Will need WAV header
        }
        ext = ext_map.get(audio.format, ".wav")

        try:
            # Write to temp file
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                temp_path = f.name
                f.write(audio.data)

            # Play using afplay
            self._playing = True
            self._process = await asyncio.create_subprocess_exec(
                "afplay", temp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await self._process.wait()

            # Cleanup
            Path(temp_path).unlink(missing_ok=True)

        except asyncio.CancelledError:
            logger.info("Playback cancelled")
            await self.stop()
        except Exception as e:
            logger.error(f"Playback failed: {e}")
        finally:
            self._playing = False
            self._process = None

    async def play_file(self, file_path: str):
        """
        Play audio from file.

        Args:
            file_path: Path to audio file
        """
        if not self._available:
            logger.error("Audio playback not available")
            return

        if not Path(file_path).exists():
            logger.error(f"Audio file not found: {file_path}")
            return

        try:
            self._playing = True
            self._process = await asyncio.create_subprocess_exec(
                "afplay", file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await self._process.wait()

        except asyncio.CancelledError:
            await self.stop()
        except Exception as e:
            logger.error(f"Playback failed: {e}")
        finally:
            self._playing = False
            self._process = None

    async def stop(self):
        """Stop current playback."""
        if self._process and self._playing:
            try:
                self._process.terminate()
                await asyncio.wait_for(self._process.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                self._process.kill()
            except Exception as e:
                logger.error(f"Error stopping playback: {e}")
            finally:
                self._playing = False
                self._process = None
                logger.info("Playback stopped")
