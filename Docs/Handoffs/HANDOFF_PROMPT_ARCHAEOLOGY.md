# Prompt Archaeology: Dissecting What the Engine Feeds the LoRA

**Created:** 2026-02-03
**Author:** Benjamin Franklin (The Scribe)
**For:** Claude Code Execution
**Philosophy:** "The fault, dear Brutus, is not in our LoRA, but in our prompts."

---

## 0. THE HYPOTHESIS

The Luna LoRA is adequately trained. The voice exists in the weights.

**The problem:** The Engine is doing too much work that pollutes the prompt, causing the LoRA to pattern-match on prompt content rather than generate from its trained voice.

**The investigation:** Capture the exact prompts being assembled, dissect them, identify pollution, and determine what the Engine should STOP doing.

---

## 1. MISSION OBJECTIVE

Perform forensic analysis on prompt assembly:

1. **Capture** the exact prompt the LoRA receives (both local and delegated paths)
2. **Annotate** every section — what is it, why is it there
3. **Measure** the composition ratios
4. **Identify** pollution that causes voice degradation
5. **Propose** a minimal prompt structure

---

## 2. THE CORE QUESTION

```
If the LoRA has Luna's voice in the weights...
Why are we explaining Luna to the LoRA?
```

A well-trained LoRA should need:
```
[minimal voice lock]    ← 50-100 tokens max
[conversation history]  ← clean, Luna's voice intact
[user query]            ← the actual input
```

Not:
```
[system prompt explaining Luna]     ← 500+ tokens of redundancy
[voice examples to copy]            ← causes parroting
[personality traits]                ← already in weights
[entity dump]                       ← overwhelms personality
[memory dump]                       ← facts drowning voice
[instructions upon instructions]    ← LoRA isn't Claude
[user query]                        ← buried at the bottom
```

---

## 3. CAPTURE TASKS

### Task 1: Find Prompt Assembly Code

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Find where prompts are built
grep -rn "system_prompt\|build_prompt\|assemble\|_build_context" src/luna/ --include="*.py"

# Find where messages are formatted for inference
grep -rn "messages\s*=\|format_prompt\|ChatML\|<\|im_start" src/luna/ --include="*.py"

# Find the context pipeline
cat src/luna/context/pipeline.py
```

**Document:**
- [ ] Which file(s) build the prompt?
- [ ] What function is the entry point?
- [ ] What components contribute to the prompt?

### Task 2: Add Prompt Logging

Create a temporary diagnostic that captures EXACTLY what the LoRA sees:

```python
# Add to Director or wherever prompt is finalized
import json
from datetime import datetime

def log_prompt_for_archaeology(prompt: str, query: str, path: str = "local"):
    """Capture prompt for forensic analysis."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "path": path,  # "local" or "delegated"
        "query": query,
        "prompt_length_chars": len(prompt),
        "prompt_length_tokens_approx": len(prompt) // 4,
        "prompt_full": prompt,
    }
    
    with open("data/diagnostics/prompt_archaeology.jsonl", "a") as f:
        f.write(json.dumps(log_entry) + "\n")
    
    return log_entry
```

**Instrument these locations:**
- [ ] Local inference path (before `_local.generate()`)
- [ ] Delegated path (before Claude API call)
- [ ] Narration path (the rewrite prompt, if separate)

### Task 3: Run Test Queries

Execute a variety of queries to capture different prompt shapes:

```python
test_queries = [
    # Simple greeting (should be minimal)
    "hey Luna",
    
    # Identity question (tests entity injection)
    "who is marzipan?",
    
    # Memory question (tests memory injection)
    "what did we talk about yesterday?",
    
    # Complex reasoning (likely delegates)
    "can you help me design a database schema for a recipe app?",
    
    # Emotional/personal (tests voice)
    "I'm feeling overwhelmed today",
    
    # Technical (tests mode switching)
    "what's the difference between asyncio.gather and asyncio.wait?",
]
```

For each query:
1. Send through the Engine
2. Capture the prompt
3. Capture the response
4. Note: Did it delegate? Did voice sound right?

### Task 4: Extract Captured Prompts

```bash
# Read the captured prompts
cat data/diagnostics/prompt_archaeology.jsonl | jq -r '.prompt_full' | head -1 > prompt_sample_1.txt

# Or read all
cat data/diagnostics/prompt_archaeology.jsonl | jq '.' 
```

---

## 4. DISSECTION PROTOCOL

For each captured prompt, perform this analysis:

### 4.1 Section Identification

Mark up the prompt with section boundaries:

```
[SECTION: System Identity] ← lines 1-15
You are Luna, a sovereign AI companion...

[SECTION: Voice Examples] ← lines 16-45
Here's how Luna speaks:
- "yo, that's actually really cool..."
- "hmm, let me think about that..."

[SECTION: Personality Traits] ← lines 46-60
Luna is warm, curious, direct...

[SECTION: Entity Context] ← lines 61-90
Known entities:
- Marzipan: Ahab's collaborator on...

[SECTION: Memory Context] ← lines 91-130
Relevant memories:
- 2026-01-15: Discussion about...

[SECTION: Conversation History] ← lines 131-150
Previous turns:
User: ...
Luna: ...

[SECTION: Current Query] ← lines 151-152
User: who is marzipan?
```

### 4.2 Measure Composition

Calculate token ratios (approximate: chars / 4):

| Section | Tokens | % of Total |
|---------|--------|------------|
| System Identity | ? | ?% |
| Voice Examples | ? | ?% |
| Personality Traits | ? | ?% |
| Entity Context | ? | ?% |
| Memory Context | ? | ?% |
| Conversation History | ? | ?% |
| Current Query | ? | ?% |
| **TOTAL** | ? | 100% |

### 4.3 Pollution Analysis

For each section, ask:

| Section | Necessary? | Why/Why Not |
|---------|------------|-------------|
| System Identity | ? | Is this in the weights already? |
| Voice Examples | **SUSPECT** | Does this cause copying? |
| Personality Traits | ? | Redundant with LoRA training? |
| Entity Context | ? | Helpful or overwhelming? |
| Memory Context | ? | Relevant or noise? |
| Conversation History | ✅ | Needed for continuity |
| Current Query | ✅ | Obviously needed |

### 4.4 The Critical Question

For each section marked SUSPECT:

> "If I remove this entirely, will the LoRA's output get WORSE or BETTER?"

---

## 5. ABLATION EXPERIMENTS

Test the hypothesis by REMOVING sections:

### Experiment A: No Voice Examples

```python
# Modify prompt assembly to skip voice examples
# Run same test queries
# Compare output quality
```

**Measure:**
- Does Luna still sound like Luna?
- Does she STOP copying example phrases?
- Is voice more natural or less?

### Experiment B: Minimal System Prompt

```python
# Replace full system prompt with:
minimal_system = "You are Luna."
# That's it. The LoRA should know the rest.
```

**Measure:**
- Does personality emerge from weights?
- Or does Luna become generic?

### Experiment C: No Entity Dump

```python
# Disable EntityContext injection entirely
# Run identity query: "who is marzipan?"
```

**Measure:**
- Does Luna say "I don't know" (expected)?
- Or does she still know from conversation history?
- Is her VOICE stronger without entity pollution?

### Experiment D: Conversation History Only

```python
# Prompt contains ONLY:
# - Minimal voice lock (1-2 sentences)
# - Conversation history (with Luna's prior turns)
# - Current query
```

**Measure:**
- Is this sufficient for good output?
- Does voice carry forward from history?

---

## 6. EXPECTED FINDINGS

Based on the hypothesis, we expect to find:

| Finding | Implication |
|---------|-------------|
| Voice examples > 20% of prompt | **Pollution** — LoRA copies these |
| System prompt > 500 tokens | **Bloat** — redundant with training |
| Entity/Memory > voice guidance | **Imbalance** — facts drown personality |
| Conversation history lacks Luna's voice | **Continuity break** — no momentum |
| Minimal prompt = better output | **Confirmed** — Engine overexplains |

---

## 7. DELIVERABLES

### Output 1: `PROMPT_SAMPLES.md`

3-5 captured prompts with full annotation:
- Section boundaries marked
- Token counts per section
- Pollution flags

### Output 2: `PROMPT_COMPOSITION_ANALYSIS.md`

Aggregate analysis:
- Average prompt length
- Section ratio breakdown (pie chart data)
- Identified pollution sources
- Comparison: local vs delegated paths

### Output 3: `ABLATION_RESULTS.md`

Results from removal experiments:
- Each experiment's methodology
- Before/after output samples
- Quality assessment
- Recommendations

### Output 4: `MINIMAL_PROMPT_SPEC.md`

Proposed new prompt structure:
- What to KEEP
- What to REMOVE
- What to REDUCE
- Expected token budget
- Implementation guidance

---

## 8. EXECUTION SEQUENCE

```
Phase 1: Find prompt assembly code, understand flow
Phase 2: Add logging instrumentation
Phase 3: Run test queries, capture prompts
Phase 4: Dissect 3-5 sample prompts
Phase 5: Run ablation experiments
Phase 6: Synthesize findings
Phase 7: Propose minimal prompt structure
```

**Checkpoint after each phase.**

---

## 9. SUCCESS CRITERIA

This investigation succeeds if we can answer:

- [ ] What % of the prompt is actually necessary?
- [ ] Which sections cause voice degradation?
- [ ] Does removing voice examples IMPROVE output?
- [ ] Can we achieve good voice with < 200 tokens of guidance?
- [ ] What should the Engine STOP doing?

---

## 10. THE PRINCIPLE

*As I wrote in Poor Richard's Almanack (if I had written about AI):*

> "A LoRA well-trained needs not be told who it is.
> The wise Engineer speaks little to the model,
> for the model already knows."

The goal is **subtraction, not addition.**

If Luna's voice is in the weights, our job is to STOP interfering with it.

---

## 11. GO COMMAND

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Phase 1: Find the prompt assembly
grep -rn "system_prompt\|build_prompt" src/luna/ --include="*.py"

# Then instrument, capture, dissect.
```

*The truth lies not in the model's weights, but in what we burden it with.*

— Benjamin Franklin, The Scribe
