# CC INSTRUCTIONS: Stop the Qwen Loop — Focus on What Matters

**STOP** chasing the Qwen 3B timeout. Here's why and what to do instead.

---

## Current Status (Verified)

1. **FTS5 fix: WORKING.** Engine logs show `[FTS5] Input: 'what are the chapters...' → Output: 'chapters OR priests OR programmers'`. Luna can now find extraction data.

2. **Keyword fallback: ALREADY WIRED.** Line 1251 of engine.py has a keyword-based routing upgrade that fires when SubtaskRunner is unavailable. Research queries ("tell me about", "what are", "explain", "chapters", etc.) get routed to AgentLoop even without Qwen.

3. **Qwen: NOT loading.** `"LocalSubtaskRunner skipped (local model not available)"`. The model file is either missing or MLX can't load it on this machine.

## What to Do (In Order)

### Task 1: VERIFY Eclissi works (5 min)

The engine is running with the FTS5 fix loaded. The curl test works — Luna lists all chapters. Verify Eclissi also works:

1. Open Eclissi in browser (http://localhost:5173 or whatever port Vite serves)
2. Type: "what are the chapters in priests and programmers?"
3. Luna should list: Introduction, Chapter One through Six, Conclusion, Afterword, Appendices
4. Check grounding scores — should show 5+ grounded claims

If Eclissi still shows old behavior:
- Hard refresh the browser (Cmd+Shift+R)
- Check that Eclissi is hitting port 8000 (same engine you just tested with curl)
- Check browser console for errors

**DO NOT** restart the engine. It's working. The FTS5 logs prove it.

### Task 2: Test the Keyword Fallback (5 min)

Ask Luna a research query where direct results would be sparse:

"What specific evidence does Lansing present that the water temple scheduling system was mathematically optimal compared to the Green Revolution approach?"

Check engine logs for:
```
[ROUTING] Keyword fallback → AgentLoop (no intent classification available)
```

If you see that log, the agentic path is firing without Qwen. The keyword fallback works.

### Task 3: Deprioritize Qwen (Read This)

Qwen 3B was meant to do intent classification and query rewriting. Both have workarounds:

- **Intent classification** → keyword fallback (already wired, line 1251)
- **Query rewriting** → the FTS5 fix with stop-word removal handles this at the search level

Qwen is nice-to-have for sophisticated routing, but it's NOT blocking anything critical. The keyword fallback + FTS5 fix cover the demo-critical path.

**If you want to debug Qwen anyway**, the issue is likely one of:
1. MLX model files not downloaded at the expected path
2. MLX not compiled for ARM64 / M1
3. The model load taking > 2s timeout on first inference (cold start)

But **do not spend more than 15 minutes on this**. The system works without it.

### Task 4: Engine Startup Script (10 min)

The engine keeps getting restarted with system Python 3.14 instead of .venv. This causes the FTS5 fix to not load (wrong bytecode cache). Fix this permanently:

Create or update a launch script that always uses .venv:

```bash
#!/bin/bash
# File: scripts/start_engine.sh
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Always clear bytecode cache on start
find src/ -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
find src/ -name "*.pyc" -delete 2>/dev/null

# Always use .venv Python
exec .venv/bin/python scripts/run.py --server --host 0.0.0.0 --port 8000
```

```bash
chmod +x scripts/start_engine.sh
```

Then always start with `./scripts/start_engine.sh` instead of bare `python scripts/run.py`.

## What NOT To Do

- Do NOT keep iterating on Qwen timeouts. The keyword fallback is sufficient.
- Do NOT restart the engine unless you have to. The current process has the FTS5 fix loaded.
- Do NOT modify `_sanitize_fts_query`. It's working. Don't touch it.
- Do NOT change the keyword fallback signals at line 1261. They're correct.
- Do NOT create new handoffs. Execute the tasks above.