# Delegation Filler System — Design Specification

**Status:** Draft  
**Author:** The Dude (Architect Mode)  
**Date:** 2025-02-01  
**Bible Reference:** Part VIII, Section 8.5  

---

## 1. Problem Statement

When Luna delegates to Claude API (2-10 second calls), the user experiences dead air:
- Loading spinner
- No feedback
- Feels like system froze

This breaks Luna's core promise: **continuous presence**.

The Bible mandates:
> "During delegation, Luna maintains presence through filler — thinking sounds, status updates, topic pivots."

---

## 2. Solution Overview

A **FillerSystem** that:
1. Starts when delegation begins
2. Emits timed filler events (audio + text)
3. Streams to frontend via WebSocket
4. Cancels cleanly when response arrives

```
User sends query
       │
       ▼
Director starts FULL_DELEGATION
       │
       ├──────────────────────────────┐
       │                              │
       ▼                              ▼
  Claude API call              FillerSystem.start()
  (2-10 seconds)                      │
       │                              ├─ 0-2s: silence (give Claude a chance)
       │                              ├─ 2-3s: "hmm..." + thinking animation
       │                              ├─ 3-5s: "still thinking..." 
       │                              ├─ 5-8s: "digging deeper..."
       │                              └─ 8s+:  "this is a big one..." + topic tease
       │                              │
       ▼                              │
  Response arrives ──────────────────►│
       │                              │
       ▼                              ▼
  FillerSystem.cancel()         Stop filler
       │
       ▼
  Send actual response
```

---

## 3. Filler Timeline

| Time | Text Filler | Audio | Orb State | Notes |
|------|-------------|-------|-----------|-------|
| 0-2s | (none) | (none) | `thinking` | Give Claude a chance |
| 2-3s | "Hmm..." | `thinking_hum.wav` | `thinking` | Gentle acknowledgment |
| 3-5s | "Still thinking..." | `thinking_long.wav` | `processing` | User knows we're working |
| 5-8s | "Digging into this..." | (none) | `processing` | More substantial update |
| 8-12s | "This is a meaty one, hang on..." | `deep_thought.wav` | `deep_work` | Acknowledge complexity |
| 12s+ | "Want me to try a different angle?" | (none) | `waiting` | Offer escape hatch |

**Randomization:** Each tier has 3-5 variants to avoid repetition.

---

## 4. Components

### 4.1 FillerSystem (New)

**Location:** `src/luna/filler/filler_system.py`

**Responsibilities:**
- Manage filler timeline
- Emit events at scheduled times
- Cancel cleanly on response
- Track state for orb animations

**Interface:**

```python
class FillerSystem:
    def __init__(self, websocket_manager: WebSocketManager):
        self._ws = websocket_manager
        self._active_task: Optional[asyncio.Task] = None
        self._cancelled = False
    
    async def start(self, query: str, session_id: str) -> None:
        """Begin filler sequence. Non-blocking — runs in background."""
        self._cancelled = False
        self._active_task = asyncio.create_task(
            self._run_filler_sequence(query, session_id)
        )
    
    async def cancel(self) -> None:
        """Stop filler immediately. Call when response ready."""
        self._cancelled = True
        if self._active_task:
            self._active_task.cancel()
            try:
                await self._active_task
            except asyncio.CancelledError:
                pass
        # Send "filler_end" event to clear frontend state
        await self._emit(FillerEvent(type="end"))
    
    async def _run_filler_sequence(self, query: str, session_id: str) -> None:
        """Execute timed filler progression."""
        timeline = self._build_timeline(query)
        start_time = time.monotonic()
        
        for entry in timeline:
            if self._cancelled:
                return
            
            # Wait until this entry's time
            elapsed = time.monotonic() - start_time
            wait_time = entry.time_sec - elapsed
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            
            if self._cancelled:
                return
            
            # Emit filler event
            await self._emit(entry.event)
    
    def _build_timeline(self, query: str) -> list[TimelineEntry]:
        """Build filler timeline, optionally customized by query type."""
        return [
            TimelineEntry(time_sec=2.0, event=FillerEvent(
                type="text",
                content=random.choice(THINKING_FILLERS),
                audio="thinking_hum.wav",
                orb_state="thinking"
            )),
            TimelineEntry(time_sec=4.0, event=FillerEvent(
                type="text", 
                content=random.choice(STILL_THINKING_FILLERS),
                orb_state="processing"
            )),
            # ... etc
        ]
    
    async def _emit(self, event: FillerEvent) -> None:
        """Send filler event to frontend via WebSocket."""
        await self._ws.broadcast({
            "type": "filler",
            "payload": event.to_dict()
        })
```

### 4.2 FillerEvent (New)

**Location:** `src/luna/filler/events.py`

```python
@dataclass
class FillerEvent:
    type: str  # "text", "audio", "orb", "end"
    content: Optional[str] = None  # Text to display
    audio: Optional[str] = None  # Audio file to play
    orb_state: Optional[str] = None  # Orb animation state
    
    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v is not None}
```

### 4.3 Filler Content (New)

**Location:** `src/luna/filler/content.py`

```python
THINKING_FILLERS = [
    "Hmm...",
    "Let me think...",
    "One moment...",
    "Mmm...",
]

STILL_THINKING_FILLERS = [
    "Still thinking...",
    "Working on it...",
    "Almost there...",
    "Pulling some threads...",
]

DEEP_THINKING_FILLERS = [
    "This is a meaty one...",
    "Digging deeper...",
    "Lots to unpack here...",
    "Bear with me...",
]

LONG_WAIT_FILLERS = [
    "This is taking longer than usual — want me to try a different approach?",
    "Still working... I can pivot if you'd like.",
    "Complex question! Hang tight or let me know if you want to redirect.",
]
```

### 4.4 Audio Assets

**Location:** `assets/audio/filler/`

| File | Duration | Description |
|------|----------|-------------|
| `thinking_hum.wav` | 1-2s | Soft "hmm" sound |
| `thinking_long.wav` | 2-3s | Extended contemplation |
| `deep_thought.wav` | 1s | Deeper acknowledgment |
| `typing_soft.wav` | 2-3s | Optional keyboard sounds |

**Note:** Can use TTS to generate these from Luna's voice model, or use subtle non-verbal sounds.

---

## 5. Integration Points

### 5.1 Director

**File:** `src/luna/actors/director.py`

**Changes:**

```python
# In __init__:
self._filler = FillerSystem(websocket_manager)

# In FULL_DELEGATION path:
async def _generate_with_full_delegation(self, query: str, session_id: str):
    # Start filler in background
    await self._filler.start(query, session_id)
    
    try:
        # Actual Claude call (2-10 seconds)
        response = await self._fallback_chain.generate(...)
        
        # Narrate response (per voice restoration fix)
        narrated = await self._narrate_response(response)
        
        return narrated
        
    finally:
        # Always cancel filler, even on error
        await self._filler.cancel()
```

### 5.2 WebSocket Manager

**File:** `src/luna/api/websocket.py` (or wherever WS lives)

**Required capability:**
- `broadcast(message: dict)` — send to all connected clients
- Or `send_to_session(session_id: str, message: dict)` — send to specific session

**If WebSocket doesn't exist yet:** Need to add it. Filler requires push capability — HTTP polling won't cut it.

### 5.3 Frontend

**File:** `frontend/src/components/ChatPanel.jsx` (or similar)

**Handle filler events:**

```javascript
// WebSocket message handler
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === "filler") {
        handleFillerEvent(data.payload);
    } else if (data.type === "response") {
        // Clear filler, show actual response
        clearFiller();
        displayResponse(data.payload);
    }
};

function handleFillerEvent(payload) {
    if (payload.type === "end") {
        clearFiller();
        return;
    }
    
    if (payload.content) {
        // Show filler text in chat (styled differently)
        showFillerText(payload.content);
    }
    
    if (payload.audio) {
        // Play audio file
        playAudio(`/assets/audio/filler/${payload.audio}`);
    }
    
    if (payload.orb_state) {
        // Update orb animation
        setOrbState(payload.orb_state);
    }
}

function clearFiller() {
    // Remove filler text from chat
    // Reset orb to idle
    // Stop any playing audio
}
```

### 5.4 Orb Integration

**File:** `src/luna/orb/orb_state.py`

**Filler states to support:**

| State | Animation | Description |
|-------|-----------|-------------|
| `thinking` | Slow pulse, slightly dimmed | Light cognitive load |
| `processing` | Faster pulse, swirling | Active work |
| `deep_work` | Intense glow, particle effects | Heavy computation |
| `waiting` | Gentle bounce | Awaiting user decision |

---

## 6. Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                         BACKEND                                  │
│                                                                  │
│  ┌──────────┐    ┌─────────────┐    ┌──────────────────┐       │
│  │ Director │───▶│FillerSystem │───▶│ WebSocketManager │       │
│  └──────────┘    └─────────────┘    └──────────────────┘       │
│       │                                      │                  │
│       │ Claude API call                      │ filler events    │
│       ▼                                      ▼                  │
│  ┌──────────────┐                    ┌─────────────┐           │
│  │FallbackChain │                    │  WebSocket  │           │
│  └──────────────┘                    └─────────────┘           │
│       │                                      │                  │
└───────│──────────────────────────────────────│──────────────────┘
        │                                      │
        │ response                             │ push
        ▼                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                         FRONTEND                                 │
│                                                                  │
│  ┌─────────────┐    ┌───────────┐    ┌─────────────┐           │
│  │  ChatPanel  │◀───│ WS Client │    │     Orb     │           │
│  └─────────────┘    └───────────┘    └─────────────┘           │
│       │                   │                 ▲                   │
│       │ display           │ filler events   │ state updates     │
│       ▼                   └─────────────────┘                   │
│  ┌─────────────┐                                                │
│  │ Filler Text │ (styled as thinking, not final response)      │
│  └─────────────┘                                                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Failure Modes

| Failure | Behavior | Recovery |
|---------|----------|----------|
| WebSocket disconnected | Filler events lost | Frontend shows loading spinner (graceful degradation) |
| Filler task crashes | Logged, delegation continues | Response still delivered |
| Response arrives during filler | `cancel()` called | Filler stops, response shown |
| Response never arrives | Filler runs to 12s+ escape hatch | User offered pivot |
| Audio file missing | Skip audio, show text only | Log warning |

---

## 8. Edge Cases

### 8.1 Very Fast Response (<2s)
- Filler never starts (first event at 2s)
- User just sees response
- Ideal case

### 8.2 User Sends Another Message During Filler
- Cancel current filler
- Start processing new message
- Don't queue filler — new query takes priority

### 8.3 Multiple Concurrent Sessions
- FillerSystem is per-session (or use session_id in events)
- Each session gets its own filler stream

### 8.4 Backend Restart During Delegation
- Filler task dies with process
- Frontend WebSocket reconnects
- User sees loading state, then either response or timeout

---

## 9. Configuration

**File:** `config/filler.yaml`

```yaml
# Filler system configuration

enabled: true

# Timing (seconds)
timeline:
  first_filler: 2.0      # When to show first filler
  second_filler: 4.0     # "Still thinking..."
  third_filler: 7.0      # "Digging deeper..."
  escape_hatch: 12.0     # Offer to pivot

# Audio
audio:
  enabled: true
  volume: 0.6

# Randomization
randomize_content: true
```

---

## 10. Testing Strategy

### Unit Tests
- FillerSystem emits events at correct times
- Cancel stops emission immediately
- Timeline respects configuration

### Integration Tests
- Director triggers filler on FULL_DELEGATION
- WebSocket receives filler events
- Filler stops when response arrives

### Manual Tests
1. Trigger slow Claude response (mock 5s delay)
2. Verify filler progression: silence → "hmm" → "still thinking"
3. Response arrives → filler stops, response shows
4. No orphaned filler text in chat

---

## 11. Future Enhancements

| Enhancement | Description | Priority |
|-------------|-------------|----------|
| Query-aware filler | Different filler for research vs creative vs technical | P2 |
| Voice synthesis | Generate filler audio from Luna's TTS model | P2 |
| User preference | Let users disable filler | P3 |
| Filler analytics | Track how often escape hatch is used | P3 |

---

## 12. Files to Create/Modify

| File | Action |
|------|--------|
| `src/luna/filler/__init__.py` | CREATE |
| `src/luna/filler/filler_system.py` | CREATE |
| `src/luna/filler/events.py` | CREATE |
| `src/luna/filler/content.py` | CREATE |
| `config/filler.yaml` | CREATE |
| `assets/audio/filler/*.wav` | CREATE (4-5 audio files) |
| `src/luna/actors/director.py` | MODIFY (integrate filler) |
| `src/luna/api/websocket.py` | MODIFY or CREATE (if no WS exists) |
| `frontend/src/components/ChatPanel.jsx` | MODIFY (handle filler events) |
| `src/luna/orb/orb_state.py` | MODIFY (add filler states) |

---

## 13. Dependencies

**Requires before implementation:**
1. WebSocket infrastructure (may need to add)
2. Voice restoration fix (P0) — filler without voice fix is putting cart before horse

**Nice to have:**
1. Orb animation system (for visual feedback)
2. Audio playback in frontend

---

## 14. Trade-offs

| Decision | Alternative | Why This Way |
|----------|-------------|--------------|
| Fixed timeline tiers | Dynamic based on estimated latency | Simpler, predictable, Claude latency hard to predict |
| Text + audio filler | Audio only | Accessibility, works without speakers |
| Cancel on response | Let filler finish | Immediate response more important than filler completion |
| 2s delay before first filler | Immediate filler | Most responses < 2s, don't filler unnecessarily |

---

*Luna doesn't go silent. She thinks out loud. That's the vibe.*
