# HANDOFF: Guardian Memory Bridge — Fix Sync + Clear

**Status: COMPLETE (2026-03-05)**
Loads 200+ Kinoni knowledge nodes into Luna's Memory Matrix for native retrieval.

---

## 1. The Problem (Resolved)

The Guardian Memory Bridge (`src/luna/services/guardian/memory_bridge.py`) had three issues preventing a clean full sync of Kinoni knowledge into Luna's Memory Matrix.

### Issue A: Early exit false positive — FIXED

`sync_all()` searched for "Kinoni" in the guardian-kinoni scope. It found 5 Scribe-created nodes (no scope tag) via content search and incorrectly assumed the bridge had already run, skipping the full 200+ node sync.

**Fix:** Early exit block was already commented out. Replaced with a proper scope-based idempotency guard using `_count_scoped_nodes()` which counts `WHERE scope = 'project:guardian-kinoni'` instead of content-searching. Threshold set to >100 nodes.

### Issue B: `clear()` scope mismatch — FIXED

`clear()` deleted by `WHERE scope = 'project:guardian-kinoni'` but only targeted `memory_nodes`. It did not delete scoped edges from `graph_edges`, and did not reload the in-memory NetworkX graph after deletion.

**Root cause:** The scope column exists and works correctly. The original report of `removed: 0` was from before any successful sync had run (the early exit in Issue A was preventing sync). Once the early exit was removed, syncs ran but `clear()` was never called — resulting in 744 duplicate nodes (4 unguarded re-syncs).

**Fix:**
- `clear()` now deletes `graph_edges WHERE scope = ?` before deleting nodes (FK-safe order)
- Reloads the in-memory graph via `matrix._graph.load()` after deletion
- Confirmed `cursor.rowcount` works correctly with `aiosqlite`

### Issue C: Edge creation scope — FIXED

`_sync_relationships()` called `matrix._graph.add_edge()` without passing `scope`, so all Guardian edges defaulted to `scope = 'global'`. This meant `clear()` could never find them, and they were invisible to scope-filtered queries.

**Fix:** Both `add_edge` call sites now pass `scope=GUARDIAN_SCOPE`. The `key=relationship` parameter for MultiDiGraph was already handled correctly in `graph.py`.

---

## 2. Changes Made

**File:** `src/luna/services/guardian/memory_bridge.py`

| Line(s) | Change |
|----------|--------|
| 66-71 | Idempotency guard: skip sync if >100 scoped nodes exist |
| 252 | Entity edge creation: added `scope=GUARDIAN_SCOPE` |
| 279 | Knowledge edge creation: added `scope=GUARDIAN_SCOPE` |
| 287-297 | New `_count_scoped_nodes()` method — counts by SQL scope, not content search |
| 299-336 | Rewritten `clear()` — deletes edges first, then nodes, then reloads graph |

**Data cleanup:** 744 duplicate nodes deleted from `luna_engine.db` via `PRAGMA trusted_schema = ON; DELETE FROM memory_nodes WHERE scope = 'project:guardian-kinoni'`.

---

## 3. Verification Results

Sync triggered via `POST /guardian/api/sync`:

```json
{
    "status": "synced",
    "entities": 23,
    "knowledge": 163,
    "edges": 468,
    "skipped": 0
}
```

| Metric | Result | Target | Status |
|--------|--------|--------|--------|
| Entities | 23 | > 20 | PASS |
| Knowledge | 163 | > 150 | PASS |
| Edges | 468 | > 30 | PASS |

Idempotency verified — second sync returns:
```json
{
    "status": "synced",
    "already_synced": true,
    "existing_nodes": 186
}
```

---

## 4. What Was NOT Touched

- Aibrarian collection (`kinoni_knowledge`, 16 docs, 883 chunks) — separate store for Nexus search
- Scribe extraction pipeline — still creates its own unscoped nodes from conversation
- `_check_existing()` method — left in place but no longer called (dead code, safe to remove later)
- Guardian data fixtures in `data/guardian/`
- `server.py` Guardian route wiring
