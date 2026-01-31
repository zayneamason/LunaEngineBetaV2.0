# HANDOFF: Memory Search API Fix

## Priority: HIGH
## Estimated Time: 5 minutes
## Risk: Low

---

## Problem

The `/memory/search` API endpoint returns empty results even though:
1. The database contains 60,730 memory nodes
2. Direct SQL queries find results correctly
3. Direct Python calls to `MemoryMatrix.search_nodes()` work perfectly

## Root Cause

In `src/luna/api/server.py`, the `/memory/search` endpoint (around line 1361) checks for methods that don't exist:

```python
if hasattr(memory, "search"):
    results = await memory.search(request.query, limit=request.limit)
elif hasattr(memory, "hybrid_search"):
    results = await memory.hybrid_search(request.query, limit=request.limit)
else:
    # Fallback to broken query
```

The `MemoryMatrix` class only has `search_nodes()`, not `search()` or `hybrid_search()`. So the code always falls through to the broken fallback.

## Verification

```bash
# This returns empty:
curl -X POST http://localhost:8000/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "mars", "limit": 5}'

# But direct SQL finds results:
sqlite3 data/luna_engine.db "SELECT COUNT(*) FROM memory_nodes WHERE content LIKE '%mars%';"
# Returns: 50+ matches
```

## The Fix

In `src/luna/api/server.py`, find the `memory_search` function (around line 1350-1380) and change the method call:

### Before:
```python
@app.post("/memory/search", response_model=MemorySearchResponse)
async def memory_search(request: MemorySearchRequest):
    # ... setup code ...
    
    # Use the matrix's search method if available
    if hasattr(memory, "search"):
        results = await memory.search(request.query, limit=request.limit)
    elif hasattr(memory, "hybrid_search"):
        results = await memory.hybrid_search(request.query, limit=request.limit)
    else:
        # Fallback to recent nodes filtered by content
        # ... broken fallback code ...
```

### After:
```python
@app.post("/memory/search", response_model=MemorySearchResponse)
async def memory_search(request: MemorySearchRequest):
    # ... setup code ...
    
    # Use the matrix's search_nodes method
    if hasattr(memory, "search_nodes"):
        nodes = await memory.search_nodes(query=request.query, limit=request.limit)
        # Convert MemoryNode objects to dicts for JSON response
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
    else:
        # Fallback (should never hit this now)
        results = []

    return MemorySearchResponse(results=results, count=len(results))
```

## Also Check

The `MatrixActor` class in `src/luna/actors/matrix.py` has a `search()` method that wraps `search_nodes()`. You could alternatively ensure the API accesses the actor's `search()` method instead of the underlying `MemoryMatrix` directly. But the fix above is simpler and more direct.

## Test After Fix

```bash
# Should now return results:
curl -X POST http://localhost:8000/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "mars", "limit": 5}'

# Expected output:
# {"results": [{"id": "...", "content": "...", ...}], "count": 5}
```

## Files to Modify

1. `src/luna/api/server.py` - Fix the `memory_search` endpoint (~line 1350-1380)

---

## Context

This was discovered during first production test of the Luna MCP. The MCP plugin calls `/memory/search` which returns empty, breaking all memory retrieval through Claude Desktop. Once fixed, Luna's memory system will work end-to-end through the MCP.
