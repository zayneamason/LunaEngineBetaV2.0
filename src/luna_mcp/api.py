"""
Luna MCP API — Layer 2 Plugin for Luna Engine
==============================================

This is a thin adapter that proxies requests to the main Luna Engine API (port 8000).
The MCP API runs on port 8742 and is only used by Claude Desktop.

Architecture:
  Claude Desktop → MCP Server (FastMCP) → MCP API (port 8742) → Engine API (port 8000)

The engine MUST be running for MCP to work. Start it with:
  python scripts/run.py --server

Endpoints:
- GET /health — Health check (checks engine connection)
- POST /memory/smart-fetch — Smart context retrieval
- POST /memory/search — Search memory matrix
- POST /memory/add-node — Add a memory node
- POST /context/detect — Process message through Luna pipeline
- GET /state — Get Luna state
- GET /consciousness — Get consciousness state
- GET /memory/log — Get memory log entries
- POST /session/start — Start a session
- POST /session/end — End session and get stats
- POST /memory/flush — Flush pending memory operations
"""

import sys
import time
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Path setup for imports
SRC_PATH = Path(__file__).parent.parent.resolve()
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from luna_mcp.memory_log import memory_logger, MEMORY_LOG_FILE, LogAction

logger = logging.getLogger(__name__)

app = FastAPI(title="Luna MCP API", version="1.0.0")

# Luna Engine API (main engine, must be running)
ENGINE_API_URL = "http://localhost:8000"


# ==============================================================================
# Engine API Client
# ==============================================================================

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
# Request/Response Models
# ==============================================================================

class SmartFetchRequest(BaseModel):
    query: str
    budget_preset: str = "balanced"  # minimal, balanced, rich


class SmartFetchResponse(BaseModel):
    nodes: List[Dict[str, Any]]
    budget_used: int
    anchor_ids: List[str]


class DetectContextRequest(BaseModel):
    message: str
    auto_fetch: bool = True
    budget_preset: str = "balanced"


class DetectContextResponse(BaseModel):
    response: str
    state: Dict[str, Any]
    memory_context: List[Dict[str, Any]]
    system_prompt: str


class AddNodeRequest(BaseModel):
    node_type: str  # FACT, DECISION, PROBLEM, ACTION, etc.
    content: str
    tags: Optional[List[str]] = None
    confidence: float = 1.0
    metadata: Optional[Dict[str, Any]] = None


class AddNodeResponse(BaseModel):
    node_id: str
    success: bool


class SearchRequest(BaseModel):
    query: str
    limit: int = 10
    search_type: str = "hybrid"  # keyword, semantic, hybrid


class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    count: int


class SessionStartRequest(BaseModel):
    session_id: Optional[str] = None


# ==============================================================================
# Health & Status Endpoints
# ==============================================================================

@app.get("/health")
async def health():
    """MCP API health check - verifies engine connection."""
    engine_healthy = await check_engine_health()
    return {
        "status": "healthy" if engine_healthy else "engine_disconnected",
        "api": "mcp",
        "version": "1.0.0",
        "engine_connected": engine_healthy,
        "engine_url": ENGINE_API_URL
    }


@app.get("/state")
async def get_state():
    """Get Luna engine state via API."""
    if not await check_engine_health():
        return {"status": "engine_not_running", "engine_url": ENGINE_API_URL}

    try:
        return await call_engine("GET", "/status")
    except Exception as e:
        return {"status": "error", "error": str(e)}


@app.get("/consciousness")
async def get_consciousness():
    """Get consciousness state via engine API."""
    if not await check_engine_health():
        return {"status": "engine_not_running", "mood": 0.5, "coherence": 0.5}

    try:
        return await call_engine("GET", "/consciousness")
    except Exception as e:
        return {"status": "error", "error": str(e), "mood": 0.5, "coherence": 0.5}


# ==============================================================================
# Memory Endpoints
# ==============================================================================

@app.post("/memory/smart-fetch", response_model=SmartFetchResponse)
async def smart_fetch(request: SmartFetchRequest):
    """
    Smart context retrieval with budget management.

    Proxies to main engine API.
    """
    logger.info(f"[TRACE] /memory/smart-fetch called: query='{request.query}' budget='{request.budget_preset}'")

    if not await check_engine_health():
        logger.warning("[TRACE] /memory/smart-fetch: Engine not healthy!")
        return SmartFetchResponse(nodes=[], budget_used=0, anchor_ids=[])

    try:
        # Call engine's memory search endpoint
        result = await call_engine(
            "POST",
            "/memory/search",
            json={"query": request.query, "limit": 20}
        )

        logger.info(f"[TRACE] /memory/smart-fetch engine response: {result}")

        nodes = result.get("results", [])
        logger.info(f"[TRACE] /memory/smart-fetch got {len(nodes)} nodes from engine")

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

        logger.info(f"[TRACE] /memory/smart-fetch returning {len(trimmed_nodes)} nodes after budget trim")

        return SmartFetchResponse(
            nodes=trimmed_nodes,
            budget_used=total_chars // 4,
            anchor_ids=[n.get("id", "") for n in trimmed_nodes]
        )
    except httpx.HTTPStatusError as e:
        logger.exception(f"[TRACE] /memory/smart-fetch HTTP error: {e}")
        return SmartFetchResponse(nodes=[], budget_used=0, anchor_ids=[])
    except Exception as e:
        logger.exception(f"[TRACE] /memory/smart-fetch EXCEPTION: {e}")
        return SmartFetchResponse(nodes=[], budget_used=0, anchor_ids=[])


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
    except httpx.HTTPStatusError as e:
        logger.exception(f"[TRACE] /memory/search HTTP error: {e}")
        return SearchResponse(results=[], count=0)
    except Exception as e:
        logger.exception(f"[TRACE] /memory/search EXCEPTION: {e}")
        return SearchResponse(results=[], count=0)


@app.post("/memory/add-node", response_model=AddNodeResponse)
async def add_node(request: AddNodeRequest):
    """Add a memory node via engine API."""
    if not await check_engine_health():
        raise HTTPException(503, "Luna Engine not running. Start with: python scripts/run.py --server")

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
    except httpx.HTTPStatusError as e:
        memory_logger.log_error(f"Add node HTTP error: {e.response.status_code}")
        raise HTTPException(e.response.status_code, f"Engine error: {e.response.text}")
    except Exception as e:
        memory_logger.log_error(f"Add node failed: {str(e)}")
        raise HTTPException(500, f"Failed to add node: {str(e)}")


@app.post("/memory/flush")
async def flush_memories():
    """
    Flush any pending memory operations.

    Ensures all queued extractions are written to Memory Matrix.
    """
    if not await check_engine_health():
        return {"pending": 0, "flushed": 0, "engine_connected": False}

    try:
        # Call engine's flush endpoint if it exists
        result = await call_engine("POST", "/memory/flush")
        return result
    except httpx.HTTPStatusError:
        # Endpoint may not exist - that's OK
        return {"pending": 0, "flushed": 0, "message": "Flush not implemented in engine"}
    except Exception as e:
        logger.error(f"Memory flush error: {e}")
        return {"pending": 0, "flushed": 0, "error": str(e)}


# ==============================================================================
# Context Detection
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
            state={"error": True, "engine_connected": True},
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
# Entity Endpoints
# ==============================================================================

@app.get("/entities/resolve")
async def resolve_entity(name: str):
    """Resolve an entity by name/alias."""
    if not await check_engine_health():
        return {"name": name, "resolved": False, "message": "Engine not connected"}

    # TODO: Implement entity resolution via engine API
    return {"name": name, "resolved": False, "message": "Entity system not yet wired"}


# ==============================================================================
# Memory Log Endpoints
# ==============================================================================

@app.get("/memory/log")
async def get_memory_log(limit: int = 100):
    """Get recent memory log entries."""
    entries = memory_logger.get_recent_entries(n=limit)
    return {
        "entries": entries,
        "count": len(entries),
        "log_file": str(MEMORY_LOG_FILE)
    }


@app.get("/memory/log/raw")
async def get_memory_log_raw():
    """Get raw memory log file contents."""
    if MEMORY_LOG_FILE.exists():
        return {"content": MEMORY_LOG_FILE.read_text()}
    return {"content": "", "error": "Log file not found"}


# ==============================================================================
# Session Management
# ==============================================================================

@app.get("/session/stats")
async def get_session_stats():
    """Get current session statistics."""
    return memory_logger.get_session_stats()


@app.post("/session/start")
async def start_session(request: SessionStartRequest):
    """Start a new session."""
    session_id = request.session_id or f"session_{int(time.time())}"
    memory_logger.start_session(session_id)
    return {"session_id": session_id, "status": "started"}


@app.post("/session/end")
async def end_session():
    """End current session and return stats."""
    stats = memory_logger.end_session()
    return stats


# ==============================================================================
# Hub Endpoints (Proxy to Engine for Conversation Recording)
# ==============================================================================

class HubSessionCreateRequest(BaseModel):
    app_context: str = "mcp"


class HubTurnAddRequest(BaseModel):
    role: str
    content: str
    session_id: str
    tokens: int = 0


class HubSearchRequest(BaseModel):
    query: str = ""
    session_id: Optional[str] = None
    limit: int = 100
    search_type: str = "recent"


class ExtractionRequest(BaseModel):
    content: str
    role: str = "user"
    session_id: Optional[str] = None
    immediate: bool = True


@app.post("/hub/session/create")
async def hub_session_create(request: HubSessionCreateRequest):
    """Create a new conversation session via engine API."""
    if not await check_engine_health():
        raise HTTPException(503, "Luna Engine not running")

    try:
        result = await call_engine(
            "POST",
            "/hub/session/create",
            json={"app_context": request.app_context}
        )
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, f"Engine error: {e.response.text}")
    except Exception as e:
        raise HTTPException(500, f"Failed to create session: {str(e)}")


@app.post("/hub/session/end")
async def hub_session_end(session_id: str):
    """End a conversation session via engine API."""
    if not await check_engine_health():
        raise HTTPException(503, "Luna Engine not running")

    try:
        result = await call_engine(
            "POST",
            f"/hub/session/end?session_id={session_id}"
        )
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, f"Engine error: {e.response.text}")
    except Exception as e:
        raise HTTPException(500, f"Failed to end session: {str(e)}")


@app.post("/hub/turn/add")
async def hub_turn_add(request: HubTurnAddRequest):
    """Add a conversation turn via engine API."""
    if not await check_engine_health():
        raise HTTPException(503, "Luna Engine not running")

    try:
        result = await call_engine(
            "POST",
            "/hub/turn/add",
            json={
                "role": request.role,
                "content": request.content,
                "session_id": request.session_id,
                "tokens": request.tokens
            }
        )
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, f"Engine error: {e.response.text}")
    except Exception as e:
        raise HTTPException(500, f"Failed to add turn: {str(e)}")


@app.post("/hub/search")
async def hub_search(request: HubSearchRequest):
    """Search conversation history via engine API."""
    if not await check_engine_health():
        return {"results": [], "total": 0}

    try:
        result = await call_engine(
            "POST",
            "/hub/search",
            json={
                "query": request.query,
                "session_id": request.session_id,
                "limit": request.limit,
                "search_type": request.search_type
            }
        )
        return result
    except httpx.HTTPStatusError as e:
        logger.error(f"Hub search error: {e}")
        return {"results": [], "total": 0}
    except Exception as e:
        logger.error(f"Hub search error: {e}")
        return {"results": [], "total": 0}


@app.post("/extraction/trigger")
async def extraction_trigger(request: ExtractionRequest):
    """Trigger memory extraction via engine API."""
    if not await check_engine_health():
        raise HTTPException(503, "Luna Engine not running")

    try:
        result = await call_engine(
            "POST",
            "/extraction/trigger",
            json={
                "content": request.content,
                "role": request.role,
                "session_id": request.session_id,
                "immediate": request.immediate
            }
        )
        return result
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, f"Engine error: {e.response.text}")
    except Exception as e:
        raise HTTPException(500, f"Failed to trigger extraction: {str(e)}")


@app.get("/hub/active_window")
async def hub_active_window(session_id: Optional[str] = None, limit: int = 100):
    """Get active window turns via engine API."""
    if not await check_engine_health():
        return {"turns": [], "total_tokens": 0, "turn_count": 0}

    try:
        params = {"limit": limit}
        if session_id:
            params["session_id"] = session_id
        result = await call_engine(
            "GET",
            "/hub/active_window",
            params=params
        )
        return result
    except httpx.HTTPStatusError as e:
        logger.error(f"Active window error: {e}")
        return {"turns": [], "total_tokens": 0, "turn_count": 0}
    except Exception as e:
        logger.error(f"Active window error: {e}")
        return {"turns": [], "total_tokens": 0, "turn_count": 0}


# ==============================================================================
# Server Runner
# ==============================================================================

def run_mcp_api(port: int = 8742):
    """Run the MCP API server."""
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Luna MCP API Server")
    parser.add_argument("--port", type=int, default=8742, help="Port to run on")
    args = parser.parse_args()
    run_mcp_api(port=args.port)
