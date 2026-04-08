# HANDOFF: Search Extractions, Not Chunks

**Date:** 2026-04-01
**Author:** Ahab + Claude (session diagnosis)
**Priority:** CRITICAL — This is the single highest-impact fix for document comprehension
**Scope:** `aibrarian_engine.py` search method only. One file. One method. One concept.

---

## THE PROBLEM

Luna has 456 pre-computed understanding artifacts for Priests and Programmers:
- 416 CLAIMs (atomic factoids extracted at ingest time)
- 38 SECTION_SUMMARYs
- 1 DOCUMENT_SUMMARY (1,800 chars — the book's thesis)
- 1 TABLE_OF_CONTENTS

These live in the `extractions` table and are **already FTS5 indexed** via `extractions_fts`.

**The retrieval pipeline has never searched them. Not once. Zero references to `extractions_fts` in the entire codebase.**

When someone asks "what is the central argument of this book?", Luna searches `chunks_fts` — raw text fragments — and matches on the words "central," "argument," and "book." She gets a Marx discussion from a foreword.
Meanwhile, a 1,800-character document summary explaining the entire thesis sits in `extractions_fts`, invisible.

This is why 43 previous handoffs tuning chunk retrieval never solved comprehension. You can't comprehend from confetti.

---

## THE FIX

### Concept: Two-Phase Retrieval

1. **Phase 1 — Search understanding** (`extractions_fts`): Find claims, summaries, and the document thesis that match the query. This tells Luna WHAT is relevant.
2. **Phase 2 — Search evidence** (`chunks_fts`): Find raw text chunks that ground the understanding with specific quotes and details.

The final context sent to the LLM combines both: comprehension artifacts first, supporting chunks second.

### Implementation

**File:** `src/luna/substrate/aibrarian_engine.py`

**Method:** `search()` (line ~816)

#### Step 1: Add `_extraction_search()` method

Add a new private method near `_fts_search()`:

```python
def _extraction_search(
    self, conn: AiBrarianConnection, query: str, limit: int
) -> list[dict]:
    """Search the extractions FTS index for comprehension artifacts."""
    try:
        fts_query = self._sanitize_fts_query(query)
        cursor = conn.conn.execute(
            """
            SELECT
                e.id, e.doc_id, e.node_type, e.content,
                e.confidence, e.metadata, rank
            FROM extractions_fts
            JOIN extractions e ON extractions_fts.rowid = e.rowid
            WHERE extractions_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (fts_query, limit),
        )
        results = []
        for row in cursor.fetchall():
            results.append({
                "doc_id": row["doc_id"],
                "title": "",
                "filename": "",
                "category": row["node_type"],
                "snippet": row["content"],
                "score": abs(row["rank"]),
                "search_type": f"extraction:{row['node_type'].lower()}",
                "confidence": row["confidence"],
                "extraction_id": row["id"],
            })
        # Enrich with document title
        if results:
            doc_ids = set(r["doc_id"] for r in results)
            for did in doc_ids:
                doc_row = conn.conn.execute(
                    "SELECT title, filename FROM documents WHERE id = ?", (did,)
                ).fetchone()
                if doc_row:
                    for r in results:
                        if r["doc_id"] == did:
                            r["title"] = doc_row["title"]
                            r["filename"] = doc_row["filename"]
        return results
    except sqlite3.OperationalError as e:
        logger.warning("Extraction search failed for '%s': %s", query, e)
        return []
```

#### Step 2: Modify `search()` to combine both layers

```python
async def search(self, collection, query, search_type="hybrid", limit=20):
    conn = self._get_conn(collection)
    # Phase 1: Search understanding layer (extractions)
    extraction_results = self._extraction_search(conn, query, limit=limit // 2)
    # Phase 2: Search evidence layer (chunks)
    chunk_limit = limit - len(extraction_results)
    if search_type == "keyword":
        chunk_results = self._fts_search(conn, query, chunk_limit)
    elif search_type == "semantic":
        chunk_results = await self._vec_search(conn, query, chunk_limit)
    else:
        kw = self._fts_search(conn, query, chunk_limit)
        sem = await self._vec_search(conn, query, chunk_limit)
        sem_alive = [r for r in sem if r.get("score", 0) > 0.01]
        chunk_results = kw if not sem_alive else self._rrf_fuse(kw, sem_alive, chunk_limit)
    # Combine: understanding first, evidence second
    results = extraction_results + chunk_results
    await self._bump_collection_access(collection)
    return results
```

#### Step 3: Format extraction results differently in context

In `_get_collection_context()` in `engine.py`, wrap extraction results with comprehension tags:

```
<comprehension type="CLAIM" confidence="0.85">
Bali's water temples functioned as sophisticated coordination mechanisms...
</comprehension>

<evidence source="Chapter 4">
The subak system consists of approximately one hundred farmers who obtain...
</evidence>
```

---

## VERIFICATION

After implementing, run these test queries against priests_and_programmers:

1. **"What is the central argument of this book?"** → Should return DOCUMENT_SUMMARY + supporting claims
2. **"How did the Green Revolution affect Balinese agriculture?"** → Should return CLAIM extractions about ecological degradation + chunks
3. **"What role did water temples play?"** → Should return CLAIM about temples as coordination mechanisms + evidence

Run via MCP: `aibrarian_search(collection="priests_and_programmers", query="...", search_type="hybrid")`
Check that results include entries where `search_type` starts with `extraction:`.

---

## DO NOT

- **DO NOT** refactor the search method signature or add new parameters
- **DO NOT** change the `_fts_search()` or `_vec_search()` methods
- **DO NOT** modify the extractions table schema
- **DO NOT** change how extractions are generated at ingest time
- **DO NOT** add any new tables, columns, or indexes
- **DO NOT** touch the `/stream` or `/message` endpoints
- **DO NOT** rename anything related to aibrarian → nexus in this handoff
- **DO NOT** add semantic search to extractions yet (FTS5 keyword is sufficient — extraction content is already clean concise language)

---

## WHY THIS IS DIFFERENT FROM THE LAST 43 HANDOFFS

Every previous handoff tried to make chunk retrieval better. This one adds a fundamentally different retrieval layer: search pre-computed understanding, not raw text.

Validated by RAPTOR (Stanford ICLR 2024), GraphRAG (Microsoft 2024), Dense X Retrieval (EMNLP 2024). Luna already has the extraction layer these papers propose. This handoff just points the retrieval at it.

---

## CONTEXT FOR CC

- `extractions` columns: `id`, `doc_id`, `chunk_index`, `node_type`, `content`, `confidence`, `metadata`, `created_at`
- `extractions_fts` is FTS5 virtual table, already populated (456 rows for P&P)
- `_sanitize_fts_query()` handles stop word removal + OR joining — reuse it
- `search()` method is at ~line 816 of `aibrarian_engine.py`
- `_fts_search()` (chunk search) is at ~line 890
- `AiBrarianConnection` is the connection wrapper with `.conn` for raw sqlite3
- P&P collection key: `priests_and_programmers`
- Verification: `aibrarian_search` MCP tool calls `search()` directly
