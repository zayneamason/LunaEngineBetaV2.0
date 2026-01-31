# CONFLICTS.md

**Generated:** 2026-01-30
**Agent:** Bug Analysis
**Phase:** 3

## Summary

| Category | Count |
|----------|-------|
| Actor Count Mismatch | 1 |
| Table Name Mismatch | 2 |
| Field Name Mismatch | 1 |
| Feature Status Mismatch | 5 |
| Database Path Mismatch | 1 |
| Configuration Mismatch | 2 |
| **Total Conflicts** | **12** |

---

## CONFLICT-001: Actor Count - Bible vs Implementation

**Bible Reference:** Part II: System Architecture, Section 2.2
**Code Reality:** 5 actors implemented, not 6

### Bible Claims
Original Bible v2.0 specified 6 actors:
- Director
- Matrix
- Scribe (Ben Franklin)
- Librarian (The Dude)
- Oven (Shadow Reasoner)
- Voice

### Code Reality
Only 5 actors implemented in `src/luna/actors/`:
- DirectorActor
- MatrixActor
- ScribeActor
- LibrarianActor
- HistoryManagerActor (NOT in original spec)

**Missing:**
- Oven Actor (Claude delegation handled in Director)
- Voice Actor (Voice I/O handled by PersonaAdapter)

**Added (not in original spec):**
- HistoryManagerActor (three-tier conversation history)

### Resolution
**Status:** Bible UPDATED (v2.1)

Bible Part II now correctly notes:
> "Actor count corrected: 5 actors implemented (Director, Matrix, Scribe, Librarian, HistoryManager)"
> "Voice and Oven actors NOT implemented"

---

## CONFLICT-002: Table Name - nodes vs memory_nodes

**Bible Reference:** Part III: Memory Matrix, original schema
**Code Reality:** Table is `memory_nodes`, not `nodes`

### Bible Claims (Original)
```sql
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    ...
);
```

### Code Reality
```sql
CREATE TABLE memory_nodes (
    id TEXT PRIMARY KEY,
    ...
);
```

### Resolution
**Status:** Bible UPDATED (v2.2)

Bible Part III schema now uses correct table name `memory_nodes`.

---

## CONFLICT-003: Table Name - edges vs graph_edges

**Bible Reference:** Part III: Memory Matrix, original schema
**Code Reality:** Table is `graph_edges`, not `edges`

### Bible Claims (Original)
```sql
CREATE TABLE edges (
    ...
);
```

### Code Reality
```sql
CREATE TABLE graph_edges (
    ...
);
```

### Resolution
**Status:** Bible UPDATED (v2.2)

Bible Part III schema now uses correct table name `graph_edges`.

---

## CONFLICT-004: Field Name - cloud_generations vs delegated_generations

**Bible Reference:** Not explicitly documented
**Code Reality:** Tests expect `cloud_generations`, code uses `delegated_generations`

### Tests (Outdated)
```python
assert director.cloud_generations == X
```

### Code Reality (Current)
```python
self._delegated_generations += 1
```

### Resolution
**Status:** Open - Tests Need Update

Update test assertions from `cloud_generations` to `delegated_generations`.

---

## CONFLICT-005: FTS5 Status - Documented as Implemented, Actually Not

**Bible Reference:** Part III: Memory Matrix v2.1
**Code Reality:** FTS5 not fully implemented, uses LIKE queries

### Bible Claims (v2.1)
```
Search Architecture:
    - FTS5 (Full-Text Search)
    - sqlite-vec (Semantic vectors)
    - Graph (Traversal)
```

### Code Reality
- `search_nodes()` uses `WHERE content LIKE ?` pattern matching
- `fts5_search()` method exists but checks for table existence and falls back
- FTS5 virtual table defined in schema.sql with triggers
- But primary search path still uses LIKE queries

### Resolution
**Status:** Bible UPDATED (v2.2)

Bible Part III now notes:
> "FTS5 full-text search is NOT currently implemented. The system uses LIKE pattern matching for keyword search. This is a known limitation."

---

## CONFLICT-006: Tag Siblings - Documented in Formula, Not Implemented

**Bible Reference:** Part III-A: Lock-In Coefficient
**Code Reality:** Tag siblings always return 0

### Bible Claims
Lock-in formula includes:
```python
locked_tag_sibling_count * 0.1  # 10% weight
```

### Code Reality
```python
# TODO: Implement tag sibling counting
locked_tag_sibling_count = 0  # Always 0
```

### Resolution
**Status:** Document as Gap

Bible Part III v2.2 Known Limitations section notes:
> "Tag siblings not implemented - 10% of lock-in weight missing"

---

## CONFLICT-007: Database Path - ~/.luna/luna.db vs data/luna_engine.db

**Bible Reference:** Part II: System Architecture, Configuration section
**Code Reality:** Two conflicting defaults

### Bible Claims
```yaml
# ~/.luna/config.yaml
matrix:
  database: "memory_matrix.db"
```

### Code Reality

| Component | Default Path |
|-----------|--------------|
| MemoryDatabase class | `~/.luna/luna.db` |
| MatrixActor | `data/luna_engine.db` |

### Resolution
**Status:** Open - Needs Code Fix

Standardize on `data/luna_engine.db` as documented in HANDOFF-MEMORY-WIPE-EMERGENCY.md.

---

## CONFLICT-008: KV Cache (Identity Buffer) - Documented, Not Implemented

**Bible Reference:** Part II: System Architecture, Layer 0.5
**Code Reality:** No KV cache implementation found

### Bible Claims
```
Layer 0.5: ACCELERATION
    identity_buffer.safetensors
    (pre-computed KV cache)
```

Also in config spec:
```yaml
director:
  identity_cache: "identity_buffer.safetensors"
```

### Code Reality
- No `identity_buffer.safetensors` file exists
- No code references `identity_cache` or `identity_buffer`
- Hot path timing budget assumes 5ms KV cache load, but this doesn't exist

### Resolution
**Status:** Document as Gap

This is a planned optimization not yet implemented.

---

## CONFLICT-009: Oven Actor - Documented, Handled Differently

**Bible Reference:** Part II, Part VIII (Delegation Protocol)
**Code Reality:** No Oven actor, delegation in Director

### Bible Claims
```
┌───────────┐      ┌───────────┐
│  DELEGATE │      │  STREAM   │
│  to Oven  │      │  to TTS   │
└───────────┘      └───────────┘
```

Also:
> "The Runtime Engine watches for `<REQ_CLAUDE>` and triggers the Shadow Reasoner flow"

### Code Reality
- No Oven actor exists
- `<REQ_CLAUDE>` token detection exists in Director
- Claude delegation handled directly in `_generate_with_delegation()` method
- No separate actor for "shadow reasoning"

### Resolution
**Status:** Bible UPDATED (v2.1)

Bible notes:
> "Oven Actor NOT implemented: Claude delegation is handled directly in Director via `_should_delegate()`"

---

## CONFLICT-010: Voice Actor - Documented, Not Actor Pattern

**Bible Reference:** Part II: System Architecture
**Code Reality:** Voice handled by PersonaAdapter, not an actor

### Bible Claims
Actor list includes "Voice" with:
```
| Voice | STT/TTS/Audio I/O |
```

Also:
```
| Hot tier unavailable | Voice Actor plays error message |
```

### Code Reality
- No VoiceActor class exists
- Voice I/O handled by `PersonaAdapter` in `src/voice/backend.py`
- PersonaAdapter does not follow actor pattern (no mailbox)
- TTS handled by `TTSManager` in `src/voice/tts/`

### Resolution
**Status:** Bible UPDATED (v2.1)

Bible notes:
> "Voice Actor NOT implemented: Voice I/O handled by `PersonaAdapter` (non-actor pattern)"

---

## CONFLICT-011: Speculative Retrieval - Documented, Partially Implemented

**Bible Reference:** Part II: Data Flow, Section 2.5
**Code Reality:** Speculative retrieval not fully wired

### Bible Claims
```
USER STARTS SPEAKING
    │
┌───┴───┐               ┌──────────────┐
│WHISPER │              │ SPECULATIVE  │
│(stream)│──────────────│  RETRIEVAL   │
│        │  trigger on  │              │
│Partial │  partial     │ Start search │
│transcripts             │ on partial   │
```

### Code Reality
- Whisper streaming exists in voice system
- No evidence of "speculative retrieval" triggered on partial transcripts
- Memory retrieval happens after full message received
- Hot path timing budget assumes retrieval already done, but code path shows retrieval happens after user message complete

### Resolution
**Status:** Document as Gap

Speculative retrieval is a documented optimization not yet implemented.

---

## CONFLICT-012: Warm Path (7B Model) - Documented, Not Implemented

**Bible Reference:** Part II: Tiered Execution, Section 2.4
**Code Reality:** No 7B model path

### Bible Claims
```
HOT PATH (3B Local)
    │
    │ Complexity threshold
    ▼
WARM PATH (7B Local)
    │
    │ <REQ_CLAUDE> token
    ▼
COLD PATH (Claude API)
```

Also in config:
```yaml
director:
  model_3b: "qwen2.5-3b-instruct"
  model_7b: "qwen2.5-7b-instruct"
  adapter_3b: "adapters/luna-3b-v1.0"
  adapter_7b: "adapters/luna-7b-v1.0"
```

### Code Reality
- Only one local model path (Qwen 3B)
- No complexity-based routing between 3B and 7B
- Routing is binary: local OR Claude delegation
- No 7B model adapter found in models directory

### Resolution
**Status:** Document as Gap

Two-tier local model system is documented but not implemented. Current implementation is binary: local 3B or cloud Claude.

---

## Resolution Summary

| Conflict | Status | Action |
|----------|--------|--------|
| Actor Count | RESOLVED | Bible updated |
| Table: nodes | RESOLVED | Bible updated |
| Table: edges | RESOLVED | Bible updated |
| Field: cloud_generations | OPEN | Update tests |
| FTS5 Status | RESOLVED | Bible updated with note |
| Tag Siblings | RESOLVED | Bible documents gap |
| Database Path | OPEN | Code fix needed |
| KV Cache | OPEN | Document as future feature |
| Oven Actor | RESOLVED | Bible updated |
| Voice Actor | RESOLVED | Bible updated |
| Speculative Retrieval | OPEN | Document as future feature |
| Warm Path (7B) | OPEN | Document as future feature |

---

## Recommendations

### Immediate Actions
1. **Fix database path conflict** - Standardize on `data/luna_engine.db`
2. **Update tests** - Rename `cloud_generations` to `delegated_generations`

### Documentation Updates
1. Add "Future Features" section to Bible documenting:
   - KV Cache (identity buffer)
   - Speculative retrieval
   - Warm path (7B model tier)
   - FTS5 full implementation
   - Tag siblings

### Code Updates to Match Bible
1. Implement FTS5 search as primary keyword path
2. Add tag sibling counting to lock-in formula
3. Consider adding KV cache for hot path optimization

### Bible Updates to Match Code
All major conflicts have been addressed in Bible v2.1/v2.2, but the Future Features documentation is needed.

---

*End of Conflicts Report*
