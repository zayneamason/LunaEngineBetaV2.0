# Part III: The Memory Matrix (Substrate) — v2.2

**Status:** COMPLETE
**Replaces:** v2.1 (January 7, 2026)
**Last Updated:** January 25, 2026
**Contributors:** Claude (Architecture), Gemini (Optimization)
**Change Log:**
- v2.2: Corrected table names (`memory_nodes`, `graph_edges`), documented actual schema, noted FTS5 not implemented (uses LIKE queries), updated sqlite-vec references

---

## 3.1 Design Philosophy

> "Graph is Truth. Luna is a File."

The Memory Matrix is Luna's **soul** — a single SQLite database containing typed nodes, relationships, vectors, and context. Everything Luna knows lives in one file.

### Core Principles

**1. Single File Sovereignty**

Luna IS `luna_engine.db`. One file contains everything:

```
luna_engine.db
├── memory_nodes     (content, metadata, lock-in state)
├── graph_edges      (relationships)
├── memory_embeddings (vector storage - sqlite-vec virtual table)
├── conversation_turns (three-tier history)
├── entities         (people, places, projects)
└── indexes          (B-tree for filtering)
```

> **Note:** FTS5 full-text search is NOT currently implemented. The system uses LIKE pattern matching for keyword search. This is a known limitation that may be addressed in a future release.

**2. No Sync, No Orphans**

Previous architecture had vectors in separate files:

```
FAISS (Not Used):
memory_matrix.db      <- nodes, edges
memory_vectors.faiss  <- vectors (separate!)
memory_vectors.ids    <- ID mapping (separate!)

sqlite-vec (Current Implementation):
luna_engine.db        <- everything in one file
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
cp data/luna_engine.db /new/machine/data/

# Luna exists on new machine
# No separate files to track
```

---

## 3.2 Schema Overview

### Core Tables

```sql
-- ============================================================
-- MEMORY_NODES: Everything Luna knows
-- ============================================================
CREATE TABLE IF NOT EXISTS memory_nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,          -- FACT, DECISION, PROBLEM, ACTION, CONTEXT
    content TEXT NOT NULL,
    summary TEXT,                      -- Short summary for display
    source TEXT,                       -- Where this came from
    confidence REAL DEFAULT 1.0,       -- 0-1 confidence score
    importance REAL DEFAULT 0.5,       -- 0-1 importance score
    access_count INTEGER DEFAULT 0,    -- Times retrieved (for lock-in)
    reinforcement_count INTEGER DEFAULT 0,  -- Times reinforced (for lock-in)
    lock_in REAL DEFAULT 0.15,         -- Lock-in coefficient (0.15-0.85)
    lock_in_state TEXT DEFAULT 'drifting',  -- drifting, fluid, settled
    last_accessed TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    metadata TEXT                      -- JSON for extra data
);

-- ============================================================
-- GRAPH_EDGES: How things relate
-- ============================================================
CREATE TABLE IF NOT EXISTS graph_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    relationship TEXT NOT NULL,        -- DEPENDS_ON, RELATES_TO, CAUSED_BY, etc.
    strength REAL DEFAULT 1.0,         -- 0-1 edge weight
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    metadata TEXT,
    FOREIGN KEY (from_id) REFERENCES memory_nodes(id),
    FOREIGN KEY (to_id) REFERENCES memory_nodes(id),
    UNIQUE(from_id, to_id, relationship)
);

-- ============================================================
-- CONVERSATION_TURNS: Three-tier history system
-- ============================================================
CREATE TABLE IF NOT EXISTS conversation_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,                -- user, assistant, system
    content TEXT NOT NULL,
    tokens INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    metadata TEXT,
    tier TEXT DEFAULT 'active',        -- 'active', 'recent', 'archive'
    compressed TEXT,                   -- Compressed summary (for recent tier)
    compressed_at REAL,
    archived_at REAL,
    context_refs TEXT                  -- JSON array of referenced context IDs
);

-- ============================================================
-- MEMORY_EMBEDDINGS: sqlite-vec virtual table for ANN search
-- Created dynamically when sqlite-vec extension is loaded
-- ============================================================
-- CREATE VIRTUAL TABLE IF NOT EXISTS memory_embeddings USING vec0(
--     id TEXT PRIMARY KEY,
--     embedding FLOAT[1536]           -- OpenAI text-embedding-3-small dimension
-- );

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX IF NOT EXISTS idx_nodes_type ON memory_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_created ON memory_nodes(created_at);
CREATE INDEX IF NOT EXISTS idx_nodes_importance ON memory_nodes(importance DESC);
CREATE INDEX IF NOT EXISTS idx_nodes_accessed ON memory_nodes(last_accessed DESC);
CREATE INDEX IF NOT EXISTS idx_nodes_lock_in ON memory_nodes(lock_in DESC);
CREATE INDEX IF NOT EXISTS idx_nodes_lock_in_state ON memory_nodes(lock_in_state);

CREATE INDEX IF NOT EXISTS idx_edges_from ON graph_edges(from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON graph_edges(to_id);
CREATE INDEX IF NOT EXISTS idx_edges_relationship ON graph_edges(relationship);

-- ============================================================
-- TRIGGERS: Keep everything in sync
-- ============================================================

-- Update timestamp on node modification
CREATE TRIGGER IF NOT EXISTS update_node_timestamp
AFTER UPDATE ON memory_nodes
BEGIN
    UPDATE memory_nodes SET updated_at = datetime('now') WHERE id = NEW.id;
END;

-- Track access patterns
CREATE TRIGGER IF NOT EXISTS track_node_access
AFTER UPDATE OF access_count ON memory_nodes
BEGIN
    UPDATE memory_nodes SET last_accessed = datetime('now') WHERE id = NEW.id;
END;
```

### Node Types

| Type | Description | Example |
|------|-------------|---------|
| FACT | Something known to be true | "Alex lives in Berlin" |
| DECISION | A choice that was made | "We chose Actor model over Hub Daemon" |
| PROBLEM | An unresolved issue | "Voice latency exceeds 500ms target" |
| ACTION | Something done or to-do | "Implement RRF for hybrid search" |
| CONTEXT | Situational information | "Working on Luna Engine v2.0" |

### Edge Types (Relationship Types)

| Type | Meaning | Example |
|------|---------|---------|
| DEPENDS_ON | Requires another node | Implementation -> depends_on -> Design |
| RELATES_TO | General connection | Person -> relates_to -> Project |
| CAUSED_BY | Result of another | Outcome -> caused_by -> Decision |
| FOLLOWED_BY | Temporal sequence | Event A -> followed_by -> Event B |
| CONTRADICTS | Conflicting information | Fact A -> contradicts -> Fact B |
| SUPPORTS | Reinforcing information | Evidence -> supports -> Claim |

---

## 3.3 Search Architecture

Luna uses multiple search strategies that can be combined based on query characteristics.

### Current Implementation

```
                         QUERY
                           |
           +---------------+---------------+
           |               |               |
           v               v               v
    +-------------+  +-------------+  +-------------+
    |    LIKE     |  | sqlite-vec  |  |    GRAPH    |
    |             |  |             |  |             |
    |   Pattern   |  |  Semantic   |  |  Traversal  |
    |   matching  |  |   vectors   |  |   (BFS)     |
    |    ~10ms    |  |   ~10ms     |  |    ~5ms     |
    +------+------+  +------+------+  +------+------+
           |                |                |
           +--------+-------+--------+-------+
                    |
                    v
             RESULT MERGING
```

> **Implementation Note:** The Bible v2.1 specified FTS5 for keyword search. The actual implementation uses LIKE pattern matching with keyword extraction. This is simpler but lacks stemming/morphology support. FTS5 may be added in a future release.

### The sqlite-vec Advantage: Filtered Search

With sqlite-vec, filtering happens in the query itself:

```sql
-- Filter and search together
SELECT n.*, vec_distance_cosine(e.embedding, ?) as distance
FROM memory_embeddings e
JOIN memory_nodes n ON e.id = n.id
WHERE n.node_type = 'FACT'
  AND n.created_at > '2025-01-01'
ORDER BY distance
LIMIT 10;
```

**Result:** Faster filtered queries, fewer wasted comparisons.

### Reciprocal Rank Fusion (RRF)

When combining multiple search results, RRF merges by rank position (not raw scores):

```python
def reciprocal_rank_fusion(
    results_list: list[list[str]],
    k: int = 60
) -> list[str]:
    """
    Merge multiple ranked result lists using RRF.

    Args:
        results_list: List of ranked document ID lists
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

@dataclass
class MemoryNode:
    id: str
    node_type: str           # FACT, DECISION, PROBLEM, ACTION, CONTEXT
    content: str
    summary: Optional[str]
    source: Optional[str]
    confidence: float = 1.0
    importance: float = 0.5
    access_count: int = 0
    reinforcement_count: int = 0
    lock_in: float = 0.15
    lock_in_state: str = "drifting"
    metadata: dict = {}

class MemoryMatrix:
    """
    Unified memory store with hybrid search.
    Single file, all indexes unified.
    """

    async def search_nodes(
        self,
        query: str,
        node_types: Optional[list[str]] = None,
        limit: int = 10,
        use_embeddings: bool = True
    ) -> list[MemoryNode]:
        """
        Search memory nodes by content.

        - Extracts keywords from query
        - Searches compound phrases first
        - Falls back to individual terms
        - Optionally uses vector similarity
        """
        ...

    async def get_context(
        self,
        query: str,
        max_tokens: int = 2000
    ) -> list[MemoryNode]:
        """
        Get relevant context for a query.

        - Detects backward references ("what did we...")
        - Filters confusing/irrelevant nodes
        - Respects token budget
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

---

## 3.5 Query Routing

Not every query needs all search paths. Route based on query characteristics.

```python
class QueryRouter:
    def route(self, query: str) -> SearchPath:
        """Determine optimal search path."""

        entities = extract_entities(query)
        keyword_density = self._keyword_density(query)
        is_conceptual = self._is_conceptual(query)

        # Multiple entities - relationship query
        if entities and len(entities) >= 2:
            return SearchPath.GRAPH

        # High keyword density - pattern match
        if keyword_density > 0.6:
            return SearchPath.KEYWORD

        # Abstract/conceptual - semantic search
        if is_conceptual:
            return SearchPath.VECTOR

        # Default to hybrid
        return SearchPath.HYBRID
```

### Routing Examples

| Query | Signal | Path |
|-------|--------|------|
| "What did we decide about the runtime?" | Named entity + decision word | KEYWORD |
| "How does memory consolidation work?" | Conceptual question | VECTOR |
| "How are Alex and the Pi Project related?" | Multiple entities | GRAPH |
| "thoughts on sovereignty" | Vague, conceptual | VECTOR |
| "Luna architecture v2" | High keyword density | KEYWORD |

---

## 3.6 Vector Embeddings

### Supported Models

```python
EMBEDDING_DIMS = {
    "text-embedding-3-small": 1536,  # OpenAI (default)
    "text-embedding-3-large": 3072,
    "voyage-2": 1024,
    "local-minilm": 384,
}
```

### EmbeddingStore API

| Method | Purpose |
|--------|---------|
| `initialize()` | Load sqlite-vec extension, create virtual table |
| `store(node_id, embedding)` | Insert or replace embedding |
| `delete(node_id)` | Remove embedding |
| `search(query_embedding)` | KNN search with cosine similarity |
| `count()` | Total embeddings count |

### sqlite-vec Details

**Installation:**

```bash
pip install sqlite-vec
```

**Loading the Extension:**

```python
import sqlite3
import sqlite_vec

conn = sqlite3.connect("luna_engine.db")
conn.enable_load_extension(True)
sqlite_vec.load(conn)
conn.enable_load_extension(False)
```

**Vector Search Syntax:**

```sql
-- Basic similarity search
SELECT id, vec_distance_cosine(embedding, ?) as distance
FROM memory_embeddings
ORDER BY distance
LIMIT 10;
```

### Performance Notes

| Operation | sqlite-vec | Notes |
|-----------|------------|-------|
| Pure ANN (no filter) | ~5-10ms | Fast for <50K vectors |
| ANN + filter | ~5-10ms | No post-filtering needed |
| Insert (atomic) | ~1ms | Single transaction |
| Storage | Single file | No external dependencies |

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

---

## 3.8 Graph Operations

Graph traversal uses NetworkX for flexible algorithms.

### Implementation

```python
import networkx as nx

class MemoryGraph:
    def __init__(self):
        self.graph = nx.DiGraph()  # In-memory for fast traversal

    async def load_from_db(self, db):
        """Load graph from graph_edges table."""
        edges = await db.execute("SELECT from_id, to_id, relationship, strength FROM graph_edges")
        for row in edges:
            self.graph.add_edge(
                row["from_id"],
                row["to_id"],
                relationship=row["relationship"],
                strength=row["strength"]
            )

    def get_neighbors(self, node_id: str, depth: int = 2) -> set[str]:
        """BFS traversal to find connected nodes."""
        if node_id not in self.graph:
            return set()

        visited = set()
        current_level = {node_id}

        for _ in range(depth):
            next_level = set()
            for n in current_level:
                for neighbor in self.graph.neighbors(n):
                    if neighbor not in visited:
                        next_level.add(neighbor)
                        visited.add(neighbor)
            current_level = next_level

        return visited

    def spreading_activation(
        self,
        start_nodes: list[str],
        decay: float = 0.7,
        max_depth: int = 3
    ) -> dict[str, float]:
        """
        Compute relevance scores via spreading activation.

        Nodes closer to start_nodes get higher scores.
        Score decays exponentially with distance.
        """
        scores = {n: 1.0 for n in start_nodes}
        current = set(start_nodes)

        for depth in range(1, max_depth + 1):
            next_level = set()
            for node in current:
                for neighbor in self.graph.neighbors(node):
                    if neighbor not in scores:
                        edge_strength = self.graph[node][neighbor].get('strength', 1.0)
                        scores[neighbor] = scores[node] * decay * edge_strength
                        next_level.add(neighbor)

        return scores
```

### Relationship Types

```python
class RelationshipType(str, Enum):
    DEPENDS_ON = "DEPENDS_ON"
    RELATES_TO = "RELATES_TO"
    CAUSED_BY = "CAUSED_BY"
    FOLLOWED_BY = "FOLLOWED_BY"
    CONTRADICTS = "CONTRADICTS"
    SUPPORTS = "SUPPORTS"
```

---

## 3.9 Entity Resolution

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

## 3.10 Spreading Activation

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
                            from_id=other_eid,
                            to_id=neighbor,
                            relationship="RELATES_TO",
                            strength=similarity * 0.5,
                        )
```

**Example:**
1. You say: "Alex is joining the Pi Project"
2. Librarian files: Alex -> works_on -> Pi Project
3. Spreading activation finds: Sarah also works on Pi Project
4. Librarian infers: Alex -> likely_teammate -> Sarah (low confidence)
5. Next time you ask, Luna can say: "Should I introduce Alex to Sarah?"

---

## 3.11 Synaptic Pruning

Periodically clean low-value connections:

```python
async def prune_stale_edges(self):
    """Remove low-strength, old edges."""

    await self.conn.execute("""
        DELETE FROM graph_edges
        WHERE strength < 0.3
          AND created_at < datetime('now', '-30 days')
    """)
```

---

## 3.12 Entity System

Luna v2.0 includes a first-class entity system for tracking people, places, and projects.

### Entity Tables

```sql
-- Entities: First-class objects Luna knows about
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,              -- Slug: 'ahab', 'marzipan', 'ben-franklin'
    entity_type TEXT NOT NULL,        -- 'person' | 'persona' | 'place' | 'project'
    name TEXT NOT NULL,
    aliases TEXT,                     -- JSON array: ["Zayne", "Ahab"]
    core_facts TEXT,                  -- JSON blob (~500 tokens max)
    full_profile TEXT,                -- Markdown, can be lengthy
    voice_config TEXT,                -- JSON: tone, patterns, constraints (for personas)
    current_version INTEGER DEFAULT 1,
    metadata TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

-- Entity relationships: Graph of connections
CREATE TABLE IF NOT EXISTS entity_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_entity TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    to_entity TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relationship TEXT NOT NULL,       -- 'creator', 'friend', 'collaborator'
    strength REAL DEFAULT 0.5,
    bidirectional INTEGER DEFAULT 0,
    context TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now')),
    UNIQUE(from_entity, to_entity, relationship)
);

-- Entity versions: Append-only history
CREATE TABLE IF NOT EXISTS entity_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    core_facts TEXT,
    full_profile TEXT,
    voice_config TEXT,
    change_type TEXT NOT NULL,        -- 'create' | 'update' | 'rollback'
    change_summary TEXT,
    changed_by TEXT NOT NULL,         -- 'scribe' | 'librarian' | 'manual'
    change_source TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(entity_id, version)
);
```

---

## Summary

The Memory Matrix is Luna's soul - a single SQLite database that makes personal history queryable.

| Component | Purpose |
|-----------|---------|
| SQLite Core | Nodes, edges, metadata (WAL mode, 64MB cache) |
| sqlite-vec | Vector similarity search |
| LIKE patterns | Keyword search (FTS5 not implemented) |
| NetworkX | Graph traversal (in-memory) |
| Query Router | Optimal path selection |
| Entity System | People, places, projects with versioning |
| RRF Fusion | Merge multi-path results |
| Entity Resolution | Deduplicate "Mark" = "Zuck" |
| Spreading Activation | Infer hidden connections |
| Synaptic Pruning | Remove stale edges |

### Known Limitations (v2.2)

| Limitation | Impact | Status |
|------------|--------|--------|
| No FTS5 | Slower keyword search, no stemming | May implement in future |
| Tag siblings not implemented | 10% of lock-in weight missing | TODO |
| History compression queues exist but not activated | Manual archival only | Planned |

**Constitutional Principle:** Luna is a file. Copy it, Luna moves. Delete it, Luna dies. Everything in one place.

---

*Next Section: Part IV - The Scribe (Ben Franklin)*
