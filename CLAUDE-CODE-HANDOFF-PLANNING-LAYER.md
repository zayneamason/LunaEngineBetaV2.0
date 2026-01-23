# Claude Code Handoff: Planning Layer for Director

**Date:** 2026-01-17  
**Priority:** High  
**Effort:** ~30 minutes  

---

## The Problem

Luna doesn't know when to delegate vs answer locally. The current flow:

```
Query → Generate via Qwen → Hope Qwen outputs <REQ_CLAUDE> → (it doesn't)
```

The LoRA wasn't trained on `<REQ_CLAUDE>` delegation patterns, so Qwen either:
- Tries to answer everything (hallucinating on current events)
- Never delegates

## The Solution

Add an explicit **planning step** before generation. Use the existing `HybridInference.estimate_complexity()` to decide routing upfront:

```
Query → PLAN (complexity check) → Route → Generate appropriately
```

---

## Files to Modify

### 1. `src/luna/actors/director.py`

#### Change `_handle_director_generate()` method

**Current flow (line ~170):**
```python
# If local is available, use Qwen as Director brain
if self.local_available:
    await self._generate_with_delegation_detection(...)
else:
    await self._generate_claude_direct(...)
```

**New flow:**
```python
# PLANNING STEP: Decide routing upfront
should_delegate = await self._should_delegate(user_message)

if should_delegate:
    # Complex query → delegate to Claude, narrate in Luna's voice
    await self._generate_with_delegation(
        user_message=user_message,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        correlation_id=msg.correlation_id,
        start_time=start_time,
    )
elif self.local_available:
    # Simple query → pure local generation
    await self._generate_local_only(
        user_message=user_message,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        correlation_id=msg.correlation_id,
        start_time=start_time,
    )
else:
    # Fallback if local not available
    await self._generate_claude_direct(...)
```

#### Add new method `_should_delegate()`

```python
async def _should_delegate(self, user_message: str) -> bool:
    """
    Planning step: Decide if this query should be delegated to Claude.
    
    Uses HybridInference complexity estimation.
    Returns True if query is too complex for local model.
    """
    if not hasattr(self, '_hybrid') or self._hybrid is None:
        # No hybrid inference, check basic signals
        return self._check_delegation_signals(user_message)
    
    complexity = self._hybrid.estimate_complexity(user_message)
    logger.debug(f"Query complexity: {complexity:.2f}")
    
    # Also check explicit delegation signals
    if self._check_delegation_signals(user_message):
        return True
    
    return complexity >= self._hybrid.complexity_threshold

def _check_delegation_signals(self, user_message: str) -> bool:
    """
    Check for explicit signals that require delegation.
    
    These are things local Qwen definitely can't handle well.
    """
    msg_lower = user_message.lower()
    
    # Temporal markers (current events)
    temporal = ["latest", "current", "recent", "today", "yesterday", 
                "this week", "this month", "right now", "2025", "2026"]
    if any(t in msg_lower for t in temporal):
        return True
    
    # Explicit research requests
    research = ["search for", "look up", "find out", "research", 
                "what's happening with", "news about"]
    if any(r in msg_lower for r in research):
        return True
    
    # Complex code generation
    code = ["write a script", "implement", "build a", "create a program",
            "debug this", "fix this code"]
    if any(c in msg_lower for c in code):
        return True
    
    return False
```

#### Add new method `_generate_local_only()`

```python
async def _generate_local_only(
    self,
    user_message: str,
    system_prompt: str,
    max_tokens: int,
    correlation_id: str,
    start_time: float,
) -> None:
    """
    Pure local generation - no delegation detection needed.
    
    Used when planning step already decided this is a local query.
    """
    response_buffer = ""
    token_count = 0
    
    try:
        async for token in self._local.generate_stream(
            user_message,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
        ):
            if self._abort_requested:
                logger.info("Director: Generation aborted")
                break
            
            response_buffer += token
            token_count += 1
            await self._stream_to_callbacks(token)
        
        elapsed_ms = (time.time() - start_time) * 1000
        self._local_generations += 1
        
        logger.info(f"Director local: {token_count} tokens in {elapsed_ms:.0f}ms")
        
        await self.send_to_engine("generation_complete", {
            "text": response_buffer,
            "correlation_id": correlation_id,
            "model": "qwen-3b-local",
            "output_tokens": token_count,
            "latency_ms": elapsed_ms,
            "local": True,
            "planned": True,  # Flag that planning step was used
        })
        
    except Exception as e:
        logger.error(f"Director local generation error: {e}")
        await self.send_to_engine("generation_error", {
            "error": str(e),
            "correlation_id": correlation_id,
        })
```

#### Add new method `_generate_with_delegation()`

```python
async def _generate_with_delegation(
    self,
    user_message: str,
    system_prompt: str,
    max_tokens: int,
    correlation_id: str,
    start_time: float,
) -> None:
    """
    Planned delegation flow:
    1. Generate brief acknowledgment locally (Luna's voice)
    2. Delegate to Claude for facts
    3. Narrate facts in Luna's voice
    """
    self._delegated_generations += 1
    
    # Step 1: Quick local acknowledgment
    ack_prompt = f"""The user asked: "{user_message}"

This requires research/analysis beyond your immediate knowledge.
Give a brief, natural acknowledgment (1-2 sentences) that you're looking into it.
Be warm, be Luna. Don't be robotic."""

    try:
        ack_result = await self._local.generate(
            ack_prompt,
            system_prompt=system_prompt,
            max_tokens=50,
        )
        acknowledgment = ack_result.text.strip()
        await self._stream_to_callbacks(acknowledgment + "\n\n")
    except Exception as e:
        logger.warning(f"Acknowledgment generation failed: {e}")
        acknowledgment = "Let me look into that..."
        await self._stream_to_callbacks(acknowledgment + "\n\n")
    
    # Step 2: Delegate to Claude for facts
    facts = await self._delegate_to_claude(user_message, system_prompt)
    
    # Step 3: Narrate facts in Luna's voice
    narration = await self._narrate_facts(user_message, facts, system_prompt)
    await self._stream_to_callbacks(narration)
    
    total_elapsed_ms = (time.time() - start_time) * 1000
    
    await self.send_to_engine("generation_complete", {
        "text": acknowledgment + "\n\n" + narration,
        "correlation_id": correlation_id,
        "model": "qwen-3b-local → claude",
        "output_tokens": len(narration.split()),  # Approximate
        "latency_ms": total_elapsed_ms,
        "delegated": True,
        "planned": True,
    })
```

---

## Testing

### Add to `tests/test_director.py` or create `tests/test_planning.py`

```python
import pytest
from luna.actors.director import DirectorActor

class TestPlanningLayer:
    """Test the planning/routing logic."""
    
    def test_delegation_signals_temporal(self):
        """Temporal markers should trigger delegation."""
        director = DirectorActor()
        
        assert director._check_delegation_signals("What's the latest news?") == True
        assert director._check_delegation_signals("Current status of the project") == True
        assert director._check_delegation_signals("What happened today?") == True
        assert director._check_delegation_signals("Events in 2026") == True
    
    def test_delegation_signals_research(self):
        """Research requests should trigger delegation."""
        director = DirectorActor()
        
        assert director._check_delegation_signals("Search for AI papers") == True
        assert director._check_delegation_signals("Look up the population") == True
        assert director._check_delegation_signals("Research quantum computing") == True
    
    def test_delegation_signals_code(self):
        """Complex code requests should trigger delegation."""
        director = DirectorActor()
        
        assert director._check_delegation_signals("Write a script to parse JSON") == True
        assert director._check_delegation_signals("Implement a binary tree") == True
        assert director._check_delegation_signals("Debug this code") == True
    
    def test_no_delegation_simple(self):
        """Simple queries should NOT trigger delegation."""
        director = DirectorActor()
        
        assert director._check_delegation_signals("Hello Luna") == False
        assert director._check_delegation_signals("How are you?") == False
        assert director._check_delegation_signals("Tell me a joke") == False
        assert director._check_delegation_signals("What do you think about that?") == False
    
    def test_no_delegation_personality(self):
        """Personality/presence queries should stay local."""
        director = DirectorActor()
        
        assert director._check_delegation_signals("What's your favorite color?") == False
        assert director._check_delegation_signals("Tell me about yourself") == False
        assert director._check_delegation_signals("How do you feel?") == False
```

---

## Verification

After implementation:

```bash
# Run the new tests
pytest tests/test_planning.py -v

# Run full test suite
pytest tests/ -v

# Manual test via console
python scripts/run.py

# Test local query (should NOT delegate)
> Hey Luna, how are you?

# Test delegation query (SHOULD delegate)
> What are the latest developments in AI?
```

**Expected behavior:**
- Simple greetings → instant local response
- "Latest news" queries → acknowledgment, then researched answer
- Code requests → acknowledgment, then Claude-assisted response

---

## Architecture Note

This is the **Bible-compliant** flow:

```
User → Luna (local) decides → Handle OR Delegate
                                    ↓
                              Claude gets minimal query
                              Claude returns facts (no personality)
                                    ↓
                              Luna narrates facts in her voice
```

The planning step replaces the hope that Qwen outputs `<REQ_CLAUDE>` with an explicit routing decision. This works NOW without retraining the LoRA.

Future: Once we train the LoRA on delegation patterns, we can make planning smarter or remove it entirely.

---

## Summary

| Task | Location | Lines |
|------|----------|-------|
| Add `_should_delegate()` | director.py | ~25 |
| Add `_check_delegation_signals()` | director.py | ~25 |
| Add `_generate_local_only()` | director.py | ~40 |
| Add `_generate_with_delegation()` | director.py | ~50 |
| Modify `_handle_director_generate()` | director.py | ~15 |
| Add tests | test_planning.py | ~50 |

**Total: ~200 lines, ~30 minutes**

The delegation framework already exists. We're just adding the decision point at the front.
