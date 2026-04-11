# CC INSTRUCTIONS: Fix _vec_search Section Resolution

## Priority: HIGH — Blocks semantic search in Hai Dai demo build

## Context

The write side is fixed (your 3 commits). Cartridge registration now writes 550 rows to `chunk_embeddings_fallback`. But the read side can't resolve them.

The `.lun` file's embeddings are keyed to `:section:N` IDs (549 of them) plus 1 bare `doc_id` centroid. `_vec_search` in `aibrarian_engine.py` only handles two ID formats:

- `:chunk:` → joins `chunks` table (line ~1026 fallback, ~1070 vec0)
- bare `doc_id` → queries `documents` table

When it sees `:section:42`, it falls into the `else` branch, tries `WHERE d.id = ':section:42'` on the documents table, gets `None`, skips it. So top-K is empty even though the data is right there.

## What To Do

Add an `elif ":section:" in chunk_id:` branch to BOTH the fallback path (around line 1026) AND the vec0 path (around line 1070). Same pattern in both places.

### The change (~15 lines per branch):

```python
elif ":section:" in chunk_id:
    # Section-level embedding from .lun cartridge
    # Parse: "{doc_id}:section:{node_id}"
    parts = chunk_id.split(":section:")
    parent_doc_id = parts[0]
    node_id = parts[1] if len(parts) > 1 else None
    
    # Try extractions table first (where .lun section content lives)
    doc_row = conn.conn.execute(
        "SELECT d.id, d.title, d.filename, d.category, "
        "e.content AS chunk_text "
        "FROM extractions e JOIN documents d ON e.doc_id = d.id "
        "WHERE e.node_id = ? AND e.doc_id = ?",
        (node_id, parent_doc_id),
    ).fetchone()
    
    # Fallback: if no extractions match, use document with truncated text
    if not doc_row:
        doc_row = conn.conn.execute(
            "SELECT d.id, d.title, d.filename, d.category, "
            "substr(d.full_text, 1, 500) AS chunk_text "
            "FROM documents d WHERE d.id = ?",
            (parent_doc_id,),
        ).fetchone()
```

### Where exactly:

**Fallback branch** (around line 1026):
```
if ":chunk:" in chunk_id:
    # existing chunk resolution
elif ":section:" in chunk_id:
    # NEW — add section resolution here
else:
    # existing bare doc_id resolution
```

**Vec0 branch** (around line 1070):
```
if ":chunk:" in chunk_id:
    # existing chunk resolution
elif ":section:" in chunk_id:
    # NEW — add section resolution here (same code)
else:
    # existing bare doc_id resolution
```

## Important: Check the extractions table schema first

Before writing the query, verify what columns the extractions table actually has. The `.lun` file might use `node_id`, `extraction_id`, or something else. Run:

```sql
.schema extractions
```

on the P&P collection db (`collections/priests-and-programmers/priests_and_programmers.db`) to confirm column names. Adapt the query accordingly.

If there's no `extractions` table in the collection db, check if the section text lives somewhere else — maybe `chunks` with a different ID format, or a `sections` table. The key thing: find where the actual text for those 549 `:section:N` embeddings lives and join to it.

## Risk

Low. This is purely additive — the existing `:chunk:` and bare `doc_id` paths are untouched. If the new branch has a bug, `doc_row` is `None`, the existing `if doc_row and doc_row["id"] not in seen_docs:` check skips it, and everything else still works. FTS5 keyword search is completely unaffected.

## Verification

After the fix:

```python
# In the ambassador build or dev instance with P&P loaded:
# Search should return results now
results = await engine.aibrarian.search("priests_and_programmers", "water temples Bali", limit=5)
assert len(results) > 0, "Semantic search should return results"
assert any(r["search_type"] == "semantic" for r in results), "Should have semantic hits"
```

Also test:
- "How do subak coordinate irrigation schedules" → should return relevant P&P sections
- "complex adaptive systems" → should match sections discussing Lansing's argument
- "relationship between religion and agriculture" → should return conceptually related sections even without those exact words

## DO NOT

- Refactor `_vec_search` broadly. Only add the `:section:` branch.
- Touch the write side (your 3 commits are good).
- Change the FTS/keyword search path.
- Add agentic/iterative search (that's a separate architectural discussion for post-demo).

## One commit. Test. Done.
