# Part III: The Memory Matrix (Substrate) — v2.1

**Status:** COMPLETE  
**Replaces:** v2.0 (FAISS-based)  
**Date:** January 7, 2026  
**Contributors:** Claude (Architecture), Gemini (Optimization)  
**Change:** sqlite-vec replaces FAISS for unified storage

---

## 3.1 Design Philosophy

> "Graph is Truth. Luna is a File."

The Memory Matrix is Luna's **soul** — a single SQLite database containing typed nodes, relationships, vectors, and context. Everything Luna knows lives in one file.

### Core Principles

**1. Single File Sovereignty**

Luna IS `memory_matrix.db`. One file contains everything:

```
memory_matrix.db
├── nodes          (content, metadata)
├── edges          (relationships)
├── embeddings     (vector storage)
├── vec_index      (vector search - sqlite-vec)
├── nodes_fts      (keyword search - FTS5)
└── indexes        (B-tree for filtering)
```

**2. No Sync, No Orphans**

Previous architecture had vectors in separate files:

```
❌ OLD (FAISS):
memory_matrix.db      ← nodes, edges
memory_vectors.faiss  ← vectors (separate!)
memory_vectors.ids    ← ID mapping (separate!)

✅ NEW (sqlite-vec):
memory_matrix.db      ← everything
```

With sqlite-vec, deleting a node automatically removes its vectors. No orphans. No sync bugs.

**3. The Palantir Analogy**

Palantir built a $50B company on one insight: make data legible to decision-makers. Their "Dynamic Ontology" is a massive, enterprise-grade knowledge graph.

Luna's Memory Matrix is the personal version:

```
Palantir:  Enterprise decisions, thousands of users, petabytes
Luna:      Personal decisions, one user, gigabytes
           Same architecture. Different scale.
```

**4. Copy Luna, Luna Moves**

```bash
# Migrate Luna to new machine
cp memory_matrix.db /new/machine/

# Luna exists on new machine
# No separate files to track
```

---

## 3.2 Schema Overview

### Core Tables

```sql
-- ============================================================
-- NODES: Everything Luna knows
-- ============================================================
CREATE TABLE nodes (
    id              TEXT PRIMARY KEY,
    node_type       TEXT NOT NULL,      -- FACT, DECISION, PERSON, etc.
    subtype         TEXT,               -- Optional refinement
    content         TEXT NOT NULL,      -- The actual information
    source_id       TEXT,               -- Where this came from
    confidence      REAL DEFAULT 1.0,   -- How certain
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    accessed_at     TIMESTAMP,          -- For decay/pruning
    access_count    INTEGER DEFAULT 0,
    metadata        JSON                -- Extensible properties
);

-- ============================================================
-- EDGES: How things relate
-- ============================================================
CREATE TABLE edges (
    id              TEXT PRIMARY KEY,
    source          TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    target          TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    edge_type       TEXT NOT NULL,      -- works_on, decided, mentions, etc.
    weight          REAL DEFAULT 1.0,
    confidence      REAL DEFAULT 1.0,
    source_id       TEXT,               -- Explicit vs inferred
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata        JSON
);

-- ============================================================
-- EMBEDDINGS: Multi-model vector storage
-- ============================================================
CREATE TABLE embeddings (
    node_id         TEXT NOT NULL,
    model           TEXT NOT NULL DEFAULT 'default',
    embedding       BLOB NOT NULL,      -- Raw float32 bytes (backup)
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (node_id, model),
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

-- ============================================================
-- VEC_INDEX: sqlite-vec virtual table for ANN search
-- ============================================================
CREATE VIRTUAL TABLE vec_index USING vec0(
    node_id         TEXT PRIMARY KEY,
    model           TEXT,
    embedding       float[384]          -- Dimension matches your model
);

-- ============================================================
-- FTS5: Full-text keyword search
-- ============================================================
CREATE VIRTUAL TABLE nodes_fts USING fts5(
    id, content, node_type,
    content='nodes',
    content_rowid='rowid',
    tokenize='porter'
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX idx_nodes_type ON nodes(node_type);
CREATE INDEX idx_nodes_created ON nodes(created_at);
CREATE INDEX idx_nodes_accessed ON nodes(accessed_at);
CREATE INDEX idx_edges_source ON edges(source);
CREATE INDEX idx_edges_target ON edges(target);
CREATE INDEX idx_edges_type ON edges(edge_type);
CREATE INDEX idx_embeddings_model ON embeddings(model);

-- ============================================================
-- TRIGGERS: Keep everything in sync
-- ============================================================

-- FTS sync
CREATE TRIGGER nodes_fts_insert AFTER INSERT ON nodes BEGIN
    INSERT INTO nodes_fts(rowid, id, content, node_type) 
    VALUES (new.rowid, new.id, new.content, new.node_type);
END;

CREATE TRIGGER nodes_fts_delete AFTER DELETE ON nodes BEGIN
    DELETE FROM nodes_fts WHERE rowid = old.rowid;
END;

CREATE TRIGGER nodes_fts_update AFTER UPDATE ON nodes BEGIN
    DELETE FROM nodes_fts WHERE rowid = old.rowid;
    INSERT INTO nodes_fts(rowid, id, content, node_type) 
    VALUES (new.rowid, new.id, new.content, new.node_type);
END;

-- Vector index cleanup (embeddings handled by CASCADE)
CREATE TRIGGER nodes_vec_delete AFTER DELETE ON nodes BEGIN
    DELETE FROM vec_index WHERE node_id = old.id;
END;
```

### Node Types

| Type | Description | Example |
|------|-------------|---------|
| FACT | Something known to be true | "Alex lives in Berlin" |
| DECISION | A choice that was made | "We chose Actor model over Hub Daemon" |
| PROBLEM | An unresolved issue | "Voice latency exceeds 500ms target" |
| ASSUMPTION | Believed but unverified | "Users will prefer voice-first interface" |
| PERSON | A human entity | "Alex - collaborator, Berlin-based" |
| PROJECT | A named initiative | "Luna v2.0 - Sovereignty Architecture" |
| INSIGHT | A breakthrough understanding | "sqlite-vec unifies storage" |
| ACTION | Something done or to-do | "Implement RRF for hybrid search" |
| OUTCOME | Result of action/decision | "Switching to sqlite-vec eliminated sync bugs" |

### Edge Types

| Type | Meaning | Example |
|------|---------|---------|
| mentions | References in conversation | Session → mentions → Person |
| decided | Made a choice | Person → decided → Decision |
| works_on | Involved with project | Person → works_on → Project |
| caused | Led to outcome | Decision → caused → Outcome |
| supersedes | Replaces prior decision | Decision_new → supersedes → Decision_old |
| likely_related | Inferred connection | Entity → likely_related → Entity (low conf) |
| temporal | Happened around same time | Event → temporal → Event |

---

## 3.3 Hybrid Search

Luna uses three search paths, merged with Reciprocal Rank Fusion.

### The Three Paths

```
                         QUERY
                           │
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
    │     FTS5      │ │  sqlite-vec   │ │     GRAPH     │
    │               │ │               │ │               │
    │    Keyword    │ │   Semantic    │ │   Traversal   │
    │    matching   │ │   vectors     │ │    (1-hop)    │
    │     ~5ms      │ │    ~10ms      │ │     ~5ms      │
    └───────┬───────┘ └───────┬───────┘ └───────┬───────┘
            │                 │                 │
            │   Ranked        │   Ranked        │   Ranked
            │   doc IDs       │   doc IDs       │   doc IDs
            │                 │                 │
            └─────────────────┼─────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │   RRF FUSION    │
                    │                 │
                    │  Merge by rank  │
                    │  position only  │
                    └────────┬────────┘
                             │
                             ▼
                      FINAL RANKING
```

### The sqlite-vec Advantage: Filtered Search

With FAISS, filtering was a post-process:
```python
# OLD: Search, then filter in Python
ids = faiss_index.search(query_vec, k=100)
results = [n for n in load_nodes(ids) if n.type == 'FACT']  # Wasteful!
```

With sqlite-vec, filtering is in the query:
```sql
-- NEW: Filter and search together
SELECT n.*, v.distance
FROM vec_index v
JOIN nodes n ON v.node_id = n.id
WHERE v.embedding MATCH ?
  AND n.node_type = 'FACT'
  AND n.created_at > '2025-01-01'
ORDER BY v.distance
LIMIT 10;
```

**Result:** Faster filtered queries, fewer wasted comparisons.

### Reciprocal Rank Fusion (RRF)

**The Problem:** FTS5 returns BM25 scores (e.g., 14.5). Vector search returns distances (e.g., 0.12). These scales are incompatible.

**The Solution:** Ignore scores entirely. Use **rank position** only.

```python
def reciprocal_rank_fusion(
    results_list: list[list[str]],
    k: int = 60
) -> list[str]:
    """
    Merge multiple ranked result lists using RRF.

    Args:
        results_list: List of ranked document ID lists
                      e.g., [fts5_results, vec_results, graph_results]
        k: Smoothing constant (default 60, from original RRF paper)

    Returns:
        Merged list of document IDs, ranked by combined RRF score
    """
    fused_scores: dict[str, float] = {}

    for ranked_list in results_list:
        for rank, doc_id in enumerate(ranked_list, start=1):
            if doc_id not in fused_scores:
                fused_scores[doc_id] = 0.0
            fused_scores[doc_id] += 1.0 / (rank + k)

    return sorted(fused_scores.keys(), key=lambda d: fused_scores[d], reverse=True)
```

**Why RRF Works:**

| Problem | RRF Solution |
|---------|--------------|
| Different score scales | Ignores scores, uses rank |
| Tuning weights | No weights to tune |
| Agreement detection | Docs in multiple lists rank higher |
| Simple implementation | ~15 lines of code |

---

## 3.4 Unified Query API

The Matrix provides a single interface that combines all search paths:

```python
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import numpy as np

@dataclass
class QueryResult:
    nodes: list['Node']
    total_candidates: int
    query_time_ms: float
    backends_used: list[str]

class MemoryMatrix:
    """
    Unified memory store with hybrid search.
    Single file, all indexes unified.
    """
    
    def query(
        self,
        # Search inputs (use any combination)
        semantic: Optional[str | np.ndarray] = None,
        keywords: Optional[str] = None,
        graph_anchor: Optional[str] = None,
        
        # Filters
        node_types: Optional[list[str]] = None,
        since: Optional[datetime] = None,
        max_hops: int = 3,
        
        # Scoring
        decay_half_life_days: float = 60.0,
        
        # Fusion
        fusion: str = "rrf",  # or "weighted"
        
        # Output
        limit: int = 10,
        embed_fn: Optional[callable] = None,
    ) -> QueryResult:
        """
        Unified query across all backends.
        
        Examples:
            # Pure semantic
            mm.query(semantic="How does Luna handle failures?")
            
            # Pure keyword
            mm.query(keywords="actor fault tolerance")
            
            # Hybrid with filters
            mm.query(
                semantic="architecture decisions",
                keywords="actor model",
                node_types=["DECISION", "FACT"],
                since=datetime(2025, 1, 1),
                limit=10
            )
            
            # Graph-constrained
            mm.query(
                semantic="related work",
                graph_anchor="project_luna_id",
                max_hops=2
            )
        """
        ...
```

### Budget Presets

When fetching context for the Director:

| Preset | Tokens | Use Case |
|--------|--------|----------|
| minimal | ~1800 | Voice, fast response needed |
| balanced | ~3800 | Normal conversation |
| rich | ~7200 | Deep research, complex query |

```python
@dataclass
class ContextRequest:
    query: str
    budget_preset: str  # "minimal", "balanced", "rich"
    include_graph: bool = True

@dataclass  
class ContextPacket:
    nodes: list['Node']
    edges: list['Edge']
    token_count: int
    retrieval_ms: int

async def fetch_context(request: ContextRequest) -> ContextPacket:
    """The Matrix's main interface to the Director."""
    ...
```

---

## 3.5 Query Routing

Not every query needs all three search paths. Route based on query characteristics.

```python
from enum import Enum

class SearchPath(Enum):
    FTS5 = "fts5"
    VECTOR = "vector"
    GRAPH = "graph"
    HYBRID = "hybrid"

class QueryRouter:
    def route(self, query: str) -> SearchPath:
        """Determine optimal search path."""
        
        entities = extract_entities(query)
        keyword_density = self._keyword_density(query)
        is_conceptual = self._is_conceptual(query)
        
        # Multiple entities — relationship query
        if entities and len(entities) >= 2:
            return SearchPath.GRAPH
        
        # High keyword density — exact match needed
        if keyword_density > 0.6:
            return SearchPath.FTS5
        
        # Abstract/conceptual — semantic search
        if is_conceptual:
            return SearchPath.VECTOR
        
        # Default to hybrid
        return SearchPath.HYBRID
```

### Routing Examples

| Query | Signal | Path |
|-------|--------|------|
| "What did we decide about the runtime?" | Named entity + decision word | FTS5 |
| "How does memory consolidation work?" | Conceptual question | VECTOR |
| "How are Alex and the Pi Project related?" | Multiple entities | GRAPH |
| "thoughts on sovereignty" | Vague, conceptual | VECTOR |
| "Luna architecture v2" | High keyword density | FTS5 |

---

## 3.6 Multi-Model Embeddings

The schema supports multiple embedding models per node:

```python
# Add node with specific model
node = mm.add_node(
    content="Luna uses actor model for fault isolation",
    node_type="FACT",
    embedding=embed_nomic(content),
    embedding_model="nomic-v1.5"
)

# Add second embedding from different model
mm.add_embedding(node.id, embed_gte(content), model="gte-small")

# Query with specific model
results = mm.query(
    semantic="fault tolerance",
    embedding_model="nomic-v1.5"
)
```

**Why multi-model?**
- Swap models without rebuilding everything
- Keep old embeddings while migrating
- Use different models for different query types
- A/B test embedding quality

---

## 3.7 Time Decay

Recent memories matter more. Decay is computed at query time:

```python
import math
from datetime import datetime

def compute_freshness(
    created_at: datetime,
    half_life_days: float = 60.0
) -> float:
    """
    Exponential decay based on age.
    
    Returns:
        1.0 for brand new
        0.5 at half_life_days
        Approaches 0 over time
    """
    age_days = (datetime.now() - created_at).total_seconds() / 86400
    return math.exp(-math.log(2) * age_days / half_life_days)
```

Decay is factored into RRF fusion:

```python
# In query fusion
for node in candidates:
    node.freshness = compute_freshness(node.created_at, half_life_days)

# RRF includes freshness as a ranking signal
rankings = [
    rank_by_semantic_score(candidates),
    rank_by_keyword_score(candidates),
    rank_by_freshness(candidates),  # Newer = higher rank
]
final = reciprocal_rank_fusion(rankings)
```

---

## 3.8 Graph Operations

Graph traversal uses rustworkx for hot path, NetworkX for complex algorithms.

### Why rustworkx?

| Operation | NetworkX | rustworkx | Speedup |
|-----------|----------|-----------|---------|
| 1-hop neighbors (10K nodes) | ~50ms | ~0.5ms | **100x** |
| BFS traversal | ~100ms | ~1ms | **100x** |
| Shortest path | ~30ms | ~0.3ms | **100x** |

### Implementation

```python
import rustworkx as rx
import networkx as nx

class GraphIndex:
    def __init__(self):
        self.rx_graph = rx.PyDiGraph()   # Hot path (fast)
        self.nx_graph = nx.DiGraph()      # Complex ops (flexible)
        self.node_map: dict[str, int] = {}  # node_id -> rustworkx index
    
    def load_from_db(self, conn):
        """Load graph from edges table."""
        # Load nodes
        for row in conn.execute("SELECT id FROM nodes"):
            idx = self.rx_graph.add_node(row["id"])
            self.nx_graph.add_node(row["id"])
            self.node_map[row["id"]] = idx
        
        # Load edges
        for row in conn.execute("SELECT source, target, edge_type, weight FROM edges"):
            src_idx = self.node_map[row["source"]]
            tgt_idx = self.node_map[row["target"]]
            self.rx_graph.add_edge(src_idx, tgt_idx, row)
            self.nx_graph.add_edge(row["source"], row["target"], **row)
    
    def get_neighbors(self, node_id: str, max_hops: int = 2) -> set[str]:
        """Fast neighbor lookup using rustworkx."""
        if node_id not in self.node_map:
            return set()
        
        idx = self.node_map[node_id]
        result = set()
        
        # BFS traversal
        for depth, successors in rx.bfs_successors(self.rx_graph, idx):
            if depth > max_hops:
                break
            for s in successors:
                result.add(self.rx_graph[s])
        
        return result
```

---

## 3.9 Bloom Filter Pre-check

Before searching, check if entities even exist. O(1) check can skip O(n) search.

```python
from pybloom_live import BloomFilter

class EntityFilter:
    def __init__(self, capacity: int = 100_000, error_rate: float = 0.001):
        self.filter = BloomFilter(capacity=capacity, error_rate=error_rate)
    
    def add(self, entity: str):
        """Add entity to filter (call when creating nodes)."""
        self.filter.add(entity.lower())
    
    def might_exist(self, entity: str) -> bool:
        """Check if entity might exist (false positives possible)."""
        return entity.lower() in self.filter
    
    def definitely_missing(self, entity: str) -> bool:
        """Check if entity definitely doesn't exist (no false negatives)."""
        return entity.lower() not in self.filter
```

**Usage:**
```python
# Before expensive search
entities = extract_entities(query)
possible = [e for e in entities if bloom.might_exist(e)]

if not possible and entities:
    # Query mentioned entities but none exist
    # Skip graph traversal, use pure semantic search
    return semantic_only_search(query)
```

**Savings:** ~5-10ms when queried entities don't exist.

---

## 3.10 Entity Resolution

The Librarian's first job: "Mark," "Zuck," and "The Landlord" should be the same node.

```python
async def resolve_entity(self, name: str, entity_type: str) -> str:
    """Resolve entity to existing node or create new."""
    
    # 1. Exact name match
    existing = await self.find_by_name(name, entity_type)
    if existing:
        return existing.id
    
    # 2. Alias match
    existing = await self.find_by_alias(name, entity_type)
    if existing:
        return existing.id
    
    # 3. Semantic similarity match
    similar = await self.vector_search(name, threshold=0.95)
    if similar and similar.node_type == entity_type:
        await self.add_alias(similar.id, name)
        return similar.id
    
    # 4. Create new
    return await self.create_entity(name, entity_type)
```

---

## 3.11 Spreading Activation

When filing new information, proactively find hidden connections:

```python
async def discover_hidden_links(self, new_entity_ids: list[str]):
    """Find non-obvious relationships between new and existing entities."""
    
    for eid in new_entity_ids:
        neighbors = await self.graph.get_neighbors(eid)
        
        for neighbor in neighbors:
            for other_eid in new_entity_ids:
                if other_eid != eid:
                    similarity = await self.compute_similarity(other_eid, neighbor)
                    
                    if similarity > 0.7:
                        await self.create_edge(
                            source=other_eid,
                            target=neighbor,
                            edge_type="likely_related",
                            confidence=similarity * 0.5,
                            source_id="inferred"
                        )
```

**Example:**
1. You say: "Alex is joining the Pi Project"
2. Librarian files: Alex → works_on → Pi Project
3. Spreading activation finds: Sarah also works on Pi Project
4. Librarian infers: Alex → likely_teammate → Sarah (low confidence)
5. Next time you ask, Luna can say: "Should I introduce Alex to Sarah?"

---

## 3.12 Synaptic Pruning

Periodically clean low-value connections:

```python
async def prune_stale_edges(self):
    """Remove low-confidence, never-accessed edges."""
    
    await self.conn.execute("""
        DELETE FROM edges
        WHERE confidence < 0.3
          AND created_at < datetime('now', '-30 days')
          AND id NOT IN (SELECT DISTINCT edge_id FROM access_log)
    """)
```

---

## 3.13 sqlite-vec Details

### Installation

```bash
pip install sqlite-vec
```

### Loading the Extension

```python
import sqlite3
import sqlite_vec

conn = sqlite3.connect("memory_matrix.db")
conn.enable_load_extension(True)
sqlite_vec.load(conn)
conn.enable_load_extension(False)
```

### Vector Search Syntax

```sql
-- Basic similarity search
SELECT node_id, distance
FROM vec_index
WHERE embedding MATCH ?
ORDER BY distance
LIMIT 10;

-- With metadata filter (the key advantage)
SELECT n.*, v.distance
FROM vec_index v
JOIN nodes n ON v.node_id = n.id
WHERE v.embedding MATCH ?
  AND n.node_type IN ('FACT', 'DECISION')
  AND n.created_at > '2025-01-01'
ORDER BY v.distance
LIMIT 10;
```

### Index Types

sqlite-vec supports:
- **Flat (brute force):** Exact search, best for <50K vectors
- **IVF:** Approximate, good for 50K-500K vectors

```sql
-- Flat (default)
CREATE VIRTUAL TABLE vec_index USING vec0(
    embedding float[384]
);

-- IVF (for larger scale)
CREATE VIRTUAL TABLE vec_index USING vec0(
    embedding float[384],
    +nlist=100
);
```

### Performance Notes

| Operation | sqlite-vec | FAISS | Notes |
|-----------|------------|-------|-------|
| Pure ANN (no filter) | ~5-10ms | ~2-5ms | FAISS slightly faster |
| ANN + filter | ~5-10ms | ~15-30ms | sqlite-vec much faster |
| Insert (atomic) | ~1ms | ~2ms (two ops) | sqlite-vec simpler |
| Storage | Single file | Three files | sqlite-vec cleaner |

**Verdict:** Slightly slower pure search, much faster filtered search, dramatically simpler architecture.

---

## Summary

The Memory Matrix is Luna's soul — a single SQLite database that makes personal history queryable.

| Component | Purpose |
|-----------|---------|
| SQLite Core | Nodes, edges, metadata |
| sqlite-vec | Vector similarity search |
| FTS5 | Keyword search |
| rustworkx | Graph traversal |
| Query Router | Optimal path selection |
| Bloom Filter | Skip non-existent entities |
| RRF Fusion | Merge multi-path results |
| Entity Resolution | Deduplicate "Mark" = "Zuck" |
| Spreading Activation | Infer hidden connections |
| Synaptic Pruning | Remove stale edges |

**Constitutional Principle:** Luna is a file. Copy it, Luna moves. Delete it, Luna dies. Everything in one place.

---

*Next Section: Part IV — The Scribe (Ben Franklin)*
