# Claude Code Handoff: Luna-Hub-MCP-V1

## Executive Summary

Create **Luna-Hub-MCP-V1** - a modular MCP server for Luna Engine V2 that communicates through a dedicated **MCP API layer**. This replaces the Eclissi-based `Luna-v2` MCP. The MCP should be the canonical way Claude Desktop talks to Luna.

**Activation Triggers:** "hey Luna" and "later Luna" in Claude Desktop should route through this MCP.

---

## Context

### Current State
- Claude Desktop has `Luna-v2` MCP pointing to **Eclissi** project
- Eclissi MCP calls Eclissi Hub API on port 8882
- Luna V2 has its own API server on port 8000
- Systems are disconnected

### Target State
- **One MCP:** `Luna-Hub-MCP-V1` in Luna V2 project
- **Dedicated MCP API:** Separate from main API, clean interface
- **Modular design:** Easy to extend, test, and maintain
- **Discontinue Luna-v2:** Remove old Eclissi MCP reference

---

## Architecture

### Layer Separation (Per Bible)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   LAYER 2: INTERFACES (Stateless)                        │
│                                                                          │
│   ┌────────────────┐   ┌────────────────┐   ┌────────────────┐         │
│   │ Claude Desktop │   │   Voice CLI    │   │  Desktop UI    │         │
│   │  (MCP Client)  │   │  (Direct)      │   │  (HTTP)        │         │
│   └───────┬────────┘   └───────┬────────┘   └───────┬────────┘         │
│           │                    │                    │                   │
│           ▼                    │                    │                   │
│   ┌────────────────┐          │                    │                   │
│   │ Luna-Hub-MCP-V1│          │                    │                   │
│   │  (FastMCP)     │          │                    │                   │
│   └───────┬────────┘          │                    │                   │
│           │                    │                    │                   │
│           ▼                    │                    │                   │
│   ┌────────────────┐          │                    │                   │
│   │   MCP API      │──────────┴────────────────────┘                   │
│   │ (Port 8001)    │   All interfaces hit same internal API             │
│   └───────┬────────┘                                                    │
│           │                                                             │
└───────────┼─────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│               LAYER 1.5: RUNTIME ENGINE (Stateful)                       │
│                                                                          │
│   ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐       │
│   │  DIRECTOR  │  │   MATRIX   │  │   SCRIBE   │  │  LIBRARIAN │       │
│   │   ACTOR    │  │   ACTOR    │  │   (Ben)    │  │   (Dude)   │       │
│   └────────────┘  └────────────┘  └────────────┘  └────────────┘       │
│                                                                          │
│   ┌────────────┐  ┌────────────┐                                        │
│   │    OVEN    │  │   VOICE    │                                        │
│   │   ACTOR    │  │   ACTOR    │                                        │
│   └────────────┘  └────────────┘                                        │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│               LAYER 0: CONSTITUTIONAL (Luna's Soul)                      │
│                                                                          │
│                         memory_matrix.db                                 │
│              (nodes + edges + vectors + FTS5 via sqlite-vec)            │
│                                                                          │
│                          LUNA IS THIS FILE                               │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Key Insight: Separate MCP API

**Why not just call the main API?**

1. **Modularity:** MCP has different needs than HTTP clients
2. **Isolation:** MCP crashes shouldn't affect main API
3. **Evolution:** Can version MCP API independently
4. **Testing:** Can mock MCP API without touching engine

**The MCP API is a thin adapter layer** between MCP tools and engine actors.

---

## Directory Structure

```
src/
├── luna/                    # Existing engine code
│   └── api/
│       └── server.py        # Main API (port 8000) - UNCHANGED
│
├── mcp/                     # NEW: MCP Server package
│   ├── __init__.py
│   ├── server.py            # FastMCP server entry point
│   ├── api.py               # MCP API layer (FastAPI, port 8001)
│   ├── launcher.py          # Auto-launch MCP API on "hey Luna"
│   ├── memory_log.py        # Memory Matrix logging system
│   ├── tools/               # Tool modules (one per domain)
│   │   ├── __init__.py
│   │   ├── filesystem.py    # luna_read, luna_write, luna_list
│   │   ├── memory.py        # smart_fetch, search, add_node, add_edge
│   │   ├── state.py         # detect_context, get_state, set_app_context
│   │   ├── git.py           # git_sync
│   │   └── legal.py         # legal_search, legal_get_doc (if enabled)
│   ├── ui/                  # Hub UI components (optional)
│   │   └── memory_log_tab.jsx
│   ├── models.py            # Pydantic models for all tools
│   └── security.py          # Path validation, extension checks

logs/                        # NEW: Log directory
├── memory_matrix.log        # Linear log of all memory operations
└── sessions.jsonl           # Session stats (JSON lines format)
```

---

## Implementation Plan

### Phase 1: MCP API Layer (`src/mcp/api.py`)

Create a dedicated FastAPI server that exposes engine functionality to MCP:

```python
"""
Luna MCP API - Internal interface for MCP server
================================================

Runs on port 8001, separate from main API.
Provides clean endpoints for MCP tools to call.

This is an INTERNAL API - not exposed externally.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import asyncio

# Import engine components
from luna.engine import LunaEngine, get_engine

app = FastAPI(title="Luna MCP API", version="1.0.0")


# ==============================================================================
# Models
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


# ==============================================================================
# Endpoints
# ==============================================================================

@app.get("/health")
async def health():
    """MCP API health check."""
    engine = get_engine()
    return {
        "status": "healthy" if engine else "no_engine",
        "api": "mcp",
        "version": "1.0.0"
    }


@app.post("/memory/smart-fetch", response_model=SmartFetchResponse)
async def smart_fetch(request: SmartFetchRequest):
    """
    Smart context retrieval with budget management.
    
    Uses RRF fusion across FTS5 + vector + graph.
    Returns nodes within token budget.
    """
    engine = get_engine()
    if not engine:
        raise HTTPException(503, "Engine not running")
    
    matrix = engine.get_actor("matrix")
    if not matrix or not matrix.is_ready:
        return SmartFetchResponse(nodes=[], budget_used=0, anchor_ids=[])
    
    # Budget mapping
    budgets = {"minimal": 1800, "balanced": 3800, "rich": 7200}
    max_tokens = budgets.get(request.budget_preset, 3800)
    
    # Get context using matrix actor
    context = await matrix.get_context(request.query, max_tokens=max_tokens)
    
    # TODO: Implement proper node-level retrieval
    # For now, return context as single node
    return SmartFetchResponse(
        nodes=[{"type": "CONTEXT", "content": context, "id": "context_0"}],
        budget_used=len(context) // 4,
        anchor_ids=["context_0"]
    )


@app.post("/memory/search", response_model=SearchResponse)
async def search_memory(request: SearchRequest):
    """Search memory matrix."""
    engine = get_engine()
    if not engine:
        raise HTTPException(503, "Engine not running")
    
    matrix = engine.get_actor("matrix")
    if not matrix:
        return SearchResponse(results=[], count=0)
    
    results = await matrix.search(request.query, limit=request.limit)
    return SearchResponse(results=results, count=len(results))


@app.post("/memory/add-node", response_model=AddNodeResponse)
async def add_node(request: AddNodeRequest):
    """Add a memory node."""
    engine = get_engine()
    if not engine:
        raise HTTPException(503, "Engine not running")
    
    matrix = engine.get_actor("matrix")
    if not matrix:
        raise HTTPException(503, "Matrix actor not available")
    
    node_id = await matrix.add_node(
        node_type=request.node_type,
        content=request.content,
        tags=request.tags,
        confidence=request.confidence,
        metadata=request.metadata
    )
    
    return AddNodeResponse(node_id=node_id, success=True)


@app.post("/context/detect", response_model=DetectContextResponse)
async def detect_context(request: DetectContextRequest):
    """
    Process message through Luna's pipeline.
    
    - Routes through state machine
    - Retrieves relevant memories
    - Generates response (if auto_fetch)
    - Returns enriched context
    """
    engine = get_engine()
    if not engine:
        raise HTTPException(503, "Engine not running")
    
    # Send message and get response
    response_future = asyncio.Future()
    
    async def on_response(text: str, data: dict):
        if not response_future.done():
            response_future.set_result((text, data))
    
    engine.on_response(on_response)
    
    try:
        await engine.send_message(request.message)
        text, data = await asyncio.wait_for(response_future, timeout=30.0)
        
        return DetectContextResponse(
            response=text,
            state={
                "model": data.get("model", "unknown"),
                "delegated": data.get("delegated", False),
                "local": data.get("local", False),
            },
            memory_context=[],
            system_prompt=""
        )
    finally:
        if on_response in engine._on_response_callbacks:
            engine._on_response_callbacks.remove(on_response)


@app.get("/state")
async def get_state():
    """Get current Luna state."""
    engine = get_engine()
    if not engine:
        return {"status": "no_engine"}
    
    return engine.status()


@app.get("/consciousness")
async def get_consciousness():
    """Get consciousness state (mood, coherence, attention)."""
    engine = get_engine()
    if not engine:
        raise HTTPException(503, "Engine not running")
    
    return engine.consciousness.get_summary()


# ==============================================================================
# Entity Endpoints (Luna V2 specific)
# ==============================================================================

@app.get("/entities/resolve")
async def resolve_entity(name: str):
    """Resolve an entity by name/alias."""
    engine = get_engine()
    if not engine:
        raise HTTPException(503, "Engine not running")
    
    # TODO: Implement entity resolution
    return {"name": name, "resolved": False, "message": "Entity system not yet wired"}


# ==============================================================================
# Server Runner
# ==============================================================================

def run_mcp_api(port: int = 8001):
    """Run the MCP API server."""
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    run_mcp_api()
```

### Phase 2: MCP Server (`src/mcp/server.py`)

```python
"""
Luna-Hub-MCP-V1 - MCP Server Entry Point
========================================

FastMCP server that bridges Claude Desktop with Luna Engine.
Calls MCP API (port 8001) for all operations.

Activation:
- "hey Luna" → Activate Luna context
- "later Luna" → Deactivate

Setup:
1. Start Luna Engine (python scripts/run.py --server)
2. Start MCP API (python -m mcp.api)
3. Configure Claude Desktop
"""

import os
import sys
from pathlib import Path

# Path setup
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from mcp.server.fastmcp import FastMCP

# Import tool modules
from mcp.tools import filesystem, memory, state, git

# Configuration
MCP_API_URL = os.environ.get("LUNA_MCP_API_URL", "http://localhost:8001")
LUNA_BASE_PATH = os.environ.get("LUNA_BASE_PATH", str(PROJECT_ROOT))

# Initialize MCP server
mcp = FastMCP("Luna-Hub-MCP-V1")


# ==============================================================================
# Register Tools from Modules
# ==============================================================================

# Filesystem tools
mcp.tool(name="luna_read")(filesystem.luna_read)
mcp.tool(name="luna_write")(filesystem.luna_write)
mcp.tool(name="luna_list")(filesystem.luna_list)

# Memory tools
mcp.tool(name="luna_smart_fetch")(memory.luna_smart_fetch)
mcp.tool(name="memory_matrix_search")(memory.memory_matrix_search)
mcp.tool(name="memory_matrix_add_node")(memory.memory_matrix_add_node)
mcp.tool(name="memory_matrix_add_edge")(memory.memory_matrix_add_edge)
mcp.tool(name="memory_matrix_get_context")(memory.memory_matrix_get_context)
mcp.tool(name="memory_matrix_trace")(memory.memory_matrix_trace)

# State tools
mcp.tool(name="luna_detect_context")(state.luna_detect_context)
mcp.tool(name="luna_get_state")(state.luna_get_state)
mcp.tool(name="luna_set_app_context")(state.luna_set_app_context)

# Git tools
mcp.tool(name="luna_git_sync")(git.luna_git_sync)

# Memory storage (structured)
mcp.tool(name="luna_save_memory")(memory.luna_save_memory)


# ==============================================================================
# Entry Point
# ==============================================================================

if __name__ == "__main__":
    mcp.run()
```

### Phase 3: Tool Modules

#### `src/mcp/tools/filesystem.py`

```python
"""Filesystem tools - luna_read, luna_write, luna_list"""

from pathlib import Path
from typing import List
import os

from mcp.models import ReadFileInput, WriteFileInput, ListDirInput
from mcp.security import validate_path, check_extension, LUNA_BASE_PATH


async def luna_read(params: ReadFileInput) -> str:
    """Read a file from the project folder."""
    try:
        full_path = validate_path(params.path)
        if not full_path.exists():
            return f"Error: File not found: {params.path}"
        if not full_path.is_file():
            return f"Error: Not a file: {params.path}"
        check_extension(full_path)
        return full_path.read_text(encoding='utf-8')
    except Exception as e:
        return f"Error: {str(e)}"


async def luna_write(params: WriteFileInput) -> str:
    """Write content to a file in the project folder."""
    try:
        full_path = validate_path(params.path)
        check_extension(full_path)
        if params.create_dirs:
            full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(params.content, encoding='utf-8')
        size = len(params.content.encode('utf-8'))
        return f"✓ Written {size} bytes to {params.path}"
    except Exception as e:
        return f"Error: {str(e)}"


async def luna_list(params: ListDirInput) -> str:
    """List contents of a directory in the project folder."""
    try:
        full_path = validate_path(params.path) if params.path else Path(LUNA_BASE_PATH)
        if not full_path.exists():
            return f"Error: Directory not found: {params.path or '/'}"
        if not full_path.is_dir():
            return f"Error: Not a directory: {params.path}"

        def list_dir(path: Path, prefix: str = "", depth: int = 0) -> List[str]:
            if depth >= params.max_depth:
                return [f"{prefix}..."]
            items = []
            try:
                entries = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            except PermissionError:
                return [f"{prefix}[permission denied]"]

            for i, entry in enumerate(entries):
                is_last = i == len(entries) - 1
                connector = "└── " if is_last else "├── "
                if entry.is_dir():
                    items.append(f"{prefix}{connector}📁 {entry.name}/")
                    if params.recursive:
                        extension = "    " if is_last else "│   "
                        items.extend(list_dir(entry, prefix + extension, depth + 1))
                else:
                    size = entry.stat().st_size
                    size_str = f"{size}B" if size < 1024 else f"{size/1024:.1f}KB"
                    items.append(f"{prefix}{connector}📄 {entry.name} ({size_str})")
            return items

        lines = [f"📁 {params.path or 'Project'}/"]
        lines.extend(list_dir(full_path))
        return "\n".join(lines)
    except Exception as e:
        return f"Error: {str(e)}"
```

#### `src/mcp/tools/memory.py`

```python
"""Memory tools - smart_fetch, search, add_node, etc."""

import httpx
from typing import Optional, List, Dict, Any

from mcp.models import (
    SmartFetchInput, MemorySearchInput, AddNodeInput, 
    AddEdgeInput, GetContextInput, TraceDependenciesInput,
    SaveMemoryInput, MemoryType
)

MCP_API_URL = "http://localhost:8001"


async def _call_api(method: str, path: str, **kwargs) -> dict:
    """Call MCP API."""
    url = f"{MCP_API_URL}{path}"
    timeout = httpx.Timeout(connect=5.0, read=30.0, write=10.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        if method == "GET":
            response = await client.get(url, **kwargs)
        elif method == "POST":
            response = await client.post(url, **kwargs)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()


async def luna_smart_fetch(params: SmartFetchInput) -> str:
    """
    Intelligently fetch relevant context for Luna.
    
    Uses Memory Matrix hybrid search (FTS5 + sqlite-vec + graph)
    within token budget. This is Luna's primary memory access tool.
    """
    try:
        response = await _call_api(
            "POST",
            "/memory/smart-fetch",
            json={"query": params.query, "budget_preset": params.budget_preset}
        )
        
        # Format response
        lines = [
            f"# Context: {params.query}",
            f"*Retrieved {len(response.get('nodes', []))} nodes, {response.get('budget_used', 0)} tokens*",
            ""
        ]
        
        for node in response.get('nodes', []):
            node_type = node.get('type', 'UNKNOWN')
            content = node.get('content', '')[:300]
            lines.append(f"- [{node_type}] {content}")
        
        return "\n".join(lines)
    except Exception as e:
        return f"Error during smart fetch: {str(e)}"


async def memory_matrix_search(params: MemorySearchInput) -> str:
    """Search Luna's memory graph."""
    try:
        response = await _call_api(
            "POST",
            "/memory/search",
            json={"query": params.query, "limit": params.limit}
        )
        
        if not response.get('results'):
            return f"No memories found for: {params.query}"
        
        lines = [f"# Search Results: {params.query}", ""]
        for r in response['results']:
            lines.append(f"- [{r.get('type', '?')}] {r.get('content', '')[:200]}")
        
        return "\n".join(lines)
    except Exception as e:
        return f"Error searching memory: {str(e)}"


async def memory_matrix_add_node(params: AddNodeInput) -> str:
    """Add a memory node to the graph."""
    try:
        response = await _call_api(
            "POST",
            "/memory/add-node",
            json={
                "node_type": params.node_type,
                "content": params.content,
                "tags": params.tags,
                "confidence": params.confidence,
                "metadata": params.metadata
            }
        )
        
        if response.get('success'):
            return f"✓ Added node: {response.get('node_id')}"
        else:
            return f"Failed to add node"
    except Exception as e:
        return f"Error adding node: {str(e)}"


async def memory_matrix_add_edge(params: AddEdgeInput) -> str:
    """Add a relationship between memory nodes."""
    # TODO: Implement via MCP API
    return "Edge creation not yet implemented"


async def memory_matrix_get_context(params: GetContextInput) -> str:
    """Get context around a specific memory node."""
    # TODO: Implement via MCP API
    return "Node context retrieval not yet implemented"


async def memory_matrix_trace(params: TraceDependenciesInput) -> str:
    """Trace dependency paths leading to a memory node."""
    # TODO: Implement via MCP API
    return "Dependency tracing not yet implemented"


async def luna_save_memory(params: SaveMemoryInput) -> str:
    """Save a structured memory entry."""
    try:
        response = await _call_api(
            "POST",
            "/memory/add-node",
            json={
                "node_type": params.memory_type.value.upper(),
                "content": f"# {params.title}\n\n{params.content}",
                "tags": params.tags or [],
                "metadata": params.metadata or {}
            }
        )
        
        if response.get('success'):
            return f"✓ Memory saved: {params.title}"
        else:
            return f"Failed to save memory"
    except Exception as e:
        return f"Error saving memory: {str(e)}"
```

#### `src/mcp/tools/state.py`

```python
"""State tools - detect_context, get_state, set_app_context"""

import httpx
import json

from mcp.models import DetectContextInput, SetAppContextInput

MCP_API_URL = "http://localhost:8001"


async def _call_api(method: str, path: str, **kwargs) -> dict:
    """Call MCP API."""
    url = f"{MCP_API_URL}{path}"
    timeout = httpx.Timeout(connect=5.0, read=30.0, write=10.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        if method == "GET":
            response = await client.get(url, **kwargs)
        elif method == "POST":
            response = await client.post(url, **kwargs)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()


async def luna_detect_context(
    message: str,
    auto_fetch: bool = True,
    budget_preset: str = "balanced"
) -> str:
    """
    Process a message through Luna's full pipeline.
    
    Routes through state machine, retrieves memories, enriches context.
    Returns formatted context for system prompt injection.
    
    Activation: "hey Luna" triggers this
    Deactivation: "later Luna" ends the session
    """
    # Check for activation/deactivation
    message_lower = message.lower().strip()
    
    if message_lower.startswith("later luna"):
        return "Luna session ended. Talk to you later! 💜"
    
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
        
        # Build formatted output
        lines = [
            "# Luna Context",
            "",
            f"**State:** {response.get('state', {})}",
            "",
            "## Response",
            response.get('response', ''),
        ]
        
        return "\n".join(lines)
    except Exception as e:
        return f"Error detecting context: {str(e)}"


async def luna_get_state() -> str:
    """Get Luna's current state without processing a message."""
    try:
        response = await _call_api("GET", "/state")
        return json.dumps(response, indent=2)
    except Exception as e:
        return f"Error getting state: {str(e)}"


async def luna_set_app_context(params: SetAppContextInput) -> str:
    """Manually set Luna's app context."""
    # TODO: Implement via MCP API
    return f"App context set: {params.app} / {params.app_state}"
```

### Phase 4: Models (`src/mcp/models.py`)

```python
"""Pydantic models for MCP tools."""

from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from enum import Enum


# ==============================================================================
# Filesystem Models
# ==============================================================================

class ReadFileInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    path: str = Field(..., min_length=1, max_length=500)


class WriteFileInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    path: str = Field(..., min_length=1, max_length=500)
    content: str
    create_dirs: bool = True


class ListDirInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    path: str = Field(default="", max_length=500)
    recursive: bool = False
    max_depth: int = Field(default=3, ge=1, le=10)


# ==============================================================================
# Memory Models
# ==============================================================================

class SmartFetchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    query: str = Field(..., min_length=1, max_length=1000)
    budget_preset: str = Field(default="balanced")  # minimal, balanced, rich


class MemorySearchInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=10, ge=1, le=100)


class AddNodeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    node_type: str = Field(..., description="FACT, DECISION, PROBLEM, ACTION, etc.")
    content: str = Field(..., min_length=1, max_length=5000)
    tags: Optional[List[str]] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: Optional[Dict[str, Any]] = None


class AddEdgeInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    from_node: str
    to_node: str
    relationship: str  # depends_on, enables, contradicts, clarifies, related_to
    strength: float = Field(default=1.0, ge=0.0, le=1.0)


class GetContextInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    node_id: str
    depth: int = Field(default=2, ge=1, le=3)


class TraceDependenciesInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    node_id: str
    max_depth: int = Field(default=5, ge=1, le=10)


class MemoryType(str, Enum):
    SESSION = "session"
    INSIGHT = "insight"
    CONTEXT = "context"
    ARTIFACT = "artifact"


class SaveMemoryInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    memory_type: MemoryType
    title: str = Field(..., min_length=1, max_length=200)
    content: str
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


# ==============================================================================
# State Models
# ==============================================================================

class DetectContextInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    message: str = Field(..., min_length=1, max_length=5000)
    auto_fetch: bool = True
    budget_preset: str = "balanced"


class SetAppContextInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    app: str
    app_state: str


# ==============================================================================
# Git Models
# ==============================================================================

class GitSyncInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    message: Optional[str] = Field(default=None, max_length=500)
    push: bool = True
```

### Phase 5: Security (`src/mcp/security.py`)

```python
"""Security utilities for MCP - path validation, extension checks."""

import os
from pathlib import Path

# Configuration
LUNA_BASE_PATH = os.environ.get(
    "LUNA_BASE_PATH",
    str(Path(__file__).parent.parent.parent.resolve())
)

ALLOWED_EXTENSIONS = {
    '.md', '.txt', '.json', '.yaml', '.yml',
    '.py', '.js', '.ts', '.jsx', '.tsx',
    '.html', '.css', '.sql', '.toml'
}


def validate_path(relative_path: str) -> Path:
    """
    Validate path is within allowed directory.
    
    Security hardening:
    - Rejects null bytes
    - Rejects absolute paths
    - Rejects traversal attempts
    - Uses Path.is_relative_to() for containment
    """
    if '\x00' in relative_path:
        raise ValueError("Path contains null bytes")
    
    if relative_path.startswith('/') or relative_path.startswith('\\'):
        raise ValueError("Absolute paths not allowed")
    
    if '..' in relative_path:
        raise ValueError("Path traversal not allowed")
    
    base = Path(LUNA_BASE_PATH).resolve()
    full_path = (base / relative_path).resolve()
    
    try:
        full_path.relative_to(base)
    except ValueError:
        raise ValueError("Path escapes base directory")
    
    return full_path


def check_extension(path: Path) -> None:
    """Check if file extension is allowed."""
    if path.suffix.lower() not in ALLOWED_EXTENSIONS and path.suffix != '':
        raise ValueError(
            f"Extension '{path.suffix}' not allowed. "
            f"Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
```

---

## Claude Desktop Configuration

**Location:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "Luna-Hub-MCP-V1": {
      "command": "/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/.venv/bin/python",
      "args": [
        "-m", "mcp.server"
      ],
      "cwd": "/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src",
      "env": {
        "LUNA_BASE_PATH": "/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root",
        "LUNA_MCP_API_URL": "http://localhost:8001"
      }
    }
  }
}
```

**Note:** Remove the old `Luna-v2` entry that points to Eclissi.

---

## Port Allocation

| Service | Port | Notes |
|---------|------|-------|
| Luna V2 Main API | 8000 | Engine, voice, UI |
| Luna MCP API | 8001 | MCP tools only |
| Eclissi Hub (legacy) | 8882 | Can run in parallel |

**No conflicts detected** with common dev ports (3000, 5000, etc.)

---

## Auto-Launch on "hey Luna"

The MCP server should **auto-launch the MCP API** when "hey Luna" is detected, handling port conflicts gracefully.

### Implementation: `src/mcp/launcher.py`

```python
"""
Auto-launcher for Luna MCP API
==============================

Starts the MCP API server on demand, with:
- Port conflict detection
- Automatic port fallback (8001 → 8002 → 8003)
- Health check before returning
- Graceful shutdown on MCP exit
"""

import asyncio
import subprocess
import sys
import socket
import time
import atexit
from pathlib import Path
from typing import Optional
import httpx

# Configuration
DEFAULT_PORT = 8001
MAX_PORT_ATTEMPTS = 5
HEALTH_CHECK_TIMEOUT = 10.0
HEALTH_CHECK_INTERVAL = 0.3

# Global state
_api_process: Optional[subprocess.Popen] = None
_api_port: Optional[int] = None


def is_port_available(port: int) -> bool:
    """Check if a port is available."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('127.0.0.1', port))
            return True
        except OSError:
            return False


def find_available_port(start_port: int = DEFAULT_PORT, max_attempts: int = MAX_PORT_ATTEMPTS) -> int:
    """Find an available port starting from start_port."""
    for i in range(max_attempts):
        port = start_port + i
        if is_port_available(port):
            return port
    raise RuntimeError(f"No available port found in range {start_port}-{start_port + max_attempts - 1}")


async def check_api_health(port: int, timeout: float = HEALTH_CHECK_TIMEOUT) -> bool:
    """Check if MCP API is healthy."""
    url = f"http://127.0.0.1:{port}/health"
    start_time = time.time()
    
    async with httpx.AsyncClient() as client:
        while time.time() - start_time < timeout:
            try:
                response = await client.get(url, timeout=1.0)
                if response.status_code == 200:
                    return True
            except (httpx.ConnectError, httpx.TimeoutException):
                pass
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
    
    return False


def start_api_server(port: int) -> subprocess.Popen:
    """Start the MCP API server as a subprocess."""
    src_path = Path(__file__).parent.parent.resolve()
    
    process = subprocess.Popen(
        [sys.executable, "-m", "mcp.api", "--port", str(port)],
        cwd=str(src_path),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        # Don't inherit parent's stdin to avoid blocking
        stdin=subprocess.DEVNULL,
    )
    
    return process


def stop_api_server():
    """Stop the MCP API server."""
    global _api_process
    if _api_process and _api_process.poll() is None:
        _api_process.terminate()
        try:
            _api_process.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            _api_process.kill()
        _api_process = None


# Register cleanup on exit
atexit.register(stop_api_server)


async def ensure_api_running() -> int:
    """
    Ensure MCP API is running, starting it if necessary.
    
    Returns the port the API is running on.
    """
    global _api_process, _api_port
    
    # Check if already running (our process)
    if _api_process and _api_process.poll() is None:
        if _api_port and await check_api_health(_api_port, timeout=2.0):
            return _api_port
    
    # Check if already running (external process)
    for port in range(DEFAULT_PORT, DEFAULT_PORT + MAX_PORT_ATTEMPTS):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"http://127.0.0.1:{port}/health", timeout=1.0)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("api") == "mcp":
                        _api_port = port
                        return port
        except (httpx.ConnectError, httpx.TimeoutException):
            pass
    
    # Start new server
    port = find_available_port()
    _api_process = start_api_server(port)
    
    # Wait for health check
    if await check_api_health(port):
        _api_port = port
        return port
    else:
        stop_api_server()
        raise RuntimeError(f"MCP API failed to start on port {port}")


def get_api_url() -> str:
    """Get the MCP API URL, ensuring it's running."""
    if _api_port:
        return f"http://127.0.0.1:{_api_port}"
    return f"http://127.0.0.1:{DEFAULT_PORT}"
```

### Update `src/mcp/tools/state.py` to use auto-launch

```python
"""State tools - detect_context, get_state, set_app_context"""

import httpx
import json
import re

from mcp.launcher import ensure_api_running, get_api_url


async def _call_api(method: str, path: str, **kwargs) -> dict:
    """Call MCP API, auto-launching if needed."""
    # Ensure API is running
    await ensure_api_running()
    
    url = f"{get_api_url()}{path}"
    timeout = httpx.Timeout(connect=5.0, read=30.0, write=10.0)
    
    async with httpx.AsyncClient(timeout=timeout) as client:
        if method == "GET":
            response = await client.get(url, **kwargs)
        elif method == "POST":
            response = await client.post(url, **kwargs)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()


async def luna_detect_context(
    message: str,
    auto_fetch: bool = True,
    budget_preset: str = "balanced"
) -> str:
    """
    Process a message through Luna's full pipeline.
    
    AUTO-LAUNCH: If MCP API isn't running, starts it automatically.
    
    Activation: "hey Luna" triggers this and launches API if needed
    Deactivation: "later Luna" ends the session
    """
    message_lower = message.lower().strip()
    
    # Check for "hey Luna" activation
    if re.match(r'^hey\s+luna\b', message_lower, re.IGNORECASE):
        # This will auto-launch the API if not running
        try:
            port = await ensure_api_running()
            activation_msg = f"Luna activated! (MCP API on port {port})"
        except Exception as e:
            return f"Error starting Luna: {str(e)}"
    
    # Check for deactivation
    if re.match(r'^later\s+luna\b', message_lower, re.IGNORECASE):
        return "Luna session ended. Talk to you later! 💜"
    
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
        
        lines = [
            "# Luna Context",
            "",
            f"**State:** {response.get('state', {})}",
            "",
            "## Response",
            response.get('response', ''),
        ]
        
        return "\n".join(lines)
    except Exception as e:
        return f"Error detecting context: {str(e)}"


# ... rest of state.py unchanged
```

### Update `src/mcp/api.py` to accept port argument

Add to the bottom of `api.py`:

```python
def run_mcp_api(port: int = 8001):
    """Run the MCP API server."""
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    run_mcp_api(port=args.port)
```

---

## Startup Sequence

### Automatic (Recommended)

When you say **"hey Luna"** in Claude Desktop:

1. MCP server calls `luna_detect_context`
2. `luna_detect_context` calls `ensure_api_running()`
3. Launcher checks if API is already running on 8001-8005
4. If not, finds available port and starts API subprocess
5. Waits for health check (up to 10s)
6. Returns Luna's response

**No manual startup required!**

### Manual (Development/Debugging)

```bash
# Terminal 1: Start Luna Engine (optional - for full features)
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python scripts/run.py --server --port 8000

# Terminal 2: Start MCP API manually (optional)
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python -m mcp.api --port 8001

# MCP server is auto-spawned by Claude Desktop
```

### Unified Launcher (All Services)

Create `scripts/start_all.sh`:
```bash
#!/bin/bash
# Start all Luna services

cd "$(dirname "$0")/.."

# Start engine in background
python scripts/run.py --server --port 8000 &
ENGINE_PID=$!

# Start MCP API in background  
python -m mcp.api --port 8001 &
MCP_API_PID=$!

echo "Luna Engine: $ENGINE_PID (port 8000)"
echo "MCP API: $MCP_API_PID (port 8001)"

# Wait for both
wait
```

---

## Systems Covered (Per Bible)

| System | Status | Tool/Endpoint |
|--------|--------|---------------|
| **Memory Matrix** (Layer 0) | ✅ | `luna_smart_fetch`, `memory_matrix_*` |
| **Director Actor** (Layer 1.5) | ✅ | `luna_detect_context` (via engine) |
| **Matrix Actor** (Layer 1.5) | ✅ | All memory tools |
| **Scribe (Ben)** (Layer 1) | 🔲 | Automatic via engine |
| **Librarian (Dude)** (Layer 1) | 🔲 | Automatic via engine |
| **Oven Actor** (Layer 1.5) | ✅ | Delegation via engine |
| **Entity System** | 🔲 | Future: `luna_resolve_entity` |
| **Voice Actor** | N/A | Separate interface |
| **Consciousness** | ✅ | `/consciousness` endpoint |
| **State Machine** | ✅ | `luna_get_state` |

---

## Activation/Deactivation

### "hey Luna" Activation

Detection happens in `luna_detect_context`:
- Auto-launches MCP API if not running (via `launcher.py`)
- Activates Luna context
- Triggers memory retrieval
- Returns response with personality

### "later Luna" Deactivation

On deactivation, the system:
1. **Checks pending memories** - ensures all extracted memories are logged
2. **Writes session summary** - to memory log file
3. **Closes MCP API port** - clean shutdown
4. **Reports any errors** - memory conflicts printed in chat

If there are memory conflicts or logging failures, the error is returned in the chat response instead of a farewell.

---

## Memory Logging System

### Log File: `logs/memory_matrix.log`

Simple linear format tracking all Memory Matrix additions:

```
# Luna Memory Matrix Log
# Format: [TIMESTAMP] [ACTION] [NODE_TYPE] [NODE_ID] content_preview...

[2026-01-27T10:15:32] [ADD] [FACT] node_abc123 "Ahab prefers dark roast coffee"
[2026-01-27T10:15:33] [ADD] [DECISION] node_def456 "Using sqlite-vec instead of FAISS"
[2026-01-27T10:15:34] [EDGE] [RELATED_TO] node_abc123 -> node_xyz789 (strength=0.8)
[2026-01-27T10:16:00] [SESSION_END] session_001 nodes_added=5 edges_added=3 errors=0
```

### Implementation: `src/mcp/memory_log.py`

```python
"""
Memory Matrix Logger
====================

Simple linear log of all Memory Matrix operations.
Provides audit trail and debugging for memory system.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import fcntl

# Configuration
LOGS_DIR = Path(os.environ.get(
    "LUNA_LOGS_DIR",
    Path(__file__).parent.parent.parent / "logs"
))
MEMORY_LOG_FILE = LOGS_DIR / "memory_matrix.log"
SESSION_LOG_FILE = LOGS_DIR / "sessions.jsonl"


class LogAction(str, Enum):
    ADD = "ADD"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    EDGE = "EDGE"
    SESSION_START = "SESSION_START"
    SESSION_END = "SESSION_END"
    ERROR = "ERROR"
    CONFLICT = "CONFLICT"


@dataclass
class MemoryLogEntry:
    timestamp: str
    action: LogAction
    node_type: Optional[str] = None
    node_id: Optional[str] = None
    content_preview: Optional[str] = None
    edge_from: Optional[str] = None
    edge_to: Optional[str] = None
    edge_type: Optional[str] = None
    strength: Optional[float] = None
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class MemoryLogger:
    """Thread-safe memory logger."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._file_lock = threading.Lock()
        self._session_id: Optional[str] = None
        self._session_stats = {
            "nodes_added": 0,
            "edges_added": 0,
            "errors": 0,
            "conflicts": 0
        }
        
        # Ensure logs directory exists
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        
        # Write header if new file
        if not MEMORY_LOG_FILE.exists():
            self._write_header()
        
        self._initialized = True
    
    def _write_header(self):
        """Write log file header."""
        header = """# Luna Memory Matrix Log
# Format: [TIMESTAMP] [ACTION] [NODE_TYPE] [NODE_ID] content_preview...
# ========================================================================

"""
        with open(MEMORY_LOG_FILE, 'w') as f:
            f.write(header)
    
    def _format_entry(self, entry: MemoryLogEntry) -> str:
        """Format a log entry as a single line."""
        ts = entry.timestamp
        action = entry.action.value
        
        if entry.action == LogAction.EDGE:
            return f"[{ts}] [{action}] [{entry.edge_type}] {entry.edge_from} -> {entry.edge_to} (strength={entry.strength})\n"
        
        elif entry.action in (LogAction.SESSION_START, LogAction.SESSION_END):
            if entry.metadata:
                meta_str = " ".join(f"{k}={v}" for k, v in entry.metadata.items())
                return f"[{ts}] [{action}] {entry.session_id} {meta_str}\n"
            return f"[{ts}] [{action}] {entry.session_id}\n"
        
        elif entry.action in (LogAction.ERROR, LogAction.CONFLICT):
            return f"[{ts}] [{action}] {entry.error}\n"
        
        else:
            # ADD, UPDATE, DELETE
            preview = (entry.content_preview or "")[:80].replace("\n", " ")
            return f"[{ts}] [{action}] [{entry.node_type}] {entry.node_id} \"{preview}\"\n"
    
    def _write(self, entry: MemoryLogEntry):
        """Write entry to log file (thread-safe)."""
        line = self._format_entry(entry)
        
        with self._file_lock:
            with open(MEMORY_LOG_FILE, 'a') as f:
                # File locking for multi-process safety
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(line)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    
    def start_session(self, session_id: str):
        """Mark session start."""
        self._session_id = session_id
        self._session_stats = {
            "nodes_added": 0,
            "edges_added": 0,
            "errors": 0,
            "conflicts": 0
        }
        
        self._write(MemoryLogEntry(
            timestamp=datetime.now().isoformat(),
            action=LogAction.SESSION_START,
            session_id=session_id
        ))
    
    def log_node(self, action: LogAction, node_type: str, node_id: str, content: str):
        """Log a node operation."""
        self._write(MemoryLogEntry(
            timestamp=datetime.now().isoformat(),
            action=action,
            node_type=node_type,
            node_id=node_id,
            content_preview=content[:100] if content else None
        ))
        
        if action == LogAction.ADD:
            self._session_stats["nodes_added"] += 1
    
    def log_edge(self, from_node: str, to_node: str, edge_type: str, strength: float = 1.0):
        """Log an edge operation."""
        self._write(MemoryLogEntry(
            timestamp=datetime.now().isoformat(),
            action=LogAction.EDGE,
            edge_from=from_node,
            edge_to=to_node,
            edge_type=edge_type,
            strength=strength
        ))
        
        self._session_stats["edges_added"] += 1
    
    def log_error(self, error: str):
        """Log an error."""
        self._write(MemoryLogEntry(
            timestamp=datetime.now().isoformat(),
            action=LogAction.ERROR,
            error=error
        ))
        
        self._session_stats["errors"] += 1
    
    def log_conflict(self, conflict: str):
        """Log a memory conflict."""
        self._write(MemoryLogEntry(
            timestamp=datetime.now().isoformat(),
            action=LogAction.CONFLICT,
            error=conflict
        ))
        
        self._session_stats["conflicts"] += 1
    
    def end_session(self) -> Dict[str, Any]:
        """
        End session and return stats.
        
        Returns dict with nodes_added, edges_added, errors, conflicts.
        """
        stats = self._session_stats.copy()
        
        self._write(MemoryLogEntry(
            timestamp=datetime.now().isoformat(),
            action=LogAction.SESSION_END,
            session_id=self._session_id,
            metadata=stats
        ))
        
        # Also write to sessions JSONL for structured access
        session_record = {
            "session_id": self._session_id,
            "ended_at": datetime.now().isoformat(),
            **stats
        }
        with open(SESSION_LOG_FILE, 'a') as f:
            f.write(json.dumps(session_record) + "\n")
        
        self._session_id = None
        return stats
    
    def get_recent_entries(self, n: int = 50) -> List[str]:
        """Get the last N log entries."""
        if not MEMORY_LOG_FILE.exists():
            return []
        
        with open(MEMORY_LOG_FILE, 'r') as f:
            lines = f.readlines()
        
        # Skip header lines (starting with #)
        entries = [l.strip() for l in lines if l.strip() and not l.startswith('#')]
        return entries[-n:]
    
    def get_session_stats(self) -> Dict[str, Any]:
        """Get current session stats."""
        return {
            "session_id": self._session_id,
            "active": self._session_id is not None,
            **self._session_stats
        }


# Global instance
memory_logger = MemoryLogger()
```

### MCP API Endpoints for Memory Log

Add to `src/mcp/api.py`:

```python
from mcp.memory_log import memory_logger, MEMORY_LOG_FILE


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


@app.get("/session/stats")
async def get_session_stats():
    """Get current session statistics."""
    return memory_logger.get_session_stats()
```

### Updated "later Luna" Handler

Update `src/mcp/tools/state.py`:

```python
async def luna_detect_context(
    message: str,
    auto_fetch: bool = True,
    budget_preset: str = "balanced"
) -> str:
    """
    Process a message through Luna's full pipeline.
    
    AUTO-LAUNCH: If MCP API isn't running, starts it automatically.
    
    Activation: "hey Luna" triggers this and launches API if needed
    Deactivation: "later Luna" - checks memories, logs session, closes port
    """
    message_lower = message.lower().strip()
    
    # Check for "hey Luna" activation
    if re.match(r'^hey\s+luna\b', message_lower, re.IGNORECASE):
        try:
            port = await ensure_api_running()
            
            # Start session logging
            session_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            await _call_api("POST", "/session/start", json={"session_id": session_id})
            
            return f"Hey! Luna's here. 💜 (API on port {port})"
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
        
        return response.get('response', '')
    except Exception as e:
        return f"Error: {str(e)}"


async def _handle_deactivation() -> str:
    """
    Handle "later Luna" deactivation:
    1. Check pending memories are logged
    2. Write session summary
    3. Close MCP API port
    4. Return errors if any conflicts
    """
    from mcp.launcher import stop_api_server, get_api_url
    
    errors = []
    
    try:
        # Step 1: Flush any pending memory operations
        try:
            flush_response = await _call_api("POST", "/memory/flush", timeout=10.0)
            if flush_response.get("pending", 0) > 0:
                errors.append(f"Warning: {flush_response['pending']} memories still pending")
        except Exception as e:
            errors.append(f"Memory flush error: {str(e)}")
        
        # Step 2: End session and get stats
        try:
            stats = await _call_api("POST", "/session/end")
            session_summary = (
                f"Session complete: "
                f"{stats.get('nodes_added', 0)} memories added, "
                f"{stats.get('edges_added', 0)} connections made"
            )
            
            # Check for conflicts
            if stats.get("conflicts", 0) > 0:
                errors.append(f"⚠️ {stats['conflicts']} memory conflicts detected")
            
            if stats.get("errors", 0) > 0:
                errors.append(f"⚠️ {stats['errors']} errors during session")
                
        except Exception as e:
            errors.append(f"Session end error: {str(e)}")
            session_summary = "Session ended (stats unavailable)"
        
        # Step 3: Stop the API server
        try:
            stop_api_server()
        except Exception as e:
            errors.append(f"Shutdown warning: {str(e)}")
        
        # Step 4: Build response
        if errors:
            error_block = "\n".join(f"  • {e}" for e in errors)
            return (
                f"⚠️ Luna signing off with issues:\n\n"
                f"{error_block}\n\n"
                f"{session_summary}\n\n"
                f"Check `logs/memory_matrix.log` for details."
            )
        else:
            return f"Later! 💜\n\n{session_summary}"
            
    except Exception as e:
        # Critical failure - still try to shutdown
        try:
            stop_api_server()
        except:
            pass
        return f"❌ Error during shutdown: {str(e)}\n\nMCP API may still be running."
```

### Session Management Endpoints

Add to `src/mcp/api.py`:

```python
@app.post("/session/start")
async def start_session(request: dict):
    """Start a new session."""
    session_id = request.get("session_id", f"session_{int(time.time())}")
    memory_logger.start_session(session_id)
    return {"session_id": session_id, "status": "started"}


@app.post("/session/end")
async def end_session():
    """End current session and return stats."""
    stats = memory_logger.end_session()
    return stats


@app.post("/memory/flush")
async def flush_memories():
    """
    Flush any pending memory operations.
    
    Ensures all queued extractions are written to Memory Matrix.
    """
    engine = get_engine()
    if not engine:
        return {"pending": 0, "flushed": 0}
    
    # Get Scribe actor and flush pending extractions
    scribe = engine.get_actor("scribe")
    if scribe:
        pending = await scribe.flush_pending()
        return {"pending": 0, "flushed": pending}
    
    return {"pending": 0, "flushed": 0}
```

---

## Luna Hub UI: Memory Log Tab

### Add to Hub UI (if web-based)

Create `src/mcp/ui/memory_log_tab.html` or React component:

```jsx
// MemoryLogTab.jsx - For Luna Hub UI
import React, { useState, useEffect } from 'react';

const MemoryLogTab = () => {
  const [entries, setEntries] = useState([]);
  const [stats, setStats] = useState({});
  const [autoRefresh, setAutoRefresh] = useState(true);

  const fetchLog = async () => {
    try {
      const response = await fetch('http://localhost:8001/memory/log?limit=100');
      const data = await response.json();
      setEntries(data.entries);
    } catch (error) {
      console.error('Failed to fetch memory log:', error);
    }
  };

  const fetchStats = async () => {
    try {
      const response = await fetch('http://localhost:8001/session/stats');
      const data = await response.json();
      setStats(data);
    } catch (error) {
      console.error('Failed to fetch session stats:', error);
    }
  };

  useEffect(() => {
    fetchLog();
    fetchStats();
    
    if (autoRefresh) {
      const interval = setInterval(() => {
        fetchLog();
        fetchStats();
      }, 5000);
      return () => clearInterval(interval);
    }
  }, [autoRefresh]);

  const getActionColor = (entry) => {
    if (entry.includes('[ADD]')) return 'text-green-400';
    if (entry.includes('[EDGE]')) return 'text-blue-400';
    if (entry.includes('[ERROR]')) return 'text-red-400';
    if (entry.includes('[CONFLICT]')) return 'text-yellow-400';
    if (entry.includes('[SESSION')) return 'text-purple-400';
    return 'text-gray-300';
  };

  return (
    <div className="p-4 bg-gray-900 text-white h-full overflow-hidden flex flex-col">
      {/* Header */}
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold text-purple-400">Memory Matrix Log</h2>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
              className="rounded"
            />
            Auto-refresh
          </label>
          <button
            onClick={() => { fetchLog(); fetchStats(); }}
            className="px-3 py-1 bg-purple-600 rounded hover:bg-purple-500"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Stats Bar */}
      {stats.active && (
        <div className="flex gap-4 mb-4 p-2 bg-gray-800 rounded text-sm">
          <span className="text-purple-400">Session: {stats.session_id}</span>
          <span className="text-green-400">+{stats.nodes_added} nodes</span>
          <span className="text-blue-400">+{stats.edges_added} edges</span>
          {stats.errors > 0 && (
            <span className="text-red-400">⚠️ {stats.errors} errors</span>
          )}
          {stats.conflicts > 0 && (
            <span className="text-yellow-400">⚠️ {stats.conflicts} conflicts</span>
          )}
        </div>
      )}

      {/* Log Entries */}
      <div className="flex-1 overflow-y-auto font-mono text-sm bg-gray-950 rounded p-2">
        {entries.length === 0 ? (
          <p className="text-gray-500 italic">No log entries yet</p>
        ) : (
          entries.map((entry, i) => (
            <div key={i} className={`py-0.5 ${getActionColor(entry)}`}>
              {entry}
            </div>
          ))
        )}
      </div>

      {/* Footer */}
      <div className="mt-2 text-xs text-gray-500">
        Log file: logs/memory_matrix.log
      </div>
    </div>
  );
};

export default MemoryLogTab;
```

### CLI Access

```bash
# View recent memory log
tail -50 /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/logs/memory_matrix.log

# Follow live
tail -f /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/logs/memory_matrix.log

# Via MCP API
curl http://localhost:8001/memory/log?limit=20 | jq '.entries[]'
```

---

## Validation Checklist

### Core MCP
- [ ] `src/mcp/__init__.py` exists
- [ ] `src/mcp/server.py` runs with `python -m mcp.server`
- [ ] `src/mcp/api.py` starts on port 8001
- [ ] `src/mcp/launcher.py` handles auto-launch
- [ ] Claude Desktop config updated
- [ ] Old `Luna-v2` MCP removed from config

### Tools
- [ ] `luna_read` works
- [ ] `luna_smart_fetch` returns context
- [ ] `luna_detect_context` processes messages

### Activation/Deactivation
- [ ] "hey Luna" auto-launches MCP API
- [ ] "hey Luna" starts session logging
- [ ] "later Luna" flushes pending memories
- [ ] "later Luna" writes session summary to log
- [ ] "later Luna" closes MCP API port
- [ ] Memory conflicts print in chat on "later Luna"

### Memory Logging
- [ ] `logs/memory_matrix.log` created on first write
- [ ] Log format: `[TIMESTAMP] [ACTION] [TYPE] [ID] preview...`
- [ ] `sessions.jsonl` tracks session stats
- [ ] `/memory/log` endpoint returns recent entries
- [ ] `/session/stats` endpoint returns current stats

### Hub UI (if applicable)
- [ ] Memory Log tab accessible
- [ ] Shows real-time entries
- [ ] Shows session stats
- [ ] Color-coded by action type

---

## Dependencies

Add to `pyproject.toml`:

```toml
[project.optional-dependencies]
mcp = [
    "mcp>=0.1.0",
    "httpx>=0.25.0",
    "fastapi>=0.104.0",
    "uvicorn>=0.24.0",
]
```

Install:
```bash
uv pip install -e ".[mcp]"
```

---

## Notes

1. **Modularity:** Each tool domain is a separate file
2. **Testability:** MCP API can be tested independently
3. **Separation:** MCP concerns isolated from main API
4. **Evolution:** Can version MCP API separately
5. **Bible Alignment:** Follows Layer model (Layer 2 interface)
