# Handoff: Unified Conversation Turn Recording API

**Created:** 2025-01-25
**Status:** Ready for Implementation
**Priority:** High — Fixes voice memory persistence gap

---

## Summary

Voice conversations don't persist to memory because they bypass the extraction pipeline. The fix is to create a unified `record_conversation_turn()` API that both text and voice use, then wire voice to call it.

---

## Current State

### What Works (Text Path)
```
engine._handle_user_message()
  → _trigger_extraction("user", msg)     → Scribe → Librarian → Memory
  → matrix.store_turn(...)               → Matrix FACT nodes
  → history_manager.add_turn(...)        → Conversation history

"generation_complete" handler
  → _trigger_extraction("assistant", text)
  → matrix.store_turn(...)
  → history_manager.add_turn(...)
```

### What's Broken (Voice Path)
```
PersonaAdapter.process_message()
  → director.generate(...)
  → return response
  ❌ No extraction triggered
  ❌ No matrix storage
  ❌ No history storage
```

### Dead Code to Remove
- `ConversationManager._memory_callback` — never wired, never called
- `ConversationManager.set_memory_callback()` — dead method

---

## Implementation Tasks

### Task 1: Add `record_conversation_turn()` to LunaEngine

**File:** `src/luna/engine.py`

Add this public method (insert around line 670, near `_trigger_extraction`):

```python
async def record_conversation_turn(
    self,
    role: str,
    content: str,
    source: str = "text",
    tokens: Optional[int] = None,
) -> None:
    """
    Public API for recording conversation turns.
    
    Unified entry point for all input paths (text, voice, API).
    Handles extraction, history, and legacy storage.
    
    Args:
        role: Who spoke ("user" or "assistant")
        content: What was said
        source: Input source ("text", "voice", "api") for logging
        tokens: Optional token count (estimated if not provided)
    """
    if not content or len(content.strip()) < 5:
        logger.debug(f"Skipping trivial {role} turn ({len(content)} chars)")
        return
    
    # 1. Trigger extraction pipeline (Scribe → Librarian → Memory Matrix)
    try:
        await self._trigger_extraction(role, content)
    except Exception as e:
        logger.error(f"Extraction error for {role} turn: {e}")
    
    # 2. Store in HistoryManager (conversation continuity)
    history_manager = self.get_actor("history_manager")
    if history_manager and history_manager.is_ready:
        try:
            await history_manager.add_turn(
                role=role,
                content=content,
                tokens=tokens or len(content) // 4,
            )
        except Exception as e:
            logger.error(f"HistoryManager error for {role} turn: {e}")
    
    # 3. Store in Matrix as FACT node (legacy storage)
    matrix = self.get_actor("matrix")
    if matrix and matrix.is_ready:
        try:
            await matrix.store_turn(
                session_id=self.session_id,
                role=role,
                content=content,
                tokens=tokens,
            )
        except Exception as e:
            logger.error(f"Matrix storage error for {role} turn: {e}")
    
    logger.debug(f"📝 Recorded {source} turn: {role} ({len(content)} chars)")
```

---

### Task 2: Refactor `_handle_user_message()` to use unified API

**File:** `src/luna/engine.py`
**Location:** Around line 419-423

**Before:**
```python
# Trigger extraction on user message (async, non-blocking)
try:
    await self._trigger_extraction("user", user_message)
except Exception as e:
    logger.error(f"Extraction error for user message: {e}")
```

**After:**
```python
# Record user turn through unified API
await self.record_conversation_turn("user", user_message, source="text")
```

**Note:** The user turn storage to matrix/history_manager happens later in `_process_message_agentic()`. You'll need to check if that creates duplication and adjust accordingly. The safest approach:
- Keep `record_conversation_turn()` call here for extraction
- Remove the redundant `matrix.store_turn()` and `history_manager.add_turn()` calls from `_process_message_agentic()` (around lines 499-503 and 483-490)

---

### Task 3: Refactor `generation_complete` handler to use unified API

**File:** `src/luna/engine.py`
**Location:** Around line 793-806

**Before:**
```python
# Store assistant turn in HistoryManager
history_manager = self.get_actor("history_manager")
if history_manager and history_manager.is_ready:
    estimated_tokens = data.get("output_tokens") or (len(text) // 4)
    await history_manager.add_turn(
        role="assistant",
        content=text,
        tokens=estimated_tokens
    )

# Store assistant turn in memory (legacy Matrix storage)
matrix = self.get_actor("matrix")
if matrix and matrix.is_ready:
    await matrix.store_turn(
        session_id=self.session_id,
        role="assistant",
        content=text,
        tokens=data.get("output_tokens"),
    )

# Trigger extraction on Luna's response
try:
    await self._trigger_extraction("assistant", text)
except Exception as e:
    logger.error(f"Extraction error for assistant message: {e}")
```

**After:**
```python
# Record assistant turn through unified API
await self.record_conversation_turn(
    role="assistant",
    content=text,
    source="text",
    tokens=data.get("output_tokens"),
)
```

---

### Task 4: Wire Voice to use unified API

**File:** `src/voice/persona_adapter.py`
**Location:** After line 196 (after getting response from director)

Find this section (approximately):
```python
if response and response.response:
    response_text = response.response
    # ... logging and prosody stuff ...
```

**Add after getting `response_text`:**
```python
# Record conversation turns through unified engine API
if self._engine and hasattr(self._engine, 'record_conversation_turn'):
    try:
        # Record user turn
        await self._engine.record_conversation_turn(
            role="user",
            content=message,
            source="voice",
        )
        # Record assistant turn
        if response_text:
            await self._engine.record_conversation_turn(
                role="assistant",
                content=response_text,
                source="voice",
            )
    except Exception as e:
        logger.error(f"Failed to record voice turns: {e}")
```

---

### Task 5: Remove dead code from ConversationManager

**File:** `src/voice/conversation/manager.py`

**Remove these sections:**

1. Remove the `_memory_callback` attribute (line 37):
```python
# DELETE THIS LINE:
self._memory_callback: Optional[callable] = None
```

2. Remove the `set_memory_callback()` method (lines 39-48):
```python
# DELETE THIS ENTIRE METHOD:
def set_memory_callback(self, callback: callable):
    """
    Set callback for memory persistence.

    Args:
        callback: Function(role: str, content: str, timestamp: int) -> None
    """
    self._memory_callback = callback
    if callback:
        logger.info("Memory callback configured for conversation persistence")
```

3. Remove the callback invocation in `end_turn()` (lines 85-94):
```python
# DELETE THIS BLOCK:
# Persist to memory if callback configured
if self._memory_callback:
    try:
        self._memory_callback(
            role="user" if turn.speaker == Speaker.USER else "assistant",
            content=text,
            timestamp=int(turn.started_at.timestamp())
        )
    except Exception as e:
        logger.error(f"Memory persistence failed: {e}")
```

---

## Testing

After implementation, verify with these tests:

### Test 1: Voice Memory Persistence
```python
# Start voice backend with engine
# Say something via voice
# Check Memory Matrix for the conversation:
sqlite3 data/luna_engine.db "SELECT * FROM memory_nodes WHERE content LIKE '%[user]%' ORDER BY created_at DESC LIMIT 5;"
```

### Test 2: Extraction Pipeline
```bash
# Watch logs for extraction messages
# Should see: "📝 Extraction triggered for user turn"
# Should see: "📝 Recorded voice turn: user (X chars)"
```

### Test 3: No Duplication
```python
# Send a text message
# Verify only ONE entry per turn in:
# - memory_nodes table
# - conversation_history table (if exists)
```

### Test 4: Run Existing Tests
```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
pytest tests/test_scribe.py tests/test_librarian.py tests/test_voice.py -v
```

---

## Architecture After Fix

```
┌─────────────────────────────────────────────────────────────────────┐
│                     INPUT SOURCES                                    │
├─────────────────┬─────────────────┬─────────────────────────────────┤
│   Text (CLI)    │   Voice (STT)   │        API (HTTP)               │
└────────┬────────┴────────┬────────┴────────────────┬────────────────┘
         │                 │                          │
         └────────────────►│◄─────────────────────────┘
                           │
                           ▼
         ┌─────────────────────────────────────────┐
         │   engine.record_conversation_turn()     │
         │   ─────────────────────────────────────  │
         │   • role: "user" | "assistant"          │
         │   • content: str                        │
         │   • source: "text" | "voice" | "api"    │
         └─────────────────┬───────────────────────┘
                           │
         ┌─────────────────┼───────────────────────┐
         │                 │                       │
         ▼                 ▼                       ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ _trigger_       │ │ history_manager │ │ matrix.store_   │
│ extraction()    │ │ .add_turn()     │ │ turn()          │
└────────┬────────┘ └─────────────────┘ └─────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    EXTRACTION PIPELINE                               │
├─────────────────────────────────────────────────────────────────────┤
│  Scribe (Ben Franklin)  →  Librarian (The Dude)  →  Memory Matrix   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Files Modified

| File | Changes |
|------|---------|
| `src/luna/engine.py` | Add `record_conversation_turn()`, refactor 2 call sites |
| `src/voice/persona_adapter.py` | Add calls to `record_conversation_turn()` |
| `src/voice/conversation/manager.py` | Remove dead `memory_callback` code |

---

## Acceptance Criteria

- [ ] `record_conversation_turn()` method exists on LunaEngine
- [ ] Text conversations still persist to memory (no regression)
- [ ] Voice conversations now persist to memory
- [ ] No duplicate entries for the same turn
- [ ] Dead `memory_callback` code removed
- [ ] All existing tests pass
- [ ] Luna can remember voice conversations (test with "do you remember...")

---

## Notes

- The `source` parameter is for logging/debugging only — all sources get the same treatment
- Error handling is per-subsystem (extraction failure shouldn't block history storage)
- Token estimation uses `len(content) // 4` as a reasonable approximation
- The existing `_trigger_extraction()` method remains as an internal implementation detail
