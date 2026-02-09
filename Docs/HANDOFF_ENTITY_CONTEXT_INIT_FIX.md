# HANDOFF: Entity Context Initialization Failure

**Date:** 2026-02-04
**Priority:** P0 - This is THE root cause of Luna's personality drift
**Estimated Complexity:** Medium (likely a timing/initialization issue)

---

## THE PROBLEM IN ONE SENTENCE

Luna receives nearly empty system prompts (~185-907 chars) instead of full personality context (~3500+ chars) because `_init_entity_context()` silently fails.

---

## CONTEXT: WHY THIS MATTERS

Luna's architecture requires personality injection via system prompts. When entity context fails to initialize:
- No DNA_FOUNDATION (core identity)
- No EXPERIENCE_LAYER (learned personality) 
- No MOOD_LAYER (emotional state)
- No MEMORY_CONTEXT (relevant memories)
- No ENTITY_CONTEXT (who she's talking to)

Result: Luna sounds like generic Claude, not Luna. Users notice immediately.

---

## EVIDENCE OF THE PROBLEM

### QA Endpoint Shows Failure
```bash
curl -s http://localhost:8000/qa/last | python3 -m json.tool
```

Returns:
```json
{
  "passed": false,
  "failed_count": 4,
  "diagnosis": "Personality prompt missing or too short...",
  "assertions": [
    {"id": "P1", "name": "Personality injected", "passed": false, "actual": "0 chars"},
    {"id": "P2", "name": "Virtues loaded", "passed": false, "actual": "Not loaded"},
    {"id": "P3", "name": "Narration applied", "passed": false, "actual": "SKIPPED"}
  ]
}
```

### Prompt Archaeology Shows Empty Prompts
File: `data/diagnostics/prompt_archaeology.jsonl`
```json
{
  "query": "What do you remember about my programming preferences?",
  "system_prompt_length": 791,
  "sections_detected": ["IDENTITY_PREAMBLE"],
  "missing_sections": ["DNA_FOUNDATION", "EXPERIENCE_LAYER", "MOOD_LAYER", "MEMORY_CONTEXT"]
}
```

### Standalone Test Confirms Failure
```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
source .venv/bin/activate
python -c "
import asyncio
from luna.actors.director import DirectorActor, ENTITY_CONTEXT_AVAILABLE

async def test():
    print(f'ENTITY_CONTEXT_AVAILABLE: {ENTITY_CONTEXT_AVAILABLE}')
    d = DirectorActor(name='test', engine=None)
    result = await d._ensure_entity_context()
    print(f'Result: {result}')
    print(f'_entity_context: {d._entity_context}')

asyncio.run(test())
"
```

Output:
```
[CONTEXT-STARVE] No engine reference - Director not attached to engine
ENTITY_CONTEXT_AVAILABLE: True
Result: False
_entity_context: None
```

---

## ROOT CAUSE HYPOTHESIS

`_init_entity_context()` in `src/luna/actors/director.py` (line ~298) has 5 sequential gates. One of them is failing silently during normal server operation.

### The 5 Gates (in order)
```python
# Gate 1: Import check
if not ENTITY_CONTEXT_AVAILABLE:
    return False

# Gate 2: Engine reference
if not self.engine:
    return False

# Gate 3: Matrix actor exists
matrix = self.engine.get_actor("matrix")
if not matrix:
    return False

# Gate 4: Matrix has _matrix attribute
if not hasattr(matrix, '_matrix'):
    return False

# Gate 5: _matrix is not None
if not matrix._matrix:
    return False
```

### What We Know
- Gate 1 passes (`ENTITY_CONTEXT_AVAILABLE = True`)
- Gate 2 fails in standalone test (no engine reference)
- In server context, engine reference SHOULD be set via `register_actor()` in `engine.py` line 219

### Likely Culprit
Timing issue. Either:
1. `_ensure_entity_context()` is called before `register_actor()` sets `self.engine`
2. Matrix actor hasn't finished initializing when Director tries to use it
3. Something is caching the "failed" state and not retrying

---

## FILES TO INVESTIGATE

### Primary
- `src/luna/actors/director.py`
  - `_init_entity_context()` - line ~298
  - `_ensure_entity_context()` - line ~415 (lazy init wrapper)
  - `on_start()` - line ~225 (removed eager init, now relies on lazy)
  - `FALLBACK_PERSONALITY` - line ~107 (bandaid added, not the fix)

### Secondary  
- `src/luna/engine.py`
  - `register_actor()` - line ~218 (sets `actor.engine = self`)
  - `_boot()` - line ~276 (creates and registers actors)
  - Boot order: Matrix → Director → Scribe → Librarian → HistoryManager

### Entity Context System
- `src/luna/identity/entity_context.py` - EntityContext class
- `src/luna/memory/memory_matrix.py` - MemoryMatrix with `.db` attribute

---

## RECENT CHANGES (may have introduced bug)

In this session, we removed eager init from `on_start()`:
```python
# REMOVED from on_start() around line 233:
# if ENTITY_CONTEXT_AVAILABLE:
#     await self._init_entity_context()

# REPLACED WITH comment:
# NOTE: Entity context init removed from on_start() — it's lazy-loaded
# on first request via _ensure_entity_context(). This fixes the race
# condition where Director starts before Matrix is ready.
```

The theory was: lazy init on first request would avoid the race condition. But something is still preventing successful init.

---

## DEBUGGING APPROACH

### Step 1: Add Diagnostic Logging
Add print statements to stderr (they show in uvicorn terminal):

```python
# In _init_entity_context(), at the start:
import sys
def dbg(msg):
    print(msg, file=sys.stderr, flush=True)

# Then at each gate:
dbg(f"[CONTEXT-STARVE] Gate 1: ENTITY_CONTEXT_AVAILABLE={ENTITY_CONTEXT_AVAILABLE}")
dbg(f"[CONTEXT-STARVE] Gate 2: self.engine={self.engine}")
# etc.
```

### Step 2: Send Test Message
```bash
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}'
```

### Step 3: Check Server Terminal
Look for `[CONTEXT-STARVE]` lines showing which gate failed.

### Step 4: Fix the Failing Gate

**If Gate 2 (no engine):**
- Check if Director is being created outside engine context
- Ensure all Director instances go through `register_actor()`

**If Gate 3 (no matrix actor):**
- Matrix might not be registered yet
- Add retry logic or wait for Matrix

**If Gate 5 (matrix._matrix is None):**
- Matrix.initialize() hasn't completed
- Add check for Matrix readiness before using it

### Step 5: Verify Fix
```bash
# Send a message
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "test"}'

# Check QA
curl -s http://localhost:8000/qa/last | python3 -c "
import sys, json
d = json.load(sys.stdin)
p1 = next((a for a in d['assertions'] if a['id'] == 'P1'), {})
p2 = next((a for a in d['assertions'] if a['id'] == 'P2'), {})
print(f'P1 (Personality): {p1.get(\"actual\", \"?\")} - {\"PASS\" if p1.get(\"passed\") else \"FAIL\"}')
print(f'P2 (Virtues): {p2.get(\"actual\", \"?\")} - {\"PASS\" if p2.get(\"passed\") else \"FAIL\"}')
"
```

**Success criteria:**
- P1 shows ">1000 chars" and PASS
- P2 shows "Loaded" and PASS

---

## POTENTIAL FIXES (ranked by likelihood)

### Fix A: Add Retry Logic in _ensure_entity_context()
```python
async def _ensure_entity_context(self) -> bool:
    if self._entity_context is not None:
        return True
    
    # Retry up to 5 times with backoff
    for attempt in range(5):
        if await self._init_entity_context():
            return True
        await asyncio.sleep(0.1 * (attempt + 1))
    
    return False
```

### Fix B: Wait for Matrix in _init_entity_context()
```python
# After getting matrix actor, wait for it to be ready
matrix = self.engine.get_actor("matrix")
if matrix:
    # Wait for _matrix to be initialized
    for _ in range(50):  # 5 second max
        if hasattr(matrix, '_matrix') and matrix._matrix:
            break
        await asyncio.sleep(0.1)
```

### Fix C: Initialize Entity Context After Matrix in _boot()
In `engine.py`, after Matrix.initialize():
```python
# After matrix initialization
if "matrix" not in self.actors:
    matrix = MatrixActor()
    self.register_actor(matrix)
    await matrix.initialize()

# Create director AFTER matrix is ready
if "director" not in self.actors:
    director = DirectorActor(enable_local=self.config.enable_local_inference)
    self.register_actor(director)
    # Explicitly init entity context now that matrix is ready
    await director._init_entity_context()
```

---

## VALIDATION CHECKLIST

After implementing fix, verify ALL of these:

- [ ] `curl http://localhost:8000/qa/last` shows P1 >1000 chars, P2=loaded
- [ ] Send 3 different messages, all pass P1/P2
- [ ] Restart server, first message still passes P1/P2
- [ ] Check `data/diagnostics/prompt_archaeology.jsonl` shows full sections
- [ ] Luna's responses sound like Luna (warm, direct, uses "~" occasionally)

---

## COMMANDS REFERENCE

```bash
# Start server
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
source .venv/bin/activate
uvicorn luna.api.server:app --host 0.0.0.0 --port 8000 --reload

# Test message
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "hello"}'

# Check QA
curl -s http://localhost:8000/qa/last | python3 -m json.tool

# Check prompt info
curl -s http://localhost:8000/slash/prompt | python3 -m json.tool

# Quick P1/P2 check
curl -s http://localhost:8000/qa/last | python3 -c "
import sys, json
d = json.load(sys.stdin)
for a in d.get('assertions', []):
    if a['id'] in ['P1', 'P2', 'P3']:
        print(f\"{a['id']}: {a['actual']} - {'✓' if a['passed'] else '✗'}\")"
```

---

## SUCCESS LOOKS LIKE

```
P1: >1500 chars - ✓
P2: Loaded - ✓
P3: Applied - ✓
```

And Luna responding with personality:
> "hey~ what's on your mind? I've been thinking about our conversation from yesterday..."

Instead of generic:
> "Hello! How can I assist you today?"

---

## NOTES FOR CLAUDE CODE

1. The server auto-reloads on file changes (WatchFiles)
2. Logs go to terminal, not to file — use print(x, file=sys.stderr, flush=True)
3. Don't break the existing fallback — it's a safety net
4. The fix should be minimal and targeted, not a rewrite
5. Test incrementally — one gate at a time
