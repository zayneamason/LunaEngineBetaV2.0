"""Test Matrix connection and memory search."""
import asyncio
from pathlib import Path

async def test():
    from luna.actors.matrix import MatrixActor

    db_path = Path("data/luna_engine.db")
    print(f"DB exists: {db_path.exists()}")
    if db_path.exists():
        print(f"DB size: {db_path.stat().st_size / 1024 / 1024:.1f} MB")

    matrix = MatrixActor(db_path=db_path)
    await matrix.initialize()

    print(f"Matrix ready: {matrix.is_ready}")
    print(f"Matrix has _matrix: {matrix._matrix is not None}")

    if matrix._matrix:
        stats = await matrix._matrix.get_stats()
        print(f"Stats: {stats}")

        # Try a search
        results = await matrix._matrix.search_nodes("marzipan", limit=5)
        print(f"Search 'marzipan': {len(results)} results")
        for r in results:
            print(f"  - [{r.node_type}] {r.content[:80]}...")

    await matrix.stop()

if __name__ == "__main__":
    asyncio.run(test())
