# Luna Engine v2.0 — Claude Code Configuration

## Project Overview

This is the **Luna Engine** — a consciousness substrate that uses LLMs the way game engines use GPUs.

The LLM is stateless inference. The engine provides identity, memory, state, and orchestration.

**Core Insight:** Luna's soul lives in the engine, not the LLM.

## Project Structure

```
luna-engine/
├── src/luna/
│   ├── engine.py           # Main engine (tick loops, lifecycle)
│   ├── core/
│   │   ├── events.py       # Event types and priorities
│   │   ├── input_buffer.py # Thread-safe input queue
│   │   └── state.py        # Engine state machine
│   ├── actors/
│   │   ├── base.py         # Actor base class with mailbox
│   │   └── director.py     # LLM management (Claude API)
│   └── ...
├── scripts/
│   └── run.py              # Entry point
└── Docs/LUNA ENGINE Bible/ # Full specification
```

## Implementation Phases

### Phase 1: Foundation (95% Complete)
- [x] Engine lifecycle (start → running → stop)
- [x] Input buffer (thread-safe queue)
- [x] Basic tick loop (poll → dispatch)
- [x] Actor base class with mailbox
- [x] Director actor (local Qwen + Claude delegation)
- [x] Matrix actor (Eclissi integration)
- [x] FastAPI server with endpoints
- [ ] **FIX: 8 failing tests** (see Handoffs/CLAUDE-CODE-HANDOFF-TEST-FIXES-2026-01-13.md)

### Phase 2: Memory Substrate ✅ COMPLETE
- [x] SQLite database with schema (substrate/database.py)
- [x] sqlite-vec for embeddings (substrate/embeddings.py)
- [x] NetworkX graph for relationships (substrate/graph.py)
- [x] MemoryMatrix operations layer (substrate/memory.py)
- [x] Eclissi integration (53k+ nodes available)

### Phase 3: Extraction Pipeline
- [ ] Scribe actor (Ben)
- [ ] Librarian actor (Dude)

### Phase 4: Consciousness
- [ ] Attention decay
- [ ] Personality weights
- [ ] State persistence

### Current Blockers
**8 failing tests must be fixed before proceeding:**
- 5 engine lifecycle tests (timing/mock issue)
- 3 naming mismatch tests (`cloud_generations` → `delegated_generations`)

See: `Docs/LUNA ENGINE Bible/Handoffs/CLAUDE-CODE-HANDOFF-TEST-FIXES-2026-01-13.md`

## Running

```bash
# Interactive mode
python scripts/run.py

# Single message
python scripts/run.py -m "Hello Luna"

# Debug mode
python scripts/run.py --debug
```

## Key Files

| File | Purpose |
|------|---------|
| `engine.py` | Main engine with tick loops |
| `core/input_buffer.py` | Buffered polling (engine pulls, not pushed) |
| `core/events.py` | Event types and priorities |
| `core/state.py` | Engine state machine |
| `actors/base.py` | Actor pattern with mailbox isolation |
| `actors/director.py` | Local Qwen + Claude delegation |
| `actors/matrix.py` | Memory substrate interface (Eclissi) |
| `substrate/database.py` | SQLite connection manager |
| `substrate/memory.py` | MemoryMatrix operations |
| `substrate/embeddings.py` | sqlite-vec vector search |
| `substrate/graph.py` | NetworkX relationship graph |
| `inference/local.py` | MLX local inference (Qwen 3B) |
| `api/server.py` | FastAPI endpoints |

## Architecture Principle

```
Engine PULLS from buffer. It doesn't get PUSHED to.
```

This gives Luna:
- Situational awareness (see all pending input)
- Abort control (can cancel on interrupt)
- Priority ordering (urgent events first)

## Reference Docs

See `Docs/LUNA ENGINE Bible/` for full specification:
- `00-FOUNDATIONS.md` — Core insight (LLM as GPU)
- `07-RUNTIME-ENGINE.md` — Tick loop design
- `Handoffs/LUNA-ENGINE-V2-IMPLEMENTATION-SPEC.md` — This implementation
