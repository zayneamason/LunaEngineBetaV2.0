# HANDOFF: Aibrarian Frontend — Eclissi Integration

**Date:** 2026-03-01  
**Author:** Ahab (via design session with Claude)  
**Target:** Claude Code implementation  
**Priority:** High — needed before ROSA March 2026 demo  
**Project Root:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root`

---

## WHAT THIS IS

Add a full library management page to the Eclissi Shell. Currently there's no Aibrarian
page — the tab system supports it but the view doesn't exist yet. The Aibrarian is Luna's
library — she walks through it, pulls books, annotates, connects knowledge to Memory Matrix.

## REFERENCE PROTOTYPES

**Location:** `frontend/src/eclissi/prototypes/` (standalone JSX, inline styles)
- `aibrarian_library_v3.jsx` — **PRIMARY REFERENCE** (857 lines, full implementation)
- `luna_aperture_dial.jsx` — Aperture control component (610 lines)

**Also available as Claude.ai artifacts** — paste JSX to preview.

These are design prototypes with inline styles. Production code should follow the existing
Eclissi patterns: widget components, `useLunaAPI` hook, Tailwind classes.

---

## EXISTING CODEBASE (what you're working with)

```
frontend/src/
├── App.jsx
├── hooks/
│   ├── useLunaAPI.js          ← REST API hook (127.0.0.1:8000)
│   ├── useIdentity.js         ← FaceID identity
│   ├── useNavigation.js       ← Tab navigation bus
│   ├── useOrbState.js         ← Luna orb state
│   └── ...
├── eclissi/
│   ├── EclissiShell.jsx       ← Main shell (tabs, widgets, panels)
│   ├── EclissiHome.jsx        ← Home/chat view
│   ├── components/
│   │   ├── ShellHeader.jsx    ← Header with orb, tabs
│   │   ├── WidgetDock.jsx     ← Bottom widget dock
│   │   ├── RightPanel.jsx     ← Right panel for details
│   │   ├── TabButton.jsx
│   │   └── PlaceholderView.jsx
│   ├── widgets/               ← Widget components (Engine, Memory, QA, etc.)
│   ├── knowledge/             ← Entity/extraction cards
│   └── styles/
├── kozmo/                     ← Kozmo app (separate tab)
└── observatory/               ← Observatory app (separate tab)
```

**Key patterns:**
- Tabs defined in `EclissiShell.jsx`: `['eclissi', 'studio', 'kozmo', 'guardian', 'observatory']`
- API calls via `useLunaAPI` → `http://127.0.0.1:8000`
- Aibrarian MCP tools are at the backend — frontend needs REST endpoints or direct MCP bridge
- Widgets dock at bottom, right panel for detail views

---

## ARCHITECTURE: THE FOUR LAYERS

The Aibrarian page is a vertical stack. Each layer has clear responsibility.

### Layer 1: Query Layer (pinned top)
- Search input: "Search collections, tags, documents..."
- Filter pills: ALL | SETTLED | FLUID | DRIFTING (with counts)
- Sort dropdown: LOCK-IN | RECENT | DOCS | NAME
- Stays pinned while collections scroll

### Layer 2: Collections (scrollable middle)
- **Compact row** (default): state icon, color bar, name, annotation count, stats pills (D/E/W), lock-in meter, state label, actions (INGEST/SHELVE)
- **Expanded row** (click to toggle, only 1 at a time): 3-column grid — stats+tags+lock-in factors | documents list | annotations sidebar
- Column headers: sticky
- Grid template: `24px 1fr 200px 120px 80px 100px`

### Layer 3: Security Layer
- Single compact bar explaining isolation rules
- Three badges: READ-ONLY DEFAULT | PROVENANCE TRACKED | ANNOTATION = BRIDGE
- Governance visualization, not interactive

### Layer 4: Memory Matrix Foundation (bottom)
- Stats: nodes, edges, entities, size
- Lock-in distribution bar (drifting/fluid/settled proportional)
- Bridged collections: which collections have annotations creating Matrix nodes

---

## KEY ARCHITECTURAL DECISIONS

### The Wall (Non-negotiable)
Collections are **read-only sandboxes**. Luna can browse any shelf, but content
does NOT bleed into Memory Matrix unless she deliberately annotates. Sovereignty
principle applied to knowledge management.

### Annotation as Bridge
Three types: bookmark, note, flag.
Each creates a Memory Matrix node with `source=aibrarian` provenance.
ONLY pathway from collection → native memory.

### Status Model
- `connected` (green) = active, Luna can query it
- `shelved` (gray) = inactive, not in recall pipeline
- `ingesting` (yellow, pulsing) = actively processing

### Lock-in Engine (Collection-adapted)
Same formula as memory nodes, MUCH slower decay (books get dusty, don't vanish):
- settled: ~16 day half-life (vs 17 min for memory nodes)
- fluid: ~1.6 day half-life
- drifting: ~3.8 hour half-life

Factors: retrieval (0.4), reinforcement (0.3), network (0.2), tagSiblings (0.1)

See `computeCollectionLockIn()` in v3 prototype for the full formula.

---

## API / MCP BRIDGE

The Aibrarian backend runs as MCP tools. Frontend needs either:

**Option A: REST endpoints** (matches existing `useLunaAPI` pattern)
Add routes to the Luna API server that proxy to Aibrarian MCP tools:
```
GET  /api/aibrarian/collections          → aibrarian_list
GET  /api/aibrarian/collections/:id/stats → aibrarian_stats
POST /api/aibrarian/collections/:id/search → aibrarian_search
POST /api/aibrarian/collections/:id/ingest → aibrarian_ingest
POST /api/aibrarian/collections/:id/ingest-dir → aibrarian_ingest_directory
GET  /api/aibrarian/collections/:id/docs  → aibrarian_list_documents
```

**Option B: Direct MCP from frontend** (WebSocket bridge)
Similar to how Observatory connects — direct MCP tool calls from the browser.

Either way, the frontend hook interface should look like:
```javascript
// useAibrarian.js
export function useAibrarian() {
  return {
    listCollections: async () => { /* aibrarian_list */ },
    getStats: async (collection) => { /* aibrarian_stats */ },
    search: async (collection, query, type) => { /* aibrarian_search */ },
    ingest: async (collection, path) => { /* aibrarian_ingest */ },
    ingestDir: async (collection, dir, recursive) => { /* aibrarian_ingest_directory */ },
    listDocs: async (collection, skip, limit) => { /* aibrarian_list_documents */ },
  };
}
```

---

## DESIGN TOKENS

```javascript
const T = {
  bg: "#0a0a12", bgRaised: "#0e0e17", bgPanel: "#12121c", bgCard: "#171723",
  bgInput: "#0f0f19",
  border: "rgba(255,255,255,0.05)", borderHover: "rgba(255,255,255,0.1)",
  text: "#e8e8f0", textSoft: "#9a9ab0", textFaint: "#5a5a70", textMuted: "#3a3a50",
  luna: "#c084fc", memory: "#7dd3fc", voice: "#a78bfa", qa: "#f87171",
  debug: "#fbbf24", prompt: "#34d399", vk: "#fb923c", guardian: "#e09f3e",
  bookmark: "#f59e0b", note: "#a78bfa",
};
// Fonts: DM Sans (body), JetBrains Mono (data), Bebas Neue (labels)
```

Map to Tailwind custom theme or CSS variables.

---

## BUILD ORDER

### Phase 1: Add Aibrarian page to Eclissi Shell
1. Create `frontend/src/eclissi/AibrarianView.jsx`
2. Add to tab routing in `EclissiShell.jsx` (likely replace `PlaceholderView` for studio tab, or add new tab)
3. Port v3 prototype layout (4 layers) using Tailwind
4. Create `useAibrarian` hook
5. Wire to Aibrarian MCP tools (mock data first, then real)
6. **Verify:** Page loads in shell, shows collections, rows expand/collapse

### Phase 2: Modals
1. Ingest modal (directory/file/url modes)
2. New collection modal
3. Wire to `aibrarian_ingest` / `aibrarian_ingest_directory`
4. **Verify:** Can create collection, trigger ingest

### Phase 3: Lock-in Engine
1. Create `frontend/src/eclissi/utils/lockIn.js` — port from prototype
2. Lock-in meter component
3. State classification + filter/sort
4. **Verify:** Collections show scores, filter/sort works

### Phase 4: Annotations
1. Annotation sidebar in expanded row
2. Create annotation → bridge to Memory Matrix node
3. Bridged collections in Matrix panel
4. **Verify:** Create annotation, see in Matrix bridge list

### Phase 5: Aperture Dial (separate PR)
1. Port `luna_aperture_dial.jsx` as shared component
2. Integrate into ShellHeader (replaces/augments orb)
3. Hover → dial overlay, drag or click presets
4. **Verify:** Dial works, value persists

---

## NON-NEGOTIABLES

1. **Collections sandboxed** — never auto-merge into Matrix
2. **Provenance tracked** — every annotation records source
3. **Scales to 30+ collections** — compact rows, filter, sort
4. **Offline-first** — local only
5. **Matches Eclissi visual language** — dark theme, existing component patterns

---

## FILES TO CREATE/MODIFY

```
frontend/src/
├── eclissi/
│   ├── EclissiShell.jsx               ← MODIFY (add aibrarian tab routing)
│   ├── AibrarianView.jsx              ← NEW (main page)
│   ├── components/
│   │   ├── LockInMeter.jsx            ← NEW
│   │   ├── CollectionRow.jsx          ← NEW (compact + expanded)
│   │   ├── IngestModal.jsx            ← NEW
│   │   ├── NewCollectionModal.jsx     ← NEW
│   │   ├── ApertureDial.jsx           ← NEW (Phase 5)
│   │   └── LunaOrb.jsx               ← NEW (Phase 5)
│   └── utils/
│       └── lockIn.js                  ← NEW (collection lock-in engine)
├── hooks/
│   └── useAibrarian.js               ← NEW
└── eclissi/prototypes/                ← REFERENCE ONLY
    ├── README.md
    ├── HANDOFF_AIBRARIAN_FRONTEND.md  ← THIS FILE
    ├── aibrarian_library_v3.jsx       ← PRIMARY PROTOTYPE
    └── luna_aperture_dial.jsx         ← APERTURE PROTOTYPE
```

---

## MOCK DATA

15 collections in v3 prototype `RAW_COLLECTIONS`. Key ones:

| ID | Docs | Purpose |
|----|------|---------|
| dataroom | 18 | Investor docs |
| luna_architecture | 34 | Engine specs |
| kinoni_deployment | 12 | Uganda ICT Hub |
| maxwell_case | 900 | Legal (scale stress test) |
| rosa_conference | 8 | ROSA demo prep |
| funding_research | 28 | Grant analysis |
| continental_council | 16 | Indigenous governance |

Matrix mock: 24,478 nodes, 23,912 edges, 79 entities, 124.2 MB
