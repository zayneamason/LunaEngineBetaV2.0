"""
Voice Backend - Main orchestrator for Luna Engine voice conversations.

This is the adapted backend that replaces HTTP-based HubClient with
direct PersonaAdapter integration and uses Piper TTS (no Docker).
"""
import logging
import asyncio
import time
import numpy as np
from typing import Optional, Callable

# Voice components
from .audio.capture import AudioCapture
from .audio.playback import AudioPlayback
from .stt.manager import STTManager, STTProviderType
from .tts.manager import TTSManager, TTSProviderType
from .conversation.manager import ConversationManager
from .conversation.state import Speaker, ConversationPhase, AudioBuffer, ConversationBuffer
from .persona_adapter import PersonaAdapter
from .prosody import ProsodyMapper, ProsodyParameters
from .diagnostics.interaction_tracer import get_tracer

logger = logging.getLogger(__name__)


class VoiceActivityDetector:
    """
    Simple energy-based voice activity detection.

    Detects speech based on audio energy threshold.
    """

    def __init__(
        self,
        threshold: float = 0.02,
        silence_duration: float = 1.5,
        min_speech_duration: float = 0.3,
        sample_rate: int = 16000
    ):
        """
        Initialize VAD.

        Args:
            threshold: Energy threshold for speech detection (0-1)
            silence_duration: Seconds of silence to end utterance
            min_speech_duration: Minimum speech duration to be valid
            sample_rate: Audio sample rate
        """
        self.threshold = threshold
        self.silence_duration = silence_duration
        self.min_speech_duration = min_speech_duration
        self.sample_rate = sample_rate

        self._is_speaking = False
        self._speech_start_time = 0.0
        self._last_speech_time = 0.0
        self._total_samples = 0

    def process_chunk(self, audio: bytes) -> tuple:
        """
        Process audio chunk and detect speech.

        Args:
            audio: Raw PCM audio bytes (16-bit signed)

        Returns:
            (is_speech, utterance_complete)
        """
        # Convert to numpy
        samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0

        # Calculate RMS energy
        energy = np.sqrt(np.mean(samples ** 2))

        current_time = self._total_samples / self.sample_rate
        self._total_samples += len(samples)

        is_speech = energy > self.threshold
        utterance_complete = False

        if is_speech:
            if not self._is_speaking:
                # Speech started
                self._is_speaking = True
                self._speech_start_time = current_time
                logger.debug(f"Speech started (energy: {energy:.4f})")
            self._last_speech_time = current_time
        else:
            if self._is_speaking:
                # Check for silence timeout
                silence_time = current_time - self._last_speech_time
                speech_duration = self._last_speech_time - self._speech_start_time

                if silence_time >= self.silence_duration:
                    # Utterance complete
                    self._is_speaking = False
                    if speech_duration >= self.min_speech_duration:
                        utterance_complete = True
                        logger.debug(f"Utterance complete ({speech_duration:.1f}s)")
                    else:
                        logger.debug(f"Speech too short ({speech_duration:.1f}s)")

        return is_speech, utterance_complete

    def reset(self):
        """Reset VAD state."""
        self._is_speaking = False
        self._speech_start_time = 0.0
        self._last_speech_time = 0.0
        self._total_samples = 0

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking


class VoiceBackend:
    """
    Main orchestrator for voice conversations with Luna.

    Supports two modes:
    1. Push-to-talk: User holds key to speak
    2. Hands-free: VAD auto-detects speech start/end

    Flow:
    1. AudioCapture records user speech
    2. STTManager (MLX-Whisper/Apple) transcribes
    3. PersonaAdapter processes through Luna Engine
    4. Director generates response with personality
    5. TTSManager (Piper/Apple) synthesizes speech
    6. AudioPlayback plays response

    Key difference from Eclissi:
    - Uses PersonaAdapter (direct) instead of HubClient (HTTP)
    - Uses Piper TTS (local) instead of Kokoro (Docker)
    """

    def __init__(
        self,
        engine=None,
        stt_provider: STTProviderType = STTProviderType.MLX_WHISPER,
        tts_provider: TTSProviderType = TTSProviderType.PIPER,
        tts_voice: str = "en_US-lessac-medium",
        hands_free: bool = False
    ):
        """
        Initialize Voice Backend.

        Args:
            engine: Luna Engine instance (optional - can be set later)
            stt_provider: STT provider to use (MLX_WHISPER or APPLE)
            tts_provider: TTS provider to use (PIPER or APPLE)
            tts_voice: Voice ID for TTS
            hands_free: Enable hands-free mode with VAD
        """
        self.hands_free = hands_free

        # PersonaAdapter - direct Luna Engine integration
        self.persona = PersonaAdapter(engine=engine)
        logger.info("Voice PersonaAdapter initialized (direct integration)")

        # Components
        self.audio_capture = AudioCapture(sample_rate=16000)
        self.audio_playback = AudioPlayback()
        self.stt = STTManager(
            default_provider=stt_provider,
            language="en"
        )
        self.tts = TTSManager(
            default_provider=tts_provider,
            default_voice=tts_voice
        )
        self.conversation = ConversationManager(max_history=10)
        self.conversation_buffer = ConversationBuffer(max_turns=10, max_tokens=2000)  # NEW: Rolling history buffer
        self.vad = VoiceActivityDetector()
        self.prosody_mapper = ProsodyMapper()
        self._tracer = get_tracer()  # NEW: Diagnostic tracer
        self._session_id = f"voice_{int(time.time())}"  # NEW: Session ID for tracer

        # State
        self._running = False
        self._recording = False
        self._listening_task: Optional[asyncio.Task] = None
        self._audio_buffer: bytes = b""

        # Callbacks
        self._on_speech_start: Optional[Callable] = None
        self._on_speech_end: Optional[Callable[[str], None]] = None
        self._on_response: Optional[Callable[[str], None]] = None
        self._on_status_change: Optional[Callable[[str], None]] = None

        logger.info("VoiceBackend initialized")

    def set_engine(self, engine):
        """
        Set or update the Luna Engine reference.

        Args:
            engine: Luna Engine instance
        """
        self.persona.set_engine(engine)
        logger.info("VoiceBackend connected to Luna Engine")

    async def start(self):
        """Start the voice backend."""
        self._running = True
        self.conversation.start_conversation()

        # Connect to Luna Engine through PersonaAdapter
        persona_connected = await self.persona.connect()
        if persona_connected:
            logger.info("PersonaAdapter connected - full personality available")
        else:
            logger.warning("PersonaAdapter not connected - Luna Engine may not be running")

        # Give TTS providers a moment to initialize
        await asyncio.sleep(0.2)

        # Validate components
        components = [
            ("STT", self.stt),
            ("TTS", self.tts),
        ]

        for name, component in components:
            if not component.is_available():
                logger.warning(f"{name} ({component.get_name()}) not available")
            else:
                logger.info(f"{name}: {component.get_name()} ready")

        # Log PersonaAdapter status
        if self.persona.is_available():
            logger.info("PersonaAdapter: Luna Engine connected (full personality + memory)")
        else:
            logger.warning("PersonaAdapter: Not available (voice responses may be limited)")

        # Notify status change
        self._notify_status("idle")

        # Start hands-free listening if enabled
        if self.hands_free:
            self._listening_task = asyncio.create_task(self._hands_free_loop())

        logger.info("VoiceBackend started")

    async def stop(self):
        """Stop the voice backend."""
        self._running = False

        if self._listening_task:
            self._listening_task.cancel()
            try:
                await self._listening_task
            except asyncio.CancelledError:
                pass

        self.audio_capture.stop()
        await self.audio_playback.stop()

        # Close PersonaAdapter
        await self.persona.close()

        logger.info("VoiceBackend stopped")

    # ===== Push-to-Talk Mode =====

    async def start_listening(self):
        """Start recording user speech (push-to-talk press)."""
        if self._recording:
            return

        logger.info("Listening...")
        self._recording = True
        self._audio_buffer = b""
        self.audio_capture.clear_queue()
        self.audio_capture.start()
        self.conversation.start_turn(Speaker.USER)

        self._notify_status("listening")

        if self._on_speech_start:
            self._on_speech_start()

    async def stop_listening(self) -> Optional[str]:
        """
        Stop recording and transcribe (push-to-talk release).

        Returns:
            Transcribed text or None if failed
        """
        if not self._recording:
            return None

        self._recording = False

        # Small delay to ensure final audio chunks are queued
        await asyncio.sleep(0.15)

        # Collect all recorded audio with longer timeout
        audio_chunks = []
        empty_count = 0
        while empty_count < 3:  # Allow up to 3 empty reads before stopping
            chunk = self.audio_capture.get_audio(timeout=0.1)
            if chunk is None:
                empty_count += 1
            else:
                audio_chunks.append(chunk)
                empty_count = 0  # Reset on successful read

        self.audio_capture.stop()

        audio_data = b"".join(audio_chunks)
        if not audio_data:
            logger.warning("No audio captured - check microphone permissions")
            return None

        # Calculate audio energy to verify capture quality
        import numpy as np
        samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
        audio_energy = np.sqrt(np.mean(samples ** 2))
        audio_duration_sec = len(audio_data) / (16000 * 2)  # 16kHz, 16-bit

        logger.info(f"Captured {len(audio_data)} bytes ({audio_duration_sec:.1f}s), energy: {audio_energy:.4f}")

        # Transcribe
        self.conversation.set_processing()
        self._notify_status("thinking")

        result = await self.stt.transcribe(audio_data, sample_rate=16000)

        if not result.text:
            logger.warning("Transcription returned empty")
            self._notify_status("idle")
            return None

        logger.info(f"Transcribed: '{result.text}' (confidence: {result.confidence:.2f})")

        # End user turn
        self.conversation.end_turn(result.text)

        if self._on_speech_end:
            self._on_speech_end(result.text)

        return result.text

    async def handle_push_to_talk(self):
        """
        Full push-to-talk flow.

        Call start_listening() when key pressed,
        call this when key released.
        """
        text = await self.stop_listening()
        if text:
            await self.process_and_respond(text)

    # ===== Hands-Free Mode =====

    async def _hands_free_loop(self):
        """Background loop for hands-free voice detection."""
        logger.info("Hands-free mode started")
        self.audio_capture.start()

        try:
            while self._running:
                # Get audio chunk
                chunk = self.audio_capture.get_audio(timeout=0.1)
                if chunk is None:
                    await asyncio.sleep(0.01)
                    continue

                # Process through VAD
                is_speech, utterance_complete = self.vad.process_chunk(chunk)

                if is_speech and not self._recording:
                    # Speech started
                    logger.info("Speech detected")
                    self._recording = True
                    self._audio_buffer = chunk
                    self.conversation.start_turn(Speaker.USER)

                    self._notify_status("listening")

                    if self._on_speech_start:
                        self._on_speech_start()

                elif self._recording:
                    # Accumulate audio
                    self._audio_buffer += chunk

                    if utterance_complete:
                        # Speech ended - process
                        self._recording = False
                        await self._process_utterance()

        except asyncio.CancelledError:
            pass
        finally:
            self.audio_capture.stop()
            logger.info("Hands-free mode stopped")

    async def _process_utterance(self):
        """Process a complete utterance from hands-free mode."""
        if not self._audio_buffer:
            return

        audio_data = self._audio_buffer
        self._audio_buffer = b""
        self.vad.reset()

        logger.info(f"Processing utterance: {len(audio_data)} bytes")

        # Transcribe
        self.conversation.set_processing()
        self._notify_status("thinking")

        result = await self.stt.transcribe(audio_data, sample_rate=16000)

        if not result.text:
            logger.warning("Transcription returned empty")
            self._notify_status("idle")
            return

        logger.info(f"Transcribed: '{result.text}'")
        self.conversation.end_turn(result.text)

        if self._on_speech_end:
            self._on_speech_end(result.text)

        # Generate and speak response
        await self.process_and_respond(result.text)

    # ===== Response Generation =====

    async def process_and_respond(self, user_text: str):
        """
        Process user input and generate spoken response.

        Args:
            user_text: Transcribed user speech
        """
        if not user_text:
            return

        start_time = time.time()
        self.conversation.set_processing()
        self._notify_status("thinking")

        # Add user message to conversation buffer BEFORE processing
        self.conversation_buffer.add_turn("user", user_text)
        logger.debug(f"[BUFFER] Added user turn, buffer size: {len(self.conversation_buffer)}")

        # Track variables for tracer
        route_decision = "unknown"
        route_reason = "unknown"
        system_prompt_tokens = 0
        memory_nodes_count = 0
        response_text = ""

        # Process through PersonaAdapter (Luna Engine)
        if self.persona.is_available():
            try:
                # Pass conversation history to PersonaAdapter - THIS IS THE KEY FIX
                history_to_pass = self.conversation_buffer.to_messages()
                logger.info(f"[HISTORY-TRACE] VoiceBackend: About to call PersonaAdapter with {len(history_to_pass)} history turns")
                for i, turn in enumerate(history_to_pass):
                    logger.info(f"[HISTORY-TRACE] VoiceBackend: Turn {i}: {turn['role']}: '{turn['content'][:50]}...'")

                response = await self.persona.process_message(
                    message=user_text,
                    interface="voice",
                    conversation_history=history_to_pass  # NEW: Pass history!
                )

                if response and response.response:
                    response_text = response.response
                    route_decision = response.debug.get("route_decision", "delegated") if response.debug else "delegated"
                    route_reason = response.debug.get("route_reason", "PersonaAdapter") if response.debug else "PersonaAdapter"
                    memory_nodes_count = response.debug.get("memories_retrieved", 0) if response.debug else len(response.memory_context)
                    system_prompt_tokens = response.debug.get("system_prompt_tokens", 0) if response.debug else 0

                    logger.info(
                        f"Luna: '{response_text[:100]}{'...' if len(response_text) > 100 else ''}'"
                    )

                    # Get prosody from personality
                    personality = response.personality_state
                    prosody_params = None

                    if personality:
                        prosody_params = self.prosody_mapper.map_personality(personality)
                        logger.debug(f"Prosody: rate={prosody_params.rate:.2f}, pitch={prosody_params.pitch:.2f}")
                    else:
                        prosody_params = self.prosody_mapper.get_luna_default()
                        logger.debug("Using default Luna prosody")

                    # Add assistant response to buffer AFTER generation
                    self.conversation_buffer.add_turn("assistant", response_text)
                    logger.debug(f"[BUFFER] Added assistant turn, buffer size: {len(self.conversation_buffer)}")

                    # Record assistant turn
                    self.conversation.start_turn(Speaker.ASSISTANT)
                    self.conversation.end_turn(response_text)

                    self._notify_status("speaking")

                    if self._on_response:
                        self._on_response(response_text)

                    # Synthesize and play
                    audio = await self.tts.synthesize(response_text)
                    if audio.data:
                        await self.audio_playback.play(audio)

                    # Log to tracer
                    elapsed_ms = (time.time() - start_time) * 1000
                    self._tracer.trace(
                        session_id=self._session_id,
                        user_message=user_text,
                        route_decision=route_decision,
                        route_reason=route_reason,
                        response_text=response_text,
                        response_time_ms=elapsed_ms,
                        system_prompt_tokens=system_prompt_tokens,
                        memory_nodes_count=memory_nodes_count,
                        conversation_history_length=len(self.conversation_buffer),
                    )

                    # Back to idle
                    self._notify_status("idle")
                    return

            except Exception as e:
                logger.error(f"PersonaAdapter processing failed: {e}", exc_info=True)
                # Log error to tracer
                elapsed_ms = (time.time() - start_time) * 1000
                self._tracer.trace(
                    session_id=self._session_id,
                    user_message=user_text,
                    route_decision="error",
                    route_reason=str(e),
                    response_text="",
                    response_time_ms=elapsed_ms,
                    conversation_history_length=len(self.conversation_buffer),
                    error=str(e),
                )

        # Fallback response if PersonaAdapter unavailable
        error_msg = (
            "I'm having trouble connecting to my engine right now. "
            "Please make sure Luna Engine is running."
        )
        logger.error("PersonaAdapter unavailable - cannot generate full response")

        # Add fallback response to buffer
        self.conversation_buffer.add_turn("assistant", error_msg)

        self.conversation.start_turn(Speaker.ASSISTANT)
        self.conversation.end_turn(error_msg)

        self._notify_status("speaking")

        if self._on_response:
            self._on_response(error_msg)

        # Speak the error message
        audio = await self.tts.synthesize(error_msg)
        if audio.data:
            await self.audio_playback.play(audio)

        # Log fallback to tracer
        elapsed_ms = (time.time() - start_time) * 1000
        self._tracer.trace(
            session_id=self._session_id,
            user_message=user_text,
            route_decision="fallback",
            route_reason="PersonaAdapter unavailable",
            response_text=error_msg,
            response_time_ms=elapsed_ms,
            conversation_history_length=len(self.conversation_buffer),
        )

        self._notify_status("idle")

    # ===== Diagnostics =====

    def get_diagnostics(self) -> dict:
        """
        Get voice interaction diagnostics.

        Returns quality metrics for debugging voice continuity issues.
        """
        return {
            "session_id": self._session_id,
            "conversation_buffer_length": len(self.conversation_buffer),
            "quality_summary": self._tracer.get_quality_summary(),
        }

    def print_diagnostics(self) -> None:
        """Print diagnostics summary to console."""
        self._tracer.print_summary()

    # ===== Direct TTS =====

    async def speak(self, text: str):
        """
        Speak the given text using TTS.

        Used for speaking typed chat responses when voice mode is active.
        Uses Piper TTS for high-quality neural voice synthesis.

        Args:
            text: Text to speak
        """
        if not text:
            return

        self._notify_status("speaking")

        if self._on_response:
            self._on_response(text)

        try:
            import os
            import tempfile

            # Piper binary and model paths
            voice_dir = os.path.dirname(os.path.abspath(__file__))
            piper_bin = os.path.join(voice_dir, "piper_bin", "piper", "piper")
            piper_model = os.path.join(voice_dir, "piper_models", "en_US-amy-medium.onnx")

            # Generate temp output file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                output_file = f.name

            try:
                # Run Piper TTS (x86_64 binary via Rosetta)
                process = await asyncio.create_subprocess_exec(
                    "arch", "-x86_64", piper_bin,
                    "--model", piper_model,
                    "--output_file", output_file,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await process.communicate(input=text.encode())

                if process.returncode != 0:
                    stderr_data = await process.stderr.read() if process.stderr else b""
                    logger.error(f"Piper TTS failed: {stderr_data.decode()}")
                    return

                # Play the audio
                play_process = await asyncio.create_subprocess_exec(
                    "afplay", output_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await play_process.wait()

            finally:
                # Clean up temp file
                if os.path.exists(output_file):
                    os.unlink(output_file)

        except Exception as e:
            logger.error(f"TTS failed: {e}")

        finally:
            self._notify_status("idle")

    # ===== Configuration =====

    def set_tts_provider(self, provider_name: str, voice: Optional[str] = None):
        """Change TTS provider."""
        self.tts.set_provider(provider_name)
        if voice:
            self.tts.set_voice(voice)
        logger.info(f"TTS provider changed to {provider_name}")

    def set_tts_voice(self, voice: str):
        """Change TTS voice."""
        self.tts.set_voice(voice)
        logger.info(f"TTS voice changed to {voice}")

    def get_available_voices(self) -> list:
        """Get available TTS voices."""
        return self.tts.get_available_voices()

    def set_hands_free(self, enabled: bool):
        """Enable/disable hands-free mode."""
        if enabled == self.hands_free:
            return

        self.hands_free = enabled

        if self._running:
            if enabled and not self._listening_task:
                self._listening_task = asyncio.create_task(self._hands_free_loop())
            elif not enabled and self._listening_task:
                self._listening_task.cancel()
                self._listening_task = None

    # ===== Callbacks =====

    def on_speech_start(self, callback: Callable):
        """Register callback for when speech starts."""
        self._on_speech_start = callback

    def on_speech_end(self, callback: Callable[[str], None]):
        """Register callback for when speech ends (with transcription)."""
        self._on_speech_end = callback

    def on_response(self, callback: Callable[[str], None]):
        """Register callback for when Luna responds."""
        self._on_response = callback

    def on_status_change(self, callback: Callable[[str], None]):
        """Register callback for status changes (idle, listening, thinking, speaking)."""
        self._on_status_change = callback

    def _notify_status(self, status: str):
        """Notify status change."""
        if self._on_status_change:
            try:
                self._on_status_change(status)
            except Exception as e:
                logger.error(f"Status callback error: {e}")

    # ===== State =====

    @property
    def is_active(self) -> bool:
        """Check if voice backend is actively running."""
        return self._running

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recording

    def get_state(self) -> dict:
        """Get current state."""
        return {
            "running": self._running,
            "recording": self._recording,
            "hands_free": self.hands_free,
            "conversation": self.conversation.get_state().to_dict(),
            "turn_count": self.conversation.turn_count,
            "components": {
                "stt": self.stt.get_name() if self.stt.is_available() else "unavailable",
                "tts": self.tts.get_name() if self.tts.is_available() else "unavailable",
                "persona": "connected" if self.persona.is_available() else "unavailable",
            }
        }
