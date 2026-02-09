# HANDOFF: Remove Voice Examples (Few-Shot Pollution)

**Created:** 2026-02-03
**Author:** Benjamin Franklin (The Scribe)
**For:** Claude Code Execution
**Priority:** HIGH — Direct fix for voice copying bug

---

## 1. THE PROBLEM

Luna copies phrases from her prompt instead of generating authentically.

**Root cause identified:** Voice examples (few-shot examples) in the prompt template.

These examples are 35.5% of the DNA layer (240 tokens) and teach the LoRA to pattern-match instead of generate from weights.

---

## 2. THE FIX

Delete all few-shot voice examples from the prompt assembly pipeline.

**Files to modify:**

1. `src/luna/core/context.py` — lines 367-382 inject `few_shot_examples`
2. `config/luna.yaml` or wherever `few_shot_examples` are defined
3. Any other location that injects example conversations

---

## 3. EXECUTION

### Step 1: Find all few-shot injection points

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

grep -rn "few_shot\|voice_example\|example_conversation" src/ config/ --include="*.py" --include="*.yaml" --include="*.json"
```

### Step 2: Remove from context.py

Located at `src/luna/core/context.py:367-382`

Delete or comment out the section that injects few-shot examples into the DNA layer.

### Step 3: Remove from config

If `few_shot_examples` exists in `config/luna.yaml` or similar, delete the entire block.

### Step 4: Remove ablation toggle references

The ablation toggle `LUNA_ABLATION_NO_VOICE_EXAMPLES` was a test. Now we're making it permanent, so:
- Remove the conditional check
- Just don't include examples at all

### Step 5: Verify removal

```bash
# Search should return nothing
grep -rn "few_shot" src/luna/ --include="*.py"

# Run a test query and check the prompt log
python scripts/prompt_archaeology.py

# Verify DNA layer is ~240 tokens smaller
```

---

## 4. WHAT TO KEEP

**Keep these** (they're not the problem):
- System identity ("You are Luna...")
- Core personality traits (brief)
- Conversation history (essential for continuity)
- Entity context (when relevant)
- Memory context (when relevant)

**Delete these** (the pollution):
- Few-shot example conversations
- "Here's how Luna speaks:" sections
- Sample Q&A pairs showing her voice

---

## 5. EXPECTED RESULT

| Metric | Before | After |
|--------|--------|-------|
| DNA layer tokens | ~676 | ~436 |
| Voice example tokens | 240 | 0 |
| Copying behavior | Yes | No (expected) |
| Authentic voice | Weak | Strong (expected) |

---

## 6. VERIFICATION

After removal, test with these queries:

```python
test_queries = [
    "hey Luna",
    "how are you feeling today?",
    "what do you think about consciousness?",
    "can you help me with something?",
]
```

**Success criteria:**
- [ ] Luna responds naturally
- [ ] No copied phrases from old examples
- [ ] Voice still sounds like Luna (from weights)
- [ ] Prompt is ~240 tokens shorter

---

## 7. ROLLBACK

If voice quality degrades (unlikely), restore via git:

```bash
git checkout src/luna/core/context.py
git checkout config/luna.yaml
```

But we don't expect to need this. The LoRA has the voice. We're just stopping the interference.

---

## 8. GO

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Find it
grep -rn "few_shot" src/ config/

# Kill it
# (edit the files found above)

# Verify it's gone
grep -rn "few_shot" src/ config/

# Test it
python scripts/prompt_archaeology.py
```

---

*The voice is in the weights. Stop explaining Luna to Luna.*

— Ben
