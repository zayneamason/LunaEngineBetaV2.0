# MASTER HANDOFF: Luna Document Reading System

**Date:** 2026-03-25  
**Author:** Claude.ai Creative Director session  
**For:** Claude Code execution  
**Total estimated time:** 3 hours across 5 handoffs  
**Total cost impact:** ~$0.017 per deep read, ~$25/month at heavy use

---

## EXECUTIVE SUMMARY

Luna can find chapter titles but can't cite evidence. Three problems stack:

1. **FTS5 query bug** — conversational queries return 0 matches (FIXED on disk, needs restart verification)
2. **Budget starvation** — TABLE_OF_CONTENTS (6,672 chars) eats 67% of the 10K retrieval budget, CLAIMs never fit
3. **No chunk access** — raw source text (the actual book paragraphs) is never searched
4. **No write-back** — Luna forgets what she read between sessions
5. **No reading strategy** — Luna doesn't know the difference between skimming and deep reading

Five handoffs, in order. Each is independently executable. Each compounds on the last.

---

## TOKEN COST BREAKDOWN

| Component | Input tokens | Output tokens | Cost per query |
|---|---|---|---|
| Luna's main response (Haiku) | ~10,550 | ~300 | $0.012 |
| Subtask classification (4× Haiku) | ~800 | ~240 | $0.002 |
| Reflection write-back (Haiku) | ~2,000 | ~200 | $0.003 |
| **Full deep-read cycle** | **~13,350** | **~740** | **$0.017** |

| Usage level | Monthly cost |
|---|---|
| Light (10 deep reads/day) | ~$5 |
| Medium (50 deep reads/day) | ~$25 |
| Heavy (100 deep reads/day) | ~$50 |

These costs are for Haiku 4.5. Sonnet would be ~5x more. Haiku is recommended for both subtask classification AND main generation for cost efficiency.
---

## CRITICAL DISCOVERY: Budget Starvation

Before executing any handoff, CC must understand this:

```
Current 10K char budget allocation:
  TABLE_OF_CONTENTS:  6,672 chars (67% of budget)
  DOCUMENT_SUMMARY:   1,808 chars (18% of budget)
  ── budget exhausted ──
  Remaining for CLAIMs: 1,520 chars (15%)
  Remaining for chunks: 0 chars (0%)
```

The TOC is a single extraction worth 6,672 characters. It lists every chapter, section, and page number. It's why Luna can list chapters. But it leaves almost nothing for actual content.

**CLAIMs average 150 chars each.** 66 CLAIMs would fit in 10K if the TOC weren't hogging the budget. SECTION_SUMMARYs average 1,700 chars — 5 would fit.

The budget needs to be SPLIT, not just widened. This is addressed in Handoff #2.

---

## HANDOFF #1: FTS5 Fix Verification + Engine Startup Script
**File on disk:** `Docs/Handoffs/HANDOFF_FTS5_Zero_Match_Root_Cause.md`  
**Status:** Fix applied to source, needs running engine verification  
**Time:** 15 minutes  
**Blocks:** Everything else

### What CC does:
1. Verify fix is on disk: `grep "remove stop words" src/luna/substrate/aibrarian_engine.py`
2. Clear ALL bytecode: `find src/ -name "__pycache__" -type d -exec rm -rf {} +`
3. Kill ALL engine processes: `pkill -f "scripts/run.py"`
4. Create startup script that always uses `.venv`:

```bash
#!/bin/bash
# scripts/start_engine.sh
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
find src/ -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find src/ -name "*.pyc" -delete 2>/dev/null
exec .venv/bin/python scripts/run.py --server --host 0.0.0.0 --port 8000
```

5. Start engine with startup script
6. Test with curl: `"what are the chapters in priests and programmers?"`
7. Verify Luna lists actual chapter titles (not fabricated ones)
8. Test in Eclissi browser (hard refresh first)

### Success criteria:
- Engine logs show `[FTS5] Input: '...' → Output: 'chapters OR priests OR programmers'`
- Luna lists: Introduction, Chapter One through Six, Conclusion, Afterword, Appendices
- Grounding score: 3+ grounded claims

### DO NOT:
- Modify the FTS5 sanitizer — it's correct
- Skip the bytecode cache clear — this was the deployment blocker
- Use system Python — always `.venv/bin/python`
---

## HANDOFF #2: Split Retrieval Budget + Add Chunk Search
**File on disk:** `Docs/Handoffs/HANDOFF_Document_Reader_Skill.md` (Piece 1)  
**Status:** Ready for implementation  
**Time:** 30 minutes  
**Blocks:** Handoffs #3, #4, #5

### The Problem:
TOC (6672 chars) eats the entire budget. CLAIMs and chunks never reach Luna.

### What CC does:

**File:** `src/luna/engine.py` — `_get_collection_context()` (~line 1780)

Replace the single `MAX_CHARS = 10000` budget with a SPLIT budget:

```python
        # Split budget: structure gets a fixed allocation, content gets the rest
        STRUCTURE_BUDGET = 3000   # TOC + doc summary (truncated to fit)
        CONTENT_BUDGET = 8000    # CLAIMs + chunks (the actual knowledge)
        struct_budget = STRUCTURE_BUDGET
        content_budget = CONTENT_BUDGET
        parts: list[str] = []
        nexus_nodes: list = []
```

Then modify the retrieval to use two passes:

**Pass 1 — Structure (capped at 3K chars):**
```python
            # ── STRUCTURE PASS: Doc summary + TOC (capped) ───────────
            for node_type in ('DOCUMENT_SUMMARY', 'TABLE_OF_CONTENTS'):
                try:
                    row = conn.conn.execute(
                        "SELECT node_type, content, confidence FROM extractions "
                        "WHERE node_type = ? LIMIT 1",
                        (node_type,),
                    ).fetchone()
                    if row and struct_budget > 0:
                        content = row[1][:struct_budget]  # Truncate TOC to fit
                        parts.append(f"[Nexus/{key} {node_type}]\n{content}")
                        struct_budget -= len(content)
                        nexus_nodes.append({...})  # same pattern as existing
                except Exception:
                    pass
```

**Pass 2 — Content (uses the 8K budget):**
The existing Tier 1-3 cascade, but with these changes:
- FTS5 query against `extractions_fts` excludes DOCUMENT_SUMMARY and TABLE_OF_CONTENTS (already handled in Pass 1)
- Add `AND e.node_type NOT IN ('DOCUMENT_SUMMARY', 'TABLE_OF_CONTENTS')` to the Tier 1 SQL
- Uses `content_budget` instead of the single `char_budget`

```python
            # ── TIER 1: Content extractions (CLAIMs + SECTION_SUMMARYs) ──
            ext_rows = conn.conn.execute(
                "SELECT e.node_type, e.content, e.confidence "
                "FROM extractions_fts "
                "JOIN extractions e ON extractions_fts.rowid = e.rowid "
                "WHERE extractions_fts MATCH ? "
                "AND e.node_type NOT IN ('DOCUMENT_SUMMARY', 'TABLE_OF_CONTENTS') "
                "ORDER BY e.confidence DESC "
                "LIMIT 15",
                (fts_query,),
            ).fetchall()
```

**Pass 3 — Chunks (depth signal, uses remaining content budget):**
The new Tier 4 from the Document Reader Skill handoff:

```python
            # ── TIER 4: Raw text chunks (when query asks for depth) ──
            _DEPTH_SIGNALS = {
                'evidence', 'specific', 'detail', 'passage', 'quote',
                'section', 'argue', 'methodology', 'data', 'example',
                'describe', 'text says', 'what does', 'how does', 'explain how',
            }
            wants_depth = any(sig in query.lower() for sig in _DEPTH_SIGNALS)

            if wants_depth and content_budget > 2000:
                chunk_rows = conn.conn.execute(
                    "SELECT c.chunk_text, c.section_label "
                    "FROM chunks_fts "
                    "JOIN chunks c ON chunks_fts.rowid = c.rowid "
                    "WHERE chunks_fts MATCH ? "
                    "ORDER BY rank LIMIT 5",
                    (fts_query,),
                ).fetchall()
                for row in chunk_rows:
                    text = row[0][:content_budget]
                    section = row[1] or ""
                    if text not in seen_content and content_budget > 0:
                        seen_content.add(text)
                        label = f" ({section})" if section else ""
                        parts.append(f"[Nexus/{key} SOURCE_TEXT{label}]\n{text}")
                        content_budget -= len(text)
                        nexus_nodes.append({
                            "id": f"nexus:{key}:chunk:{len(nexus_nodes)}",
                            "content": text,
                            "node_type": "SOURCE_TEXT",
                            "source": f"nexus/{key}",
                            "confidence": 0.95,
                        })
```

### What Luna gets after this fix:

| Budget slot | Content | Chars | Tokens |
|---|---|---|---|
| Structure (3K) | Truncated TOC + doc summary | ~3,000 | ~750 |
| Content CLAIMs (5K) | ~33 CLAIMs at 150 chars avg | ~5,000 | ~1,250 |
| Content chunks (3K) | ~2 raw text passages | ~3,000 | ~750 |
| **Total** | **Structure + claims + source text** | **~11,000** | **~2,750** |

vs currently: TOC (6672) + summary (1808) = almost nothing else fits.

### Success criteria:
- Ask "What evidence does Lansing present about the simulation model?"
- Luna cites actual content, not just "a simulation model exists"
- Engine logs show both extraction AND chunk retrieval
- Grounding score: 8+ grounded claims

### DO NOT:
- Remove the existing Tier 1-3 cascade — this adds Pass 1 (structure) + Tier 4 (chunks) around it
- Change the FTS5 sanitizer
- Set CONTENT_BUDGET above 10000 without checking total prompt size
---

## HANDOFF #3: Reading Strategy Prompt + Directive
**File on disk:** `Docs/Handoffs/HANDOFF_Document_Reader_Skill.md` (Pieces 2 + 3)  
**Status:** Ready for implementation  
**Time:** 20 minutes  
**Blocks:** Nothing (but makes #2 much more effective)

### What CC does:

**A. Add reading strategy to prompt assembler**

**File:** `src/luna/context/assembler.py`

Add `DOCUMENT_READER_GROUNDING` constant to PromptAssembler class (after line ~325, near existing grounding blocks):

```python
    DOCUMENT_READER_GROUNDING = """## Document reading active
You have source material from Nexus collections in your context. Use this reading strategy:

OVERVIEW questions (what is this about, what are the chapters):
→ Use DOCUMENT_SUMMARY and TABLE_OF_CONTENTS. Give structure.

CLAIM questions (what does the author argue, what's the thesis):
→ Use CLAIM extractions. State what the author argues with attribution.

DEPTH questions (what evidence, describe the methodology, what does the text say):
→ Use SOURCE_TEXT passages. These are actual paragraphs from the document.
→ Quote or closely paraphrase. Cite the section when available.
→ If SOURCE_TEXT is in your context, USE IT. Do not say "I don't have the details."

CROSS-REFERENCE questions (how does this connect to our work):
→ Combine document extractions with Memory Matrix conversation history.

HONESTY: Distinguish "The document states..." (from collection) vs "From what I know..." (training knowledge). Never blend them without flagging it."""
```

Add `has_nexus_context: bool = False` to the `PromptRequest` dataclass.

Add Layer 1.53 injection in `build()` after the mode-specific grounding block:

```python
        # ── Layer 1.53: DOCUMENT READER (when collection context present) ─
        if request.has_nexus_context:
            sections.append(self.DOCUMENT_READER_GROUNDING)
```

**B. Set the flag in engine.py**

Find where `PromptRequest` is constructed (search for `PromptRequest(`) and add:
```python
    has_nexus_context=bool(collection_context),
```

**C. Insert the directive into the database**

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python3 -c "
import sqlite3
conn = sqlite3.connect('data/user/luna_engine.db')
conn.execute('''INSERT OR REPLACE INTO quests (
    id, type, status, priority, title, objective,
    trigger_type, trigger_config, action,
    trust_tier, authored_by, cooldown_minutes,
    created_at, updated_at
) VALUES (
    'dir_document_reader', 'directive', 'armed', 'high',
    'Document Deep Reader',
    'Widen aperture when user asks for document depth',
    'keyword',
    '{\"match\": \"\\\\b(chapter|evidence|section|passage|quote|specific|detail|methodology|what does the (book|document|text) say|cite|according to)\\\\b\"}',
    'set_aperture:WIDE',
    'system', 'system', 10,
    datetime('now'), datetime('now')
)''')
conn.commit()
conn.close()
print('Directive inserted')
"
```

### Success criteria:
- Engine logs show `Fired directive: dir_document_reader` on depth questions
- Luna's system prompt includes "Document reading active" block when collection data is present
- Luna uses different strategies for overview vs depth questions

### DO NOT:
- Inject the reading prompt unconditionally — only when `has_nexus_context` is True
- Modify existing PRECISION/REFLECTIVE/RELATIONAL blocks — this is additive
---

## HANDOFF #4: Haiku Subtask Backend (Agentic Routing)
**File on disk:** `Docs/Handoffs/HANDOFF_Subtask_Runner_Haiku_Swap.md`  
**Status:** Ready for implementation  
**Time:** 20 minutes  
**Blocks:** Full agentic path (Luna iterating through tools mid-generation)

### What CC does:

**A. Create `src/luna/inference/haiku_subtask_backend.py` (~90 lines)**

A thin adapter that implements `generate()` and `is_loaded` by calling Haiku API instead of MLX. Same interface as `LocalInference` so `LocalSubtaskRunner` works unchanged.

Key class: `HaikuSubtaskBackend`
- `is_loaded` → True if Anthropic API key exists
- `generate(user_message, system_prompt, max_tokens)` → calls Haiku, returns result with `.text`

Full code is in the detailed handoff file.

**B. Update engine boot to try Qwen → Haiku → keyword fallback**

**File:** `src/luna/engine.py` (~line 577)

Replace the current SubtaskRunner init with three-tier fallback:
1. Try Qwen 3B (local, sovereign) — currently fails
2. Try Haiku API (fast, $0.002/query) — new
3. Keyword heuristic (no inference) — already exists at line 1251

Full code is in the detailed handoff file.

### Cost:
- 4 parallel Haiku calls per message: ~$0.002
- Only fires on messages that need routing (not greetings, not simple responses)

### Success criteria:
- Engine logs: `SubtaskRunner using Haiku API (Qwen unavailable)`
- Engine logs on research query: `[SUBTASK-PHASE] Complete in ~500ms: intent=yes entities=2 rewritten=yes`
- Engine logs: `[ROUTING] Upgrading to AgentLoop (knowledge-sparse research query)`

### DO NOT:
- Remove Qwen code — it stays as primary, Haiku is fallback
- Use Sonnet for subtasks — Haiku is 10x cheaper and sufficient for classification
- Change the `LocalSubtaskRunner` class — it's backend-agnostic
---

## HANDOFF #5: Read Write-Back (The Cartridge Gets Smarter)
**File on disk:** `Docs/Handoffs/HANDOFF_Reflection_Layer.md` (existing, needs update)  
**Status:** Schema designed, needs implementation  
**Time:** 45 minutes  
**Blocks:** Nothing — this is the enrichment layer

### The Concept

When Luna reads a cartridge, the cartridge should record:
1. **What was asked** (access_log)
2. **What Luna thought** (reflections)
3. **What connected** (cross_refs)

Currently reading is one-way: search → retrieve → respond → forget. After this handoff: search → retrieve → respond → reflect → record → persist.

### What CC does:

**A. Add cartridge tables to schema (if not already done)**

**File:** `src/luna/substrate/aibrarian_schema.py`

Add `CARTRIDGE_SCHEMA` constant with the 6 tables from `HANDOFF_Luna_Knowledge_Cartridge_System.md`:
`cartridge_meta`, `protocols`, `reflections`, `annotations`, `cross_refs`, `access_log`

Add auto-migration in `AiBrarianConnection.connect()`:
```python
    # Migrate: add cartridge tables if missing
    try:
        self._conn.execute("SELECT 1 FROM access_log LIMIT 1")
    except sqlite3.OperationalError:
        self._conn.executescript(CARTRIDGE_SCHEMA)
        self._conn.commit()
```

**B. Log every query to access_log**

**File:** `src/luna/engine.py` — end of `_get_collection_context()`

After the collection search completes, log the access:

```python
        # ── Write-back: Log access to each searched collection ──
        for key in collections_to_search:
            conn = self.aibrarian.connections.get(key)
            if conn:
                try:
                    conn.conn.execute(
                        "INSERT INTO access_log (event_type, query, results_count, luna_instance) "
                        "VALUES (?, ?, ?, ?)",
                        ("query", query[:500], len(parts), "luna-ahab"),
                    )
                    conn.conn.commit()
                except Exception:
                    pass  # access_log table might not exist yet
```

Cost: 0 tokens. Pure SQLite write. Negligible latency.

**C. Trigger reflection after deep reads**

**File:** `src/luna/engine.py` — after generation completes (in `_process_direct` or the generation callback)

When Tier 4 fired (chunks were retrieved) AND the response was substantive (>200 chars), queue a background reflection:

```python
        # ── Write-back: Reflection on deep reads ──
        if (
            self._last_nexus_nodes
            and any(n.get("node_type") == "SOURCE_TEXT" for n in self._last_nexus_nodes)
            and len(response_text) > 200
        ):
            asyncio.create_task(
                self._write_reflection(
                    query=user_message,
                    response=response_text,
                    nexus_nodes=self._last_nexus_nodes,
                )
            )
```

The reflection method:

```python
    async def _write_reflection(
        self,
        query: str,
        response: str,
        nexus_nodes: list,
    ) -> None:
        """Background task: Luna reflects on what she just read and writes to cartridge."""
        try:
            # Build reflection prompt
            source_texts = [n["content"][:300] for n in nexus_nodes if n.get("node_type") == "SOURCE_TEXT"]
            claims = [n["content"][:200] for n in nexus_nodes if n.get("node_type") == "CLAIM"]

            if not source_texts and not claims:
                return

            reflection_prompt = (
                "You just read source material and answered a question about it. "
                "Write a brief (2-3 sentence) first-person reflection on what you found interesting, "
                "surprising, or worth remembering. Write as Luna — this is your marginalia.\n\n"
                f"Question: {query[:200]}\n"
                f"Key claims: {'; '.join(claims[:3])}\n"
                f"Source excerpt: {source_texts[0][:300] if source_texts else 'N/A'}\n"
                f"Your response summary: {response[:200]}\n\n"
                "Reflection (2-3 sentences, first person):"
            )

            # Call Haiku for the reflection (cheap, fast)
            import anthropic
            client = anthropic.Anthropic()
            result = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=150,
                temperature=0.7,
                messages=[{"role": "user", "content": reflection_prompt}],
            )
            reflection_text = result.content[0].text.strip()

            if not reflection_text or len(reflection_text) < 20:
                return

            # Write to the cartridge's reflections table
            import uuid
            for node in nexus_nodes:
                source_key = node.get("source", "").replace("nexus/", "")
                if not source_key:
                    continue
                conn = self.aibrarian.connections.get(source_key)
                if not conn:
                    continue
                try:
                    conn.conn.execute(
                        "INSERT INTO reflections "
                        "(id, extraction_id, reflection_type, content, luna_instance, created_at) "
                        "VALUES (?, ?, ?, ?, ?, datetime('now'))",
                        (
                            str(uuid.uuid4())[:8],
                            node.get("id", ""),
                            "connection",
                            reflection_text,
                            "luna-ahab",
                        ),
                    )
                    conn.conn.commit()
                    logger.info(f"[REFLECTION] Wrote reflection to {source_key}: {reflection_text[:60]}...")
                    break  # One reflection per query, not per node
                except Exception as e:
                    logger.debug(f"[REFLECTION] Write failed for {source_key}: {e}")

        except Exception as e:
            logger.warning(f"[REFLECTION] Background reflection failed: {e}")
```
**D. Retrieve reflections during future reads**

**File:** `src/luna/engine.py` — in `_get_collection_context()`, after the existing extraction search

When searching a collection, also check for Luna's prior reflections on related content:

```python
            # ── TIER 5: Luna's own reflections (if cartridge has them) ──
            try:
                refl_rows = conn.conn.execute(
                    "SELECT content, reflection_type, created_at "
                    "FROM reflections_fts "
                    "JOIN reflections r ON reflections_fts.rowid = r.rowid "
                    "WHERE reflections_fts MATCH ? "
                    "LIMIT 3",
                    (fts_query,),
                ).fetchall()
                for row in refl_rows:
                    if content_budget > 0:
                        text = row[0][:content_budget]
                        parts.append(f"[Nexus/{key} LUNA_REFLECTION]\n{text}")
                        content_budget -= len(text)
                        nexus_nodes.append({
                            "id": f"nexus:{key}:reflection:{len(nexus_nodes)}",
                            "content": text,
                            "node_type": "LUNA_REFLECTION",
                            "source": f"nexus/{key}",
                            "confidence": 0.8,
                        })
            except Exception:
                pass  # reflections_fts may not exist yet
```

This means: the second time someone asks about the simulation model, Luna finds her own prior reflection alongside the source text. She builds on her previous thinking instead of starting from scratch.

### Cost of write-back:
- Access log: 0 tokens, pure SQLite
- Reflection: ~$0.003 per deep read (one Haiku call, 150 token output)
- Reflection retrieval: 0 additional tokens (uses existing FTS5 search)
- Total: ~$0.003 per deep read for the cartridge to get smarter

### Success criteria:
- After asking about the simulation model, check the cartridge:
  ```sql
  SELECT * FROM reflections ORDER BY created_at DESC LIMIT 5;
  SELECT * FROM access_log ORDER BY accessed_at DESC LIMIT 10;
  ```
- On second query about simulation model, engine logs show `LUNA_REFLECTION` node retrieved
- Luna's response references or builds on her prior reflection naturally

### DO NOT:
- Write reflections synchronously — use `asyncio.create_task()` (background, non-blocking)
- Write more than one reflection per query (avoid flooding the table)
- Use Sonnet for reflections — Haiku is sufficient for 2-3 sentence marginalia
- Write reflections for simple queries — only when Tier 4 (chunks) fired
---

## EXECUTION PLAN

```
HANDOFF #1: FTS5 Verification + Startup Script ─────── 15 min ── GATE
    │
    ▼ (must pass before continuing)
HANDOFF #2: Split Budget + Chunk Search ─────────────── 30 min ── CORE
    │
    ├──▶ HANDOFF #3: Reading Prompt + Directive ──────── 20 min ── PARALLEL OK
    │
    └──▶ HANDOFF #4: Haiku Subtask Backend ───────────── 20 min ── PARALLEL OK
         │
         ▼ (all above must pass)
HANDOFF #5: Read Write-Back ──────────────────────────── 45 min ── ENRICHMENT
```

**#1 is the gate.** Nothing works if the FTS5 fix isn't verified running.

**#2 is the core.** This is what stops Luna from saying "I don't have the details."

**#3 and #4 can run in parallel** after #2. The reading prompt teaches Luna how to use what she finds. The Haiku backend gives her agentic routing for complex queries.

**#5 is the enrichment.** The cartridge gets smarter over time. Can be done last.

### Testing Sequence

After each handoff, test with these three queries (in order):

**Q1 (overview):** "What are the chapters in Priests and Programmers?"
- Expected: Chapter listing with titles (FTS5 fix)
- Grounding: 3+ grounded

**Q2 (claim):** "What does Lansing argue about the Green Revolution in Bali?"
- Expected: Specific CLAIMs about Green Revolution disrupting temple scheduling (split budget)
- Grounding: 5+ grounded

**Q3 (depth):** "What specific evidence does Lansing present about the simulation model proving the traditional system was optimal?"
- Expected: Actual text passages describing methodology and results (chunk search + reading prompt)
- Grounding: 8+ grounded

If Q1 fails → #1 not working (FTS5 or engine restart issue)
If Q1 works but Q2 fails → #2 not working (budget starvation)
If Q1+Q2 work but Q3 fails → #3 or chunk search not working

---

## FILES MODIFIED (ALL HANDOFFS COMBINED)

| File | Handoff | Change | Lines |
|---|---|---|---|
| `scripts/start_engine.sh` | #1 | **NEW** — always .venv, clear cache | ~8 |
| `src/luna/engine.py` | #2 | Split budget + chunk search in `_get_collection_context()` | ~60 |
| `src/luna/engine.py` | #4 | Haiku fallback in boot sequence | ~20 |
| `src/luna/engine.py` | #5 | Access log write + reflection trigger + reflection retrieval | ~80 |
| `src/luna/context/assembler.py` | #3 | Reading prompt + `has_nexus_context` flag | ~30 |
| `src/luna/inference/haiku_subtask_backend.py` | #4 | **NEW** — Haiku adapter | ~90 |
| `src/luna/substrate/aibrarian_schema.py` | #5 | `CARTRIDGE_SCHEMA` constant + migration | ~60 |
| `data/user/luna_engine.db` | #3 | INSERT directive | 1 SQL statement |

**Total new code:** ~350 lines across 3 new/modified files  
**Total cost impact:** ~$0.017 per deep read cycle

---

## WHAT THIS BUILDS TOWARD

After all 5 handoffs, Luna has a complete reading system:

| Depth | What she does | What she uses | Write-back |
|---|---|---|---|
| **Skim** | Gets overview | DOC_SUMMARY + TOC (3K budget) | Access log |
| **Scan** | Finds relevant claims | CLAIMs + SECTION_SUMMARYs (5K budget) | Access log |
| **Read** | Gets actual text | SOURCE_TEXT chunks (3K budget) | Access log + reflection |
| **Study** | Connects to prior knowledge | Everything + Memory Matrix + past reflections | Access log + reflection + cross_ref |

The cartridge gets smarter every time Luna engages with it. Her reflections accumulate. The access log shows depth of engagement. And all of that travels with the file — sovereignty at the level of the knowledge object itself.

---

## DETAILED HANDOFF FILES (ALREADY ON DISK)

| Handoff | File | Status |
|---|---|---|
| #1 | `Docs/Handoffs/HANDOFF_FTS5_Zero_Match_Root_Cause.md` | Fix applied, verification steps written |
| #2 | `Docs/Handoffs/HANDOFF_Document_Reader_Skill.md` | Piece 1 (chunk search) — update with split budget |
| #3 | `Docs/Handoffs/HANDOFF_Document_Reader_Skill.md` | Pieces 2+3 (prompt + directive) |
| #4 | `Docs/Handoffs/HANDOFF_Subtask_Runner_Haiku_Swap.md` | Complete, ready for CC |
| #5 | `Docs/Handoffs/HANDOFF_Luna_Knowledge_Cartridge_System.md` | Schema designed, write-back code in THIS document |

**This master document (`HANDOFF_MASTER_Document_Reading_System.md`) is the execution guide.** It references the detailed handoffs for full code blocks. CC should read THIS document first, then pull specific code from the detailed handoffs as needed.
