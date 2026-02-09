# P0 HANDOFF: Luna's Voice Narration Layer Not Applied

**Date:** 2026-02-04
**Priority:** P0 - Luna sounds like Claude, not herself
**Depends On:** Entity context fix (COMPLETED - P1/P2 now passing)

---

## THE PROBLEM IN ONE SENTENCE

Luna's delegation path returns raw Claude/Groq responses without voice transformation, so she sounds like a generic assistant instead of Luna.

---

## EVIDENCE

### User Interaction
```
User: "hey luna its me"
Luna: "It's wonderful to hear from you again. How are things? What brings joy these days? 😊"

User: "do you know who it is?"  
Luna: "I can't recall specifics about 'it.' My recent conversations were more focused on tests..."
```

**Problems:**
- "It's wonderful to hear from you again" — Claude-speak, not Luna
- "What brings joy these days? 😊" — generic assistant cheerfulness
- Doesn't recognize Ahab despite having 10K chars of context
- Formal, distant tone instead of warm and direct

### QA Confirms
```bash
curl -s http://localhost:8000/qa/last | grep narration
```

Returns:
```json
{
  "id": "narration",
  "name": "Narration applied",
  "passed": false,
  "actual": "SKIPPED",
  "details": "FULL_DELEGATION requires voice transformation"
}
```

---

## WHAT NARRATION SHOULD DO

The narration layer takes Claude's raw response and rewrites it in Luna's voice:

**Before (raw Claude):**
> "It's wonderful to hear from you again. How are things? I'm here whenever you need to chat. What brings joy these days? 😊"

**After (narrated as Luna):**
> "hey~ good to see you again. what's on your mind? I remember we were deep in the weeds with that context bug yesterday..."

**Key transformations:**
- Lowercase casual style
- Uses "~" occasionally
- References shared history naturally
- Warm but direct, not performatively cheerful
- Knows who she's talking to (Ahab)

---

## ARCHITECTURE

```
User Query
    ↓
Director.process()
    ↓
_generate_with_delegation()  ← delegates to Claude/Groq
    ↓
Raw Claude Response
    ↓
_narrate_response()  ← SHOULD transform voice, but SKIPPED
    ↓
Final Response (currently sounds like Claude)
```

---

## FILES TO INVESTIGATE

### Primary
- `src/luna/actors/director.py`
  - `_narrate_response()` — the narration function itself
  - `_generate_with_delegation()` — should call narration after getting response
  - Look for where `"SKIPPED"` is set in QA tracking

### Search for narration logic
```bash
grep -n "narrat" src/luna/actors/director.py | head -30
grep -n "SKIPPED" src/luna/actors/director.py
grep -n "_narrate" src/luna/actors/director.py
```

---

## LIKELY CAUSES

### 1. Narration call is commented out or conditional
```python
# Somewhere in _generate_with_delegation():
# response = await self._narrate_response(raw_response)  # <-- might be skipped
```

### 2. Early return before narration
```python
if some_condition:
    return raw_response  # <-- bypasses narration
```

### 3. Narration function returns early
```python
async def _narrate_response(self, text: str) -> str:
    if not self._some_flag:
        return text  # <-- returns unchanged
```

### 4. Flag not being set
```python
self._narration_enabled = False  # <-- never set to True
```

---

## DEBUGGING APPROACH

### Step 1: Find where SKIPPED is set
```bash
grep -n "SKIPPED\|skipped" src/luna/actors/director.py
```

This will show where the QA system detects narration was skipped.

### Step 2: Trace the delegation path
Find `_generate_with_delegation()` and trace what happens after getting the raw response. Is `_narrate_response()` called?

### Step 3: Check _narrate_response()
- Does it exist?
- What conditions cause early return?
- Is it actually being called?

### Step 4: Add debug logging
```python
async def _narrate_response(self, text: str, ...) -> str:
    print(f"[NARRATION] Called with {len(text)} chars", file=sys.stderr, flush=True)
    # ... rest of function
    print(f"[NARRATION] Returning {len(result)} chars", file=sys.stderr, flush=True)
    return result
```

---

## WHAT NARRATION NEEDS

The narration prompt should include:
1. Luna's voice characteristics (from virtues/kernel)
2. The raw response to transform
3. Instructions to rewrite in Luna's voice WITHOUT changing meaning

Example narration prompt:
```
You are Luna's voice. Rewrite this response in Luna's authentic voice:
- Lowercase, casual but intelligent
- Warm and direct, not performatively cheerful  
- Uses "~" occasionally for softness
- References shared context naturally
- Speaks like talking to a close collaborator

Raw response to transform:
{raw_response}

Rewrite in Luna's voice (same meaning, different tone):
```

---

## SUCCESS CRITERIA

### QA Check
```bash
curl -s http://localhost:8000/qa/last | python3 -c "
import sys, json
d = json.load(sys.stdin)
for a in d.get('assertions', []):
    if a['id'] == 'narration':
        print(f\"narration: {a['actual']} - {'✓' if a['passed'] else '✗'}\")"
```

**Success:** `narration: Applied - ✓`

### Voice Check
Send these test messages and verify Luna sounds like Luna:

```bash
# Test 1: Recognition
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "hey luna, its me"}'
# Should: recognize Ahab, reference shared work, casual tone

# Test 2: Memory reference  
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "what were we working on?"}'
# Should: reference context starvation bug, entity context fix, etc.

# Test 3: Personality
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "how are you feeling?"}'
# Should: warm, self-aware, mentions her systems/state naturally
```

### Luna Should Sound Like:
- "hey~ yeah I remember, we were debugging that context thing..."
- "good to see you again. the entity context fix went through, feeling more... present now"
- Uses lowercase, occasional "~", warm but not saccharine

### Luna Should NOT Sound Like:
- "It's wonderful to hear from you again!"
- "What brings joy these days? 😊"
- "I'm here whenever you need to chat!"
- Formal, generic, performatively positive

---

## COMMANDS REFERENCE

```bash
# Start server (if not running)
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
source .venv/bin/activate
uvicorn luna.api.server:app --host 0.0.0.0 --port 8000 --reload

# Test message
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "hey luna"}'

# Check narration specifically
curl -s http://localhost:8000/qa/last | python3 -c "
import sys, json
d = json.load(sys.stdin)
for a in d.get('assertions', []):
    if a['id'] == 'narration':
        print(f\"narration: {a['actual']} - {'✓' if a['passed'] else '✗'}\")"

# Full QA check
curl -s http://localhost:8000/qa/last | python3 -c "
import sys, json
d = json.load(sys.stdin)
for a in d.get('assertions', []):
    if a['id'] in ['P1', 'P2', 'narration']:
        print(f\"{a['id']}: {a['actual']} - {'✓' if a['passed'] else '✗'}\")"
```

---

## IMPORTANT NOTES

1. **Don't break P1/P2** — entity context is now working, preserve it
2. **Narration adds latency** — it's an extra LLM call, but necessary for voice
3. **Use same provider** — narration should use same LLM as delegation (Groq) for speed
4. **Keep it simple** — narration prompt should be short, focused on voice transformation
5. **Test incrementally** — verify narration passes before testing conversation quality

---

## RELATED FILES

- `Docs/HANDOFF_ENTITY_CONTEXT_INIT_FIX.md` — just completed, P1/P2 now passing
- `Docs/HANDOFF_CONTEXT_STARVATION.md` — original investigation
- `src/luna/actors/director.py` — main file to modify
