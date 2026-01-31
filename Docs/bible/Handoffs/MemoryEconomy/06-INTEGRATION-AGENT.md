# Agent A6: Integration Agent

**Task:** Wire everything together, create constellation assembly  
**Dependencies:** A2, A3, A4, A5 (all other agents must complete first)  
**Outputs:** `src/luna/memory/constellation.py`, config, final wiring  
**Estimated Time:** 45 minutes

---

## Objective

This agent runs LAST. It:
1. Creates ConstellationAssembler (combines clusters + nodes)
2. Wires into Director
3. Creates config file
4. Validates full pipeline

---

## Constellation Assembly

Create `src/luna/memory/constellation.py`:

```python
"""
ConstellationAssembler - Combines clusters and nodes into context.

This is the final assembly layer that:
1. Takes retrieval results (nodes + clusters)
2. Prioritizes by lock-in
3. Respects token budget
4. Formats for Director
"""

from dataclasses import dataclass, field
from typing import List, Dict
import json

from luna.memory.cluster_manager import Cluster


@dataclass
class Constellation:
    """Assembled context from Memory Economy."""
    clusters: List[Dict] = field(default_factory=list)
    nodes: List[Dict] = field(default_factory=list)
    total_tokens: int = 0
    lock_in_distribution: Dict[str, int] = field(default_factory=dict)
    assembly_stats: Dict = field(default_factory=dict)


class ConstellationAssembler:
    """Assembles context constellations from retrieval results."""
    
    def __init__(self, max_tokens: int = 3000):
        self.max_tokens = max_tokens
        self.words_per_token = 0.75  # Rough estimate
    
    def assemble(
        self, 
        clusters: List[Dict], 
        nodes: List[Dict],
        prioritize_clusters: bool = True
    ) -> Constellation:
        """
        Assemble constellation respecting token budget.
        
        Strategy:
        1. Include high lock-in clusters first
        2. Add individual nodes
        3. Stop when budget exhausted
        """
        selected_clusters = []
        selected_nodes = []
        total_tokens = 0
        
        # Sort clusters by lock-in
        if clusters:
            clusters_sorted = sorted(
                clusters,
                key=lambda c: c['cluster'].lock_in if hasattr(c['cluster'], 'lock_in') else 0,
                reverse=True
            )
        else:
            clusters_sorted = []
        
        # Add clusters first if prioritized
        if prioritize_clusters:
            for cluster_data in clusters_sorted:
                cluster = cluster_data['cluster']
                estimated = self._estimate_cluster_tokens(cluster)
                
                if total_tokens + estimated <= self.max_tokens:
                    selected_clusters.append(cluster_data)
                    total_tokens += estimated
                else:
                    break
        
        # Add individual nodes
        for node in nodes:
            estimated = self._estimate_node_tokens(node)
            
            if total_tokens + estimated <= self.max_tokens:
                selected_nodes.append(node)
                total_tokens += estimated
            else:
                break
        
        # Calculate lock-in distribution
        lock_in_dist = {'crystallized': 0, 'settled': 0, 'fluid': 0, 'drifting': 0}
        
        for cluster_data in selected_clusters:
            cluster = cluster_data['cluster']
            state = cluster.state if hasattr(cluster, 'state') else 'fluid'
            lock_in_dist[state] = lock_in_dist.get(state, 0) + 1
        
        return Constellation(
            clusters=selected_clusters,
            nodes=selected_nodes,
            total_tokens=total_tokens,
            lock_in_distribution=lock_in_dist,
            assembly_stats={
                'clusters_considered': len(clusters),
                'clusters_selected': len(selected_clusters),
                'nodes_considered': len(nodes),
                'nodes_selected': len(selected_nodes),
                'budget_used_pct': round(total_tokens / self.max_tokens * 100, 1)
            }
        )
    
    def _estimate_cluster_tokens(self, cluster) -> int:
        """Estimate tokens for a cluster."""
        tokens = 50  # Base overhead
        
        if hasattr(cluster, 'summary') and cluster.summary:
            tokens += int(len(cluster.summary.split()) / self.words_per_token)
        
        if hasattr(cluster, 'name') and cluster.name:
            tokens += int(len(cluster.name.split()) / self.words_per_token)
        
        member_count = getattr(cluster, 'member_count', 5)
        tokens += min(member_count, 5) * 20
        
        return tokens
    
    def _estimate_node_tokens(self, node: Dict) -> int:
        """Estimate tokens for a node."""
        content = node.get('content', '')
        return max(10, int(len(content.split()) / self.words_per_token))
    
    def format_for_director(self, constellation: Constellation) -> str:
        """Format constellation as text for Director's context."""
        lines = []
        
        if constellation.clusters:
            lines.append("=== ACTIVE MEMORY CLUSTERS ===")
            lines.append("")
            
            for cluster_data in constellation.clusters:
                cluster = cluster_data['cluster']
                name = getattr(cluster, 'name', 'Unnamed Cluster')
                state = getattr(cluster, 'state', 'unknown')
                lock_in = getattr(cluster, 'lock_in', 0)
                summary = getattr(cluster, 'summary', '')
                member_count = getattr(cluster, 'member_count', 0)
                
                lines.append(f"**{name}**")
                lines.append(f"  State: {state} | Lock-in: {lock_in:.2f} | Members: {member_count}")
                if summary:
                    lines.append(f"  {summary}")
                lines.append("")
        
        if constellation.nodes:
            lines.append("=== RELEVANT MEMORIES ===")
            lines.append("")
            
            for node in constellation.nodes:
                node_type = node.get('node_type', 'UNKNOWN')
                content = node.get('content', '')[:200]
                lines.append(f"[{node_type}] {content}...")
                lines.append("")
        
        stats = constellation.assembly_stats
        lines.append(f"<!-- Context: {stats.get('clusters_selected', 0)} clusters, "
                    f"{stats.get('nodes_selected', 0)} nodes, "
                    f"{stats.get('budget_used_pct', 0)}% budget -->")
        
        return "\n".join(lines)
```

---

## Configuration File

Create `config/memory_economy_config.json`:

```json
{
  "enabled": true,
  "use_clusters": true,
  "use_louvain": false,
  
  "constellation": {
    "max_tokens": 3000,
    "prioritize_clusters": true
  },
  
  "thresholds": {
    "drifting": 0.20,
    "fluid": 0.70,
    "settled": 0.85,
    "similarity": 0.82,
    "auto_activation": 0.80
  },
  
  "weights": {
    "node": 0.40,
    "access": 0.30,
    "edge": 0.20,
    "age": 0.10
  },
  
  "decay": {
    "crystallized": 0.00001,
    "settled": 0.0001,
    "fluid": 0.001,
    "drifting": 0.01
  },
  
  "services": {
    "clustering_interval_hours": 1,
    "lockin_update_interval_minutes": 5
  },
  
  "clustering": {
    "min_cluster_size": 3,
    "max_cluster_size": 50,
    "min_keyword_overlap": 0.4
  }
}
```

---

## Full Pipeline Test

Create `scripts/test_memory_economy_full.py`:

```python
#!/usr/bin/env python3
"""
Full Memory Economy pipeline test.
Run AFTER all agents have completed their work.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_full_pipeline():
    print("=" * 60)
    print("MEMORY ECONOMY - FULL PIPELINE TEST")
    print("=" * 60)
    
    db_path = Path(__file__).parent.parent / "data" / "luna_engine.db"
    
    # 1. Test schema
    print("\n1. Testing schema...")
    import sqlite3
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name IN ('clusters', 'cluster_members', 'cluster_edges')
    """)
    tables = [r[0] for r in cursor.fetchall()]
    conn.close()
    
    assert len(tables) == 3, f"Expected 3 tables, found {tables}"
    print(f"   ✅ Tables exist: {tables}")
    
    # 2. Test ClusterManager
    print("\n2. Testing ClusterManager...")
    from luna.memory.cluster_manager import ClusterManager
    mgr = ClusterManager(str(db_path))
    
    test_id = mgr.create_cluster("Pipeline Test Cluster", "Testing full pipeline")
    cluster = mgr.get_cluster(test_id)
    assert cluster is not None
    print(f"   ✅ Created cluster: {test_id[:8]}...")
    mgr.delete_cluster(test_id)
    print("   ✅ Deleted test cluster")
    
    # 3. Test ClusteringEngine
    print("\n3. Testing ClusteringEngine...")
    from luna.memory.clustering_engine import ClusteringEngine
    engine = ClusteringEngine(str(db_path))
    keywords = engine._extract_keywords("Luna memory matrix architecture test")
    assert len(keywords) > 0
    print(f"   ✅ Keyword extraction: {keywords[:3]}")
    
    # 4. Test LockInCalculator
    print("\n4. Testing LockInCalculator...")
    from luna.memory.lock_in import LockInCalculator
    calc = LockInCalculator(str(db_path))
    
    test_id = mgr.create_cluster("LockIn Test", "Testing lock-in")
    lock_in = calc.calculate_cluster_lock_in(test_id)
    print(f"   ✅ Lock-in calculation: {lock_in:.3f}")
    mgr.delete_cluster(test_id)
    
    # 5. Test ConstellationAssembler
    print("\n5. Testing ConstellationAssembler...")
    from luna.memory.constellation import ConstellationAssembler
    assembler = ConstellationAssembler(max_tokens=3000)
    
    constellation = assembler.assemble(clusters=[], nodes=[])
    assert constellation.total_tokens == 0
    print(f"   ✅ Empty constellation: {constellation.assembly_stats}")
    
    # 6. Test ClusterRetrieval
    print("\n6. Testing ClusterRetrieval...")
    from luna.librarian.cluster_retrieval import ClusterRetrieval
    retrieval = ClusterRetrieval(str(db_path))
    auto = retrieval.get_auto_activated_clusters()
    print(f"   ✅ Auto-activated clusters: {len(auto)}")
    
    # 7. Get stats
    print("\n7. Memory Economy Stats...")
    stats = mgr.get_stats()
    print(f"   Total clusters: {stats['total_clusters']}")
    print(f"   State distribution: {stats['state_distribution']}")
    print(f"   Average lock-in: {stats['avg_lock_in']}")
    print(f"   Total edges: {stats['total_edges']}")
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS PASSED - Memory Economy is operational!")
    print("=" * 60)

if __name__ == "__main__":
    test_full_pipeline()
```

---

## Success Criteria

- [ ] ConstellationAssembler created
- [ ] Config file created
- [ ] Full pipeline test passes
- [ ] Director can use constellation context
- [ ] No regressions in existing functionality

---

## Final Validation Commands

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Run full test
python scripts/test_memory_economy_full.py

# Check cluster stats
python -c "
from luna.memory.cluster_manager import ClusterManager
mgr = ClusterManager('data/luna_engine.db')
print(mgr.get_stats())
"

# Run clustering once
python -m luna.services.clustering_service --once

# Run lock-in update once
python -m luna.services.lockin_service --once
```
