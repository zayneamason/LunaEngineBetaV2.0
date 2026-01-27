# Memory Economy Implementation - Swarm Coordinator

**Date:** January 27, 2026  
**Type:** Hive Swarm Configuration  
**Agents:** 6 parallel workers + 1 coordinator

---

## Swarm Overview

The Memory Economy implementation is split into 6 parallel workstreams that can be executed by Claude Flow's hive swarm. Each agent has:

1. **Clear boundaries** - What files to create/modify
2. **Explicit contracts** - What interfaces must be stable
3. **Dependencies** - What must complete before this can start
4. **Validation** - How to verify success

---

## Agent Assignments

| Agent | Name | Phase | Dependencies | Parallelizable |
|-------|------|-------|--------------|----------------|
| A1 | **Schema Agent** | Foundation | None | ✅ Yes (first) |
| A2 | **ClusterManager Agent** | Foundation | A1 | ✅ After A1 |
| A3 | **ClusteringEngine Agent** | Clustering | A1, A2 | ✅ After A1 |
| A4 | **Librarian Agent** | Retrieval | A1, A2 | ✅ After A1 |
| A5 | **LockIn Agent** | Dynamics | A1, A2 | ✅ After A1 |
| A6 | **Integration Agent** | Assembly | A2, A3, A4, A5 | ❌ Last |

---

## Execution Order

```
Phase 1 (Parallel-safe):
  A1: Schema Agent (creates tables)
      ↓
Phase 2 (Parallel after A1):
  A2: ClusterManager (CRUD) ─────┐
  A3: ClusteringEngine ──────────┼─→ Can run in parallel
  A4: Librarian Integration ─────┤
  A5: LockIn Dynamics ───────────┘
      ↓
Phase 3 (Sequential):
  A6: Integration Agent (wires everything together)
```

---

## Shared Contracts

### Database Schema (A1 creates, all agents depend on)

```sql
-- Tables: clusters, cluster_members, cluster_edges
-- See: 01-SCHEMA-AGENT.md for full DDL
```

### ClusterManager Interface (A2 creates, A3-A6 consume)

```python
class ClusterManager:
    def create_cluster(name, summary, centroid) -> str
    def add_member(cluster_id, node_id, strength) -> None
    def remove_member(cluster_id, node_id) -> None
    def get_cluster(cluster_id) -> Cluster
    def get_cluster_members(cluster_id) -> List[str]
    def update_lock_in(cluster_id, value) -> None
    def record_access(cluster_id) -> None
    def list_clusters(state?, min_lock_in?, limit) -> List[Cluster]
    def delete_cluster(cluster_id) -> None
```

### Cluster Dataclass (shared)

```python
@dataclass
class Cluster:
    cluster_id: str
    name: str
    summary: Optional[str]
    lock_in: float
    state: str  # drifting|fluid|settled|crystallized
    created_at: str
    updated_at: str
    last_accessed_at: Optional[str]
    access_count: int
    member_count: int
    avg_node_lock_in: float
    centroid_embedding: Optional[bytes]
```

---

## File Locations

```
src/luna/memory/
├── cluster_manager.py     (A2)
├── clustering_engine.py   (A3)
├── constellation.py       (A6)
├── lock_in.py             (A5)

src/luna/librarian/
├── librarian.py           (A4 - modify existing)

src/luna/services/
├── clustering_service.py  (A3)
├── lockin_service.py      (A5)

scripts/
├── migration_001_memory_economy.py  (A1)
├── test_clusters.py       (A2)

config/
├── memory_economy_config.json  (A6)
```

---

## Validation Sequence

After all agents complete:

```bash
# 1. Verify tables exist
sqlite3 data/luna_engine.db ".tables" | grep -E "clusters|cluster_members|cluster_edges"

# 2. Run manual cluster test
python scripts/test_clusters.py

# 3. Run clustering engine
python -c "from luna.memory.clustering_engine import ClusteringEngine; e = ClusteringEngine('data/luna_engine.db'); e.run_clustering()"

# 4. Verify clusters created
sqlite3 data/luna_engine.db "SELECT COUNT(*) FROM clusters"

# 5. Test retrieval
python -c "from luna.librarian.librarian import Librarian; l = Librarian('data/luna_engine.db'); print(l.hybrid_search_with_clusters('Luna memory'))"
```

---

## Rollback

If any agent fails:

```sql
-- Nuclear option: drop all Memory Economy tables
DROP TABLE IF EXISTS cluster_edges;
DROP TABLE IF EXISTS cluster_members;
DROP TABLE IF EXISTS clusters;
```

Existing Memory Matrix functionality remains unaffected.

---

## Agent Handoff Files

1. `01-SCHEMA-AGENT.md` - Database migration
2. `02-CLUSTER-MANAGER-AGENT.md` - CRUD operations  
3. `03-CLUSTERING-ENGINE-AGENT.md` - Background clustering
4. `04-LIBRARIAN-AGENT.md` - Retrieval integration
5. `05-LOCKIN-AGENT.md` - Lock-in dynamics
6. `06-INTEGRATION-AGENT.md` - Final wiring

Each file is self-contained with full implementation code.

---

## Swarm YAML

See `memory-economy-swarm.yaml` for Claude Flow configuration.
