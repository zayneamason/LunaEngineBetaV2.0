#!/usr/bin/env python3
"""
Commit Sample Extractions to Sandbox - Make data visible in Observatory

Takes the 7 successful extractions from test_extraction_sample.py and commits
them to the actual sandbox database so you can browse them in the Observatory UI.
"""

import sys
import os
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp_server.ingester.committer import TranscriptCommitter


class MockEmbedding:
    """Mock embedding function for testing."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings (all zeros for simplicity)."""
        return [[0.0] * self.dimension for _ in texts]


async def main():
    print("=" * 70)
    print("COMMIT SAMPLE EXTRACTIONS TO SANDBOX")
    print("=" * 70)

    # ========================================================================
    # Load Extraction Results
    # ========================================================================

    print("\n[1/3] Loading extraction sample results...")

    sample_path = Path(__file__).parent / "extraction_sample_results.json"
    if not sample_path.exists():
        print(f"\n❌ ERROR: {sample_path} not found")
        print("Run test_extraction_sample.py first")
        return 1

    with open(sample_path) as f:
        sample_data = json.load(f)

    successful = [
        r for r in sample_data["results"]
        if r["extraction"].get("extraction_status") == "complete"
    ]

    print(f"✓ Loaded {len(successful)} successful extractions")

    # ========================================================================
    # Setup Committer with Sandbox Database
    # ========================================================================

    print("\n[2/3] Setting up committer with sandbox database...")

    sandbox_db = Path(__file__).parent / "sandbox_matrix.db"

    if not sandbox_db.exists():
        print(f"\n❌ ERROR: Sandbox database not found at {sandbox_db}")
        print("Run the sandbox initialization first")
        return 1

    print(f"✓ Using sandbox database: {sandbox_db}")

    committer = TranscriptCommitter(str(sandbox_db))
    embedding_fn = MockEmbedding(dimension=384)

    # ========================================================================
    # Commit Extractions
    # ========================================================================

    print(f"\n[3/3] Committing {len(successful)} extractions to sandbox...")

    # Prepare batch
    batch_extractions = []
    for r in successful:
        extraction = r["extraction"]
        conversation = r["conversation"]
        batch_extractions.append((extraction, conversation))

    # Progress callback
    def progress(current, total):
        print(f"  [{current}/{total}] Committed: {batch_extractions[current-1][1]['title'][:50]}")

    # Commit batch
    result = await committer.commit_batch(
        extractions=batch_extractions,
        embedding_fn=embedding_fn,
        progress_callback=progress,
    )

    # ========================================================================
    # Results
    # ========================================================================

    print("\n" + "=" * 70)
    print("COMMIT RESULTS")
    print("=" * 70)

    print(f"\n📊 Batch Summary:")
    print(f"  Total extractions: {result['total']}")
    print(f"  Successful: {result['successful']}")
    print(f"  Failed: {result['failed']}")
    print(f"  Nodes committed: {result['nodes_committed']}")
    print(f"  Edges committed: {result['edges_committed']}")

    if result['errors']:
        print(f"\n❌ Errors:")
        for error in result['errors']:
            print(f"  • {error}")

    # ========================================================================
    # Next Steps
    # ========================================================================

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)

    print("\nTo view in Observatory UI:")
    print("  1. Start the MCP server:")
    print("     cd mcp_server && python server.py")
    print("\n  2. In another terminal, start the frontend:")
    print("     cd frontend && npm run dev")
    print("\n  3. Open http://localhost:5173")
    print(f"\n  4. Browse {result['nodes_committed']} nodes and {result['edges_committed']} edges")

    print("\n" + "=" * 70)
    print("✅ Sample Extractions Committed to Sandbox")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
