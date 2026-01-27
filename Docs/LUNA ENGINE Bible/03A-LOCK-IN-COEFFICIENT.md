# Part III-A: The Lock-In Coefficient

**Status:** IMPLEMENTED (90%)
**Last Updated:** January 25, 2026
**Implementation:** `src/luna/substrate/lock_in.py`

---

## 3A.1 Overview

The Lock-In Coefficient (L) represents how "settled" a memory is in Luna's consciousness. It determines whether a memory persists, fades, or remains fluid.

> "Memories that matter get reinforced. Memories that don't, drift away."

This is not simple recency — it's an activity-based persistence model that considers:
- How often you retrieve the memory
- Whether you explicitly reinforce it
- How connected it is to other settled memories
- ~~Whether it shares tags with settled memories~~ (NOT YET IMPLEMENTED)

---

## 3A.2 Lock-In States

| State | Range | Meaning | Behavior |
|-------|-------|---------|----------|
| **DRIFTING** | L < 0.30 | Rarely accessed, may fade | Candidate for pruning |
| **FLUID** | 0.30 <= L < 0.70 | Active but not settled | Normal memory |
| **SETTLED** | L >= 0.70 | Core knowledge, persistent | Protected from decay |

```python
# From src/luna/substrate/lock_in.py
class LockInState(str, Enum):
    DRIFTING = "drifting"  # L < 0.30
    FLUID = "fluid"        # 0.30 <= L < 0.70
    SETTLED = "settled"    # L >= 0.70

# Thresholds
THRESHOLD_SETTLED = 0.70
THRESHOLD_DRIFTING = 0.30

# Output bounds (never fully 0 or 1)
LOCK_IN_MIN = 0.15
LOCK_IN_MAX = 0.85
```

---

## 3A.3 Weighted Factors

Lock-in is computed from four weighted factors:

| Factor | Weight | Description | Status |
|--------|--------|-------------|--------|
| **Retrieval** | 0.40 | How often this memory is accessed | IMPLEMENTED |
| **Reinforcement** | 0.30 | Explicit marks as "important" | IMPLEMENTED |
| **Network** | 0.20 | Connected to settled nodes | IMPLEMENTED |
| **Tag Siblings** | 0.10 | Shares tags with settled nodes | NOT IMPLEMENTED |

```python
# From src/luna/substrate/lock_in.py
DEFAULT_WEIGHTS = {
    "retrieval": 0.4,       # How often accessed (heaviest weight)
    "reinforcement": 0.3,   # Explicitly marked important
    "network": 0.2,         # Connected to settled nodes
    "tag_siblings": 0.1     # Shares tags with settled nodes
}
```

### Implementation Note: Tag Siblings

**WARNING:** Tag siblings are NOT currently implemented. The code contains:

```python
# Lines 273-274 in lock_in.py
# TODO: Implement tag sibling counting
locked_tag_sibling_count = 0
```

This means **10% of the lock-in weight is currently inactive**. The tag sibling feature requires:
1. A `tags` table in the database schema
2. A `node_tags` junction table
3. Implementation of `_count_locked_tag_siblings()` method

Until implemented, lock-in calculations use only 90% of intended signal.

---

## 3A.4 The Sigmoid Transform

Raw activity scores are mapped to lock-in coefficients using a sigmoid function. This creates smooth, bounded transitions.

### Mathematical Formula

```
activity = (retrieval * 0.4 + reinforcement * 0.3 + network * 0.2 + tags * 0.1) / 10.0

sigmoid(x) = 1 / (1 + e^(-K * (x - X0)))

lock_in = 0.15 + (0.85 - 0.15) * sigmoid(activity)
```

### Sigmoid Parameters

| Parameter | Value | Purpose |
|-----------|-------|---------|
| **K** | 1.2 | Steepness (higher = sharper transition) |
| **X0** | 0.5 | Midpoint (where sigmoid = 0.5) |

```python
# From src/luna/substrate/lock_in.py
DEFAULT_SIGMOID_K = 1.2   # Steepness
DEFAULT_SIGMOID_X0 = 0.5  # Midpoint
```

### Why Sigmoid?

1. **Bounded Output:** Lock-in stays between 0.15 and 0.85 (never fully locked or fully drifting)
2. **Smooth Transitions:** No hard cutoffs — gradual change as activity increases
3. **Diminishing Returns:** High activity doesn't infinitely increase lock-in
4. **Mathematical Stability:** No overflow at extreme values (clamped at +/-700)

---

## 3A.5 Activity Computation

```python
def compute_activity(
    retrieval_count: int = 0,
    reinforcement_count: int = 0,
    locked_neighbor_count: int = 0,
    locked_tag_sibling_count: int = 0,  # Currently always 0
) -> float:
    """
    Compute raw activity score from weighted factors.

    Returns:
        Activity score (typically 0.0 to 2.0+)
    """
    config = get_config()

    activity = (
        retrieval_count * config.weight_retrieval +
        reinforcement_count * config.weight_reinforcement +
        locked_neighbor_count * config.weight_network +
        locked_tag_sibling_count * config.weight_tag_siblings
    ) / 10.0

    return activity
```

### Example Calculations

| Scenario | Retrieval | Reinforce | Neighbors | Activity | Lock-In | State |
|----------|-----------|-----------|-----------|----------|---------|-------|
| New memory | 0 | 0 | 0 | 0.0 | 0.15 | DRIFTING |
| Mentioned once | 1 | 0 | 0 | 0.04 | 0.16 | DRIFTING |
| Regular use | 10 | 0 | 0 | 0.40 | 0.44 | FLUID |
| Important + used | 10 | 3 | 2 | 0.53 | 0.50 | FLUID |
| Core knowledge | 20 | 5 | 5 | 1.05 | 0.66 | FLUID |
| Deeply settled | 50 | 10 | 10 | 2.5 | 0.82 | SETTLED |

---

## 3A.6 Configuration

Lock-in behavior is configurable at runtime:

```python
@dataclass
class LockInConfig:
    """Configuration for lock-in computation."""
    enabled: bool = True  # When False, all memories return 0.5 (neutral)
    weight_retrieval: float = 0.4
    weight_reinforcement: float = 0.3
    weight_network: float = 0.2
    weight_tag_siblings: float = 0.1
    sigmoid_k: float = 1.2
    sigmoid_x0: float = 0.5
    threshold_settled: float = 0.70
    threshold_drifting: float = 0.30
```

### Disabling Lock-In

When `enabled=False`, all memories return a neutral lock-in of 0.5, effectively treating all memories equally. This is useful for testing or when you want to disable memory decay entirely.

---

## 3A.7 Node-Level Computation

For a specific memory node, lock-in includes network effects:

```python
async def compute_lock_in_for_node(
    node_id: str,
    retrieval_count: int,
    reinforcement_count: int,
    graph: "MemoryGraph",
) -> tuple[float, LockInState]:
    """
    Compute lock-in for a specific node, including network effects.
    """
    # Count settled neighbors (simplified - uses depth=1 neighbors / 3)
    locked_neighbor_count = 0

    if graph and graph.has_node(node_id):
        neighbors = await graph.get_neighbors(node_id, depth=1)
        locked_neighbor_count = len(neighbors) // 3  # Rough estimate
        # TODO: Optimize with batch query for actual L >= 0.7 count

    # Tag siblings not implemented
    locked_tag_sibling_count = 0  # TODO

    lock_in = compute_lock_in(
        retrieval_count=retrieval_count,
        reinforcement_count=reinforcement_count,
        locked_neighbor_count=locked_neighbor_count,
        locked_tag_sibling_count=locked_tag_sibling_count,
    )

    state = classify_state(lock_in)
    return lock_in, state
```

---

## 3A.8 Database Schema

Lock-in values are stored in the `memory_nodes` table:

```sql
-- From src/luna/substrate/schema.sql
CREATE TABLE memory_nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    content TEXT NOT NULL,
    -- ... other fields ...
    access_count INTEGER DEFAULT 0,       -- For lock-in tracking
    reinforcement_count INTEGER DEFAULT 0,
    lock_in REAL DEFAULT 0.15,            -- 0.15-0.85 coefficient
    lock_in_state TEXT DEFAULT 'drifting',
    -- ...
);

-- Index for filtering by lock-in state
CREATE INDEX idx_memory_nodes_lock_in_state ON memory_nodes(lock_in_state);
```

---

## 3A.9 Memory Matrix Integration

The MemoryMatrix provides lock-in-aware filtering:

```python
# From src/luna/substrate/memory.py
class MemoryMatrix:
    async def get_nodes_by_lock_in_state(
        self,
        state: LockInState
    ) -> list[MemoryNode]:
        """Get all nodes in a specific lock-in state."""
        ...

    async def get_drifting_nodes(self) -> list[MemoryNode]:
        """Get all drifting nodes (L < 0.30) — candidates for pruning."""
        ...

    async def get_settled_nodes(self) -> list[MemoryNode]:
        """Get all settled nodes (L >= 0.70) — core knowledge."""
        ...

    async def record_access(self, node_id: str):
        """Increment access count and recalculate lock-in."""
        ...

    async def reinforce_node(self, node_id: str):
        """Explicitly reinforce a node, increasing lock-in."""
        ...
```

---

## 3A.10 Visual Indicators

For debugging and UI display:

```python
def get_state_emoji(state: LockInState) -> str:
    """Visual indicator for state."""
    return {
        LockInState.SETTLED: "🟢",   # Green = stable, persistent
        LockInState.FLUID: "🔵",     # Blue = active, changeable
        LockInState.DRIFTING: "🟠",  # Orange = fading, at risk
    }.get(state, "⚪")
```

---

## 3A.11 Future Work

### Priority 1: Implement Tag Siblings

The tag sibling feature would add 10% of lock-in signal:

1. **Schema Changes:**
   ```sql
   CREATE TABLE tags (
       id TEXT PRIMARY KEY,
       name TEXT NOT NULL UNIQUE
   );

   CREATE TABLE node_tags (
       node_id TEXT REFERENCES memory_nodes(id),
       tag_id TEXT REFERENCES tags(id),
       PRIMARY KEY (node_id, tag_id)
   );
   ```

2. **Implementation:**
   ```python
   async def _count_locked_tag_siblings(
       self,
       node_id: str
   ) -> int:
       """Count nodes sharing tags with L >= 0.7."""
       # Get tags for this node
       # Find other nodes with same tags
       # Filter to L >= 0.7
       # Return count
   ```

### Priority 2: Batch Lock-In Updates

Currently, lock-in is recalculated on access. For performance:
- Batch recalculation during reflective tick
- Cache neighbor lock-in states
- Use graph spreading activation for network effects

### Priority 3: Lock-In Decay

Consider time-based decay for rarely accessed memories:
- Drifting memories lose lock-in over time
- Settled memories are protected from decay
- Fluid memories decay slowly if not accessed

---

## Summary

The Lock-In Coefficient is Luna's memory persistence system. It determines which memories become core knowledge and which fade away.

| Aspect | Value |
|--------|-------|
| **States** | DRIFTING (< 0.30), FLUID (0.30-0.70), SETTLED (>= 0.70) |
| **Bounds** | 0.15 to 0.85 (never fully locked/drifting) |
| **Factors** | Retrieval (40%), Reinforcement (30%), Network (20%), Tags (10% - TODO) |
| **Transform** | Sigmoid with K=1.2, X0=0.5 |
| **Location** | `src/luna/substrate/lock_in.py` |

**Known Gap:** Tag siblings contribute 0% of lock-in weight (hardcoded to 0, marked TODO).

---

*Next Section: Part IV — The Scribe (Ben Franklin)*
