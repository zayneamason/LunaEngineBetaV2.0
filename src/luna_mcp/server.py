"""
Luna-Hub-MCP-V1 — MCP Server Entry Point
========================================

FastMCP server that bridges Claude Desktop with Luna Engine.
Calls MCP API (port 8001) for all operations.

Activation:
- "hey Luna" → Activate Luna context, auto-launch MCP API
- "later Luna" → Deactivate, flush memories, close port

Setup:
1. Configure Claude Desktop (see README)
2. Say "hey Luna" in Claude Desktop to activate

Usage:
    python -m luna_mcp.server

Or in Claude Desktop config:
    {
      "mcpServers": {
        "Luna-Hub-MCP-V1": {
          "command": "/path/to/.venv/bin/python",
          "args": ["-m", "luna_mcp.server"],
          "cwd": "/path/to/project/src"
        }
      }
    }
"""

import os
import sys
from pathlib import Path
from typing import Optional, List

# Path setup
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# Set environment variables before imports
os.environ.setdefault("LUNA_BASE_PATH", str(PROJECT_ROOT))
os.environ.setdefault("LUNA_MCP_API_URL", "http://localhost:8742")

from mcp.server.fastmcp import FastMCP

# Import tool modules
from luna_mcp.tools import filesystem, memory, state, git

# Import auto-session functions
from luna_mcp.tools.memory import (
    ensure_auto_session,
    auto_record_turn,
    get_auto_session_status,
    _end_auto_session
)

# Configuration
MCP_API_URL = os.environ.get("LUNA_MCP_API_URL", "http://localhost:8742")
LUNA_BASE_PATH = os.environ.get("LUNA_BASE_PATH", str(PROJECT_ROOT))

# Initialize MCP server
mcp = FastMCP("Luna-Hub-MCP-V1")


# ==============================================================================
# Filesystem Tools
# ==============================================================================

@mcp.tool()
async def luna_read(path: str) -> str:
    """
    Read a file from Luna's project folder.

    Args:
        path: Relative path to file (e.g., "src/luna/engine.py")

    Returns:
        File contents or error message
    """
    return await filesystem.luna_read(path)


@mcp.tool()
async def luna_write(path: str, content: str, create_dirs: bool = True) -> str:
    """
    Write content to a file in Luna's project folder.

    Args:
        path: Relative path to file
        content: Content to write
        create_dirs: Create parent directories if needed (default: True)

    Returns:
        Success message or error
    """
    return await filesystem.luna_write(path, content, create_dirs)


@mcp.tool()
async def luna_list(path: str = "", recursive: bool = False, max_depth: int = 3) -> str:
    """
    List contents of a directory in Luna's project.

    Args:
        path: Relative path to directory (empty for project root)
        recursive: Recursively list subdirectories
        max_depth: Maximum depth for recursive listing (1-10)

    Returns:
        Formatted directory listing
    """
    return await filesystem.luna_list(path, recursive, max_depth)


# ==============================================================================
# Memory Tools
# ==============================================================================

@mcp.tool()
async def luna_smart_fetch(query: str, budget_preset: str = "balanced") -> str:
    """
    Intelligently fetch relevant context from Luna's memory.

    Uses Memory Matrix hybrid search (FTS5 + vectors + graph).
    This is Luna's primary memory access tool.

    AUTO-SESSION: Automatically records query as conversation context.

    Args:
        query: What to search for
        budget_preset: Token budget - "minimal" (1800), "balanced" (3800), "rich" (7200)

    Returns:
        Formatted context with relevant memories
    """
    # Ensure auto-session and record query as user context
    await ensure_auto_session()
    await auto_record_turn("user", f"[Memory Query] {query}")

    result = await memory.luna_smart_fetch(query, budget_preset)

    # Record summary of what was retrieved
    lines = result.split('\n')
    summary = lines[1] if len(lines) > 1 else "Memory fetch completed"
    await auto_record_turn("assistant", f"[Memory Response] {summary}")

    return result


@mcp.tool()
async def memory_matrix_search(query: str, limit: int = 10) -> str:
    """
    Search Luna's memory graph directly.

    AUTO-SESSION: Automatically records search as conversation context.

    Args:
        query: Search query
        limit: Maximum results (1-100)

    Returns:
        Formatted search results
    """
    # Ensure auto-session and record search
    await ensure_auto_session()
    await auto_record_turn("user", f"[Memory Search] {query}")

    result = await memory.memory_matrix_search(query, limit)

    return result


@mcp.tool()
async def memory_matrix_add_node(
    node_type: str,
    content: str,
    tags: Optional[List[str]] = None,
    confidence: float = 1.0
) -> str:
    """
    Add a memory node to Luna's graph.

    Args:
        node_type: Type - FACT, DECISION, PROBLEM, ACTION, INSIGHT, QUESTION, etc.
        content: Memory content
        tags: Optional tags for categorization
        confidence: Confidence score (0.0-1.0)

    Returns:
        Success message with node ID
    """
    return await memory.memory_matrix_add_node(node_type, content, tags, confidence)


@mcp.tool()
async def memory_matrix_add_edge(
    from_node: str,
    to_node: str,
    relationship: str,
    strength: float = 1.0
) -> str:
    """
    Add a relationship between memory nodes.

    Args:
        from_node: Source node ID
        to_node: Target node ID
        relationship: Type - depends_on, enables, contradicts, clarifies, related_to
        strength: Relationship strength (0.0-1.0)

    Returns:
        Success message or error
    """
    return await memory.memory_matrix_add_edge(from_node, to_node, relationship, strength)


@mcp.tool()
async def memory_matrix_get_context(node_id: str, depth: int = 2) -> str:
    """
    Get context around a specific memory node.

    Args:
        node_id: Node ID to get context for
        depth: Depth of context traversal (1-3)

    Returns:
        Formatted context graph
    """
    return await memory.memory_matrix_get_context(node_id, depth)


@mcp.tool()
async def memory_matrix_trace(node_id: str, max_depth: int = 5) -> str:
    """
    Trace dependency paths to a memory node.

    Args:
        node_id: Node ID to trace
        max_depth: Maximum trace depth (1-10)

    Returns:
        Formatted dependency trace
    """
    return await memory.memory_matrix_trace(node_id, max_depth)


@mcp.tool()
async def luna_save_memory(
    memory_type: str,
    title: str,
    content: str,
    tags: Optional[List[str]] = None
) -> str:
    """
    Save a structured memory entry.

    Args:
        memory_type: Type - "session", "insight", "context", "artifact"
        title: Memory title
        content: Memory content
        tags: Optional tags

    Returns:
        Success message
    """
    return await memory.luna_save_memory(memory_type, title, content, tags)


# ==============================================================================
# Session & Conversation Recording Tools
# ==============================================================================

@mcp.tool()
async def luna_start_session(app_context: str = "mcp") -> str:
    """
    Start a new conversation session for memory recording.

    IMPORTANT: Call this at the beginning of a conversation to enable
    memory recording. Without a session, conversations are NOT persisted.

    Args:
        app_context: Application context (default: "mcp")

    Returns:
        Session ID for tracking, or error message
    """
    return await memory.luna_start_session(app_context)


@mcp.tool()
async def luna_record_turn(
    role: str,
    content: str,
    session_id: Optional[str] = None
) -> str:
    """
    Record a conversation turn to Luna's memory.

    Call this for each user message and Luna response.

    Args:
        role: "user" or "assistant"
        content: The message content
        session_id: Optional session ID (uses current if None)

    Returns:
        Confirmation with turn ID
    """
    return await memory.luna_record_turn(role, content, session_id)


@mcp.tool()
async def luna_end_session(session_id: Optional[str] = None) -> str:
    """
    End conversation session and trigger memory extraction.

    Call this when conversation ends (e.g., "later Luna").
    This triggers Ben the Scribe to extract memories from the conversation.

    Args:
        session_id: Session to end (uses current if None)

    Returns:
        Confirmation with extraction status
    """
    return await memory.luna_end_session(session_id)


@mcp.tool()
async def luna_get_current_session() -> str:
    """
    Get the current active session ID.

    Returns:
        Current session ID or message if no session active
    """
    return await memory.luna_get_current_session()


@mcp.tool()
async def luna_auto_session_status() -> str:
    """
    Get the status of automatic session recording.

    Auto-sessions start automatically when you use Luna tools.
    They end after 5 minutes of inactivity.

    Returns:
        JSON formatted auto-session status
    """
    import json
    status = await get_auto_session_status()
    return json.dumps(status, indent=2, default=str)


@mcp.tool()
async def luna_flush_session() -> str:
    """
    Manually flush the current auto-session and trigger extraction.

    Use this when you want to ensure the current conversation is
    saved without waiting for the inactivity timeout.

    Returns:
        Confirmation message
    """
    await _end_auto_session()
    return "✓ Auto-session flushed and extraction triggered"


# ==============================================================================
# State Tools
# ==============================================================================

@mcp.tool()
async def luna_detect_context(
    message: str,
    auto_fetch: bool = True,
    budget_preset: str = "balanced"
) -> str:
    """
    Process a message through Luna's full pipeline.

    AUTO-LAUNCH: Starts MCP API if not running.
    AUTO-SESSION: Automatically records conversation turns.

    Special messages:
    - "hey Luna" → Activates Luna and launches API
    - "later Luna" → Deactivates, saves session, closes API

    Args:
        message: Message to process
        auto_fetch: Automatically fetch relevant memories
        budget_preset: Token budget preset

    Returns:
        Luna's response with context
    """
    # Ensure auto-session is active and record user message
    await ensure_auto_session()
    await auto_record_turn("user", message)

    # Process through pipeline
    result = await state.luna_detect_context(message, auto_fetch, budget_preset)

    # Record response (truncated for storage)
    response_summary = result[:500] if len(result) > 500 else result
    await auto_record_turn("assistant", response_summary)

    # Check for deactivation trigger ("later Luna")
    if "later luna" in message.lower():
        await _end_auto_session()

    return result


@mcp.tool()
async def luna_get_state() -> str:
    """
    Get Luna's current state without processing a message.

    Returns:
        JSON formatted state information
    """
    return await state.luna_get_state()


@mcp.tool()
async def luna_set_app_context(app: str, app_state: str) -> str:
    """
    Manually set Luna's app context.

    Args:
        app: Application name (e.g., "code_editor", "browser")
        app_state: Application state description

    Returns:
        Confirmation message
    """
    return await state.luna_set_app_context(app, app_state)


# ==============================================================================
# Git Tools
# ==============================================================================

@mcp.tool()
async def luna_git_sync(message: Optional[str] = None, push: bool = True) -> str:
    """
    Sync Luna project changes with Git.

    Stages all changes, commits, and optionally pushes.

    Args:
        message: Commit message (auto-generates if not provided)
        push: Push to remote after commit (default: True)

    Returns:
        Status message
    """
    return await git.luna_git_sync(message, push)


@mcp.tool()
async def luna_git_status() -> str:
    """
    Get current git status for Luna project.

    Returns:
        Formatted git status
    """
    return await git.luna_git_status()


# ==============================================================================
# Entry Point
# ==============================================================================

if __name__ == "__main__":
    mcp.run()
