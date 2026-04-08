"""
Observatory HTTP routes — wraps MCP tool functions as FastAPI endpoints.

Mounted at /observatory by server.py. The frontend (observatory/api.js)
calls /observatory/api/* which resolves to these handlers.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import aiosqlite
from fastapi import APIRouter, Form, HTTPException, Query
from fastapi.websockets import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from luna.core.paths import user_dir
from luna_mcp.observatory.config import RetrievalParams
from luna_mcp.observatory.tools import (
    tool_observatory_entities,
    tool_observatory_graph_dump,
    tool_observatory_maintenance_sweep,
    tool_observatory_quest_board,
    tool_observatory_replay,
    tool_observatory_stats,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/observatory", tags=["observatory"])

# ---------------------------------------------------------------------------
# Observatory WebSocket — live event stream for the frontend
# ---------------------------------------------------------------------------

_observatory_websockets: set[WebSocket] = set()


async def broadcast_observatory_event(event_data: dict) -> None:
    """Broadcast an event to all connected Observatory WebSocket clients."""
    if not _observatory_websockets:
        return
    payload = json.dumps(event_data)
    dead: set[WebSocket] = set()
    for ws in _observatory_websockets:
        try:
            await ws.send_text(payload)
        except Exception:
            dead.add(ws)
    _observatory_websockets.difference_update(dead)


@router.websocket("/ws/events")
async def observatory_events_ws(websocket: WebSocket):
    """WebSocket endpoint for Observatory live events."""
    await websocket.accept()
    _observatory_websockets.add(websocket)
    logger.info("Observatory WS connected. Total: %d", len(_observatory_websockets))

    # Subscribe to knowledge bus so extraction events flow to Observatory too
    from luna.core.event_bus import event_bus

    async def _forward(ev):
        await broadcast_observatory_event({
            "type": ev.type,
            "data": ev.payload,
            "ts": ev.timestamp,
        })

    event_bus.subscribe("knowledge", _forward)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _observatory_websockets.discard(websocket)
        # Remove the subscriber to avoid leaking callbacks
        if _forward in event_bus._subscribers.get("knowledge", []):
            event_bus._subscribers["knowledge"].remove(_forward)
        logger.info("Observatory WS disconnected. Total: %d", len(_observatory_websockets))


# ---------------------------------------------------------------------------
# DB helpers (mirrors tools.py private helpers)
# ---------------------------------------------------------------------------

DB_PATH = user_dir() / "luna_engine.db"


@asynccontextmanager
async def _readonly_db():
    db = await aiosqlite.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA busy_timeout=15000")
    try:
        yield db
    finally:
        await db.close()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class QuestCompleteBody(BaseModel):
    journal_text: str = ""
    themes: list = []


# ===========================================================================
# Direct MCP wrappers (11 endpoints)
# ===========================================================================

@router.get("/api/stats")
async def stats():
    return await tool_observatory_stats()


@router.get("/api/graph-dump")
async def graph_dump(
    limit: int = Query(500),
    min_lock_in: float = Query(0.0),
):
    return await tool_observatory_graph_dump(limit, min_lock_in)


@router.post("/api/replay")
async def replay(query: str = Form(...)):
    return await tool_observatory_replay(query)


@router.get("/api/entities")
async def entities(
    type: Optional[str] = Query(None),
    project: Optional[str] = Query(None),
    limit: int = Query(20),
):
    return await tool_observatory_entities(
        entity_type=type or "", limit=limit,
    )


@router.get("/api/entities/{entity_id}")
async def entity_detail(entity_id: str):
    return await tool_observatory_entities(entity_id=entity_id)


@router.get("/api/quests")
async def quests(
    status: Optional[str] = Query(None),
    type: Optional[str] = Query(None),
    project: Optional[str] = Query(None),
):
    return await tool_observatory_quest_board(
        action="list",
        status=status or "",
        quest_type=type or "",
        project=project or "",
    )


@router.get("/api/quests/{quest_id}")
async def quest_detail(quest_id: str):
    return await tool_observatory_quest_board(action="list", quest_id=quest_id)


@router.post("/api/quests/{quest_id}/accept")
async def quest_accept(quest_id: str):
    return await tool_observatory_quest_board(action="accept", quest_id=quest_id)


@router.post("/api/quests/{quest_id}/complete")
async def quest_complete(quest_id: str, body: QuestCompleteBody = QuestCompleteBody()):
    return await tool_observatory_quest_board(
        action="complete",
        quest_id=quest_id,
        journal_text=body.journal_text,
    )


@router.post("/api/maintenance-sweep")
async def maintenance_sweep():
    return await tool_observatory_maintenance_sweep()


@router.get("/api/config")
async def config():
    return RetrievalParams.load().to_dict()


# ===========================================================================
# New SQL endpoints (6 + 1 stub)
# ===========================================================================

@router.get("/api/events/recent")
async def events_recent(
    n: int = Query(50),
    type_filter: Optional[str] = Query(None),
):
    if not DB_PATH.exists():
        return {"events": []}
    async with _readonly_db() as db:
        q = "SELECT id, node_type, content, lock_in, created_at FROM memory_nodes"
        params: list = []
        if type_filter:
            q += " WHERE node_type = ?"
            params.append(type_filter)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(n)
        cursor = await db.execute(q, params)
        rows = await cursor.fetchall()
    return {"events": [dict(r) for r in rows]}


@router.get("/api/zoom/universe")
async def zoom_universe():
    if not DB_PATH.exists():
        return {"clusters": [], "edges": []}
    try:
        async with _readonly_db() as db:
            cursor = await db.execute(
                "SELECT cluster_id, name, summary, lock_in, state, member_count, "
                "avg_node_lock_in FROM clusters ORDER BY lock_in DESC"
            )
            clusters = [dict(r) for r in await cursor.fetchall()]
            cursor = await db.execute(
                "SELECT from_cluster, to_cluster, relationship, strength "
                "FROM cluster_edges"
            )
            edges = [dict(r) for r in await cursor.fetchall()]
        return {"clusters": clusters, "edges": edges}
    except Exception:
        return {"clusters": [], "edges": []}


@router.get("/api/zoom/galaxy")
async def zoom_galaxy(
    cluster_id: str = Query(...),
    limit: int = Query(200),
):
    if not DB_PATH.exists():
        return {"nodes": [], "edges": [], "focus_cluster": None}
    try:
        async with _readonly_db() as db:
            # Fetch cluster metadata for the label/breadcrumb
            focus_cluster = None
            try:
                cursor = await db.execute(
                    "SELECT cluster_id, name, summary, lock_in, state, "
                    "member_count, avg_node_lock_in FROM clusters "
                    "WHERE cluster_id = ?",
                    (cluster_id,),
                )
                row = await cursor.fetchone()
                if row:
                    focus_cluster = dict(row)
                    focus_cluster["label"] = focus_cluster.get("name") or cluster_id
            except Exception:
                pass  # clusters table may not exist

            cursor = await db.execute(
                "SELECT mn.id, mn.node_type AS type, mn.content, mn.lock_in "
                "FROM cluster_members cm "
                "JOIN memory_nodes mn ON cm.node_id = mn.id "
                "WHERE cm.cluster_id = ? "
                "ORDER BY mn.lock_in DESC LIMIT ?",
                (cluster_id, limit),
            )
            nodes = [dict(r) for r in await cursor.fetchall()]
            if nodes:
                ids = [n["id"] for n in nodes]
                placeholders = ",".join("?" * len(ids))
                cursor = await db.execute(
                    f"SELECT from_id, to_id, relationship, strength "
                    f"FROM graph_edges "
                    f"WHERE from_id IN ({placeholders}) AND to_id IN ({placeholders})",
                    ids + ids,
                )
                edges = [dict(r) for r in await cursor.fetchall()]
            else:
                edges = []
        return {
            "nodes": nodes,
            "edges": edges,
            "focus_cluster": focus_cluster or {"label": cluster_id},
        }
    except Exception:
        return {"nodes": [], "edges": [], "focus_cluster": {"label": cluster_id}}


@router.get("/api/zoom/solarsystem")
async def zoom_solarsystem(node_id: str = Query(...)):
    if not DB_PATH.exists():
        return {"focus_node": None, "edges": [], "neighbors": []}
    async with _readonly_db() as db:
        cursor = await db.execute(
            "SELECT id, node_type, content, lock_in, lock_in_state, scope, "
            "metadata, created_at FROM memory_nodes WHERE id = ?",
            (node_id,),
        )
        node_row = await cursor.fetchone()
        if not node_row:
            return {"focus_node": None, "edges": [], "neighbors": []}
        focus_node = dict(node_row)
        # Normalize type field for frontend
        focus_node["type"] = focus_node.pop("node_type", "OBSERVATION")

        cursor = await db.execute(
            "SELECT ge.from_id, ge.to_id, ge.relationship, ge.strength, "
            "mn.id AS neighbor_id, mn.node_type AS neighbor_type, "
            "mn.content AS neighbor_content, mn.lock_in AS neighbor_lock_in, "
            "mn.lock_in_state AS neighbor_lock_in_state "
            "FROM graph_edges ge "
            "JOIN memory_nodes mn ON "
            "  (CASE WHEN ge.from_id = ? THEN ge.to_id ELSE ge.from_id END) = mn.id "
            "WHERE ge.from_id = ? OR ge.to_id = ?",
            (node_id, node_id, node_id),
        )
        raw_edges = await cursor.fetchall()

        # Build deduplicated neighbors list and clean edge list
        seen_neighbors: dict = {}
        edges = []
        for r in raw_edges:
            edges.append({
                "from_id": r["from_id"],
                "to_id": r["to_id"],
                "relationship": r["relationship"],
                "strength": r["strength"] or 0.5,
            })
            nid = r["neighbor_id"]
            if nid not in seen_neighbors:
                seen_neighbors[nid] = {
                    "id": nid,
                    "type": r["neighbor_type"],
                    "content": (r["neighbor_content"] or "")[:200],
                    "lock_in": r["neighbor_lock_in"] or 0,
                    "lock_in_state": r["neighbor_lock_in_state"] or "drifting",
                }

    return {
        "focus_node": focus_node,
        "neighbors": list(seen_neighbors.values()),
        "edges": edges,
    }


@router.get("/api/threads")
async def threads(
    status: Optional[str] = Query(None),
    project: Optional[str] = Query(None),
):
    if not DB_PATH.exists():
        return {"threads": []}
    async with _readonly_db() as db:
        q = (
            "SELECT id, content, lock_in, metadata, created_at "
            "FROM memory_nodes WHERE node_type = 'THREAD'"
        )
        params: list = []
        if status:
            q += " AND json_extract(content, '$.status') = ?"
            params.append(status)
        if project:
            q += " AND json_extract(content, '$.project_slug') = ?"
            params.append(project)
        q += " ORDER BY created_at DESC LIMIT 100"
        cursor = await db.execute(q, params)
        rows = await cursor.fetchall()
    results = []
    for r in rows:
        row = dict(r)
        # Parse the thread data from the content JSON string
        try:
            thread_data = json.loads(row.get("content", "{}"))
        except (json.JSONDecodeError, TypeError):
            thread_data = {}
        # Merge thread fields (topic, status, entities, etc.) into top level
        thread_data["id"] = row["id"]
        thread_data["lock_in"] = row.get("lock_in")
        thread_data["created_at"] = row.get("created_at")
        results.append(thread_data)
    return {"threads": results}


def _parse_journal_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from a journal markdown file.

    Returns (metadata_dict, body_text).
    """
    import yaml as _yaml

    meta: dict = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                meta = _yaml.safe_load(parts[1]) or {}
            except Exception:
                meta = {}
            body = parts[2].strip()
    return meta, body


def _journal_summary(path: Path) -> dict:
    """Build a list-level summary dict for a journal file."""
    raw = path.read_text()
    meta, body = _parse_journal_frontmatter(raw)
    # Derive slug from filename: 2025-12-28_012_time-pink-floyd.md → time-pink-floyd
    stem = path.stem  # e.g. "2025-12-28_012_time-pink-floyd"
    parts = stem.split("_", 2)
    slug = parts[2] if len(parts) >= 3 else stem
    # Title: frontmatter 'prompt' field, or first H1 in body, or slug
    title = meta.get("prompt") or meta.get("title") or ""
    if not title:
        for line in body.splitlines():
            if line.startswith("# "):
                title = line.lstrip("# ").strip()
                break
    return {
        "filename": path.name,
        "date": meta.get("date", parts[0] if len(parts) >= 1 else ""),
        "entry": meta.get("entry", int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0),
        "title": title,
        "slug": slug,
        "song": meta.get("symphony") or meta.get("song") or "",
        "resonance": meta.get("resonance", ""),
        "size": path.stat().st_size,
        "modified": path.stat().st_mtime,
    }


@router.get("/api/journals")
async def journals():
    journal_dir = user_dir() / "journal"
    if not journal_dir.exists():
        return {"journals": []}
    files = sorted(
        journal_dir.glob("*.md"),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )
    return {
        "journals": [_journal_summary(f) for f in files]
    }


@router.get("/api/journals/{filename}")
async def journal_detail(filename: str):
    if ".." in filename or "/" in filename:
        raise HTTPException(400, "Invalid filename")
    path = user_dir() / "journal" / filename
    resolved = path.resolve()
    if not str(resolved).startswith(str((user_dir() / "journal").resolve())):
        raise HTTPException(400, "Invalid filename")
    if not path.exists():
        raise HTTPException(404, "Journal not found")
    raw = path.read_text()
    meta, body = _parse_journal_frontmatter(raw)
    stem = path.stem
    parts = stem.split("_", 2)
    slug = parts[2] if len(parts) >= 3 else stem
    title = meta.get("prompt") or meta.get("title") or ""
    if not title:
        for line in body.splitlines():
            if line.startswith("# "):
                title = line.lstrip("# ").strip()
                break
    return {
        "filename": filename,
        "date": meta.get("date", parts[0] if len(parts) >= 1 else ""),
        "entry": meta.get("entry", int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0),
        "title": title,
        "slug": slug,
        "song": meta.get("symphony") or meta.get("song") or "",
        "resonance": meta.get("resonance", ""),
        "body": body,
    }


@router.post("/api/layout/recompute")
async def layout_recompute():
    return {"ok": True}
