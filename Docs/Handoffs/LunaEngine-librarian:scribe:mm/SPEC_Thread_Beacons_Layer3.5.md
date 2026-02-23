# SPEC: Thread Beacons — Layer 3.5

## Luna Flow State Architecture

**Layer:** 3.5 of 7
**Owner:** Librarian (The Dude) + Observatory (visualization)
**Depends on:** Layer 3 (Thread Management — threads exist as THREAD nodes)
**Enables:** Layer 5 (Context Threading), Layer 6 (Consciousness Wiring), Observatory GraphView enhancement

---

## Problem

Threads exist in the Matrix as THREAD nodes (Layer 3), but they're invisible in the knowledge graph. They're metadata sitting in a list view. Meanwhile, the graph has entities floating in space with edges between them — but no indication of *where focused work happened*.

The graph shows structure. Threads show attention. Neither can see the other.

Layer 3.5 makes threads visible in the graph as **beacons** — gravitational anchor points that mark where sustained conversational attention occurred — and uses them as a **catalyst** for generating new edges between entities that were discussed together.

---

## What Is a Beacon

A beacon is a THREAD node rendered in the graph with distinct visual presence. It is not just another dot. It's a landmark that says "this is where thinking happened."

Visually:
- Larger than entity or fact nodes
- Pulsing glow if active, steady warm glow if parked, dim if closed
- INVOLVES edges radiate outward to connected entities like spokes
- Status-encoded: active=green pulse, parked=amber steady, closed=faded

Structurally:
- Hub node with high edge count (one INVOLVES edge per entity in thread)
- Natural clustering anchor — entities in the same thread cluster around it
- Cross-thread entities (entities appearing in multiple threads) become visible bridges

A graph with beacons tells a different story than one without. Without beacons, you see knowledge. With beacons, you see *where the conversations were*.

---

## Edge Catalysis

This is the load-bearing idea. Threads don't just visualize attention — they **generate structure**.

### The Insight

If two entities appear together in a thread with 40 turns, that's strong evidence of a meaningful relationship — even if no one ever explicitly stated the relationship. The thread is implicit signal that becomes explicit structure.

### Co-Occurrence Edges

When a thread is parked or closed, the Librarian generates **DISCUSSED_WITH** edges between entity pairs that co-occurred in that thread.

```python
# Entities in thread: [Observatory, entity_mentions, Ahab, Luna]
# Generated edges:
#   Observatory --[DISCUSSED_WITH]--> entity_mentions  (strength based on co-occurrence)
#   Observatory --[DISCUSSED_WITH]--> Ahab
#   Observatory --[DISCUSSED_WITH]--> Luna
#   entity_mentions --[DISCUSSED_WITH]--> Ahab
#   entity_mentions --[DISCUSSED_WITH]--> Luna
#   Ahab --[DISCUSSED_WITH]--> Luna
```

Edge strength is calculated from:
- **Turn count**: more turns = stronger signal
- **Resume count**: thread was revisited = even stronger
- **Entity density**: entities that appear in many threads together get reinforced

### Reinforcement, Not Duplication

If a DISCUSSED_WITH edge already exists between two entities (from a previous thread), the strength is **reinforced**, not duplicated. Multiple threads discussing Observatory + Ahab together increase that edge's strength toward crystallization.

```python
# First thread with Observatory + Ahab (12 turns): strength = 0.35
# Second thread with Observatory + Ahab (47 turns): strength = 0.65
# Third thread (8 turns): strength = 0.72
# The relationship between Observatory and Ahab is becoming structural knowledge
```

This mirrors how human memory works. You don't remember "I talked about X and Y together on February 19th." You remember "X and Y are related" — because they kept showing up together.

### What This Creates

Over time, the graph develops organic structure from conversation patterns:
- Entities that are frequently discussed together develop strong mutual edges
- Clusters emerge naturally from co-occurrence patterns
- The graph reflects *how Ahab thinks about things* — which concepts live together in his mind
- Bridges between clusters become visible (entities that span multiple thread contexts)

---

## Data Model

### New Edge Type: DISCUSSED_WITH

Added to the edge type vocabulary. Stored in the existing edges table.

```python
# Edge between two entity nodes
{
    "from_id": "entity_observatory",
    "to_id": "entity_ahab",
    "edge_type": "DISCUSSED_WITH",
    "strength": 0.65,          # Co-occurrence signal
    "metadata": {
        "thread_count": 3,     # How many threads generated this edge
        "total_turns": 67,     # Combined turn count across threads
        "last_thread_id": "thread_a1b2c3d4",
        "first_seen": "2026-02-15T09:00:00Z",
        "last_reinforced": "2026-02-19T14:15:00Z",
    }
}
```

### New Edge Type: BEACON_OF

Connects a THREAD node to the conversation session or time range it represents. Optional — for temporal navigation in the graph.

```python
{
    "from_id": "thread_a1b2c3d4",
    "to_id": "session_20260219_103000",
    "edge_type": "BEACON_OF",
    "strength": 1.0,
}
```

### Modified: INVOLVES Edge Metadata

The existing INVOLVES edges (THREAD → entity) gain a `turn_count` in metadata to track how much of the thread focused on that entity.

```python
{
    "from_id": "thread_a1b2c3d4",
    "to_id": "entity_observatory",
    "edge_type": "INVOLVES",
    "strength": 0.9,
    "metadata": {
        "first_mention_turn": 3,
        "last_mention_turn": 45,
        "mention_density": 0.82,  # fraction of turns mentioning this entity
    }
}
```

---

## Librarian Changes

### New Method: `_catalyze_edges()`

Called when a thread is parked or closed. Generates co-occurrence edges.

```python
async def _catalyze_edges(self, thread: Thread) -> int:
    """
    Generate DISCUSSED_WITH edges between entity pairs in a thread.
    
    Called on park or close. Returns number of edges created/reinforced.
    
    Edge strength formula:
        base = min(1.0, thread.turn_count / 50)  # Normalize to 50 turns
        resume_bonus = min(0.2, thread.resume_count * 0.05)
        strength = min(1.0, base + resume_bonus)
    """
    entities = thread.entities
    if len(entities) < 2:
        return 0
    
    # Calculate base strength from thread engagement
    base_strength = min(1.0, thread.turn_count / 50)
    resume_bonus = min(0.2, thread.resume_count * 0.05)
    strength = min(1.0, base_strength + resume_bonus)
    
    edges_created = 0
    matrix = await self._get_matrix()
    if not matrix:
        return 0
    
    # Generate edges for every entity pair
    for i, entity_a in enumerate(entities):
        for entity_b in entities[i+1:]:
            # Resolve entity node IDs
            id_a = await self._resolve_entity_id(entity_a)
            id_b = await self._resolve_entity_id(entity_b)
            if not id_a or not id_b:
                continue
            
            # Check for existing DISCUSSED_WITH edge
            existing = await matrix.find_edge(id_a, id_b, "DISCUSSED_WITH")
            
            if existing:
                # Reinforce: weighted average biased toward new signal
                old_strength = existing.strength
                old_meta = json.loads(existing.metadata or "{}")
                new_thread_count = old_meta.get("thread_count", 1) + 1
                new_total_turns = old_meta.get("total_turns", 0) + thread.turn_count
                
                # Reinforcement formula: old * 0.7 + new * 0.3, capped at 1.0
                reinforced = min(1.0, old_strength * 0.7 + strength * 0.3)
                
                await matrix.update_edge(
                    existing.id,
                    strength=reinforced,
                    metadata=json.dumps({
                        "thread_count": new_thread_count,
                        "total_turns": new_total_turns,
                        "last_thread_id": thread.id,
                        "first_seen": old_meta.get("first_seen"),
                        "last_reinforced": datetime.now().isoformat(),
                    }),
                )
                logger.debug(
                    f"The Dude: Reinforced {entity_a} ↔ {entity_b} "
                    f"({old_strength:.2f} → {reinforced:.2f}, "
                    f"{new_thread_count} threads)"
                )
            else:
                # Create new edge
                await matrix.add_edge(
                    from_id=id_a,
                    to_id=id_b,
                    edge_type="DISCUSSED_WITH",
                    strength=strength,
                    metadata=json.dumps({
                        "thread_count": 1,
                        "total_turns": thread.turn_count,
                        "last_thread_id": thread.id,
                        "first_seen": datetime.now().isoformat(),
                        "last_reinforced": datetime.now().isoformat(),
                    }),
                )
                logger.debug(
                    f"The Dude: New edge {entity_a} ↔ {entity_b} "
                    f"(strength={strength:.2f}, from thread '{thread.topic}')"
                )
            
            edges_created += 1
    
    logger.info(
        f"The Dude: Catalyzed {edges_created} edges from thread "
        f"'{thread.topic}' ({len(entities)} entities, "
        f"{thread.turn_count} turns)"
    )
    
    return edges_created
```

### Modified: `_park_thread()` and `_close_thread()`

Add catalysis call:

```python
async def _park_thread(self, thread: Thread) -> None:
    """Snapshot, park, and catalyze edges."""
    thread.status = ThreadStatus.PARKED
    thread.parked_at = datetime.now()
    
    await self._update_thread_node(thread)
    
    # NEW: Generate co-occurrence edges
    edges = await self._catalyze_edges(thread)
    if edges > 0:
        logger.info(
            f"The Dude: Thread '{thread.topic}' catalyzed {edges} edges on park"
        )
    
    self._thread_cache[thread.id] = thread
    self._threads_parked += 1
```

Same addition to the close path.

---

## Observatory Graph Integration

### Visual Specification

THREAD nodes in the GraphView should render as beacons, not standard dots.

```javascript
// Node rendering in GraphView — add THREAD type handling
const THREAD_STATUS_STYLES = {
  active: {
    color: '#4ade80',
    glowColor: 'rgba(74, 222, 128, 0.3)',
    glowRadius: 20,
    pulse: true,
    size: 12,       // Larger than entity nodes (typically 4-8)
    shape: 'diamond', // Distinct from circle entities
  },
  parked: {
    color: '#f59e0b',
    glowColor: 'rgba(245, 158, 11, 0.15)',
    glowRadius: 12,
    pulse: false,
    size: 10,
    shape: 'diamond',
  },
  closed: {
    color: '#64748b',
    glowColor: 'none',
    glowRadius: 0,
    pulse: false,
    size: 7,
    shape: 'diamond',
  },
}

// INVOLVES edges render as spokes radiating from beacon
// DISCUSSED_WITH edges render as entity-to-entity connections
//   with dashed line style to distinguish from explicit relationships
```

### Graph Settings Integration

Add to GraphSettings panel:

```javascript
// New settings for thread beacons
showThreadBeacons: true,     // Toggle beacon visibility
showDiscussedWith: true,     // Toggle DISCUSSED_WITH edges
beaconMinTurns: 5,           // Only show threads with N+ turns
beaconGlowIntensity: 1.0,   // Multiplier on glow effect
```

### Beacon Interaction

Clicking a beacon in the graph should:
1. Select the thread in the ThreadsView (cross-tab navigation)
2. Highlight all INVOLVES entities in the graph
3. Show DISCUSSED_WITH edges for those entities
4. Display a tooltip with: topic, status, turn count, entity list

### Semantic Zoom Behavior

At universe zoom level: beacons appear as bright points in the star field, marking "dense attention areas" in the knowledge space.

At galaxy zoom level: beacons show their diamond shape with entity spokes visible.

At solar system zoom level: full beacon detail — topic label, entity connections, DISCUSSED_WITH web.

---

## How This Feeds Higher Layers

### Layer 5 (Context Threading)
When the pipeline retrieves context for a query, DISCUSSED_WITH edges provide a new retrieval signal. If the query mentions entity A, and entity A has a strong DISCUSSED_WITH edge to entity B, entity B should be pulled into context even if the query doesn't mention it. This is associative recall powered by conversation patterns.

### Layer 6 (Consciousness Wiring)
Beacons contribute to attention state. Active beacon = high attention. Multiple parked beacons with open tasks = background tension. The beacon count and their status distribution feed the coherence and engagement metrics.

### Layer 7 (Proactive Surfacing)
"We were discussing Observatory cleanup. There's still an open task about deploying the stoplist. Also — I notice you keep working on Observatory and entity_mentions together. They've shown up in 3 threads now."

Luna can surface not just thread context, but the *patterns* that emerge from thread catalysis. She sees which entities keep appearing together in your thinking.

---

## Sovereignty Invariant

All edge catalysis is local. No cloud calls. The thread-to-edge pipeline runs entirely in the Librarian actor using Matrix operations on the local SQLite database.

DISCUSSED_WITH edges are organic knowledge generated from conversation patterns — they belong to the user's file, not to any external service.

---

## Testing

### Unit: Edge Catalysis

```python
# Thread with 4 entities, 30 turns
thread = Thread(
    id="t1", topic="observatory cleanup",
    entities=["Observatory", "entity_mentions", "Ahab", "Luna"],
    turn_count=30, resume_count=1,
)

edges = await librarian._catalyze_edges(thread)
assert edges == 6  # C(4,2) = 6 pairs

# Verify strength: base = 30/50 = 0.6, resume_bonus = 0.05
# strength = 0.65
edge = await matrix.find_edge("Observatory", "entity_mentions", "DISCUSSED_WITH")
assert abs(edge.strength - 0.65) < 0.01
```

### Unit: Edge Reinforcement

```python
# First thread: Observatory + Ahab
await librarian._catalyze_edges(Thread(
    entities=["Observatory", "Ahab"], turn_count=20
))
edge1 = await matrix.find_edge("Observatory", "Ahab", "DISCUSSED_WITH")
# strength = 20/50 = 0.4

# Second thread: Observatory + Ahab (stronger)
await librarian._catalyze_edges(Thread(
    entities=["Observatory", "Ahab"], turn_count=40
))
edge2 = await matrix.find_edge("Observatory", "Ahab", "DISCUSSED_WITH")
# reinforced = 0.4 * 0.7 + 0.8 * 0.3 = 0.28 + 0.24 = 0.52

assert edge2.strength > edge1.strength
meta = json.loads(edge2.metadata)
assert meta["thread_count"] == 2
```

### Unit: No Cloud Calls

```python
# Verify catalysis is fully local
with patch("httpx.AsyncClient") as mock_http:
    await librarian._catalyze_edges(thread)
    mock_http.assert_not_called()
```

### Integration: Graph Visualization

```python
# After catalysis, verify graph dump includes:
# 1. THREAD node with beacon metadata
# 2. INVOLVES edges from thread to entities
# 3. DISCUSSED_WITH edges between entity pairs
dump = await observatory_graph_dump()
thread_nodes = [n for n in dump["nodes"] if n["type"] == "THREAD"]
assert len(thread_nodes) >= 1

discussed_edges = [e for e in dump["edges"] if e["type"] == "DISCUSSED_WITH"]
assert len(discussed_edges) >= 1
```

---

## Files Modified

| File | Change |
|------|--------|
| `src/luna/actors/librarian.py` | Add `_catalyze_edges()`, call from `_park_thread()` and close path |
| `src/luna/extraction/types.py` | Add DISCUSSED_WITH to edge type constants |
| `frontend/src/observatory/views/GraphView.jsx` | Add beacon rendering for THREAD nodes, DISCUSSED_WITH edge style |
| `frontend/src/observatory/views/GraphSettings.jsx` | Add beacon visibility/intensity settings |
| `frontend/src/observatory/views/ThreadsView.jsx` | NEW — thread list/detail view (prototype complete) |
| `frontend/src/observatory/ObservatoryApp.jsx` | Add Threads tab |
| `tests/test_edge_catalysis.py` | New — catalysis math, reinforcement, sovereignty |

---

## Success Criteria

Layer 3.5 complete when:

1. Threads are visible as beacons in the Observatory graph
2. Active threads pulse green, parked threads glow amber, closed threads dim
3. INVOLVES edges radiate from beacons to entity nodes
4. `_catalyze_edges()` generates DISCUSSED_WITH edges on thread park/close
5. Repeated co-occurrence reinforces edge strength (not duplicates)
6. Edge metadata tracks thread_count, total_turns, timestamps
7. GraphSettings has beacon toggle and intensity controls
8. Clicking a beacon cross-navigates to ThreadsView
9. All catalysis is local (zero cloud calls)
10. ThreadsView prototype integrated into Observatory with real data feed

---

## The Philosophy

Threads are where attention lives. Beacons make attention visible. Edge catalysis turns attention into structure.

Over months of conversations, the graph will organically develop a topology that reflects how Ahab thinks — which concepts cluster together, which domains bridge, where the dense areas of focused work are. Not because anyone manually drew those connections, but because the conversations themselves wove them.

The graph becomes a map of a mind.
