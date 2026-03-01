# HANDOFF: Expression Pipeline — Folded into Diagnostic Nodes + Eclissi Mount

**Author:** Ahab / Zayne  
**Date:** 2026-02-28  
**Target:** Claude Code  
**Supersedes:** `HANDOFF_Expression_Pipeline_Diagnostic_Tool.md` (standalone Vite app approach — abandoned)

---

## TL;DR

Two things, one build:

1. **Fold** the expression pipeline (5-axis dimensional orb, gesture triage, Canvas 2D ring renderer) into the existing `LunaDiagnosticNodes_V2/luna-diagnostic/` app as a new view alongside the engine pipeline graph.

2. **Mount** the diagnostic tool inside Eclissi as a first-class view, same pattern as Kozmo and Observatory — toggle button in the header, full takeover render, `DiagnosticApp` component in `frontend/src/diagnostic/`.

---

## WHAT ALREADY EXISTS

### Diagnostic Nodes App — `Tools/LunaDiagnosticNodes_V2/luna-diagnostic/`

A working Vite+React app (`npm run dev` works) using `@xyflow/react`:

| File | What it does |
|------|-------------|
| `src/App.jsx` | Root — ReactFlow canvas, HUD, detail panel, live data wiring |
| `src/data.js` | ~30 engine nodes + edges (input→buffer→dispatch→memory→context→director→guards→output) |
| `src/useLiveData.js` | HTTP polling (8 REST endpoints, 2s interval), `applyLiveData()` patches node statuses |
| `src/EngineNode.jsx` | Custom ReactFlow node with status dot, icon, body text |
| `src/AnimatedEdge.jsx` | Custom edge with flow animation |
| `src/DetailPanel.jsx` | Click-to-inspect node detail |
| `package.json` | `react`, `react-dom`, `@xyflow/react`, `vite` |

**Key:** Uses HTTP polling to REST APIs, not WebSocket. Connection badge already exists.

### Expression Pipeline Prototype — `Tools/Luna-Expression-Pipeline/luna_expression_v4_rings.jsx`

823-line standalone JSX (not runnable). Contains:

- 13 expression nodes: 6 triggers → blender → 5 dimensions → mapping → orb output + gesture override + priority stack
- Canvas 2D ring renderer (5 breathing rings, Lissajous drift, glow, core dot)
- Gesture triage panel (12 survivors, 33 absorbed, 6 killed)
- 7 scenario simulations
- Dimension sliders with live visual feedback

### Eclissi Frontend — `frontend/src/`

Main Luna UI. Mode-switched views in `App.jsx`:

```jsx
// Header bar toggle buttons:
<button onClick={() => { setKozmoMode(!kozmoMode); ... }}>KOZMO</button>
<button onClick={() => { setObservatoryMode(!observatoryMode); ... }}>OBSERVATORY</button>
<a href="/guardian/">GUARDIAN</a>  // separate static mount

// Render logic:
{kozmoMode ? (
  <div className="absolute inset-0 top-[72px]"><KozmoApp onBack={...} /></div>
) : observatoryMode ? (
  <div className="absolute inset-0 top-[72px]"><ObservatoryApp onBack={...} /></div>
) : (
  <> {/* normal Eclissi chat view */} </>
)}
```

Pattern: each app lives in its own folder (`frontend/src/kozmo/`, `frontend/src/observatory/`), exports a root component (`KozmoApp`, `ObservatoryApp`), takes an `onBack` prop.

### Backend (already built)

| Component | File | Relevant |
|-----------|------|----------|
| WebSocket `ws/orb` | `server.py:568` | Broadcasts `rendererState` + `dimensions` on every change |
| `DimensionalEngine` | `dimensional_engine.py` | 5-axis blender (6 triggers → 5 dimensions) |
| `dim_renderer_map.py` | `dim_renderer_map.py` | Dimensions → ring rendering params |
| `OrbStateManager.to_dict()` | `orb_state.py:406` | Full WebSocket payload shape |
| REST status endpoints | `server.py` | `/api/status`, `/api/health`, `/api/debug/context`, etc. |

### WebSocket Payload Shape (from `OrbStateManager.to_dict()`)

```json
{
  "animation": "idle",
  "color": null,
  "brightness": 1.0,
  "source": "dimension",
  "timestamp": "2026-02-28T20:15:00",
  "renderer": {
    "rings": [
      { "id": 0, "baseRadius": 44.0, "baseOpacity": 0.08,
        "hue": 262.0, "saturation": 60.0, "lightness": 45.0,
        "strokeWidth": 1.2, "hasFill": false }
    ],
    "animation": {
      "breatheSpeed": 0.015, "breatheAmplitude": 2.5,
      "driftRadiusX": 12.0, "driftRadiusY": 8.0,
      "driftSpeed": 0.0006, "ringPhaseOffset": 0.7,
      "syncBreathing": false, "sequentialPulse": false,
      "flicker": false, "colorOverride": null,
      "expandedDrift": false, "contracted": false,
      "speechRhythm": false, "splitGroups": false,
      "glowAmbientMax": 0.08, "glowCoronaMax": 0.12
    },
    "transition": {
      "preAttackMs": 200, "preAttackContraction": 0.15,
      "attackMs": 300, "sustainMs": -1,
      "releaseMs": 600, "ease": "ease_out"
    }
  },
  "dimensions": {
    "valence": 0.350, "arousal": 0.280,
    "certainty": 0.650, "engagement": 0.420,
    "warmth": 0.580
  },
  "speechHint": null
}
```

---

## PHASE 1: Fold Expression Pipeline into Diagnostic Nodes App

### 1A. Add View Switching to Diagnostic App

The app currently has one view (the engine pipeline graph). Add a second view: the expression pipeline.

**Modify `src/App.jsx`:**

Add a view toggle in the HUD:

```
[ENGINE PIPELINE] | [EXPRESSION PIPELINE]
```

- `ENGINE PIPELINE` = existing ReactFlow graph (current behavior)
- `EXPRESSION PIPELINE` = new view with expression nodes, orb preview, triage panel

These are full-view swaps, not overlays.

### 1B. New Files in `luna-diagnostic/src/`

```
src/
├── App.jsx                      # Modified — add view toggle
├── data.js                      # Unchanged — engine pipeline nodes
├── useLiveData.js               # Unchanged — HTTP polling for engine data
├── EngineNode.jsx               # Unchanged
├── AnimatedEdge.jsx             # Unchanged
├── DetailPanel.jsx              # Unchanged
├── expression/                  # ← NEW FOLDER
│   ├── ExpressionView.jsx       # Root view — contains ReactFlow + orb + triage
│   ├── expressionData.js        # 13 expression nodes + edges (from v4 prototype)
│   ├── ExpressionNode.jsx       # Custom node with dimension bars, trigger values
│   ├── OrbPreview.jsx           # Canvas 2D ring renderer (extracted from v4)
│   ├── DimensionSliders.jsx     # 5-axis sliders with live/override toggle
│   ├── TriagePanel.jsx          # Gesture triage display (12/33/6)
│   ├── ScenarioRunner.jsx       # 7 scenario simulation buttons
│   └── useOrbConnection.js      # WebSocket hook for ws/orb
```

### 1C. Expression Nodes — `expressionData.js`

Port the 13 nodes from the v4 prototype into `@xyflow/react` format:

| Node ID | Type | Label | Fields |
|---------|------|-------|--------|
| `t_sentiment` | trigger | Sentiment | value: -1→1 |
| `t_memory` | trigger | Memory Hit | value: -1→1 |
| `t_identity` | trigger | Identity | value: 0→1 |
| `t_topic` | trigger | Topic Weight | value: 0→1 |
| `t_flow` | trigger | Flow | value: 0→1 |
| `t_time` | trigger | Time Mod | value: -0.3→0.3 |
| `blender` | blend | Blender | smoothing: 0.3 |
| `d_valence` | dimension | Valence | value: -1→1 |
| `d_arousal` | dimension | Arousal | value: 0→1 |
| `d_certainty` | dimension | Certainty | value: 0→1 |
| `d_engagement` | dimension | Engagement | value: 0→1 |
| `d_warmth` | dimension | Warmth | value: 0→1 |
| `gesture` | gesture | Gesture Override | 12 survivors list |
| `priority` | priority | Priority Stack | P0-P4 levels |
| `map_render` | mapping | Dim→Renderer | computed params display |
| `c_orb` | orb | Orb Output | link to OrbPreview |

Edges follow the pipeline: triggers → blender → dimensions → mapping → orb, with gesture override feeding into priority stack.

Use the same `EngineNode` component (or a variant `ExpressionNode`) with the type color system from the v4 prototype.

### 1D. WebSocket Hook — `useOrbConnection.js`

```javascript
export function useOrbConnection(url = 'ws://127.0.0.1:8000/ws/orb') {
  const [orbState, setOrbState] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastUpdate, setLastUpdate] = useState(null);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  // Connect, parse JSON, auto-reconnect with 3s backoff
  // ...

  return {
    isConnected,
    orbState,          // full payload
    dimensions: orbState?.dimensions || null,
    rendererState: orbState?.renderer || null,
    source: orbState?.source || null,
    lastUpdate,
  };
}
```

**This is separate from `useLiveData`** (which does HTTP polling for engine status). The expression view uses both:
- `useLiveData` for engine health in the HUD
- `useOrbConnection` for real-time dimensional state

### 1E. OrbPreview — Canvas 2D Ring Renderer

Extract the Canvas 2D renderer from lines ~550-823 of the v4 prototype. This is the breathing ring orb.

Two modes:

- **LIVE mode:** Receives `rendererState` from WebSocket. Renders rings using backend-computed hue, opacity, breathe speed, etc.
- **SIM mode:** Receives dimension slider values. Computes renderer params locally using the same mapping logic from `dim_renderer_map.py` (ported to JS).

The orb sits to the right of the ReactFlow graph in the expression view, always visible.

### 1F. Layout — Expression View

```
┌────────────────────────────────────────────────────────┐
│ ◈ LUNA DIAGNOSTIC  [Engine Pipeline] [Expression]  🟢  │
├─────────────────────────────────┬──────────────────────┤
│                                 │                      │
│   ReactFlow Canvas              │   OrbPreview         │
│   (13 expression nodes)         │   (Canvas 2D)        │
│                                 │                      │
│   Triggers → Blender →          │   [breathing rings]  │
│   Dimensions → Mapping          │                      │
│                                 │   DimensionSliders   │
│                                 │   [v][a][c][e][w]    │
│                                 │                      │
├─────────────────────────────────┴──────────────────────┤
│ Triage: 12 survive │ 33 absorbed │ 6 killed  [Scenari] │
└────────────────────────────────────────────────────────┘
```

Left: ReactFlow graph (draggable, zoomable). Right sidebar: OrbPreview + sliders. Bottom: triage + scenarios.

---

## PHASE 2: Mount in Eclissi as First-Class View

Same pattern as Kozmo and Observatory.

### 2A. New Folder — `frontend/src/diagnostic/`

```
frontend/src/diagnostic/
├── DiagnosticApp.jsx         # Root component (wraps the diagnostic tool)
├── expression/               # Expression pipeline components (same as 1B)
│   ├── ExpressionView.jsx
│   ├── expressionData.js
│   ├── ExpressionNode.jsx
│   ├── OrbPreview.jsx
│   ├── DimensionSliders.jsx
│   ├── TriagePanel.jsx
│   ├── ScenarioRunner.jsx
│   └── useOrbConnection.js
├── pipeline/                 # Engine pipeline components (ported from LunaDiagnosticNodes_V2)
│   ├── PipelineView.jsx
│   ├── pipelineData.js       # (from data.js)
│   ├── useLiveData.js        # (from useLiveData.js)
│   ├── EngineNode.jsx
│   ├── AnimatedEdge.jsx
│   └── DetailPanel.jsx
└── shared/
    └── ConnectionBadge.jsx
```

`DiagnosticApp.jsx` has the view toggle between Pipeline and Expression views, HUD, and connection status. Takes `onBack` prop.

### 2B. Add to Eclissi Header — `frontend/src/App.jsx`

**Add state:**
```javascript
const [diagnosticMode, setDiagnosticMode] = useState(false);
```

**Add import:**
```javascript
import DiagnosticApp from './diagnostic/DiagnosticApp';
```

**Add toggle button** (in header, alongside KOZMO / OBSERVATORY / GUARDIAN):

```jsx
<button
  onClick={() => { setDiagnosticMode(!diagnosticMode); setKozmoMode(false); setObservatoryMode(false); }}
  className={`px-3 py-1.5 text-xs rounded border transition-all ${
    diagnosticMode
      ? 'border-[#818cf8]/50 text-[#818cf8]'
      : 'bg-kozmo-bg border-kozmo-border text-kozmo-muted hover:border-kozmo-border/80'
  }`}
  style={diagnosticMode ? { background: 'rgba(129,140,248,0.1)' } : {}}
>
  DIAGNOSTIC
</button>
```

**Add render branch** (in the mode switching block):

```jsx
{kozmoMode ? (
  <div className="absolute inset-0 top-[72px]" style={{ zIndex: 2 }}>
    <KozmoApp onBack={() => setKozmoMode(false)} />
  </div>
) : observatoryMode ? (
  <div className="absolute inset-0 top-[72px]" style={{ zIndex: 2 }}>
    <ObservatoryApp onBack={() => setObservatoryMode(false)} />
  </div>
) : diagnosticMode ? (
  <div className="absolute inset-0 top-[72px]" style={{ zIndex: 2 }}>
    <DiagnosticApp onBack={() => setDiagnosticMode(false)} />
  </div>
) : (
  <> {/* normal Eclissi chat view */} </>
)}
```

**Update navigation bus** (in the `navPending` effect):

```javascript
case 'diagnostic':
  setDiagnosticMode(true);
  setKozmoMode(false);
  setObservatoryMode(false);
  break;
```

### 2C. Add `@xyflow/react` to Eclissi Dependencies

**Modify `frontend/package.json`:**

```json
"dependencies": {
  "@xyflow/react": "^12.6.0",
  // ... existing deps
}
```

Run `npm install` in `frontend/`.

### 2D. Relationship Between Standalone and Eclissi

After Phase 2, the code lives in **two places**:

| Location | Purpose |
|----------|---------|
| `Tools/LunaDiagnosticNodes_V2/luna-diagnostic/` | Standalone dev tool (`npm run dev` on port 5173) |
| `frontend/src/diagnostic/` | Embedded in Eclissi (same port as main UI, 8000) |

The standalone version stays for independent development/debugging. The Eclissi version is the production mount. During Phase 1, build into the standalone app. During Phase 2, port into Eclissi.

**Alternative:** If maintaining two copies feels wrong, Phase 2 can be the only target. Build directly into `frontend/src/diagnostic/` and skip the standalone app update. The existing `LunaDiagnosticNodes_V2` becomes a legacy reference.

---

## PHASE 3: Bidirectional Control (Backend Changes)

Same as original handoff — lets sliders push dimension overrides to the engine.

### 3A. New REST Endpoint — `server.py`

```python
class DimensionOverride(BaseModel):
    valence: Optional[float] = None
    arousal: Optional[float] = None
    certainty: Optional[float] = None
    engagement: Optional[float] = None
    warmth: Optional[float] = None

@app.post("/api/orb/dimensions/override")
async def override_dimensions(override: DimensionOverride):
    """Push dimension overrides from diagnostic tool."""
    if _orb_state_manager:
        _orb_state_manager.apply_dimension_override(override.dict(exclude_none=True))
        return {"status": "ok", "overrides": override.dict(exclude_none=True)}
    raise HTTPException(status_code=503, detail="Orb state manager not initialized")
```

### 3B. OrbStateManager Changes — `orb_state.py`

Add `_dimension_overrides = {}` in `__init__`.

Add `apply_dimension_override(overrides: dict)` — merges overrides into current dimensional state, applies to renderer, broadcasts.

Modify `update_dimensions()` to merge any active overrides before applying to renderer. When overrides dict is empty, engine drives everything.

### 3C. Slider Override UI

Each dimension slider gets a lock/unlock toggle:
- **Unlocked (default):** Displays live value from engine (read-only)
- **Locked:** User controls the slider, value POSTs to `/api/orb/dimensions/override`

Clearing all locks POSTs `{}` to clear overrides.

---

## BUILD ORDER

### Phase 1 — Standalone Diagnostic Tool
1. Add view toggle to `luna-diagnostic/src/App.jsx`
2. Create `src/expression/` folder with extracted components
3. Port v4 prototype nodes into `@xyflow/react` format
4. Create `useOrbConnection.js` WebSocket hook
5. Extract Canvas 2D renderer into `OrbPreview.jsx`
6. Wire dimension nodes to live WebSocket data
7. Wire orb to live `rendererState`
8. Add LIVE/SIM toggle, scenario runner, triage panel
9. **Test:** `cd luna-diagnostic && npm run dev` — both views work, expression orb breathes from live engine

### Phase 2 — Eclissi Mount
10. Create `frontend/src/diagnostic/` folder
11. Port components from standalone (or build fresh there)
12. Create `DiagnosticApp.jsx` with `onBack` prop
13. Add `@xyflow/react` to `frontend/package.json`
14. Add DIAGNOSTIC toggle + render branch to `frontend/src/App.jsx`
15. Add to navigation bus
16. **Test:** Start Luna engine, open Eclissi, click DIAGNOSTIC → full pipeline + expression views render, live data flows

### Phase 3 — Bidirectional
17. Add `POST /api/orb/dimensions/override` to `server.py`
18. Add `apply_dimension_override()` to `OrbStateManager`
19. Modify `update_dimensions()` for override merging
20. Wire slider lock/override in `DimensionSliders.jsx`
21. **Test:** Lock warmth slider, drag to 0.9 → orb responds in both diagnostic view AND main Eclissi chat view

---

## FILES MODIFIED

### Phase 1 (standalone tool only)

| Action | File |
|--------|------|
| MODIFY | `Tools/LunaDiagnosticNodes_V2/luna-diagnostic/src/App.jsx` — add view toggle |
| CREATE | `Tools/LunaDiagnosticNodes_V2/luna-diagnostic/src/expression/ExpressionView.jsx` |
| CREATE | `Tools/LunaDiagnosticNodes_V2/luna-diagnostic/src/expression/expressionData.js` |
| CREATE | `Tools/LunaDiagnosticNodes_V2/luna-diagnostic/src/expression/ExpressionNode.jsx` |
| CREATE | `Tools/LunaDiagnosticNodes_V2/luna-diagnostic/src/expression/OrbPreview.jsx` |
| CREATE | `Tools/LunaDiagnosticNodes_V2/luna-diagnostic/src/expression/DimensionSliders.jsx` |
| CREATE | `Tools/LunaDiagnosticNodes_V2/luna-diagnostic/src/expression/TriagePanel.jsx` |
| CREATE | `Tools/LunaDiagnosticNodes_V2/luna-diagnostic/src/expression/ScenarioRunner.jsx` |
| CREATE | `Tools/LunaDiagnosticNodes_V2/luna-diagnostic/src/expression/useOrbConnection.js` |

### Phase 2 (Eclissi integration)

| Action | File |
|--------|------|
| CREATE | `frontend/src/diagnostic/DiagnosticApp.jsx` |
| CREATE | `frontend/src/diagnostic/expression/*` (same as Phase 1) |
| CREATE | `frontend/src/diagnostic/pipeline/*` (ported from standalone) |
| CREATE | `frontend/src/diagnostic/shared/ConnectionBadge.jsx` |
| MODIFY | `frontend/src/App.jsx` — add diagnosticMode state + toggle + render branch |
| MODIFY | `frontend/package.json` — add `@xyflow/react` |

### Phase 3 (backend)

| Action | File |
|--------|------|
| MODIFY | `src/luna/api/server.py` — add `POST /api/orb/dimensions/override` |
| MODIFY | `src/luna/services/orb_state.py` — add `apply_dimension_override()`, modify `update_dimensions()` |

### Reference Files (read, don't modify)

| File | Why |
|------|-----|
| `src/luna/services/dimensional_engine.py` | Trigger→dimension weights |
| `src/luna/services/dim_renderer_map.py` | Dimension→renderer param ranges |
| `src/luna/services/orb_renderer.py` | `to_dict()` output shape |
| `frontend/src/components/OrbCanvas.jsx` | Production Canvas 2D renderer |
| `frontend/src/hooks/useOrbState.js` | Production WebSocket hook |
| `Tools/Luna-Expression-Pipeline/luna_expression_v4_rings.jsx` | UI prototype to extract from |
| `Tools/Luna-Expression-Pipeline/gesture_triage_map.py` | Triage data |

---

## NON-NEGOTIABLES

1. **Standalone still works.** `cd Tools/LunaDiagnosticNodes_V2/luna-diagnostic && npm run dev` must continue to work after Phase 1.
2. **Eclissi build still works.** `cd frontend && npm run build` must succeed after Phase 2. No broken imports.
3. **SIM mode works without engine.** Expression view is useful for design iteration even when Luna isn't running.
4. **Engine pipeline view is untouched.** Don't modify existing engine nodes, edges, or live data logic.
5. **Don't break production orb.** Phase 3 backend changes must be no-op when no overrides are active.
6. **One WebSocket, one polling hook.** Expression view uses `useOrbConnection` (WS). Engine view uses `useLiveData` (HTTP). Don't merge them.
