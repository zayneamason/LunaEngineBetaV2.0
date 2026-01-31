#!/usr/bin/env python3
"""
Backfill Embeddings
===================

Generates embeddings for existing memory_nodes using local MiniLM model.
Estimated time: ~50ms per node → 22K nodes ≈ 18 minutes

Features:
- Resumable: tracks progress, skips already-embedded nodes
- Batch processing: 32 nodes at a time for efficiency
- Progress reporting: shows percentage and ETA

Usage:
    python scripts/backfill_embeddings.py [--db-path PATH] [--batch-size N]
"""

import argparse
import asyncio
import logging
import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from luna.substrate.database import MemoryDatabase
from luna.substrate.local_embeddings import get_embeddings, EMBEDDING_DIM
from luna.substrate.embeddings import EmbeddingStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


async def backfill_embeddings(
    db_path: str,
    batch_size: int = 32,
    limit: int = 0,
) -> tuple[int, int]:
    """
    Generate embeddings for all nodes without embeddings.

    Args:
        db_path: Path to the SQLite database
        batch_size: Number of nodes to process per batch
        limit: Max nodes to process (0 = no limit)

    Returns:
        Tuple of (nodes_processed, nodes_skipped)
    """
    db = MemoryDatabase(Path(db_path))
    await db.connect()

    # Initialize embedding store with 384 dimensions for local model
    store = EmbeddingStore(db, dim=EMBEDDING_DIM, table_name="memory_embeddings_local")
    vec_available = await store.initialize()

    if not vec_available:
        logger.error("sqlite-vec not available! Cannot store embeddings.")
        logger.error("Install with: pip install sqlite-vec")
        await db.close()
        return 0, 0

    # Get the local embeddings model
    embeddings = get_embeddings()
    logger.info(f"Using model: {embeddings.model_name} ({embeddings.dim} dimensions)")

    # Preload the model
    logger.info("Loading embedding model...")
    embeddings.preload()
    logger.info("Model loaded")

    try:
        # Count total nodes
        total_row = await db.fetchone("SELECT COUNT(*) FROM memory_nodes")
        total_nodes = total_row[0] if total_row else 0

        # Count already embedded nodes
        embedded_row = await db.fetchone(f"SELECT COUNT(*) FROM {store.table_name}")
        already_embedded = embedded_row[0] if embedded_row else 0

        nodes_to_process = total_nodes - already_embedded
        if limit > 0:
            nodes_to_process = min(nodes_to_process, limit)

        logger.info(f"Total nodes: {total_nodes}")
        logger.info(f"Already embedded: {already_embedded}")
        logger.info(f"To process: {nodes_to_process}")

        if nodes_to_process == 0:
            logger.info("All nodes already have embeddings!")
            return 0, already_embedded

        # Get nodes without embeddings
        query = f"""
            SELECT m.id, m.content, m.summary
            FROM memory_nodes m
            LEFT JOIN {store.table_name} e ON m.id = e.node_id
            WHERE e.node_id IS NULL
            ORDER BY m.created_at DESC
        """
        if limit > 0:
            query += f" LIMIT {limit}"

        rows = await db.fetchall(query)

        processed = 0
        start_time = time.time()
        batch_texts = []
        batch_ids = []

        for row in rows:
            node_id, content, summary = row[0], row[1], row[2]

            # Combine content and summary for embedding
            text = content or ""
            if summary:
                text = f"{summary}\n{text}"

            batch_ids.append(node_id)
            batch_texts.append(text)

            # Process batch when full
            if len(batch_texts) >= batch_size:
                vectors = embeddings.encode_batch(batch_texts, show_progress=False)

                for nid, vec in zip(batch_ids, vectors):
                    await store.store(nid, vec)

                processed += len(batch_ids)
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                eta = (nodes_to_process - processed) / rate if rate > 0 else 0

                logger.info(
                    f"Progress: {processed}/{nodes_to_process} "
                    f"({100*processed/nodes_to_process:.1f}%) "
                    f"- {rate:.1f} nodes/sec - ETA: {eta:.0f}s"
                )

                batch_texts = []
                batch_ids = []

        # Process remaining batch
        if batch_texts:
            vectors = embeddings.encode_batch(batch_texts, show_progress=False)
            for nid, vec in zip(batch_ids, vectors):
                await store.store(nid, vec)
            processed += len(batch_ids)

        elapsed = time.time() - start_time
        logger.info(f"Completed: {processed} nodes in {elapsed:.1f}s")

        return processed, already_embedded

    finally:
        await db.close()


async def main():
    parser = argparse.ArgumentParser(
        description="Generate embeddings for existing memory nodes"
    )
    parser.add_argument(
        "--db-path",
        default="data/luna_memory.db",
        help="Path to the SQLite database (default: data/luna_memory.db)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=32,
        help="Batch size for embedding generation (default: 32)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max nodes to process, 0 for all (default: 0)"
    )
    args = parser.parse_args()

    # Resolve path relative to project root
    db_path = Path(args.db_path)
    if not db_path.is_absolute():
        db_path = Path(__file__).parent.parent / db_path

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        sys.exit(1)

    logger.info(f"Backfilling embeddings for: {db_path}")
    processed, skipped = await backfill_embeddings(
        str(db_path),
        batch_size=args.batch_size,
        limit=args.limit,
    )

    logger.info(f"Done! Processed: {processed}, Already embedded: {skipped}")


if __name__ == "__main__":
    asyncio.run(main())
