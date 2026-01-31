# Luna Engine v2.0 Memory Substrate Audit

**Audit Date:** January 25, 2026
**Auditor:** Phase 1 Substrate Agent
**Scope:** Complete audit of memory substrate layer

---

## Executive Summary

**Overall Status:** 85% Complete

The Luna Engine v2.0 substrate implementation is fundamentally sound with excellent architectural decisions but some important discrepancies between documented claims and actual implementation.

| Component | LOC | Status | Completeness |
|-----------|-----|--------|--------------|
| database.py | 233 | ✅ Complete | 100% |
| embeddings.py | 356 | ✅ Implemented | 90% |
| graph.py | 503 | ✅ Implemented | 95% |
| lock_in.py | 286 | ⚠️ Partial | 90% |
| memory.py | 1036 | ✅ Implemented | 95% |
| schema.sql | 290 | ✅ Complete | 95% |
| **Total** | **2866** | **85% Complete** | **93% avg** |

---

## 1. Database Layer (database.py)

### Status: ✅ FULLY IMPLEMENTED

**Key Features:**
- Async SQLite via `aiosqlite` for concurrent access
- WAL (Write-Ahead Logging) mode enabled
- 64MB cache size configured
- Foreign key constraints enabled
- Graceful WAL checkpoint on shutdown

**Configuration:**
```python
db_path = {project_root}/data/luna_engine.db
PRAGMA journal_mode = WAL
PRAGMA foreign_keys = ON
PRAGMA cache_size = -64000  # 64MB
```

**Critical Fix Applied:**
- Database location moved from `~/.luna/` to project `/data/` directory
- This resolved memory wipe issue documented in HANDOFF-MEMORY-WIPE-INVESTIGATION.md

---

## 2. Schema Structure (schema.sql)

### Core Tables

**Memory Nodes Table (PRIMARY)**
```sql
CREATE TABLE memory_nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,          -- FACT, DECISION, PROBLEM, ACTION, CONTEXT
    content TEXT NOT NULL,
    summary TEXT,
    source TEXT,
    confidence REAL DEFAULT 1.0,      -- 0-1 score
    importance REAL DEFAULT 0.5,      -- 0-1 score
    access_count INTEGER DEFAULT 0,   -- For lock-in tracking
    reinforcement_count INTEGER DEFAULT 0,
    lock_in REAL DEFAULT 0.15,        -- 0.15-0.85 coefficient
    lock_in_state TEXT DEFAULT 'drifting',
    last_accessed TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata TEXT                     -- JSON blob
);
```

**Conversation Turns Table**
```sql
CREATE TABLE conversation_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,              -- user|assistant|system
    content TEXT NOT NULL,
    tokens INTEGER,
    tier TEXT DEFAULT 'active',      -- active|recent|archive
    compressed TEXT,
    compressed_at REAL,
    archived_at REAL,
    context_refs TEXT
);
```

**Graph Edges Table**
```sql
CREATE TABLE graph_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id TEXT NOT NULL REFERENCES memory_nodes(id),
    to_id TEXT NOT NULL REFERENCES memory_nodes(id),
    relationship TEXT NOT NULL,
    strength REAL DEFAULT 1.0,
    UNIQUE(from_id, to_id, relationship)
);
```

**Entity System Tables**
- `entities` - People, personas, places, projects
- `entity_relationships` - Graph of connections
- `entity_mentions` - Links entities to Memory Matrix nodes
- `entity_versions` - Append-only history of profile changes

### Index Strategy

**Total Indexes:** 20 strategic indexes

| Category | Indexes | Purpose |
|----------|---------|---------|
| Node | 6 | Filter by type, temporal, importance, lock-in |
| Conversation | 4 | Session, temporal, tier filtering |
| Graph | 3 | Edge traversal (from, to, relationship) |
| Entity | 5 | Type, name, relationship traversal |
| System | 2 | Queue operations |

---

## 3. Vector Embeddings (embeddings.py)

### Status: ✅ IMPLEMENTED (90%)

**Model Support:**
```python
EMBEDDING_DIMS = {
    "text-embedding-3-small": 1536,     # OpenAI (default)
    "text-embedding-3-large": 3072,
    "voyage-2": 1024,
    "local-minilm": 384,
}
```

**EmbeddingStore API:**
| Method | Purpose |
|--------|---------|
| `initialize()` | Load sqlite-vec extension, create table |
| `store(node_id, embedding)` | Insert or replace embedding |
| `delete(node_id)` | Remove embedding |
| `search(query_embedding)` | KNN search with cosine similarity |
| `count()` | Total embeddings count |

**Similarity Metric:**
- `vec_distance_cosine()` (sqlite-vec built-in)
- Converts distance to similarity: `1 - distance`

### Gap: No Embedding Backup
- Embeddings stored only in virtual table
- No backup in regular embeddings table

---

## 4. Graph Layer (graph.py)

### Status: ✅ IMPLEMENTED (95%)

**Architecture:** Hybrid approach
- **In-Memory:** NetworkX DiGraph for fast traversal (O(1) neighbor lookup)
- **Persistent:** SQLite `graph_edges` table for durability

**Relationship Types:**
```python
class RelationshipType(str, Enum):
    DEPENDS_ON = "DEPENDS_ON"
    RELATES_TO = "RELATES_TO"
    CAUSED_BY = "CAUSED_BY"
    FOLLOWED_BY = "FOLLOWED_BY"
    CONTRADICTS = "CONTRADICTS"
    SUPPORTS = "SUPPORTS"
```

**MemoryGraph API:**
| Method | Purpose |
|--------|---------|
| `load_from_db()` | Load all edges into NetworkX at startup |
| `add_edge(from_id, to_id, relationship, strength)` | Add relationship |
| `get_neighbors(node_id, depth)` | BFS traversal |
| `spreading_activation(start_nodes, decay, max_depth)` | Relevance scoring |
| `get_stats()` | Node/edge counts, connectivity |

---

## 5. Lock-In Coefficient (lock_in.py)

### Status: ⚠️ PARTIAL (90%)

**Lock-In States:**
```python
class LockInState(str, Enum):
    DRIFTING = "drifting"    # L < 0.30 - rarely accessed, may fade
    FLUID = "fluid"          # 0.30 <= L < 0.70 - active but not settled
    SETTLED = "settled"      # L >= 0.70 - core knowledge, persistent
```

**Weighted Factors:**
```python
DEFAULT_WEIGHTS = {
    "retrieval": 0.4,       # How often accessed (heaviest)
    "reinforcement": 0.3,   # Explicit "important" marks
    "network": 0.2,         # Connected to settled nodes
    "tag_siblings": 0.1     # Shares tags with settled nodes
}
```

**Sigmoid Transform:**
```python
raw_sigmoid = sigmoid(activity)
lock_in = 0.15 + (0.85 - 0.15) * raw_sigmoid
# Result: 0.15 to 0.85 (never fully 0 or 1)
```

### Gap: Tag Siblings Not Implemented

**Lines 273-274 in lock_in.py:**
```python
# TODO: Implement tag sibling counting
locked_tag_sibling_count = 0
```

**Impact:** 10% of lock-in calculation weight missing

---

## 6. Memory Matrix Operations (memory.py)

### Status: ✅ IMPLEMENTED (95%)

**MemoryNode Data Class:**
```python
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
```

**MemoryMatrix API:**
| Category | Methods |
|----------|---------|
| Node Operations | `add_node()`, `get_node()`, `update_node()`, `delete_node()` |
| Search | `search_nodes()`, `get_context()`, `get_nodes_by_type()` |
| Conversation | `add_conversation_turn()`, `get_recent_turns()`, `get_session_history()` |
| Access Tracking | `record_access()`, `reinforce_node()`, `get_most_accessed()` |
| Lock-In Filtering | `get_nodes_by_lock_in_state()`, `get_drifting_nodes()`, `get_settled_nodes()` |

**get_context() Deep Dive:**
1. Detects backward references ("what did we...", "remember when...")
2. Extracts meaningful keywords (skip stopwords, 3+ chars)
3. Searches for compound phrases first
4. Filters out confusing identity nodes, system prompts, raw logs
5. Respects token budget

---

## 7. Bible vs. Implementation Discrepancies

### Critical Discrepancy #1: FTS5 Not Implemented

**Bible Part III Claims:**
```sql
CREATE VIRTUAL TABLE nodes_fts USING fts5(
    id, content, node_type,
    content='nodes',
    tokenize='porter'
);
```

**Actual Implementation:**
- Uses `LIKE` pattern matching for search
- No FTS5 virtual table in schema.sql

**Impact:**
- Search is slower (full table scan vs. indexed FTS5)
- No stemming/morphology (porter tokenizer)
- No ranking by relevance match quality

### Critical Discrepancy #2: Table Names

| Bible | Implementation |
|-------|----------------|
| `nodes` | `memory_nodes` |
| `edges` | `graph_edges` |
| `vec_index` | `memory_embeddings` (virtual) |

**Root Cause:** Bible Part III was aspirational spec from January 7, 2026. Implementation evolved with more specific naming.

### Critical Discrepancy #3: Tag Siblings Not Implemented

**Lock-in Algorithm Claims:**
- 4 factors affect lock-in coefficient
- 10% weight on `locked_tag_sibling_count`

**Actual:** `locked_tag_sibling_count = 0` (TODO)

---

## 8. Strengths

1. **Hybrid Persistence:** NetworkX in-memory + SQLite persistent
2. **WAL Mode:** Proper concurrent access handling
3. **Spreading Activation:** Sophisticated context retrieval via graph traversal
4. **Lock-In Coefficient:** Sigmoid-based memory decay (mathematically sound)
5. **Three-Tier History:** Active → Recent → Archive design
6. **Entity System:** First-class person/persona/place/project support
7. **Consciousness Snapshots:** Periodic state saves

---

## 9. Gaps & Recommendations

| Gap | Severity | Impact | Fix Complexity |
|-----|----------|--------|----------------|
| No FTS5 search | Medium | Slower search, no stemming | High - requires triggers |
| Tag siblings not impl. | Medium | 10% lock-in weight missing | Medium |
| No embedding backup | Low | Loss if sqlite-vec fails | Low |
| History compression unimpl. | Medium | Queues exist but not activated | High |

### Immediate Priority

1. **Implement FTS5** - Add `nodes_fts` virtual table with triggers
2. **Tag System** - Create `tags` and `node_tags` tables
3. **Verify sqlite-vec** - Test extension loads in production

### Testing Needed

- Schema.sql migrations (repeated runs?)
- sqlite-vec extension availability
- Spreading activation performance (depth=3 on large graphs)
- Lock-in coefficient validation

---

**End of Substrate Audit**
