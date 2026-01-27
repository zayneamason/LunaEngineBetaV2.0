# Handoff: Voice Conversation → Memory Matrix Gap Investigation

**Created:** 2025-01-25
**Purpose:** Investigate why Voice Luna conversations don't persist to memory
**Codebase:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root`

---

## The Problem

Luna cannot remember voice conversations. A user named "Catherine" had a conversation with Voice Luna about making tacos. When Luna was later asked about Catherine, she had no memory of the conversation.

**Hypothesis:** Voice transcripts aren't being fed into the AI-BRARIAN pipeline (Ben Franklin → The Dude → Memory Matrix).

---

## What We Know So Far

### 1. Voice Backend Location
`src/voice/backend.py` - VoiceBackend class orchestrates voice conversations

### 2. Conversation Manager Has Memory Hook
`src/voice/conversation/manager.py` has a `_memory_callback` that's supposed to persist turns:

```python
def set_memory_callback(self, callback: callable):
    """Set callback for memory persistence."""
    self._memory_callback = callback
```

And it's called in `end_turn()`:
```python
if self._memory_callback:
    self._memory_callback(
        role="user" if turn.speaker == Speaker.USER else "assistant",
        content=text,
        timestamp=int(turn.started_at.timestamp())
    )
```

### 3. Chunker Exists
`src/luna/extraction/chunker.py` - SemanticChunker class exists and can chunk conversation turns

### 4. Unknown: Scribe (Ben Franklin) Implementation
The Bible docs describe Ben Franklin as the extraction system, but we haven't found where the Scribe actor/class is implemented in the actual codebase.

---

## Investigation Tasks

### Task 1: Find the Scribe Implementation
Search for:
- Files containing "scribe", "franklin", "extraction"
- Classes that implement the extraction pipeline described in the Bible
- Any actor/component that takes conversation input and produces structured extractions

```bash
# Search patterns
grep -r "scribe" src/ --include="*.py"
grep -r "franklin" src/ --include="*.py" -i
grep -r "ExtractionOutput" src/ --include="*.py"
grep -r "class.*Extractor" src/ --include="*.py"
```

### Task 2: Trace the Memory Callback Wiring
Find where `conversation.set_memory_callback()` is called:
- Is it called in VoiceBackend initialization?
- What function is passed as the callback?
- Does that callback actually write to the Memory Matrix?

```bash
grep -r "set_memory_callback" src/ --include="*.py"
grep -r "memory_callback" src/ --include="*.py"
```

### Task 3: Find the Librarian (The Dude) Implementation
Search for:
- Entity resolution logic
- Knowledge wiring
- Anything that files extractions into the Memory Matrix

```bash
grep -r "librarian" src/ --include="*.py" -i
grep -r "dude" src/ --include="*.py" -i
grep -r "entity.*resolv" src/ --include="*.py" -i
grep -r "file.*extraction" src/ --include="*.py"
```

### Task 4: Check Memory Matrix Integration Points
Look at:
- `src/luna/memory/` - How does data get written?
- `src/luna/substrate/` - Is there a filing interface?
- `src/luna/actors/` - Are Scribe/Librarian implemented as actors?

### Task 5: Check the Hub/Pipeline Integration
Look for:
- Any "hub" or "pipeline" modules
- Chunking pipeline that processes conversations
- Background workers that might handle extraction

```bash
grep -r "hub" src/ --include="*.py" -i
grep -r "pipeline" src/ --include="*.py"
grep -r "worker" src/ --include="*.py"
```

### Task 6: Database Schema Check
Examine:
- `data/luna_engine.db` schema - what tables exist?
- Are there tables for conversation_logs, extractions, etc?
- Is there a conversations or transcripts table?

```bash
sqlite3 data/luna_engine.db ".schema"
sqlite3 data/luna_engine.db "SELECT name FROM sqlite_master WHERE type='table';"
```

---

## Key Questions to Answer

1. **Where is the Scribe (Ben Franklin) implemented?**
   - Is it an actor? A class? A module?
   - Is it actually instantiated and running?

2. **Is the memory callback wired up?**
   - Does VoiceBackend call `set_memory_callback()`?
   - What does the callback function actually do?

3. **What's the data flow from voice to memory?**
   - Voice → STT → Text → ??? → Memory Matrix
   - Where does the chain break?

4. **Are voice conversations being logged anywhere?**
   - Check for transcript files
   - Check for conversation_history tables
   - Check for any persistence of voice sessions

5. **Is extraction happening at all?**
   - Is the chunker being called?
   - Is Claude/Shadow Reasoner being invoked for extraction?
   - Are extractions being filed with the Librarian?

---

## Deliverables

Create a summary document (`INVESTIGATION_RESULTS.md`) with:

1. **Architecture Diagram** - Actual data flow as implemented (not as designed)
2. **Gap Analysis** - Where the pipeline breaks (with file:line references)
3. **Component Inventory**:
   - What exists and works
   - What exists but isn't wired
   - What's missing entirely
4. **Fix Proposal** - Specific code changes needed to wire voice → memory

---

## Reference Documents

- Bible Part IV (The Scribe): `/mnt/project/04-THE-SCRIBE.md`
- Bible Part V (The Librarian): `/mnt/project/05-THE-LIBRARIAN.md`
- Bible Part III (Memory Matrix): `/mnt/project/03-MEMORY-MATRIX.md`

---

## Notes for Investigator

- The codebase uses Python 3.14 with async/await patterns
- Memory Matrix uses sqlite-vec (NOT FAISS)
- The system has actors in `src/luna/actors/`
- Voice system is in `src/voice/`
- Core Luna engine is in `src/luna/`

**Priority:** Understanding current state before proposing fixes. We need facts, not assumptions.
