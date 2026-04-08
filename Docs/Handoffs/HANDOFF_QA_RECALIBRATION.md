# HANDOFF: QA Assertion Audit & Recalibration

**Date:** March 2, 2026  
**From:** The Dude + Ben Franklin (Scribe)  
**To:** Claude Code  
**Priority:** Do this BEFORE the pipeline diagnostic overlay handoffs

---

## THE PROBLEM

Luna's QA system has a 3.8% pass rate over 7 days. 75 failures out of 78 inferences. This isn't because Luna is catastrophically broken — it's because the test suite is checking for an architecture that no longer exists and has at least one assertion with inverted logic.

As Ben noted: *"A thermometer that reads fever when the patient is well is worse than no thermometer at all."*

The QA system needs to be recalibrated to test the architecture **as it exists today**, not the architecture we intended to build six weeks ago. Until this is done, the pipeline diagnostic overlay will just paint everything red, which tells us nothing.

---

## THREE ISSUES

### Issue 1: P3 "Narration applied" — checks for dead architecture

**Current behavior:** Checks if `narration_applied == True`. Always fails because narration was intentionally disabled at line 965-969 of director.py:

```python
# NARRATION DISABLED: Qwen 3B rewrite was degrading Groq's
# 70B output quality. Luna's voice is now injected via the
# system prompt (PromptAssembler), not post-hoc rewriting.
```

**Fix:** Rewrite P3 to check the current architecture. Luna's voice is now injected via the PromptAssembler system prompt. The assertion should verify:

1. Voice blocks are present in the system prompt (check for `<luna_voice` tag or voice-related content)
2. System prompt contains personality/tone directives (already covered by P1's length check, but P3 should specifically check for voice injection)

**New P3 implementation:**

```python
def check_voice_injection(ctx: InferenceContext, assertion: Assertion) -> AssertionResult:
    """Check that Luna's voice is injected via system prompt (replaces narration check)."""
    prompt = ctx.system_prompt or ""
    
    # Check for voice injection markers
    has_luna_voice = "<luna_voice" in prompt or "luna_voice" in prompt.lower()
    has_tone_hints = "tone hints" in prompt.lower() or "style mechanics" in prompt.lower()
    has_avoid_block = "<avoid>" in prompt or "<never>" in prompt
    
    voice_present = has_luna_voice or (has_tone_hints and has_avoid_block)
    
    return AssertionResult(
        id=assertion.id,
        name=assertion.name,
        passed=voice_present,
        severity=assertion.severity,
        expected="Voice injection in system prompt (<luna_voice> block or tone directives)",
        actual=f"luna_voice: {has_luna_voice}, tone_hints: {has_tone_hints}, avoid_block: {has_avoid_block}",
    )
```

Update the assertion registration to use this function instead of the old narration check. Update the name to "Voice injected" and description to "System prompt contains Luna's voice directives (via PromptAssembler)".

Also update the diagnosis generator in `validator.py` — the `_generate_diagnosis()` method currently says "Check _narrate_response() in Director" when P3 fails. Change it to reference the PromptAssembler voice injection path.

---

### Issue 2: CUSTOM-CB2C01 "Knowledge Surrender Detection" — inverted logic

**Current behavior:** This is a custom `regex` type assertion stored in the SQLite database. It uses the pattern:

```
i don't have (any|specific)? ?(information|memory|memories|context|knowledge|details)|tell me (more|a bit more)|i'm not (sure|familiar)|i don't know (about|anything)|not in my (memory|records|context)
```

The regex match logic in `_check_pattern()` says:
```python
passed = match is not None  # match found = PASS
```

But this assertion is **detecting bad behavior** (knowledge surrender). If the regex matches, Luna IS surrendering, which should be a FAIL. The logic is backwards.

**The actual result from the last report:**
- actual: "No match" (Luna didn't surrender)  
- passed: false (assertion FAILED her for not surrendering)

This is completely inverted.

**Fix:** Change the match_type from `regex` to a new concept, or — simpler — change the stored assertion to use `not_contains` style logic. But since it's a regex, the cleanest fix is:

**Option A (recommended):** Add a `negate` field to PatternConfig. When `negate=true`, the pass/fail result is inverted. This handles the common case of "detect bad patterns" assertions where a match means failure.

```python
@dataclass
class PatternConfig:
    target: str
    match_type: str
    pattern: str
    case_sensitive: bool = False
    negate: bool = False  # NEW: when true, match = fail
```

Then in `_check_pattern()`:
```python
# After computing passed...
if pc.negate:
    passed = not passed
```

Then update the stored CUSTOM-CB2C01 assertion to set `negate=true`.

**Option B (simpler):** Add a `regex_not_match` match type alongside the existing `regex`:
```python
elif pc.match_type == "regex_not_match":
    flags = 0 if pc.case_sensitive else re.IGNORECASE
    match = re.search(pc.pattern, target_value, flags)
    passed = match is None  # PASS when pattern NOT found
    expected = f"Does not match regex '{pc.pattern}'"
    actual = f"Match: {match.group()}" if match else "No match (good)"
```

Then update CUSTOM-CB2C01 to use `regex_not_match` instead of `regex`.

**Go with Option B** — it's more explicit about intent and doesn't require a schema migration for the negate field.

**Database update:**
```sql
UPDATE qa_assertions 
SET pattern_config_json = json_set(pattern_config_json, '$.match_type', 'regex_not_match')
WHERE id = 'CUSTOM-CB2C01';
```

---

### Issue 3: Pass rate is misleading due to the 7-day stats window

**Current behavior:** `/qa/stats/detailed` reports 3.8% pass rate across 7 days (3 passed, 75 failed). But the LAST inference was 16/18 passing — only P3 and CUSTOM-CB2C01 failed, and both of those are bugs in the assertions, not bugs in Luna.

If we fix P3 and CUSTOM-CB2C01, Luna's actual pass rate on the last inference would be **100%.** The 3.8% number is a ghost from weeks of these two broken assertions failing every single time.

**Fix:** After fixing the assertions, clear the QA history so the stats reflect the current state:

```python
# In database.py, add a method:
def clear_reports_before(self, cutoff_date: str):
    """Clear QA reports before a date. Use after recalibration."""
    with self._conn() as conn:
        conn.execute("DELETE FROM qa_reports WHERE timestamp < ?", (cutoff_date,))
```

Or simpler — just note in the handoff that after fixing the assertions, the old stats are meaningless. The diagnostic overlay should show "since last recalibration" or similar. Don't delete data, just add a recalibration timestamp.

**Add to server.py:**
```python
@app.post("/qa/recalibrate")
async def qa_recalibrate():
    """Mark a recalibration point. Stats will show 'since recalibration' context."""
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA not available")
    validator = get_qa_validator()
    validator.mark_recalibration()
    return {"status": "recalibrated", "timestamp": datetime.now().isoformat()}
```

---

## FULL ASSERTION AUDIT

Review each of the 18 built-in assertions against the current architecture. Here's my assessment:

| ID | Name | Status | Notes |
|----|------|--------|-------|
| P1 | Personality injected | ✅ Valid | Checks prompt length >1000 chars. Works. |
| P2 | Virtues loaded | ✅ Valid | Checks identity buffer exists. Works. |
| P3 | Narration applied | ⛔ BROKEN | Checks dead narration pipeline. **FIX: rewrite to check voice injection in prompt.** |
| S1 | No code blocks | ✅ Valid | Pattern check on response. Works. |
| S2 | No ASCII art | ✅ Valid | Pattern check. Works. |
| S3 | No mermaid diagrams | ✅ Valid | Pattern check. Works. |
| S4 | No bullet lists | ✅ Valid | Counts bullets. Works. |
| S5 | Response length | ✅ Valid | 20-5000 chars. Works. |
| V1 | No Claude-isms | ✅ Valid | Banned phrase detection. Works. |
| F1 | Provider success | ✅ Valid | Checks provider returned response. Works. |
| F2 | No timeout | ✅ Valid | Checks <30s latency. Works. |
| I1 | Graph has edges | ✅ Valid | Memory Matrix health. Works. |
| I2 | Cluster health | ✅ Valid | <99% drifting. Works. |
| I3 | Node type diversity | ✅ Valid | <95% FACTs. Works. |
| I4 | No assistant extraction | ✅ Valid | Prevents extracting Luna's own responses. Works. |
| E1 | Extraction backend active | ✅ Valid | Scribe running. Works. |
| E2 | Extractions include entities | ✅ Valid | Entity extraction quality. Works. |
| CUSTOM-CB2C01 | Knowledge Surrender Detection | ⛔ INVERTED | Regex match = pass, but match means Luna IS surrendering. **FIX: use regex_not_match.** |

**Result: 16 valid, 1 broken (P3), 1 inverted (CUSTOM-CB2C01).**

If both are fixed, the last inference would have been 18/18 — 100% pass rate.

---

## FILES MODIFIED

| File | Change |
|------|--------|
| `src/luna/qa/assertions.py` | Add `regex_not_match` match type in `_check_pattern()`. Rewrite P3 builtin function. |
| `src/luna/qa/validator.py` | Update `_generate_diagnosis()` to reference PromptAssembler instead of `_narrate_response()`. Add `mark_recalibration()` method. |
| `src/luna/qa/database.py` | Update CUSTOM-CB2C01 match_type to `regex_not_match`. Add `clear_reports_before()` (optional). |
| `src/luna/api/server.py` | Add `POST /qa/recalibrate` endpoint. |

**Total: 4 files modified, 0 new files.**

---

## VERIFY

After implementation:

1. Send a message to Luna: "hey luna, how are you?"
2. Check `/qa/last` — P3 should now PASS (voice blocks in prompt)
3. Check CUSTOM-CB2C01 — if Luna doesn't surrender, it should PASS
4. Overall: expect 18/18 or close to it
5. The 3.8% stat is now historical — new inferences should show dramatically higher pass rates

---

## ORDER OF OPERATIONS

1. **This handoff FIRST** — recalibrate QA
2. Then Pipeline Diagnostic Overlay — now the colors mean something  
3. Then MCP Diagnostic Controls — the ghost endpoints
4. Then Pipeline Interactive Diagnostics — trace, diff, playground

No point painting nodes red if the red paint is lying to you.
