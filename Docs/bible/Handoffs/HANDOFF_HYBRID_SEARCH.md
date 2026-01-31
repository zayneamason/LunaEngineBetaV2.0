# HANDOFF: Hybrid Search (FTS5 + Local Embeddings)

**Priority:** HIGH  
**Estimated Time:** 2-3 hours  
**Dependencies:** sentence-transformers (already installed), sqlite-vec (already installed)

---

## Goal

Implement dual search for the Memory Matrix:
1. **FTS5** — Fast tokenized keyword search with stemming (free, instant)
2. **Local Embeddings** — Semantic similarity using MiniLM (free, ~50ms per query)

Combined, this gives Luna the ability to find "who helps with architecture" even when the exact word "architecture" isn't present.

---

## Key Components

### FTS5 (Full-Text Search)
- Porter stemmer: "collaborate" matches "collaborator", "collaboration"
- Phrase search, boolean operators, prefix matching
- Built into SQLite, no extension needed
- Triggers keep it synced with memory_nodes

### Local Embeddings (MiniLM)
- Model: `all-MiniLM-L6-v2` (already installed via sentence-transformers)
- 384 dimensions, ~50ms per embedding on CPU
- No API costs
- sqlite-vec handles vector storage and similarity search

### Hybrid Search
- Runs FTS5 and semantic search in parallel
- Uses Reciprocal Rank Fusion (RRF) to merge results
- Configurable weights (default: 40% keyword, 60% semantic)

---

## Backfill Stats
- 22K nodes × 50ms = ~18 minutes one-time backfill
- After that, embeddings generated automatically on add_node

---

## Files to Create/Modify

| File | Action |
|------|--------|
| `src/luna/substrate/schema.sql` | Add FTS5 table + triggers |
| `src/luna/substrate/local_embeddings.py` | New: MiniLM wrapper |
| `src/luna/substrate/embeddings.py` | Update: use local model |
| `src/luna/substrate/memory.py` | Add: fts5_search, semantic_search, hybrid_search |
| `src/luna/api/server.py` | Update: /memory/search endpoint |
| `scripts/populate_fts5.py` | New: backfill FTS5 index |
| `scripts/backfill_embeddings.py` | New: generate embeddings for existing nodes |

---

See full implementation details in the main handoff file.
