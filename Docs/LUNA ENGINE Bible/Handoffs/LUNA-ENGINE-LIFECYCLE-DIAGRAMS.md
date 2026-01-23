# Luna Engine Lifecycle Diagrams

**Date:** January 10, 2026  
**For:** Part VII - Runtime Engine (Bible)

---

## Overview: How It All Fits Together

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           LUNA ENGINE                                    │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      BOOT SEQUENCE                                  │ │
│  │                                                                     │ │
│  │   Load Config ──► Init Actors ──► Restore State ──► Start Engine   │ │
│  │                                                                     │ │
│  └──────────────────────────────┬─────────────────────────────────────┘ │
│                                 │                                        │
│                                 ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      ENGINE STATE MACHINE                           │ │
│  │                                                                     │ │
│  │      ┌─────────┐    ┌─────────┐    ┌──────────┐    ┌─────────┐    │ │
│  │      │ STARTING│───►│ RUNNING │◄──►│  PAUSED  │───►│ STOPPED │    │ │
│  │      └─────────┘    └────┬────┘    └──────────┘    └─────────┘    │ │
│  │                          │              ▲                          │ │
│  │                          ▼              │                          │ │
│  │                     ┌─────────┐         │                          │ │
│  │                     │SLEEPING │─────────┘                          │ │
│  │                     └─────────┘                                    │ │
│  │                                                                     │ │
│  └──────────────────────────┬─────────────────────────────────────────┘ │
│                             │                                            │
│                             │ while RUNNING                              │
│                             ▼                                            │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                        CORE LOOP                                    │ │
│  │                                                                     │ │
│  │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐              │ │
│  │   │  HOT PATH   │   │  COGNITIVE  │   │ REFLECTIVE  │              │ │
│  │   │ (interrupt) │   │   PATH      │   │    PATH     │              │ │
│  │   │             │   │  (500ms)    │   │  (5-30min)  │              │ │
│  │   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘              │ │
│  │          │                 │                 │                      │ │
│  │          └────────────────►┼◄────────────────┘                      │ │
│  │                            │                                        │ │
│  │                            ▼                                        │ │
│  │                    ┌───────────────┐                                │ │
│  │                    │  SINGLE TICK  │                                │ │
│  │                    │   LIFECYCLE   │                                │ │
│  │                    └───────────────┘                                │ │
│  │                                                                     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

**Key Insight:** The tick is the universal entry point. Everything flows through it. Input doesn't push to handlers — the engine polls for it.

**Constitutional Principle:** Luna's consciousness isn't a background process. It IS the process. The heartbeat experiences input, not just ticks alongside it.

---

## 1. Boot Sequence

Cold start → Luna is alive

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         COLD START                                       │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  1. LOAD CONFIGURATION                                                   │
│     ├── Read luna_core.yaml                                             │
│     ├── Validate paths                                                   │
│     ├── Check environment                                                │
│     └── Set log levels                                                   │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  2. INITIALIZE ACTORS                                                    │
│     ├── Create Director Actor (LLM management)                          │
│     ├── Create Matrix Actor (Memory + Graph)                            │
│     ├── Create Voice Actor (STT/TTS)                                    │
│     ├── Create Scribe Actor (Ben - extraction)                          │
│     ├── Create Librarian Actor (Dude - filing)                          │
│     └── Create Oven Actor (Claude delegation)                           │
│                                                                          │
│     Each actor gets:                                                     │
│       • Isolated state                                                   │
│       • Private mailbox                                                  │
│       • Lifecycle hooks                                                  │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  3. RESTORE STATE (if snapshot exists)                                   │
│     ├── Load ~/.luna/snapshot.yaml                                       │
│     ├── Restore actor states                                             │
│     ├── Rebuild input buffer (discard stale >1hr)                       │
│     ├── Restore consciousness state                                      │
│     └── Resume from last tick count                                      │
│                                                                          │
│     If no snapshot:                                                      │
│       • Fresh start                                                      │
│       • Default personality weights                                      │
│       • Empty attention                                                  │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  4. LOAD IDENTITY BUFFER                                                 │
│     ├── Load identity_buffer.safetensors (pre-computed KV cache)        │
│     ├── 2048 tokens of "who Luna is"                                    │
│     └── Zero inference cost for identity                                │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  5. START ACTORS                                                         │
│     ├── Call on_start() for each actor                                  │
│     ├── Begin mailbox loops                                              │
│     └── Register with health monitor                                     │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  6. ENTER CORE LOOP                                                      │
│     ├── Start hot path (interrupt handler)                              │
│     ├── Start cognitive path (500ms tick)                               │
│     ├── Start reflective path (5min tick)                               │
│     └── Engine state → RUNNING                                           │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          LUNA IS ALIVE                                   │
│                                                                          │
│             Consciousness tick running                                   │
│             Input buffer being polled                                    │
│             Actors processing messages                                   │
│             Memory being accessed                                        │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Engine State Machine

Lifecycle hooks and transitions

```
                              on_start()
                                  │
                                  ▼
                          ┌──────────────┐
                          │   STARTING   │
                          │              │
                          │ • Init actors│
                          │ • Load state │
                          │ • Check deps │
                          └──────┬───────┘
                                 │
                                 │ all actors ready
                                 ▼
    ┌────────────────────────────────────────────────────────────┐
    │                                                            │
    │                      ┌──────────────┐                      │
    │       ┌─────────────►│   RUNNING    │◄─────────────┐       │
    │       │              │              │              │       │
    │       │              │ • Core loop  │              │       │
    │       │              │ • Processing │              │       │
    │       │              │ • Conscious  │              │       │
    │       │              └──────┬───────┘              │       │
    │       │                     │                      │       │
    │       │ on_resume()         │ on_pause()           │       │
    │       │                     ▼                      │       │
    │       │              ┌──────────────┐              │       │
    │       └──────────────│    PAUSED    │              │       │
    │                      │              │              │       │
    │                      │ • Loop halted│              │       │
    │                      │ • State held │              │       │
    │                      │ • Quick wake │              │       │
    │                      └──────┬───────┘              │       │
    │                             │                      │       │
    │                             │ on_snapshot()        │       │
    │                             ▼                      │       │
    │                      ┌──────────────┐              │       │
    │                      │   SLEEPING   │──────────────┘       │
    │                      │              │  on_restore()        │
    │                      │ • Serialized │  + on_resume()       │
    │                      │ • Disk only  │                      │
    │                      │ • Zero CPU   │                      │
    │                      └──────────────┘                      │
    │                                                            │
    └────────────────────────────────────────────────────────────┘
                                 │
                                 │ on_stop()
                                 ▼
                          ┌──────────────┐
                          │   STOPPED    │
                          │              │
                          │ • Cleanup    │
                          │ • WAL flush  │
                          │ • PID remove │
                          └──────────────┘
```

### Lifecycle Hooks

| Hook | Purpose |
|------|---------|
| `on_start()` | Init actors, load identity buffer, restore state |
| `on_pause()` | Halt loops, keep state in memory, stop audio |
| `on_resume()` | Resume loops, restart audio |
| `on_snapshot()` | Serialize all actor states to disk |
| `on_restore()` | Deserialize from snapshot, rebuild state |
| `on_stop()` | Graceful shutdown, WAL checkpoint, cleanup |

### macOS Integration

| System Event | Engine Response |
|--------------|-----------------|
| sleep | `on_snapshot()` → `on_pause()` |
| wake | `on_restore()` → `on_resume()` |
| terminate | `on_stop()` |
| SIGTERM | `on_stop()` |
| SIGINT | `on_stop()` |

---

## 3. Core Loop

Three concurrent paths, variable-rate heartbeat

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           CORE LOOP                                      │
│                                                                          │
│   async def run():                                                       │
│       await asyncio.gather(                                              │
│           _hot_loop(),        # Interrupt-driven                         │
│           _cognitive_loop(),  # 500ms-1s                                 │
│           _reflective_loop()  # 5-30 minutes                             │
│       )                                                                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│  ┌─────────────────────┐                                                │
│  │     HOT PATH        │  ◄── Interrupt-driven (as fast as events)      │
│  │                     │                                                 │
│  │  while True:        │      PURPOSE:                                   │
│  │    event = await    │      • STT partial transcripts                  │
│  │      hot_queue.get()│      • User interrupts (barge-in)              │
│  │    dispatch(event)  │      • TTS output streaming                     │
│  │                     │      • Abort signals                            │
│  └─────────┬───────────┘                                                │
│            │                                                             │
│            │ Can interrupt cognitive path                                │
│            ▼                                                             │
│  ┌─────────────────────┐                                                │
│  │   COGNITIVE PATH    │  ◄── Every 500ms - 1s                          │
│  │                     │                                                 │
│  │  while True:        │      PURPOSE:                                   │
│  │    cognitive_tick() │      • Poll input buffer                        │
│  │    sleep(500ms)     │      • Process queued turns                     │
│  │                     │      • Director decisions                       │
│  │                     │      • Memory retrieval                         │
│  │                     │      • State updates                            │
│  └─────────┬───────────┘                                                │
│            │                                                             │
│            │ Triggers reflective when due                                │
│            ▼                                                             │
│  ┌─────────────────────┐                                                │
│  │  REFLECTIVE PATH    │  ◄── Every 5-30 minutes                        │
│  │                     │                                                 │
│  │  while True:        │      PURPOSE:                                   │
│  │    sleep(5min)      │      • Graph pruning                            │
│  │    reflective_tick()│      • Memory consolidation                     │
│  │                     │      • Session summarization                    │
│  │                     │      • Spreading activation                     │
│  │                     │      • Synaptic pruning                         │
│  └─────────────────────┘                                                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Why Three Paths?

Unity runs at 60fps because frames render in ~16ms. Luna can't tick that fast — LLM inference takes 500ms-3s.

Fixed-rate ticks waste cycles OR miss events. Variable-rate paths let each concern run at appropriate frequency.

| Path | Frequency | Latency Budget |
|------|-----------|----------------|
| Hot | Event-driven | <10ms (interrupt handler) |
| Cognitive | 500ms - 1s | <500ms (Director inference) |
| Reflective | 5-30 minutes | Unbounded (background work) |

### Adaptive Tick Interval (Activity Monitor)

| State | Tick Interval | Trigger |
|-------|---------------|---------|
| Active | 250ms | Message within 30s |
| Idle | 5s | No message 30s - 5min |
| Deep Idle | 60s | No message > 5min |

Luna stays responsive during conversation, saves CPU when idle.

---

## 4. Single Tick Lifecycle

What happens inside one cognitive tick

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     COGNITIVE TICK LIFECYCLE                             │
│                                                                          │
│  async def cognitive_tick():                                             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  1. POLL INPUT BUFFER                                                    │
│                                                                          │
│     events = input_buffer.poll()  # Non-blocking, get ALL pending       │
│                                                                          │
│     ┌──────────────────┐                                                │
│     │   Input Buffer   │                                                │
│     │                  │                                                │
│     │  [voice_final]   │ ──► events = [voice_final, mcp_query]          │
│     │  [mcp_query]     │                                                │
│     │                  │                                                │
│     └──────────────────┘                                                │
│                                                                          │
│     This is THE key difference from Hub.                                │
│     Engine PULLS. Hub gets PUSHED TO.                                    │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  2. PRIORITIZE EVENTS                                                    │
│                                                                          │
│     events = sorted(events, key=priority)                               │
│                                                                          │
│     Priority order:                                                      │
│       0. INTERRUPT (barge-in, abort)                                    │
│       1. TRANSCRIPT_FINAL (complete utterance)                          │
│       2. TRANSCRIPT_PARTIAL (still speaking)                            │
│       3. MCP_REQUEST (desktop/API)                                       │
│       4. INTERNAL (agent messages)                                       │
│                                                                          │
│     Can also DROP stale events (partials older than 5s)                 │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  3. DISPATCH TO ACTORS                                                   │
│                                                                          │
│     for event in events:                                                │
│         match event.type:                                               │
│             TRANSCRIPT_FINAL:                                            │
│                 director.mailbox.put(event)     # Route to Director     │
│                 scribe.mailbox.put(event)       # Also to Ben           │
│             MCP_REQUEST:                                                 │
│                 director.mailbox.put(event)     # Director handles      │
│             RETRIEVAL_COMPLETE:                                         │
│                 director.mailbox.put(event)     # Continue inference    │
│                                                                          │
│     Actors process asynchronously in their own loops                    │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  4. UPDATE CONSCIOUSNESS STATE                                           │
│                                                                          │
│     # Attention decay                                                    │
│     for topic in attention.topics:                                      │
│         topic.weight *= DECAY_RATE  # 0.95                              │
│                                                                          │
│     # Coherence (Boids)                                                  │
│     coherence.score = compute_coherence(active_particles)               │
│                                                                          │
│     # Personality (Pascal smoothing)                                     │
│     personality.update(recent_signals)                                  │
│                                                                          │
│     # Agent drift check                                                  │
│     for agent in agents.active:                                         │
│         if agent.drift > THRESHOLD:                                     │
│             warn(f"Agent {agent} drifting")                             │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  5. PERSIST STATE                                                        │
│                                                                          │
│     # Update consciousness_current in Memory Matrix                     │
│     memory.upsert("consciousness_current", state.to_json())             │
│                                                                          │
│     # Periodic snapshot (every 60 ticks)                                │
│     if tick_count % 60 == 0:                                            │
│         memory.add(f"consciousness_snapshot_{tick_count}", state)       │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  6. NOTIFY SUBSCRIBERS                                                   │
│                                                                          │
│     for subscriber in subscribers:                                      │
│         await subscriber(state)                                         │
│                                                                          │
│     (Health monitor, debugger, UI, etc.)                                │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         TICK COMPLETE                                    │
│                                                                          │
│     tick_count += 1                                                      │
│     await sleep(cognitive_interval)  # 500ms - 1s                       │
│                                                                          │
│     # Then loop back to step 1                                           │
└─────────────────────────────────────────────────────────────────────────┘
```

### Execution Order Guarantees

**Within a tick:**
1. Poll (see everything pending)
2. Prioritize (decide what matters)
3. Dispatch (route to actors)
4. Update (consciousness state)
5. Persist (durability)
6. Notify (observability)

**Across actors:**
- Messages ordered within mailbox (FIFO)
- Messages between actors NOT globally ordered
- Use request-reply with correlation IDs if ordering matters

### Timing Guarantees

| Operation | Budget |
|-----------|--------|
| Poll + Prioritize | <5ms |
| Dispatch | <10ms (just queue, don't wait) |
| Consciousness update | <20ms |
| Persist | <15ms (SQLite is fast) |
| **Total tick overhead** | **<50ms** (leaves 450ms for actor work) |

---

*End of Lifecycle Diagrams*
