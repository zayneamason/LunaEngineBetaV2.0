# Part V: The Librarian (The Dude) — v3.0

**Status:** CURRENT
**Replaces:** BIBLE-PART-V-THE-LIBRARIAN-v2.1.md
**Last Updated:** January 30, 2026
**Implementation:** `src/luna/actors/librarian.py`

---

## 5.1 The Librarian: The Dude

The Librarian is the **deep brain** — taking Scribe output and weaving it into the Substrate. He doesn't just store; he **connects**.

**Persona:** The Dude from The Big Lebowski. Chill, competent, cuts through bullshit. The Dude abides... and files things where they belong.

> "This will not stand, ya know, this aggression will not stand, man." — The Dude

(On duplicate entities trying to sneak into the graph.)

### The Separation Principle

**Critical Design Rule:** The Dude has personality in his PROCESS (commentary can be irreverent), but his OUTPUTS are NEUTRAL (clean context packets, properly filed nodes). Luna's memories stay unpolluted.

```
┌─────────────────────────────────────────────────────────────┐
│  PROCESS (Dude's Domain)         OUTPUT (Neutral)           │
│                                                              │
│  "Yeah, well, that's just like,  →  ContextPacket(          │
│   your opinion, man..."              nodes=[...],           │
│                                       edges=[...],          │
│  Chill commentary OK here            token_count=1847       │
│                                      )                      │
│                                                              │
│                                      No Dude flavor         │
│                                      in the data itself     │
└─────────────────────────────────────────────────────────────┘
```

Why? Luna's responses should be Luna's. The Dude does the filing; Luna does the speaking.

---

## 5.2 Core Functions

**Status:** IMPLEMENTED (per AUDIT-ACTORS.md)

The Dude handles six primary tasks:

| Function | What It Does | When It Runs | Status |
|----------|--------------|--------------|--------|
| Entity Resolution | Deduplicate ("Mark" = "Zuck" = "The Landlord") | Immediate | Implemented |
| Knowledge Wiring | Create explicit edges from extractions | Immediate | Implemented |
| Entity Updates | File biographical facts to entity profiles | Immediate | Implemented |
| Entity Rollback | Revert entities to previous versions | On request | Implemented |
| Spreading Activation | Discover hidden connections | Deferred | Planned |
| Synaptic Pruning | Clean low-value edges AND drifting nodes | Periodic | Implemented |

### Message Types (Mailbox Interface)

| Message Type | Purpose | Payload | Status |
|--------------|---------|---------|--------|
| `file` | File extraction from Scribe | `ExtractionOutput dict` | Implemented |
| `entity_update` | Update entity profile | `{update_type, entity_id, name, entity_type, facts, source}` | Implemented |
| `get_context` | Retrieve context for query | `{query, budget, node_types}` | Implemented |
| `resolve_entity` | Find or create entity | `{name, entity_type}` | Implemented |
| `rollback_entity` | Revert to version | `{entity_id, version, reason}` | Implemented |
| `prune` | Run maintenance | `{confidence_threshold, age_days, prune_nodes, max_prune_nodes}` | Implemented |
| `get_stats` | Return statistics | None | Implemented |

### Messages Sent (Outbound)

| Target | Message Type | When | Status |
|--------|--------------|------|--------|
| Engine | `filing_result` | After successful filing (if reply_to set) | Implemented |
| Engine | `entity_update_result` | After entity update (if reply_to set) | Implemented |
| Engine | `rollback_result` | After rollback attempt | Implemented |
| Engine | `context_result` | Response to get_context | Implemented |
| Engine | `entity_resolved` | Response to resolve_entity | Implemented |
| Engine | `prune_result` | Response to prune | Implemented |
| Engine | `librarian_stats` | Response to get_stats | Implemented |

---

## 5.3 Entity Resolution (Deduplication)

**Status:** IMPLEMENTED

"Mark," "Zuck," and "The Landlord" might all be the same node.

### Resolution Strategy (3-Level)

The implementation uses a simplified 3-level resolution:

```python
async def _resolve_entity(
    self,
    name: str,
    entity_type: str,
    source_id: str = "",
) -> str:
    """
    Resolve entity to existing node or create new.

    Resolution order:
    1. Alias cache (O(1))
    2. Exact DB match
    3. Create new if not found
    """
    name_lower = name.lower().strip()

    # 1. Check alias cache
    if name_lower in self.alias_cache:
        logger.debug(f"The Dude: Cache hit for '{name}'")
        return self.alias_cache[name_lower]

    # 2. Check exact DB match via Matrix actor
    matrix = await self._get_matrix()
    if matrix:
        existing = await self._find_existing_node(matrix, name, entity_type)
        if existing:
            self.alias_cache[name_lower] = existing
            self._nodes_merged += 1
            return existing

    # 3. Create new node
    node_id = await self._create_node(name, entity_type, source_id)
    self.alias_cache[name_lower] = node_id
    self._nodes_created += 1

    return node_id
```

### Resolution Priority

| Step | Cost | Skip If |
|------|------|---------|
| Alias cache | O(1) | Never |
| Exact DB match | O(log n) | Cache hit |
| Create new | O(1) | Previous match |

**Note:** The implementation prioritizes simplicity over the full fuzzy matching described in the original spec. Semantic similarity search is deferred to future enhancement.

---

## 5.4 Knowledge Wiring

**Status:** IMPLEMENTED

New memory -> find all related nodes -> create edges.

```python
async def _wire_extraction(
    self,
    extraction: ExtractionOutput,
) -> FilingResult:
    """
    Wire extraction into Memory Matrix.

    1. Resolve/create nodes for each extracted object
    2. Create edges between entities
    """
    result = FilingResult()

    # 1. Process objects - create/resolve nodes
    for obj in extraction.objects:
        node_id = await self._resolve_entity(
            name=obj.content,
            entity_type=obj.type.value if hasattr(obj.type, 'value') else str(obj.type),
            source_id=extraction.source_id,
        )

        # Track if created or merged
        if self._nodes_created > len(result.nodes_created) + len(result.nodes_merged):
            result.nodes_created.append(node_id)
        else:
            result.nodes_merged.append((obj.content, node_id))

        # Also resolve any mentioned entities
        for entity in obj.entities:
            await self._resolve_entity(entity, "ENTITY", extraction.source_id)

    # 2. Create edges via MatrixActor's graph
    for edge in extraction.edges:
        from_id = await self._resolve_entity(edge.from_ref, "ENTITY", extraction.source_id)
        to_id = await self._resolve_entity(edge.to_ref, "ENTITY", extraction.source_id)

        edge_created = await self._create_edge(
            from_id=from_id,
            to_id=to_id,
            edge_type=edge.edge_type,
            confidence=edge.confidence,
        )

        if edge_created:
            result.edges_created.append(f"{from_id}->{to_id}")
        else:
            result.edges_skipped.append(f"duplicate: {edge.from_ref}->{edge.to_ref}")

    return result
```

**Note:** The implementation uses NetworkX (not rustworkx) for graph operations via the MatrixActor. See Section 5.10 for details.

---

## 5.5 Spreading Activation

**Status:** PLANNED (not yet implemented)

The magic part. When filing a fact, proactively find related nodes:

```python
class SpreadingActivation:
    def __init__(self, matrix: MemoryMatrix):
        self.matrix = matrix
        # rustworkx for fast graph traversal
        import rustworkx as rx
        self.graph = matrix.get_rustworkx_graph()

    async def discover_hidden_links(
        self,
        new_entity_ids: list[UUID],
        max_hops: int = 2,
        similarity_threshold: float = 0.7
    ) -> list[UUID]:
        """Find and create inferred edges."""
        inferred_edges = []

        for eid in new_entity_ids:
            # Get neighbors up to max_hops (using rustworkx BFS)
            node_idx = self.matrix.id_to_idx[eid]
            neighbors = rx.bfs_successors(self.graph, node_idx)

            for neighbor_idx in neighbors:
                neighbor_id = self.matrix.idx_to_id[neighbor_idx]

                # Check against OTHER new entities
                for other_eid in new_entity_ids:
                    if other_eid != eid:
                        # Compute similarity
                        similarity = self.compute_similarity(other_eid, neighbor_id)

                        if similarity > similarity_threshold:
                            # Check edge doesn't already exist
                            if not self.matrix.edge_exists(other_eid, neighbor_id, "likely_related"):
                                edge_id = self.matrix.create_edge(
                                    from_id=other_eid,
                                    to_id=neighbor_id,
                                    edge_type="likely_related",
                                    confidence=similarity * 0.5,  # Inferred = lower confidence
                                    source_id="inferred"
                                )
                                inferred_edges.append(edge_id)

        return inferred_edges
```

### Example Spreading Activation

```
Input:
  "Alex is joining the Pi Project"

Step 1: Ben extracts
  - Entity: Alex (PERSON)
  - Entity: Pi Project (PROJECT)
  - Edge: Alex → works_on → Pi Project

Step 2: The Dude files (explicit)
  Alex ──works_on──▶ Pi Project

Step 3: Spreading activation finds
  Pi Project ──has_member──▶ Sarah (existing)

Step 4: The Dude infers (low confidence)
  Alex ──likely_teammate──▶ Sarah (confidence: 0.35)

Result:
  Next time user asks about Alex, Luna can say:
  "Should I introduce Alex to Sarah? They're both on Pi Project."
```

---

## 5.5.1 Entity Updates

**Status:** IMPLEMENTED

The Dude handles entity profile updates from Ben using the EntityResolver:

```python
async def _file_entity_update(self, update: EntityUpdate) -> Optional[Entity]:
    """
    File an entity update to the database.

    Creates or updates an entity based on the update type.
    Always creates a new version record (append-only).
    """
    resolver = await self._get_entity_resolver()
    if not resolver:
        return None

    # Resolve or create the entity
    if update.update_type == ChangeType.CREATE or not update.entity_id:
        entity = await resolver.resolve_or_create(
            name=update.name,
            entity_type=entity_type,
            source=update.source or "scribe",
        )
    else:
        entity = await resolver.get_entity(update.entity_id)

    # Merge new facts with existing
    merged_facts = dict(entity.core_facts)
    merged_facts.update(update.facts)

    # Update entity record and create version record (append-only)
    ...
```

**Key Features:**
- Uses EntityResolver for proper entity resolution
- Creates version records for every update (append-only history)
- Tracks `entity_versions_created` for audit

## 5.5.2 Entity Rollback

**Status:** IMPLEMENTED

The Dude can revert entities to previous versions:

```python
async def _rollback_entity(
    self,
    entity_id: str,
    target_version: Optional[int] = None,
    reason: str = "Rollback requested",
) -> bool:
    """
    Rollback an entity to a previous version.

    Args:
        entity_id: Entity ID to rollback
        target_version: Target version (None = previous version)
        reason: Reason for rollback

    Returns:
        True if rollback successful
    """
    # Get target version record
    row = await resolver.db.fetchone(
        """SELECT core_facts, full_profile, voice_config
           FROM entity_versions WHERE entity_id = ? AND version = ?""",
        (entity_id, target_version)
    )

    # Create new version with rollback data (preserves audit trail)
    await resolver.db.execute(
        """INSERT INTO entity_versions (
            entity_id, version, ..., change_type, change_summary
        ) VALUES (?, ?, ..., 'rollback', ?)""",
        (entity_id, new_version, f"Rolled back to v{target_version}: {reason}")
    )
```

**Key Features:**
- Retrieves target version from `entity_versions` table
- Creates a new version record with `change_type='rollback'`
- Preserves full audit trail of what was changed and why
- Closes out previous version with `valid_until` timestamp

---

## 5.6 Synaptic Pruning

**Status:** IMPLEMENTED

Periodically clean low-value connections and drifting nodes:

```python
class SynapticPruner:
    def __init__(self, matrix: MemoryMatrix):
        self.matrix = matrix

    async def prune(self, config: PruningConfig = None) -> PruningResult:
        """Remove stale, low-confidence, never-accessed edges."""
        config = config or PruningConfig()
        result = PruningResult()

        # Find candidates for pruning
        stale_edges = self.matrix.query("""
            SELECT e.id, e.confidence, e.created_at
            FROM edges e
            LEFT JOIN access_log a ON e.id = a.edge_id
            WHERE e.confidence < :confidence_threshold
              AND e.created_at < datetime('now', :age_threshold)
              AND a.edge_id IS NULL
        """, {
            'confidence_threshold': config.confidence_threshold,  # 0.3
            'age_threshold': config.age_threshold  # '-30 days'
        })

        for edge in stale_edges:
            # Double-check: is this edge part of a chain we care about?
            if not self.is_in_important_chain(edge.id):
                self.matrix.delete_edge(edge.id)
                result.pruned.append(edge.id)
            else:
                result.preserved.append(edge.id)

        return result

    def is_in_important_chain(self, edge_id: UUID) -> bool:
        """Check if edge connects to high-value nodes."""
        edge = self.matrix.get_edge(edge_id)
        from_node = self.matrix.get_node(edge.from_id)
        to_node = self.matrix.get_node(edge.to_id)

        # Preserve if connects to identity nodes
        if from_node.tags and 'identity' in from_node.tags:
            return True
        if to_node.tags and 'identity' in to_node.tags:
            return True

        return False

@dataclass
class PruningConfig:
    confidence_threshold: float = 0.3
    age_threshold: str = '-30 days'
    preserve_identity_chains: bool = True
```

### Drifting Node Cleanup

**Status:** IMPLEMENTED

The Dude prunes "drifting" nodes - entities with low lock-in that are old and never reinforced:

```python
async def _prune_drifting_nodes(
    self,
    age_days: int = 30,
    max_prune: int = 100,
) -> dict:
    """
    Remove nodes that are drifting and old.

    Only prunes nodes that:
    - Have lock_in_state = 'drifting'
    - Are older than age_days
    - Have zero reinforcement_count (never explicitly marked important)

    Returns:
        Dict with 'pruned', 'preserved', and 'candidates' counts
    """
    # Get drifting nodes from MemoryMatrix
    drifting = await matrix.get_drifting_nodes(limit=max_prune * 2)

    for node in drifting:
        # Never prune reinforced nodes
        if node.reinforcement_count > 0:
            continue

        # Skip recent nodes
        if node.created_at.timestamp() > cutoff:
            continue

        # Prune this node
        await matrix.delete_node(node.id)
```

**Key Features:**
- Uses lock-in state from MemoryMatrix (not graph degree)
- Respects `reinforcement_count` to protect user-marked important nodes
- Configurable `age_days` and `max_prune` limits
- Returns detailed statistics for monitoring

---

## 5.6.1 Graph Building via MatrixActor

**Status:** IMPLEMENTED

The Librarian builds the knowledge graph through the MatrixActor's graph interface:

```python
async def _create_edge(
    self,
    from_id: str,
    to_id: str,
    edge_type: str,
    confidence: float = 1.0,
) -> bool:
    """
    Create edge between nodes via MatrixActor's graph.

    Returns True if created, False if duplicate.
    """
    matrix_actor = self.engine.get_actor("matrix")
    if hasattr(matrix_actor, "_graph") and matrix_actor._graph:
        graph = matrix_actor._graph

        # Check if edge already exists (deduplication)
        if graph.has_edge(from_id, to_id, edge_type):
            return False

        # Create edge
        graph.add_edge(
            from_id=from_id,
            to_id=to_id,
            edge_type=edge_type,
            weight=confidence,
        )
        return True
```

**Key Features:**
- Uses NetworkX graph via MatrixActor (not rustworkx)
- Automatic deduplication of edges
- Confidence stored as edge weight

---

## 5.7 Scheduling Model

The Dude runs on a **hybrid schedule**:

| Mode | Trigger | Action | Priority |
|------|---------|--------|----------|
| **Immediate** | Ben's extraction arrives | File nodes, create explicit edges | High |
| **Deferred** | Queue reaches threshold | Batch process inferred edges | Medium |
| **Periodic** | Every 5-30 minutes | Spreading activation, pruning, FAISS rebuild | Low |

### Why Hybrid?

| Mode | Rationale |
|------|-----------|
| Immediate | User expects memories to be available quickly |
| Deferred | Inference is expensive, batch is efficient |
| Periodic | Maintenance shouldn't block conversation |

```python
class LibrarianScheduler:
    def __init__(self, librarian: Librarian):
        self.librarian = librarian
        self.inference_queue: list[UUID] = []
        self.batch_threshold = 10

    async def on_extraction(self, extraction: ExtractionOutput):
        """Event: Ben sent us an extraction."""
        # IMMEDIATE: File the obvious stuff
        result = await self.librarian.wire(extraction)

        # DEFERRED: Queue inference work
        self.inference_queue.extend(result.objects_created)

        if len(self.inference_queue) >= self.batch_threshold:
            await self.process_inference_batch()

    async def process_inference_batch(self):
        """Process accumulated inference work."""
        entity_ids = self.inference_queue.copy()
        self.inference_queue.clear()

        await self.librarian.spreading_activation.discover_hidden_links(entity_ids)

    async def periodic_maintenance(self):
        """Runs every 15 minutes."""
        # 1. Process any remaining inference queue
        if self.inference_queue:
            await self.process_inference_batch()

        # 2. Spreading activation on recent high-value nodes
        recent_nodes = self.librarian.get_recent_nodes(hours=1)
        await self.librarian.spreading_activation.discover_hidden_links(recent_nodes)

        # 3. Prune stale edges
        await self.librarian.pruner.prune()

        # 4. Rebuild FAISS if significant changes
        if self.librarian.matrix.needs_faiss_rebuild():
            await self.librarian.matrix.rebuild_faiss_index()
```

---

## 5.8 Retrieval Contract

**Status:** IMPLEMENTED

When the Director needs context, The Dude provides it.

### Interface

```python
@dataclass
class ContextRequest:
    query: str
    budget_preset: str  # "minimal", "balanced", "rich"
    include_graph: bool = True
    recency_weight: float = 0.3  # How much to favor recent nodes
    entity_hints: list[str] = None  # Known entities to prioritize

@dataclass
class ContextPacket:
    nodes: list[MemoryNode]
    edges: list[MemoryEdge]
    token_count: int
    search_method: str  # "fts5", "faiss", "graph", "hybrid"
    retrieval_ms: int
    confidence_range: tuple[float, float]  # min/max confidence
```

### Budget Presets

| Preset | Token Target | Use Case |
|--------|--------------|----------|
| `minimal` | ~1800 | Voice mode, fast response needed |
| `balanced` | ~3800 | Normal conversation |
| `rich` | ~7200 | Deep research, complex query |

```python
class ContextFetcher:
    BUDGET_PRESETS = {
        'minimal': 1800,
        'balanced': 3800,
        'rich': 7200
    }

    async def fetch(self, request: ContextRequest) -> ContextPacket:
        """
        The Dude's main interface to the Director.
        Returns context within token budget.
        """
        start_time = time.monotonic()
        budget = self.BUDGET_PRESETS[request.budget_preset]

        # 1. Route query to optimal search path
        search_path = self.router.route(request.query)

        # 2. Execute search
        if search_path == SearchPath.FTS5:
            nodes = await self.matrix.fts5_search(request.query)
            method = "fts5"
        elif search_path == SearchPath.FAISS:
            embedding = self.embed(request.query)
            nodes = await self.matrix.faiss_search(embedding)
            method = "faiss"
        elif search_path == SearchPath.GRAPH:
            entities = extract_entities(request.query)
            nodes = await self.matrix.graph_search(entities)
            method = "graph"
        else:  # HYBRID
            nodes = await self.matrix.hybrid_search(request.query)
            method = "hybrid"

        # 3. Apply recency weighting
        nodes = self.apply_recency_weight(nodes, request.recency_weight)

        # 4. Trim to budget
        nodes, edges = self.trim_to_budget(nodes, budget, request.include_graph)

        # 5. Package result
        return ContextPacket(
            nodes=nodes,
            edges=edges,
            token_count=self.count_tokens(nodes, edges),
            search_method=method,
            retrieval_ms=int((time.monotonic() - start_time) * 1000),
            confidence_range=(
                min(n.confidence for n in nodes) if nodes else 0,
                max(n.confidence for n in nodes) if nodes else 0
            )
        )

    def trim_to_budget(
        self,
        nodes: list[MemoryNode],
        budget: int,
        include_graph: bool
    ) -> tuple[list[MemoryNode], list[MemoryEdge]]:
        """Trim nodes to fit token budget, optionally include edges."""
        result_nodes = []
        result_edges = []
        current_tokens = 0

        for node in nodes:
            node_tokens = count_tokens(node.content)

            if current_tokens + node_tokens > budget:
                break

            result_nodes.append(node)
            current_tokens += node_tokens

            if include_graph:
                # Add relevant edges (up to 10% of remaining budget)
                edge_budget = int((budget - current_tokens) * 0.1)
                edges = self.get_edges_for_node(node.id, budget=edge_budget)
                result_edges.extend(edges)
                current_tokens += sum(count_tokens(e.type) for e in edges)

        return result_nodes, result_edges
```

---

## 5.9 Filing Contract

**Status:** IMPLEMENTED

The formal interface between Ben and The Dude:

```python
@dataclass
class FilingResult:
    objects_created: list[UUID]
    objects_merged: list[tuple[str, UUID]]  # (name, existing_id)
    edges_created: list[UUID]
    edges_skipped: list[str]  # reasons
    inferred_edges: list[UUID]
    filing_time_ms: int

async def file(extraction: ExtractionOutput) -> FilingResult:
    """
    File extracted objects and edges into the Substrate.

    Called by the Scribe when extraction is complete.
    Returns detailed results for debugging/monitoring.
    """
    ...
```

### Filing Guarantees

| Guarantee | Implementation |
|-----------|----------------|
| Idempotency | Same extraction filed twice produces same result |
| Atomicity | Either all objects/edges filed or none |
| Consistency | No orphan edges (both endpoints must exist) |
| Deduplication | Entity resolution prevents duplicates |

---

## 5.10 Performance Notes

**Status:** IMPLEMENTED (NetworkX, rustworkx migration deferred)

### Graph Library Choice

The current implementation uses **NetworkX** (not rustworkx as originally planned):

```python
import networkx as nx

# Current implementation (NetworkX)
self._graph = nx.DiGraph()
self._graph.add_node(node_id, **node_data)
self._graph.add_edge(from_id, to_id, **edge_data)
neighbors = list(self._graph.neighbors(node_id))
```

**Rationale:** NetworkX is sufficient for current scale (thousands of nodes). The rustworkx migration is deferred until performance profiling indicates need.

**Future Optimization:** If graph operations become a bottleneck (>10K nodes), migrate to rustworkx:

```python
import rustworkx as rx

# rustworkx (100x faster for large graphs)
neighbors = rx.bfs_successors(G, node_idx)
```

See Part III Section 3.9 for migration details.

### Latency Budget

```
┌────────────────────────────────────────────────────────────────┐
│  CONTEXT RETRIEVAL (target: <100ms)                            │
│                                                                 │
│  Query routing: 5ms                                            │
│  Bloom filter check: 1ms                                       │
│  FTS5/FAISS/Graph search: 50-80ms                              │
│  Trim to budget: 5ms                                           │
│  ────────────────────────────────                              │
│  Total: 61-91ms ✓                                              │
└────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────┐
│  FILING (async, non-blocking)                                  │
│                                                                 │
│  Entity resolution: 5-20ms                                     │
│  Edge creation: 10ms                                           │
│  Embedding storage: 5ms                                        │
│  ────────────────────────────────                              │
│  Total: 20-35ms                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 5.11 Librarian Statistics

**Status:** IMPLEMENTED

The Dude tracks comprehensive filing statistics:

```python
{
    "filings_count": 150,           # Total filing operations
    "nodes_created": 1234,          # New entities added
    "nodes_merged": 567,            # Deduplicated to existing
    "edges_created": 890,           # Relationships filed
    "context_retrievals": 450,      # Context queries served
    "entity_updates_filed": 123,    # Profile updates filed
    "entity_versions_created": 180, # Version records created
    "avg_filing_time_ms": 35,       # Average operation time
    "cache_size": 456,              # Alias cache entries
    "inference_queue_size": 0       # Pending inference work
}
```

---

## 5.12 The Dude's Principles

| Principle | Implementation |
|-----------|----------------|
| **Separation** | Personality in process, neutrality in output |
| **Lazy Inference** | Don't infer everything immediately; batch and defer |
| **Confidence Tracking** | Every edge knows how certain we are |
| **Prune Aggressively** | Low-value connections cost more than they're worth |
| **Budget Awareness** | Never return more context than requested |

> "The Dude abides." — The Dude

The Dude abides by these principles. He files things where they belong, connects what should be connected, and cleans up the mess. No drama. Just good filing.

---

*End of Part V (v3.0)*
