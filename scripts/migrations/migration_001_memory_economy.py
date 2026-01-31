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

    # CLUSTERS TABLE
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

    # CLUSTER_MEMBERS TABLE
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

    # CLUSTER_EDGES TABLE
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

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name IN ('clusters', 'cluster_members', 'cluster_edges')
    """)
    tables = [row[0] for row in cursor.fetchall()]

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
    db_path = Path(__file__).parent.parent / "data" / "luna_engine.db"

    if len(sys.argv) > 1:
        db_path = Path(sys.argv[1])

    if not db_path.exists():
        print(f"❌ Database not found: {db_path}")
        sys.exit(1)

    # Run migration with force=True to avoid interactive prompt
    success = migrate(str(db_path), force=True)

    if success:
        verify(str(db_path))
