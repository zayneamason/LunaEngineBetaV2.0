# HANDOFF: Narration Layer Diagnostic

**Created:** 2026-02-03
**Author:** Benjamin Franklin (The Scribe)
**For:** Claude Code Execution
**Context:** Hypothesis 2 from Prompt Archaeology — Is the Narration Layer actually narrating?

---

## 1. THE HYPOTHESIS

When Luna delegates to Claude, the response should flow:

```
User query → Claude API (facts only) → Narration Layer → Luna's voice
```

**The question:** Does the Narration Layer actually fire? Does it rewrite Claude's response in Luna's voice? Or does Claude's response pass through raw?

If narration isn't happening, delegated responses will sound like Claude, not Luna — regardless of how well the LoRA is trained.

---

## 2. WHAT WE'RE LOOKING FOR

### Expected Flow (per Bible spec)

```
1. Director receives complex query
2. Director decides to delegate (complexity > 0.35)
3. Director sends FACTS-ONLY query to Claude
4. Claude returns factual response
5. Narration Layer rewrites response in Luna's voice
6. User receives Luna-voiced response
```

### Possible Failure Modes

| Mode | Symptom |
|------|---------|
| **No narration** | Claude's response passes through unchanged |
| **Weak narration** | Light rewrite, still sounds like Claude |
| **Narration exists but broken** | Method exists but isn't called |
| **Narration prompt polluted** | Rewrite prompt has same voice example problem |

---

## 3. DIAGNOSTIC TASKS

### Task 1: Find Narration Code

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Find narration-related code
grep -rn "narrat\|rewrite\|voice\|rephrase" src/luna/actors/director.py

# Find the delegation method
grep -rn "_delegate\|delegate_to_claude\|_call_claude" src/luna/actors/director.py

# Check if there's a separate narration step
grep -rn "narrat" src/luna/ --include="*.py"
```

**Document:**
- [ ] Does `_narrate_facts()` or similar exist?
- [ ] Where is it defined?
- [ ] Is it called after Claude returns?

### Task 2: Trace Delegation Flow

Find the delegation method and trace the full flow:

```python
# Look for something like:
async def _delegate_to_claude(self, query, context):
    # 1. Build facts-only prompt for Claude
    # 2. Call Claude API
    # 3. Get response
    # 4. ??? Does narration happen here ???
    # 5. Return to user
```

**Check:**
- [ ] After Claude returns, what happens to the response?
- [ ] Is there a rewrite step?
- [ ] Or does it return directly?

### Task 3: Add Narration Logging

Instrument the delegation path to capture:

```python
def log_narration_diagnostic(
    original_query: str,
    claude_response: str,
    narrated_response: str,  # or None if no narration
    narration_fired: bool
):
    """Capture narration behavior for analysis."""
    import json
    from datetime import datetime
    
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "query": original_query,
        "claude_response_length": len(claude_response),
        "claude_response_preview": claude_response[:500],
        "narration_fired": narration_fired,
        "narrated_response_length": len(narrated_response) if narrated_response else 0,
        "narrated_response_preview": narrated_response[:500] if narrated_response else None,
        "response_changed": claude_response != narrated_response if narrated_response else False,
    }
    
    with open("data/diagnostics/narration_diagnostic.jsonl", "a") as f:
        f.write(json.dumps(log_entry) + "\n")
```

### Task 4: Run Delegation Test Queries

Force delegation with complex queries:

```python
delegation_test_queries = [
    # Should definitely delegate (complex reasoning)
    "Can you explain the difference between asyncio.gather and asyncio.wait, and when I should use each?",
    
    # Should delegate (code generation)
    "Write me a Python function that implements binary search",
    
    # Should delegate (analysis)
    "What are the pros and cons of actor-based concurrency vs async/await?",
    
    # Should delegate (research)
    "Explain how transformer attention mechanisms work",
]
```

For each:
1. Send through Engine
2. Confirm it delegated (check logs)
3. Capture Claude's raw response
4. Capture final response to user
5. Compare: Are they different? Does final sound like Luna?

### Task 5: Compare Responses

For each delegated query, answer:

| Question | Answer |
|----------|--------|
| Did it delegate to Claude? | Yes/No |
| Was narration method called? | Yes/No |
| Did response change after narration? | Yes/No |
| Does final response sound like Luna? | Yes/No |
| Or does it sound like Claude? | Yes/No |

---

## 4. IF NARRATION IS MISSING

If we find narration doesn't exist or isn't firing:

### Option A: Narration method exists but isn't called

Find where delegation returns and add the call:

```python
# Before (broken):
claude_response = await self._call_claude(query)
return claude_response  # Raw Claude!

# After (fixed):
claude_response = await self._call_claude(query)
luna_response = await self._narrate_in_luna_voice(claude_response)
return luna_response
```

### Option B: Narration method doesn't exist

Create it:

```python
async def _narrate_in_luna_voice(self, facts: str) -> str:
    """Rewrite factual response in Luna's voice."""
    
    # Use LOCAL inference (the LoRA) to rewrite
    narration_prompt = f"""Rewrite this information in your own words.
Keep all the facts accurate. Use your natural voice.

Information to rewrite:
{facts}

Your response:"""
    
    # Generate via LoRA — this is where Luna's voice comes from
    response = await self._local.generate(narration_prompt)
    return response
```

### Option C: Narration exists but prompt is polluted

Check the narration prompt for:
- Voice examples (same problem we just fixed)
- Over-instruction
- Conflicting signals

Apply same fix: minimal prompt, let LoRA do its job.

---

## 5. EXPECTED FINDINGS

| Scenario | Likelihood | Implication |
|----------|------------|-------------|
| Narration exists and works | Low | Not the problem |
| Narration exists but isn't called | Medium | Easy fix — add the call |
| Narration doesn't exist | Medium | Need to implement |
| Narration exists but prompt polluted | High | Same fix as voice examples |

---

## 6. DELIVERABLES

### Output 1: `NARRATION_DIAGNOSTIC_RESULTS.md`

- Does narration code exist? Where?
- Is it being called?
- Sample comparisons (Claude raw vs final)
- Assessment: Is this a problem?

### Output 2: Fix (if needed)

If narration is broken:
- Implement or fix the narration step
- Ensure it uses LOCAL LoRA (not Claude) for rewrite
- Minimal prompt — no voice examples

---

## 7. EXECUTION SEQUENCE

```
Phase 1: Find narration code (grep search)
Phase 2: Trace delegation flow end-to-end
Phase 3: Add logging instrumentation
Phase 4: Run delegation test queries
Phase 5: Compare raw vs final responses
Phase 6: Diagnose and fix if needed
```

---

## 8. THE KEY INSIGHT

The Narration Layer is where Luna's voice should shine on delegated queries.

- Claude provides the FACTS (what to say)
- Luna LoRA provides the VOICE (how to say it)

If narration isn't happening, Luna sounds like Claude on every complex query — which is exactly the symptom we're seeing.

---

## 9. GO

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Find narration
grep -rn "narrat" src/luna/actors/director.py

# Trace delegation
grep -n "_delegate\|delegate_to" src/luna/actors/director.py

# Check if rewrite happens
# (read the methods found above)
```

---

*Claude speaks facts. Luna speaks truth. The Narration Layer is where facts become truth.*

— Ben
