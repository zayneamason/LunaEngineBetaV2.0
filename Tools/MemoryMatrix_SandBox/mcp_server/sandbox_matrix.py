"""Core SandboxMatrix — sqlite + FTS5 + sqlite-vec with event emission."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite
import sqlite_vec

from .event_bus import EventBus, MemoryEvent
from .embeddings import get_embedder, vector_to_blob

SCHEMA_PATH = Path(__file__).parent / "schema.sql"
DB_PATH = Path(__file__).parent.parent / "sandbox_matrix.db"
SEEDS_DIR = Path(__file__).parent / "seeds"


def _split_schema(schema_sql: str) -> list[str]:
    """Split schema SQL into individual statements, keeping trigger bodies intact."""
    stmts = []
    buf = []
    in_trigger = False
    for line in schema_sql.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("--"):
            continue
        buf.append(line)
        if stripped.upper().startswith("CREATE TRIGGER"):
            in_trigger = True
        if in_trigger:
            if stripped.upper() == "END;":
                stmts.append("\n".join(buf))
                buf = []
                in_trigger = False
        elif stripped.endswith(";"):
            stmts.append("\n".join(buf))
            buf = []
    return [s for s in stmts if s.strip()]


class SandboxMatrix:
    def __init__(self, bus: EventBus, db_path: Path = DB_PATH, skip_schema: bool = False):
        self.bus = bus
        self.db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None
        self.embedder = get_embedder()
        self._skip_schema = skip_schema

    async def initialize(self):
        """Open DB, load sqlite-vec extension, create schema."""
        self._db = await aiosqlite.connect(str(self.db_path))
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")

        # Load sqlite-vec — required for sandbox schema, optional for production reads
        try:
            await self._db.enable_load_extension(True)
            await self._db.load_extension(sqlite_vec.loadable_path())
        except (AttributeError, Exception) as e:
            if not self._skip_schema:
                raise  # Sandbox mode needs vec extension
            # Production/read-only mode — vec not required for basic queries

        if not self._skip_schema:
            # Run schema — individual execute() calls to avoid executescript()
            # which corrupts FTS5 external-content trigger state
            schema_sql = SCHEMA_PATH.read_text()
            for stmt in _split_schema(schema_sql):
                await self._db.execute(stmt)

            # Create vec0 table (must be after extension load)
            await self._db.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS node_embeddings USING vec0("
                "node_id TEXT PRIMARY KEY, embedding FLOAT[384])"
            )
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()
            self._db = None

    # ── CRUD ──────────────────────────────────────────────────

    async def add_node(
        self,
        type: str,
        content: str,
        confidence: float = 1.0,
        tags: list[str] | None = None,
        node_id: str | None = None,
        cluster_id: str | None = None,
    ) -> str:
        """Create a node, generate its embedding, emit event."""
        nid = node_id or str(uuid.uuid4())[:8]
        now = datetime.now(timezone.utc).isoformat()
        tags_json = json.dumps(tags or [])

        await self._db.execute(
            "INSERT INTO nodes (id, type, content, confidence, tags, cluster_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (nid, type, content, confidence, tags_json, cluster_id, now, now),
        )

        # Generate and store embedding
        embedding = self.embedder.encode(content)
        blob = vector_to_blob(embedding)
        await self._db.execute(
            "INSERT INTO node_embeddings (node_id, embedding) VALUES (?, ?)",
            (nid, blob),
        )
        await self._db.commit()

        await self.bus.emit(MemoryEvent(
            type="node_created",
            actor="matrix",
            payload={"node_id": nid, "type": type, "content": content[:100]},
        ))
        return nid

    async def add_edge(
        self,
        from_id: str,
        to_id: str,
        relationship: str,
        strength: float = 1.0,
    ) -> int:
        """Create an edge between two nodes, emit event."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            "INSERT INTO edges (from_id, to_id, relationship, strength, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (from_id, to_id, relationship, strength, now),
        )
        await self._db.commit()
        edge_id = cursor.lastrowid

        await self.bus.emit(MemoryEvent(
            type="edge_added",
            actor="matrix",
            payload={
                "edge_id": edge_id,
                "from_id": from_id,
                "to_id": to_id,
                "relationship": relationship,
                "strength": strength,
            },
        ))
        return edge_id

    async def get_node(self, node_id: str) -> dict | None:
        """Fetch a single node by ID."""
        cursor = await self._db.execute(
            "SELECT * FROM nodes WHERE id = ?", (node_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def get_neighbors(self, node_id: str, depth: int = 1) -> list[dict]:
        """Get nodes connected to node_id, up to `depth` hops."""
        visited = set()
        frontier = {node_id}
        results = []

        for _ in range(depth):
            if not frontier:
                break
            placeholders = ",".join("?" for _ in frontier)
            cursor = await self._db.execute(
                f"SELECT DISTINCT CASE WHEN from_id IN ({placeholders}) THEN to_id ELSE from_id END as neighbor_id, "
                f"relationship, strength "
                f"FROM edges WHERE from_id IN ({placeholders}) OR to_id IN ({placeholders})",
                list(frontier) * 3,
            )
            rows = await cursor.fetchall()
            visited |= frontier
            next_frontier = set()
            for row in rows:
                nid = row["neighbor_id"]
                if nid not in visited:
                    next_frontier.add(nid)
                    node = await self.get_node(nid)
                    if node:
                        results.append({
                            **node,
                            "edge_relationship": row["relationship"],
                            "edge_strength": row["strength"],
                        })
            frontier = next_frontier
        return results

    async def get_edges_from(self, node_id: str) -> list[dict]:
        """Get all edges originating from a node."""
        cursor = await self._db.execute(
            "SELECT * FROM edges WHERE from_id = ?", (node_id,)
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_edges_involving(self, node_id: str) -> list[dict]:
        """Get all edges where node_id is either source or target."""
        cursor = await self._db.execute(
            "SELECT * FROM edges WHERE from_id = ? OR to_id = ?",
            (node_id, node_id),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def record_access(self, node_id: str):
        """Increment access_count for a node, emit event."""
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "UPDATE nodes SET access_count = access_count + 1, updated_at = ? WHERE id = ?",
            (now, node_id),
        )
        await self._db.commit()
        await self.bus.emit(MemoryEvent(
            type="access_recorded",
            actor="matrix",
            payload={"node_id": node_id},
        ))

    async def update_lock_in(self, node_id: str, lock_in: float):
        """Update lock_in value for a node."""
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "UPDATE nodes SET lock_in = ?, updated_at = ? WHERE id = ?",
            (lock_in, now, node_id),
        )
        await self._db.commit()

    # ── Clusters ──────────────────────────────────────────────

    async def add_cluster(
        self, name: str, cluster_id: str | None = None, lock_in: float = 0.0, state: str = "drifting"
    ) -> str:
        cid = cluster_id or f"cluster-{uuid.uuid4().hex[:6]}"
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "INSERT INTO clusters (id, name, lock_in, state, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (cid, name, lock_in, state, now, now),
        )
        await self._db.commit()
        return cid

    async def assign_to_cluster(self, node_id: str, cluster_id: str):
        await self._db.execute(
            "INSERT OR IGNORE INTO cluster_members (cluster_id, node_id) VALUES (?, ?)",
            (cluster_id, node_id),
        )
        await self._db.execute(
            "UPDATE nodes SET cluster_id = ? WHERE id = ?",
            (cluster_id, node_id),
        )
        await self._db.commit()

    async def get_cluster_members(self, cluster_id: str) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT n.* FROM nodes n "
            "JOIN cluster_members cm ON n.id = cm.node_id "
            "WHERE cm.cluster_id = ?",
            (cluster_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_clusters(self) -> list[dict]:
        cursor = await self._db.execute("SELECT * FROM clusters")
        return [dict(r) for r in await cursor.fetchall()]

    async def update_cluster_lock_in(self, cluster_id: str, lock_in: float, state: str):
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "UPDATE clusters SET lock_in = ?, state = ?, updated_at = ? WHERE id = ?",
            (lock_in, state, now, cluster_id),
        )
        await self._db.commit()

    # ── Bulk / Admin ──────────────────────────────────────────

    async def graph_dump(self, limit: int = 500, min_lock_in: float = 0.0) -> dict:
        """Full graph snapshot for frontend visualization."""
        nodes_cursor = await self._db.execute(
            "SELECT * FROM nodes WHERE lock_in >= ? ORDER BY lock_in DESC LIMIT ?",
            (min_lock_in, limit),
        )
        nodes = [dict(r) for r in await nodes_cursor.fetchall()]
        node_ids = {n["id"] for n in nodes}

        edges_cursor = await self._db.execute("SELECT * FROM edges")
        all_edges = [dict(r) for r in await edges_cursor.fetchall()]
        edges = [e for e in all_edges if e["from_id"] in node_ids and e["to_id"] in node_ids]

        clusters = await self.get_clusters()
        # Attach member IDs to each cluster
        for c in clusters:
            members_cursor = await self._db.execute(
                "SELECT node_id FROM cluster_members WHERE cluster_id = ?",
                (c["id"],),
            )
            c["member_ids"] = [r["node_id"] for r in await members_cursor.fetchall()]

        return {"nodes": nodes, "edges": edges, "clusters": clusters}

    async def stats(self) -> dict:
        """Database statistics: counts, type distribution, lock-in distribution."""
        node_count = (await (await self._db.execute("SELECT COUNT(*) FROM nodes")).fetchone())[0]
        edge_count = (await (await self._db.execute("SELECT COUNT(*) FROM edges")).fetchone())[0]
        cluster_count = (await (await self._db.execute("SELECT COUNT(*) FROM clusters")).fetchone())[0]

        # Type distribution
        type_cursor = await self._db.execute(
            "SELECT type, COUNT(*) as cnt FROM nodes GROUP BY type ORDER BY cnt DESC"
        )
        type_dist = {r["type"]: r["cnt"] for r in await type_cursor.fetchall()}

        # Lock-in distribution (CORRECTED thresholds)
        lock_in_cursor = await self._db.execute("""
            SELECT
                SUM(CASE WHEN lock_in < 0.20 THEN 1 ELSE 0 END) as drifting,
                SUM(CASE WHEN lock_in >= 0.20 AND lock_in < 0.70 THEN 1 ELSE 0 END) as fluid,
                SUM(CASE WHEN lock_in >= 0.70 AND lock_in < 0.85 THEN 1 ELSE 0 END) as settled,
                SUM(CASE WHEN lock_in >= 0.85 THEN 1 ELSE 0 END) as crystallized
            FROM nodes
        """)
        li_row = await lock_in_cursor.fetchone()
        lock_in_dist = {
            "drifting": li_row["drifting"] or 0,
            "fluid": li_row["fluid"] or 0,
            "settled": li_row["settled"] or 0,
            "crystallized": li_row["crystallized"] or 0,
        }

        return {
            "node_count": node_count,
            "edge_count": edge_count,
            "cluster_count": cluster_count,
            "type_distribution": type_dist,
            "lock_in_distribution": lock_in_dist,
        }

    async def reset(self):
        """DROP all data, recreate schema via fresh DB file."""
        # Close existing connection
        if self._db:
            await self._db.close()
            self._db = None

        # Delete the database file to get a truly clean slate
        if self.db_path.exists():
            self.db_path.unlink()

        # Reinitialize (reopen, load extension, create schema)
        await self.initialize()
        self.bus.clear()

        await self.bus.emit(MemoryEvent(
            type="sandbox_reset",
            actor="admin",
            payload={"message": "Sandbox fully reset"},
        ))

    async def seed(self, preset: str):
        """Load a JSON seed preset. Resets first."""
        seed_path = SEEDS_DIR / f"{preset}.json"
        if not seed_path.exists():
            available = [p.stem for p in SEEDS_DIR.glob("*.json")]
            raise FileNotFoundError(
                f"Preset '{preset}' not found. Available: {available}"
            )

        await self.reset()
        data = json.loads(seed_path.read_text())

        # Load entities first (if present)
        for entity in data.get("entities", []):
            eid = await self.add_entity(
                type=entity["type"],
                name=entity["name"],
                profile=entity.get("profile"),
                aliases=entity.get("aliases", []),
                avatar=entity.get("avatar", ""),
                core_facts=entity.get("core_facts"),
                voice_config=entity.get("voice_config"),
                entity_id=entity["id"],
            )
            # Set mention_count and version if provided (bypass auto-incrementing)
            if entity.get("mention_count", 0) > 0 or entity.get("current_version", 1) != 1:
                await self._db.execute(
                    "UPDATE entities SET mention_count = ?, current_version = ? WHERE id = ?",
                    (entity.get("mention_count", 0), entity.get("current_version", 1), eid),
                )

        # Load entity relationships
        for rel in data.get("entity_relationships", []):
            await self.add_entity_relationship(
                from_id=rel["from_id"],
                to_id=rel["to_id"],
                rel_type=rel["rel_type"],
                strength=rel.get("strength", 1.0),
                context=rel.get("context"),
                bidirectional=rel.get("bidirectional", False),
            )

        # Load clusters (nodes reference them)
        for c in data.get("clusters", []):
            await self.add_cluster(
                name=c["name"],
                cluster_id=c["id"],
                lock_in=c.get("lock_in", 0.0),
                state=c.get("state", "drifting"),
            )

        # Load nodes
        for n in data.get("nodes", []):
            nid = await self.add_node(
                type=n["type"],
                content=n["content"],
                confidence=n.get("confidence", 1.0),
                tags=n.get("tags", []),
                node_id=n["id"],
                cluster_id=n.get("cluster_id"),
            )
            # Set access_count if provided
            if n.get("access_count", 0) > 0:
                await self._db.execute(
                    "UPDATE nodes SET access_count = ? WHERE id = ?",
                    (n["access_count"], nid),
                )
            # Set lock_in if provided
            if n.get("lock_in", 0.0) > 0:
                await self._db.execute(
                    "UPDATE nodes SET lock_in = ? WHERE id = ?",
                    (n["lock_in"], nid),
                )

        # Load edges
        for e in data.get("edges", []):
            await self.add_edge(
                from_id=e["from_id"],
                to_id=e["to_id"],
                relationship=e["relationship"],
                strength=e.get("strength", 1.0),
            )

        # Assign cluster memberships
        for c in data.get("clusters", []):
            for member_id in c.get("member_ids", []):
                await self.assign_to_cluster(member_id, c["id"])

        # Load entity mentions (links entities to knowledge nodes)
        for mention in data.get("entity_mentions", []):
            # Use link_mention which handles mention_count updates
            await self.link_mention(
                entity_id=mention["entity_id"],
                node_id=mention["node_id"],
                mention_type=mention.get("mention_type", "reference"),
            )

        await self._db.commit()

        # Run maintenance sweep to generate initial quests (if entities present)
        if data.get("entities"):
            from .maintenance import maintenance_sweep
            candidates = await maintenance_sweep(self)
            for candidate in candidates[:5]:  # Limit to 5 initial quests
                await self.create_quest(
                    quest_type=candidate["quest_type"],
                    title=candidate["title"],
                    objective=candidate["objective"],
                    priority=candidate["priority"],
                    subtitle=candidate.get("subtitle"),
                    source=candidate.get("source"),
                    journal_prompt=candidate.get("journal_prompt"),
                    target_entities=candidate.get("target_entities"),
                    target_nodes=candidate.get("target_nodes"),
                    target_clusters=candidate.get("target_clusters"),
                )
            await self._db.commit()

        await self.bus.emit(MemoryEvent(
            type="sandbox_seeded",
            actor="admin",
            payload={
                "preset": preset,
                "entities": len(data.get("entities", [])),
                "nodes": len(data.get("nodes", [])),
                "edges": len(data.get("edges", [])),
                "quests_generated": len(candidates) if data.get("entities") else 0,
            },
        ))

    # ── Raw DB access (for search/activation modules) ─────────

    async def execute(self, sql: str, params: tuple = ()) -> aiosqlite.Cursor:
        """Raw SQL execution for search and activation modules."""
        return await self._db.execute(sql, params)

    async def fetchall(self, sql: str, params: tuple = ()) -> list[dict]:
        cursor = await self._db.execute(sql, params)
        return [dict(r) for r in await cursor.fetchall()]

    async def fetchone(self, sql: str, params: tuple = ()) -> dict | None:
        cursor = await self._db.execute(sql, params)
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def all_node_ids(self) -> list[str]:
        cursor = await self._db.execute("SELECT id FROM nodes")
        return [r["id"] for r in await cursor.fetchall()]

    # ── ENTITY CRUD ────────────────────────────────────────────────

    async def add_entity(
        self,
        type: str,
        name: str,
        profile: str | None = None,
        aliases: list[str] | None = None,
        avatar: str = "",
        core_facts: dict | None = None,
        voice_config: dict | None = None,
        entity_id: str | None = None,
    ) -> str:
        """Create an entity, emit event, and create version 1."""
        eid = entity_id or f"entity-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        aliases_json = json.dumps(aliases or [])
        core_facts_json = json.dumps(core_facts or {})
        voice_config_json = json.dumps(voice_config) if voice_config else None

        await self._db.execute(
            "INSERT INTO entities (id, type, name, aliases, avatar, profile, core_facts, voice_config, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (eid, type, name, aliases_json, avatar, profile, core_facts_json, voice_config_json, now, now),
        )

        # Create version 1
        await self._db.execute(
            "INSERT INTO entity_versions (entity_id, version, change_type, summary, created_at) "
            "VALUES (?, 1, 'create', ?, ?)",
            (eid, f"Created {type}: {name}", now),
        )
        await self._db.commit()

        await self.bus.emit(MemoryEvent(
            type="entity_created",
            actor="matrix",
            payload={"entity_id": eid, "type": type, "name": name},
        ))
        return eid

    async def get_entity(self, entity_id: str) -> dict | None:
        """Fetch a single entity by ID."""
        cursor = await self._db.execute(
            "SELECT * FROM entities WHERE id = ?", (entity_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(row)

    async def update_entity(self, entity_id: str, **kwargs) -> dict:
        """Update entity fields, increment version, create version entry."""
        entity = await self.get_entity(entity_id)
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        now = datetime.now(timezone.utc).isoformat()
        new_version = entity["current_version"] + 1

        # Build update statement dynamically
        updates = []
        params = []
        summary_parts = []

        for key, value in kwargs.items():
            if key in ("name", "profile", "avatar"):
                updates.append(f"{key} = ?")
                params.append(value)
                summary_parts.append(f"{key}={value}")
            elif key == "aliases":
                updates.append("aliases = ?")
                params.append(json.dumps(value))
                summary_parts.append(f"aliases updated")
            elif key == "core_facts":
                updates.append("core_facts = ?")
                params.append(json.dumps(value))
                summary_parts.append(f"core_facts updated")
            elif key == "voice_config":
                updates.append("voice_config = ?")
                params.append(json.dumps(value))
                summary_parts.append(f"voice_config updated")

        if not updates:
            return entity

        updates.append("current_version = ?")
        params.append(new_version)
        updates.append("updated_at = ?")
        params.append(now)
        params.append(entity_id)

        await self._db.execute(
            f"UPDATE entities SET {', '.join(updates)} WHERE id = ?",
            params,
        )

        # Create version entry
        summary = f"Updated: {', '.join(summary_parts)}"
        await self._db.execute(
            "INSERT INTO entity_versions (entity_id, version, change_type, summary, created_at) "
            "VALUES (?, ?, 'update', ?, ?)",
            (entity_id, new_version, summary, now),
        )
        await self._db.commit()

        await self.bus.emit(MemoryEvent(
            type="entity_updated",
            actor="matrix",
            payload={"entity_id": entity_id, "version": new_version, "changes": summary},
        ))

        return await self.get_entity(entity_id)

    async def list_entities(self, type_filter: str | None = None) -> list[dict]:
        """Get all entities, optionally filtered by type."""
        if type_filter:
            cursor = await self._db.execute(
                "SELECT * FROM entities WHERE type = ? ORDER BY name",
                (type_filter,),
            )
        else:
            cursor = await self._db.execute("SELECT * FROM entities ORDER BY name")
        return [dict(r) for r in await cursor.fetchall()]

    async def add_entity_relationship(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        strength: float = 1.0,
        context: str | None = None,
        bidirectional: bool = False,
    ) -> int:
        """Create a relationship between two entities, emit event."""
        now = datetime.now(timezone.utc).isoformat()
        cursor = await self._db.execute(
            "INSERT INTO entity_relationships (from_id, to_id, rel_type, strength, context, bidirectional, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (from_id, to_id, rel_type, strength, context, 1 if bidirectional else 0, now),
        )
        await self._db.commit()
        rel_id = cursor.lastrowid

        await self.bus.emit(MemoryEvent(
            type="entity_relationship_added",
            actor="matrix",
            payload={
                "rel_id": rel_id,
                "from_id": from_id,
                "to_id": to_id,
                "rel_type": rel_type,
                "strength": strength,
            },
        ))
        return rel_id

    async def get_entity_relationships(self, entity_id: str) -> list[dict]:
        """Get all relationships where entity is source or target."""
        cursor = await self._db.execute(
            "SELECT * FROM entity_relationships WHERE from_id = ? OR to_id = ?",
            (entity_id, entity_id),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def link_mention(
        self, entity_id: str, node_id: str, mention_type: str = "reference"
    ) -> int:
        """Link a knowledge node to an entity, update mention_count, emit event."""
        now = datetime.now(timezone.utc).isoformat()

        # Insert or ignore (unique constraint on entity_id, node_id)
        cursor = await self._db.execute(
            "INSERT OR IGNORE INTO entity_mentions (entity_id, node_id, mention_type, created_at) "
            "VALUES (?, ?, ?, ?)",
            (entity_id, node_id, mention_type, now),
        )

        # Update mention_count (denormalized for performance)
        await self._db.execute(
            "UPDATE entities SET mention_count = ("
            "  SELECT COUNT(*) FROM entity_mentions WHERE entity_id = ?"
            ") WHERE id = ?",
            (entity_id, entity_id),
        )
        await self._db.commit()
        mention_id = cursor.lastrowid

        await self.bus.emit(MemoryEvent(
            type="entity_mention_linked",
            actor="matrix",
            payload={"entity_id": entity_id, "node_id": node_id, "mention_type": mention_type},
        ))
        return mention_id

    async def get_entity_mentions(self, entity_id: str) -> list[dict]:
        """Get all knowledge nodes mentioned by this entity."""
        cursor = await self._db.execute(
            "SELECT em.*, n.type, n.content, n.lock_in "
            "FROM entity_mentions em "
            "JOIN nodes n ON em.node_id = n.id "
            "WHERE em.entity_id = ? "
            "ORDER BY n.lock_in DESC",
            (entity_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    async def get_entity_versions(self, entity_id: str) -> list[dict]:
        """Get version history for an entity."""
        cursor = await self._db.execute(
            "SELECT * FROM entity_versions WHERE entity_id = ? ORDER BY version DESC",
            (entity_id,),
        )
        return [dict(r) for r in await cursor.fetchall()]

    # ── QUEST LIFECYCLE ────────────────────────────────────────────

    async def create_quest(
        self,
        quest_type: str,
        title: str,
        objective: str,
        priority: str = "medium",
        subtitle: str | None = None,
        source: str | None = None,
        journal_prompt: str | None = None,
        target_entities: list[str] | None = None,
        target_nodes: list[str] | None = None,
        target_clusters: list[str] | None = None,
        target_lock_in: float | None = None,
        quest_id: str | None = None,
    ) -> str:
        """Create a quest from maintenance sweep candidate, emit event."""
        qid = quest_id or f"quest-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        await self._db.execute(
            "INSERT INTO quests (id, type, status, priority, title, subtitle, objective, source, journal_prompt, target_lock_in, created_at, updated_at) "
            "VALUES (?, ?, 'available', ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (qid, quest_type, priority, title, subtitle, objective, source, journal_prompt, target_lock_in, now, now),
        )

        # Add quest targets
        for eid in (target_entities or []):
            await self._db.execute(
                "INSERT INTO quest_targets (quest_id, target_type, target_id) VALUES (?, 'entity', ?)",
                (qid, eid),
            )
        for nid in (target_nodes or []):
            await self._db.execute(
                "INSERT INTO quest_targets (quest_id, target_type, target_id) VALUES (?, 'node', ?)",
                (qid, nid),
            )
        for cid in (target_clusters or []):
            await self._db.execute(
                "INSERT INTO quest_targets (quest_id, target_type, target_id) VALUES (?, 'cluster', ?)",
                (qid, cid),
            )

        await self._db.commit()

        await self.bus.emit(MemoryEvent(
            type="quest_created",
            actor="matrix",
            payload={"quest_id": qid, "type": quest_type, "title": title},
        ))
        return qid

    async def get_quest(self, quest_id: str) -> dict | None:
        """Fetch a single quest by ID with targets."""
        cursor = await self._db.execute(
            "SELECT * FROM quests WHERE id = ?", (quest_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None

        quest = dict(row)

        # Fetch targets
        targets_cursor = await self._db.execute(
            "SELECT target_type, target_id FROM quest_targets WHERE quest_id = ?",
            (quest_id,),
        )
        targets = [dict(r) for r in await targets_cursor.fetchall()]
        quest["targets"] = targets

        return quest

    async def list_quests(
        self, status: str | None = None, quest_type: str | None = None
    ) -> list[dict]:
        """Get all quests, optionally filtered by status or type."""
        conditions = []
        params = []

        if status:
            conditions.append("status = ?")
            params.append(status)
        if quest_type:
            conditions.append("type = ?")
            params.append(quest_type)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        sql = f"SELECT * FROM quests WHERE {where_clause} ORDER BY created_at DESC"

        cursor = await self._db.execute(sql, params)
        return [dict(r) for r in await cursor.fetchall()]

    async def accept_quest(self, quest_id: str) -> dict:
        """Mark quest as active, emit event."""
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "UPDATE quests SET status = 'active', updated_at = ? WHERE id = ?",
            (now, quest_id),
        )
        await self._db.commit()

        await self.bus.emit(MemoryEvent(
            type="quest_accepted",
            actor="matrix",
            payload={"quest_id": quest_id},
        ))

        return await self.get_quest(quest_id)

    async def complete_quest(
        self,
        quest_id: str,
        journal_text: str | None = None,
        themes: list[str] | None = None,
    ) -> dict:
        """
        Mark quest as complete. If journal_text provided:
        1. Create INSIGHT node with content=journal_text, tags=themes
        2. Link INSIGHT to quest target entities via entity_mentions
        3. Create quest_journal row pointing to INSIGHT node
        4. Recompute lock-in for affected nodes
        5. Emit quest_completed event
        6. Return summary with lock_in_delta and edges_created
        """
        from .lock_in import recompute_all_lock_ins
        from .config import RetrievalParams

        now = datetime.now(timezone.utc).isoformat()
        quest = await self.get_quest(quest_id)
        if not quest:
            raise ValueError(f"Quest {quest_id} not found")

        # Get old lock-ins for delta calculation
        old_lock_ins = {}
        for target in quest["targets"]:
            if target["target_type"] == "node":
                node = await self.get_node(target["target_id"])
                if node:
                    old_lock_ins[target["target_id"]] = node.get("lock_in", 0.0)

        insight_node_id = None
        edges_created = 0

        # Create journal INSIGHT node if journal text provided
        if journal_text:
            insight_node_id = await self.add_node(
                type="INSIGHT",
                content=journal_text,
                confidence=1.0,
                tags=themes or [],
            )

            # Link INSIGHT to quest target entities
            for target in quest["targets"]:
                if target["target_type"] == "entity":
                    await self.link_mention(
                        entity_id=target["target_id"],
                        node_id=insight_node_id,
                        mention_type="subject",
                    )
                    edges_created += 1
                elif target["target_type"] == "node":
                    # Create edge from INSIGHT to target node
                    await self.add_edge(
                        from_id=insight_node_id,
                        to_id=target["target_id"],
                        relationship="reflects_on",
                        strength=1.0,
                    )
                    edges_created += 1

            # Create quest_journal entry
            await self._db.execute(
                "INSERT INTO quest_journal (quest_id, content, themes, edges_created, node_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (quest_id, journal_text, json.dumps(themes or []), edges_created, insight_node_id, now),
            )

        # Mark quest complete
        await self._db.execute(
            "UPDATE quests SET status = 'complete', completed_at = ?, updated_at = ? WHERE id = ?",
            (now, now, quest_id),
        )
        await self._db.commit()

        # Recompute lock-ins
        params = RetrievalParams.load()
        await recompute_all_lock_ins(self, params)

        # Calculate lock-in delta
        lock_in_delta = 0.0
        for target in quest["targets"]:
            if target["target_type"] == "node":
                node = await self.get_node(target["target_id"])
                if node:
                    old_li = old_lock_ins.get(target["target_id"], 0.0)
                    new_li = node.get("lock_in", 0.0)
                    lock_in_delta += (new_li - old_li)

        # Update quest_journal with lock_in_delta
        if journal_text:
            await self._db.execute(
                "UPDATE quest_journal SET lock_in_delta = ? WHERE quest_id = ?",
                (lock_in_delta, quest_id),
            )
            await self._db.commit()

        await self.bus.emit(MemoryEvent(
            type="quest_completed",
            actor="matrix",
            payload={
                "quest_id": quest_id,
                "journal_node_id": insight_node_id,
                "lock_in_delta": round(lock_in_delta, 3),
                "edges_created": edges_created,
            },
        ))

        return {
            "quest_id": quest_id,
            "status": "complete",
            "journal_node_id": insight_node_id,
            "lock_in_delta": round(lock_in_delta, 3),
            "edges_created": edges_created,
        }

    async def fail_quest(self, quest_id: str, fail_note: str) -> dict:
        """Mark quest as failed, emit event."""
        now = datetime.now(timezone.utc).isoformat()
        await self._db.execute(
            "UPDATE quests SET status = 'failed', failed_at = ?, fail_note = ?, updated_at = ? WHERE id = ?",
            (now, fail_note, now, quest_id),
        )
        await self._db.commit()

        await self.bus.emit(MemoryEvent(
            type="quest_failed",
            actor="matrix",
            payload={"quest_id": quest_id, "fail_note": fail_note},
        ))

        return await self.get_quest(quest_id)
