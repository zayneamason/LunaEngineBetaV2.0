# BUG-REGISTRY.md

**Generated:** 2026-01-30
**Agent:** Bug Analysis
**Phase:** 3

## Summary

| Severity | Count |
|----------|-------|
| Critical | 7 |
| High | 9 |
| Medium | 11 |
| Low | 8 |
| **Total** | **35** |

---

## Critical Bugs

### BUG-001: API Keys Exposed in Repository

**Category:** Security Violation
**Severity:** Critical
**Component:** Configuration
**Status:** Open

#### Description
Real API keys (Anthropic, Groq, Google) are committed to the repository in `.env` file and partially exposed in diagnostic output files.

#### Root Cause
`.env` file was not added to `.gitignore` before committing. Diagnostic scripts print key prefixes/suffixes.

#### Evidence
- File: `/.env` contains `ANTHROPIC_API_KEY=sk-ant-api03-J30cClhH3zyG1tAe...`
- File: `Docs/Handoffs/DiagnosticResults/DIAGNOSTIC_OUTPUT.txt` contains truncated keys

#### Suggested Fix
1. Immediately rotate ALL three API keys
2. Add `.env` to `.gitignore`
3. Scrub git history using BFG Repo-Cleaner
4. Delete `DIAGNOSTIC_OUTPUT.txt`
5. Update diagnostic scripts to mask keys

#### Code Reference
[AUDIT-CONFIG.md](Docs/LUNA ENGINE Bible/Audit/AUDIT-CONFIG.md) - Security Check section

---

### BUG-002: Memory Database Path Conflict

**Category:** Reported (HANDOFF)
**Severity:** Critical
**Component:** substrate/database.py
**Status:** Open

#### Description
Two conflicting default database paths exist: `~/.luna/luna.db` (15 nodes) vs `data/luna_engine.db` (60k+ nodes). Runtime sometimes connects to wrong database, causing "memory wipe" symptoms.

#### Root Cause
`MemoryDatabase` defaults to `~/.luna/luna.db` while `MatrixActor` expects `data/luna_engine.db`. Fresh database created at wrong location.

#### Evidence
- HANDOFF-MEMORY-WIPE-EMERGENCY.md documents 59,939 nodes reduced to 15
- MemoryDatabase line 41-42: `DEFAULT_DB_DIR = Path.home() / ".luna"`

#### Suggested Fix
```python
# In src/luna/substrate/database.py
DEFAULT_DB_DIR = Path(__file__).parent.parent.parent.parent / "data"
DEFAULT_DB_NAME = "luna_engine.db"
```

#### Code Reference
[substrate/database.py:41-42](src/luna/substrate/database.py#L41)

---

### BUG-003: Conversation History Loss (60-Second Amnesia)

**Category:** Reported (HANDOFF)
**Severity:** Critical
**Component:** Context Pipeline / Director
**Status:** Open

#### Description
Luna forgets context from turns 60 seconds ago in the same session. Example: Luna says "Oh my GOD, Yulia!" in Turn 3, then claims no context about Yulia in Turn 4.

#### Root Cause
Conversation history not consistently passed to LLM. Multiple possible failure points: ConversationBuffer, PersonaAdapter, Director context building.

#### Evidence
- HANDOFF-CONVERSATION-HISTORY-NOT-WORKING-PROVE-ME-WRONG.md documents exact failure sequence
- Multiple emergency handoffs created for this issue

#### Suggested Fix
1. Add diagnostic logging at each handoff point
2. Verify conversation buffer is being populated
3. Ensure history makes it into LLM messages array
4. Check for session boundary issues clearing buffer

#### Code Reference
[actors/director.py](src/luna/actors/director.py), [context/pipeline.py](src/luna/context/pipeline.py)

---

### BUG-004: MLX Local Inference Silent Failure

**Category:** Reported (HANDOFF)
**Severity:** Critical
**Component:** inference/local.py
**Status:** Open

#### Description
Local inference fails silently when `mlx-lm` not importable. Luna confabulates wildly instead of using trained LoRA personality.

#### Root Cause
`try/except` swallows ImportError for MLX dependencies. Server starts "successfully" when critical systems are dead.

#### Evidence
```
[ERROR] luna.inference.local: MLX not available: No module named 'mlx_lm'
[WARNING] luna.actors.director: Failed to load local model, using Claude only
```
HANDOFF_CRITICAL_SYSTEMS_AUDIT_AND_SAFEGUARDS.md documents incident.

#### Suggested Fix
1. Implement CriticalSystemsCheck that blocks startup if MLX unavailable
2. Add startup health gate before FastAPI loads
3. Add runtime watchdog for system health

#### Code Reference
[inference/local.py](src/luna/inference/local.py)

---

### BUG-005: Memory Search API Returns Empty Results

**Category:** Reported (HANDOFF)
**Severity:** Critical
**Component:** api/server.py
**Status:** Open

#### Description
`/memory/search` endpoint returns empty results despite 60,730 nodes in database. Direct SQL queries work correctly.

#### Root Cause
Endpoint checks for non-existent methods `search()` and `hybrid_search()` instead of `search_nodes()`.

#### Evidence
```python
# Current (broken)
if hasattr(memory, "search"):  # False - method doesn't exist
    results = await memory.search(...)
```
HANDOFF_MEMORY_SEARCH_FIX.md documents issue.

#### Suggested Fix
```python
if hasattr(memory, "search_nodes"):
    nodes = await memory.search_nodes(query=request.query, limit=request.limit)
```

#### Code Reference
[api/server.py:~1361](src/luna/api/server.py#L1361)

---

### BUG-006: Entity Context Initialization Signature Mismatch

**Category:** Reported (HANDOFF)
**Severity:** Critical
**Component:** entities/context.py
**Status:** Open

#### Description
EntityContext fails to initialize with "takes 2 positional arguments but 3 were given" error.

#### Root Cause
Constructor signature changed but callers not updated.

#### Evidence
```
[WARNING] luna.context.pipeline: [PIPELINE] Entity system init failed:
EntityContext.__init__() takes 2 positional arguments but 3 were given
```

#### Suggested Fix
Audit all EntityContext instantiations and align with current signature.

#### Code Reference
[entities/context.py](src/luna/entities/context.py)

---

### BUG-007: Forge MCP reset_stats Method Missing

**Category:** Reported (HANDOFF)
**Severity:** Critical
**Component:** luna_mcp/tools/forge.py
**Status:** Open

#### Description
`forge_load` fails with `'Crucible' object has no attribute 'reset_stats'`.

#### Root Cause
forge.py calls `crucible.reset_stats()` but Crucible class only has `clear()` method.

#### Evidence
HANDOFF_FORGE_MCP_BUGFIX.md documents issue.

#### Suggested Fix
```python
# Line 83 in forge.py
crucible.clear()  # was reset_stats()
```

#### Code Reference
[luna_mcp/tools/forge.py:83](src/luna_mcp/tools/forge.py#L83)

---

## High Priority Bugs

### BUG-008: Lock-In Threshold Mismatch Between Node and Cluster

**Category:** Potential (Audit Finding)
**Severity:** High
**Component:** substrate/lock_in.py, memory/lock_in.py
**Status:** Open

#### Description
Two different threshold systems for lock-in states. Node-level uses 0.30/0.70, cluster-level uses 0.20/0.70/0.85.

#### Root Cause
Independent implementations without harmonization.

#### Evidence
- Node-level (substrate/lock_in.py): drifting < 0.30, settled >= 0.70
- Cluster-level (memory/lock_in.py): drifting < 0.20, crystallized >= 0.85

#### Suggested Fix
Harmonize thresholds to a single configuration source in `memory_economy_config.json`.

#### Code Reference
[substrate/lock_in.py](src/luna/substrate/lock_in.py), [memory/lock_in.py](src/luna/memory/lock_in.py)

---

### BUG-009: N+1 Query Pattern in Semantic Search

**Category:** Potential (Audit Finding)
**Severity:** High
**Component:** substrate/memory.py
**Status:** Open

#### Description
`semantic_search()` executes individual `get_node()` query per result instead of batch fetch.

#### Root Cause
Loop iterates over similarity results and queries each node individually.

#### Evidence
```python
# Lines 709-717 in memory.py
for node_id, similarity in similar:
    node = await self.get_node(node_id)  # Individual query per result
```

#### Suggested Fix
Batch-fetch nodes using `WHERE id IN (?, ?, ...)`.

#### Code Reference
[substrate/memory.py:709-717](src/luna/substrate/memory.py#L709)

---

### BUG-010: Centroid Calculation Looks in Wrong Table

**Category:** Potential (Audit Finding)
**Severity:** High
**Component:** memory/clustering_engine.py
**Status:** Open

#### Description
`ClusteringEngine._calculate_centroid()` looks for `embedding` column in `memory_nodes`, but embeddings are stored in `memory_embeddings_local` vec0 table.

#### Root Cause
Schema mismatch - embeddings stored in virtual table, not main table.

#### Evidence
AUDIT-MEMORY.md documents: "Looks for embedding column in memory_nodes, which doesn't exist in schema."

#### Suggested Fix
Query `memory_embeddings_local` table for embeddings instead of `memory_nodes`.

#### Code Reference
[memory/clustering_engine.py](src/luna/memory/clustering_engine.py)

---

### BUG-011: HistoryManager Actor Not Exported

**Category:** Potential (Audit Finding)
**Severity:** High
**Component:** actors/__init__.py
**Status:** Open

#### Description
`HistoryManagerActor` exists in `history_manager.py` but is NOT exported in `actors/__init__.py`.

#### Root Cause
Oversight when adding HistoryManager actor.

#### Evidence
AUDIT-ACTORS.md notes: "HistoryManagerActor is NOT exported in `__init__.py` but exists in `history_manager.py`."

#### Suggested Fix
```python
# In actors/__init__.py
from .history_manager import HistoryManagerActor
__all__.append("HistoryManagerActor")
```

#### Code Reference
[actors/__init__.py](src/luna/actors/__init__.py)

---

### BUG-012: Scribe Uses Synchronous Anthropic Client

**Category:** Potential (Audit Finding)
**Severity:** High
**Component:** actors/scribe.py
**Status:** Open

#### Description
Scribe actor uses synchronous `client.messages.create()` within async handler, blocking the actor's message loop.

#### Root Cause
Using sync Anthropic client instead of AsyncAnthropic.

#### Evidence
AUDIT-ACTORS.md notes: "Lines 480-491 in scribe.py: response = self.client.messages.create(...) # Sync Anthropic call"

#### Suggested Fix
Replace with `anthropic.AsyncAnthropic()` client.

#### Code Reference
[actors/scribe.py:480-491](src/luna/actors/scribe.py#L480)

---

### BUG-013: Memory Retrieval Empty for Known Entities

**Category:** Reported (HANDOFF)
**Severity:** High
**Component:** actors/director.py
**Status:** Open

#### Description
Luna says "I'm drawing a blank on Marzipan" despite Marzipan nodes existing in database with 60k+ nodes.

#### Root Cause
Memory context not being fetched or injected into Director's generation flow.

#### Evidence
HANDOFF_MEMORY_AND_INFERENCE_FIX.md documents: "Memory retrieval empty - 'I'm drawing a blank on Marzipan'"

#### Suggested Fix
Add `_fetch_memory_context()` method to Director and inject into delegation flow.

#### Code Reference
[actors/director.py](src/luna/actors/director.py)

---

### BUG-014: Identity Pollution (Confusing Users)

**Category:** Reported (HANDOFF)
**Severity:** High
**Component:** actors/director.py
**Status:** Open

#### Description
Luna confused Ahab with "Kamau" because a memory node mentioned "Kamau Zuberi Akabueze" and was retrieved as relevant.

#### Root Cause
No identity anchor in system prompt to distinguish current user from mentioned entities.

#### Evidence
HANDOFF_MEMORY_AND_INFERENCE_FIX.md documents identity pollution issue.

#### Suggested Fix
Add identity anchor to system prompt:
```
## Current Conversation
You are talking with Ahab (also known as Zayne). He is your creator.
Do not confuse him with other people mentioned in your memories.
```

#### Code Reference
[actors/director.py](src/luna/actors/director.py)

---

### BUG-015: 8 Failing Tests (Engine Lifecycle + Naming)

**Category:** Reported (CLAUDE.md)
**Severity:** High
**Component:** tests/
**Status:** Open

#### Description
8 tests failing: 5 engine lifecycle tests (timing/mock issue), 3 naming mismatch tests (`cloud_generations` vs `delegated_generations`).

#### Root Cause
1. Lifecycle tests have race conditions with asyncio timing
2. Field renamed from `cloud_generations` to `delegated_generations` without updating tests

#### Evidence
CLAUDE.md documents: "8 failing tests must be fixed before proceeding"

#### Suggested Fix
1. Increase timeouts or use event-based signaling for lifecycle tests
2. Rename field in tests from `cloud_generations` to `delegated_generations`

#### Code Reference
See: `Docs/LUNA ENGINE Bible/Handoffs/CLAUDE-CODE-HANDOFF-TEST-FIXES-2026-01-13.md`

---

### BUG-016: Local Inference Extremely Slow (2-3 tok/s)

**Category:** Reported (HANDOFF)
**Severity:** High
**Component:** inference/local.py
**Status:** Open

#### Description
Local inference runs at 2-3 tok/s instead of expected 50+ tok/s. 31-38 seconds for ~100 tokens.

#### Root Cause
Possible: Model not quantized, running on CPU instead of GPU, context window too large, model too large for memory.

#### Evidence
HANDOFF_MEMORY_AND_INFERENCE_FIX.md documents performance issue.

#### Suggested Fix
1. Verify model is 4-bit quantized
2. Check `mx.default_device()` is GPU
3. Reduce max context if needed
4. Consider smaller model (3B vs 7B)

#### Code Reference
[inference/local.py](src/luna/inference/local.py)

---

## Medium Priority Bugs

### BUG-017: Network Effects Not Implemented in Lock-In

**Category:** TODO Comment
**Severity:** Medium
**Component:** substrate/lock_in.py
**Status:** Open

#### Description
`locked_neighbor_count` always returns 0, missing 20% of lock-in coefficient weight.

#### Root Cause
Graph wiring incomplete - TODO comment in code.

#### Evidence
```python
# TODO: Add network effects (locked neighbors) when graph is wired
locked_neighbor_count = 0  # Always 0 currently
```

#### Suggested Fix
Implement graph neighbor query when graph is properly wired.

#### Code Reference
[substrate/memory.py:1194](src/luna/substrate/memory.py#L1194)

---

### BUG-018: Tag Siblings Not Implemented

**Category:** TODO Comment
**Severity:** Medium
**Component:** substrate/lock_in.py
**Status:** Open

#### Description
`locked_tag_sibling_count` always returns 0, missing 10% of lock-in coefficient weight.

#### Root Cause
Tag sibling counting not implemented.

#### Evidence
```python
# TODO: Implement tag sibling counting
locked_tag_sibling_count = 0  # Always 0
```

#### Suggested Fix
Implement tag-based sibling query when tag system is active.

#### Code Reference
[substrate/lock_in.py:273](src/luna/substrate/lock_in.py#L273)

---

### BUG-019: Unused Schema Tables

**Category:** Potential (Audit Finding)
**Severity:** Medium
**Component:** substrate/schema.sql
**Status:** Open

#### Description
Multiple tables defined in schema but never used in code.

#### Root Cause
Tables created for future features that were never implemented.

#### Evidence
| Table | Status |
|-------|--------|
| `consciousness_snapshots` | Defined, not used |
| `sessions` | Defined, not used |
| `compression_queue` | Defined, not implemented |
| `extraction_queue` | Defined, not implemented |
| `history_embeddings` | Defined, not implemented |
| `tuning_sessions` | Defined, not used |
| `tuning_iterations` | Defined, not used |

#### Suggested Fix
Either implement the features or remove unused tables from schema.

#### Code Reference
[substrate/schema.sql](src/luna/substrate/schema.sql)

---

### BUG-020: Memory Economy Tables Not in schema.sql

**Category:** Potential (Audit Finding)
**Severity:** Medium
**Component:** memory/cluster_manager.py
**Status:** Open

#### Description
ClusterManager creates tables dynamically (`clusters`, `cluster_members`, `cluster_edges`) instead of in schema.sql.

#### Root Cause
Schema fragmentation - auto-created tables separate from main schema.

#### Suggested Fix
Move Memory Economy table definitions to schema.sql for consistency.

#### Code Reference
[memory/cluster_manager.py](src/luna/memory/cluster_manager.py)

---

### BUG-021: EntityResolver Import Failure Silent

**Category:** Potential (Audit Finding)
**Severity:** Medium
**Component:** substrate/memory.py
**Status:** Open

#### Description
EntityResolver import fails silently, returning None without raising.

#### Root Cause
`try/except` swallows ImportError with only a warning log.

#### Evidence
```python
try:
    from ..entities.resolution import EntityResolver
except ImportError as e:
    logger.warning(f"Could not import EntityResolver: {e}")
    return None  # Silently fails
```

#### Suggested Fix
Either raise the exception or implement graceful feature degradation with user notification.

#### Code Reference
[substrate/memory.py](src/luna/substrate/memory.py)

---

### BUG-022: Scribe Extraction Not Implemented in Director

**Category:** TODO Comment
**Severity:** Medium
**Component:** actors/director.py
**Status:** Open

#### Description
TODO comment indicates Scribe extraction should happen but is not implemented.

#### Evidence
```python
# TODO: Implement Scribe extraction here
```

#### Suggested Fix
Wire Director to send extraction messages to Scribe actor after conversation turns.

#### Code Reference
[actors/director.py:734](src/luna/actors/director.py#L734)

---

### BUG-023: Compression/Extraction Queue Notifications Not Implemented

**Category:** TODO Comment
**Severity:** Medium
**Component:** actors/history_manager.py
**Status:** Open

#### Description
HistoryManager has TODOs to notify Scribe for compression/extraction but not implemented.

#### Evidence
```python
# TODO: Notify Scribe actor to process compression (line 616)
# TODO: Notify Scribe actor to process extraction (line 631)
```

#### Suggested Fix
Add message sending to Scribe actor when turns are queued for processing.

#### Code Reference
[actors/history_manager.py:616-631](src/luna/actors/history_manager.py#L616)

---

### BUG-024: Graph Pruning/Consolidation Not Implemented

**Category:** TODO Comment
**Severity:** Medium
**Component:** engine.py
**Status:** Open

#### Description
Graph maintenance operations mentioned in TODO but not implemented.

#### Evidence
```python
# TODO: Graph pruning, consolidation, etc. (line 935)
```

#### Code Reference
[engine.py:935](src/luna/engine.py#L935)

---

### BUG-025: WAL Flush Not Implemented

**Category:** TODO Comment
**Severity:** Medium
**Component:** engine.py
**Status:** Open

#### Description
WAL (Write-Ahead Log) flushing mentioned in TODO but not implemented.

#### Evidence
```python
# TODO: Flush WAL (line 1248)
```

#### Suggested Fix
Implement periodic WAL checkpoint for database integrity.

#### Code Reference
[engine.py:1248](src/luna/engine.py#L1248)

---

### BUG-026: Vector Search Integration Missing for Entities

**Category:** TODO Comment
**Severity:** Medium
**Component:** entities/storage.py
**Status:** Open

#### Description
Vector search integration for entities planned but not implemented.

#### Evidence
```python
# TODO: Integrate with vector search when embeddings are available (line 234)
```

#### Code Reference
[entities/storage.py:234](src/luna/entities/storage.py#L234)

---

### BUG-027: Evidence Nodes Not Linked in Reflection

**Category:** TODO Comment
**Severity:** Medium
**Component:** entities/reflection.py
**Status:** Open

#### Description
Reflection loop creates patches without linking to evidence nodes.

#### Evidence
```python
evidence_nodes=[],  # TODO: Link to actual memory nodes (line 408)
```

#### Code Reference
[entities/reflection.py:408](src/luna/entities/reflection.py#L408)

---

## Low Priority Bugs

### BUG-028: api/server.py Too Large (4,650 lines)

**Category:** Potential (Audit Finding)
**Severity:** Low
**Component:** api/server.py
**Status:** Open

#### Description
Single API file exceeds 500 line guideline by nearly 10x.

#### Suggested Fix
Split into modules: `api/routes/chat.py`, `api/routes/memory.py`, `api/routes/tuning.py`, etc.

#### Code Reference
[api/server.py](src/luna/api/server.py)

---

### BUG-029: Frontend Timeout Cleanup Missing

**Category:** Potential (Audit Finding)
**Severity:** Low
**Component:** frontend/TuningPanel, EngineStatus
**Status:** Open

#### Description
setTimeout in TuningPanel and EngineStatus not cleaned up on unmount.

#### Suggested Fix
Add clearTimeout in useEffect cleanup functions.

#### Code Reference
AUDIT-FRONTEND.md documents this in Subscription Cleanup Audit section.

---

### BUG-030: Undeclared Python Dependencies

**Category:** Potential (Audit Finding)
**Severity:** Low
**Component:** pyproject.toml
**Status:** Open

#### Description
Several packages used but not declared in pyproject.toml.

#### Evidence
| Package | Used In |
|---------|---------|
| `groq` | llm/providers/groq_provider.py |
| `google-generativeai` | llm/providers/gemini_provider.py |
| `openai` | substrate/embeddings.py |
| `sentence-transformers` | substrate/local_embeddings.py |
| `tiktoken` | core/context.py |

#### Suggested Fix
Add to optional dependency groups in pyproject.toml.

#### Code Reference
AUDIT-DEPENDENCIES.md documents undeclared dependencies.

---

### BUG-031: Lock-In Batch Query Not Optimized

**Category:** TODO Comment
**Severity:** Low
**Component:** substrate/lock_in.py
**Status:** Open

#### Description
Lock-in computation could be optimized with batch queries.

#### Evidence
```python
# TODO: Optimize with batch query (line 270)
```

#### Code Reference
[substrate/lock_in.py:270](src/luna/substrate/lock_in.py#L270)

---

### BUG-032: Deprecated Config Key (use_louvain)

**Category:** Potential (Audit Finding)
**Severity:** Low
**Component:** memory_economy_config.json
**Status:** Open

#### Description
`use_louvain` key set to false with no implementation references.

#### Suggested Fix
Remove key if Louvain clustering not planned.

#### Code Reference
[config/memory_economy_config.json](config/memory_economy_config.json)

---

### BUG-033: Identity Module Empty

**Category:** Potential (Audit Finding)
**Severity:** Low
**Component:** identity/__init__.py
**Status:** Open

#### Description
Identity module is a single-line empty placeholder (1 line).

#### Suggested Fix
Either implement identity features or remove placeholder module.

#### Code Reference
[identity/__init__.py](src/luna/identity/__init__.py)

---

### BUG-034: No Error Boundaries in Frontend

**Category:** Potential (Audit Finding)
**Severity:** Low
**Component:** frontend/
**Status:** Open

#### Description
No React Error Boundaries present for graceful failure handling.

#### Suggested Fix
Add error boundaries around major component sections.

#### Code Reference
AUDIT-FRONTEND.md Recommendations section.

---

### BUG-035: Unused Frontend Components Exported

**Category:** Potential (Audit Finding)
**Severity:** Low
**Component:** frontend/
**Status:** Open

#### Description
LunaAutoTuner, MemoryEconomyPanel, LLMProviderDropdown exported but never used in main App.

#### Suggested Fix
Either integrate or remove from exports to reduce bundle size.

#### Code Reference
AUDIT-FRONTEND.md Orphan Components section.

---

## Summary by Component

| Component | Critical | High | Medium | Low |
|-----------|----------|------|--------|-----|
| api/server.py | 1 | 0 | 0 | 1 |
| actors/director.py | 0 | 3 | 1 | 0 |
| actors/scribe.py | 0 | 1 | 0 | 0 |
| actors/__init__.py | 0 | 1 | 0 | 0 |
| actors/history_manager.py | 0 | 0 | 1 | 0 |
| substrate/memory.py | 0 | 1 | 2 | 0 |
| substrate/database.py | 1 | 0 | 0 | 0 |
| substrate/lock_in.py | 0 | 0 | 2 | 1 |
| substrate/schema.sql | 0 | 0 | 1 | 0 |
| inference/local.py | 1 | 1 | 0 | 0 |
| memory/clustering_engine.py | 0 | 1 | 0 | 0 |
| memory/lock_in.py | 0 | 1 | 0 | 0 |
| memory/cluster_manager.py | 0 | 0 | 1 | 0 |
| entities/context.py | 1 | 0 | 0 | 0 |
| entities/storage.py | 0 | 0 | 1 | 0 |
| entities/reflection.py | 0 | 0 | 1 | 0 |
| engine.py | 0 | 0 | 2 | 0 |
| context/pipeline.py | 1 | 0 | 0 | 0 |
| luna_mcp/tools/forge.py | 1 | 0 | 0 | 0 |
| config/ | 1 | 0 | 0 | 1 |
| pyproject.toml | 0 | 0 | 0 | 1 |
| frontend/ | 0 | 0 | 0 | 3 |
| tests/ | 0 | 1 | 0 | 0 |
| identity/ | 0 | 0 | 0 | 1 |

---

*End of Bug Registry*
