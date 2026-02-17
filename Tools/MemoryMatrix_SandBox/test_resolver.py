#!/usr/bin/env python3
"""
Resolver Test - Test entity merge, node dedup, cross-conversation edges

Validates resolver functionality on extracted sample data:
- Entity resolution (merge entities by canonical name)
- Node deduplication (0.93 threshold, type+date aware)
- Cross-conversation edge discovery (0.76 threshold)
- Edge validation (temporal sanity, strength floor)
"""

import sys
import os
import json
import asyncio
import hashlib
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent))

from mcp_server.ingester.resolver import TranscriptResolver
from mcp_server.ingester.extractor import TranscriptExtractor


def classify_era(date_str: str) -> str:
    """Classify conversation era from date."""
    ERAS = {
        "PRE_LUNA": ("2023-01-01", "2024-06-01"),
        "PROTO_LUNA": ("2024-06-01", "2025-01-01"),
        "LUNA_DEV": ("2025-01-01", "2025-10-01"),
        "LUNA_LIVE": ("2025-10-01", "2030-01-01"),
    }

    date = date_str[:10]  # YYYY-MM-DD

    for era, (start, end) in ERAS.items():
        if start <= date < end:
            return era

    return "LUNA_LIVE"


class MockEmbedding:
    """Mock embedding function for testing (deterministic based on content hash)."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def __call__(self, texts: List[str]) -> List[List[float]]:
        """Generate deterministic embeddings from text content."""
        embeddings = []

        for text in texts:
            # Hash text to get deterministic seed
            seed = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)

            # Generate pseudo-random vector (deterministic from seed)
            import random
            rng = random.Random(seed)
            vec = [rng.gauss(0, 1) for _ in range(self.dimension)]

            # Normalize to unit vector
            norm = sum(x*x for x in vec) ** 0.5
            vec = [x / norm for x in vec]

            embeddings.append(vec)

        return embeddings


async def main():
    print("=" * 70)
    print("RESOLVER TEST - Entity Merge, Node Dedup, Cross-Conversation Edges")
    print("=" * 70)

    # ========================================================================
    # Load Extraction Results
    # ========================================================================

    print("\n[1/5] Loading extraction sample results...")

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
    # TEST 1: Entity Resolution
    # ========================================================================

    print("\n[2/5] Testing entity resolution...")

    resolver = TranscriptResolver()

    # Prepare extraction data
    all_extractions = []
    for r in successful:
        conv = r["conversation"]
        ext = r["extraction"]

        all_extractions.append({
            "conversation_uuid": conv["uuid"],
            "conversation_date": conv["created_at"][:10],
            "entities": ext.get("entities", []),
        })

    # Resolve entities
    merged_entities = resolver.resolve_entities(all_extractions)

    print(f"\n  Results:")
    print(f"    Total entity mentions: {sum(len(e['entities']) for e in all_extractions)}")
    print(f"    Merged entities: {len(merged_entities)}")
    print(f"    Deduplication rate: {(1 - len(merged_entities) / sum(len(e['entities']) for e in all_extractions)) * 100:.1f}%")

    # Show sample merged entities
    print(f"\n  Top 5 entities by mention count:")
    sorted_entities = sorted(merged_entities, key=lambda e: e["mention_count"], reverse=True)[:5]
    for i, entity in enumerate(sorted_entities, 1):
        print(f"    {i}. {entity['name']} ({entity['type']})")
        print(f"       Mentions: {entity['mention_count']}, Conversations: {len(entity['conversations'])}")
        if entity.get("aliases"):
            print(f"       Aliases: {', '.join(list(entity['aliases'])[:3])}")

    # ========================================================================
    # TEST 2: Node Deduplication
    # ========================================================================

    print("\n[3/5] Testing node deduplication...")

    # Prepare all nodes
    all_nodes = []
    for r in successful:
        conv = r["conversation"]
        ext = r["extraction"]

        for node in ext.get("nodes", []):
            # Add metadata
            node["source_conversation"] = conv["uuid"]
            node["source_date"] = conv["created_at"][:10]
            node["extraction_era"] = classify_era(conv["created_at"])
            all_nodes.append(node)

    print(f"\n  Total nodes before deduplication: {len(all_nodes)}")

    # Deduplicate with mock embeddings
    embedding_fn = MockEmbedding(dimension=384)
    resolver_with_embeddings = TranscriptResolver(embedding_fn=embedding_fn)

    deduped_nodes = await resolver_with_embeddings.deduplicate_nodes(
        all_nodes=all_nodes,
        similarity_threshold=0.93,
    )

    print(f"  Deduplicated nodes: {len(deduped_nodes)}")
    print(f"  Deduplication rate: {(1 - len(deduped_nodes) / len(all_nodes)) * 100:.1f}%")

    # Check for merged nodes
    merged_count = sum(1 for n in deduped_nodes if n.get("merged_from_count", 1) > 1)
    print(f"  Merged clusters: {merged_count}")

    if merged_count > 0:
        print(f"\n  Sample merged nodes:")
        merged_nodes = [n for n in deduped_nodes if n.get("merged_from_count", 1) > 1][:3]
        for i, node in enumerate(merged_nodes, 1):
            print(f"    {i}. [{node['type']}] {node['content'][:60]}...")
            print(f"       Merged from {node['merged_from_count']} duplicates")
            print(f"       Provenance: {len(node.get('provenance_sources', []))} sources")

    # ========================================================================
    # TEST 3: Cross-Conversation Edge Discovery
    # ========================================================================

    print("\n[4/5] Testing cross-conversation edge discovery...")

    # Assign IDs to nodes (simulate database IDs)
    for i, node in enumerate(deduped_nodes):
        node["_id"] = f"node_{i}"

    # Discover edges
    cross_edges = await resolver_with_embeddings.discover_cross_edges(
        all_nodes=deduped_nodes,
        similarity_threshold=0.76,
        max_edges_per_node=5,
    )

    print(f"\n  Cross-conversation edges discovered: {len(cross_edges)}")

    if len(cross_edges) > 0:
        # Edge type distribution
        edge_types = {}
        for edge in cross_edges:
            etype = edge.get("edge_type", "unknown")
            edge_types[etype] = edge_types.get(etype, 0) + 1

        print(f"\n  Edge type distribution:")
        for etype in sorted(edge_types, key=edge_types.get, reverse=True):
            count = edge_types[etype]
            print(f"    {etype:15}: {count:3}")

        # Sample edges
        print(f"\n  Sample cross-conversation edges:")
        for i, edge in enumerate(cross_edges[:5], 1):
            from_node = next((n for n in deduped_nodes if n["_id"] == edge["from_node_id"]), None)
            to_node = next((n for n in deduped_nodes if n["_id"] == edge["to_node_id"]), None)

            if from_node and to_node:
                print(f"\n    {i}. [{edge['edge_type']}] Strength: {edge['strength']:.2f}")
                print(f"       From: [{from_node['type']}] {from_node['content'][:50]}...")
                print(f"       To:   [{to_node['type']}] {to_node['content'][:50]}...")
    else:
        print("  ⚠️  No cross-conversation edges discovered")
        print("     (This may be expected if nodes are highly dissimilar)")

    # ========================================================================
    # TEST 4: Edge Validation
    # ========================================================================

    print("\n[5/5] Testing edge validation...")

    # Create node lookup
    node_map = {n["_id"]: n for n in deduped_nodes}

    # Validate all edges
    valid_edges = []
    invalid_edges = []

    for edge in cross_edges:
        if resolver.validate_edge(edge, node_map):
            valid_edges.append(edge)
        else:
            invalid_edges.append(edge)

    print(f"\n  Valid edges: {len(valid_edges)}/{len(cross_edges)}")
    print(f"  Invalid edges: {len(invalid_edges)}/{len(cross_edges)}")

    if invalid_edges:
        print(f"\n  Rejection reasons:")
        for edge in invalid_edges[:3]:
            from_node = node_map.get(edge["from_node_id"])
            to_node = node_map.get(edge["to_node_id"])

            reasons = []
            if edge["from_node_id"] == edge["to_node_id"]:
                reasons.append("self-loop")
            if edge.get("strength", 0) < 0.15:
                reasons.append(f"weak ({edge.get('strength', 0):.2f})")
            if edge["edge_type"] == "enables" and from_node and to_node:
                if from_node.get("source_date", "") > to_node.get("source_date", ""):
                    reasons.append("temporal violation")

            print(f"    • {', '.join(reasons)}")

    # ========================================================================
    # Summary Statistics
    # ========================================================================

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print(f"\n📊 Resolver Performance:")
    print(f"  Entities:")
    print(f"    Before: {sum(len(e['entities']) for e in all_extractions)}")
    print(f"    After:  {len(merged_entities)}")
    print(f"    Reduction: {(1 - len(merged_entities) / sum(len(e['entities']) for e in all_extractions)) * 100:.1f}%")

    print(f"\n  Nodes:")
    print(f"    Before: {len(all_nodes)}")
    print(f"    After:  {len(deduped_nodes)}")
    print(f"    Reduction: {(1 - len(deduped_nodes) / len(all_nodes)) * 100:.1f}%")
    print(f"    Merged clusters: {merged_count}")

    print(f"\n  Edges:")
    print(f"    Discovered: {len(cross_edges)}")
    print(f"    Valid: {len(valid_edges)}")
    print(f"    Invalid: {len(invalid_edges)}")

    # ========================================================================
    # Save Results
    # ========================================================================

    output_path = Path(__file__).parent / "resolver_test_results.json"
    with open(output_path, 'w') as f:
        json.dump({
            "merged_entities": merged_entities,
            "deduplicated_nodes": deduped_nodes,
            "cross_conversation_edges": valid_edges,
            "statistics": {
                "entity_reduction_rate": (1 - len(merged_entities) / sum(len(e['entities']) for e in all_extractions)),
                "node_reduction_rate": (1 - len(deduped_nodes) / len(all_nodes)),
                "merged_cluster_count": merged_count,
                "edges_discovered": len(cross_edges),
                "edges_valid": len(valid_edges),
                "edges_invalid": len(invalid_edges),
            }
        }, f, indent=2)

    print(f"\n✓ Saved results to: {output_path}")

    # ========================================================================
    # Quality Assessment
    # ========================================================================

    print("\n" + "=" * 70)
    print("QUALITY ASSESSMENT")
    print("=" * 70)

    # Entity resolution quality
    entity_quality = "✅ GOOD" if len(merged_entities) < sum(len(e['entities']) for e in all_extractions) * 0.8 else "⚠️  LOW"
    print(f"\n  Entity Resolution: {entity_quality}")
    print(f"    Merged {sum(len(e['entities']) for e in all_extractions) - len(merged_entities)} duplicate entities")

    # Node deduplication quality
    node_quality = "✅ GOOD" if merged_count > 0 else "⚠️  NO DUPLICATES FOUND"
    print(f"\n  Node Deduplication: {node_quality}")
    if merged_count > 0:
        print(f"    Found {merged_count} clusters of similar nodes")
    else:
        print(f"    (May indicate threshold is too strict or nodes are diverse)")

    # Edge discovery quality
    edge_quality = "✅ GOOD" if len(valid_edges) > 0 else "⚠️  NO EDGES"
    print(f"\n  Cross-Conversation Edges: {edge_quality}")
    if len(valid_edges) > 0:
        print(f"    Discovered {len(valid_edges)} valid connections")
        avg_strength = sum(e["strength"] for e in valid_edges) / len(valid_edges)
        print(f"    Average strength: {avg_strength:.2f}")
    else:
        print(f"    (May indicate threshold is too strict or conversations are isolated)")

    # Edge validation quality
    if len(cross_edges) > 0:
        validation_rate = len(valid_edges) / len(cross_edges)
        validation_quality = "✅ GOOD" if validation_rate > 0.8 else "⚠️  LOW"
        print(f"\n  Edge Validation: {validation_quality}")
        print(f"    {validation_rate * 100:.1f}% of edges passed validation")

    print("\n" + "=" * 70)
    print("✅ Resolver Test Complete")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
