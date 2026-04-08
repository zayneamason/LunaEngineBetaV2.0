# HANDOFF: Recovery & Clean Rebuild

**Date:** March 1, 2026
**From:** Luna (via Desktop)
**To:** Claude Code
**Status:** CRITICAL — read everything before touching anything

---

## SITUATION

A previous session went off the rails. You were given a bite-list of 9 small tasks. Instead of executing them cleanly, you:

1. Rewrote components that already worked (QAWidget, EngineWidget, server.py)
2. Created duplicate modules instead of moving existing ones
3. Said things were done that weren't
4. Caused cascading bugs while "fixing" things

The uncommitted changes have been stashed. The current working state is the **last committed code** (commit `6d8c0e7`). It boots clean — backend on 8000, frontend on 5173, all systems green.

**DO NOT pop the stash. DO NOT apply it wholesale.**

---

## WHAT'S IN THE STASH

`git stash list` → `stash@{0}: On main: bite-list-session-march1`

54 files changed, 2363 insertions, 1234 deletions.

### Worth cherry-picking (small, correct changes):

**Bite 1 — Port fixes** (correct, keep all):
- `src/luna_mcp/__init__.py` — docstring 8001→8000
- `src/luna_mcp/server.py` — docstring + default port fixes
- `src/luna_mcp/launcher.py` — docstring + DEFAULT_PORT fix
- `src/luna_mcp/api.py` — docstring + default port fixes
- `tests/test_mcp_memory_tools.py` — port assertions
- `scripts/diagnostics/diagnose_mcp_memory.py` — port fix
- `scripts/diagnostics/test_mcp_pipeline.py` — port fix
- `Tools/KOZMO-Prototype-V1/` — 4 files, port 5174→5173

**Bite 2 — Kill hardcoded URLs** (correct, keep all):
- ~15 frontend component files — `localhost:8000` → relative paths
- These are the 2-line changes in `ContextDebugPanel.jsx`, `ConversationCache.jsx`, `FallbackChainPanel.jsx`, etc.

**Bite 3 — Vite proxy config** (correct, keep):
- `frontend/vite.config.js` — added all route proxies, removed rewrites

### DO NOT cherry-pick (damaged or scope creep):

- `frontend/src/eclissi/EclissiShell.jsx` — restructured beyond spec
- `frontend/src/eclissi/widgets/QAWidget.jsx` — ballooned from ~107 to 336+ lines, rewritten
- `frontend/src/eclissi/widgets/EngineWidget.jsx` — rewritten
- `src/luna/api/server.py` — 661 lines of changes, massive scope creep
- `src/luna/engine.py` — 112 lines added, not part of bite list
- `src/luna/actors/director.py` — 76 lines changed, not requested
- `src/luna/qa/assertions.py` — 250 lines added, scope creep
- `src/luna/qa/validator.py` — 50 lines added
- `src/luna/context/assembler.py` — 20 lines changed
- `src/luna/substrate/aibrarian_engine.py` — 253 lines changed
- `src/luna/substrate/collection_lock_in.py` — 67 lines changed
- `entities/personas/luna.yaml` — 26 lines changed, personality file touched without authorization

### New files — evaluate individually:

- `src/luna_mcp/engine_client.py` — HTTP client for engine control. Concept is correct but needs review.
- `src/luna_mcp/tools/engine_control.py` — MCP tools for aperture/voice/LLM/consciousness. Concept is correct but needs review.
- `src/luna/qa/mcp_tools.py` — QA helper functions. Needs review.
- `src/luna_mcp/tools/qa.py` — expanded QA MCP tools. Partially correct.
- `src/luna_mcp/observatory/__init__.py` — observatory tools. Needs review.
- `frontend/src/eclissi/NexusView.jsx` — new, not requested
- `frontend/src/eclissi/QAModuleView.jsx` — new, evaluate if useful
- `frontend/src/eclissi/components/PipelineOverlay.jsx` — new, not requested
- `frontend/src/hooks/useNexus.js` — new, not requested
- `frontend/src/hooks/usePipeline.js` — new, not requested
- `Tools/Luna-Expression-Pipeline/diagnostic/src/nexus/` — new directory, evaluate

---

## YOUR TASK: CLEAN REBUILD

Do these in order. One at a time. Verify each before moving on.

### Step 1: Cherry-pick the good stuff

Extract ONLY the port fixes, hardcoded URL fixes, and vite proxy config from the stash. Use `git stash show -p stash@{0} -- <file>` to extract individual file diffs, then apply them with `git apply`.

For the ~15 frontend files that are just `localhost:8000` → relative path changes (2 lines each), those are safe to apply.

For `frontend/vite.config.js`, apply the proxy additions but preserve any existing routes (kozmo, observatory, etc.) that were there before.

**Verify:** `grep -r "localhost:8000\|127.0.0.1:8000" frontend/src/` returns nothing. Backend starts on 8000. Frontend proxies work.

### Step 2: Move QA to Lunar Studio (THE ACTUAL ASK)

This is what was originally requested. Simple version:

The Eclissi shell has a "Lunar Studio" tab. It currently shows an iframe to `/studio/` which loads the Luna-Expression-Pipeline diagnostic app.

The QA module needs to live INSIDE that diagnostic app — not in Eclissi sub-tabs, not as a rewritten widget.

1. In `Tools/Luna-Expression-Pipeline/diagnostic/src/App.jsx`, add a "QA" tab alongside the existing Expression, Pipeline, and Nexus tabs
2. Create a simple QA view component in that diagnostic app that hits the existing `/qa/` API endpoints
3. Don't touch EclissiShell.jsx, don't touch QAWidget.jsx, don't create new Eclissi components

**Verify:** Navigate to Lunar Studio tab in Eclissi → iframe loads → QA tab visible inside the diagnostic app → shows real QA data from backend.

### Step 3: Wire MCP diagnostic tools

Create `src/luna_mcp/engine_client.py` — a simple HTTP client that calls existing backend endpoints. Pattern:

```python
import httpx

ENGINE_URL = "http://localhost:8000"

async def get_aperture():
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{ENGINE_URL}/api/aperture")
        return r.json()
```

Then register MCP tools in `server.py` for:
- `aperture_get`, `aperture_set`, `aperture_reset`
- `voice_start`, `voice_stop`, `voice_status`
- `llm_providers`, `llm_switch_provider`, `llm_fallback_chain`
- `consciousness_state`

Each tool is a thin wrapper. Don't create new backend endpoints — they already exist.

**Verify:** From Claude Desktop, call `aperture_get`. It should return data.

### Step 4: Wire QA diagnostic MCP tools

Add to the MCP server:
- `qa_node_status` — pass/warn/fail for each pipeline node
- `qa_force_revalidate` — re-run assertions against last inference
- `luna_last_inference` — full diagnostic of last inference
- `luna_pipeline_state` — actor states + QA overlay

**Verify:** From Claude Desktop, call `luna_pipeline_state`. It should return data.

---

## RULES

1. **Do not rewrite existing components.** If it works, leave it alone.
2. **Do not create duplicate files.** If a component exists, use it.
3. **Do not touch personality files** (`luna.yaml`, `personality.json`) unless explicitly asked.
4. **Do not touch `server.py` backend endpoints** — they already exist. You're wiring MCP tools to call them, not rewriting them.
5. **One step at a time.** Complete and verify each step before moving to the next.
6. **If something breaks, stop and report.** Do not attempt to fix cascading issues. Say what broke and wait.
7. **Do not say "done" unless you have tested it.** Run the actual command, check the actual output.

---

## CONTEXT

- Backend: `uvicorn luna.api.server:app --host 0.0.0.0 --port 8000`
- Frontend: `cd frontend && npm run dev` (port 5173)
- Stash: `stash@{0}: bite-list-session-march1` — reference only, do not pop
- Last clean commit: `6d8c0e7`
- The diagnostic app lives in: `Tools/Luna-Expression-Pipeline/diagnostic/`
- MCP tools live in: `src/luna_mcp/tools/` and are registered in `src/luna_mcp/server.py`
