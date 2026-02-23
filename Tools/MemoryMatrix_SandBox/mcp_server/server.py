"""Observatory MCP Server — dual-mode: MCP (default) + HTTP/WS on :8100."""

import asyncio
import json
import os
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from mcp.server.fastmcp import FastMCP

from .event_bus import EventBus, MemoryEvent
from .sandbox_matrix import SandboxMatrix
from .config import RetrievalParams
from . import tools as tool_fns

# ── Shared State ──────────────────────────────────────────────

bus = EventBus()
matrix = SandboxMatrix(bus)

# ── FastMCP Setup ─────────────────────────────────────────────

mcp = FastMCP(
    "Observatory-Sandbox",
    instructions="Memory Matrix Observatory — sandboxed prototyping tool",
)


@mcp.tool()
async def sandbox_reset() -> str:
    """Wipe the sandbox database completely. All data cleared."""
    if _is_production:
        return json.dumps({"error": "Cannot reset production database"})
    result = await tool_fns.tool_sandbox_reset(matrix)
    return json.dumps(result, indent=2)


@mcp.tool()
async def sandbox_seed(preset: str = "small_graph") -> str:
    """Load a preset dataset (small_graph, stress_test, pathological). Resets first."""
    if _is_production:
        return json.dumps({"error": "Cannot seed production database"})
    result = await tool_fns.tool_sandbox_seed(matrix, preset)
    return json.dumps(result, indent=2)


@mcp.tool()
async def sandbox_add_node(
    type: str, content: str, confidence: float = 1.0, tags: str = "[]"
) -> str:
    """Create a new memory node. Tags is a JSON array string."""
    tag_list = json.loads(tags) if isinstance(tags, str) else tags
    result = await tool_fns.tool_sandbox_add_node(matrix, type, content, confidence, tag_list)
    return json.dumps(result, indent=2)


@mcp.tool()
async def sandbox_add_edge(
    from_id: str, to_id: str, relationship: str, strength: float = 1.0
) -> str:
    """Create an edge between two nodes."""
    result = await tool_fns.tool_sandbox_add_edge(matrix, from_id, to_id, relationship, strength)
    return json.dumps(result, indent=2)


@mcp.tool()
async def sandbox_search(query: str, method: str = "hybrid") -> str:
    """Search the sandbox. Methods: fts5, vector, hybrid, all."""
    result = await tool_fns.tool_sandbox_search(matrix, query, method)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def sandbox_recall(query: str) -> str:
    """Full retrieval pipeline: search → activate → assemble constellation."""
    result = await tool_fns.tool_sandbox_recall(matrix, query)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def sandbox_replay(query: str) -> str:
    """Full pipeline with detailed trace of every phase (FTS5→Vector→Fusion→Activation→Assembly)."""
    result = await tool_fns.tool_sandbox_replay(matrix, query)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def sandbox_graph_dump(limit: int = 500, min_lock_in: float = 0.0) -> str:
    """Full graph snapshot (nodes, edges, clusters) for visualization."""
    result = await tool_fns.tool_sandbox_graph_dump(matrix, limit, min_lock_in)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def sandbox_stats() -> str:
    """Database statistics: node/edge/cluster counts, type and lock-in distributions."""
    result = await tool_fns.tool_sandbox_stats(matrix)
    return json.dumps(result, indent=2)


@mcp.tool()
async def sandbox_tune(param: str, value: float) -> str:
    """Adjust a retrieval parameter. Persists to sandbox_config.json."""
    result = await tool_fns.tool_sandbox_tune(matrix, param, value)
    return json.dumps(result, indent=2)


# ── Entity & Quest MCP Tools ──────────────────────────────────────


@mcp.tool()
async def sandbox_add_entity(
    type: str,
    name: str,
    profile: str = "",
    aliases: str = "[]",
    avatar: str = "",
    core_facts: str = "{}",
    voice_config: str = "",
) -> str:
    """Create a new entity (person, persona, place, project)."""
    aliases_list = json.loads(aliases) if aliases else []
    core_facts_dict = json.loads(core_facts) if core_facts else {}
    voice_config_dict = json.loads(voice_config) if voice_config else None
    result = await tool_fns.tool_sandbox_add_entity(
        matrix, type, name, profile or None, aliases_list, avatar, core_facts_dict, voice_config_dict
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def sandbox_add_entity_relationship(
    from_id: str, to_id: str, rel_type: str, strength: float = 1.0, context: str = ""
) -> str:
    """Create a relationship between two entities."""
    result = await tool_fns.tool_sandbox_add_entity_relationship(
        matrix, from_id, to_id, rel_type, strength, context or None
    )
    return json.dumps(result, indent=2)


@mcp.tool()
async def sandbox_link_mention(
    entity_id: str, node_id: str, mention_type: str = "reference"
) -> str:
    """Link a knowledge node to an entity."""
    result = await tool_fns.tool_sandbox_link_mention(matrix, entity_id, node_id, mention_type)
    return json.dumps(result, indent=2)


@mcp.tool()
async def sandbox_maintenance_sweep() -> str:
    """Run maintenance sweep to generate quest candidates from graph health analysis."""
    result = await tool_fns.tool_sandbox_maintenance_sweep(matrix)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def sandbox_quest_accept(quest_id: str) -> str:
    """Accept a quest (mark as active)."""
    result = await tool_fns.tool_sandbox_quest_accept(matrix, quest_id)
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def sandbox_quest_complete(
    quest_id: str, journal_text: str = "", themes: str = "[]"
) -> str:
    """Complete a quest, optionally with journal reflection."""
    themes_list = json.loads(themes) if themes else []
    result = await tool_fns.tool_sandbox_quest_complete(
        matrix, quest_id, journal_text or None, themes_list
    )
    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def sandbox_quest_list(status: str = "", quest_type: str = "") -> str:
    """List quests with optional filters."""
    result = await tool_fns.tool_sandbox_quest_list(
        matrix, status or None, quest_type or None
    )
    return json.dumps(result, indent=2, default=str)


# ── FastAPI HTTP + WebSocket Server ───────────────────────────

app = FastAPI(title="Observatory Sandbox API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket clients
ws_clients: set[WebSocket] = set()


async def broadcast_event(event: MemoryEvent):
    """Broadcast event to all connected WebSocket clients."""
    data = event.to_json()
    disconnected = set()
    for ws in ws_clients:
        try:
            await ws.send_text(data)
        except Exception:
            disconnected.add(ws)
    ws_clients -= disconnected


# Subscribe event bus to broadcast
bus.subscribe(broadcast_event)


import sqlite3 as _sqlite3

from .layout import compute_cluster_layout, invalidate_cache as invalidate_layout
from .auto_cluster import ensure_cluster_tables, auto_cluster_from_db, needs_auto_cluster

# ── DB path tracking (updated on switch-db) ────────────────────
_production_db = str(Path(__file__).resolve().parent.parent.parent.parent / "data" / "luna_engine.db")
_sandbox_db = str(Path(__file__).parent.parent / "sandbox_matrix.db")
_current_db_path: str = _production_db if Path(_production_db).exists() else _sandbox_db
_is_production: bool = Path(_production_db).exists()


def _get_table_names() -> dict:
    """Return correct table/column names based on current DB mode."""
    if _is_production:
        return {
            "nodes": "memory_nodes",
            "edges": "graph_edges",
            "type_col": "node_type",
            # Entity column mappings
            "entity_type_col": "entity_type",
            "entity_rel_from": "from_entity",
            "entity_rel_to": "to_entity",
            "entity_rel_type": "relationship",
            "entity_profile": "full_profile",
        }
    return {
        "nodes": "nodes",
        "edges": "edges",
        "type_col": "type",
        # Entity column mappings
        "entity_type_col": "type",
        "entity_rel_from": "from_id",
        "entity_rel_to": "to_id",
        "entity_rel_type": "rel_type",
        "entity_profile": "profile",
    }


def _sync_db():
    """Get a sync sqlite3 connection for HTTP thread reads."""
    conn = _sqlite3.connect(_current_db_path)
    conn.row_factory = _sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


@app.get("/api/graph-dump")
async def api_graph_dump(limit: int = 500, min_lock_in: float = 0.0):
    tn = _get_table_names()
    conn = _sync_db()
    try:
        # Detect available columns (production lacks tags/cluster_id)
        cols = {r[1] for r in conn.execute(f"PRAGMA table_info({tn['nodes']})").fetchall()}
        select_parts = [
            "id",
            f"{tn['type_col']} as type",
            "content",
            "confidence",
            "lock_in",
        ]
        for col in ("access_count", "cluster_id", "tags", "created_at", "updated_at"):
            if col in cols:
                select_parts.append(col)
        col_str = ", ".join(select_parts)

        nodes = [dict(r) for r in conn.execute(
            f"SELECT {col_str} FROM {tn['nodes']} WHERE lock_in >= ? ORDER BY lock_in DESC LIMIT ?",
            (min_lock_in, limit)
        ).fetchall()]
        node_ids = {n["id"] for n in nodes}
        edges = [dict(r) for r in conn.execute(
            f"SELECT from_id, to_id, relationship, strength FROM {tn['edges']}"
        ).fetchall()]
        # Filter edges to only include those connecting visible nodes
        edges = [e for e in edges if e["from_id"] in node_ids and e["to_id"] in node_ids]
        # Detect cluster PK column name (sandbox: 'id', production: 'cluster_id')
        cluster_cols = {r[1] for r in conn.execute("PRAGMA table_info(clusters)").fetchall()}
        cpk = "cluster_id" if "cluster_id" in cluster_cols else "id"
        clusters_raw = conn.execute(
            f"SELECT {cpk} as id, name, lock_in, state, created_at, updated_at FROM clusters"
        ).fetchall()
        clusters = []
        for c in clusters_raw:
            cd = dict(c)
            # Alias 'name' → 'label' for frontend compatibility
            cd["label"] = cd.pop("name")
            members = conn.execute(
                "SELECT node_id FROM cluster_members WHERE cluster_id = ?", (cd["id"],)
            ).fetchall()
            cd["member_ids"] = [m["node_id"] for m in members]
            clusters.append(cd)
        return {"nodes": nodes, "edges": edges, "clusters": clusters}
    finally:
        conn.close()


@app.get("/api/stats")
async def api_stats():
    tn = _get_table_names()
    conn = _sync_db()
    try:
        node_count = conn.execute(f"SELECT count(*) FROM {tn['nodes']}").fetchone()[0]
        edge_count = conn.execute(f"SELECT count(*) FROM {tn['edges']}").fetchone()[0]
        cluster_count = conn.execute("SELECT count(*) FROM clusters").fetchone()[0]
        types = {}
        for r in conn.execute(f"SELECT {tn['type_col']}, count(*) as c FROM {tn['nodes']} GROUP BY {tn['type_col']}"):
            types[r[0]] = r[1]
        lock_dist = {"drifting": 0, "fluid": 0, "settled": 0, "crystallized": 0}
        for r in conn.execute(f"SELECT lock_in FROM {tn['nodes']}"):
            v = r[0]
            if v >= 0.85: lock_dist["crystallized"] += 1
            elif v >= 0.70: lock_dist["settled"] += 1
            elif v >= 0.20: lock_dist["fluid"] += 1
            else: lock_dist["drifting"] += 1
        return {"node_count": node_count, "edge_count": edge_count, "cluster_count": cluster_count,
                "type_distribution": types, "lock_in_distribution": lock_dist}
    finally:
        conn.close()


# ── Entity & Quest HTTP Endpoints ────────────────────────────────


@app.get("/api/entities")
async def api_entities(type: str = Query(default=None)):
    """Get all entities, optionally filtered by type."""
    tn = _get_table_names()
    conn = _sync_db()
    try:
        if type:
            rows = conn.execute(
                f"SELECT * FROM entities WHERE {tn['entity_type_col']} = ? ORDER BY name", (type,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM entities ORDER BY name").fetchall()

        entities = []
        for r in rows:
            entity = dict(r)
            # Normalize column names for frontend
            if _is_production:
                entity.setdefault("type", entity.pop("entity_type", None))
                entity.setdefault("profile", entity.pop("full_profile", None))
            # Get relationship counts
            rel_count = conn.execute(
                f"SELECT COUNT(*) FROM entity_relationships WHERE {tn['entity_rel_from']} = ? OR {tn['entity_rel_to']} = ?",
                (entity["id"], entity["id"]),
            ).fetchone()[0]
            entity["relationship_count"] = rel_count
            entities.append(entity)

        return {"entities": entities, "count": len(entities)}
    finally:
        conn.close()


@app.get("/api/entities/{entity_id}")
async def api_entity_detail(entity_id: str):
    """Get entity detail with relationships, mentions, versions, and quests."""
    tn = _get_table_names()
    conn = _sync_db()
    try:
        # Entity
        entity = conn.execute("SELECT * FROM entities WHERE id = ?", (entity_id,)).fetchone()
        if not entity:
            return {"error": "Entity not found"}, 404
        entity_dict = dict(entity)
        # Normalize column names for frontend
        if _is_production:
            entity_dict.setdefault("type", entity_dict.pop("entity_type", None))
            entity_dict.setdefault("profile", entity_dict.pop("full_profile", None))

        # Relationships
        relationships = [dict(r) for r in conn.execute(
            f"SELECT * FROM entity_relationships WHERE {tn['entity_rel_from']} = ? OR {tn['entity_rel_to']} = ?",
            (entity_id, entity_id),
        ).fetchall()]
        # Normalize relationship column names for frontend
        if _is_production:
            for rel in relationships:
                rel.setdefault("from_id", rel.pop("from_entity", None))
                rel.setdefault("to_id", rel.pop("to_entity", None))
                rel.setdefault("rel_type", rel.get("relationship"))

        # Mentions (with node details)
        mentions = [dict(r) for r in conn.execute(
            f"SELECT em.*, n.{tn['type_col']} as type, n.content, n.lock_in FROM entity_mentions em "
            f"JOIN {tn['nodes']} n ON em.node_id = n.id WHERE em.entity_id = ? ORDER BY n.lock_in DESC",
            (entity_id,),
        ).fetchall()]

        # Versions
        versions = [dict(r) for r in conn.execute(
            "SELECT * FROM entity_versions WHERE entity_id = ? ORDER BY version DESC",
            (entity_id,),
        ).fetchall()]

        # Quests targeting this entity
        quests = [dict(r) for r in conn.execute(
            "SELECT q.* FROM quests q "
            "JOIN quest_targets qt ON q.id = qt.quest_id "
            "WHERE qt.target_type = 'entity' AND qt.target_id = ?",
            (entity_id,),
        ).fetchall()]

        return {
            "entity": entity_dict,
            "relationships": relationships,
            "mentions": mentions,
            "versions": versions,
            "quests": quests,
        }
    finally:
        conn.close()


@app.get("/api/quests")
async def api_quests(status: str = Query(default=None), type: str = Query(default=None)):
    """Get all quests, optionally filtered by status or type."""
    conn = _sync_db()
    try:
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if type:
            conditions.append("type = ?")
            params.append(type)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM quests WHERE {where_clause} ORDER BY created_at DESC"

        quests = [dict(r) for r in conn.execute(sql, params).fetchall()]

        # Add targets to each quest
        for quest in quests:
            targets = [dict(r) for r in conn.execute(
                "SELECT target_type, target_id FROM quest_targets WHERE quest_id = ?",
                (quest["id"],),
            ).fetchall()]
            quest["targets"] = targets

        return {"quests": quests, "count": len(quests)}
    finally:
        conn.close()


@app.get("/api/quests/{quest_id}")
async def api_quest_detail(quest_id: str):
    """Get quest detail with targets and journal entries."""
    conn = _sync_db()
    try:
        quest = conn.execute("SELECT * FROM quests WHERE id = ?", (quest_id,)).fetchone()
        if not quest:
            return {"error": "Quest not found"}
        quest_dict = dict(quest)

        # Targets
        targets = [dict(r) for r in conn.execute(
            "SELECT target_type, target_id FROM quest_targets WHERE quest_id = ?",
            (quest_id,),
        ).fetchall()]
        quest_dict["targets"] = targets

        # Journal entries
        journal = [dict(r) for r in conn.execute(
            "SELECT * FROM quest_journal WHERE quest_id = ? ORDER BY created_at DESC",
            (quest_id,),
        ).fetchall()]
        quest_dict["journal_entries"] = journal

        return quest_dict
    finally:
        conn.close()


@app.post("/api/maintenance-sweep")
async def api_maintenance_sweep():
    """Trigger maintenance sweep to generate quests."""
    if _is_production:
        # Use production observatory tools directly (correct column names)
        from luna_mcp.observatory.tools import (
            tool_observatory_maintenance_sweep,
            tool_observatory_quest_board,
        )
        # Run sweep, then create quests from candidates
        result = await tool_observatory_quest_board(action="create")
        return result
    result = await tool_fns.tool_sandbox_maintenance_sweep(matrix)
    return result


@app.post("/api/quests/{quest_id}/accept")
async def api_quest_accept(quest_id: str):
    """Accept a quest (mark as active)."""
    if _is_production:
        conn = _sync_db()
        try:
            conn.execute(
                "UPDATE quests SET status = 'active', updated_at = datetime('now') WHERE id = ?",
                (quest_id,),
            )
            conn.commit()
            return {"status": "ok", "quest_id": quest_id, "action": "accept"}
        finally:
            conn.close()
    result = await tool_fns.tool_sandbox_quest_accept(matrix, quest_id)
    return result


@app.post("/api/quests/{quest_id}/complete")
async def api_quest_complete(quest_id: str, body: dict):
    """Complete a quest with optional journal."""
    if _is_production:
        journal_text = body.get("journal_text")
        themes = body.get("themes", [])
        conn = _sync_db()
        try:
            conn.execute(
                "UPDATE quests SET status = 'complete', completed_at = datetime('now'), "
                "updated_at = datetime('now') WHERE id = ?",
                (quest_id,),
            )
            if journal_text:
                import json as _json
                conn.execute(
                    "INSERT INTO quest_journal (quest_id, content, themes, created_at) "
                    "VALUES (?, ?, ?, datetime('now'))",
                    (quest_id, journal_text, _json.dumps(themes)),
                )
            conn.commit()
            result = {"status": "ok", "quest_id": quest_id, "action": "complete"}
            if journal_text:
                result["journal"] = "saved"
            return result
        finally:
            conn.close()
    journal_text = body.get("journal_text")
    themes = body.get("themes", [])
    result = await tool_fns.tool_sandbox_quest_complete(matrix, quest_id, journal_text, themes)
    return result


@app.get("/api/threads")
async def api_threads(status: str = Query(default=None)):
    """Get THREAD nodes from Memory Matrix, parsed from JSON content."""
    tn = _get_table_names()
    conn = _sync_db()
    try:
        conditions = [f"{tn['type_col']} = 'THREAD'"]
        params = []
        if status:
            # Status is stored inside the JSON content, so we filter after parsing
            pass

        rows = conn.execute(
            f"SELECT id, content, lock_in, created_at, updated_at "
            f"FROM {tn['nodes']} WHERE {tn['type_col']} = 'THREAD' "
            f"ORDER BY updated_at DESC LIMIT 100"
        ).fetchall()

        threads = []
        for r in rows:
            row = dict(r)
            # Parse the JSON content blob (Thread.to_dict() output)
            try:
                thread_data = json.loads(row["content"] or "{}")
            except (json.JSONDecodeError, TypeError):
                thread_data = {}

            # Merge DB fields with parsed thread data
            thread = {
                "id": thread_data.get("id", row["id"]),
                "topic": thread_data.get("topic", ""),
                "status": thread_data.get("status", "active"),
                "entities": thread_data.get("entities", []),
                "entity_node_ids": thread_data.get("entity_node_ids", []),
                "open_tasks": thread_data.get("open_tasks", []),
                "turn_count": thread_data.get("turn_count", 0),
                "resume_count": thread_data.get("resume_count", 0),
                "started_at": thread_data.get("started_at", row["created_at"]),
                "parked_at": thread_data.get("parked_at"),
                "resumed_at": thread_data.get("resumed_at"),
                "closed_at": thread_data.get("closed_at"),
                "project_slug": thread_data.get("project_slug"),
                "parent_thread_id": thread_data.get("parent_thread_id"),
                "lock_in": row["lock_in"],
                "node_id": row["id"],
            }

            # Apply status filter (stored inside JSON, not a SQL column)
            if status and thread["status"] != status:
                continue

            # Get INVOLVES edges to find connected entities
            involves = conn.execute(
                f"SELECT to_id FROM {tn['edges']} "
                f"WHERE from_id = ? AND relationship = 'INVOLVES'",
                (row["id"],),
            ).fetchall()
            thread["involves_node_ids"] = [e["to_id"] for e in involves]

            threads.append(thread)

        return {"threads": threads, "count": len(threads)}
    finally:
        conn.close()


@app.get("/api/events/recent")
async def api_events_recent(n: int = Query(default=50), type_filter: str = Query(default=None)):
    return bus.recent(n=n, type_filter=type_filter)


@app.get("/api/config")
async def api_config():
    return RetrievalParams.load().to_dict()


@app.get("/api/mode")
async def api_mode():
    """Return current DB mode and path."""
    return {"mode": "production" if _is_production else "sandbox", "db_path": _current_db_path}


@app.post("/api/switch-db")
async def api_switch_db(body: dict):
    """Switch the backing database between sandbox and production."""
    global matrix, _current_db_path, _is_production
    target = body.get("db", "sandbox")
    if target == "production":
        db_path = Path(__file__).resolve().parent.parent.parent.parent / "data" / "luna_engine.db"
        _is_production = True
    else:
        target = "sandbox"
        db_path = Path(__file__).resolve().parent.parent / "sandbox_matrix.db"
        _is_production = False
    if matrix._db is not None:
        await matrix._db.close()
    _current_db_path = str(db_path)
    matrix = SandboxMatrix(bus, db_path=db_path, skip_schema=_is_production)
    await matrix.initialize()

    # For production: ensure cluster tables exist + auto-cluster if empty
    if _is_production and needs_auto_cluster(_current_db_path):
        ensure_cluster_tables(_current_db_path)
        cluster_count = auto_cluster_from_db(
            _current_db_path,
            edges_table="graph_edges",
            nodes_table="memory_nodes",
        )
    else:
        cluster_count = None

    # Recompute layout cache for new DB
    invalidate_layout()
    compute_cluster_layout(_current_db_path, _get_table_names())

    result = {"status": "ok", "db": target, "path": str(db_path)}
    if cluster_count is not None:
        result["auto_clustered"] = cluster_count
    return result


@app.post("/api/replay")
async def api_replay(query: str):
    # Replay needs async matrix — run in main loop via thread-safe bridge
    # For now return error suggesting MCP tool
    return {"error": "Use sandbox_replay MCP tool for replay traces (HTTP replay requires async bridge)"}


# ── Semantic Zoom Endpoints ─────────────────────────────────────


@app.get("/api/zoom/universe")
async def api_zoom_universe():
    """Universe view: cluster-level overview with pre-computed positions."""
    tn = _get_table_names()

    # Auto-cluster if no clusters exist yet but there are nodes
    conn_check = _sync_db()
    try:
        total = conn_check.execute(f"SELECT COUNT(*) FROM {tn['nodes']}").fetchone()[0]
        has_cm = conn_check.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='clusters'"
        ).fetchone()
        cluster_count = 0
        if has_cm:
            cluster_count = conn_check.execute("SELECT COUNT(*) FROM clusters").fetchone()[0]
    finally:
        conn_check.close()

    if total > 0 and cluster_count == 0:
        ensure_cluster_tables(_current_db_path, nodes_table=tn["nodes"])
        created = auto_cluster_from_db(
            _current_db_path,
            edges_table=tn["edges"],
            nodes_table=tn["nodes"],
        )
        if created > 0:
            invalidate_layout()
            print(f"[zoom/universe] Auto-clustered {created} communities from {total} nodes")

    layout = compute_cluster_layout(_current_db_path, tn)

    conn = _sync_db()
    try:
        # Total node count
        total_nodes = conn.execute(f"SELECT COUNT(*) FROM {tn['nodes']}").fetchone()[0]

        # Count unclustered nodes (via cluster_members table)
        unclustered = conn.execute(
            f"SELECT COUNT(*) FROM {tn['nodes']} n "
            f"WHERE NOT EXISTS (SELECT 1 FROM cluster_members cm WHERE cm.node_id = n.id)"
        ).fetchone()[0]

        clusters = []
        for cid, data in layout.items():
            clusters.append({
                "id": cid,
                "label": data["label"],
                "x": data["x"],
                "y": data["y"],
                "node_count": data["node_count"],
                "avg_lock_in": data["avg_lock_in"],
                "lock_in": data["lock_in"],
                "state": data["state"],
                "top_types": data["top_types"],
                "inter_cluster_edges": data["inter_cluster_edges"],
            })

        return {
            "clusters": clusters,
            "unclustered_count": unclustered,
            "total_nodes": total_nodes,
            "total_clusters": len(clusters),
        }
    finally:
        conn.close()


def _build_sub_groups(nodes, edges, tn, conn):
    """
    Split nodes into sub-groups: project-scoped groups + connected-component communities.
    Returns (sub_groups, inter_group_edges).
    """
    import networkx as nx

    # Check if scope column exists (production has it, sandbox doesn't)
    has_scope = any(r.get("scope") for r in nodes)

    # 1. Group by project scope
    project_groups = {}  # scope -> [nodes]
    ungrouped = []
    for n in nodes:
        scope = n.get("scope", "global") or "global"
        if scope.startswith("project:"):
            slug = scope[len("project:"):]
            project_groups.setdefault(slug, []).append(n)
        else:
            ungrouped.append(n)

    # 2. For ungrouped nodes, find connected components
    if ungrouped:
        G = nx.Graph()
        ungrouped_ids = {n["id"] for n in ungrouped}
        for n in ungrouped:
            G.add_node(n["id"])
        for e in edges:
            if e["from_id"] in ungrouped_ids and e["to_id"] in ungrouped_ids:
                G.add_edge(e["from_id"], e["to_id"])

        components = list(nx.connected_components(G))
        # Sort by size descending
        components.sort(key=len, reverse=True)
        ungrouped_map = {n["id"]: n for n in ungrouped}
    else:
        components = []
        ungrouped_map = {}

    # 3. Build sub_groups list
    sub_groups = []

    # Project groups
    for slug, group_nodes in project_groups.items():
        group_node_ids = {n["id"] for n in group_nodes}
        group_edges = [e for e in edges
                       if e["from_id"] in group_node_ids and e["to_id"] in group_node_ids]
        avg_li = sum(n.get("lock_in") or 0 for n in group_nodes) / max(len(group_nodes), 1)
        sub_groups.append({
            "id": f"project:{slug}",
            "label": slug.replace("-", " ").title(),
            "type": "project",
            "node_count": len(group_nodes),
            "avg_lock_in": round(avg_li, 3),
            "nodes": group_nodes,
            "edges": group_edges,
        })

    # Community groups from connected components
    for i, comp in enumerate(components):
        if len(comp) < 2:
            # Singletons go into a catch-all group
            continue
        group_nodes = [ungrouped_map[nid] for nid in comp if nid in ungrouped_map]
        group_node_ids = set(comp)
        group_edges = [e for e in edges
                       if e["from_id"] in group_node_ids and e["to_id"] in group_node_ids]
        # Find hub node for label
        hub = max(group_nodes, key=lambda n: n.get("lock_in") or 0)
        hub_label = (hub.get("content") or hub["id"])[:30]
        avg_li = sum(n.get("lock_in") or 0 for n in group_nodes) / max(len(group_nodes), 1)
        sub_groups.append({
            "id": f"community:{i}",
            "label": hub_label,
            "type": "community",
            "node_count": len(group_nodes),
            "avg_lock_in": round(avg_li, 3),
            "nodes": group_nodes,
            "edges": group_edges,
        })

    # Collect singletons into one group
    singleton_ids = set()
    for comp in components:
        if len(comp) < 2:
            singleton_ids |= comp
    if singleton_ids:
        group_nodes = [ungrouped_map[nid] for nid in singleton_ids if nid in ungrouped_map]
        if group_nodes:
            avg_li = sum(n.get("lock_in") or 0 for n in group_nodes) / max(len(group_nodes), 1)
            sub_groups.append({
                "id": "community:misc",
                "label": "Unclustered",
                "type": "community",
                "node_count": len(group_nodes),
                "avg_lock_in": round(avg_li, 3),
                "nodes": group_nodes,
                "edges": [],
            })

    # 4. Compute inter-group edges
    node_to_group = {}
    for sg in sub_groups:
        for n in sg["nodes"]:
            node_to_group[n["id"]] = sg["id"]

    inter_group_edges = []
    for e in edges:
        g1 = node_to_group.get(e["from_id"])
        g2 = node_to_group.get(e["to_id"])
        if g1 and g2 and g1 != g2:
            inter_group_edges.append(e)

    return sub_groups, inter_group_edges


@app.get("/api/zoom/galaxy")
async def api_zoom_galaxy(cluster_id: str, limit: int = 200):
    """Galaxy view: sub-groups (projects + communities) within a cluster."""
    tn = _get_table_names()
    layout = compute_cluster_layout(_current_db_path, tn)

    conn = _sync_db()
    try:
        # Focus cluster info
        focus = layout.get(cluster_id, {})

        # Check which columns exist on the nodes table
        node_cols_set = {r[1] for r in conn.execute(f"PRAGMA table_info({tn['nodes']})").fetchall()}
        has_scope = "scope" in node_cols_set
        has_access_count = "access_count" in node_cols_set
        has_cluster_id_col = "cluster_id" in node_cols_set

        scope_col = ", n.scope" if has_scope else ""
        access_col = ", n.access_count" if has_access_count else ""

        # Fetch nodes in this cluster, sorted by lock_in DESC then created_at DESC
        nodes = [dict(r) for r in conn.execute(
            f"SELECT n.id, n.{tn['type_col']} as type, n.content, n.confidence, n.lock_in"
            f"{access_col}, cm.cluster_id, n.created_at, n.updated_at{scope_col} "
            f"FROM cluster_members cm "
            f"JOIN {tn['nodes']} n ON cm.node_id = n.id "
            f"WHERE cm.cluster_id = ? ORDER BY n.lock_in DESC, n.created_at DESC LIMIT ?",
            (cluster_id, limit),
        ).fetchall()]

        # Fallback: try direct cluster_id column on nodes table (sandbox only)
        if not nodes and has_cluster_id_col:
            extra = ""
            if has_access_count:
                extra += ", access_count"
            extra += ", cluster_id"
            nodes = [dict(r) for r in conn.execute(
                f"SELECT id, {tn['type_col']} as type, content, confidence, lock_in"
                f"{extra}, created_at, updated_at"
                f"{', scope' if has_scope else ''} "
                f"FROM {tn['nodes']} WHERE cluster_id = ? "
                f"ORDER BY lock_in DESC, created_at DESC LIMIT ?",
                (cluster_id, limit),
            ).fetchall()]

        node_ids = {n["id"] for n in nodes}

        # Fetch edges between these nodes
        if node_ids:
            placeholders = ",".join("?" for _ in node_ids)
            edges = [dict(r) for r in conn.execute(
                f"SELECT from_id, to_id, relationship, strength FROM {tn['edges']} "
                f"WHERE from_id IN ({placeholders}) AND to_id IN ({placeholders})",
                list(node_ids) + list(node_ids),
            ).fetchall()]
        else:
            edges = []

        # Build sub-groups (projects + connected components)
        sub_groups, inter_group_edges = _build_sub_groups(nodes, edges, tn, conn)

        # Find neighbor clusters
        neighbor_clusters = []
        for edge_info in focus.get("inter_cluster_edges", []):
            ncid = edge_info["target_cluster"]
            if ncid in layout and ncid != cluster_id:
                nc = layout[ncid]
                neighbor_clusters.append({
                    "id": ncid,
                    "label": nc["label"],
                    "x": nc["x"],
                    "y": nc["y"],
                    "node_count": nc["node_count"],
                    "edge_count_to_focus": edge_info["weight"],
                })

        return {
            "focus_cluster": {
                "id": cluster_id,
                "label": focus.get("label", cluster_id),
                "x": focus.get("x", 0),
                "y": focus.get("y", 0),
            },
            "sub_groups": sub_groups,
            "inter_group_edges": inter_group_edges,
            "neighbor_clusters": neighbor_clusters,
            # Keep flat lists for backward compat
            "nodes": nodes,
            "edges": edges,
        }
    finally:
        conn.close()


@app.get("/api/zoom/solarsystem")
async def api_zoom_solarsystem(node_id: str):
    """Solar System view: a node with all its 1-hop neighbors."""
    tn = _get_table_names()

    conn = _sync_db()
    try:
        # Detect available columns
        node_cols = {r[1] for r in conn.execute(f"PRAGMA table_info({tn['nodes']})").fetchall()}
        extra_cols = ""
        if "access_count" in node_cols:
            extra_cols += ", access_count"
        if "cluster_id" in node_cols:
            extra_cols += ", cluster_id"

        # Fetch focus node
        focus = conn.execute(
            f"SELECT id, {tn['type_col']} as type, content, confidence, lock_in"
            f"{extra_cols}, created_at, updated_at "
            f"FROM {tn['nodes']} WHERE id = ?",
            (node_id,),
        ).fetchone()

        if not focus:
            return {"error": "Node not found"}

        focus_dict = dict(focus)

        # Find all edges involving this node
        all_edges = [dict(r) for r in conn.execute(
            f"SELECT from_id, to_id, relationship, strength FROM {tn['edges']} "
            f"WHERE from_id = ? OR to_id = ?",
            (node_id, node_id),
        ).fetchall()]

        # Collect neighbor IDs
        neighbor_ids = set()
        for e in all_edges:
            if e["from_id"] != node_id:
                neighbor_ids.add(e["from_id"])
            if e["to_id"] != node_id:
                neighbor_ids.add(e["to_id"])

        # Fetch neighbor nodes
        neighbors = []
        if neighbor_ids:
            placeholders = ",".join("?" for _ in neighbor_ids)
            neighbors = [dict(r) for r in conn.execute(
                f"SELECT id, {tn['type_col']} as type, content, confidence, lock_in"
                f"{extra_cols}, created_at, updated_at "
                f"FROM {tn['nodes']} WHERE id IN ({placeholders})",
                list(neighbor_ids),
            ).fetchall()]

        # Also get edges between neighbors (for sub-graph context)
        all_ids = neighbor_ids | {node_id}
        if len(all_ids) > 1:
            placeholders = ",".join("?" for _ in all_ids)
            edges = [dict(r) for r in conn.execute(
                f"SELECT from_id, to_id, relationship, strength FROM {tn['edges']} "
                f"WHERE from_id IN ({placeholders}) AND to_id IN ({placeholders})",
                list(all_ids) + list(all_ids),
            ).fetchall()]
        else:
            edges = all_edges

        return {
            "focus_node": focus_dict,
            "neighbors": neighbors,
            "edges": edges,
        }
    finally:
        conn.close()


@app.post("/api/layout/recompute")
async def api_layout_recompute():
    """Force-recompute the cluster layout cache."""
    invalidate_layout()
    tn = _get_table_names()
    layout = compute_cluster_layout(_current_db_path, tn)
    return {"status": "ok", "clusters": len(layout)}


# ── Journal File Endpoints ───────────────────────────────────

# Project root → data/journal/  (same parent chain as switch-db uses)
_JOURNAL_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "journal"

# Known frontmatter keys (used for inline parsing)
_FM_KEYS = ["symphony", "song", "movement", "resonance", "date", "entry", "prompt"]


def _parse_journal_frontmatter(filepath: Path) -> dict:
    """Parse a journal .md file's frontmatter + derive metadata from filename."""
    name = filepath.stem  # e.g. 2025-12-28_042_thank-you
    parts = name.split("_", 2)
    meta = {
        "filename": filepath.name,
        "date": parts[0] if len(parts) > 0 else "",
        "entry": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0,
        "slug": parts[2] if len(parts) > 2 else "",
    }

    text = filepath.read_text(encoding="utf-8")
    fm_raw, _ = _split_frontmatter(text)
    meta.update(fm_raw)

    # Ensure entry is always int
    try:
        meta["entry"] = int(meta["entry"])
    except (ValueError, TypeError):
        pass

    # Extract title from first markdown heading
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("##"):
            meta["title"] = stripped[2:].strip()
            break

    return meta


def _split_frontmatter(text: str) -> tuple[dict, str]:
    """Split frontmatter from body. Handles both inline and multi-line YAML."""
    text = text.strip()
    if not text.startswith("---"):
        return {}, text

    # Check if it's inline: `--- key: val key: val ---` on ~1-3 lines before blank line
    # Or multi-line YAML: `---\nkey: val\nkey: val\n---`
    lines = text.split("\n")

    # Try multi-line YAML first: find closing `---` on its own line
    if lines[0].strip() == "---":
        for i in range(1, min(len(lines), 20)):
            if lines[i].strip() == "---":
                yaml_block = "\n".join(lines[1:i])
                body = "\n".join(lines[i + 1:]).strip()
                return _parse_yaml_block(yaml_block), body

    # Inline format: `--- content ---` possibly spanning multiple lines
    # Collect everything from first `---` to next `---` or blank line
    raw = text[3:]  # skip opening ---
    end_idx = raw.find("---")
    if end_idx != -1:
        fm_text = raw[:end_idx].strip()
        body = raw[end_idx + 3:].strip()
        return _parse_inline_frontmatter(fm_text), body

    return {}, text


def _parse_yaml_block(block: str) -> dict:
    """Parse simple key: value YAML lines."""
    result = {}
    for line in block.split("\n"):
        line = line.strip()
        if ": " in line:
            key, _, val = line.partition(": ")
            key = key.strip().lower()
            if key in _FM_KEYS:
                result[key] = val.strip()
    return result


def _parse_inline_frontmatter(text: str) -> dict:
    """Parse inline frontmatter like 'symphony: X resonance: Y date: Z entry: N'."""
    # Normalize whitespace
    text = " ".join(text.split())
    result = {}

    # Find each known key and extract its value (up to the next known key or end)
    positions = []
    for key in _FM_KEYS:
        idx = text.lower().find(key + ":")
        if idx != -1:
            positions.append((idx, key))
    positions.sort()

    for i, (pos, key) in enumerate(positions):
        start = pos + len(key) + 1  # skip "key:"
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        val = text[start:end].strip()
        result[key] = val

    return result


@app.get("/api/journals")
async def api_list_journals():
    """List all journal entries from data/journal/ markdown files."""
    entries = []
    if _JOURNAL_DIR.exists():
        for f in sorted(_JOURNAL_DIR.glob("*.md")):
            meta = _parse_journal_frontmatter(f)
            entries.append(meta)
    return {"journals": entries}


@app.get("/api/journals/{filename}")
async def api_get_journal(filename: str):
    """Return full content of a single journal file."""
    # Sanitize: only allow .md files, no path traversal
    if ".." in filename or "/" in filename:
        return {"error": "invalid filename"}
    path = _JOURNAL_DIR / filename
    if not path.exists() or path.suffix != ".md":
        return {"error": "not found"}
    text = path.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(text)

    # Extract title
    title = ""
    for line in body.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("##"):
            title = stripped[2:].strip()
            break

    parts = path.stem.split("_", 2)
    entry_num = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return {
        **fm,  # frontmatter fields first (song, resonance, etc.)
        "filename": filename,
        "date": parts[0] if len(parts) > 0 else "",
        "entry": entry_num,
        "slug": parts[2] if len(parts) > 2 else "",
        "title": title,
        "body": body,
    }


@app.websocket("/ws/events")
async def ws_events(websocket: WebSocket):
    await websocket.accept()
    ws_clients.add(websocket)
    try:
        while True:
            # Keep connection alive, client can send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_clients.discard(websocket)


# ── Startup / Entrypoint ─────────────────────────────────────

_HTTP_LOG = Path("/tmp/observatory_http_debug.log")


def run_http_server():
    """Run FastAPI in a daemon thread (Python 3.14 compatible)."""
    try:
        _HTTP_LOG.write_text("Thread started\n")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        config = uvicorn.Config(app, host="0.0.0.0", port=8100, log_level="warning", loop="none")
        server = uvicorn.Server(config)
        with _HTTP_LOG.open("a") as f:
            f.write("About to start uvicorn\n")
        print("[HTTP] Starting on :8100", file=sys.stderr, flush=True)
        loop.run_until_complete(server.serve())
    except Exception as e:
        with _HTTP_LOG.open("a") as f:
            f.write(f"ERROR: {e}\n")
            import traceback
            traceback.print_exc(file=f)
        print(f"[HTTP] FATAL: {e}", file=sys.stderr, flush=True)


async def init_matrix():
    """Initialize the matrix (called on startup)."""
    await matrix.initialize()


def main():
    http_only = "--http" in sys.argv
    start_prod = "--production" in sys.argv or os.environ.get("OBSERVATORY_MODE") == "production"

    if http_only:
        # HTTP-only mode for frontend development
        loop = asyncio.new_event_loop()
        if start_prod:
            # Skip sandbox init, go straight to production DB
            loop.run_until_complete(api_switch_db({"db": "production"}))
        else:
            loop.run_until_complete(init_matrix())
        mode_label = "PRODUCTION" if start_prod else "SANDBOX"
        print(f"Observatory — HTTP-only mode on :8100 [{mode_label}]")
        uvicorn.run(app, host="0.0.0.0", port=8100)
    else:
        # MCP mode: FastMCP in main thread, HTTP in background
        loop = asyncio.new_event_loop()
        if start_prod:
            loop.run_until_complete(api_switch_db({"db": "production"}))
        else:
            loop.run_until_complete(init_matrix())

        # Start HTTP server in background thread
        http_thread = threading.Thread(target=run_http_server, daemon=True)
        http_thread.start()
        mode_label = "PRODUCTION" if start_prod else "SANDBOX"
        print(f"Observatory — MCP mode (HTTP on :8100 in background) [{mode_label}]", file=sys.stderr)

        # Run MCP server
        mcp.run()


if __name__ == "__main__":
    main()
