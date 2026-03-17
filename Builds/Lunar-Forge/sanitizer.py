"""
Lunar Forge — Database Sanitizer.

Creates a filtered copy of luna_engine.db for clean builds.
Filters by: entities, node types, confidence, date range, conversations.

Usage (as module):
    from sanitizer import DatabaseSanitizer, SanitizeConfig
    config = SanitizeConfig(source_db=Path(...), output_db=Path(...))
    sanitizer = DatabaseSanitizer(config)
    report = sanitizer.execute()
"""

from __future__ import annotations

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("forge.sanitizer")

FORGE_ROOT = Path(__file__).parent
ENGINE_ROOT = Path(
    os.environ.get(
        "LUNA_ENGINE_ROOT",
        str(FORGE_ROOT.parent.parent / "_LunaEngine_BetaProject_V2.0_Root"),
    )
)
SCHEMA_PATH = ENGINE_ROOT / "src" / "luna" / "substrate" / "schema.sql"


@dataclass
class SanitizeConfig:
    source_db: Path
    output_db: Path
    include_entities: Optional[list[str]] = None
    exclude_entities: Optional[list[str]] = None
    include_node_types: Optional[list[str]] = None
    min_confidence: float = 0.0
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    include_conversations: bool = False
    include_system_entities: bool = True


@dataclass
class SanitizeReport:
    source_stats: dict = field(default_factory=dict)
    output_stats: dict = field(default_factory=dict)
    removed: dict = field(default_factory=dict)
    output_size_mb: float = 0.0
    filters_applied: list[str] = field(default_factory=list)


def _count_table(conn: sqlite3.Connection, table: str) -> int:
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.OperationalError:
        return 0


def _get_stats(conn: sqlite3.Connection) -> dict:
    tables = [
        "memory_nodes", "conversation_turns", "entities",
        "graph_edges", "entity_relationships", "entity_mentions",
        "entity_versions", "sessions",
    ]
    return {t: _count_table(conn, t) for t in tables}


class DatabaseSanitizer:
    def __init__(self, config: SanitizeConfig):
        self.config = config
        if not self.config.source_db.exists():
            raise FileNotFoundError(f"Source DB not found: {self.config.source_db}")

    def get_source_stats(self) -> dict:
        conn = sqlite3.connect(str(self.config.source_db))
        stats = _get_stats(conn)
        stats["size_mb"] = round(self.config.source_db.stat().st_size / (1024 * 1024), 2)
        conn.close()
        return stats

    def list_entities(self) -> list[dict]:
        conn = sqlite3.connect(str(self.config.source_db))
        rows = conn.execute("""
            SELECT e.id, e.entity_type, e.name, e.origin,
                   COUNT(DISTINCT em.node_id) as mention_count
            FROM entities e
            LEFT JOIN entity_mentions em ON em.entity_id = e.id
            GROUP BY e.id
            ORDER BY mention_count DESC
        """).fetchall()
        conn.close()
        return [
            {"id": r[0], "entity_type": r[1], "name": r[2], "origin": r[3], "mention_count": r[4]}
            for r in rows
        ]

    def list_node_type_counts(self) -> dict:
        conn = sqlite3.connect(str(self.config.source_db))
        rows = conn.execute(
            "SELECT node_type, COUNT(*) FROM memory_nodes GROUP BY node_type ORDER BY COUNT(*) DESC"
        ).fetchall()
        conn.close()
        return {r[0]: r[1] for r in rows}

    def _build_entity_filter(self) -> Optional[set[str]]:
        """Resolve which entity IDs to include. Returns None if no entity filtering."""
        cfg = self.config
        if cfg.include_entities is None and cfg.exclude_entities is None:
            return None

        conn = sqlite3.connect(str(cfg.source_db))
        all_ids = {r[0] for r in conn.execute("SELECT id FROM entities").fetchall()}
        system_ids = set()
        if cfg.include_system_entities:
            system_ids = {r[0] for r in conn.execute(
                "SELECT id FROM entities WHERE origin = 'system'"
            ).fetchall()}
        conn.close()

        if cfg.include_entities is not None:
            result = set(cfg.include_entities) | system_ids
        else:
            result = all_ids.copy()

        if cfg.exclude_entities:
            result -= set(cfg.exclude_entities) - system_ids  # Never exclude system entities

        return result

    def _build_node_where(self, prefix: str = "mn") -> tuple[str, list]:
        """Build WHERE clause for memory_nodes filtering. Returns (clause, params).
        prefix: table alias to qualify column names (avoids ambiguity in joins).
        """
        conditions = []
        params = []
        p = f"{prefix}." if prefix else ""

        if self.config.include_node_types:
            placeholders = ",".join("?" for _ in self.config.include_node_types)
            conditions.append(f"{p}node_type IN ({placeholders})")
            params.extend(self.config.include_node_types)

        if self.config.min_confidence > 0:
            conditions.append(f"{p}confidence >= ?")
            params.append(self.config.min_confidence)

        if self.config.date_from:
            conditions.append(f"{p}created_at >= ?")
            params.append(self.config.date_from)

        if self.config.date_to:
            conditions.append(f"{p}created_at <= ?")
            params.append(self.config.date_to)

        clause = " AND ".join(conditions) if conditions else "1=1"
        return clause, params

    def preview(self) -> SanitizeReport:
        """Dry run — count what would be included without creating a DB."""
        conn = sqlite3.connect(str(self.config.source_db))
        source_stats = _get_stats(conn)
        source_stats["size_mb"] = round(self.config.source_db.stat().st_size / (1024 * 1024), 2)

        entity_ids = self._build_entity_filter()
        node_where_aliased, node_params_a = self._build_node_where("mn")
        node_where_plain, node_params_p = self._build_node_where("")

        filters_applied = []

        # Count entities
        if entity_ids is not None:
            entity_count = len(entity_ids)
            filters_applied.append(f"entities: {entity_count} selected")
        else:
            entity_count = source_stats["entities"]

        # Count nodes — entity-linked + unlinked
        if entity_ids is not None:
            placeholders = ",".join("?" for _ in entity_ids)
            # Nodes linked to included entities
            linked_count = conn.execute(
                f"""SELECT COUNT(DISTINCT mn.id) FROM memory_nodes mn
                    INNER JOIN entity_mentions em ON em.node_id = mn.id
                    WHERE em.entity_id IN ({placeholders}) AND {node_where_aliased}""",
                list(entity_ids) + node_params_a,
            ).fetchone()[0]
            # Unlinked nodes (global knowledge not tied to any entity)
            unlinked_count = conn.execute(
                f"""SELECT COUNT(*) FROM memory_nodes
                    WHERE id NOT IN (SELECT node_id FROM entity_mentions) AND {node_where_plain}""",
                node_params_p,
            ).fetchone()[0]
            node_count = linked_count + unlinked_count
        else:
            node_count = conn.execute(
                f"SELECT COUNT(*) FROM memory_nodes WHERE {node_where_plain}", node_params_p
            ).fetchone()[0]

        if self.config.include_node_types:
            filters_applied.append(f"node_types: {', '.join(self.config.include_node_types)}")
        if self.config.min_confidence > 0:
            filters_applied.append(f"confidence >= {self.config.min_confidence}")
        if self.config.date_from:
            filters_applied.append(f"from: {self.config.date_from}")
        if self.config.date_to:
            filters_applied.append(f"to: {self.config.date_to}")

        # Conversations
        if self.config.include_conversations:
            turn_where = []
            turn_params = []
            if self.config.date_from:
                turn_where.append("created_at >= ?")
                turn_params.append(self.config.date_from)
            if self.config.date_to:
                turn_where.append("created_at <= ?")
                turn_params.append(self.config.date_to)
            tw = " AND ".join(turn_where) if turn_where else "1=1"
            turn_count = conn.execute(f"SELECT COUNT(*) FROM conversation_turns WHERE {tw}", turn_params).fetchone()[0]
            filters_applied.append(f"conversations: {turn_count} turns")
        else:
            turn_count = 0
            filters_applied.append("conversations: excluded")

        conn.close()

        # Estimate size (rough: ~5KB per node average)
        est_size = round((node_count * 5 + turn_count * 2) / 1024, 1)

        output_stats = {
            "memory_nodes": node_count,
            "entities": entity_count,
            "conversation_turns": turn_count,
            "est_size_mb": est_size,
        }
        removed = {
            "memory_nodes": source_stats["memory_nodes"] - node_count,
            "entities": source_stats["entities"] - entity_count,
            "conversation_turns": source_stats["conversation_turns"] - turn_count,
        }

        return SanitizeReport(
            source_stats=source_stats,
            output_stats=output_stats,
            removed=removed,
            output_size_mb=est_size,
            filters_applied=filters_applied,
        )

    def execute(self) -> SanitizeReport:
        """Create the filtered database."""
        cfg = self.config
        source_stats = self.get_source_stats()

        # Remove existing output
        if cfg.output_db.exists():
            cfg.output_db.unlink()
        cfg.output_db.parent.mkdir(parents=True, exist_ok=True)

        # Create target DB — clone schema from source (includes migrations)
        target = sqlite3.connect(str(cfg.output_db))
        target.execute("PRAGMA journal_mode=WAL")
        target.execute("PRAGMA foreign_keys=OFF")  # OFF during bulk insert for performance

        # Copy schema from source DB (handles migration columns like cluster_id)
        source_conn = sqlite3.connect(str(cfg.source_db))
        schema_rows = source_conn.execute(
            "SELECT type, name, sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY CASE type "
            "WHEN 'table' THEN 1 WHEN 'index' THEN 2 WHEN 'trigger' THEN 3 ELSE 4 END"
        ).fetchall()
        source_conn.close()

        for row_type, row_name, row_sql in schema_rows:
            # Skip FTS/vec virtual tables, sqlite internals, and autoindex
            if any(skip in row_name for skip in ("_fts", "vec0", "sqlite_", "_autoindex")):
                continue
            try:
                target.execute(row_sql)
            except sqlite3.OperationalError as e:
                logger.debug("Schema copy skip %s: %s", row_name, e)

        # Create FTS table separately
        try:
            target.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_nodes_fts USING fts5(
                    content, summary, content='memory_nodes', content_rowid='rowid', tokenize='porter unicode61'
                )
            """)
        except sqlite3.OperationalError:
            pass
        target.commit()

        # Attach source DB
        target.execute("ATTACH DATABASE ? AS source", (str(cfg.source_db),))

        entity_ids = self._build_entity_filter()
        node_where_aliased, node_params_a = self._build_node_where("mn")
        node_where_plain, node_params_p = self._build_node_where("")
        filters_applied = []

        # 1. Copy entities
        if entity_ids is not None:
            placeholders = ",".join("?" for _ in entity_ids)
            target.execute(
                f"INSERT OR IGNORE INTO entities SELECT * FROM source.entities WHERE id IN ({placeholders})",
                list(entity_ids),
            )
            filters_applied.append(f"entities: {len(entity_ids)} selected")
        else:
            target.execute("INSERT INTO entities SELECT * FROM source.entities")

        logger.info("Copied %d entities", _count_table(target, "entities"))

        # 2. Copy memory_nodes — entity-linked
        if entity_ids is not None:
            placeholders = ",".join("?" for _ in entity_ids)
            target.execute(
                f"""INSERT OR IGNORE INTO memory_nodes
                    SELECT DISTINCT mn.* FROM source.memory_nodes mn
                    INNER JOIN source.entity_mentions em ON em.node_id = mn.id
                    WHERE em.entity_id IN ({placeholders}) AND {node_where_aliased}""",
                list(entity_ids) + node_params_a,
            )

        # 2b. Copy unlinked nodes (global knowledge)
        target.execute(
            f"""INSERT OR IGNORE INTO memory_nodes
                SELECT * FROM source.memory_nodes
                WHERE id NOT IN (SELECT node_id FROM source.entity_mentions)
                AND {node_where_plain}""",
            node_params_p,
        )

        # 2c. If no entity filter, copy all matching nodes
        if entity_ids is None:
            target.execute(
                f"INSERT OR IGNORE INTO memory_nodes SELECT * FROM source.memory_nodes WHERE {node_where_plain}",
                node_params_p,
            )

        node_count = _count_table(target, "memory_nodes")
        logger.info("Copied %d memory nodes", node_count)

        if self.config.include_node_types:
            filters_applied.append(f"node_types: {', '.join(self.config.include_node_types)}")
        if self.config.min_confidence > 0:
            filters_applied.append(f"confidence >= {self.config.min_confidence}")
        if self.config.date_from:
            filters_applied.append(f"from: {self.config.date_from}")
        if self.config.date_to:
            filters_applied.append(f"to: {self.config.date_to}")

        # 3. Copy graph_edges — only where both endpoints exist
        target.execute("""
            INSERT OR IGNORE INTO graph_edges
            SELECT ge.* FROM source.graph_edges ge
            WHERE ge.from_id IN (SELECT id FROM memory_nodes)
            AND ge.to_id IN (SELECT id FROM memory_nodes)
        """)
        logger.info("Copied %d graph edges", _count_table(target, "graph_edges"))

        # 4. Copy entity_relationships — only where both entities exist
        target.execute("""
            INSERT OR IGNORE INTO entity_relationships
            SELECT er.* FROM source.entity_relationships er
            WHERE er.from_entity IN (SELECT id FROM entities)
            AND er.to_entity IN (SELECT id FROM entities)
        """)

        # 5. Copy entity_mentions — only where both exist
        target.execute("""
            INSERT OR IGNORE INTO entity_mentions
            SELECT em.* FROM source.entity_mentions em
            WHERE em.entity_id IN (SELECT id FROM entities)
            AND em.node_id IN (SELECT id FROM memory_nodes)
        """)
        logger.info("Copied %d entity mentions", _count_table(target, "entity_mentions"))

        # 6. Copy entity_versions — for included entities
        target.execute("""
            INSERT OR IGNORE INTO entity_versions
            SELECT ev.* FROM source.entity_versions ev
            WHERE ev.entity_id IN (SELECT id FROM entities)
        """)

        # 7. Conversations
        if cfg.include_conversations:
            turn_conditions = []
            turn_params = []
            if cfg.date_from:
                turn_conditions.append("created_at >= ?")
                turn_params.append(cfg.date_from)
            if cfg.date_to:
                turn_conditions.append("created_at <= ?")
                turn_params.append(cfg.date_to)
            tw = " AND ".join(turn_conditions) if turn_conditions else "1=1"
            target.execute(
                f"INSERT INTO conversation_turns SELECT * FROM source.conversation_turns WHERE {tw}",
                turn_params,
            )
            # Copy sessions that have turns
            target.execute("""
                INSERT OR IGNORE INTO sessions
                SELECT s.* FROM source.sessions s
                WHERE s.session_id IN (SELECT DISTINCT session_id FROM conversation_turns)
            """)
            filters_applied.append(f"conversations: included")
            logger.info("Copied %d conversation turns", _count_table(target, "conversation_turns"))
        else:
            filters_applied.append("conversations: excluded")

        # 8. Copy consciousness_snapshots (lightweight, always include)
        target.execute("INSERT OR IGNORE INTO consciousness_snapshots SELECT * FROM source.consciousness_snapshots")

        # 9. Commit, detach source, rebuild FTS
        target.commit()
        target.execute("DETACH DATABASE source")
        target.execute("PRAGMA foreign_keys=ON")

        # Rebuild FTS index
        try:
            target.execute("INSERT INTO memory_nodes_fts(memory_nodes_fts) VALUES('rebuild')")
            target.commit()
        except sqlite3.OperationalError as e:
            logger.warning("FTS rebuild skipped: %s", e)

        target.close()

        # VACUUM in a fresh connection (can't VACUUM with attached DBs)
        vacuum_conn = sqlite3.connect(str(cfg.output_db))
        vacuum_conn.execute("VACUUM")
        vacuum_conn.close()

        # Build report
        output_conn = sqlite3.connect(str(cfg.output_db))
        output_stats = _get_stats(output_conn)
        output_conn.close()
        output_stats["size_mb"] = round(cfg.output_db.stat().st_size / (1024 * 1024), 2)

        removed = {}
        for key in source_stats:
            if key in output_stats and isinstance(source_stats[key], (int, float)):
                removed[key] = source_stats[key] - output_stats[key]

        report = SanitizeReport(
            source_stats=source_stats,
            output_stats=output_stats,
            removed=removed,
            output_size_mb=output_stats["size_mb"],
            filters_applied=filters_applied,
        )

        logger.info(
            "Sanitization complete: %d → %d nodes, %d → %d entities, %.1f → %.1f MB",
            source_stats.get("memory_nodes", 0), output_stats.get("memory_nodes", 0),
            source_stats.get("entities", 0), output_stats.get("entities", 0),
            source_stats.get("size_mb", 0), output_stats.get("size_mb", 0),
        )

        return report
