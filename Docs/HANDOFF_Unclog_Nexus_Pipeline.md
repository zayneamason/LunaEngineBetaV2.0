# HANDOFF: Unclog Nexus Retrieval Pipeline

**Priority:** P0 — Nothing else matters until this is done  
**Scope:** Two bugs blocking ALL Nexus/collection retrieval  
**Time estimate:** 15–20 minutes  
**Risk:** Low — targeted fixes, no architectural changes

---

## Context

Luna cannot retrieve ANY content from Nexus collections (including the research library). Six handoffs exist in `Docs/Handoffs/` for upgrading the comprehension pipeline (multi-query decomposition, retry loops, grounding wiring, etc). **None of them matter yet.** The pipe is clogged at the gate. These two bugs mean the aperture path never runs — Luna never even attempts to search collections.

Step 1 of the comprehension roadmap (switching LLM to Claude Sonnet 4.6) has been completed via `llm_switch_provider("claude")` and persisted in config. The brain is better. The retrieval is still dead.

---

## Bug A: Lock-in Gate Returns Empty → Collections Never Searched

### What happens

1. User asks: "What is Priests and Programmers about?"
2. Engine calls `collection_lock_in.get_all()` to build `lock_in_map`
3. `get_all()` returns `{}` (empty dict)
4. `lock_in_map.get("research_library", 0.0)` returns `0.0`
5. `0.0` is NOT `> 0` → collection is excluded from `collections_to_search`
6. `collections_to_search` is empty → aperture path never runs
7. Zero `[PHASE2] Collection recall` logs appear
8. Luna gets no Nexus context → hedges or fills from training knowledge

### Evidence

- Repeated testing of "Priests and Programmers" queries across 20+ attempts: 0 grounded responses
- Data room search returns Luna Labs product docs instead of the book content
- Luna herself acknowledges the retrieval failure: "the data room pull didn't actually surface the Priests & Programmers document"
- No `[PHASE2]` logs in engine output during these queries

### Where to look

Find where `collection_lock_in.get_all()` is called and `lock_in_map` is built. The gate logic is:

```python
# Pseudocode of what's happening
lock_in_map = collection_lock_in.get_all()  # Returns {} 
for name in available_collections:
    if lock_in_map.get(name, 0.0) > 0:  # 0.0 > 0 is False
        collections_to_search.append(name)  # Never reached
```

### The fix

**Investigation first:** Read `collection_lock_in.get_all()` and trace why it returns empty. Possible causes:

1. The lock-in DB table is empty (collections were never scored)
2. The lock-in values were written but the query path reads from a different DB or table
3. The method silently catches an exception and returns `{}`

**Then fix the gate logic.** Even if `get_all()` returns empty, collections with ingested documents should still be searchable. The gate should default to OPEN, not CLOSED:

```python
# Fix: If lock-in data is missing, include all collections that have documents
if not lock_in_map:
    # Fallback: search all available collections
    collections_to_search = list(available_collections)
else:
    for name in available_collections:
        if lock_in_map.get(name, 0.0) > 0:
            collections_to_search.append(name)
```

The principle: **absence of lock-in data means "unknown," not "excluded."** A collection with 416 structural extractions should not be invisible because a scoring step didn't run.

### Verification

After fix, send: "What is Priests and Programmers about?"

- Engine logs should show `[PHASE2] Collection recall` entries
- Luna's response should reference actual content from the book (water temples, Lansing, Bali, subak system)
- Grounding score should show >0 grounded claims (even if grounding-to-Nexus wiring isn't done yet, the response quality will visibly change)

---

## Bug B: Single Quotes Break FTS5 Syntax

### What happens

1. User asks: "who are the 'priests' and who are the 'programmers'?"
2. Query passes through `_sanitize_fts_query()`
3. Single quotes are NOT stripped
4. FTS5 receives a malformed query and either errors silently or returns no results
5. Even if Bug A is fixed, queries with apostrophes or quoted terms will still fail

### Where to look

Find `_sanitize_fts_query()` (or whatever the FTS query sanitizer is named). It likely strips double quotes and special characters but misses single quotes.

### The fix

Add single quote stripping to the sanitizer:

```python
def _sanitize_fts_query(query: str) -> str:
    # ... existing sanitization ...
    query = query.replace("'", "")  # Strip single quotes (break FTS5 MATCH)
    query = query.replace('"', "")  # Strip double quotes if not already handled
    # ... rest of sanitization ...
    return query
```

Also consider stripping curly/smart quotes (`\u2018`, `\u2019`, `\u201C`, `\u201D`) since these can arrive from mobile keyboards or pasted text.

### Verification

After fix, send: "who are the 'priests' and who are the 'programmers'?"

- Should return results (not empty/error)
- Compare with same query without quotes: "who are the priests and who are the programmers" — results should be equivalent

---

## Execution Order

1. **Fix Bug A first** (lock-in gate) — this is the total blocker
2. **Fix Bug B second** (FTS5 quotes) — this catches a class of query failures
3. **Test both together** with: `who are the 'priests' and who are the 'programmers'?`

---

## What NOT To Do

- Do NOT implement any of the six comprehension handoffs (Steps 2–6) in this session. Those are separate work. This handoff is ONLY about unclogging the pipe.
- Do NOT restructure the aperture system, rename collections, or refactor the lock-in architecture. Targeted fixes only.
- Do NOT change the LLM provider. It's already been switched to Claude Sonnet 4.6. Verify with `llm_providers` MCP tool if unsure.
- Do NOT modify the Nexus extraction pipeline, ingestion logic, or collection schemas.
- Do NOT add retry loops or multi-query decomposition — those are Steps 2 and 3, separate handoffs already written.

---

## After This Handoff

Once the pipe is unclogged and Luna can actually find collection content, the remaining comprehension roadmap in `Docs/Handoffs/` is:

| # | File | What it does | Status |
|---|------|-------------|--------|
| 1 | `HANDOFF_Switch_LLM_To_Claude.md` | Switch to Sonnet 4.6 | **DONE** |
| **→** | **This handoff** | **Unclog the retrieval gate** | **DO THIS NOW** |
| 2 | `HANDOFF_Multi_Query_Decomposition.md` | Split compound questions into parallel searches | Ready |
| 3 | `HANDOFF_Retrieval_Retry_Loop.md` | Three-tier cascade: FTS5 → expanded → semantic | Ready |
| 4 | `HANDOFF_Grounding_Nexus_Wiring.md` | Fix the lying scoreboard | Ready |
| 5 | `HANDOFF_Nexus_Matrix_Bridge.md` | Document knowledge persists across sessions | Ready |
| 6 | `HANDOFF_Agentic_Nexus_Retrieval.md` | Luna requests more context mid-generation | Ready |

Steps 2–6 compound on each other but each is independently executable. None of them work if the gate is still closed.

---

## The One-Line Summary

Luna has 416 structural extractions from the book. She has a Claude Sonnet brain ready to reason over them. The retrieval gate is returning empty and blocking everything. Open the gate.
