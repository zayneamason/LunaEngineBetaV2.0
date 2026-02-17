# Claude Code Handoff: Quest Board + Entity Layer → Observatory Sandbox

## Executive Summary

Extend the Observatory Sandbox with two new layers:
1. **Entity System** — people, personas, places, projects as first-class graph objects (mirroring Luna Hub's `entities` / `entity_relationships` / `entity_mentions` / `entity_versions` tables)
2. **Quest Board** — habit-building quests generated from Librarian-style `maintenance_sweep()` patterns that emerge from graph health analysis

**Design reference:** The React artifact `quest_habit_v3.jsx` (in this project's files) is the interactive prototype. It shows the visual design, data model, and interaction patterns. The Observatory integration makes it *live* — backed by real data, real lock-in calculations, real retrieval pipelines.

**What this is NOT:** This is not a port of the artifact into the frontend. This is wiring the artifact's *concepts* into the Observatory's existing backend + frontend architecture.

---

## Project Location

```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Tools/MemoryMatrix_SandBox/
```

## Reference Files

| File | What | Where |
|------|------|-------|
| `quest_habit_v3.jsx` | Design prototype — entity cards, quest board, journal, mechanics | Project knowledge (Claude artifact) |
| `mcp_server/schema.sql` | Current DB schema | Sandbox |
| `mcp_server/lock_in.py` | Lock-in calculator | Sandbox |
| `mcp_server/tools.py` | Current 10 MCP tools | Sandbox |
| `frontend/src/views/GraphView.jsx` | Current graph (force-directed, node-only) | Sandbox |
| `frontend/src/components/NodeCard.jsx` | Current detail panel | Sandbox |
| `frontend/src/components/LockInRing.jsx` | Circular lock-in indicator | Sandbox |
| `frontend/src/store.js` | Zustand state | Sandbox |
| `frontend/src/api.js` | REST client | Sandbox |

---

## What Exists Today

```
Observatory Sandbox (current state):
├── Backend: 10 MCP tools, HTTP on :8100, WebSocket events
├── DB: nodes, edges, clusters, cluster_members, nodes_fts, node_embeddings
├── Frontend: Graph tab, Timeline tab, Replay tab
├── Lock-in: 4-factor calculator, LockInRing component
├── Search: FTS5 + vector + hybrid + spreading activation + constellation assembly
└── Seeds: small_graph.json, stress_test.json, pathological.json
```

**Missing:**
- No entity system (people/places/projects as first-class objects)
- No entity relationships (typed connections between entities)
- No entity mentions (linking knowledge nodes to entities)
- No entity versions (change history)
- No quest system
- No journal/reflection system
- Lock-in drifting threshold is 0.30, should be 0.20

---

## Architecture: What Gets Added

```
NEW TABLES:
├── entities (id, type, name, aliases, avatar, profile, core_facts, voice_config, ...)
├── entity_relationships (from_id, to_id, rel_type, strength, context, ...)
├── entity_mentions (entity_id, node_id, mention_type, ...)
├── entity_versions (entity_id, version, change_type, summary, snapshot, ...)
├── quests (id, type, status, priority, title, objective, ...)
├── quest_targets (quest_id, entity_id | node_id, ...)
└── quest_journal (quest_id, content, themes, lock_in_delta, edges_created, ...)

NEW MCP TOOLS:
├── sandbox_add_entity(type, name, profile, ...)
├── sandbox_add_entity_relationship(from_id, to_id, rel_type, ...)
├── sandbox_link_mention(entity_id, node_id, mention_type)
├── sandbox_maintenance_sweep()  → generates quest candidates
├── sandbox_quest_accept(quest_id)
├── sandbox_quest_complete(quest_id, journal_text, themes)
└── sandbox_quest_list(filter)

NEW HTTP ENDPOINTS:
├── GET  /api/entities          → all entities with relationship counts
├── GET  /api/entities/:id      → entity detail + relationships + mentions + versions + quests
├── GET  /api/quests            → quest list with filters
├── POST /api/maintenance-sweep → trigger quest generation
└── POST /api/quest/:id/complete → complete quest + create journal

NEW FRONTEND VIEWS:
├── EntityGraphView  → Two-layer graph (entities primary, knowledge secondary)
├── EntityDetail     → Tabbed panel: Profile | Knowledge | Quests | History
├── QuestBoard       → Quest list with entity badges and status filters
└── Journal          → Completed quest reflections (INSIGHT nodes with source: quest_reflection)

MODIFIED:
├── lock_in.py: Fix drifting threshold 0.30 → 0.20
├── schema.sql: Add new tables
├── tools.py: Register new tools
├── server.py: Add new HTTP endpoints
├── store.js: Add entity + quest state
├── api.js: Add entity + quest API calls
└── App.jsx: Add new tab routing
```

---

## Phase 1: Schema Migration

### 1A: New Tables

Add to `mcp_server/schema.sql` (or create a `schema_v2.sql` migration):

```sql
-- ============================================================================
-- ENTITY SYSTEM — people, personas, places, projects as first-class objects
-- ============================================================================

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('person', 'persona', 'place', 'project')),
    name TEXT NOT NULL,
    aliases TEXT DEFAULT '[]',           -- JSON array of alternate names
    avatar TEXT DEFAULT '',              -- single char or emoji
    profile TEXT,                        -- prose description (nullable = sparse profile)
    core_facts TEXT DEFAULT '{}',        -- JSON object of key-value facts
    voice_config TEXT,                   -- JSON: {tone, patterns[], constraints[]} — personas only
    mention_count INTEGER DEFAULT 0,     -- denormalized count from entity_mentions
    current_version INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_id TEXT NOT NULL,
    to_id TEXT NOT NULL,
    rel_type TEXT NOT NULL CHECK(rel_type IN (
        'creator', 'collaborator', 'friend', 'embodies',
        'located_at', 'works_on', 'knows', 'depends_on', 'enables'
    )),
    strength REAL DEFAULT 1.0,
    context TEXT,                        -- optional annotation
    bidirectional INTEGER DEFAULT 0,     -- 0=directed, 1=bidirectional
    created_at TEXT NOT NULL,
    FOREIGN KEY (from_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (to_id) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS entity_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    mention_type TEXT DEFAULT 'reference' CHECK(mention_type IN ('subject', 'reference', 'context')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE,
    UNIQUE(entity_id, node_id)           -- one mention link per entity-node pair
);

CREATE TABLE IF NOT EXISTS entity_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    change_type TEXT NOT NULL CHECK(change_type IN ('create', 'update', 'synthesize', 'rollback')),
    summary TEXT NOT NULL,
    snapshot TEXT,                        -- JSON snapshot of entity at this version (optional)
    created_at TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
);

-- ============================================================================
-- QUEST SYSTEM — habit-building quests from graph health analysis
-- ============================================================================

CREATE TABLE IF NOT EXISTS quests (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('main', 'side', 'contract', 'treasure_hunt', 'scavenger')),
    status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available', 'active', 'complete', 'failed', 'expired')),
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high', 'urgent')),
    title TEXT NOT NULL,
    subtitle TEXT,
    objective TEXT NOT NULL,
    source TEXT,                          -- what triggered this quest (e.g. "maintenance_sweep → orphan entity")
    journal_prompt TEXT,                  -- optional writing prompt for side quests
    target_lock_in REAL,                  -- lock-in of primary target at quest creation
    reward_base REAL DEFAULT 0.15,        -- base reward before level scaling
    investigation TEXT DEFAULT '{}',      -- JSON: {recalls, sources, hops}
    expires_at TEXT,                      -- ISO datetime or null
    completed_at TEXT,
    failed_at TEXT,
    fail_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quest_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_id TEXT NOT NULL,
    target_type TEXT NOT NULL CHECK(target_type IN ('entity', 'node', 'cluster')),
    target_id TEXT NOT NULL,
    FOREIGN KEY (quest_id) REFERENCES quests(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS quest_journal (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quest_id TEXT NOT NULL,
    content TEXT NOT NULL,                -- the reflection text
    themes TEXT DEFAULT '[]',             -- JSON array of theme tags
    lock_in_delta REAL DEFAULT 0.0,       -- how much lock-in changed
    edges_created INTEGER DEFAULT 0,       -- edges added during quest
    node_id TEXT,                          -- the INSIGHT node created from this journal
    created_at TEXT NOT NULL,
    FOREIGN KEY (quest_id) REFERENCES quests(id) ON DELETE CASCADE,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE SET NULL
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entity_rels_from ON entity_relationships(from_id);
CREATE INDEX IF NOT EXISTS idx_entity_rels_to ON entity_relationships(to_id);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_entity ON entity_mentions(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_node ON entity_mentions(node_id);
CREATE INDEX IF NOT EXISTS idx_quests_status ON quests(status);
CREATE INDEX IF NOT EXISTS idx_quests_type ON quests(type);
CREATE INDEX IF NOT EXISTS idx_quest_targets_quest ON quest_targets(quest_id);
CREATE INDEX IF NOT EXISTS idx_quest_targets_target ON quest_targets(target_id);
```

### 1B: Fix Lock-In Threshold

In `mcp_server/lock_in.py`, change:

```python
# BEFORE (wrong):
STATES = [
    (0.00, 0.30, "drifting"),
    (0.30, 0.70, "fluid"),
    ...
]

# AFTER (correct per Memory Economy spec):
STATES = [
    (0.00, 0.20, "drifting"),
    (0.20, 0.70, "fluid"),
    (0.70, 0.85, "settled"),
    (0.85, 1.01, "crystallized"),
]
```

Also update `frontend/src/components/NodeCard.jsx` and any other frontend references.

---

## Phase 2: Backend — Entity CRUD + Quest Generation

### 2A: Entity Methods on SandboxMatrix

Add to `sandbox_matrix.py` (or create `entities.py` module):

```python
# Required methods:
async def add_entity(self, type, name, profile=None, aliases=None, avatar="",
                     core_facts=None, voice_config=None, entity_id=None) -> str
async def get_entity(self, entity_id) -> dict | None
async def update_entity(self, entity_id, **kwargs) -> dict  # creates version entry
async def list_entities(self, type_filter=None) -> list[dict]
async def add_entity_relationship(self, from_id, to_id, rel_type, strength=1.0, context=None) -> int
async def get_entity_relationships(self, entity_id) -> list[dict]
async def link_mention(self, entity_id, node_id, mention_type="reference") -> int
async def get_entity_mentions(self, entity_id) -> list[dict]
async def get_entity_versions(self, entity_id) -> list[dict]
```

**Key behavior:**
- `add_entity()` creates version 1 automatically
- `update_entity()` increments version, creates entity_versions row
- `link_mention()` updates `mention_count` on entity (denormalized)
- All mutations emit events: `entity_created`, `entity_updated`, `entity_relationship_added`, `entity_mention_linked`

### 2B: Maintenance Sweep (Quest Generator)

Create `mcp_server/maintenance.py`:

This is the heart of the quest system. It scans the graph for health issues and generates quest candidates.

```python
async def maintenance_sweep(matrix) -> list[dict]:
    """
    Scan for graph health issues. Returns quest candidates.
    
    Checks (in order):
    1. find_orphan_entities()    → entities with mentions but no relationships
    2. find_stale_entities()     → entities not updated in 30+ days with active mentions
    3. find_fragmented_entities()→ entities with high mention count but sparse profile
    4. find_contradictions()     → DECISION nodes with contradicting content in same cluster
    5. find_drifting_clusters()  → clusters with avg lock-in below 0.20
    6. find_unreflected_sessions()→ OUTCOME nodes with no linked INSIGHT/REFLECTION
    
    Each returns:
    {
        "quest_type": "scavenger" | "treasure_hunt" | "contract" | "side",
        "priority": "low" | "medium" | "high" | "urgent",
        "title": str,
        "subtitle": str,
        "objective": str,
        "source": str,  # which check generated this
        "target_entities": [entity_id, ...],
        "target_nodes": [node_id, ...],
        "target_clusters": [cluster_id, ...],
        "journal_prompt": str | None,
    }
    """
```

**Quest type mapping:**

| Health Check | Quest Type | Example |
|---|---|---|
| Orphan entity (mentions but no relationships) | Scavenger | "Map Eden's relationships — 5 mentions, 0 connections" |
| Stale entity (not updated 30+ days) | Treasure Hunt | "Refresh Tarsila's profile — last updated Dec 5" |
| Fragmented entity (high mentions, thin profile) | Scavenger | "Who is Tarsila? 8 mentions, 1 fact" |
| Contradicting decisions in same cluster | Contract | "Delegation Crossroads — two strategies can't both be the plan" |
| Drifting cluster (avg lock-in < 0.20) | Treasure Hunt | "The HTTP cluster is fading — reinforce or let go" |
| Outcome with no reflection | Side Quest | "Journal about the graph pipeline fix" |

### 2C: Quest Completion Flow

```python
async def complete_quest(matrix, quest_id, journal_text=None, themes=None) -> dict:
    """
    1. Mark quest as complete
    2. If journal_text provided:
       a. Create INSIGHT node with content=journal_text, tags=themes
       b. Link INSIGHT to quest target entities via entity_mentions
       c. Create quest_journal row pointing to INSIGHT node
    3. Reinforce target nodes (call existing reinforce logic)
    4. Recompute lock-in for affected nodes
    5. Emit quest_completed event
    6. Return summary with lock_in_delta and edges_created
    """
```

### 2D: New MCP Tools

Add to `tools.py`:

| Tool | Params | Returns |
|---|---|---|
| `sandbox_add_entity` | type, name, profile?, aliases?, avatar?, core_facts?, voice_config? | entity dict |
| `sandbox_add_entity_relationship` | from_id, to_id, rel_type, strength?, context? | relationship dict |
| `sandbox_link_mention` | entity_id, node_id, mention_type? | mention dict |
| `sandbox_maintenance_sweep` | (none) | list of quest candidates |
| `sandbox_quest_accept` | quest_id | quest dict with status=active |
| `sandbox_quest_complete` | quest_id, journal_text?, themes? | completion summary |
| `sandbox_quest_list` | status?, type? | list of quest dicts |

### 2E: New HTTP Endpoints

Add to `server.py`:

```python
# Entity endpoints
GET  /api/entities                 → list all entities with relationship counts
GET  /api/entities/{id}            → entity detail + rels + mentions + versions + quests
GET  /api/entity-graph             → entities + relationships for graph rendering

# Quest endpoints
GET  /api/quests                   → quest list (filterable: ?status=available&type=scavenger)
GET  /api/quests/{id}              → quest detail with targets and journal
POST /api/maintenance-sweep        → trigger sweep, return quest candidates
POST /api/quests/{id}/accept       → mark active
POST /api/quests/{id}/complete     → body: {journal_text, themes}

# Combined graph endpoint (for the two-layer view)
GET  /api/graph-full               → entities + relationships + nodes + edges + clusters + quests
```

---

## Phase 3: Seed Data

### 3A: Entity Seed (`seeds/entity_graph.json`)

Create a seed that includes entities from the v3 artifact. Structure:

```json
{
  "entities": [
    {"id": "ahab", "type": "person", "name": "Ahab", "aliases": ["Zayne"], "avatar": "A", "profile": "...", "core_facts": {...}},
    {"id": "luna", "type": "persona", "name": "Luna", "avatar": "◉", "profile": "...", "voice_config": {...}},
    {"id": "mars-college", "type": "place", "name": "Mars College", "avatar": "◆", "profile": "..."},
    {"id": "luna-engine", "type": "project", "name": "Luna Engine v2.0", "avatar": "◈", "profile": "..."},
    ...
  ],
  "entity_relationships": [
    {"from": "ahab", "to": "luna-engine", "rel_type": "creator", "strength": 1.0},
    {"from": "luna", "to": "ahab", "rel_type": "knows", "strength": 1.0, "context": "Creator — absolute trust"},
    ...
  ],
  "nodes": [...],  // existing knowledge nodes
  "edges": [...],  // existing knowledge edges
  "entity_mentions": [
    {"entity_id": "luna-engine", "node_id": "k_actors", "mention_type": "subject"},
    ...
  ],
  "clusters": [...]
}
```

Use the ENTITIES, RELATIONSHIPS, KNOWLEDGE_NODES, and implicit mention links from `quest_habit_v3.jsx` as the source data. The artifact has ~14 entities, ~17 relationships, ~13 knowledge nodes with entity links.

### 3B: Update `sandbox_seed()` to Handle Entities

When seeding, load entities → entity_relationships → nodes → edges → entity_mentions → compute lock-ins → run maintenance_sweep to pre-generate quests.

---

## Phase 4: Frontend — Entity Graph View

### 4A: New View: `EntityGraphView.jsx`

**This is the main deliverable.** A two-layer interactive graph.

**Layer 1 (Primary): Entity Graph**
- Source: `/api/entity-graph` → entities + entity_relationships
- Rendering: Portrait-style circles with avatars, colored by entity type
- Edges: Typed relationship lines with labels (creator, collaborator, embodies, etc.)
- Size: Proportional to mention count
- Selection: Click entity → opens EntityDetail panel

**Layer 2 (Secondary, toggleable): Knowledge Graph**
- Source: nodes linked to selected entity via entity_mentions
- Rendering: Small orbiting dots around parent entity
- Colored by knowledge type (FACT=cyan, DECISION=purple, etc.)
- Each dot shows lock-in state via opacity/animation

**Quest Indicators:**
- Entities with active quests get a pulsing ring
- Urgent quests get red indicator badge
- Completed quests show green check

**Lock-In Visualization (RESTORE FROM V2):**
- Lock-in ring around every entity node (partial circle showing %)
- Lock-in state color: drifting=#64748b, fluid=#3b82f6, settled=#22c55e, crystallized=#f59e0b
- Drifting nodes get subtle breathing animation
- Drifting threshold is 0.20 (NOT 0.30)

**Interaction:**
- Click entity → detail panel slides in from right
- Click background → deselect
- Hover entity → highlight connected entities, dim unconnected
- Toggle buttons: KNOWLEDGE ON/OFF, LABELS ON/OFF

**Design reference:** See `quest_habit_v3.jsx` EntityGraph component for the SVG rendering approach, color system, and interaction patterns. The Observatory version uses `react-force-graph-2d` instead of manual SVG positioning, but the visual style should match.

### 4B: Component: `EntityDetail.jsx`

Tabbed detail panel (right side, 360px wide):

**Portrait Header:**
- Avatar circle with entity type color + border
- Name, type label, version number, mention count
- Alias pills

**Tabs:**
1. **PROFILE** — Core facts table, voice config (personas), profile text (Crimson Pro serif), relationship list with typed arrows
2. **KNOWLEDGE** — Knowledge nodes linked via entity_mentions, each showing lock-in ring + state + quest badge if applicable
3. **QUESTS** — Active + completed + failed quests targeting this entity, expandable with objective, investigation metrics, journal entries
4. **HISTORY** — Entity version timeline (create → update → synthesize → rollback) with diff summaries

### 4C: View: `QuestBoard.jsx`

New top-level tab in App.jsx.

**Layout:**
- Left: Filterable quest list (status: all/available/active/history, type filters)
- Right: Quest detail panel when selected

**Quest Card:**
- Type icon + color badge
- Title + subtitle (subtitle in Crimson Pro italic)
- Entity target pills (colored by entity type)
- Priority indicator (urgent = red !)
- Status indicator (✓ complete, ✗ failed)

**Quest Detail (expanded):**
- Full objective text
- Target entities with portrait mini-cards
- Investigation metrics: recalls, sources, hops
- Reward metrics: base reward, scaled reward (level scaling), target lock-in
- Journal prompt (if side quest)
- Journal entry (if complete) — Crimson Pro italic with theme pills
- Fail note (if failed)
- Source attribution (what generated this quest)

### 4D: View: `Journal.jsx`

New top-level tab in App.jsx.

**Layout:** Centered column (520px max), vertical scroll

**Each Entry:**
- Quest title + completion date
- Journal text in Crimson Pro serif italic, with left border accent
- Theme pills
- Lock-in delta + edges created
- Linked entity pills

**Design reference:** See JournalView in `quest_habit_v3.jsx` for exact styling.

### 4E: Update App.jsx Tab Routing

```jsx
// Current tabs:  Graph | Timeline | Replay
// New tabs:      Entities | Quests | Journal | Graph | Timeline | Replay
```

"Entities" becomes the default/first tab. The existing "Graph" tab stays as the raw knowledge graph view (for debugging). "Entities" is the human-facing view.

### 4F: Update store.js

Add to Zustand store:

```javascript
// Entity state
entities: [],
entityRelationships: [],
selectedEntityId: null,
entityDetail: null,  // full entity with rels, mentions, versions, quests

// Quest state
quests: [],
selectedQuestId: null,

// Actions
fetchEntities: async () => {...},
fetchEntityDetail: async (id) => {...},
fetchQuests: async (filters) => {...},
selectEntity: (id) => {...},
selectQuest: (id) => {...},
runMaintenanceSweep: async () => {...},
```

### 4G: Update api.js

```javascript
export const api = {
  // ... existing endpoints ...
  
  // Entity endpoints
  entities: () => fetchJSON('/api/entities'),
  entityDetail: (id) => fetchJSON(`/api/entities/${id}`),
  entityGraph: () => fetchJSON('/api/entity-graph'),
  
  // Quest endpoints
  quests: (filters = {}) => {
    const params = new URLSearchParams(filters).toString()
    return fetchJSON(`/api/quests?${params}`)
  },
  questDetail: (id) => fetchJSON(`/api/quests/${id}`),
  maintenanceSweep: () => fetchJSON('/api/maintenance-sweep', { method: 'POST' }),
  questAccept: (id) => fetchJSON(`/api/quests/${id}/accept`, { method: 'POST' }),
  questComplete: (id, body) => fetchJSON(`/api/quests/${id}/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }),
}
```

---

## Phase 5: Lock-In Visualization (Restore + Enhance)

This is what dropped between v2 and v3. Restore it everywhere.

### Every Entity Node in EntityGraphView:
- **Lock-in ring:** Partial circle around node, proportion = lock-in value
- **State color:** drifting=#64748b, fluid=#3b82f6, settled=#22c55e, crystallized=#f59e0b
- **Breathing animation** on drifting nodes (opacity pulses 0.15 → 0.30)
- **State label** below entity name (small, dimmed)

### Every Knowledge Dot:
- **Opacity** mapped to lock-in (drifting nodes nearly invisible)
- **Breathing** animation on drifting nodes
- **Lock-in bar** in knowledge tab of entity detail

### Quest Board:
- **Target lock-in** displayed for each quest
- **Reward scaling chart** (bar chart showing reward vs lock-in, like v2 mechanics view)
- **Lock-in delta** on completed quests ("this quest moved Memory Matrix from 0.65 → 0.71")

### Status Bar:
- **Lock-in distribution** — count of drifting/fluid/settled/crystallized nodes
- **Average lock-in** across all nodes

### Lock-In State Thresholds (CORRECT values everywhere):
```
drifting:     [0.00, 0.20)  — gray, breathing
fluid:        [0.20, 0.70)  — blue
settled:      [0.70, 0.85)  — green
crystallized: [0.85, 1.00]  — amber/gold
```

---

## Build Order

| Phase | What | Validation | Effort |
|-------|------|-----------|--------|
| 1A | Schema migration (new tables) | Tables created on init | 30min |
| 1B | Fix lock-in threshold 0.30 → 0.20 | `lock_in_state(0.15)` returns "drifting" | 5min |
| 2A | Entity CRUD on SandboxMatrix | `sandbox_add_entity` creates entity + version 1 | 1hr |
| 2B | Entity relationships + mentions | Link entities, mention counts update | 30min |
| 2C | Maintenance sweep | `sandbox_maintenance_sweep` returns quest candidates | 1.5hr |
| 2D | Quest lifecycle (accept/complete/fail) | Full quest flow with journal + INSIGHT creation | 1hr |
| 2E | New MCP tools + HTTP endpoints | All tools visible in Claude Desktop, curl works | 1hr |
| 3A | Entity seed data (from v3 artifact) | `sandbox_seed("entity_graph")` loads everything | 45min |
| 3B | Seed runs maintenance_sweep on load | Quests auto-generated from graph health | 15min |
| 4A | EntityGraphView (two-layer graph) | Entities render with portraits, relationships, knowledge dots | 2hr |
| 4B | EntityDetail panel (tabbed) | Profile, Knowledge, Quests, History tabs all work | 1.5hr |
| 4C | QuestBoard view | Quest list + detail + entity badges | 1hr |
| 4D | Journal view | Completed quest reflections render | 30min |
| 4E | Lock-in visualization restoration | Rings, colors, breathing, state labels everywhere | 1hr |
| 4F | App.jsx routing + store + api updates | New tabs work, data flows | 30min |

**Total estimate:** ~12 hours of focused work. Backend first (phases 1-3), then frontend (phases 4-5).

**Critical path:** Phase 2C (maintenance_sweep) is the hardest. It needs to analyze graph health across multiple dimensions. Start simple — implement 2-3 checks first, add more iteratively.

---

## Visual Design Constants

Use these everywhere for consistency with the v3 artifact:

```javascript
// Entity type colors
const ENTITY_TYPES = {
  person:  { color: "#f472b6", icon: "●", bg: "#2a1228" },
  persona: { color: "#c084fc", icon: "◉", bg: "#1e1638" },
  place:   { color: "#34d399", icon: "◆", bg: "#0f2418" },
  project: { color: "#67e8f9", icon: "◈", bg: "#0e2a2e" },
}

// Lock-in states (CORRECTED thresholds)
const LOCK_IN = {
  drifting:     { color: "#64748b", range: [0, 0.20], label: "Drifting", icon: "◌" },
  fluid:        { color: "#3b82f6", range: [0.20, 0.70], label: "Fluid", icon: "◐" },
  settled:      { color: "#22c55e", range: [0.70, 0.85], label: "Settled", icon: "◉" },
  crystallized: { color: "#f59e0b", range: [0.85, 1.0], label: "Crystallized", icon: "◆" },
}

// Quest type colors
const QUEST_TYPES = {
  main:          { color: "#c084fc", icon: "⚔", label: "Main Quest" },
  side:          { color: "#67e8f9", icon: "✎", label: "Side Quest" },
  contract:      { color: "#f87171", icon: "⚡", label: "Contract" },
  treasure_hunt: { color: "#fbbf24", icon: "◈", label: "Treasure Hunt" },
  scavenger:     { color: "#34d399", icon: "◇", label: "Scavenger" },
}

// Relationship type colors
const REL_TYPES = {
  creator:      { color: "#c084fc", dash: false },
  collaborator: { color: "#67e8f9", dash: false },
  friend:       { color: "#f472b6", dash: false },
  embodies:     { color: "#fbbf24", dash: true },
  located_at:   { color: "#34d399", dash: true },
  works_on:     { color: "#67e8f9", dash: true },
  knows:        { color: "#64748b", dash: true },
  depends_on:   { color: "#f87171", dash: true },
  enables:      { color: "#34d399", dash: false },
}

// Fonts
// System: 'JetBrains Mono', 'SF Mono', monospace
// Narrative: 'Crimson Pro', serif (for profiles, journal, objectives)
// Background: #0a0c10 (slightly warmer than Observatory's #06060e)
```

---

## Validation Checklist

### Backend
- [ ] Schema migration runs cleanly (new tables created)
- [ ] `lock_in_state(0.15)` returns "drifting" (not "fluid")
- [ ] `sandbox_add_entity("person", "Test")` creates entity + version 1
- [ ] `sandbox_add_entity_relationship(...)` creates typed connection
- [ ] `sandbox_link_mention(entity_id, node_id)` updates mention_count
- [ ] `sandbox_maintenance_sweep()` returns quest candidates from graph analysis
- [ ] `sandbox_quest_accept(quest_id)` changes status to active
- [ ] `sandbox_quest_complete(quest_id, journal, themes)` creates INSIGHT node + journal row
- [ ] `sandbox_seed("entity_graph")` loads entities + relationships + mentions + quests

### Frontend
- [ ] EntityGraphView renders entities as portrait circles with correct type colors
- [ ] Relationship lines show between entities with type labels
- [ ] Knowledge nodes orbit selected entity when KNOWLEDGE toggle is on
- [ ] Lock-in rings visible on every entity node (proportional, colored by state)
- [ ] Drifting nodes breathe (opacity animation)
- [ ] Quest indicators pulse on entities with active quests
- [ ] EntityDetail panel opens on click with 4 tabs
- [ ] QuestBoard view shows filterable quest list with entity badges
- [ ] Journal view renders completed quest reflections in Crimson Pro
- [ ] Status bar shows entity counts + lock-in distribution

### Integration
- [ ] Seed → entities appear in EntityGraphView
- [ ] Seed → maintenance_sweep generates quests automatically
- [ ] Accept quest in QuestBoard → status updates in real time (WebSocket)
- [ ] Complete quest → INSIGHT node created → appears in entity's Knowledge tab
- [ ] Complete quest → lock-in recalculated → lock-in ring updates in graph
- [ ] All existing Observatory features (Graph, Timeline, Replay) still work

---

## Critical Notes

1. **Don't break existing functionality.** The current Graph/Timeline/Replay views must keep working. Entity system is additive.
2. **Entity system is separate from knowledge nodes.** Entities live in `entities` table. Knowledge lives in `nodes` table. They connect through `entity_mentions`. Don't merge them.
3. **Lock-in threshold is 0.20, not 0.30.** This is from the Memory Economy spec. Fix it in backend AND frontend.
4. **Maintenance sweep is the quest generator.** It's not random — quests emerge from real graph health issues. Every quest should have a clear `source` explaining what triggered it.
5. **Quest journal creates INSIGHT nodes.** This closes the loop: quest → reflection → knowledge → lock-in growth → new quests. The system feeds itself.
6. **The v3 artifact is a design reference, not production code.** Don't copy-paste it. Use its data model and visual design, but implement against the Observatory's architecture (Zustand store, REST API, WebSocket events, react-force-graph-2d).
7. **Fonts:** Load JetBrains Mono and Crimson Pro from Google Fonts in `index.html`. System monospace as fallback.
