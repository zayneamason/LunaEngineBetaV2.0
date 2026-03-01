# AiBrarian Embedding Pipeline — Diagnostic Handoff

**Date:** 2026-02-27
**From:** Luna diagnostic session (Ben + Luna + CC)
**To:** Claude Code
**Priority:** High — blocks semantic search for entire dataroom

---

## Problem

The AiBrarian dataroom collection has **zero embeddings**. Semantic search returns nothing. Hybrid search silently degrades to keyword-only.

- 18 documents ingested
- 27 chunks created (chunking works fine)
- **0 rows in `chunk_embeddings` table**
- sqlite-vec IS loaded (virtual table exists and schema is correct)
- FTS5 keyword search works perfectly

## Root Cause (Suspected)

The embedding generator in `_EmbeddingGenerator._load_model()` catches `ImportError` silently. If `sentence-transformers` is not installed, `_model_instance` stays `None`, and `generate_batch()` returns `[None] * len(texts)` — meaning `_embed_chunks()` skips every insert without error.

## Files to Inspect

| File | What to check |
|------|---------------|
| `src/luna/substrate/aibrarian_engine.py` | `_EmbeddingGenerator` class (~line 280-310), `_embed_chunks()` method, `ingest()` pipeline |
| `src/luna/substrate/embeddings.py` | Existing embedding patterns (Memory Matrix uses this — does IT work?) |
| `src/luna/substrate/local_embeddings.py` | May have a working local embedding impl already |
| `config/aibrarian_registry.yaml` | Confirm `embedding_model` and `embedding_dim` settings |
| `data/aibrarian/dataroom.db` | The SQLite DB — verify `chunk_embeddings` table schema |

## Diagnostic Steps

```bash
# 1. Check if sentence-transformers is installed
pip show sentence-transformers

# 2. Check if the model can load
python3 -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('all-MiniLM-L6-v2'); print('OK:', m.encode('test').shape)"

# 3. Check if sqlite-vec is installed and working
python3 -c "import sqlite_vec; print('sqlite-vec path:', sqlite_vec.loadable_path())"

# 4. Check the DB directly
python3 -c "
import sqlite3
conn = sqlite3.connect('data/aibrarian/dataroom.db')
print('chunks:', conn.execute('SELECT COUNT(*) FROM chunks').fetchone()[0])
print('embeddings:', conn.execute('SELECT COUNT(*) FROM chunk_embeddings').fetchone()[0])
print('tables:', [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()])
"

# 5. Check if Memory Matrix embeddings work (comparison)
python3 -c "
import sqlite3
conn = sqlite3.connect('data/memory_matrix.db')
# Check if MM has embeddings — if yes, the model works but AiBrarian isn't calling it
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()]
print('MM tables:', tables)
"
```

## Fix Path

### If `sentence-transformers` is missing:
```bash
pip install sentence-transformers
```
Then re-ingest the dataroom to generate embeddings.

### If installed but model download failed:
```bash
python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
```
This forces the download. Then re-ingest.

### If both are fine — check the wiring:
The `_embed_chunks` method requires `conn._vec_loaded == True`. Verify that sqlite-vec loaded successfully during `AiBrarianConnection.connect()`. The try/except there may be swallowing an error.

### Re-ingestion after fix:
```python
# The ingest path does INSERT OR REPLACE, so re-ingesting is safe
# But chunks won't be re-embedded unless you either:
# a) Delete and re-ingest the collection
# b) Add a standalone embed-existing-chunks function

# Quickest path — nuke and re-ingest:
# 1. Find the source directory from the registry yaml
# 2. Delete the DB (or just the chunk_embeddings rows)
# 3. Re-run ingest_directory
```

## Secondary Issue: Chunk Sizing

Not broken, just worth reviewing. Current defaults:
- `chunk_size: 500` words
- `chunk_overlap: 50` words

This produces reasonable results for the current corpus. The Tarcila Quest doc (2310 words) got 6 chunks, Strategic Plan (1632 words) got 4. Index pages under 500 words are single chunks, which is correct.

**No action needed** unless you want finer granularity for search — could drop to 300/30 for more targeted retrieval.

## Also Worth Checking

- `local_embeddings.py` exists alongside `embeddings.py` — is there a working local embedding implementation that AiBrarian should be using instead of its own `_EmbeddingGenerator`? Potential code duplication / missed integration.
- The `extract_on_ingest` config flag exists but `ingest()` never calls `extract()` — the extraction TODO comment at the bottom references wiring to the Scribe actor. Not blocking, just noting.

## Expected Outcome

After fix + re-ingest:
- `chunk_embeddings` should have ~45 rows (27 chunks + 18 doc-level averages)
- `aibrarian_search(collection, query, search_type="semantic")` should return results
- Hybrid search should fuse keyword + semantic via RRF as designed
