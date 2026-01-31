# Agent A2: ClusterManager Agent

**Task:** Implement Cluster CRUD operations  
**Dependencies:** A1 (Schema Agent)  
**Outputs:** `src/luna/memory/cluster_manager.py`  
**Estimated Time:** 30 minutes

---

## Objective

Create the `ClusterManager` class that provides all CRUD operations for clusters. This is the **shared interface** that all other agents will use.

---

## Implementation

Create `src/luna/memory/cluster_manager.py`:

```python
"""
ClusterManager - CRUD operations for Memory Economy clusters.

This is the shared interface used by:
- ClusteringEngine (creates clusters)
- Librarian (reads clusters)
- LockInService (updates lock-in)
- ConstellationAssembler (reads clusters)
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path


@dataclass
class Cluster:
    """Represents a semantic cluster of memories."""
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


@dataclass
class ClusterEdge:
    """Represents a relationship between clusters."""
    from_cluster: str
    to_cluster: str
    relationship: str
    strength: float
    lock_in: float
    created_at: str
    last_reinforced_at: Optional[str]
    reinforcement_count: int


# State thresholds
STATE_THRESHOLDS = {
    'drifting': 0.20,
    'fluid': 0.70,
    'settled': 0.85,
    # crystallized = above 0.85
}


def get_state_from_lock_in(lock_in: float) -> str:
    """Determine state from lock-in value."""
    if lock_in < STATE_THRESHOLDS['drifting']:
        return 'drifting'
    elif lock_in < STATE_THRESHOLDS['fluid']:
        return 'fluid'
    elif lock_in < STATE_THRESHOLDS['settled']:
        return 'settled'
    else:
        return 'crystallized'


class ClusterManager:
    """Manages cluster lifecycle operations."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # ==================== CREATE ====================
    
    def create_cluster(
        self, 
        name: str, 
        summary: Optional[str] = None,
        centroid_embedding: Optional[bytes] = None,
        initial_lock_in: float = 0.0
    ) -> str:
        """
        Create a new cluster.
        
        Args:
            name: Human-readable cluster name
            summary: Pre-computed summary for fast retrieval
            centroid_embedding: Semantic center (sqlite-vec format)
            initial_lock_in: Starting lock-in value (default 0.0)
        
        Returns:
            cluster_id (UUID string)
        """
        cluster_id = str(uuid.uuid4())
        state = get_state_from_lock_in(initial_lock_in)
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO clusters (
                cluster_id, name, summary, lock_in, state, centroid_embedding
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (cluster_id, name, summary, initial_lock_in, state, centroid_embedding))
        
        conn.commit()
        conn.close()
        
        return cluster_id
    
    # ==================== MEMBERS ====================
    
    def add_member(
        self, 
        cluster_id: str, 
        node_id: str, 
        membership_strength: float = 1.0
    ) -> None:
        """
        Add a node to a cluster.
        
        Args:
            cluster_id: Target cluster UUID
            node_id: Memory node ID to add
            membership_strength: How strongly node belongs (0.0-1.0)
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Insert or update membership
        cursor.execute("""
            INSERT OR REPLACE INTO cluster_members 
            (cluster_id, node_id, membership_strength)
            VALUES (?, ?, ?)
        """, (cluster_id, node_id, membership_strength))
        
        # Update cached member count
        cursor.execute("""
            UPDATE clusters 
            SET member_count = (
                SELECT COUNT(*) FROM cluster_members 
                WHERE cluster_id = ?
            ),
            updated_at = CURRENT_TIMESTAMP
            WHERE cluster_id = ?
        """, (cluster_id, cluster_id))
        
        conn.commit()
        conn.close()
    
    def remove_member(self, cluster_id: str, node_id: str) -> None:
        """Remove a node from a cluster."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM cluster_members 
            WHERE cluster_id = ? AND node_id = ?
        """, (cluster_id, node_id))
        
        # Update cached member count
        cursor.execute("""
            UPDATE clusters 
            SET member_count = (
                SELECT COUNT(*) FROM cluster_members 
                WHERE cluster_id = ?
            ),
            updated_at = CURRENT_TIMESTAMP
            WHERE cluster_id = ?
        """, (cluster_id, cluster_id))
        
        conn.commit()
        conn.close()
    
    def get_cluster_members(self, cluster_id: str) -> List[Tuple[str, float]]:
        """
        Get all nodes in a cluster.
        
        Returns:
            List of (node_id, membership_strength) tuples, sorted by strength DESC
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT node_id, membership_strength 
            FROM cluster_members 
            WHERE cluster_id = ?
            ORDER BY membership_strength DESC
        """, (cluster_id,))
        
        members = [(row['node_id'], row['membership_strength']) for row in cursor.fetchall()]
        conn.close()
        
        return members
    
    # ==================== EDGES ====================
    
    def add_edge(
        self,
        from_cluster: str,
        to_cluster: str,
        relationship: str,
        strength: float = 0.5,
        lock_in: float = 0.15
    ) -> None:
        """
        Create or update an edge between clusters.
        
        Args:
            from_cluster: Source cluster ID
            to_cluster: Target cluster ID
            relationship: Edge type (related_to, enables, etc.)
            strength: Connection strength (0.0-1.0)
            lock_in: Edge persistence (0.0-1.0)
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO cluster_edges
            (from_cluster, to_cluster, relationship, strength, lock_in)
            VALUES (?, ?, ?, ?, ?)
        """, (from_cluster, to_cluster, relationship, strength, lock_in))
        
        conn.commit()
        conn.close()
    
    def reinforce_edge(self, from_cluster: str, to_cluster: str, relationship: str) -> None:
        """Record that an edge was traversed (strengthens it)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE cluster_edges 
            SET reinforcement_count = reinforcement_count + 1,
                last_reinforced_at = CURRENT_TIMESTAMP,
                lock_in = MIN(1.0, lock_in + 0.01)
            WHERE from_cluster = ? AND to_cluster = ? AND relationship = ?
        """, (from_cluster, to_cluster, relationship))
        
        conn.commit()
        conn.close()
    
    def get_edges_from(self, cluster_id: str) -> List[ClusterEdge]:
        """Get all edges originating from a cluster."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM cluster_edges 
            WHERE from_cluster = ?
            ORDER BY lock_in DESC
        """, (cluster_id,))
        
        edges = [ClusterEdge(**dict(row)) for row in cursor.fetchall()]
        conn.close()
        
        return edges
    
    def get_connected_clusters(
        self, 
        cluster_id: str, 
        min_lock_in: float = 0.0
    ) -> List[Tuple[str, float]]:
        """
        Get clusters connected via high lock-in edges.
        
        Returns:
            List of (cluster_id, edge_lock_in) for connected clusters
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT to_cluster, lock_in FROM cluster_edges 
            WHERE from_cluster = ? AND lock_in >= ?
            ORDER BY lock_in DESC
        """, (cluster_id, min_lock_in))
        
        connected = [(row['to_cluster'], row['lock_in']) for row in cursor.fetchall()]
        conn.close()
        
        return connected
    
    # ==================== READ ====================
    
    def get_cluster(self, cluster_id: str) -> Optional[Cluster]:
        """Retrieve cluster by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM clusters WHERE cluster_id = ?", (cluster_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return Cluster(**dict(row))
    
    def list_clusters(
        self, 
        state: Optional[str] = None,
        min_lock_in: Optional[float] = None,
        limit: int = 100
    ) -> List[Cluster]:
        """
        List clusters with optional filters.
        
        Args:
            state: Filter by state (drifting|fluid|settled|crystallized)
            min_lock_in: Minimum lock-in threshold
            limit: Max results
        
        Returns:
            List of Cluster objects, sorted by lock_in DESC
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        query = "SELECT * FROM clusters WHERE 1=1"
        params = []
        
        if state:
            query += " AND state = ?"
            params.append(state)
        
        if min_lock_in is not None:
            query += " AND lock_in >= ?"
            params.append(min_lock_in)
        
        query += " ORDER BY lock_in DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        
        clusters = [Cluster(**dict(row)) for row in cursor.fetchall()]
        conn.close()
        
        return clusters
    
    # ==================== UPDATE ====================
    
    def update_lock_in(self, cluster_id: str, new_lock_in: float) -> None:
        """
        Update cluster lock-in strength.
        
        Automatically updates state based on thresholds.
        """
        # Clamp to [0.0, 1.0]
        new_lock_in = max(0.0, min(1.0, new_lock_in))
        state = get_state_from_lock_in(new_lock_in)
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE clusters 
            SET lock_in = ?,
                state = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE cluster_id = ?
        """, (new_lock_in, state, cluster_id))
        
        conn.commit()
        conn.close()
    
    def record_access(self, cluster_id: str) -> None:
        """
        Record that a cluster was accessed.
        
        Used for lock-in calculation (access frequency component).
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE clusters 
            SET access_count = access_count + 1,
                last_accessed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE cluster_id = ?
        """, (cluster_id,))
        
        conn.commit()
        conn.close()
    
    def update_summary(self, cluster_id: str, summary: str) -> None:
        """Update cluster summary (for caching)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE clusters 
            SET summary = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE cluster_id = ?
        """, (summary, cluster_id))
        
        conn.commit()
        conn.close()
    
    def update_centroid(self, cluster_id: str, centroid: bytes) -> None:
        """Update cluster centroid embedding."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE clusters 
            SET centroid_embedding = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE cluster_id = ?
        """, (centroid, cluster_id))
        
        conn.commit()
        conn.close()
    
    # ==================== DELETE ====================
    
    def delete_cluster(self, cluster_id: str) -> None:
        """
        Delete a cluster.
        
        CASCADE will automatically remove members and edges.
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM clusters WHERE cluster_id = ?", (cluster_id,))
        
        conn.commit()
        conn.close()
    
    # ==================== STATS ====================
    
    def get_stats(self) -> dict:
        """Get Memory Economy statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # Cluster counts by state
        cursor.execute("""
            SELECT state, COUNT(*) as count 
            FROM clusters 
            GROUP BY state
        """)
        state_counts = {row['state']: row['count'] for row in cursor.fetchall()}
        
        # Total clusters
        cursor.execute("SELECT COUNT(*) as total FROM clusters")
        total_clusters = cursor.fetchone()['total']
        
        # Average lock-in
        cursor.execute("SELECT AVG(lock_in) as avg FROM clusters")
        avg_lock_in = cursor.fetchone()['avg'] or 0.0
        
        # Total edges
        cursor.execute("SELECT COUNT(*) as total FROM cluster_edges")
        total_edges = cursor.fetchone()['total']
        
        conn.close()
        
        return {
            'total_clusters': total_clusters,
            'state_distribution': state_counts,
            'avg_lock_in': round(avg_lock_in, 3),
            'total_edges': total_edges,
        }
```

---

## Test Script

Create `scripts/test_clusters.py`:

```python
#!/usr/bin/env python3
"""Test ClusterManager CRUD operations."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from luna.memory.cluster_manager import ClusterManager

def test_crud():
    db_path = Path(__file__).parent.parent / "data" / "luna_engine.db"
    mgr = ClusterManager(str(db_path))
    
    print("=== Testing ClusterManager ===\n")
    
    # CREATE
    print("1. Creating test cluster...")
    cluster_id = mgr.create_cluster(
        name="Test: Actor Model Decisions",
        summary="Testing cluster CRUD operations",
        initial_lock_in=0.5
    )
    print(f"   Created: {cluster_id}")
    
    # READ
    print("\n2. Reading cluster...")
    cluster = mgr.get_cluster(cluster_id)
    print(f"   Name: {cluster.name}")
    print(f"   State: {cluster.state}")
    print(f"   Lock-in: {cluster.lock_in}")
    
    # UPDATE lock-in
    print("\n3. Updating lock-in to 0.75...")
    mgr.update_lock_in(cluster_id, 0.75)
    cluster = mgr.get_cluster(cluster_id)
    print(f"   New state: {cluster.state}")  # Should be "settled"
    print(f"   New lock-in: {cluster.lock_in}")
    
    # Record access
    print("\n4. Recording access...")
    mgr.record_access(cluster_id)
    cluster = mgr.get_cluster(cluster_id)
    print(f"   Access count: {cluster.access_count}")
    
    # LIST
    print("\n5. Listing all clusters...")
    all_clusters = mgr.list_clusters(limit=5)
    print(f"   Total: {len(all_clusters)}")
    for c in all_clusters[:3]:
        print(f"   - {c.name} ({c.state}, {c.lock_in:.2f})")
    
    # STATS
    print("\n6. Getting stats...")
    stats = mgr.get_stats()
    print(f"   {stats}")
    
    # DELETE
    print("\n7. Deleting test cluster...")
    mgr.delete_cluster(cluster_id)
    deleted = mgr.get_cluster(cluster_id)
    print(f"   Deleted: {deleted is None}")
    
    print("\n✅ All CRUD operations working!")

if __name__ == "__main__":
    test_crud()
```

---

## Validation

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python scripts/test_clusters.py
```

Expected output:
```
=== Testing ClusterManager ===

1. Creating test cluster...
   Created: <uuid>

2. Reading cluster...
   Name: Test: Actor Model Decisions
   State: fluid
   Lock-in: 0.5

3. Updating lock-in to 0.75...
   New state: settled
   New lock-in: 0.75

4. Recording access...
   Access count: 1

5. Listing all clusters...
   Total: 1
   - Test: Actor Model Decisions (settled, 0.75)

6. Getting stats...
   {'total_clusters': 1, 'state_distribution': {'settled': 1}, ...}

7. Deleting test cluster...
   Deleted: True

✅ All CRUD operations working!
```

---

## Success Criteria

- [ ] ClusterManager class created
- [ ] All CRUD methods work
- [ ] State transitions based on lock-in thresholds
- [ ] Edge operations work
- [ ] Stats method returns valid data
- [ ] Test script passes

---

## Interface Contract

Other agents MUST use these methods:

| Method | Used By |
|--------|---------|
| `create_cluster()` | ClusteringEngine |
| `add_member()` | ClusteringEngine |
| `get_cluster()` | Librarian, LockInService |
| `list_clusters()` | LockInService, Integration |
| `update_lock_in()` | LockInService |
| `record_access()` | Librarian |
| `get_connected_clusters()` | Librarian (multi-hop) |
