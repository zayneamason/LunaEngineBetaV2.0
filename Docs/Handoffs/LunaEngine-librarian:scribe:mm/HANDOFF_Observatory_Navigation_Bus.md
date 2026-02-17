# HANDOFF: Observatory Navigation Bus + Live Wiring

## What You're Doing Right Now

Building Layers 2-3 of the Flow Awareness architecture (see `HANDOFF_Layers_2_3_Flow_And_Threads.md`). That work gives Luna the ability to detect conversational flow shifts and manage persistent threads. When that lands, THREAD nodes will appear in the Memory Matrix alongside existing FACT, DECISION, ACTION, etc.

This handoff is the **next piece** — wiring Observatory to be Luna's live control panel instead of a hollow sandbox, and building the navigation bus that connects every reference across Eclissi, Observatory, and Kozmo into clickable doorways.

---

## Current State

Three worlds exist in the frontend. They share `AnnotatedText` for entity highlighting, but clicking an entity in Chat has nowhere to go. Clicking a quest's target entity in Observatory doesn't jump to the Entities tab. Nothing cross-navigates.

```
ECLISSI (main view)
├── ChatPanel           — entities highlighted, onEntityClick = noop
├── ThoughtStream       — extraction events, no click-through  
├── ConsciousnessMonitor
├── ConversationCache
├── ContextDebugPanel
├── MemoryMonitorPanel
├── QA Panel / VK Panel
│
├── KOZMO (full takeover, bool toggle)
│   ├── Codex / Scribo / Lab
│   └── KozmoChat
│
└── OBSERVATORY (full takeover, bool toggle)
    ├── Entities / Quests / Journal / Graph / Timeline / Replay / Settings
    └── DB toggle: sandbox | production ← REMOVE sandbox
```

**Mode switching is boolean:** `kozmoMode` and `observatoryMode` in `App.jsx`. No deep-linking. No way to say "open Observatory at Entities tab with entity X selected."

---

## Part 1: Kill Sandbox Mode

Remove the sandbox/production toggle from Observatory. It's production only now.

### Files to change:

**`frontend/src/observatory/ObservatoryApp.jsx`:**
- Remove `dbMode` and `switchDb` from store destructure
- Remove the DB toggle button from the header
- On mount, just fetch data directly (no `switchDb('production')` call — the backend should default to production)

**`frontend/src/observatory/store.js`:**
- Remove `dbMode` state
- Remove `switchDb` action
- `handleEvent`: Remove sandbox_reset/sandbox_seeded handlers (these are sandbox-only events)
- Initial fetch on store creation can assume production

**`frontend/src/observatory/api.js`:**
- Remove `switchDb` method
- All other endpoints stay — they just hit production Matrix

**Backend `observatory_server.py` (or equivalent):**
- Remove `/api/switch-db` endpoint
- Default and only database = production Matrix (`data/luna_engine.db`)
- Keep all other endpoints as-is

---

## Part 2: Navigation Bus

A tiny zustand store that any component can write to and any app shell can read from.

### Create: `frontend/src/hooks/useNavigation.js`

```javascript
/**
 * Cross-app navigation bus.
 * 
 * Any component can call navigate() to request a view change.
 * App.jsx listens and switches modes/tabs/selections accordingly.
 * 
 * This is the connective tissue between Chat, Observatory, and Kozmo.
 */
import { create } from 'zustand'

export const useNavigation = create((set, get) => ({
  // Current navigation request (consumed by App.jsx)
  pending: null,

  /**
   * Request navigation to a specific view.
   * 
   * Examples:
   *   navigate({ to: 'observatory', tab: 'entities', entityId: 'e_abc' })
   *   navigate({ to: 'observatory', tab: 'quests', questId: 'q_def' })
   *   navigate({ to: 'observatory', tab: 'graph', nodeId: 'n_ghi', zoom: 'solarsystem' })
   *   navigate({ to: 'observatory', tab: 'journal', filename: '2026-02-16-001.md' })
   *   navigate({ to: 'observatory', tab: 'timeline', eventType: 'node_created' })
   *   navigate({ to: 'kozmo', view: 'codex', entitySlug: 'luna' })
   *   navigate({ to: 'eclissi' })  // back to main
   */
  navigate: (request) => set({ pending: { ...request, _ts: Date.now() } }),

  /**
   * Consume the pending request (called by App.jsx after acting on it).
   */
  consume: () => set({ pending: null }),
}))
```

That's it. 30 lines. No framework, no router library. Just a shared mailbox.

### Wire into App.jsx

```javascript
import { useNavigation } from './hooks/useNavigation'

// Inside Eclissi component:
const { pending, consume } = useNavigation()

useEffect(() => {
  if (!pending) return

  switch (pending.to) {
    case 'observatory':
      setObservatoryMode(true)
      setKozmoMode(false)
      // Deep-link info is passed to ObservatoryApp via props or store
      break
    case 'kozmo':
      setKozmoMode(true)
      setObservatoryMode(false)
      break
    case 'eclissi':
      setKozmoMode(false)
      setObservatoryMode(false)
      break
  }

  consume()
}, [pending])
```

### Wire into ObservatoryApp.jsx

Observatory needs to read the navigation request to know which tab to activate and what to select:

```javascript
import { useNavigation } from '../hooks/useNavigation'

export default function ObservatoryApp({ onBack }) {
  const [tab, setTab] = useState('Entities')
  const { pending } = useNavigation()
  const { selectEntity, fetchEntityDetail, selectQuest, fetchQuestDetail } = useObservatoryStore()

  // Handle deep-link navigation
  useEffect(() => {
    if (!pending || pending.to !== 'observatory') return

    if (pending.tab) {
      // Capitalize first letter to match tab names
      const tabName = pending.tab.charAt(0).toUpperCase() + pending.tab.slice(1)
      if (TABS.includes(tabName)) {
        setTab(tabName)
      }
    }

    // Deep-link to specific items
    if (pending.entityId) {
      selectEntity(pending.entityId)
      fetchEntityDetail(pending.entityId)
    }
    if (pending.questId) {
      selectQuest(pending.questId)
    }
    if (pending.nodeId) {
      // Graph view deep-link handled by GraphView reading from store
      useObservatoryStore.getState().fetchSolarSystem(pending.nodeId)
    }
  }, [pending])

  // ... rest unchanged
}
```

### Wire into AnnotatedText.jsx

The key change — `onEntityClick` now has a real destination:

**In any component that renders AnnotatedText without a local handler:**

```javascript
import { useNavigation } from '../hooks/useNavigation'

// In ChatPanel, ThoughtStream, ConversationCache, etc:
const { navigate } = useNavigation()

<AnnotatedText
  text={text}
  entities={entities}
  onEntityClick={(entityId) => navigate({
    to: 'observatory',
    tab: 'entities',
    entityId,
  })}
/>
```

**In Observatory views that already have local entity click handlers** (EntitiesView, JournalView), keep the local handler — it just selects within the same view. But add cross-tab navigation for quests and graph nodes.

---

## Part 3: Cross-Reference Wiring

Now that the bus exists, here's every crossing to wire, grouped by source.

### From: ChatPanel

| Trigger | Navigation |
|---------|------------|
| Entity name click (AnnotatedText) | `navigate({ to: 'observatory', tab: 'entities', entityId })` |

**Implementation:** Pass `onEntityClick` callback using navigate. Currently `entities` prop is passed but no click handler.

```javascript
// ChatPanel.jsx — in message rendering where AnnotatedText is used:
const { navigate } = useNavigation()

// Replace existing AnnotatedText usage with:
<AnnotatedText
  text={segment}
  entities={entities}
  onEntityClick={(entityId) => navigate({
    to: 'observatory', tab: 'entities', entityId,
  })}
/>
```

### From: ThoughtStream

| Trigger | Navigation |
|---------|------------|
| Extraction event click | `navigate({ to: 'observatory', tab: 'timeline', eventType })` |
| Entity mention in thought | `navigate({ to: 'observatory', tab: 'entities', entityId })` |

**Implementation:** ThoughtStream already uses AnnotatedText. Wire `onEntityClick`. Add click handler to thought items that navigates to Timeline with filter.

### From: Observatory — EntitiesView

| Trigger | Navigation |
|---------|------------|
| Quest in entity detail → quests sub-tab | `setTab('Quests')` + `selectQuest(questId)` |
| Knowledge node in entity detail | `setTab('Graph')` + `fetchSolarSystem(nodeId)` |

**Implementation:** EntitiesView's `EntityDetail` shows quests and knowledge nodes. Add click handlers:

```javascript
// In EntityDetail, quests sub-tab:
const { navigate } = useNavigation()

// Quest item click:
onClick={() => {
  // Navigate within Observatory (same app, just switch tab)
  // Use a shared callback or direct store manipulation
  navigate({ to: 'observatory', tab: 'quests', questId: quest.id })
}}

// Knowledge node click:
onClick={() => {
  navigate({ to: 'observatory', tab: 'graph', nodeId: mention.id, zoom: 'solarsystem' })
}}
```

### From: Observatory — QuestsView

| Trigger | Navigation |
|---------|------------|
| Target entity in quest detail | `navigate({ to: 'observatory', tab: 'entities', entityId })` |

**Implementation:** Quest detail shows source/target entities. Make them clickable:

```javascript
// In QuestDetail, where entity references appear:
// If quest has target_entity_id or similar field
onClick={() => navigate({ to: 'observatory', tab: 'entities', entityId: quest.target_entity_id })}
```

### From: Observatory — JournalView

| Trigger | Navigation |
|---------|------------|
| Entity mention click (AnnotatedText) | `navigate({ to: 'observatory', tab: 'entities', entityId })` |

**Implementation:** JournalView already uses AnnotatedText with entity highlighting but no `onEntityClick`. Wire it:

```javascript
// JournalReader component:
const { navigate } = useNavigation()

// In mdComponents and processChildren:
<AnnotatedText
  text={child}
  entities={entities}
  onEntityClick={(entityId) => navigate({
    to: 'observatory', tab: 'entities', entityId,
  })}
/>
```

### From: Observatory — Timeline

| Trigger | Navigation |
|---------|------------|
| Node event click | `navigate({ to: 'observatory', tab: 'graph', nodeId, zoom: 'solarsystem' })` |
| Entity in event data | `navigate({ to: 'observatory', tab: 'entities', entityId })` |

**Implementation:** EventCard currently just displays. Make node IDs and entity names clickable.

### From: Observatory — GraphView

| Trigger | Navigation |
|---------|------------|
| Click node that is an entity | `navigate({ to: 'observatory', tab: 'entities', entityId })` |
| Click THREAD node (Layer 3) | `navigate({ to: 'observatory', tab: 'quests' })` filtered to thread's open tasks |

**Implementation:** GraphView's node click handler currently does `selectNode()`. Add entity-type detection:

```javascript
// On node click in GraphView:
if (node.type === 'ENTITY' || ['person', 'persona', 'place', 'project'].includes(node.entity_type)) {
  navigate({ to: 'observatory', tab: 'entities', entityId: node.id })
} else if (node.type === 'THREAD') {
  navigate({ to: 'observatory', tab: 'quests', threadId: node.id })
} else {
  // Default: solar system zoom
  fetchSolarSystem(node.id)
}
```

### From: Kozmo — KozmoChat

| Trigger | Navigation |
|---------|------------|
| Entity mention click | `navigate({ to: 'observatory', tab: 'entities', entityId })` |

**Implementation:** If KozmoChat uses AnnotatedText, wire `onEntityClick`. If not, add it.

### From: Kozmo — Codex Entity Detail

| Trigger | Navigation |
|---------|------------|
| "View in Memory" button | `navigate({ to: 'observatory', tab: 'entities', entityId })` |

**Implementation:** Add a small link/button in Codex entity detail that crosses to Observatory. This is the Kozmo→Observatory bridge. Only works if the entity exists in both systems (matched by name or alias).

---

## Part 4: Internal Observatory Tab Navigation

The navigation bus handles cross-app jumps. But Observatory also needs internal tab switching with deep-link targets. This is simpler — just lift tab state and selection into the store or use a callback pattern.

### Option A: Callback from ObservatoryApp (recommended)

```javascript
// ObservatoryApp.jsx — pass navigateTab to all views
const navigateTab = (tab, selection = {}) => {
  setTab(tab)
  if (selection.entityId) {
    selectEntity(selection.entityId)
    fetchEntityDetail(selection.entityId)
  }
  if (selection.questId) {
    selectQuest(selection.questId)
    fetchQuestDetail(selection.questId)
  }
  if (selection.nodeId) {
    fetchSolarSystem(selection.nodeId)
  }
}

// Pass to views:
<EntitiesView navigateTab={navigateTab} />
<QuestsView navigateTab={navigateTab} />
<JournalView navigateTab={navigateTab} />
// etc.
```

Views call `navigateTab('Quests', { questId: 'q_abc' })` for internal jumps.

### Option B: Use the same navigation bus

For consistency, internal Observatory navigation could also go through `navigate()`. App.jsx ignores it (already in observatory mode), ObservatoryApp picks it up. This is simpler conceptually — one pattern for everything — but means internal tab switches round-trip through the bus.

**Recommendation: Option A for internal, bus for cross-app.** Keeps internal navigation instant and doesn't pollute the bus with intra-Observatory noise.

---

## Part 5: Thread Integration (After Layers 2-3 Land)

When THREAD nodes start appearing in the Matrix, Observatory needs to surface them. Two paths:

### Quests as Thread Tasks

The quest system's SWEEP operation (`runMaintenanceSweep`) generates quests from graph health analysis. Extend this to also generate quests from open threads:

- Parked thread with open tasks → "Continue: {thread.topic}" quest
- Stale parked thread (>3 days) → "Review: {thread.topic}" quest
- Thread with unresolved PROBLEM → high-priority quest

This means quests become the merged view of: graph health issues + open thread tasks + manual tasks.

### Threads Tab (Optional, Later)

If threads need their own dedicated view beyond what quests provides, add a "Threads" tab to Observatory. But start by surfacing threads through the existing quest system. If that's sufficient, no new tab needed. Reduction over addition.

### Project Context Bridge

When Kozmo activates a project, Observatory should filter/highlight relevant data:

```javascript
// In KozmoProvider.jsx — when project activates:
// Already calls /project/activate on backend
// Backend (Layer 3) now tells Librarian to set project context
// Observatory can listen for project_threads_available event via WebSocket
// and surface parked threads as "Continue" quests
```

---

## Build Order

1. **Create `useNavigation.js`** — the bus (30 lines)
2. **Wire App.jsx** — consume pending navigations, switch modes
3. **Wire ObservatoryApp.jsx** — read pending, set tab + selection
4. **Wire ChatPanel** — pass onEntityClick using navigate
5. **Kill sandbox toggle** — remove from Observatory header, store, api
6. **Wire EntitiesView cross-tabs** — quest clicks → Quests tab, knowledge nodes → Graph
7. **Wire QuestsView** — entity references clickable → Entities tab
8. **Wire JournalView** — entity click handler via AnnotatedText
9. **Wire Timeline** — event click → Graph node
10. **Wire GraphView** — node click → Entities tab (if entity type)
11. **Wire ThoughtStream** — entity clicks → Observatory
12. **Wire Kozmo crossings** — KozmoChat entity clicks, Codex "view in memory" link

Steps 1-5 are the foundation. Steps 6-12 are additive — each one lights up another crossing.

---

## Testing

### Navigation Bus

```
1. Click entity name in ChatPanel
   → Observatory opens, Entities tab active, that entity selected and loaded
   
2. Click entity in Observatory Journal entry
   → Entities tab activates, that entity selected
   
3. Click quest in entity detail (Entities → Quests sub-tab)
   → Quests tab activates, that quest selected
   
4. Click knowledge node in entity detail
   → Graph tab activates, solar system zoom on that node
   
5. Click "← LUNA" in Observatory
   → Returns to Eclissi main view
```

### Cross-App

```
6. In Kozmo, entity mention in KozmoChat
   → Observatory opens at Entities tab for that entity
   
7. From Observatory, click "← LUNA" 
   → Returns to Eclissi main
   
8. Navigate to Observatory Graph, click entity node
   → Entities tab activates for that entity (internal jump)
```

### Sandbox Removal

```
9. Observatory opens with no DB toggle visible
10. All data comes from production Matrix
11. No sandbox_reset/sandbox_seeded events in Timeline
```

---

## Files Summary

| File | Action |
|------|--------|
| `frontend/src/hooks/useNavigation.js` | **NEW** — navigation bus |
| `frontend/src/App.jsx` | Wire navigation consumer, switch modes on navigate |
| `frontend/src/observatory/ObservatoryApp.jsx` | Read deep-link from navigation, remove sandbox toggle |
| `frontend/src/observatory/store.js` | Remove dbMode, switchDb, sandbox event handlers |
| `frontend/src/observatory/api.js` | Remove switchDb method |
| `frontend/src/components/ChatPanel.jsx` | Wire onEntityClick → navigate |
| `frontend/src/components/ThoughtStream.jsx` | Wire onEntityClick → navigate |
| `frontend/src/components/AnnotatedText.jsx` | No changes needed (already accepts onEntityClick) |
| `frontend/src/observatory/views/EntitiesView.jsx` | Add cross-tab navigation for quests and knowledge nodes |
| `frontend/src/observatory/views/QuestsView.jsx` | Add entity reference clicks |
| `frontend/src/observatory/views/JournalView.jsx` | Wire onEntityClick in AnnotatedText |
| `frontend/src/observatory/views/Timeline.jsx` | Wire event click → Graph node |
| `frontend/src/observatory/views/GraphView.jsx` | Wire node click → Entities (if entity type) |
| `frontend/src/observatory/components/EventCard.jsx` | Make node IDs / entities clickable |
| `frontend/src/kozmo/components/KozmoChat.jsx` | Wire onEntityClick → navigate (if uses AnnotatedText) |
| Backend observatory server | Remove `/api/switch-db`, default to production |

---

## Relationship to Current Work

**Layers 2-3 (flow awareness + threads)** change the backend. THREAD nodes appear in Matrix. Flow signals flow through the extraction pipeline.

**This handoff (Observatory wiring)** changes the frontend. Navigation bus connects the three worlds. Sandbox dies. Everything that names something becomes a doorway.

**They converge at:** THREAD nodes appearing in Observatory's Graph view, and thread open tasks surfacing as Quests. That convergence happens naturally once both sides land — no additional integration work needed beyond what's already specified in the thread-to-quest mapping above.

Build Layers 2-3 first. Then this. Or do them in parallel if you've got the headspace — they don't conflict.
