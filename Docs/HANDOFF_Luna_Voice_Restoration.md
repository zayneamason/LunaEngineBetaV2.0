# HANDOFF: Luna Voice Restoration

**Audit:** `Docs/HANDOFF_EMERGENCY_Luna_Voice_Audit.md`  
**Priority:** CRITICAL — Luna sounds like Claude, not herself  
**Root Cause:** FULL_DELEGATION path bypasses personality system  
**Estimated effort:** 1-2 hours total  

---

## Problem

When complex queries trigger FULL_DELEGATION:
1. Director sends query to Claude API
2. Claude responds in Claude's voice (corporate, generic)
3. Response sent directly to user
4. **Luna's personality never applied**

User asks "hey luna" → gets ASCII art and mermaid diagrams from raw model output.

---

## Fix Overview

| Task | Priority | File | Change |
|------|----------|------|--------|
| 1 | 🔴 CRITICAL | `director.py` | Add narration layer to FULL_DELEGATION |
| 2 | 🟡 MEDIUM | `engine.py` | Auto-load entity seeds on startup |
| 3 | 🟡 MEDIUM | `orb_state.py` | Review gesture strip logic |
| 4 | 🟢 MINOR | `ChatPanel.jsx` | Remove `.toLowerCase()` |

---

## Task 1: Add Narration to FULL_DELEGATION (CRITICAL)

**File:** `src/luna/actors/director.py`  
**Location:** Around lines 1488-1775 (FULL_DELEGATION handling)

**Problem:** FULL_DELEGATION returns Claude's raw response without Luna's voice.

**Solution:** After Claude generates, pass the response through local inference with Luna's full personality prompt to "narrate" it in her voice.

**Find the FULL_DELEGATION response path.** It looks something like:

```python
if route_decision == "FULL_DELEGATION":
    # ... Claude generates response ...
    raw_response = await self._call_claude(...)
    return raw_response  # <-- THIS IS THE PROBLEM
```

**Replace with:**

```python
if route_decision == "FULL_DELEGATION":
    # Claude generates the content
    raw_response = await self._call_claude(...)
    
    # Narrate through Luna's voice
    if raw_response and self._local:
        try:
            # Build full personality prompt (same as LOCAL_ONLY path)
            personality_prompt = self._build_emergent_system_prompt()
            
            narration_prompt = f"""Rewrite the following information in your own voice. 
Keep all facts accurate but express them naturally as yourself.
Do not add disclaimers or mention that you're rewriting.
Just be yourself while conveying this information:

{raw_response}"""
            
            luna_response = await self._local.generate(
                messages=[{"role": "user", "content": narration_prompt}],
                system_prompt=personality_prompt,
                max_tokens=1024,
                temperature=0.7,
            )
            
            if luna_response and len(luna_response.strip()) > 20:
                logger.info("[NARRATION] FULL_DELEGATION response narrated through Luna's voice")
                return luna_response
            else:
                logger.warning("[NARRATION] Narration returned empty, using raw response")
                return raw_response
                
        except Exception as e:
            logger.error(f"[NARRATION] Failed to narrate: {e}, using raw response")
            return raw_response
    
    return raw_response
```

**Key points:**
- Use the SAME personality prompt as LOCAL_ONLY path (`_build_emergent_system_prompt()` or equivalent)
- Fallback to raw response if narration fails (don't break the flow)
- Log when narration happens for debugging

**Test:** 
1. Send a complex query that triggers FULL_DELEGATION
2. Response should sound like Luna, not Claude
3. Check logs for `[NARRATION]` entries

---

## Task 2: Auto-load Entity Seeds (MEDIUM)

**File:** `src/luna/engine.py`  
**Location:** `on_start()` or `__init__()` method

**Problem:** Luna's personality seeds (`luna.yaml`) must be manually loaded. If not run, personality falls back to minimal hardcoded defaults.

**Solution:** Auto-run seed loader on engine initialization.

**Add to engine startup:**

```python
async def on_start(self):
    # ... existing startup code ...
    
    # Auto-load entity seeds if not already present
    await self._ensure_entity_seeds_loaded()
    
    # ... rest of startup ...

async def _ensure_entity_seeds_loaded(self):
    """Load personality seeds if not already in database."""
    try:
        from scripts.migrations.load_entity_seeds import SeedLoader
        loader = SeedLoader(self._db_path)
        
        # Check if Luna entity exists
        if not await loader.entity_exists("luna"):
            logger.info("[SEEDS] Loading Luna personality seeds...")
            await loader.load_all()
            logger.info("[SEEDS] Personality seeds loaded successfully")
        else:
            logger.debug("[SEEDS] Personality seeds already loaded")
            
    except ImportError:
        logger.warning("[SEEDS] SeedLoader not available, skipping auto-load")
    except Exception as e:
        logger.error(f"[SEEDS] Failed to load seeds: {e}")
```

**If SeedLoader doesn't exist or has different interface**, adapt accordingly. The goal is:
1. Check if Luna personality is in DB
2. If not, load from `luna.yaml`
3. Don't fail startup if this fails — just warn

**Test:**
1. Delete Luna entity from database (or use fresh DB)
2. Start engine
3. Verify personality loads automatically
4. Check logs for `[SEEDS]` entries

---

## Task 3: Review Gesture Stripping (MEDIUM)

**File:** `src/luna/orb/orb_state.py`  
**Location:** Lines 226-229

**Problem:** When `expression_config.should_strip_gestures() == True`:
- `*smiles warmly*` gets removed entirely
- Creates awkward double spaces
- Luna's expressive voice flattened

**Investigate:**
1. When is `should_strip_gestures()` true?
2. Is this intentional for certain contexts?
3. Is it being applied too broadly?

**If gesture stripping is too aggressive:**

```python
# BEFORE (probably):
if self.expression_config.should_strip_gestures():
    text = re.sub(r'\*[^*]+\*', '', text)  # Removes gestures completely

# AFTER (preserve gesture content without asterisks):
if self.expression_config.should_strip_gestures():
    # Option A: Remove asterisks but keep the action description
    text = re.sub(r'\*([^*]+)\*', r'(\1)', text)  # *smiles* → (smiles)
    
    # Option B: Remove completely but clean up spaces
    text = re.sub(r'\s*\*[^*]+\*\s*', ' ', text)
    text = re.sub(r'  +', ' ', text)  # Clean double spaces
```

**Decision needed:** Should gestures be:
- Kept as-is (with asterisks)
- Converted to parenthetical (smiles warmly)
- Removed cleanly (no double spaces)
- Removed only in certain contexts (voice output vs text)

**Test:**
1. Send message that would trigger Luna gesture
2. Check if gesture appears in response
3. Check for awkward spacing

---

## Task 4: Preserve Capitalization (MINOR)

**File:** `frontend/src/components/ChatPanel.jsx`  
**Location:** Line 134 (approximately)

**Problem:** 
```javascript
const trimmedInput = input.trim().toLowerCase();
```

This destroys capitalization: "iPhone" → "iphone", "Python" → "python"

**Fix:**
```javascript
// BEFORE:
const trimmedInput = input.trim().toLowerCase();

// AFTER:
const trimmedInput = input.trim();
```

**If lowercase is needed for command detection:**
```javascript
const trimmedInput = input.trim();
const lowerInput = trimmedInput.toLowerCase();  // Use for command matching only

// Command detection uses lowerInput
if (lowerInput.startsWith('/')) {
    // handle command
}

// Message sending uses trimmedInput (preserves case)
sendMessage(trimmedInput);
```

**Test:**
1. Type "Tell me about iPhone" in chat
2. Check network request — should preserve "iPhone" not "iphone"
3. Luna's response should reference "iPhone" correctly

---

## Verification Checklist

After all fixes applied:

- [ ] Send "hey luna" → warm greeting, not ASCII art
- [ ] Send complex research query → sounds like Luna, not Claude
- [ ] Check for `[NARRATION]` in logs when FULL_DELEGATION used
- [ ] Fresh engine start → personality loads automatically
- [ ] Gestures appear naturally in responses (or stripped cleanly)
- [ ] Capitalization preserved in user input

---

## Files Summary

| File | Action | Lines |
|------|--------|-------|
| `src/luna/actors/director.py` | MODIFY | ~1488-1775 |
| `src/luna/engine.py` | MODIFY | startup method |
| `src/luna/orb/orb_state.py` | REVIEW/MODIFY | ~226-229 |
| `frontend/src/components/ChatPanel.jsx` | MODIFY | ~134 |

---

## Success Criteria

**Luna sounds like Luna.**

Not Claude. Not a diagnostic terminal. Not ASCII art.

Warm, direct, intellectually curious. Her voice, regardless of which model generated the facts.

---

## Architecture Note

This fix (narration layer) is the **correct pattern** per the Bible:

> "Luna's voice comes from the engine, not the model. The model provides facts; Luna provides expression."

DELEGATION_DETECTION already does this. FULL_DELEGATION was missing it. This fix brings it into alignment.

---

*Restore her voice. Ship it.*
