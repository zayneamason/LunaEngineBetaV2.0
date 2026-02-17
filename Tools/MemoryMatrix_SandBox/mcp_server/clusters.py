"""Cluster computation and constellation assembly."""

from .config import RetrievalParams
from .event_bus import MemoryEvent

if __name__ != "__main__":
    from .sandbox_matrix import SandboxMatrix


async def assemble_constellation(
    matrix: "SandboxMatrix",
    activated_nodes: list[dict],
    params: RetrievalParams,
) -> dict:
    """
    Assemble a 'constellation' from activated nodes for retrieval output.

    Takes the activated node set, groups by cluster, respects token budget,
    and returns the final retrieval payload.

    Returns:
    {
        "nodes": [...],         # selected nodes within token budget
        "clusters_hit": [...],  # cluster IDs represented
        "total_tokens": int,    # estimated token count
        "budget_used": float,   # fraction of token budget used
        "dropped": int,         # nodes dropped due to budget
    }
    """
    budget = params.token_budget
    used = 0
    selected = []
    clusters_hit = set()
    dropped = 0

    # Sort by activation score (already sorted, but be safe)
    sorted_nodes = sorted(activated_nodes, key=lambda x: x.get("activation", 0), reverse=True)

    for item in sorted_nodes:
        node = item.get("node", {})
        content = node.get("content", "")
        # Rough token estimate: ~4 chars per token
        est_tokens = len(content) // 4 + 10  # +10 for metadata overhead

        if used + est_tokens > budget:
            dropped += 1
            continue

        used += est_tokens
        selected.append(item)
        if node.get("cluster_id"):
            clusters_hit.add(node["cluster_id"])

    result = {
        "nodes": selected,
        "clusters_hit": list(clusters_hit),
        "total_tokens": used,
        "budget_used": round(used / budget, 3) if budget > 0 else 0,
        "dropped": dropped,
    }

    await matrix.bus.emit(MemoryEvent(
        type="constellation_assembled",
        actor="clusters",
        payload={
            "selected_count": len(selected),
            "clusters_hit": list(clusters_hit),
            "total_tokens": used,
            "budget_pct": result["budget_used"],
            "dropped": dropped,
        },
    ))
    return result
