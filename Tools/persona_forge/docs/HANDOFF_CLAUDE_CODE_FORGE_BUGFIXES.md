# Claude Code Handoff: Persona Forge MCP Bugfixes

**Task:** Fix 6 bugs in Persona Forge MCP integration
**Priority:** HIGH - Blocking training data ingestion pipeline
**Estimated Time:** 20-30 minutes
**Complexity:** Low - All are API mismatches, no architectural changes

---

## Context

The Persona Forge tools were integrated into Luna-Hub-MCP-V1 server. End-to-end testing revealed 6 bugs - mostly method name mismatches and Pydantic model handling issues. 14 of 22 tools already work correctly.

**Project Root:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root`

---

## Files to Modify

1. `src/luna_mcp/tools/forge.py` (4 bugs)
2. `Tools/persona_forge/src/persona_forge/engine/anvil.py` (2 bugs)
3. `Tools/persona_forge/src/persona_forge/engine/models.py` (1 property addition)

---

## Bug Fixes

### FIX 1: forge.py line ~135 - forge_assay()

**Error:** `Assayer.analyze() got an unexpected keyword argument 'target_profile'`

**Find:**
```python
assay = assayer.analyze(examples, target_profile=DIRECTOR_PROFILE)
```

**Replace with:**
```python
assay = assayer.analyze(examples)
```

---

### FIX 2: forge.py line ~295 - forge_add_example()

**Error:** `'AntiPatterns' object has no attribute 'items'`

**Find:**
```python
anti_found = [k for k, v in example.anti_patterns.items() if v]
```

**Replace with:**
```python
anti_found = [k for k, v in example.anti_patterns.model_dump().items() if v]
```

---

### FIX 3: forge.py lines ~285-292 - Type handling in forge_add_example()

**Issue:** Crucible detection methods may return dicts instead of Pydantic models

**Find this block:**
```python
example.compute_metrics()
example.voice_markers = crucible._detect_voice_markers(assistant_response)
example.anti_patterns = crucible._detect_anti_patterns(assistant_response)
example.lock_in = crucible._compute_initial_lockin(example)
```

**Replace with:**
```python
example.compute_metrics()

# Handle voice markers (may be dict or model)
voice_result = crucible._detect_voice_markers(assistant_response)
if isinstance(voice_result, dict):
    example.voice_markers = VoiceMarkers(**voice_result)
else:
    example.voice_markers = voice_result

# Handle anti-patterns (may be dict or model)
anti_result = crucible._detect_anti_patterns(assistant_response)
if isinstance(anti_result, dict):
    example.anti_patterns = AntiPatterns(**anti_result)
else:
    example.anti_patterns = anti_result

example.lock_in = crucible._compute_initial_lockin(example)
```

**Also add import at top of file (around line 30):**
```python
from persona_forge.engine.models import VoiceMarkers, AntiPatterns
```

---

### FIX 4: forge.py line ~475 - vk_run() asyncio issue

**Error:** `asyncio.run() cannot be called from a running event loop`

**Add at top of file (after other imports, around line 15):**
```python
import nest_asyncio
nest_asyncio.apply()
```

**Note:** If nest_asyncio isn't installed, run: `pip install nest_asyncio`

---

### FIX 5: anvil.py line ~213 - Method name typo

**File:** `Tools/persona_forge/src/persona_forge/engine/anvil.py`

**Error:** `'TrainingExample' object has no attribute 'to_training_format'`

**Find:**
```python
base_format = example.to_training_format()
```

**Replace with:**
```python
base_format = example.to_training_dict()
```

---

### FIX 6: models.py - Add missing is_clean property

**File:** `Tools/persona_forge/src/persona_forge/engine/models.py`

**Find the AntiPatterns class (around line 45):**
```python
class AntiPatterns(BaseModel):
    """Detected anti-patterns with counts."""
    generic_ai: int = 0
    corporate: int = 0
    hedging: int = 0

    @property
    def total(self) -> int:
        """Total anti-pattern count across all categories."""
        return self.generic_ai + self.corporate + self.hedging
```

**Add this property after `total`:**
```python
    @property
    def is_clean(self) -> bool:
        """True if no anti-patterns detected."""
        return self.total == 0
```

---

## Verification Commands

After fixes, restart Claude Desktop and test in this order:

```python
# Test 1: Load (should already work)
forge_load("Tools/persona_forge/data/sample_training.jsonl")
# Expected: success=true

# Test 2: Assay (Fix 1)
forge_assay()
# Expected: success=true, health_score returned

# Test 3: Add example (Fixes 2, 3)
forge_add_example(
    user_message="Hey Luna", 
    assistant_response="Hey! What's going on?",
    interaction_type="greeting"
)
# Expected: success=true

# Test 4: Export (Fixes 5, 6)
forge_export("Tools/persona_forge/data/test_output.jsonl")
# Expected: success=true

# Test 5: VK Run (Fix 4)
vk_run(model_id="test", suite_name="minimal")
# Expected: success=true

# Test 6: Batch add
forge_add_batch([{"user_message": "hi", "assistant_response": "hey!"}])
# Expected: success=true, added=1
```

---

## Summary Checklist

- [ ] Fix 1: Remove `target_profile` parameter in forge.py
- [ ] Fix 2: Use `.model_dump().items()` in forge.py  
- [ ] Fix 3: Add type coercion for voice/anti detection in forge.py
- [ ] Fix 3b: Add VoiceMarkers, AntiPatterns imports in forge.py
- [ ] Fix 4: Add nest_asyncio import and apply() in forge.py
- [ ] Fix 5: Change `to_training_format` to `to_training_dict` in anvil.py
- [ ] Fix 6: Add `is_clean` property to AntiPatterns in models.py
- [ ] Restart Claude Desktop
- [ ] Run verification tests

---

## Reference

Full diagnostic details in:
`Tools/persona_forge/docs/HANDOFF_FORGE_MCP_BUGFIXES.md`
