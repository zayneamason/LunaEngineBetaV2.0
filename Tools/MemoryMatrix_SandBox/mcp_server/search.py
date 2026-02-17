"""Search implementations: FTS5, vector (sqlite-vec), hybrid (RRF fusion)."""

import time
from .event_bus import MemoryEvent
from .embeddings import get_embedder, vector_to_blob
from .config import RetrievalParams

if __name__ != "__main__":
    from .sandbox_matrix import SandboxMatrix


async def search_fts5(
    matrix: "SandboxMatrix", query: str, params: RetrievalParams
) -> list[dict]:
    """FTS5 keyword search. Returns scored results."""
    t0 = time.time()
    # FTS5 match query — escape special chars
    fts_query = " OR ".join(query.split())
    cursor = await matrix.execute(
        "SELECT n.*, bm25(nodes_fts) as score "
        "FROM nodes_fts fts "
        "JOIN nodes n ON n.rowid = fts.rowid "
        "WHERE nodes_fts MATCH ? "
        "ORDER BY score "
        "LIMIT ?",
        (fts_query, params.fts5_limit),
    )
    rows = await cursor.fetchall()
    results = [
        {"node": dict(r), "score": abs(r["score"]), "method": "fts5"}
        for r in rows
    ]
    elapsed = time.time() - t0

    await matrix.bus.emit(MemoryEvent(
        type="search_fts5_done",
        actor="search",
        payload={
            "query": query,
            "result_count": len(results),
            "elapsed_ms": round(elapsed * 1000, 2),
            "top_ids": [r["node"]["id"] for r in results[:5]],
        },
    ))
    return results


async def search_vector(
    matrix: "SandboxMatrix", query: str, params: RetrievalParams
) -> list[dict]:
    """sqlite-vec cosine similarity search."""
    t0 = time.time()
    embedder = get_embedder()
    query_vec = embedder.encode(query)
    query_blob = vector_to_blob(query_vec)

    cursor = await matrix.execute(
        "SELECT node_id, distance "
        "FROM node_embeddings "
        "WHERE embedding MATCH ? AND k = ?",
        (query_blob, params.vector_limit),
    )
    vec_rows = await cursor.fetchall()

    results = []
    for r in vec_rows:
        node = await matrix.get_node(r["node_id"])
        if node:
            # L2 distance → cosine similarity for unit vectors: cos = 1 - d²/2
            dist = r["distance"]
            similarity = 1.0 - (dist * dist) / 2.0
            if similarity >= params.sim_threshold:
                results.append({
                    "node": node,
                    "score": similarity,
                    "method": "vector",
                })
    elapsed = time.time() - t0

    await matrix.bus.emit(MemoryEvent(
        type="search_vector_done",
        actor="search",
        payload={
            "query": query,
            "result_count": len(results),
            "elapsed_ms": round(elapsed * 1000, 2),
            "top_ids": [r["node"]["id"] for r in results[:5]],
        },
    ))
    return results


async def search_hybrid(
    matrix: "SandboxMatrix", query: str, params: RetrievalParams
) -> list[dict]:
    """Hybrid search: FTS5 + vector with Reciprocal Rank Fusion (RRF)."""
    t0 = time.time()
    fts_results = await search_fts5(matrix, query, params)
    vec_results = await search_vector(matrix, query, params)

    # RRF: score(d) = Σ 1/(k + rank_i)
    k = params.rrf_k
    rrf_scores: dict[str, float] = {}
    rrf_nodes: dict[str, dict] = {}

    for rank, r in enumerate(fts_results, start=1):
        nid = r["node"]["id"]
        rrf_scores[nid] = rrf_scores.get(nid, 0.0) + 1.0 / (k + rank)
        rrf_nodes[nid] = r["node"]

    for rank, r in enumerate(vec_results, start=1):
        nid = r["node"]["id"]
        rrf_scores[nid] = rrf_scores.get(nid, 0.0) + 1.0 / (k + rank)
        rrf_nodes[nid] = r["node"]

    # Sort by fused score
    sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)
    results = [
        {"node": rrf_nodes[nid], "score": rrf_scores[nid], "method": "hybrid"}
        for nid in sorted_ids
    ]
    elapsed = time.time() - t0

    await matrix.bus.emit(MemoryEvent(
        type="search_fusion_done",
        actor="search",
        payload={
            "query": query,
            "fts5_count": len(fts_results),
            "vector_count": len(vec_results),
            "fused_count": len(results),
            "elapsed_ms": round(elapsed * 1000, 2),
            "top_ids": [r["node"]["id"] for r in results[:5]],
        },
    ))
    return results
