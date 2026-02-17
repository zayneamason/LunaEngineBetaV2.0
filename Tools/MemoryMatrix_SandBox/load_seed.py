#!/usr/bin/env python
"""Quick script to load entity_graph seed into the sandbox."""
import asyncio
from pathlib import Path
import sys

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from mcp_server.event_bus import EventBus
from mcp_server.sandbox_matrix import SandboxMatrix

async def main():
    bus = EventBus()
    matrix = SandboxMatrix(bus)
    await matrix.initialize()

    print("Loading entity_graph seed...")
    await matrix.seed("entity_graph")
    print("✅ Seed loaded successfully!")

    # Show stats
    stats = await matrix.stats()
    print(f"\nDatabase stats:")
    print(f"  Nodes: {stats['node_count']}")
    print(f"  Edges: {stats['edge_count']}")
    print(f"  Clusters: {stats['cluster_count']}")

    # Show entities
    entities = await matrix.list_entities()
    print(f"  Entities: {len(entities)}")
    for entity in entities:
        print(f"    - {entity['name']} ({entity['type']})")

    # Show quests
    quests = await matrix.list_quests()
    print(f"  Quests generated: {len(quests)}")
    for quest in quests[:3]:
        print(f"    - {quest['title']}")

    await matrix.close()

if __name__ == "__main__":
    asyncio.run(main())
