# Voice System Migration Handoff for Claude Code

**Date:** 2025-01-21  
**Target:** Luna Engine v2.0  
**Source:** Eclissi Hub voice system  
**Executor:** Claude Code  
**Estimated Effort:** 2-3 days

---

## Mission

Migrate the complete voice system from Eclissi Hub to Luna Engine, replacing Kokoro TTS (Docker) with Piper TTS (no Docker), and adapting the Hub HTTP integration to direct PersonaCore integration.

---

## Project Context

**Luna Engine Location:**
```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/
```

**Source (Eclissi - Reference Only):**
```
/Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/src/voice/
```

**Target (Luna Engine v2.0):**
```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/voice/
```
*(Create new voice/ directory in Luna Engine)*

**Key Architecture Docs:**
- `/Users/zayneamason/_HeyLuna_BETA/_xEclessi_BetaDocumentation/VOICE-BACKEND-ARCHITECTURE.md`
- `/Users/zayneamason/_HeyLuna_BETA/_xEclessi_BetaDocumentation/VOICE-MIGRATION-CHECKLIST.md`

---

## Implementation Plan

### Phase 1: Piper TTS Implementation

**Goal:** Replace Kokoro (Docker) with Piper (no Docker)

#### Task 1.1: Create Piper TTS Provider

**File:** `src/voice/tts/piper.py`

**Reference implementations:**
- `../../../_Eclessi_BetaProject_Root/src/voice/tts/apple.py` (simple local provider)
- `../../../_Eclessi_BetaProject_Root/src/voice/tts/edge.py` (async pattern)
- `../../../_Eclessi_BetaProject_Root/src/voice/tts/kokoro.py` (neural TTS with voices)

**Requirements:**
```python
"""
Piper TTS - Fast local neural text-to-speech.

Piper is a lightweight neural TTS system that runs locally without Docker.
Quality is close to cloud TTS but fully offline and fast enough for real-time.

Setup:
1. pip install piper-tts
2. Models auto-download on first use (~20-50MB each)

Features:
- 50+ voices across multiple languages
- Real-time inference on CPU
- Streaming support for low latency
- Fully offline, no API calls
"""

# Female voices for Luna (American and British English)
PIPER_FEMALE_VOICES = {
    # US Female voices
    "en_US-amy-medium": ("Amy (US)", "en-US"),
    "en_US-lessac-medium": ("Lessac (US)", "en-US"),  # Recommended default
    "en_US-libritts-high": ("LibriTTS (US)", "en-US"),  # Best quality, slower
    
    # UK Female voices
    "en_GB-alba-medium": ("Alba (UK)", "en-GB"),
    "en_GB-jenny_dioco-medium": ("Jenny (UK)", "en-GB"),
}

DEFAULT_VOICE = "en_US-lessac-medium"

class PiperTTS(TTSProvider):
    """Piper TTS provider - Fast local neural TTS."""
    
    def __init__(self, voice: str = DEFAULT_VOICE):
        """
        Initialize Piper TTS.
        
        Args:
            voice: Voice ID (e.g., "en_US-lessac-medium")
        """
        # Import piper
        # Load voice model (auto-download if needed)
        # Set up for synthesis
        
    async def synthesize(self, text: str, voice: Optional[str] = None, prosody: Optional[dict] = None) -> AudioBuffer:
        """
        Generate complete audio for text.
        
        Args:
            text: Text to synthesize
            voice: Optional voice override
            prosody: Optional prosody params (rate, pitch, volume)
                     Note: Piper supports rate, but not pitch/volume
        
        Returns:
            AudioBuffer with synthesized audio
        """
        # Run Piper synthesis in executor (it's synchronous)
        # Apply prosody (speed modulation if provided)
        # Return AudioBuffer
        
    async def stream_synthesize(self, text: str, voice: Optional[str] = None) -> AsyncIterator[AudioBuffer]:
        """
        Stream audio chunks as they're generated.
        
        Piper supports streaming - yields chunks for lower latency.
        """
        # Stream synthesis
        # Yield AudioBuffer chunks
        
    def get_voices(self) -> List[VoiceInfo]:
        """Get available Piper voices."""
        # Return list from PIPER_FEMALE_VOICES
        
    def is_available(self) -> bool:
        """Check if Piper is available."""
        # Check if piper-tts installed and model loaded
        
    def get_name(self) -> str:
        """Get provider name."""
        return f"Piper ({self.voice})"
```

**Implementation Notes:**
- Use `piper-tts` Python package
- Models auto-download to `~/.local/share/piper/voices/`
- Synthesis is synchronous, wrap in `asyncio.get_event_loop().run_in_executor()`
- Streaming: Piper yields chunks, convert each to AudioBuffer
- Prosody: Piper supports speed (not pitch/volume), apply via synthesis config

**Testing:**
```python
# Test script
async def test_piper():
    tts = PiperTTS(voice="en_US-lessac-medium")
    assert tts.is_available()
    
    audio = await tts.synthesize("Hello Ahab, this is Luna speaking.")
    assert len(audio.data) > 0
    assert audio.sample_rate > 0
    
    print(f"✓ Generated {len(audio.data)} bytes at {audio.sample_rate}Hz")
```

---

#### Task 1.2: Copy and Update TTS System

**Copy these files from Eclissi to Luna Engine:**

1. **Copy TTS base files:**
```bash
# From: /Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/src/voice/tts/
# To: /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/voice/tts/

- provider.py (TTSProvider protocol)
- manager.py (TTSManager - WILL NEED UPDATES)
- apple.py (Apple TTS)
- edge.py (Edge TTS)
```

2. **Update `manager.py` after copying:**

**Add Piper to enum:**
```python
class TTSProviderType(Enum):
    """Available TTS provider types."""
    PIPER = "piper"      # Add this
    APPLE = "apple"
    EDGE = "edge"
    # KOKORO removed (no Docker)
```

**Add Piper voices constant:**
```python
# After APPLE_FEMALE_VOICES definition
PIPER_FEMALE_VOICES = {
    "en_US-lessac-medium": "Lessac (US)",
    "en_US-amy-medium": "Amy (US)",
    "en_GB-alba-medium": "Alba (UK)",
    "en_US-libritts-high": "LibriTTS High Quality (US)",
}
```

**Initialize Piper in `_init_providers()`:**
```python
def _init_providers(self):
    """Initialize all available TTS providers."""
    # Apple TTS - always available on macOS
    try:
        apple = AppleTTS(voice=self._current_voice)
        self._providers[TTSProviderType.APPLE] = apple
        logger.info("Apple TTS initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize Apple TTS: {e}")
    
    # Edge TTS - online
    try:
        edge = EdgeTTS(voice=self._current_voice)
        self._providers[TTSProviderType.EDGE] = edge
        logger.info("Edge TTS initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize Edge TTS: {e}")
    
    # Piper TTS - local neural (PRIMARY)
    try:
        from .piper import PiperTTS
        piper_voice = self._current_voice if self._current_voice.startswith("en_") else "en_US-lessac-medium"
        piper = PiperTTS(voice=piper_voice)
        self._providers[TTSProviderType.PIPER] = piper
        logger.info("Piper TTS initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize Piper TTS: {e}")
```

**Update `get_available_voices()` to include Piper:**
```python
def get_available_voices(self, female_only: bool = True) -> List[Dict]:
    """Get list of available voices for UI dropdown."""
    voices = []
    
    # Apple voices
    if TTSProviderType.APPLE in self._providers:
        for voice_name, lang in APPLE_FEMALE_VOICES.items():
            voices.append({
                "id": voice_name,
                "name": voice_name,
                "provider": "apple",
                "language": lang,
                "current": (self._current_type == TTSProviderType.APPLE and
                           self._current_voice == voice_name)
            })
    
    # Edge voices (if you want to include them)
    # ...
    
    # Piper voices
    if TTSProviderType.PIPER in self._providers:
        for voice_id, name in PIPER_FEMALE_VOICES.items():
            voices.append({
                "id": voice_id,
                "name": name,
                "provider": "piper",
                "language": "en-US" if "US" in voice_id else "en-GB",
                "current": (self._current_type == TTSProviderType.PIPER and
                           self._current_voice == voice_id)
            })
    
    return voices
```

**Update fallback logic:**
```python
# Change default fallback to Apple
self._fallback_type = TTSProviderType.APPLE

# In synthesize(), when falling back from Piper to Apple:
is_using_fallback = (
    self._current_type == TTSProviderType.PIPER and
    isinstance(provider, AppleTTS)
)

if is_using_fallback and voice.startswith("en_"):
    voice = "Samantha"  # Convert Piper voice to Apple voice
```

**Testing:**
- Verify Piper appears in available providers
- Verify Piper voices listed correctly
- Verify fallback to Apple works

---

#### Task 1.3: Copy Remaining Voice Components

**Copy these directories/files as-is from Eclissi:**

```bash
# From: /Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/src/voice/
# To: /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/voice/

Directories:
- audio/ (capture.py, playback.py)
- stt/ (provider.py, manager.py, mlx_whisper.py, apple.py, whisper.py)
- conversation/ (state.py, manager.py)

Files:
- prosody.py
- wakeword.py
```

**Minor updates needed:**

1. **In `conversation/manager.py`:**
   - Update SessionManager import path for Luna Engine
   - Should be: `from consciousness.session_manager import SessionManager`

2. **In all files:**
   - Verify import paths work for Luna Engine structure
   - Change relative imports if needed

---

### Phase 2: PersonaCore Integration (Replace HubClient)

**Goal:** Replace HTTP-based HubClient with direct PersonaCore calls

#### Task 2.1: Create PersonaCore Adapter

**File:** `src/voice/persona_adapter.py` (NEW FILE)

**Purpose:** Replaces `hub_client.py` with direct PersonaCore integration

**Implementation:**
```python
"""
PersonaCore Adapter - Direct integration for Voice backend.

Replaces HTTP-based HubClient with direct PersonaCore calls.
No network overhead, direct method invocation.
"""
import logging
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VoiceResponse:
    """Response from PersonaCore for voice queries."""
    response: str                    # Luna's text response
    memory_context: list            # Retrieved memories
    state: dict                     # Personality + consciousness state
    debug: Optional[dict] = None    # Debug info


class PersonaAdapter:
    """
    Direct integration with Luna Engine PersonaCore.
    
    Replaces HubClient HTTP calls with direct PersonaCore method calls.
    Compatible with HubClient API for minimal backend changes.
    """
    
    def __init__(self, persona_core):
        """
        Initialize adapter.
        
        Args:
            persona_core: PersonaCore instance from runtime
        """
        from persona.core import PersonaCore
        
        if not isinstance(persona_core, PersonaCore):
            raise TypeError(f"Expected PersonaCore, got {type(persona_core)}")
        
        self.persona = persona_core
        self._available = True
        
        logger.info("PersonaCore adapter initialized (direct integration)")
    
    def is_available(self) -> bool:
        """Check if PersonaCore is available."""
        return self._available and self.persona is not None
    
    async def connect(self) -> bool:
        """
        Connect to PersonaCore (compatibility with HubClient API).
        
        Since we're using direct integration, this always succeeds
        if PersonaCore was properly initialized.
        """
        return self.is_available()
    
    async def process_message(
        self,
        message: str,
        interface: str = "voice",
        session_id: Optional[str] = None,
        generate_response: bool = True
    ) -> Optional[VoiceResponse]:
        """
        Process a message through PersonaCore.
        
        Args:
            message: User message
            interface: Interface type (voice | desktop)
            session_id: Optional session ID
            generate_response: If True, generates LLM response
        
        Returns:
            VoiceResponse with Luna's personality-enriched response
        """
        if not self.is_available():
            logger.error("PersonaCore not available")
            return None
        
        try:
            # Process query through PersonaCore
            # Budget: "balanced" for voice (not too heavy, not too light)
            result = self.persona.process_query(
                query=message,
                budget="balanced"  # Voice uses balanced budget
            )
            
            # Extract personality state
            personality_state = {
                "personality": result.personality.to_dict() if result.personality else {},
                "attention": {},  # TODO: Get from consciousness system if needed
                "coherence": {},  # TODO: Get from consciousness system if needed
            }
            
            # Generate response if requested
            if generate_response:
                # TODO: This needs Director LLM integration (Bible Part VI)
                # For now, this is a placeholder
                # When Director is ready, this calls Director.generate()
                
                # Temporary placeholder
                response_text = getattr(result, 'generated_response', None)
                
                if not response_text:
                    # Fallback: Generate simple acknowledgment
                    response_text = "I'm processing that through my PersonaCore, but response generation isn't wired yet."
                    logger.warning("Response generation not yet implemented - using placeholder")
            else:
                response_text = ""
            
            return VoiceResponse(
                response=response_text,
                memory_context=result.memory_context or [],
                state=personality_state,
                debug={
                    "budget_used": getattr(result, 'budget_used', 0),
                    "memories_retrieved": len(result.memory_context) if result.memory_context else 0,
                }
            )
        
        except Exception as e:
            logger.error(f"PersonaCore processing failed: {e}", exc_info=True)
            return None
    
    async def close(self):
        """Close adapter (compatibility with HubClient API)."""
        # No cleanup needed for direct integration
        logger.info("PersonaCore adapter closed")
```

**Notes:**
- **TODO marker:** Response generation needs Director LLM (Bible Part VI)
- For now, uses placeholder or existing response if available
- Interface matches HubClient so backend.py needs minimal changes

---

#### Task 2.2: Copy and Update VoiceBackend

**Copy from Eclissi:**
```bash
# From: /Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/src/voice/backend.py
# To: /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/voice/backend.py
```

**After copying, make these changes:**

1. **Update imports:**
```python
# Remove:
from .hub_client import HubClient

# Add:
from .persona_adapter import PersonaAdapter
```

2. **Update `__init__` signature:**
```python
def __init__(
    self,
    persona_core,  # NEW: Direct PersonaCore instance instead of hub_url
    stt_provider: STTProviderType = STTProviderType.MLX_WHISPER,
    tts_provider: TTSProviderType = TTSProviderType.PIPER,  # Changed from KOKORO
    tts_voice: str = "en_US-lessac-medium",  # Changed from "af_bella"
    hands_free: bool = False
):
    """
    Initialize Voice Backend.
    
    Args:
        persona_core: PersonaCore instance from runtime
        stt_provider: STT provider to use
        tts_provider: TTS provider to use
        tts_voice: Voice ID for TTS
        hands_free: Enable hands-free mode with VAD
    """
    self.hands_free = hands_free
    
    # PersonaCore integration - direct, not HTTP
    self.persona = PersonaAdapter(persona_core)
    
    # Session management for memory
    from pathlib import Path
    data_path = Path(__file__).parent.parent.parent / "data" / "memories"
    self.session_manager = SessionManager(
        base_path=str(data_path),
        buffer_size=100
    )
    logger.info("Voice PersonaCore integration initialized")
    
    # ... rest of __init__ unchanged ...
```

3. **Replace all `self.hub` references with `self.persona`:**
   - In `start()`: `hub_connected` → `persona_connected`, `self.hub.connect()` → `self.persona.connect()`
   - In `process_and_respond()`: `self.hub.process_message()` → `self.persona.process_message()`
   - In `_report_status()`: Remove or adapt (no HTTP status reporting needed)
   - In `stop()`: `self.hub.close()` → `self.persona.close()`

4. **Update logging messages:**
   - "Hub daemon connected" → "PersonaCore connected"
   - "Hub daemon not available" → "PersonaCore not available"

**Testing:**
- VoiceBackend should initialize with PersonaCore
- Queries should process through PersonaCore
- Responses should include personality context

---

### Phase 3: Runtime Integration

**Goal:** Wire VoiceBackend into Luna Engine runtime

#### Task 3.1: Add Voice to Runtime Engine

**File:** `src/runtime/engine.py`

**Changes:**

1. **Import VoiceBackend:**
```python
from typing import Optional
from voice.backend import VoiceBackend
from voice.stt.manager import STTProviderType
from voice.tts.manager import TTSProviderType
```

2. **Add voice actor to engine:**
```python
class RuntimeEngine:
    def __init__(self, config):
        # ... existing actors ...
        
        # Voice actor (optional - only if voice enabled)
        self.voice: Optional[VoiceBackend] = None
        
        # Initialize voice if enabled
        if config.voice_enabled:
            self._init_voice()
    
    def _init_voice(self):
        """Initialize voice backend."""
        try:
            self.voice = VoiceBackend(
                persona_core=self.persona_core,  # Pass PersonaCore instance
                stt_provider=STTProviderType.MLX_WHISPER,
                tts_provider=TTSProviderType.PIPER,
                tts_voice="en_US-lessac-medium",
                hands_free=False  # Start in push-to-talk mode
            )
            
            logger.info("Voice backend initialized")
        except Exception as e:
            logger.error(f"Failed to initialize voice: {e}", exc_info=True)
            self.voice = None
```

3. **Add voice start/stop to engine lifecycle:**
```python
async def start(self):
    """Start the runtime engine."""
    logger.info("Starting Luna Engine runtime...")
    
    # ... existing startup (consciousness, memory, persona) ...
    
    # Start voice if enabled
    if self.voice:
        try:
            await self.voice.start()
            logger.info("✓ Voice backend started")
        except Exception as e:
            logger.error(f"Voice backend failed to start: {e}")
            self.voice = None

async def stop(self):
    """Stop the runtime engine."""
    logger.info("Stopping Luna Engine runtime...")
    
    # Stop voice first
    if self.voice:
        try:
            await self.voice.stop()
            logger.info("✓ Voice backend stopped")
        except Exception as e:
            logger.error(f"Error stopping voice: {e}")
    
    # ... existing shutdown (persona, memory, consciousness) ...
```

**Notes:**
- Voice runs in same process as runtime
- Voice doesn't need separate tick (event-driven on audio input)
- Voice updates consciousness/memory through PersonaCore

---

#### Task 3.2: Add Voice Configuration

**File:** `src/config/__init__.py`

**Add voice configuration:**
```python
class Config:
    # ... existing config ...
    
    # Voice configuration
    voice_enabled: bool = False  # Enable voice backend
    voice_stt_provider: str = "mlx_whisper"
    voice_tts_provider: str = "piper"
    voice_tts_voice: str = "en_US-lessac-medium"
    voice_mode: str = "push_to_talk"  # or "hands_free"
    
    def __init__(self):
        # ... existing init ...
        
        # Load voice config from env or defaults
        self.voice_enabled = os.getenv("VOICE_ENABLED", "false").lower() == "true"
        self.voice_stt_provider = os.getenv("VOICE_STT_PROVIDER", "mlx_whisper")
        self.voice_tts_provider = os.getenv("VOICE_TTS_PROVIDER", "piper")
        self.voice_tts_voice = os.getenv("VOICE_TTS_VOICE", "en_US-lessac-medium")
        self.voice_mode = os.getenv("VOICE_MODE", "push_to_talk")
```

**Add to `.env.example`:**
```bash
# Voice Configuration
VOICE_ENABLED=false
VOICE_STT_PROVIDER=mlx_whisper
VOICE_TTS_PROVIDER=piper
VOICE_TTS_VOICE=en_US-lessac-medium
VOICE_MODE=push_to_talk
```

**Testing:**
- Config should load voice settings
- Runtime should respect voice_enabled flag
- Voice shouldn't start if voice_enabled=false

---

### Phase 4: Testing & Validation

#### Task 4.1: Unit Tests

**Create:** `tests/test_voice.py`

**Tests:**
```python
import pytest
import asyncio
from voice.tts.piper import PiperTTS
from voice.tts.manager import TTSManager, TTSProviderType
from voice.persona_adapter import PersonaAdapter
from voice.backend import VoiceBackend

@pytest.mark.asyncio
async def test_piper_tts():
    """Test Piper TTS synthesis."""
    tts = PiperTTS(voice="en_US-lessac-medium")
    
    if not tts.is_available():
        pytest.skip("Piper TTS not available (install: pip install piper-tts)")
    
    audio = await tts.synthesize("Hello world")
    assert len(audio.data) > 0
    assert audio.sample_rate > 0
    print(f"✓ Piper generated {len(audio.data)} bytes at {audio.sample_rate}Hz")

@pytest.mark.asyncio
async def test_tts_manager_piper():
    """Test TTSManager with Piper provider."""
    manager = TTSManager(
        default_provider=TTSProviderType.PIPER,
        default_voice="en_US-lessac-medium"
    )
    
    assert manager.is_available()
    
    audio = await manager.synthesize("Testing Piper TTS")
    assert len(audio.data) > 0

def test_persona_adapter_init():
    """Test PersonaAdapter initialization."""
    # Mock PersonaCore
    from persona.core import PersonaCore
    from unittest.mock import Mock
    
    mock_persona = Mock(spec=PersonaCore)
    adapter = PersonaAdapter(mock_persona)
    
    assert adapter.is_available()
    assert adapter.persona == mock_persona

@pytest.mark.asyncio
async def test_voice_backend_init():
    """Test VoiceBackend initialization."""
    from persona.core import PersonaCore
    from unittest.mock import Mock
    
    mock_persona = Mock(spec=PersonaCore)
    
    backend = VoiceBackend(
        persona_core=mock_persona,
        tts_provider=TTSProviderType.APPLE  # Use Apple for testing (always available)
    )
    
    await backend.start()
    assert backend._running
    
    await backend.stop()
    assert not backend._running
```

**Run tests:**
```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
pytest tests/test_voice.py -v
```

---

#### Task 4.2: Integration Test

**Create:** `tests/test_voice_integration.py`

**Test end-to-end flow:**
```python
import pytest
import asyncio

@pytest.mark.asyncio
async def test_voice_with_runtime(runtime_engine):
    """Test voice integrated with runtime engine."""
    # Assumes runtime has voice enabled
    voice = runtime_engine.voice
    
    if not voice:
        pytest.skip("Voice not enabled (set VOICE_ENABLED=true)")
    
    # Verify voice initialized correctly
    assert voice._running
    assert voice.persona.is_available()
    
    # Test processing a message
    # (This requires PersonaCore to be working)
    await voice.process_and_respond("Hello Luna")
    
    # Verify conversation saved
    assert voice.conversation.turn_count > 0
```

---

#### Task 4.3: Manual Testing Checklist

**Standalone Piper Test:**
```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Test Piper TTS standalone
python -c "
import asyncio
from voice.tts.piper import PiperTTS

async def test():
    tts = PiperTTS()
    print(f'Available: {tts.is_available()}')
    if tts.is_available():
        audio = await tts.synthesize('Hello Ahab, this is Luna speaking.')
        print(f'Generated {len(audio.data)} bytes at {audio.sample_rate}Hz')
    else:
        print('Piper not available - install: pip install piper-tts')

asyncio.run(test())
"
```

**CLI Test (if CLI exists/ported):**
```bash
# Test voice backend via CLI
python -m voice.cli --tts piper --voice en_US-lessac-medium
```

**Runtime Integration Test:**
```bash
# Enable voice in config
export VOICE_ENABLED=true

# Start Luna Engine
python -m runtime.main

# Test via runtime interface
# Verify:
# - Voice initialized correctly
# - Can process speech
# - Responses include personality
# - Voice sounds natural
# - Conversations save to memory
```

**Quality Checks:**
- [ ] Piper voice sounds natural (not robotic)
- [ ] Latency < 2 seconds (end-to-end)
- [ ] No audio artifacts (clicks, pops)
- [ ] Prosody modulation working (personality affects voice)
- [ ] Fallback to Apple TTS works if Piper fails
- [ ] Memory persistence working (conversations save)

---

## Dependencies

**Add to `requirements.txt`:**
```bash
# Voice system
piper-tts>=1.2.0
sounddevice>=0.4.6
numpy>=1.24.0
openai-whisper>=20231117
mlx-whisper>=0.1.0
edge-tts>=6.1.0

# Audio processing
pyaudio>=0.2.13  # Alternative to sounddevice
webrtcvad>=2.0.10  # For better VAD (optional)
silero-vad>=4.0.0  # For neural VAD (optional)
```

**Install:**
```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
pip install -r requirements.txt
```

**Verify Piper installation:**
```bash
python -c "import piper; print('Piper installed successfully')"
```

---

## Success Criteria

Voice migration is complete when:

- [x] **Phase 1 Complete:**
  - [ ] Piper TTS provider implemented and working
  - [ ] TTSManager includes Piper with correct fallback
  - [ ] VoiceBackend defaults to Piper
  - [ ] All core voice components copied to Luna Engine

- [x] **Phase 2 Complete:**
  - [ ] PersonaAdapter replaces HubClient
  - [ ] VoiceBackend integrates with PersonaCore directly
  - [ ] No HTTP/network calls for voice processing

- [x] **Phase 3 Complete:**
  - [ ] Voice wired into RuntimeEngine
  - [ ] Voice configuration in Config
  - [ ] Voice respects VOICE_ENABLED flag

- [x] **Phase 4 Complete:**
  - [ ] Unit tests pass
  - [ ] Integration test passes
  - [ ] Manual test: Can speak to Luna and get response
  - [ ] Manual test: Voice sounds natural (Piper quality)
  - [ ] Manual test: Conversations save to Memory Matrix

- [x] **System Requirements:**
  - [ ] No Docker required
  - [ ] System works offline (except Claude delegation)
  - [ ] Latency < 2 seconds
  - [ ] Graceful fallback (Piper → Apple)

---

## Open Items / TODOs

### Immediate (Blockers)
- [ ] **Director LLM integration in PersonaAdapter**
  - Currently uses placeholder response
  - Needs wiring to Director.generate() when Director is ready
  - See: Bible Part VI (BIBLE-UPDATE-PART-VI-DIRECTOR-LLM.md)

### Future Enhancements (Not Blockers)
- [ ] Better VAD (Silero or WebRTC) - current energy-based VAD works but basic
- [ ] Wake word detection (Porcupine or OpenWakeWord) - currently needs push-to-talk
- [ ] Collision detection / barge-in - currently can't interrupt Luna mid-speech
- [ ] TTS streaming (Piper supports it) - reduce latency further
- [ ] End-to-end streaming pipeline (LLM → TTS → Audio)
- [ ] Physical embodiment hooks (orb animation, speaker tracking)
- [ ] Voice cloning / custom Piper voice training

---

## File Structure Reference

**After migration, Luna Engine voice structure:**
```
src/
├── voice/                          # ← NEW (migrated from Eclissi)
│   ├── __init__.py
│   ├── backend.py                  # VoiceBackend orchestrator
│   ├── persona_adapter.py          # ← NEW (replaces hub_client.py)
│   ├── prosody.py                  # Personality → voice params
│   ├── wakeword.py                 # Wake word detection
│   │
│   ├── audio/
│   │   ├── __init__.py
│   │   ├── capture.py              # Microphone input
│   │   └── playback.py             # Speaker output
│   │
│   ├── stt/
│   │   ├── __init__.py
│   │   ├── provider.py             # STT protocol
│   │   ├── manager.py              # STT manager
│   │   ├── mlx_whisper.py          # MLX Whisper
│   │   ├── apple.py                # Apple STT
│   │   └── whisper.py              # Whisper fallback
│   │
│   ├── tts/
│   │   ├── __init__.py
│   │   ├── provider.py             # TTS protocol
│   │   ├── manager.py              # TTS manager
│   │   ├── apple.py                # Apple TTS
│   │   ├── edge.py                 # Edge TTS
│   │   └── piper.py                # ← NEW (Piper TTS, no Docker)
│   │
│   └── conversation/
│       ├── __init__.py
│       ├── state.py                # Conversation state dataclasses
│       └── manager.py              # Conversation manager
│
├── runtime/
│   └── engine.py                   # ← UPDATE: Add VoiceBackend actor
│
├── persona/
│   └── core.py                     # ← USED BY: PersonaAdapter
│
└── config/
    └── __init__.py                 # ← UPDATE: Add voice config
```

---

## Execution Checklist

### Phase 1: Piper TTS
- [ ] Create `src/voice/tts/piper.py`
- [ ] Copy `src/voice/tts/provider.py` from Eclissi
- [ ] Copy `src/voice/tts/apple.py` from Eclissi
- [ ] Copy `src/voice/tts/edge.py` from Eclissi
- [ ] Copy `src/voice/tts/manager.py` from Eclissi
- [ ] Update `manager.py` with Piper integration
- [ ] Test Piper standalone
- [ ] Test TTSManager with Piper

### Phase 2: Copy Core Components
- [ ] Copy `src/voice/audio/` from Eclissi
- [ ] Copy `src/voice/stt/` from Eclissi
- [ ] Copy `src/voice/conversation/` from Eclissi
- [ ] Copy `src/voice/prosody.py` from Eclissi
- [ ] Copy `src/voice/wakeword.py` from Eclissi
- [ ] Update imports in `conversation/manager.py`
- [ ] Test components individually

### Phase 3: PersonaCore Integration
- [ ] Create `src/voice/persona_adapter.py`
- [ ] Copy `src/voice/backend.py` from Eclissi
- [ ] Update `backend.py` imports (remove HubClient, add PersonaAdapter)
- [ ] Update `backend.py` __init__ (persona_core instead of hub_url)
- [ ] Replace all `self.hub` with `self.persona`
- [ ] Test VoiceBackend with mock PersonaCore

### Phase 4: Runtime Integration
- [ ] Update `src/runtime/engine.py` (add voice actor)
- [ ] Update `src/config/__init__.py` (add voice config)
- [ ] Update `.env.example` (add voice settings)
- [ ] Test runtime with voice enabled
- [ ] Test runtime with voice disabled

### Phase 5: Testing
- [ ] Create `tests/test_voice.py`
- [ ] Create `tests/test_voice_integration.py`
- [ ] Run unit tests
- [ ] Run integration tests
- [ ] Manual testing checklist
- [ ] Performance testing (latency)
- [ ] Quality testing (voice naturalness)

---

## Execution Order

**Recommended sequence:**

1. **Day 1 Morning:** Phase 1 (Piper TTS)
   - Tasks 1.1, 1.2, 1.3
   - Test Piper working standalone

2. **Day 1 Afternoon:** Phase 2 Part 1 (Copy components)
   - Task 1.3 (copy audio, STT, conversation, etc.)
   - Test components individually

3. **Day 2 Morning:** Phase 2 Part 2 (PersonaCore integration)
   - Tasks 2.1, 2.2
   - Test VoiceBackend with PersonaCore

4. **Day 2 Afternoon:** Phase 3 (Runtime integration)
   - Tasks 3.1, 3.2
   - Test voice in runtime

5. **Day 3:** Phase 4 (Testing & debugging)
   - Tasks 4.1, 4.2, 4.3
   - Fix any issues found
   - Document remaining TODOs

---

## Notes for Claude Code

### Critical Implementation Details

1. **Piper TTS Synthesis:**
   - Piper is synchronous, must wrap in `run_in_executor()`
   - Models auto-download to `~/.local/share/piper/voices/`
   - First synthesis will be slow (downloading model)
   - Subsequent calls are fast (~100-200ms)

2. **PersonaCore Integration:**
   - PersonaCore is passed as instance, not created
   - Runtime creates PersonaCore, passes to VoiceBackend
   - PersonaAdapter is compatibility wrapper (matches HubClient API)

3. **Import Paths:**
   - All voice imports are relative within `voice/`
   - PersonaCore import: `from persona.core import PersonaCore`
   - Config import: `from config import Config`
   - SessionManager: `from consciousness.session_manager import SessionManager`

4. **Testing Strategy:**
   - Test each component standalone first
   - Mock PersonaCore for unit tests
   - Integration test requires full runtime
   - Manual testing requires microphone/speakers

5. **Error Handling:**
   - Piper not installed → fallback to Apple TTS
   - PersonaCore not available → graceful error message
   - Audio device not found → log error, don't crash

### Reference Documentation

- **Voice Architecture:** `/Users/zayneamason/_HeyLuna_BETA/_xEclessi_BetaDocumentation/VOICE-BACKEND-ARCHITECTURE.md`
- **Migration Checklist:** `/Users/zayneamason/_HeyLuna_BETA/_xEclessi_BetaDocumentation/VOICE-MIGRATION-CHECKLIST.md`
- **Piper TTS Docs:** https://github.com/rhasspy/piper
- **Bible Part VI (Director):** `./BIBLE-UPDATE-PART-VI-DIRECTOR-LLM.md`

### Common Issues & Solutions

**Issue:** Piper models not downloading
- **Solution:** Check internet connection, manually download from GitHub releases

**Issue:** Audio device not found
- **Solution:** Check `sounddevice.query_devices()`, specify device ID

**Issue:** PersonaCore not generating response
- **Solution:** Director LLM not wired yet, use placeholder (this is expected)

**Issue:** Import errors in voice components
- **Solution:** Update relative imports, verify all `__init__.py` files exist

---

**Ready for execution. Hand off to Claude Code.**

**Estimated completion:** 2-3 days  
**Priority:** Medium (not blocking other work, but needed for complete Luna experience)  
**Dependencies:** PersonaCore (exists), Director LLM (TODO marker, not blocking)
