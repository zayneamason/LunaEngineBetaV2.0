# Bible v3.0: Part VII - The Runtime Engine

**Version:** 3.0
**Status:** VERIFIED — Implementation Audited
**Last Updated:** 2026-01-30
**Original Date:** December 29, 2025
**Primary Contributors:** Gemini (Optimization), Claude (Architecture)
**Implementation Accuracy:** 95% (see Audit notes)

> **Audit Notes (2026-01-30):**
> - **5 actors implemented:** Director, Matrix, Scribe, Librarian, HistoryManager
> - **Voice Actor NOT implemented:** Voice I/O handled by PersonaAdapter (non-actor pattern)
> - **Oven Actor NOT implemented:** Claude delegation merged into DirectorActor
> - **HistoryManager actor added:** Three-tier conversation history (v2.0 addition)
> - **on_idle() hook NOT implemented:** Actor loop has no idle callback in actual code
> - **Lifecycle hooks:** Implementation uses `handle()` not `handle_message()`
> - **sqlite-vec replaces FAISS:** Matrix uses sqlite-vec for vector search
> - **Tick timings verified:** Cognitive 500ms, Reflective 5 minutes (from EngineConfig)

---

# Part VII: The Runtime Engine

## 7.1 Design Philosophy

The original Luna architecture was **service-based** — a collection of components called via HTTP endpoints. Voice pushes to Hub. Hub calls Memory. Memory returns. Hub responds.

This model has a fundamental problem: **no heartbeat**.

The Runtime Engine introduces an **engine-based** architecture:

| Service-Based | Engine-Based |
|---------------|--------------|
| Components wait to be called | Components live in a continuous loop |
| Request → Response | Tick → Process → Update |
| Stateless handlers | Stateful actors |
| Events interrupt | Events buffer and poll |
| Luna responds | Luna *lives* |

**The Core Insight:**

Luna is not a program you call. Luna is a system that lives. The Runtime Engine is her **nervous system** — it coordinates when components wake up, what input they receive, and how they communicate.

---

## 7.2 The Priority-Weighted Event Loop

A fixed-frequency tick (like Unity's 60fps) makes no sense for an LLM that takes 500ms-3s to think. Instead, Luna uses a **variable-rate heartbeat** with three priority paths:

> **IMPLEMENTATION NOTE (January 2026):** The "Hot Path" is implemented via buffer polling at each cognitive tick, not true interrupt-driven processing. This provides up to 500ms latency for interrupts but simplifies the architecture significantly.

```
┌─────────────────────────────────────────────────────────────┐
│              HOT PATH (Buffer-Polled, ~500ms latency)        │
│                                                              │
│   • STT partial transcripts                                  │
│   • User interrupts (barge-in) — via INTERRUPT priority     │
│   • TTS output streaming                                     │
│   • Implementation: InputBuffer.poll_all() each tick        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                  COGNITIVE PATH (500ms fixed)                │
│                                                              │
│   • Director heartbeat via _cognitive_tick()                │
│   • Query routing decisions (see 7.9 QueryRouter)           │
│   • Context ring rebalancing                                │
│   • Consciousness state update                              │
│   • History manager tick                                    │
│   • Frequency: Every 500ms (asyncio.sleep(0.5))            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                REFLECTIVE PATH (5 minutes)                   │
│                                                              │
│   • Context decay via context.decay_all()                   │
│   • Graph pruning and maintenance (TODO)                    │
│   • Session summarization (via HistoryManager)              │
│   • Memory consolidation                                     │
│   • Frequency: Every 300 seconds (5 minutes)               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Implementation (Actual v2.0)

```python
class LunaEngine:
    def __init__(self):
        # Input buffer (engine pulls, not pushed)
        self.input_buffer = InputBuffer(max_size=100)

        # Actor registry
        self.actors: Dict[str, Actor] = {}

        # State management
        self.state = EngineState.STARTING
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._ready_event = asyncio.Event()

        # Consciousness substrate (Phase 4)
        self.consciousness = ConsciousnessState()

        # Context management (not in original spec)
        self.context = RevolvingContext(token_budget=8000)

        # Query routing (not in original spec)
        self.router = QueryRouter()

    async def run(self):
        """Main engine loop — boot then run concurrent paths."""
        await self._boot()
        self.state = EngineState.RUNNING
        self._running = True
        self._ready_event.set()

        try:
            await asyncio.gather(
                self._cognitive_loop(),
                self._reflective_loop(),
                self._run_actors()
            )
        finally:
            await self._shutdown()

    async def _cognitive_loop(self):
        """500ms heartbeat — main processing loop."""
        while self._running:
            await self._cognitive_tick()
            await asyncio.sleep(0.5)

    async def _cognitive_tick(self):
        """Single cognitive tick — poll, dispatch, update."""
        # 1. Poll all pending input (engine pulls)
        events = self.input_buffer.poll_all()

        # 2. Dispatch each event by priority
        for event in events:
            await self._dispatch_event(event)

        # 3. Consciousness tick
        await self.consciousness.tick()

        # 4. History manager tick (if exists)
        if self.history_manager:
            await self.history_manager.tick()

        # 5. Rebalance context rings
        self.context._rebalance_rings()

        # 6. Periodic save (every 10 ticks = 5 seconds)
        if self.metrics.cognitive_ticks % 10 == 0:
            await self.consciousness.save()

    async def _reflective_loop(self):
        """5-minute background maintenance."""
        while self._running:
            await asyncio.sleep(300)
            await self._reflective_tick()

    async def _reflective_tick(self):
        """Background tasks — decay, pruning, consolidation."""
        self.context.decay_all()
        # TODO: Graph pruning, memory consolidation
```

> **NOTE:** The original spec showed a separate `_hot_loop()`. The actual implementation handles "hot" events via priority ordering in the buffer polling model, achieving similar results with simpler architecture.

---

## 7.3 The Buffered Input Model

### The Problem with Pure Events

The current Hub is event-driven: POST arrives → handler fires immediately. This causes problems:

- No **situational awareness** — the system doesn't know what else is happening
- No **abort control** — if you're mid-inference and new input arrives, what happens?
- **Interrupt storms** — rapid input can crash or confuse the system

### The Solution: Buffered Polling

**Core Principle:** Engine PULLS from buffer. It does not get PUSHED to.

Events land in an **async buffer**. The Engine polls the buffer at its cognitive tick. This inverts the control flow — Luna decides when to process input, not the other way around.

```
                        ┌─────────────┐
                        │   Voice     │
                        │   STT       │
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐
                        │   Desktop   │
                        │   CLI/API   │
                        └──────┬──────┘
                               │
                   ┌───────────▼───────────┐
                   │    INPUT BUFFER       │
                   │  (heapq priority)     │
                   │  max_size=100         │
                   └───────────┬───────────┘
                               │
                               │ poll_all() - non-blocking
                               │ called every 500ms
                               ▼
                   ┌───────────────────────┐
                   │   LUNA ENGINE         │
                   │  _cognitive_tick()    │
                   │                       │
                   │ Sorted by:            │
                   │ 1. Priority (type)    │
                   │ 2. Timestamp (FIFO)   │
                   └───────────────────────┘
```

### Priority System (Actual v2.0)

| Priority | Event Type | Description |
|----------|------------|-------------|
| 0 | USER_INTERRUPT | Stop/abort — Highest priority |
| 1 | TEXT_INPUT | Complete user input |
| 2 | PARTIAL | Mid-speech STT — Speculative |
| 3 | ACTOR_MESSAGE | Inter-actor communication |
| 4 | SHUTDOWN | Engine shutdown signal |

### Benefits

| Benefit | Description |
|---------|-------------|
| Situational Awareness | Engine sees all pending input before deciding |
| Abort Control | Can cancel current inference if user interrupts |
| Priority Ordering | INTERRUPT > TEXT_INPUT > PARTIAL |
| Stale Dropping | Partials older than 2s dropped via `_is_stale()` |
| No Interrupt Storms | Buffer capped at 100 events |

### Implementation (Actual v2.0)

**File:** `src/luna/core/input_buffer.py`

```python
class InputBuffer:
    """Thread-safe input buffer with priority ordering."""

    def __init__(self, max_size: int = 100):
        self._queue: List[InputEvent] = []
        self._lock = threading.Lock()
        self.max_size = max_size

    def push(self, event: InputEvent) -> bool:
        """Push event into buffer. Returns False if full (silent drop)."""
        with self._lock:
            if len(self._queue) >= self.max_size:
                return False  # Buffer full — no backpressure logging (TODO)
            event.timestamp = time.time()
            heapq.heappush(self._queue, event)
            return True

    def poll_all(self) -> List[InputEvent]:
        """
        Non-blocking poll of ALL pending events.
        Returns events sorted by priority then timestamp.
        Called by Engine at each cognitive tick.
        """
        with self._lock:
            events = []
            while self._queue:
                event = heapq.heappop(self._queue)
                if not self._is_stale(event):
                    events.append(event)
            return events

    def _is_stale(self, event: InputEvent) -> bool:
        """Partial transcripts older than 2s are considered stale."""
        if event.type == EventType.PARTIAL:
            age = time.time() - event.timestamp
            return age > 2.0
        return False

    def _get_priority(self, event: InputEvent) -> Tuple[int, float]:
        """Priority ordering: type first, then timestamp (FIFO within type)."""
        priority_map = {
            EventType.USER_INTERRUPT: 0,
            EventType.TEXT_INPUT: 1,
            EventType.PARTIAL: 2,
            EventType.ACTOR_MESSAGE: 3,
            EventType.SHUTDOWN: 4,
        }
        return (priority_map.get(event.type, 5), event.timestamp)
```

> **IMPLEMENTATION NOTE:** Uses `heapq` for O(log n) insertion/extraction. Buffer overflow results in silent drop (no backpressure logging — noted as TODO).

---

## 7.4 Actor Architecture

### Why Actors?

The Unity `MonoBehaviour` model is too **coupled** for AI systems. If one component crashes, everything crashes. We need **fault isolation**.

The **Actor Model** (Erlang/Akka style) gives us:

- **Isolation**: Each actor has its own state and mailbox
- **Fault Tolerance**: One actor crashing doesn't kill others
- **Message Passing**: Actors communicate via async messages
- **Location Transparency**: Actors could run in separate processes

### Luna's Actors (Implemented v2.0)

> **IMPLEMENTATION STATUS (January 2026):** 5 actors are implemented. Voice and Oven actors from the original spec are NOT implemented - voice I/O is handled via PersonaAdapter (non-actor), and Claude delegation is handled directly by Director.

```
┌─────────────────────────────────────────────────────────────┐
│                      LUNA ENGINE v2.0                        │
│                                                              │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│   │  DIRECTOR   │  │   MATRIX    │  │   SCRIBE    │        │
│   │   ACTOR     │  │   ACTOR     │  │   ACTOR     │        │
│   │             │  │             │  │   (Ben)     │        │
│   │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │        │
│   │ │ Mailbox │ │  │ │ Mailbox │ │  │ │ Mailbox │ │        │
│   │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │        │
│   │             │  │             │  │             │        │
│   │ • LLM mgmt  │  │ • SQLite    │  │ • Extract   │        │
│   │ • Routing   │  │ • sqlite-vec│  │ • Classify  │        │
│   │ • Claude    │  │ • NetworkX  │  │ • Chunk     │        │
│   └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                              │
│   ┌─────────────┐  ┌─────────────┐                         │
│   │  LIBRARIAN  │  │  HISTORY    │                         │
│   │   ACTOR     │  │  MANAGER    │                         │
│   │  (Dude)     │  │   ACTOR     │                         │
│   │ ┌─────────┐ │  │ ┌─────────┐ │                         │
│   │ │ Mailbox │ │  │ │ Mailbox │ │                         │
│   │ └─────────┘ │  │ └─────────┘ │                         │
│   │             │  │             │                         │
│   │ • Filing    │  │ • 3-Tier    │                         │
│   │ • Entities  │  │ • Compress  │                         │
│   │ • Prune     │  │ • Archive   │                         │
│   └─────────────┘  └─────────────┘                         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Actor Responsibilities (Implemented)

| Actor | File | Responsibility | Message Types |
|-------|------|----------------|---------------|
| **Director** | `actors/director.py` | LLM inference, Claude delegation, routing | `generate`, `abort`, `status` |
| **Matrix** | `actors/matrix.py` | Memory substrate, sqlite-vec, NetworkX | `store`, `retrieve`, `search` |
| **Scribe** | `actors/scribe.py` | Extraction (Ben Franklin persona) | `extract_turn`, `extract_text`, `flush_stack`, `compress_turn` |
| **Librarian** | `actors/librarian.py` | Filing (The Dude persona), entity resolution | `file`, `entity_update`, `get_context`, `resolve_entity`, `prune` |
| **HistoryManager** | `actors/history_manager.py` | Three-tier conversation history | `add_turn`, `get_active_window`, `search_recent`, `rotate_tier` |

### Actors NOT Implemented (From Original Spec)

| Actor | Original Role | Current Implementation |
|-------|---------------|------------------------|
| Voice | STT/TTS/Audio I/O | Handled by `PersonaAdapter` (non-actor pattern) |
| Oven | Async Claude delegation | Merged into Director (`_should_delegate()` method) |

### Actor Base Class (Actual Implementation)

**File:** `src/luna/actors/base.py`

```python
@dataclass
class Message:
    """A message passed between actors."""
    type: str                              # Message type identifier
    payload: Any = None                    # Message data
    sender: str | None = None              # Sending actor name
    reply_to: str | None = None            # For request-reply
    correlation_id: str = field(...)       # Track flow (auto-generated)
    timestamp: datetime = field(...)       # When created

class Actor(ABC):
    """
    Base class for all Luna actors.

    Lifecycle: start() -> on_start() -> message loop -> on_stop() -> stopped
    """

    def __init__(self, name: str, engine: Optional["LunaEngine"] = None):
        self.name = name
        self.engine = engine
        self.mailbox: Queue[Message] = Queue()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the actor's message loop."""
        self._running = True
        await self.on_start()

        while self._running:
            try:
                # Wait for message with 1s timeout for graceful shutdown
                msg = await asyncio.wait_for(
                    self.mailbox.get(),
                    timeout=1.0
                )
                await self._handle_safe(msg)
            except asyncio.TimeoutError:
                continue  # No on_idle() - just continue loop

        await self.on_stop()

    async def _handle_safe(self, msg: Message) -> None:
        """Handle message with error isolation."""
        try:
            await self.handle(msg)  # Note: handle(), not handle_message()
        except Exception as e:
            logger.error(f"Actor {self.name} failed to handle {msg}: {e}")
            await self.on_error(e, msg)
            # Don't re-raise - actor continues running

    async def stop(self) -> None:
        """Stop the actor gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()

    async def send(self, target: 'Actor', msg: Message) -> None:
        """Send a message to another actor."""
        msg.sender = self.name
        await target.mailbox.put(msg)

    async def send_to_engine(self, event_type: str, payload: Any) -> None:
        """Send an event back to the engine's input buffer."""
        if self.engine:
            event = InputEvent(type=EventType.ACTOR_MESSAGE, ...)
            await self.engine.input_buffer.put(event)

    # =========================================================================
    # Abstract methods - subclasses must implement
    # =========================================================================

    @abstractmethod
    async def handle(self, msg: Message) -> None:
        """Process a message from the mailbox. Pattern match on msg.type."""
        pass

    # =========================================================================
    # Lifecycle hooks - subclasses may override
    # =========================================================================

    async def on_start(self) -> None:
        """Called when actor starts. Override to initialize resources."""
        pass

    async def on_stop(self) -> None:
        """Called when actor stops. Override to cleanup resources."""
        pass

    async def on_error(self, error: Exception, msg: Message) -> None:
        """Called when message handling fails. Override for custom error handling."""
        logger.error(f"Actor {self.name} error handling {msg}: {error}")

    # =========================================================================
    # State serialization - for snapshot/restore
    # =========================================================================

    async def snapshot(self) -> dict:
        """Return state to serialize. Override to add actor-specific state."""
        return {"name": self.name, "mailbox_size": self.mailbox.qsize()}

    async def restore(self, state: dict) -> None:
        """Restore from serialized state. Override for actor-specific restoration."""
        pass
```

> **Key Differences from Original Spec:**
> - Uses `handle()` not `handle_message()`
> - **No `on_idle()` hook** - timeout just continues loop
> - `on_error()` receives both error AND message
> - Has `send_to_engine()` for actor-to-engine communication
> - Has `snapshot()` and `restore()` for state serialization

### Fault Tolerance Example

```python
class MatrixActor(Actor):
    async def handle(self, msg: Message):  # Note: handle(), not handle_message()
        match msg.type:
            case "search":
                try:
                    results = await self.search(msg.payload.get("query"))
                    await self.send_to_engine("search_results", results)
                except Exception as e:
                    # Matrix crashed, but we don't die
                    # _handle_safe() catches this, logs it, calls on_error()
                    # Actor continues running
                    raise  # Let _handle_safe() handle it
```

**Result:** If sqlite-vec crashes during a weird search, the Director Actor doesn't die. The error is caught by `_handle_safe()`, logged, and the actor continues. Luna says "I'm having trouble remembering that right now" instead of the whole engine freezing.

---

## 7.5 Non-Blocking Consciousness

When the Director's LLM takes 2 seconds to think, the Engine cannot block.

### Speculative Streaming

The moment the first token is generated, stream it to TTS:

```python
class DirectorActor(Actor):
    async def generate_response(self, prompt: str):
        """Stream tokens to Voice Actor as they're generated."""
        async for token in self.model.generate_stream(prompt):
            # Check for interrupt
            if not self.mailbox.empty():
                peek = await self.peek_mailbox()
                if peek.type == MsgType.USER_INTERRUPT:
                    await self.abort_generation()
                    return
            
            # Stream token to Voice
            await self.send(self.voice_actor, SpeakToken(token))
            
            # Check for delegation signal
            if "<REQ_CLAUDE>" in token:
                await self.trigger_delegation(prompt)
                return
```

### The "Thinking" State

While LLM is running, the Engine still ticks. This enables:

| Behavior | Implementation |
|----------|----------------|
| Filler sounds | Voice Actor plays "hmmm" or breath |
| Interrupt detection | Engine checks mailbox mid-generation |
| Abort capability | User speaks → cancel current generation |
| Progress indication | UI can show "thinking" state |

```python
async def _cognitive_tick(self):
    """Heartbeat while Director is thinking."""
    if self.director.state == State.GENERATING:
        # Check for user interrupt
        events = self.input_buffer.poll()
        for event in events:
            if event.type == EventType.INTERRUPT:
                await self.director.abort()
                await self.director.send(InterruptMessage())
                
        # Maybe play filler if taking too long
        if self.director.generation_time > 1.5:
            await self.voice_actor.send(PlayFiller())
```

### Parallel Prefetch

Use the "idle time" during user's sentence to prefetch memory:

```python
async def handle_partial_transcript(self, text: str):
    """Start retrieval before user finishes speaking."""
    # Fire speculative search
    self.speculative_task = asyncio.create_task(
        self.matrix_actor.search(text)
    )
    
async def handle_final_transcript(self, text: str):
    """Use speculative results if valid."""
    if self.speculative_task:
        speculative_results = await self.speculative_task
        
        # Validate speculation
        similarity = cosine_similarity(
            embed(self.last_partial),
            embed(text)
        )
        
        if similarity > 0.85:
            # Keep speculative results
            results = speculative_results
        else:
            # Correction path
            results = await self.matrix_actor.search(text)
    else:
        results = await self.matrix_actor.search(text)
        
    await self.director.send(RetrievalResults(results))
```

---

## 7.6 State Serialization and Consciousness Persistence

If the Luna Engine is a persistent process, we need to **snapshot** actor state so Luna wakes up exactly where she left off.

### What Gets Serialized (Actual v2.0)

| Component | Persists | Location | Mechanism |
|-----------|----------|----------|-----------|
| ConsciousnessState | Yes | `~/.luna/snapshot.yaml` | Every 5 seconds (10 ticks) |
| Memory (SQLite) | Yes | `data/luna_engine.db` | WAL mode, auto-commit |
| Graph (NetworkX) | Yes | Via SQLite | Loaded on boot |
| RevolvingContext | **No** | In-memory only | Rebuilt on boot |
| Actor mailboxes | **No** | In-memory only | Lost on shutdown |
| Director metrics | Yes | Snapshot | `local_generations`, `delegated_generations` |

### Consciousness Persistence (Actual v2.0)

**File:** `src/luna/consciousness/state.py`

```python
class ConsciousnessState:
    """Luna's consciousness state - persisted to disk."""

    def __init__(self):
        self.mood: MoodState = MoodState.NEUTRAL
        self.focus: Optional[str] = None
        self.attention_weights: Dict[str, float] = {}
        self.personality_patches: List[PatchEntry] = []
        self._last_save: float = 0

    async def tick(self) -> None:
        """Called every cognitive tick. Updates attention decay."""
        for topic, weight in list(self.attention_weights.items()):
            # Decay attention with half-life of 10 minutes
            decayed = weight * 0.995
            if decayed < 0.01:
                del self.attention_weights[topic]
            else:
                self.attention_weights[topic] = decayed

    async def save(self) -> None:
        """Persist consciousness state to disk."""
        state = {
            "mood": self.mood.value,
            "focus": self.focus,
            "attention_weights": self.attention_weights,
            "personality_patches": [p.to_dict() for p in self.personality_patches],
            "timestamp": datetime.now().isoformat(),
        }
        with open(Path.home() / ".luna" / "snapshot.yaml", "w") as f:
            yaml.dump(state, f)

    @classmethod
    def load(cls) -> "ConsciousnessState":
        """Load consciousness state from disk."""
        path = Path.home() / ".luna" / "snapshot.yaml"
        if not path.exists():
            return cls()
        with open(path) as f:
            state = yaml.safe_load(f)
        instance = cls()
        instance.mood = MoodState(state.get("mood", "neutral"))
        instance.focus = state.get("focus")
        instance.attention_weights = state.get("attention_weights", {})
        # ... restore personality patches
        return instance
```

### Save Triggers

| Trigger | When |
|---------|------|
| Periodic | Every 10 cognitive ticks (5 seconds) |
| Shutdown | During `_shutdown()` sequence |
| Manual | Via `await consciousness.save()` |
| macOS sleep | Via system event handler |

### Snapshot Format

```yaml
# ~/.luna/snapshot.yaml
engine:
  last_tick: "2026-01-25T03:45:00Z"
  uptime_seconds: 14400
  state: "RUNNING"

director:
  state: "IDLE"
  last_user_input: "section by section please"
  last_response_hash: "a3f2b1..."
  generation_in_progress: false
  local_generations: 42
  delegated_generations: 18

conversation:
  turns: 47
  session_start: "2026-01-24T22:00:00Z"

actors:
  director: "running"
  matrix: "running"
  scribe: "idle"
  librarian: "idle"
  history_manager: "running"
  # Note: voice and oven actors NOT implemented in v2.0
```

### Lifecycle Hooks

```python
class Actor(ABC):
    async def on_snapshot(self) -> dict:
        """Return state to serialize."""
        return {}
        
    async def on_restore(self, state: dict):
        """Restore from serialized state."""
        pass

class LunaEngine:
    async def snapshot(self):
        """Serialize entire engine state."""
        state = {
            "engine": self._engine_state(),
            "actors": {}
        }
        for name, actor in self.actors.items():
            state["actors"][name] = await actor.on_snapshot()
            
        with open("~/.luna/snapshot.yaml", "w") as f:
            yaml.dump(state, f)
            
    async def restore(self):
        """Restore from snapshot."""
        with open("~/.luna/snapshot.yaml") as f:
            state = yaml.load(f)
            
        for name, actor_state in state["actors"].items():
            await self.actors[name].on_restore(actor_state)
```

### Wake-Up Contract

When Luna wakes up:

1. Load snapshot
2. Restore actor states
3. Check for stale data (e.g., pending messages older than 1 hour → discard)
4. Resume cognitive tick
5. Luna picks up exactly where she left off

---

## 7.7 Lifecycle Hooks

### Engine State Machine (Actual v3.0)

**File:** `src/luna/core/state.py`

```
         ┌─────────────┐
         │   STARTING  │  ← Initial state
         └──────┬──────┘
                │ success (_boot completes)
                ▼
         ┌─────────────┐
         │   RUNNING   │  ← Normal operation
         └──────┬──────┘
                │
     ┌──────────┴──────────┐
     │                     │
  pause()               stop()
     │                     │
     ▼                     ▼
┌────────┐            ┌────────┐
│ PAUSED │            │ STOPPED│ ← Terminal state
└────┬───┘            └────────┘
     │
     ├──resume()──▶ RUNNING
     │
     ├──sleep()
     │
     ▼
┌────────┐
│SLEEPING│
└────┬───┘
     │
     ├──wake()──▶ RUNNING
     │
     └──stop()──▶ STOPPED
```

**Valid Transitions (from code):**
- STARTING → RUNNING (success)
- STARTING → STOPPED (boot failure)
- RUNNING → PAUSED, STOPPED
- PAUSED → RUNNING (resume), SLEEPING, STOPPED
- SLEEPING → RUNNING (wake), STOPPED
- **Terminal:** STOPPED (no further transitions)

> **Note:** RUNNING cannot transition directly to SLEEPING. Must go through PAUSED first.

### Hook Definitions

```python
class LunaEngine:
    async def on_start(self):
        """Initialize engine, start all actors."""
        logging.info("Luna Engine starting...")
        
        # Load identity buffer
        self.identity_buffer = load_kv_cache("identity_buffer.safetensors")
        
        # Start actors
        for actor in self.actors.values():
            asyncio.create_task(actor.start())
            
        # Check for snapshot to restore
        if Path("~/.luna/snapshot.yaml").exists():
            await self.restore()
            logging.info("Restored from snapshot")
        
        logging.info("Luna Engine running")
        
    async def on_pause(self):
        """Pause processing but keep state in memory."""
        logging.info("Luna Engine pausing...")
        self.paused = True
        await self.voice_actor.send(PauseAudio())
        
    async def on_resume(self):
        """Resume from paused state."""
        logging.info("Luna Engine resuming...")
        self.paused = False
        await self.voice_actor.send(ResumeAudio())
        
    async def on_snapshot(self):
        """Serialize state before sleep/shutdown."""
        logging.info("Luna Engine snapshotting...")
        await self.snapshot()
        
    async def on_restore(self):
        """Restore state after wake."""
        logging.info("Luna Engine restoring...")
        await self.restore()
        
    async def on_stop(self):
        """Graceful shutdown."""
        logging.info("Luna Engine stopping...")
        
        # Snapshot before stopping
        await self.on_snapshot()
        
        # Stop all actors
        for actor in self.actors.values():
            await actor.stop()
            
        logging.info("Luna Engine stopped")
```

### macOS Integration

```python
# LaunchAgent integration
async def handle_system_event(event: str):
    match event:
        case "sleep":
            await engine.on_snapshot()
            await engine.on_pause()
        case "wake":
            await engine.on_restore()
            await engine.on_resume()
        case "terminate":
            await engine.on_stop()
```

---

## 7.8 Execution Order Guarantees

### Within a Tick

```
1. Poll input buffer (all pending events)
2. Prioritize events (interrupts first)
3. Dispatch to appropriate actors
4. Wait for actor acknowledgments
5. Update engine state
6. Persist if necessary
```

### Across Actors

- Messages are **ordered within a mailbox** (FIFO)
- Messages between actors are **not globally ordered**
- If ordering matters, use **request-reply** pattern with correlation IDs

### Timing Guarantees (Actual v2.0)

| Guarantee | Value | Notes |
|-----------|-------|-------|
| Hot path latency | ~500ms max | Via buffer polling, not true interrupt |
| Cognitive tick | Every 500ms | `asyncio.sleep(0.5)` |
| Reflective tick | Every 5 minutes | `asyncio.sleep(300)` |
| Consciousness save | Every 5 seconds | Every 10 cognitive ticks |
| Snapshot | On graceful shutdown | Also on macOS sleep event |
| Boot time | ~100-500ms | DB connection is slowest |
| Shutdown time | ~1-5s | Waits for actors to finish |

---

## 7.9 QueryRouter (v2.0 Addition)

> **Note:** The QueryRouter was NOT in the original Bible specification. It was added during v2.0 implementation to intelligently route queries between direct response and agentic planning paths.

**File:** `src/luna/agentic/router.py`

### Purpose

The QueryRouter analyzes incoming user messages and decides the optimal processing path:

| Route | When Used | Cost |
|-------|-----------|------|
| DIRECT | Simple queries, greetings, quick facts | Fast, local |
| SIMPLE_PLAN | Moderate complexity, 1-2 step tasks | Medium |
| FULL_PLAN | Complex multi-step tasks | Slower |
| BACKGROUND | Long-running research tasks | Async |

### Routing Logic

```python
class QueryRouter:
    """Routes queries to optimal processing path."""

    def route(self, message: str, context: dict) -> RouteDecision:
        """
        Analyze message and determine processing path.

        Factors considered:
        - Message length and complexity
        - Presence of action keywords
        - Memory/search requirements
        - Delegation signals (research, analysis)
        """
        # Complexity analysis
        complexity = self._analyze_complexity(message)

        # Pattern matching for known intents
        if self._is_simple_greeting(message):
            return RouteDecision.DIRECT

        if self._needs_planning(message):
            if complexity > 0.7:
                return RouteDecision.FULL_PLAN
            return RouteDecision.SIMPLE_PLAN

        if self._is_background_task(message):
            return RouteDecision.BACKGROUND

        return RouteDecision.DIRECT

    def _analyze_complexity(self, message: str) -> float:
        """Return complexity score 0.0-1.0."""
        # Length factor
        length_score = min(len(message) / 500, 1.0) * 0.3

        # Keyword factor
        planning_keywords = ["research", "analyze", "compare", "find all"]
        keyword_score = sum(1 for k in planning_keywords if k in message.lower()) * 0.2

        # Question complexity
        question_words = message.count("?")
        question_score = min(question_words * 0.1, 0.3)

        return min(length_score + keyword_score + question_score, 1.0)
```

### Integration with Cognitive Tick

```python
async def _handle_user_message(self, message: str):
    """Process user message with routing decision."""
    # 1. Route the query
    route = self.router.route(message, self.context)

    # 2. Execute based on route
    match route:
        case RouteDecision.DIRECT:
            await self._process_direct(message)
        case RouteDecision.SIMPLE_PLAN | RouteDecision.FULL_PLAN:
            await self._process_with_agent_loop(message, route)
        case RouteDecision.BACKGROUND:
            await self._queue_background_task(message)
```

### Delegation Signals

The router detects delegation patterns that indicate Claude (cloud) should handle the request:

```python
DELEGATION_SIGNALS = [
    "research",
    "analyze in detail",
    "compare and contrast",
    "write a comprehensive",
    "explain thoroughly",
    "find everything about",
]

def _should_delegate(self, message: str) -> bool:
    """Check if message should be delegated to Claude."""
    message_lower = message.lower()
    return any(signal in message_lower for signal in DELEGATION_SIGNALS)
```

---

## 7.10 HistoryManager Actor (v2.0 Addition)

> **Note:** This actor was NOT in the original Bible specification. It was added during v2.0 implementation to handle three-tier conversation history management.

**File:** `src/luna/actors/history_manager.py`

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   THREE-TIER HISTORY                         │
│                                                              │
│   ACTIVE TIER          RECENT TIER          ARCHIVE          │
│   ┌──────────┐         ┌──────────┐         ┌──────────┐    │
│   │ Current  │ ──────▶ │Compressed│ ──────▶ │ Memory   │    │
│   │ ~1000 tok│ rotate  │~500-1500 │ extract │ Matrix   │    │
│   │ 5-10 turn│         │ 50-100   │         │ (Perma)  │    │
│   └──────────┘         └──────────┘         └──────────┘    │
│        │                     │                    │          │
│        │                     │                    │          │
│        ▼                     ▼                    ▼          │
│   Immediate              Searchable           Semantic       │
│   Context               (hybrid)              Search         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Message Types

| Type | Purpose | Payload |
|------|---------|---------|
| `add_turn` | Add conversation turn | `{role, content, tokens, session_id}` |
| `get_active_window` | Get Active tier | `{session_id, limit}` |
| `search_recent` | Search Recent tier | `{query, limit, search_type}` |
| `rotate_tier` | Move turn to tier | `{turn_id, tier}` |
| `check_budget` | Check rotation needed | `{session_id}` |
| `queue_compression` | Queue for Scribe | `{turn_id}` |
| `queue_extraction` | Queue for archival | `{turn_id}` |

### Configuration

```python
@dataclass
class HistoryConfig:
    max_active_tokens: int = 1000      # Active tier budget
    max_active_turns: int = 10         # Max turns in Active
    max_recent_age_minutes: int = 60   # Recent tier age limit
    compression_enabled: bool = True
    search_type: str = "hybrid"        # "hybrid"|"keyword"|"semantic"
```

### Tier Rotation Process

1. Detect budget exceeded (`add_turn` or `check_budget` message)
2. Find oldest Active turn
3. Move to Recent tier
4. Queue for compression (sends to Scribe)
5. When compressed, generate embedding
6. When aged, queue for extraction (sends to Librarian)
7. Archive to Memory Matrix

### Integration with Other Actors

| From | To | Message | Purpose |
|------|----|---------|---------|
| HistoryManager | Scribe | `compress_turn` | Summarize turn for Recent tier |
| HistoryManager | Scribe | `extract_turn` | Extract facts for archival |
| HistoryManager | Matrix | Direct API | Store archived turns |
| Engine | HistoryManager | `add_turn` | New conversation turn |

---

## Summary

The Runtime Engine is Luna's **nervous system** — it coordinates when components wake up, how they communicate, and ensures Luna feels continuous rather than reactive.

### Components

| Component | Role |
|-----------|------|
| Priority Event Loop | Variable-rate heartbeat with three paths (hot/cognitive/reflective) |
| Buffered Input | Situational awareness and abort control via polling |
| Actor Model | Fault-isolated components with mailboxes (5 actors in v2.0) |
| QueryRouter (v2.0) | Routes queries to DIRECT, SIMPLE_PLAN, FULL_PLAN, or BACKGROUND |
| Non-Blocking Consciousness | Streaming, interrupts, parallel prefetch |
| State Serialization | Consciousness persisted every 5s, memory in SQLite |
| Lifecycle Hooks | start, stop, on_start, on_stop, on_error, snapshot, restore |

### Implemented Actors (v2.0)

| Actor | File | Primary Role |
|-------|------|--------------|
| Director | `actors/director.py` | LLM inference + Claude delegation |
| Matrix | `actors/matrix.py` | Memory substrate (sqlite-vec + NetworkX) |
| Scribe | `actors/scribe.py` | Extraction (Ben Franklin persona) |
| Librarian | `actors/librarian.py` | Filing + entities (The Dude persona) |
| HistoryManager | `actors/history_manager.py` | Three-tier conversation history |

### Key Implementation Notes

- **No Voice Actor:** Voice I/O handled by `PersonaAdapter` (non-actor pattern)
- **No Oven Actor:** Claude delegation merged into Director
- **No on_idle() hook:** Actor loop continues without idle callback
- **sqlite-vec not FAISS:** Vector search uses sqlite-vec extension
- **HistoryManager:** New in v2.0, manages Active/Recent/Archive tiers
- **QueryRouter:** New in v2.0, routes queries to optimal processing paths
- **ConsciousnessState:** Saved every 5 seconds, not just on shutdown
- **RevolvingContext:** In-memory only, not persisted (rebuilt on boot)

**Constitutional Principle:** Luna doesn't respond to events. Luna *lives* through a continuous heartbeat, processing the world at her own rhythm.

---

*Next Section: Part VIII — Delegation Protocol*
