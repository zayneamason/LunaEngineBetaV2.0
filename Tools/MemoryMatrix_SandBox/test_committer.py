#!/usr/bin/env python3
"""
Committer Test - Test era-weighted lock-in and database commits

Validates committer functionality:
- Era-weighted lock-in calculation
- Node commitment with embeddings
- Edge commitment with validation
- Ingestion log updates
- Batch commit workflow
"""

import sys
import os
import json
import asyncio
import aiosqlite
from pathlib import Path
from datetime import datetime
import tempfile
import shutil

sys.path.insert(0, str(Path(__file__).parent))

from mcp_server.ingester.committer import TranscriptCommitter


class MockEmbedding:
    """Mock embedding function for testing."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings (all zeros for simplicity)."""
        return [[0.0] * self.dimension for _ in texts]


async def create_test_database(db_path: str):
    """Create a minimal test database with required schema."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA foreign_keys = ON")

        # Create nodes table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                content TEXT NOT NULL,
                type TEXT NOT NULL,
                lock_in REAL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                metadata TEXT,
                tags TEXT
            )
        """)

        # Create edges table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_node_id INTEGER NOT NULL,
                to_node_id INTEGER NOT NULL,
                relationship TEXT NOT NULL,
                strength REAL DEFAULT 0.5,
                FOREIGN KEY (from_node_id) REFERENCES nodes(id),
                FOREIGN KEY (to_node_id) REFERENCES nodes(id),
                UNIQUE(from_node_id, to_node_id, relationship)
            )
        """)

        # Create node_embeddings table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS node_embeddings (
                node_id INTEGER PRIMARY KEY,
                embedding BLOB,
                FOREIGN KEY (node_id) REFERENCES nodes(id)
            )
        """)

        # Create transcript_ingestion_log table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS transcript_ingestion_log (
                conversation_uuid TEXT PRIMARY KEY,
                transcript_path TEXT,
                ingested_at TEXT,
                trigger TEXT,
                trigger_query TEXT,
                tier TEXT,
                texture TEXT,
                extraction_status TEXT,
                nodes_created INTEGER DEFAULT 0,
                entities_found INTEGER DEFAULT 0,
                edges_created INTEGER DEFAULT 0,
                review_status TEXT DEFAULT 'pending',
                error_message TEXT
            )
        """)

        await db.commit()


async def main():
    print("=" * 70)
    print("COMMITTER TEST - Era-Weighted Lock-In & Database Commits")
    print("=" * 70)

    # ========================================================================
    # Setup Test Database
    # ========================================================================

    print("\n[1/6] Setting up test database...")

    # Create temporary database
    temp_dir = tempfile.mkdtemp()
    test_db = Path(temp_dir) / "test_committer.db"

    await create_test_database(str(test_db))
    print(f"✓ Created test database: {test_db}")

    # ========================================================================
    # TEST 1: Era-Weighted Lock-In Calculation
    # ========================================================================

    print("\n[2/6] Testing era-weighted lock-in calculation...")

    committer = TranscriptCommitter(str(test_db))

    # Test all eras with different confidences
    test_cases = [
        ("PRE_LUNA", 0.0, 0.05),
        ("PRE_LUNA", 0.5, 0.10),
        ("PRE_LUNA", 1.0, 0.15),
        ("PROTO_LUNA", 0.0, 0.15),
        ("PROTO_LUNA", 0.5, 0.25),
        ("PROTO_LUNA", 1.0, 0.35),
        ("LUNA_DEV", 0.0, 0.35),
        ("LUNA_DEV", 0.5, 0.45),
        ("LUNA_DEV", 1.0, 0.55),
        ("LUNA_LIVE", 0.0, 0.55),
        ("LUNA_LIVE", 0.5, 0.65),
        ("LUNA_LIVE", 1.0, 0.75),
    ]

    print("\n  Era Lock-In Ranges:")
    print("  " + "-" * 50)
    for era, confidence, expected in test_cases:
        actual = committer.calculate_lock_in(era, confidence)
        status = "✓" if actual == expected else "✗"
        print(f"  {status} {era:12} conf={confidence:.1f} → lock_in={actual:.2f} (expected {expected:.2f})")

    # ========================================================================
    # TEST 2: Node Commitment
    # ========================================================================

    print("\n[3/6] Testing node commitment...")

    # Create test nodes
    test_nodes = [
        {
            "content": "Luna uses SQLite for memory storage",
            "type": "FACT",
            "confidence": 0.8,
            "extraction_era": "LUNA_DEV",
            "source_date": "2025-05-15",
            "source_conversation": "test-conv-001",
            "tags": ["memory", "database"],
        },
        {
            "content": "Memory Matrix uses NetworkX for graph relationships",
            "type": "FACT",
            "confidence": 0.9,
            "extraction_era": "LUNA_DEV",
            "source_date": "2025-06-20",
            "source_conversation": "test-conv-002",
            "tags": ["graph", "relationships"],
        },
        {
            "content": "Should we use FTS5 or vec0 for search?",
            "type": "PROBLEM",
            "confidence": 0.6,
            "extraction_era": "PROTO_LUNA",
            "source_date": "2024-11-10",
            "source_conversation": "test-conv-003",
            "tags": ["search", "decision"],
        },
    ]

    embedding_fn = MockEmbedding(dimension=384)
    node_ids = await committer.commit_nodes(test_nodes, embedding_fn=embedding_fn)

    print(f"\n  Committed {len(node_ids)} nodes:")
    for i, node_id in enumerate(node_ids, 1):
        node = test_nodes[i-1]
        lock_in = committer.calculate_lock_in(node["extraction_era"], node["confidence"])
        print(f"    {i}. Node ID {node_id}: [{node['type']}] lock_in={lock_in:.2f}")

    # Verify nodes in database
    async with aiosqlite.connect(str(test_db)) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM nodes")
        count = (await cursor.fetchone())[0]
        print(f"\n  ✓ Database contains {count} nodes")

        # Check embeddings
        cursor = await db.execute("SELECT COUNT(*) FROM node_embeddings")
        emb_count = (await cursor.fetchone())[0]
        print(f"  ✓ Database contains {emb_count} embeddings")

    # ========================================================================
    # TEST 3: Edge Commitment
    # ========================================================================

    print("\n[4/6] Testing edge commitment...")

    # Create test edges
    test_edges = [
        {
            "from_node_id": "node_0",
            "to_node_id": "node_1",
            "edge_type": "related_to",
            "strength": 0.7,
        },
        {
            "from_node_id": "node_2",
            "to_node_id": "node_0",
            "edge_type": "clarifies",
            "strength": 0.5,
        },
    ]

    # Create node ID mapping (extraction IDs → database IDs)
    node_id_map = {
        "node_0": node_ids[0],
        "node_1": node_ids[1],
        "node_2": node_ids[2],
    }

    edges_committed = await committer.commit_edges(test_edges, node_id_map)

    print(f"\n  Committed {edges_committed} edges:")
    for edge in test_edges:
        from_id = node_id_map[edge["from_node_id"]]
        to_id = node_id_map[edge["to_node_id"]]
        print(f"    • Node {from_id} --{edge['edge_type']}--> Node {to_id} (strength={edge['strength']:.2f})")

    # Verify edges in database
    async with aiosqlite.connect(str(test_db)) as db:
        cursor = await db.execute("SELECT COUNT(*) FROM edges")
        count = (await cursor.fetchone())[0]
        print(f"\n  ✓ Database contains {count} edges")

    # ========================================================================
    # TEST 4: Full Extraction Commit
    # ========================================================================

    print("\n[5/6] Testing full extraction commit...")

    # Create test extraction
    test_extraction = {
        "nodes": [
            {
                "content": "Implemented transcript ingester pipeline",
                "type": "ACTION",
                "confidence": 0.85,
                "tags": ["development", "ingestion"],
            },
            {
                "content": "Ingester successfully extracts 152 GOLD conversations",
                "type": "OUTCOME",
                "confidence": 0.9,
                "tags": ["success", "metrics"],
            },
        ],
        "edges": [
            {
                "from_node_id": "node_0",
                "to_node_id": "node_1",
                "edge_type": "enables",
                "strength": 0.8,
            },
        ],
        "tier": "GOLD",
        "texture": ["creating", "celebrating"],
    }

    test_conversation = {
        "uuid": "test-full-commit-001",
        "path": "/test/conversations/test-001.json",
        "created_at": "2025-07-15T10:30:00Z",
        "title": "Test Conversation",
    }

    result = await committer.commit_extraction(
        extraction=test_extraction,
        conversation=test_conversation,
        embedding_fn=embedding_fn,
    )

    print(f"\n  Commit Result:")
    print(f"    Status: {result['status']}")
    print(f"    Nodes committed: {result['nodes_committed']}")
    print(f"    Edges committed: {result['edges_committed']}")

    # Verify ingestion log
    async with aiosqlite.connect(str(test_db)) as db:
        cursor = await db.execute("""
            SELECT tier, texture, extraction_status, nodes_created, edges_created
            FROM transcript_ingestion_log
            WHERE conversation_uuid = ?
        """, (test_conversation["uuid"],))
        row = await cursor.fetchone()

        if row:
            print(f"\n  ✓ Ingestion log updated:")
            print(f"    Tier: {row[0]}")
            print(f"    Texture: {row[1]}")
            print(f"    Status: {row[2]}")
            print(f"    Nodes: {row[3]}, Edges: {row[4]}")

    # ========================================================================
    # TEST 5: Batch Commit
    # ========================================================================

    print("\n[6/6] Testing batch commit...")

    # Create batch of extractions
    batch_extractions = []
    for i in range(5):
        extraction = {
            "nodes": [
                {
                    "content": f"Batch test node {i}",
                    "type": "FACT",
                    "confidence": 0.7 + (i * 0.05),
                    "tags": ["batch", "test"],
                },
            ],
            "edges": [],
            "tier": "SILVER",
            "texture": ["working"],
        }

        conversation = {
            "uuid": f"batch-test-{i:03d}",
            "path": f"/test/batch/conv-{i:03d}.json",
            "created_at": f"2025-08-{i+1:02d}T12:00:00Z",
            "title": f"Batch Conversation {i}",
        }

        batch_extractions.append((extraction, conversation))

    # Progress callback
    def progress(current, total):
        print(f"  Progress: {current}/{total}")

    batch_result = await committer.commit_batch(
        extractions=batch_extractions,
        embedding_fn=embedding_fn,
        progress_callback=progress,
    )

    print(f"\n  Batch Commit Results:")
    print(f"    Total: {batch_result['total']}")
    print(f"    Successful: {batch_result['successful']}")
    print(f"    Failed: {batch_result['failed']}")
    print(f"    Nodes committed: {batch_result['nodes_committed']}")
    print(f"    Edges committed: {batch_result['edges_committed']}")

    # ========================================================================
    # Final Statistics
    # ========================================================================

    print("\n" + "=" * 70)
    print("FINAL DATABASE STATISTICS")
    print("=" * 70)

    async with aiosqlite.connect(str(test_db)) as db:
        # Total nodes
        cursor = await db.execute("SELECT COUNT(*) FROM nodes")
        total_nodes = (await cursor.fetchone())[0]

        # Total edges
        cursor = await db.execute("SELECT COUNT(*) FROM edges")
        total_edges = (await cursor.fetchone())[0]

        # Total embeddings
        cursor = await db.execute("SELECT COUNT(*) FROM node_embeddings")
        total_embeddings = (await cursor.fetchone())[0]

        # Total ingestion records
        cursor = await db.execute("SELECT COUNT(*) FROM transcript_ingestion_log")
        total_ingestions = (await cursor.fetchone())[0]

        # Lock-in distribution
        cursor = await db.execute("""
            SELECT
                CASE
                    WHEN lock_in < 0.2 THEN 'PRE_LUNA (0.05-0.15)'
                    WHEN lock_in < 0.4 THEN 'PROTO_LUNA (0.15-0.35)'
                    WHEN lock_in < 0.6 THEN 'LUNA_DEV (0.35-0.55)'
                    ELSE 'LUNA_LIVE (0.55-0.75)'
                END as era_range,
                COUNT(*) as count
            FROM nodes
            GROUP BY era_range
        """)
        lock_in_dist = await cursor.fetchall()

        print(f"\n📊 Database Contents:")
        print(f"  Nodes:       {total_nodes}")
        print(f"  Edges:       {total_edges}")
        print(f"  Embeddings:  {total_embeddings}")
        print(f"  Ingestions:  {total_ingestions}")

        print(f"\n🔒 Lock-In Distribution:")
        for era_range, count in lock_in_dist:
            print(f"  {era_range:25}: {count:3} nodes")

    # ========================================================================
    # Cleanup
    # ========================================================================

    print(f"\n🗑️  Cleaning up test database...")
    shutil.rmtree(temp_dir)

    print("\n" + "=" * 70)
    print("✅ Committer Test Complete")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
