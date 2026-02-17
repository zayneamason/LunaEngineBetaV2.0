"""Auto-clustering for production DB using Louvain community detection."""

import sqlite3
import uuid
from datetime import datetime, timezone


def ensure_cluster_tables(db_path: str, nodes_table: str = "memory_nodes"):
    """
    Create clusters + cluster_members tables if they don't exist.
    Adds cluster_id column to nodes_table if missing.
    Idempotent — safe to call multiple times.
    """
    conn = sqlite3.connect(db_path)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS clusters (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            lock_in REAL DEFAULT 0.0,
            state TEXT DEFAULT 'drifting',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS cluster_members (
            cluster_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            PRIMARY KEY (cluster_id, node_id),
            FOREIGN KEY (cluster_id) REFERENCES clusters(id) ON DELETE CASCADE
        )
    """)

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_cluster_members_node ON cluster_members(node_id)"
    )

    # Add cluster_id column to nodes table if missing
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({nodes_table})").fetchall()]
    if "cluster_id" not in cols:
        conn.execute(f"ALTER TABLE {nodes_table} ADD COLUMN cluster_id TEXT")

    conn.commit()
    conn.close()


def needs_auto_cluster(db_path: str) -> bool:
    """Check if auto-clustering is needed (clusters table exists but is empty)."""
    conn = sqlite3.connect(db_path)
    try:
        has_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='clusters'"
        ).fetchone()
        if not has_table:
            return True
        count = conn.execute("SELECT COUNT(*) FROM clusters").fetchone()[0]
        return count == 0
    finally:
        conn.close()


def auto_cluster_from_db(
    db_path: str,
    edges_table: str = "graph_edges",
    nodes_table: str = "memory_nodes",
    resolution: float = 1.0,
    min_community_size: int = 2,
) -> int:
    """
    Run Louvain community detection on the edge graph and create clusters.

    Args:
        db_path: Path to the SQLite database.
        edges_table: Name of the edges table (sandbox: 'edges', production: 'graph_edges').
        nodes_table: Name of the nodes table (sandbox: 'nodes', production: 'memory_nodes').
        resolution: Louvain resolution parameter. Higher = more clusters.
        min_community_size: Minimum members for a community to become a cluster.

    Returns:
        Number of clusters created.
    """
    import networkx as nx
    from networkx.algorithms.community import louvain_communities

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Build graph from edges
    G = nx.Graph()
    edges = conn.execute(
        f"SELECT from_id, to_id, strength FROM {edges_table}"
    ).fetchall()

    for e in edges:
        G.add_edge(e["from_id"], e["to_id"], weight=e["strength"])

    if len(G.nodes) == 0:
        conn.close()
        return 0

    # Run Louvain community detection
    communities = louvain_communities(G, resolution=resolution, seed=42)

    # Sort communities by size (largest first)
    communities = sorted(communities, key=len, reverse=True)

    now = datetime.now(timezone.utc).isoformat()
    cluster_count = 0

    for i, community in enumerate(communities):
        if len(community) < min_community_size:
            continue

        cid = f"auto-{uuid.uuid4().hex[:8]}"

        # Find the hub node (highest degree) for naming
        hub_node = max(community, key=lambda n: G.degree(n))
        # Truncate long hub names
        hub_label = hub_node[:40] if len(hub_node) > 40 else hub_node

        # Compute average lock_in for the community
        placeholders = ",".join("?" for _ in community)
        avg_row = conn.execute(
            f"SELECT COALESCE(AVG(lock_in), 0) FROM {nodes_table} WHERE id IN ({placeholders})",
            list(community),
        ).fetchone()
        avg_lock_in = round(avg_row[0], 3) if avg_row else 0

        # Determine state from avg lock_in
        if avg_lock_in >= 0.85:
            state = "crystallized"
        elif avg_lock_in >= 0.70:
            state = "settled"
        elif avg_lock_in >= 0.20:
            state = "fluid"
        else:
            state = "drifting"

        conn.execute(
            "INSERT OR IGNORE INTO clusters (id, name, lock_in, state, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (cid, f"Community {i} ({hub_label})", avg_lock_in, state, now, now),
        )

        for node_id in community:
            conn.execute(
                "INSERT OR IGNORE INTO cluster_members (cluster_id, node_id) VALUES (?, ?)",
                (cid, node_id),
            )
            conn.execute(
                f"UPDATE {nodes_table} SET cluster_id = ? WHERE id = ?",
                (cid, node_id),
            )

        cluster_count += 1

    conn.commit()
    conn.close()
    return cluster_count
