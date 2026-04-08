# NEXUS COMPREHENSION SYSTEM — Complete Reference

**Supersedes:** `HANDOFF_Nexus_Comprehension_Execute.md` (stale, fabricated numbers)  
**Companion:** `HANDOFF_Nexus_Structural_Extraction.md` (the structural fix, now deployed)  
**Date:** 2026-03-22  
**Status:** LIVE — 456 extractions, structural tagging operational

---

## PART 1: CURRENT STATE

### What's in the database right now

| Metric | Count |
|--------|-------|
| Documents | 1 (Priests & Programmers, ~80K words) |
| Chunks | 196 (500-word overlapping segments) |
| Extractions | 456 (1 DOCUMENT_SUMMARY + 1 TABLE_OF_CONTENTS + 38 SECTION_SUMMARY + 416 CLAIM) |
| Entities | ~120+ |
| Chunks with section_label | 195/196 |

### What changed from the old system

The old system had 109 extractions with zero structural metadata. The new system has:

- **Structure detection**: regex-based heading identification runs at ingest time. Detects chapter boundaries, section headings, appendix markers from pdftotext output.
- **Chunk tagging**: every chunk carries `section_label` (e.g., "CHAPTER TWO") and `section_level` (1=chapter, 2=section).
- **Section-label in FTS5**: `chunks_fts` indexes both `chunk_text` and `section_label`, so queries like "chapter 2" match chunk metadata directly.
- **Structure-aware extraction**: Haiku receives a `DOCUMENT LOCATION` hint telling it which chapter it's looking at. This produced 4x more claims (416 vs 99) because Haiku writes better extractions with structural context.
- **TABLE_OF_CONTENTS extraction**: synthetic extraction generated from detected structure. Free (no API call).
- **Section metadata on extractions**: every CLAIM and SECTION_SUMMARY carries `{"section": "WATER CONTROL"}` in its metadata field.

### Known noise in structure detection

The regex picks up PDF artifacts from pdftotext:
- Letterspaced headings: `C H A P T E R THREE` (pdftotext renders small-caps this way)
- Figure captions in appendix mistaken for section headings
- Endnote section headers ("Chapter Two" in the notes section) creating phantom chapter markers
- The TOC extraction is noisy because it includes all of the above

The main body chunk tagging (chunks 20-165) is clean. The noise is cosmetic and doesn't significantly affect recall quality.

---

## PART 2: HOW LUNA ACTUALLY THINKS WHEN YOU ASK A QUESTION

This is the honest architecture. Two completely different paths depending on where you talk to Luna.

### Path A: Luna UI (localhost:5173) — The Full Pipeline

When you type a message in the Eclissi UI, this happens:

```
User types "What is Chapter 2 about?"
       │
       ▼
1. _handle_user_message()
       │
       ▼
2. _process_message_agentic()
       │
       ├─── PHASE 1: Parallel retrieval
       │    ├── Subtask runner (Qwen): intent classification, entity extraction, query rewriting
       │    ├── Memory Matrix: get_context() — searches conversation memory (25K nodes)
       │    └── _get_collection_context() — THIS IS WHERE NEXUS FIRES
       │         ├── Searches extractions_fts for matching claims/summaries
       │         ├── Always includes DOCUMENT_SUMMARY
       │         └── Falls back to raw chunks if extractions are sparse
       │
       ├─── PHASE 2: Routing (semantic or regex)
       │    └── Classifies as DIRECT (simple) or PLANNED (complex)
       │
       ├─── PHASE 3: Entity hints to Scribe
       │
       └─── PHASE 4: Generation
            ├── _build_system_prompt() assembles:
            │    ├── Luna's identity kernel
            │    ├── Consciousness state hints
            │    ├── Thread context
            │    ├── Directive context
            │    ├── History context (recent conversation)
            │    └── Memory context (Matrix + Nexus combined as free text)
            │
            ├── Sends to Groq (70B model) for generation
            │
            └── Post-generation: GroundingLink evaluates response
```

**The critical detail:** `_get_collection_context()` returns Nexus results as a string that gets concatenated with Memory Matrix results. Both are injected into the system prompt under "Relevant Memory Context." The LLM (Groq 70B) sees both sources but they're mixed together as free text.

### Path B: Claude Desktop via MCP — The Shortcut

When you say "hey Luna" in Claude Desktop:

```
"hey Luna" + question
       │
       ▼
luna_detect_context(message, auto_fetch=True)
       │
       ├── If bare "hey Luna" (no question):
       │    └── Returns personality kernel directly. NO engine pipeline. NO Nexus.
       │
       └── If "hey Luna" + content question:
            ├── Calls MCP API /context/detect
            ├── MCP API proxies to engine /message endpoint
            ├── Engine runs _process_message_agentic() (same as Path A)
            └── Returns Luna's full response with context
```

**The catch:** The initial "hey Luna" greeting bypasses everything. Follow-up messages go through the engine. But Claude Desktop generates its own response using the context returned — the engine's response may or may not be what Claude Desktop shows you.

### Path C: MCP tools directly (smart_fetch, aibrarian_search)

When you call `luna_smart_fetch` or `aibrarian_search` directly from Claude Desktop:

```
aibrarian_search("research_library", "chapter 2 water control")
       │
       ▼
MCP server → AiBrarianEngine.search() → FTS5/hybrid search
       │
       ▼
Returns raw search results (chunks, not extractions)
```

This path queries chunks but NOT the comprehension layer. `aibrarian_search` doesn't search `extractions_fts` — it searches `chunks_fts`. The comprehension layer only fires through `_get_collection_context()` in the engine pipeline.

---

## PART 3: DOES LUNA ACTUALLY LEARN?

### The honest answer: No. She retrieves.

Luna doesn't learn from your questions. She doesn't adapt her understanding based on what you ask. Here's what actually happens:

1. **At ingest time** (once): Haiku reads the document, extracts claims and summaries, stores them in SQLite. This is the "comprehension" step. It happens once and doesn't change.

2. **At query time** (every message): FTS5 keyword search runs against those pre-extracted claims. Whatever matches gets injected into the system prompt. The LLM (Groq 70B) generates a response using that context.

3. **There is no feedback loop.** If Luna gives a bad answer, nothing updates. If you correct her, the correction goes into the Memory Matrix (conversation memory) but doesn't modify the Nexus extractions. The document comprehension is static.

4. **There is no query adaptation.** If you ask "compare chapter 2 to chapter 3," the engine runs ONE FTS5 search with the full query string. It doesn't decompose it into two sub-queries (one for chapter 2, one for chapter 3) and merge the results. The subtask runner could theoretically rewrite the query, but it runs Qwen locally and its query rewriting is basic.

### What "thinking" actually looks like

When Luna says "I don't have enough detail in my memory context to give you a reliable breakdown of Chapter 2 specifically" — that's not Luna being cautious. That's Groq 70B reading the system prompt, seeing no context about Chapter 2, and generating an honest hedge. The LLM is doing what LLMs do: generating text conditioned on context. No context about Chapter 2 = no confident answer about Chapter 2.

When Luna says "from what I have — both in memory and a direct passage from the text itself" and then gives a good answer about the book's thesis — that's the DOCUMENT_SUMMARY extraction being injected. The LLM has the summary in its context window and generates from it.

**Luna doesn't "try to find an answer." The search runs before the LLM sees the question.** The pipeline is: search → inject → generate. Not: generate → realize gap → search more → regenerate.

### Does honesty hinder comprehension?

Yes, in a specific way. Luna's personality kernel says:

> "When you know something, lead with it. Share what you know before asking questions."

But the grounding system's anti-hallucination pressure and Luna's calibrated honesty mean she hedges even when she HAS relevant context. Look at the test results:

- "What is Priests and Programmers about?" → Great answer (DOCUMENT_SUMMARY was injected)
- "What is Chapter 2 about?" → "I don't have enough detail" (before structural fix — no chapter metadata existed)
- "Who are the priests and programmers?" → Answers from general knowledge + Memory Matrix fragments, flags that she doesn't have the document content

The problem isn't honesty. The problem is **the pipeline gives up too early.** One FTS5 search, one shot. If the keywords don't match, the context window is empty, and the LLM generates a hedge. There's no:

- Query expansion ("chapter 2" → "chapter two" OR "powers of water")
- Iterative search (first search fails → try different terms)
- Cross-reference (user mentioned "chapter 2" + book title → infer they mean Priests & Programmers → search that collection specifically)

---

## PART 4: THE GROUNDING DISCONNECT

### Why grounding shows "0 grounded" on correct answers

The grounding evaluator (`GroundingLink`) runs post-generation. It takes Luna's response and compares each sentence against `injected_nodes`. Here's the problem:

**`injected_nodes` comes from `director._last_injected_memories`** — which contains Memory Matrix nodes only. The Nexus collection context is injected into the system prompt as free-form text, not as structured nodes with IDs. So GroundingLink never sees it.

When Luna answers "the book is about Bali's water temple system" using the DOCUMENT_SUMMARY extraction from Nexus, the grounding evaluator compares that sentence against Memory Matrix nodes about your conversation history. No match. "UNGROUNDED."

The answer is correct. The grounding system just can't see where it came from.

### The fix (not yet implemented)

`_get_collection_context()` needs to return structured extraction objects (with IDs and content) alongside the assembled text. These objects need to be passed to the Director actor and stored in `_last_injected_memories` so GroundingLink can match against them.

This is a P2 fix — it doesn't affect Luna's answers, only the accuracy of the grounding scoreboard.

---

## PART 5: WHAT WOULD MAKE LUNA ACTUALLY THINK

The current system is retrieval, not reasoning. Here's what would change that, in order of impact:

### 1. Multi-query decomposition (P1)

When a user asks "compare chapter 2 to chapter 3," decompose into:
- Query 1: search extractions for chapter 2 content
- Query 2: search extractions for chapter 3 content
- Merge both into context before generation

This is a change to `_get_collection_context()` or the subtask runner. The infrastructure exists (subtask runner already does query rewriting via Qwen) — it just needs to be wired to produce multiple search queries.

### 2. Iterative retrieval (P2)

If the first search returns < 2 results, try:
- Expand query terms (synonyms, related concepts)
- Search with section_label filter relaxed
- Fall back to semantic (embedding) search instead of keyword

Currently: one FTS5 shot, done. This would add a retry loop.

### 3. Nexus → Memory Matrix bridge (P2)

When Luna gives a good answer grounded in Nexus content, the Scribe should extract key claims from that answer and store them in the Memory Matrix with source attribution. This way, Luna "remembers" what she learned from the book across conversations. Currently, document knowledge lives only in Nexus and conversation knowledge lives only in Memory Matrix. They never cross-pollinate.

### 4. Grounding link for Nexus sources (P2)

Wire Nexus extraction IDs into the grounding evaluator so the scoreboard reflects reality.

### 5. Agentic document exploration (P3)

Instead of "search once, generate once," give the LLM the ability to request additional searches mid-generation. "I found a relevant summary but need more detail — let me search for the specific evidence." This is the AgentLoop path that exists in the engine but isn't wired to Nexus yet.

---

## PART 6: RE-INGEST INSTRUCTIONS

### Quick path (backend already running with new code)

```bash
curl -s -X POST http://localhost:8000/api/nexus/ingest \
  -H "Content-Type: application/json" \
  -d '{"collection": "research_library", "file_path": "/absolute/path/to/document.pdf"}' \
  --max-time 600
```

### Full restart path

```bash
# Kill
pkill -f "scripts/run.py"
sleep 2

# Delete DB for clean schema (required if schema changed)
rm -f data/local/research_library.db

# Start with venv python (NEVER system python)
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
PYTHONPATH=src .venv/bin/python scripts/run.py --server --host 0.0.0.0 --port 8000 &
sleep 15

# Ingest — extraction takes 2-5 minutes (Haiku API calls)
curl -s -X POST http://localhost:8000/api/nexus/ingest \
  -H "Content-Type: application/json" \
  -d '{"collection": "research_library", "file_path": "..."}' \
  --max-time 600
```

### Verification

```bash
sqlite3 data/local/research_library.db "
  SELECT COUNT(*) as docs FROM documents;
  SELECT COUNT(*) as chunks FROM chunks;
  SELECT COUNT(*) as tagged FROM chunks WHERE section_label IS NOT NULL;
  SELECT node_type, COUNT(*) FROM extractions GROUP BY node_type;
"
```

---

## DO NOT

- **DO NOT use system python3.** Always `.venv/bin/python`. System Python lacks sqlite-vec and sentence-transformers.
- **DO NOT skip ANTHROPIC_API_KEY.** Extraction silently returns empty without it.
- **DO NOT re-ingest without force** if extractions already exist — the method skips if count > 0.
- **DO NOT trust the old handoff numbers.** The "262 extractions, 297 entities" in `HANDOFF_Nexus_Comprehension_Execute.md` were fabricated by a CC session that didn't actually run the ingest.
- **DO NOT confuse Nexus search with aibrarian_search MCP tool.** The MCP tool searches chunks. The comprehension layer (extractions) only fires through the engine's `_get_collection_context()`.

---

## ENVIRONMENT

```
Project root:  /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
Venv python:   .venv/bin/python
Document:      Docs/PRIESTS AND PROGRAMMERS_Lansing.pdf
Collection:    research_library
Registry:      config/aibrarian_registry.yaml
Backend:       scripts/run.py --server --host 0.0.0.0 --port 8000
Frontend:      frontend/ (npm run dev → :5173)
API key:       ANTHROPIC_API_KEY (must be in environment)
LLM:           Groq 70B (generation), Haiku (extraction at ingest)
Embeddings:    all-MiniLM-L6-v2 via sentence-transformers (local)
```
