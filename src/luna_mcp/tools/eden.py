"""
Eden Tools for Luna-Hub-MCP-V1
================================

Async wrappers for Eden.art API tools.
Exposes Eden creative AI capabilities through MCP for direct Claude Desktop access.

Tools:
- eden_create_image: Generate an image from a text prompt
- eden_create_video: Generate a video from a text prompt
- eden_chat: Chat with an Eden agent
- eden_list_agents: List available Eden agents
- eden_health: Check Eden API connectivity

Requires EDEN_API_KEY in .env to function.
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


# =============================================================================
# EDEN ADAPTER SINGLETON
# =============================================================================

_adapter = None
_adapter_initialized = False


async def _get_adapter():
    """Lazy-init the Eden adapter singleton."""
    global _adapter, _adapter_initialized

    if _adapter_initialized:
        return _adapter

    api_key = os.environ.get("EDEN_API_KEY", "")
    if not api_key or api_key == "your_key_here":
        _adapter_initialized = True
        _adapter = None
        logger.debug("Eden: No API key set, tools unavailable")
        return None

    try:
        from luna.services.eden import EdenAdapter, EdenConfig
        config = EdenConfig.load()
        adapter = EdenAdapter(config)
        await adapter.__aenter__()
        _adapter = adapter
        _adapter_initialized = True
        logger.info("Eden adapter initialized for MCP")
        return adapter
    except Exception as e:
        logger.warning(f"Eden adapter init failed: {e}")
        _adapter_initialized = True
        _adapter = None
        return None


async def _shutdown_adapter():
    """Shutdown the adapter if active. Called on server shutdown."""
    global _adapter, _adapter_initialized
    if _adapter:
        try:
            await _adapter.__aexit__(None, None, None)
        except Exception:
            pass
    _adapter = None
    _adapter_initialized = False


def _format_result(result) -> str:
    """Format result as JSON string for MCP."""
    if isinstance(result, str):
        return result
    return json.dumps(result, indent=2, default=str)


def _not_available(reason: str = "Eden API not configured") -> str:
    """Return error when Eden is unavailable."""
    return json.dumps({
        "error": "Eden unavailable",
        "message": f"{reason}. Set EDEN_API_KEY in .env to enable.",
    }, indent=2)


# =============================================================================
# ASYNC TOOL IMPLEMENTATIONS
# =============================================================================

async def eden_create_image(
    prompt: str,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> str:
    """
    Generate an image from a text prompt using Eden.art.

    Args:
        prompt: Text description of the image to generate
        width: Image width in pixels (optional)
        height: Image height in pixels (optional)

    Returns:
        JSON with task_id, status, url, and is_complete fields
    """
    adapter = await _get_adapter()
    if not adapter:
        return _not_available()

    try:
        extra_args = {}
        if width:
            extra_args["width"] = width
        if height:
            extra_args["height"] = height

        task = await adapter.create_image(
            prompt=prompt,
            extra_args=extra_args if extra_args else None,
        )

        result = {
            "task_id": task.id,
            "status": task.status.value,
            "is_complete": task.is_complete,
            "is_failed": task.is_failed,
            "url": task.first_output_url,
            "error": task.error,
        }
        return _format_result(result)

    except Exception as e:
        logger.error(f"Eden create_image failed: {e}")
        return _format_result({"error": str(e)})


async def eden_create_video(
    prompt: str,
) -> str:
    """
    Generate a video from a text prompt using Eden.art.

    Args:
        prompt: Text description of the video to generate

    Returns:
        JSON with task_id, status, url, and is_complete fields
    """
    adapter = await _get_adapter()
    if not adapter:
        return _not_available()

    try:
        task = await adapter.create_video(prompt=prompt)

        result = {
            "task_id": task.id,
            "status": task.status.value,
            "is_complete": task.is_complete,
            "is_failed": task.is_failed,
            "url": task.first_output_url,
            "error": task.error,
        }
        return _format_result(result)

    except Exception as e:
        logger.error(f"Eden create_video failed: {e}")
        return _format_result({"error": str(e)})


async def eden_chat(
    message: str,
    agent_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> str:
    """
    Chat with an Eden agent. Creates a new session or continues an existing one.

    Args:
        message: Message to send to the agent
        agent_id: Eden agent ID (uses EDEN_AGENT_ID env var if not provided)
        session_id: Existing session ID to continue (creates new if not provided)

    Returns:
        JSON with session_id, agent responses, and tool calls
    """
    adapter = await _get_adapter()
    if not adapter:
        return _not_available()

    try:
        # Resolve agent ID
        aid = agent_id or os.environ.get("EDEN_AGENT_ID", "")
        if not aid or aid == "optional_default_agent":
            return _format_result({
                "error": "No agent_id provided",
                "message": "Provide agent_id parameter or set EDEN_AGENT_ID in .env",
            })

        if session_id:
            # Continue existing session
            messages = await adapter.send_message(
                session_id=session_id,
                content=message,
            )
        else:
            # Create new session
            session = await adapter.create_session(
                agent_ids=[aid],
                content=message,
            )
            session_id = session.id
            messages = session.messages

        # Format messages
        formatted = []
        for msg in messages:
            entry = {
                "role": msg.role.value,
                "content": msg.content,
            }
            if msg.tool_calls:
                entry["tool_calls"] = [
                    {"tool": tc.tool, "args": tc.args, "status": tc.status}
                    for tc in msg.tool_calls
                ]
            formatted.append(entry)

        result = {
            "session_id": session_id,
            "messages": formatted,
            "message_count": len(formatted),
        }
        return _format_result(result)

    except Exception as e:
        logger.error(f"Eden chat failed: {e}")
        return _format_result({"error": str(e)})


async def eden_list_agents() -> str:
    """
    List available Eden agents.

    Returns:
        JSON array of agents with id, name, description, and tools
    """
    adapter = await _get_adapter()
    if not adapter:
        return _not_available()

    try:
        agents = await adapter.list_agents()

        result = [
            {
                "id": a.id,
                "name": a.name,
                "description": a.description,
                "tools": a.tools,
                "public": a.public,
            }
            for a in agents
        ]
        return _format_result({"agents": result, "count": len(result)})

    except Exception as e:
        logger.error(f"Eden list_agents failed: {e}")
        return _format_result({"error": str(e)})


async def eden_health() -> str:
    """
    Check Eden API connectivity and authentication.

    Returns:
        JSON with status (ok/error) and api_key presence
    """
    adapter = await _get_adapter()
    if not adapter:
        return _not_available()

    try:
        healthy = await adapter.health_check()
        result = {
            "status": "ok" if healthy else "error",
            "api_base": adapter.config.api_base,
            "has_api_key": bool(adapter.config.api_key),
        }
        return _format_result(result)

    except Exception as e:
        logger.error(f"Eden health check failed: {e}")
        return _format_result({"status": "error", "error": str(e)})
