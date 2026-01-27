# Agent A4: Librarian Agent

**Task:** Integrate cluster retrieval into existing Librarian  
**Dependencies:** A1 (Schema), A2 (ClusterManager)  
**Outputs:** Modified `src/luna/librarian/` with cluster support  
**Estimated Time:** 30 minutes

---

## Objective

Extend the Librarian to return clusters alongside individual nodes during retrieval. This enables "constellation" context assembly.

---

## Implementation

Add to existing Librarian class (or create new module):

Create `src/luna/librarian/cluster_retrieval.py`:

```python
"""
Cluster-aware retrieval for the Librarian.

Adds hybrid_search_with_clusters() that returns both nodes and relevant clusters.
"""

import sqlite3
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from luna.memory.cluster_manager import ClusterManager, Cluster


class ClusterRetrieval:
    """Cluster-aware retrieval layer for the Librarian."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.cluster_mgr = ClusterManager(db_path)
        
        # Config
        self.auto_activation_threshold = 0.80  # Auto-include clusters above this
        self.max_clusters_per_query = 5
    
    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def find_relevant_clusters(
        self, 
        node_ids: List[str],
        top_k: int = 5
    ) -> List[Tuple[Cluster, float]]:
        """
        Find clusters relevant to retrieved nodes.
        
        Strategy:
        1. Check which clusters contain retrieved nodes
        2. Score by: membership_strength * cluster_lock_in
        3. Return top clusters
        
        Args:
            node_ids: IDs of retrieved nodes
            top_k: Max clusters to return
        
        Returns:
            List of (Cluster, relevance_score) tuples
        """
        if not node_ids:
            return []
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cluster_scores = defaultdict(float)
        
        for node_id in node_ids:
            cursor.execute("""
                SELECT cm.cluster_id, cm.membership_strength, c.lock_in, c.state
                FROM cluster_members cm
                JOIN clusters c ON cm.cluster_id = c.cluster_id
                WHERE cm.node_id = ?
            """, (node_id,))
            
            for row in cursor.fetchall():
                cluster_id = row['cluster_id']
                membership = row['membership_strength']
                lock_in = row['lock_in']
                
                # Score = membership * lock_in
                cluster_scores[cluster_id] += membership * lock_in
        
        conn.close()
        
        # Sort by score
        sorted_clusters = sorted(
            cluster_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )[:top_k]
        
        # Fetch full cluster objects
        results = []
        for cluster_id, score in sorted_clusters:
            cluster = self.cluster_mgr.get_cluster(cluster_id)
            if cluster:
                # Record access (for lock-in dynamics)
                self.cluster_mgr.record_access(cluster_id)
                results.append((cluster, score))
        
        return results
    
    def get_auto_activated_clusters(self) -> List[Cluster]:
        """
        Get clusters above auto-activation threshold.
        
        These are "always warm" clusters that should be included
        regardless of query relevance.
        """
        return self.cluster_mgr.list_clusters(
            min_lock_in=self.auto_activation_threshold,
            limit=self.max_clusters_per_query
        )
    
    def expand_cluster_context(
        self, 
        cluster_id: str,
        max_nodes: int = 10
    ) -> List[Dict]:
        """
        Expand a cluster into its member nodes.
        
        Returns:
            List of node dicts with content and metadata
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT n.id, n.node_type, n.content, n.lock_in_coefficient,
                   cm.membership_strength
            FROM cluster_members cm
            JOIN memory_nodes n ON cm.node_id = n.id
            WHERE cm.cluster_id = ?
            ORDER BY cm.membership_strength DESC
            LIMIT ?
        """, (cluster_id, max_nodes))
        
        nodes = []
        for row in cursor.fetchall():
            nodes.append({
                'node_id': row['id'],
                'node_type': row['node_type'],
                'content': row['content'],
                'lock_in': row['lock_in_coefficient'],
                'membership_strength': row['membership_strength']
            })
        
        conn.close()
        return nodes
    
    def get_multi_hop_clusters(
        self,
        cluster_id: str,
        min_edge_lock_in: float = 0.7,
        max_hops: int = 1
    ) -> List[Tuple[Cluster, float]]:
        """
        Get clusters connected via high lock-in edges.
        
        This enables "constellation" recall - one cluster activates
        its neighbors.
        
        Args:
            cluster_id: Starting cluster
            min_edge_lock_in: Minimum edge lock-in to traverse
            max_hops: How many hops to follow
        
        Returns:
            List of (Cluster, edge_lock_in) tuples
        """
        connected = self.cluster_mgr.get_connected_clusters(
            cluster_id=cluster_id,
            min_lock_in=min_edge_lock_in
        )
        
        results = []
        for neighbor_id, edge_lock_in in connected:
            cluster = self.cluster_mgr.get_cluster(neighbor_id)
            if cluster:
                results.append((cluster, edge_lock_in))
        
        return results


def integrate_with_librarian(librarian_instance, db_path: str):
    """
    Monkey-patch existing Librarian with cluster support.
    
    Usage:
        from luna.librarian.librarian import Librarian
        from luna.librarian.cluster_retrieval import integrate_with_librarian
        
        lib = Librarian(db_path)
        integrate_with_librarian(lib, db_path)
        
        # Now use:
        result = lib.hybrid_search_with_clusters(query)
    """
    cluster_retrieval = ClusterRetrieval(db_path)
    
    def hybrid_search_with_clusters(
        query: str,
        limit: int = 10,
        include_clusters: bool = True
    ) -> Dict:
        """Enhanced search returning nodes + clusters."""
        
        # Call existing hybrid search
        nodes = librarian_instance.hybrid_search(query, limit=limit)
        
        if not include_clusters:
            return {'nodes': nodes, 'clusters': []}
        
        # Get node IDs
        node_ids = [n.get('id') or n.get('node_id') for n in nodes]
        
        # Find relevant clusters
        cluster_results = cluster_retrieval.find_relevant_clusters(
            node_ids=node_ids,
            top_k=5
        )
        
        # Also check auto-activated clusters
        auto_clusters = cluster_retrieval.get_auto_activated_clusters()
        
        # Merge (avoid duplicates)
        seen_ids = {c.cluster_id for c, _ in cluster_results}
        for cluster in auto_clusters:
            if cluster.cluster_id not in seen_ids:
                cluster_results.append((cluster, cluster.lock_in))
        
        return {
            'nodes': nodes,
            'clusters': [
                {'cluster': c, 'relevance_score': s}
                for c, s in cluster_results
            ]
        }
    
    # Attach method
    librarian_instance.hybrid_search_with_clusters = hybrid_search_with_clusters
    librarian_instance.cluster_retrieval = cluster_retrieval
    
    return librarian_instance
```

---

## Alternative: Direct Librarian Modification

If you prefer to modify the existing Librarian class directly, add these methods:

```python
# In src/luna/librarian/librarian.py

from luna.memory.cluster_manager import ClusterManager

class Librarian:
    def __init__(self, db_path: str):
        # ... existing init ...
        self.cluster_mgr = ClusterManager(db_path)
    
    def hybrid_search_with_clusters(
        self, 
        query: str, 
        limit: int = 10,
        include_clusters: bool = True
    ) -> Dict:
        """Enhanced search with cluster support."""
        
        # Existing node search
        nodes = self.hybrid_search(query, limit=limit)
        
        if not include_clusters:
            return {'nodes': nodes, 'clusters': []}
        
        # Find clusters containing these nodes
        node_ids = [n['id'] for n in nodes]
        clusters = self._find_relevant_clusters(node_ids)
        
        return {'nodes': nodes, 'clusters': clusters}
    
    def _find_relevant_clusters(self, node_ids: List[str]) -> List[Dict]:
        """Find clusters relevant to retrieved nodes."""
        # ... implementation from ClusterRetrieval ...
```

---

## Validation

```python
# Test script
from luna.librarian.librarian import Librarian
from luna.librarian.cluster_retrieval import integrate_with_librarian

db_path = "data/luna_engine.db"
lib = Librarian(db_path)
integrate_with_librarian(lib, db_path)

# Test cluster-aware retrieval
result = lib.hybrid_search_with_clusters("Luna memory architecture")

print(f"Nodes: {len(result['nodes'])}")
print(f"Clusters: {len(result['clusters'])}")

for cluster_data in result['clusters']:
    c = cluster_data['cluster']
    print(f"  - {c.name} (lock-in: {c.lock_in:.2f})")
```

---

## Success Criteria

- [ ] `hybrid_search_with_clusters()` returns both nodes and clusters
- [ ] Cluster relevance scored correctly
- [ ] Auto-activated clusters included
- [ ] Access recorded for lock-in dynamics
- [ ] No regression in existing search functionality
