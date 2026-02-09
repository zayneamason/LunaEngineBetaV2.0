# HANDOFF: AI-BRARIAN & Memory Matrix Audit

**Date:** 2026-02-08
**From:** Architect (The Dude)
**To:** Claude Code
**Priority:** High — Correctness audit before further development
**Project Root:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root`

---

## OBJECTIVE

Run a comprehensive analysis and audit of three interconnected systems:

1. **The Scribe (Ben Franklin)** — Extraction pipeline
2. **The Librarian (The Dude)** — Filing & retrieval pipeline
3. **Memory Matrix** — Storage substrate (sqlite-vec, graph, FTS5)

The goal is to verify these systems are correctly wired, functioning end-to-end, and identify any dead code, broken paths, or architectural drift from the design spec.

---

## SYSTEM MAP

### File Locations

```
src/luna/
├── extraction/              # Scribe data types & chunking
│   ├── types.py             # ExtractionType, ExtractedObject, ExtractedEdge, ExtractionOutput, FilingResult, Chunk, ExtractionConfig
│   └── chunker.py           # SemanticChunker (turn + text chunking)
├── actors/
│   ├── scribe.py            # ScribeActor (Ben Franklin) — LLM-powered extraction
│   ├── librarian.py         # LibrarianActor (The Dude) — filing, wiring, pruning, entity resolution
│   └── matrix.py            # MatrixActor — Memory Matrix wrapper
├── librarian/
│   └── cluster_retrieval.py # ClusterRetrieval — cluster-aware search (monkey-patches Librarian)
├── memory/
│   ├── ring.py              # ConversationRing — fixed-size turn buffer
│   ├── lock_in.py           # LockInCalculator — cluster-level lock-in dynamics
│   ├── constellation.py     # ConstellationAssembler — context assembly with budget
│   ├── cluster_manager.py   # ClusterManager — cluster CRUD operations
│   └── clustering_engine.py # Clustering logic
├── substrate/               # Low-level storage (CHECK: memory.py, database.py, graph.py, embeddings.py)
├── entities/                # Entity system (models.py, resolution.py)
├── engine.py                # Main engine — wires actors, extraction trigger, tick loops
├── api/
│   └── server.py            # FastAPI server (port 8000) — /extraction/trigger, /memory/*, /hub/*
src/luna_mcp/
├── api.py                   # MCP API (port 8742) — proxy layer to Engine API
├── tools/
│   └── memory.py            # MCP tool functions — smart_fetch, search, add_node, session management, auto-session
├── memory_log.py            # Memory operation logging
```

### Data Flow (Happy Path)

```
User Message
    ↓
Engine.process_input() → records turn via record_conversation_turn()
    ↓
Engine triggers extraction → sends "extract_turn" message to ScribeActor
    ↓
ScribeActor:
  1. Skips assistant turns (GOOD — only extracts user info)
  2. Chunks via SemanticChunker
  3. Batches or processes immediately
  4. Calls Claude API (Haiku) with EXTRACTION_SYSTEM_PROMPT
  5. Parses JSON → ExtractedObjects + ExtractedEdges + EntityUpdates
  6. Sends "file" message to LibrarianActor
  7. Sends "entity_update" messages for entity changes
    ↓
LibrarianActor:
  1. Receives "file" → calls _wire_extraction()
  2. Resolves entities (cache → DB → create new)
  3. Creates edges in graph
  4. Receives "entity_update" → calls _file_entity_update()
  5. Creates versioned entity records (append-only)
    ↓
Memory Matrix (via MatrixActor):
  - Nodes stored in SQLite (memory_nodes table)
  - Vectors in sqlite-vec
  - Graph edges in NetworkX
  - Clusters tracked in clusters/cluster_members tables
```

### MCP Session Flow (Auto-Session)

```
MCP Tool Call (any tool)
    ↓
ensure_auto_session() → creates session via /hub/session/create
    ↓
auto_record_turn() → buffers turns, flushes at threshold (4 turns)
    ↓
Inactivity Monitor (60s check, 5min timeout)
    ↓
_end_auto_session():
  1. Flushes buffered turns
  2. Fetches all turns via /hub/active_window
  3. Ends session via /hub/session/end
  4. Triggers extraction via /extraction/trigger with full conversation content
```

---

## AUDIT TASKS

### Phase 1: Static Analysis

Run these checks without starting the engine:

1. **Import chain verification** — Verify all imports resolve correctly:
   ```bash
   cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
   source .venv/bin/activate
   python -c "from luna.actors.scribe import ScribeActor; print('Scribe OK')"
   python -c "from luna.actors.librarian import LibrarianActor; print('Librarian OK')"
   python -c "from luna.actors.matrix import MatrixActor; print('Matrix OK')"
   python -c "from luna.extraction.types import ExtractionType, ExtractedObject; print('Types OK')"
   python -c "from luna.extraction.chunker import SemanticChunker; print('Chunker OK')"
   python -c "from luna.memory.lock_in import LockInCalculator; print('LockIn OK')"
   python -c "from luna.memory.constellation import ConstellationAssembler; print('Constellation OK')"
   python -c "from luna.librarian.cluster_retrieval import ClusterRetrieval; print('ClusterRetrieval OK')"
   python -c "from luna.entities.resolution import EntityResolver; print('EntityResolver OK')"
   ```

2. **Dead code detection** — Check for:
   - Functions/classes in `librarian/cluster_retrieval.py` that reference a `Librarian` class via `integrate_with_librarian()` — does a standalone Librarian class exist, or is this only the actor? The monkey-patch function may be dead code if never called.
   - `EXTRACTION_BACKENDS` in `types.py` references `"claude-3-haiku-20240307"` and `"claude-3-5-sonnet-20241022"` — verify these model strings are still valid or need updating.
   - `_extract_local()` in scribe.py falls back to empty result if local model unavailable — confirm this is intentional vs. should fall back to Claude.

3. **Schema validation** — Inspect the actual database:
   ```bash
   sqlite3 /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/luna_memory.db ".tables"
   sqlite3 /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/luna_memory.db ".schema memory_nodes"
   sqlite3 /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/luna_memory.db ".schema clusters"
   sqlite3 /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/luna_memory.db ".schema cluster_members"
   sqlite3 /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/luna_memory.db ".schema cluster_edges"
   sqlite3 /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/luna_memory.db ".schema entities"
   sqlite3 /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/luna_memory.db ".schema entity_versions"
   sqlite3 /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/luna_memory.db ".schema conversation_turns"
   ```
   Also check `memory.db` — determine which is the active database and whether there's confusion between the two.

4. **Column/field alignment** — The Scribe produces `ExtractedObject` with fields `type, content, confidence, entities, source_id, metadata`. The Librarian's `_wire_extraction()` uses `obj.content` as the entity name for `_resolve_entity()`. This means **every extracted FACT gets resolved as an entity node** — is this intentional? A FACT like "Mars College is in February 2026" would create a node with that full sentence as the content AND as the entity name. Audit whether this is creating noise vs. clean knowledge nodes.

### Phase 2: Wiring Verification

5. **Engine → Scribe trigger** — In `engine.py`, find where extraction is triggered. Verify:
   - Is it triggered on every user message, or only on session end?
   - Does the MCP `/extraction/trigger` endpoint in `api/server.py` actually route to the Scribe actor, or does it go through a different path?
   - Check if both paths (engine internal + API endpoint) result in the same extraction flow.

6. **Scribe → Librarian message passing** — Verify:
   - `_send_to_librarian()` sends a Message with type="file" and payload=`extraction.to_dict()`
   - LibrarianActor.handle() case "file" receives this and calls `_wire_extraction()`
   - `_send_entity_update_to_librarian()` sends type="entity_update"
   - LibrarianActor handles "entity_update" and calls `_file_entity_update()`
   - Confirm the actors are both registered in the engine and mailboxes are wired.

7. **Librarian → Matrix wiring** — The Librarian calls `_get_matrix()` which does:
   ```python
   matrix_actor = self.engine.get_actor("matrix")
   return matrix_actor._matrix or matrix_actor._memory
   ```
   Verify MatrixActor actually has these attributes set. Check `actors/matrix.py` for initialization.

8. **Entity Resolution** — `_resolve_entity()` calls `_find_existing_node()` which does `matrix.search_nodes(name, node_type=entity_type, limit=1)`. Verify:
   - `MemoryMatrix.search_nodes()` exists and works with these parameters
   - The entity resolution is NOT creating duplicate nodes for the same concept
   - The alias cache is properly persisted or at least not lost on restart

9. **Graph edge creation** — `_create_edge()` accesses `matrix_actor._graph` which should be a NetworkX graph. Verify:
   - The graph is initialized in MatrixActor
   - `has_edge()` and `add_edge()` methods exist
   - Edges persist to SQLite (not just in-memory NetworkX)

### Phase 3: Memory Matrix Deep Audit

10. **Node counts and health** — Run queries:
    ```sql
    SELECT COUNT(*) FROM memory_nodes;
    SELECT node_type, COUNT(*) FROM memory_nodes GROUP BY node_type;
    SELECT COUNT(*) FROM memory_nodes WHERE lock_in < 0.2;  -- drifting nodes
    SELECT COUNT(*) FROM clusters;
    SELECT state, COUNT(*) FROM clusters GROUP BY state;
    SELECT COUNT(*) FROM cluster_members;
    SELECT COUNT(*) FROM entities;
    SELECT COUNT(*) FROM entity_versions;
    ```

11. **Embedding coverage** — Check how many nodes have embeddings:
    ```sql
    -- This depends on the sqlite-vec table structure
    -- Check what the vector table is called and its row count
    ```

12. **FTS5 health** — Verify full-text search index exists and works:
    ```sql
    -- Check if FTS5 virtual table exists
    SELECT * FROM sqlite_master WHERE type='table' AND name LIKE '%fts%';
    -- Test a search
    SELECT * FROM memory_nodes_fts WHERE memory_nodes_fts MATCH 'Luna' LIMIT 5;
    ```

13. **Cluster health** — Verify lock-in distribution makes sense:
    ```sql
    SELECT 
      CASE 
        WHEN lock_in >= 0.85 THEN 'crystallized'
        WHEN lock_in >= 0.70 THEN 'settled'
        WHEN lock_in >= 0.20 THEN 'fluid'
        ELSE 'drifting'
      END as computed_state,
      state as stored_state,
      COUNT(*)
    FROM clusters
    GROUP BY computed_state, stored_state;
    ```
    Flag any mismatches between computed and stored state.

14. **Conversation turn recording** — Verify turns are being recorded:
    ```sql
    SELECT COUNT(*) FROM conversation_turns;
    SELECT role, COUNT(*) FROM conversation_turns GROUP BY role;
    -- Check most recent turns
    SELECT role, substr(content, 1, 80), created_at FROM conversation_turns ORDER BY created_at DESC LIMIT 10;
    ```

### Phase 4: Test Coverage Analysis

15. **Run existing tests** — Execute and report results:
    ```bash
    cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
    source .venv/bin/activate
    python -m pytest tests/test_scribe.py -v 2>&1 | head -50
    python -m pytest tests/test_librarian.py -v 2>&1 | head -50
    python -m pytest tests/test_extraction_pipeline.py -v 2>&1 | head -50
    python -m pytest tests/test_memory.py -v 2>&1 | head -50
    python -m pytest tests/test_lock_in.py -v 2>&1 | head -50
    python -m pytest tests/test_mcp_memory_tools.py -v 2>&1 | head -50
    python -m pytest tests/test_entity_system.py -v 2>&1 | head -50
    python -m pytest tests/test_memory_retrieval_e2e.py -v 2>&1 | head -50
    ```

16. **Coverage gaps** — After running tests, identify what's NOT tested:
    - Scribe → Librarian message flow (end-to-end)
    - Entity resolution deduplication
    - Cluster lock-in calculation accuracy
    - MCP auto-session → extraction trigger flow
    - ConstellationAssembler token budgeting
    - ClusterRetrieval integration with actual LibrarianActor
    - Graph edge persistence (NetworkX → SQLite roundtrip)

### Phase 5: Known Concerns to Investigate

17. **Dual database confusion** — There are TWO database files at project root:
    - `luna_memory.db` (likely the active one)
    - `memory.db` (possibly legacy)
    
    Determine which one the engine actually uses. Check `EngineConfig` and `MatrixActor` for db_path configuration. Flag if there's a risk of the engine writing to one while MCP reads from the other.

18. **Extraction backend model freshness** — `EXTRACTION_BACKENDS` in `types.py` references:
    - `claude-3-haiku-20240307` — Check if this model is still available/optimal
    - `claude-3-5-sonnet-20241022` — Same check
    
    These may need updating to newer model versions.

19. **Entity resolution creates noise** — The `_wire_extraction()` method resolves EVERY `ExtractedObject.content` as an entity. This means a FACT like "Luna Engine uses sqlite-vec for embeddings" gets treated as an entity name. This is likely wrong — only items in `obj.entities` should be resolved as entities, while the object itself should be stored as a memory node with its type.

20. **`integrate_with_librarian()` may be dead code** — This function in `librarian/cluster_retrieval.py` monkey-patches a hypothetical `Librarian` instance, but the actual Librarian is an Actor (`LibrarianActor`). Check if this integration function is called anywhere, or if the cluster retrieval is wired differently.

21. **Auto-session extraction content** — In `luna_mcp/tools/memory.py`, `_end_auto_session()` sends the full conversation to `/extraction/trigger`. But the Scribe's `_handle_extract_turn()` skips assistant turns. The auto-session sends the ENTIRE conversation (both roles mixed together) as a single content blob to `extract_text`. Verify whether the extraction prompt correctly handles this mixed content, or if assistant content is leaking into extractions.

22. **Lock-in decay timing** — `LockInCalculator` uses real clock time for decay. If the engine isn't running for days, clusters could decay to near-zero on next calculation. Verify this is handled gracefully and doesn't cause mass data loss.

---

## OUTPUT FORMAT

Produce a report with these sections:

```
## 1. Import & Dependency Health
[Pass/Fail for each import check]

## 2. Database State
[Table counts, schema validation, dual-db status]

## 3. Wiring Verification
[For each connection point: WIRED/BROKEN/UNKNOWN]

## 4. Test Results
[Pass/fail counts per test file, any failures]

## 5. Known Issues Found
[Numbered list with severity: CRITICAL/HIGH/MEDIUM/LOW]

## 6. Dead Code Identified
[Functions/classes that appear unused]

## 7. Recommendations
[Prioritized action items]
```

---

## CONSTRAINTS

- **DO NOT** start the engine server (port 8000) — this is a static + database audit
- **DO NOT** call any external APIs (no Anthropic calls)
- **DO NOT** modify any source files — read-only audit
- **DO** run tests (they should use mocks/fixtures)
- **DO** query the SQLite databases directly
- **DO** check git status for uncommitted changes that might affect findings
