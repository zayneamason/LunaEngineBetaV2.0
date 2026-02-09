"""
QA Tools for Luna-Hub-MCP-V1
=============================

Async wrappers for Luna's self-diagnosis QA tools.
Exposes QA functionality through MCP for direct Claude Desktop access.

Tools:
- qa_get_last_report: Get last inference QA report
- qa_get_health: Check Luna's QA health status
- qa_search_reports: Search QA report history
- qa_get_stats: Get QA statistics
- qa_get_assertions: List configured assertions
- qa_add_assertion: Add custom assertion
- qa_toggle_assertion: Enable/disable assertion
- qa_delete_assertion: Delete custom assertion
- qa_add_bug: Add bug to regression database
- qa_add_bug_from_last: Create bug from last failure
- qa_list_bugs: List known bugs
- qa_update_bug_status: Update bug status
- qa_get_bug: Get bug details
- qa_diagnose_last: Detailed diagnosis of last failure
- qa_check_personality: Check personality configuration
"""

import asyncio
import json
import logging
from typing import Optional, List
from functools import partial

logger = logging.getLogger(__name__)


# =============================================================================
# QA MODULE IMPORTS
# =============================================================================

try:
    from luna.qa.mcp_tools import (
        qa_get_last_report as _qa_get_last_report,
        qa_get_health as _qa_get_health,
        qa_search_reports as _qa_search_reports,
        qa_get_stats as _qa_get_stats,
        qa_get_assertion_list as _qa_get_assertion_list,
        qa_add_assertion as _qa_add_assertion,
        qa_toggle_assertion as _qa_toggle_assertion,
        qa_delete_assertion as _qa_delete_assertion,
        qa_add_bug as _qa_add_bug,
        qa_add_bug_from_last as _qa_add_bug_from_last,
        qa_list_bugs as _qa_list_bugs,
        qa_update_bug_status as _qa_update_bug_status,
        qa_get_bug as _qa_get_bug,
        qa_diagnose_last as _qa_diagnose_last,
        qa_check_personality as _qa_check_personality,
    )
    QA_AVAILABLE = True
except ImportError as e:
    QA_AVAILABLE = False
    logger.warning(f"QA module not available: {e}")


# =============================================================================
# ASYNC HELPERS
# =============================================================================

def _run_sync(func, *args, **kwargs):
    """Run a synchronous function."""
    return func(*args, **kwargs)


async def _async_wrap(func, *args, **kwargs):
    """Wrap a sync function to run in executor."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, partial(_run_sync, func, *args, **kwargs)
    )


def _format_result(result) -> str:
    """Format result as JSON string for MCP."""
    if isinstance(result, str):
        return result
    return json.dumps(result, indent=2, default=str)


def _not_available() -> str:
    """Return error message when QA module not available."""
    return json.dumps({
        "error": "QA module not available",
        "message": "The Luna QA system is not loaded. Ensure luna.qa is accessible."
    }, indent=2)


# =============================================================================
# ASYNC TOOL IMPLEMENTATIONS
# =============================================================================

async def qa_get_last_report() -> str:
    """
    Get the QA report for Luna's most recent inference.

    Returns assertion results, diagnosis, and debugging info.
    Use this to understand why the last response may have failed QA.
    """
    if not QA_AVAILABLE:
        return _not_available()
    result = await _async_wrap(_qa_get_last_report)
    return _format_result(result)


async def qa_get_health() -> str:
    """
    Get Luna's current QA health status.

    Returns:
        - pass_rate: float (0-1)
        - recent_failures: list of failed assertion names
        - failing_bugs: count of known bugs still failing
    """
    if not QA_AVAILABLE:
        return _not_available()
    result = await _async_wrap(_qa_get_health)
    return _format_result(result)


async def qa_search_reports(
    query: Optional[str] = None,
    route: Optional[str] = None,
    passed: Optional[bool] = None,
    limit: int = 10
) -> str:
    """
    Search QA report history.

    Args:
        query: Filter by query text
        route: Filter by route (LOCAL_ONLY, DELEGATION_DETECTION, FULL_DELEGATION)
        passed: Filter by pass/fail status
        limit: Max results (default 10)
    """
    if not QA_AVAILABLE:
        return _not_available()
    result = await _async_wrap(_qa_search_reports, query, route, passed, limit)
    return _format_result(result)


async def qa_get_stats(time_range: str = "24h") -> str:
    """
    Get QA statistics for a time range.

    Args:
        time_range: "1h", "24h", "7d", "30d"
    """
    if not QA_AVAILABLE:
        return _not_available()
    result = await _async_wrap(_qa_get_stats, time_range)
    return _format_result(result)


async def qa_get_assertions() -> str:
    """Get all configured QA assertions."""
    if not QA_AVAILABLE:
        return _not_available()
    result = await _async_wrap(_qa_get_assertion_list)
    return _format_result(result)


async def qa_add_assertion(
    name: str,
    category: str,
    severity: str,
    target: str,
    condition: str,
    pattern: str,
    case_sensitive: bool = False
) -> str:
    """
    Add a new pattern-based assertion to the QA system.

    Args:
        name: Human-readable name
        category: structural, voice, personality, flow
        severity: critical, high, medium, low
        target: response, raw_response, system_prompt, query
        condition: contains, not_contains, regex, length_gt, length_lt
        pattern: The pattern to match
        case_sensitive: Whether match is case-sensitive (default False)

    Example:
        qa_add_assertion(
            name="No French",
            category="voice",
            severity="medium",
            target="response",
            condition="not_contains",
            pattern="bonjour|merci"
        )
    """
    if not QA_AVAILABLE:
        return _not_available()
    result = await _async_wrap(
        _qa_add_assertion, name, category, severity, target, condition, pattern, case_sensitive
    )
    return _format_result(result)


async def qa_toggle_assertion(assertion_id: str, enabled: bool) -> str:
    """Enable or disable a QA assertion."""
    if not QA_AVAILABLE:
        return _not_available()
    result = await _async_wrap(_qa_toggle_assertion, assertion_id, enabled)
    return _format_result(result)


async def qa_delete_assertion(assertion_id: str) -> str:
    """Delete a custom QA assertion (built-in assertions cannot be deleted)."""
    if not QA_AVAILABLE:
        return _not_available()
    result = await _async_wrap(_qa_delete_assertion, assertion_id)
    return _format_result(result)


async def qa_add_bug(
    name: str,
    query: str,
    expected_behavior: str,
    actual_behavior: str,
    severity: str = "high"
) -> str:
    """
    Add a known bug to the regression database.

    This bug will be tested every time the regression suite runs.

    Args:
        name: Bug name/title
        query: The query that triggers the bug
        expected_behavior: What should happen
        actual_behavior: What actually happens
        severity: critical, high, medium, low (default "high")
    """
    if not QA_AVAILABLE:
        return _not_available()
    result = await _async_wrap(
        _qa_add_bug, name, query, expected_behavior, actual_behavior, severity
    )
    return _format_result(result)


async def qa_add_bug_from_last(name: str, expected_behavior: str) -> str:
    """
    Create a bug from the last failed QA report.

    Automatically populates query, actual behavior, and affected assertions.

    Args:
        name: Bug name/title
        expected_behavior: What should happen
    """
    if not QA_AVAILABLE:
        return _not_available()
    result = await _async_wrap(_qa_add_bug_from_last, name, expected_behavior)
    return _format_result(result)


async def qa_list_bugs(status: Optional[str] = None) -> str:
    """
    List known bugs.

    Args:
        status: Filter by status (open, failing, fixed, wontfix)
    """
    if not QA_AVAILABLE:
        return _not_available()
    result = await _async_wrap(_qa_list_bugs, status)
    return _format_result(result)


async def qa_update_bug_status(bug_id: str, status: str) -> str:
    """
    Update a bug's status.

    Args:
        bug_id: The bug ID
        status: New status (open, failing, fixed, wontfix)
    """
    if not QA_AVAILABLE:
        return _not_available()
    result = await _async_wrap(_qa_update_bug_status, bug_id, status)
    return _format_result(result)


async def qa_get_bug(bug_id: str) -> str:
    """Get details for a specific bug by ID."""
    if not QA_AVAILABLE:
        return _not_available()
    result = await _async_wrap(_qa_get_bug, bug_id)
    return _format_result(result)


async def qa_diagnose_last() -> str:
    """
    Get a detailed diagnosis of the last QA failure.

    Returns structured information about what went wrong and how to fix it.
    Includes: failures by category, diagnosis text, response preview.
    """
    if not QA_AVAILABLE:
        return _not_available()
    result = await _async_wrap(_qa_diagnose_last)
    return _format_result(result)


async def qa_check_personality() -> str:
    """
    Check if Luna's personality is properly configured.

    Returns status of personality-related assertions (P1, P2, P3) from last report.
    Includes: personality_injected, virtues_loaded, narration_applied.
    """
    if not QA_AVAILABLE:
        return _not_available()
    result = await _async_wrap(_qa_check_personality)
    return _format_result(result)
