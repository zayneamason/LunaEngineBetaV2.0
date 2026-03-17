"""
Engine Control Tools for Luna-Hub-MCP-V1
==========================================

MCP tool wrappers for aperture, voice, LLM, consciousness, and extraction
control. Each tool hits the live Engine API via EngineClient.

Tools:
- aperture_get, aperture_set, aperture_reset, aperture_lock_in_status
- voice_start, voice_stop, voice_status, voice_speak
- llm_providers, llm_switch_provider, llm_fallback_chain
- consciousness_state
- extraction_trigger, extraction_stats
"""

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _format_result(result) -> str:
    if isinstance(result, str):
        return result
    return json.dumps(result, indent=2, default=str)


# =============================================================================
# Aperture Control
# =============================================================================

async def aperture_get() -> str:
    """
    Get current aperture state — mode, thresholds, and active collections.
    """
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.aperture_get()
    return _format_result(result)


async def aperture_set(mode: Optional[str] = None, angle: Optional[float] = None) -> str:
    """
    Set aperture mode and parameters.

    Args:
        mode: Aperture preset — "wide", "balanced", "focused", "pinpoint"
        angle: Custom aperture angle (0.0 to 1.0)
    """
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.aperture_set(mode, angle)
    return _format_result(result)


async def aperture_reset() -> str:
    """Reset aperture to defaults."""
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.aperture_reset()
    return _format_result(result)


async def aperture_lock_in_status() -> str:
    """Get lock-in levels for all collections."""
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.aperture_lock_in_status()
    return _format_result(result)


# =============================================================================
# Voice Control
# =============================================================================

async def voice_start() -> str:
    """Start a voice session."""
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.voice_start()
    return _format_result(result)


async def voice_stop() -> str:
    """Stop the active voice session."""
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.voice_stop()
    return _format_result(result)


async def voice_status() -> str:
    """Get current voice session state."""
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.voice_status()
    return _format_result(result)


async def voice_speak(text: str) -> str:
    """
    Speak text via TTS.

    Args:
        text: The text for Luna to speak aloud
    """
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.voice_speak(text)
    return _format_result(result)


# =============================================================================
# LLM Provider
# =============================================================================

async def llm_providers() -> str:
    """List available LLM providers and their status."""
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.llm_providers()
    return _format_result(result)


async def llm_switch_provider(provider: str) -> str:
    """
    Switch the active LLM provider.

    Args:
        provider: Provider name — "local", "groq", "claude", "openai", "together"
    """
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.llm_switch_provider(provider)
    return _format_result(result)


async def llm_fallback_chain() -> str:
    """Get the current LLM fallback chain order."""
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.llm_fallback_chain()
    return _format_result(result)


# =============================================================================
# Consciousness
# =============================================================================

async def consciousness_state() -> str:
    """Get Luna's current consciousness state model."""
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.consciousness_state()
    return _format_result(result)


# =============================================================================
# Extraction
# =============================================================================

async def extraction_trigger() -> str:
    """Trigger extraction on recent conversation."""
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.extraction_trigger()
    return _format_result(result)


async def extraction_stats() -> str:
    """Get extraction pipeline stats."""
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.extraction_stats()
    return _format_result(result)


# =============================================================================
# QA Pipeline Control (bite-09)
# =============================================================================

async def qa_node_status() -> str:
    """
    Get pass/warn/fail status for each pipeline node right now.

    Returns a map like: { "director": "pass", "memory_matrix": "fail" }
    """
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.qa_node_status()
    return _format_result(result)


async def qa_force_revalidate(assertion_ids: str) -> str:
    """
    Re-run specific assertions against the last inference.

    Args:
        assertion_ids: Comma-separated assertion IDs, e.g. "R1,R3,V1"
    """
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    ids = [a.strip() for a in assertion_ids.split(",") if a.strip()]
    result = await client.qa_force_revalidate(ids)
    return _format_result(result)


async def qa_assertion_history(assertion_id: str, count: int = 10) -> str:
    """
    Get pass/fail trend for a specific assertion over the last N inferences.

    Args:
        assertion_id: The assertion ID (e.g. "R1", "P1", "V1")
        count: How many recent inferences to check (default 10)
    """
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.qa_assertion_history(assertion_id, count)
    return _format_result(result)


async def qa_inject_test(message: str) -> str:
    """
    Send a test message through the full pipeline and return QA results
    WITHOUT affecting conversation state.

    Args:
        message: The test message to run through the pipeline
    """
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.qa_inject_test(message)
    return _format_result(result)


# =============================================================================
# Full Diagnostic Snapshots
# =============================================================================

async def luna_last_inference() -> str:
    """Full diagnostic snapshot of the last inference.

    Returns route, assembler state, QA report, prompt length, and source.
    """
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.last_inference()
    return _format_result(result)


async def luna_pipeline_state() -> str:
    """Actor states with QA overlay.

    Returns node status (director, memory_matrix, etc.) and QA health.
    """
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.pipeline_state()
    return _format_result(result)


async def luna_prompt_preview(message: str = "Hello", route: str = None) -> str:
    """
    Preview the full assembled system prompt for a message WITHOUT calling the LLM.

    Shows the last system prompt info (identity injection, voice directives, assembler metadata).
    Use this to check what Luna sees before responding.

    Args:
        message: The message to preview prompt for
        route: Optional route override ("local", "delegated", "fallback")
    """
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.prompt_preview(message, route)
    return _format_result(result)


async def qa_simulate_with_options(
    message: str,
    route_override: str = None,
    narration_enabled: bool = None,
    extra_context: str = None,
) -> str:
    """
    Run a test message through Luna's full pipeline with diagnostic overrides.

    This is the primary debugging tool. Send a message and get back the full
    result with QA validation. Use overrides to isolate quality problems:
    - route_override="local" — test if problem is delegation vs local
    - narration_enabled=false — see raw LLM output without voice transform
    - extra_context — inject memory and test if retrieval is the bottleneck

    Args:
        message: Test message to send through the pipeline
        route_override: Force "local", "delegated", or "fallback" routing
        narration_enabled: Override narration on (true) or off (false)
        extra_context: Extra text to inject into context for this turn
    """
    from luna_mcp.engine_client import EngineClient
    body = {"message": message}
    if route_override:
        body["route_override"] = route_override
    if narration_enabled is not None:
        body["narration_enabled"] = narration_enabled
    if extra_context:
        body["extra_context"] = extra_context

    from luna_mcp.engine_client import _http_post
    result = await _http_post("/api/diagnostics/trigger/test-inference", body)
    if result:
        result["source"] = "api"
        return _format_result(result)
    return _format_result({"error": "Engine offline — test inference requires live API", "source": "unavailable"})


async def qa_check_assertion_text(assertion_id: str, response_text: str) -> str:
    """
    Test a single QA assertion against provided text.

    Quick way to check if a response would pass or fail a specific assertion
    without running the full pipeline. Good for testing pattern changes.

    Args:
        assertion_id: The assertion ID (e.g. "V1", "S4", "P3", "CUSTOM-CB2C01")
        response_text: The text to check against the assertion
    """
    from luna_mcp.engine_client import _http_post
    result = await _http_post(
        "/qa/check-assertion",
        {"assertion_id": assertion_id, "response_text": response_text},
    )
    if result:
        return _format_result(result)
    return _format_result({"error": "QA not available", "source": "unavailable"})


async def diagnostics_full() -> str:
    """Full diagnostic summary — engine health, QA state, component status."""
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.diagnostics_full()
    return _format_result(result)
