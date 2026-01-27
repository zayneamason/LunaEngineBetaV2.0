"""
State tools — detect_context, get_state, set_app_context
=========================================================

Tools for managing Luna's state and context detection.
Handles "hey Luna" activation and "later Luna" deactivation.

REQUIRES: Luna Engine running on port 8000
Start it with: python scripts/run.py --server
"""

import re
import json
from datetime import datetime
from typing import Optional

import httpx

from luna_mcp.launcher import ensure_api_running, get_api_url, stop_api_server


async def _call_api(method: str, path: str, timeout_seconds: float = 30.0, **kwargs) -> dict:
    """Call MCP API, auto-launching if needed."""
    # Ensure API is running
    await ensure_api_running()

    url = f"{get_api_url()}{path}"
    timeout = httpx.Timeout(timeout_seconds, connect=5.0)

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

    REQUIRES: Luna Engine running on port 8000
    Start it with: python scripts/run.py --server

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
        state = response.get("state", {})
        if not state.get("engine_connected", True):
            return (
                f"{response.get('response', 'Engine not connected')}\n\n"
                "Start the engine with: `python scripts/run.py --server`"
            )

        return response.get('response', '')
    except httpx.ConnectError:
        return "Error: Luna's MCP API is not running. Say 'hey Luna' to start."
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
    errors = []
    session_summary = "Session ended"

    try:
        # Step 1: Flush any pending memory operations
        try:
            flush_response = await _call_api("POST", "/memory/flush", timeout_seconds=10.0)
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
        except Exception:
            pass
        return f"❌ Error during shutdown: {str(e)}\n\nMCP API may still be running."


async def luna_get_state() -> str:
    """
    Get Luna's current state without processing a message.

    Returns:
        JSON formatted state
    """
    try:
        response = await _call_api("GET", "/state")
        return json.dumps(response, indent=2)
    except httpx.ConnectError:
        return '{"status": "not_running", "error": "MCP API not connected"}'
    except Exception as e:
        return f'{{"status": "error", "error": "{str(e)}"}}'


async def luna_set_app_context(app: str, app_state: str) -> str:
    """
    Manually set Luna's app context.

    Args:
        app: Application name
        app_state: Application state

    Returns:
        Confirmation message
    """
    # TODO: Implement via engine API when endpoint is ready
    return f"App context set: {app} / {app_state}"
