# AI-BRARIAN & Memory Matrix Audit Results

**Date:** 2026-02-08
**Auditor:** Claude Code (5 parallel agents)
**Scope:** Scribe (Ben), Librarian (The Dude), Memory Matrix, Entity System, MCP layer
**Mode:** Read-only — no files modified

---

## 1. Import & Dependency Health

| Module | Status |
|--------|--------|
| `luna.actors.scribe.ScribeActor` | PASS |
| `luna.actors.librarian.LibrarianActor` | PASS |
| `luna.actors.matrix.MatrixActor` | PASS |
| `luna.extraction.types.ExtractionType` | PASS |
| `luna.extraction.chunker.SemanticChunker` | PASS |
| `luna.memory.lock_in.LockInCalculator` | PASS |
| `luna.memory.constellation.ConstellationAssembler` | PASS |
| `luna.librarian.cluster_retrieval.ClusterRetrieval` | PASS |
| `luna.entities.resolution.EntityResolver` | PASS |

**All 9 imports pass.** One soft warning: `tiktoken` is not installed — SemanticChunker falls back to `len/4` token counting.

---

## 2. Database State

### Active Database

The **one true database** is `data/luna_engine.db` (124 MB). Both `engine.py` and `matrix.py` resolve to `data/luna_engine.db`.

| Metric | Value |
|--------|-------|
| Total memory nodes | 22,516 |
| Node type breakdown | FACT: 20,633 (91.6%), ENTITY: 529, OBSERVATION: 386, QUESTION: 364, + 11 others |
| Low lock-in nodes (< 0.2) | 21,523 (95.6%) |
| Total clusters | 195 |
| Cluster states | ALL 195 = "drifting" (100%) |
| Cluster members | 4,316 |
| Entities | 101 |
| Entity versions | 212 |
| Conversation turns | 865 (519 assistant, 346 user) |
| FTS5 index rows | 22,516 (matches memory_nodes — healthy) |
| Most recent activity | 2026-02-08 21:31:04 |

### Orphan Database Files

| File | Size | Tables | Data |
|------|------|--------|------|
| `luna_memory.db` (root) | 0 bytes | none | empty |
| `memory.db` (root) | 86 KB | 4 entity tables | 0 rows |
| `data/luna.db` | 204 KB | 12 tables (full schema) | 0 rows |
| `data/memory.db` | 0 bytes | none | empty |
| `scripts/data/luna_engine.db` | 278 KB | full schema + FTS + embeddings | 0 rows |

**Note:** `memory.db` has `entity_mentions` with a foreign key to `memory_nodes`, but `memory_nodes` doesn't exist in that DB — broken referential integrity.

### Key Database Observations

- **95.6% of nodes are drifting** — memory consolidation has never successfully elevated any node.
- **100% of clusters are drifting** — the lock-in/consolidation pipeline appears to have never run successfully.
- **91.6% of nodes are FACTs** — the extraction pipeline is over-classifying as FACT. The knowledge graph is extremely flat.
- **Turn ratio is 1.5:1 assistant:user** — memory query/response pairs are being logged as separate turns, inflating the count.

---

## 3. Wiring Verification

| Connection Point | Status | Notes |
|-----------------|--------|-------|
| Engine → Scribe (internal) | **WIRED** | `record_conversation_turn()` → `_trigger_extraction()` → `scribe.mailbox.put()` on every user message |
| Engine registers Scribe + Librarian | **WIRED** | Both registered in `_boot()` |
| API `/extraction/trigger` → Scribe | **PARTIAL** | Works but bypasses mailbox (direct `handle()` call), uses `extract_text` vs internal `extract_turn`, manually drains Librarian mailbox |
| Scribe → Librarian `"file"` message | **WIRED** | `_send_to_librarian()` → Librarian `handle()` routes to `_wire_extraction()` |
| Scribe → Librarian `"entity_update"` | **WIRED** | `_send_entity_update_to_librarian()` → Librarian routes to `_file_entity_update()` |
| Librarian → Matrix via `_get_matrix()` | **WIRED** | Primary path `matrix_actor._matrix` works. `_memory` fallback is dead code but harmless. |
| Entity Resolution (extraction wiring) | **WIRED** | `_resolve_entity()` uses alias cache + `MemoryMatrix.search_nodes()` on `memory_nodes` table |
| Entity Resolution (entity updates) | **WIRED** | Uses `EntityResolver` which queries `entities` table by id/name/alias |
| Alias cache persistence | **BROKEN** | Both `LibrarianActor.alias_cache` and `EntityResolver._cache` are in-memory only — lost on restart |
| Graph edge creation | **BROKEN** | **3 compounding bugs** (see Issue #1 below) |
| Graph edge persistence (underlying) | **WIRED** | `MemoryGraph.add_edge()` correctly persists to both NetworkX + SQLite — but the Librarian never successfully calls it |
| Edge pruning | **BROKEN** | Calls `graph.get_all_edges()` which does not exist on `MemoryGraph` |

---

## 4. Test Results

| Test File | Passed | Failed | Time |
|-----------|--------|--------|------|
| `tests/test_scribe.py` | 23 | 0 | 0.04s |
| `tests/test_librarian.py` | 16 | 0 | 0.03s |
| `tests/test_extraction_pipeline.py` | 13 | 0 | ~23s |
| `tests/test_memory.py` | 12 | 0 | 11.40s |
| `tests/test_lock_in.py` | 13 | 0 | 0.02s |
| `tests/test_mcp_memory_tools.py` | 9 | 0 | 3.65s |
| `tests/test_entity_system.py` | 27 | 0 | 0.44s |
| `tests/test_memory_retrieval_e2e.py` | 3 | 0 | 0.02s |
| **TOTAL** | **116** | **0** | **~39s** |

**116/116 tests pass.** 4 non-actionable Swig deprecation warnings from sqlite-vec.

**Coverage gaps** (not tested):
- Scribe → Librarian → Matrix end-to-end with real graph edges
- Graph edge creation/persistence roundtrip (currently broken — tests mock around it)
- Auto-session → extraction trigger flow
- ConstellationAssembler token budgeting under real load
- ClusterRetrieval integration with actual LibrarianActor
- Lock-in consolidation pipeline (cluster promotion from drifting)
- Multi-day offline → lock-in decay behavior

**50 test files exist total** — 42 were not part of this audit run.

---

## 5. Known Issues Found

### CRITICAL

**Issue #1: Graph edge creation is completely non-functional**
- **Location:** `src/luna/actors/librarian.py` — `_create_edge()` (line 772)
- **Three compounding bugs:**
  1. `graph.has_edge(from_id, to_id, edge_type)` called with **3 args** — `MemoryGraph.has_edge()` only accepts **2 args** → `TypeError`
  2. `graph.add_edge(...)` called **without `await`** — it's an `async def` method → returns unawaited coroutine
  3. Wrong keyword arguments: passes `edge_type=` and `weight=` — method expects `relationship=` and `strength=` → `TypeError`
- **Impact:** The knowledge graph has ZERO edges. All 22,516 memory nodes are isolated. No relationships exist between entities, facts, or observations. The entire relational layer of Luna's memory is dead.
- **Edge pruning is also broken:** `_prune_edges()` calls `graph.get_all_edges()` which doesn't exist → `AttributeError`

**Issue #2: Auto-session extraction bypasses assistant-turn filter**
- **Location:** `src/luna_mcp/tools/memory.py` — `_end_auto_session()` (line 197)
- **What happens:** Mixes user + assistant turns into single content blob, sends as `extract_text` with `role="conversation"`, which bypasses the Scribe's `extract_turn` assistant filter
- **Impact:** LLM-generated text is being extracted as if it were user-provided knowledge, polluting the memory matrix with Luna's own outputs

### HIGH

**Issue #3: Entity resolution noise — FACTs treated as entity names**
- **Location:** `src/luna/actors/librarian.py` — `_wire_extraction()` (line 694)
- `obj.content` (full sentences like "Marzipan is an architect") is passed to `_resolve_entity()` as the entity name
- Creates noisy nodes where fact sentences become entity identifiers
- Pollutes alias cache with sentence strings
- Likely contributing to the 91.6% FACT skew in node types

**Issue #4: Memory consolidation has never run**
- **Evidence:** 100% of clusters are "drifting", 95.6% of nodes have lock-in < 0.2
- Either the consolidation pipeline has never been triggered, or it crashes silently
- The lock-in system's infrastructure is sound but appears to never execute in practice

**Issue #5: 5 orphan database files**
- `luna_memory.db`, `memory.db`, `data/luna.db`, `data/memory.db`, `scripts/data/luna_engine.db`
- All empty or unpopulated. Two migration scripts (`populate_fts5.py`, `backfill_embeddings.py`) default to `data/luna_memory.db` (wrong path)
- Risk of confusion when running migration scripts

**Issue #6: Alias cache not persisted**
- Both `LibrarianActor.alias_cache` and `EntityResolver._cache` are in-memory dicts
- Lost on every engine restart → cold-start entity resolution has no cache → slower resolution + possible duplicate creation

### MEDIUM

**Issue #7: `_extract_local()` docstring lies about Claude fallback**
- **Location:** `src/luna/actors/scribe.py` (line 501)
- Docstring says "Falls back to Claude if local not available"
- Actual code returns `(ExtractionOutput(), [])` — empty result, DEBUG log only
- When `backend="local"` and local model is unavailable, all extraction is silently dropped

**Issue #8: Stale model IDs in EXTRACTION_BACKENDS**
- `claude-3-haiku-20240307` — old Haiku (superseded by 3.5 Haiku)
- `claude-3-5-sonnet-20241022` — valid but outdated
- Also hardcoded in `compress_turn()` at scribe.py:776
- These still work but may not offer best price/performance

**Issue #9: Cluster lock-in has no floor above 0.0**
- Cluster-level lock-in uses exponential decay with time
- "Fluid" clusters (half-life 2.8h) effectively destroyed after 3 days offline
- "Settled" clusters destroyed after ~7 days
- Even "crystallized" clusters destroyed after ~30 days
- No minimum floor — can decay to 0.0
- Node-level lock-in is safe (no temporal decay, floor at 0.15)

### LOW

**Issue #10: tiktoken not installed**
- SemanticChunker falls back to `len/4` token counting
- May produce inaccurate chunk sizing

**Issue #11: engine.py:394 references `matrix._memory` (doesn't exist)**
- MatrixActor has `_matrix` not `_memory`
- Would crash in `_ensure_entity_seeds_loaded()` if that code path executes

---

## 6. Dead Code Identified

| Code | Location | Evidence |
|------|----------|----------|
| `integrate_with_librarian()` | `src/luna/librarian/cluster_retrieval.py:268` | Defined, exported in `__init__.py`, but never called by any module |
| `_memory` fallback in `_get_matrix()` | `src/luna/actors/librarian.py:982` | MatrixActor has no `_memory` attribute — fallback always returns None |
| `_prune_edges()` | `src/luna/actors/librarian.py:843` | Calls non-existent `graph.get_all_edges()` — crashes on first call |

---

## 7. Recommendations

### Priority 1: Fix Graph Edge Creation (CRITICAL)

Fix `_create_edge()` in `librarian.py`:
```python
# FIX 1: has_edge takes 2 args, not 3
if graph.has_edge(from_id, to_id):
    return False

# FIX 2: await the async method + correct kwarg names
await graph.add_edge(
    from_id=from_id,
    to_id=to_id,
    relationship=edge_type,    # was: edge_type=edge_type
    strength=confidence,        # was: weight=confidence
)
```

Also fix `_prune_edges()` to use actual MemoryGraph API methods.

### Priority 2: Fix Auto-Session Extraction Content Mixing

In `_end_auto_session()`, either:
- Filter to only user turns before sending to extraction
- Or send individual turns via `extract_turn` (which has the assistant filter) instead of `extract_text`

### Priority 3: Fix Entity Resolution Noise

In `_wire_extraction()`, change `_resolve_entity(name=obj.content, ...)` to store `obj.content` as a memory node WITHOUT resolving it as an entity name. Only resolve items from `obj.entities` as entities. FACTs should be memory nodes, not entity identifiers.

### Priority 4: Investigate Memory Consolidation

The lock-in/clustering pipeline has never elevated any cluster from "drifting". Determine:
- Is `update_all_clusters()` ever called?
- Is there a background service that triggers consolidation?
- If not, wire it to the engine tick loop or a periodic timer.

### Priority 5: Clean Up Orphan Databases

Delete: `luna_memory.db`, `memory.db`, `data/luna.db`, `data/memory.db`, `scripts/data/luna_engine.db`
Fix migration script defaults to `data/luna_engine.db`.

### Priority 6: Persist Alias Cache

Write `alias_cache` to a JSON file or SQLite table on shutdown, reload on startup.

### Priority 7: Update Model IDs

Update `EXTRACTION_BACKENDS` and hardcoded model strings to current Anthropic model IDs.

---

## Appendix: Database File Map

```
data/luna_engine.db  (124 MB)  ← THE ONE TRUE DATABASE
luna_memory.db       (0 bytes) ← orphan
memory.db            (86 KB)   ← orphan (entity schema only, 0 rows)
data/luna.db         (204 KB)  ← orphan (full schema, 0 rows)
data/memory.db       (0 bytes) ← orphan
scripts/data/luna_engine.db (278 KB) ← orphan (full schema, 0 rows)
```
