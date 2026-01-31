# AUDIT-MEMORY.md

**Generated:** 2026-01-30
**Agent:** Memory Substrate Auditor
**Phase:** 1.3

## Summary

| Metric | Value |
|--------|-------|
| Tables defined in schema.sql | 15 (including virtual tables) |
| Vector dimensions | 384 (local MiniLM) / 1536 (OpenAI fallback) |
| Memory operations in MemoryMatrix | 25+ methods |
| Lock-in states | 3 (drifting, fluid, settled) + 1 cluster-level (crystallized) |
| FTS5 status | Implemented with triggers |
| Embedding provider | local-minilm (default), OpenAI (optional) |

---

## Schema Verification

### Tables Defined in schema.sql

| Table | Purpose | Used In Code |
|-------|---------|--------------|
| `memory_nodes` | Core memory storage | MemoryMatrix.add_node(), get_node(), etc. |
| `conversation_turns` | Chat history | MemoryMatrix.add_conversation_turn() |
| `graph_edges` | Node relationships | MemoryGraph.add_edge(), load_from_db() |
| `consciousness_snapshots` | State persistence | Not actively used in current code |
| `sessions` | Session tracking | Defined but not actively used |
| `compression_queue` | Background compression | Defined, not implemented |
| `extraction_queue` | Archive processing | Defined, not implemented |
| `history_embeddings` | Semantic search on history | Defined, not implemented |
| `memory_nodes_fts` (FTS5) | Full-text search | MemoryMatrix.fts5_search() |
| `entities` | First-class entity tracking | EntityResolver (if exists) |
| `entity_relationships` | Entity graph | Referenced in _link_entity_mentions() |
| `entity_mentions` | Entity-node links | Referenced in _link_entity_mentions() |
| `entity_versions` | Entity change history | Defined, not actively used |
| `tuning_sessions` | Parameter tuning | Defined, not actively used |
| `tuning_iterations` | Tuning experiments | Defined, not actively used |

### Memory Economy Tables (cluster_manager.py)

These are created dynamically by ClusterManager, not in schema.sql:

| Table | Purpose |
|-------|---------|
| `clusters` | Semantic groupings |
| `cluster_members` | Node-to-cluster mappings |
| `cluster_edges` | Inter-cluster relationships |

**Gap:** Memory Economy tables are not in schema.sql but are auto-created by ClusterManager.

### Schema Column Verification

`memory_nodes` columns match code usage:
- `id`, `node_type`, `content`, `summary`, `source` - Used in add_node()
- `confidence`, `importance` - Used in add_node(), get_context()
- `access_count`, `reinforcement_count` - Used in record_access(), reinforce_node()
- `lock_in`, `lock_in_state` - Used in record_access(), get_nodes_by_lock_in_state()
- `last_accessed`, `created_at`, `updated_at`, `metadata` - All used correctly

---

## Vector Search Implementation

### Architecture

1. **EmbeddingStore** (`substrate/embeddings.py`)
   - Wraps sqlite-vec virtual table
   - Supports configurable dimensions (DEFAULT_DIM = 384)
   - Graceful fallback when sqlite-vec unavailable

2. **EmbeddingGenerator** (`substrate/embeddings.py`)
   - Default model: `local-minilm` (384 dims)
   - Optional: OpenAI `text-embedding-3-small` (1536 dims)

3. **LocalEmbeddings** (`substrate/local_embeddings.py`)
   - Uses `all-MiniLM-L6-v2` from sentence-transformers
   - Thread-safe singleton pattern
   - Lazy model loading

### Vector Table Creation

```sql
-- Created dynamically by EmbeddingStore.initialize()
CREATE VIRTUAL TABLE IF NOT EXISTS memory_embeddings_local USING vec0(
    node_id TEXT PRIMARY KEY,
    embedding FLOAT[384]
)
```

### Embedding Flow

1. `MemoryMatrix.add_node()` calls `_store_embedding()`
2. `_ensure_embedding_components()` lazily initializes store + generator
3. `EmbeddingGenerator.generate()` creates embedding via local MiniLM
4. `EmbeddingStore.store()` converts to blob and inserts

### Search Implementation

```python
# semantic_search() flow:
query_embedding = await self._embedding_generator.generate(query)
similar = await self._embedding_store.search(query_embedding, limit, min_similarity)
# search() uses vec_distance_cosine for similarity
```

---

## Memory Operations API

### Core CRUD

| Method | Description |
|--------|-------------|
| `add_node()` | Create memory node with auto-embedding |
| `get_node()` | Retrieve by ID |
| `update_node()` | Partial update |
| `delete_node()` | Remove node |

### Search Operations

| Method | Description |
|--------|-------------|
| `search_nodes()` | LIKE-based text search |
| `fts5_search()` | Full-text search with Porter stemmer |
| `semantic_search()` | Vector similarity search |
| `hybrid_search()` | RRF fusion of FTS5 + semantic |
| `get_context()` | Token-budgeted context retrieval |

### Access Tracking

| Method | Description |
|--------|-------------|
| `record_access()` | Increment access_count, update lock-in |
| `reinforce_node()` | Explicit reinforcement, recalculate lock-in |
| `get_most_accessed()` | Top accessed nodes |

### Conversation Operations

| Method | Description |
|--------|-------------|
| `add_conversation_turn()` | Store turn |
| `get_recent_turns()` | Session history (reverse chrono) |
| `get_session_history()` | Full session |

---

## Lock-In Coefficient

### Two Implementations

**1. Node-Level (`substrate/lock_in.py`)**

Formula:
```python
activity = (
    retrieval_count * 0.4 +
    reinforcement_count * 0.3 +
    locked_neighbor_count * 0.2 +
    locked_tag_sibling_count * 0.1
) / 10.0

lock_in = LOCK_IN_MIN + (LOCK_IN_MAX - LOCK_IN_MIN) * sigmoid(activity)
# Bounds: [0.15, 0.85]
```

State Classification:
- `drifting`: L < 0.30
- `fluid`: 0.30 <= L < 0.70
- `settled`: L >= 0.70

**2. Cluster-Level (`memory/lock_in.py`)**

Formula:
```python
lock_in = (
    0.40 * weighted_node_strength +    # Member lock-ins
    0.30 * log_access_factor +          # log(access+1)/log(11)
    0.20 * avg_edge_strength +          # Connected edges
    0.10 * age_factor                   # 1/(1+days/30)
) * decay_factor                        # exp(-lambda * seconds)
```

State Classification (different thresholds!):
- `drifting`: L < 0.20
- `fluid`: 0.20 <= L < 0.70
- `settled`: 0.70 <= L < 0.85
- `crystallized`: L >= 0.85

**Gap:** Two different threshold systems exist. Node-level uses 0.30/0.70, cluster-level uses 0.20/0.70/0.85.

### Decay Rates (Cluster-Level)

| State | Lambda | Half-Life |
|-------|--------|-----------|
| crystallized | 0.00001 | ~11.5 days |
| settled | 0.0001 | ~1.15 days |
| fluid | 0.001 | ~2.8 hours |
| drifting | 0.01 | ~17 minutes |

---

## Query Performance Notes

### Potential N+1 Pattern

**Location:** `substrate/memory.py:709-717`

```python
# In semantic_search():
for node_id, similarity in similar:
    node = await self.get_node(node_id)  # <-- Individual query per result
    if node is None:
        continue
    if node_type and node.node_type != node_type:
        continue
    results.append((node, similarity))
```

**Recommendation:** Fetch nodes in batch using `WHERE id IN (?, ?, ...)` instead of individual queries.

### Other Query Patterns

1. **get_context()** - Multiple queries but bounded (compound + keyword search)
2. **hybrid_search()** - Runs two searches sequentially (FTS5 + semantic)
3. **record_access()** - Two queries: UPDATE + SELECT + UPDATE

### Index Coverage

Good index coverage in schema.sql:
- `idx_nodes_type`, `idx_nodes_created`, `idx_nodes_importance`
- `idx_nodes_accessed`, `idx_nodes_lock_in`, `idx_nodes_lock_in_state`
- `idx_turns_session`, `idx_turns_tier_timestamp`
- `idx_edges_from`, `idx_edges_to`, `idx_edges_relationship`

---

## Memory Economy Status

### Implementation Status: Implemented

The Memory Economy is fully implemented with the following components:

1. **ClusterManager** (`memory/cluster_manager.py`)
   - CRUD operations for clusters
   - Member management
   - Edge management
   - Statistics

2. **ClusteringEngine** (`memory/clustering_engine.py`)
   - Keyword-based clustering (MVP strategy)
   - Jaccard similarity for grouping
   - Centroid calculation (with NumPy)

3. **LockInCalculator** (`memory/lock_in.py`)
   - Logarithmic access boost
   - State-dependent decay
   - Batch update capability

4. **ConstellationAssembler** (`memory/constellation.py`)
   - Token-budgeted context assembly
   - Cluster/node prioritization
   - Director-ready formatting

5. **ConversationRing** (`memory/ring.py`)
   - Fixed-size ring buffer
   - FIFO eviction
   - Entity mention detection

### Configuration

`config/memory_economy_config.json` provides:
- Threshold configuration
- Decay rates
- Service intervals
- Clustering parameters
- Retrieval limits

---

## FTS5 Status

### Status: Fully Implemented

**Virtual Table:**
```sql
CREATE VIRTUAL TABLE IF NOT EXISTS memory_nodes_fts USING fts5(
    content,
    summary,
    content='memory_nodes',
    content_rowid='rowid',
    tokenize='porter unicode61'
);
```

**Sync Triggers:**
- `memory_nodes_fts_insert` - On INSERT
- `memory_nodes_fts_update` - On UPDATE of content/summary
- `memory_nodes_fts_delete` - On DELETE

**Usage:**
```python
# MemoryMatrix.fts5_search() checks for table existence
# Falls back to LIKE search if FTS5 unavailable
fts_exists = await self.db.fetchone("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name='memory_nodes_fts'
""")
```

---

## Clustering Engine State

### Current Strategy: Keyword-Based Clustering

**Algorithm:**
1. Extract keywords from all memory nodes
2. Build inverted index (keyword -> node_ids)
3. Calculate Jaccard similarity between nodes
4. Form clusters from nodes with >= 40% keyword overlap
5. Skip keywords appearing in > 100 nodes (too generic)

**Parameters:**
- `similarity_threshold`: 0.82
- `min_cluster_size`: 3
- `max_cluster_size`: 50
- `min_keyword_overlap`: 0.4
- `max_generic_frequency`: 100

**Stopword List:** ~120 common words excluded

### Centroid Calculation

When NumPy is available:
```python
embeddings = []
for node_id in node_ids:
    # Fetch embedding from memory_nodes
    ...
centroid = np.mean(embeddings, axis=0)
```

**Note:** Looks for `embedding` column in `memory_nodes`, which doesn't exist in schema. The actual embeddings are in `memory_embeddings_local` (vec0 table).

---

## Implementation Gaps

### 1. Unused Schema Tables

| Table | Status |
|-------|--------|
| `consciousness_snapshots` | Defined, not used |
| `sessions` | Defined, not used |
| `compression_queue` | Defined, not implemented |
| `extraction_queue` | Defined, not implemented |
| `history_embeddings` | Defined, not implemented |
| `tuning_sessions` | Defined, not used |
| `tuning_iterations` | Defined, not used |

### 2. Lock-In Threshold Mismatch

- **Node-level:** drifting < 0.30, settled >= 0.70
- **Cluster-level:** drifting < 0.20, crystallized >= 0.85

These should be harmonized for consistency.

### 3. Centroid Calculation Bug

`ClusteringEngine._calculate_centroid()` looks for `embedding` column in `memory_nodes`, but embeddings are stored in `memory_embeddings_local` vec0 table.

### 4. Network Effects Incomplete

In `substrate/lock_in.py:compute_lock_in_for_node()`:
```python
# TODO: Add network effects (locked neighbors) when graph is wired
locked_neighbor_count = 0  # Always 0 currently
```

### 5. Tag Siblings Not Implemented

```python
# TODO: Implement tag sibling counting
locked_tag_sibling_count = 0  # Always 0
```

### 6. EntityResolver Import Failure Silent

```python
try:
    from ..entities.resolution import EntityResolver
except ImportError as e:
    logger.warning(f"Could not import EntityResolver: {e}")
    return None  # Silently fails
```

### 7. Memory Economy Tables Not in schema.sql

ClusterManager creates its own tables dynamically, leading to schema fragmentation.

---

## Recommendations

1. **Fix N+1 Query:** Batch-fetch nodes in `semantic_search()`
2. **Harmonize Lock-In Thresholds:** Align node and cluster thresholds
3. **Fix Centroid Calculation:** Query `memory_embeddings_local` instead of `memory_nodes.embedding`
4. **Implement Network Effects:** Wire up `locked_neighbor_count` calculation
5. **Consolidate Schema:** Move Memory Economy tables to schema.sql
6. **Clean Unused Tables:** Remove or implement compression/extraction queues
7. **Add Batch Operations:** Create `add_nodes_batch()` for bulk imports
