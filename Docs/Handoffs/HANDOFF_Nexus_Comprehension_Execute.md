# HANDOFF: Nexus Document Comprehension — Execution Complete

**Date:** 2026-03-22
**Status:** COMPLETED
**Verified results:** 196 chunks, 262 extractions (2 DOCUMENT_SUMMARY + 22 SECTION_SUMMARY + 238 CLAIM), 297 entities. FTS5 search on extractions confirmed working. Recall pipeline live.

---

## WHAT WAS DONE

Four code fixes were deployed and executed to make Luna comprehend documents in the Nexus:

| Fix | File | What |
|-----|------|------|
| A | `src/luna/substrate/aibrarian_engine.py` | Replaced `extract()` stub with real Haiku comprehension. Added `DOCUMENT_EXTRACTION_PROMPT` constant. Batches chunks in groups of 5, calls Anthropic API, stores summaries + claims + entities. |
| B | `src/luna/substrate/aibrarian_schema.py` | Added `extractions_fts` FTS5 virtual table + 3 sync triggers (INSERT/DELETE/UPDATE) to `STANDARD_SCHEMA`. |
| C | `src/luna/engine.py` | Replaced aperture-driven path in `_get_collection_context()` — searches extractions first (comprehension layer), falls back to raw keyword chunks when extractions are sparse. |
| D | `src/luna/substrate/aibrarian_engine.py` | RRF fallback + `_fts_search` full chunk_text — both were already applied before this session. |

### Execution steps completed:
1. Killed backend (PIDs on :8000)
2. Deleted corrupt `data/local/research_library.db` (triple-ingested from prior sessions)
3. Restarted backend with `.venv/bin/python` — DB auto-recreated with new schema including `extractions_fts`
4. Re-ingested Priests and Programmers PDF via `/api/nexus/ingest`
5. Extraction ran ~40 Haiku batches over ~4 minutes
6. Verified: 262 extractions, 297 entities, FTS5 search returns structured comprehension
7. Relaunched frontend on :5173

### Verified results:
```
Documents:   2 (PDF split into two doc_ids)
Chunks:      196
Extractions: 262
  - DOCUMENT_SUMMARY: 2
  - SECTION_SUMMARY:  22
  - CLAIM:            238
Entities:    297
```

DOCUMENT_SUMMARY correctly describes Lansing's research on Balinese water temples, the subak system, the Green Revolution disruption, and the computer modeling methodology.

FTS5 search verified for "Green Revolution" and "Lansing" — returns relevant summaries and claims.

---

## HOW IT WORKS

### Ingest-time (once per document, ~$0.14 for a book):
1. PDF is chunked into ~500-word segments
2. Chunks are batched in groups of 5
3. Each batch is sent to Haiku with `DOCUMENT_EXTRACTION_PROMPT`
4. Haiku returns JSON: `{summary, claims[], entities[]}`
5. Results are stored in `extractions` and `entities` tables
6. FTS5 triggers auto-populate `extractions_fts`

### Query-time (~500-1000 tokens of context):
1. `_get_collection_context()` searches `extractions_fts` via FTS5 MATCH
2. Always includes `DOCUMENT_SUMMARY` (answers "what is this about?")
3. If extractions are sparse (<2 hits), falls back to raw chunk keyword search
4. Results are assembled into context with 6000-char budget

### What Luna can now do:
- "What is Priests and Programmers about?" → answers from DOCUMENT_SUMMARY
- "What happened when the Green Revolution came to Bali?" → finds CLAIM extractions
- "Who is Lansing?" → finds ENTITY extractions
- "How does the subak irrigation system work?" → finds SECTION_SUMMARY + CLAIMs

---

## RE-INGEST INSTRUCTIONS (for future documents)

If you need to ingest a new document or re-ingest an existing one:

### Quick path (backend already running with new code):
```bash
curl -s -X POST http://localhost:8000/api/nexus/ingest \
  -H "Content-Type: application/json" \
  -d '{"collection": "research_library", "file_path": "/absolute/path/to/document.pdf"}' \
  --max-time 600
```

### If extraction doesn't run (extractions = 0 after ingest):
1. Check `ANTHROPIC_API_KEY` is in the environment
2. Check backend logs for "Extraction batch" vs "Extraction stub"
3. To force re-extraction on existing doc: delete the DB and re-ingest, or call extract with `force=True`

### Full restart path (if backend needs new code):
```bash
# Kill
pkill -f "scripts/run.py"
sleep 2

# Optional: delete DB for clean slate
rm -f data/local/research_library.db

# Start
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
PYTHONPATH=src .venv/bin/python scripts/run.py --server --host 0.0.0.0 --port 8000 &
sleep 15

# Ingest
curl -s -X POST http://localhost:8000/api/nexus/ingest \
  -H "Content-Type: application/json" \
  -d '{"collection": "research_library", "file_path": "..."}' \
  --max-time 600
```

### Verification:
```bash
sqlite3 data/local/research_library.db "
  SELECT COUNT(*) as docs FROM documents;
  SELECT COUNT(*) as chunks FROM chunks;
  SELECT node_type, COUNT(*) FROM extractions GROUP BY node_type;
  SELECT COUNT(*) as entities FROM entities;
"
```

---

## DO NOT

- **DO NOT use system python3.** Always `.venv/bin/python`.
- **DO NOT skip ANTHROPIC_API_KEY.** Extraction silently returns empty without it.
- **DO NOT re-ingest without force** if extractions already exist — the method skips if count > 0.
- **DO NOT send document extractions to the Memory Matrix.** Document understanding stays in the collection DB.
- **DO NOT modify the Scribe actor.** Document extraction is separate from conversation extraction.

## ENVIRONMENT

```
Project root: /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
Venv python:  .venv/bin/python
Document:     Docs/PRIESTS AND PROGRAMMERS_Lansing.pdf
Collection:   research_library
Registry:     config/aibrarian_registry.yaml
Backend:      scripts/run.py --server --host 0.0.0.0 --port 8000
Frontend:     frontend/ (npm run dev → :5173)
API key:      ANTHROPIC_API_KEY (must be in environment)
```
