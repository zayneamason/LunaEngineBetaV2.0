# HANDOFF: PiperTTS Binary Wrapper Implementation

**Date:** 2025-01-27
**From:** Architecture Session (Claude.ai)
**To:** Claude Code
**Priority:** High - Voice system broken

---

## Problem Statement

Luna's TTS stopped working and fell back to Apple's Samantha voice. Root cause: a previous CC session rewrote `backend.py:speak()` to route through `TTSManager`, but `PiperTTS` class was written to use `piper-tts` Python package which was **never installed**. The system had always used a **vendored Piper binary** via subprocess.

### What Broke

```
BEFORE (working):
  speak() → subprocess.run([piper_binary, ...]) → audio

AFTER (broken):
  speak() → TTSManager → PiperTTS → "from piper import PiperVoice" → ImportError → Apple TTS fallback
```

### Evidence

- Working binary exists: `src/voice/piper_bin/piper/piper` (v1.2.0)
- Binary test passes: `./piper --version` → `1.2.0`
- Python package not installed: `pip list | grep piper` → (empty)
- Ahab confirms Piper voice was working until this session

---

## Solution: Rewrite PiperTTS to Use Binary

Rewrite `src/voice/tts/piper.py` to call the vendored binary via subprocess instead of importing the Python package. This maintains the TTSManager abstraction (so preprocessing still works) while using the proven binary.

### Architecture

```
TTSManager.synthesize(text)
    ↓
preprocess_for_speech(text)  # Strips *, #, ~, etc.
    ↓
PiperTTS.synthesize(clean_text)
    ↓
subprocess.run([PIPER_BINARY, "--model", model, "--output_raw", "-"])
    ↓
AudioBuffer(wav_bytes)
```

### Key Requirements

1. **Use vendored binary path:** `src/voice/piper_bin/piper/piper`
2. **Implement TTSProvider interface:** Must have `synthesize()`, `stream_synthesize()`, `is_available()`, `list_voices()`
3. **Handle model paths:** Models may be in `src/voice/piper_bin/` or `~/.local/share/piper/`
4. **Return AudioBuffer:** Match existing interface in `src/voice/conversation/state.py`
5. **Async-safe:** Wrap subprocess in `asyncio.create_subprocess_exec()` or `run_in_executor()`

---

## Implementation Spec

### File: `src/voice/tts/piper.py`

```python
"""
Piper TTS Provider - Uses vendored Piper binary for synthesis.

This wraps the Piper CLI binary rather than the Python package,
ensuring we use the proven, version-locked binary at:
    src/voice/piper_bin/piper/piper

Architecture:
    TTSManager → PiperTTS.synthesize() → subprocess → binary → WAV bytes
"""
import asyncio
import logging
import os
import subprocess
from pathlib import Path
from typing import Optional, List, AsyncIterator

from .provider import TTSProvider
from ..conversation.state import AudioBuffer, VoiceInfo

logger = logging.getLogger(__name__)

# Vendored binary location (relative to project root)
PIPER_BIN_DIR = Path(__file__).parent.parent.parent.parent / "voice" / "piper_bin" / "piper"
PIPER_BINARY = PIPER_BIN_DIR / "piper"

# Alternative: absolute path if relative fails
PIPER_BINARY_FALLBACK = Path("/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/voice/piper_bin/piper/piper")

# Model locations to search
MODEL_SEARCH_PATHS = [
    Path(__file__).parent.parent.parent.parent / "voice" / "piper_bin" / "models",
    Path.home() / ".local" / "share" / "piper" / "voices",
    Path.home() / "Library" / "Caches" / "piper",
]

# Voice configurations
PIPER_VOICES = {
    "en_US-lessac-medium": {"name": "Lessac (US)", "lang": "en-US"},
    "en_US-amy-medium": {"name": "Amy (US)", "lang": "en-US"},
    "en_GB-alba-medium": {"name": "Alba (UK)", "lang": "en-GB"},
}

DEFAULT_VOICE = "en_US-lessac-medium"


class PiperTTS(TTSProvider):
    """
    Piper TTS using vendored binary.
    
    Calls the Piper CLI binary via subprocess for synthesis.
    Binary outputs raw PCM which we wrap in WAV format.
    """
    
    def __init__(self, voice: str = DEFAULT_VOICE, speed: float = 1.0):
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
        for path in [PIPER_BINARY, PIPER_BINARY_FALLBACK]:
            if path.exists() and os.access(path, os.X_OK):
                return path
        logger.error(f"Piper binary not found at {PIPER_BINARY} or {PIPER_BINARY_FALLBACK}")
        return None
    
    def _find_model(self, voice_id: str) -> Optional[Path]:
        """Locate the ONNX model file for a voice."""
        model_filename = f"{voice_id}.onnx"
        for search_dir in MODEL_SEARCH_PATHS:
            model_path = search_dir / model_filename
            if model_path.exists():
                return model_path
            # Also check nested structure: voices/en/en_US/lessac/medium/
            # Piper sometimes uses this structure
        logger.warning(f"Model not found for voice {voice_id}")
        return None
    
    @property
    def is_available(self) -> bool:
        return self._available
    
    async def synthesize(self, text: str, voice_id: Optional[str] = None) -> AudioBuffer:
        """
        Synthesize text to audio using Piper binary.
        
        Args:
            text: Text to synthesize (should already be preprocessed)
            voice_id: Optional voice override
            
        Returns:
            AudioBuffer with WAV audio data
        """
        if not self._available:
            logger.error("PiperTTS not available")
            return AudioBuffer(data=b"", sample_rate=22050)
        
        if not text.strip():
            return AudioBuffer(data=b"", sample_rate=22050)
        
        try:
            # Build command
            cmd = [
                str(self._binary_path),
                "--model", str(self._model_path),
                "--output_raw",  # Output raw PCM, we'll wrap in WAV
                "-",  # Output to stdout
            ]
            
            # Add speed if not default
            if self.speed != 1.0:
                cmd.extend(["--length_scale", str(1.0 / self.speed)])
            
            # Run subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate(input=text.encode('utf-8'))
            
            if process.returncode != 0:
                logger.error(f"Piper failed: {stderr.decode()}")
                return AudioBuffer(data=b"", sample_rate=22050)
            
            # Piper outputs raw 16-bit PCM at 22050Hz mono
            # Wrap in WAV header
            wav_bytes = self._pcm_to_wav(stdout, sample_rate=22050, channels=1, sample_width=2)
            
            return AudioBuffer(data=wav_bytes, sample_rate=22050)
            
        except Exception as e:
            logger.error(f"PiperTTS synthesis error: {e}")
            return AudioBuffer(data=b"", sample_rate=22050)
    
    async def stream_synthesize(self, text: str, voice_id: Optional[str] = None) -> AsyncIterator[bytes]:
        """Stream synthesis - for now just yields complete audio."""
        result = await self.synthesize(text, voice_id)
        if result.data:
            yield result.data
    
    def list_voices(self) -> List[VoiceInfo]:
        """List available Piper voices."""
        voices = []
        for voice_id, info in PIPER_VOICES.items():
            voices.append(VoiceInfo(
                id=voice_id,
                name=info["name"],
                language=info["lang"],
                provider="piper"
            ))
        return voices
    
    def _pcm_to_wav(self, pcm_data: bytes, sample_rate: int, channels: int, sample_width: int) -> bytes:
        """Wrap raw PCM in WAV header."""
        import struct
        
        data_size = len(pcm_data)
        
        # WAV header
        header = struct.pack(
            '<4sI4s4sIHHIIHH4sI',
            b'RIFF',
            data_size + 36,  # File size - 8
            b'WAVE',
            b'fmt ',
            16,  # Subchunk1 size
            1,   # Audio format (PCM)
            channels,
            sample_rate,
            sample_rate * channels * sample_width,  # Byte rate
            channels * sample_width,  # Block align
            sample_width * 8,  # Bits per sample
            b'data',
            data_size,
        )
        
        return header + pcm_data
```

---

## Required Changes Summary

| File | Change |
|------|--------|
| `src/voice/tts/piper.py` | **Rewrite** - Use subprocess to call binary instead of Python package |
| `src/voice/tts/manager.py` | **Verify** - Should already work, just ensure PiperTTS initializes |

---

## Testing Checklist

1. **Binary detection:**
   ```python
   from src.voice.tts.piper import PiperTTS
   tts = PiperTTS()
   assert tts.is_available, "Binary not found"
   ```

2. **Synthesis:**
   ```python
   result = await tts.synthesize("Hello, this is a test.")
   assert len(result.data) > 1000, "No audio generated"
   ```

3. **TTSManager integration:**
   ```python
   from src.voice.tts import TTSManager
   mgr = TTSManager()
   result = await mgr.synthesize("*smiles* Hello there!")
   # Should preprocess AND use Piper
   assert len(result.data) > 1000
   ```

4. **Full voice pipeline:**
   - Start backend: `PYTHONPATH=src python scripts/run.py --server`
   - Call `/voice/speak` endpoint
   - Verify audio is NOT Samantha/Apple voice

---

## Model Location Issue

The binary is confirmed at `src/voice/piper_bin/piper/piper`, but models may not be present. Check:

```bash
ls -la src/voice/piper_bin/models/
ls -la ~/.local/share/piper/voices/
```

If no models found, either:
1. Download `en_US-lessac-medium.onnx` from Piper releases
2. Or let Piper auto-download (if the binary supports it)

The implementation should handle missing models gracefully and log clearly.

---

## Success Criteria

- [ ] `PiperTTS.is_available` returns `True`
- [ ] `TTSManager.synthesize()` produces audio (not empty bytes)
- [ ] Voice output is Piper (neural), not Apple Samantha
- [ ] Preprocessing still works (`*asterisk*` not spoken)
- [ ] No new Python dependencies required

---

## Notes

- The vendored binary approach aligns with Luna's sovereignty philosophy ("Luna is a file")
- Version-locked at Piper 1.2.0 - no PyPI surprises
- This is the professional solution: proper abstraction, proven code path, no new deps
