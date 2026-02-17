"""MCP tool implementations — 10 tools for Observatory Sandbox."""

import time
from .sandbox_matrix import SandboxMatrix
from .search import search_fts5, search_vector, search_hybrid
from .activation import spreading_activation
from .lock_in import recompute_all_lock_ins
from .clusters import assemble_constellation
from .config import RetrievalParams


async def tool_sandbox_reset(matrix: SandboxMatrix) -> dict:
    """Wipe the sandbox database completely."""
    await matrix.reset()
    return {"status": "ok", "message": "Sandbox fully reset. All data cleared."}


async def tool_sandbox_seed(matrix: SandboxMatrix, preset: str) -> dict:
    """Load a preset dataset. Resets first."""
    await matrix.seed(preset)
    stats = await matrix.stats()
    return {
        "status": "ok",
        "preset": preset,
        "loaded": stats,
    }


async def tool_sandbox_add_node(
    matrix: SandboxMatrix,
    type: str,
    content: str,
    confidence: float = 1.0,
    tags: list[str] | None = None,
) -> dict:
    """Create a new memory node with embedding."""
    node_id = await matrix.add_node(type=type, content=content, confidence=confidence, tags=tags)
    node = await matrix.get_node(node_id)
    return {"status": "ok", "node": node}


async def tool_sandbox_add_edge(
    matrix: SandboxMatrix,
    from_id: str,
    to_id: str,
    relationship: str,
    strength: float = 1.0,
) -> dict:
    """Create an edge between two nodes."""
    edge_id = await matrix.add_edge(from_id=from_id, to_id=to_id, relationship=relationship, strength=strength)
    return {"status": "ok", "edge_id": edge_id}


async def tool_sandbox_search(
    matrix: SandboxMatrix,
    query: str,
    method: str = "hybrid",
    params: RetrievalParams | None = None,
) -> dict:
    """Search the sandbox. Methods: fts5, vector, hybrid, all."""
    p = params or RetrievalParams.load()
    results = {}

    if method in ("fts5", "all"):
        results["fts5"] = await search_fts5(matrix, query, p)
    if method in ("vector", "all"):
        results["vector"] = await search_vector(matrix, query, p)
    if method in ("hybrid", "all"):
        results["hybrid"] = await search_hybrid(matrix, query, p)

    # Flatten for single-method queries
    if method != "all" and method in results:
        return {
            "query": query,
            "method": method,
            "results": results[method],
            "count": len(results[method]),
        }

    return {
        "query": query,
        "method": "all",
        "results": results,
        "counts": {k: len(v) for k, v in results.items()},
    }


async def tool_sandbox_recall(
    matrix: SandboxMatrix, query: str, params: RetrievalParams | None = None
) -> dict:
    """Full retrieval pipeline: search → activate → assemble constellation."""
    p = params or RetrievalParams.load()

    # 1. Hybrid search
    search_results = await search_hybrid(matrix, query, p)

    # 2. Record access for top results
    seed_ids = [r["node"]["id"] for r in search_results[:10]]
    for sid in seed_ids:
        await matrix.record_access(sid)

    # 3. Spreading activation from search hits
    activated = await spreading_activation(matrix, seed_ids, p)

    # 4. Assemble constellation within token budget
    constellation = await assemble_constellation(matrix, activated, p)

    return {
        "query": query,
        "search_hits": len(search_results),
        "activated": len(activated),
        "constellation": constellation,
    }


async def tool_sandbox_replay(
    matrix: SandboxMatrix, query: str, params: RetrievalParams | None = None
) -> dict:
    """Full pipeline with detailed trace of every phase."""
    p = params or RetrievalParams.load()
    phases = []

    # Phase 1: FTS5
    t0 = time.time()
    fts_results = await search_fts5(matrix, query, p)
    phases.append({
        "phase": "fts5",
        "elapsed_ms": round((time.time() - t0) * 1000, 2),
        "result_count": len(fts_results),
        "results": [{"id": r["node"]["id"], "score": r["score"], "content": r["node"]["content"][:80]} for r in fts_results],
    })

    # Phase 2: Vector
    t0 = time.time()
    vec_results = await search_vector(matrix, query, p)
    phases.append({
        "phase": "vector",
        "elapsed_ms": round((time.time() - t0) * 1000, 2),
        "result_count": len(vec_results),
        "results": [{"id": r["node"]["id"], "score": round(r["score"], 4), "content": r["node"]["content"][:80]} for r in vec_results],
    })

    # Phase 3: RRF Fusion
    t0 = time.time()
    hybrid_results = await search_hybrid(matrix, query, p)
    phases.append({
        "phase": "fusion",
        "elapsed_ms": round((time.time() - t0) * 1000, 2),
        "result_count": len(hybrid_results),
        "results": [{"id": r["node"]["id"], "score": round(r["score"], 6), "content": r["node"]["content"][:80]} for r in hybrid_results],
    })

    # Phase 4: Spreading Activation
    seed_ids = [r["node"]["id"] for r in hybrid_results[:10]]
    t0 = time.time()
    activated = await spreading_activation(matrix, seed_ids, p)
    phases.append({
        "phase": "activation",
        "elapsed_ms": round((time.time() - t0) * 1000, 2),
        "seed_count": len(seed_ids),
        "activated_count": len(activated),
        "results": [
            {"id": r["node_id"], "activation": round(r["activation"], 4), "hop": r["hop"]}
            for r in activated[:20]
        ],
    })

    # Phase 5: Constellation Assembly
    t0 = time.time()
    constellation = await assemble_constellation(matrix, activated, p)
    phases.append({
        "phase": "assembly",
        "elapsed_ms": round((time.time() - t0) * 1000, 2),
        "selected_count": len(constellation["nodes"]),
        "clusters_hit": constellation["clusters_hit"],
        "tokens_used": constellation["total_tokens"],
        "budget_pct": constellation["budget_used"],
        "dropped": constellation["dropped"],
    })

    return {
        "query": query,
        "phases": phases,
        "params": p.to_dict(),
    }


async def tool_sandbox_graph_dump(
    matrix: SandboxMatrix, limit: int = 500, min_lock_in: float = 0.0
) -> dict:
    """Full graph snapshot for frontend visualization."""
    return await matrix.graph_dump(limit=limit, min_lock_in=min_lock_in)


async def tool_sandbox_stats(matrix: SandboxMatrix) -> dict:
    """Database statistics."""
    return await matrix.stats()


async def tool_sandbox_tune(
    matrix: SandboxMatrix, param: str, value: float
) -> dict:
    """Adjust a retrieval parameter. Persists to sandbox_config.json."""
    p = RetrievalParams.load()
    if not hasattr(p, param):
        return {
            "status": "error",
            "message": f"Unknown param '{param}'. Valid: {list(p.to_dict().keys())}",
        }
    setattr(p, param, type(getattr(p, param))(value))
    p.save()
    return {
        "status": "ok",
        "param": param,
        "new_value": getattr(p, param),
        "all_params": p.to_dict(),
    }


async def tool_sandbox_import(
    matrix: SandboxMatrix, snapshot_path: str
) -> dict:
    """Import a JSON snapshot (e.g., from Luna Hub production export)."""
    from pathlib import Path
    path = Path(snapshot_path)
    if not path.exists():
        return {"status": "error", "message": f"File not found: {snapshot_path}"}

    import json
    data = json.loads(path.read_text())
    await matrix.seed.__wrapped__(matrix, "")  # Won't work — use reset + manual load
    # Actually, just reset and load the data directly
    await matrix.reset()

    for n in data.get("nodes", []):
        await matrix.add_node(
            type=n.get("type", "UNKNOWN"),
            content=n.get("content", ""),
            confidence=n.get("confidence", 1.0),
            tags=n.get("tags", []),
            node_id=n.get("id"),
        )
    for e in data.get("edges", []):
        await matrix.add_edge(
            from_id=e["from_id"],
            to_id=e["to_id"],
            relationship=e.get("relationship", "RELATED_TO"),
            strength=e.get("strength", 1.0),
        )

    stats = await matrix.stats()
    return {"status": "ok", "imported": stats}


# ── ENTITY & QUEST TOOLS ─────────────────────────────────────────


async def tool_sandbox_add_entity(
    matrix: SandboxMatrix,
    type: str,
    name: str,
    profile: str | None = None,
    aliases: list[str] | None = None,
    avatar: str = "",
    core_facts: dict | None = None,
    voice_config: dict | None = None,
) -> dict:
    """Create a new entity (person, persona, place, project)."""
    entity_id = await matrix.add_entity(
        type=type,
        name=name,
        profile=profile,
        aliases=aliases,
        avatar=avatar,
        core_facts=core_facts,
        voice_config=voice_config,
    )
    entity = await matrix.get_entity(entity_id)
    return {"status": "ok", "entity": entity}


async def tool_sandbox_add_entity_relationship(
    matrix: SandboxMatrix,
    from_id: str,
    to_id: str,
    rel_type: str,
    strength: float = 1.0,
    context: str | None = None,
) -> dict:
    """Create a relationship between two entities."""
    rel_id = await matrix.add_entity_relationship(
        from_id=from_id,
        to_id=to_id,
        rel_type=rel_type,
        strength=strength,
        context=context,
    )
    return {"status": "ok", "rel_id": rel_id}


async def tool_sandbox_link_mention(
    matrix: SandboxMatrix,
    entity_id: str,
    node_id: str,
    mention_type: str = "reference",
) -> dict:
    """Link a knowledge node to an entity."""
    mention_id = await matrix.link_mention(
        entity_id=entity_id,
        node_id=node_id,
        mention_type=mention_type,
    )
    # Get updated entity with new mention count
    entity = await matrix.get_entity(entity_id)
    return {"status": "ok", "mention_id": mention_id, "entity": entity}


async def tool_sandbox_maintenance_sweep(matrix: SandboxMatrix) -> dict:
    """Run maintenance sweep to generate quest candidates from graph health analysis."""
    from .maintenance import maintenance_sweep

    candidates = await maintenance_sweep(matrix)

    # Create quests from candidates
    created_quests = []
    for candidate in candidates:
        quest_id = await matrix.create_quest(
            quest_type=candidate["quest_type"],
            title=candidate["title"],
            objective=candidate["objective"],
            priority=candidate["priority"],
            subtitle=candidate.get("subtitle"),
            source=candidate.get("source"),
            journal_prompt=candidate.get("journal_prompt"),
            target_entities=candidate.get("target_entities"),
            target_nodes=candidate.get("target_nodes"),
            target_clusters=candidate.get("target_clusters"),
        )
        created_quests.append(await matrix.get_quest(quest_id))

    return {
        "status": "ok",
        "candidates_found": len(candidates),
        "quests_created": len(created_quests),
        "quests": created_quests,
    }


async def tool_sandbox_quest_accept(matrix: SandboxMatrix, quest_id: str) -> dict:
    """Accept a quest (mark as active)."""
    quest = await matrix.accept_quest(quest_id)
    return {"status": "ok", "quest": quest}


async def tool_sandbox_quest_complete(
    matrix: SandboxMatrix,
    quest_id: str,
    journal_text: str | None = None,
    themes: list[str] | None = None,
) -> dict:
    """Complete a quest, optionally with journal reflection."""
    result = await matrix.complete_quest(
        quest_id=quest_id,
        journal_text=journal_text,
        themes=themes,
    )
    return {"status": "ok", **result}


async def tool_sandbox_quest_list(
    matrix: SandboxMatrix,
    status: str | None = None,
    quest_type: str | None = None,
) -> dict:
    """List quests with optional filters."""
    quests = await matrix.list_quests(status=status, quest_type=quest_type)
    return {
        "status": "ok",
        "count": len(quests),
        "quests": quests,
    }
