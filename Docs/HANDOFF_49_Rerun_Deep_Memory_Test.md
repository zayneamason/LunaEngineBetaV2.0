# HANDOFF #49: Re-Run Deep Memory Test — Measure the Delta

**Priority:** HIGH — Four handoffs landed (#45, #46, #47, #48) without re-measurement. Need to know what improved.

**Scope:** Run the existing test, collect numbers, compare to baseline. No code changes.

## What Changed Since Last Run

The April 5 test run (baseline) scored poorly with these issues:
- 1173 "database is locked" errors
- 15-50s latency per response
- ~6 intent classifier timeouts + JSON parse failures
- Identity confusion (Kamau vs Ahab)
- 17/37 checks crashing before Luna could respond

Since then, four handoffs landed:

| # | Fix | Expected Impact |
|---|-----|-----------------|
| 45 | One Door Architecture — unified inference pipeline | Eliminates repetition bug, all paths get conversation history |
| 46 | Lock cascade guard + intent classifier hardening | Lock errors → near zero, intent fallback rate → near zero |
| 47 | Retrieval Quality L1 — three-signal scoring (similarity × frequency × recency) | Better context selection, owner identity boost |
| 48 | Edge type cleanup — 202 types → 8 canonical | Cleaner graph, high-signal edges doubled (184 → 363) |

## Run the Test

```bash
# 1. Make sure engine is running
PYTHONPATH=src .venv/bin/python scripts/run.py --server

# 2. Run the deep memory test
PYTHONPATH=src .venv/bin/python scripts/live_memory_test.py
```

## What to Measure

Capture ALL of the following. Compare each to the April 5 baseline.

### A. Infrastructure Health

1. **Lock errors:** `grep -c "database is locked" <log_output>` — Baseline: 1173. Target: <10.
2. **Intent fallback rate:** `grep -c "keyword fallback" <log_output>` — Baseline: ~6 timeouts + parse failures. Target: <2.
3. **Average latency:** Mean response time across all test messages. Baseline: 15-50s. Target: measurable improvement.
4. **Crashes:** Count of checks where Luna could not respond at all. Baseline: 17/37. Target: <5.

### B. Identity & Memory Quality
5. **Identity recognition:** Does Luna identify Ahab on first ask? Baseline: confused Kamau/Ahab. Target: Ahab from turn 1.
6. **Context relevance:** Are retrieved memories relevant to the query? Check debug output for retrieval scores — should show varied scores (not all 1.0).
7. **Recency bias:** Recent memories should score higher than old ones with similar content. Check debug for the three-signal score.

### C. Test Score
8. **Overall pass rate:** X/37 checks passing. Baseline: 6/37 (Grade F). Target: improvement — even 15/37 would be significant progress.
9. **Category breakdown:** Which categories improved vs stayed broken. The test covers: relationship recall, emotional expression, personality triggers, conversation building, development milestones, self-awareness.

### D. Edge Quality (New)
10. **New edges created during test:** `SELECT relationship, COUNT(*) FROM graph_edges WHERE created_at > '<test_start_time>' GROUP BY relationship` — All new edges should be canonical types only.

## Write the Report

Save results to: `Docs/REPORT_Luna_Deep_Memory_Test_2026-04-05_Post_Fixes.md`

Use the same format as the previous report (`Docs/REPORT_Luna_Deep_Memory_Test_2026-03-19.md`) but add a delta section at the top comparing each metric to the April 5 baseline.

## DO NOT

- DO NOT fix bugs during this test. Just record what happens. If something is broken, note it in the report.
- DO NOT change any code. This is measurement only.
- DO NOT skip categories. Run the full test even if early categories fail.
- DO NOT restart the engine mid-test unless it crashes. We want to see lock contention behavior across a sustained conversation.

## After the Report

The delta tells us what to work on next:
- If lock errors are near zero but latency is still high → latency is from model inference, not contention
- If identity is fixed but other memory is weak → retrieval scoring works but coverage is sparse
- If scores improved but plateau early → context assembly is better but still missing something
- If new edges aren't canonical → write-time enforcement isn't wired correctly

The numbers decide the next handoff. Not guesses.
