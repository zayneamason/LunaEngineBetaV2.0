# HANDOFF: Persona Forge MCP Integration Bugfixes

**Created:** 2026-01-29
**Author:** Claude (Architect Mode)
**Priority:** HIGH - Blocks all ingestion pipeline work
**Estimated Fix Time:** 30-45 minutes

---

## Executive Summary

End-to-end testing of the Persona Forge MCP integration revealed **6 bugs** across 3 files. Most are API signature mismatches between the MCP wrapper (`forge.py`) and the underlying engine classes. All fixes are straightforward - no architectural changes needed.

**What Works:**
- ✅ `forge_load()` - loads JSONL correctly
- ✅ `forge_status()` - returns session state
- ✅ `forge_list_sources()` - lists files
- ✅ `forge_read_raw()` - reads file content
- ✅ `forge_read_matrix()` - reads Memory Matrix nodes (22K+ available)
- ✅ `forge_read_turns()` - reads conversation turns (459 turns, 64 sessions)
- ✅ `forge_mint()` - generates synthetic examples (partially - adds to list)
- ✅ `forge_search()` - searches existing examples
- ✅ `character_list()` - lists profiles
- ✅ `character_load()` - loads Luna profile
- ✅ `character_show()` - displays profile details
- ✅ `character_modulate()` - adjusts traits
- ✅ `vk_list()` - lists test suites
- ✅ `vk_probes()` - shows probe details

**What's Broken:**
- ❌ `forge_assay()` - wrong parameter passed to analyze()
- ❌ `forge_gaps()` - depends on forge_assay()
- ❌ `forge_add_example()` - AntiPatterns model iteration
- ❌ `forge_add_batch()` - depends on forge_add_example()
- ❌ `forge_export()` - method name mismatch + missing property
- ❌ `vk_run()` - asyncio.run() in async context

---

## Bug Details & Fixes

### Bug 1: forge_assay() - Wrong Parameter

**File:** `src/luna_mcp/tools/forge.py`
**Line:** ~135
**Error:** `Assayer.analyze() got an unexpected keyword argument 'target_profile'`

**Root Cause:** The wrapper passes `target_profile` to `analyze()`, but the Assayer sets profile in `__init__`, not in `analyze()`.

**Current Code:**
```python
assay = assayer.analyze(examples, target_profile=DIRECTOR_PROFILE)
```

**Fixed Code:**
```python
assay = assayer.analyze(examples)
```

**Note:** The `_state["assayer"]` is already initialized with the default profile in the global state setup.

---

### Bug 2: forge_add_example() - Pydantic Model Iteration

**File:** `src/luna_mcp/tools/forge.py`
**Line:** ~295
**Error:** `'AntiPatterns' object has no attribute 'items'`

**Root Cause:** `VoiceMarkers` and `AntiPatterns` are Pydantic models, not dicts. The code calls `.items()` but should use `.model_dump()`.

**Current Code:**
```python
anti_found = [k for k, v in example.anti_patterns.items() if v]
```

**Fixed Code:**
```python
anti_found = [k for k, v in example.anti_patterns.model_dump().items() if v]
```

**Also update voice_markers line (around line ~288):**
```python
# Current
example.voice_markers = crucible._detect_voice_markers(assistant_response)

# If voice_markers are returned as dicts, convert to models:
voice_dict = crucible._detect_voice_markers(assistant_response)
if isinstance(voice_dict, dict):
    example.voice_markers = VoiceMarkers(**voice_dict)
else:
    example.voice_markers = voice_dict
```

---

### Bug 3: forge_export() - Method Name Mismatch

**File:** `Tools/persona_forge/src/persona_forge/engine/anvil.py`
**Line:** ~213 (in `_example_to_record`)
**Error:** `'TrainingExample' object has no attribute 'to_training_format'`

**Root Cause:** The `TrainingExample` model has `to_training_dict()`, not `to_training_format()`.

**Current Code:**
```python
base_format = example.to_training_format()
```

**Fixed Code:**
```python
base_format = example.to_training_dict()
```

---

### Bug 4: forge_export() - Missing is_clean Property

**File:** `Tools/persona_forge/src/persona_forge/engine/anvil.py`
**Line:** ~223 (in `_example_to_record`)
**Error:** `'AntiPatterns' object has no attribute 'is_clean'`

**Root Cause:** `AntiPatterns` model doesn't have an `is_clean` property.

**Option A - Add property to model (preferred):**

**File:** `Tools/persona_forge/src/persona_forge/engine/models.py`
**In class AntiPatterns, add:**
```python
@property
def is_clean(self) -> bool:
    """True if no anti-patterns detected."""
    return self.total == 0
```

**Option B - Fix in anvil.py directly:**
```python
# Current
"anti_patterns_clean": example.anti_patterns.is_clean,

# Fixed
"anti_patterns_clean": example.anti_patterns.total == 0,
```

---

### Bug 5: vk_run() - Asyncio Event Loop

**File:** `src/luna_mcp/tools/forge.py`
**Line:** ~475 (in vk_run function)
**Error:** `asyncio.run() cannot be called from a running event loop`

**Root Cause:** The VK runner uses `asyncio.run()` internally, but MCP tools already run in an async context.

**Current Code:**
```python
async def vk_run(model_id: str, suite_name: str = "luna", verbose: bool = False) -> dict[str, Any]:
    # ...
    runner = SyncVoightKampffRunner(model_fn=mock_model_fn, model_id=model_id)
    report = runner.run_suite(suite)  # This internally calls asyncio.run()
```

**Fix Options:**

**Option A - Use nest_asyncio (quick fix):**
At top of forge.py:
```python
import nest_asyncio
nest_asyncio.apply()
```

**Option B - Use thread pool (cleaner):**
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

async def vk_run(model_id: str, suite_name: str = "luna", verbose: bool = False) -> dict[str, Any]:
    # ... setup code ...
    
    # Run sync code in thread pool
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor() as pool:
        report = await loop.run_in_executor(
            pool,
            lambda: runner.run_suite(suite)
        )
    
    # ... result formatting ...
```

**Option C - Check for existing loop:**
```python
def _run_sync_in_async(sync_func):
    """Run sync function that might use asyncio.run()."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - safe to use asyncio.run()
        return sync_func()
    
    # Already in async context - use thread
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor() as pool:
        future = pool.submit(sync_func)
        return future.result()
```

---

### Bug 6: Crucible Voice/Anti Detection Return Types

**File:** `src/luna_mcp/tools/forge.py`
**Lines:** ~285-290

**Potential Issue:** The Crucible's `_detect_voice_markers()` and `_detect_anti_patterns()` might return dicts instead of Pydantic models, causing type mismatches.

**Defensive Fix:**
```python
# In forge_add_example(), after creating example:

# Detect and assign voice markers
voice_result = crucible._detect_voice_markers(assistant_response)
if isinstance(voice_result, dict):
    from persona_forge.engine.models import VoiceMarkers
    example.voice_markers = VoiceMarkers(**voice_result)
else:
    example.voice_markers = voice_result

# Detect and assign anti-patterns
anti_result = crucible._detect_anti_patterns(assistant_response)
if isinstance(anti_result, dict):
    from persona_forge.engine.models import AntiPatterns
    example.anti_patterns = AntiPatterns(**anti_result)
else:
    example.anti_patterns = anti_result
```

---

## Complete Fix File Locations

| File | Bugs | Lines |
|------|------|-------|
| `src/luna_mcp/tools/forge.py` | 1, 2, 5, 6 | ~135, ~285-295, ~475 |
| `Tools/persona_forge/src/persona_forge/engine/anvil.py` | 3, 4 | ~213, ~223 |
| `Tools/persona_forge/src/persona_forge/engine/models.py` | 4 (optional) | Add property |

---

## Verification Steps

After applying fixes, run these tests in order:

```
# 1. Basic load
forge_load("Tools/persona_forge/data/sample_training.jsonl")
# Expected: success=true, examples_loaded=10

# 2. Assay (Bug 1)
forge_assay()
# Expected: success=true, health_score > 0

# 3. Add example (Bugs 2, 6)
forge_add_example(
    user_message="Hey Luna",
    assistant_response="Hey! What's up?",
    interaction_type="greeting"
)
# Expected: success=true, id returned

# 4. Export (Bugs 3, 4)
forge_export("Tools/persona_forge/data/test_export.jsonl")
# Expected: success=true, path returned

# 5. VK Run (Bug 5)
vk_run(model_id="test-mock", suite_name="minimal")
# Expected: success=true, passed=true/false

# 6. Full pipeline
forge_add_batch([
    {"user_message": "test", "assistant_response": "response"}
])
# Expected: success=true, added=1
```

---

## Data Available for Ingestion (Post-Fix)

Once fixed, we have access to:

| Source | Tool | Count | Quality |
|--------|------|-------|---------|
| Conversation Turns | `forge_read_turns()` | 459 | GOLD |
| Memory Matrix Nodes | `forge_read_matrix()` | 22,050 | Varies |
| Alpha Session Notes | `forge_read_raw()` | 76 files | GOLD |
| Session Transcripts | `forge_read_raw()` | 145 files | GOLD |

Database location: `data/luna_engine.db`

---

## Notes for Claude Code

1. **Start with Bug 1** - it's blocking everything else
2. **Bug 2 and 6 are related** - both deal with Pydantic model handling
3. **Bug 5 requires a design decision** - recommend Option A (nest_asyncio) for speed
4. **Add import if needed:** `from persona_forge.engine.models import VoiceMarkers, AntiPatterns`
5. **Test incrementally** - don't batch all fixes

---

## Rollback

If issues persist, the original standalone Forge MCP server still works:
`Tools/persona_forge/src/persona_forge/mcp/server.py`

It can be re-enabled in Claude Desktop config as a separate server.
