"""
Data Room Tools for Luna Engine
=================================

Tools for querying DOCUMENT nodes ingested from the Google Drive data room.
Uses the same global _memory_matrix reference as memory_tools.

Requires: scripts/ingest_dataroom.py to have been run at least once.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from .registry import Tool
from .memory_tools import get_memory_matrix

logger = logging.getLogger(__name__)


# =============================================================================
# TOOL IMPLEMENTATIONS
# =============================================================================

async def dataroom_search(
    query: str,
    category: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """
    Search data room documents by keyword, category, or status.

    Args:
        query: Search text
        category: Optional category filter (e.g. "2. Financials")
        status: Optional status filter ("Final", "Draft", "Needs Review")
        limit: Maximum results

    Returns:
        List of matching document dicts
    """
    matrix = get_memory_matrix()
    if matrix is None:
        raise RuntimeError("Memory matrix not initialized.")

    nodes = await matrix.search_nodes(query=query, node_type="DOCUMENT", limit=limit * 3)

    results = []
    for node in nodes:
        meta = node.metadata if isinstance(node.metadata, dict) else (
            json.loads(node.metadata) if node.metadata else {}
        )

        if category and meta.get("category") != category:
            continue
        if status and meta.get("status") != status:
            continue

        results.append({
            "id": node.id,
            "name": node.summary or node.content,
            "category": meta.get("category"),
            "subfolder": meta.get("subfolder"),
            "status": meta.get("status"),
            "url": meta.get("gdrive_url"),
            "importance": node.importance,
            "tags": meta.get("tags", []),
        })

        if len(results) >= limit:
            break

    logger.debug(f"dataroom_search '{query}' → {len(results)} results")
    return results


async def dataroom_status() -> dict:
    """
    Get data room statistics: total documents, breakdown by category and status.

    Returns:
        Dict with total_documents, by_category, by_status
    """
    matrix = get_memory_matrix()
    if matrix is None:
        raise RuntimeError("Memory matrix not initialized.")

    docs = await matrix.get_nodes_by_type("DOCUMENT", limit=1000)

    category_counts = {}
    status_counts = {}

    for doc in docs:
        meta = doc.metadata if isinstance(doc.metadata, dict) else (
            json.loads(doc.metadata) if doc.metadata else {}
        )
        cat = meta.get("category", "Unknown")
        category_counts[cat] = category_counts.get(cat, 0) + 1

        st = meta.get("status", "Unknown")
        status_counts[st] = status_counts.get(st, 0) + 1

    return {
        "total_documents": len(docs),
        "by_category": category_counts,
        "by_status": status_counts,
    }


async def dataroom_recent(days: int = 7) -> list[dict]:
    """
    Get recently synced data room documents.

    Args:
        days: Look back this many days (default 7)

    Returns:
        List of recently synced document dicts, newest first
    """
    matrix = get_memory_matrix()
    if matrix is None:
        raise RuntimeError("Memory matrix not initialized.")

    docs = await matrix.get_nodes_by_type("DOCUMENT", limit=1000)
    cutoff = datetime.now() - timedelta(days=days)

    recent = []
    for doc in docs:
        meta = doc.metadata if isinstance(doc.metadata, dict) else (
            json.loads(doc.metadata) if doc.metadata else {}
        )
        last_synced = meta.get("last_synced")
        if not last_synced:
            continue

        try:
            sync_time = datetime.fromisoformat(last_synced)
        except (ValueError, TypeError):
            continue

        if sync_time >= cutoff:
            recent.append({
                "id": doc.id,
                "name": doc.summary or doc.content,
                "category": meta.get("category"),
                "status": meta.get("status"),
                "synced_at": last_synced,
                "url": meta.get("gdrive_url"),
            })

    recent.sort(key=lambda x: x["synced_at"], reverse=True)
    return recent


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

dataroom_search_tool = Tool(
    name="dataroom_search",
    description="Search the investor data room for documents by keyword, category, or status.",
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search text to find matching documents",
            },
            "category": {
                "type": "string",
                "description": "Filter by category (e.g. '2. Financials', '3. Legal')",
            },
            "status": {
                "type": "string",
                "description": "Filter by status",
                "enum": ["Final", "Draft", "Needs Review"],
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of results",
                "default": 10,
            },
        },
        "required": ["query"],
    },
    execute=dataroom_search,
    requires_confirmation=False,
    timeout_seconds=30,
)

dataroom_status_tool = Tool(
    name="dataroom_status",
    description="Get data room statistics: total documents, breakdown by category and status.",
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
    execute=dataroom_status,
    requires_confirmation=False,
    timeout_seconds=15,
)

dataroom_recent_tool = Tool(
    name="dataroom_recent",
    description="Get recently synced data room documents.",
    parameters={
        "type": "object",
        "properties": {
            "days": {
                "type": "integer",
                "description": "Look back this many days",
                "default": 7,
            },
        },
        "required": [],
    },
    execute=dataroom_recent,
    requires_confirmation=False,
    timeout_seconds=15,
)


# =============================================================================
# CONVENIENCE EXPORTS
# =============================================================================

ALL_DATAROOM_TOOLS = [
    dataroom_search_tool,
    dataroom_status_tool,
    dataroom_recent_tool,
]


def register_dataroom_tools(registry) -> None:
    """Register all data room tools with a ToolRegistry."""
    for tool in ALL_DATAROOM_TOOLS:
        registry.register(tool)
    logger.info(f"Registered {len(ALL_DATAROOM_TOOLS)} dataroom tools")
