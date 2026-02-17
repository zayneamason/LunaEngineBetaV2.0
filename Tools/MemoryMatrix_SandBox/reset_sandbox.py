#!/usr/bin/env python3
"""Reset sandbox database to clean slate for proper pipeline testing."""

import asyncio
import aiosqlite
from pathlib import Path


async def main():
    sandbox_db = Path(__file__).parent / "sandbox_matrix.db"

    print("Resetting sandbox database...")

    async with aiosqlite.connect(sandbox_db) as db:
        # Disable foreign keys
        await db.execute("PRAGMA foreign_keys = OFF")

        # Delete ingestion data
        await db.execute("DELETE FROM transcript_ingestion_log")
        await db.execute("DELETE FROM edges")
        # Skip node_embeddings (uses vec0 module which may not be loaded)

        # Delete nodes (will cascade to FTS via triggers)
        # Get all node IDs first to avoid FTS virtual table issues
        cursor = await db.execute("SELECT id FROM nodes")
        node_ids = [row[0] for row in await cursor.fetchall()]

        print(f"Deleting {len(node_ids)} nodes...")

        for node_id in node_ids:
            await db.execute("DELETE FROM nodes WHERE id = ?", (node_id,))

        await db.commit()

        # Verify
        cursor = await db.execute("SELECT COUNT(*) FROM nodes")
        node_count = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM edges")
        edge_count = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM transcript_ingestion_log")
        log_count = (await cursor.fetchone())[0]

        print(f"\n✓ Database reset complete:")
        print(f"  Nodes: {node_count}")
        print(f"  Edges: {edge_count}")
        print(f"  Ingestion log: {log_count}")

        # Re-enable foreign keys
        await db.execute("PRAGMA foreign_keys = ON")
        await db.commit()


if __name__ == "__main__":
    asyncio.run(main())
