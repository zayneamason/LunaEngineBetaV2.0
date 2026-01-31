# Claude Code Handoff: MCP Plugin Wiring (Option 1)

## Executive Summary

**Problem:** Luna-Hub-MCP-V1 runs in standalone mode - it spawns its own API (port 8742) but has no connection to the actual Luna Engine. Memories don't persist, extraction never triggers.

**Solution:** Rewire MCP to be a true **Layer 2 plugin** that calls the main Luna Engine API (port 8000), just like the Desktop UI does.

**Scope:** ~100 lines of changes across 3 files. No new files needed.

---

## Current vs Target Architecture

### Current (Broken)

```
┌─────────────────────────────────────────────────────────────────────┐
│  Claude Desktop                                                      │
│       │                                                              │
│       ▼                                                              │
│  MCP Server (FastMCP)                                               │
│       │                                                              │
│       ▼                                                              │
│  MCP API (port 8742)  ◄─── get_engine() returns None!               │
│       │                                                              │
│       ▼                                                              │
│  STANDALONE MODE ❌  ◄─── No extraction, no persistence              │
│                                                                      │
│                                                                      │
│  Luna Engine API (port 8000) ◄─── Running separately, never called  │
│       │                                                              │
│       ▼                                                              │
│  Director, Scribe, Librarian, Matrix ◄─── All the good stuff        │
└─────────────────────────────────────────────────────────────────────┘
```

### Target (Plugin Architecture)

```
┌─────────────────────────────────────────────────────────────────────┐
│                   LAYER 2: INTERFACES                                │
│                                                                      │
│  ┌────────────────┐   ┌────────────────┐   ┌────────────────┐       │
│  │   Voice CLI    │   │  Desktop UI    │   │      MCP       │       │
│  │ (in-process)   │   │  (frontend/)   │   │  (luna_mcp/)   │       │
│  └───────┬────────┘   └───────┬────────┘   └───────┬────────┘       │
│          │                    │                    │                 │
│          │ direct             │ HTTP               │ HTTP            │
│          │                    │                    │                 │
│          └────────────────────┴────────────────────┘                 │
│                               │                                      │
│                               ▼                                      │
│                    ┌─────────────────────────────────┐              │
│                    │     LUNA ENGINE API             │              │
│                    │     (port 8000)                 │              │
│                    │                                 │              │
│                    │  ✅ Director                    │              │
│                    │  ✅ Scribe (Ben Franklin)       │              │
│                    │  ✅ Librarian (The Dude)        │              │
│                    │  ✅ Memory Matrix               │              │
│                    │  ✅ Extraction Pipeline         │              │
│                    │                                 │              │
│                    └─────────────────────────────────┘              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Changes Required

### 1. Update `src/luna_mcp/api.py`

**Goal:** Replace `get_engine()` calls with HTTP calls to `localhost:8000`

```python
# ==============================================================================
# AT THE TOP - Add engine API client
# ==============================================================================

import httpx

# Luna Engine API (main engine, must be running)
ENGINE_API_URL = "http://localhost:8000"


async def call_engine(method: str, path: str, **kwargs) -> dict:
    """
    Call the main Luna Engine API.
    
    The engine must be running on port 8000.
    """
    url = f"{ENGINE_API_URL}{path}"
    timeout = httpx.Timeout(30.0, connect=5.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        if method == "GET":
            response = await client.get(url, **kwargs)
        elif method == "POST":
            response = await client.post(url, **kwargs)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()


async def check_engine_health() -> bool:
    """Check if Luna Engine API is running."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(2.0)) as client:
            response = await client.get(f"{ENGINE_API_URL}/health")
            return response.status_code == 200
    except (httpx.ConnectError, httpx.TimeoutException):
        return False


# ==============================================================================
# REMOVE this function entirely:
# ==============================================================================

# def get_engine():
#     """Get the Luna engine instance, if running."""
#     try:
#         from luna.engine import get_engine as _get_engine
#         return _get_engine()
#     except ImportError:
#         return None
#     except Exception:
#         return None


# ==============================================================================
# UPDATE /health endpoint
# ==============================================================================

@app.get("/health")
async def health():
    """MCP API health check."""
    engine_healthy = await check_engine_health()
    return {
        "status": "healthy" if engine_healthy else "engine_disconnected",
        "api": "mcp",
        "version": "1.0.0",
        "engine_connected": engine_healthy,
        "engine_url": ENGINE_API_URL
    }


# ==============================================================================
# UPDATE /context/detect endpoint
# ==============================================================================

@app.post("/context/detect", response_model=DetectContextResponse)
async def detect_context(request: DetectContextRequest):
    """
    Process message through Luna's pipeline.
    
    Proxies to main engine API at localhost:8000.
    """
    if not await check_engine_health():
        return DetectContextResponse(
            response="Luna Engine not running. Start it with: python scripts/run.py --server",
            state={"engine_connected": False},
            memory_context=[],
            system_prompt=""
        )
    
    try:
        # Call the main engine API
        result = await call_engine(
            "POST",
            "/message",
            json={"message": request.message, "timeout": 30.0}
        )
        
        return DetectContextResponse(
            response=result.get("text", ""),
            state={
                "model": result.get("model", "unknown"),
                "delegated": result.get("delegated", False),
                "local": result.get("local", False),
                "engine_connected": True
            },
            memory_context=[],
            system_prompt=""
        )
    except httpx.HTTPStatusError as e:
        return DetectContextResponse(
            response=f"Engine error: {e.response.status_code}",
            state={"error": True},
            memory_context=[],
            system_prompt=""
        )
    except Exception as e:
        return DetectContextResponse(
            response=f"Error: {str(e)}",
            state={"error": True},
            memory_context=[],
            system_prompt=""
        )


# ==============================================================================
# UPDATE /memory/smart-fetch endpoint
# ==============================================================================

@app.post("/memory/smart-fetch", response_model=SmartFetchResponse)
async def smart_fetch(request: SmartFetchRequest):
    """
    Smart context retrieval with budget management.
    
    Proxies to main engine API.
    """
    if not await check_engine_health():
        return SmartFetchResponse(nodes=[], budget_used=0, anchor_ids=[])
    
    try:
        # Call engine's memory search endpoint
        result = await call_engine(
            "POST",
            "/memory/search",
            json={"query": request.query, "limit": 20}
        )
        
        nodes = result.get("results", [])
        
        # Budget mapping
        budgets = {"minimal": 1800, "balanced": 3800, "rich": 7200}
        max_tokens = budgets.get(request.budget_preset, 3800)
        
        # Trim to budget (rough estimate: 4 chars per token)
        total_chars = 0
        trimmed_nodes = []
        for node in nodes:
            content = node.get("content", "")
            if total_chars + len(content) < max_tokens * 4:
                trimmed_nodes.append(node)
                total_chars += len(content)
        
        return SmartFetchResponse(
            nodes=trimmed_nodes,
            budget_used=total_chars // 4,
            anchor_ids=[n.get("id", "") for n in trimmed_nodes]
        )
    except Exception as e:
        logger.error(f"Smart fetch error: {e}")
        return SmartFetchResponse(nodes=[], budget_used=0, anchor_ids=[])


# ==============================================================================
# UPDATE /memory/search endpoint
# ==============================================================================

@app.post("/memory/search", response_model=SearchResponse)
async def search_memory(request: SearchRequest):
    """Search memory matrix via engine API."""
    if not await check_engine_health():
        return SearchResponse(results=[], count=0)
    
    try:
        result = await call_engine(
            "POST", 
            "/memory/search",
            json={"query": request.query, "limit": request.limit}
        )
        
        results = result.get("results", [])
        return SearchResponse(results=results, count=len(results))
    except Exception as e:
        logger.error(f"Memory search error: {e}")
        return SearchResponse(results=[], count=0)


# ==============================================================================
# UPDATE /memory/add-node endpoint
# ==============================================================================

@app.post("/memory/add-node", response_model=AddNodeResponse)
async def add_node(request: AddNodeRequest):
    """Add a memory node via engine API."""
    if not await check_engine_health():
        raise HTTPException(503, "Luna Engine not running")
    
    try:
        result = await call_engine(
            "POST",
            "/memory/add",
            json={
                "node_type": request.node_type,
                "content": request.content,
                "tags": request.tags,
                "confidence": request.confidence,
                "metadata": request.metadata
            }
        )
        
        # Log to memory log
        memory_logger.log_node(
            LogAction.ADD,
            request.node_type,
            result.get("node_id", "unknown"),
            request.content
        )
        
        return AddNodeResponse(
            node_id=result.get("node_id", ""),
            success=True
        )
    except Exception as e:
        memory_logger.log_error(f"Add node failed: {str(e)}")
        raise HTTPException(500, f"Failed to add node: {str(e)}")


# ==============================================================================
# UPDATE /state endpoint
# ==============================================================================

@app.get("/state")
async def get_state():
    """Get Luna engine state via API."""
    if not await check_engine_health():
        return {"status": "engine_not_running", "engine_url": ENGINE_API_URL}
    
    try:
        return await call_engine("GET", "/status")
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ==============================================================================
# UPDATE /consciousness endpoint
# ==============================================================================

@app.get("/consciousness")
async def get_consciousness():
    """Get consciousness state via engine API."""
    if not await check_engine_health():
        return {"status": "engine_not_running", "mood": 0.5, "coherence": 0.5}
    
    try:
        return await call_engine("GET", "/consciousness")
    except Exception as e:
        return {"status": "error", "error": str(e), "mood": 0.5, "coherence": 0.5}
```

---

### 2. Update `src/luna_mcp/tools/state.py`

**Goal:** Update "hey Luna" to check if engine is running

```python
# ==============================================================================
# UPDATE luna_detect_context function
# ==============================================================================

async def luna_detect_context(
    message: str,
    auto_fetch: bool = True,
    budget_preset: str = "balanced"
) -> str:
    """
    Process a message through Luna's full pipeline.

    REQUIRES: Luna Engine running on port 8000
    
    Start engine with: python scripts/run.py --server

    Activation: "hey Luna" triggers this
    Deactivation: "later Luna" - flushes memories, logs session, closes MCP API
    """
    message_lower = message.lower().strip()

    # Check for "hey Luna" activation
    if re.match(r'^hey\s+luna\b', message_lower, re.IGNORECASE):
        try:
            # First, ensure MCP API is running
            port = await ensure_api_running()
            
            # Check if engine is connected
            health = await _call_api("GET", "/health")
            engine_connected = health.get("engine_connected", False)
            
            if not engine_connected:
                return (
                    "⚠️ Luna MCP is ready, but the **Luna Engine** isn't running.\n\n"
                    "Start it with:\n"
                    "```\n"
                    "cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root\n"
                    "python scripts/run.py --server\n"
                    "```\n\n"
                    "Then say 'hey Luna' again!"
                )
            
            # Start session logging
            session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            try:
                await _call_api("POST", "/session/start", json={"session_id": session_id})
            except Exception:
                pass  # Session logging is optional

            return f"Hey! Luna's here. 💜 (Engine connected on port 8000)"
        except Exception as e:
            return f"Error starting Luna: {str(e)}"

    # Check for "later Luna" deactivation
    if re.match(r'^later\s+luna\b', message_lower, re.IGNORECASE):
        return await _handle_deactivation()

    # Normal message processing
    try:
        response = await _call_api(
            "POST",
            "/context/detect",
            json={
                "message": message,
                "auto_fetch": auto_fetch,
                "budget_preset": budget_preset
            }
        )
        
        # Check for engine connection error
        if not response.get("state", {}).get("engine_connected", True):
            return response.get("response", "Engine not connected")
        
        return response.get('response', '')
    except httpx.ConnectError:
        return "Error: Luna's MCP API is not running. Say 'hey Luna' to start."
    except Exception as e:
        return f"Error: {str(e)}"
```

---

### 3. Add Missing Engine Endpoints (if needed)

Check if these endpoints exist in `src/luna/api/server.py`. If not, add them:

```python
# ==============================================================================
# ADD to src/luna/api/server.py if missing
# ==============================================================================

@app.post("/memory/search")
async def memory_search(request: dict):
    """Search memory matrix."""
    query = request.get("query", "")
    limit = request.get("limit", 10)
    
    if not _engine:
        raise HTTPException(503, "Engine not initialized")
    
    matrix = _engine.get_actor("matrix")
    if not matrix:
        return {"results": [], "count": 0}
    
    try:
        results = await matrix.search(query, limit=limit)
        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Memory search error: {e}")
        return {"results": [], "count": 0, "error": str(e)}


@app.post("/memory/add")
async def memory_add(request: dict):
    """Add a memory node."""
    if not _engine:
        raise HTTPException(503, "Engine not initialized")
    
    matrix = _engine.get_actor("matrix")
    if not matrix:
        raise HTTPException(503, "Matrix actor not available")
    
    try:
        node_id = await matrix.add_node(
            node_type=request.get("node_type", "FACT"),
            content=request.get("content", ""),
            tags=request.get("tags"),
            confidence=request.get("confidence", 1.0),
            metadata=request.get("metadata")
        )
        return {"node_id": node_id, "success": True}
    except Exception as e:
        raise HTTPException(500, f"Failed to add node: {str(e)}")
```

---

## Verification Steps

### 1. Start Luna Engine (Terminal 1)

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python scripts/run.py --server
```

Verify it's running:
```bash
curl http://localhost:8000/health
# Should return: {"status": "running", ...}
```

### 2. Test MCP in Claude Desktop

1. Say "hey Luna"
2. Should see: "Hey! Luna's here. 💜 (Engine connected on port 8000)"
3. Say something like "Remember that I like tacos"
4. Say "later Luna"
5. Should see session summary with memories added

### 3. Verify Extraction Worked

```bash
sqlite3 data/luna_engine.db "SELECT created_at, node_type, substr(content, 1, 50) FROM memory_nodes ORDER BY created_at DESC LIMIT 5;"
```

Should see recent entries from your conversation.

### 4. Test Without Engine Running

1. Stop the engine (Ctrl+C in Terminal 1)
2. Say "hey Luna" in Claude Desktop
3. Should see: "⚠️ Luna MCP is ready, but the Luna Engine isn't running..."

---

## Configuration

### Port Allocation (Final)

| Service | Port | Purpose |
|---------|------|---------|
| **Luna Engine API** | 8000 | Main engine, all interfaces connect here |
| **MCP API** | 8742 | Thin adapter for Claude Desktop (proxies to 8000) |
| **Eclissi Hub** | 8882 | Legacy (can run in parallel) |

### Claude Desktop Config

No changes needed - keeps current config:

```json
{
  "mcpServers": {
    "Luna-Hub-MCP-V1": {
      "command": "/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/.venv/bin/python",
      "args": ["-m", "luna_mcp.server"],
      "cwd": "/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src",
      "env": {
        "LUNA_BASE_PATH": "/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root",
        "LUNA_MCP_API_URL": "http://localhost:8742"
      }
    }
  }
}
```

---

## Summary

| What | Before | After |
|------|--------|-------|
| MCP API connection | `get_engine()` (fails - no engine in process) | HTTP to `localhost:8000` |
| Engine dependency | Standalone mode (broken) | Requires engine running |
| Extraction | Never triggered | Works via engine API |
| Memory persistence | None | Full pipeline active |
| Architecture | Orphaned process | True Layer 2 plugin |

**Total changes:** ~100 lines across 2-3 files
**Risk:** Low - just changing connection method
**Dependencies:** Engine must be running on port 8000
