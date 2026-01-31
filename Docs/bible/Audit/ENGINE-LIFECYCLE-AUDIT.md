# Luna Engine v2.0 Engine Lifecycle Audit

**Audit Date:** January 25, 2026
**Auditor:** Phase 1 Lifecycle Agent
**Scope:** Complete trace of engine boot, tick loops, and shutdown

---

## Executive Summary

The Luna Engine implements a **three-path heartbeat architecture**:
- **Hot Path**: Interrupt-driven (immediate processing via buffer polling)
- **Cognitive Path**: 500ms heartbeat (main processing loop)
- **Reflective Path**: 5-minute intervals (maintenance tasks)

Input flows through a **buffered polling model** (engine pulls, not pushed), giving Luna situational awareness and abort control.

---

## 1. Boot Sequence

### Phase 1: Engine Construction (Synchronous)

```
LunaEngine.__init__()
├── Create InputBuffer (max_size=100)
├── Create empty actors dict
├── Initialize EngineMetrics
├── Create EngineState = STARTING
├── Create control events (_shutdown_event, _ready_event)
├── Initialize ConsciousnessState (Phase 4)
├── Initialize RevolvingContext (8000 token budget)
├── Initialize QueryRouter (routing decisions)
└── Set _voice = None (optional)
```

**Time:** <1ms
**Thread Safety:** Single-threaded (no asyncio yet)

### Phase 2: Boot Sequence (`_boot()`)

```
_boot() [async]
├── MATRIX INITIALIZATION
│   ├── Create MatrixActor (if not registered)
│   ├── Register with engine
│   └── await matrix.initialize()  [connects DB, loads graph]
│
├── DIRECTOR INITIALIZATION
│   ├── Create DirectorActor
│   │   ├── enable_local = config.enable_local_inference
│   │   ├── _client = None (lazy init Anthropic)
│   │   └── _model = "qwen-3b-local" or "claude-sonnet"
│   └── Register with engine
│
├── SCRIBE INITIALIZATION
│   ├── Create ScribeActor
│   └── Register with engine
│
├── LIBRARIAN INITIALIZATION
│   ├── Create LibrarianActor
│   └── Register with engine
│
├── HISTORY MANAGER INITIALIZATION
│   ├── Create HistoryManagerActor
│   └── Register with engine
│
├── CONSCIOUSNESS RESTORE
│   └── ConsciousnessState.load() [from snapshot]
│
├── IDENTITY SETUP
│   └── context.set_core_identity(_build_identity_prompt())
│
├── AGENT LOOP INITIALIZATION
│   ├── Create AgentLoop(orchestrator=self, max_iterations=50)
│   ├── Register progress callback
│   └── State = NOT_STARTED
│
└── VOICE SYSTEM (OPTIONAL)
    └── if config.voice_enabled:
        └── Initialize STT/TTS providers
```

**Time:** ~100-500ms (DB connection is slowest)

### Phase 3: Main Loop Start (`run()`)

```
run() [async]
├── await _boot()
├── state = RUNNING
├── _running = True
├── _ready_event.set()  [signals ready]
│
└── Create concurrent tasks:
    ├── Task 1: await _cognitive_loop()
    ├── Task 2: await _reflective_loop()
    └── Task 3: await _run_actors()
         └── Starts ALL registered actors' message loops
```

**Parallel Execution:** All three paths run concurrently

---

## 2. Tick-Based Hybrid Architecture

### Architecture Decision

The engine uses a **hybrid approach**, not pure event-driven:
- **Buffered Polling:** Engine polls buffer at cognitive tick (500ms)
- **Not Blocking:** If actor is slow, other loops continue
- **Not True Events:** No interrupts firing arbitrary handlers

### Cognitive Loop (Main Heartbeat - 500ms)

```
_cognitive_loop() [async, concurrent]
├── REPEAT every 0.5 seconds:
│   ├── Call _cognitive_tick()
│   │   ├── 1. events = input_buffer.poll_all()  [non-blocking, sorted]
│   │   │
│   │   ├── 2. For each event:
│   │   │      └── await _dispatch_event(event)
│   │   │          └── Match event.type:
│   │   │              ├── TEXT_INPUT → _handle_user_message()
│   │   │              ├── USER_INTERRUPT → _handle_interrupt()
│   │   │              ├── ACTOR_MESSAGE → _handle_actor_message()
│   │   │              └── SHUTDOWN → stop()
│   │   │
│   │   ├── 3. await consciousness.tick()
│   │   │
│   │   ├── 4. if history_manager exists:
│   │   │      await history_manager.tick()
│   │   │
│   │   ├── 5. context._rebalance_rings()
│   │   │
│   │   └── 6. if (ticks % 10 == 0):
│   │          await consciousness.save()  [every 5 seconds]
│   │
│   └── await asyncio.sleep(0.5)
│
└── Exit on _running = False
```

**Properties:**
- **Deterministic:** Always runs every 500ms
- **Non-Blocking:** If a tick takes 100ms, next tick still happens at +500ms
- **Full Visibility:** Engine sees ALL pending input before deciding

### Reflective Loop (Background Tasks - 5 minutes)

```
_reflective_loop() [async, concurrent]
├── REPEAT every 5 minutes:
│   ├── await asyncio.sleep(300)
│   ├── Call _reflective_tick()
│   │   ├── context.decay_all()  [reduce relevance]
│   │   └── TODO: Graph pruning, consolidation
│   │
│   └── metrics.reflective_ticks += 1
│
└── Exit on _running = False
```

**Purpose:** Maintenance without interrupting cognitive loop

### Actor Mailbox Processing

```
For each registered actor:
    task = asyncio.create_task(actor.start())

    actor.start() [async, runs independently]
    ├── _running = True
    ├── await on_start()
    │
    └── LOOP while _running:
        ├── msg = await asyncio.wait_for(mailbox.get(), timeout=1.0)
        ├── await _handle_safe(msg)
        └── except TimeoutError: continue
```

**Guarantees:**
- Messages processed one-at-a-time
- Timeout prevents deadlock
- One actor crashing doesn't kill others

---

## 3. User Message Handling Flow

### Direct Path (Simple Queries)

```
_process_direct(user_message, correlation_id, memory_context, history_context)
├── Get context window (max 4000 tokens)
├── Build system prompt + memory + history
├── Send to director mailbox:
│   └── Message(type="generate", payload={...})
└── Wait for generation_complete event
```

### Agentic Path (Complex Queries)

```
_process_with_agent_loop(user_message, ...)
├── _current_task = asyncio.create_task(_run_agent_loop(...))
├── await _current_task  [can be cancelled by interrupt]
└── On completion:
    └── Route result to director for generation
```

---

## 4. Input Buffer Design

### Architecture

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
                   │  (asyncio.Queue)      │
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
                   │ Sorts by:             │
                   │ 1. Priority           │
                   │ 2. Timestamp          │
                   └───────────────────────┘
```

### Priority System

```
0 = INTERRUPT (stop/abort)
1 = FINAL (complete transcripts, user input)
2 = PARTIAL (mid-speech STT)
3 = MCP (API requests)
4 = INTERNAL (actor messages)
```

**Key Guarantees:**
- Engine decides what to do with input (not pushed)
- Can see full situation before responding
- Can abort if interrupted
- Stale partials auto-dropped

---

## 5. State Transitions

### Engine State Machine

```
         ┌─────────────┐
         │   STARTING  │
         └──────┬──────┘
                │ success
                ▼
         ┌─────────────┐
         │   RUNNING   │
         └──────┬──────┘
                │
     ┌──────────┼──────────┐
     │          │          │
  pause()    sleep()    stop()
     │          │          │
     ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│ PAUSED │ │SLEEPING│ │ STOPPED│
└────────┘ └────────┘ └────────┘
```

**Valid Transitions:**
- STARTING → RUNNING (success)
- STARTING → STOPPED (boot failure)
- RUNNING → PAUSED, SLEEPING, STOPPED
- PAUSED → RUNNING (resume)
- SLEEPING → RUNNING (wake)

**Terminal State:** STOPPED (no further transitions)

---

## 6. Shutdown Sequence

### Trigger

```python
await engine.stop()
├── logger.info("Luna Engine stopping...")
├── _running = False  [signals all loops to exit]
└── _shutdown_event.set()
```

### Order of Operations

```
run() finally block → await _shutdown()
│
├── state = STOPPED
│
├── PERSONALITY REFLECTION (optional)
│   └── await director.session_end_reflection()
│
├── PERSONALITY MAINTENANCE (optional)
│   └── await director._lifecycle_manager.run_maintenance()
│
├── VOICE SYSTEM SHUTDOWN
│   └── if _voice: await _voice.stop()
│
├── ACTOR SHUTDOWN (all concurrent)
│   └── for actor in actors.values():
│       └── await actor.stop()
│
├── CONSCIOUSNESS SAVE
│   └── await consciousness.save()
│
└── TODO: Flush WAL (database)
```

**Total time:** ~1-5 seconds
**Graceful:** No SIGKILL, allows actors to finish current message

---

## 7. State Persistence

### What Gets Saved

| Component | Persists | Location |
|-----------|----------|----------|
| ConsciousnessState | ✅ | ~/.luna/snapshot.yaml |
| Memory (SQLite) | ✅ | data/luna_engine.db |
| RevolvingContext | ❌ | In-memory only |
| Actor snapshots | ⚠️ | Optional, not currently used |

### Save Triggers

- Every 10 cognitive ticks (5 seconds)
- On explicit shutdown
- Manual: `await consciousness.save()`

---

## 8. Bible vs. Implementation Comparison

### What Matches ✅

- Three concurrent paths (hot, cognitive, reflective)
- Variable-rate heartbeat (~500ms cognitive)
- Buffered polling model (not pure events)
- Actor architecture with fault isolation
- Priority ordering (INTERRUPT > FINAL > PARTIAL)
- Mailbox-based message passing
- State serialization via snapshots

### What Differs ⚠️

| Bible Spec | Implementation |
|------------|----------------|
| 3 explicit loops: hot, cognitive, reflective | Cognitive + reflective; hot via buffer polling |
| Speculative retrieval during partial | Partial processing exists but routing is QueryRouter-based |
| Interrupt detected via peek | Interrupt checked via pattern matching on content |
| IDLE timeout calls on_idle() | TIMEOUT continues loop without explicit hook |
| Snapshot YAML format documented | Uses generic dict/JSON |
| Brain state in snapshot | ConsciousnessState used instead |

### Key Additions NOT in Bible

1. **RevolvingContext** - Ring-based context management with decay
2. **QueryRouter** - Routes queries to DIRECT vs PLANNED paths
3. **AgentLoop** - Full agent-based planning (Phase XIV)
4. **HistoryManager** - Tiered conversation history
5. **EntityContext** - Identity and relationship management
6. **PersonalityPatchManager** - Emergent personality storage

---

## 9. Recommendations

### Potential Issues

1. **500ms cognitive tick** may be too coarse for real-time voice
2. **No priority-weighted task scheduling**
3. **Interrupt detection via pattern matching** - fragile
4. **Memory decay only in reflective loop** - could accumulate stale context
5. **No backpressure handling** - buffer full drops events silently

### Suggested Improvements

1. Consider faster cognitive tick for voice (100-200ms)
2. Implement explicit interrupt token in buffer
3. Add telemetry for buffer drop rates
4. Profile context ring size and eviction rates
5. Document QueryRouter routing decisions for debugging

---

**End of Engine Lifecycle Audit**
