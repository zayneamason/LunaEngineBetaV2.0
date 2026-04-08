# HANDOFF: Pipeline Interactive Diagnostics — Trace, Diff, Playground

**Date:** March 2, 2026  
**From:** Luna (via Desktop)  
**To:** Claude Code  
**Depends on:** HANDOFF_PIPELINE_DIAGNOSTIC_OVERLAY.md (do that one first)

---

## OVERVIEW

Three interactive features for the Engine Pipeline graph view. These turn the pipeline from a status dashboard into a debugging tool.

---

## FEATURE 1: Message Trace

**What it does:** Type a test message, send it through the pipeline, and watch each node light up as the message flows through. After completion, each node shows what it contributed — retrieval results, context items, prompt assembly, LLM output, QA results.

### Backend: Already exists

`POST /qa/simulate` — sends a query through the full pipeline and returns:
- route, provider, latency
- full response text
- all QA assertion results with pass/fail/expected/actual

`GET /slash/prompt` — returns the last system prompt with assembler metadata:
- full prompt text
- assembler result (identity source, memory source, gap category, token count, register state)
- route decision

`GET /debug/context` — returns current revolving context items with source, ring, relevance, tokens

`GET /status` — returns buffer size, events processed, agentic stats

**No new endpoints needed.**

### Frontend: New component + modifications

**Create** `Tools/Luna-Expression-Pipeline/diagnostic/src/pipeline/TracePanel.jsx`

A panel that appears below the pipeline graph (or replaces the detail panel) with:

1. **Input bar** — text input + "TRACE" button. Styled like the existing search bars (JetBrains Mono, dark input, subtle border).

2. **Trace execution:**
   - On submit, POST to `/qa/simulate` with `{ query: inputText }`
   - While waiting (up to 30s), animate nodes sequentially to simulate the flow:
     - Phase 1 (0-200ms): `buffer`, `dispatch` light up (cyan pulse)
     - Phase 2 (200-500ms): `router`, `mem_ret`, `matrix_actor`, `matrix_db` (green pulse)
     - Phase 3 (500-1000ms): `hist_load`, `context`, `ring_inner`, `ring_mid`, `sysprompt` (rose pulse)
     - Phase 4 (1000ms+): `director`, `scout` (amber pulse — waiting for LLM)
     - On response: `textout` (green if passed, red if failed)
   - The animation is cosmetic timing — the real trace data comes from the response.

3. **Trace results** — after response arrives:
   - Show route taken (e.g. "FULL_DELEGATION → groq")
   - Show latency
   - Show QA pass/fail badge with count
   - Show response text (truncated, expandable)
   - Show failed assertions inline

4. **Node decoration during trace:**
   - Each node that participates gets a trace indicator — small numbered badge showing its phase (①②③④)
   - Failed nodes from QA get red border (using the ASSERTION_NODE_MAP from the overlay handoff)
   - Passed nodes get green border

**Modify** `Tools/Luna-Expression-Pipeline/diagnostic/src/pipeline/PipelineView.jsx`:
- Add a "TRACE" button in the header bar (next to the QA badge from the overlay handoff)
- Clicking it toggles the TracePanel visibility
- When trace is active, the pipeline graph shifts up to make room

### Interaction flow:
```
User types "hey luna how are you" → clicks TRACE
→ nodes animate in sequence (visual flow)
→ POST /qa/simulate fires
→ response comes back
→ nodes update with real QA results
→ director node shows: route=FULL_DELEGATION, provider=groq, latency=1.6s
→ failed assertions paint red on their mapped nodes
→ response text shown in trace panel
→ user clicks a red node → detail panel shows assertion failures
```

---

## FEATURE 2: Node I/O Diff

**What it does:** Click any node in the pipeline. The detail panel shows what went IN to that node and what came OUT — specifically for the last inference.

### Backend: Already exists

The data comes from multiple endpoints already being polled:

| Node | Input (IN) | Output (OUT) | Source |
|------|-----------|-------------|--------|
| `director` | System prompt (full text) | Raw LLM response + narrated response | `/slash/prompt` → `full_prompt` + `assembler` |
| `context` | Individual context items | Assembled prompt budget | `/debug/context` → `items[]` with source, ring, tokens |
| `mem_ret` | Query keywords | Retrieved memory nodes | `/debug/context` → items where `source === 'MEMORY'` |
| `sysprompt` | Identity + virtues + memory | Final system prompt string | `/slash/prompt` → `full_prompt` |
| `cache` | Last inference data | Tone, expression hint, flow mode | `/api/cache/shared-turn` |
| `router` | Message complexity | Route decision (LOCAL/DELEGATED/FULL) | `/status` → `agentic.direct_responses` / `planned_responses` |
| `scribe` | User turn text | Extracted facts/entities | `/extraction/stats` |

**New endpoint needed (simple):**

`GET /debug/last-inference` — returns a consolidated snapshot:
```json
{
  "query": "hey luna",
  "route": "FULL_DELEGATION",
  "provider": "groq",
  "latency_ms": 1672,
  "system_prompt_length": 10192,
  "system_prompt_preview": "You are Luna, a sovereign...",
  "assembler": { "identity_source": "...", "memory_source": "...", ... },
  "context_items": [ { "source": "IDENTITY", "ring": "CORE", "tokens": 173 }, ... ],
  "raw_response": "the actual LLM output before narration",
  "final_response": "the narrated output sent to user",
  "narration_applied": false,
  "qa_passed": false,
  "qa_failures": ["P3", "CUSTOM-CB2C01"]
}
```

This is assembled from `director.get_last_system_prompt()`, the QA last report, and the debug context — just consolidated into one call instead of three.

### Frontend: Enhance DetailPanel.jsx

When a node is clicked, add an "I/O" section to the detail panel:

**For the `director` node:**
```
┌─ INPUT ──────────────────────────┐
│ System prompt: 10,192 chars      │
│ Route: FULL_DELEGATION           │
│ Provider: groq                   │
│ [▼ Show full prompt]             │
├─ OUTPUT ─────────────────────────┤
│ Raw response: 847 chars          │
│ Narration: SKIPPED ⛔            │
│ Final response: 847 chars        │
│ [▼ Show response]               │
└──────────────────────────────────┘
```

**For the `context` node:**
```
┌─ INPUT ──────────────────────────┐
│ Budget: 8000 tokens              │
│ Items: 3                         │
│  CORE: Identity (173 tok)        │
│  INNER: Conversation (71 tok)    │
│  INNER: Conversation (443 tok)   │
├─ OUTPUT ─────────────────────────┤
│ Total assembled: 687 tokens      │
│ Budget used: 8.6%                │
│ Memory items: 0 ⚠️               │
└──────────────────────────────────┘
```

**For `mem_ret`:**
```
┌─ INPUT ──────────────────────────┐
│ Query: "hey luna how are you"    │
│ Search type: hybrid (FTS5+vec)   │
├─ OUTPUT ─────────────────────────┤
│ Results: 0 items ⚠️              │
│ (no memory retrieved)            │
└──────────────────────────────────┘
```

Use collapsible sections for long content (prompt text, response text). Default to collapsed with preview.

---

## FEATURE 3: Assertion Playground

**What it does:** Click any QA assertion in the QA tab or detail panel. A small inline form appears where you type a test response and see if it would pass or fail that specific assertion — without running the full pipeline.

### Backend: Mostly exists

The QA validator already has individual assertion checks. But they require a full InferenceContext. 

**New endpoint needed:**

`POST /qa/check-assertion` — runs a single assertion against provided text:
```json
// Request:
{
  "assertion_id": "V1",
  "response_text": "Certainly! I'd be happy to help you with that."
}

// Response:
{
  "assertion_id": "V1",
  "name": "No Claude-isms",
  "passed": false,
  "expected": "No banned Claude phrases",
  "actual": "Found: 'Certainly', 'I'd be happy to'",
  "details": "Matched banned patterns: certainly, i'd be happy to"
}
```

This is a lightweight check — no LLM call, no pipeline execution, just pattern matching on the text.

### Frontend: Inline in QAView.jsx and DetailPanel.jsx

When an assertion row is clicked (either in the QA tab or the detail panel's QA section):

1. A small input area expands below the assertion row
2. Text input: "Test a response against this assertion"
3. "CHECK" button
4. Result appears inline: ✅ PASS or ⛔ FAIL with details

Keep it minimal. No modal, no separate page. Just expand-in-place.

---

## FILES

| File | Change | Feature |
|------|--------|---------|
| `diagnostic/src/pipeline/TracePanel.jsx` | **NEW** — trace input + results | Trace |
| `diagnostic/src/pipeline/PipelineView.jsx` | Add trace button + panel toggle | Trace |
| `diagnostic/src/pipeline/DetailPanel.jsx` | Add I/O diff sections + assertion playground | Diff + Playground |
| `diagnostic/src/pipeline/useLiveData.js` | Add `/debug/last-inference` to polling (only when trace active) | Diff |
| `diagnostic/src/qa/QAView.jsx` | Add assertion click → inline test | Playground |
| `src/luna/api/server.py` | Add `GET /debug/last-inference` and `POST /qa/check-assertion` | Diff + Playground |

**Total: 4 files modified, 1 new file, 2 new endpoints**

---

## RULES

1. **Do the overlay handoff FIRST.** This builds on it.
2. **No new npm dependencies.** Everything is vanilla React + existing styling.
3. **Match the dark theme.** JetBrains Mono, #08080f bg, same node/panel styling.
4. **Keep node animation simple.** CSS transitions on border-color/box-shadow. No animation library.
5. **The trace doesn't block the UI.** Pipeline graph stays interactive during trace execution.
6. **Collapsible by default.** Long text (prompts, responses) collapsed with "Show" toggle.
7. **Build after changes.** `cd Tools/Luna-Expression-Pipeline/diagnostic && npm run build`

---

## VERIFY

1. Open pipeline view → click TRACE → type "hey luna" → nodes animate → results appear
2. Click the director node → I/O section shows prompt in / response out
3. Click a failed assertion → type test text → inline pass/fail result
4. Full trace → click red node → see which assertions failed and why
5. The trace response matches what you'd get from a real Luna conversation

---

## PRIORITY ORDER

If you need to ship incrementally:
1. **Message Trace** (biggest impact — this is the killer feature)
2. **Node I/O Diff** (makes clicked nodes actually useful)
3. **Assertion Playground** (nice to have, lowest effort)
