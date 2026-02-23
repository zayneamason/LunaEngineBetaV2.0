# GUARDIAN SERVICE — Claude Code Integration Spec

## Overview

Integrate Guardian into the Luna Engine as a service, following the exact
pattern established by Kozmo. Guardian becomes a FastAPI router + static
frontend served from the engine. One server, one URL, one tunnel.

**After this work:** `http://127.0.0.1:8000/guardian/` serves the full
Guardian app. Tarcila opens a tunnel URL in her browser and demos it live
while Hai Dai narrates at ROSA.

---

## Architecture (mirrors Kozmo exactly)

```
src/luna/services/guardian/          ← NEW service module
  __init__.py
  routes/
    __init__.py                      ← combines sub-routers, prefix=/guardian/api
    threads.py                       ← GET /guardian/api/threads/:id
    knowledge.py                     ← GET /guardian/api/knowledge/:id
    entities.py                      ← GET /guardian/api/entities
    membrane.py                      ← GET /guardian/api/membrane
    graph.py                         ← GET /guardian/api/graph

data/guardian/                       ← demo data (moved from Eclissi-Guardian/generated/)
  conversations/
    amara_thread.json
    musoke_thread.json
    wasswa_thread.json
    elder_thread.json
  knowledge_nodes/
    facts.json
    insights.json
    decisions.json
    actions.json
    milestones.json
  entities/
    entities_updated.json
    relationships_updated.json
  membrane/
    consent_events.json
    scope_transitions.json
  org_timeline/
    knowledge_graph.json

frontend/guardian/                   ← Guardian frontend (moved from Eclissi-Guardian/frontend/)
  index.html
  css/
  js/
```

---

## Step 1: Copy Demo Data

Copy the fixture files into the engine's data directory.

```bash
# From _HeyLuna_BETA/
cp -r Eclissi-Guardian/generated/ _LunaEngine_BetaProject_V2.0_Root/data/guardian/
```

These are READ-ONLY demo fixtures. The routes serve them as JSON. No database needed for the demo.

---

## Step 2: Create Guardian Service Module

### `src/luna/services/guardian/__init__.py`

```python
"""
Guardian Service — Cultural Knowledge Stewardship Interface

Serves the Guardian demo data and frontend. Follows the Kozmo pattern:
routes registered via include_router, frontend served as static files.
"""
```

### `src/luna/services/guardian/routes/__init__.py`

```python
"""
Guardian Routes Package

Combines sub-routers into a single router for server.py.
Mirrors the Kozmo routes pattern exactly.
"""

from pathlib import Path
from fastapi import APIRouter

# Demo data root
GUARDIAN_DATA_ROOT = Path("data/guardian")

from .threads import router as threads_router
from .knowledge import router as knowledge_router
from .entities import router as entities_router
from .membrane import router as membrane_router
from .graph import router as graph_router

router = APIRouter(prefix="/guardian/api", tags=["guardian"])
router.include_router(threads_router)
router.include_router(knowledge_router)
router.include_router(entities_router)
router.include_router(membrane_router)
router.include_router(graph_router)
```

### `src/luna/services/guardian/routes/threads.py`

```python
"""Thread routes — serve conversation JSON fixtures."""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter()

THREADS_DIR = Path("data/guardian/conversations")

# Thread slug → filename mapping
THREAD_MAP = {
    "amara": "amara_thread.json",
    "musoke": "musoke_thread.json",
    "wasswa": "wasswa_thread.json",
    "elder": "elder_thread.json",
}


@router.get("/threads")
async def list_threads():
    """List available threads."""
    return {
        "threads": [
            {"id": slug, "name": slug.title()}
            for slug in THREAD_MAP.keys()
        ]
    }


@router.get("/threads/{thread_id}")
async def get_thread(thread_id: str):
    """Get thread messages by ID."""
    filename = THREAD_MAP.get(thread_id)
    if not filename:
        raise HTTPException(status_code=404, detail=f"Thread not found: {thread_id}")

    path = THREADS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Thread file missing: {filename}")

    with open(path) as f:
        return json.load(f)
```

### `src/luna/services/guardian/routes/knowledge.py`

```python
"""Knowledge node routes — serve knowledge JSON fixtures."""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter()

KNOWLEDGE_DIR = Path("data/guardian/knowledge_nodes")

# Node type → filename mapping
NODE_FILES = {
    "facts": "facts.json",
    "insights": "insights.json",
    "decisions": "decisions.json",
    "actions": "actions.json",
    "milestones": "milestones.json",
}


@router.get("/knowledge")
async def list_knowledge():
    """Get all knowledge nodes (merged from all type files)."""
    all_nodes = {}
    for node_type, filename in NODE_FILES.items():
        path = KNOWLEDGE_DIR / filename
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                for node in data.get("nodes", []):
                    all_nodes[node["id"]] = node
    return {"nodes": list(all_nodes.values()), "count": len(all_nodes)}


@router.get("/knowledge/{node_id}")
async def get_knowledge_node(node_id: str):
    """Get a single knowledge node by ID."""
    for filename in NODE_FILES.values():
        path = KNOWLEDGE_DIR / filename
        if path.exists():
            with open(path) as f:
                data = json.load(f)
                for node in data.get("nodes", []):
                    if node["id"] == node_id:
                        return node
    raise HTTPException(status_code=404, detail=f"Node not found: {node_id}")
```

### `src/luna/services/guardian/routes/entities.py`

```python
"""Entity routes — serve entity JSON fixtures."""

import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter()

ENTITIES_DIR = Path("data/guardian/entities")


@router.get("/entities")
async def list_entities():
    """Get all entities."""
    path = ENTITIES_DIR / "entities_updated.json"
    if not path.exists():
        return {"entities": []}
    with open(path) as f:
        return json.load(f)


@router.get("/entities/relationships")
async def get_relationships():
    """Get all entity relationships."""
    path = ENTITIES_DIR / "relationships_updated.json"
    if not path.exists():
        return {"relationships": []}
    with open(path) as f:
        return json.load(f)


@router.get("/entities/{entity_id}")
async def get_entity(entity_id: str):
    """Get a single entity by ID."""
    path = ENTITIES_DIR / "entities_updated.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Entities file missing")
    with open(path) as f:
        data = json.load(f)
        for ent in data.get("entities", []):
            if ent["id"] == entity_id:
                return ent
    raise HTTPException(status_code=404, detail=f"Entity not found: {entity_id}")
```

### `src/luna/services/guardian/routes/membrane.py`

```python
"""Membrane routes — serve consent and scope transition fixtures."""

import json
from pathlib import Path
from fastapi import APIRouter

router = APIRouter()

MEMBRANE_DIR = Path("data/guardian/membrane")


@router.get("/membrane/consent")
async def get_consent_events():
    """Get consent events."""
    path = MEMBRANE_DIR / "consent_events.json"
    if not path.exists():
        return {"events": []}
    with open(path) as f:
        return json.load(f)


@router.get("/membrane/scope")
async def get_scope_transitions():
    """Get scope transitions."""
    path = MEMBRANE_DIR / "scope_transitions.json"
    if not path.exists():
        return {"transitions": []}
    with open(path) as f:
        return json.load(f)
```

### `src/luna/services/guardian/routes/graph.py`

```python
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
```

---

## Step 3: Register in server.py

Add these lines to `src/luna/api/server.py`:

### Import (add near the kozmo import, ~line 47):

```python
from luna.services.guardian.routes import router as guardian_router
```

### Router registration (add after `app.include_router(kozmo_router)`, ~line 432):

```python
# Mount GUARDIAN service router
app.include_router(guardian_router)
```

### Static frontend (add after Kozmo static mount, ~line 443):

```python
# Serve GUARDIAN frontend
try:
    _guardian_frontend = _Path(__file__).parent.parent.parent.parent / "Eclissi-Guardian" / "frontend"
    if not _guardian_frontend.exists():
        # Fallback: check if copied into engine tree
        _guardian_frontend = _Path("frontend/guardian")
    if _guardian_frontend.exists():
        app.mount("/guardian", StaticFiles(directory=str(_guardian_frontend), html=True), name="guardian")
        logger.info(f"Guardian frontend mounted at /guardian from {_guardian_frontend}")
    else:
        logger.warning("Guardian frontend not found — /guardian will not be served")
except Exception as e:
    logger.warning(f"Guardian frontend mount failed: {e}")
```

### CORS — add tunnel-friendly wildcard (replace the existing allow_origins):

```python
# For demo/tunnel access, allow all origins.
# Production should lock this down.
allow_origins=["*"],
```

OR keep the explicit list and add the tunnel domain when you know it.

### Auto-activate project scope for Guardian requests (optional middleware):

```python
@app.middleware("http")
async def guardian_project_scope(request, call_next):
    """Auto-activate guardian project scope for /guardian/api/ requests."""
    if request.url.path.startswith("/guardian/api/"):
        if _engine and _engine.active_project != "guardian-kinoni":
            _engine.set_active_project("guardian-kinoni")
    response = await call_next(request)
    return response
```

---

## Step 4: Update Guardian Frontend Data Layer

The frontend currently loads from `/generated/`. Change to use the API routes.

### Update `js/data.js`

Replace the hardcoded fixture loading with API calls:

```js
var GuardianData = (function () {
  var data = {
    threads: {},
    knowledgeNodes: {},
    entities: {},
    relationships: [],
    membrane: { consent: [], scope: [] },
    knowledgeGraph: { nodes: [], edges: [], entity_nodes: [], entity_edges: [] }
  };

  // API base — same origin when served from engine
  var API = '/guardian/api';

  async function fetchJSON(path) {
    var res = await fetch(API + path);
    if (!res.ok) throw new Error('Failed to load ' + path + ': ' + res.status);
    return res.json();
  }

  async function init() {
    var results = await Promise.all([
      fetchJSON('/threads/amara'),
      fetchJSON('/knowledge'),
      fetchJSON('/entities'),
      fetchJSON('/entities/relationships'),
      fetchJSON('/membrane/consent'),
      fetchJSON('/membrane/scope'),
      fetchJSON('/graph'),
      fetchJSON('/threads/musoke'),
      fetchJSON('/threads/wasswa'),
      fetchJSON('/threads/elder'),
    ]);

    // Threads
    data.threads.amara = results[0].messages;
    data.threads.musoke = results[7].messages;
    data.threads.wasswa = results[8].messages;
    data.threads.elder = results[9].messages;

    // Knowledge nodes — /knowledge returns merged list
    results[1].nodes.forEach(function (node) {
      data.knowledgeNodes[node.id] = node;
    });

    // Entities
    (results[2].entities || []).forEach(function (ent) {
      data.entities[ent.id] = ent;
    });

    // Relationships
    data.relationships = results[3].relationships || [];

    // Membrane
    data.membrane.consent = results[4].events || [];
    data.membrane.scope = results[5].transitions || [];

    // Knowledge graph
    data.knowledgeGraph = results[6];

    buildKeywordIndex();
    return data;
  }

  // ... rest of GuardianData unchanged ...
```

### Update `js/luna-chat.js` and `js/main-chat.js`

Change the API URL from hardcoded `http://127.0.0.1:8000/message` to relative:

```js
// Old:
var LUNA_API = 'http://127.0.0.1:8000/message';

// New:
var LUNA_API = '/message';
```

Same for voice-layer.js TTS endpoint:

```js
// Old:
var response = await fetch('http://127.0.0.1:8000/api/tts', { ... });

// New:
var response = await fetch('/api/tts', { ... });
```

**All API calls become relative paths** because the frontend is served from the same origin as the API. No CORS issues. No hardcoded URLs. Works through any tunnel.

---

## Step 5: Project Scope Activation

### Option A: Middleware (shown in Step 3)
Auto-activates `guardian-kinoni` scope for any `/guardian/api/` request.

### Option B: Frontend init call
Guardian calls activate on startup:

```js
// In app.js, before GuardianData.init()
fetch('/project/activate', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ slug: 'guardian-kinoni' }),
}).catch(function () {
  console.warn('[Guardian] Could not activate project scope');
});
```

**Recommend Option A** — the middleware approach is invisible and foolproof.

---

## Step 6: Tunnel Setup for Demo

Same pattern as the dataroom:

```bash
# Start engine (serves API + Guardian frontend + Kozmo + everything)
cd _LunaEngine_BetaProject_V2.0_Root && python scripts/run.py --server

# Expose via tunnel
ngrok http 8000
# or
cloudflared tunnel --url http://localhost:8000
```

Tarcila opens: `https://<tunnel-id>.ngrok.io/guardian/`

Everything works — API calls are relative, same origin, no CORS.

---

## Build Order for Claude Code

1. Create `src/luna/services/guardian/` directory structure
2. Create `src/luna/services/guardian/__init__.py`
3. Create `src/luna/services/guardian/routes/__init__.py`
4. Create `src/luna/services/guardian/routes/threads.py`
5. Create `src/luna/services/guardian/routes/knowledge.py`
6. Create `src/luna/services/guardian/routes/entities.py`
7. Create `src/luna/services/guardian/routes/membrane.py`
8. Create `src/luna/services/guardian/routes/graph.py`
9. Copy demo data: `cp -r Eclissi-Guardian/generated/ _LunaEngine_BetaProject_V2.0_Root/data/guardian/`
10. Update `server.py`: import guardian_router, include_router, mount static frontend
11. Update `server.py`: add CORS wildcard or tunnel domain
12. Update `server.py`: add guardian project scope middleware
13. Update `data.js`: change BASE to `/guardian/api`, rewrite init() to use API routes
14. Update `luna-chat.js`: LUNA_API → `/message`
15. Update `main-chat.js`: LUNA_API → `/message`  
16. Update `voice-layer.js`: TTS URL → `/api/tts`
17. Test: `python scripts/run.py --server` then open `http://localhost:8000/guardian/`
18. Verify: threads load, knowledge nodes render, Luna chat works, Observatory works

---

## Verification Checklist

### Service Registration
- [ ] `http://localhost:8000/guardian/api/threads` returns thread list
- [ ] `http://localhost:8000/guardian/api/threads/amara` returns messages
- [ ] `http://localhost:8000/guardian/api/knowledge` returns all nodes
- [ ] `http://localhost:8000/guardian/api/entities` returns entities
- [ ] `http://localhost:8000/guardian/api/membrane/consent` returns events
- [ ] `http://localhost:8000/guardian/api/graph` returns knowledge graph

### Frontend Serving
- [ ] `http://localhost:8000/guardian/` serves index.html
- [ ] CSS and JS files load correctly (check network tab)
- [ ] No 404s for static assets

### Data Integration
- [ ] Thread messages render in spine
- [ ] Knowledge nodes appear in knowledge bars
- [ ] Entity names highlighted in message bubbles
- [ ] Observatory loads entity graph
- [ ] Membrane events render in membrane bars

### Luna Chat (same origin)
- [ ] Panel Luna chat sends to `/message` and receives response
- [ ] Main chat sends to `/message` and receives response
- [ ] `/api/tts` returns audio (if TTS endpoint is implemented)
- [ ] No CORS errors in console

### Project Scope
- [ ] `GET /project/active` shows `guardian-kinoni` when Guardian is loaded
- [ ] Scribe skips messages with `[GUARDIAN CONTEXT` prefix (already implemented)
- [ ] Luna's global memory not polluted by Guardian queries

### Tunnel Demo
- [ ] ngrok/cloudflare tunnel exposes `http://localhost:8000`
- [ ] External browser opens `https://<tunnel>/guardian/` successfully
- [ ] All API calls work through tunnel (relative paths, same origin)
- [ ] Luna responds through tunnel

---

## Files Summary

### NEW FILES (in engine repo):
1. `src/luna/services/guardian/__init__.py`
2. `src/luna/services/guardian/routes/__init__.py`
3. `src/luna/services/guardian/routes/threads.py`
4. `src/luna/services/guardian/routes/knowledge.py`
5. `src/luna/services/guardian/routes/entities.py`
6. `src/luna/services/guardian/routes/membrane.py`
7. `src/luna/services/guardian/routes/graph.py`
8. `data/guardian/` (copied from Eclissi-Guardian/generated/)

### MODIFIED FILES (in engine repo):
9. `src/luna/api/server.py` — import, include_router, static mount, CORS, middleware
10. `src/luna/actors/scribe.py` — Guardian context guard (ALREADY DONE)

### MODIFIED FILES (Guardian frontend):
11. `frontend/js/data.js` — API base → `/guardian/api`, rewrite init()
12. `frontend/js/luna-chat.js` — LUNA_API → `/message`
13. `frontend/js/main-chat.js` — LUNA_API → `/message`
14. `frontend/js/voice-layer.js` — TTS URL → `/api/tts`

---

## Notes

### Why Not Database Routes (Yet)
The demo routes serve JSON fixtures directly. This is intentional — the demo
data is hand-crafted for the Kinoni narrative and doesn't exist in the Memory
Matrix. Post-ROSA, the routes can be upgraded to query the actual Memory
Matrix, but for March 2026, JSON fixtures are faster and more reliable.

### Frontend Location
The spec mounts the Guardian frontend from `Eclissi-Guardian/frontend/` via
a path relative to server.py. This avoids copying the frontend into the
engine repo. If you want it self-contained, copy the frontend into
`_LunaEngine_BetaProject_V2.0_Root/frontend/guardian/` and update the
static mount path.

### Kozmo Coexistence
Guardian and Kozmo both register as services in the same server. They don't
conflict — different URL prefixes (`/kozmo/` vs `/guardian/`), different data
directories. Both accessible from the same tunnel URL.

### Post-Demo Migration Path
1. Replace JSON fixtures with Memory Matrix queries
2. Guardian routes call `engine.memory_matrix.search()` instead of `json.load()`
3. Add write routes (consent events, new knowledge submissions)
4. Add WebSocket for live updates (new messages, scope changes)
5. Separate Guardian into its own deployable with the engine as dependency
