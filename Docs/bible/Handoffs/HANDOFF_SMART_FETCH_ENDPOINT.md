# HANDOFF: Add /memory/smart-fetch Endpoint

## Priority: HIGH
## Estimated Time: 15 minutes
## Risk: Low
## Depends On: HANDOFF_MEMORY_SEARCH_FIX.md (completed)

---

## Problem

The MCP tool `luna_smart_fetch` calls `/memory/smart-fetch` endpoint, but this endpoint doesn't exist in the API:

```bash
curl -X POST http://localhost:8000/memory/smart-fetch \
  -H "Content-Type: application/json" \
  -d '{"query": "mars college", "budget_preset": "balanced"}'

# Returns: {"detail":"Not Found"}
```

This breaks the primary memory retrieval tool for the MCP plugin.

## Context

The `smart_fetch` is supposed to be smarter than basic search:
- Uses token budgeting (minimal: 1800, balanced: 3800, rich: 7200)
- Returns context-formatted results
- Intended for the MCP's `luna_detect_context` and `luna_smart_fetch` tools

The `MatrixActor` already has a `get_context()` method that does this internally (used on lines 599, 710, 772 of server.py), but it's not exposed as an API endpoint.

## The Fix

Add a new endpoint to `src/luna/api/server.py` that wraps the matrix's `get_context` method.

### Add Request/Response Models (around line 1320, near other memory models):

```python
class SmartFetchRequest(BaseModel):
    """Request for smart fetch."""
    query: str
    budget_preset: str = "balanced"  # minimal, balanced, rich


class SmartFetchResponse(BaseModel):
    """Response from smart fetch."""
    nodes: list[dict]
    budget_used: int
```

### Add the Endpoint (around line 1390, after /memory/search):

```python
@app.post("/memory/smart-fetch", response_model=SmartFetchResponse)
async def memory_smart_fetch(request: SmartFetchRequest):
    """
    Intelligently fetch relevant context with token budgeting.
    
    This is the primary memory retrieval endpoint used by the MCP plugin.
    Uses the matrix's get_context method with token budget presets.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix or not matrix.is_ready:
        return SmartFetchResponse(nodes=[], budget_used=0)

    # Map budget presets to token limits
    budget_map = {
        "minimal": 1800,
        "balanced": 3800,
        "rich": 7200,
    }
    max_tokens = budget_map.get(request.budget_preset, 3800)

    try:
        # Use the matrix's get_context method
        nodes = await matrix.get_context(
            query=request.query,
            max_tokens=max_tokens,
        )

        # Convert MemoryNode objects to dicts
        results = [
            {
                "id": n.id,
                "node_type": n.node_type,
                "content": n.content,
                "confidence": n.confidence,
                "lock_in": n.lock_in,
                "lock_in_state": n.lock_in_state,
            }
            for n in nodes
        ]

        # Estimate tokens used (rough: ~4 chars per token)
        total_chars = sum(len(n.content) for n in nodes)
        budget_used = total_chars // 4

        return SmartFetchResponse(nodes=results, budget_used=budget_used)

    except Exception as e:
        logger.error(f"Smart fetch error: {e}")
        return SmartFetchResponse(nodes=[], budget_used=0)
```

## Test After Fix

```bash
# Should now return results with token budget info:
curl -X POST http://localhost:8000/memory/smart-fetch \
  -H "Content-Type: application/json" \
  -d '{"query": "mars college", "budget_preset": "balanced"}'

# Expected output:
# {"nodes": [{"id": "...", "node_type": "FACT", "content": "...", ...}], "budget_used": 1234}
```

## Files to Modify

1. `src/luna/api/server.py` - Add SmartFetchRequest, SmartFetchResponse models and /memory/smart-fetch endpoint

## Alternative Quick Fix

If you want a faster fix, you could modify `src/luna_mcp/tools/memory.py` to have `luna_smart_fetch` use `/memory/search` instead:

```python
async def luna_smart_fetch(query: str, budget_preset: str = "balanced") -> str:
    # Quick fix: use /memory/search instead of missing /memory/smart-fetch
    budget_map = {"minimal": 5, "balanced": 10, "rich": 20}
    limit = budget_map.get(budget_preset, 10)
    
    response = await _call_api(
        "POST",
        "/memory/search",
        json={"query": query, "limit": limit}
    )
    # ... rest of formatting
```

But the proper fix is adding the endpoint to maintain the intended architecture.

---

## Context

Discovered during first production MCP test. The `/memory/search` fix (previous handoff) restored basic search, but `smart_fetch` is the primary tool used by `luna_detect_context` for context retrieval. This is needed for full MCP functionality.
