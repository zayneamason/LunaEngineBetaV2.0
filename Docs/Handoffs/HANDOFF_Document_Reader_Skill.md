# HANDOFF: Document Reader Skill — Teach Luna How to Read

**Priority:** P1 — Bridges the gap between "knows chapters" and "knows content"  
**Date:** 2026-03-25  
**Time estimate:** 45 minutes  
**Risk:** Low — additive, no existing behavior changes  
**Depends on:** FTS5 fix (on disk, working)

---

## The Problem

Luna can now find extraction data (CLAIMs, SECTION_SUMMARYs) thanks to the FTS5 fix. She lists chapters perfectly. But when asked for *depth* — "what evidence does Lansing present about the simulation model?" — she hedges. Because:

1. **Extractions are summaries.** "Dr. James Kremer developed a simulation model" is a CLAIM. It says the model exists. It doesn't contain the actual methodology, variables, outputs, or evidence.

2. **Chunks have the real text.** The 196 raw text chunks contain the actual paragraphs from the book — the evidence, the data, the quotes. But `_get_collection_context()` only searches `extractions_fts`. It never touches `chunks_fts`.

3. **Luna has no reading strategy.** She doesn't know the difference between skimming (get overview), scanning (find relevant claims), and reading (get the actual text). She does the same thing for every query.

---

## The Solution: Three Pieces

### Piece 1: Add Chunk Search to Retrieval Pipeline

**File:** `src/luna/engine.py` — `_get_collection_context()` around line 1800

After the existing Tier 1-3 cascade (which searches extractions), add a Tier 4 that searches chunks. This fires ONLY when the extraction results suggest deeper content exists but the question asks for specifics.

Add this block AFTER the Tier 3 semantic fallback and BEFORE the "Store structured nodes" comment:

```python
            # ── TIER 4: Chunk deep-read (when extractions are thin on detail) ─
            # If we found extraction CLAIMS/SUMMARIES but the query asks for
            # depth/evidence/specifics, also pull raw text chunks
            _DEPTH_SIGNALS = {
                'evidence', 'specific', 'detail', 'passage', 'quote', 'chapter',
                'section', 'argue', 'methodology', 'data', 'example', 'describe',
                'text says', 'what does', 'how does', 'explain how',
            }
            query_lower = query.lower()
            wants_depth = any(sig in query_lower for sig in _DEPTH_SIGNALS)

            if wants_depth and char_budget > 2000:
                try:
                    chunk_rows = conn.conn.execute(
                        "SELECT c.chunk_text, c.section_label "
                        "FROM chunks_fts "
                        "JOIN chunks c ON chunks_fts.rowid = c.rowid "
                        "WHERE chunks_fts MATCH ? "
                        "ORDER BY rank "
                        "LIMIT 5",
                        (fts_query,),
                    ).fetchall()
                    for row in chunk_rows:
                        text = row[0] if isinstance(row, tuple) else row["chunk_text"]
                        section = row[1] if isinstance(row, tuple) else row.get("section_label", "")
                        if text and text not in seen_content and char_budget > 0:
                            seen_content.add(text)
                            chunk = text[:char_budget]
                            label = f" ({section})" if section else ""
                            parts.append(f"[Nexus/{key} SOURCE_TEXT{label}]\n{chunk}")
                            char_budget -= len(chunk)

                            nexus_nodes.append({
                                "id": f"nexus:{key}:chunk:{len(nexus_nodes)}",
                                "content": text,
                                "node_type": "SOURCE_TEXT",
                                "source": f"nexus/{key}",
                                "confidence": 0.95,
                            })
                except Exception as e:
                    logger.warning(f"[PHASE2] Chunk deep-read for {key}: {e}")
```
**What this does:** When someone asks about "evidence" or "details" or "what the chapter says," Tier 4 pulls actual paragraphs from the book alongside the extraction summaries. Luna gets BOTH the Cliff's Notes AND the source text.

**Why `wants_depth` gate:** Simple questions ("what are the chapters?") don't need raw chunks — extractions are perfect. Only depth-seeking queries pay the cost of chunk retrieval. This keeps simple responses fast.

---

### Piece 2: Reading Strategy Prompt Injection

**File:** `src/luna/context/assembler.py` — add a new grounding block

Add this constant to the PromptAssembler class, alongside the existing PRECISION/REFLECTIVE/RELATIONAL blocks:

```python
    DOCUMENT_READER_GROUNDING = """## Document Reading Mode (active)
You have source material available from your Nexus collections. When answering questions about documents:

READING STRATEGY:
- For OVERVIEW questions ("what is this about?", "what are the chapters?"):
  Use DOCUMENT_SUMMARY and SECTION_SUMMARY extractions. Give structure.

- For CLAIM questions ("what does Lansing argue?", "what's the main thesis?"):
  Use CLAIM extractions. State what the author argues, with attribution.

- For DEPTH questions ("what evidence?", "describe the methodology", "what does the text say about..."):
  Use SOURCE_TEXT passages (raw text from the document). These are actual paragraphs.
  Quote or closely paraphrase the source. Be specific. Cite the section when available.

- For CROSS-REFERENCE questions ("how does this connect to..."):
  Use your Memory Matrix conversation history AND document extractions together.

HONESTY RULES:
- If SOURCE_TEXT passages are in your context, USE them — don't say "I don't have the details."
- If you have CLAIM extractions but no SOURCE_TEXT, say what the claims state and note you don't have the full passage.
- If you have NOTHING from the collection, say so clearly.
- NEVER invent content. NEVER blend training knowledge with collection data without flagging it.
- Distinguish: "The document states..." (from collection) vs "From what I know..." (training knowledge)
"""
```
**Injection point:** In the `build()` method, after the Layer 1.52 mode-specific grounding block (around line 375), add:

```python
        # ── Layer 1.53: DOCUMENT READER (when collection context is present) ─
        if request.has_nexus_context:
            sections.append(self.DOCUMENT_READER_GROUNDING)
```

**Where does `has_nexus_context` come from?** Add it to PromptRequest. It's set to True by the engine when `_get_collection_context()` returns non-empty content. This way, the reading instructions only appear when Luna actually has document data to work with.

In the PromptRequest dataclass (around line 130 of assembler.py), add:
```python
    has_nexus_context: bool = False
```

In engine.py, when building the prompt request (look for where PromptRequest is constructed), set:
```python
    has_nexus_context=bool(collection_context),
```

---

### Piece 3: Document Reader Directive

**Database:** `data/user/luna_engine.db` — `quests` table

Insert a new directive that fires when someone asks document-depth questions:

```sql
INSERT INTO quests (
    id, type, status, priority, title, objective,
    trigger_type, trigger_config, action,
    trust_tier, authored_by, cooldown_minutes,
    created_at, updated_at
) VALUES (
    'dir_document_reader',
    'directive',
    'armed',
    'high',
    'Document Deep Reader',
    'When user asks for document depth (chapters, evidence, sections, quotes), widen aperture and activate reading mode',
    'keyword',
    '{"match": "\\b(chapter|evidence|section|passage|quote|specific|detail|methodology|what does the (book|document|text) say|cite|according to)\\b"}',
    'set_aperture:WIDE',
    'system',
    'system',
    10,
    datetime('now'),
    datetime('now')
);
```

**What this does:** When someone says "what evidence does Lansing present" or "tell me about chapter 3" or "what does the text say about," the directive fires and:
1. Sets aperture to WIDE (more retrieval budget)
2. The wider aperture + Tier 4 chunk search + the reading strategy prompt injection all work together

The directive is lightweight — it just opens the aperture. The real work is in Tier 4 (chunk search) and the prompt injection (reading strategy).

---

### Optional: Document Reader Skill (Multi-Step)

If you also want a callable skill that does full preparation (like Guardian Demo Prep), add:

```sql
INSERT INTO quests (
    id, type, status, priority, title, objective,
    steps, trigger_type,
    trust_tier, authored_by,
    created_at, updated_at
) VALUES (
    'skill_deep_read',
    'skill',
    'available',
    'medium',
    'Deep Document Reader',
    'Full preparation for deep document analysis: widen aperture, load collections, sweep memory for related context',
    '["set_aperture:WIDE", "memory_sweep:document chapters evidence", "surface_parked_threads"]',
    NULL,
    'system',
    'system',
    datetime('now'),
    datetime('now')
);
```

This skill can be invoked manually or by another directive via `run_skill:Deep Document Reader`.

---
## How It Works End-to-End

### Before (current — FTS5 fix only):
```
User: "What evidence does Lansing present about the simulation model?"
  → FTS5 search: "evidence OR lansing OR present OR simulation OR model"
  → Tier 1: Finds CLAIMs: "Dr. Kremer developed a simulation model..."
  → Tier 2/3: Maybe more CLAIMs
  → Tier 4: DOESN'T EXIST — no chunk search
  → Prompt: No reading strategy — Luna doesn't know how to use what she found
  → Luna: "I can see there's a simulation model mentioned, but I don't have the details..."
```

### After (with reading skill):
```
User: "What evidence does Lansing present about the simulation model?"
  → Directive fires: "evidence" keyword match → set_aperture:WIDE
  → FTS5 search: "evidence OR lansing OR present OR simulation OR model"
  → Tier 1: CLAIMs: "Kremer developed a simulation model..."
  → Tier 2/3: SECTION_SUMMARYs about Chapter 6 and Appendix B
  → Tier 4: wants_depth=True ("evidence" signal) → searches chunks_fts
    → Gets actual paragraphs: "The model was specifically designed to evaluate
       the effects of different levels of social coordination on irrigation
       demand and pest control..."
  → Prompt: DOCUMENT_READER_GROUNDING injected (has_nexus_context=True)
    → Luna sees: "For DEPTH questions, use SOURCE_TEXT passages. Quote closely."
  → Luna: "Lansing's simulation model, built with James Kremer, was specifically
     designed to evaluate different levels of social coordination on irrigation
     and pest management. The model showed that..." [cites actual text]
```

---

## Verification

### Test 1: Overview question (should NOT trigger Tier 4)
```
"What are the chapters in Priests and Programmers?"
```
Expected: Same chapter listing as before. No chunks needed. Fast.

### Test 2: Depth question (should trigger Tier 4)
```
"What evidence does Lansing present about the simulation model?"
```
Expected:
- Engine logs: `[PHASE2] Chunk deep-read for research_library` (Tier 4 fired)
- Luna's response cites actual text passages, not just "a simulation model exists"
- Grounding score: 5+ grounded claims

### Test 3: Cross-reference question
```
"How does the water temple system connect to what we've been building?"
```
Expected:
- Extraction CLAIMs + Memory Matrix conversation nodes
- Luna connects Lansing's concepts to Luna/Tapestry work
- RELATIONAL_GROUNDING from the assembler if the collection has `reflection_mode: "relational"`

### Test 4: Directive firing
Check engine logs for:
```
Fired directive: dir_document_reader (Document Deep Reader)
```
When the user asks about "evidence" or "chapters."

---

## Execution Order

1. **Tier 4 chunk search** in engine.py (15 min) — the retrieval change
2. **Reading strategy prompt** in assembler.py (10 min) — the prompt injection
3. **`has_nexus_context` flag** in assembler.py + engine.py (5 min) — the injection trigger
4. **Directive insert** in luna_engine.db (5 min) — the keyword trigger
5. **Restart engine, test** (10 min)

---

## What NOT To Do

- Do NOT remove or modify Tier 1-3. Tier 4 is additive.
- Do NOT change the FTS5 sanitizer. It's working.
- Do NOT inject DOCUMENT_READER_GROUNDING unconditionally — only when `has_nexus_context` is True
- Do NOT make Tier 4 run on every query — the `wants_depth` gate is intentional
- Do NOT change the existing PRECISION/REFLECTIVE/RELATIONAL grounding blocks — the reading skill is additive
- Do NOT increase chunk LIMIT beyond 5 without checking char_budget — chunks are 500 chars each, 5 chunks = 2500 chars
- Do NOT search both chunks_fts AND extractions_fts in Tier 4 — extractions are already covered by Tiers 1-3

---

## Files Modified

| File | Change |
|---|---|
| `src/luna/engine.py` | Add Tier 4 chunk search in `_get_collection_context()` (~25 lines) |
| `src/luna/context/assembler.py` | Add DOCUMENT_READER_GROUNDING constant + Layer 1.53 injection (~25 lines) |
| `src/luna/context/assembler.py` | Add `has_nexus_context` to PromptRequest dataclass (1 line) |
| `src/luna/engine.py` | Set `has_nexus_context` when building PromptRequest (1 line) |
| `data/user/luna_engine.db` | INSERT directive + optional skill (2 SQL statements) |

## The Reading Hierarchy

After this skill is implemented, Luna has four reading depths:

| Depth | What she uses | When |
|---|---|---|
| **Skim** | DOCUMENT_SUMMARY + TABLE_OF_CONTENTS | "What is this about?" |
| **Scan** | CLAIM + SECTION_SUMMARY extractions | "What does Lansing argue?" |
| **Read** | Raw SOURCE_TEXT chunks | "What evidence?" / "What does the text say?" |
| **Study** | Chunks + extractions + Memory Matrix + reflections | Cross-reference and analysis |

Each depth is automatic. No UI toggle. No manual aperture. Luna reads the question and goes as deep as needed.
