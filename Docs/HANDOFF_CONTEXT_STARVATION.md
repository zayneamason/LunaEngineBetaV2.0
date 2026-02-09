# HANDOFF: Context Starvation — Luna's Empty System Prompt

**Date:** 2026-02-04
**Priority:** P0 — Root cause of personality drift
**Type:** Investigation + Fix

---

## THE PROBLEM

Luna's system prompts are nearly empty. Prompt Archaeology logs show:

| Query | System Prompt | Expected |
|-------|---------------|----------|
| "What do you remember about my programming preferences?" | 791 chars | 3000-5000 chars |
| "what is 2+2?" | 185 chars | 1500+ chars |

**What's being sent:**
```
You are Luna, a sovereign AI companion.
Be warm, direct, and natural. Never output internal reasoning or debugging info.
Never use generic chatbot greetings like "How can I help you?"
```

**What SHOULD be sent:**
- DNA Layer (core identity, voice constraints)
- Experience Layer (personality patches from memory)
- Mood Layer (current conversational state)
- Memory Context (relevant retrieved memories)
- Conversation History (recent turns)
- Entity Context (who Luna is talking to)

---

## EVIDENCE

### Prompt Archaeology Logs
Location: `data/diagnostics/prompt_archaeology.jsonl`

Sample entry:
```json
{
  "timestamp": "2026-02-03T06:49:14.680853",
  "query": "what is 2+2?",
  "total_chars": 185,
  "total_tokens_approx": 9,
  "sections": {
    "IDENTITY_PREAMBLE": {"chars": 39, "tokens_approx": 9, "percent": 100.0}
  },
  "pollution_warning": null
}
```

Only `IDENTITY_PREAMBLE` detected. Missing:
- `DNA_FOUNDATION`
- `EXPERIENCE_LAYER`
- `MOOD_LAYER`
- `MEMORY_CONTEXT`
- `THIS_SESSION`
- `KNOWN_PEOPLE`
- `RETRIEVED_CONTEXT`

### QA System Confirms
```json
{
  "personality_injected": false,
  "personality_length": 0,
  "system_prompt": "",
  "virtues_loaded": false
}
```

---

## WHERE TO LOOK

### Primary: Director Actor
`src/luna/actors/director.py`

Key methods that build system prompt:
1. `process()` — Main entry point (line ~534)
2. `_load_emergent_prompt()` — Should load 3-layer personality (line ~447)
3. `_load_identity_buffer()` — Fallback identity loading (line ~400)
4. `_fetch_memory_context()` — Memory retrieval (line ~1350)
5. `_build_local_context_fallback()` — Legacy context assembly (line ~1290)

Search for where `system_prompt` gets assigned. There are multiple code paths:
- Delegated path (line ~563-707)
- Local path (line ~804-877)
- Fallback path (line ~877+)

### Secondary: Context Pipeline
`src/luna/context/pipeline.py`

This is supposed to unify context assembly. Check:
- `ContextPipeline.build()` — Should return full `ContextPacket`
- `ContextPacket.system_prompt` — The assembled prompt

### Tertiary: Identity Buffer
`src/luna/entities/context.py`

- `EntityContext.load_identity_buffer()` — Loads Luna's identity
- `IdentityBuffer.to_prompt()` — Formats identity for prompt
- `IdentityBuffer.get_emergent_prompt()` — Gets full 3-layer personality

---

## HYPOTHESIS

The context assembly is short-circuiting somewhere. Likely causes:

1. **Entity context not initialized** — `_ensure_entity_context()` returns False
2. **Emergent prompt fails silently** — Exception caught, falls through to minimal prompt
3. **Context pipeline not available** — `CONTEXT_PIPELINE_AVAILABLE = False`
4. **Memory Matrix not ready** — `matrix.is_ready = False`

### Diagnostic Questions
1. Is `_entity_context` None when `process()` runs?
2. Does `_load_emergent_prompt()` return None or empty string?
3. Is `_context_pipeline` None?
4. What does `await self._ensure_entity_context()` return?

---

## INVESTIGATION STEPS

### Step 1: Add Diagnostic Logging
In `Director.process()`, add at the start:
```python
logger.info(f"[CONTEXT-STARVE] _entity_context: {self._entity_context}")
logger.info(f"[CONTEXT-STARVE] _context_pipeline: {self._context_pipeline}")
logger.info(f"[CONTEXT-STARVE] _patch_manager: {self._patch_manager}")
logger.info(f"[CONTEXT-STARVE] _identity_buffer: {self._identity_buffer}")
```

### Step 2: Trace _load_emergent_prompt
In `_load_emergent_prompt()`, add logging before each return:
```python
logger.info(f"[EMERGENT] Result: {len(result) if result else 'None'} chars")
```

### Step 3: Check Context Pipeline Init
In `_init_entity_context()`, verify each step succeeds:
```python
logger.info(f"[INIT] EntityContext created: {self._entity_context is not None}")
logger.info(f"[INIT] PatchManager created: {self._patch_manager is not None}")
logger.info(f"[INIT] ContextPipeline created: {self._context_pipeline is not None}")
```

### Step 4: Run Test Query
Send a simple query through Luna and collect:
- Console logs with `[CONTEXT-STARVE]` prefix
- Updated prompt_archaeology.jsonl
- QA report via `qa_get_last_report`

---

## EXPECTED FIX

Once you find where context assembly fails, the fix is likely:

1. **If entity context not initializing:**
   - Check Matrix actor readiness
   - Ensure database path is valid
   - Verify lazy init timing

2. **If emergent prompt failing:**
   - Check `voice_config` file exists
   - Verify `PersonalityPatchManager` has patches
   - Ensure `get_emergent_prompt()` succeeds

3. **If context pipeline not available:**
   - Check import succeeds
   - Verify `pipeline.initialize()` completes
   - Ensure `packet.system_prompt` is populated

---

## SUCCESS CRITERIA

After fix, Prompt Archaeology logs should show:

```json
{
  "total_chars": 3500,
  "total_tokens_approx": 875,
  "sections": {
    "IDENTITY_PREAMBLE": {"chars": 39, "tokens_approx": 9},
    "DNA_FOUNDATION": {"chars": 800, "tokens_approx": 200},
    "EXPERIENCE_LAYER": {"chars": 600, "tokens_approx": 150},
    "MOOD_LAYER": {"chars": 200, "tokens_approx": 50},
    "MEMORY_CONTEXT": {"chars": 1000, "tokens_approx": 250}
  }
}
```

And QA should report:
```json
{
  "personality_injected": true,
  "personality_length": 3500,
  "virtues_loaded": true
}
```

---

## FILES TO MODIFY

| File | Purpose |
|------|---------|
| `src/luna/actors/director.py` | Main context assembly |
| `src/luna/context/pipeline.py` | Unified context pipeline |
| `src/luna/entities/context.py` | Entity/identity loading |
| `src/luna/entities/bootstrap.py` | Personality bootstrap |

---

## RELATED DOCS

- `Docs/HANDOFF_PROMPT_ARCHAEOLOGY.md` — Archaeology system docs
- `Docs/Tuning_System_Analysis.md` — Tuning system investigation
- `src/luna/qa/validator.py` — QA assertions reference

---

## NOTES

This is the root cause of Luna's personality drift. She's not failing to retrieve memories or struggling with attention — she's simply not receiving any context at all. The LLM is generating responses from a nearly empty system prompt.

Fix this first. Everything else is downstream.
