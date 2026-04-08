# HANDOFF: Swap SubtaskRunner Backend from Qwen 3B to Haiku

**Priority:** P1 — Unblocks agentic routing  
**Date:** 2026-03-25  
**Time estimate:** 20 minutes  
**Risk:** Low — additive, falls back gracefully  
**Depends on:** FTS5 fix (already on disk and working)

---

## Why

Qwen 3B via MLX won't load reliably on this machine. The model file exists, MLX imports fine, standalone loading works — but during engine boot it fails with "local model not available." Debugging the MLX timing issue is a rabbit hole.

Meanwhile, the SubtaskRunner does 4 simple classification tasks (intent, entities, query rewrite, query decomposition) that take <60 tokens of output each. Haiku does these faster (300-500ms vs 800-1500ms), more reliably (API vs finicky MLX loading), and at negligible cost (~$0.0001/query for 4 parallel classification calls).

The agentic routing upgrade at engine.py line 1228 requires intent classification to fire. Without the SubtaskRunner, it falls back to a keyword heuristic (line 1251) which is rougher. With Haiku doing the classification, Luna gets proper intent-based routing to the AgentLoop.

**Sovereignty note:** The subtask calls are classification/routing — not Luna's voice, not her personality, not her responses. It's the equivalent of a calculator deciding which drawer to open. Using Haiku for this does NOT compromise Luna's sovereignty model. The actual generation still goes through whatever provider is configured (currently Haiku for delegation, but that's a separate path).

---

## The Architecture

The `LocalSubtaskRunner` calls its backend through one interface point:

```python
# In _run_with_timeout (line ~175):
result = await self._local.generate(
    user_message=prompt,
    system_prompt=None,
    max_tokens=max_tokens,
)
# And checks availability via:
self._local.is_loaded
```

We create a `HaikuSubtaskBackend` that implements the same interface — `generate()` and `is_loaded` — but calls the existing `ClaudeProvider` instead of MLX.

---
## Change 1: Create the Haiku Backend Adapter

**New file:** `src/luna/inference/haiku_subtask_backend.py`

```python
"""
Haiku Subtask Backend
=====================

Drop-in replacement for LocalInference that calls Claude Haiku
via the existing ClaudeProvider for lightweight classification tasks.

Same interface as LocalInference:
  - .is_loaded -> bool
  - .generate(user_message, system_prompt, max_tokens) -> result with .text
"""

import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class HaikuResult:
    """Mimics LocalInference result shape."""
    text: str


class HaikuSubtaskBackend:
    """
    Calls Claude Haiku for subtask classification.
    
    Implements the same interface as LocalInference so it slots
    directly into LocalSubtaskRunner without changes to the runner.
    """

    HAIKU_MODEL = "claude-haiku-4-5-20251001"

    def __init__(self):
        self._client = None
        self._available = False
        self._init_client()

    def _init_client(self):
        """Initialize the Anthropic client."""
        try:
            import anthropic
            self._client = anthropic.Anthropic()
            # Quick validation — will throw if no API key
            self._available = self._client.api_key is not None
            if self._available:
                logger.info("[HAIKU-SUBTASK] Backend ready (model: %s)", self.HAIKU_MODEL)
            else:
                logger.warning("[HAIKU-SUBTASK] No API key found")
        except ImportError:
            logger.warning("[HAIKU-SUBTASK] anthropic package not installed")
        except Exception as e:
            logger.warning("[HAIKU-SUBTASK] Init failed: %s", e)

    @property
    def is_loaded(self) -> bool:
        """Compatible with LocalInference.is_loaded check."""
        return self._available

    async def generate(
        self,
        user_message: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 60,
        **kwargs,
    ) -> HaikuResult:
        """
        Call Haiku for a classification subtask.
        
        Compatible with LocalInference.generate() signature.
        Runs synchronous Anthropic call in thread to stay async-friendly.
        """
        import asyncio

        def _call():
            messages = [{"role": "user", "content": user_message}]
            create_kwargs = {
                "model": self.HAIKU_MODEL,
                "max_tokens": max_tokens,
                "temperature": 0.0,
                "messages": messages,
            }
            if system_prompt:
                create_kwargs["system"] = system_prompt
            response = self._client.messages.create(**create_kwargs)
            return response.content[0].text

        text = await asyncio.get_event_loop().run_in_executor(None, _call)
        return HaikuResult(text=text)
```

---
## Change 2: Update Engine Boot to Use Haiku Backend as Fallback

**File:** `src/luna/engine.py` — around line 577

**Current code:**
```python
        # Initialize LocalSubtaskRunner (Qwen 3B lightweight agentic dispatch)
        if SUBTASK_RUNNER_AVAILABLE:
            director = self.get_actor("director")
            if director and director._enable_local and not director.local_available:
                await director._init_local_inference()
            if director and director.local_available:
                self._subtask_runner = LocalSubtaskRunner(director._local)
                logger.info("LocalSubtaskRunner initialized (Qwen 3B subtasks active)")
            else:
                logger.info("LocalSubtaskRunner skipped (local model not available)")
        else:
            logger.debug("LocalSubtaskRunner module not available")
```

**Replace with:**
```python
        # Initialize SubtaskRunner — try Qwen first, fall back to Haiku
        if SUBTASK_RUNNER_AVAILABLE:
            subtask_backend = None

            # Try 1: Qwen 3B local (sovereign, offline-capable)
            director = self.get_actor("director")
            if director and director._enable_local and not director.local_available:
                await director._init_local_inference()
            if director and director.local_available:
                subtask_backend = director._local
                logger.info("SubtaskRunner using Qwen 3B (local)")

            # Try 2: Haiku API (fast, reliable, negligible cost)
            if subtask_backend is None:
                try:
                    from luna.inference.haiku_subtask_backend import HaikuSubtaskBackend
                    haiku = HaikuSubtaskBackend()
                    if haiku.is_loaded:
                        subtask_backend = haiku
                        logger.info("SubtaskRunner using Haiku API (Qwen unavailable)")
                except Exception as e:
                    logger.warning(f"Haiku subtask backend failed: {e}")

            # Wire it up
            if subtask_backend is not None:
                self._subtask_runner = LocalSubtaskRunner(subtask_backend)
                logger.info("LocalSubtaskRunner initialized")
            else:
                logger.warning("SubtaskRunner unavailable (no local model, no Haiku API)")
        else:
            logger.debug("LocalSubtaskRunner module not available")
```

**What this does:** Tries Qwen first (sovereignty). If Qwen fails (which it currently does), falls back to Haiku via the adapter. The `LocalSubtaskRunner` doesn't care which backend it's talking to — both implement `generate()` and `is_loaded`.

---
## What Changes End-to-End

### Before (broken):
```
User: "What evidence does Lansing present for the water temple system?"
  → SubtaskRunner: unavailable (Qwen won't load)
  → Intent classification: NONE
  → Routing: keyword fallback catches "evidence" → AgentLoop (rough)
  → OR: keyword fallback misses → stays DIRECT (no agentic retrieval)
```

### After (with Haiku backend):
```
User: "What evidence does Lansing present for the water temple system?"
  → SubtaskRunner: Haiku backend (~400ms total for 4 parallel calls)
  → Intent: {"intent": "research", "complexity": "complex", "tools": []}
  → Entities: [{"name": "Lansing", "type": "person"}, {"name": "water temple", "type": "concept"}]
  → Query rewrite: "Lansing evidence water temple system optimal" (resolves conversational phrasing)
  → Decomposition: ["Lansing simulation model evidence", "water temple scheduling optimization"]
  → Routing: intent=research + Nexus sparse → AgentLoop (precise)
  → AgentLoop: uses decomposed queries for targeted multi-step retrieval
```

The key improvement: intent classification gives the router REAL signal instead of keyword matching. And query rewriting + decomposition feed BETTER queries into the FTS5 search (which now works thanks to the OR fix).

---

## Tradeoffs

| | Qwen 3B (local) | Haiku (API) |
|---|---|---|
| Latency per subtask | 800-1500ms on M1 | 300-500ms |
| All 4 subtasks parallel | ~1500ms | ~500ms |
| Cost | Free | ~$0.0001 per message (4 calls × ~100 tokens each) |
| Offline | Yes | No |
| Reliability | Broken (won't load) | Works today |
| Quality | Good for JSON classification | Better for JSON classification |

**At ~$0.0001 per message, 1000 messages/day would cost $0.10/day.** This is negligible. And the subtask calls are tiny — 60-100 tokens of output each, all structured JSON.

---

## Keeping Qwen as Primary (Future)

The boot order tries Qwen first. When the MLX loading issue is eventually fixed, Qwen automatically takes over — no code changes needed. Haiku only fires when `director.local_available` is False.

For fully offline deployments (the sovereignty use case), the Haiku backend simply won't initialize (no API key), and the system falls through to the keyword fallback at line 1251 of engine.py. Three tiers:
1. Qwen (local, sovereign) — preferred
2. Haiku (API, fast, reliable) — fallback
3. Keyword heuristic (no inference) — last resort

---

## Verification

After implementation, restart the engine and check logs for:

```
SubtaskRunner using Haiku API (Qwen unavailable)
LocalSubtaskRunner initialized
```

Then ask Luna in Eclissi: "What specific evidence does Lansing present that the traditional system was optimal?"

Check engine logs for:
```
[SUBTASK-PHASE] Complete in ~500ms: intent=yes entities=2 rewritten=yes decomposed=2
[ROUTING] Upgrading to AgentLoop (knowledge-sparse research query)
```

If you see intent=yes, the Haiku backend is working. If you see the routing upgrade, the full agentic path is live.

---

## What NOT To Do

- Do NOT remove or modify the Qwen loading code — it stays as the primary path
- Do NOT change the `LocalSubtaskRunner` class — it's backend-agnostic already
- Do NOT modify the prompts (INTENT_PROMPT, ENTITY_PROMPT, etc.) — they work for both Qwen and Haiku
- Do NOT increase timeout beyond 2000ms for Haiku — it should complete in <500ms
- Do NOT use Sonnet for subtasks — Haiku is sufficient and 10x cheaper for classification
- Do NOT remove the keyword fallback at line 1251 — it's the offline safety net

---

## Files

| File | Action |
|---|---|
| `src/luna/inference/haiku_subtask_backend.py` | **NEW** — ~90 lines, Haiku adapter |
| `src/luna/engine.py` | **EDIT** — ~15 lines changed in boot sequence (line ~577) |
