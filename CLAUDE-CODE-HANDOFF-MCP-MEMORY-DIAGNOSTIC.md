# Claude Code Handoff: MCP Memory Tools Diagnostic

## Executive Summary

**Symptom:** MCP memory tools (`memory_matrix_search`, `luna_smart_fetch`) return empty results to Claude, but the underlying APIs work correctly when called directly via curl.

**The Mystery:**
```
curl → MCP API (8742) → Engine API (8000) → ✅ Returns 3 results
MCP Tool → MCP API (8742) → Engine API (8000) → ❌ Returns empty
```

**Your Mission:** Trace the data flow, find where results get dropped, and fix it.

---

## What We Know Works

### 1. Engine API (port 8000) - WORKS ✅

```bash
curl -s -X POST http://localhost:8000/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "taco", "limit": 5}'

# Returns:
{
  "results": [
    {"id": "3f096466-59b", "node_type": "ACTION", "content": "A will dig deeper...", ...},
    {"id": "83048446-c01", "node_type": "QUESTION", "content": "Do you still have...", ...},
    {"id": "893dd425-416", "node_type": "FACT", "content": "[assistant] Oh, right!...", ...}
  ],
  "count": 3
}
```

### 2. MCP API (port 8742) - WORKS ✅

```bash
curl -s -X POST http://localhost:8742/memory/search \
  -H "Content-Type: application/json" \
  -d '{"query": "taco", "limit": 5}'

# Returns: Same 3 results - proxy is working
```

### 3. Engine has data - CONFIRMED ✅

```bash
sqlite3 data/luna_engine.db "SELECT COUNT(*) FROM memory_nodes;"
# Returns: 60714
```

### 4. MCP Connection - WORKS ✅

"hey Luna" returns: `"Hey! Luna's here. 💜 (Engine connected on port 8000)"`

---

## What's Broken

### MCP Tools Return Empty

When Luna calls `memory_matrix_search` or `luna_smart_fetch` through Claude Desktop, she gets no results:

```
Luna: "Hmm, still coming up empty through the MCP tools..."
```

The gap is somewhere in this chain:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Claude Desktop                                                      │
│       │                                                              │
│       │ calls tool                                                   │
│       ▼                                                              │
│  FastMCP Server (server.py)                                         │
│       │                                                              │
│       │ invokes async function                                       │
│       ▼                                                              │
│  memory_matrix_search() in tools/memory.py                          │
│       │                                                              │
│       │ calls _call_api("POST", "/memory/search", ...)              │
│       ▼                                                              │
│  _call_api() in tools/memory.py                                     │
│       │                                                              │
│       │ httpx.AsyncClient().post(...)                                │
│       ▼                                                              │
│  MCP API (port 8742) /memory/search endpoint                        │
│       │                                                              │
│       │ proxies to engine                                            │
│       ▼                                                              │
│  Engine API (port 8000) /memory/search                              │
│       │                                                              │
│       │ returns {"results": [...], "count": 3}                       │
│       ▼                                                              │
│  ??? WHERE DOES IT GET LOST ???                                     │
│       │                                                              │
│       ▼                                                              │
│  Luna sees: "No memories found"                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Diagnostic Tasks

### Task 1: Add Tracing to MCP Tools

Add detailed logging to trace the data flow through `tools/memory.py`:

**File:** `src/luna_mcp/tools/memory.py`

```python
import logging

logger = logging.getLogger(__name__)

async def _call_api(method: str, path: str, **kwargs) -> dict:
    """Call MCP API with tracing."""
    url = f"{get_api_url()}{path}"
    
    logger.info(f"[TRACE] _call_api: {method} {url}")
    logger.info(f"[TRACE] _call_api kwargs: {kwargs}")
    
    timeout = httpx.Timeout(30.0, connect=5.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        if method == "GET":
            response = await client.get(url, **kwargs)
        elif method == "POST":
            response = await client.post(url, **kwargs)
        else:
            raise ValueError(f"Unsupported method: {method}")

        logger.info(f"[TRACE] _call_api status: {response.status_code}")
        logger.info(f"[TRACE] _call_api raw response: {response.text[:500]}")
        
        response.raise_for_status()
        result = response.json()
        
        logger.info(f"[TRACE] _call_api parsed: {type(result)} keys={result.keys() if isinstance(result, dict) else 'N/A'}")
        
        return result


async def memory_matrix_search(query: str, limit: int = 10) -> str:
    """Search with tracing."""
    logger.info(f"[TRACE] memory_matrix_search called: query='{query}' limit={limit}")
    
    try:
        response = await _call_api(
            "POST",
            "/memory/search",
            json={"query": query, "limit": limit}
        )
        
        logger.info(f"[TRACE] memory_matrix_search response: {response}")
        
        results = response.get('results', [])
        logger.info(f"[TRACE] memory_matrix_search results count: {len(results)}")
        
        if not results:
            logger.warning(f"[TRACE] memory_matrix_search: NO RESULTS - response was: {response}")
            return f"No memories found for: {query}"

        lines = [f"# Search Results: {query}", ""]
        for r in results:
            node_type = r.get('node_type', r.get('type', '?'))
            content = r.get('content', '')[:200]
            lines.append(f"- [{node_type}] {content}")
            logger.info(f"[TRACE] memory_matrix_search result: [{node_type}] {content[:50]}...")

        return "\n".join(lines)
    except Exception as e:
        logger.exception(f"[TRACE] memory_matrix_search EXCEPTION: {e}")
        return f"Error searching memory: {str(e)}"
```

### Task 2: Add Tracing to MCP API

**File:** `src/luna_mcp/api.py`

Add logging to the `/memory/search` endpoint:

```python
@app.post("/memory/search", response_model=SearchResponse)
async def search_memory(request: SearchRequest):
    """Search memory matrix via engine API."""
    logger.info(f"[TRACE] /memory/search called: query='{request.query}' limit={request.limit}")
    
    if not await check_engine_health():
        logger.warning("[TRACE] /memory/search: Engine not healthy!")
        return SearchResponse(results=[], count=0)
    
    try:
        result = await call_engine(
            "POST", 
            "/memory/search",
            json={"query": request.query, "limit": request.limit}
        )
        
        logger.info(f"[TRACE] /memory/search engine response: {result}")
        
        results = result.get("results", [])
        logger.info(f"[TRACE] /memory/search returning {len(results)} results")
        
        return SearchResponse(results=results, count=len(results))
    except Exception as e:
        logger.exception(f"[TRACE] /memory/search EXCEPTION: {e}")
        return SearchResponse(results=[], count=0)
```

### Task 3: Create Unit Test

**File:** `tests/test_mcp_memory_tools.py`

```python
"""
Unit tests for MCP memory tools data flow.

Tests each layer independently to isolate where data gets dropped.
"""

import pytest
import httpx
import asyncio
from unittest.mock import patch, AsyncMock

# Test configuration
ENGINE_API = "http://localhost:8000"
MCP_API = "http://localhost:8742"


class TestEngineAPIDirectly:
    """Test the engine API works correctly."""
    
    @pytest.mark.asyncio
    async def test_engine_search_returns_results(self):
        """Engine API should return results for known query."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ENGINE_API}/memory/search",
                json={"query": "taco", "limit": 5}
            )
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"Engine API response: {data}")
        
        assert "results" in data
        assert "count" in data
        assert data["count"] > 0, "Engine should have taco memories"
        assert len(data["results"]) > 0


class TestMCPAPIDirectly:
    """Test the MCP API proxy works correctly."""
    
    @pytest.mark.asyncio
    async def test_mcp_api_search_returns_results(self):
        """MCP API should proxy results from engine."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MCP_API}/memory/search",
                json={"query": "taco", "limit": 5}
            )
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"MCP API response: {data}")
        
        assert "results" in data
        assert "count" in data
        assert data["count"] > 0, "MCP API should proxy taco memories"
        assert len(data["results"]) > 0
    
    @pytest.mark.asyncio
    async def test_mcp_api_response_structure(self):
        """Verify response structure matches what tools expect."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{MCP_API}/memory/search",
                json={"query": "taco", "limit": 5}
            )
        
        data = response.json()
        
        # Check structure
        assert isinstance(data.get("results"), list)
        
        if data["results"]:
            result = data["results"][0]
            print(f"Result structure: {result.keys()}")
            
            # Check expected fields
            assert "id" in result or "node_id" in result
            assert "content" in result
            # Note: might be 'type' or 'node_type' - check which!
            has_type = "type" in result or "node_type" in result
            assert has_type, f"Result missing type field: {result.keys()}"


class TestMCPToolsDirectly:
    """Test the MCP tool functions directly (bypassing FastMCP)."""
    
    @pytest.mark.asyncio
    async def test_memory_matrix_search_function(self):
        """Test the actual tool function."""
        # Import the tool
        import sys
        sys.path.insert(0, "src")
        from luna_mcp.tools.memory import memory_matrix_search
        
        result = await memory_matrix_search("taco", limit=5)
        
        print(f"Tool function result:\n{result}")
        
        # Should NOT say "No memories found"
        assert "No memories found" not in result, f"Tool returned no results: {result}"
        assert "Error" not in result, f"Tool returned error: {result}"
        
        # Should have formatted results
        assert "Search Results" in result or "[" in result
    
    @pytest.mark.asyncio
    async def test_luna_smart_fetch_function(self):
        """Test the smart fetch tool function."""
        import sys
        sys.path.insert(0, "src")
        from luna_mcp.tools.memory import luna_smart_fetch
        
        result = await luna_smart_fetch("taco", budget_preset="balanced")
        
        print(f"Smart fetch result:\n{result}")
        
        # Should have some content
        assert "Error" not in result, f"Tool returned error: {result}"


class TestCallAPIFunction:
    """Test the _call_api helper directly."""
    
    @pytest.mark.asyncio
    async def test_call_api_returns_dict(self):
        """Verify _call_api returns proper dict."""
        import sys
        sys.path.insert(0, "src")
        from luna_mcp.tools.memory import _call_api
        
        result = await _call_api(
            "POST",
            "/memory/search",
            json={"query": "taco", "limit": 5}
        )
        
        print(f"_call_api result type: {type(result)}")
        print(f"_call_api result: {result}")
        
        assert isinstance(result, dict)
        assert "results" in result
        assert len(result["results"]) > 0


class TestResponseFormatting:
    """Test that response formatting handles the data correctly."""
    
    def test_format_with_node_type_key(self):
        """Test formatting when response uses 'node_type' key."""
        response = {
            "results": [
                {"id": "abc", "node_type": "FACT", "content": "Test content"},
                {"id": "def", "node_type": "ACTION", "content": "More content"},
            ],
            "count": 2
        }
        
        # Simulate the formatting logic
        results = response.get('results', [])
        assert len(results) == 2
        
        for r in results:
            node_type = r.get('node_type', r.get('type', '?'))
            assert node_type != '?', f"Failed to get type from: {r.keys()}"
    
    def test_format_with_type_key(self):
        """Test formatting when response uses 'type' key."""
        response = {
            "results": [
                {"id": "abc", "type": "FACT", "content": "Test content"},
            ],
            "count": 1
        }
        
        results = response.get('results', [])
        for r in results:
            node_type = r.get('node_type', r.get('type', '?'))
            assert node_type == 'FACT'


class TestGetAPIURL:
    """Test the get_api_url() function."""
    
    def test_get_api_url_returns_correct_url(self):
        """Verify we're hitting the right URL."""
        import sys
        sys.path.insert(0, "src")
        from luna_mcp.launcher import get_api_url
        
        url = get_api_url()
        print(f"get_api_url() returns: {url}")
        
        # Should be MCP API, not engine
        assert "8742" in url or "8001" in url, f"Unexpected URL: {url}"
        assert "localhost" in url or "127.0.0.1" in url


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
```

### Task 4: Create Standalone Diagnostic Script

**File:** `scripts/diagnose_mcp_memory.py`

```python
#!/usr/bin/env python3
"""
MCP Memory Tools Diagnostic Script

Traces the entire data flow from tool to engine and back.
Run this to find where results get dropped.
"""

import asyncio
import httpx
import sys
from pathlib import Path

# Setup path
SRC_PATH = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_PATH))

ENGINE_API = "http://localhost:8000"
MCP_API = "http://localhost:8742"
TEST_QUERY = "taco"


async def check_engine_health():
    """Check if engine is running."""
    print("\n" + "="*60)
    print("STEP 1: Check Engine Health")
    print("="*60)
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{ENGINE_API}/health")
            print(f"  Engine status: {response.status_code}")
            print(f"  Response: {response.json()}")
            return response.status_code == 200
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


async def check_mcp_api_health():
    """Check if MCP API is running."""
    print("\n" + "="*60)
    print("STEP 2: Check MCP API Health")
    print("="*60)
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{MCP_API}/health")
            print(f"  MCP API status: {response.status_code}")
            print(f"  Response: {response.json()}")
            return response.status_code == 200
    except Exception as e:
        print(f"  ERROR: {e}")
        return False


async def test_engine_search_direct():
    """Test engine search directly."""
    print("\n" + "="*60)
    print("STEP 3: Test Engine Search Directly")
    print("="*60)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{ENGINE_API}/memory/search",
                json={"query": TEST_QUERY, "limit": 5}
            )
            print(f"  Status: {response.status_code}")
            data = response.json()
            print(f"  Results count: {data.get('count', 'N/A')}")
            print(f"  Results type: {type(data.get('results'))}")
            if data.get('results'):
                print(f"  First result keys: {data['results'][0].keys()}")
                print(f"  First result preview: {str(data['results'][0])[:200]}")
            return data
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


async def test_mcp_api_search():
    """Test MCP API search."""
    print("\n" + "="*60)
    print("STEP 4: Test MCP API Search")
    print("="*60)
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{MCP_API}/memory/search",
                json={"query": TEST_QUERY, "limit": 5}
            )
            print(f"  Status: {response.status_code}")
            data = response.json()
            print(f"  Results count: {data.get('count', 'N/A')}")
            print(f"  Results type: {type(data.get('results'))}")
            if data.get('results'):
                print(f"  First result keys: {data['results'][0].keys()}")
                print(f"  First result preview: {str(data['results'][0])[:200]}")
            else:
                print(f"  WARNING: No results returned!")
                print(f"  Full response: {data}")
            return data
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


async def test_call_api_function():
    """Test the _call_api function directly."""
    print("\n" + "="*60)
    print("STEP 5: Test _call_api() Function")
    print("="*60)
    
    try:
        from luna_mcp.tools.memory import _call_api
        
        result = await _call_api(
            "POST",
            "/memory/search",
            json={"query": TEST_QUERY, "limit": 5}
        )
        
        print(f"  Return type: {type(result)}")
        print(f"  Keys: {result.keys() if isinstance(result, dict) else 'N/A'}")
        print(f"  Results count: {len(result.get('results', []))}")
        
        if result.get('results'):
            print(f"  First result: {result['results'][0]}")
        else:
            print(f"  WARNING: No results!")
            print(f"  Full return value: {result}")
        
        return result
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_memory_matrix_search_tool():
    """Test the actual tool function."""
    print("\n" + "="*60)
    print("STEP 6: Test memory_matrix_search() Tool")
    print("="*60)
    
    try:
        from luna_mcp.tools.memory import memory_matrix_search
        
        result = await memory_matrix_search(TEST_QUERY, limit=5)
        
        print(f"  Return type: {type(result)}")
        print(f"  Return length: {len(result)}")
        print(f"  Contains 'No memories found': {'No memories found' in result}")
        print(f"  Contains 'Error': {'Error' in result}")
        print(f"\n  Full output:\n{'-'*40}\n{result}\n{'-'*40}")
        
        return result
    except Exception as e:
        print(f"  ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_get_api_url():
    """Check what URL the tools are using."""
    print("\n" + "="*60)
    print("STEP 7: Check get_api_url()")
    print("="*60)
    
    try:
        from luna_mcp.launcher import get_api_url, _api_port
        
        url = get_api_url()
        print(f"  get_api_url() returns: {url}")
        print(f"  _api_port value: {_api_port}")
        
        return url
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


async def main():
    print("="*60)
    print("MCP MEMORY TOOLS DIAGNOSTIC")
    print("="*60)
    print(f"Test query: '{TEST_QUERY}'")
    print(f"Engine API: {ENGINE_API}")
    print(f"MCP API: {MCP_API}")
    
    # Run all diagnostics
    engine_ok = await check_engine_health()
    if not engine_ok:
        print("\n❌ Engine not running! Start it first.")
        return
    
    mcp_ok = await check_mcp_api_health()
    if not mcp_ok:
        print("\n❌ MCP API not running! Say 'hey Luna' first.")
        return
    
    await test_get_api_url()
    engine_results = await test_engine_search_direct()
    mcp_results = await test_mcp_api_search()
    call_api_results = await test_call_api_function()
    tool_results = await test_memory_matrix_search_tool()
    
    # Summary
    print("\n" + "="*60)
    print("DIAGNOSTIC SUMMARY")
    print("="*60)
    print(f"  Engine search:     {'✅ Has results' if engine_results and engine_results.get('results') else '❌ No results'}")
    print(f"  MCP API search:    {'✅ Has results' if mcp_results and mcp_results.get('results') else '❌ No results'}")
    print(f"  _call_api():       {'✅ Has results' if call_api_results and call_api_results.get('results') else '❌ No results'}")
    print(f"  Tool function:     {'✅ Has results' if tool_results and 'No memories found' not in tool_results else '❌ No results'}")
    
    # Find the break point
    print("\n" + "="*60)
    print("ANALYSIS")
    print("="*60)
    
    if not engine_results or not engine_results.get('results'):
        print("  🔴 BREAK POINT: Engine search returns no results")
        print("     → Check Memory Matrix / database")
    elif not mcp_results or not mcp_results.get('results'):
        print("  🔴 BREAK POINT: MCP API proxy returns no results")
        print("     → Check src/luna_mcp/api.py /memory/search endpoint")
    elif not call_api_results or not call_api_results.get('results'):
        print("  🔴 BREAK POINT: _call_api() returns no results")
        print("     → Check src/luna_mcp/tools/memory.py _call_api function")
        print("     → Possibly hitting wrong URL or parsing issue")
    elif tool_results and 'No memories found' in tool_results:
        print("  🔴 BREAK POINT: Tool function formats empty results")
        print("     → Check memory_matrix_search() response handling")
        print("     → Likely issue with 'results' key or empty check logic")
    else:
        print("  ✅ All layers returning data correctly!")
        print("     → Issue may be in FastMCP layer or Claude Desktop")


if __name__ == "__main__":
    asyncio.run(main())
```

---

## Run Diagnostics

### Step 1: Start Required Services

```bash
# Terminal 1: Start Engine
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python scripts/run.py --server

# Terminal 2: Start MCP API (or say "hey Luna" in Claude)
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python -m luna_mcp.api --port 8742
```

### Step 2: Run Diagnostic Script

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python scripts/diagnose_mcp_memory.py
```

### Step 3: Run Unit Tests

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python -m pytest tests/test_mcp_memory_tools.py -v -s
```

### Step 4: Check Logs

After running diagnostics with tracing enabled:

```bash
# Check MCP API logs
tail -100 server.log | grep TRACE

# Or run MCP API in foreground to see logs
python -m luna_mcp.api --port 8742 2>&1 | tee mcp_debug.log
```

---

## Expected Findings

Based on current evidence, likely issues:

### Possibility 1: URL Mismatch
`get_api_url()` might return wrong port or not be initialized when tools run.

### Possibility 2: Response Key Mismatch
Engine returns `node_type`, tools check for `type` (already suspected).

### Possibility 3: Async/Await Issue
Something in the async chain drops the response.

### Possibility 4: FastMCP Layer
The FastMCP server might be munging responses before returning to Claude.

### Possibility 5: Empty Check Bug
```python
if not response.get('results'):  # This is True for empty list []
```
vs
```python
if not response.get('results', None):  # Different behavior
```

---

## Deliverables

1. **Run the diagnostic script** and paste full output
2. **Run the unit tests** and note which pass/fail
3. **Identify the break point** (which layer drops data)
4. **Fix the specific bug** once located
5. **Verify fix** by running diagnostics again

---

## File Locations

| File | Purpose |
|------|---------|
| `src/luna_mcp/tools/memory.py` | MCP tool functions (likely bug location) |
| `src/luna_mcp/api.py` | MCP API endpoints |
| `src/luna_mcp/launcher.py` | API URL management |
| `src/luna/api/server.py` | Engine API endpoints |
| `tests/test_mcp_memory_tools.py` | New unit tests (create this) |
| `scripts/diagnose_mcp_memory.py` | New diagnostic script (create this) |
