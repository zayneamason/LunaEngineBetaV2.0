# Bible Update: Part VII - The Runtime Engine

**Status:** DRAFT — Ready for review  
**New Section:** Not in original Bible  
**Date:** December 29, 2025  
**Primary Contributor:** Gemini (Optimization), Claude (Architecture)

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

```
┌─────────────────────────────────────────────────────────────┐
│                    HOT PATH (Interrupt-Driven)               │
│                                                              │
│   • STT partial transcripts                                  │
│   • User interrupts (barge-in)                              │
│   • TTS output streaming                                     │
│   • Frequency: As fast as events arrive                     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                  COGNITIVE PATH (~1-2 Hz)                    │
│                                                              │
│   • Director heartbeat                                       │
│   • "Is user still speaking?"                               │
│   • "Did retrieval complete?"                               │
│   • "Should I start speculative inference?"                 │
│   • Frequency: Every 500ms - 1s                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────────┐
│                REFLECTIVE PATH (Minutes)                     │
│                                                              │
│   • Graph pruning and maintenance                           │
│   • Session summarization                                    │
│   • Background reflection tick                              │
│   • Memory consolidation                                     │
│   • Frequency: Every 5-30 minutes                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class LunaEngine:
    def __init__(self):
        self.hot_queue = asyncio.Queue()      # Interrupt-driven
        self.cognitive_interval = 0.5          # 2 Hz
        self.reflective_interval = 300         # 5 minutes
        self.actors = ActorRegistry()
        
    async def run(self):
        """Main engine loop — three concurrent paths."""
        await asyncio.gather(
            self._hot_loop(),
            self._cognitive_loop(),
            self._reflective_loop()
        )
    
    async def _hot_loop(self):
        """Process interrupts immediately."""
        while True:
            event = await self.hot_queue.get()
            await self._dispatch_hot(event)
    
    async def _cognitive_loop(self):
        """Director heartbeat — check state, make decisions."""
        while True:
            await self._cognitive_tick()
            await asyncio.sleep(self.cognitive_interval)
    
    async def _reflective_loop(self):
        """Background maintenance and growth."""
        while True:
            await asyncio.sleep(self.reflective_interval)
            await self._reflective_tick()
```

---

## 7.3 The Buffered Input Model

### The Problem with Pure Events

The current Hub is event-driven: POST arrives → handler fires immediately. This causes problems:

- No **situational awareness** — the system doesn't know what else is happening
- No **abort control** — if you're mid-inference and new input arrives, what happens?
- **Interrupt storms** — rapid input can crash or confuse the system

### The Solution: Buffered Polling

Events land in an **async buffer**. The Engine polls the buffer at its heartbeat.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Voice     │     │   Desktop   │     │    MCP      │
│   Input     │     │   Input     │     │   Input     │
└──────┬──────┘     └──────┬──────┘     └──────┬──────┘
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                           ▼
              ┌────────────────────────┐
              │     INPUT BUFFER       │
              │                        │
              │  [voice_partial_1]     │
              │  [voice_partial_2]     │
              │  [voice_final]         │
              │  [mcp_query]           │
              │                        │
              └────────────────────────┘
                           │
                           │ Engine polls at heartbeat
                           ▼
              ┌────────────────────────┐
              │     LUNA ENGINE        │
              │                        │
              │  • Sees full queue     │
              │  • Makes decisions     │
              │  • Can prioritize      │
              │  • Can drop stale      │
              │                        │
              └────────────────────────┘
```

### Benefits

| Benefit | Description |
|---------|-------------|
| Situational Awareness | Engine sees all pending input before deciding |
| Abort Control | Can cancel current inference if user interrupts |
| Priority Ordering | Can process urgent events first |
| Stale Dropping | Can discard outdated partials |
| No Interrupt Storms | Buffer absorbs bursts |

### Implementation

```python
class InputBuffer:
    def __init__(self):
        self.queue = asyncio.Queue()
        
    async def push(self, event: InputEvent):
        """Called by interfaces (Voice, Desktop, MCP)."""
        event.timestamp = time.time()
        await self.queue.put(event)
        
    def poll(self) -> list[InputEvent]:
        """Called by Engine at heartbeat. Returns all pending."""
        events = []
        while not self.queue.empty():
            try:
                events.append(self.queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return events
    
    def poll_prioritized(self) -> list[InputEvent]:
        """Poll with priority ordering."""
        events = self.poll()
        
        # Interrupts first, then finals, then partials
        return sorted(events, key=lambda e: (
            0 if e.type == EventType.INTERRUPT else
            1 if e.type == EventType.TRANSCRIPT_FINAL else
            2
        ))
```

---

## 7.4 Actor Architecture

### Why Actors?

The Unity `MonoBehaviour` model is too **coupled** for AI systems. If one component crashes, everything crashes. We need **fault isolation**.

The **Actor Model** (Erlang/Akka style) gives us:

- **Isolation**: Each actor has its own state and mailbox
- **Fault Tolerance**: One actor crashing doesn't kill others
- **Message Passing**: Actors communicate via async messages
- **Location Transparency**: Actors could run in separate processes

### Luna's Actors

```
┌─────────────────────────────────────────────────────────────┐
│                      LUNA ENGINE                             │
│                                                              │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│   │  DIRECTOR   │  │   MATRIX    │  │    VOICE    │        │
│   │   ACTOR     │  │   ACTOR     │  │   ACTOR     │        │
│   │             │  │             │  │             │        │
│   │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │        │
│   │ │ Mailbox │ │  │ │ Mailbox │ │  │ │ Mailbox │ │        │
│   │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │        │
│   │             │  │             │  │             │        │
│   │ • LLM mgmt  │  │ • SQLite    │  │ • STT       │        │
│   │ • State     │  │ • FAISS     │  │ • TTS       │        │
│   │ • Routing   │  │ • Graph     │  │ • Audio I/O │        │
│   └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                              │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│   │   SCRIBE    │  │  LIBRARIAN  │  │    OVEN     │        │
│   │   ACTOR     │  │   ACTOR     │  │   ACTOR     │        │
│   │             │  │             │  │             │        │
│   │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │        │
│   │ │ Mailbox │ │  │ │ Mailbox │ │  │ │ Mailbox │ │        │
│   │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │        │
│   │             │  │             │  │             │        │
│   │ • Extract   │  │ • Filing    │  │ • Claude    │        │
│   │ • Classify  │  │ • Edges     │  │ • Research  │        │
│   │ • Chunk     │  │ • Prune     │  │ • Async     │        │
│   └─────────────┘  └─────────────┘  └─────────────┘        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Actor Responsibilities

| Actor | Responsibility | Mailbox Receives |
|-------|----------------|------------------|
| Director | LLM inference, state machine, routing | Transcripts, retrieval results, interrupts |
| Matrix | Memory storage, search, graph ops | Queries, insertions, updates |
| Voice | Audio I/O, STT, TTS | Audio streams, text to speak |
| Scribe | Extraction, classification, chunking | Conversation turns, documents |
| Librarian | Filing, edge creation, maintenance | Extracted nodes, filing requests |
| Oven | Async Claude delegation, research | Heavy tasks, delegation requests |

### Actor Base Class

```python
from abc import ABC, abstractmethod
import asyncio

class Actor(ABC):
    def __init__(self, name: str, engine: 'LunaEngine'):
        self.name = name
        self.engine = engine
        self.mailbox = asyncio.Queue()
        self.running = False
        
    async def start(self):
        """Start the actor's message loop."""
        self.running = True
        await self.on_start()
        while self.running:
            try:
                msg = await asyncio.wait_for(
                    self.mailbox.get(), 
                    timeout=1.0
                )
                await self.handle_message(msg)
            except asyncio.TimeoutError:
                await self.on_idle()
            except Exception as e:
                await self.on_error(e)
                
    async def stop(self):
        """Stop the actor gracefully."""
        self.running = False
        await self.on_stop()
        
    async def send(self, target: 'Actor', msg: Message):
        """Send a message to another actor."""
        await target.mailbox.put(msg)
        
    @abstractmethod
    async def handle_message(self, msg: Message):
        """Process a message from the mailbox."""
        pass
        
    async def on_start(self):
        """Called when actor starts."""
        pass
        
    async def on_stop(self):
        """Called when actor stops."""
        pass
        
    async def on_idle(self):
        """Called when mailbox is empty (1s timeout)."""
        pass
        
    async def on_error(self, error: Exception):
        """Called when message handling fails."""
        logging.error(f"Actor {self.name} error: {error}")
```

### Fault Tolerance Example

```python
class MatrixActor(Actor):
    async def handle_message(self, msg: Message):
        match msg.type:
            case MsgType.SEARCH:
                try:
                    results = await self.search(msg.query)
                    await self.send(msg.reply_to, SearchResults(results))
                except Exception as e:
                    # Matrix crashed, but we don't die
                    # Send empty results, Director handles gracefully
                    logging.error(f"Matrix search failed: {e}")
                    await self.send(msg.reply_to, SearchResults([]))
```

**Result:** If FAISS crashes during a weird search, the Director Actor doesn't die. It receives empty results and Luna says "I'm having trouble remembering that right now" instead of the whole engine freezing.

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

## 7.6 State Serialization

If the Luna Engine is a persistent process, we need to **snapshot** actor state so Luna wakes up exactly where she left off.

### What Gets Serialized

| Component | Serialization |
|-----------|---------------|
| Director state | Current conversation state, active context |
| Identity Buffer | Already in `.safetensors` |
| Matrix state | SQLite is already persistent |
| Actor mailboxes | Pending messages (optional) |
| Engine state | Active threads, last tick time |

### Snapshot Format

```yaml
# ~/.luna/snapshot.yaml
engine:
  last_tick: "2025-12-29T03:45:00Z"
  uptime_seconds: 14400
  
director:
  state: "IDLE"
  last_user_input: "section by section please"
  last_response_hash: "a3f2b1..."
  generation_in_progress: false
  
conversation:
  turns: 47
  session_start: "2025-12-28T22:00:00Z"
  
actors:
  director: "running"
  matrix: "running"
  voice: "paused"  # Mac was closed
  scribe: "idle"
  librarian: "idle"
  oven: "idle"
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

### Full Lifecycle

```
┌─────────────────────────────────────────────────────────────┐
│                     ENGINE LIFECYCLE                         │
│                                                              │
│   on_start()                                                │
│       │                                                      │
│       ▼                                                      │
│   ┌─────────┐                                               │
│   │ RUNNING │ ◄─────────────────────────────────┐           │
│   └────┬────┘                                   │           │
│        │                                        │           │
│        │ on_pause()                  on_resume()│           │
│        ▼                                        │           │
│   ┌─────────┐                                   │           │
│   │ PAUSED  │ ──────────────────────────────────┘           │
│   └────┬────┘                                               │
│        │                                                     │
│        │ on_snapshot()                                       │
│        ▼                                                     │
│   ┌─────────┐                                               │
│   │ SLEEPING│                                               │
│   └────┬────┘                                               │
│        │                                                     │
│        │ on_restore() + on_start()                          │
│        ▼                                                     │
│   ┌─────────┐                                               │
│   │ RUNNING │                                               │
│   └────┬────┘                                               │
│        │                                                     │
│        │ on_stop()                                          │
│        ▼                                                     │
│   ┌─────────┐                                               │
│   │ STOPPED │                                               │
│   └─────────┘                                               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

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

### Timing Guarantees

| Guarantee | Value |
|-----------|-------|
| Hot path latency | Best-effort, typically <10ms |
| Cognitive tick | Every 500ms ± 100ms |
| Reflective tick | Every 5 minutes ± 30 seconds |
| Snapshot | Before sleep, on graceful shutdown |

---

## Summary

The Runtime Engine is Luna's **nervous system** — it coordinates when components wake up, how they communicate, and ensures Luna feels continuous rather than reactive.

| Component | Role |
|-----------|------|
| Priority Event Loop | Variable-rate heartbeat with three paths |
| Buffered Input | Situational awareness and abort control |
| Actor Model | Fault-isolated components with mailboxes |
| Non-Blocking Consciousness | Streaming, interrupts, parallel prefetch |
| State Serialization | Wake up where you left off |
| Lifecycle Hooks | Start, pause, resume, snapshot, restore, stop |

**Constitutional Principle:** Luna doesn't respond to events. Luna *lives* through a continuous heartbeat, processing the world at her own rhythm.

---

*Next Section: Part VIII — Delegation Protocol*
