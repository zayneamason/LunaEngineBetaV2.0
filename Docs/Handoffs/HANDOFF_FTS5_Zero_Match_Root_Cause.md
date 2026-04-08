# HANDOFF: FTS5 Zero-Match Bug — Root Cause Found, Fix Applied, Verification Needed

**Priority:** P0 — THIS IS THE BUG. Everything else was a red herring.  
**Date:** 2026-03-24  
**Time estimate:** 15 minutes to verify and restart properly  
**Risk:** The fix is already on disk. This handoff is about making sure the running engine actually loads it.

---

## The Root Cause (CONFIRMED)

`_sanitize_fts_query()` in `aibrarian_engine.py` strips punctuation but passes the **full conversational query** to FTS5 as **implicit AND**. FTS5 requires ALL words to appear in the same extraction row.

### Proof (tested against live database):

| Query | FTS5 Mode | Matches |
|---|---|---|
| "do you have chapter knowledge" | Implicit AND (BEFORE fix) | **0** |
| "do you have chapter knowledge" | OR + stop words removed (AFTER fix) | **35** |
| "tell me about the priests and programmers" | Implicit AND | **0** |
| "tell me about the priests and programmers" | OR + stop words removed | **406** |
| "what are the chapters in priests and programmers" | Implicit AND | **0** |
| "what are the chapters in priests and programmers" | OR + stop words removed | **425** |

Every conversational query returns ZERO matches under implicit AND. This is why:
- The gate fix didn't help (gate was open, search returned 0)
- The pipe widening didn't help (wider pipe, still 0 results flowing through)
- The retry tiers didn't help (Tier 1 returns 0, Tier 2 expands but still AND, still 0)
- Luna kept saying "I don't have chapter knowledge" (because she literally got 0 extraction hits)

**The 456 extractions are there. The FTS5 index has 456 rows. The data is perfect. The search query was broken.**

---
## The Fix (ALREADY APPLIED TO DISK)

**File:** `src/luna/substrate/aibrarian_engine.py` — `_sanitize_fts_query()` at line ~851

The fix has been applied by Claude.ai directly to the source file. It does three things:
1. Strips punctuation (same as before)
2. **NEW: Removes stop words** (do, you, have, the, is, are, what, tell, me, about, etc.)
3. **NEW: Joins remaining tokens with OR** instead of implicit AND

### Before (broken):
```
User: "what are the chapters in priests and programmers"
FTS5 receives: "what are the chapters in priests and programmers"
FTS5 interprets: what AND are AND the AND chapters AND in AND priests AND and AND programmers
Result: 0 matches (no extraction contains ALL those words)
```

### After (fixed):
```
User: "what are the chapters in priests and programmers"
Stop words removed: "chapters", "priests", "programmers"  
FTS5 receives: "chapters OR priests OR programmers"
Result: 425 matches
```

### Verification that the fix is on disk:
```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
grep -A 5 "def _sanitize_fts_query" src/luna/substrate/aibrarian_engine.py
```

You should see: `"""Sanitize query for FTS5: strip punctuation, remove stop words, join with OR."""`

If you see the OLD docstring: `"""Escape special FTS5 characters to prevent syntax errors."""` — the edit was lost. Re-apply from the code below.

---
## Full Fix Code (if re-application needed)

Replace the `_sanitize_fts_query` method in `src/luna/substrate/aibrarian_engine.py` (around line 851):

```python
    @staticmethod
    def _sanitize_fts_query(query: str) -> str:
        """Sanitize query for FTS5: strip punctuation, remove stop words, join with OR."""
        import re
        # Remove FTS5 special chars and general punctuation that breaks MATCH syntax
        sanitized = re.sub(r'[?*"\'():^{}~.,;!@#$%&\[\]\u2018\u2019\u201C\u201D\u2014\u2013]', ' ', query)
        # Collapse whitespace
        sanitized = re.sub(r'\s+', ' ', sanitized).strip()
        if not sanitized:
            return query
        # Strip stop words — conversational filler that kills FTS5 implicit-AND matching
        _STOP = {
            'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'do', 'does', 'did', 'have', 'has', 'had', 'having',
            'i', 'me', 'my', 'you', 'your', 'we', 'our', 'they', 'them', 'their',
            'he', 'she', 'it', 'its', 'his', 'her',
            'what', 'which', 'who', 'whom', 'that', 'this', 'these', 'those',
            'am', 'will', 'would', 'shall', 'should', 'can', 'could', 'may', 'might',
            'to', 'of', 'in', 'for', 'on', 'at', 'by', 'with', 'from', 'about',
            'into', 'through', 'during', 'before', 'after', 'above', 'below',
            'and', 'but', 'or', 'nor', 'not', 'so', 'if', 'then',
            'tell', 'know', 'think', 'like', 'just', 'also', 'very', 'really',
            'how', 'when', 'where', 'why', 'there', 'here', 'some', 'any', 'all',
            'more', 'most', 'other', 'than', 'too', 'only', 'each', 'every',
        }
        tokens = [t for t in sanitized.lower().split() if t not in _STOP and len(t) > 1]
        if not tokens:
            # All tokens were stop words — fall back to original minus punctuation
            tokens = sanitized.split()
        # Join with OR so FTS5 matches any keyword, not all of them
        return ' OR '.join(tokens)
```

---
## Why Eclissi Might Still Show Old Behavior

The fix is on the source file. But the running engine may not have loaded it. Possible reasons:

### 1. Engine wasn't restarted with .venv Python
The engine MUST run under `.venv/bin/python` (not system Python). Check:
```bash
lsof -i :8000 -t | xargs ps -p -o pid,command=
```
If you see `/Library/Frameworks/Python...` or `/opt/homebrew/...` instead of `.venv/bin/python`, it's the wrong interpreter.

### 2. Cached .pyc file
Python caches compiled bytecode. The engine might be loading a stale `.pyc`:
```bash
find /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src -name "aibrarian_engine.cpython-*.pyc" -delete
```

### 3. The engine.py ALSO calls _sanitize_fts_query
`engine.py` line ~1796 imports and calls `AiBrarianEngine._sanitize_fts_query(query)`. Since it imports from the class, it uses the same fixed method. BUT verify:
```bash
grep "_sanitize_fts_query" /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/engine.py
```
Should show it importing from `luna.substrate.aibrarian_engine`. If there's a LOCAL copy of the function in engine.py, that would override the fix.

### 4. Multiple engine processes
Kill ALL engine processes before restarting:
```bash
pkill -f "scripts/run.py"
sleep 2
# Verify nothing on port 8000
lsof -i :8000
```

---

## Verification Steps (DO ALL OF THESE)

### Step 1: Verify fix is on disk
```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
head -3 <(grep -A 3 "def _sanitize_fts_query" src/luna/substrate/aibrarian_engine.py)
```
Must show: `remove stop words, join with OR`

### Step 2: Clear cached bytecode
```bash
find src/ -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find src/ -name "*.pyc" -delete 2>/dev/null
```

### Step 3: Kill all engine processes
```bash
pkill -f "scripts/run.py" 2>/dev/null
pkill -f "run_luna" 2>/dev/null
sleep 3
lsof -i :8000  # should show nothing
```

### Step 4: Restart with .venv Python
```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
.venv/bin/python scripts/run.py --server --host 0.0.0.0 --port 8000
```
Wait for `Application startup complete` in the log.

### Step 5: Test with curl FIRST (before Eclissi)
```bash
curl -s -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "what are the chapters in priests and programmers?", "stream": false}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('text','')[:500])"
```
Expected: Luna lists actual chapter titles (The Powers of Water, The Waters of Power, etc.)

### Step 6: Test in Eclissi
Open Eclissi, ask: "what are the chapters in priests and programmers?"
Expected: Same chapter-level response with grounded scores > 5.

### Step 7: If curl works but Eclissi doesn't
Eclissi might be hitting a different port or a cached response. Check:
```bash
# What port does Eclissi connect to?
grep -r "localhost\|127.0.0.1\|8000" frontend/src/ | grep -v node_modules | grep -v ".map"
```

---
## Add Diagnostic Logging (REQUIRED)

Even after the fix works, add a log line so we can confirm at runtime that the OR query is being used. In `_sanitize_fts_query`, before the return:

```python
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[FTS5] Input: '{query[:60]}' → Output: '{' OR '.join(tokens)[:80]}'")
        return ' OR '.join(tokens)
```

And in `engine.py` `_get_collection_context()`, after the Tier 1 FTS5 search (around line 1810), add:

```python
            logger.info(f"[PHASE2] Tier 1 FTS5 for {key}: query='{fts_query[:60]}', results={len(ext_rows)}")
```

This way, on the next query, the engine log will show:
```
[FTS5] Input: 'what are the chapters in priests and programmers' → Output: 'chapters OR priests OR programmers'
[PHASE2] Tier 1 FTS5 for research_library: query='chapters OR priests OR programmers', results=15
```

If you see `results=0` in that log, the fix isn't loaded. If you see `results=15`, the fix is working and the problem is downstream.

---

## What NOT To Do

- Do NOT widen pipe limits, change aperture settings, modify the gate logic, or touch MAX_CHARS. Those were all red herrings. The pipe was fine. The search returned zero.
- Do NOT re-ingest the book, re-extract, rebuild FTS5 indexes, or modify the collection config. The data is perfect. 456 extractions, 196 chunks, all indexed.
- Do NOT modify the retrieval tiers, add new search strategies, or restructure the pipeline. The three-tier cascade works — it just had nothing to cascade because Tier 1 returned zero.
- Do NOT switch LLM providers. This is a search bug, not a generation bug.
- Do NOT create new handoffs for related issues until this one is verified working in Eclissi.

---

## The One-Line Summary

Every conversational query returned ZERO FTS5 matches because implicit AND required all words to appear in one extraction. Stop words removed + OR joining fixes it. The fix is on disk. Clear .pyc cache, kill all engine processes, restart with .venv Python, verify with curl, then test in Eclissi.

---

## Files Modified

| File | Change | Status |
|---|---|---|
| `src/luna/substrate/aibrarian_engine.py` | Rewrote `_sanitize_fts_query()` — stop word removal + OR joining | **ALREADY ON DISK** — verify and restart |

## Files to Add Logging To

| File | Where | What |
|---|---|---|
| `src/luna/substrate/aibrarian_engine.py` | End of `_sanitize_fts_query()` | Log input → output transformation |
| `src/luna/engine.py` | After Tier 1 FTS5 in `_get_collection_context()` | Log query + result count per collection |


---

## ADDENDUM: Luna's Agentic Processes — Status and Blocker

The FTS5 bug didn't just break the direct retrieval path. It broke the agentic path too. Here's the full picture.

### What Exists and Is Wired

| Component | File | Status |
|---|---|---|
| AgentLoop | `src/luna/agentic/loop.py` | Initialized at engine boot (line 487), max 50 iterations |
| QueryRouter | `src/luna/agentic/router.py` | Routes DIRECT vs PLANNED based on complexity + signals |
| Planner | `src/luna/agentic/planner.py` | Generates step-by-step plans for the AgentLoop |
| nexus_tools.py | `src/luna/tools/nexus_tools.py` | 3 tools: `nexus_search`, `nexus_lookup_section`, `nexus_get_summary` |
| Tool registration | `loop.py` line ~312 | Nexus tools registered in AgentLoop's tool registry |
| Routing upgrade | `engine.py` line ~1228 | Upgrades DIRECT → AgentLoop when Nexus results are sparse + intent is research |
| LocalSubtaskRunner | `src/luna/inference/subtasks.py` | Qwen 3B for intent classification + query rewriting |

### How the Agentic Path Is Supposed to Work

```
User asks complex knowledge question
  → SubtaskRunner classifies intent as "research" or "memory_query"
  → Initial retrieval runs (_get_collection_context)
  → Routing checks: is Nexus sparse (< 2 nodes) AND intent is research?
  → YES → Upgrade to AgentLoop
  → AgentLoop iterates:
      Iteration 1: nexus_get_summary() → gets document overview + TOC
      Iteration 2: nexus_search("specific topic") → gets targeted extractions
      Iteration 3: nexus_lookup_section("CHAPTER THREE") → gets section detail
  → LLM generates with rich multi-source context
```

### Why It Was Dead

The agentic upgrade condition at engine.py line 1228:

```python
if (
    routing.path == ExecutionPath.DIRECT
    and self.agent_loop
    and len(self._last_nexus_nodes) < 2      # ← Was ALWAYS true (0 nodes from FTS5 bug)
    and subtask_phase
    and subtask_phase.intent
    and subtask_phase.intent.get("intent") in ("research", "memory_query")
)
```

Even when the upgrade DID fire, the AgentLoop's `nexus_search` tool calls the SAME `_sanitize_fts_query()` that was broken. So:

1. Direct path: FTS5 implicit AND → 0 results → sparse context
2. Routing sees sparse → upgrades to AgentLoop
3. AgentLoop calls nexus_search → SAME FTS5 implicit AND → 0 results
4. AgentLoop gives up → Luna hedges

The FTS5 fix (already on disk) repairs BOTH paths because both call the same sanitizer.

### Second Potential Blocker: SubtaskRunner Availability

The routing upgrade requires `subtask_phase.intent.get("intent") in ("research", "memory_query")`. This intent classification comes from the LocalSubtaskRunner (Qwen 3B).

**CC must verify:** After restarting the engine with the FTS5 fix, check the startup logs for:
- `LocalSubtaskRunner initialized` or similar → Qwen is running, intent classification works
- If this log is MISSING → the subtask runner isn't loading → `subtask_phase` is an empty stub → the agentic upgrade condition NEVER triggers → Luna stays on DIRECT path forever

If Qwen isn't available, the agentic path is dead code. Two possible fixes:
1. Get Qwen loaded (check if model file exists at the expected path)
2. Add a fallback heuristic that doesn't require Qwen: if the query contains knowledge-seeking signals ("what does", "tell me about", "explain", "chapters", "evidence") AND Nexus results are sparse, upgrade to AgentLoop regardless of intent classification

### What to Verify (After FTS5 Fix Is Confirmed Working)

1. **Check if SubtaskRunner loads:**
```bash
grep -i "subtask\|qwen\|local.*runner" /tmp/luna_engine.log
```

2. **Check if agentic upgrade ever fires:**
```bash
grep "Upgrading to AgentLoop" /tmp/luna_engine.log
```

3. **If it fires, check if nexus tools return results:**
```bash
grep "NEXUS-TOOL" /tmp/luna_engine.log
```

4. **If nothing fires, add temporary debug logging to the routing check:**
```python
# In engine.py around line 1228, add:
logger.info(f"[ROUTING-DEBUG] path={routing.path}, agent_loop={bool(self.agent_loop)}, "
            f"nexus_nodes={len(self._last_nexus_nodes)}, "
            f"subtask_phase={bool(subtask_phase)}, "
            f"intent={subtask_phase.intent if subtask_phase else 'None'}")
```

### Priority

1. **FTS5 fix** — unblocks BOTH direct and agentic paths
2. **Verify SubtaskRunner** — determines if agentic path can trigger
3. **If SubtaskRunner is down** — add keyword-based fallback heuristic for routing upgrade
