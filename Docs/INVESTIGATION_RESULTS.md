# Voice → Memory Gap Investigation Results

**Date:** 2025-01-25
**Investigator:** Claude Code
**Status:** ✅ COMPLETE - Root cause identified

---

## Executive Summary

**The Problem:** Voice conversations with Luna aren't persisted to memory. When Catherine talked to Luna about tacos, Luna had no memory of it afterward.

**Root Cause:** The pipeline is implemented but **not wired**. The extraction path exists from Scribe → Librarian → Memory Matrix, but voice conversations never reach the Scribe because:

1. `VoiceBackend` never calls `conversation.set_memory_callback()`
2. `PersonaAdapter` doesn't trigger extraction after processing

**Fix Effort:** ~15 lines of code in one file.

---

## Architecture: What Exists vs What's Wired

### Component Inventory

| Component | File | Status |
|-----------|------|--------|
| **Scribe Actor (Ben Franklin)** | [src/luna/actors/scribe.py](src/luna/actors/scribe.py) | ✅ Exists, fully implemented |
| **Librarian Actor (The Dude)** | [src/luna/actors/librarian.py](src/luna/actors/librarian.py) | ✅ Exists, fully implemented |
| **Memory Matrix (SQLite)** | [src/luna/substrate/](src/luna/substrate/) | ✅ Exists, schema complete |
| **ConversationManager** | [src/voice/conversation/manager.py](src/voice/conversation/manager.py) | ⚠️ Has callback hook, never set |
| **VoiceBackend** | [src/voice/backend.py](src/voice/backend.py) | ❌ Missing callback wiring |
| **PersonaAdapter** | [src/voice/persona_adapter.py](src/voice/persona_adapter.py) | ❌ Missing extraction trigger |
| **Engine._trigger_extraction()** | [src/luna/engine.py:672](src/luna/engine.py#L672) | ✅ Exists, but unused by voice |

### Database Tables (All exist and are correct)

```
conversation_turns    - Turn storage ✅
entities             - Entity storage ✅
extraction_queue     - Extraction processing ✅
memory_nodes         - Memory storage ✅
entity_versions      - Entity history ✅
graph_edges          - Knowledge graph ✅
```

---

## Data Flow Analysis

### Designed Flow (How it SHOULD work)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         VOICE INPUT                                 │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  VoiceBackend.process_and_respond()                                 │
│  src/voice/backend.py:436                                           │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌────────────────────────────┐    ┌────────────────────────────────────┐
│  ConversationManager       │    │  PersonaAdapter.process_message()  │
│  .end_turn()               │    │  src/voice/persona_adapter.py:99   │
│  src/voice/conversation/   │    └────────────────────────────────────┘
│  manager.py:77             │                        │
└────────────────────────────┘                        ▼
            │                         ┌────────────────────────────────┐
            │ (should call)           │  Director.process()            │
            │ _memory_callback        │  → generates response          │
            ▼                         └────────────────────────────────┘
┌────────────────────────────┐                        │
│  Engine._trigger_extraction│                        │
│  src/luna/engine.py:672    │◄───────────────────────┘ (should trigger)
└────────────────────────────┘
            │
            ▼
┌────────────────────────────┐
│  Scribe (Ben Franklin)     │
│  .handle("extract_turn")   │
│  src/luna/actors/scribe.py │
└────────────────────────────┘
            │
            ▼ _send_to_librarian()
┌────────────────────────────┐
│  Librarian (The Dude)      │
│  .handle("file")           │
│  src/luna/actors/          │
│  librarian.py              │
└────────────────────────────┘
            │
            ▼
┌────────────────────────────┐
│  Memory Matrix (SQLite)    │
│  memory_nodes, entities,   │
│  graph_edges               │
└────────────────────────────┘
```

### Actual Flow (What's happening NOW)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         VOICE INPUT                                 │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│  VoiceBackend.process_and_respond()                                 │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                    ┌───────────────┴───────────────┐
                    ▼                               ▼
┌────────────────────────────┐    ┌────────────────────────────────────┐
│  ConversationManager       │    │  PersonaAdapter.process_message()  │
│  .end_turn()               │    └────────────────────────────────────┘
│  _memory_callback = None ❌│                        │
│  NOTHING HAPPENS           │                        ▼
└────────────────────────────┘    ┌────────────────────────────────────┐
                                  │  Director.process()                │
                                  │  → generates response              │
                                  │  → NO EXTRACTION TRIGGERED ❌      │
                                  └────────────────────────────────────┘
                                                      │
                                                      ▼
                                  ┌────────────────────────────────────┐
                                  │  Response returned to user         │
                                  │  CONVERSATION LOST ❌              │
                                  └────────────────────────────────────┘


  ┌────────────────────────────────────────────────────────────────────┐
  │  Scribe (Ben)       }                                              │
  │  Librarian (Dude)   } ← ORPHANED - Never called by voice path     │
  │  Memory Matrix      }                                              │
  └────────────────────────────────────────────────────────────────────┘
```

---

## Gap Analysis

### GAP 1: Memory Callback Never Set

**Location:** [src/voice/backend.py:174](src/voice/backend.py#L174)

```python
# VoiceBackend.__init__()
self.conversation = ConversationManager(max_history=10)
# ❌ MISSING: self.conversation.set_memory_callback(...)
```

The `ConversationManager` has a `_memory_callback` hook at [src/voice/conversation/manager.py:37](src/voice/conversation/manager.py#L37):

```python
self._memory_callback: Optional[callable] = None
```

And it gets called in `end_turn()` at [line 100-108](src/voice/conversation/manager.py#L100):

```python
if self._memory_callback:  # ← NEVER TRUE because callback never set
    try:
        self._memory_callback(
            role="user" if turn.speaker == Speaker.USER else "assistant",
            content=text,
            timestamp=int(turn.started_at.timestamp())
        )
    except Exception as e:
        logger.error(f"Memory persistence failed: {e}")
```

**Impact:** User turns recorded in ConversationManager never reach the extraction pipeline.

### GAP 2: PersonaAdapter Doesn't Trigger Extraction

**Location:** [src/voice/persona_adapter.py:99-217](src/voice/persona_adapter.py#L99)

The `process_message()` method:
1. Calls `director.process()` to generate response ✅
2. Returns response to VoiceBackend ✅
3. **Never calls `engine._trigger_extraction()`** ❌

The engine HAS the method at [src/luna/engine.py:672](src/luna/engine.py#L672):

```python
async def _trigger_extraction(self, role: str, content: str) -> None:
    """Sends the turn to Scribe for semantic extraction..."""
    scribe = self.get_actor("scribe")
    if scribe and len(content) >= 10:
        msg = Message(
            type="extract_turn",
            payload={"role": role, "content": content, ...},
        )
        await scribe.mailbox.put(msg)
```

**Impact:** Both user messages AND Luna's responses are never extracted.

---

## Fix Proposal

### Option A: Wire in PersonaAdapter (Recommended)

**File:** [src/voice/persona_adapter.py](src/voice/persona_adapter.py)
**Lines:** After line 196 (after getting response_text)

```python
# After getting response from Director...
response_text = result.get("response", "") if result else ""

# ===== ADD: Trigger extraction for memory persistence =====
if self._engine and hasattr(self._engine, '_trigger_extraction'):
    # Extract user message
    try:
        await self._engine._trigger_extraction("user", message)
    except Exception as e:
        logger.warning(f"User extraction failed: {e}")

    # Extract assistant response
    if response_text and len(response_text) >= 10:
        try:
            await self._engine._trigger_extraction("assistant", response_text)
        except Exception as e:
            logger.warning(f"Assistant extraction failed: {e}")
# ===== END ADD =====
```

**Why this option:**
- Single location, both turns extracted
- Clean integration point
- Doesn't require async callback wiring

### Option B: Wire Memory Callback

**File:** [src/voice/backend.py](src/voice/backend.py)
**In:** `async def start()` method, after line 215

```python
# ===== ADD: Wire memory callback for extraction =====
if self.persona._engine:
    def memory_callback(role: str, content: str, timestamp: int):
        # Fire-and-forget extraction
        asyncio.create_task(
            self.persona._engine._trigger_extraction(role, content)
        )
    self.conversation.set_memory_callback(memory_callback)
    logger.info("Memory callback wired to extraction pipeline")
# ===== END ADD =====
```

**Why this might not work as well:**
- Only captures turns that go through `ConversationManager.end_turn()`
- May miss assistant responses (they're tracked separately in `conversation_buffer`)

---

## Verification Steps

After applying the fix:

1. **Start Luna Engine with voice mode**
2. **Have a conversation** (e.g., "My name is Catherine, I like tacos")
3. **Check extraction logs:**
   ```
   📝 Extraction triggered for user turn (XX chars)
   📝 Extraction triggered for assistant turn (XX chars)
   Ben: Extracted X objects, Y edges
   The Dude: Filed X new nodes...
   ```
4. **Query memory:**
   ```bash
   sqlite3 data/luna_engine.db "SELECT * FROM entities WHERE name LIKE '%Catherine%';"
   sqlite3 data/luna_engine.db "SELECT * FROM memory_nodes ORDER BY created_at DESC LIMIT 5;"
   ```
5. **Ask Luna:** "What do you know about Catherine?"

---

## Summary

| What | Status | Fix Required |
|------|--------|--------------|
| Scribe Actor | ✅ Works | None |
| Librarian Actor | ✅ Works | None |
| Memory Matrix | ✅ Works | None |
| Extraction Pipeline | ✅ Works | None |
| Voice → Extraction Wiring | ❌ Broken | ~15 lines in persona_adapter.py |

**The entire extraction pipeline works perfectly.** The only problem is that voice conversations never enter the pipeline. One simple change in `PersonaAdapter.process_message()` will fix this.
