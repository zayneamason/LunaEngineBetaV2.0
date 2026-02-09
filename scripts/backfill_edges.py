#!/usr/bin/env python3
"""
Backfill edges for existing memory nodes.

Reads all memory nodes, identifies entity mentions and relationships,
creates edges in the graph. One-time batch operation.

Usage:
    python scripts/backfill_edges.py [--db-path PATH] [--dry-run] [--batch-size N]
"""

import argparse
import asyncio
import json
import logging
import os
import re
import sqlite3
import sys
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# =========================================================================
# ENTITY EXTRACTION (lightweight, no LLM needed)
# =========================================================================

# Known entities from the Luna Engine ecosystem
KNOWN_ENTITIES = {
    # People
    "ahab": "person",
    "zayne": "person",
    "marzipan": "person",
    "tarcila": "person",
    "luna": "persona",
    "ben franklin": "persona",
    "benjamin franklin": "persona",
    "the dude": "persona",
    "the scribe": "persona",
    "the librarian": "persona",
    # Projects / Systems
    "luna engine": "project",
    "memory matrix": "system",
    "ai-brarian": "system",
    "aibrarian": "system",
    "persona forge": "system",
    "voight-kampff": "system",
    "director llm": "system",
    "memory monitor": "system",
    "luna hub": "system",
    "luna orb": "system",
    # Technologies
    "sqlite-vec": "technology",
    "qwen": "technology",
    "mlx": "technology",
    "lora": "technology",
    "piper tts": "technology",
    "websocket": "technology",
    # Places / Events
    "mars college": "place",
}

# Relationship patterns (regex -> edge_type)
RELATIONSHIP_PATTERNS = [
    (r"(\w+)\s+(?:is|are)\s+working\s+on\s+(.+)", "WORKS_ON"),
    (r"(\w+)\s+(?:uses?|using)\s+(.+)", "USES"),
    (r"(\w+)\s+(?:depends?\s+on|requires?)\s+(.+)", "DEPENDS_ON"),
    (r"(\w+)\s+(?:collaborat\w+\s+with|working\s+with)\s+(.+)", "COLLABORATES_WITH"),
    (r"(\w+)\s+(?:created?|built?|designed?)\s+(.+)", "CREATED"),
    (r"(\w+)\s+(?:is\s+part\s+of|belongs?\s+to)\s+(.+)", "PART_OF"),
    (r"(\w+)\s+(?:replaces?|replaced)\s+(.+)", "REPLACES"),
    (r"(\w+)\s+(?:enables?|allows?)\s+(.+)", "ENABLES"),
    (r"(\w+)\s+(?:contradicts?|conflicts?\s+with)\s+(.+)", "CONTRADICTS"),
]


def find_entity_mentions(content: str) -> list[tuple[str, str]]:
    """Find known entity mentions in content. Returns [(name, type)]."""
    content_lower = content.lower()
    found = []
    for name, etype in KNOWN_ENTITIES.items():
        if name in content_lower:
            found.append((name, etype))
    return found


def extract_co_mentions(content: str) -> list[tuple[str, str, str]]:
    """
    Find entity co-mentions in the same content.
    If two entities appear in the same node, they're related.
    Returns [(entity_a, entity_b, edge_type)].
    """
    mentions = find_entity_mentions(content)
    edges = []
    for i, (name_a, _) in enumerate(mentions):
        for name_b, _ in mentions[i + 1:]:
            edges.append((name_a, name_b, "RELATES_TO"))
    return edges


# =========================================================================
# BACKFILL ENGINE
# =========================================================================

class EdgeBackfiller:
    def __init__(self, db_path: str, dry_run: bool = False):
        self.db_path = db_path
        self.dry_run = dry_run
        self.stats = {
            "nodes_scanned": 0,
            "edges_created": 0,
            "edges_skipped_duplicate": 0,
            "edges_failed": 0,
            "entity_nodes_found": 0,
            "entity_nodes_created": 0,
            "errors": [],
        }
        # Entity name -> node_id cache
        self.entity_cache: dict[str, str] = {}

    def run(self, batch_size: int = 500):
        """Run the backfill synchronously (uses its own SQLite connection)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        try:
            # Phase A: Build entity cache from existing ENTITY nodes
            self._build_entity_cache(conn)

            # Phase B: Scan all nodes and create edges
            self._scan_and_wire(conn, batch_size)

            # Phase C: Summary
            self._report()

        finally:
            conn.close()

    def _build_entity_cache(self, conn: sqlite3.Connection):
        """Load existing entity nodes into cache."""
        cursor = conn.execute(
            "SELECT id, content FROM memory_nodes WHERE node_type = 'ENTITY'"
        )
        for row in cursor:
            name_lower = row["content"].lower().strip()
            self.entity_cache[name_lower] = row["id"]
            self.stats["entity_nodes_found"] += 1

        logger.info(f"Entity cache loaded: {len(self.entity_cache)} existing entities")

    def _resolve_or_create_entity(
        self, conn: sqlite3.Connection, name: str, entity_type: str
    ) -> str:
        """Resolve entity to existing node or create new one."""
        name_lower = name.lower().strip()

        if name_lower in self.entity_cache:
            return self.entity_cache[name_lower]

        # Check DB for exact match
        row = conn.execute(
            "SELECT id FROM memory_nodes WHERE node_type = 'ENTITY' AND LOWER(content) = ?",
            (name_lower,),
        ).fetchone()

        if row:
            self.entity_cache[name_lower] = row["id"]
            return row["id"]

        # Create new entity node
        if self.dry_run:
            node_id = f"dry_run_{name_lower}"
        else:
            import uuid
            node_id = str(uuid.uuid4())[:12]
            conn.execute(
                """
                INSERT INTO memory_nodes (id, node_type, content, confidence, lock_in, created_at)
                VALUES (?, 'ENTITY', ?, 1.0, 0.1, ?)
                """,
                (node_id, name, datetime.now().isoformat()),
            )
            self.stats["entity_nodes_created"] += 1

        self.entity_cache[name_lower] = node_id
        logger.debug(f"Created entity node: '{name}' -> {node_id}")
        return node_id

    def _create_edge(
        self,
        conn: sqlite3.Connection,
        from_id: str,
        to_id: str,
        relationship: str,
        strength: float = 0.7,
    ) -> bool:
        """Create an edge in the graph_edges table."""
        # Check for duplicate
        existing = conn.execute(
            "SELECT 1 FROM graph_edges WHERE from_id = ? AND to_id = ? AND relationship = ?",
            (from_id, to_id, relationship),
        ).fetchone()

        if existing:
            self.stats["edges_skipped_duplicate"] += 1
            return False

        if self.dry_run:
            self.stats["edges_created"] += 1
            return True

        try:
            conn.execute(
                """
                INSERT INTO graph_edges (from_id, to_id, relationship, strength, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (from_id, to_id, relationship, strength, datetime.now().isoformat()),
            )
            self.stats["edges_created"] += 1
            return True
        except Exception as e:
            self.stats["edges_failed"] += 1
            self.stats["errors"].append(f"Edge {from_id}->{to_id}: {e}")
            return False

    def _scan_and_wire(self, conn: sqlite3.Connection, batch_size: int):
        """Scan all non-ENTITY nodes and create edges from entity mentions."""
        total = conn.execute(
            "SELECT COUNT(*) FROM memory_nodes WHERE node_type != 'ENTITY'"
        ).fetchone()[0]

        logger.info(f"Scanning {total} nodes for entity mentions...")

        offset = 0
        while offset < total:
            cursor = conn.execute(
                """
                SELECT id, node_type, content FROM memory_nodes
                WHERE node_type != 'ENTITY'
                ORDER BY created_at ASC
                LIMIT ? OFFSET ?
                """,
                (batch_size, offset),
            )

            batch_edges = 0
            for row in cursor:
                self.stats["nodes_scanned"] += 1
                node_id = row["id"]
                content = row["content"] or ""

                # Find entity mentions in this node's content
                mentions = find_entity_mentions(content)

                for entity_name, entity_type in mentions:
                    entity_id = self._resolve_or_create_entity(
                        conn, entity_name, entity_type
                    )
                    # Create MENTIONS edge: memory_node -> entity
                    if self._create_edge(conn, node_id, entity_id, "MENTIONS", 0.7):
                        batch_edges += 1

                # Create co-mention edges between entities
                co_mentions = extract_co_mentions(content)
                for name_a, name_b, edge_type in co_mentions:
                    id_a = self.entity_cache.get(name_a.lower())
                    id_b = self.entity_cache.get(name_b.lower())
                    if id_a and id_b:
                        if self._create_edge(conn, id_a, id_b, edge_type, 0.5):
                            batch_edges += 1

            if not self.dry_run:
                conn.commit()

            offset += batch_size
            logger.info(
                f"  Processed {min(offset, total)}/{total} nodes | "
                f"batch_edges={batch_edges} | "
                f"total_edges={self.stats['edges_created']}"
            )

    def _report(self):
        """Print final report."""
        logger.info("=" * 60)
        logger.info("BACKFILL COMPLETE" + (" (DRY RUN)" if self.dry_run else ""))
        logger.info("=" * 60)
        logger.info(f"  Nodes scanned:          {self.stats['nodes_scanned']}")
        logger.info(f"  Entity nodes found:     {self.stats['entity_nodes_found']}")
        logger.info(f"  Entity nodes created:   {self.stats['entity_nodes_created']}")
        logger.info(f"  Edges created:          {self.stats['edges_created']}")
        logger.info(f"  Edges skipped (dupes):  {self.stats['edges_skipped_duplicate']}")
        logger.info(f"  Edges failed:           {self.stats['edges_failed']}")
        if self.stats["errors"]:
            logger.warning(f"  Errors ({len(self.stats['errors'])}):")
            for err in self.stats["errors"][:10]:
                logger.warning(f"    - {err}")
        logger.info("=" * 60)


# =========================================================================
# CLI
# =========================================================================

def main():
    parser = argparse.ArgumentParser(description="Backfill edges in Memory Matrix")
    parser.add_argument(
        "--db-path",
        default=None,
        help="Path to luna_engine.db (auto-detects if not specified)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate without writing to database",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Nodes per batch (default: 500)",
    )
    args = parser.parse_args()

    # Auto-detect DB path
    db_path = args.db_path
    if not db_path:
        candidates = [
            os.path.expanduser("~/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/data/luna_engine.db"),
            "data/luna_engine.db",
        ]
        for candidate in candidates:
            if os.path.exists(candidate):
                db_path = candidate
                break

    if not db_path or not os.path.exists(db_path):
        logger.error(f"Database not found. Tried: {candidates}")
        logger.error("Use --db-path to specify the location.")
        sys.exit(1)

    logger.info(f"Database: {db_path}")
    logger.info(f"Dry run: {args.dry_run}")
    logger.info(f"Batch size: {args.batch_size}")

    # Confirm if not dry run
    if not args.dry_run:
        # Check current edge count
        conn = sqlite3.connect(db_path)
        edge_count = conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
        node_count = conn.execute("SELECT COUNT(*) FROM memory_nodes").fetchone()[0]
        conn.close()

        logger.info(f"Current state: {node_count} nodes, {edge_count} edges")
        response = input(f"\nThis will create edges in {db_path}. Continue? [y/N] ")
        if response.lower() != "y":
            logger.info("Aborted.")
            sys.exit(0)

    backfiller = EdgeBackfiller(db_path, dry_run=args.dry_run)
    start = time.time()
    backfiller.run(batch_size=args.batch_size)
    elapsed = time.time() - start
    logger.info(f"Completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
