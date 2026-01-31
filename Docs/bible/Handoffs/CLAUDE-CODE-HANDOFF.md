# Luna Engine v2.0 — Claude Code Handoff

**Date:** 2026-01-13  
**Status:** Phase 1 at 95%, Phase 2 COMPLETE, 8 tests need fixing  
**Priority:** Fix tests → resume development

---

## Quick Start

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
source .venv/bin/activate

# Run tests (currently 80/88 passing)
python -m pytest tests/ -v

# Run console
python scripts/run.py

# Run API server
python scripts/run.py --server --port 8000
```

---

## Current State

### What's Working (80 tests pass)

| Component | Status | Tests |
|-----------|--------|-------|
| Actors (base, mailbox, isolation) | ✅ Solid | 10/10 |
| API Server (FastAPI endpoints) | ✅ Solid | 9/9 |
| Embeddings (sqlite-vec) | ✅ Solid | 9/9 |
| Input Buffer (priority queue) | ✅ Solid | 14/14 |
| Memory Matrix (full ops layer) | ✅ Solid | 12/12 |
| Console UI (Rich terminal) | ✅ Done | — |
| Local Inference (MLX/Qwen) | ✅ Done | 9/12 |

### What's Broken (8 tests fail)

**5 Engine Lifecycle Tests:**
- `test_engine_starts_and_stops` — stuck at STARTING state
- `test_engine_initializes_actors` — director not registered
- `test_cognitive_ticks_increment` — ticks stay at 0
- `test_events_processed_count` — events not processed
- `test_get_actor` — director is None

**Root Cause:** Tests wait 0.3s but boot sequence blocks on MatrixActor.initialize() trying to load Eclissi DB.

**3 Naming Mismatch Tests:**
- `test_director_routing_stats` — expects `cloud_generations`
- `test_director_snapshot` — expects `cloud_generations`
- `test_should_use_local_simple` — logic issue

**Root Cause:** Code uses `delegated_generations`, tests expect `cloud_generations`.

---

## Fixes Required

### Fix 1: Add Ready Signal to Engine

**File:** `src/luna/engine.py`

```python
def __init__(self, config: Optional[EngineConfig] = None):
    # ... existing code ...
    self._ready_event = asyncio.Event()  # ADD THIS

async def run(self) -> None:
    try:
        await self._boot()
        self.state = EngineState.RUNNING
        self._running = True
        self._ready_event.set()  # ADD THIS
        # ... rest of method ...

# ADD THIS METHOD
async def wait_ready(self, timeout: float = 5.0) -> bool:
    """Wait for engine to be ready."""
    try:
        await asyncio.wait_for(self._ready_event.wait(), timeout)
        return True
    except asyncio.TimeoutError:
        return False
```

### Fix 2: Mock Eclissi in Tests

**File:** `tests/conftest.py`

```python
@pytest.fixture
def engine_config(temp_data_dir, monkeypatch):
    """Create test engine configuration with Eclissi mocked out."""
    import luna.actors.matrix as matrix_module
    monkeypatch.setattr(matrix_module, "ECLISSI_AVAILABLE", False)
    
    return EngineConfig(
        cognitive_interval=0.1,
        reflective_interval=60,
        data_dir=temp_data_dir,
    )
```

### Fix 3: Update Engine Tests to Use Ready Signal

**File:** `tests/test_engine.py`

Replace all instances of:
```python
await asyncio.sleep(0.3)
assert engine.state == EngineState.RUNNING
```

With:
```python
assert await engine.wait_ready(timeout=5.0)
assert engine.state == EngineState.RUNNING
```

### Fix 4: Update Naming in Tests

**File:** `tests/test_local_inference.py`

Line 244:
```python
assert "delegated_generations" in stats  # Was: cloud_generations
```

Line 254:
```python
assert "delegated_generations" in snapshot  # Was: cloud_generations
```

---

## Architecture Overview

```
LunaEngine (tick-based runtime)
├── InputBuffer (priority queue, engine PULLS)
├── Actors
│   ├── DirectorActor (local Qwen 3B + Claude delegation)
│   └── MatrixActor (Memory Matrix interface)
├── Substrate
│   ├── MemoryDatabase (SQLite + WAL)
│   ├── MemoryMatrix (CRUD, search, context)
│   ├── EmbeddingStore (sqlite-vec)
│   └── MemoryGraph (NetworkX)
└── API
    ├── FastAPI Server (/message, /stream, /status, /health, /abort)
    └── Rich Console UI (streaming chat)
```

**Core Insight:** Engine PULLS from buffer. It doesn't get PUSHED to.

---

## Key Files

| File | Purpose |
|------|---------|
| `engine.py` | Main tick loops, lifecycle |
| `actors/director.py` | Qwen 3B + Claude delegation |
| `actors/matrix.py` | Memory substrate interface |
| `substrate/memory.py` | MemoryMatrix operations |
| `substrate/embeddings.py` | sqlite-vec vectors |
| `substrate/graph.py` | NetworkX relationships |
| `api/server.py` | FastAPI endpoints |
| `cli/console.py` | Rich terminal UI |
| `inference/local.py` | MLX local inference |

---

## After Fixing Tests

Once all 88 tests pass, resume with:

### Phase 3: Extraction Pipeline
- [ ] Scribe actor (Ben Franklin) — extracts facts from conversations
- [ ] Librarian actor (The Dude) — files memories into graph

### Phase 4: Consciousness
- [ ] Attention decay
- [ ] Personality weights
- [ ] State persistence

---

## Reference Docs

- Full architecture: `Docs/LUNA ENGINE Bible/`
- Detailed test analysis: `Docs/LUNA ENGINE Bible/Handoffs/CLAUDE-CODE-HANDOFF-TEST-FIXES-2026-01-13.md`

---

## Verification

After applying fixes:

```bash
python -m pytest tests/ -v
# Expected: 88 passed, 0 failed
```

Then update this file's checklist and continue development.

---

**TL;DR: Fix 4 things, run tests, resume Phase 3.**
