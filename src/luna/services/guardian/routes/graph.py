"""Knowledge graph routes — serve graph visualization data."""

import json
from pathlib import Path
from fastapi import APIRouter

router = APIRouter()

GRAPH_DIR = Path("data/guardian/org_timeline")


@router.get("/graph")
async def get_knowledge_graph():
    """Get full knowledge graph (nodes + edges for Observatory)."""
    path = GRAPH_DIR / "knowledge_graph.json"
    if not path.exists():
        return {"nodes": [], "edges": [], "entity_nodes": [], "entity_edges": []}
    with open(path) as f:
        return json.load(f)
