"""Lock-in calculator — 4-factor weighted formula for memory consolidation."""

import math
from datetime import datetime, timezone

from .event_bus import MemoryEvent
from .config import RetrievalParams

if __name__ != "__main__":
    from .sandbox_matrix import SandboxMatrix

# Lock-in state thresholds (Memory Economy spec — CORRECTED)
STATES = [
    (0.00, 0.20, "drifting"),
    (0.20, 0.70, "fluid"),
    (0.70, 0.85, "settled"),
    (0.85, 1.01, "crystallized"),
]


def lock_in_state(value: float) -> str:
    """Map a lock-in value [0,1] to a state name."""
    for lo, hi, name in STATES:
        if lo <= value < hi:
            return name
    return "crystallized"


def compute_lock_in(
    confidence: float,
    access_count: int,
    avg_edge_strength: float,
    age_days: float,
    params: RetrievalParams,
) -> float:
    """
    4-factor weighted formula:
    lock_in = (confidence * w1) + (log_access_freq * w2) + (avg_edge_strength * w3) + (age_stability * w4)

    - log_access_freq: log2(access_count + 1) / log2(100), capped at 1.0
    - age_stability: min(age_days / 30, 1.0) — stabilizes over 30 days
    """
    # Normalize access frequency (log scale, caps at ~100 accesses)
    log_access = min(math.log2(access_count + 1) / math.log2(100), 1.0)

    # Age stability (linearly increases over 30 days, caps at 1.0)
    age_stability = min(age_days / 30.0, 1.0)

    lock_in = (
        confidence * params.lock_in_node_weight
        + log_access * params.lock_in_access_weight
        + avg_edge_strength * params.lock_in_edge_weight
        + age_stability * params.lock_in_age_weight
    )
    return max(0.0, min(1.0, lock_in))


async def recompute_all_lock_ins(
    matrix: "SandboxMatrix", params: RetrievalParams
) -> dict:
    """Recalculate lock-in for all nodes. Emits lock_in_changed for state transitions."""
    now = datetime.now(timezone.utc)
    node_ids = await matrix.all_node_ids()
    transitions = []

    for nid in node_ids:
        node = await matrix.get_node(nid)
        if not node:
            continue

        old_lock_in = node.get("lock_in", 0.0)
        old_state = lock_in_state(old_lock_in)

        # Compute avg edge strength
        edges = await matrix.get_edges_involving(nid)
        if edges:
            avg_strength = sum(e["strength"] for e in edges) / len(edges)
        else:
            avg_strength = 0.0

        # Compute age in days
        created = node.get("created_at", now.isoformat())
        try:
            created_dt = datetime.fromisoformat(created)
            if created_dt.tzinfo is None:
                created_dt = created_dt.replace(tzinfo=timezone.utc)
            age_days = (now - created_dt).total_seconds() / 86400.0
        except (ValueError, TypeError):
            age_days = 0.0

        new_lock_in = compute_lock_in(
            confidence=node.get("confidence", 1.0),
            access_count=node.get("access_count", 0),
            avg_edge_strength=avg_strength,
            age_days=age_days,
            params=params,
        )
        new_state = lock_in_state(new_lock_in)

        await matrix.update_lock_in(nid, new_lock_in)

        if old_state != new_state:
            transitions.append({
                "node_id": nid,
                "old_state": old_state,
                "new_state": new_state,
                "old_lock_in": round(old_lock_in, 3),
                "new_lock_in": round(new_lock_in, 3),
            })
            await matrix.bus.emit(MemoryEvent(
                type="lock_in_changed",
                actor="lock_in",
                payload={
                    "node_id": nid,
                    "old_state": old_state,
                    "new_state": new_state,
                    "lock_in": round(new_lock_in, 3),
                },
            ))

    # Also update cluster lock-ins (average of member lock-ins)
    clusters = await matrix.get_clusters()
    for cluster in clusters:
        members = await matrix.get_cluster_members(cluster["id"])
        if members:
            avg_li = sum(m.get("lock_in", 0.0) for m in members) / len(members)
        else:
            avg_li = 0.0
        c_state = lock_in_state(avg_li)
        await matrix.update_cluster_lock_in(cluster["id"], avg_li, c_state)

    return {
        "nodes_updated": len(node_ids),
        "state_transitions": len(transitions),
        "transitions": transitions,
    }
