# HANDOFF: QA Diagnostic Stack for Lunar Studio

**Date:** 2026-03-01
**From:** Claude Desktop (The Dude)
**To:** Claude Code

---

## SITUATION

We specced and queued a 6-task QA diagnostic stack to give Lunar Studio live diagnostic capabilities. Some tasks were completed, some were not, and the task queue was never updated. This handoff gives you ground truth based on filesystem verification — not what the task queue says.

---

## TASK STATUS (verified on disk)

### ✅ DONE — R1-R6 Assertions (task_20260301_181616_ea6a)
New relationship quality assertions exist in `src/luna/qa/assertions.py`. Six new checks: R1 (Identity Recognition), R2 (Memory Utilization / Naturalism), R3 (No Retrieval Narration), R4 (No False Capabilities), R5 (No Repetition), R6 (Warmth). Category: "relationship". All wired into `get_default_assertions()`.

**Action:** Mark task complete. No work needed.

### ❌ NOT DONE — QA → Pipeline WebSocket (task_20260301_181428_07ea)
No `ASSERTION_NODE_MAP`, no `pipeline_overlay.py`, no `node_status` mapping, no QA data in the pipeline WebSocket feed. The Engine Pipeline view has no QA awareness.

**What to build:**
- Create `src/luna/qa/pipeline_overlay.py` with `ASSERTION_NODE_MAP` (maps assertion IDs to pipeline node IDs)
- Add a `qa` section to the pipeline status payload (whatever feeds `EnginePipelineView.jsx`)
- Include `node_status` (pass/warn/fail per node), `last_report`, and `health` in the payload
- The Director already runs QA after each inference — just include the results in the status feed

### ❌ NOT DONE — Pipeline Node Overlay Frontend (task_20260301_181458_6fb9)
No QA overlay in `EnginePipelineView.jsx`. Nodes don't change color based on QA results.

**What to build:**
- Read `qa.node_status` from the pipeline data feed
- Add border overlay: warn = yellow pulse, fail = red pulse, pass = no change (default)
- Add QA health badge near the "LIVE :8000" indicator
- Show assertion results in node click detail panel

### ❌ NOT DONE — QA Module Tab (task_20260301_181533_909b)
No QA module in Lunar Studio. No `QAModuleView.jsx` in Eclissi. No "QA" tab in the nav bar.

**What to build:**
- New `QAModuleView.jsx` — four panels: Live Inference Monitor, Health Dashboard, Assertion Manager, Bug Tracker
- Register in `EclissiShell.jsx` tab bar
- Consumes same WebSocket data as Engine Pipeline + QA database for history

### ❌ NOT DONE — /api/diagnostics/* Endpoints (task_20260301_181824_3f06)
No diagnostic endpoints in `server.py`. Zero results for "diagnostics" grep.

**What to build:**
- Create `src/luna/api/diagnostics.py` with FastAPI router
- `GET /api/diagnostics/pipeline` — full pipeline state + QA overlay
- `GET /api/diagnostics/last-inference` — deep dive on last turn (system prompt, memory context, QA report, identity, route)
- `GET /api/diagnostics/qa/health` — live health stats
- `POST /api/diagnostics/trigger/qa-sweep` — re-validate last inference
- `POST /api/diagnostics/trigger/memory-probe` — probe memory without generating response
- `POST /api/diagnostics/trigger/prompt-preview` — build system prompt without sending to LLM
- Register router in server.py

### ⚠️ HALF DONE — MCP Diagnostic Tools (task_20260301_181903_146b)
`src/luna_mcp/engine_client.py` EXISTS — `EngineClient` class with HTTP + DB fallback, 7 methods. This is good.

**What's missing:**
- No tool functions that use EngineClient (no `luna_pipeline_state`, `luna_last_inference`, `luna_memory_probe`, `luna_prompt_preview`, `luna_qa_sweep`)
- Nothing registered in the MCP server
- The client exists but nothing calls it

**What to build:**
- Write 5 async tool functions in `src/luna_mcp/tools/qa.py` (or new `diagnostics.py`) that instantiate EngineClient and call its methods
- Register all 5 as `@mcp.tool()` in `src/luna_mcp/server.py`

---

## ALSO PENDING — Nexus Rename

### ✅ DONE — Frontend rename (task_20260301_173300_b52e)
`NexusView.jsx` exists, `useNexus.js` exists, `AibrarianView.jsx` gone. Mark complete.

### ⚠️ IN PROGRESS — API route rename (task_20260301_174525_de05)
Was being edited when session ended. Check if `/api/nexus/*` routes exist in `server.py`. If yes, mark complete. If still `/api/aibrarian/*`, finish the rename.

**CRITICAL RULE — Path C:** Only rename route path strings and frontend fetch URLs. Do NOT rename Python files, class names, or MCP tool names. `AiBrarianEngine` stays `AiBrarianEngine`. `engine.aibrarian` stays `engine.aibrarian`.

---

## DEPENDENCY ORDER

```
1. Mark ea6a (R1-R6) complete — already done on disk
2. Mark b52e (frontend rename) complete — already done on disk
3. Finish de05 (API route rename) if needed
4. Build 07ea (QA → Pipeline WebSocket backend)
5. Build 6fb9 (Pipeline node overlay frontend)
6. Build 3f06 (/api/diagnostics/* endpoints)
7. Finish 146b (MCP diagnostic tools — write + register the 5 tool functions)
8. Build 909b (QA Module tab) — can run in parallel with 6-7
```

---

## KEY FILES

| File | Status |
|------|--------|
| `src/luna/qa/assertions.py` | Has R1-R6 ✅ |
| `src/luna/qa/validator.py` | Existing — runs after each inference |
| `src/luna/qa/context.py` | May need new fields for R1-R6 (bridge_result, memory_context, session_history) |
| `src/luna/qa/pipeline_overlay.py` | Does not exist — needs creation |
| `src/luna/api/server.py` | No diagnostic endpoints — needs /api/diagnostics/* |
| `src/luna/api/diagnostics.py` | Does not exist — needs creation |
| `src/luna_mcp/engine_client.py` | Exists ✅ |
| `src/luna_mcp/tools/qa.py` | Exists but no diagnostic tool functions |
| `src/luna_mcp/server.py` | No diagnostic tools registered |
| `frontend/src/eclissi/EnginePipelineView.jsx` | No QA overlay |
| `frontend/src/eclissi/EclissiShell.jsx` | No QA tab |
| `frontend/src/eclissi/NexusView.jsx` | Exists ✅ |
| `frontend/src/hooks/useNexus.js` | Exists ✅ |

---

## MARK THESE COMPLETE FIRST

Before starting any new work, update the task queue:
- `task_20260301_181616_ea6a` → completed (R1-R6 verified on disk)
- `task_20260301_173300_b52e` → completed (NexusView.jsx verified on disk)
