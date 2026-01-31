# HANDOFF: Forge MCP Bugfix

## Issue
`forge_load` fails with error:
```
'Crucible' object has no attribute 'reset_stats'
```

## Root Cause
The `forge.py` integration calls `crucible.reset_stats()` but the Crucible class only has `clear()` method.

## Fix

**File:** `src/luna_mcp/tools/forge.py`

**Line 83** - Change:
```python
crucible.reset_stats()
```

To:
```python
crucible.clear()
```

## Full Context

```python
# Line 80-90 in forge.py
async def forge_load(path: str) -> dict[str, Any]:
    """Load training data from JSONL file."""
    crucible = _state["crucible"]
    crucible.clear()  # <-- FIX: was reset_stats()

    path_obj = _resolve_path(path)
    if not path_obj.exists():
        return {"success": False, "error": f"File not found: {path_obj}"}
    # ... rest unchanged
```

## Validation

After fix, restart Claude Desktop and test:
```
forge_load("Tools/persona_forge/data/sample_training.jsonl")
```

Should return:
```json
{
  "success": true,
  "examples_loaded": N,
  "total_examples": N
}
```

## Time Estimate
< 1 minute
