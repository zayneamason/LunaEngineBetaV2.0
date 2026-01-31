# Agent A1: Schema Agent

**Task:** Create Memory Economy database tables  
**Dependencies:** None (runs first)  
**Outputs:** 3 tables + 8 indexes in luna_engine.db  
**Estimated Time:** 15 minutes

---

## Objective

Add three tables to the existing Memory Matrix database:
- `clusters` - Semantic groupings
- `cluster_members` - Node membership
- `cluster_edges` - Inter-cluster relationships

---

## Database Location

```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/data/luna_engine.db
```

---

## Implementation

Create `scripts/migration_001_memory_economy.py`:

```python
#!/usr/bin/env python3
"""
Memory Economy Migration - Add cluster tables to Luna Engine database.

Run: python scripts/migration_001_memory_economy.py
"""

import sqlite3
from pathlib import Path
import sys

def migrate(db_path: str, force: bool = False):
    """Add Memory Economy tables to existing database."""
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print(f"Database: {db_path}")
    print("Starting Memory Economy migration...")
    
    # Check if tables already exist
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name IN ('clusters', 'cluster_members', 'cluster_edges')
    """)
    existing = [row[0] for row in cursor.fetchall()]
    
    if existing:
        print(f"⚠️  Tables already exist: {existing}")
        if not force:
            response = input("Drop and recreate? (yes/no): ")
            if response.lower() != 'yes':
                print("Migration aborted.")
                conn.close()
                return False
        
        for table in ['cluster_edges', 'cluster_members', 'clusters']:
            if table in existing:
                cursor.execute(f"DROP TABLE {table}")
                print(f"  Dropped {table}")
    
    # ==================== CLUSTERS TABLE ====================
    cursor.execute("""
        CREATE TABLE clusters (
            cluster_id TEXT PRIMARY KEY,
            name TEXT,
            summary TEXT,
            lock_in REAL DEFAULT 0.0,
            state TEXT DEFAULT 'drifting',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_accessed_at TEXT,
            access_count INTEGER DEFAULT 0,
            member_count INTEGER DEFAULT 0,
            avg_node_lock_in REAL DEFAULT 0.0,
            centroid_embedding BLOB
        )
    """)
    
    cursor.execute("CREATE INDEX idx_clusters_lock_in ON clusters(lock_in DESC)")
    cursor.execute("CREATE INDEX idx_clusters_state ON clusters(state)")
    cursor.execute("CREATE INDEX idx_clusters_updated ON clusters(updated_at DESC)")
    
    print("✅ Created clusters table (3 indexes)")
    
    # ==================== CLUSTER_MEMBERS TABLE ====================
    cursor.execute("""
        CREATE TABLE cluster_members (
            cluster_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            membership_strength REAL DEFAULT 1.0,
            added_at TEXT DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (cluster_id, node_id),
            FOREIGN KEY (cluster_id) REFERENCES clusters(cluster_id) ON DELETE CASCADE,
            FOREIGN KEY (node_id) REFERENCES memory_nodes(id) ON DELETE CASCADE
        )
    """)
    
    cursor.execute("CREATE INDEX idx_cluster_members_node ON cluster_members(node_id)")
    cursor.execute("CREATE INDEX idx_cluster_members_strength ON cluster_members(membership_strength DESC)")
    
    print("✅ Created cluster_members table (2 indexes)")
    
    # ==================== CLUSTER_EDGES TABLE ====================
    cursor.execute("""
        CREATE TABLE cluster_edges (
            from_cluster TEXT NOT NULL,
            to_cluster TEXT NOT NULL,
            relationship TEXT NOT NULL,
            strength REAL DEFAULT 0.5,
            lock_in REAL DEFAULT 0.15,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_reinforced_at TEXT,
            reinforcement_count INTEGER DEFAULT 0,
            PRIMARY KEY (from_cluster, to_cluster, relationship),
            FOREIGN KEY (from_cluster) REFERENCES clusters(cluster_id) ON DELETE CASCADE,
            FOREIGN KEY (to_cluster) REFERENCES clusters(cluster_id) ON DELETE CASCADE
        )
    """)
    
    cursor.execute("CREATE INDEX idx_cluster_edges_from ON cluster_edges(from_cluster)")
    cursor.execute("CREATE INDEX idx_cluster_edges_to ON cluster_edges(to_cluster)")
    cursor.execute("CREATE INDEX idx_cluster_edges_strength ON cluster_edges(strength DESC)")
    
    print("✅ Created cluster_edges table (3 indexes)")
    
    # Commit changes
    conn.commit()
    conn.close()
    
    print("\n✅ Memory Economy migration complete!")
    print("   - 3 tables created")
    print("   - 8 indexes created")
    print("   - CASCADE deletes configured")
    
    return True

def verify(db_path: str) -> bool:
    """Verify migration was successful."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name IN ('clusters', 'cluster_members', 'cluster_edges')
    """)
    tables = [row[0] for row in cursor.fetchall()]
    
    # Check indexes
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='index' AND name LIKE 'idx_cluster%'
    """)
    indexes = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    
    print("\n=== Verification ===")
    print(f"Tables: {tables}")
    print(f"Indexes: {indexes}")
    
    success = len(tables) == 3 and len(indexes) == 8
    print(f"Status: {'✅ PASS' if success else '❌ FAIL'}")
    
    return success

if __name__ == "__main__":
    # Default database path
    db_path = Path(__file__).parent.parent / "data" / "luna_engine.db"
    
    # Allow override via command line
    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])
    
    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)
    
    # Run migration
    success = migrate(str(db_path))
    
    if success:
        verify(str(db_path))
```

---

## Validation

After running migration:

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python scripts/migration_001_memory_economy.py

# Verify tables exist
sqlite3 data/luna_engine.db ".tables" | grep -E "cluster"

# Expected output:
# cluster_edges    cluster_members  clusters
```

---

## Schema Reference

### clusters

| Column | Type | Notes |
|--------|------|-------|
| cluster_id | TEXT | UUID v4, PRIMARY KEY |
| name | TEXT | Human-readable label |
| summary | TEXT | Pre-computed for fast retrieval |
| lock_in | REAL | 0.0-1.0, persistence strength |
| state | TEXT | drifting\|fluid\|settled\|crystallized |
| created_at | TEXT | ISO timestamp |
| updated_at | TEXT | ISO timestamp |
| last_accessed_at | TEXT | For decay calculation |
| access_count | INTEGER | Usage tracking |
| member_count | INTEGER | Cached count |
| avg_node_lock_in | REAL | Average member lock-in |
| centroid_embedding | BLOB | sqlite-vec vector |

### cluster_members

| Column | Type | Notes |
|--------|------|-------|
| cluster_id | TEXT | FK → clusters |
| node_id | TEXT | FK → memory_nodes |
| membership_strength | REAL | 0.0-1.0 |
| added_at | TEXT | ISO timestamp |

### cluster_edges

| Column | Type | Notes |
|--------|------|-------|
| from_cluster | TEXT | FK → clusters |
| to_cluster | TEXT | FK → clusters |
| relationship | TEXT | related_to, enables, etc. |
| strength | REAL | 0.0-1.0 |
| lock_in | REAL | Edge persistence (0.0-1.0) |
| created_at | TEXT | ISO timestamp |
| last_reinforced_at | TEXT | For decay |
| reinforcement_count | INTEGER | Usage count |

---

## Success Criteria

- [ ] Migration runs without errors
- [ ] 3 tables created
- [ ] 8 indexes created
- [ ] CASCADE deletes work (test: create cluster, delete it, verify members gone)
- [ ] Foreign keys reference correct parent tables

---

## Notes

- Uses `memory_nodes` table (existing) as FK target for node_id
- Edge lock_in (0.15 default) matches existing system
- Cluster state defaults to 'drifting' (lowest persistence)
