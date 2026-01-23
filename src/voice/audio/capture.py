"""
Audio capture from microphone using sounddevice.

Provides real-time audio input with configurable buffering and callbacks.
"""
import logging
import threading
import queue
from typing import Optional, Callable, List

logger = logging.getLogger(__name__)


class AudioCapture:
    """
    Captures audio from microphone using sounddevice.

    Features:
    - 16kHz mono recording (optimal for STT)
    - Background thread with queue-based buffering
    - Callback support for real-time processing
    - Device enumeration and selection
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_duration_ms: int = 100,
        device: Optional[int] = None
    ):
        """
        Initialize audio capture.

        Args:
            sample_rate: Sample rate in Hz (default 16000 for STT)
            channels: Number of channels (default 1 for mono)
            chunk_duration_ms: Duration of each audio chunk in ms
            device: Audio input device index (None = default)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_duration_ms = chunk_duration_ms
        self.device = device

        # Calculate chunk size
        self.chunk_size = int(sample_rate * chunk_duration_ms / 1000)

        # State
        self._running = False
        self._stream = None
        self._audio_queue: queue.Queue = queue.Queue()
        self._callbacks: List[Callable[[bytes], None]] = []
        self._available = False

        # Check availability
        self._check_available()

    def _check_available(self):
        """Check if audio capture is available."""
        try:
            import sounddevice as sd
            # Try to get default input device
            sd.query_devices(kind='input')
            self._available = True
        except Exception as e:
            logger.warning(f"Audio capture not available: {e}")
            self._available = False

    def is_available(self) -> bool:
        """Check if audio capture is available."""
        return self._available

    def add_callback(self, callback: Callable[[bytes], None]):
        """
        Add callback for real-time audio processing.

        Args:
            callback: Function called with each audio chunk (bytes)
        """
        self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[bytes], None]):
        """Remove a previously added callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def start(self):
        """Start audio capture."""
        if self._running:
            logger.warning("Audio capture already running")
            return

        if not self._available:
            logger.error("Audio capture not available")
            return

        try:
            import sounddevice as sd
            import numpy as np

            def audio_callback(indata, frames, time_info, status):
                """Called by sounddevice for each audio chunk."""
                if status:
                    logger.warning(f"Audio status: {status}")

                # Convert to bytes (16-bit PCM)
                audio_bytes = (indata * 32767).astype(np.int16).tobytes()

                # Add to queue
                self._audio_queue.put(audio_bytes)

                # Call registered callbacks
                for cb in self._callbacks:
                    try:
                        cb(audio_bytes)
                    except Exception as e:
                        logger.error(f"Audio callback error: {e}")

            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                blocksize=self.chunk_size,
                device=self.device,
                dtype='float32',
                callback=audio_callback
            )
            self._stream.start()
            self._running = True
            logger.info(f"Audio capture started ({self.sample_rate}Hz, {self.channels}ch)")

        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}")
            self._running = False

    def stop(self):
        """Stop audio capture."""
        if not self._running:
            return

        try:
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None

            self._running = False
            logger.info("Audio capture stopped")

        except Exception as e:
            logger.error(f"Error stopping audio capture: {e}")

    def get_audio(self, timeout: float = 0.1) -> Optional[bytes]:
        """
        Get next audio chunk from queue.

        Args:
            timeout: Timeout in seconds

        Returns:
            Audio bytes or None if timeout
        """
        try:
            return self._audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear_queue(self):
        """Clear the audio queue."""
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

    @staticmethod
    def list_devices() -> List[dict]:
        """
        List available audio input devices.

        Returns:
            List of device info dicts
        """
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = []
            for i, d in enumerate(devices):
                if d['max_input_channels'] > 0:
                    input_devices.append({
                        'index': i,
                        'name': d['name'],
                        'channels': d['max_input_channels'],
                        'sample_rate': d['default_samplerate']
                    })
            return input_devices
        except Exception as e:
            logger.error(f"Failed to list devices: {e}")
            return []

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
