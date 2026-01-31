#!/usr/bin/env python3
"""
Populate FTS5 Index
===================

Backfills the FTS5 full-text search index from existing memory_nodes.
Run this once after adding FTS5 to the schema.

Usage:
    python scripts/populate_fts5.py [--db-path PATH]
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from luna.substrate.database import MemoryDatabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


async def populate_fts5(db_path: str) -> int:
    """
    Populate FTS5 index from existing memory_nodes.

    Args:
        db_path: Path to the SQLite database

    Returns:
        Number of nodes indexed
    """
    db = MemoryDatabase(Path(db_path))
    await db.connect()

    try:
        # Check if FTS5 table exists
        result = await db.fetchone("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='memory_nodes_fts'
        """)

        if not result:
            logger.error("FTS5 table 'memory_nodes_fts' not found!")
            logger.error("Run the schema.sql first to create the FTS5 virtual table.")
            return 0

        # Count existing nodes
        count_row = await db.fetchone("SELECT COUNT(*) FROM memory_nodes")
        total_nodes = count_row[0] if count_row else 0
        logger.info(f"Found {total_nodes} memory nodes to index")

        if total_nodes == 0:
            logger.info("No nodes to index")
            return 0

        # Clear existing FTS5 data (in case of re-run)
        await db.execute("DELETE FROM memory_nodes_fts")
        logger.info("Cleared existing FTS5 index")

        # Rebuild FTS5 index from memory_nodes
        # The 'rebuild' command re-indexes all content
        await db.execute("""
            INSERT INTO memory_nodes_fts(memory_nodes_fts)
            VALUES('rebuild')
        """)

        # Verify the index
        fts_count = await db.fetchone("SELECT COUNT(*) FROM memory_nodes_fts")
        indexed = fts_count[0] if fts_count else 0

        logger.info(f"FTS5 index populated: {indexed} nodes indexed")

        # Test a simple search
        test_result = await db.fetchone("""
            SELECT COUNT(*) FROM memory_nodes_fts
            WHERE memory_nodes_fts MATCH 'test OR luna'
        """)
        logger.info(f"Test search returned {test_result[0] if test_result else 0} matches")

        return indexed

    finally:
        await db.close()


async def main():
    parser = argparse.ArgumentParser(
        description="Populate FTS5 index from existing memory nodes"
    )
    parser.add_argument(
        "--db-path",
        default="data/luna_memory.db",
        help="Path to the SQLite database (default: data/luna_memory.db)"
    )
    args = parser.parse_args()

    # Resolve path relative to project root
    db_path = Path(args.db_path)
    if not db_path.is_absolute():
        db_path = Path(__file__).parent.parent / db_path

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        sys.exit(1)

    logger.info(f"Populating FTS5 index for: {db_path}")
    count = await populate_fts5(str(db_path))

    if count > 0:
        logger.info(f"Successfully indexed {count} nodes")
    else:
        logger.warning("No nodes were indexed")


if __name__ == "__main__":
    asyncio.run(main())
