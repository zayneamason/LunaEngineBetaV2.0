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
from luna_mcp.tools import filesystem, memory, state, git, forge, qa, eden
from luna_mcp.observatory import tools as observatory

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
# Persona Forge Tools - Dataset
# ==============================================================================

@mcp.tool()
async def forge_load(path: str) -> dict:
    """Load training data from JSONL file."""
    return await forge.forge_load(path)


@mcp.tool()
async def forge_assay() -> dict:
    """Analyze current dataset quality and coverage."""
    return await forge.forge_assay()


@mcp.tool()
async def forge_gaps() -> dict:
    """Show coverage gaps needing synthesis."""
    return await forge.forge_gaps()


@mcp.tool()
async def forge_mint(interaction_type: str, count: int = 10) -> dict:
    """Generate synthetic training examples."""
    return await forge.forge_mint(interaction_type, count)


@mcp.tool()
async def forge_export(output_path: str, train_split: float = 0.9) -> dict:
    """Export training data to JSONL."""
    return await forge.forge_export(output_path, train_split)


@mcp.tool()
async def forge_status() -> dict:
    """Get current Forge session state."""
    return await forge.forge_status()


# ==============================================================================
# Persona Forge Tools - Ingestion
# ==============================================================================

@mcp.tool()
async def forge_list_sources(directory: str, pattern: str = "*") -> dict:
    """List available source files for ingestion."""
    return await forge.forge_list_sources(directory, pattern)


@mcp.tool()
async def forge_read_raw(path: str, max_chars: int = 50000, offset: int = 0) -> dict:
    """Read raw file content for LLM-assisted extraction."""
    return await forge.forge_read_raw(path, max_chars, offset)


@mcp.tool()
async def forge_add_example(
    user_message: str,
    assistant_response: str,
    interaction_type: str = "short_exchange",
    source_file: str = None,
    source_type: str = "manual",
    confidence: float = 1.0,
    tags: list = None,
    context: str = None
) -> dict:
    """Add a single training example (Claude-extracted)."""
    return await forge.forge_add_example(
        user_message, assistant_response, interaction_type,
        source_file, source_type, confidence, tags, context
    )


@mcp.tool()
async def forge_add_batch(examples: list) -> dict:
    """Add multiple training examples at once."""
    return await forge.forge_add_batch(examples)


@mcp.tool()
async def forge_search(query: str, field: str = "all", limit: int = 10) -> dict:
    """Search existing examples for deduplication."""
    return await forge.forge_search(query, field, limit)


@mcp.tool()
async def forge_read_matrix(
    db_path: str,
    node_types: list = None,
    limit: int = 100,
    offset: int = 0
) -> dict:
    """Read memory nodes from Memory Matrix database."""
    return await forge.forge_read_matrix(db_path, node_types, limit, offset)


@mcp.tool()
async def forge_read_turns(
    db_path: str,
    session_id: str = None,
    limit: int = 100,
    offset: int = 0
) -> dict:
    """Read conversation turns from database (GOLD quality)."""
    return await forge.forge_read_turns(db_path, session_id, limit, offset)


# ==============================================================================
# Persona Forge Tools - Character
# ==============================================================================

@mcp.tool()
async def character_list() -> dict:
    """List available personality profiles."""
    return await forge.character_list()


@mcp.tool()
async def character_load(profile_name: str) -> dict:
    """Load a personality profile."""
    return await forge.character_load(profile_name)


@mcp.tool()
async def character_modulate(trait_name: str, delta: float) -> dict:
    """Adjust a trait in the current profile."""
    return await forge.character_modulate(trait_name, delta)


@mcp.tool()
async def character_save(path: str = None) -> dict:
    """Save current profile to disk."""
    return await forge.character_save(path)


@mcp.tool()
async def character_show() -> dict:
    """Get detailed info about current profile."""
    return await forge.character_show()


# ==============================================================================
# Persona Forge Tools - Voight-Kampff
# ==============================================================================

@mcp.tool()
async def vk_run(model_id: str, suite_name: str = "luna", verbose: bool = False) -> dict:
    """Run a Voight-Kampff test suite against a model."""
    return await forge.vk_run(model_id, suite_name, verbose)


@mcp.tool()
async def vk_list() -> dict:
    """List available Voight-Kampff test suites."""
    return await forge.vk_list()


@mcp.tool()
async def vk_probes(suite_name: str) -> dict:
    """Get the list of probes in a test suite."""
    return await forge.vk_probes(suite_name)


# ==============================================================================
# QA Tools — Luna's Self-Diagnosis
# ==============================================================================

@mcp.tool()
async def qa_get_last_report() -> str:
    """
    Get the QA report for Luna's most recent inference.

    Returns assertion results, diagnosis, and debugging info.
    Use this to understand why the last response may have failed QA.
    """
    return await qa.qa_get_last_report()


@mcp.tool()
async def qa_get_health() -> str:
    """
    Get Luna's current QA health status.

    Returns pass_rate (0-1), recent_failures, and failing_bugs count.
    """
    return await qa.qa_get_health()


@mcp.tool()
async def qa_search_reports(
    query: str = None,
    route: str = None,
    passed: bool = None,
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
    return await qa.qa_search_reports(query, route, passed, limit)


@mcp.tool()
async def qa_get_stats(time_range: str = "24h") -> str:
    """
    Get QA statistics for a time range.

    Args:
        time_range: "1h", "24h", "7d", "30d"
    """
    return await qa.qa_get_stats(time_range)


@mcp.tool()
async def qa_get_assertions() -> str:
    """Get all configured QA assertions."""
    return await qa.qa_get_assertions()


@mcp.tool()
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
        case_sensitive: Whether match is case-sensitive
    """
    return await qa.qa_add_assertion(
        name, category, severity, target, condition, pattern, case_sensitive
    )


@mcp.tool()
async def qa_toggle_assertion(assertion_id: str, enabled: bool) -> str:
    """Enable or disable a QA assertion."""
    return await qa.qa_toggle_assertion(assertion_id, enabled)


@mcp.tool()
async def qa_delete_assertion(assertion_id: str) -> str:
    """Delete a custom QA assertion (built-in assertions cannot be deleted)."""
    return await qa.qa_delete_assertion(assertion_id)


@mcp.tool()
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
        severity: critical, high, medium, low
    """
    return await qa.qa_add_bug(name, query, expected_behavior, actual_behavior, severity)


@mcp.tool()
async def qa_add_bug_from_last(name: str, expected_behavior: str) -> str:
    """
    Create a bug from the last failed QA report.

    Auto-populates query, actual behavior, and affected assertions.

    Args:
        name: Bug name/title
        expected_behavior: What should happen
    """
    return await qa.qa_add_bug_from_last(name, expected_behavior)


@mcp.tool()
async def qa_list_bugs(status: str = None) -> str:
    """
    List known bugs.

    Args:
        status: Filter by status (open, failing, fixed, wontfix)
    """
    return await qa.qa_list_bugs(status)


@mcp.tool()
async def qa_update_bug_status(bug_id: str, status: str) -> str:
    """
    Update a bug's status.

    Args:
        bug_id: The bug ID
        status: New status (open, failing, fixed, wontfix)
    """
    return await qa.qa_update_bug_status(bug_id, status)


@mcp.tool()
async def qa_get_bug(bug_id: str) -> str:
    """Get details for a specific bug by ID."""
    return await qa.qa_get_bug(bug_id)


@mcp.tool()
async def qa_diagnose_last() -> str:
    """
    Get a detailed diagnosis of the last QA failure.

    Returns failures by category, diagnosis text, and response preview.
    """
    return await qa.qa_diagnose_last()


@mcp.tool()
async def qa_check_personality() -> str:
    """
    Check if Luna's personality is properly configured.

    Returns status of P1, P2, P3 assertions and personality injection state.
    """
    return await qa.qa_check_personality()


# ==============================================================================
# Eden Tools (Creative AI — image/video generation, agent chat)
# ==============================================================================

@mcp.tool()
async def eden_create_image(
    prompt: str,
    width: int = None,
    height: int = None,
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
    return await eden.eden_create_image(prompt, width, height)


@mcp.tool()
async def eden_create_video(prompt: str) -> str:
    """
    Generate a video from a text prompt using Eden.art.

    Args:
        prompt: Text description of the video to generate

    Returns:
        JSON with task_id, status, url, and is_complete fields
    """
    return await eden.eden_create_video(prompt)


@mcp.tool()
async def eden_chat(
    message: str,
    agent_id: str = None,
    session_id: str = None,
) -> str:
    """
    Chat with an Eden agent. Creates a new session or continues an existing one.

    Args:
        message: Message to send to the agent
        agent_id: Eden agent ID (uses EDEN_AGENT_ID env var if not provided)
        session_id: Existing session ID to continue (creates new if not provided)

    Returns:
        JSON with session_id, messages, and message_count
    """
    return await eden.eden_chat(message, agent_id, session_id)


@mcp.tool()
async def eden_list_agents() -> str:
    """
    List available Eden agents.

    Returns:
        JSON with agents array and count
    """
    return await eden.eden_list_agents()


@mcp.tool()
async def eden_health() -> str:
    """
    Check Eden API connectivity and authentication.

    Returns:
        JSON with status (ok/error), api_base, and has_api_key
    """
    return await eden.eden_health()


# ==============================================================================
# Data Room Tools
# ==============================================================================

@mcp.tool()
async def dataroom_search(query: str, category: str = None, status: str = None, limit: int = 10) -> str:
    """
    Search Luna's investor data room for documents.

    Searches DOCUMENT nodes ingested from the Google Drive data room.
    Can filter by category (e.g. "2. Financials") or status ("Final", "Draft", "Needs Review").
    Requires FaceID authentication — documents are gated by the dual-tier permission bridge.

    Args:
        query: Search text (e.g. "cost breakdown", "LOI", "team")
        category: Optional category filter (e.g. "2. Financials", "3. Legal")
        status: Optional status filter ("Final", "Draft", "Needs Review")
        limit: Maximum results (default 10)

    Returns:
        Formatted list of matching documents with links
    """
    try:
        # Check FaceID identity — data room requires authentication
        try:
            status_resp = await state._call_api("GET", "/status")
            identity = status_resp.get("identity", {})
            if not identity.get("is_present"):
                return "Data room access requires FaceID authentication. Please ensure the camera can see you."
        except Exception:
            pass  # If status check fails, let the gated API handle it
        params = {"query": query, "limit": limit}
        if category:
            params["category"] = category
        if status:
            params["status"] = status

        response = await state._call_api("POST", "/dataroom/search", params=params)
        results = response.get("results", [])

        if not results:
            return f"No data room documents found for '{query}'."

        lines = [f"# Data Room Search: {query}", f"*{len(results)} documents found*", ""]
        for doc in results:
            name = doc.get("name", "Unknown")
            cat = doc.get("category", "")
            url = doc.get("url", "")
            file_type = doc.get("file_type", "")
            status_str = doc.get("status", "")
            link = f" — [Open]({url})" if url else ""
            status_tag = f" [{status_str}]" if status_str else ""
            lines.append(f"- **{name}**{status_tag} ({cat}, {file_type}){link}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error searching data room: {str(e)}"


@mcp.tool()
async def dataroom_status() -> str:
    """
    Get data room overview: total documents, coverage by category, status breakdown.

    Shows which of the 9 investor data room categories have documents
    and flags any gaps (categories with no documents).

    Returns:
        Formatted status report with category and status breakdown
    """
    try:
        response = await state._call_api("GET", "/dataroom/status")
        total = response.get("total_documents", 0)
        by_cat = response.get("by_category", {})
        by_status = response.get("by_status", {})

        all_categories = [
            "1. Company Overview", "2. Financials", "3. Legal",
            "4. Product", "5. Market & Competition", "6. Team",
            "7. Go-to-Market", "8. Partnerships & Impact", "9. Risk & Mitigation",
        ]

        lines = [
            f"# Data Room Status",
            f"**{total} documents** across {len(by_cat)} categories",
            "",
            "## By Category",
        ]

        for cat in all_categories:
            count = by_cat.get(cat, 0)
            marker = f"({count} docs)" if count > 0 else "EMPTY"
            lines.append(f"- {cat}: {marker}")

        missing = [c for c in all_categories if by_cat.get(c, 0) == 0]
        if missing:
            lines.append("")
            lines.append(f"**Missing:** {', '.join(missing)}")

        if by_status:
            lines.append("")
            lines.append("## By Status")
            for st, count in sorted(by_status.items()):
                lines.append(f"- {st}: {count}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error getting data room status: {str(e)}"


@mcp.tool()
async def dataroom_recent(days: int = 7) -> str:
    """
    Get recently synced data room documents.

    Shows documents added or updated in the last N days.
    Requires FaceID authentication.

    Args:
        days: Look back this many days (default 7)

    Returns:
        List of recently synced documents
    """
    try:
        # Check FaceID identity
        try:
            status_resp = await state._call_api("GET", "/status")
            identity = status_resp.get("identity", {})
            if not identity.get("is_present"):
                return "Data room access requires FaceID authentication. Please ensure the camera can see you."
        except Exception:
            pass
        response = await state._call_api("GET", f"/dataroom/recent?days={days}")
        docs = response.get("documents", [])

        if not docs:
            return f"No data room documents synced in the last {days} days."

        lines = [
            f"# Recently Synced ({len(docs)} documents, last {days} days)",
            "",
        ]
        for doc in docs:
            name = doc.get("name", "Unknown")
            cat = doc.get("category", "")
            synced = doc.get("synced_at", "")[:16]
            url = doc.get("url", "")
            link = f" — [Open]({url})" if url else ""
            lines.append(f"- **{name}** ({cat}) synced {synced}{link}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error getting recent documents: {str(e)}"


# ==============================================================================
# Observatory Tools — Memory Matrix diagnostics
# ==============================================================================

@mcp.tool()
async def observatory_stats() -> str:
    """
    Database health overview: node/edge/entity/mention counts, lock-in distribution, DB size.

    Returns:
        JSON with counts by type, lock-in stats, and file size
    """
    import json
    result = await observatory.tool_observatory_stats()
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def observatory_graph_dump(limit: int = 500, min_lock_in: float = 0.0) -> str:
    """
    Full graph snapshot for visualization.

    Args:
        limit: Maximum nodes to return (default 500)
        min_lock_in: Minimum lock-in threshold (default 0.0)

    Returns:
        JSON with nodes and edges arrays
    """
    import json
    result = await observatory.tool_observatory_graph_dump(limit, min_lock_in)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def observatory_search(query: str, method: str = "hybrid") -> str:
    """
    Multi-method search comparison: FTS5, vector, hybrid.

    In diagnostic mode, vector search is unavailable (requires engine runtime).
    Use luna_smart_fetch for live vector+hybrid search.

    Args:
        query: Search query
        method: "fts5", "vector", "hybrid", or "all"

    Returns:
        JSON with search results and timing
    """
    import json
    result = await observatory.tool_observatory_search(query, method)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def observatory_replay(query: str) -> str:
    """
    Trace the retrieval pipeline phase-by-phase with timing.

    Shows FTS5 results, graph neighborhood, and retrieval parameters.
    Vector and activation phases require engine runtime.

    Args:
        query: Query to trace through the pipeline

    Returns:
        JSON with phase-by-phase results and params
    """
    import json
    result = await observatory.tool_observatory_replay(query)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def observatory_tune(param: str, value: float) -> str:
    """
    Adjust a retrieval parameter. Persists to data/observatory_config.json.

    Available params: decay, min_activation, max_hops, token_budget,
    sim_threshold, fts5_limit, vector_limit, rrf_k,
    lock_in_node_weight, lock_in_access_weight, lock_in_edge_weight,
    lock_in_age_weight, cluster_sim_threshold

    Args:
        param: Parameter name
        value: New value

    Returns:
        JSON with updated params
    """
    import json
    result = await observatory.tool_observatory_tune(param, value)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def observatory_entities(
    entity_id: str = "", entity_type: str = "", limit: int = 20
) -> str:
    """
    List or inspect entities in the knowledge graph.

    With no args: lists all entities ranked by mention count.
    With entity_id: returns full detail (mentions, relationships).
    With entity_type: filters by type (person, persona, place, project).

    Args:
        entity_id: Specific entity to inspect (optional)
        entity_type: Filter by type (optional)
        limit: Max results for list mode (default 20)

    Returns:
        JSON with entity details or list
    """
    import json
    result = await observatory.tool_observatory_entities(entity_id, entity_type, limit)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def observatory_maintenance_sweep() -> str:
    """
    Scan for graph health issues. Returns quest candidates (does NOT auto-create).

    Checks: orphan entities, stale entities, fragmented profiles, drifting high-access nodes.

    Returns:
        JSON with candidate quests
    """
    import json
    result = await observatory.tool_observatory_maintenance_sweep()
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def observatory_quest_board(
    action: str = "list",
    quest_id: str = "",
    journal_text: str = "",
    status: str = "",
    quest_type: str = "",
) -> str:
    """
    Manage observatory quests: list, accept, complete, or create from sweep.

    Actions:
    - "list": List quests (optionally filter by status/quest_type)
    - "accept": Accept a quest (requires quest_id)
    - "complete": Complete a quest (requires quest_id, optional journal_text)
    - "create": Run maintenance sweep and create quests from candidates

    Args:
        action: "list", "accept", "complete", or "create"
        quest_id: Quest ID for accept/complete
        journal_text: Reflection text for completed quests
        status: Filter by status (available, active, complete)
        quest_type: Filter by type (scavenger, treasure_hunt, contract, side)

    Returns:
        JSON with action result
    """
    import json
    result = await observatory.tool_observatory_quest_board(
        action, quest_id, journal_text, status, quest_type
    )
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def observatory_quest_create(
    title: str,
    objective: str,
    quest_type: str = "side",
    priority: str = "medium",
    subtitle: str = "",
    source: str = "manual",
    journal_prompt: str = "",
    target_entity_ids: str = "[]",
    target_node_ids: str = "[]",
) -> str:
    """
    Create a quest manually.

    Args:
        title: Quest title
        objective: What needs to be done
        quest_type: Type - side, contract, main, treasure_hunt, scavenger
        priority: Priority - low, medium, high, urgent
        subtitle: Short subtitle
        source: Where this quest came from (e.g. "Luna diagnostic", "manual")
        journal_prompt: Prompt for the journal entry on completion
        target_entity_ids: JSON array of entity IDs to target (e.g. '["entity-abc"]')
        target_node_ids: JSON array of node IDs to target (e.g. '["node-xyz"]')

    Returns:
        JSON with quest_id, title, status
    """
    import json
    result = await observatory.tool_observatory_quest_create(
        title, objective, quest_type, priority, subtitle,
        source, journal_prompt, target_entity_ids, target_node_ids,
    )
    return json.dumps(result, indent=2, default=str)


# ==============================================================================
# Observatory: Entity Review Quest
# ==============================================================================


@mcp.tool()
async def observatory_entity_review_quest() -> str:
    """Check entity review queue and create a hygiene quest for pending entities.

    Reads data/entity_review_queue.json (populated by the entity creation gate)
    and creates a quest for Luna to review newly created entities. Clears the
    queue after quest creation.

    Returns:
        JSON with status, pending count, and quest_id if created
    """
    import json
    result = await observatory.tool_observatory_entity_review_quest()
    return json.dumps(result, indent=2, default=str)


# ==============================================================================
# Entry Point
# ==============================================================================

if __name__ == "__main__":
    mcp.run()
