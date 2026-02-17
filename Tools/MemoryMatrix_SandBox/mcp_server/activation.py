"""Spreading activation — graph traversal from seed nodes with decaying signal."""

from .event_bus import MemoryEvent
from .config import RetrievalParams

if __name__ != "__main__":
    from .sandbox_matrix import SandboxMatrix


async def spreading_activation(
    matrix: "SandboxMatrix",
    seed_ids: list[str],
    params: RetrievalParams,
) -> list[dict]:
    """
    Spread activation from seed nodes through edges.

    Algorithm:
    1. Initialize seeds at activation=1.0, hop=0
    2. For each hop (1..max_hops):
       - Get edges from current frontier
       - new_activation = source_activation * decay * edge_strength
       - If new_activation >= min_activation, activate target
    3. Emit activation_hop event per hop
    4. Emit activation_done with totals

    Returns: list sorted by activation desc with
    {node_id, activation, hop, source_id, edge_type, node}
    """
    # activation_map: node_id → {activation, hop, source_id, edge_type}
    activation_map: dict[str, dict] = {}

    # Initialize seeds
    frontier = {}
    for sid in seed_ids:
        activation_map[sid] = {
            "node_id": sid,
            "activation": 1.0,
            "hop": 0,
            "source_id": None,
            "edge_type": None,
        }
        frontier[sid] = 1.0

    await matrix.bus.emit(MemoryEvent(
        type="activation_started",
        actor="activation",
        payload={"seed_ids": seed_ids, "max_hops": params.max_hops},
    ))

    for hop in range(1, params.max_hops + 1):
        if not frontier:
            break

        new_frontier = {}
        hop_activated = []

        for source_id, source_activation in frontier.items():
            edges = await matrix.get_edges_from(source_id)
            # Also check reverse edges (bidirectional traversal)
            reverse_edges = await matrix.fetchall(
                "SELECT id, to_id as from_id, from_id as to_id, relationship, strength, created_at "
                "FROM edges WHERE to_id = ?",
                (source_id,),
            )
            all_edges = edges + reverse_edges

            for edge in all_edges:
                target_id = edge["to_id"]
                if target_id == source_id:
                    continue  # skip self-loops
                if target_id in activation_map:
                    continue  # already activated at an earlier hop

                new_activation = source_activation * params.decay * edge.get("strength", 1.0)

                if new_activation >= params.min_activation:
                    activation_map[target_id] = {
                        "node_id": target_id,
                        "activation": new_activation,
                        "hop": hop,
                        "source_id": source_id,
                        "edge_type": edge["relationship"],
                    }
                    new_frontier[target_id] = new_activation
                    hop_activated.append(target_id)

        await matrix.bus.emit(MemoryEvent(
            type="activation_hop",
            actor="activation",
            payload={
                "hop": hop,
                "activated_count": len(hop_activated),
                "activated_ids": hop_activated[:20],
            },
        ))
        frontier = new_frontier

    # Enrich with full node data
    results = []
    for info in activation_map.values():
        node = await matrix.get_node(info["node_id"])
        if node:
            results.append({**info, "node": node})

    # Sort by activation descending
    results.sort(key=lambda x: x["activation"], reverse=True)

    await matrix.bus.emit(MemoryEvent(
        type="activation_done",
        actor="activation",
        payload={
            "total_activated": len(results),
            "hops_used": max((r["hop"] for r in results), default=0),
            "top_ids": [r["node_id"] for r in results[:10]],
        },
    ))
    return results
