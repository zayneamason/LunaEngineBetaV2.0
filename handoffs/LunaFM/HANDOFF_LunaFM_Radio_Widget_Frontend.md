# HANDOFF: LunaFM Radio Widget — Eclissi Frontend

**Priority:** HIGH — pairs with the LunaFM backend handoff
**Scope:** Radio icon in sidebar + widget panel showing channel output, dials, and settings
**Frontend Root:** `frontend/src/`

---

## WHAT THIS IS

A new widget in the Eclissi sidebar (accessed via a radio icon) that lets the user see and control LunaFM — Luna's background cognitive broadcast system. Shows live channel output, provides tuning controls, and displays the LunaScript frequency coupling.

---

## INTEGRATION PATTERN (3 touches)

### Touch 1: Add to WidgetDock.jsx

File: `frontend/src/eclissi/components/WidgetDock.jsx`

Add to the WIDGETS array (after the `thought` entry, before the last divider or at end):

```jsx
{ id: 'radio', icon: '📻', label: 'LunaFM', accent: 'var(--ec-accent-voice)' },
```

Or better — use a simple SVG radio icon instead of emoji for consistency:

```jsx
{ id: 'radio', icon: '◉', label: 'LunaFM', accent: '#7F77DD' },
```

### Touch 2: Import in EclissiShell.jsx

File: `frontend/src/eclissi/EclissiShell.jsx`

Add import:
```jsx
import RadioWidget from './widgets/RadioWidget';
```

Add to WIDGET_COMPONENTS:
```jsx
const WIDGET_COMPONENTS = {
  // ... existing widgets ...
  radio: RadioWidget,
};
```

### Touch 3: Create the widget

File: `frontend/src/eclissi/widgets/RadioWidget.jsx`

---

## BACKEND API ENDPOINTS (to build alongside widget)

These need to exist in the FastAPI backend for the widget to read from:

```
GET  /lunafm/status
  → { station_running, channels: [{id, name, state, last_emission, artifacts_count, interval_s}], uptime_s }

GET  /lunafm/stream  (SSE)
  → Server-sent events of channel emissions in real time
  → data: {"channel": "entertainment", "type": "SYNTHESIS", "content": "...", "timestamp": "..."}

GET  /lunafm/artifacts?channel=entertainment&limit=20
  → Paginated list of LunaFM-generated nodes from memory_nodes where source LIKE 'lunafm:%'

POST /lunafm/channel/{id}/config
  → Body: {"interval_s": 30, "enabled": true, "aperture": "WIDE"}
  → Updates channel schedule and aperture

GET  /lunafm/traits
  → Current LunaScript trait vector: {curiosity: 0.72, warmth: 0.65, depth: 0.58, ...}

GET  /lunafm/spectral
  → {last_computed, node_count, edge_count, fiedler_value, top_resonance_pairs: [...]}
```

---

## WIDGET LAYOUT

The RadioWidget should have 3 sections, stacked vertically in the widget panel:

### Section 1: Station header + channel cards

```
┌─────────────────────────────────────┐
│ ◉ LunaFM                    ON/OFF │
│ 3 channels · 42 artifacts · 2h up  │
├─────────────────────────────────────┤
│                                     │
│ ┌─────────┐┌─────────┐┌─────────┐  │
│ │ ● News  ││ ◌ Ent.  ││ ● Hist  │  │
│ │ scanning││  idle   ││emitting │  │
│ │ 15s     ││ 2min    ││ 10min   │  │
│ │ 12 flags││ 8 synth ││ 5 cons  │  │
│ └─────────┘└─────────┘└─────────┘  │
│                                     │
```

- Each channel card shows: state indicator (colored dot), name, current state, interval, artifact count
- State colors: idle=gray, scanning=blue, processing=amber, emitting=green, cooldown=dim, paused=red
- Cards are clickable — clicking one expands its detail view

### Section 2: Thought stream (live feed)

```
│ ─── Thought stream ──────────────── │
│                                     │
│ [entertainment] 2:34 AM             │
│ SYNTHESIS: Elder Musoke's drought   │
│ stories and subak irrigation share  │
│ distributed authority pattern       │
│ node_a → node_b (STRUCTURAL)       │
│                                     │
│ [news] 2:33 AM                      │
│ FLAG: Topic shift — user moved from │
│ architecture to philosophical       │
│                                     │
│ [history] 2:28 AM                   │
│ CONSOLIDATION: Merged 2 duplicate   │
│ marzipan nodes (lock_in 0.85→0.45) │
│                                     │
```

- Reverse-chronological feed of channel emissions
- Color-coded by channel (news=coral, entertainment=amber, history=teal)
- Auto-scrolls as new emissions arrive via SSE
- Each entry shows: channel, timestamp, type, content preview, metadata

### Section 3: Tuning controls

```
│ ─── Tuning ──────────────────────── │
│                                     │
│ Aperture          [====●=====] WIDE │
│ TUNNEL  NARROW  BALANCED  WIDE OPEN│
│                                     │
│ News frequency    [=●========] 15s  │
│ Ent. frequency    [====●=====] 2min │
│ History frequency [=======●==] 10m  │
│                                     │
│ ─── Cognitive state ─────────────── │
│                                     │
│ curiosity  ████████░░  0.72         │
│ warmth     ██████░░░░  0.65         │
│ depth      █████░░░░░  0.58         │
│ energy     ███░░░░░░░  0.34         │
│ directness ██████░░░░  0.61         │
│ formality  ██░░░░░░░░  0.23         │
│ humor      ████░░░░░░  0.41         │
│ patience   ███████░░░  0.78         │
│                                     │
│ Small deltas show LunaFM nudges:    │
│ curiosity +0.05 (entertainment)     │
└─────────────────────────────────────┘
```

- Aperture dial: 5 presets (TUNNEL/NARROW/BALANCED/WIDE/OPEN), maps to V3 sigma
- Channel frequency sliders: adjustable interval per channel
- Cognitive state: 8 LunaScript traits as horizontal bars with live values
- Trait nudges shown as small +/- deltas with source channel

---

## COMPONENT STRUCTURE

```jsx
// RadioWidget.jsx — top-level widget
export default function RadioWidget() {
  return (
    <div>
      <StationHeader />
      <ChannelCards />
      <ThoughtStream />
      <TuningControls />
    </div>
  );
}
```

### Sub-components:

**StationHeader** — station name, on/off toggle, uptime, total artifacts count. Calls `GET /lunafm/status` on mount and every 5s.

**ChannelCards** — 3 side-by-side cards for News/Entertainment/History. State indicator dot, name, current state, interval, artifact count. Poll from `/lunafm/status`. Clickable to expand detail.

**ThoughtStream** — connects to `GET /lunafm/stream` (SSE) for real-time emissions. Falls back to polling `/lunafm/artifacts?limit=20` if SSE not available. Reverse-chronological. Color-coded by channel. Auto-scroll with "new items" indicator if scrolled up.

**TuningControls** — aperture slider, frequency sliders, cognitive state bars. Aperture and frequency changes call `POST /lunafm/channel/{id}/config`. Trait bars read from `GET /lunafm/traits` (poll every 3s). Nudge deltas highlighted temporarily when they change.

---

## STYLING

Follow existing Eclissi widget patterns:
- Use `var(--ec-bg-raised)`, `var(--ec-border)`, `var(--ec-text-muted)` etc.
- Widget panel width is whatever the existing widget panel uses (~300-400px)
- Channel card state dots: use inline colored circles, not emoji
- Thought stream entries: subtle left border color per channel
- Trait bars: use the same bar component pattern if one exists in other widgets (LunaScriptWidget likely has one)

Check `LunaScriptWidget.jsx` — it probably already renders trait bars. Reuse that component or pattern.

---

## SSE STREAM FORMAT

```
event: emission
data: {
  "channel": "entertainment",
  "type": "SYNTHESIS", 
  "content": "Elder Musoke's drought stories and subak irrigation share distributed authority pattern",
  "metadata": {
    "node_a_id": "abc123",
    "node_b_id": "def456",
    "connection_type": "STRUCTURAL",
    "lock_in": 0.2
  },
  "timestamp": "2026-04-06T03:34:12Z"
}

event: state_change
data: {
  "channel": "news",
  "from": "idle",
  "to": "scanning",
  "timestamp": "2026-04-06T03:34:15Z"
}

event: trait_nudge
data: {
  "trait": "curiosity",
  "delta": 0.05,
  "source": "entertainment",
  "new_value": 0.77,
  "timestamp": "2026-04-06T03:34:12Z"
}
```

---

## DO NOT

- Do NOT build the backend LunaFM daemon in this handoff — that's the separate LunaFM handoff
- Do NOT modify existing widgets
- Do NOT change the WidgetDock layout/styling — just add one entry
- Do NOT add new npm dependencies if avoidable (use fetch for SSE, native EventSource)
- Do NOT put mock data in the widget — use real API calls. If backend isn't ready, show "LunaFM not running" state gracefully

---

## FILES TO CREATE

```
frontend/src/eclissi/widgets/RadioWidget.jsx      — main widget
frontend/src/eclissi/widgets/radio/               — sub-components (optional, can be inline)
  StationHeader.jsx
  ChannelCards.jsx  
  ThoughtStream.jsx
  TuningControls.jsx
```

## FILES TO MODIFY

```
frontend/src/eclissi/components/WidgetDock.jsx     — add radio entry to WIDGETS array
frontend/src/eclissi/EclissiShell.jsx              — import RadioWidget, add to WIDGET_COMPONENTS
```

---

## IMPLEMENTATION ORDER

1. Add radio icon to WidgetDock + empty RadioWidget → verify it appears and toggles
2. StationHeader + ChannelCards with `/lunafm/status` polling → verify live data
3. ThoughtStream with SSE → verify real-time emission display
4. TuningControls with sliders → verify config changes persist
5. Cognitive state trait bars → verify live trait display with nudge deltas

Step 1 is 5 minutes of work and proves the integration. Steps 2-5 build out the functionality incrementally.
