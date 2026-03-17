"""
Observatory tool implementations for production Memory Matrix.

Uses direct aiosqlite read-only access to data/luna_engine.db.
No engine reference needed — pure diagnostic SQL queries.
"""

import json
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from luna.core.paths import user_dir
from luna.core.owner import get_owner
from .config import RetrievalParams

logger = logging.getLogger(__name__)

DB_PATH = user_dir() / "luna_engine.db"

LUNA_API = "http://localhost:8000"


async def _check_admin_access() -> bool:
    """Check if current FaceID identity is admin. Returns True if admin or engine unavailable."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{LUNA_API}/status")
            data = resp.json()
            identity = data.get("identity", {})
            if identity.get("is_present") and identity.get("luna_tier") != "admin":
                return False
    except Exception:
        pass  # Engine unavailable → allow (diagnostic mode)
    return True


@asynccontextmanager
async def _readonly_db():
    """Open a read-only connection to the production database."""
    db = await aiosqlite.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


@asynccontextmanager
async def _readwrite_db():
    """Open a read-write connection (for quest_board mutations only)."""
    db = await aiosqlite.connect(str(DB_PATH))
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.commit()
        await db.close()


# ==============================================================================
# 1. observatory_stats
# ==============================================================================

async def tool_observatory_stats() -> dict:
    """Database health overview."""
    if not DB_PATH.exists():
        return {"error": f"Database not found at {DB_PATH}"}

    async with _readonly_db() as db:
        # Node counts by type
        cursor = await db.execute(
            "SELECT node_type, COUNT(*) as cnt FROM memory_nodes GROUP BY node_type"
        )
        type_rows = await cursor.fetchall()
        nodes_by_type = {r["node_type"]: r["cnt"] for r in type_rows}
        total_nodes = sum(nodes_by_type.values())

        # Edge counts by relationship
        cursor = await db.execute(
            "SELECT relationship, COUNT(*) as cnt FROM graph_edges GROUP BY relationship"
        )
        edge_rows = await cursor.fetchall()
        edges_by_type = {r["relationship"]: r["cnt"] for r in edge_rows}
        total_edges = sum(edges_by_type.values())

        # Entity counts by type
        cursor = await db.execute(
            "SELECT entity_type, COUNT(*) as cnt FROM entities GROUP BY entity_type"
        )
        entity_rows = await cursor.fetchall()
        entities_by_type = {r["entity_type"]: r["cnt"] for r in entity_rows}
        total_entities = sum(entities_by_type.values())

        # Mention counts by type
        cursor = await db.execute(
            "SELECT mention_type, COUNT(*) as cnt FROM entity_mentions GROUP BY mention_type"
        )
        mention_rows = await cursor.fetchall()
        mentions_by_type = {r["mention_type"]: r["cnt"] for r in mention_rows}
        total_mentions = sum(mentions_by_type.values())

        # Lock-in distribution
        cursor = await db.execute("""
            SELECT
                AVG(lock_in) as avg_li,
                SUM(CASE WHEN lock_in_state = 'drifting' THEN 1 ELSE 0 END) as drifting,
                SUM(CASE WHEN lock_in_state = 'fluid' THEN 1 ELSE 0 END) as fluid,
                SUM(CASE WHEN lock_in_state = 'settled' THEN 1 ELSE 0 END) as settled
            FROM memory_nodes
        """)
        li_row = await cursor.fetchone()

        # DB file size
        db_size_mb = round(DB_PATH.stat().st_size / (1024 * 1024), 1)

    return {
        "nodes": {"total": total_nodes, "by_type": nodes_by_type},
        "edges": {"total": total_edges, "by_type": edges_by_type},
        "entities": {"total": total_entities, "by_type": entities_by_type},
        "mentions": {"total": total_mentions, "by_type": mentions_by_type},
        "lock_in": {
            "avg": round(li_row["avg_li"] or 0, 3) if li_row else 0,
            "drifting": li_row["drifting"] or 0 if li_row else 0,
            "fluid": li_row["fluid"] or 0 if li_row else 0,
            "settled": li_row["settled"] or 0 if li_row else 0,
        },
        "db_size_mb": db_size_mb,
    }


# ==============================================================================
# 2. observatory_graph_dump
# ==============================================================================

async def tool_observatory_graph_dump(limit: int = 500, min_lock_in: float = 0.0) -> dict:
    """Full graph snapshot for visualization. Admin-only."""
    if not await _check_admin_access():
        return {"error": "Observatory access is restricted to admin users."}
    if not DB_PATH.exists():
        return {"error": f"Database not found at {DB_PATH}"}

    async with _readonly_db() as db:
        # Get nodes filtered by lock_in
        cursor = await db.execute(
            "SELECT id, node_type, content, lock_in, lock_in_state, scope "
            "FROM memory_nodes WHERE lock_in >= ? ORDER BY lock_in DESC LIMIT ?",
            (min_lock_in, limit),
        )
        node_rows = await cursor.fetchall()

        cursor = await db.execute("SELECT COUNT(*) as cnt FROM memory_nodes")
        total_row = await cursor.fetchone()
        total_nodes = total_row["cnt"] if total_row else 0

        node_ids_set = set()
        nodes = []
        for r in node_rows:
            nid = r["id"]
            node_ids_set.add(nid)
            nodes.append({
                "id": nid,
                "type": r["node_type"],
                "content": (r["content"] or "")[:200],
                "lock_in": r["lock_in"] or 0,
                "lock_in_state": r["lock_in_state"] or "drifting",
                "scope": r["scope"] or "global",
            })

        # Get edges between returned nodes
        edges = []
        if node_ids_set:
            placeholders = ",".join("?" for _ in node_ids_set)
            id_list = list(node_ids_set)
            cursor = await db.execute(
                f"SELECT from_id, to_id, relationship, strength "
                f"FROM graph_edges "
                f"WHERE from_id IN ({placeholders}) AND to_id IN ({placeholders})",
                id_list + id_list,
            )
            edge_rows = await cursor.fetchall()
            for r in edge_rows:
                edges.append({
                    "from": r["from_id"],
                    "to": r["to_id"],
                    "relationship": r["relationship"],
                    "strength": r["strength"] or 1.0,
                })

    return {
        "nodes": nodes,
        "edges": edges,
        "truncated": len(nodes) < total_nodes,
        "total_nodes": total_nodes,
        "returned_nodes": len(nodes),
    }


# ==============================================================================
# 3. observatory_search
# ==============================================================================

async def tool_observatory_search(query: str, method: str = "hybrid") -> dict:
    """Multi-method search with comparison (FTS5 + basic similarity). Admin-only."""
    if not await _check_admin_access():
        return {"error": "Observatory access is restricted to admin users."}
    if not DB_PATH.exists():
        return {"error": f"Database not found at {DB_PATH}"}

    params = RetrievalParams.load()
    results = {}

    async with _readonly_db() as db:
        if method in ("fts5", "hybrid", "all"):
            t0 = time.time()
            fts_query = " OR ".join(query.split())
            try:
                cursor = await db.execute(
                    "SELECT n.id, n.node_type, n.content, n.lock_in, bm25(memory_nodes_fts) as score "
                    "FROM memory_nodes_fts fts "
                    "JOIN memory_nodes n ON n.rowid = fts.rowid "
                    "WHERE memory_nodes_fts MATCH ? "
                    "ORDER BY score "
                    "LIMIT ?",
                    (fts_query, params.fts5_limit),
                )
                fts_rows = await cursor.fetchall()
                results["fts5"] = {
                    "elapsed_ms": round((time.time() - t0) * 1000, 2),
                    "count": len(fts_rows),
                    "results": [
                        {
                            "id": r["id"],
                            "score": round(abs(r["score"]), 4),
                            "type": r["node_type"],
                            "content": (r["content"] or "")[:120],
                            "lock_in": r["lock_in"] or 0,
                        }
                        for r in fts_rows
                    ],
                }
            except Exception as e:
                results["fts5"] = {"error": str(e), "elapsed_ms": round((time.time() - t0) * 1000, 2)}

        # Vector search requires sqlite-vec extension + embedder — skip in diagnostic mode
        # and note it in the response
        if method in ("vector", "all"):
            results["vector"] = {
                "note": "Vector search requires the engine runtime (sqlite-vec + embedder). "
                        "Use luna_smart_fetch for live vector search.",
                "count": 0,
                "results": [],
            }

        if method == "hybrid" and "fts5" in results:
            # In diagnostic mode, hybrid = FTS5 only (no vector component)
            results["hybrid"] = results["fts5"].copy()
            results["hybrid"]["note"] = (
                "Diagnostic hybrid = FTS5 only. Full hybrid (FTS5 + vector RRF) "
                "requires the engine runtime."
            )

    if method != "all" and method in results:
        return {"query": query, "method": method, **results[method]}
    return {"query": query, "method": "all", "results": results}


# ==============================================================================
# 4. observatory_replay
# ==============================================================================

async def tool_observatory_replay(query: str) -> dict:
    """Pipeline trace — shows FTS5 results and what the full pipeline would see."""
    if not DB_PATH.exists():
        return {"error": f"Database not found at {DB_PATH}"}

    params = RetrievalParams.load()
    phases = []

    async with _readonly_db() as db:
        # Phase 1: FTS5
        t0 = time.time()
        fts_query = " OR ".join(query.split())
        try:
            cursor = await db.execute(
                "SELECT n.id, n.node_type, n.content, n.lock_in, bm25(memory_nodes_fts) as score "
                "FROM memory_nodes_fts fts "
                "JOIN memory_nodes n ON n.rowid = fts.rowid "
                "WHERE memory_nodes_fts MATCH ? "
                "ORDER BY score "
                "LIMIT ?",
                (fts_query, params.fts5_limit),
            )
            fts_rows = await cursor.fetchall()
            phases.append({
                "phase": "fts5",
                "elapsed_ms": round((time.time() - t0) * 1000, 2),
                "result_count": len(fts_rows),
                "results": [
                    {
                        "id": r["id"],
                        "score": round(abs(r["score"]), 4),
                        "type": r["node_type"],
                        "content": (r["content"] or "")[:80],
                        "lock_in": r["lock_in"] or 0,
                    }
                    for r in fts_rows[:10]
                ],
            })
        except Exception as e:
            phases.append({"phase": "fts5", "error": str(e)})

        # Phase 2: Vector (note — requires engine runtime)
        phases.append({
            "phase": "vector",
            "note": "Requires engine runtime (sqlite-vec + embedder). Skipped in diagnostic mode.",
            "result_count": 0,
        })

        # Phase 3: Fusion (simulated — just FTS5 ranked)
        if phases[0].get("results"):
            phases.append({
                "phase": "fusion",
                "note": "Simulated — FTS5 ranking only (no vector component).",
                "result_count": phases[0]["result_count"],
            })

        # Phase 4: Graph neighborhood of top FTS5 hits
        if phases[0].get("results"):
            t0 = time.time()
            seed_ids = [r["id"] for r in phases[0]["results"][:5]]
            placeholders = ",".join("?" for _ in seed_ids)
            cursor = await db.execute(
                f"SELECT to_id as neighbor, relationship, strength "
                f"FROM graph_edges WHERE from_id IN ({placeholders}) "
                f"UNION "
                f"SELECT from_id as neighbor, relationship, strength "
                f"FROM graph_edges WHERE to_id IN ({placeholders})",
                seed_ids + seed_ids,
            )
            neighbor_rows = await cursor.fetchall()
            phases.append({
                "phase": "graph_neighborhood",
                "elapsed_ms": round((time.time() - t0) * 1000, 2),
                "seed_count": len(seed_ids),
                "neighbor_count": len(neighbor_rows),
                "neighbors": [
                    {"id": r["neighbor"], "relationship": r["relationship"], "strength": r["strength"] or 1.0}
                    for r in neighbor_rows[:20]
                ],
            })

    return {"query": query, "phases": phases, "params": params.to_dict()}


# ==============================================================================
# 5. observatory_tune
# ==============================================================================

async def tool_observatory_tune(param: str, value: float) -> dict:
    """Adjust a retrieval parameter."""
    p = RetrievalParams.load()
    if not hasattr(p, param):
        return {
            "status": "error",
            "message": f"Unknown param '{param}'. Valid: {list(p.to_dict().keys())}",
        }
    setattr(p, param, type(getattr(p, param))(value))
    p.save()
    return {
        "status": "ok",
        "param": param,
        "new_value": getattr(p, param),
        "all_params": p.to_dict(),
    }


# ==============================================================================
# 6. observatory_entities
# ==============================================================================

async def tool_observatory_entities(
    entity_id: str = "", entity_type: str = "", limit: int = 20
) -> dict:
    """List or inspect entities. Admin-only."""
    if not await _check_admin_access():
        return {"error": "Observatory access is restricted to admin users."}
    if not DB_PATH.exists():
        return {"error": f"Database not found at {DB_PATH}"}

    async with _readonly_db() as db:
        if entity_id:
            # Full detail for one entity
            cursor = await db.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
            entity_row = await cursor.fetchone()
            if not entity_row:
                return {"error": f"Entity '{entity_id}' not found"}

            cursor = await db.execute(
                "SELECT em.mention_type, em.confidence, em.context_snippet, "
                "mn.id, mn.node_type, mn.content, mn.lock_in "
                "FROM entity_mentions em "
                "JOIN memory_nodes mn ON em.node_id = mn.id "
                "WHERE em.entity_id = ? "
                "ORDER BY em.confidence DESC",
                (entity_id,),
            )
            mention_rows = await cursor.fetchall()

            cursor = await db.execute(
                "SELECT * FROM entity_relationships WHERE from_entity = ? OR to_entity = ?",
                (entity_id, entity_id),
            )
            rel_rows = await cursor.fetchall()

            return {
                "entity": dict(entity_row),
                "mentions": [
                    {
                        "mention_type": r["mention_type"],
                        "confidence": r["confidence"],
                        "context_snippet": r["context_snippet"],
                        "node_id": r["id"],
                        "node_type": r["node_type"],
                        "content": (r["content"] or "")[:200],
                        "lock_in": r["lock_in"],
                    }
                    for r in mention_rows
                ],
                "relationships": [dict(r) for r in rel_rows],
            }

        # List entities — count mentions via subquery since no mention_count column
        if entity_type:
            cursor = await db.execute(
                "SELECT e.id, e.entity_type, e.name, e.current_version, "
                "(SELECT COUNT(*) FROM entity_mentions em WHERE em.entity_id = e.id) as mention_count "
                "FROM entities e WHERE e.entity_type = ? "
                "ORDER BY mention_count DESC LIMIT ?",
                (entity_type, limit),
            )
        else:
            cursor = await db.execute(
                "SELECT e.id, e.entity_type, e.name, e.current_version, "
                "(SELECT COUNT(*) FROM entity_mentions em WHERE em.entity_id = e.id) as mention_count "
                "FROM entities e "
                "ORDER BY mention_count DESC LIMIT ?",
                (limit,),
            )

        rows = await cursor.fetchall()

    entities = [
        {
            "id": r["id"],
            "type": r["entity_type"],
            "name": r["name"],
            "mention_count": r["mention_count"],
            "version": r["current_version"],
        }
        for r in rows
    ]
    return {"entities": entities, "count": len(entities)}


# ==============================================================================
# 7. observatory_maintenance_sweep
# ==============================================================================

async def tool_observatory_maintenance_sweep() -> dict:
    """Graph health analysis — returns quest candidates (does NOT auto-create)."""
    if not DB_PATH.exists():
        return {"error": f"Database not found at {DB_PATH}"}

    candidates = []

    async with _readonly_db() as db:
        # 1. Orphan entities (mentions but no relationships)
        cursor = await db.execute("""
            SELECT e.id, e.name,
                (SELECT COUNT(*) FROM entity_mentions em WHERE em.entity_id = e.id) as mention_count
            FROM entities e
            WHERE (SELECT COUNT(*) FROM entity_mentions em WHERE em.entity_id = e.id) > 0
            AND NOT EXISTS (
                SELECT 1 FROM entity_relationships er
                WHERE er.from_entity = e.id OR er.to_entity = e.id
            )
        """)
        orphan_rows = await cursor.fetchall()
        for r in orphan_rows:
            candidates.append({
                "quest_type": "scavenger",
                "priority": "high" if r["mention_count"] >= 5 else "medium",
                "title": f"Map {r['name']}'s relationships",
                "subtitle": f"{r['mention_count']} mentions, 0 connections",
                "source": "orphan entity",
                "target_entities": [r["id"]],
            })

        # 2. Stale entities (not updated in 30+ days)
        cursor = await db.execute("""
            SELECT e.id, e.name, e.updated_at,
                (SELECT COUNT(*) FROM entity_mentions em WHERE em.entity_id = e.id) as mention_count
            FROM entities e
            WHERE (SELECT COUNT(*) FROM entity_mentions em WHERE em.entity_id = e.id) > 0
            AND e.updated_at < datetime('now', '-30 days')
            ORDER BY mention_count DESC LIMIT 5
        """)
        stale_rows = await cursor.fetchall()
        for r in stale_rows:
            candidates.append({
                "quest_type": "treasure_hunt",
                "priority": "medium",
                "title": f"Refresh {r['name']}'s profile",
                "subtitle": f"Last updated: {(r['updated_at'] or '')[:10]}",
                "source": "stale entity",
                "target_entities": [r["id"]],
            })

        # 3. Fragmented entities (mentions but no profile)
        cursor = await db.execute("""
            SELECT e.id, e.name,
                (SELECT COUNT(*) FROM entity_mentions em WHERE em.entity_id = e.id) as mention_count
            FROM entities e
            WHERE (SELECT COUNT(*) FROM entity_mentions em WHERE em.entity_id = e.id) >= 5
            AND (e.full_profile IS NULL OR e.full_profile = '' OR e.core_facts = '{}')
            ORDER BY mention_count DESC LIMIT 5
        """)
        frag_rows = await cursor.fetchall()
        for r in frag_rows:
            candidates.append({
                "quest_type": "scavenger",
                "priority": "high",
                "title": f"Who is {r['name']}?",
                "subtitle": f"{r['mention_count']} mentions, sparse profile",
                "source": "fragmented entity",
                "target_entities": [r["id"]],
            })

        # 4. Drifting knowledge (high-access nodes stuck at drifting)
        cursor = await db.execute("""
            SELECT id, node_type, content, lock_in, access_count FROM memory_nodes
            WHERE lock_in_state = 'drifting' AND access_count >= 3
            ORDER BY access_count DESC LIMIT 5
        """)
        drifting_rows = await cursor.fetchall()
        for r in drifting_rows:
            candidates.append({
                "quest_type": "treasure_hunt",
                "priority": "medium",
                "title": f"Anchor drifting {r['node_type']}: {(r['content'] or '')[:40]}...",
                "subtitle": f"Lock-in: {r['lock_in']:.2f}, accessed {r['access_count']} times",
                "source": "drifting high-access node",
                "target_nodes": [r["id"]],
            })

    return {
        "candidates_found": len(candidates),
        "candidates": candidates,
    }


# ==============================================================================
# 8. observatory_quest_board
# ==============================================================================


async def tool_observatory_quest_board(
    action: str = "list",
    quest_id: str = "",
    journal_text: str = "",
    status: str = "",
    quest_type: str = "",
    project: str = "",
) -> dict:
    """Unified quest management: list, accept, complete, create."""
    if not DB_PATH.exists():
        return {"error": f"Database not found at {DB_PATH}"}

    async with _readwrite_db() as db:

        if action == "list":
            conditions = []
            params = []
            if status:
                conditions.append("status = ?")
                params.append(status)
            if quest_type:
                conditions.append("type = ?")
                params.append(quest_type)
            if project:
                conditions.append("project = ?")
                params.append(project)

            where = " AND ".join(conditions) if conditions else "1=1"
            cursor = await db.execute(
                f"""SELECT q.*,
                    (SELECT json_group_array(json_object(
                        'target_type', qt.target_type,
                        'target_id', qt.target_id
                    )) FROM quest_targets qt WHERE qt.quest_id = q.id) as targets
                FROM quests q
                WHERE {where}
                ORDER BY created_at DESC LIMIT 50""",
                tuple(params),
            )
            rows = await cursor.fetchall()
            quests = []
            for r in rows:
                q = dict(r)
                q["targets"] = json.loads(q.get("targets") or "[]")
                quests.append(q)
            return {"action": "list", "count": len(quests), "quests": quests}

        elif action == "accept" and quest_id:
            await db.execute(
                "UPDATE quests SET status = 'active', updated_at = datetime('now') WHERE id = ?",
                (quest_id,),
            )
            return {"action": "accept", "quest_id": quest_id, "status": "active"}

        elif action == "complete" and quest_id:
            await db.execute(
                "UPDATE quests SET status = 'complete', completed_at = datetime('now'), "
                "updated_at = datetime('now') WHERE id = ?",
                (quest_id,),
            )
            result = {"action": "complete", "quest_id": quest_id, "status": "complete"}

            if journal_text:
                await db.execute(
                    "INSERT INTO quest_journal (quest_id, content, themes, created_at) "
                    "VALUES (?, ?, '[]', datetime('now'))",
                    (quest_id, journal_text),
                )
                result["journal"] = "saved"

            return result

        elif action == "create":
            sweep = await tool_observatory_maintenance_sweep()
            candidates = sweep.get("candidates", [])
            created = []

            for c in candidates:
                qid = f"quest-{uuid.uuid4().hex[:8]}"
                now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

                await db.execute(
                    "INSERT INTO quests (id, type, status, priority, title, subtitle, "
                    "objective, source, created_at, updated_at) "
                    "VALUES (?, ?, 'available', ?, ?, ?, ?, ?, ?, ?)",
                    (
                        qid,
                        c.get("quest_type", "side"),
                        c.get("priority", "medium"),
                        c.get("title", ""),
                        c.get("subtitle", ""),
                        c.get("objective", c.get("title", "")),
                        c.get("source", "maintenance_sweep"),
                        now_str,
                        now_str,
                    ),
                )

                for entity_id in c.get("target_entities", []):
                    await db.execute(
                        "INSERT INTO quest_targets (quest_id, target_type, target_id) "
                        "VALUES (?, 'entity', ?)",
                        (qid, entity_id),
                    )

                for node_id in c.get("target_nodes", []):
                    await db.execute(
                        "INSERT INTO quest_targets (quest_id, target_type, target_id) "
                        "VALUES (?, 'node', ?)",
                        (qid, node_id),
                    )

                created.append(qid)

            # Also create entity review quest if pending
            review_result = await tool_observatory_entity_review_quest()
            if review_result.get("quest_id"):
                created.append(review_result["quest_id"])

            return {"action": "create", "created": len(created), "quest_ids": created,
                    "entity_review": review_result}

        # =================================================================
        # Intent Layer actions (directives & skills)
        # =================================================================

        elif action == "create_directive" and quest_id:
            # quest_id repurposed as JSON config string for directives
            import json as _j
            try:
                cfg = _j.loads(quest_id)
            except (json.JSONDecodeError, TypeError):
                return {"error": "create_directive requires quest_id as JSON config"}

            title_d = cfg.get("title", "")
            objective_d = cfg.get("objective", title_d)
            if not title_d:
                return {"error": "directive requires 'title'"}

            qid = f"dir-{uuid.uuid4().hex[:8]}"
            now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            authored = cfg.get("authored_by", "luna")
            approved = cfg.get("approved_by")
            initial_status = "armed" if approved else "available"

            await db.execute(
                "INSERT INTO quests (id, type, status, priority, title, objective, "
                "trigger_type, trigger_config, action, trust_tier, authored_by, "
                "approved_by, cooldown_minutes, source, created_at, updated_at) "
                "VALUES (?, 'directive', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'observatory', ?, ?)",
                (qid, initial_status, cfg.get("priority", "medium"),
                 title_d, objective_d,
                 cfg.get("trigger_type", "keyword"),
                 json.dumps(cfg.get("trigger_config", {})),
                 cfg.get("action", ""),
                 cfg.get("trust_tier", "confirm"),
                 authored, approved,
                 cfg.get("cooldown_minutes"),
                 now_str, now_str),
            )
            return {"action": "create_directive", "quest_id": qid,
                    "status": initial_status, "title": title_d}

        elif action == "create_skill" and quest_id:
            import json as _j
            try:
                cfg = _j.loads(quest_id)
            except (json.JSONDecodeError, TypeError):
                return {"error": "create_skill requires quest_id as JSON config"}

            title_s = cfg.get("title", "")
            if not title_s:
                return {"error": "skill requires 'title'"}

            qid = f"skill-{uuid.uuid4().hex[:8]}"
            now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            await db.execute(
                "INSERT INTO quests (id, type, status, priority, title, objective, "
                "steps, tags_json, authored_by, source, created_at, updated_at) "
                "VALUES (?, 'skill', 'available', ?, ?, ?, ?, ?, ?, 'observatory', ?, ?)",
                (qid, cfg.get("priority", "medium"),
                 title_s, cfg.get("objective", title_s),
                 json.dumps(cfg.get("steps", [])),
                 json.dumps(cfg.get("tags", [])),
                 cfg.get("authored_by", "luna"),
                 now_str, now_str),
            )
            return {"action": "create_skill", "quest_id": qid,
                    "status": "available", "title": title_s}

        elif action == "arm" and quest_id:
            await db.execute(
                "UPDATE quests SET status = 'armed', approved_by = ?, "
                "updated_at = datetime('now') "
                "WHERE id = ? AND type = 'directive'",
                (get_owner().entity_id or "system", quest_id,),
            )
            return {"action": "arm", "quest_id": quest_id, "status": "armed"}

        elif action == "disarm" and quest_id:
            await db.execute(
                "UPDATE quests SET status = 'disabled', updated_at = datetime('now') "
                "WHERE id = ? AND type IN ('directive', 'skill')",
                (quest_id,),
            )
            return {"action": "disarm", "quest_id": quest_id, "status": "disabled"}

        elif action == "disable_all_directives":
            cursor = await db.execute(
                "UPDATE quests SET status = 'disabled', updated_at = datetime('now') "
                "WHERE type = 'directive' AND status IN ('armed', 'fired')"
            )
            return {"action": "disable_all_directives",
                    "disabled": cursor.rowcount}

        elif action == "fire_history" and quest_id:
            cursor = await db.execute(
                "SELECT id, title, fire_count, last_fired_at, invocation_count, "
                "last_invoked_at, status FROM quests WHERE id = ?",
                (quest_id,),
            )
            row = await cursor.fetchone()
            if row:
                r = dict(row)
                return {"action": "fire_history", "quest_id": quest_id, **r}
            return {"error": f"Quest {quest_id} not found"}

    return {"error": f"Unknown action '{action}' or missing quest_id"}


# ==============================================================================
# 9. observatory_quest_create (manual quest creation)
# ==============================================================================


async def tool_observatory_quest_create(
    title: str,
    objective: str,
    quest_type: str = "side",
    priority: str = "medium",
    subtitle: str = "",
    source: str = "manual",
    journal_prompt: str = "",
    target_entity_ids: str = "[]",
    target_node_ids: str = "[]",
    project: str = "",
) -> dict:
    """Create a quest manually. Optionally scope to a project slug."""
    if not DB_PATH.exists():
        return {"error": f"Database not found at {DB_PATH}"}

    qid = f"quest-{uuid.uuid4().hex[:8]}"
    now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    async with _readwrite_db() as db:
        # Ensure project column exists (idempotent migration)
        try:
            await db.execute(
                "ALTER TABLE quests ADD COLUMN project TEXT DEFAULT NULL"
            )
        except Exception:
            pass  # Column already exists

        await db.execute(
            "INSERT INTO quests (id, type, status, priority, title, subtitle, "
            "objective, source, journal_prompt, project, created_at, updated_at) "
            "VALUES (?, ?, 'available', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (qid, quest_type, priority, title, subtitle, objective, source,
             journal_prompt or None, project or None, now_str, now_str),
        )

        for eid in json.loads(target_entity_ids):
            await db.execute(
                "INSERT INTO quest_targets (quest_id, target_type, target_id) "
                "VALUES (?, 'entity', ?)",
                (qid, eid),
            )
        for nid in json.loads(target_node_ids):
            await db.execute(
                "INSERT INTO quest_targets (quest_id, target_type, target_id) "
                "VALUES (?, 'node', ?)",
                (qid, nid),
            )

    # Emit quest_generated for live knowledge feed
    try:
        from luna.core.event_bus import event_bus, KnowledgeEvent
        event_bus.emit("knowledge", KnowledgeEvent(
            type="quest_generated",
            payload={"quest_id": qid, "title": title, "quest_type": quest_type},
        ))
    except Exception:
        pass  # Event bus may not be available in all contexts

    return {"quest_id": qid, "title": title, "status": "available", "project": project or None}


# ==============================================================================
# 10. Entity review quest (hygiene system)
# ==============================================================================

REVIEW_QUEUE_PATH = DB_PATH.parent / "entity_review_queue.json"


async def tool_observatory_entity_review_quest() -> dict:
    """Check the entity review queue and create a quest if entities are pending."""
    if not REVIEW_QUEUE_PATH.exists():
        return {"status": "empty", "pending": 0}

    try:
        queue = json.loads(REVIEW_QUEUE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {"status": "empty", "pending": 0}

    if not queue:
        return {"status": "empty", "pending": 0}

    entity_names = [e["name"] for e in queue[:20]]
    names_str = ", ".join(entity_names)
    if len(queue) > 20:
        names_str += f" ...and {len(queue) - 20} more"

    entity_ids = [e["entity_id"] for e in queue]
    priority = "medium" if len(queue) > 10 else "low"

    result = await tool_observatory_quest_create(
        title=f"Review {len(queue)} New Entities",
        objective=(
            f"New entities were created since the last review: {names_str}. "
            "Check each one: is this a real person, project, place, or persona "
            "in Luna's world? Or is it garbage that slipped through? "
            "Delete the garbage, keep the real ones."
        ),
        quest_type="side",
        priority=priority,
        subtitle="Memory Hygiene — entity review",
        source="entity_review",
        journal_prompt=(
            "Which entities did you keep and why? "
            "Which did you delete? "
            "Should any new terms be added to the stoplist?"
        ),
        target_entity_ids=json.dumps(entity_ids),
    )

    # Clear the review queue after quest creation
    REVIEW_QUEUE_PATH.write_text("[]")

    return {
        "status": "quest_created",
        "pending": len(queue),
        "quest_id": result.get("quest_id"),
        "entities_queued": entity_names,
    }


# ==============================================================================
# 11. observatory_collection_health
# ==============================================================================

async def tool_observatory_collection_health() -> dict:
    """
    Collection lock-in health overview.
    Reports lock-in scores, states, patterns, and floor violations
    for all tracked collections.
    """
    if not DB_PATH.exists():
        return {"error": f"Database not found at {DB_PATH}"}

    from luna.substrate.collection_lock_in import (
        PATTERN_FLOORS,
        COLLECTION_LOCK_IN_MIN,
    )

    # Load registry for pattern lookup
    registry_collections = {}
    try:
        import yaml
        registry_path = DB_PATH.parent.parent / "config" / "aibrarian_registry.yaml"
        if registry_path.exists():
            registry = yaml.safe_load(registry_path.read_text())
            registry_collections = registry.get("collections", {})
    except Exception:
        pass

    collections = []
    alerts = []

    async with _readonly_db() as db:
        cursor = await db.execute(
            """SELECT collection_key, lock_in, state,
                      access_count, annotation_count,
                      last_accessed_at, updated_at
               FROM collection_lock_in
               ORDER BY lock_in DESC"""
        )
        rows = await cursor.fetchall()

    for r in rows:
        key = r["collection_key"]
        lock_in = r["lock_in"]
        state = r["state"]

        col_cfg = registry_collections.get(key, {})
        pattern = col_cfg.get("ingestion_pattern", "utilitarian")

        floor = PATTERN_FLOORS.get(pattern, COLLECTION_LOCK_IN_MIN)
        near_floor = lock_in < (floor + 0.05)
        at_floor = lock_in <= floor

        entry = {
            "collection_key": key,
            "lock_in": round(lock_in, 4),
            "state": state,
            "pattern": pattern,
            "floor": floor,
            "access_count": r["access_count"],
            "annotation_count": r["annotation_count"],
            "last_accessed_at": r["last_accessed_at"],
            "near_floor": near_floor,
            "at_floor": at_floor,
        }
        collections.append(entry)

        if pattern == "ceremonial" and near_floor:
            alerts.append({
                "severity": "critical" if at_floor else "warning",
                "collection": key,
                "message": (
                    f"Ceremonial collection '{key}' at floor "
                    f"(lock_in={lock_in:.3f}, floor={floor}). "
                    "Community knowledge at minimum visibility."
                    if at_floor else
                    f"Ceremonial collection '{key}' approaching floor "
                    f"(lock_in={lock_in:.3f}, floor={floor})."
                ),
            })

    return {
        "collections_tracked": len(collections),
        "collections": collections,
        "alerts": alerts,
        "alert_count": len(alerts),
    }
