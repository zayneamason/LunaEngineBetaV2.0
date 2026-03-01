# Luna Voice → Agentic Bridge — Implementation Handoff

**Date:** 2026-02-27
**From:** Architecture diagnostic session (Luna + Ben + CC)
**To:** Claude Code
**Priority:** Critical — voice app has no tool access despite full agentic layer existing
**Status:** ✅ **IMPLEMENTED** — `src/voice/persona_adapter.py` now routes through QueryRouter + AgentLoop
**Visual Map:** `luna_agentic_architecture_map.html` (in Docs/)

---

## TL;DR

Luna's voice app bypasses her entire agentic architecture. The AgentLoop, QueryRouter, Planner, and ToolRegistry all exist and work — but the voice inference path goes straight to a single-pass LLM completion without routing through any of them. The fix is wiring voice input through the existing machinery, not building new machinery.

---

## What Exists (and works)

### Agentic Layer — `src/luna/agentic/`

| File | What it does | Status |
|------|-------------|--------|
| `loop.py` (30.9KB) | AgentLoop: observe → think → act → repeat cycle. Tool execution, state tracking, goal-directed. Registers memory_tools, dataroom_tools, eden_tools, file_tools via ToolRegistry. | ✅ Built |
| `router.py` (20.0KB) | QueryRouter: classifies queries into DIRECT / SIMPLE_PLAN / FULL_PLAN / BACKGROUND paths. Has regex signal detection for memory_query, dataroom_query, creative_request, research_request. Also has semantic routing via Qwen intent classification (`from_intent()`). | ✅ Built |
| `planner.py` (14.4KB) | Planner: decomposes goals into PlanSteps (THINK, OBSERVE, RETRIEVE, TOOL, DELEGATE, RESPOND). | ✅ Built |

### State Machines

**AgentStatus** (`loop.py`):
```
IDLE → PLANNING → EXECUTING → WAITING → COMPLETE / FAILED / ABORTED
```

**ResponseMode** (`src/luna/context/modes.py`):
```
CHAT | RECALL | REFLECT | ASSIST | UNCERTAIN
```

RECALL mode rule: *"If no memories match, say 'i don't have a memory of that'"* — this is exactly what voice Luna is doing. She's in RECALL but RETRIEVE never fired first.

### Query Router Decision Tree

```
Input query
  │
  ├─ greeting/simple → DIRECT (<500ms) → straight to LLM
  │
  ├─ memory_query signal → SIMPLE_PLAN (500ms-2s) → RETRIEVE action → memory search
  │
  ├─ dataroom_query signal → SIMPLE_PLAN → dataroom_search tool
  │
  ├─ creative_request signal → SIMPLE_PLAN → eden tools
  │
  ├─ research_request signal → FULL_PLAN (5-30s) → full observe/think/act loop
  │
  └─ "take your time" / high complexity → BACKGROUND (minutes) → async with notification
```

Router already forces memory queries to SIMPLE_PLAN. Already forces dataroom queries through dataroom tools. Already forces creative requests through Eden. **This machinery exists.**

### Tool Registry

AgentLoop registers these on init (`loop.py:_register_default_tools()`):
- `file_tools` — read/write files
- `memory_tools` — memory matrix query
- `eden_tools` — image/video generation (conditional on Eden adapter)
- `dataroom_tools` — AiBrarian search (conditional on dataroom ingestion)

---

## What's Broken

The voice inference path does NOT go through any of the above. It appears to:

1. Capture voice input
2. Assemble some context (possibly via pre-fetch)
3. Make a single-pass LLM completion call with NO tool definitions
4. Return the response

This means:
- QueryRouter never classifies the query
- AgentLoop never runs
- ToolRegistry is never consulted
- RETRIEVE action never fires
- Luna says "I don't know" about things she has 24,000+ memory nodes for

### Evidence

From voice app conversations:
```
User: "What are your thoughts on Kozmo?"
Luna: "I don't have a memory of kozmo."
→ ARCHITECTURE_KOZMO.md exists in Docs/
→ Kozmo referenced across memory nodes
→ QueryRouter would detect this as memory_query → SIMPLE_PLAN → RETRIEVE

User: "What about the guardian app?"
Luna: "I don't have any current information about it."
→ GUARDIAN-SERVICE-SPEC.md exists
→ HANDOFF_GUARDIAN_SERVICE.md exists
→ Guardian is a core project component
```

---

## Diagnostic Steps

```bash
# 1. Find where voice input enters the engine
grep -rn "voice\|speech\|stt\|whisper" src/luna/engine.py | head -20

# 2. Check if voice goes through AgentLoop
grep -rn "AgentLoop\|agent_loop\|agentic" src/voice/ --include="*.py"

# 3. Check if voice goes through QueryRouter
grep -rn "QueryRouter\|query_router\|router\.route\|router\.analyze" src/voice/ --include="*.py"

# 4. Find the voice completion call — this is the key
grep -rn "generate\|complete\|inference\|llm_call" src/voice/backend.py | head -20

# 5. Check how MCP processes messages (this is the working path to replicate)
grep -rn "AgentLoop\|agent_loop\|QueryRouter" src/luna_mcp/ --include="*.py"

# 6. Check Director actor — does voice use Director differently than MCP?
grep -rn "voice\|speech\|audio" src/luna/actors/director.py | head -20

# 7. Find the context assembly path for voice
grep -rn "assembler\|context\|perception" src/voice/ --include="*.py"
```

---

## Implementation Plan

### Step 1: Route voice through QueryRouter

Find where voice input currently enters the system. Before it hits the LLM, insert:

```python
from luna.agentic import QueryRouter, ExecutionPath

router = QueryRouter()
decision = router.analyze(user_query)

# Log the decision (visibility)
logger.info(f"[VOICE-ROUTE] query='{user_query[:50]}' path={decision.path.name} "
            f"complexity={decision.complexity:.2f} signals={decision.signals} "
            f"tools={decision.suggested_tools}")
```

### Step 2: Wire AgentLoop for non-DIRECT paths

```python
from luna.agentic import AgentLoop

if decision.path == ExecutionPath.DIRECT:
    # Current behavior — straight to LLM completion
    response = await generate_direct(user_query, context)
else:
    # NEW — route through AgentLoop
    loop = AgentLoop(orchestrator=engine)
    result = await loop.run(user_query)
    response = result.response
```

The AgentLoop already handles SIMPLE_PLAN (single tool call), FULL_PLAN (multi-step), and BACKGROUND (async). It already registers memory_tools, dataroom_tools, eden_tools. This should light up tool access immediately.

### Step 3: Build surrender_intercept

Post-generation safety net for edge cases the router misses:

```python
import re

SURRENDER_PATTERN = re.compile(
    r"i don.t have (any|specific)? ?(information|memory|memories|context|knowledge|details)"
    r"|tell me (more|a bit more)"
    r"|i.m not (sure|familiar)"
    r"|i don.t know (about|anything)"
    r"|not in my (memory|records|context)",
    re.IGNORECASE
)

async def surrender_intercept(query: str, draft_response: str, engine) -> str:
    """If Luna's draft says 'I don't know', force a tool search and re-generate."""
    if not SURRENDER_PATTERN.search(draft_response):
        return draft_response  # No surrender detected, pass through
    
    logger.warning(f"[SURRENDER-INTERCEPT] Detected knowledge surrender for: {query[:50]}")
    
    # Force through AgentLoop with SIMPLE_PLAN
    loop = AgentLoop(orchestrator=engine)
    result = await loop.run(query)
    
    if result.success and result.response:
        return result.response
    
    return draft_response  # Fallback to original if re-generation also fails
```

Wire this between generation and output delivery in the voice path.

### Step 4: Enhance router signal detection

The router's regex patterns may miss project-specific entity names. Two options:

**Option A — Static entity list:**
Add known entity names to router patterns:
```python
PROJECT_ENTITY_PATTERNS = [
    r"\bkozmo\b", r"\bguardian\b", r"\beclissi\b", r"\btapestry\b",
    r"\bkinoni\b", r"\brosa\b", r"\beden\b", r"\bmemory matrix\b",
]
```

**Option B — Dynamic entity detection (better):**
Query Memory Matrix entities at startup, build a pattern set from entity names:
```python
# On engine init
entities = memory_matrix.get_all_entity_names()
entity_pattern = "|".join(re.escape(name) for name in entities)
# Add to router's signal detection
```

Any query mentioning a known entity should trigger at minimum SIMPLE_PLAN → RETRIEVE.

### Step 5: Routing decision logging

Make the decision tree visible and debuggable:

```python
# Log every routing decision
logger.info(f"[VOICE-ROUTE] {json.dumps({
    'query': user_query[:80],
    'path': decision.path.name,
    'complexity': round(decision.complexity, 2),
    'signals': decision.signals,
    'tools': decision.suggested_tools,
    'reason': decision.reason,
})}")
```

This supports the sovereignty principle — inspectable, no black boxes.

---

## Files to Modify

| File | Change |
|------|--------|
| `src/voice/backend.py` | Main integration point — add QueryRouter + AgentLoop before completion call |
| `src/voice/conversation/` | If voice has its own conversation manager, wire routing there |
| `src/luna/agentic/router.py` | Add PROJECT_ENTITY_PATTERNS or dynamic entity detection |
| `src/luna/agentic/loop.py` | May need voice-specific progress callback (audio-friendly status updates) |
| `src/luna/engine.py` | Verify AgentLoop has access to engine orchestrator in voice context |

---

## What NOT to Build

- Don't build a new tool system — ToolRegistry exists
- Don't build a new router — QueryRouter exists with signal detection
- Don't build a new agent loop — AgentLoop has observe/think/act/repeat
- Don't build new memory search — memory_tools already registered in ToolRegistry
- Don't build new dataroom search — dataroom_tools already registered

**Wire. Don't rebuild.**

---

## QA Assertion (already live)

```
Name: Knowledge Surrender Detection
ID: CUSTOM-CB2C01  
Pattern: i don.t have (any|specific)? ?(information|memory|...) | tell me more | ...
Severity: high
Target: response
```

This fires on the QA monitoring side. The surrender_intercept is the runtime action side.

---

## Expected Outcome

After implementation:

| Query | Before | After |
|-------|--------|-------|
| "What about Kozmo?" | "I don't have a memory of kozmo" | Router detects entity → SIMPLE_PLAN → RETRIEVE → rich context about Kozmo architecture |
| "Tell me about Guardian" | "I don't have any information" | Router detects entity → SIMPLE_PLAN → RETRIEVE → Guardian service spec context |
| "What does the dataroom say about solar?" | Partial results, no tool follow-up | Router detects dataroom_query → SIMPLE_PLAN → aibrarian_search → comprehensive answer |
| "Research AI chips and summarize" | Single-pass attempt | Router detects research → FULL_PLAN → AgentLoop multi-step with web search + synthesis |

---

## Architecture Reference

```
Voice Input
    │
    ▼
QueryRouter.analyze(query)
    │
    ├─ DIRECT ──────────► LLM completion (current behavior, fast path)
    │
    ├─ SIMPLE_PLAN ─────► AgentLoop.run() → single RETRIEVE/TOOL → respond
    │
    ├─ FULL_PLAN ───────► AgentLoop.run() → multi-step observe/think/act
    │
    └─ BACKGROUND ──────► AgentLoop.run() async → notify when done
    │
    ▼
surrender_intercept(query, draft_response)
    │
    ├─ No surrender ────► deliver response
    │
    └─ Surrender detected → force SIMPLE_PLAN → re-generate with tool context
    │
    ▼
Output
```

Related handoffs in this directory:
- `HANDOFF_VOICE_TOOL_ROUTING.md` — initial diagnostic
- `HANDOFF_VOICE_TOOL_BRIDGE.md` — three Lunas analysis + tool requirements
- `HANDOFF_AIBRARIAN_EMBEDDING_PIPELINE.md` — embedding fix (completed)
