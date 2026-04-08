# HANDOFF: Retrieval Retry Loop for Nexus

**Priority:** P1 — Prevents Luna from giving up after one failed search  
**Status:** Ready for implementation  
**Depends on:** Step 2 (Multi-Query Decomposition) should land first, but this works independently  
**Target file:** `src/luna/engine.py` (modify `_get_collection_context` aperture-driven path)  
**Scope:** Retrieval pipeline only. No changes to generation, subtasks, or frontend.

---

## THE PROBLEM

When Luna searches Nexus for context, she gets ONE shot:

1. FTS5 keyword search against `extractions_fts`
2. If < 2 results, FTS5 keyword search against `chunks_fts`
3. Done.

Both searches use the exact same FTS5 MATCH engine with the raw user query. If the keywords don't match — and they often don't — Luna gets an empty context window and hedges.

**Queries that fail today:**

| Query | Why it fails |
|-------|-------------|
| "What did Lansing discover?" | FTS5 searches for "Lansing discover" — the word "discover" doesn't appear in the extractions |
| "How did outside experts mess things up?" | "mess things up" isn't in any extraction or chunk |
| "Tell me about the water management system" | "management system" returns nothing because extractions say "irrigation" and "subak", not "management system" |
| "Do you see what we were talking about?" | Zero content keywords to match against |
| "What's the main argument of the book?" | "main argument" doesn't appear in any extraction even though DOCUMENT_SUMMARY *is* the main argument |

The semantic search path (`_vec_search`) exists in the AiBrarianEngine. Embeddings are generated at ingest time. The infrastructure is there. It's just never called from `_get_collection_context()`.

## THE FIX

Replace the single-shot retrieval in `_get_collection_context()` with a three-tier cascade. Each tier only fires if the previous one returned insufficient results.

### Tier 1: Extraction FTS5 (existing — no change)
Keyword search against `extractions_fts`. Fast, precise when keywords match. This is what exists today.

### Tier 2: Query expansion + extraction FTS5 (NEW)
If Tier 1 returns < 2 results, extract individual content words from the query and try broader FTS5 searches. Free, instant.

### Tier 3: Semantic search against chunks (NEW)
If Tier 2 still returns < 2 results, use `self.aibrarian.search(key, query, "semantic")` which runs embedding similarity via sqlite-vec. This catches conceptual matches that keyword search misses entirely.

---

## IMPLEMENTATION

### Modified `_get_collection_context()` — aperture-driven path

Replace the per-collection search block (the section inside `for key in collections_to_search:`) with:

```python
        for key in collections_to_search:
            if char_budget <= 0:
                break

            conn = self.aibrarian.connections.get(key)
            if not conn:
                continue

            from luna.substrate.aibrarian_engine import AiBrarianEngine
            fts_query = AiBrarianEngine._sanitize_fts_query(query)

            # ── TIER 1: Extraction FTS5 (precise keyword match) ──────────
            ext_rows = []
            try:
                ext_rows = conn.conn.execute(
                    "SELECT e.node_type, e.content, e.confidence "
                    "FROM extractions_fts "
                    "JOIN extractions e ON extractions_fts.rowid = e.rowid "
                    "WHERE extractions_fts MATCH ? "
                    "ORDER BY e.confidence DESC "
                    "LIMIT 5",
                    (fts_query,),
                ).fetchall()
            except Exception:
                pass

            # Always include document summary
            sum_rows = []
            try:
                sum_rows = conn.conn.execute(
                    "SELECT node_type, content, confidence "
                    "FROM extractions "
                    "WHERE node_type = 'DOCUMENT_SUMMARY' "
                    "LIMIT 1",
                ).fetchall()
            except Exception:
                pass

            # ── TIER 2: Query expansion (if Tier 1 is sparse) ────────────
            if len(ext_rows) < 2:
                expanded_rows = _expand_and_search_extractions(conn, query)
                ext_rows = list(ext_rows) + expanded_rows

            # Merge (deduplicate by content)
            seen_content: set[str] = set()
            for row in list(sum_rows) + list(ext_rows):
                content = row[1] if isinstance(row, tuple) else row["content"]
                node_type = row[0] if isinstance(row, tuple) else row["node_type"]
                if content not in seen_content and char_budget > 0:
                    seen_content.add(content)
                    chunk = content[: char_budget]
                    parts.append(f"[Nexus/{key} {node_type}]\n{chunk}")
                    char_budget -= len(chunk)

            # ── TIER 3: Semantic fallback (if still sparse) ──────────────
            if len(seen_content) < 2 and char_budget > 1000:
                try:
                    # Try semantic search first (embedding similarity)
                    sem_results = await self.aibrarian.search(
                        key, query, "semantic", limit=3
                    )
                    # Fall back to keyword chunks if semantic returns nothing
                    if not sem_results:
                        sem_results = await self.aibrarian.search(
                            key, query, "keyword", limit=3
                        )
                    for r in sem_results:
                        content = r.get("snippet") or r.get("content", "")
                        title = r.get("title") or r.get("filename", "")
                        if content and content not in seen_content and char_budget > 0:
                            seen_content.add(content)
                            chunk = content[: char_budget]
                            parts.append(
                                f"[Nexus/{key} chunk: {title}]\n{chunk}"
                            )
                            char_budget -= len(chunk)
                except Exception as e:
                    logger.warning(f"[PHASE2] Semantic fallback for {key}: {e}")
```

### New helper function: `_expand_and_search_extractions()`

Add this as a module-level function in `engine.py` (not a method — it doesn't need `self`), near the top of the file or right before `_get_collection_context`:

```python
import re as _re

# Stopwords for query expansion (lightweight, no NLTK)
_EXPANSION_STOPWORDS = frozenset(
    "the a an is are was were in on at to for of and or but with by from "
    "that this it as be has have had not no do does did will would can could "
    "may might about what how why when where who which tell me please "
    "your my our you they she he i we".split()
)


def _expand_and_search_extractions(conn, query: str) -> list:
    """
    Tier 2: Extract content words from query, search extractions
    with progressively broader FTS5 queries.
    
    Strategy:
    1. Extract meaningful words (remove stopwords)
    2. Try OR-joined query (any word matches)
    3. Try individual high-value words
    
    Returns list of extraction rows (same shape as Tier 1 results).
    """
    from luna.substrate.aibrarian_engine import AiBrarianEngine

    # Extract content words
    words = _re.findall(r"[a-zA-Z]{3,}", query.lower())
    content_words = [w for w in words if w not in _EXPANSION_STOPWORDS]
    
    if not content_words:
        return []
    
    results = []
    seen_ids: set[str] = set()
    
    # Strategy A: OR-joined query (any content word matches)
    or_query = " OR ".join(content_words)
    try:
        sanitized = AiBrarianEngine._sanitize_fts_query(or_query)
        rows = conn.conn.execute(
            "SELECT e.node_type, e.content, e.confidence "
            "FROM extractions_fts "
            "JOIN extractions e ON extractions_fts.rowid = e.rowid "
            "WHERE extractions_fts MATCH ? "
            "ORDER BY e.confidence DESC "
            "LIMIT 5",
            (sanitized,),
        ).fetchall()
        for row in rows:
            content = row[1] if isinstance(row, tuple) else row["content"]
            cid = content[:80]
            if cid not in seen_ids:
                seen_ids.add(cid)
                results.append(row)
    except Exception:
        pass
    
    if len(results) >= 3:
        return results
    
    # Strategy B: Individual content words (most specific first)
    # Sort by length descending — longer words are more specific
    for word in sorted(content_words, key=len, reverse=True):
        if len(results) >= 5:
            break
        try:
            sanitized = AiBrarianEngine._sanitize_fts_query(word)
            rows = conn.conn.execute(
                "SELECT e.node_type, e.content, e.confidence "
                "FROM extractions_fts "
                "JOIN extractions e ON extractions_fts.rowid = e.rowid "
                "WHERE extractions_fts MATCH ? "
                "ORDER BY e.confidence DESC "
                "LIMIT 2",
                (sanitized,),
            ).fetchall()
            for row in rows:
                content = row[1] if isinstance(row, tuple) else row["content"]
                cid = content[:80]
                if cid not in seen_ids:
                    seen_ids.add(cid)
                    results.append(row)
        except Exception:
            continue
    
    return results
```

---

## HOW THE CASCADE WORKS

### Example 1: "What did Lansing discover?"

```
TIER 1: FTS5 MATCH "Lansing discover"
  → 0 results (no extraction contains both words adjacent)

TIER 2: Extract content words → ["lansing", "discover"]
  → OR query: "lansing OR discover"
  → 3 results: DOCUMENT_SUMMARY (mentions Lansing), 2 CLAIMs about his research
  → SUFFICIENT — skip Tier 3

LLM sees: Document summary + specific claims about Lansing's findings
Luna answers confidently.
```

### Example 2: "How did outside experts mess things up?"

```
TIER 1: FTS5 MATCH "outside experts mess things"
  → 0 results

TIER 2: Extract content words → ["outside", "experts", "mess", "things"]
  → OR query: "outside OR experts OR mess OR things"
  → 1 result: a CLAIM mentioning "outside experts" or "development experts"
  → Still sparse (< 2 after dedup with summary)

TIER 3: Semantic search — embed "How did outside experts mess things up?"
  → Cosine similarity finds chunks about Green Revolution disruption,
    temple system being dismantled by development planners
  → 2-3 semantically relevant chunks returned

LLM sees: 1 extraction + 2-3 relevant chunks about the Green Revolution failure
Luna answers with specific examples from the book.
```

### Example 3: "What is chapter 2 about?" (already works — no change)

```
TIER 1: FTS5 MATCH "chapter 2"
  → 3 results (section_label matches via chunks_fts, extractions tagged with section metadata)
  → SUFFICIENT — skip Tier 2 and 3

No change in behavior for queries that already work.
```

### Example 4: "Tell me about the book" (vague but valid)

```
TIER 1: FTS5 MATCH "tell book"
  → 0 results (after stopword sanitization, barely anything left)
  → But DOCUMENT_SUMMARY is always included regardless

TIER 2: Content words → ["tell", "book"] → both too generic
  → OR query returns scattered results
  → But DOCUMENT_SUMMARY already provides the answer

LLM sees: DOCUMENT_SUMMARY (always injected)
Luna answers from the summary — same as today but more robust.
```

---

## WHY THREE TIERS INSTEAD OF JUST SEMANTIC

Semantic search (embedding similarity) is powerful but has costs:

1. **Latency**: Embedding the query takes ~50ms (sentence-transformers on M1). FTS5 is <1ms.
2. **Precision**: FTS5 returns exact keyword matches — when they hit, they're more precise than embedding similarity.
3. **Embedding quality**: The local MiniLM model produces decent but not great embeddings. FTS5 on well-extracted claims is often more reliable.

The cascade gives you the best of both:
- Tier 1: Fast + precise (when keywords align)
- Tier 2: Fast + broader (when exact keywords miss but content words overlap)
- Tier 3: Slow + conceptual (when the user's phrasing doesn't match the book's vocabulary at all)

Most queries should resolve at Tier 1 or Tier 2. Tier 3 only fires for genuinely difficult queries where the user's language diverges significantly from the source text.

---

## INTERACTION WITH STEP 2 (MULTI-QUERY DECOMPOSITION)

The retry loop runs INSIDE `_get_collection_context()`, which is called by `_get_collection_context_multi()` from Step 2. So each sub-query gets its own retry cascade. This is the correct behavior:

```
"Compare chapter 2 to chapter 6"
  → Step 2 decomposes: ["chapter 2", "chapter 6"]
  → _get_collection_context("chapter 2")
    → Tier 1: FTS5 hits section-labeled extractions → DONE
  → _get_collection_context("chapter 6")
    → Tier 1: FTS5 hits Green Revolution extractions → DONE
```

```
"How does Lansing's argument compare to modern development theory?"
  → Step 2 decomposes: ["Lansing argument", "modern development theory"]
  → _get_collection_context("Lansing argument")
    → Tier 1: 1 result → Tier 2: OR "lansing OR argument" → 3 results → DONE
  → _get_collection_context("modern development theory")
    → Tier 1: 0 → Tier 2: OR "modern OR development OR theory" → 2 results → DONE
```

---

## DO NOT

- Do NOT modify the AiBrarianEngine search methods — they work fine as-is
- Do NOT add new database tables or schema changes — this is pure query logic
- Do NOT remove the existing Tier 1 search — it's fast and precise when it hits
- Do NOT make Tier 3 (semantic) fire on every query — it adds ~50ms latency
- Do NOT add external NLP libraries for query expansion — the stopword + regex approach is sufficient
- Do NOT modify the subtask runner — query expansion is retrieval-side, not planning-side
- Do NOT expand against Memory Matrix — this is Nexus-only. Memory Matrix has its own retrieval path.

---

## VERIFICATION

After implementation:

```bash
# Restart backend
pkill -f "scripts/run.py"
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
PYTHONPATH=src .venv/bin/python scripts/run.py --server --host 0.0.0.0 --port 8000 &
sleep 15
```

Test in Luna UI with queries that CURRENTLY fail:

1. **"What did Lansing discover?"**
   → Logs should show: Tier 1 sparse → Tier 2 OR expansion → results found
   → Luna answers about his research findings

2. **"How did outside experts mess things up?"**
   → Logs should show cascade firing
   → Luna answers about the Green Revolution disruption

3. **"Tell me about the water management system"**
   → "management system" won't FTS5 match, but "water" will in Tier 2
   → Luna gets irrigation/subak extractions

4. **"What is chapter 2 about?"** (should still work as before)
   → Tier 1 should return results
   → Logs should NOT show Tier 2 or 3 firing

5. Check backend logs for cascade visibility:
   ```
   [PHASE2] Collection recall: 4 fragments, 3200 chars, collections=['research_library']
   ```

---

## ESTIMATED SCOPE

- ~60 lines new code (`_expand_and_search_extractions` function)
- ~20 lines modified in `_get_collection_context()` (add Tier 2 call, change Tier 3 to semantic-first)
- Zero new dependencies
- Zero schema changes
- Zero frontend changes
- Zero changes to AiBrarianEngine
