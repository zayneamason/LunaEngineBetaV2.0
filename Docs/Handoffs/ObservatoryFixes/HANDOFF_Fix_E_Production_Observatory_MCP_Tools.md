# HANDOFF: Fix E — Production Observatory MCP Tools
## Priority: P1 (Replace sandbox, unblock deregistration)
## Estimated Effort: 3-4 hours
## Owner: CC (Claude Code)
## Dependencies: None (can ship independently of Fix A-D)

---

## Problem

The Observatory-Sandbox MCP server (`Tools/MemoryMatrix_SandBox/`) provides useful
diagnostic and management tools, but they operate on a disposable `sandbox_matrix.db`
instead of production. Meanwhile, Luna-Hub MCP has basic memory tools but lacks:

- Retrieval pipeline diagnostics (search method comparison, activation trace)
- Graph statistics and visualization dumps
- Retrieval parameter tuning
- Entity management CRUD
- Maintenance sweeps and quest generation
- Full graph snapshots for the Observatory frontend

**Goal:** Add production Observatory tools to the Luna-Hub MCP server. Then deregister
the sandbox MCP entirely.

---

## Architecture Decision

**Add tools to existing Luna-Hub MCP** (`src/luna_mcp/server.py`), not a new server.

Rationale:
- Luna-Hub already has the engine reference and database connection
- One MCP server = one process = simpler ops
- Tools can reuse MemoryMatrix, MemoryGraph, EntityResolver directly
- No second database connection competing for WAL locks

**Namespace:** All new tools prefixed `observatory_` to distinguish from existing
`memory_matrix_*` and `luna_*` tools.

---

## Tool Spec: 8 New Tools

### 1. `observatory_stats`
**Replaces:** `sandbox_stats`
**Purpose:** Database health overview for the Observatory dashboard

```python
@mcp.tool()
async def observatory_stats() -> dict:
    """
    Get Memory Matrix statistics: node/edge/cluster counts,
    type and lock-in distributions.
    """
```

**Returns:**
```json
{
  "nodes": {"total": 52341, "by_type": {"FACT": 31200, "DECISION": 4100, ...}},
  "edges": {"total": 18700, "by_type": {"MENTIONS": 8200, "related_to": 3100, ...}},
  "clusters": {"total": 142, "avg_size": 12.3},
  "entities": {"total": 41, "by_type": {"person": 12, "project": 8, ...}},
  "mentions": {"total": 4200, "by_type": {"subject": 320, "focus": 580, "reference": 3300}},
  "lock_in": {"avg": 0.42, "drifting": 1200, "anchored": 8400, "locked": 2100},
  "db_size_mb": 48.2
}
```

**Implementation:** Query the MatrixActor's database directly:
```python
matrix_actor = engine.get_actor("matrix")
matrix = matrix_actor._matrix
db = matrix_actor._db

# Node counts by type
rows = await db.fetchall("SELECT node_type, COUNT(*) FROM memory_nodes GROUP BY node_type")
# Edge counts by type  
rows = await db.fetchall(
    "SELECT relationship, COUNT(*) FROM (SELECT relationship FROM ...graph edges...) GROUP BY relationship"
)
# etc.
```

---

### 2. `observatory_graph_dump`
**Replaces:** `sandbox_graph_dump`
**Purpose:** Full graph snapshot for frontend force-directed visualization

```python
@mcp.tool()
async def observatory_graph_dump(limit: int = 500, min_lock_in: float = 0.0) -> dict:
    """
    Full graph snapshot (nodes, edges, clusters) for visualization.
    Filters by lock-in threshold to reduce noise.
    """
```

**Returns:**
```json
{
  "nodes": [
    {"id": "abc123", "type": "FACT", "content": "...", "lock_in": 0.72, "cluster_id": "c_05", ...},
    ...
  ],
  "edges": [
    {"from": "abc123", "to": "def456", "relationship": "MENTIONS", "strength": 0.8},
    ...
  ],
  "clusters": [
    {"id": "c_05", "label": "Memory Architecture", "size": 14},
    ...
  ],
  "truncated": false,
  "total_nodes": 52341,
  "returned_nodes": 500
}
```

**Implementation:** Read from MemoryGraph's NetworkX graph:
```python
graph = matrix_actor._graph
G = graph._graph  # networkx.DiGraph

nodes = []
for node_id, data in G.nodes(data=True):
    lock_in = data.get("lock_in", 0.0)
    if lock_in < min_lock_in:
        continue
    nodes.append({...})
    if len(nodes) >= limit:
        break

edges = [
    {"from": u, "to": v, "relationship": d.get("relationship"), "strength": d.get("strength", 1.0)}
    for u, v, d in G.edges(data=True)
    if u in node_ids_set and v in node_ids_set  # Only edges between returned nodes
]
```

---

### 3. `observatory_search`
**Replaces:** `sandbox_search`
**Enhances:** `memory_matrix_search` (which only does basic text search)
**Purpose:** Multi-method search with method comparison

```python
@mcp.tool()
async def observatory_search(query: str, method: str = "hybrid") -> dict:
    """
    Search production Memory Matrix. 
    Methods: fts5, vector, hybrid, all.
    
    'all' runs all three and returns results side-by-side for comparison.
    """
```

**Implementation:** Reuse the search modules from the sandbox. They're pure functions
that take a database connection — just point them at production instead of sandbox DB.

Key files to port (or import):
- `Tools/MemoryMatrix_SandBox/mcp_server/search.py` → `src/luna_mcp/observatory/search.py`
- `Tools/MemoryMatrix_SandBox/mcp_server/activation.py` → reuse or import
- `Tools/MemoryMatrix_SandBox/mcp_server/clusters.py` → reuse or import

These modules are stateless — they take a matrix/db reference and return results.
Porting is mostly changing the import path.

---

### 4. `observatory_replay`
**Replaces:** `sandbox_replay`  
**Purpose:** Full pipeline trace with phase-by-phase timing. The Observatory's
most diagnostic tool — shows exactly how retrieval works.

```python
@mcp.tool()
async def observatory_replay(query: str) -> dict:
    """
    Full retrieval pipeline with detailed trace of every phase:
    FTS5 → Vector → Fusion → Activation → Assembly.
    
    Shows timing, result counts, and top results at each phase.
    Use this to debug why a query returns unexpected results.
    """
```

**Returns:** Same structure as `sandbox_replay` — array of phase objects with
`elapsed_ms`, `result_count`, `results[]`.

**Implementation:** Direct port of `tool_sandbox_replay` from sandbox tools,
pointed at production matrix.

---

### 5. `observatory_tune`
**Replaces:** `sandbox_tune`
**Purpose:** Live adjustment of retrieval parameters

```python
@mcp.tool()
async def observatory_tune(param: str, value: float) -> dict:
    """
    Adjust a retrieval parameter. Persists to observatory_config.json.
    
    Parameters: decay, min_activation, max_hops, token_budget,
    sim_threshold, fts5_limit, vector_limit, rrf_k,
    lock_in_node_weight, lock_in_access_weight,
    lock_in_edge_weight, lock_in_age_weight,
    cluster_sim_threshold
    """
```

**Implementation:** Port `RetrievalParams` from sandbox config.
Change persist path from `sandbox_config.json` to `data/observatory_config.json`.

---

### 6. `observatory_entities`
**New — no direct sandbox equivalent**
**Purpose:** Entity listing and detail view for MCP-side inspection

```python
@mcp.tool()
async def observatory_entities(
    entity_id: str = "",
    entity_type: str = "",
    limit: int = 20,
) -> dict:
    """
    List or inspect entities in the Memory Matrix.
    
    - No args: list all entities with mention counts
    - entity_id: get full detail for one entity (facts, mentions, relationships)
    - entity_type: filter by type (person, project, place, persona)
    """
```

**Implementation:** Use EntityResolver from production engine:
```python
resolver = matrix._entity_resolver or EntityResolver(db)

if entity_id:
    entity = await resolver.get_entity(entity_id)
    mentions = await resolver.get_entity_mentions(entity_id)
    relationships = await resolver.get_entity_relationships(entity_id)
    return {"entity": entity, "mentions": mentions, "relationships": relationships}
else:
    entities = await resolver.list_entities(entity_type=entity_type, limit=limit)
    return {"entities": entities, "count": len(entities)}
```

---

### 7. `observatory_maintenance_sweep`
**Replaces:** `sandbox_maintenance_sweep`
**Purpose:** Graph health analysis → quest candidate generation

```python
@mcp.tool()
async def observatory_maintenance_sweep() -> dict:
    """
    Run maintenance sweep on production graph.
    Identifies: orphan entities, stale entities, fragmented profiles,
    contradicting decisions, drifting clusters, unreflected sessions.
    
    Returns quest candidates (does NOT auto-create quests).
    """
```

**Change from sandbox:** Returns candidates only, does NOT auto-create quests.
Let the human (or Luna) decide which quests to accept. Safer for production.

**Implementation:** Port `maintenance.py` from sandbox, point at production DB.

---

### 8. `observatory_quest_board`
**Replaces:** `sandbox_quest_*` (accept, complete, list)
**Purpose:** Unified quest management

```python
@mcp.tool()
async def observatory_quest_board(
    action: str = "list",
    quest_id: str = "",
    journal_text: str = "",
    status: str = "",
    quest_type: str = "",
) -> dict:
    """
    Quest board management.
    
    Actions:
    - list: Show quests (filter by status/type)
    - accept: Accept a quest (quest_id required)
    - complete: Complete a quest (quest_id required, journal_text optional)
    - create: Create quest from maintenance sweep candidates
    """
```

**Rationale for single tool:** The sandbox had 3 separate quest tools. For production,
a single tool with an action parameter is cleaner — fewer tools in the MCP list,
same functionality.

---

## File Structure

```
src/luna_mcp/
├── server.py                    # Add 8 new @mcp.tool() registrations
├── observatory/                 # NEW directory
│   ├── __init__.py
│   ├── tools.py                 # Tool implementations
│   ├── search.py                # Ported from sandbox (FTS5, vector, hybrid)
│   ├── activation.py            # Ported from sandbox (spreading activation)
│   ├── clusters.py              # Ported from sandbox (constellation assembly)
│   ├── config.py                # RetrievalParams (ported, new persist path)
│   └── maintenance.py           # Ported from sandbox (graph health checks)
```

### What to port from sandbox:

| Sandbox File | → Production File | Changes |
|---|---|---|
| `mcp_server/search.py` | `observatory/search.py` | Change DB reference from SandboxMatrix to production MemoryDatabase |
| `mcp_server/activation.py` | `observatory/activation.py` | Same — swap matrix reference |
| `mcp_server/clusters.py` | `observatory/clusters.py` | Same |
| `mcp_server/config.py` | `observatory/config.py` | Change persist path to `data/observatory_config.json` |
| `mcp_server/maintenance.py` | `observatory/maintenance.py` | Same — swap matrix reference |
| `mcp_server/lock_in.py` | `observatory/lock_in.py` | If needed by activation/clusters |

The sandbox modules are well-factored — they take a matrix object and return data.
Porting is primarily about changing the matrix type from `SandboxMatrix` to production
`MemoryMatrix`/`MemoryDatabase`. The core algorithms don't change.

---

## Tools NOT Ported (and why)

| Sandbox Tool | Decision | Reason |
|---|---|---|
| `sandbox_reset` | **DROP** | Never reset production |
| `sandbox_seed` | **DROP** | No test data in production |
| `sandbox_import` | **DROP** | Sandbox-specific import format |
| `sandbox_add_node` | **SKIP** | Already exists as `memory_matrix_add_node` |
| `sandbox_add_edge` | **SKIP** | Already exists as `memory_matrix_add_edge` |
| `sandbox_add_entity` | **SKIP** | Scribe/Librarian handle entity creation through extraction |
| `sandbox_add_entity_relationship` | **SKIP** | Librarian handles through extraction wiring |
| `sandbox_link_mention` | **SKIP** | Fix B's `_link_entity_mentions` handles automatically |

---

## Integration with server.py

In `src/luna_mcp/server.py`, add after the existing memory_matrix tools:

```python
# ==============================================================================
# Observatory Tools (production diagnostics)
# ==============================================================================

from luna_mcp.observatory.tools import (
    tool_observatory_stats,
    tool_observatory_graph_dump,
    tool_observatory_search,
    tool_observatory_replay,
    tool_observatory_tune,
    tool_observatory_entities,
    tool_observatory_maintenance_sweep,
    tool_observatory_quest_board,
)

@mcp.tool()
async def observatory_stats() -> dict:
    """Database statistics: node/edge/cluster counts, type and lock-in distributions."""
    return await tool_observatory_stats(engine)

@mcp.tool()
async def observatory_graph_dump(limit: int = 500, min_lock_in: float = 0.0) -> dict:
    """Full graph snapshot (nodes, edges, clusters) for visualization."""
    return await tool_observatory_graph_dump(engine, limit, min_lock_in)

# ... etc for each tool
```

Each tool implementation receives the `engine` reference and accesses
MatrixActor, MemoryGraph, EntityResolver through it.

---

## After Deployment

1. Verify all 8 tools appear in Claude Desktop MCP tool list
2. Run `observatory_stats` — should return real production counts
3. Run `observatory_replay("Luna's robot body")` — should show full pipeline trace
4. Run `observatory_entities` — should list all 41 entities
5. **Deregister Observatory-Sandbox MCP** from Claude project config
6. Optionally archive `Tools/MemoryMatrix_SandBox/` (don't delete — has extraction scripts)

---

## Verification Checklist

```
[ ] observatory_stats returns real node/edge counts matching production DB
[ ] observatory_graph_dump returns nodes with lock_in scores
[ ] observatory_search("Luna", "all") returns FTS5 + vector + hybrid results
[ ] observatory_replay traces full pipeline with timing per phase
[ ] observatory_tune adjusts params and persists to data/observatory_config.json
[ ] observatory_entities lists entities with mention counts
[ ] observatory_entities(entity_id="eclissi") returns full entity detail
[ ] observatory_maintenance_sweep identifies graph health issues
[ ] observatory_quest_board(action="list") shows existing quests
[ ] Sandbox MCP deregistered, sandbox_* tools no longer in tool list
```
