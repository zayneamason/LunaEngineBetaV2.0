#!/usr/bin/env python3
"""
Backfill Entity Mentions

This script populates the entity_mentions table by scanning all existing
memory_nodes for entity references. This is a one-time migration to fix
the missing entity-to-memory links.

Usage:
    python scripts/backfill_entity_mentions.py [--dry-run] [--limit N] [--batch-size N]

Options:
    --dry-run       Show what would be done without making changes
    --limit N       Only process N nodes (for testing)
    --batch-size N  Process N nodes at a time (default: 100)
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from luna.substrate.database import MemoryDatabase
from luna.entities.resolution import EntityResolver

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def backfill_mentions(
    db_path: str = "data/luna_engine.db",
    dry_run: bool = False,
    limit: int = None,
    batch_size: int = 100,
) -> dict:
    """
    Backfill entity_mentions table from existing memory_nodes.

    Args:
        db_path: Path to SQLite database
        dry_run: If True, don't write changes
        limit: Max nodes to process (None = all)
        batch_size: Process this many nodes at a time

    Returns:
        Statistics dict
    """
    stats = {
        'nodes_scanned': 0,
        'nodes_with_mentions': 0,
        'total_mentions_created': 0,
        'entities_found': set(),
        'errors': 0,
        'start_time': datetime.now().isoformat(),
    }

    logger.info(f"Starting entity mention backfill (dry_run={dry_run})")
    logger.info(f"Database: {db_path}")

    # Initialize database and resolver
    db = MemoryDatabase(Path(db_path))
    await db.connect()
    resolver = EntityResolver(db)

    try:
        # Get total count
        row = await db.fetchone("SELECT COUNT(*) FROM memory_nodes")
        total_nodes = row[0] if row else 0
        logger.info(f"Total memory nodes: {total_nodes}")

        if limit:
            total_nodes = min(total_nodes, limit)
            logger.info(f"Processing limited to {total_nodes} nodes")

        # Check existing mentions
        row = await db.fetchone("SELECT COUNT(*) FROM entity_mentions")
        existing_mentions = row[0] if row else 0
        logger.info(f"Existing entity mentions: {existing_mentions}")

        # Get all entities for reference
        rows = await db.fetchall("SELECT id, name, entity_type FROM entities")
        entities_in_db = {row[0]: (row[1], row[2]) for row in rows}
        logger.info(f"Entities in database: {len(entities_in_db)}")

        # Process nodes in batches
        offset = 0
        processed = 0

        while processed < total_nodes:
            batch_limit = min(batch_size, total_nodes - processed)

            rows = await db.fetchall(
                """
                SELECT id, node_type, content
                FROM memory_nodes
                ORDER BY created_at ASC
                LIMIT ? OFFSET ?
                """,
                (batch_limit, offset)
            )

            if not rows:
                break

            for row in rows:
                node_id, node_type, content = row[0], row[1], row[2]
                stats['nodes_scanned'] += 1

                if not content:
                    continue

                # Detect entities in this node
                try:
                    entities = await resolver.detect_mentions(content)

                    if entities:
                        stats['nodes_with_mentions'] += 1

                        for entity in entities:
                            stats['entities_found'].add(entity.id)

                            # Create context snippet
                            name_lower = entity.name.lower()
                            content_lower = content.lower()
                            pos = content_lower.find(name_lower)
                            if pos >= 0:
                                start = max(0, pos - 30)
                                end = min(len(content), pos + len(entity.name) + 70)
                                snippet = content[start:end]
                                if start > 0:
                                    snippet = "..." + snippet
                                if end < len(content):
                                    snippet = snippet + "..."
                            else:
                                snippet = content[:100] + "..." if len(content) > 100 else content

                            if not dry_run:
                                # Check if mention already exists
                                existing = await db.fetchone(
                                    "SELECT 1 FROM entity_mentions WHERE entity_id = ? AND node_id = ?",
                                    (entity.id, node_id)
                                )
                                if not existing:
                                    await resolver.create_mention(
                                        entity_id=entity.id,
                                        node_id=node_id,
                                        mention_type="reference",
                                        confidence=1.0,
                                        context_snippet=snippet,
                                    )
                                    stats['total_mentions_created'] += 1
                            else:
                                stats['total_mentions_created'] += 1

                except Exception as e:
                    stats['errors'] += 1
                    logger.warning(f"Error processing node {node_id}: {e}")

            processed += len(rows)
            offset += batch_limit

            # Progress update
            pct = (processed / total_nodes) * 100
            logger.info(
                f"Progress: {processed}/{total_nodes} ({pct:.1f}%) - "
                f"Mentions: {stats['total_mentions_created']}, "
                f"Entities: {len(stats['entities_found'])}"
            )

        stats['end_time'] = datetime.now().isoformat()
        stats['entities_found'] = list(stats['entities_found'])

        return stats

    finally:
        await db.close()


def print_stats(stats: dict, dry_run: bool):
    """Print backfill statistics."""
    print("\n" + "=" * 60)
    print("BACKFILL COMPLETE" + (" (DRY RUN)" if dry_run else ""))
    print("=" * 60)
    print(f"Nodes scanned:       {stats['nodes_scanned']:,}")
    print(f"Nodes with mentions: {stats['nodes_with_mentions']:,}")
    print(f"Mentions created:    {stats['total_mentions_created']:,}")
    print(f"Unique entities:     {len(stats['entities_found'])}")
    print(f"Errors:              {stats['errors']}")
    print("=" * 60)

    if stats['entities_found']:
        print("\nEntities linked:")
        for entity_id in sorted(stats['entities_found'])[:20]:
            print(f"  - {entity_id}")
        if len(stats['entities_found']) > 20:
            print(f"  ... and {len(stats['entities_found']) - 20} more")


async def main():
    parser = argparse.ArgumentParser(description="Backfill entity mentions")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only process N nodes (for testing)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Process N nodes at a time (default: 100)"
    )
    parser.add_argument(
        "--db",
        type=str,
        default="data/luna_engine.db",
        help="Path to database (default: data/luna_engine.db)"
    )

    args = parser.parse_args()

    stats = await backfill_mentions(
        db_path=args.db,
        dry_run=args.dry_run,
        limit=args.limit,
        batch_size=args.batch_size,
    )

    print_stats(stats, args.dry_run)

    if args.dry_run:
        print("\nThis was a dry run. Run without --dry-run to apply changes.")


if __name__ == "__main__":
    asyncio.run(main())
