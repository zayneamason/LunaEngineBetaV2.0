# HANDOFF: Guardian Service Integration

## Context

Guardian is the cultural knowledge stewardship frontend for Project Tapestry.
It's currently a standalone static HTML app in `../Eclissi-Guardian/frontend/`
with demo fixture data in `../Eclissi-Guardian/generated/`.

This handoff integrates Guardian into the Luna Engine as a service — same
pattern as Kozmo. One server, one URL, one tunnel for demo day.

**Full spec:** `Docs/GUARDIAN-SERVICE-SPEC.md` (638 lines, complete code for
every file). Read it first.

## What to Build

### 1. Guardian service module

Create the service following the Kozmo pattern:

```
src/luna/services/guardian/
  __init__.py                        ← docstring only
  routes/
    __init__.py                      ← combines sub-routers under /guardian/api
    threads.py                       ← GET /guardian/api/threads, /threads/:id
    knowledge.py                     ← GET /guardian/api/knowledge, /knowledge/:id
    entities.py                      ← GET /guardian/api/entities, /entities/:id, /entities/relationships
    membrane.py                      ← GET /guardian/api/membrane/consent, /membrane/scope
    graph.py                         ← GET /guardian/api/graph
```

All routes serve JSON fixtures from `data/guardian/`. No database queries.
Read `json.load()`, return the data. See the spec for exact code.

Reference: `src/luna/services/kozmo/routes/__init__.py` — follow this pattern
exactly for the router combination and prefix.

### 2. Copy demo data

```bash
cp -r ../Eclissi-Guardian/generated/ data/guardian/
```

Resulting structure:
```
data/guardian/
  conversations/amara_thread.json, musoke_thread.json, wasswa_thread.json, elder_thread.json
  knowledge_nodes/facts.json, insights.json, decisions.json, actions.json, milestones.json
  entities/entities_updated.json, relationships_updated.json
  membrane/consent_events.json, scope_transitions.json
  org_timeline/knowledge_graph.json
```

### 3. Register in server.py

Three additions to `src/luna/api/server.py`:

**a) Import** (near line 47, next to kozmo import):
```python
from luna.services.guardian.routes import router as guardian_router
```

**b) Include router** (after `app.include_router(kozmo_router)`):
```python
app.include_router(guardian_router)
```

**c) Mount static frontend** (after Kozmo static mount):
```python
try:
    _guardian_frontend = _Path(__file__).parent.parent.parent.parent / "Eclissi-Guardian" / "frontend"
    if not _guardian_frontend.exists():
        _guardian_frontend = _Path("frontend/guardian")
    if _guardian_frontend.exists():
        app.mount("/guardian", StaticFiles(directory=str(_guardian_frontend), html=True), name="guardian")
        logger.info(f"Guardian frontend mounted at /guardian from {_guardian_frontend}")
except Exception as e:
    logger.warning(f"Guardian frontend mount failed: {e}")
```

**d) CORS** — change `allow_origins` to `["*"]` for tunnel access:
```python
allow_origins=["*"],
```

### 4. Update Guardian frontend to use relative API paths

**`../Eclissi-Guardian/frontend/js/data.js`:**
- Change `var BASE = '/generated/';` to use `/guardian/api/` routes
- Rewrite `init()` to call the new API endpoints instead of static JSON paths
- See spec for exact rewrite of the init function

**`../Eclissi-Guardian/frontend/js/luna-chat.js`:**
- Change `LUNA_API` from `'http://127.0.0.1:8000/message'` to `'/message'`

**`../Eclissi-Guardian/frontend/js/main-chat.js`:**
- Change `LUNA_API` from `'http://127.0.0.1:8000/message'` to `'/message'`

**`../Eclissi-Guardian/frontend/js/voice-layer.js`:**
- Change TTS fetch URL from `'http://127.0.0.1:8000/api/tts'` to `'/api/tts'`

## Verification

Start the server and check each of these:

```bash
python scripts/run.py --server
```

**API routes work:**
```bash
curl http://localhost:8000/guardian/api/threads
curl http://localhost:8000/guardian/api/threads/amara
curl http://localhost:8000/guardian/api/knowledge
curl http://localhost:8000/guardian/api/entities
curl http://localhost:8000/guardian/api/entities/relationships
curl http://localhost:8000/guardian/api/membrane/consent
curl http://localhost:8000/guardian/api/membrane/scope
curl http://localhost:8000/guardian/api/graph
```

**Frontend loads:**
- Open `http://localhost:8000/guardian/` in browser
- Thread messages render in spine
- Knowledge bars appear on messages
- Click a knowledge node → panel opens
- Luna chat in panel sends to `/message` and gets response
- Observatory loads with entity graph
- No CORS errors in console
- No 404s in network tab

## Do NOT Change

- `src/luna/actors/scribe.py` — Guardian context guard already added
- Guardian CSS or HTML structure — only JS data layer changes
- Kozmo routes or registration — leave Kozmo untouched
- Engine core, director, memory matrix — don't touch these

## Part 2: Memory Bridge (the power)

Guardian has a memory bridge at `src/luna/services/guardian/memory_bridge.py`
(ALREADY WRITTEN — do not recreate). It syncs Guardian demo data into Luna's
Memory Matrix with project scope `project:guardian-kinoni`. After sync, Luna
*knows* about the Kinoni community without context injection.

### Wire the bridge into server.py

Add a Guardian sync endpoint and auto-sync on project activation.

**a) Import** (near other Guardian imports):
```python
from luna.services.guardian.memory_bridge import GuardianMemoryBridge
```

**b) Module-level state** (near `_engine = None`):
```python
_guardian_bridge: Optional[GuardianMemoryBridge] = None
```

**c) Sync endpoint:**
```python
@app.post("/guardian/api/sync")
async def guardian_sync():
    """Sync Guardian demo data into Luna's Memory Matrix."""
    global _guardian_bridge
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    if _guardian_bridge is None:
        _guardian_bridge = GuardianMemoryBridge(_engine)

    stats = await _guardian_bridge.sync_all()
    return {"status": "synced", **stats}


@app.post("/guardian/api/clear")
async def guardian_clear():
    """Clear Guardian data from Memory Matrix."""
    global _guardian_bridge
    if _guardian_bridge is None:
        return {"status": "nothing_to_clear"}

    removed = await _guardian_bridge.clear()
    return {"status": "cleared", "removed": removed}


@app.get("/guardian/api/sync/status")
async def guardian_sync_status():
    """Check if Guardian data is synced."""
    if _guardian_bridge is None:
        return {"synced": False}
    return {"synced": _guardian_bridge.is_synced}
```

**d) Auto-sync on project activation** — update the guardian scope middleware:
```python
@app.middleware("http")
async def guardian_project_scope(request, call_next):
    """Auto-activate guardian project scope and sync memory bridge."""
    global _guardian_bridge
    if request.url.path.startswith("/guardian/") and _engine is not None:
        # Activate project scope
        if _engine.active_project != "guardian-kinoni":
            _engine.set_active_project("guardian-kinoni")

        # Auto-sync on first request (lazy init)
        if _guardian_bridge is None:
            _guardian_bridge = GuardianMemoryBridge(_engine)
        if not _guardian_bridge.is_synced:
            try:
                stats = await _guardian_bridge.sync_all()
                logger.info(f"Guardian bridge auto-synced: {stats}")
            except Exception as e:
                logger.error(f"Guardian bridge auto-sync failed: {e}")

    response = await call_next(request)
    return response
```

### Frontend: trigger sync on load

In the Guardian frontend's `app.js`, add a sync call during init:

```js
// In DOMContentLoaded, before GuardianData.init()
fetch('/guardian/api/sync', { method: 'POST' })
  .then(r => r.json())
  .then(data => console.log('[Guardian] Memory bridge:', data))
  .catch(() => console.warn('[Guardian] Memory bridge sync failed'));
```

### What this means for the demo

Tarcila opens Guardian in her browser. The middleware auto-activates
`guardian-kinoni` scope and syncs 23 entities + 163 knowledge nodes + 40
relationships into the Memory Matrix. Now when she types in the main chat:

> "What do you know about the springs in Lwengo?"

Luna can answer from memory — no knowledge panel open, no context injection.
She *knows*. That's the demo moment.

### Verification

```bash
# Sync manually
curl -X POST http://localhost:8000/guardian/api/sync
# -> {"status": "synced", "entities": 23, "knowledge": 163, "edges": 40+}

# Check status
curl http://localhost:8000/guardian/api/sync/status
# -> {"synced": true}

# Test Luna's awareness (main chat, no context prefix)
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "What do you know about Elder Musoke and the springs?", "timeout": 30}'
# Luna should reference Musoke, springs, governance — from memory, not injection
```

## Key Reference Files

| File | What to look at |
|------|----------------|
| `src/luna/services/kozmo/routes/__init__.py` | Router combination pattern to follow |
| `src/luna/services/guardian/memory_bridge.py` | ALREADY WRITTEN — wire it, don't rewrite it |
| `src/luna/api/server.py` ~line 432 | Where Kozmo is registered (add Guardian next to it) |
| `src/luna/api/server.py` ~line 436 | How Kozmo static files are mounted |
| `Docs/GUARDIAN-SERVICE-SPEC.md` | Complete code for every route file |
| `../Eclissi-Guardian/frontend/js/data.js` | Current data layer to rewrite |
