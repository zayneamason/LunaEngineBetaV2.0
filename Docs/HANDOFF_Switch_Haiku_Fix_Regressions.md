# HANDOFF: Switch to Haiku + Fix Post-Merge Regressions

**Priority:** HIGH — mainline chat behavior affected
**Scope:** 3 targeted fixes. No refactoring beyond what's listed.

---

## DO NOT

- Do NOT refactor `process()` or `_should_delegate()` beyond the specific fixes below
- Do NOT touch LunaFM, Ollama provider internals, or scoring logic
- Do NOT change any other provider configs beyond `current_provider`

---

## Fix 1: Switch active provider to Claude/Haiku

**File:** `config/llm_providers.json`

Change:
```json
"current_provider": "groq"
```
To:
```json
"current_provider": "claude"
```

Claude provider's `default_model` is already `claude-haiku-4-5-20251001`. No other changes needed.

**Verify:** Start engine, confirm logs show Haiku as active provider.

---

## Fix 2: Stale `_last_intent` in mainline chat path

**Problem:** `_should_delegate()` reads `self._last_intent`, but only `process()` (Scout path) sets it. Mainline chat callers (`_handle_director_generate()` and public `generate()`) never set it, so it defaults to `CHAT` mode → may route locally when it shouldn't.

**File:** `src/luna/actors/director.py`

**Fix:** In `_should_delegate()`, when `_last_intent` is None, default to delegating (return True) instead of defaulting to CHAT mode and potentially routing local.

Find the block where `_last_intent` is read and the fallback is applied. Change the fallback behavior so that `None` intent → delegate (safe default). The logic should be:

```python
# If intent was never classified for this call path, delegate to be safe
intent = getattr(self, '_last_intent', None)
if intent is None:
    return True  # delegate when we don't know intent
```

Do NOT restructure the rest of `_should_delegate()`. Only change the None-intent fallback.

**Verify:** 
- `grep -n "_last_intent" src/luna/actors/director.py` — confirm the None path returns True
- Import smoke test passes

---

## Fix 3: MIN_TOKEN_BUDGET too low

**Problem:** `MIN_TOKEN_BUDGET=1024` causes prompt template leakage on non-Qwen models (Haiku especially). Was tuned for Qwen3's token efficiency.

**File:** `src/luna/actors/director.py` (or wherever `MIN_TOKEN_BUDGET` is defined — check with grep)

**Fix:** Bump to 2048:
```python
MIN_TOKEN_BUDGET = 2048
```

**Verify:** Send 3 test turns through Eclissi. No `User:` / `Response:` template patterns in output.

---

## Commit

Single commit: `fix: switch to Haiku, fix stale intent fallback, bump MIN_TOKEN_BUDGET`

---

## Verification

1. Engine starts without errors
2. Logs show `claude` provider active with `claude-haiku-4-5-20251001`
3. `_should_delegate()` returns True when `_last_intent` is None
4. 3 test turns through Eclissi — no template leakage, responses coherent
5. `MIN_TOKEN_BUDGET` = 2048 confirmed via grep
