# Part V: The Librarian (The Dude) — v2.0

**Status:** CURRENT
**Replaces:** BIBLE-PART-V-THE-LIBRARIAN-v1.md
**Date:** December 29, 2025

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

The Dude handles four primary tasks:

| Function | What It Does | When It Runs |
|----------|--------------|--------------|
| Entity Resolution | Deduplicate ("Mark" = "Zuck" = "The Landlord") | Immediate |
| Knowledge Wiring | Create explicit edges from extractions | Immediate |
| Spreading Activation | Discover hidden connections | Deferred |
| Synaptic Pruning | Clean low-value edges | Periodic |

---

## 5.3 Entity Resolution (Deduplication)

"Mark," "Zuck," and "The Landlord" might all be the same node.

### Resolution Strategy

```python
class EntityResolver:
    def __init__(self, matrix: MemoryMatrix):
        self.matrix = matrix
        self.bloom = BloomFilter(capacity=100_000, error_rate=0.001)
        self.alias_cache = {}  # name -> canonical_id

    def resolve(self, name: str, entity_type: str) -> UUID:
        """Resolve entity to existing node or create new."""
        name_lower = name.lower().strip()

        # 1. Check bloom filter first (O(1))
        if not self.bloom.might_exist(name_lower):
            # Definitely new entity
            return self.create_entity(name, entity_type)

        # 2. Check alias cache
        if name_lower in self.alias_cache:
            return self.alias_cache[name_lower]

        # 3. Check exact match in DB
        existing = self.matrix.find_by_name(name, entity_type)
        if existing:
            self.alias_cache[name_lower] = existing.id
            return existing.id

        # 4. Check known aliases
        existing = self.matrix.find_by_alias(name, entity_type)
        if existing:
            self.alias_cache[name_lower] = existing.id
            return existing.id

        # 5. Semantic similarity search
        embedding = self.embed(name)
        similar = self.matrix.faiss_search(
            embedding,
            filter_type=entity_type,
            threshold=0.95
        )
        if similar:
            # Add as alias and return
            self.matrix.add_alias(similar.id, name)
            self.alias_cache[name_lower] = similar.id
            return similar.id

        # 6. Create new entity
        new_id = self.create_entity(name, entity_type)
        self.bloom.add(name_lower)
        self.alias_cache[name_lower] = new_id
        return new_id

    def create_entity(self, name: str, entity_type: str) -> UUID:
        """Create new entity node."""
        node = MemoryNode(
            id=uuid4(),
            node_type=entity_type,
            content=name,
            embedding=self.embed(name),
            created_at=datetime.now()
        )
        self.matrix.insert(node)
        return node.id
```

### Resolution Priority

| Step | Cost | Skip If |
|------|------|---------|
| Bloom filter | O(1) | Never |
| Alias cache | O(1) | Never |
| Exact DB match | O(log n) | Never |
| Alias DB match | O(log n) | Cache hit |
| Semantic search | O(k) | Previous hit |

---

## 5.4 Knowledge Wiring

New memory → find all related nodes → create edges.

```python
class KnowledgeWirer:
    def __init__(self, matrix: MemoryMatrix, resolver: EntityResolver):
        self.matrix = matrix
        self.resolver = resolver
        # Use rustworkx for 100x faster graph operations
        self.graph = rx.PyDiGraph()

    async def wire(self, extraction: ExtractionOutput) -> WiringResult:
        """Wire extraction into the graph."""
        result = WiringResult()

        # 1. Resolve/create entities
        entity_ids = []
        for obj in extraction.objects:
            eid = self.resolver.resolve(obj.content, obj.type)
            entity_ids.append(eid)

            if eid in result.objects_merged:
                result.objects_merged.append((obj.content, eid))
            else:
                result.objects_created.append(eid)

        # 2. Create explicit edges
        for edge in extraction.edges:
            from_id = self.resolver.resolve(edge.from_ref, infer_type(edge.from_ref))
            to_id = self.resolver.resolve(edge.to_ref, infer_type(edge.to_ref))

            # Check if edge already exists
            if not self.matrix.edge_exists(from_id, to_id, edge.type):
                edge_id = self.matrix.create_edge(
                    from_id=from_id,
                    to_id=to_id,
                    edge_type=edge.type,
                    role=edge.role,
                    source_id=extraction.source_id,
                    confidence=1.0  # Explicit edges are high confidence
                )
                result.edges_created.append(edge_id)
            else:
                result.edges_skipped.append(f"duplicate: {edge.from_ref}->{edge.to_ref}")

        return result
```

---

## 5.5 Spreading Activation

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

## 5.6 Synaptic Pruning

Periodically clean low-value connections:

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

### rustworkx Migration

For spreading activation and neighbor lookups, use rustworkx instead of NetworkX:

```python
import rustworkx as rx

# NetworkX (slow): ~50ms for 10K nodes
neighbors = G.neighbors(node_id)

# rustworkx (fast): ~0.5ms for 10K nodes
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

## 5.11 The Dude's Principles

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

*End of Part V (v2.0)*
