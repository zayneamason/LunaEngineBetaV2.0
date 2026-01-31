# Memory Economy Integration Layer — Implementation Handoff

**Created:** 2026-01-27  
**Status:** Ready for Implementation  
**Priority:** High — Backend complete, needs API wiring  

---

## Executive Summary

The Memory Economy backend is **fully operational** (195 clusters, 4,316 nodes) but **not integrated** with user-facing systems. This handoff specifies:

1. **New API Endpoints** for cluster/constellation visibility
2. **Thought Stream Extensions** for real-time cluster events
3. **Director Wiring** for constellation-based context building
4. **Tuning Parameters** for Memory Economy (extend existing ParamRegistry)
5. **Frontend Components** for visualization

---

## Current State

### What EXISTS and WORKS

```
✅ ClusterManager        → /src/luna/memory/cluster_manager.py
✅ ConstellationAssembler → /src/luna/memory/constellation.py
✅ ClusterRetrieval      → /src/luna/librarian/cluster_retrieval.py
✅ Config                → /config/memory_economy_config.json
✅ 195 clusters, 4,316 nodes in database
```

### What DOESN'T EXIST Yet

```
❌ API endpoints for /clusters/*
❌ Constellation assembly endpoint
❌ Thought stream cluster events
❌ Director using ConstellationAssembler
❌ Tuning parameters for Memory Economy
❌ Frontend cluster visualization
```

---

## Part 1: New API Endpoints

Add to `/src/luna/api/server.py` after the existing memory endpoints (~line 1600):

### 1.1 Cluster Statistics

```python
# =============================================================================
# MEMORY ECONOMY ENDPOINTS — Cluster Visibility
# =============================================================================

class ClusterStatsResponse(BaseModel):
    """Memory Economy cluster statistics."""
    cluster_count: int
    total_nodes: int
    state_distribution: dict  # {drifting: n, fluid: n, settled: n, crystallized: n}
    avg_lock_in: float
    nodes_per_cluster_avg: float
    nodes_per_cluster_max: int
    top_clusters: list[dict]  # Top 5 by size


@app.get("/clusters/stats", response_model=ClusterStatsResponse)
async def get_cluster_stats():
    """
    Get Memory Economy cluster statistics.
    
    Shows cluster distribution, lock-in states, and top clusters.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    matrix = _engine.get_actor("matrix")
    if not matrix or not matrix.is_ready:
        raise HTTPException(status_code=503, detail="Matrix not ready")
    
    try:
        from luna.memory.cluster_manager import ClusterManager
        
        # Get DB path from matrix
        db_path = matrix._matrix.db_path if matrix._matrix else None
        if not db_path:
            raise HTTPException(status_code=503, detail="Database not available")
        
        cluster_mgr = ClusterManager(db_path)
        
        # Get all clusters
        all_clusters = cluster_mgr.list_clusters()
        
        # Calculate state distribution
        state_dist = {"drifting": 0, "fluid": 0, "settled": 0, "crystallized": 0}
        total_lock_in = 0.0
        sizes = []
        
        for c in all_clusters:
            state_dist[c.state] += 1
            total_lock_in += c.lock_in
            sizes.append(c.member_count)
        
        cluster_count = len(all_clusters)
        avg_lock_in = total_lock_in / cluster_count if cluster_count > 0 else 0.0
        
        # Top clusters by size
        sorted_clusters = sorted(all_clusters, key=lambda c: c.member_count, reverse=True)[:5]
        top_clusters = [
            {
                "cluster_id": c.cluster_id,
                "label": c.label,
                "member_count": c.member_count,
                "lock_in": round(c.lock_in, 3),
                "state": c.state,
            }
            for c in sorted_clusters
        ]
        
        return ClusterStatsResponse(
            cluster_count=cluster_count,
            total_nodes=sum(sizes),
            state_distribution=state_dist,
            avg_lock_in=round(avg_lock_in, 3),
            nodes_per_cluster_avg=round(sum(sizes) / cluster_count, 1) if cluster_count > 0 else 0,
            nodes_per_cluster_max=max(sizes) if sizes else 0,
            top_clusters=top_clusters,
        )
    except Exception as e:
        logger.error(f"Cluster stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 1.2 List Clusters

```python
class ClusterListItem(BaseModel):
    """Single cluster in list response."""
    cluster_id: str
    label: str
    member_count: int
    lock_in: float
    state: str
    keywords: list[str]


class ClusterListResponse(BaseModel):
    """Response from cluster list."""
    clusters: list[ClusterListItem]
    total: int


@app.get("/clusters/list", response_model=ClusterListResponse)
async def list_clusters(
    state: Optional[str] = None,
    min_lock_in: Optional[float] = None,
    limit: int = 50,
):
    """
    List clusters with optional filtering.
    
    Args:
        state: Filter by state (drifting, fluid, settled, crystallized)
        min_lock_in: Minimum lock-in threshold
        limit: Maximum clusters to return
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    matrix = _engine.get_actor("matrix")
    if not matrix or not matrix.is_ready:
        raise HTTPException(status_code=503, detail="Matrix not ready")
    
    try:
        from luna.memory.cluster_manager import ClusterManager
        
        db_path = matrix._matrix.db_path
        cluster_mgr = ClusterManager(db_path)
        
        all_clusters = cluster_mgr.list_clusters()
        
        # Apply filters
        if state:
            all_clusters = [c for c in all_clusters if c.state == state]
        if min_lock_in is not None:
            all_clusters = [c for c in all_clusters if c.lock_in >= min_lock_in]
        
        # Sort by lock-in descending
        all_clusters.sort(key=lambda c: c.lock_in, reverse=True)
        
        # Apply limit
        clusters = all_clusters[:limit]
        
        return ClusterListResponse(
            clusters=[
                ClusterListItem(
                    cluster_id=c.cluster_id,
                    label=c.label,
                    member_count=c.member_count,
                    lock_in=round(c.lock_in, 3),
                    state=c.state,
                    keywords=c.keywords[:5] if c.keywords else [],
                )
                for c in clusters
            ],
            total=len(all_clusters),
        )
    except Exception as e:
        logger.error(f"Cluster list failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 1.3 Get Cluster Details

```python
class ClusterMember(BaseModel):
    """Member node in a cluster."""
    node_id: str
    content: str
    node_type: str
    lock_in: float
    membership_strength: float


class ClusterDetailResponse(BaseModel):
    """Full cluster details."""
    cluster_id: str
    label: str
    member_count: int
    lock_in: float
    state: str
    keywords: list[str]
    members: list[ClusterMember]
    related_clusters: list[dict]  # Adjacent clusters


@app.get("/clusters/{cluster_id}", response_model=ClusterDetailResponse)
async def get_cluster_detail(cluster_id: str):
    """
    Get detailed information about a specific cluster.
    
    Includes member nodes and related clusters.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    matrix = _engine.get_actor("matrix")
    if not matrix or not matrix.is_ready:
        raise HTTPException(status_code=503, detail="Matrix not ready")
    
    try:
        from luna.memory.cluster_manager import ClusterManager
        
        db_path = matrix._matrix.db_path
        cluster_mgr = ClusterManager(db_path)
        
        # Get cluster
        cluster = cluster_mgr.get_cluster(cluster_id)
        if not cluster:
            raise HTTPException(status_code=404, detail=f"Cluster not found: {cluster_id}")
        
        # Get members with their node details
        members = cluster_mgr.get_cluster_members(cluster_id)
        member_details = []
        for m in members:
            node = await matrix._matrix.get_node(m["node_id"])
            if node:
                member_details.append(ClusterMember(
                    node_id=m["node_id"],
                    content=node.content[:200],  # Truncate for response
                    node_type=node.node_type,
                    lock_in=round(node.lock_in, 3),
                    membership_strength=round(m["membership_strength"], 3),
                ))
        
        # Get related clusters (shared members or edges)
        related = cluster_mgr.get_related_clusters(cluster_id, limit=5)
        
        return ClusterDetailResponse(
            cluster_id=cluster.cluster_id,
            label=cluster.label,
            member_count=cluster.member_count,
            lock_in=round(cluster.lock_in, 3),
            state=cluster.state,
            keywords=cluster.keywords or [],
            members=member_details,
            related_clusters=[
                {
                    "cluster_id": r.cluster_id,
                    "label": r.label,
                    "lock_in": round(r.lock_in, 3),
                }
                for r in related
            ],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cluster detail failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

### 1.4 Constellation Assembly Endpoint

```python
class ConstellationRequest(BaseModel):
    """Request for constellation assembly."""
    query: str
    max_tokens: int = Field(default=3000, ge=500, le=8000)
    max_clusters: int = Field(default=5, ge=1, le=10)


class ConstellationResponse(BaseModel):
    """Assembled constellation for context."""
    activated_clusters: list[dict]
    expanded_nodes: list[dict]
    total_tokens: int
    lock_in_distribution: dict
    assembly_time_ms: float


@app.post("/constellation/assemble", response_model=ConstellationResponse)
async def assemble_constellation(request: ConstellationRequest):
    """
    Assemble a constellation for a query.
    
    This is the primary Memory Economy retrieval endpoint.
    Returns clusters + nodes formatted for context injection.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    matrix = _engine.get_actor("matrix")
    if not matrix or not matrix.is_ready:
        raise HTTPException(status_code=503, detail="Matrix not ready")
    
    import time
    start = time.time()
    
    try:
        from luna.librarian.cluster_retrieval import ClusterRetrieval
        from luna.memory.constellation import ConstellationAssembler
        
        db_path = matrix._matrix.db_path
        
        # Step 1: Retrieve relevant nodes
        nodes = await matrix._matrix.search_nodes(query=request.query, limit=20)
        node_ids = [n.id for n in nodes]
        
        # Step 2: Find relevant clusters
        retrieval = ClusterRetrieval(db_path)
        cluster_results = retrieval.find_relevant_clusters(
            node_ids=node_ids,
            top_k=request.max_clusters
        )
        
        # Step 3: Assemble constellation
        assembler = ConstellationAssembler(max_tokens=request.max_tokens)
        
        cluster_dicts = [
            {"cluster": c, "score": score}
            for c, score in cluster_results
        ]
        node_dicts = [
            {"node_id": n.id, "content": n.content, "node_type": n.node_type, "lock_in": n.lock_in}
            for n in nodes
        ]
        
        constellation = assembler.assemble(
            clusters=cluster_dicts,
            nodes=node_dicts,
            prioritize_clusters=True
        )
        
        elapsed_ms = (time.time() - start) * 1000
        
        # Emit thought stream event
        await _engine._emit_progress(
            f"[CONSTELLATION] Assembled: {len(constellation.clusters)} clusters, "
            f"{len(constellation.nodes)} nodes, {constellation.total_tokens} tokens"
        )
        
        return ConstellationResponse(
            activated_clusters=[
                {
                    "cluster_id": c.get("cluster_id") or c.get("cluster", {}).get("cluster_id"),
                    "label": c.get("label") or c.get("cluster", {}).get("label"),
                    "lock_in": c.get("lock_in") or c.get("cluster", {}).get("lock_in"),
                    "member_count": c.get("member_count") or c.get("cluster", {}).get("member_count"),
                }
                for c in constellation.clusters
            ],
            expanded_nodes=[
                {
                    "node_id": n.get("node_id"),
                    "content": n.get("content", "")[:200],
                    "node_type": n.get("node_type"),
                    "lock_in": n.get("lock_in"),
                }
                for n in constellation.nodes
            ],
            total_tokens=constellation.total_tokens,
            lock_in_distribution=constellation.lock_in_distribution,
            assembly_time_ms=round(elapsed_ms, 1),
        )
    except Exception as e:
        logger.error(f"Constellation assembly failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Part 2: Thought Stream Extensions

Extend the `/thoughts` SSE endpoint to emit Memory Economy events.

### 2.1 New Event Types

Add to the thought stream in `/persona/stream` and constellation endpoints:

```python
# In persona_stream endpoint, after memory retrieval (~line 780):

# Memory Economy events (if constellation used)
if constellation_result:
    await _engine._emit_progress(
        f"[CLUSTER_ACTIVATED] {', '.join(c['label'] for c in activated_clusters[:3])}"
    )
    
    # Emit per-cluster activation for detailed frontend display
    for cluster in activated_clusters:
        await thought_queue.put({
            "type": "cluster_activated",
            "cluster_id": cluster["cluster_id"],
            "label": cluster["label"],
            "lock_in": cluster["lock_in"],
            "relevance": cluster.get("score", 0),
        })
```

### 2.2 New Event Definitions

```python
# Thought stream event types for Memory Economy:

# event: cluster_activated
# data: {"cluster_id": "abc123", "label": "project_architecture", "lock_in": 0.85, "relevance": 0.92}

# event: constellation_assembled  
# data: {"cluster_count": 3, "node_count": 12, "total_tokens": 1850}

# event: memory_economy_stats
# data: {"active_clusters": 5, "total_retrieved": 15, "avg_lock_in": 0.72}
```

---

## Part 3: Director Integration

Wire ConstellationAssembler into Director's context building.

### 3.1 Integration Point

In `/src/luna/actors/director.py`, modify `_fetch_memory_context()` (~line 1100):

```python
async def _fetch_memory_context(self, query: str, max_tokens: int = 1500) -> str:
    """
    Fetch relevant memory context for a query.
    
    UPDATED: Uses Memory Economy constellation assembly for cluster-aware retrieval.
    """
    if not self.engine:
        logger.debug("Memory fetch: No engine available")
        return ""
    
    matrix = self.engine.get_actor("matrix")
    if not matrix or not matrix.is_ready:
        return ""
    
    logger.debug(f"Memory fetch: Searching for query '{query[:50]}...'")
    
    try:
        # Check if Memory Economy is enabled
        use_clusters = True  # Could be from config
        
        if use_clusters:
            # Use constellation assembly for cluster-aware retrieval
            return await self._fetch_constellation_context(query, max_tokens, matrix)
        else:
            # Fallback to basic node search
            return await self._fetch_basic_context(query, max_tokens, matrix)
            
    except Exception as e:
        logger.error(f"Memory fetch failed: {e}")
        return ""


async def _fetch_constellation_context(
    self, 
    query: str, 
    max_tokens: int,
    matrix
) -> str:
    """
    Fetch context using Memory Economy constellation assembly.
    
    This provides cluster-aware retrieval with:
    - Relevant clusters activated together
    - Lock-in prioritized node selection
    - Token-budgeted assembly
    """
    try:
        from luna.librarian.cluster_retrieval import ClusterRetrieval
        from luna.memory.constellation import ConstellationAssembler
        
        db_path = matrix._matrix.db_path
        
        # Step 1: Get relevant nodes
        nodes = await matrix._matrix.search_nodes(query=query, limit=20)
        node_ids = [n.id for n in nodes]
        
        # Step 2: Find relevant clusters
        retrieval = ClusterRetrieval(db_path)
        cluster_results = retrieval.find_relevant_clusters(node_ids=node_ids, top_k=5)
        
        # Step 3: Assemble constellation
        assembler = ConstellationAssembler(max_tokens=max_tokens)
        
        cluster_dicts = [{"cluster": c, "score": score} for c, score in cluster_results]
        node_dicts = [
            {"node_id": n.id, "content": n.content, "node_type": n.node_type, "lock_in": n.lock_in}
            for n in nodes
        ]
        
        constellation = assembler.assemble(
            clusters=cluster_dicts,
            nodes=node_dicts,
            prioritize_clusters=True
        )
        
        # Step 4: Format for prompt
        context_parts = []
        
        # Add cluster context
        for cluster_data in constellation.clusters:
            cluster = cluster_data.get("cluster") or cluster_data
            label = getattr(cluster, 'label', None) or cluster.get('label', 'unknown')
            context_parts.append(f"<cluster label='{label}'>")
            # Cluster members already included in nodes
        
        # Add node context
        for node_data in constellation.nodes:
            node_type = node_data.get("node_type", "memory")
            content = node_data.get("content", "")
            lock_in = node_data.get("lock_in", 0.5)
            age = self._humanize_age(node_data.get("created_at")) if node_data.get("created_at") else "unknown"
            
            context_parts.append(
                f"<memory type='{node_type}' lock_in='{lock_in:.2f}' age='{age}'>\n{content}\n</memory>"
            )
        
        result = "\n\n".join(context_parts)
        logger.info(
            f"Constellation context: {len(constellation.clusters)} clusters, "
            f"{len(constellation.nodes)} nodes, ~{constellation.total_tokens} tokens"
        )
        
        return result
        
    except ImportError:
        logger.warning("Memory Economy not available, falling back to basic retrieval")
        return await self._fetch_basic_context(query, max_tokens, matrix)
    except Exception as e:
        logger.error(f"Constellation fetch failed: {e}")
        return await self._fetch_basic_context(query, max_tokens, matrix)


async def _fetch_basic_context(self, query: str, max_tokens: int, matrix) -> str:
    """Basic node-only retrieval (fallback)."""
    # Existing implementation moved here
    nodes = await matrix._matrix.search_nodes(query=query, limit=10)
    if not nodes:
        return ""
    
    context_parts = []
    for node in nodes:
        age = self._humanize_age(node.created_at) if hasattr(node, 'created_at') else "unknown"
        context_parts.append(
            f"<memory type='{node.node_type}' age='{age}'>\n{node.content}\n</memory>"
        )
    
    return "\n\n".join(context_parts)
```

---

## Part 4: Tuning Parameters Extension

Add Memory Economy parameters to `/src/luna/tuning/params.py`:

### 4.1 New Parameters

Add to `TUNABLE_PARAMS` dict:

```python
    # -------------------------------------------------------------------------
    # MEMORY ECONOMY PARAMETERS
    # -------------------------------------------------------------------------
    "memory_economy.enabled": {
        "default": 1.0,
        "bounds": (0.0, 1.0),
        "step": 1.0,
        "description": "Enable Memory Economy cluster-based retrieval. 0 = basic node search, 1 = constellation assembly.",
        "category": "memory_economy",
    },
    "memory_economy.use_clusters": {
        "default": 1.0,
        "bounds": (0.0, 1.0),
        "step": 1.0,
        "description": "Use cluster-aware retrieval. When enabled, related memories are retrieved together.",
        "category": "memory_economy",
    },
    "memory_economy.max_clusters_per_query": {
        "default": 5,
        "bounds": (1, 10),
        "step": 1,
        "description": "Maximum clusters to activate per query. Higher = more context, more tokens.",
        "category": "memory_economy",
    },
    "memory_economy.cluster_budget_pct": {
        "default": 0.6,
        "bounds": (0.3, 0.9),
        "step": 0.1,
        "description": "Fraction of token budget allocated to cluster content (vs individual nodes).",
        "category": "memory_economy",
    },
    "memory_economy.auto_activation_threshold": {
        "default": 0.80,
        "bounds": (0.5, 0.95),
        "step": 0.05,
        "description": "Lock-in threshold for auto-activated clusters (always warm).",
        "category": "memory_economy",
    },
    "memory_economy.similarity_threshold": {
        "default": 0.82,
        "bounds": (0.5, 0.95),
        "step": 0.02,
        "description": "Minimum similarity for cluster membership.",
        "category": "memory_economy",
    },
    "memory_economy.merge_threshold": {
        "default": 0.6,
        "bounds": (0.3, 0.9),
        "step": 0.1,
        "description": "Similarity threshold for merging clusters.",
        "category": "memory_economy",
    },
    "memory_economy.min_cluster_size": {
        "default": 3,
        "bounds": (2, 10),
        "step": 1,
        "description": "Minimum members for a valid cluster.",
        "category": "memory_economy",
    },
    "memory_economy.max_cluster_size": {
        "default": 50,
        "bounds": (20, 100),
        "step": 10,
        "description": "Maximum members before cluster splits.",
        "category": "memory_economy",
    },
    
    # Decay rates by state
    "memory_economy.decay.drifting": {
        "default": 0.01,
        "bounds": (0.001, 0.1),
        "step": 0.005,
        "description": "Lock-in decay rate for drifting clusters.",
        "category": "memory_economy",
    },
    "memory_economy.decay.fluid": {
        "default": 0.001,
        "bounds": (0.0001, 0.01),
        "step": 0.001,
        "description": "Lock-in decay rate for fluid clusters.",
        "category": "memory_economy",
    },
    "memory_economy.decay.settled": {
        "default": 0.0001,
        "bounds": (0.00001, 0.001),
        "step": 0.0001,
        "description": "Lock-in decay rate for settled clusters.",
        "category": "memory_economy",
    },
    
    # Retrieval weights
    "memory_economy.weight.node": {
        "default": 0.40,
        "bounds": (0.1, 0.7),
        "step": 0.05,
        "description": "Weight of node content in cluster lock-in calculation.",
        "category": "memory_economy",
    },
    "memory_economy.weight.access": {
        "default": 0.30,
        "bounds": (0.1, 0.5),
        "step": 0.05,
        "description": "Weight of access frequency in cluster lock-in.",
        "category": "memory_economy",
    },
    "memory_economy.weight.edge": {
        "default": 0.20,
        "bounds": (0.05, 0.4),
        "step": 0.05,
        "description": "Weight of edge connections in cluster lock-in.",
        "category": "memory_economy",
    },
    "memory_economy.weight.age": {
        "default": 0.10,
        "bounds": (0.0, 0.3),
        "step": 0.05,
        "description": "Weight of age/recency in cluster lock-in.",
        "category": "memory_economy",
    },
```

### 4.2 Engine Application

Add to `_apply_to_engine()` method in `ParamRegistry`:

```python
if parts[0] == "memory_economy":
    # Load config and update
    import json
    config_path = "/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/config/memory_economy_config.json"
    
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        # Map parameter path to config location
        if parts[1] == "enabled":
            config["enabled"] = bool(value)
        elif parts[1] == "use_clusters":
            config["use_clusters"] = bool(value)
        elif parts[1] == "max_clusters_per_query":
            config["retrieval"]["max_clusters_per_query"] = int(value)
        elif parts[1] == "cluster_budget_pct":
            config["constellation"]["cluster_budget_pct"] = float(value)
        elif parts[1] == "auto_activation_threshold":
            config["thresholds"]["auto_activation"] = float(value)
        elif parts[1] == "similarity_threshold":
            config["thresholds"]["similarity"] = float(value)
        elif parts[1] == "merge_threshold":
            config["clustering"]["merge_similarity_threshold"] = float(value)
        elif parts[1] == "min_cluster_size":
            config["clustering"]["min_cluster_size"] = int(value)
        elif parts[1] == "max_cluster_size":
            config["clustering"]["max_cluster_size"] = int(value)
        elif parts[1] == "decay" and len(parts) > 2:
            config["decay"][parts[2]] = float(value)
        elif parts[1] == "weight" and len(parts) > 2:
            config["weights"][parts[2]] = float(value)
        
        # Write back
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        
        logger.info(f"Memory Economy config updated: {name}={value}")
        return True
    except Exception as e:
        logger.error(f"Failed to update Memory Economy config: {e}")
        return False
```

---

## Part 5: Frontend Components

### 5.1 Memory Economy Panel Component

Create `/frontend/src/components/MemoryEconomyPanel.tsx`:

```tsx
import { useState, useEffect } from 'react';

interface ClusterStats {
  cluster_count: number;
  total_nodes: number;
  state_distribution: {
    drifting: number;
    fluid: number;
    settled: number;
    crystallized: number;
  };
  avg_lock_in: number;
  top_clusters: Array<{
    cluster_id: string;
    label: string;
    member_count: number;
    lock_in: number;
    state: string;
  }>;
}

export function MemoryEconomyPanel() {
  const [stats, setStats] = useState<ClusterStats | null>(null);
  const [activeCluster, setActiveCluster] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  const fetchStats = async () => {
    try {
      const res = await fetch('/clusters/stats');
      const data = await res.json();
      setStats(data);
    } catch (e) {
      console.error('Failed to fetch cluster stats:', e);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return <div>Loading Memory Economy...</div>;
  if (!stats) return <div>Memory Economy unavailable</div>;

  return (
    <div className="memory-economy-panel">
      <h3>Memory Economy</h3>
      
      {/* Overview Stats */}
      <div className="stats-grid">
        <div className="stat">
          <span className="label">Clusters</span>
          <span className="value">{stats.cluster_count}</span>
        </div>
        <div className="stat">
          <span className="label">Nodes</span>
          <span className="value">{stats.total_nodes}</span>
        </div>
        <div className="stat">
          <span className="label">Avg Lock-in</span>
          <span className="value">{(stats.avg_lock_in * 100).toFixed(0)}%</span>
        </div>
      </div>
      
      {/* State Distribution */}
      <div className="state-distribution">
        <h4>Lock-in States</h4>
        <div className="state-bar">
          <div 
            className="state drifting" 
            style={{ width: `${stats.state_distribution.drifting / stats.cluster_count * 100}%` }}
            title={`Drifting: ${stats.state_distribution.drifting}`}
          />
          <div 
            className="state fluid"
            style={{ width: `${stats.state_distribution.fluid / stats.cluster_count * 100}%` }}
            title={`Fluid: ${stats.state_distribution.fluid}`}
          />
          <div 
            className="state settled"
            style={{ width: `${stats.state_distribution.settled / stats.cluster_count * 100}%` }}
            title={`Settled: ${stats.state_distribution.settled}`}
          />
          <div 
            className="state crystallized"
            style={{ width: `${stats.state_distribution.crystallized / stats.cluster_count * 100}%` }}
            title={`Crystallized: ${stats.state_distribution.crystallized}`}
          />
        </div>
        <div className="state-legend">
          <span className="legend-item drifting">Drifting ({stats.state_distribution.drifting})</span>
          <span className="legend-item fluid">Fluid ({stats.state_distribution.fluid})</span>
          <span className="legend-item settled">Settled ({stats.state_distribution.settled})</span>
          <span className="legend-item crystallized">Crystallized ({stats.state_distribution.crystallized})</span>
        </div>
      </div>
      
      {/* Top Clusters */}
      <div className="top-clusters">
        <h4>Top Clusters</h4>
        {stats.top_clusters.map(cluster => (
          <div 
            key={cluster.cluster_id}
            className={`cluster-item ${activeCluster === cluster.cluster_id ? 'active' : ''}`}
            onClick={() => setActiveCluster(cluster.cluster_id)}
          >
            <span className="label">{cluster.label}</span>
            <span className="count">{cluster.member_count} nodes</span>
            <span className={`state ${cluster.state}`}>{cluster.state}</span>
            <span className="lock-in">{(cluster.lock_in * 100).toFixed(0)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

### 5.2 CSS for Memory Economy Panel

```css
.memory-economy-panel {
  padding: 16px;
  background: var(--bg-secondary);
  border-radius: 8px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.stat {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.stat .label {
  font-size: 12px;
  color: var(--text-secondary);
}

.stat .value {
  font-size: 24px;
  font-weight: bold;
}

.state-bar {
  display: flex;
  height: 20px;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.state.drifting { background: #f59e0b; }
.state.fluid { background: #3b82f6; }
.state.settled { background: #10b981; }
.state.crystallized { background: #8b5cf6; }

.cluster-item {
  display: flex;
  justify-content: space-between;
  padding: 8px;
  border-radius: 4px;
  cursor: pointer;
}

.cluster-item:hover {
  background: var(--bg-tertiary);
}

.cluster-item.active {
  background: var(--accent-bg);
}
```

---

## Part 6: Implementation Checklist

### Phase 1: API Endpoints (Day 1)
- [ ] Add ClusterStatsResponse model
- [ ] Implement GET /clusters/stats
- [ ] Add ClusterListResponse model
- [ ] Implement GET /clusters/list
- [ ] Add ClusterDetailResponse model
- [ ] Implement GET /clusters/{cluster_id}
- [ ] Add ConstellationResponse model
- [ ] Implement POST /constellation/assemble

### Phase 2: Director Wiring (Day 1-2)
- [ ] Add _fetch_constellation_context() method
- [ ] Modify _fetch_memory_context() to use constellation
- [ ] Add fallback to _fetch_basic_context()
- [ ] Test cluster-aware retrieval

### Phase 3: Thought Stream (Day 2)
- [ ] Add cluster_activated event type
- [ ] Add constellation_assembled event type
- [ ] Wire events into persona_stream endpoint
- [ ] Test SSE events in browser

### Phase 4: Tuning Parameters (Day 2-3)
- [ ] Add memory_economy.* parameters to TUNABLE_PARAMS
- [ ] Add _apply_to_engine() routing for memory_economy
- [ ] Test parameter changes via /tuning/params API
- [ ] Verify config file updates

### Phase 5: Frontend (Day 3-4)
- [ ] Create MemoryEconomyPanel component
- [ ] Add to dashboard layout
- [ ] Connect to /clusters/stats API
- [ ] Add thought stream cluster event handling
- [ ] Style and polish

### Phase 6: Testing & Documentation (Day 4)
- [ ] Write integration tests
- [ ] Update API documentation
- [ ] Update frontend README
- [ ] Performance testing

---

## Files to Modify

```
MODIFY:
├── src/luna/api/server.py          # Add cluster & constellation endpoints
├── src/luna/actors/director.py     # Wire constellation into context building
├── src/luna/tuning/params.py       # Add memory_economy parameters
└── frontend/src/components/        # Add MemoryEconomyPanel

REFERENCE (read-only):
├── src/luna/memory/cluster_manager.py
├── src/luna/memory/constellation.py
├── src/luna/librarian/cluster_retrieval.py
└── config/memory_economy_config.json
```

---

## Testing Commands

```bash
# Test cluster stats
curl http://localhost:8000/clusters/stats | jq

# Test cluster list
curl "http://localhost:8000/clusters/list?state=settled&limit=10" | jq

# Test constellation assembly
curl -X POST http://localhost:8000/constellation/assemble \
  -H "Content-Type: application/json" \
  -d '{"query": "Luna architecture", "max_tokens": 2000}' | jq

# Test tuning parameter
curl -X POST http://localhost:8000/tuning/params/memory_economy.max_clusters_per_query \
  -H "Content-Type: application/json" \
  -d '{"value": 7}' | jq
```

---

## Success Criteria

1. **API works**: All 4 new endpoints return valid responses
2. **Director uses clusters**: Memory context includes cluster labels and structure
3. **Thought stream shows events**: Frontend displays cluster activations
4. **Tuning works**: Parameter changes affect Memory Economy behavior
5. **Frontend displays stats**: MemoryEconomyPanel renders correctly

---

*This handoff enables full Memory Economy integration. The backend is solid — this wires it to the user.*
