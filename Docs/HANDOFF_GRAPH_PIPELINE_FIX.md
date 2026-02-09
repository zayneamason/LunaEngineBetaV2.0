# HANDOFF: AI-BRARIAN Full Graph Pipeline — Fix, Instrument, Backfill

**Date:** 2026-02-09
**Author:** Architect (The Dude)
**For:** Claude Code execution agents
**Scope:** Fix remaining bugs, add observability, wire graph into retrieval, backfill edges
**Mode:** SURGICAL — exact file paths and changes specified

---

## PROJECT ROOT

```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/
```

---

## OVERVIEW

Four phases, executed in order. Each phase must pass verification before proceeding.

| Phase | What | Files |
|-------|------|-------|
| 1 | Fix `_prune_edges` property bug | `src/luna/actors/librarian.py` |
| 2 | Add debug logging + error instrumentation | `src/luna/actors/librarian.py`, `src/luna/substrate/graph.py` |
| 3 | Wire graph traversal into `get_context()` | `src/luna/substrate/memory.py` |
| 4 | Backfill edges from existing nodes | `scripts/backfill_edges.py` (NEW) |

---

## PHASE 1: Fix `_prune_edges` Property Bug

### File: `src/luna/actors/librarian.py`

**Line ~889.** The `_prune_edges` method accesses `graph.graph.edges(data=True)`.
`MemoryGraph` exposes the NetworkX DiGraph via `._graph` (private), not `.graph`.
There IS a `.graph` property on MemoryGraph (line ~107 of graph.py) but it's accessed as
`self.graph` from inside the class — externally the Librarian should use `._graph`.

Actually, checking graph.py line 107: there's a `@property` called `graph` that returns
`self._graph`. So `graph.graph` works but is a property access, not a bug per se —
HOWEVER, the `_prune_edges` code iterates `.graph.edges()` which returns the NetworkX
view directly. This actually works.

Wait — re-reading: the issue is different. `_prune_edges` accesses `created_at` from
edge data as a timestamp float, but `add_edge` stores it as an ISO string. So the
comparison `created > cutoff` compares a string to a float. This silently preserves
everything because string > float in Python 3 raises TypeError... but that's caught
by the outer try/except.

**Fix:** Parse `created_at` properly in `_prune_edges`.

**Find (line ~889-891):**
```python
        for u, v, data in graph.graph.edges(data=True):
            strength = data.get("strength", 1.0)
            created = data.get("created_at", datetime.now().timestamp())
```

**Replace with:**
```python
        for u, v, data in graph.graph.edges(data=True):
            strength = data.get("strength", 1.0)
            # created_at is stored as ISO string by add_edge, parse it
            created_raw = data.get("created_at")
            if isinstance(created_raw, str):
                try:
                    created = datetime.fromisoformat(created_raw).timestamp()
                except ValueError:
                    created = datetime.now().timestamp()
            elif isinstance(created_raw, (int, float)):
                created = float(created_raw)
            else:
                created = datetime.now().timestamp()
```

### Verification
```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python -m pytest tests/integration/test_seam_validation.py -v
```

---

## PHASE 2: Debug Logging + Error Instrumentation

The core problem that let edges stay dead for months: silent exception swallowing.
Every failure path logged a `warning` or `debug` and continued. No counters, no
alerts, no way to notice.

### 2A: Add edge pipeline counters to Librarian

**File:** `src/luna/actors/librarian.py`

Add counter fields to `__init__`. Find the existing counter initializations:

**Find (in `__init__`, around line 50-70 — look for the counter block):**
```python
        self._edges_created = 0
```

**Add after:**
```python
        self._edges_failed = 0
        self._edges_skipped_duplicate = 0
        self._entity_resolve_failures = 0
```

### 2B: Instrument `_create_edge` with structured logging

**Find the entire `_create_edge` method (line ~787-822) and replace with:**

```python
    async def _create_edge(
        self,
        from_id: str,
        to_id: str,
        edge_type: str,
        confidence: float = 1.0,
    ) -> bool:
        """
        Create edge between nodes.

        Returns True if created, False if duplicate.
        Logs all failures with full context for debugging.
        """
        # Get matrix actor to access graph
        if not self.engine:
            logger.error(
                "EDGE_FAIL: No engine reference | "
                f"from={from_id} to={to_id} type={edge_type}"
            )
            self._edges_failed += 1
            return False

        matrix_actor = self.engine.get_actor("matrix")
        if not matrix_actor:
            logger.error(
                "EDGE_FAIL: Matrix actor not found | "
                f"from={from_id} to={to_id} type={edge_type}"
            )
            self._edges_failed += 1
            return False

        # Use matrix actor's graph if available
        if not hasattr(matrix_actor, "_graph") or not matrix_actor._graph:
            logger.error(
                "EDGE_FAIL: Matrix actor has no graph | "
                f"from={from_id} to={to_id} type={edge_type} "
                f"has_attr={hasattr(matrix_actor, '_graph')} "
                f"graph_val={getattr(matrix_actor, '_graph', 'MISSING')}"
            )
            self._edges_failed += 1
            return False

        graph = matrix_actor._graph

        # Check if edge already exists
        if graph.has_edge(from_id, to_id):
            logger.debug(
                f"EDGE_SKIP: Duplicate | from={from_id} to={to_id} type={edge_type}"
            )
            self._edges_skipped_duplicate += 1
            return False

        # Create the edge
        try:
            await graph.add_edge(
                from_id=from_id,
                to_id=to_id,
                relationship=edge_type,
                strength=confidence,
            )
            logger.info(
                f"EDGE_OK: {from_id} --[{edge_type} @ {confidence:.2f}]--> {to_id}"
            )
            return True
        except TypeError as e:
            # This is the exact error class that killed edges before.
            # If this fires, the API contract has changed again.
            logger.critical(
                f"EDGE_CRITICAL: TypeError in graph.add_edge — API CONTRACT VIOLATION | "
                f"from={from_id} to={to_id} type={edge_type} confidence={confidence} | "
                f"error={e}"
            )
            self._edges_failed += 1
            return False
        except Exception as e:
            logger.error(
                f"EDGE_FAIL: Unexpected error in graph.add_edge | "
                f"from={from_id} to={to_id} type={edge_type} | "
                f"error_type={type(e).__name__} error={e}"
            )
            self._edges_failed += 1
            return False
```

### 2C: Instrument `_wire_extraction` edge loop

In `_wire_extraction`, the edge creation loop (line ~750-775) has a bare
`except Exception as e` that logs a warning. Add counter tracking.

**Find (in `_wire_extraction`, the edge loop error handler, ~line 770):**
```python
            except Exception as e:
                logger.warning(f"The Dude: Failed to create edge: {e}")
                result.edges_skipped.append(f"error: {e}")
```

**Replace with:**
```python
            except Exception as e:
                logger.error(
                    f"EDGE_WIRE_FAIL: Exception in edge wiring | "
                    f"from_ref={edge.from_ref} to_ref={edge.to_ref} "
                    f"type={edge.edge_type} | error={type(e).__name__}: {e}"
                )
                self._edges_failed += 1
                result.edges_skipped.append(f"error: {type(e).__name__}: {e}")
```

### 2D: Instrument `_resolve_entity` failure path

**Find (in `_resolve_entity`, the create-new path, ~line 382):**
```python
        # 3. Create new node
        node_id = await self._create_node(name, entity_type, source_id)
        self.alias_cache[name_lower] = node_id
        self._nodes_created += 1

        logger.debug(f"The Dude: Created new node for '{name}' -> {node_id}")
        return node_id
```

**Replace with:**
```python
        # 3. Create new node
        try:
            node_id = await self._create_node(name, entity_type, source_id)
            self.alias_cache[name_lower] = node_id
            self._nodes_created += 1
            logger.debug(f"ENTITY_NEW: '{name}' -> {node_id} (type={entity_type})")
            return node_id
        except Exception as e:
            logger.error(
                f"ENTITY_FAIL: Could not create node for '{name}' | "
                f"type={entity_type} source={source_id} | error={e}"
            )
            self._entity_resolve_failures += 1
            # Return a fallback ID so edge creation can still attempt
            import uuid
            fallback_id = f"unresolved_{uuid.uuid4().hex[:8]}"
            logger.warning(f"ENTITY_FALLBACK: Using {fallback_id} for '{name}'")
            return fallback_id
```

### 2E: Add failure counters to `get_stats()`

**Find (in `get_stats`, line ~1004):**
```python
        return {
            "filings_count": self._filings_count,
            "nodes_created": self._nodes_created,
            "nodes_merged": self._nodes_merged,
            "edges_created": self._edges_created,
```

**Replace with:**
```python
        return {
            "filings_count": self._filings_count,
            "nodes_created": self._nodes_created,
            "nodes_merged": self._nodes_merged,
            "edges_created": self._edges_created,
            "edges_failed": self._edges_failed,
            "edges_skipped_duplicate": self._edges_skipped_duplicate,
            "entity_resolve_failures": self._entity_resolve_failures,
```

### 2F: Add edge creation logging to `MemoryGraph.add_edge`

**File:** `src/luna/substrate/graph.py`

This is defense-in-depth. If the Librarian's try/catch somehow misses, the graph
itself should log what it receives.

**Find (in `add_edge`, after the database persist, ~line 191):**
```python
        logger.debug(f"Added edge: {from_id} --{relationship}[{strength}]--> {to_id}")
```

**Replace with:**
```python
        logger.info(
            f"GRAPH_EDGE_ADDED: {from_id} --{relationship}[{strength:.2f}]--> {to_id} | "
            f"total_edges={self._graph.number_of_edges()}"
        )
```

### 2G: Add edge count to graph stats for monitoring

**Find (in `get_stats` in graph.py, ~line 456):**
```python
        return {
            "node_count": self._graph.number_of_nodes(),
            "edge_count": self._graph.number_of_edges(),
```

This already exists — good. No change needed here.

### Verification

After Phase 2 changes, run:
```bash
python -m pytest tests/ -v -k "test_seam or test_librarian" --tb=short
```

Verify that `get_stats()` now returns `edges_failed`, `edges_skipped_duplicate`,
and `entity_resolve_failures` fields.

Grep the log output for the new structured markers:
```
EDGE_OK, EDGE_FAIL, EDGE_CRITICAL, EDGE_SKIP, EDGE_WIRE_FAIL
ENTITY_NEW, ENTITY_FAIL, ENTITY_FALLBACK
GRAPH_EDGE_ADDED
```

---

## PHASE 3: Wire Graph Traversal into `get_context()`

Currently `get_context()` does keyword LIKE queries and returns a flat list.
The graph exists, has `spreading_activation`, but nobody calls it from retrieval.

### File: `src/luna/substrate/memory.py`

After the keyword search returns `rows` and before the token budget loop,
add graph expansion. This goes after the rows are collected (~line 972,
after the `break` in the dedup loop) and before the "Collect nodes within
token budget" comment (~line 974).

**Find (line ~972-975):**
```python
                if len(rows) >= 50:
                    break

        # Collect nodes within token budget, filtering out confusing identity nodes
```

**Replace with:**
```python
                if len(rows) >= 50:
                    break

        # =====================================================================
        # GRAPH EXPANSION: Use spreading activation to find connected nodes
        # =====================================================================
        # If we found keyword matches, expand through graph to find related nodes
        # that keyword search would miss (e.g., "Mars College" → Robot Body → Tarcila)
        if rows and hasattr(self, 'graph') and self.graph:
            try:
                # Get IDs from keyword results as seed nodes
                seed_ids = [row[0] for row in rows[:10]]  # Top 10 keyword hits

                # Run spreading activation from seeds
                activations = await self.graph.spreading_activation(
                    start_nodes=seed_ids,
                    decay=0.5,
                    max_depth=2,
                )

                if activations:
                    # Get activated node IDs not already in results
                    existing_ids = {row[0] for row in rows}
                    graph_ids = [
                        (nid, score) for nid, score in activations.items()
                        if nid not in existing_ids and score >= 0.2
                    ]
                    # Sort by activation score
                    graph_ids.sort(key=lambda x: x[1], reverse=True)

                    # Fetch the top graph-discovered nodes
                    if graph_ids:
                        graph_node_ids = [gid for gid, _ in graph_ids[:15]]
                        placeholders = ",".join("?" * len(graph_node_ids))
                        graph_rows = await self.db.fetchall(
                            f"""
                            SELECT * FROM memory_nodes
                            WHERE id IN ({placeholders})
                            ORDER BY lock_in DESC
                            """,
                            tuple(graph_node_ids)
                        )
                        rows.extend(graph_rows)
                        logger.info(
                            f"GRAPH_EXPAND: Added {len(graph_rows)} nodes via "
                            f"spreading activation from {len(seed_ids)} seeds "
                            f"({len(activations)} total activated)"
                        )

            except Exception as e:
                # Graph expansion is supplementary — never block retrieval
                logger.warning(f"GRAPH_EXPAND_FAIL: {type(e).__name__}: {e}")

        # Collect nodes within token budget, filtering out confusing identity nodes
```

### Check: Does MemoryMatrix have a `self.graph` reference?

<need to verify this before the agent implements>

**Find in `MemoryMatrix.__init__`** whether `self.graph` is set. If not, the agent
must wire it:

Search for `class MemoryMatrix` in `src/luna/substrate/memory.py` and check `__init__`.
Look for either `self.graph = ` or `self._graph = `.

If `self.graph` does NOT exist in MemoryMatrix, the agent must add it:

In `MemoryMatrix.__init__`, after `self.db = db` (or similar), add:
```python
        self.graph: Optional["MemoryGraph"] = None
```

Then in the Matrix actor's initialization (wherever `_matrix` is created and graph
is loaded), set:
```python
        self._matrix.graph = self._graph
```

The agent should search for where `MemoryGraph` is instantiated and where
`_matrix` and `_graph` are assigned in the Matrix actor to find the right
injection point.

### Verification

```bash
# Start engine, send a message, check logs for GRAPH_EXPAND
python -c "
import asyncio
from luna.substrate.memory import MemoryMatrix
# Test that get_context doesn't crash if graph is None
# (the hasattr check should skip gracefully)
"
```

Run integration tests:
```bash
python -m pytest tests/ -v --tb=short
```

---

## PHASE 4: Backfill Edges from Existing Nodes

22,000+ nodes exist with zero edges. We need a one-time batch job to extract
edges from existing node content and wire them into the graph.

### Create: `scripts/backfill_edges.py`

```python
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

# Relationship patterns (regex → edge_type)
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
        # Entity name → node_id cache
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
                    # Create MENTIONS edge: memory_node → entity
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
        help="Path to luna_memory.db (auto-detects if not specified)",
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
            os.path.expanduser("~/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/data/luna_memory.db"),
            os.path.expanduser("~/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/luna_memory.db"),
            "data/luna_memory.db",
            "luna_memory.db",
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
```

### Running the backfill

```bash
# First: dry run to see what would happen
python scripts/backfill_edges.py --dry-run

# If counts look reasonable, run for real
python scripts/backfill_edges.py

# After backfill, verify in the engine
# Start engine, then:
curl http://localhost:8000/memory/stats | python -m json.tool | grep edge
```

### What the backfill does

1. Loads existing ENTITY nodes into a cache
2. Scans all non-ENTITY nodes (22K+ FACTs, DECISIONs, etc.)
3. For each node, finds mentions of known entities in the content
4. Creates MENTIONS edges from the memory node to the entity node
5. Creates RELATES_TO edges between entities co-mentioned in the same node
6. Commits in batches of 500 for performance

**Expected output:** Thousands of MENTIONS edges + hundreds of RELATES_TO edges,
depending on how many nodes mention known entities.

**What it does NOT do:**
- No LLM calls — purely pattern matching against known entity names
- No modification of existing nodes — only creates new edges and entity nodes
- No deletion of anything
- Safe to run multiple times (duplicate detection via unique constraint)

### After backfill: verify consolidation picks up edges

Once edges exist, the reflective tick's `LockInCalculator.update_all_clusters`
will start using the edge_strength component (20% weight). Within 5 minutes
of engine startup, clusters should begin migrating from drifting → fluid
as edge weights contribute to lock-in scores.

Monitor via Memory Monitor panel or:
```bash
curl http://localhost:8000/clusters/stats | python -m json.tool
```

---

## PHASE 2.5 (OPTIONAL): QA Assertions for Edge Pipeline

Add these QA assertions to catch regressions. The Memory Monitor panel's
`diagnoseHealth()` already checks for these, but QA assertions provide
automated continuous monitoring.

Use the MCP tool or API:

```python
# I1: Edge pipeline flowing
qa_add_assertion(
    name="edge_pipeline_flowing",
    category="structural",
    severity="critical",
    target="raw_response",
    condition="not_contains",  # This is a health check, not response check
    pattern="EDGE_CRITICAL",
    case_sensitive=True,
)

# I2: Edge count > 0 after backfill
# (This would need a custom assertion or periodic health check)
```

Actually, the QA system checks response text, not system state. For edge pipeline
monitoring, the Memory Monitor panel + structured logging are the right tools.

The log markers from Phase 2 can be monitored via:
```bash
# Watch for edge failures in real time
tail -f logs/luna.log | grep "EDGE_FAIL\|EDGE_CRITICAL"
```

---

## VERIFICATION CHECKLIST

### Phase 1
- [ ] `_prune_edges` parses `created_at` as ISO string, not raw comparison

### Phase 2
- [ ] `_create_edge` logs `EDGE_OK` on success, `EDGE_FAIL` on error, `EDGE_CRITICAL` on TypeError
- [ ] `_wire_extraction` logs `EDGE_WIRE_FAIL` with full context on error
- [ ] `_resolve_entity` logs `ENTITY_FAIL` and returns fallback ID on error
- [ ] `get_stats()` returns `edges_failed`, `edges_skipped_duplicate`, `entity_resolve_failures`
- [ ] `graph.add_edge` logs `GRAPH_EDGE_ADDED` with total edge count

### Phase 3
- [ ] `get_context()` calls `spreading_activation` when graph is available
- [ ] Graph expansion logged as `GRAPH_EXPAND`
- [ ] Graph expansion failure doesn't block retrieval (logged as `GRAPH_EXPAND_FAIL`)
- [ ] `MemoryMatrix.graph` is wired to `MemoryGraph` instance

### Phase 4
- [ ] `scripts/backfill_edges.py` exists and runs
- [ ] `--dry-run` mode works without modifying database
- [ ] Backfill creates MENTIONS edges from nodes to entity nodes
- [ ] Backfill creates RELATES_TO edges between co-mentioned entities
- [ ] Duplicate edges are skipped (not double-created)
- [ ] After backfill, `curl /memory/stats` shows `total_edges > 0`
- [ ] After backfill + 5min, `curl /clusters/stats` shows state distribution changing

### Overall
- [ ] All existing tests pass: `python -m pytest tests/ -v`
- [ ] Engine starts without errors
- [ ] Send a message → check logs for `EDGE_OK` entries
- [ ] Memory Monitor panel shows edges in Overview tab

---

## FILES SUMMARY

| File | Action | Phase |
|------|--------|-------|
| `src/luna/actors/librarian.py` | MODIFY | 1, 2 |
| `src/luna/substrate/graph.py` | MODIFY | 2 |
| `src/luna/substrate/memory.py` | MODIFY | 3 |
| `scripts/backfill_edges.py` | CREATE | 4 |

---

## LOG MARKER REFERENCE

After implementation, these markers will appear in logs:

| Marker | Level | Meaning |
|--------|-------|---------|
| `EDGE_OK` | INFO | Edge successfully created |
| `EDGE_FAIL` | ERROR | Edge creation failed (with reason) |
| `EDGE_CRITICAL` | CRITICAL | TypeError — API contract violation |
| `EDGE_SKIP` | DEBUG | Duplicate edge skipped |
| `EDGE_WIRE_FAIL` | ERROR | Exception in _wire_extraction edge loop |
| `ENTITY_NEW` | DEBUG | New entity node created |
| `ENTITY_FAIL` | ERROR | Entity resolution failed |
| `ENTITY_FALLBACK` | WARNING | Using fallback ID for unresolvable entity |
| `GRAPH_EDGE_ADDED` | INFO | Edge persisted to graph + DB |
| `GRAPH_EXPAND` | INFO | Graph traversal expanded retrieval results |
| `GRAPH_EXPAND_FAIL` | WARNING | Graph traversal failed (non-blocking) |

---

**End of handoff.**
