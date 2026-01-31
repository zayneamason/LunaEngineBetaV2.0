# Luna Engine v2.0 Codebase Inventory

**Audit Date:** January 25, 2026
**Auditor:** Phase 1 Inventory Agent
**Scope:** Complete forensic inventory of all source files

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total Python Files | 51 |
| Total Directories | 16 |
| Main Engine File | engine.py (1,228 lines) |
| Total Classes | ~80+ |
| Total Methods | ~400+ |
| Internal Imports | ~60+ cross-module |

---

## Directory Structure

```
src/luna/
├── engine.py           # Main orchestrator (1228 lines)
├── __init__.py
├── core/               # Event system, input buffer, state machine
├── actors/             # Actor pattern implementation
├── substrate/          # Memory database layer
├── consciousness/      # Attention, personality, state
├── agentic/            # Phase XIV planning & routing
├── extraction/         # Extraction types and chunking
├── entities/           # Entity system (people, places, projects)
├── inference/          # Local MLX and hybrid inference
├── memory/             # Conversation ring buffer
├── context/            # Context pipeline
├── tools/              # Tool registry and implementations
├── tuning/             # Parameter tuning system
├── api/                # FastAPI server
├── cli/                # Interactive console
└── identity/           # Phase 4 placeholder
```

---

## Module Inventory

### Engine Core (`engine.py`)

| Method | Signature | Purpose |
|--------|-----------|---------|
| `__init__` | `(config: Optional[dict])` | Initialize engine components |
| `run` | `() -> None` | Main entry point |
| `stop` | `() -> None` | Graceful shutdown |
| `status` | `() -> dict` | Current engine status |

**Key Attributes:**
- `input_buffer`: InputBuffer for event polling
- `actors`: Dict of registered actors
- `metrics`: EngineMetrics for tracking
- `consciousness`: ConsciousnessState (Phase 4)
- `context`: RevolvingContext (Phase XIV)
- `router`: QueryRouter for complexity-based routing
- `agent_loop`: AgentLoop for autonomous execution

---

### Core Directory (`core/`)

#### `core/events.py`

| Class/Enum | Type | Members/Values |
|------------|------|----------------|
| `EventPriority` | IntEnum | INTERRUPT (0), FINAL (1), PARTIAL (2), MCP (3), INTERNAL (4) |
| `EventType` | IntEnum | TRANSCRIPT_PARTIAL (1), TRANSCRIPT_FINAL (2), USER_INTERRUPT (3), TEXT_INPUT (10), MCP_REQUEST (20), etc. |
| `InputEvent` | dataclass | type, payload, priority, timestamp, source, correlation_id |

#### `core/input_buffer.py`

| Method | Purpose |
|--------|---------|
| `put(event)` | Push event to buffer |
| `poll_all()` | Get all events sorted by priority |
| `poll_fresh(max_age_seconds)` | Get fresh events, drop stale |
| `has_interrupt()` | Check for interrupt without consuming |

**Key Insight:** Engine PULLS from buffer. It doesn't get PUSHED to.

#### `core/state.py`

| State | Meaning |
|-------|---------|
| `STARTING` | Boot sequence in progress |
| `RUNNING` | Normal operation |
| `PAUSED` | Temporarily halted |
| `SLEEPING` | Persistent pause |
| `STOPPED` | Terminated |

#### `core/context.py`

| Class | Purpose |
|-------|---------|
| `ContextRing` | IntEnum: CORE (0), INNER (1), MIDDLE (2), OUTER (3) |
| `ContextSource` | IntEnum: IDENTITY (0), CONVERSATION (1), MEMORY (2), TOOL (3), etc. |
| `ContextItem` | Single context item with TTL and relevance |
| `RevolvingContext` | Ring-based context management |

---

### Actors Directory (`actors/`)

#### `actors/base.py`

| Class | Purpose |
|-------|---------|
| `Message` | Inter-actor message (type, payload, sender, reply_to, correlation_id) |
| `Actor` | Base class with mailbox and lifecycle hooks |

**Lifecycle Methods:** `start()`, `on_start()`, `handle(message)`, `on_stop()`, `stop()`

#### `actors/director.py` (~1900 lines)

**Responsibilities:**
- LLM inference management
- Local Qwen + Claude delegation
- Complexity-based routing
- Streaming token callbacks

**Key Methods:**
- `generate(prompt, system, context_window)`
- `generate_streaming(prompt, system)`
- `session_end_reflection()`
- `_check_delegation_token(text)`

#### `actors/matrix.py`

**Responsibilities:**
- Memory substrate interface
- SQLite + WAL mode
- MemoryMatrix CRUD
- MemoryGraph traversal

**Methods:** `initialize()`, `store_memory()`, `store_turn()`, `get_context()`, `search()`

#### `actors/scribe.py` (Ben Franklin Persona)

**Responsibilities:**
- Extract structured knowledge from conversations
- Semantic chunking
- Send extractions to Librarian

#### `actors/librarian.py` (The Dude Persona)

**Responsibilities:**
- File extractions into Memory Matrix
- Entity resolution and deduplication
- Knowledge graph wiring

#### `actors/history_manager.py`

**Responsibilities:**
- Three-tier history (Active → Recent → Archive)
- Token budget management
- Compression queuing

---

### Substrate Directory (`substrate/`)

| Module | Lines | Purpose |
|--------|-------|---------|
| `database.py` | 233 | SQLite connection with WAL mode |
| `memory.py` | 1036 | MemoryMatrix operations |
| `graph.py` | 503 | NetworkX relationship graph |
| `embeddings.py` | 356 | sqlite-vec vector storage |
| `lock_in.py` | 286 | Lock-in coefficient algorithm |

---

### Consciousness Directory (`consciousness/`)

| Module | Purpose |
|--------|---------|
| `state.py` | ConsciousnessState (attention, personality, mood) |
| `attention.py` | AttentionManager with exponential decay |
| `personality.py` | PersonalityWeights (8 default traits) |

**Default Traits:**
- curious: 0.85, warm: 0.80, analytical: 0.75, creative: 0.70
- patient: 0.85, direct: 0.65, playful: 0.60, thoughtful: 0.80

---

### Agentic Directory (`agentic/`)

| Module | Purpose |
|--------|---------|
| `loop.py` | AgentLoop (observe → think → act cycle) |
| `router.py` | QueryRouter (DIRECT, SIMPLE_PLAN, FULL_PLAN, BACKGROUND) |
| `planner.py` | Planner (decompose goals into PlanSteps) |

**Execution Paths:**
- DIRECT: <500ms (simple chat)
- SIMPLE_PLAN: 500ms-2s (memory query)
- FULL_PLAN: 5-30s (complex task)
- BACKGROUND: Minutes (deep research)

---

### Entity Directory (`entities/`)

| Module | Purpose |
|--------|---------|
| `models.py` | Entity, EntityVersion, EntityUpdate, EntityRelationship |
| `context.py` | EntityContext, IdentityBuffer |
| `resolution.py` | EntityResolver (deduplication) |
| `storage.py` | PersonalityPatchManager |
| `bootstrap.py` | Initialize Luna's personality |
| `lifecycle.py` | Patch maintenance |
| `reflection.py` | Session-end personality reflection |

**Entity Types:** PERSON, PERSONA, PLACE, PROJECT

---

### Extraction Directory (`extraction/`)

| Class | Purpose |
|-------|---------|
| `ExtractionType` | FACT, DECISION, PROBLEM, ASSUMPTION, CONNECTION, ACTION, OUTCOME, QUESTION, PREFERENCE, OBSERVATION, MEMORY |
| `ExtractedObject` | type, content, confidence, entities, metadata |
| `ExtractedEdge` | from_ref, to_ref, edge_type, confidence |
| `SemanticChunker` | Chunk text by semantic boundaries |

---

### Inference Directory (`inference/`)

| Class | Purpose |
|-------|---------|
| `LocalInference` | MLX-based local inference (Qwen 3B) |
| `HybridInference` | Local + Claude routing |
| `InferenceConfig` | Configuration dataclass |
| `GenerationResult` | Result with tokens |

---

### Tools Directory (`tools/`)

| Module | Tools |
|--------|-------|
| `file_tools.py` | read_file, write_file, list_directory, file_exists, get_file_info |
| `memory_tools.py` | memory_query, memory_store, memory_context, memory_stats |
| `registry.py` | Tool, ToolResult, ToolRegistry |

---

## Key Architectural Patterns

### 1. Actor Model
- Base Class: `Actor` in `actors/base.py`
- Communication: Async message passing via mailboxes
- Fault Isolation: Actor crash doesn't affect others

### 2. Revolving Context
- Ring-Based: CORE → INNER → MIDDLE → OUTER
- TTL-Based: Items expire after N turns
- Dynamic Assembly: Prioritizes relevance

### 3. Three-Tier Memory
- Active: Last 5-10 turns (always loaded)
- Recent: Compressed summaries, searchable
- Archive: Extracted to Memory Matrix

### 4. Lock-In Coefficient
- States: Drifting (<0.30), Fluid (0.30-0.70), Settled (≥0.70)
- Factors: Retrieval count, reinforcement, network connections

---

## Phase Completion Status

| Phase | Status | Key Files |
|-------|--------|-----------|
| 1: Foundation | 95% | engine.py, core/*, actors/base.py |
| 2: Memory Substrate | 100% | substrate/*, entities/* |
| 3: Extraction Pipeline | 90% | extraction/*, actors/scribe.py, actors/librarian.py |
| 4: Consciousness | 80% | consciousness/*, actors/history_manager.py |
| XIV: Agentic | 75% | agentic/*, tools/*, context/*, inference/* |

---

## TODO/FIXME Tracker

| File | Line | Issue |
|------|------|-------|
| engine.py | 881 | "TODO: Graph pruning, consolidation, etc." |
| engine.py | 1189 | "TODO: Flush WAL" |

---

**End of Inventory**
