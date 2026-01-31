# Claude Code Handoff: Test Fixes

**Date:** 2026-01-13  
**Author:** Architecture Session (Dude mode)  
**Priority:** HIGH — 8 failing tests blocking development

---

## Executive Summary

Luna Engine v2.0 has **88 tests**, of which **80 pass** and **8 fail**. The substrate layer (Memory Matrix, embeddings, graph, input buffer) is rock solid. The failures are concentrated in two areas:

1. **Engine lifecycle tests (5 failures)** — Boot sequence timing/blocking issue
2. **Naming mismatch (3 failures)** — `cloud_generations` → `delegated_generations` rename not reflected in tests

**Estimated fix time:** 30-60 minutes

---

## Test Results Summary

```
88 tests total: 80 passed, 8 failed

✅ SOLID (100% passing):
- test_actors.py        — 10/10
- test_api.py           — 9/9  
- test_embeddings.py    — 9/9
- test_input_buffer.py  — 14/14
- test_memory.py        — 12/12

❌ BROKEN:
- test_engine.py        — 5 failures
- test_local_inference.py — 3 failures
```

---

## Issue #1: Engine Lifecycle Tests (5 failures)

### Failing Tests

| Test | Expected | Actual |
|------|----------|--------|
| `test_engine_starts_and_stops` | `state == RUNNING` | `state == STARTING` |
| `test_engine_initializes_actors` | `"director" in actors` | Only `"matrix"` present |
| `test_cognitive_ticks_increment` | `cognitive_ticks > 0` | `cognitive_ticks == 0` |
| `test_events_processed_count` | `events_processed >= 2` | `events_processed == 0` |
| `test_get_actor` | `director is not None` | `director is None` |

### Root Cause Analysis

The tests wait 0.3 seconds (`await asyncio.sleep(0.3)`) then expect the engine to be in `RUNNING` state with both actors registered. But:

1. **`engine.py` line 117-129** shows the boot sequence:
```python
async def _boot(self) -> None:
    if "matrix" not in self.actors:
        matrix = MatrixActor()
        self.register_actor(matrix)
        await matrix.initialize()  # ← BLOCKING CALL
    
    if "director" not in self.actors:
        self.register_actor(DirectorActor())  # ← Never reached if above blocks
```

2. **`MatrixActor.initialize()`** (actors/matrix.py line 78-95):
   - Tries to import from Eclissi via `sys.path.insert(0, '/Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/src')`
   - Runs `EclissiMemoryMatrix()` in executor
   - If Eclissi DB doesn't exist (test uses temp dir), falls back to basic substrate
   - The fallback path opens SQLite, loads schema, loads graph from DB

3. **The timing issue:** 0.3 seconds isn't enough for:
   - SQLite connection + schema load
   - NetworkX graph load
   - Two actors to register
   - State transition to RUNNING

### Fix Strategy

**Option A: Increase test timeout (quick fix)**
```python
# tests/test_engine.py
await asyncio.sleep(1.0)  # Instead of 0.3
```

**Option B: Add explicit ready signal (proper fix)**
```python
# engine.py
self._ready_event = asyncio.Event()

async def run(self) -> None:
    await self._boot()
    self.state = EngineState.RUNNING
    self._running = True
    self._ready_event.set()  # Signal ready
    ...

async def wait_ready(self, timeout: float = 5.0) -> bool:
    """Wait for engine to be ready."""
    try:
        await asyncio.wait_for(self._ready_event.wait(), timeout)
        return True
    except asyncio.TimeoutError:
        return False
```

```python
# tests/test_engine.py
task = asyncio.create_task(engine.run())
assert await engine.wait_ready(timeout=5.0)
assert engine.state == EngineState.RUNNING
```

**Option C: Mock MatrixActor in tests (isolation fix)**
```python
# tests/conftest.py
@pytest.fixture
def engine_config(temp_data_dir, monkeypatch):
    # Patch MatrixActor to skip Eclissi import
    monkeypatch.setattr("luna.actors.matrix.ECLISSI_AVAILABLE", False)
    monkeypatch.setattr("luna.actors.matrix.ECLISSI_DB_PATH", temp_data_dir / "nonexistent.db")
    return EngineConfig(...)
```

### Recommended Fix

**Do Option B (ready signal) + Option C (mock in tests)**

The ready signal is good architecture — callers shouldn't guess timing. The mock ensures tests are isolated from filesystem state.

---

## Issue #2: Naming Mismatch (3 failures)

### Failing Tests

| Test | Expected Key | Actual Key |
|------|--------------|------------|
| `test_director_routing_stats` | `cloud_generations` | `delegated_generations` |
| `test_director_snapshot` | `cloud_generations` | `delegated_generations` |
| `test_should_use_local_simple` | `result is False` | `result is True` |

### Root Cause

**DirectorActor** (actors/director.py) was refactored to use "delegated" terminology (Claude is a delegate, not a cloud service):

```python
# OLD (what tests expect)
self._cloud_generations = 0

# NEW (what code has)  
self._delegated_generations = 0
```

The `get_routing_stats()` and `snapshot()` methods return `delegated_generations`, but tests assert `cloud_generations`.

### Fix (Simple)

Update tests to use new naming:

```python
# tests/test_local_inference.py

# Line 244 - test_director_routing_stats
def test_director_routing_stats(self, director):
    stats = director.get_routing_stats()
    assert "local_generations" in stats
    assert "delegated_generations" in stats  # Was: cloud_generations
    assert "local_available" in stats

# Line 254 - test_director_snapshot  
async def test_director_snapshot(self, director):
    snapshot = await director.snapshot()
    assert "local_available" in snapshot
    assert "local_generations" in snapshot
    assert "delegated_generations" in snapshot  # Was: cloud_generations
```

### Third Failure: `test_should_use_local_simple`

```python
def test_should_use_local_simple(self):
    local = LocalInference()
    hybrid = HybridInference(local)
    result = hybrid.should_use_local("Hello!")
    assert result is False  # Expected False because MLX not available
```

**Issue:** The test comment says "MLX not available in test environment" but `should_use_local()` returns `True`. 

Check `HybridInference.should_use_local()` logic — it may be checking `self._local.is_loaded` incorrectly or the complexity estimation is returning "simple" which routes to local regardless of availability.

**Fix:** Either:
1. Fix the `should_use_local()` method to check `_local.is_loaded` first
2. Or update the test expectation with correct comment

---

## File Changes Required

### 1. `src/luna/engine.py`

Add ready signal:

```python
def __init__(self, config: Optional[EngineConfig] = None):
    ...
    self._ready_event = asyncio.Event()

async def run(self) -> None:
    try:
        await self._boot()
        self.state = EngineState.RUNNING
        self._running = True
        self._ready_event.set()  # ADD THIS
        ...

async def wait_ready(self, timeout: float = 5.0) -> bool:
    """Wait for engine to be ready."""
    try:
        await asyncio.wait_for(self._ready_event.wait(), timeout)
        return True
    except asyncio.TimeoutError:
        return False
```

### 2. `tests/conftest.py`

Add Eclissi isolation:

```python
@pytest.fixture
def engine_config(temp_data_dir, monkeypatch):
    """Create test engine configuration with Eclissi mocked out."""
    # Ensure tests don't try to use Eclissi
    import luna.actors.matrix as matrix_module
    monkeypatch.setattr(matrix_module, "ECLISSI_AVAILABLE", False)
    
    return EngineConfig(
        cognitive_interval=0.1,
        reflective_interval=60,
        data_dir=temp_data_dir,
    )
```

### 3. `tests/test_engine.py`

Use ready signal:

```python
async def test_engine_starts_and_stops(self, engine_config):
    engine = LunaEngine(engine_config)
    task = asyncio.create_task(engine.run())
    
    # Wait for engine to be ready (not arbitrary sleep)
    assert await engine.wait_ready(timeout=5.0)
    assert engine.state == EngineState.RUNNING
    assert engine._running is True
    
    await engine.stop()
    await asyncio.wait_for(task, timeout=5.0)
    assert engine.state == EngineState.STOPPED
```

### 4. `tests/test_local_inference.py`

Fix naming:

```python
# Line 244
def test_director_routing_stats(self, director):
    stats = director.get_routing_stats()
    assert "local_generations" in stats
    assert "delegated_generations" in stats  # CHANGED
    assert "local_available" in stats

# Line 254
async def test_director_snapshot(self, director):
    snapshot = await director.snapshot()
    assert "local_available" in snapshot
    assert "local_generations" in snapshot
    assert "delegated_generations" in snapshot  # CHANGED
```

---

## Verification

After fixes, run:

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
source .venv/bin/activate
python -m pytest tests/ -v
```

Expected: **88 passed, 0 failed**

---

## Architecture Notes

The failures revealed something important: **MatrixActor has hardcoded paths to Eclissi**:

```python
# actors/matrix.py line 23
sys.path.insert(0, '/Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/src')

# Line 33
ECLISSI_DB_PATH = Path("/Users/zayneamason/_HeyLuna_BETA/_Eclessi_BetaProject_Root/data/memory/matrix/memory_matrix.db")
```

This is fine for development but needs attention for:
- CI/CD environments
- Other developer machines
- Production deployment

Consider making these configurable via environment variables or config.

---

## Summary Checklist

- [ ] Add `_ready_event` and `wait_ready()` to `engine.py`
- [ ] Mock Eclissi in `conftest.py`
- [ ] Update engine tests to use `wait_ready()`
- [ ] Rename `cloud_generations` → `delegated_generations` in tests
- [ ] Fix or update `test_should_use_local_simple` expectation
- [ ] Run full test suite
- [ ] Update CLAUDE.md phase checklist

---

**End of handoff. Good hunting.**
