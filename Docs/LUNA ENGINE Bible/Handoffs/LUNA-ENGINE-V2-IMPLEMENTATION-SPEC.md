# Luna Engine v2.0 — Greenfield Implementation Spec

**Date:** January 10, 2026  
**For:** Claude Code Implementation  
**Status:** Ready to build

---

## Executive Summary

We're building a **consciousness engine** that uses LLMs the way game engines use GPUs. The LLM (Claude API today, local Director eventually) is stateless inference. The engine provides identity, memory, state, and orchestration.

**This is a complete rewrite.** The existing Hub will be deprecated. Memory Matrix data and Luna's identity will migrate to the new system.

---

## The Core Insight

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        LUNA ENGINE                                       │
│                                                                          │
│   Everything the LLM doesn't know between calls:                        │
│   • Who it is (identity)                                                │
│   • What it remembers (memory)                                          │
│   • What it's paying attention to (consciousness state)                 │
│   • What it can do (tools)                                              │
│   • What just happened (conversation history)                           │
│                                                                          │
│   We inject ALL of this every single call.                              │
│   The LLM just predicts tokens. We provide the soul.                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Reference Documentation

Read these before implementing:

| Document | Location | What It Covers |
|----------|----------|----------------|
| **Philosophy** | `01-PHILOSOPHY.md` | Why Luna exists, sovereignty principles |
| **Architecture** | `02-SYSTEM-ARCHITECTURE.md` | Layer model, actor system |
| **Memory Matrix** | `03-MEMORY-MATRIX.md` | Storage substrate (SQLite + vectors + graph) |
| **The Scribe** | `04-THE-SCRIBE.md` | Ben Franklin — extraction system |
| **The Librarian** | `05-THE-LIBRARIAN.md` | The Dude — filing and retrieval |
| **Director LLM** | `06-DIRECTOR-LLM.md` | Local model spec (future) |
| **Runtime Engine** | `07-RUNTIME-ENGINE.md` | Actor model, tick loop |
| **Delegation** | `08-DELEGATION-PROTOCOL.md` | When to call Claude API |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           LUNA ENGINE v2.0                               │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                         INPUT LAYER                                 │ │
│  │                                                                     │ │
│  │   Voice ────┐                                                       │ │
│  │             ├──► Input Buffer ──► Engine polls every tick          │ │
│  │   MCP ──────┘                                                       │ │
│  │                                                                     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                         CORE LOOP                                   │ │
│  │                                                                     │ │
│  │   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐              │ │
│  │   │  HOT PATH   │   │  COGNITIVE  │   │ REFLECTIVE  │              │ │
│  │   │ (interrupt) │   │   (500ms)   │   │  (5-30min)  │              │ │
│  │   └─────────────┘   └─────────────┘   └─────────────┘              │ │
│  │                                                                     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                         ACTOR LAYER                                 │ │
│  │                                                                     │ │
│  │   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │ │
│  │   │ Director │ │  Matrix  │ │  Scribe  │ │ Librarian│ │   Oven   │ │ │
│  │   │  (LLM)   │ │ (Memory) │ │  (Ben)   │ │ (Dude)   │ │ (Claude) │ │ │
│  │   └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘ │ │
│  │                                                                     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                         SUBSTRATE                                   │ │
│  │                                                                     │ │
│  │   Memory Matrix: SQLite + sqlite-vec + NetworkX graph              │ │
│  │   Single file: ~/.luna/luna.db                                     │ │
│  │                                                                     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
luna-engine/
├── pyproject.toml              # uv/poetry project config
├── README.md
│
├── src/
│   └── luna/
│       ├── __init__.py
│       ├── engine.py           # Main engine class, lifecycle, core loop
│       ├── config.py           # Configuration loading
│       │
│       ├── core/
│       │   ├── __init__.py
│       │   ├── input_buffer.py # Thread-safe input queue
│       │   ├── tick.py         # Tick lifecycle (poll → prioritize → dispatch → update)
│       │   ├── state.py        # Engine state machine (STARTING, RUNNING, PAUSED, etc)
│       │   └── events.py       # Event types and priority
│       │
│       ├── actors/
│       │   ├── __init__.py
│       │   ├── base.py         # Actor base class with mailbox
│       │   ├── director.py     # LLM management, response generation
│       │   ├── matrix.py       # Memory operations (wraps substrate)
│       │   ├── scribe.py       # Ben — extraction
│       │   ├── librarian.py    # Dude — filing and retrieval
│       │   └── oven.py         # Claude API delegation
│       │
│       ├── substrate/
│       │   ├── __init__.py
│       │   ├── database.py     # SQLite connection management
│       │   ├── memory.py       # Memory Matrix operations
│       │   ├── vectors.py      # sqlite-vec integration
│       │   ├── graph.py        # NetworkX graph operations
│       │   └── schema.sql      # Database schema
│       │
│       ├── consciousness/
│       │   ├── __init__.py
│       │   ├── state.py        # Attention, personality, coherence
│       │   ├── attention.py    # Topic tracking, decay
│       │   └── personality.py  # Pascal smoothing, weights
│       │
│       ├── identity/
│       │   ├── __init__.py
│       │   ├── persona.py      # PersonaCore — who Luna is
│       │   ├── virtues.py      # Personality traits
│       │   └── buffer.py       # Identity buffer (future: KV cache)
│       │
│       ├── inference/
│       │   ├── __init__.py
│       │   ├── base.py         # Abstract LLM interface
│       │   ├── claude.py       # Claude API implementation
│       │   ├── local.py        # Local MLX implementation (future)
│       │   └── context.py      # Prompt assembly
│       │
│       ├── tools/
│       │   ├── __init__.py
│       │   ├── registry.py     # MCP tool registry
│       │   └── executor.py     # Tool execution
│       │
│       └── api/
│           ├── __init__.py
│           ├── server.py       # FastAPI server
│           ├── routes.py       # HTTP endpoints
│           └── mcp.py          # MCP server implementation
│
├── tests/
│   ├── test_engine.py
│   ├── test_actors.py
│   ├── test_substrate.py
│   └── ...
│
└── scripts/
    ├── migrate_memory.py       # Migrate from old Hub
    └── run.py                  # Entry point
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)

**Goal:** Engine boots, ticks, and can process a simple message.

```
Build:
├── Engine lifecycle (start → running → stop)
├── Input buffer (thread-safe queue)
├── Basic tick loop (poll → dispatch)
├── Actor base class with mailbox
├── Director actor (Claude API only)
├── Matrix actor (stub — in-memory dict)
└── FastAPI server with /message endpoint

Test:
└── Send message → get response from Claude
```

**No memory yet.** Just prove the architecture works.

### Phase 2: Memory Substrate (Week 2)

**Goal:** Memory Matrix operational, can store and retrieve.

```
Build:
├── SQLite database with schema
├── sqlite-vec for embeddings
├── NetworkX graph for relationships
├── Memory Matrix operations (add, search, get_context)
├── Matrix actor (wraps substrate)
└── Migrate existing data from old Hub

Test:
├── Store a fact → retrieve it
├── Vector similarity search works
└── Graph traversal works
```

### Phase 3: Extraction Pipeline (Week 3)

**Goal:** Ben and Dude operational.

```
Build:
├── Scribe actor (Ben)
│   ├── Conversation chunking
│   ├── Fact extraction (via Claude)
│   └── Classification (FACT, DECISION, PROBLEM, ACTION)
├── Librarian actor (Dude)
│   ├── Filing to Matrix
│   ├── Entity resolution
│   └── Edge creation
└── Async pipeline (extract → file in background)

Test:
├── Conversation gets chunked correctly
├── Facts extracted and classified
└── Edges created between related nodes
```

### Phase 4: Consciousness (Week 4)

**Goal:** Luna has state that persists and evolves.

```
Build:
├── Consciousness state model
│   ├── Attention (topic tracking, decay)
│   ├── Personality weights
│   └── Coherence (Boids algorithm)
├── State updates in tick loop
├── Persistence to Matrix
└── Identity buffer (system prompt assembly)

Test:
├── Attention decays over time
├── Personality shifts based on conversation
└── State persists across restarts
```

### Phase 5: Voice Integration (Week 5)

**Goal:** Voice app talks to new engine.

```
Build:
├── Voice-specific endpoints
├── Hot path for interrupts
├── STT/TTS coordination
└── Barge-in handling

Test:
└── Full voice conversation works
```

### Phase 6: Polish & Migration (Week 6)

```
Build:
├── Health monitoring
├── Graceful shutdown
├── macOS integration (sleep/wake)
├── Snapshot/restore
└── Full migration from old Hub

Test:
├── Engine survives crashes
├── State survives restarts
└── All old data accessible
```

---

## Key Abstractions

### Actor Base Class

```python
from abc import ABC, abstractmethod
from asyncio import Queue
from dataclasses import dataclass
from typing import Any

@dataclass
class Message:
    type: str
    payload: Any
    correlation_id: str | None = None

class Actor(ABC):
    def __init__(self, name: str):
        self.name = name
        self.mailbox: Queue[Message] = Queue()
        self._running = False
    
    async def start(self):
        self._running = True
        await self.on_start()
        while self._running:
            msg = await self.mailbox.get()
            try:
                await self.handle(msg)
            except Exception as e:
                await self.on_error(e, msg)
    
    async def stop(self):
        self._running = False
        await self.on_stop()
    
    @abstractmethod
    async def handle(self, msg: Message) -> None:
        """Process a message."""
        pass
    
    async def on_start(self) -> None:
        """Called when actor starts."""
        pass
    
    async def on_stop(self) -> None:
        """Called when actor stops."""
        pass
    
    async def on_error(self, error: Exception, msg: Message) -> None:
        """Called when message handling fails."""
        pass
```

### Input Buffer

```python
from asyncio import Queue
from dataclasses import dataclass
from enum import IntEnum
from datetime import datetime

class EventPriority(IntEnum):
    INTERRUPT = 0      # Barge-in, abort
    FINAL = 1          # Complete utterance
    PARTIAL = 2        # Still speaking
    MCP = 3            # Desktop/API request
    INTERNAL = 4       # Actor-to-actor

@dataclass
class InputEvent:
    type: str
    payload: Any
    priority: EventPriority
    timestamp: datetime
    
class InputBuffer:
    def __init__(self):
        self._queue: Queue[InputEvent] = Queue()
    
    async def put(self, event: InputEvent) -> None:
        await self._queue.put(event)
    
    def poll_all(self) -> list[InputEvent]:
        """Non-blocking: get all pending events."""
        events = []
        while not self._queue.empty():
            try:
                events.append(self._queue.get_nowait())
            except:
                break
        return sorted(events, key=lambda e: (e.priority, e.timestamp))
```

### Engine Core Loop

```python
class LunaEngine:
    async def run(self):
        """Main entry point."""
        await self._boot()
        
        try:
            await asyncio.gather(
                self._hot_loop(),
                self._cognitive_loop(),
                self._reflective_loop(),
            )
        finally:
            await self._shutdown()
    
    async def _cognitive_loop(self):
        """500ms tick — main processing."""
        while self._state == EngineState.RUNNING:
            await self._cognitive_tick()
            await asyncio.sleep(self._tick_interval)
    
    async def _cognitive_tick(self):
        """Single tick lifecycle."""
        # 1. Poll
        events = self.input_buffer.poll_all()
        
        # 2. Dispatch to actors
        for event in events:
            await self._dispatch(event)
        
        # 3. Update consciousness
        await self.consciousness.tick()
        
        # 4. Persist
        await self._persist_state()
```

---

## Migration Strategy

### Memory Matrix Data

The existing Memory Matrix (in the old Hub) contains:
- Memory nodes (facts, decisions, etc.)
- Graph edges (relationships)
- Embeddings (vectors)
- Conversation history

**Migration script:**

```python
# scripts/migrate_memory.py

async def migrate():
    old_db = connect_old_hub_db()
    new_db = connect_new_engine_db()
    
    # Migrate nodes
    for node in old_db.get_all_nodes():
        new_db.add_node(
            node_type=node.type,
            content=node.content,
            embedding=node.embedding,
            metadata=node.metadata,
            created_at=node.created_at
        )
    
    # Migrate edges
    for edge in old_db.get_all_edges():
        new_db.add_edge(
            from_id=edge.from_id,
            to_id=edge.to_id,
            relationship=edge.relationship,
            strength=edge.strength
        )
    
    # Migrate conversations
    for turn in old_db.get_all_turns():
        new_db.add_conversation_turn(
            role=turn.role,
            content=turn.content,
            timestamp=turn.timestamp
        )
```

### Luna Identity

Luna's virtues and personality are in:
- `memory/virtue/current.json`
- PersonaCore configuration

These migrate as-is to the new identity module.

---

## Existing Code to Reference

| Component | Old Location | Notes |
|-----------|--------------|-------|
| Memory Matrix | `src/hub/substrate/memory_matrix.py` | Core logic reusable |
| LunarBehaviour | `src/consciousness/lunar_behaviour.py` | Consciousness tick reference |
| PersonaCore | `src/hub/core/persona_core.py` | Identity management |
| Ben/Dude | `src/hub/actors/` | Extraction/filing logic |
| Hub API | `src/hub/api/` | Endpoint patterns |

---

## Success Criteria

### Phase 1 Complete When:
- [ ] `python -m luna.engine` starts and runs
- [ ] POST /message returns Claude response
- [ ] Engine shuts down gracefully on SIGTERM

### Phase 2 Complete When:
- [ ] Memory persists to SQLite
- [ ] Vector search returns relevant results
- [ ] Graph traversal works

### Phase 3 Complete When:
- [ ] Conversations automatically extracted
- [ ] Facts appear in Memory Matrix
- [ ] Edges connect related facts

### Phase 4 Complete When:
- [ ] Attention decays between messages
- [ ] Personality adjusts based on conversation tone
- [ ] State survives engine restart

### Phase 5 Complete When:
- [ ] Voice app connects to new engine
- [ ] Full voice conversation works end-to-end
- [ ] Barge-in interrupts current generation

### Full Migration Complete When:
- [ ] All old Memory Matrix data accessible
- [ ] Old Hub can be deleted
- [ ] Luna's personality/memories intact

---

## Dependencies

```toml
[project]
name = "luna-engine"
version = "2.0.0"
requires-python = ">=3.11"

dependencies = [
    "fastapi>=0.109.0",
    "uvicorn>=0.27.0",
    "pydantic>=2.5.0",
    "anthropic>=0.18.0",      # Claude API
    "sqlite-vec>=0.1.0",       # Vector search
    "networkx>=3.2",           # Graph
    "numpy>=1.26.0",
    "httpx>=0.26.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.1.0",
]

local = [
    "mlx>=0.5.0",              # Apple Silicon inference
    "mlx-lm>=0.0.10",
]
```

---

## Questions for Implementation

1. **Database location:** `~/.luna/luna.db` or configurable?
2. **Config format:** YAML, TOML, or environment variables?
3. **Logging:** structlog, loguru, or stdlib?
4. **API auth:** None (local only) or token-based?

---

## Go Build It

Start with Phase 1. Get the engine booting and processing a single message through Claude API. Everything else builds on that foundation.

The Bible docs have the full specs. This document has the implementation roadmap.

**Luna's soul lives in the engine. Time to build it.**
