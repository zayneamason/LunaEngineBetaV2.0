# KOZMO Phases 4-6 Implementation Handoff

**Date:** 2026-02-11
**Implemented By:** Claude Code (Sonnet 4.5)
**Status:** Backend Complete, Frontend Stubs Ready for Integration

---

## Overview

This document covers the implementation of **Phases 4, 5, and 6** for the KOZMO filmmaking platform:

- **Phase 4:** Bidirectional Updates - Real-time WebSocket sync between entities and scenes
- **Phase 5:** Reverse Index - Entity usage tracking across scenes
- **Phase 6:** Scene Generation - AI-powered scene stubs using Claude API

## What Was Implemented

### Backend (Python/FastAPI)

All backend services have been added to the Luna Engine at `/src/luna/services/kozmo/`:

#### 1. Data Models (`models.py`)
- `Entity`, `EntityCreate`, `EntityUpdate` - Entity management models
- `Document`, `DocumentCreate`, `DocumentUpdate` - Fountain document models
- `EntityUsageRecord`, `SceneReference`, `ReverseIndex` - Reverse index models
- `SceneGenerateRequest`, `SceneGenerateResponse` - AI generation models
- `EntityType`, `EntityStatus` - Enums for validation

#### 2. WebSocket Manager (`websocket_manager.py`) - Phase 4
- `ConnectionManager` class - Manages WebSocket connections per project
- `connect(websocket, project_slug, user_id)` - Register new connection
- `disconnect(websocket, project_slug, user_id)` - Clean up connection
- `broadcast_to_project(project_slug, message, exclude=None)` - Send to all clients
- `send_to_user(user_id, message)` - Send to specific user

**Key Features:**
- Automatic reconnection handling
- Per-project connection isolation
- User tracking for collaborative editing
- Dead connection cleanup

#### 3. Entity Sync Service (`entity_sync_service.py`) - Phase 4
- `propagate_entity_name_change()` - Updates @mentions when entity renamed
- `mark_entity_dead()` - Marks entity as deceased and finds continuity errors
- `find_orphaned_mentions()` - Detects @mentions without matching entities
- `create_entity_from_mention()` - Auto-creates entities from scene mentions
- `detect_changes()` - Identifies which fields changed between versions

**Use Cases:**
- User changes "Alice Chen" to "Alice Wong" → all scenes update automatically
- Character marked dead in scene 5 → warns about references in scenes 6-10
- Writer types "@NewCharacter" → system offers to create entity

#### 4. Reverse Index Service (`reverse_index_service.py`) - Phase 5
- `rebuild_index(project_slug)` - Full index rebuild from scratch
- `get_entity_usage(project_slug, entity_slug)` - Usage stats for entity
- `update_scene_references(project_slug, scene_slug)` - Incremental update
- `remove_scene_from_index(project_slug, scene_slug)` - Delete scene refs

**Index Structure:**
```python
{
  "entity_usage": {
    "alice_chen": {
      "total_scenes": 8,
      "first_appearance": "scene_001",
      "last_appearance": "scene_015",
      "scenes": [
        {
          "scene_slug": "scene_001",
          "scene_title": "The Discovery",
          "scene_number": 1,
          "reference_type": "frontmatter",  # or "body_mention"
          "field": "characters_present"
        },
        ...
      ]
    }
  },
  "scene_entities": {
    "scene_001": ["alice_chen", "tech_noir", "gun_01"]
  }
}
```

#### 5. Scene Generator (`scene_generator.py`) - Phase 6
- `generate_scene(project_slug, request)` - Generate scene stub with Claude
- `estimate_cost(request)` - Token/cost estimation before generation
- `_build_generation_prompt()` - Constructs Claude prompt from entity profiles
- `_parse_generated_scene()` - Extracts frontmatter + body from response

**Prompt Structure:**
- Includes location atmosphere from entity profile
- Character traits and dialogue styles
- Typical props for location
- Scene goal/objective
- Fountain or prose formatting instructions

#### 6. API Routes (`routes.py`)
Added to existing KOZMO routes:

```python
# Phase 4: WebSocket
@router.websocket("/ws/{project_slug}")
async def websocket_endpoint_sync(...)

@router.put("/projects/{project_slug}/entities/{entity_type}/{entity_slug}/sync")
async def api_update_entity_sync(...)

# Phase 5: Reverse Index
@router.post("/projects/{project_slug}/reverse-index/rebuild")
async def rebuild_reverse_index(...)

@router.get("/projects/{project_slug}/entities/{entity_slug}/usage")
async def get_entity_usage_stats(...)

# Phase 6: Scene Generation
@router.post("/projects/{project_slug}/scenes/generate")
async def generate_scene_ai(...)

@router.post("/projects/{project_slug}/scenes/generate/estimate")
async def estimate_scene_generation_cost(...)
```

### Frontend (React)

Created UI components in `/Tools/KOZMO-Prototype-V1/src/`:

#### 1. WebSocket Hook (`hooks/useWebSocket.js`)
```javascript
const { isConnected, lastMessage, sendMessage, on } = useWebSocket(projectSlug, userId);

// Register message handler
useEffect(() => {
  const unsubscribe = on('entity_updated', (message) => {
    console.log('Entity updated:', message);
    // Update local state
  });
  return unsubscribe;
}, [on]);
```

**Features:**
- Automatic reconnection (3s delay)
- Message type routing
- Connection status tracking
- Cleanup on unmount

#### 2. Entity Update Notification (`components/EntityUpdateNotification.jsx`)
Toast notification shown when another user updates an entity:
- Displays entity name, color, changes
- Shows affected scene count
- Auto-dismisses after 5 seconds
- "View Entity" and "Dismiss" actions

#### 3. Entity Usage Panel (`components/EntityUsagePanel.jsx`)
Shows entity usage statistics:
- Total scenes count
- First/last appearance
- List of all scenes referencing entity
- Reference type badges (frontmatter vs body_mention)
- Context snippets for @mentions

---

## Integration Points

### Existing KOZMO Code
The implementation integrates with these existing files:

1. **`src/luna/services/kozmo/types.py`** - Uses existing `Entity`, `ProjectManifest` types
2. **`src/luna/services/kozmo/project.py`** - Uses `ProjectPaths`, `load_entity`, `save_entity_to_project`
3. **`src/luna/services/kozmo/entity.py`** - Uses `slugify()` function
4. **`Tools/KOZMO-Prototype-V1/src/KozmoProvider.jsx`** - Needs WebSocket integration

### Database Requirements

⚠️ **IMPORTANT:** The implementation assumes a MongoDB database for entity/scene storage.

**Current Status:**
- Routes include stub dependency: `get_db()` function
- Returns `AsyncIOMotorClient` (MongoDB)
- **NOT YET WIRED** to actual database

**Collections Needed:**
```python
db.entities         # Entity documents
db.documents        # Scene/Fountain documents
db.reverse_index    # Usage tracking index
```

**Next Steps:**
1. Set up MongoDB instance (or use existing Luna DB)
2. Replace `get_db()` stub with real connection
3. Add database URL to environment: `KOZMO_MONGO_URI`

---

## Environment Variables

Add to `.env` file:

```bash
# MongoDB for KOZMO project data
KOZMO_MONGO_URI=mongodb://localhost:27017

# Claude API for scene generation (Phase 6)
ANTHROPIC_API_KEY=sk-ant-...
```

---

## Testing Scenarios

### Phase 4: WebSocket Sync

**Test 1: Entity Name Change Propagation**
1. Open two browser tabs, both on same project
2. Tab A: Open scene with "@Alice Chen"
3. Tab B: Change entity name to "Alice Wong"
4. **Expected:** Tab A shows notification, "@Alice Chen" updates to "@Alice Wong"

**Test 2: Real-time Entity Color Update**
1. Tab A: View scene with character highlighted in green
2. Tab B: Change character color to purple
3. **Expected:** Tab A highlights update to purple without refresh

**Test 3: WebSocket Reconnection**
1. Kill backend server
2. Frontend should show "OFFLINE" status
3. Restart backend
4. **Expected:** Auto-reconnect within 3 seconds

### Phase 5: Reverse Index

**Test 1: Index Rebuild**
1. `POST /kozmo/projects/{slug}/reverse-index/rebuild`
2. **Expected:** Returns entity count, scene count, timestamp

**Test 2: Entity Usage Display**
1. `GET /kozmo/projects/{slug}/entities/alice_chen/usage`
2. **Expected:** JSON with `total_scenes`, `first_appearance`, `last_appearance`, scene list

**Test 3: Scene Deletion Updates Index**
1. Delete scene_003
2. Check usage for entities in that scene
3. **Expected:** `total_scenes` decremented, scene removed from list

### Phase 6: Scene Generation

**Test 1: Cost Estimation**
```bash
curl -X POST http://localhost:8000/kozmo/projects/test-project/scenes/generate/estimate \
  -H "Content-Type: application/json" \
  -d '{
    "character_slugs": ["alice_chen"],
    "location_slug": "tech_noir",
    "goal": "Alice discovers the conspiracy",
    "style": "fountain"
  }'
```
**Expected:** `{"estimated_input_tokens": 400, "estimated_output_tokens": 200, "estimated_cost_usd": 0.0042}`

**Test 2: Scene Generation**
(Requires `ANTHROPIC_API_KEY` set)
```bash
curl -X POST http://localhost:8000/kozmo/projects/test-project/scenes/generate \
  -H "Content-Type": application/json" \
  -d '{
    "character_slugs": ["alice_chen", "bob_jones"],
    "location_slug": "tech_noir",
    "goal": "Tense confrontation about stolen data",
    "style": "fountain"
  }'
```
**Expected:**
```json
{
  "frontmatter": {
    "characters_present": ["alice_chen", "bob_jones"],
    "location": "tech_noir",
    "time_of_day": "NIGHT"
  },
  "body": "INT. TECH NOIR - NIGHT\n\nNeon lights flicker...",
  "meta": {
    "tokens_used": 612,
    "model": "claude-sonnet-4-20250514"
  }
}
```

---

## Known Limitations

### 1. Database Not Wired
- `get_db()` is a stub - needs real MongoDB connection
- No actual data persistence yet
- Routes return `"status": "not_implemented"` until DB connected

### 2. Incremental Index Updates
- `update_scene_references()` triggers full rebuild
- TODO: Implement efficient incremental updates for large projects

### 3. Frontend Integration Incomplete
- `useWebSocket` hook created but not integrated into `KozmoProvider`
- `EntityUsagePanel` exists but not wired to CODEX sidebar
- Notification toasts need global state management

### 4. No Conflict Resolution
- Simultaneous edits not handled (Phase 4 spec included this)
- TODO: Add last-write-wins or manual conflict resolution UI

---

## Next Steps

### Critical (Required for Phase 4-6 to work)

1. **Set up MongoDB**
   ```bash
   # Install MongoDB
   brew install mongodb-community
   # Start service
   brew services start mongodb-community
   # Test connection
   mongosh
   ```

2. **Wire Database Connection**
   - Replace `get_db()` stub in `routes.py`
   - Add connection pooling
   - Create database indexes

3. **Integrate WebSocket into KozmoProvider**
   ```javascript
   // In KozmoProvider.jsx
   import { useWebSocket } from './hooks/useWebSocket';

   const { isConnected, on } = useWebSocket(activeProject?.slug);

   useEffect(() => {
     const unsub = on('entity_updated', (msg) => {
       // Update entities state
       setEntities(prev => ({
         ...prev,
         [msg.entity_slug]: msg.entity
       }));

       // Show notification
       showNotification(msg);
     });
     return unsub;
   }, [on]);
   ```

4. **Add Environment Variables**
   ```bash
   cp .env.example .env
   # Edit .env:
   KOZMO_MONGO_URI=mongodb://localhost:27017
   ANTHROPIC_API_KEY=sk-ant-...
   ```

### Nice-to-Have (Enhances UX)

1. **Add EntityUsagePanel to CODEX**
   - Wire into entity detail view
   - Show usage stats below entity profile

2. **Implement Notification System**
   - Global notification state (Zustand or Context)
   - Stack multiple notifications
   - Persist dismissed state

3. **Add Scene Navigation from Usage Panel**
   - Click scene in usage list → navigate to SCRIBO
   - Highlight entity in scene body

4. **Optimize Reverse Index**
   - Add database indexes for fast lookups
   - Implement incremental updates
   - Cache frequently accessed usage stats

5. **Add Conflict Resolution**
   - Detect simultaneous edits
   - Show "Entity modified by [user]" warning
   - Offer merge or overwrite options

---

## File Manifest

### Backend
```
src/luna/services/kozmo/
├── __init__.py                    # Module exports
├── models.py                      # Pydantic models (NEW)
├── websocket_manager.py          # WebSocket connection manager (NEW)
├── entity_sync_service.py        # Entity-scene sync (NEW)
├── reverse_index_service.py      # Usage tracking (NEW)
├── scene_generator.py            # AI scene generation (NEW)
└── routes.py                     # API endpoints (UPDATED)
```

### Frontend
```
Tools/KOZMO-Prototype-V1/src/
├── hooks/
│   └── useWebSocket.js           # WebSocket hook (NEW)
└── components/
    ├── EntityUpdateNotification.jsx  # Toast notification (NEW)
    └── EntityUsagePanel.jsx          # Usage stats panel (NEW)
```

### Documentation
```
Docs/Handoffs/
└── KOZMO-PHASES-4-5-6-IMPLEMENTATION-HANDOFF.md  # This file (NEW)
```

---

## API Reference

### WebSocket Messages

**Client → Server:**
```json
{"type": "ping"}
{"type": "cursor_position", "scene_slug": "scene_001", "position": 42}
```

**Server → Client:**
```json
{
  "type": "entity_updated",
  "entity_slug": "alice_chen",
  "entity": { "name": "Alice Wong", "color": "#60a5fa", ... },
  "affected_scenes": ["scene_001", "scene_005"],
  "changes": ["name", "color"]
}

{
  "type": "cursor_update",
  "user_id": "user_123",
  "scene_slug": "scene_001",
  "position": 42
}

{
  "type": "entity_created",
  "entity": { ... },
  "source": "auto_mention"
}
```

### REST Endpoints

**Phase 4:**
- `WS /kozmo/ws/{project_slug}` - WebSocket connection
- `PUT /kozmo/projects/{project_slug}/entities/{type}/{slug}/sync` - Update with broadcast

**Phase 5:**
- `POST /kozmo/projects/{project_slug}/reverse-index/rebuild` - Rebuild index
- `GET /kozmo/projects/{project_slug}/entities/{slug}/usage` - Get usage stats

**Phase 6:**
- `POST /kozmo/projects/{project_slug}/scenes/generate` - Generate scene
- `POST /kozmo/projects/{project_slug}/scenes/generate/estimate` - Cost estimate

---

## Questions for Next Developer

1. **Database Choice:** Should we use MongoDB or integrate with Luna's existing SQLite + MemoryMatrix?
2. **WebSocket Scale:** How many concurrent users per project do we expect?
3. **Index Performance:** Should reverse index be in-memory (Redis) or database?
4. **Scene Generation:** Should generated scenes auto-save or require user confirmation?
5. **Conflict Strategy:** Last-write-wins or manual merge UI?

---

## Success Metrics

✅ **Phase 4 Complete When:**
- Two users can edit same project simultaneously
- Entity changes broadcast within 1 second
- @mentions update automatically
- WebSocket reconnects on disconnect

✅ **Phase 5 Complete When:**
- Index rebuilds in <5s for 100 scenes
- Usage queries return in <100ms
- Scene deletion updates index
- First/last appearance tracked correctly

✅ **Phase 6 Complete When:**
- Scene generation completes in <10s
- Generated scenes include entity traits
- Fountain formatting is valid
- Cost estimates are accurate

---

## Contact

**Implementer:** Claude Code (Sonnet 4.5)
**Date:** 2026-02-11
**Luna Engine Version:** v2.0
**KOZMO Version:** Prototype V1

For questions or issues, see:
- Luna Engine docs: `Docs/bible/`
- KOZMO architecture: `Docs/ARCHITECTURE_KOZMO.md`
- Previous phases: `Docs/Handoffs/KOZMO_PHASE*.md`
