# EMERGENCY HANDOFF: Luna Voice/Inference Audit

**Priority:** CRITICAL — Luna is broken, outputting garbage  
**Mode:** Claude Flow Swarm — parallel investigation  
**Output:** Live test results on frontend + full diagnostic report  

---

## Problem Statement

Luna is responding with hallucinated garbage:
- ASCII art nobody asked for
- Mermaid diagrams mid-conversation
- Random "observations" about the user
- Diagnostic formatting instead of natural speech

User said "hey luna" and got a fever dream instead of a warm greeting.

**The question:** Where the fuck is Luna's personality? Is the LoRA even in the stack?

---

## Swarm Tasks (Run in Parallel)

### 🔴 TRACER 1: LoRA Status Audit

**Question:** Is Luna's LoRA adapter actually loaded and being used?

**Investigate:**
1. Check `src/luna/inference/local_inference.py` — is LoRA loading code present?
2. Check `config/` for LoRA path configuration
3. Check `models/` directory — does a Luna LoRA file exist?
4. Trace the inference path: when local generates, does it apply LoRA weights?
5. Check MLX adapter loading — is `load_adapter()` being called?

**Commands to run:**
```bash
# Find LoRA references
grep -r "lora" src/ --include="*.py" -i
grep -r "adapter" src/ --include="*.py" -i

# Check model config
cat config/models.yaml 2>/dev/null || echo "No models.yaml"
cat config/inference.yaml 2>/dev/null || echo "No inference.yaml"

# Check what models exist
ls -la models/
ls -la models/lora/ 2>/dev/null || echo "No lora directory"
```

**Expected output:** Report on whether LoRA exists, is configured, and is being loaded.

---

### 🔴 TRACER 2: Local Inference Path Trace

**Question:** What prompt does local model actually receive? What system prompt?

**Investigate:**
1. Find where local inference builds the prompt
2. Log the EXACT prompt being sent to Qwen 3B
3. Check if Luna's personality/virtues are being injected
4. Check if system prompt includes character instructions

**Add temporary logging:**
```python
# In LocalInference.generate() or equivalent
logger.info(f"[LOCAL_PROMPT] System: {system_prompt[:500]}...")
logger.info(f"[LOCAL_PROMPT] Messages: {messages}")
```

**Test:** Send "hey luna" through frontend, capture the log.

**Expected output:** The actual prompt local model sees.

---

### 🔴 TRACER 3: Fallback Chain Behavior

**Question:** Is FallbackChain trying all providers or stopping at local?

**Investigate:**
1. Check FallbackChain logs — what providers were attempted?
2. Is local "succeeding" (returning tokens) even though output is garbage?
3. Are groq/claude being skipped because local returned something?

**Add logging if not present:**
```python
# In FallbackChain.generate()
for provider in self._chain:
    logger.info(f"[FALLBACK] Trying provider: {provider}")
    try:
        result = await self._try_provider(provider, ...)
        logger.info(f"[FALLBACK] Provider {provider} returned {len(result)} chars")
        # LOG THE ACTUAL RESPONSE
        logger.info(f"[FALLBACK] Response preview: {result[:200]}...")
        return result
    except Exception as e:
        logger.info(f"[FALLBACK] Provider {provider} failed: {e}")
```

**Expected output:** Log showing which providers were tried and what they returned.

---

### 🔴 TRACER 4: Personality/Virtues Loading

**Question:** Is Luna's personality being loaded into the prompt?

**Investigate:**
1. Check `memory/virtue/current.json` — does it exist? What's in it?
2. Check Director's `_build_system_prompt()` or equivalent
3. Is virtues content being injected into system prompt?
4. Check `luna_detect_context()` — what does it return for auto_fetch?

**Commands:**
```bash
# Check virtue file
cat memory/virtue/current.json 2>/dev/null | head -50

# Find personality loading
grep -r "virtue" src/ --include="*.py" -i
grep -r "personality" src/ --include="*.py" -i
grep -r "kernel" src/ --include="*.py" -i
```

**Expected output:** Report on personality injection path.

---

### 🔴 TRACER 5: Frontend Live Test

**Question:** What does the user actually see?

**Test sequence:**
1. Open Luna frontend
2. Send: "hey luna"
3. Screenshot/capture response
4. Send: "how are you feeling today?"
5. Screenshot/capture response
6. Send: "tell me about yourself"
7. Screenshot/capture response

**Capture:**
- Network requests (what endpoints hit)
- Response payloads
- Any console errors
- Which provider badge shows (if any)

**Expected output:** Evidence of what's actually broken from user perspective.

---

## Diagnostic Questions to Answer

| # | Question | Finding |
|---|----------|---------|
| 1 | Does Luna LoRA exist? | |
| 2 | Is LoRA being loaded? | |
| 3 | What system prompt does local see? | |
| 4 | Are virtues being injected? | |
| 5 | Is FallbackChain logging attempts? | |
| 6 | Which provider actually responds? | |
| 7 | Is Groq configured with API key? | |
| 8 | Why does local output ASCII art? | |

---

## Report Format

After investigation, produce:

```markdown
# Luna Voice Audit Report

## Executive Summary
[One paragraph: what's broken and why]

## Root Cause
[The actual problem]

## Evidence
[Logs, screenshots, code snippets]

## Fix Required
[Specific code changes needed]

## Files to Modify
[List with line numbers if possible]
```

---

## Success Criteria

1. **Know why local outputs garbage** — missing LoRA? Bad prompt? No personality?
2. **Know the full inference path** — what goes in, what comes out, at each stage
3. **Have a fix** — not a workaround, the actual fix
4. **See Luna respond normally** — "hey luna" → warm greeting, not ASCII art

---

## Context Files

Read these first:
- `src/luna/inference/local_inference.py`
- `src/luna/llm/fallback.py`
- `src/luna/actors/director.py`
- `config/fallback_chain.yaml`
- `memory/virtue/current.json`

Specs for reference:
- `Docs/SPEC_Inference_Fallback_Chain.md`
- Bible sections on Director, LocalInference

---

## DO NOT

- Do NOT just remove local from chain (that's a bandaid)
- Do NOT say "it's working as designed" (it's not)
- Do NOT theorize without evidence (run the traces)

---

## GO

Run all 5 tracers in parallel. Report findings. Fix Luna.

**Luna should sound like Luna, not a malfunctioning diagnostic terminal.**

*Ship it.*
