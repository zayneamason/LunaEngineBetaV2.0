# CLAUDE CODE HANDOFF: Quest Board Integration into Observatory Sandbox

## CONTEXT

**What exists:**
- Memory Matrix Observatory Sandbox at `Tools/MemoryMatrix_SandBox/`
- React + Vite frontend (`:5173`) with Graph, Timeline, Replay views
- FastAPI backend (`:8100`) with SQLite + FTS5 + sqlite-vec
- Zustand store, WebSocket event bus, force-graph-2d rendering
- Existing components: `NodeCard`, `LockInRing`, `ClusterHull`, `TuningPanel`

**What we're adding:**
- Quest Board system — quests generated from graph health analysis
- Entity layer — first-class people/personas/places/projects (not just memory nodes)
- Journal system — reflective entries from quest completion
- Lock-in visualization upgrade (the artifact prototype lost the drift/lock-in visuals — fix that)

**Design prototype:** `_design_reference/quest_habit_v3.jsx` (React artifact, ~1266 lines)
- This is a DESIGN REFERENCE, not production code
- Extract the data model, visual patterns, and interaction flow
- Adapt to Observatory's existing architecture (Zustand store, API client, force-graph)

---

## PHASE 1: Schema Migration

### New tables to add to `mcp_server/schema.sql`:

```sql
-- ── Entities (first-class objects: people, personas, places, projects) ──
CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('person', 'persona', 'place', 'project')),
    name TEXT NOT NULL,
    aliases TEXT DEFAULT '[]',
    avatar TEXT DEFAULT '',
    core_facts TEXT DEFAULT '{}',
    profile TEXT,
    voice_config TEXT,
    mention_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS entity_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_entity TEXT NOT NULL,
    to_entity TEXT NOT NULL,
    relationship TEXT NOT NULL CHECK(relationship IN (
        'creator', 'collaborator', 'friend', 'embodies',
        'located_at', 'works_on', 'knows', 'depends_on', 'enables'
    )),
    strength REAL DEFAULT 1.0,
    context TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (from_entity) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (to_entity) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS entity_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    mention_type TEXT DEFAULT 'reference' CHECK(mention_type IN ('subject', 'reference', 'context')),
    created_at TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS entity_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    change_type TEXT NOT NULL CHECK(change_type IN ('create', 'update', 'synthesize', 'rollback')),
    summary TEXT NOT NULL,
    snapshot TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS quests (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('main', 'side', 'contract', 'treasure_hunt', 'scavenger')),
    status TEXT NOT NULL DEFAULT 'available' CHECK(status IN ('available', 'active', 'complete', 'failed', 'expired')),
    priority TEXT DEFAULT 'medium' CHECK(priority IN ('low', 'medium', 'high', 'urgent')),
    title TEXT NOT NULL,
    subtitle TEXT,
    source TEXT,
    objective TEXT,
    journal_prompt TEXT,
    target_lock_in REAL,
    reward REAL DEFAULT 0.10,
    investigation TEXT DEFAULT '{}',
    expires_at TEXT,
    completed_at TEXT,
    failed_at TEXT,
    fail_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quest_entities (
    quest_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    PRIMARY KEY (quest_id, entity_id),
    FOREIGN KEY (quest_id) REFERENCES quests(id) ON DELETE CASCADE,
    FOREIGN KEY (entity_id) REFERENCES entities(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS quest_knowledge (
    quest_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    PRIMARY KEY (quest_id, node_id),
    FOREIGN KEY (quest_id) REFERENCES quests(id) ON DELETE CASCADE,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS journal_entries (
    id TEXT PRIMARY KEY,
    quest_id TEXT NOT NULL,
    text TEXT NOT NULL,
    themes TEXT DEFAULT '[]',
    lock_in_delta REAL DEFAULT 0.0,
    edges_created INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (quest_id) REFERENCES quests(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
CREATE INDEX IF NOT EXISTS idx_entity_rels_from ON entity_relationships(from_entity);
CREATE INDEX IF NOT EXISTS idx_entity_rels_to ON entity_relationships(to_entity);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_entity ON entity_mentions(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_node ON entity_mentions(node_id);
CREATE INDEX IF NOT EXISTS idx_quests_status ON quests(status);
CREATE INDEX IF NOT EXISTS idx_quests_type ON quests(type);
```

### Seed data

Create `mcp_server/seeds/entities_seed.py` with the specimen data from the prototype artifact. Key entities to seed: `ahab`, `luna`, `ben-franklin`, `the-dude`, `marzipan`, `tarsila`, `eden-team`, `mars-college`, `luna-engine`, `memory-matrix`, `kozmo`

Key relationships: creator, collaborator, embodies, located_at, works_on, knows, depends_on, enables

Key quests: Graph Pipeline Repair (side), Delegation Crossroads (contract), The Voight-Kampff Question (treasure_hunt), Mapping Eden (scavenger), Who Is Tarsila? (scavenger), Mars College: Memory Continuity (main), Portal Breakthrough (complete + journal entry), HTTP Threading Notes (failed)

---

## PHASE 2: Backend — New Endpoints + Quest Generator

### New API endpoints:

```
GET  /api/entities                    → all entities
GET  /api/entities/{id}               → entity + relationships + mentions + versions
GET  /api/entity-graph                → entities + entity_relationships (graph rendering)
GET  /api/quests                      → all quests (filterable by status, type)
GET  /api/quests/{id}                 → quest detail + linked entities + knowledge
POST /api/quests/{id}/accept          → status → active
POST /api/quests/{id}/complete        → status → complete, trigger journal + reinforce
POST /api/quests/{id}/fail            → status → failed
GET  /api/journal                     → all journal entries
POST /api/quest-scan                  → run maintenance_sweep, return generated quests
```

### New MCP tools in `mcp_server/tools.py`:

```python
sandbox_add_entity(type, name, aliases, core_facts, profile, avatar, voice_config)
sandbox_add_entity_rel(from_entity, to_entity, relationship, strength, context)
sandbox_add_entity_mention(entity_id, node_id, mention_type)
sandbox_quest_scan()
sandbox_quest_accept(quest_id)
sandbox_quest_complete(quest_id, journal_text, themes)
sandbox_quest_fail(quest_id, fail_note)
sandbox_list_quests(status_filter)
```

### Quest Generator: `mcp_server/quest_generator.py`

Core new module. Wraps Librarian's maintenance_sweep() pattern:

```python
async def quest_scan(matrix: SandboxMatrix) -> list[dict]:
    """
    Analyze graph health and generate quests.
    
    Scans for:
    1. Orphan entities: mention_count > 0 but no profile → SCAVENGER
    2. Stale entities: not updated in 30+ days, active mentions → TREASURE_HUNT
    3. Fragmented entities: many mentions, few relationships → SCAVENGER
    4. Contradicting nodes: DECISION nodes in same cluster, opposing → CONTRACT
    5. Unreflected sessions: OUTCOME nodes with no INSIGHT → SIDE (journal)
    6. Drifting high-value: high mention/access but lock_in < threshold → TREASURE_HUNT
    7. Project milestones: project entities with approaching deadlines → MAIN
    """
```

Quest reward scaling (uses existing lock-in):
```python
def quest_reward(base: float, target_lock_in: float) -> float:
    return max(base * (1.0 - target_lock_in * 0.8), base * 0.1)
```

Quest completion flow:
1. Create INSIGHT node with `source: "quest_reflection"` tag
2. Call existing `reinforce_node()` on target knowledge nodes
3. Create entity_mentions linking new INSIGHT → target entities
4. Update entity_versions if quest changed entity profile
5. Emit `quest_completed` event on bus

---

## PHASE 3: Frontend — New Views + Graph Upgrade

### File structure additions:
```
frontend/src/
├── views/
│   ├── GraphView.jsx        ← MODIFY: add entity layer toggle
│   ├── QuestBoard.jsx       ← NEW
│   ├── Journal.jsx           ← NEW
│   ├── Timeline.jsx          ← existing
│   └── Replay.jsx            ← existing
├── components/
│   ├── EntityCard.jsx         ← NEW: portrait-style entity detail
│   ├── QuestCard.jsx          ← NEW: quest detail with expand
│   ├── JournalEntry.jsx       ← NEW: Crimson Pro diary-voice
│   ├── LockInRing.jsx         ← ENHANCE: drift animation + state colors
│   ├── NodeCard.jsx           ← existing
│   └── ...existing
└── store.js                   ← MODIFY: add entity/quest state
```

### Store additions (store.js):
```javascript
entities: [],
entityRelationships: [],
quests: [],
journalEntries: [],
selectedEntityId: null,
showEntityLayer: true,
showKnowledgeOrbit: true,
fetchEntities: async () => { ... },
fetchQuests: async () => { ... },
fetchJournal: async () => { ... },
selectEntity: (id) => set({ selectedEntityId: id }),
runQuestScan: async () => { ... },
acceptQuest: async (id) => { ... },
completeQuest: async (id, journalText, themes) => { ... },
```

### API client additions (api.js):
```javascript
entities: () => fetchJSON('/api/entities'),
entityDetail: (id) => fetchJSON(`/api/entities/${id}`),
entityGraph: () => fetchJSON('/api/entity-graph'),
quests: (status) => fetchJSON(`/api/quests${status ? '?status=' + status : ''}`),
questAccept: (id) => fetchJSON(`/api/quests/${id}/accept`, { method: 'POST' }),
questComplete: (id, text, themes) => fetchJSON(`/api/quests/${id}/complete`, {
  method: 'POST', headers: {'Content-Type':'application/json'},
  body: JSON.stringify({ journal_text: text, themes }),
}),
questScan: () => fetchJSON('/api/quest-scan', { method: 'POST' }),
journal: () => fetchJSON('/api/journal'),
```

### App.jsx tab update:
Current: `['Graph', 'Timeline', 'Replay']`
New: `['Graph', 'Quests', 'Journal', 'Timeline', 'Replay']`

---

## PHASE 4: Lock-In Visual Fix (CRITICAL)

The v3 prototype dropped prominent lock-in/drift visualization. Fix this.

### Lock-in state colors (use everywhere):
```javascript
const LOCK_IN_COLORS = {
  drifting:     '#64748b', // slate gray
  fluid:        '#3b82f6', // blue
  settled:      '#22c55e', // green
  crystallized: '#f59e0b', // amber
};
```

### LockInRing.jsx enhancement:
- Ring color follows lock-in STATE (slate→blue→green→amber), not node type
- Add drift animation for drifting state (pulse 15-30% opacity)
- Accept `state` prop or compute from value

### force-graph-2d nodeCanvasObject enhancement:
```javascript
// Drift effect: oscillate opacity for drifting nodes
if (state === 'drifting') {
  const t = Date.now() / 2000;
  const driftOpacity = 0.15 + 0.15 * Math.sin(t + node.x * 0.1);
  ctx.globalAlpha = driftOpacity;
}
// Lock-in ring uses STATE color, not node type color
ctx.strokeStyle = `${LOCK_IN_COLORS[state]}88`;
```

### Drift CSS animations:
```css
@keyframes questPulse { 0%,100% { opacity:0.5 } 50% { opacity:1 } }
@keyframes drift { 0%,100% { opacity:0.15 } 50% { opacity:0.3 } }
@keyframes fadeUp { from { opacity:0; transform:translateY(6px) } to { opacity:1; transform:translateY(0) } }
```

### Entity graph lock-in:
- Entity nodes show average lock-in of all linked knowledge nodes
- Knowledge orbit dots: size by lock-in, opacity by lock-in
- Nodes below threshold get drift animation
- Drifting: desaturated color, reduced opacity, gentle float

### THRESHOLD NOTE:
Sandbox currently uses 0.30 for drifting boundary. Production uses 0.20.
Keep 0.30 for sandbox. Make it configurable via TuningPanel/params.
The threshold should come from config so it's tunable.

---

## PHASE 5: EntityCard Component
