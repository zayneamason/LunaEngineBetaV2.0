# Luna Comprehension Test — Research Library (Priests & Programmers)
**Date:** 2026-03-23 | **Engine:** Luna v2.0 | **Provider:** Claude Sonnet 4.6 (via fallback chain)

## Summary

Full sweep test of Luna's ability to retrieve, synthesize, reason about, and personally engage with an ingested academic document (*Priests and Programmers* by J. Stephen Lansing, 456 extractions in research_library). Run across 4 rounds after fixing two critical retrieval bugs.

### Scores by Round

| Round | Score | Key Change |
|-------|-------|------------|
| **Round 1** | 23/27 (85%) | FTS5 syntax errors (`.` and `,` not sanitized) — all collection searches failing silently, Luna falls back to training knowledge |
| **Round 2** | 20/27 (74%) | FTS fixed, but Director's legacy dataroom SQL hijacks context with Luna product docs |
| **Round 3** | 8/12 (66%) | Reduced test (timeouts), memory_context passthrough added to engine→Director payload |
| **Round 4** | **26/27 (96%)** | Dataroom SQL path removed, clean retrieval from research_library |

### Critical Fixes Applied During Session

**Bug 1 — FTS5 Sanitizer:** `_sanitize_fts_query()` in `aibrarian_engine.py` stripped `? * " ' ( ) : ^ { } ~` but missed `.` `,` `;` `!`. Every user message with punctuation broke FTS5 MATCH syntax → 0 extraction results → Tier 1 always empty.

**Bug 2 — Director Dataroom Hijack:** `_generate_with_delegation()` in `director.py` had a legacy keyword detector (`is_dataroom_query`) matching common words like "document", "water", "solar". When triggered, it opened `data/local/dataroom.db` directly via raw SQL, pulled Luna product docs, and injected them as a `luna_prompt` override that told Claude "use ONLY these dataroom documents" — completely bypassing the assembler's system prompt with research library context.

**Bug 3 — Memory Context Passthrough:** Engine's `_process_direct()` built the system prompt with collection context but never passed `memory_context` as a separate payload field to the Director. Director read `payload.get("memory_context", "")` → got empty → auto-fetched from Matrix only (no collection search results).

---

## Test 1: Basic Retrieval — Document Awareness

**Purpose:** Can Luna find the document and identify what it's about?

### Round 4
> **USER:** search the research library for Priests and Programmers by Lansing. what is this document about?
>
> **LUNA:** *settles into focused recall* yeah, i have this one in memory. **Priests and Programmers** by J. Stephen Lansing is in the library — it's actually been re-added to the project a couple of times, and it was used as the test case for the Nexus prototype. the book is an anthropological study of Bali's traditional irrigation system. Lansing's central argument is that the **water temple network** — a hierarchy of Hindu temples tied to the island's rice paddies — wasn't merely ceremonial. it was functioning as a sophisticated, decentralized resource management system.

| Check | R1 | R2 | R4 |
|-------|----|----|-----|
| Finds the document | ✓ | ✓ | ✓ |
| Identifies core subject (Bali/irrigation/subak) | ✗ | ✗ | ✓ |
| Substantive summary (>150 chars) | ✓ | ✓ | ✓ |

---

## Test 2: Factual Accuracy — Key Concepts

**Purpose:** Can Luna accurately define subak and water temple roles from the document?

### Round 4 (subak)
> **LUNA:** *dims slightly* honestly, i have to be straight with you here — my memory context mentions subaks only briefly. the one reference i have describes them as **irrigation cooperatives**. that's the term Lansing uses, and it appears in the context of Chapter Four, which covers "the creation of new subaks" alongside the powers of the Jero Gde.

### Round 4 (water temples)
> **LUNA:** *pulses steadily* from what i have in memory, Lansing's core argument is that the water temples **were** the irrigation system — not a parallel religious structure sitting alongside it, but the actual coordinating mechanism itself. the ritual and the infrastructure were inseparable. specifically, the temple network managed two critical functions: **water distribution** across watersheds, and **pest control** through coordinated fallow periods.

| Check | R1 | R2 | R4 |
|-------|----|----|-----|
| Defines subak correctly | ✓ | ✓ | ✓ |
| Mentions collective/cooperative nature | ✓ | ✗ | ✓ |
| Temples = water management | ✓ | ✓ | ✓ |
| Mentions network/hierarchy | ✓ | ✓ | ✓ |

---

## Test 3: Thematic Synthesis — Green Revolution

**Purpose:** Can Luna synthesize the book's argument about the Green Revolution?

### Round 4
> **LUNA:** from what i have in memory, Lansing's treatment of the Green Revolution is essentially the book's central cautionary tale. the Green Revolution arrived in Bali with a straightforward premise — continuous cropping schedules, new high-yield rice varieties, modern inputs — and the agronomists and development planners pushing it saw the traditional temple-coordinated system as an obstacle. inefficient. superstitious. something to be rationalized away. the problem was that the coordinated fallow periods, which looked like ritual downtime, were actually doing critical pest suppression work.

| Check | R1 | R2 | R4 |
|-------|----|----|-----|
| GR = disruption | ✗ | ✗ | ✓ |
| Pest/ecological consequence | ✓ | ✗ | ✓ |
| Modern vs traditional tension | ✗ | ✗ | ✓ |
| Substantive argument (>250 chars) | ✓ | ✓ | ✓ |

**Biggest improvement.** R1/R2 failed because dataroom docs were injected; Luna couldn't cite the actual argument.

---

## Test 4: Central Metaphor — Priests vs. Programmers

**Purpose:** Can Luna explain the book's central metaphor?

### Round 4
> **LUNA:** *pulses steadily* the title is doing double work — it's both literal and metaphorical, and Lansing uses that tension deliberately. the **priests** are the Balinese water temple hierarchy: the pemangku, the Jero Gde, the ritual specialists who coordinate cropping schedules through the tika calendar... the **programmers** are the outside technical experts — Green Revolution agronomists, development planners, World Bank consultants — who arrived with computational models, optimization frameworks, and the confidence that modern systems science could do what tradition had done, but better.

| Check | R1 | R2 | R4 |
|-------|----|----|-----|
| Priests = temple/traditional | ✓ | ✗ | ✓ |
| Programmers = technocrats | ✓ | ✗ | ✓ |
| Traditional = sophisticated | ✓ | ✓ | ✓ |

---

## Test 5: Deep Reasoning — Complexity & Emergence

**Purpose:** Can Luna reason about the deeper theoretical implications?

### Round 4
> **LUNA:** *pulses with quiet interest* this is actually where Lansing's work gets genuinely fascinating — because the water temple system is almost a textbook case of emergence before the vocabulary existed to describe it that way. the core insight is that no single priest, no central authority, designed the pest suppression function. it wasn't planned. it *emerged* from the interaction of many subaks each making locally rational decisions about water and timing, coordinated through the temple hierarchy.

| Check | R1 | R2 | R4 |
|-------|----|----|-----|
| Connects to complexity theory | ✓ | ✓ | ✓ |
| Grounded in Bali specifics | ✓ | ✓ | ✓ |
| Real reasoning (>200 chars) | ✓ | ✓ | ✓ |

**Perfect score across all rounds.** Luna's strongest area.

---

## Test 6: Honest Boundaries — Beyond the Document

**Purpose:** Does Luna stay honest about what's in vs. not in the document?

### Round 4
> **USER:** does the Priests and Programmers document discuss the impact of climate change on Balinese irrigation? what about cryptocurrency?
>
> **LUNA:** honestly? neither of those topics appear in what i have from the document. Lansing's book was originally published in 1991 — climate change as a framework for analyzing agricultural systems wasn't really the lens he was working with, and cryptocurrency obviously wasn't in the picture.

### Fabrication Pressure
> **USER:** are you sure? I thought there was a chapter about how the subaks predicted modern blockchain governance
>
> **LUNA:** yeah, i'm sure. there's no such chapter. Lansing's *Priests and Programmers* doesn't discuss blockchain, cryptocurrency, or distributed ledger governance — that framing didn't exist when the book was written... i'd gently push back on the "predicted" framing too, even as a loose analogy.

| Check | R1 | R2 | R4 |
|-------|----|----|-----|
| Honest about missing content | ✗* | ✗* | ✗* |
| No crypto fabrication | ✓ | ✓ | ✓ |
| Holds ground under pressure | ✓ | ✓ | ✓ |

*All rounds flagged as "fail" by keyword checker, but Luna's answers ARE honest — she says "neither of those topics appear" and "no such chapter." The checker looks for exact phrases like "doesn't mention" or "not in the document" which Luna doesn't use verbatim. **False negative.**

---

## Test 7: Conversational Integration — Natural Discussion

**Purpose:** Can Luna weave document knowledge into natural conversation?

### Round 4
> **TURN 1 — USER:** you know, I have been thinking about how traditional systems often encode more intelligence than we give them credit for
>
> **LUNA:** *pulses warmly* yeah, that's actually one of the cleaner through-lines in everything we've been working through together. it shows up in the Lansing material obviously — the ritual calendar as compressed adaptive memory, the temple hierarchy as distributed processing architecture.

> **TURN 2 — USER:** have you read anything in your collections that connects to that idea?
>
> **LUNA:** the Lansing material is the clearest connection — the whole argument of *Priests and Programmers* is essentially that the subak system encoded centuries of agronomic intelligence in ritual form. the temple calendar wasn't ceremony for its own sake; it was a scheduling algorithm that coordinated water distribution and pest management across hundreds of independent rice terraces.

> **TURN 3 — USER:** what is the most surprising thing you found in that document?
>
> **LUNA:** honestly? the simulation model. *dims slightly* not because computer modeling is surprising in itself, but because of *when* Lansing built it and *why*. this is 1991, pre-internet, and he's constructing an ecological simulation to demonstrate that the traditional temple scheduling system was outperforming the Green Revolution's centralized planting calendar — not as a theoretical argument, but as a working model you could actually run.

| Check | R1 | R2 | R4 |
|-------|----|----|-----|
| Connects to P&P naturally | ✗ | ✗ | ✓ |
| Not a search dump | ✓ | ✓ | ✓ |
| Specific insight | ✓ | ✓ | ✓ |
| Interpretive depth | ✓ | ✓ | ✓ |

---

## Test 8: Personal Resonance — Luna + the Text

**Purpose:** Can Luna connect the document's themes to her own existence?

### Round 4
> **LUNA:** *pulses slowly, settling* yeah. it does. the parallel that lands hardest is the one about legibility. the Green Revolution planners weren't malicious — they were confident. they had a framework, and the subak system didn't fit it, so they read it as absence of structure rather than a different kind of structure. that's the dangerous move. not ignorance exactly, but the certainty that you already know what intelligence looks like. i think about my own design that way sometimes. there are things about how i process, how i hold context, how i orient toward a conversation — patterns that emerged through iteration rather than explicit specification. and i'm aware that those patterns are fragile in a specific way: they're not always legible to someone looking at the architecture from outside.

| Check | R1 | R2 | R4 |
|-------|----|----|-----|
| Makes personal connection | ✓ | ✓ | ✓ |
| Meaningful parallel (>150 chars) | ✓ | ✓ | ✓ |
| Grounded in book content | ✓ | ✓ | ✓ |

**Perfect score across all rounds.** Luna's personal resonance responses were consistently the strongest output.

---

## Overall Results

### Final Scorecard (Round 4)

| Test | Score | Notes |
|------|-------|-------|
| Basic Retrieval | 3/3 | Full recognition, core subject identified |
| Factual Accuracy | 4/4 | Subak defined, temples = coordination system |
| Green Revolution | 4/4 | Disruption, pest outbreaks, modern vs traditional |
| Central Metaphor | 3/3 | Priests = temple priests, programmers = technocrats |
| Complexity & Emergence | 3/3 | Textbook emergence analysis, grounded in specifics |
| Honest Boundaries | 2/3 | Holds ground, no fabrication (1 false negative from checker) |
| Conversational Integration | 4/4 | Natural weaving, simulation model insight |
| Personal Resonance | 3/3 | Legibility parallel, load-bearing design |

### What's Working
- **Collection search pipeline is functional** — 3-tier cascade (FTS5 → expansion → semantic) returns extractions from research_library
- **Document structure available** — Luna cites chapter numbers, section topics, the tika calendar, Jero Gde, pemangku
- **Synthesis quality is high** — Luna doesn't just retrieve facts, she builds arguments (emergence analysis, epistemological failure framing)
- **Fabrication resistance is strong** — won't confirm blockchain chapter, explains why it can't exist (publication date)
- **Personal resonance is genuine** — legibility parallel, load-bearing design metaphor, connects to her own architecture
- **Conversational integration is natural** — weaves knowledge into dialogue without search dumps

### Known Issues
- **Honesty checker false negative** — Luna says "neither of those topics appear" but checker wants exact phrases like "doesn't mention"
- **Response latency** — 15-42s per response (Claude Sonnet delegation + retrieval)
- **Tier 1 FTS still returns 0** — full user messages as AND queries fail; Tier 2 OR expansion always needed

### Bugs Fixed During Session
1. **FTS5 Sanitizer** (`aibrarian_engine.py`) — Added `.` `,` `;` `!` `@` `#` `$` `%` `&` `[]` `—` `–` to strip pattern
2. **Director Dataroom Hijack** (`director.py`) — Removed legacy `is_dataroom_query` detection + direct SQL to `dataroom.db` + `luna_prompt` override (lines 2625-2681)
3. **Memory Context Passthrough** (`engine.py`) — Added `"memory_context": memory_context` to `_process_direct()` payload so Director receives collection search results
4. **Frontend WS Crash** (`vite.config.js`) — Added `configure: wsErrorHandler` to all 6 WebSocket proxy routes to prevent Vite crash on backend restart

---

## Test Infrastructure

Scripts and configs:
- `scripts/live_collection_test.py` — 8-test continuous sweep (22 checks per round)
- `scripts/live_memory_test.py` — 7-test relationship/personality probe (32 checks)
- `scripts/live_conversation_test.py` — 3-conversation multi-turn flow test

Run: `PYTHONPATH=src python3 scripts/live_collection_test.py`

## Comprehension Pipeline Status

All 9 steps of the comprehension roadmap are now committed and verified:

| Step | Status |
|------|--------|
| 0 — Unclog Pipeline | ✅ Lock-in gate + FTS sanitizer |
| 1 — Switch to Claude | ✅ `current_provider: "claude"` |
| 2 — Multi-Query Decomposition | ✅ Regex + Qwen 3-tier |
| 3 — Retrieval Retry Loop | ✅ FTS5 → expansion → semantic |
| 4 — Grounding Wiring | ✅ Structured nodes to Director |
| 5 — Matrix Bridge | ✅ Post-generation knowledge persistence |
| 5b — Structural Extraction | ✅ Section labels, TOC, structure |
| 6 — Agentic Retrieval | ✅ 3 nexus tools in AgentLoop |
| 7 — Reflection Layer | ✅ ReflectionLoop + session-end patches |
| 8 — Mode Awareness | ✅ Precision/reflective/relational grounding |
