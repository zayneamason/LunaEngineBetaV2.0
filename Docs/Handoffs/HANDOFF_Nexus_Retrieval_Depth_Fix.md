# HANDOFF: Nexus Retrieval Depth Fix — Luna Can't Surface Chapter-Level Detail

**Priority:** P0 — Blocks investor demo capability  
**Scope:** Two fixes, one codebase path each  
**Time estimate:** 20–30 minutes  
**Risk:** Low — targeted parameter changes + one endpoint extension  
**Date:** 2026-03-24

---

## The Problem

Luna has 456 structural extractions from *Priests and Programmers* sitting in `research_library` (confirmed: 1 document, 196 chunks, 456 extractions, `enabled: true`, `read_only: false`). When asked about the book, she gives impressive responses — but they come from training knowledge and Memory Matrix conversation nodes, not from the actual extraction data.

Evidence from live Eclissi session (grounding scores across 8 responses):

| Response | Grounded | Inferred | Ungrounded |
|---|---|---|---|
| Complex systems analysis | 0 | 6 | 14 |
| Negative test (climate/crypto) | 0 | 3 | 4 |
| False claim rejection | 1 | 0 | 6 |
| Traditional intelligence | 0 | 4 | 10 |
| Cross-collection connection | 1 | 5 | 7 |
| Most surprising finding | 1 | 7 | 5 |
| Self-reflection response | 3 | 5 | 11 |
| "Tell me about P&P again" | 2 | 4 | 4 |

She's getting 0–3 grounded claims per response. With 456 extractions available, she should be getting 10+. Luna herself says: *"what I don't have is the full text or chapter-level detail."*

The pipe isn't closed — it's leaking. A trickle gets through. Not enough for chapter-level answers. Not enough for an investor demo.

---

## Root Cause Analysis

Two separate issues, two separate code paths.
### Fix A: Widen the Eclissi Retrieval Window (Affects Voice Luna / Eclissi)

**File:** `src/luna/engine.py` — `_get_collection_context()` starting at line ~1718

**What's happening:** The gate fix from the Unclog handoff IS working — `research_library` IS being searched. But the retrieval limits are too tight:

```python
# TIER 1: Extraction FTS5 — only grabs 5 results
ext_rows = conn.conn.execute(
    "SELECT e.node_type, e.content, e.confidence "
    "FROM extractions_fts "
    "JOIN extractions e ON extractions_fts.rowid = e.rowid "
    "WHERE extractions_fts MATCH ? "
    "ORDER BY e.confidence DESC "
    "LIMIT 5",                          # <--- TOO LOW
    (fts_query,),
).fetchall()
```

```python
# TIER 2: Only triggers if Tier 1 returns < 2 results
if len(ext_rows) < 2:                   # <--- TOO CONSERVATIVE
    expanded_rows = _expand_and_search_extractions(conn, query)
```

```python
# TIER 3: Only triggers if total unique content < 2
if len(seen_content) < 2 and char_budget > 1000:  # <--- SAME ISSUE
```

The result: Tier 1 grabs 5 extractions, the sparse check says "5 >= 2, that's enough" and skips Tiers 2 and 3. Of those 5, after deduplication and budget trimming, 1–3 make it into the context window. Hence the trickle.
**The fix — 5 targeted changes in `_get_collection_context()`:**

1. **Increase Tier 1 LIMIT from 5 to 15:**
```python
"LIMIT 15",
```

2. **Change Tier 2 threshold from `< 2` to `< 8`:**
```python
if len(ext_rows) < 8:
```

3. **Change Tier 3 threshold from `< 2` to `< 5`:**
```python
if len(seen_content) < 5 and char_budget > 1000:
```

4. **Increase Tier 3 semantic/keyword limit from 3 to 5:**
```python
sem_results = await self.aibrarian.search(
    key, query, "semantic", limit=5
)
# ... and the keyword fallback:
sem_results = await self.aibrarian.search(
    key, query, "keyword", limit=5
)
```

5. **Increase MAX_CHARS budget from 6000 to 10000:**
```python
MAX_CHARS = 10000
```

**Why these numbers:** 15 extraction hits x ~200 chars average = ~3000 chars for Tier 1. Tier 2 adds expanded queries for another ~1500. Tier 3 adds semantic chunks for another ~2000. Total ~6500 chars well within the 10K budget. Should produce 8–15 grounded claims per response instead of 1–3.
**Verification:**

After fix, restart the engine and in Eclissi ask: "What are the main chapters or themes in Priests and Programmers?"

Expected:
- Luna describes specific content (subak system, water temples, Green Revolution, simulation model, pest management)
- Grounding scores show 5+ grounded claims
- She references specific concepts from the extractions, not just general training knowledge

---

### Fix B: Add Nexus Search to `/memory/smart-fetch` Endpoint (Affects MCP Tools)

**File:** `src/luna/api/server.py` — `memory_smart_fetch()` at line ~3568

**What's happening:** The `/memory/smart-fetch` endpoint (used by `luna_smart_fetch` MCP tool) ONLY searches the Memory Matrix. It calls `memory.get_context()` which is a pure Matrix operation. It has zero awareness that Nexus collections exist. This is by design — it was never wired.

**Current code (line ~3590):**
```python
# Uses the matrix's get_context method — Memory Matrix ONLY
nodes = await memory.get_context(query=request.query, max_tokens=max_tokens)
```

**The fix:** After the Matrix search, also search Nexus collections and merge results. Add this block AFTER the existing `memory.get_context()` call and BEFORE the results formatting, inside the try block:
```python
        # ── Also search Nexus collections ──
        nexus_results = []
        if _engine and hasattr(_engine, 'aibrarian') and _engine.aibrarian:
            aibrarian = _engine.aibrarian
            for key, cfg in aibrarian.registry.collections.items():
                if not cfg.enabled or cfg.read_only:
                    continue
                try:
                    conn = aibrarian.connections.get(key)
                    if not conn:
                        continue
                    from luna.substrate.aibrarian_engine import AiBrarianEngine
                    fts_query = AiBrarianEngine._sanitize_fts_query(request.query)
                    ext_rows = conn.conn.execute(
                        "SELECT e.node_type, e.content, e.confidence "
                        "FROM extractions_fts "
                        "JOIN extractions e ON extractions_fts.rowid = e.rowid "
                        "WHERE extractions_fts MATCH ? "
                        "ORDER BY e.confidence DESC "
                        "LIMIT 10",
                        (fts_query,),
                    ).fetchall()
                    for row in ext_rows:
                        nexus_results.append({
                            "id": f"nexus:{key}:{row[0]}:{len(nexus_results)}",
                            "node_type": row[0],
                            "content": row[1],
                            "confidence": row[2] if len(row) > 2 else 0.85,
                            "lock_in": 0.5,
                            "lock_in_state": "fluid",
                            "source": f"nexus/{key}",
                        })
                except Exception as e:
                    logger.warning(f"Smart-fetch Nexus search for {key}: {e}")
```
Then merge nexus_results into the final results list (right before the Permission gate comment):

```python
        # Merge Matrix + Nexus results
        results = results + nexus_results
```

**Verification:**

From Claude Desktop or Claude.ai MCP, call:
```
luna_smart_fetch(query="water temple system Bali", budget_preset="rich")
```

Expected:
- Returns both Memory Matrix nodes AND Nexus extraction nodes
- Nexus nodes have `source: "nexus/research_library"` in their dict
- Total node count > 0 even for queries that only exist in collections

---

## Execution Order

1. **Fix A first** — this is what matters for Eclissi/voice Luna and the investor demo
2. **Fix B second** — this makes MCP tools useful for knowledge retrieval
3. **Test Fix A in Eclissi** with chapter-level questions about Priests and Programmers
4. **Test Fix B via MCP** with `luna_smart_fetch` call

---

## What NOT To Do

- Do NOT modify the aperture system, lock-in architecture, or collection registry config — those are all working correctly
- Do NOT change the gate logic in `_get_collection_context` — the default-open fix from the Unclog handoff is correct
- Do NOT restructure the endpoint architecture — this is additive, not a refactor
- Do NOT touch the Memory Matrix search paths — they work fine for what they do
- Do NOT implement the Reflection Layer, Mode Awareness, or any other comprehension roadmap step — this handoff is ONLY about retrieval depth
- Do NOT increase MAX_CHARS beyond 10000 without checking the context assembler's total budget
---

## Context: Why This Matters

Hai Dai needs to show investors that Luna can discuss specific document content in depth — not just give impressive-sounding responses from training knowledge. The current state is:

- Luna sounds great (Sonnet brain + personality + conversation memory)
- Luna is honest about gaps ("I don't have the full text")
- But the grounding scores prove she's mostly inferring, not retrieving
- Chapter-level questions get generic answers instead of specific extraction-backed detail

Fix A directly addresses this by letting more extraction data flow through to her context window. The knowledge is there. The brain is good. The pipe just needs to be wider.

---

## Files Modified

| File | Change |
|---|---|
| `src/luna/engine.py` | Widen limits in `_get_collection_context()`: Tier 1 LIMIT 5→15, Tier 2 threshold 2→8, Tier 3 threshold 2→5, semantic limit 3→5, MAX_CHARS 6000→10000 |
| `src/luna/api/server.py` | Add Nexus collection search to `memory_smart_fetch()` endpoint after Matrix search |
