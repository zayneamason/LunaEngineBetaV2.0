"""Cluster centroid layout pre-computation using NetworkX spring_layout."""

import sqlite3
from pathlib import Path

import networkx as nx

_layout_cache: dict[str, dict] | None = None
_cache_db_path: str | None = None


def invalidate_cache():
    """Clear the cached layout so it's recomputed on next call."""
    global _layout_cache, _cache_db_path
    _layout_cache = None
    _cache_db_path = None


def compute_cluster_layout(db_path: str, table_names: dict | None = None) -> dict[str, dict]:
    """
    Build a cluster adjacency graph and run spring_layout to get stable (x, y)
    positions for each cluster centroid.

    Args:
        db_path: Path to the SQLite database.
        table_names: Optional dict with keys 'nodes', 'edges', 'type_col'
                     for production DB compatibility. Defaults to sandbox names.

    Returns:
        dict mapping cluster_id -> {x, y, node_count, avg_lock_in, label, state, top_types}
    """
    global _layout_cache, _cache_db_path

    # Return cache if valid
    if _layout_cache is not None and _cache_db_path == db_path:
        return _layout_cache

    tn = table_names or {"nodes": "nodes", "edges": "edges", "type_col": "type"}
    nodes_table = tn["nodes"]
    edges_table = tn["edges"]
    type_col = tn["type_col"]

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Check if clusters table exists
    has_clusters = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='clusters'"
    ).fetchone()

    if not has_clusters:
        conn.close()
        _layout_cache = {}
        _cache_db_path = db_path
        return _layout_cache

    # Detect cluster PK column name (sandbox: 'id', production: 'cluster_id')
    cluster_cols = {r[1] for r in conn.execute("PRAGMA table_info(clusters)").fetchall()}
    cluster_pk = "cluster_id" if "cluster_id" in cluster_cols else "id"

    # Get clusters with member counts, avg lock_in, and type distribution
    clusters = conn.execute("""
        SELECT c.{cpk} as id, c.name, c.lock_in, c.state,
               COUNT(cm.node_id) as node_count,
               COALESCE(AVG(n.lock_in), 0) as avg_lock_in
        FROM clusters c
        LEFT JOIN cluster_members cm ON c.{cpk} = cm.cluster_id
        LEFT JOIN {nodes} n ON cm.node_id = n.id
        GROUP BY c.{cpk}
    """.format(nodes=nodes_table, cpk=cluster_pk)).fetchall()

    if not clusters:
        conn.close()
        _layout_cache = {}
        _cache_db_path = db_path
        return _layout_cache

    # Build cluster graph
    G = nx.Graph()
    for c in clusters:
        G.add_node(c["id"], label=c["name"], node_count=c["node_count"],
                   avg_lock_in=round(c["avg_lock_in"], 3), lock_in=c["lock_in"],
                   state=c["state"])

    # Per-cluster type distribution
    type_dist = {}
    for c in clusters:
        rows = conn.execute("""
            SELECT n.{type_col} as ntype, COUNT(*) as cnt
            FROM cluster_members cm
            JOIN {nodes} n ON cm.node_id = n.id
            WHERE cm.cluster_id = ?
            GROUP BY n.{type_col}
        """.format(nodes=nodes_table, type_col=type_col), (c["id"],)).fetchall()
        type_dist[c["id"]] = {r["ntype"]: r["cnt"] for r in rows}

    # Inter-cluster edges (count edges between clusters via cluster_members join)
    inter_edges = conn.execute("""
        SELECT cm1.cluster_id as c1, cm2.cluster_id as c2, COUNT(*) as weight
        FROM {edges} e
        JOIN cluster_members cm1 ON e.from_id = cm1.node_id
        JOIN cluster_members cm2 ON e.to_id = cm2.node_id
        WHERE cm1.cluster_id != cm2.cluster_id
        GROUP BY cm1.cluster_id, cm2.cluster_id
    """.format(edges=edges_table)).fetchall()

    for row in inter_edges:
        if G.has_node(row["c1"]) and G.has_node(row["c2"]):
            G.add_edge(row["c1"], row["c2"], weight=row["weight"])

    conn.close()

    if len(G.nodes) == 0:
        _layout_cache = {}
        _cache_db_path = db_path
        return _layout_cache

    # Spring layout — deterministic seed for stability
    pos = nx.spring_layout(G, k=2.0, iterations=100, seed=42, weight="weight")

    # Scale to [-500, 500] range
    result = {}
    for cid, (x, y) in pos.items():
        data = G.nodes[cid]
        # Collect inter-cluster edge list for this cluster
        inter = []
        for neighbor in G.neighbors(cid):
            edge_data = G.edges[cid, neighbor]
            inter.append({"target_cluster": neighbor, "weight": edge_data.get("weight", 1)})

        result[cid] = {
            "x": round(x * 500, 1),
            "y": round(y * 500, 1),
            "node_count": data.get("node_count", 0),
            "avg_lock_in": data.get("avg_lock_in", 0),
            "lock_in": data.get("lock_in", 0),
            "state": data.get("state", "drifting"),
            "label": data.get("label", cid),
            "top_types": type_dist.get(cid, {}),
            "inter_cluster_edges": inter,
        }

    _layout_cache = result
    _cache_db_path = db_path
    return _layout_cache
