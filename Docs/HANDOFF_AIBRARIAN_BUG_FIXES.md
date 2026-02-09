# HANDOFF: AI-BRARIAN Bug Fixes & QA Hardening

**Date:** 2026-02-08
**Author:** Architect (The Dude)
**For:** Claude Code execution agents
**Scope:** Fix 6 bugs, add integration tests, extend QA module
**Mode:** SURGICAL — fix only what's specified, touch nothing else

---

## ROOT CAUSE ANALYSIS

All bugs share a common origin: **interface contracts designed but never enforced at integration boundaries.**

- Commit `838c713` (Jan 19): 67 files / 19,183 lines — introduced Librarian, Graph, Scribe in one shot
- Commit `8427ec1`: 202 files / 60,263 lines — added entity system, MCP layer
- Both were multi-agent generated single commits with no integration testing
- Each subsystem works in isolation; bugs live in the seams between them
- Tests mock at every boundary, so the mocked interfaces diverge from real implementations
- Swallowed exceptions (`except Exception as e: logger.warning(...)`) mask all failures in production

---

## PROJECT ROOT

```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/
```

All paths below are relative to this root unless noted.

---
## BUG #1: Graph Edge Creation — CRITICAL

### Problem
`_create_edge()` in `src/luna/actors/librarian.py` (line 772) has 3 compounding bugs. The knowledge graph has ZERO edges across 22,516 nodes. Every edge creation has silently failed since the first commit.

### Root Cause
Librarian was written against a different mental model of the `MemoryGraph` API than what `graph.py` actually implements.

### Location
`src/luna/actors/librarian.py` — method `_create_edge()` (line 772)

### Current (broken):
```python
async def _create_edge(
    self,
    from_id: str,
    to_id: str,
    edge_type: str,
    confidence: float = 1.0,
) -> bool:
    # ...
    if hasattr(matrix_actor, "_graph") and matrix_actor._graph:
        graph = matrix_actor._graph

        # BUG 1: 3 args — MemoryGraph.has_edge() takes 2
        if graph.has_edge(from_id, to_id, edge_type):
            return False

        # BUG 2: missing await — add_edge is async
        # BUG 3: wrong kwargs — edge_type/weight vs relationship/strength
        graph.add_edge(
            from_id=from_id,
            to_id=to_id,
            edge_type=edge_type,
            weight=confidence,
        )
        return True

    return False
```

### Fix:
```python
async def _create_edge(
    self,
    from_id: str,
    to_id: str,
    edge_type: str,
    confidence: float = 1.0,
) -> bool:
    """
    Create edge between nodes.

    Returns True if created, False if duplicate.
    """
    if not self.engine:
        return False

    matrix_actor = self.engine.get_actor("matrix")
    if not matrix_actor:
        return False

    matrix = self._get_matrix()
    if not matrix:
        return False

    graph = matrix.graph
    if not graph:
        return False

    # FIX 1: has_edge takes exactly 2 args (from_id, to_id)
    if graph.has_edge(from_id, to_id):
        return False

    # FIX 2: await the async method
    # FIX 3: correct kwarg names (relationship, strength)
    await graph.add_edge(
        from_id=from_id,
        to_id=to_id,
        relationship=edge_type,
        strength=confidence,
    )
    return True
```

### Also fix: `_prune_edges()` (line 843)

Current calls `graph.get_all_edges()` which doesn't exist on `MemoryGraph`.

Replace with:
```python
async def _prune_edges(
    self,
    confidence_threshold: float = 0.3,
    age_days: int = 30,
) -> dict:
    """Prune low-confidence and old edges."""
    matrix = self._get_matrix()
    if not matrix or not matrix.graph:
        return {"pruned": 0, "remaining": 0}

    graph = matrix.graph
    stats = await graph.get_stats()
    pruned = 0

    # Iterate edges via NetworkX directly
    edges_to_remove = []
    for from_id, to_id, data in graph.graph.edges(data=True):
        strength = data.get("strength", 1.0)
        if strength < confidence_threshold:
            edges_to_remove.append((from_id, to_id))

    for from_id, to_id in edges_to_remove:
        await graph.remove_edge(from_id, to_id)
        pruned += 1

    return {
        "pruned": pruned,
        "remaining": stats["edge_count"] - pruned,
    }
```

### Verification
After fix, run:
```python
# In Python REPL with engine running
matrix = engine.get_actor("matrix")._matrix
stats = await matrix.graph.get_stats()
print(f"Edges: {stats['edge_count']}")  # Should be > 0 after extraction
```

---

## BUG #2: Auto-Session Extraction Bypasses Assistant Filter — CRITICAL

### Problem
`_end_auto_session()` in `src/luna_mcp/tools/memory.py` (line 197) mixes user + assistant turns into a single content blob, sends via `extract_text` (which has NO role filter), bypassing the Scribe's assistant-turn filter that only exists in `extract_turn`.

### Impact
Luna's own LLM-generated responses are being extracted as facts and stored in the Memory Matrix. This pollutes memory with generated content.

### Location
`src/luna_mcp/tools/memory.py` — function `_end_auto_session()` (line 197)

### Current (broken):
```python
async def _end_auto_session():
    # ...
    # Gets ALL turns (user + assistant)
    turns = window_response.get("turns", [])

    # Concatenates them all
    conversation_parts = []
    for turn in turns:
        role = turn.get("role", "unknown")
        content = turn.get("content", "")
        conversation_parts.append(f"{role}: {content}")
    conversation_content = "\n\n".join(conversation_parts)

    # Sends as extract_text — NO role filter
    await _call_api(
        "POST",
        "/extraction/trigger",
        json={
            "content": conversation_content,
            "role": "conversation",
            "session_id": session_id,
            "immediate": True
        }
    )
```

### Fix:
Filter to user turns only, send each individually:
```python
async def _end_auto_session():
    global _auto_session_active, _auto_session_id, _turn_buffer

    if not _auto_session_id:
        return

    session_id = _auto_session_id
    logger.info(f"[AUTO-SESSION] Ending session: {session_id}")

    try:
        # Flush any remaining buffered turns
        await _flush_turn_buffer()

        # Get turns from session
        window_response = await _call_api(
            "GET",
            f"/hub/active_window?session_id={session_id}&limit=100"
        )
        turns = window_response.get("turns", [])

        # End session
        await _call_api(
            "POST",
            f"/hub/session/end?session_id={session_id}"
        )

        # Filter to user turns ONLY — assistant turns are not facts
        user_turns = [t for t in turns if t.get("role") == "user"]

        if user_turns:
            logger.info(f"[AUTO-SESSION] Triggering extraction for {len(user_turns)} user turns (skipped {len(turns) - len(user_turns)} assistant turns)")

            # Send each user turn individually
            for turn in user_turns:
                await _call_api(
                    "POST",
                    "/extraction/trigger",
                    json={
                        "content": turn.get("content", ""),
                        "role": "user",
                        "session_id": session_id,
                        "immediate": True,
                    }
                )

        logger.info(f"[AUTO-SESSION] Session ended successfully: {session_id}")

    except Exception as e:
        logger.error(f"[AUTO-SESSION] Error ending session: {e}")
    finally:
        _auto_session_active = False
        _auto_session_id = None
        _turn_buffer = []
```

**NOTE:** The `/extraction/trigger` endpoint uses `extract_text` when `immediate=True`. But since we're now only sending user content, the role filter isn't needed — we've already filtered upstream. `role` is set to `"user"` for safety.

---

## BUG #3: Entity Resolution Noise — HIGH

### Problem
In `_wire_extraction()` (line 694), `obj.content` (full sentences like "Marzipan is an architect") is passed to `_resolve_entity()` as the entity name. This creates noisy nodes where fact sentences become entity identifiers.

### Location
`src/luna/actors/librarian.py` — method `_wire_extraction()` (line 694)

### Current (noisy):
```python
for obj in extraction.objects:
    node_id = await self._resolve_entity(
        name=obj.content,  # <-- Full sentence passed as entity name!
        entity_type=obj.type.value if hasattr(obj.type, 'value') else str(obj.type),
        source_id=extraction.source_id,
    )
```

### Fix:
Store extracted objects as memory nodes directly. Only resolve items from `obj.entities` as entities:
```python
for obj in extraction.objects:
    # Store the extraction as a memory node (NOT an entity)
    matrix = self._get_matrix()
    if matrix:
        node_id = await matrix.add_node(
            content=obj.content,
            node_type=obj.type.value if hasattr(obj.type, 'value') else str(obj.type),
            source=extraction.source_id,
            confidence=obj.confidence,
            tags=obj.tags if hasattr(obj, 'tags') else [],
        )

        if node_id:
            result.nodes_created.append(node_id)

        # Resolve ONLY named entities from the entities list
        for entity_name in obj.entities:
            entity_node_id = await self._resolve_entity(
                name=entity_name,
                entity_type="ENTITY",
                source_id=extraction.source_id,
            )
            # Create edge from fact node to entity node
            if node_id and entity_node_id:
                await self._create_edge(
                    from_id=node_id,
                    to_id=entity_node_id,
                    edge_type="MENTIONS",
                    confidence=obj.confidence,
                )
```

**IMPORTANT:** Check `MemoryMatrix.add_node()` method signature before implementing. Verify and adjust parameter names to match the actual API.

---

## BUG #4: Memory Consolidation Never Runs — HIGH

### Problem
`update_all_clusters()` exists in `LockInCalculator` but is never called. The reflective tick has a TODO at line 1011:
```python
# TODO: Graph pruning, consolidation, etc.
```
100% of clusters are "drifting". 95.6% of nodes have lock-in < 0.2.

### Location
`src/luna/engine.py` — method `_reflective_tick()` (around line 984)

### Fix:
Wire consolidation into the reflective tick:
```python
async def _reflective_tick(self):
    """Reflective tick — periodic maintenance. Runs every ~60 seconds."""
    # ... existing reflective work ...

    # Memory consolidation
    matrix_actor = self.get_actor("matrix")
    if matrix_actor and hasattr(matrix_actor, '_matrix') and matrix_actor._matrix:
        matrix = matrix_actor._matrix
        if hasattr(matrix, 'lock_in') and matrix.lock_in:
            try:
                result = matrix.lock_in.update_all_clusters()
                if result.get("clusters_updated", 0) > 0:
                    logger.info(
                        f"Memory consolidation: {result['clusters_updated']} clusters updated, "
                        f"{result.get('nodes_promoted', 0)} nodes promoted"
                    )
            except Exception as e:
                logger.warning(f"Memory consolidation failed: {e}")
```

**IMPORTANT:** Verify the exact attribute path to `lock_in` on the matrix. Adjust as needed.

---
## BUG #5: Orphan Database Files — MEDIUM

### Problem
5 empty/unused database files exist alongside the real one. Migration scripts default to wrong paths.

### Fix:
```bash
# Delete orphan files
rm luna_memory.db memory.db data/luna.db data/memory.db scripts/data/luna_engine.db

# Fix migration scripts to use correct path
# In scripts/populate_fts5.py — change default db_path to "data/luna_engine.db"
# In scripts/backfill_embeddings.py — change default db_path to "data/luna_engine.db"
```

Find all scripts referencing wrong DB paths:
```bash
grep -rn "luna_memory.db\|data/memory.db\|data/luna.db" scripts/ src/ --include="*.py"
```
Fix each one to point at `data/luna_engine.db`.

---

## BUG #6: Alias Cache Not Persisted — MEDIUM

### Problem
Both `LibrarianActor.alias_cache` and `EntityResolver._cache` are in-memory dicts. Lost on restart.

### Location
`src/luna/actors/librarian.py` — `__init__` (line 77)

### Fix:
Add cache persistence to Librarian startup/shutdown:
```python
import json
from pathlib import Path

ALIAS_CACHE_PATH = Path("data/alias_cache.json")

class LibrarianActor(Actor):
    def __init__(self, ...):
        # ... existing init ...
        self.alias_cache: dict[str, str] = self._load_alias_cache()

    def _load_alias_cache(self) -> dict[str, str]:
        """Load alias cache from disk if available."""
        if ALIAS_CACHE_PATH.exists():
            try:
                with open(ALIAS_CACHE_PATH, "r") as f:
                    cache = json.load(f)
                logger.info(f"Loaded alias cache: {len(cache)} entries")
                return cache
            except Exception as e:
                logger.warning(f"Failed to load alias cache: {e}")
        return {}

    def _save_alias_cache(self):
        """Persist alias cache to disk."""
        try:
            ALIAS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(ALIAS_CACHE_PATH, "w") as f:
                json.dump(self.alias_cache, f)
            logger.debug(f"Saved alias cache: {len(self.alias_cache)} entries")
        except Exception as e:
            logger.warning(f"Failed to save alias cache: {e}")
```

Call `_save_alias_cache()` after every new alias is added and in the engine shutdown sequence. Use `LUNA_BASE_PATH` env var if set.

---

## PHASE 2: INTEGRATION TESTS

Create: `tests/integration/test_seam_validation.py`

These tests validate the seams between subsystems using REAL objects (not mocks).

```python
"""
Integration tests for subsystem seams.

Rule: If module A calls module B, there must be at least one
test that uses real A and real B together.
"""

import pytest
import asyncio
import tempfile
import os
from pathlib import Path


# SEAM 1: Librarian → Graph (Bug #1)

@pytest.mark.asyncio
async def test_librarian_create_edge_uses_correct_graph_api():
    """Validates _create_edge() calls MemoryGraph with correct args."""
    from luna.substrate.graph import MemoryGraph
    from luna.substrate.database import MemoryDatabase

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = MemoryDatabase(db_path)
        await db.initialize()
        graph = MemoryGraph(db)
        await graph.load_from_db()

        # These calls must not raise
        assert graph.has_edge("node_a", "node_b") == False  # 2 args only

        edge = await graph.add_edge(       # must be awaited
            from_id="node_a",
            to_id="node_b",
            relationship="RELATES_TO",     # not edge_type
            strength=0.8,                  # not weight
        )

        assert edge is not None
        assert graph.has_edge("node_a", "node_b") == True

        edges = await graph.get_edges("node_a")
        assert len(edges) == 1
        assert edges[0].relationship == "RELATES_TO"
        assert edges[0].strength == 0.8

        await db.close()


@pytest.mark.asyncio
async def test_librarian_create_edge_roundtrip():
    """Full roundtrip: LibrarianActor._create_edge() → MemoryGraph → verify."""
    from luna.actors.librarian import LibrarianActor
    from luna.actors.matrix import MatrixActor
    from unittest.mock import MagicMock

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")

        # Create real matrix actor - adjust init based on actual constructor
        matrix_actor = MatrixActor()
        await matrix_actor.initialize(db_path=db_path)

        # Librarian with mocked engine returning real matrix
        librarian = LibrarianActor()
        mock_engine = MagicMock()
        mock_engine.get_actor = MagicMock(return_value=matrix_actor)
        librarian.engine = mock_engine

        result = await librarian._create_edge(
            from_id="test_node_1",
            to_id="test_node_2",
            edge_type="DEPENDS_ON",
            confidence=0.9,
        )

        assert result == True

        # Verify edge in graph
        graph = matrix_actor._matrix.graph if hasattr(matrix_actor, '_matrix') else matrix_actor._graph
        assert graph.has_edge("test_node_1", "test_node_2")


# CONTRACT TESTS: Verify API signatures match usage

def test_graph_has_edge_signature():
    """MemoryGraph.has_edge accepts exactly 2 positional args."""
    import inspect
    from luna.substrate.graph import MemoryGraph
    sig = inspect.signature(MemoryGraph.has_edge)
    params = list(sig.parameters.keys())
    assert params == ["self", "from_id", "to_id"], \
        f"has_edge signature changed! Expected [self, from_id, to_id], got {params}"


def test_graph_add_edge_signature():
    """MemoryGraph.add_edge uses 'relationship' and 'strength' kwargs."""
    import inspect
    from luna.substrate.graph import MemoryGraph
    sig = inspect.signature(MemoryGraph.add_edge)
    params = list(sig.parameters.keys())
    assert "relationship" in params, "add_edge missing 'relationship' param"
    assert "strength" in params, "add_edge missing 'strength' param"
    assert "edge_type" not in params, "add_edge still has old 'edge_type' param"
    assert "weight" not in params, "add_edge still has old 'weight' param"


def test_graph_add_edge_is_async():
    """MemoryGraph.add_edge must be async (requires await)."""
    import asyncio
    from luna.substrate.graph import MemoryGraph
    assert asyncio.iscoroutinefunction(MemoryGraph.add_edge), \
        "add_edge is not async — callers must await it"
```

---
## PHASE 3: QA MODULE EXTENSIONS

### 3A: New Assertion Category — "integration"

Add integration health assertions that run against Memory Matrix state.

### Location
`src/luna/qa/assertions.py` — add new builtin functions + assertions

### New Assertions:

```python
# INTEGRATION ASSERTIONS

def check_graph_has_edges(ctx: InferenceContext, a: Assertion) -> AssertionResult:
    """Check that the memory graph has edges. Zero = relational layer dead."""
    edge_count = 0
    if hasattr(ctx, 'memory_stats') and ctx.memory_stats:
        edge_count = ctx.memory_stats.get("graph_edges", 0)
    passed = edge_count > 0
    return AssertionResult(
        id=a.id, name=a.name, passed=passed, severity=a.severity,
        expected="Graph edges > 0",
        actual=f"{edge_count} edges",
        details="Knowledge graph has zero edges — relational layer is dead" if not passed else None,
    )


def check_cluster_health(ctx: InferenceContext, a: Assertion) -> AssertionResult:
    """Check that not ALL clusters are drifting."""
    drifting_pct = 100.0
    if hasattr(ctx, 'memory_stats') and ctx.memory_stats:
        total = ctx.memory_stats.get("total_clusters", 0)
        drifting = ctx.memory_stats.get("drifting_clusters", 0)
        if total > 0:
            drifting_pct = (drifting / total) * 100
    passed = drifting_pct < 100.0
    return AssertionResult(
        id=a.id, name=a.name, passed=passed, severity=a.severity,
        expected="< 100% clusters drifting",
        actual=f"{drifting_pct:.1f}% drifting",
        details="Memory consolidation has never run" if not passed else None,
    )


def check_node_type_diversity(ctx: InferenceContext, a: Assertion) -> AssertionResult:
    """Check that node types aren't >95% FACT."""
    fact_pct = 100.0
    if hasattr(ctx, 'memory_stats') and ctx.memory_stats:
        total = ctx.memory_stats.get("total_nodes", 0)
        facts = ctx.memory_stats.get("fact_nodes", 0)
        if total > 0:
            fact_pct = (facts / total) * 100
    passed = fact_pct < 95.0
    return AssertionResult(
        id=a.id, name=a.name, passed=passed, severity=a.severity,
        expected="< 95% FACT nodes",
        actual=f"{fact_pct:.1f}% FACT",
        details="Entity resolution noise — FACTs treated as entities" if not passed else None,
    )


def check_extraction_no_assistant_content(ctx: InferenceContext, a: Assertion) -> AssertionResult:
    """Check that extraction didn't process assistant-generated content."""
    has_leak = False
    if hasattr(ctx, 'extraction_stats') and ctx.extraction_stats:
        has_leak = ctx.extraction_stats.get("assistant_turns_extracted", 0) > 0
    return AssertionResult(
        id=a.id, name=a.name, passed=not has_leak, severity=a.severity,
        expected="0 assistant turns extracted",
        actual="Assistant content extracted!" if has_leak else "Clean",
        details="Auto-session is leaking LLM output into memory" if has_leak else None,
    )
```

### Add to `get_default_assertions()`:
```python
# Integration
Assertion(
    id="I1", name="Graph has edges",
    description="Memory graph should have relationship edges between nodes",
    category="integration", severity="critical",
    check_type="builtin", builtin_fn=check_graph_has_edges,
),
Assertion(
    id="I2", name="Cluster consolidation active",
    description="Not all clusters should be drifting — consolidation should run",
    category="integration", severity="high",
    check_type="builtin", builtin_fn=check_cluster_health,
),
Assertion(
    id="I3", name="Node type diversity",
    description="Node types shouldn't be >95% FACT (entity resolution noise)",
    category="integration", severity="high",
    check_type="builtin", builtin_fn=check_node_type_diversity,
),
Assertion(
    id="I4", name="No assistant content extraction",
    description="Only user content should be extracted into memory",
    category="integration", severity="critical",
    check_type="builtin", builtin_fn=check_extraction_no_assistant_content,
),
```

### 3B: Extend InferenceContext

Add to `src/luna/qa/context.py` — InferenceContext dataclass:

```python
# Memory health (populated by engine before QA validation)
memory_stats: dict = field(default_factory=dict)
extraction_stats: dict = field(default_factory=dict)
```

Update `to_dict()` and `from_dict()` to include these fields.

### 3C: Populate Memory Stats

Wherever `InferenceContext` is created (Director or engine inference path), populate:

```python
ctx.memory_stats = {
    "graph_edges": graph_stats.get("edge_count", 0),
    "total_nodes": ...,
    "fact_nodes": ...,
    "total_clusters": ...,
    "drifting_clusters": ...,
}
```

Check existing stats endpoints in `server.py` for patterns.

### 3D: Add Integration Diagnosis

In `QAValidator._generate_diagnosis()`:

```python
graph_dead = any(r.id == "I1" and not r.passed for r in results)
if graph_dead:
    diagnoses.append(
        "CRITICAL: Memory graph has zero edges. Check _create_edge() "
        "in LibrarianActor — likely API mismatch with MemoryGraph."
    )

consolidation_dead = any(r.id == "I2" and not r.passed for r in results)
if consolidation_dead:
    diagnoses.append(
        "Memory consolidation has never run. All clusters drifting. "
        "Check update_all_clusters() is wired to reflective tick."
    )

entity_noise = any(r.id == "I3" and not r.passed for r in results)
if entity_noise:
    diagnoses.append(
        "Node type distribution >95% FACT. Entity resolution likely "
        "treating fact content as entity names. Check _wire_extraction()."
    )

assistant_leak = any(r.id == "I4" and not r.passed for r in results)
if assistant_leak:
    diagnoses.append(
        "Assistant content being extracted into memory. "
        "Check auto-session extraction — should only extract user turns."
    )
```

---

## PHASE 4: REGRESSION BUGS

Register in QA system:

```python
qa_add_bug(
    name="BUG-GRAPH-001: Zero graph edges",
    query="(system health check)",
    expected_behavior="Graph edge_count > 0 after extraction runs",
    actual_behavior="edge_count = 0, _create_edge has 3 API mismatches",
    severity="critical",
)

qa_add_bug(
    name="BUG-EXTRACT-001: Assistant content in memory",
    query="(auto-session extraction)",
    expected_behavior="Only user turns extracted into memory",
    actual_behavior="Mixed user+assistant sent via extract_text (no role filter)",
    severity="critical",
)

qa_add_bug(
    name="BUG-ENTITY-001: FACT content as entity names",
    query="(entity resolution)",
    expected_behavior="FACTs stored as memory nodes, entities from obj.entities",
    actual_behavior="obj.content used as entity name, 91.6% FACT skew",
    severity="high",
)

qa_add_bug(
    name="BUG-LOCKIN-001: Consolidation never runs",
    query="(memory consolidation)",
    expected_behavior="Clusters promoted from drifting over time",
    actual_behavior="100% clusters drifting, update_all_clusters never called",
    severity="high",
)
```

---

## EXECUTION ORDER

```
Phase 1: Bug Fixes (do in order — #1 unblocks #3)
  1.1  Fix _create_edge()           [librarian.py]
  1.2  Fix _prune_edges()           [librarian.py]
  1.3  Fix _end_auto_session()      [memory.py]
  1.4  Fix _wire_extraction()       [librarian.py]
  1.5  Wire consolidation           [engine.py]
  1.6  Delete orphan DBs            [project root + data/]
  1.7  Fix migration script paths   [scripts/]
  1.8  Add alias cache persistence  [librarian.py]

Phase 2: Integration Tests
  2.1  Create test_seam_validation.py
  2.2  Run all tests, confirm 0 failures

Phase 3: QA Extensions
  3.1  Add integration assertions   [assertions.py]
  3.2  Extend InferenceContext       [context.py]
  3.3  Wire memory stats population  [engine or director]
  3.4  Add integration diagnosis     [validator.py]
  3.5  Register regression bugs      [qa database]

Phase 4: Validation
  4.1  Run full test suite
  4.2  Start engine, trigger extraction on test content
  4.3  Verify graph edges exist
  4.4  Verify QA assertions I1-I4 pass
  4.5  Run QA health check
```

---

## VERIFICATION CHECKLIST

After all fixes:

- [ ] `graph.has_edge()` called with exactly 2 args everywhere
- [ ] `graph.add_edge()` always awaited, uses `relationship=` and `strength=`
- [ ] `_prune_edges()` uses actual MemoryGraph API methods
- [ ] Auto-session extracts user turns only
- [ ] FACT content stored as memory nodes, not entity names
- [ ] `obj.entities` items resolved as entities
- [ ] `update_all_clusters()` runs in reflective tick
- [ ] No orphan `.db` files at project root
- [ ] Migration scripts point to `data/luna_engine.db`
- [ ] Alias cache persists to disk
- [ ] Integration tests pass (test_seam_validation.py)
- [ ] QA assertions I1-I4 exist and have correct logic
- [ ] All 116+ tests still pass
- [ ] New tests pass

---

## FILES MODIFIED

| File | Changes |
|------|---------|
| `src/luna/actors/librarian.py` | Fix `_create_edge()`, `_prune_edges()`, `_wire_extraction()`, add alias cache persistence |
| `src/luna_mcp/tools/memory.py` | Fix `_end_auto_session()` to filter user turns only |
| `src/luna/engine.py` | Wire `update_all_clusters()` into `_reflective_tick()` |
| `src/luna/qa/assertions.py` | Add I1-I4 integration assertions + builtin functions |
| `src/luna/qa/context.py` | Add `memory_stats`, `extraction_stats` fields |
| `src/luna/qa/validator.py` | Add integration diagnosis logic |
| `tests/integration/test_seam_validation.py` | NEW — integration seam tests |
| Various migration scripts | Fix default DB paths |
| Orphan `.db` files | DELETE |

---

## ANTI-PATTERNS TO AVOID

1. **Don't mock the boundary you're testing.** If testing Librarian → Graph, use a REAL Graph.
2. **Don't swallow exceptions silently.** If `_create_edge` fails, log at ERROR, not WARNING.
3. **Don't send mixed-role content through unfiltered paths.** Always filter upstream.
4. **Don't use full sentences as entity names.** Entities are proper nouns, not fact content.
5. **Don't leave TODO comments for critical wiring.** If consolidation needs to run, wire it.

---

**End of handoff.**