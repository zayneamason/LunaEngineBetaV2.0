"""
Memory tools — smart_fetch, search, add_node, etc.
==================================================

Tools for accessing Luna's Memory Matrix through the MCP API.

Auto-Session Recording (v2):
- Sessions start automatically on first tool activity
- Turns are recorded automatically for conversational tools
- Sessions end after inactivity timeout (5 minutes)
"""

import asyncio
import logging
import time
import httpx
from typing import Optional, List, Dict, Any

from luna_mcp.models import (
    SmartFetchInput, MemorySearchInput, AddNodeInput,
    AddEdgeInput, GetContextInput, TraceDependenciesInput,
    SaveMemoryInput, MemoryType
)
from luna_mcp.launcher import get_api_url, ensure_api_running

logger = logging.getLogger(__name__)

# ==============================================================================
# Auto-Session State (Module Level)
# ==============================================================================

_auto_session_active: bool = False
_auto_session_id: Optional[str] = None
_last_activity: Optional[float] = None
_inactivity_timeout: int = 300  # 5 minutes
_monitor_task: Optional[asyncio.Task] = None
_turn_buffer: List[Dict[str, str]] = []  # Buffer turns before flushing
_buffer_flush_threshold: int = 4  # Flush after 4 turns


# ==============================================================================
# Auto-Session Functions
# ==============================================================================

async def ensure_auto_session() -> Optional[str]:
    """
    Automatically start a session if not active.

    Called before every tool execution to ensure session exists.
    Starts inactivity monitor on first call.

    Returns:
        Session ID or None if creation failed
    """
    global _auto_session_active, _auto_session_id, _last_activity, _monitor_task

    # Update activity timestamp
    _last_activity = time.time()

    # Return existing session if active
    if _auto_session_active and _auto_session_id:
        logger.debug(f"[AUTO-SESSION] Using existing session: {_auto_session_id}")
        return _auto_session_id

    # Start new session
    logger.info("[AUTO-SESSION] Starting new auto-session")
    try:
        result = await _start_auto_session()
        if result:
            _auto_session_id = result
            _auto_session_active = True

            # Start inactivity monitor if not running
            if _monitor_task is None or _monitor_task.done():
                _monitor_task = asyncio.create_task(_inactivity_monitor())
                logger.info("[AUTO-SESSION] Started inactivity monitor")

            return _auto_session_id
    except Exception as e:
        logger.error(f"[AUTO-SESSION] Failed to start session: {e}")

    return None


async def _start_auto_session() -> Optional[str]:
    """Internal: Create session via API."""
    try:
        response = await _call_api(
            "POST",
            "/hub/session/create",
            json={"app_context": "mcp-auto"}
        )
        session_id = response.get("session_id")
        if session_id:
            logger.info(f"[AUTO-SESSION] Created session: {session_id}")
            return session_id
    except Exception as e:
        logger.error(f"[AUTO-SESSION] Session creation failed: {e}")
    return None


async def auto_record_turn(role: str, content: str):
    """
    Record a turn with auto-session management.

    Buffers turns and flushes periodically to reduce API calls.

    Args:
        role: "user" or "assistant"
        content: Message content (will be truncated if too long)
    """
    global _turn_buffer, _last_activity

    # Ensure session exists
    session_id = await ensure_auto_session()
    if not session_id:
        logger.warning("[AUTO-SESSION] Cannot record turn: no session")
        return

    # Update activity
    _last_activity = time.time()

    # Truncate long content
    truncated = content[:2000] if len(content) > 2000 else content

    # Add to buffer
    _turn_buffer.append({
        "role": role,
        "content": truncated,
        "session_id": session_id
    })

    logger.debug(f"[AUTO-SESSION] Buffered {role} turn, buffer size: {len(_turn_buffer)}")

    # Flush if buffer threshold reached
    if len(_turn_buffer) >= _buffer_flush_threshold:
        await _flush_turn_buffer()


async def _flush_turn_buffer():
    """Flush buffered turns to the API."""
    global _turn_buffer

    if not _turn_buffer:
        return

    logger.info(f"[AUTO-SESSION] Flushing {len(_turn_buffer)} buffered turns")

    for turn in _turn_buffer:
        try:
            tokens = len(turn["content"]) // 4
            await _call_api(
                "POST",
                "/hub/turn/add",
                json={
                    "role": turn["role"],
                    "content": turn["content"],
                    "session_id": turn["session_id"],
                    "tokens": tokens
                }
            )
        except Exception as e:
            logger.error(f"[AUTO-SESSION] Failed to flush turn: {e}")

    _turn_buffer = []


async def _inactivity_monitor():
    """
    Background task to end stale sessions after inactivity timeout.

    Checks every 60 seconds. Ends session if no activity for 5 minutes.
    """
    global _auto_session_active, _auto_session_id, _last_activity

    logger.info("[AUTO-SESSION] Inactivity monitor started")

    while True:
        try:
            await asyncio.sleep(60)  # Check every minute

            if not _auto_session_active or not _last_activity:
                continue

            inactive_seconds = time.time() - _last_activity

            if inactive_seconds > _inactivity_timeout:
                logger.info(f"[AUTO-SESSION] Session inactive for {inactive_seconds:.0f}s, ending")
                await _end_auto_session()
        except asyncio.CancelledError:
            logger.info("[AUTO-SESSION] Inactivity monitor cancelled")
            break
        except Exception as e:
            logger.error(f"[AUTO-SESSION] Monitor error: {e}")


async def _end_auto_session():
    """
    End the current auto-session and trigger extraction.

    Called by inactivity monitor or manual deactivation.
    """
    global _auto_session_active, _auto_session_id, _turn_buffer

    if not _auto_session_id:
        return

    session_id = _auto_session_id
    logger.info(f"[AUTO-SESSION] Ending session: {session_id}")

    try:
        # Flush any remaining buffered turns
        await _flush_turn_buffer()

        # Get turns from session
        window_response = await _call_api(
            "GET",
            f"/hub/active_window?session_id={session_id}&limit=100"
        )
        turns = window_response.get("turns", [])

        # Filter to user turns only — never extract assistant content
        user_turns = [t for t in turns if t.get("role") == "user"]

        # End session
        await _call_api(
            "POST",
            f"/hub/session/end?session_id={session_id}"
        )

        # Extraction now happens in real-time via /hub/turn/add — no need to trigger here

        logger.info(f"[AUTO-SESSION] Session ended successfully: {session_id}")

    except Exception as e:
        logger.error(f"[AUTO-SESSION] Error ending session: {e}")
    finally:
        _auto_session_active = False
        _auto_session_id = None
        _turn_buffer = []


async def get_auto_session_status() -> Dict[str, Any]:
    """Get current auto-session status for debugging."""
    return {
        "active": _auto_session_active,
        "session_id": _auto_session_id,
        "last_activity": _last_activity,
        "time_since_activity": time.time() - _last_activity if _last_activity else None,
        "buffer_size": len(_turn_buffer),
        "inactivity_timeout": _inactivity_timeout
    }


# ==============================================================================
# API Helper
# ==============================================================================

async def _call_api(method: str, path: str, **kwargs) -> dict:
    """Call MCP API with tracing."""
    # Ensure API is running before calling
    await ensure_api_running()

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


async def luna_smart_fetch(query: str, budget_preset: str = "balanced") -> str:
    """
    Intelligently fetch relevant context for Luna.

    Uses Memory Matrix hybrid search (FTS5 + sqlite-vec + graph)
    within token budget. This is Luna's primary memory access tool.

    Args:
        query: What to search for
        budget_preset: Token budget - minimal (1800), balanced (3800), rich (7200)

    Returns:
        Formatted context summary
    """
    logger.info(f"[TRACE] luna_smart_fetch called: query='{query}' budget='{budget_preset}'")

    try:
        response = await _call_api(
            "POST",
            "/memory/smart-fetch",
            json={"query": query, "budget_preset": budget_preset}
        )

        logger.info(f"[TRACE] luna_smart_fetch response: {response}")

        # Format response
        nodes = response.get('nodes', [])
        budget_used = response.get('budget_used', 0)

        logger.info(f"[TRACE] luna_smart_fetch nodes count: {len(nodes)}, budget: {budget_used}")

        lines = [
            f"# Context: {query}",
            f"*Retrieved {len(nodes)} nodes, {budget_used} tokens*",
            ""
        ]

        for node in nodes:
            node_type = node.get('node_type', node.get('type', 'UNKNOWN'))
            content = node.get('content', '')[:300]
            lines.append(f"- [{node_type}] {content}")
            logger.info(f"[TRACE] luna_smart_fetch node: [{node_type}] {content[:50]}...")

        return "\n".join(lines)
    except httpx.ConnectError:
        logger.exception("[TRACE] luna_smart_fetch ConnectError")
        return f"Error: MCP API not reachable at {get_api_url()}"
    except Exception as e:
        logger.exception(f"[TRACE] luna_smart_fetch EXCEPTION: {e}")
        return f"Error during smart fetch: {str(e)}"


async def memory_matrix_search(query: str, limit: int = 10) -> str:
    """
    Search Luna's memory graph.

    Args:
        query: Search query
        limit: Maximum number of results

    Returns:
        Formatted search results
    """
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
    except httpx.ConnectError:
        logger.exception("[TRACE] memory_matrix_search ConnectError")
        return f"Error: MCP API not reachable at {get_api_url()}"
    except Exception as e:
        logger.exception(f"[TRACE] memory_matrix_search EXCEPTION: {e}")
        return f"Error searching memory: {str(e)}"


async def memory_matrix_add_node(
    node_type: str,
    content: str,
    tags: Optional[List[str]] = None,
    confidence: float = 1.0,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Add a memory node to the graph.

    Args:
        node_type: Node type (FACT, DECISION, PROBLEM, ACTION, etc.)
        content: Content of the memory
        tags: Optional tags for categorization
        confidence: Confidence score (0.0-1.0)
        metadata: Additional metadata

    Returns:
        Success message with node ID or error
    """
    try:
        response = await _call_api(
            "POST",
            "/memory/add-node",
            json={
                "node_type": node_type,
                "content": content,
                "tags": tags,
                "confidence": confidence,
                "metadata": metadata
            }
        )

        if response.get('success'):
            return f"✓ Added node: {response.get('node_id')}"
        else:
            return "Failed to add node"
    except httpx.ConnectError:
        logger.exception("[TRACE] memory_matrix_add_node ConnectError")
        return f"Error: MCP API not reachable at {get_api_url()}"
    except Exception as e:
        logger.exception(f"[TRACE] memory_matrix_add_node EXCEPTION: {e}")
        return f"Error adding node: {str(e)}"


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
        relationship: Relationship type (DEPENDS_ON, RELATES_TO, CAUSED_BY, etc.)
        strength: Relationship strength (0.0-1.0)

    Returns:
        Success message or error
    """
    try:
        response = await _call_api(
            "POST",
            "/memory/add-edge",
            json={
                "from_node": from_node,
                "to_node": to_node,
                "relationship": relationship.upper(),
                "strength": strength,
            }
        )

        if response.get('success'):
            return f"✓ Edge created: {from_node} --{relationship}[{strength}]--> {to_node}"
        else:
            return f"Failed to create edge: {response.get('message', 'Unknown error')}"
    except httpx.ConnectError:
        return f"Error: MCP API not reachable at {get_api_url()}"
    except Exception as e:
        return f"Error creating edge: {str(e)}"


async def memory_matrix_get_context(node_id: str, depth: int = 2) -> str:
    """
    Get context around a specific memory node.

    Args:
        node_id: Node ID to get context for
        depth: Depth of context graph traversal

    Returns:
        Formatted context or error
    """
    try:
        response = await _call_api(
            "POST",
            "/memory/node-context",
            json={
                "node_id": node_id,
                "depth": depth,
            }
        )

        neighbors = response.get('neighbors', [])
        edges = response.get('edges', [])

        # Format output
        output_parts = [f"## Context for Node: {node_id}"]
        output_parts.append(f"**Depth:** {depth}")
        output_parts.append(f"**Neighbors:** {len(neighbors)}")

        if neighbors:
            output_parts.append("\n### Connected Nodes:")
            for n in neighbors[:20]:  # Limit display
                output_parts.append(f"  - {n}")

        if edges:
            output_parts.append("\n### Edges:")
            for e in edges[:20]:  # Limit display
                output_parts.append(f"  - {e['from_id']} --{e['relationship']}[{e['strength']:.2f}]--> {e['to_id']}")

        return "\n".join(output_parts)
    except httpx.ConnectError:
        return f"Error: MCP API not reachable at {get_api_url()}"
    except Exception as e:
        return f"Error getting context: {str(e)}"


async def memory_matrix_trace(node_id: str, max_depth: int = 5) -> str:
    """
    Trace dependency paths leading to a memory node using spreading activation.

    Args:
        node_id: Node ID to trace dependencies for
        max_depth: Maximum depth for dependency trace

    Returns:
        Formatted dependency trace or error
    """
    try:
        response = await _call_api(
            "POST",
            "/memory/trace",
            json={
                "node_id": node_id,
                "max_depth": max_depth,
            }
        )

        activations = response.get('activations', {})
        paths = response.get('paths', [])

        # Format output
        output_parts = [f"## Dependency Trace for Node: {node_id}"]
        output_parts.append(f"**Max Depth:** {max_depth}")
        output_parts.append(f"**Related Nodes:** {len(activations)}")

        if activations:
            output_parts.append("\n### Activation Scores (Spreading Activation):")
            # Sort by activation score
            sorted_acts = sorted(activations.items(), key=lambda x: x[1], reverse=True)
            for nid, score in sorted_acts[:20]:  # Top 20
                bar = "█" * int(score * 10)
                output_parts.append(f"  {nid}: {score:.3f} {bar}")

        if paths:
            output_parts.append("\n### Direct Connections:")
            for p in paths[:10]:
                output_parts.append(f"  {p['from_id']} --{p['relationship']}--> {p['to_id']}")

        return "\n".join(output_parts)
    except httpx.ConnectError:
        return f"Error: MCP API not reachable at {get_api_url()}"
    except Exception as e:
        return f"Error tracing dependencies: {str(e)}"


async def luna_save_memory(
    memory_type: str,
    title: str,
    content: str,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
    """
    Save a structured memory entry.

    Args:
        memory_type: Type of memory (session, insight, context, artifact)
        title: Memory title
        content: Memory content
        tags: Optional tags
        metadata: Optional metadata

    Returns:
        Success message or error
    """
    try:
        # Convert memory_type to node_type
        type_mapping = {
            "session": "SESSION",
            "insight": "INSIGHT",
            "context": "CONTEXT",
            "artifact": "ARTIFACT"
        }
        node_type = type_mapping.get(memory_type.lower(), memory_type.upper())

        response = await _call_api(
            "POST",
            "/memory/add-node",
            json={
                "node_type": node_type,
                "content": f"# {title}\n\n{content}",
                "tags": tags or [],
                "metadata": metadata or {}
            }
        )

        if response.get('success'):
            return f"✓ Memory saved: {title}"
        else:
            return "Failed to save memory"
    except httpx.ConnectError:
        logger.exception("[TRACE] luna_save_memory ConnectError")
        return f"Error: MCP API not reachable at {get_api_url()}"
    except Exception as e:
        logger.exception(f"[TRACE] luna_save_memory EXCEPTION: {e}")
        return f"Error saving memory: {str(e)}"


# ==============================================================================
# Session & Conversation Recording
# ==============================================================================

# Module-level session tracking
_current_session_id: Optional[str] = None


async def luna_start_session(app_context: str = "mcp") -> str:
    """
    Start a new conversation session for memory recording.

    Call this at the beginning of a conversation to enable memory recording.
    Without starting a session, conversations through MCP are not persisted.

    Args:
        app_context: Application context identifier (default: "mcp")

    Returns:
        Session ID for subsequent turns, or error message
    """
    global _current_session_id

    logger.info(f"[TRACE] luna_start_session called: app_context='{app_context}'")

    try:
        response = await _call_api(
            "POST",
            "/hub/session/create",
            json={"app_context": app_context}
        )

        logger.info(f"[TRACE] luna_start_session response: {response}")

        session_id = response.get("session_id")
        if session_id:
            _current_session_id = session_id
            return f"✓ Session started: {session_id}"
        else:
            return "Failed to create session"
    except httpx.ConnectError:
        logger.exception("[TRACE] luna_start_session ConnectError")
        return f"Error: Engine API not reachable at {get_api_url()}"
    except Exception as e:
        logger.exception(f"[TRACE] luna_start_session EXCEPTION: {e}")
        return f"Error starting session: {str(e)}"


async def luna_record_turn(
    role: str,
    content: str,
    session_id: Optional[str] = None
) -> str:
    """
    Record a conversation turn to Luna's memory.

    Call this for each user message and Luna response to build
    conversation history that can be extracted into memories.

    Args:
        role: "user" or "assistant"
        content: The message content
        session_id: Optional session ID (uses current session if None)

    Returns:
        Confirmation with turn ID, or error message
    """
    global _current_session_id

    # Use provided session_id or fall back to current
    effective_session_id = session_id or _current_session_id

    logger.info(f"[TRACE] luna_record_turn called: role='{role}' session='{effective_session_id}' content_len={len(content)}")

    if not effective_session_id:
        return "Error: No active session. Call luna_start_session() first."

    try:
        # Rough token estimate: ~4 chars per token
        tokens = len(content) // 4

        response = await _call_api(
            "POST",
            "/hub/turn/add",
            json={
                "role": role,
                "content": content,
                "session_id": effective_session_id,
                "tokens": tokens
            }
        )

        logger.info(f"[TRACE] luna_record_turn response: {response}")

        turn_id = response.get("turn_id")
        tier = response.get("tier", "unknown")

        if turn_id is not None:
            return f"✓ Recorded {role} turn #{turn_id} (tier: {tier})"
        else:
            return "Failed to record turn"
    except httpx.ConnectError:
        logger.exception("[TRACE] luna_record_turn ConnectError")
        return f"Error: Engine API not reachable at {get_api_url()}"
    except Exception as e:
        logger.exception(f"[TRACE] luna_record_turn EXCEPTION: {e}")
        return f"Error recording turn: {str(e)}"


async def luna_end_session(session_id: Optional[str] = None) -> str:
    """
    End a conversation session and trigger memory extraction.

    Call this when a conversation ends (e.g., user says "later Luna").
    This signals Ben the Scribe to process the conversation and
    extract memories (FACT, DECISION, PROBLEM, ACTION nodes).

    Args:
        session_id: Session ID to end (uses current session if None)

    Returns:
        Confirmation message, or error
    """
    global _current_session_id

    # Use provided session_id or fall back to current
    effective_session_id = session_id or _current_session_id

    logger.info(f"[TRACE] luna_end_session called: session='{effective_session_id}'")

    if not effective_session_id:
        return "Error: No active session to end."

    try:
        # First, fetch the active window turns for this session
        window_response = await _call_api(
            "GET",
            f"/hub/active_window?session_id={effective_session_id}&limit=100"
        )

        logger.info(f"[TRACE] luna_end_session: fetched {len(window_response.get('turns', []))} turns")

        # Filter to user turns only — never extract assistant content
        turns = window_response.get("turns", [])
        user_turns = [t for t in turns if t.get("role") == "user"]

        # End the session
        await _call_api(
            "POST",
            f"/hub/session/end?session_id={effective_session_id}"
        )

        logger.info(f"[TRACE] luna_end_session: session ended")

        # Trigger extraction for each user turn individually
        objects_extracted = 0
        if user_turns:
            logger.info(f"[TRACE] luna_end_session: triggering extraction for {len(user_turns)} user turns (filtered from {len(turns)} total)")

            for turn in user_turns:
                content = turn.get("content", "").strip()
                if content:
                    extraction_response = await _call_api(
                        "POST",
                        "/extraction/trigger",
                        json={
                            "content": content,
                            "role": "user",
                            "session_id": effective_session_id,
                            "immediate": True
                        }
                    )
                    objects_extracted += extraction_response.get("objects_extracted", 0)

            logger.info(f"[TRACE] luna_end_session extraction total: {objects_extracted} objects")
        else:
            logger.info(f"[TRACE] luna_end_session: no user content to extract")

        # Clear current session
        if effective_session_id == _current_session_id:
            _current_session_id = None

        return f"✓ Session ended: {effective_session_id} ({len(turns)} turns, {objects_extracted} objects extracted)"
    except httpx.ConnectError:
        logger.exception("[TRACE] luna_end_session ConnectError")
        return f"Error: Engine API not reachable at {get_api_url()}"
    except Exception as e:
        logger.exception(f"[TRACE] luna_end_session EXCEPTION: {e}")
        return f"Error ending session: {str(e)}"


async def luna_get_current_session() -> str:
    """
    Get the current active session ID.

    Returns:
        Current session ID or message if no session active
    """
    global _current_session_id

    if _current_session_id:
        return f"Current session: {_current_session_id}"
    else:
        return "No active session. Call luna_start_session() to begin recording."
