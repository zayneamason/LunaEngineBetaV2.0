"""
Piper TTS Provider - Uses vendored Piper binary for synthesis.

This wraps the Piper CLI binary rather than the Python package,
ensuring we use the proven, version-locked binary at:
    src/voice/piper_bin/piper/piper

Architecture:
    TTSManager → PiperTTS.synthesize() → subprocess → binary → WAV bytes

The binary approach is more reliable than the Python package because:
1. No PyPI dependency issues (piper-tts package was never installed)
2. Version-locked at Piper 1.2.0
3. Proven code path (this is how it originally worked)

Voice Knobs (from Performance Layer):
- length_scale: Speed control (0.5 = 2x fast, 2.0 = half speed)
- noise_scale: Expressiveness (0 = monotone, 1 = expressive)
- noise_w: Rhythm variation (0 = robotic, 1 = natural)
- sentence_silence: Pause between sentences (seconds)
"""
import asyncio
import logging
import os
import struct
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING

from .provider import TTSProvider
from ..conversation.state import AudioBuffer, VoiceInfo

if TYPE_CHECKING:
    from luna.services.performance_state import VoiceKnobs

logger = logging.getLogger(__name__)

# Vendored binary location
# Path: src/voice/piper_bin/piper/piper
try:
    from luna.core.paths import project_root as _project_root
    _SRC_DIR = _project_root() / "src"
except ImportError:
    _SRC_DIR = Path(__file__).parent.parent.parent  # src/ (fallback)
PIPER_BIN_DIR = _SRC_DIR / "voice" / "piper_bin" / "piper"
PIPER_BINARY = PIPER_BIN_DIR / "piper"

# Model locations to search
MODEL_SEARCH_PATHS = [
    _SRC_DIR / "voice" / "piper_models",  # Primary: src/voice/piper_models/
    _SRC_DIR / "voice" / "piper_bin" / "models",  # Alternative location
    Path.home() / ".local" / "share" / "piper" / "voices",
    Path.home() / "Library" / "Caches" / "piper",
]

# Female voices for Luna (American and British English)
PIPER_FEMALE_VOICES = {
    "en_US-lessac-medium": ("Lessac (US)", "en-US"),
    "en_US-amy-medium": ("Amy (US)", "en-US"),
    "en_US-libritts-high": ("LibriTTS (US)", "en-US"),
    "en_GB-alba-medium": ("Alba (UK)", "en-GB"),
    "en_GB-jenny_dioco-medium": ("Jenny (UK)", "en-GB"),
    "en_US-lessac-high": ("Lessac High (US)", "en-US"),
}

DEFAULT_VOICE = "en_US-amy-medium"


class PiperTTS(TTSProvider):
    """
    Piper TTS using vendored binary.

    Calls the Piper CLI binary via subprocess for synthesis.
    Binary outputs raw PCM which we wrap in WAV format.
    """

    def __init__(self, voice: str = DEFAULT_VOICE, speed: float = 1.0):
        """
        Initialize Piper TTS.

        Args:
            voice: Voice ID (e.g., "en_US-lessac-medium")
            speed: Speech rate multiplier (0.5-2.0, default 1.0)
        """
        self.voice = voice
        self.speed = max(0.5, min(2.0, speed))
        self._binary_path = self._find_binary()
        self._model_path = self._find_model(voice)
        self._available = self._binary_path is not None and self._model_path is not None

        if self._available:
            logger.info(f"PiperTTS initialized: binary={self._binary_path}, model={self._model_path}")
        else:
            logger.warning(f"PiperTTS not available: binary={self._binary_path}, model={self._model_path}")

    def _find_binary(self) -> Optional[Path]:
        """Locate the Piper binary."""
        if PIPER_BINARY.exists() and os.access(PIPER_BINARY, os.X_OK):
            return PIPER_BINARY
        logger.error(f"Piper binary not found at {PIPER_BINARY}")
        return None

    def _find_model(self, voice_id: str) -> Optional[Path]:
        """Locate the ONNX model file for a voice."""
        model_filename = f"{voice_id}.onnx"

        for search_dir in MODEL_SEARCH_PATHS:
            if not search_dir.exists():
                continue

            # Direct path: search_dir/voice_id.onnx
            model_path = search_dir / model_filename
            if model_path.exists():
                logger.debug(f"Found model at {model_path}")
                return model_path

            # Nested structure: search_dir/en/en_US/voice/quality/
            # Some Piper installations use this structure
            parts = voice_id.split("-")
            if len(parts) >= 2:
                lang_region = parts[0]  # e.g., "en_US"
                lang = lang_region.split("_")[0] if "_" in lang_region else lang_region
                nested_path = search_dir / lang / lang_region
                if nested_path.exists():
                    for onnx in nested_path.rglob("*.onnx"):
                        if voice_id in str(onnx):
                            logger.debug(f"Found model at {onnx}")
                            return onnx

        logger.warning(f"Model not found for voice {voice_id} in {MODEL_SEARCH_PATHS}")
        return None

    def is_available(self) -> bool:
        """Check if Piper is available."""
        return self._available

    async def synthesize(
        self,
        text: str,
        voice_id: Optional[str] = None,
        voice_knobs: Optional["VoiceKnobs"] = None,
    ) -> AudioBuffer:
        """
        Synthesize text to audio using Piper binary.

        Args:
            text: Text to synthesize (should already be preprocessed)
            voice_id: Optional voice override (not used - would require model reload)
            voice_knobs: Optional voice modulation parameters (from PerformanceOrchestrator)

        Returns:
            AudioBuffer with WAV audio data
        """
        if not self._available:
            logger.error("PiperTTS not available")
            return AudioBuffer(data=b"", sample_rate=22050)

        if not text.strip():
            return AudioBuffer(data=b"", sample_rate=22050)

        # Warn if voice_id differs
        if voice_id and voice_id != self.voice:
            logger.warning(
                f"Voice override '{voice_id}' ignored - Piper requires model reload. "
                f"Using loaded voice: {self.voice}"
            )

        try:
            # Build command
            # Piper CLI: echo "text" | piper --model path.onnx --output_raw
            cmd = [
                str(self._binary_path),
                "--model", str(self._model_path),
                "--output_raw",  # Output raw PCM to stdout
            ]

            # Add voice knobs if provided (from Performance Layer)
            if voice_knobs is not None:
                cmd.extend(voice_knobs.to_piper_args())
            elif self.speed != 1.0:
                # Fallback to legacy speed parameter
                # (length_scale: >1 = slower, <1 = faster)
                cmd.extend(["--length_scale", str(1.0 / self.speed)])

            logger.debug(f"Running Piper: {' '.join(cmd)}")

            # Run subprocess asynchronously
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, "DYLD_LIBRARY_PATH": str(PIPER_BIN_DIR)},
            )

            # Send text via stdin
            stdout, stderr = await process.communicate(input=text.encode('utf-8'))

            if process.returncode != 0:
                logger.error(f"Piper failed (code {process.returncode}): {stderr.decode()}")
                return AudioBuffer(data=b"", sample_rate=22050)

            if not stdout:
                logger.error("Piper returned no audio data")
                return AudioBuffer(data=b"", sample_rate=22050)

            # Piper outputs raw 16-bit PCM at 22050Hz mono
            # Wrap in WAV header for playback compatibility
            wav_bytes = self._pcm_to_wav(stdout, sample_rate=22050, channels=1, sample_width=2)

            logger.debug(f"Piper synthesized {len(wav_bytes)} bytes of audio")

            return AudioBuffer(
                data=wav_bytes,
                sample_rate=22050,
                channels=1,
                format="wav"
            )

        except Exception as e:
            logger.error(f"PiperTTS synthesis error: {e}", exc_info=True)
            return AudioBuffer(data=b"", sample_rate=22050)

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

    def _pcm_to_wav(self, pcm_data: bytes, sample_rate: int, channels: int, sample_width: int) -> bytes:
        """
        Wrap raw PCM data in a WAV header.

        Args:
            pcm_data: Raw PCM audio bytes
            sample_rate: Samples per second (e.g., 22050)
            channels: Number of channels (1 for mono)
            sample_width: Bytes per sample (2 for 16-bit)

        Returns:
            Complete WAV file as bytes
        """
        data_size = len(pcm_data)
        byte_rate = sample_rate * channels * sample_width
        block_align = channels * sample_width
        bits_per_sample = sample_width * 8

        # WAV header (44 bytes)
        header = struct.pack(
            '<4sI4s4sIHHIIHH4sI',
            b'RIFF',
            data_size + 36,           # File size - 8
            b'WAVE',
            b'fmt ',
            16,                       # Subchunk1 size (PCM)
            1,                        # Audio format (1 = PCM)
            channels,
            sample_rate,
            byte_rate,
            block_align,
            bits_per_sample,
            b'data',
            data_size,
        )

        return header + pcm_data
