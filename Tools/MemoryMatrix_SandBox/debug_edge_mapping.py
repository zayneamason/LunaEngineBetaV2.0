#!/usr/bin/env python3
"""Debug edge mapping issue."""

import json
from pathlib import Path

# Load extraction results
sample_path = Path(__file__).parent / "extraction_sample_results.json"
with open(sample_path) as f:
    sample_data = json.load(f)

successful = [
    r for r in sample_data["results"]
    if r["extraction"].get("extraction_status") == "complete"
]

# Check first extraction with edges
for r in successful:
    edges = r["extraction"].get("edges", [])
    nodes = r["extraction"].get("nodes", [])

    if edges:
        print(f"\n{'='*70}")
        print(f"Conversation: {r['conversation']['title']}")
        print(f"Nodes: {len(nodes)}, Edges: {len(edges)}")
        print(f"{'='*70}")

        # Simulate node_id_map creation
        node_id_map = {f"node_{i}": f"uuid_{i}" for i in range(len(nodes))}

        print(f"\nNode ID Map (first 5):")
        for i in range(min(5, len(nodes))):
            print(f"  node_{i} -> uuid_{i}")

        print(f"\nEdges:")
        for i, edge in enumerate(edges[:5], 1):
            from_idx = edge.get("from_node_index")
            to_idx = edge.get("to_node_index")
            edge_type = edge.get("edge_type")

            print(f"\n  {i}. {edge_type}")
            print(f"     from_node_index: {from_idx}")
            print(f"     to_node_index: {to_idx}")

            # Check if indices are in range
            if from_idx is not None and from_idx < len(nodes):
                from_key = f"node_{from_idx}"
                from_id = node_id_map.get(from_key)
                print(f"     ✓ from_key '{from_key}' -> {from_id}")
            else:
                print(f"     ✗ from_node_index {from_idx} OUT OF RANGE (max {len(nodes)-1})")

            if to_idx is not None and to_idx < len(nodes):
                to_key = f"node_{to_idx}"
                to_id = node_id_map.get(to_key)
                print(f"     ✓ to_key '{to_key}' -> {to_id}")
            else:
                print(f"     ✗ to_node_index {to_idx} OUT OF RANGE (max {len(nodes)-1})")

        break  # Only show first conversation with edges
