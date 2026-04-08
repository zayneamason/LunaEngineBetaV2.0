# CC INSTRUCTIONS: CRITICAL — /stream Endpoint Doesn't Search Nexus

**Priority:** P0 — THIS IS WHY ECLISSI CAN'T FIND CHAPTERS  
**Time:** 15 minutes  
**This is the actual root cause.** Everything else works. The `/stream` endpoint bypasses all of it.

---

## The Bug

The `/stream` endpoint (line 2263 of server.py) — which is what Eclissi uses for streaming responses — does its own retrieval:

```python
# Line ~2337 of server.py
memory_context = await matrix.get_context(request.message, max_tokens=1500)
```

This searches the **Memory Matrix ONLY**. It never calls `_get_collection_context()`. It never touches Nexus. It never searches extractions or chunks. All the FTS5 fixes, split budget, chunk search, reading prompt — none of it fires through `/stream`.

Meanwhile, `/message` (line 1502) calls `_engine.send_message()` which goes through `engine.process()` → `_retrieve_context()` → `_get_collection_context()`. That path works perfectly — curl proves it.

| Endpoint | Caller | Nexus? | Result |
|---|---|---|---|
| `/message` | curl, API | YES | Lists all chapters |
| `/stream` | Eclissi | NO | "I don't have that information" |

---

## The Fix

In `src/luna/api/server.py`, in the `stream_message` function (line ~2337), AFTER the Memory Matrix retrieval and BEFORE building the system prompt, add Nexus collection search:

Find this block (around line 2337):
```python
                memory_context = await matrix.get_context(request.message, max_tokens=1500)
                if _constellation_ctx:
                    memory_context = _constellation_ctx + ("\n\n" + memory_context if memory_context else "")
```

Add immediately AFTER it:
```python
            # ── Nexus collection search (mirrors engine._get_collection_context) ──
            collection_context = ""
            try:
                collection_context = await _engine._get_collection_context(request.message)
            except Exception as _nexus_err:
                logger.warning(f"[STREAM] Nexus search failed: {_nexus_err}")

            if collection_context:
                memory_context = (memory_context or "") + "\n\n" + collection_context
```

That's it. One call. `_get_collection_context()` already exists, already has the FTS5 fix, the split budget, the chunk search, the reading prompt trigger — everything. The `/stream` endpoint just needs to call it.

---

## Also Check: `/persona/stream` (line 2451)

There may be a second streaming endpoint that Eclissi uses in certain modes. Check if it has the same issue:

```bash
grep -A 30 "async def persona_stream" src/luna/api/server.py | grep "memory_context\|matrix.get_context\|_get_collection_context"
```

If it also only calls `matrix.get_context()` without `_get_collection_context()`, apply the same fix.

---

## Also Check: `/api/guardian/chat/stream` (line 1234)

Same check for the Guardian stream endpoint.

---

## Verification

1. Restart engine (use `scripts/start_engine.sh`)
2. Open Eclissi in browser
3. Ask: "what are the chapters in priests and programmers?"
4. Luna MUST list actual chapter titles
5. Check grounding score: should show 5+ grounded claims
6. Ask: "What evidence does Lansing present about the simulation model?"
7. Luna should cite actual content, not hedge

---

## Why This Was Invisible

Every diagnostic test used curl → `/message` → engine.process() → works. But Eclissi uses `/stream` → separate retrieval → no Nexus. The FTS5 fix was confirmed working via curl multiple times. The bug was never in the search. It was in which endpoint Eclissi talks to.

---

## DO NOT

- Do NOT rewrite `_get_collection_context()` — it works, just call it
- Do NOT add inline Nexus search code to `/stream` — call the engine method
- Do NOT remove the Memory Matrix search — collection context is ADDITIVE
- Do NOT change the `/message` endpoint — it already works