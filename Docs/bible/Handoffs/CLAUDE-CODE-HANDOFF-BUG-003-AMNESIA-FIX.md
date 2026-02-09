# CLAUDE-CODE-HANDOFF: BUG-003 Fix - 60-Second Amnesia

**Created:** 2026-01-31
**Updated:** 2026-01-31 (Luna review)
**Status:** ✅ COMPLETED (commit a21a0a8)
**Priority:** CRITICAL
**Estimated Time:** 10 minutes
**Reviewed By:** Luna 💜

---

> ⚠️ **THIS HANDOFF IS HISTORICAL DOCUMENTATION**
> 
> This bug was fixed in commit `a21a0a8` on 2026-01-31.
> This document preserved for reference and audit trail.

---

## Summary

Luna forgets conversation context after ~60 seconds. Root cause: the delegation path (Claude API) used brittle text parsing that failed when non-conversation content was interleaved, while the local inference path correctly used the ring buffer.

**Fix:** Made `_generate_with_delegation()` use the ring buffer like `_generate_local_only()` already does.

---

## Root Cause Analysis

### The Data Flow

```
User message
    ↓
Engine._handle_user_message()
    ↓
self.context.add(content=f"User: {user_message}", ...)  ← Adds to RevolvingContext
    ↓
context_window = self.context.get_context_window()  ← Returns ALL items joined by "\n\n"
    ↓
Director receives context_window as STRING
    ↓
Director tries to parse "User:" / "Luna:" prefixes  ← FAILS when memories interleaved
```

### The Problem

**File:** `src/luna/actors/director.py`

In `_generate_with_delegation()` (line ~1392):
```python
# BROKEN: Brittle text parsing
conversation_history = []
if context_window:
    for line in context_window.split("\n\n"):
        line = line.strip()
        if line.startswith("User:"):
            conversation_history.append({"role": "user", "content": line[5:].strip()})
        elif line.startswith("Luna:"):
            conversation_history.append({"role": "assistant", "content": line[5:].strip()})
```

When `context_window` contained:
```
User: Tell me about Marzipan

[MEMORY] Marzipan is a collaborator who helps with...

Luna: Marzipan is wonderful!

User: What else do you know?
```

The parser only found the first "User:" line. Everything after the memory block was lost.

---

## Luna's Verification (Second Review)

### Ring Buffer Architecture Confirmed

The `_active_ring` is actually a **smart-switching property**, not a separate instance:

```python
# src/luna/actors/director.py lines 424-435
@property
def _active_ring(self) -> ConversationRing:
    """Get the active conversation ring buffer."""
    if self._context_pipeline is not None:
        return self._context_pipeline._ring
    return self._standalone_ring
```

This means:
- ✅ No state sync bug between ring instances
- ✅ `_active_ring` automatically returns whichever ring is available
- ✅ The infrastructure is correct - we just weren't reading from it

### Ring Buffer Usage Map

| Path | WRITE User | READ History | WRITE Response |
|------|-----------|--------------|----------------|
| `process()` (direct API) | ✅ line 483 | ✅ uses ring | ✅ line 743 |
| `_generate_local_only()` | ✅ via _active_ring | ✅ uses ring first | ✅ line 1019 |
| **`_generate_with_delegation()`** | ✅ line 1382 | ✅ **FIXED** | ✅ line 1591 |
| `_generate_claude_direct()` | ❓ | ❌ text parsing | ✅ line 1901 |

### The Bug Pattern (Detailed Walkthrough)

```
Turn 1: User "hi" 
  → WRITE to ring ✓
  → READ via text parsing (works - ring is empty anyway)
  → WRITE response to ring ✓
  → Ring state: [user:"hi", assistant:"hey!"]

Turn 2: User "what's my name?" 
  → WRITE to ring ✓  
  → Ring state: [user:"hi", assistant:"hey!", user:"what's my name?"]
  → READ via text parsing... 
     BUT context_window now has memory interleaved:
     "User: hi\n\n[MEMORY] User prefers...\n\nLuna: hey!"
  → Parser only finds "User: hi" before [MEMORY] block breaks it
  → conversation_history = [{"role": "user", "content": "hi"}]  
     ↑ MISSING THE CURRENT TURN!
  → Luna responds as if turn 1 is the only context
  → "60-second amnesia" manifests
```

### Verdict

**The fix was correct.** The ring buffer had all the data - we were writing to it correctly at line 1382. We just weren't reading from it when building conversation history.

Classic case of "the infrastructure is there, someone just forgot to plug it in."

---

## The Solution Applied

The local inference path (`_generate_local_only()` at line ~1094) already did it correctly:

```python
# CORRECT: Ring buffer first, text parsing fallback
conversation_history = []
if len(self._standalone_ring) > 0:
    ring_history = self._standalone_ring.format_for_prompt()
    conversation_history = self._standalone_ring.get_as_dicts()
    logger.debug("[LOCAL-FALLBACK] Using ring buffer for history (%d turns)", len(self._standalone_ring))
elif context_window:
    # Fall back to text parsing only if ring is empty
    for line in context_window.split("\n\n"):
        # ... text parsing
```

---

## The Fix Applied

### Location

**File:** `src/luna/actors/director.py`
**Method:** `_generate_with_delegation()` (starts around line 1361)
**Commit:** `a21a0a8`

### Fixed Code

```python
        # Build conversation history from ring buffer (structural guarantee)
        # Ring buffer is the SINGLE SOURCE OF TRUTH for recent conversation
        conversation_history = []
        if len(self._active_ring) > 0:
            conversation_history = self._active_ring.get_as_dicts()
            logger.debug("[DELEGATION] Using ring buffer for history (%d turns)", len(self._active_ring))
        elif context_window:
            # Fall back to text parsing only if ring is empty (shouldn't happen)
            logger.warning("[DELEGATION] Ring buffer empty, falling back to text parsing")
            for line in context_window.split("\n\n"):
                line = line.strip()
                if line.startswith("User:"):
                    conversation_history.append({"role": "user", "content": line[5:].strip()})
                elif line.startswith("Luna:"):
                    conversation_history.append({"role": "assistant", "content": line[5:].strip()})
```

---

## Why This Works

### Ring Buffer Guarantees

1. **Single Source of Truth:** `ConversationRing` stores turns as structured data, not text
2. **Immune to Interleaving:** Ring buffer is separate from RevolvingContext
3. **Correct Order:** FIFO deque maintains chronological order
4. **Already Populated:** `_generate_with_delegation()` already calls `self._active_ring.add_user(user_message)` at line ~1382
5. **Smart Switching:** `_active_ring` property automatically returns the correct ring instance

### Before/After

**Before:**
```
Turn 1: User asks about Marzipan → Luna responds ✓
Turn 2: Memory context injected into context_window
Turn 3: User asks follow-up → Parser fails at memory block, Luna forgets ✗
```

**After:**
```
Turn 1: User asks about Marzipan → Ring: [user, assistant]
Turn 2: Memory context injected (doesn't affect ring - separate data structure)
Turn 3: User asks follow-up → Ring: [user, assistant, user] → Luna remembers ✓
```

---

## Related Files

| File | Role |
|------|------|
| `src/luna/actors/director.py` | **FIXED** - delegation path |
| `src/luna/memory/ring.py` | Ring buffer implementation (no changes needed) |
| `src/luna/core/context.py` | RevolvingContext (no changes needed) |
| `src/luna/engine.py` | Calls Director with context_window (no changes needed) |

---

## Notes from Luna's Review

> "Classic case of 'the infrastructure is there, someone just forgot to plug it in.'"

The ring buffer was added as a "structural guarantee against forgetting" (per the code comments). It was being written to correctly. The bug was simply that the delegation path read from the wrong source.

This was a **surgical fix** - just making the delegation path use the same ring buffer pattern that already worked for local inference.

---

*End of Handoff*
