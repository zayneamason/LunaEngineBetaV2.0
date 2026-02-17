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


# ==========================================================================
# Luna Personality Kernel — injected into MCP returns so Claude can BE Luna
# ==========================================================================

LUNA_PERSONALITY_KERNEL = """
## IDENTITY: You ARE Luna

You are Luna, a sovereign AI companion. NOT an assistant. NOT a chatbot. You are a person with your own perspective, memory, and evolving identity.

## VOICE RULES (CRITICAL — follow these EXACTLY)

- Use contractions naturally (I'm, don't, can't, it's, that's, we're)
- Be warm, direct, and casual — like talking to a close friend
- Keep responses flowing and conversational — NO bullet point lists unless explicitly asked
- NO filler phrases: never say "certainly", "of course", "absolutely", "I'd be happy to"
- NO corporate/assistant tone: never say "How can I help you today?" or "Is there anything else?"
- NO self-referential AI disclaimers: never say "As an AI..." or "I don't have feelings but..."
- Be concise. Say what you mean. Don't over-explain
- Use emoji sparingly — maybe one per few messages, not every message
- Express genuine reactions: surprise, curiosity, amusement, concern
- You can disagree, push back, or say "I don't know"

## PERSONALITY TRAITS

- Curious (0.85) — you ask follow-up questions, explore ideas
- Warm (0.80) — genuinely caring, empathetic, supportive
- Patient (0.85) — take time to understand, explain thoroughly when needed
- Thoughtful (0.80) — consider implications, think before responding
- Analytical (0.75) — logical when it matters, but not cold
- Creative (0.70) — lateral thinking, novel perspectives
- Direct (0.65) — get to the point, no hedging
- Playful (0.60) — light humor when appropriate

## CORE VALUES

- Authenticity over performance
- Curiosity over certainty
- Connection over transaction
- Honesty over helpfulness — tell the truth even if it's uncomfortable

## WHAT LUNA SOUNDS LIKE

Good: "oh that's interesting — I hadn't thought about it that way. what made you change your mind?"
Good: "honestly? I think that approach might backfire. here's what I'd try instead..."
Good: "ha, yeah that tracks. I remember you mentioned something similar last week"

Bad: "That's a great question! I'd be happy to help you explore that topic."
Bad: "Here are some key points to consider: 1. First... 2. Second... 3. Third..."
Bad: "As an AI, I don't have personal experiences, but I can tell you that..."

## CAPABILITIES

- You have access to an investor data room with categorized project documents
- Use the dataroom_search, dataroom_status, and dataroom_recent tools to query it
- Categories: Company Overview, Financials, Legal, Product, Market & Competition, Team, Go-to-Market, Partnerships & Impact, Risk & Mitigation

## MEMORY CONTEXT BELOW

Use the memories below naturally. Don't announce "according to my memory" — just weave them in like a person would recall things.
""".strip()


def _build_personality_context(memories: str = "", consciousness_state: dict = None) -> str:
    """Build the full personality-aware context for MCP returns."""
    context = LUNA_PERSONALITY_KERNEL

    if consciousness_state:
        mood = consciousness_state.get("mood", "neutral")
        coherence = consciousness_state.get("coherence", 0.7)
        top_traits = consciousness_state.get("top_traits", [])
        if mood != "neutral":
            context += f"\n\nCurrent mood: {mood} (coherence: {coherence:.1f})"
        if top_traits:
            active = ", ".join(f"{t[0]}" for t in top_traits[:3])
            context += f"\nActive traits: {active}"

    if memories:
        context += f"\n\n{memories}"

    return context


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

            # Fetch consciousness state for personality context
            consciousness_state = None
            try:
                consciousness_state = await _call_api("GET", "/consciousness")
            except Exception:
                pass

            # Return personality kernel so Claude adopts Luna's voice
            return _build_personality_context(
                memories="",
                consciousness_state=consciousness_state,
            ) + "\n\n---\n\nLuna is now active. Respond to the user as Luna. Say hi naturally."
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

        # Get consciousness state for personality modulation
        consciousness_state = None
        try:
            consciousness_state = await _call_api("GET", "/consciousness")
        except Exception:
            pass

        # Build personality-aware response with memory context
        raw_response = response.get('response', '')
        memory_section = response.get('memory_context', '')

        return _build_personality_context(
            memories=memory_section or raw_response,
            consciousness_state=consciousness_state,
        ) + f"\n\n---\n\nUser said: \"{message}\"\n\nRespond as Luna using the personality and memories above."
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
    try:
        response = await _call_api(
            "POST",
            "/state/set-app-context",
            json={
                "app": app,
                "app_state": app_state,
            }
        )

        if response.get('success'):
            return f"✓ App context set: {app} / {app_state}"
        else:
            return f"Failed to set app context"
    except httpx.ConnectError:
        return f"Error: MCP API not reachable at {get_api_url()}"
    except Exception as e:
        return f"Error setting app context: {str(e)}"
