#!/usr/bin/env python3
"""
Test Real Embeddings - Unlock Resolver with Local Sentence-Transformers

Tests node deduplication and cross-conversation edge discovery
with REAL semantic embeddings (not mocks).

Expected results:
- Node dedup: 10-15% reduction from semantic similarity
- Cross-edges: 20-30 edges discovered across conversations
"""

import sys
import os
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp_server.ingester.resolver import TranscriptResolver
from mcp_server.ingester.embeddings import SentenceTransformerEmbeddings


def classify_era(date_str: str) -> str:
    """Classify conversation era from date."""
    ERAS = {
        "PRE_LUNA": ("2023-01-01", "2024-06-01"),
        "PROTO_LUNA": ("2024-06-01", "2025-01-01"),
        "LUNA_DEV": ("2025-01-01", "2025-10-01"),
        "LUNA_LIVE": ("2025-10-01", "2030-01-01"),
    }

    date = date_str[:10]

    for era, (start, end) in ERAS.items():
        if start <= date < end:
            return era

    return "LUNA_LIVE"


async def main():
    print("=" * 70)
    print("REAL EMBEDDINGS TEST - Unlock Node Dedup & Cross-Edges")
    print("=" * 70)

    # ========================================================================
    # Load Extraction Data
    # ========================================================================

    print("\n[1/4] Loading extraction results...")

    sample_path = Path(__file__).parent / "extraction_sample_results.json"
    with open(sample_path) as f:
        sample_data = json.load(f)

    successful = [
        r for r in sample_data["results"]
        if r["extraction"].get("extraction_status") == "complete"
    ]

    # Prepare nodes
    all_nodes = []
    for r in successful:
        conv = r["conversation"]
        ext = r["extraction"]

        for node in ext.get("nodes", []):
            node["source_conversation"] = conv["uuid"]
            node["source_date"] = conv["created_at"][:10]
            node["extraction_era"] = classify_era(conv["created_at"])
            all_nodes.append(node)

    print(f"✓ Loaded {len(successful)} conversations")
    print(f"✓ Total nodes: {len(all_nodes)}")

    # ========================================================================
    # Initialize Real Embeddings
    # ========================================================================

    print("\n[2/4] Initializing sentence-transformers embeddings...")

    try:
        embedding_fn = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")
        print(f"✓ Using model: {embedding_fn.model_name} ({embedding_fn.dimension} dimensions)")
    except Exception as e:
        print(f"\n❌ Failed to initialize embeddings: {e}")
        return 1

    # ========================================================================
    # Test Node Deduplication
    # ========================================================================

    print("\n[3/4] Running node deduplication with real embeddings...")
    print("  Threshold: 0.93 (strict semantic similarity)")

    resolver = TranscriptResolver(embedding_fn=embedding_fn)

    try:
        deduped_nodes = await resolver.deduplicate_nodes(
            all_nodes=all_nodes,
            similarity_threshold=0.93,
        )

        reduction = len(all_nodes) - len(deduped_nodes)
        reduction_pct = (reduction / len(all_nodes)) * 100

        print(f"\n  ✓ Deduplication complete:")
        print(f"    Before: {len(all_nodes)} nodes")
        print(f"    After:  {len(deduped_nodes)} nodes")
        print(f"    Reduced: {reduction} nodes ({reduction_pct:.1f}%)")

        # Show merged clusters
        merged = [n for n in deduped_nodes if n.get("merged_from_count", 1) > 1]
        if merged:
            print(f"\n  📦 Merged Clusters: {len(merged)}")
            for i, node in enumerate(merged[:3], 1):
                print(f"\n    {i}. [{node['type']}] {node['content'][:60]}...")
                print(f"       Merged from {node['merged_from_count']} duplicates")

    except Exception as e:
        print(f"\n❌ Deduplication failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ========================================================================
    # Test Cross-Conversation Edge Discovery
    # ========================================================================

    print("\n[4/4] Discovering cross-conversation edges...")
    print("  Threshold: 0.76 (moderate semantic similarity)")

    try:
        cross_edges = await resolver.discover_cross_edges(
            all_nodes=deduped_nodes,
            similarity_threshold=0.76,
            max_edges_per_node=5,
        )

        print(f"\n  ✓ Edge discovery complete:")
        print(f"    Edges found: {len(cross_edges)}")

        if cross_edges:
            # Edge type distribution
            edge_types = {}
            for edge in cross_edges:
                etype = edge.get("edge_type", "unknown")
                edge_types[etype] = edge_types.get(etype, 0) + 1

            print(f"\n  🔗 Edge Type Distribution:")
            for etype in sorted(edge_types, key=edge_types.get, reverse=True):
                count = edge_types[etype]
                print(f"    {etype:15}: {count:3}")

            # Sample edges
            print(f"\n  Sample cross-conversation edges:")
            for i, edge in enumerate(cross_edges[:3], 1):
                from_node = next((n for n in deduped_nodes if n.get("_id") == edge["from_node_id"]), None)
                to_node = next((n for n in deduped_nodes if n.get("_id") == edge["to_node_id"]), None)

                if from_node and to_node:
                    print(f"\n    {i}. [{edge['edge_type']}] Strength: {edge['strength']:.2f}")
                    print(f"       {from_node['content'][:50]}...")
                    print(f"       → {to_node['content'][:50]}...")

    except Exception as e:
        print(f"\n❌ Edge discovery failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ========================================================================
    # Usage Statistics
    # ========================================================================

    print("\n" + "=" * 70)
    print("EMBEDDING USAGE STATISTICS")
    print("=" * 70)

    stats = embedding_fn.get_stats()
    print(f"\n🧠 Sentence-Transformers (Local):")
    print(f"  Requests: {stats['total_requests']}")
    print(f"  Texts embedded: {stats['total_texts']:,}")
    print(f"  Cost: $0.00 (local inference)")

    # ========================================================================
    # Save Results
    # ========================================================================

    output_path = Path(__file__).parent / "real_embeddings_test_results.json"
    with open(output_path, 'w') as f:
        json.dump({
            "deduplication": {
                "before": len(all_nodes),
                "after": len(deduped_nodes),
                "reduction": reduction,
                "reduction_pct": reduction_pct,
                "merged_clusters": len(merged),
            },
            "cross_edges": {
                "total": len(cross_edges),
                "by_type": edge_types if cross_edges else {},
            },
            "embedding_stats": stats,
        }, f, indent=2)

    print(f"\n✓ Results saved to: {output_path}")

    print("\n" + "=" * 70)
    print("✅ Real Embeddings Test Complete")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
