# HANDOFF: Restart Backend & Re-Ingest Research Library

## CONTEXT

Code changes from the "Wire Document Comprehension into the Nexus" handoff are
already deployed to disk. Four fixes are live in the source files:

- Fix A: `extract()` in `aibrarian_engine.py` — real Haiku comprehension (was stub)
- Fix B: `extractions_fts` FTS5 table in `aibrarian_schema.py`
- Fix C: `_get_collection_context()` in `engine.py` — aperture-driven recall
- Fix D: RRF fallback fix in `aibrarian_engine.py`

**Status (2026-03-22):** All four fixes deployed, backend restarted with .venv/bin/python,
research_library.db recreated with `extractions_fts` schema, Priests and Programmers
re-ingested with full Haiku extraction (262 extractions, 297 entities). Recall pipeline
verified — FTS5 searches on extractions return structured comprehension.

**Original problem:** The backend was running under system Python 3.14 (not .venv/bin/python)
and was started BEFORE the code changes deployed. The running process had old code
in memory. The research_library.db was created before Fix B so it was missing the
`extractions_fts` table. The document was ingested before Fix A so extractions = 0.

## WHAT TO DO

Execute these steps in order. Each step has a verification gate.

### Step 1: Kill all Luna processes

```bash
pkill -f "scripts/run.py"
pkill -f "luna_mcp.api"
sleep 2
# Verify: ps aux | grep -E "run.py|luna_mcp" | grep -v grep
# Should return nothing
```

### Step 2: Delete the research_library database

```bash
rm -f /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/data/local/research_library.db
# The backend will recreate it on startup with the updated schema (create_if_missing: true)
```

### Step 3: Restart backend with .venv/bin/python

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
.venv/bin/python scripts/run.py --server --host 0.0.0.0 --port 8000 &
```

**CRITICAL:** Verify it started with the venv python. The process listing will show
`/opt/homebrew/Cellar/python@3.14/...` because the venv was created FROM system Python.
That's expected — what matters is that the venv site-packages are on the path.

Verify packages are available:
```bash
.venv/bin/python -c "import sentence_transformers; import sqlite_vec; import anthropic; print('ALL PACKAGES OK')"
```

Wait for backend to be ready:
```bash
sleep 10
curl -s http://localhost:8000/api/settings | head -c 100
# Should return JSON, not an error
```

### Step 4: Verify the new schema

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('data/local/research_library.db')
tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' ORDER BY name\").fetchall()]
print('Tables:', tables)
has_ext_fts = 'extractions_fts' in str(tables)
print('extractions_fts exists:', has_ext_fts)
if not has_ext_fts:
    print('ERROR: extractions_fts table missing! Fix B did not apply to schema.')
    print('Check aibrarian_schema.py STANDARD_SCHEMA for the extractions_fts block.')
conn.close()
"
```

**If `extractions_fts` is missing:** The schema change in `aibrarian_schema.py` was
not included or the DB was created before it was saved. Check the file:
```bash
grep -c "extractions_fts" /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/substrate/aibrarian_schema.py
# Should return 5+ (the CREATE TABLE + triggers)
# If 0, Fix B was not applied — add it manually
```

If the schema file has it but the DB doesn't, the DB was created before the file was
saved. Delete the DB and restart the backend again:
```bash
rm -f data/local/research_library.db
pkill -f "scripts/run.py"
sleep 2
.venv/bin/python scripts/run.py --server --host 0.0.0.0 --port 8000 &
sleep 10
```

### Step 5: Re-ingest the document

```bash
curl -s -X POST http://localhost:8000/api/nexus/ingest \
  -H "Content-Type: application/json" \
  -d '{"collection": "research_library", "file_path": "/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Docs/PRIESTS AND PROGRAMMERS_Lansing.pdf"}' \
  --max-time 300
```

**This will take 2-5 minutes.** The extraction step calls Haiku for each batch of
5 chunks (~40 API calls total). Watch the backend logs for progress:
```
Extraction batch 1/40: DOCUMENT_SUMMARY + N claims + N entities
Extraction batch 2/40: SECTION_SUMMARY + N claims + N entities
...
Document extraction complete: <doc_id> → N extractions across 40 batches
```

If extraction doesn't happen (logs just show "Ingested ... → doc_id" with no
extraction batches), check:
1. Is `ANTHROPIC_API_KEY` set in the environment?
2. Does the extract() method in aibrarian_engine.py contain "Run document
   comprehension extraction via Haiku" or "Extraction stub"?

### Step 6: Verify extraction results

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('data/local/research_library.db')

# Check document
docs = conn.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
chunks = conn.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]
extractions = conn.execute('SELECT COUNT(*) FROM extractions').fetchone()[0]
entities = conn.execute('SELECT COUNT(*) FROM entities').fetchone()[0]
print(f'Documents: {docs}')
print(f'Chunks: {chunks}')
print(f'Extractions: {extractions}')
print(f'Entities: {entities}')

# Check for document summary
summary = conn.execute(
    \"SELECT content FROM extractions WHERE node_type = 'DOCUMENT_SUMMARY' LIMIT 1\"
).fetchone()
if summary:
    print(f'\\nDOCUMENT_SUMMARY (first 300 chars):\\n{summary[0][:300]}')
else:
    print('\\nERROR: No DOCUMENT_SUMMARY found!')

# Check extraction types
types = conn.execute(
    'SELECT node_type, COUNT(*) as cnt FROM extractions GROUP BY node_type ORDER BY cnt DESC'
).fetchall()
print(f'\\nExtraction types: {dict(types)}')

conn.close()
"
```

**Expected results (verified 2026-03-22):**
- Documents: 2 (PDF split into two doc_ids)
- Chunks: 196
- Extractions: 262 (2 DOCUMENT_SUMMARY + 22 SECTION_SUMMARY + 238 CLAIM)
- Entities: 297 (people, places, systems, concepts)
- DOCUMENT_SUMMARY contains a real description of Lansing's research on Balinese
  water temples, the subak system, and Green Revolution disruption

### Step 7: Verify recall pipeline

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
.venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('data/local/research_library.db')

# Test keyword search on extractions
try:
    results = conn.execute(
        \"SELECT node_type, substr(content, 1, 100) FROM extractions_fts \"
        \"JOIN extractions e ON extractions_fts.rowid = e.rowid \"
        \"WHERE extractions_fts MATCH 'water temple irrigation' \"
        \"LIMIT 3\"
    ).fetchall()
    print(f'Extraction search results: {len(results)}')
    for r in results:
        print(f'  [{r[0]}] {r[1]}...')
except Exception as ex:
    print(f'ERROR searching extractions_fts: {ex}')

conn.close()
"
```

### Step 8: Test in UI

Open the Luna UI and ask:
- "What is Priests and Programmers about?"
- "What happened when the Green Revolution came to Bali?"
- "Who is Lansing?"

Luna should answer from extracted comprehension, not just keyword fragments.

Check backend logs for: `[PHASE2] Collection recall: N fragments, NNNN chars`

## DO NOT

- DO NOT use system python3 directly. Always use `.venv/bin/python`.
- DO NOT skip the schema verification (Step 4). If `extractions_fts` is missing,
  the recall pipeline silently fails.
- DO NOT re-ingest without deleting the old DB first. The old DB lacks the FTS5
  table and has stale data.
- DO NOT modify any source files. All code changes are already on disk.
- DO NOT skip waiting for extraction to complete. It takes 2-5 minutes and makes
  ~40 Haiku API calls. If you test before it finishes, extractions will be incomplete.

## ENVIRONMENT

- Project root: `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root`
- Venv: `.venv/bin/python` (Python 3.14 with sentence-transformers, sqlite-vec, anthropic)
- Document: `Docs/PRIESTS AND PROGRAMMERS_Lansing.pdf`
- Collection: `research_library` (config in `config/aibrarian_registry.yaml`)
- Backend: `scripts/run.py --server --host 0.0.0.0 --port 8000`
- API key: `ANTHROPIC_API_KEY` must be in environment for extraction to work
