# Orb Visual Implementation — Claude Code Handoff

## What This Is

The orb needs a new visual renderer. The current `orb_state.py` handles **what** the orb should be doing (gestures, system events, priority resolution). This handoff covers **how it looks and moves** — the rendering layer that consumes those state signals.

The orb is a bullseye of concentric rings that floats like a fairy, glows, breathes, and docks to a spatial grid system that indexes the entire viewport.

Reference prototype: `grid_layer_prototype.html` (in outputs — working demo of everything described below).

## Two Systems

### 1. Grid Layer (viewport spatial index)
The entire Guardian viewport sits on an invisible coordinate grid. Every component — orb, panels, inputs — is a child of this grid. The grid is always running, always tracking, but only visible in debug mode.

### 2. Orb (ring-based visual entity)
The orb is a set of concentric rings rendered on canvas. Each ring is independently controllable. The orb floats, glows, breathes, and snaps to grid anchor points.

---

## Grid Layer Spec

### Architecture
- Full viewport 2D grid with evenly spaced anchor points
- Subdivides: L0 (10×6 = 77pts) → L1 (20×12) → L2 (40×24) → L3 (80×48)
- Each point is addressable: `{id, col, row, x, y, nx, ny, zone, children}`
- `nx/ny` are normalized 0–1 viewport coordinates
- Zone assignment based on normalized position (maps to UI regions)
- Children list tracks what components are mounted at each point

### Zone Map (configurable)
| Zone | Viewport Region |
|------|----------------|
| `knowledge` | nx < 0.33 |
| `conversation` | center |
| `meta` | nx > 0.66 |
| `input` | ny > 0.92 |
| `nav` | ny < 0.05 |

In production, zones should be driven by actual component mount positions, not hardcoded thresholds.

### API Surface
```
GridLayer.find(x, y) → nearest point
GridLayer.queryRadius(x, y, r) → [points]
GridLayer.queryZone(name) → [points]
GridLayer.mount(pointId, componentRef)
GridLayer.unmount(pointId)
GridLayer.subdivide(level)
GridLayer.getLevel() → number
GridLayer.onZoneEnter(callback) → unsubscribe
GridLayer.onZoneLeave(callback) → unsubscribe
```

### Debug Mode
- Toggle via hotkey (backtick in prototype)
- Renders: grid lines, anchor dots, crosshair on nearest point, ID/zone/children labels
- Bottom-left log overlay streams: point hover, zone enter/leave, subdivision events, orb snap events

### Integration Point
Guardian frontend. This is a React component that wraps a canvas layer beneath all UI. The grid state lives in a context provider that any child component can consume.

```
src/luna/services/guardian/frontend/
├── components/
│   ├── GridLayer.tsx       ← new
│   ├── GridDebug.tsx       ← new (log overlay)
│   └── ...
├── contexts/
│   └── GridContext.tsx      ← new
```

---

## Orb Visual Spec

### Ring Model
Each ring is a data object:
```python
@dataclass
class OrbRing:
    id: int
    base_radius: float      # resting radius in px
    radius: float            # current animated radius
    base_opacity: float      # resting opacity (0–1)
    opacity: float           # current animated opacity
    hue: float               # HSL hue (default 262 = purple)
    saturation: float        # HSL sat
    lightness: float         # HSL light
    stroke_width: float      # border weight
    has_fill: bool           # innermost ring gets radial gradient fill
```

Default: 5 rings, outermost ~44px radius, spacing derived from `base_radius / (count + 0.5)`.

### Ring Operations
Each ring supports independent mutation:

| Operation | What |
|-----------|------|
| **subdivide** | Split one ring into two thinner rings at ±half-gap from original radius |
| **scale** | Multiply radius by factor |
| **fade** | Set opacity (0–1) |
| **color** | Set hue/sat/light independently |
| **stroke** | Set border width (0.3–4px) |
| **fill** | Toggle radial gradient fill |

`subdivideAll()` splits every ring. `reset()` returns to base configuration.

### Animation System (all JS/canvas, no CSS animation)

#### Breathing
Each ring breathes on its own phase-offset sine wave:
```
offset = ringIndex * 0.7
wave = sin(breatheT + offset)
ring.radius = ring.baseRadius + wave * 2.5 + sin(breatheT * 0.6 + offset * 1.3) * 1.2
ring.opacity = ring.baseOpacity * (0.6 + (0.5 + sin(breatheT * 0.9 + offset) * 0.5) * 0.5)
```
This creates a ripple effect — inner rings pulse slightly out of phase with outer rings.

#### Floating (Fairy Drift)
The orb's render position drifts around its anchor point via Lissajous curve:
```
dx = sin(t * 1.0) * 12 + sin(t * 2.3) * 4
dy = cos(t * 0.7) * 8 + cos(t * 1.9) * 3
bob = sin(t * 0.4) * 5
```
- `t` increments at 0.0006 per frame — very slow
- Position eases toward drift target: `orbX += (targetX - orbX) * 0.04`
- Different frequencies on X/Y means the path never exactly repeats
- Vertical bob adds the "hovering" feel

#### Glow
Three concentric radial gradients rendered behind the rings:

1. **Ambient halo** — radius 2.2× base, very faint (`0.06 * glowPulse`)
2. **Corona** — radius 1.4× base, medium (`0.1 * glowPulse`)
3. **Core bloom** — radius 4× core dot, bright center (`0.5 * corePulse`)

`glowPulse` = `0.7 + sin(breatheT * 0.8) * 0.3` — slow, soft oscillation.

#### Core Dot
Center point, 3–5px radius, pulses brightness on its own cycle:
```
corePulse = 0.6 + sin(breatheT * 1.2) * 0.4
coreRadius = 3 + corePulse * 2
```

#### Anchor Tether
When drifting far from grid anchor, a faint dashed line appears connecting orb to home point. Opacity scales with distance: `min(0.08, dist * 0.003)`.

### Dragging
- Click within `ORB_BASE_RADIUS + 10` to grab
- During drag: orb follows cursor exactly, no drift, no breathing pause
- On release: snap to nearest grid point, resume floating from new home
- Log events: `grab`, `snap` with grid point ID, coordinates, zone

---

## Integration with Existing `orb_state.py`

The current `OrbStateManager` already handles:
- Gesture detection from text (`*pulses*`, `*glows*`, `*drifts*`)
- System events (`processing_query`, `memory_search`, `error`)
- Priority resolution (gesture < system < error)
- WebSocket broadcast to subscribers

### What Needs to Change

`orb_state.py` emits **animation names** (`OrbAnimation.PULSE`, `OrbAnimation.DRIFT`, etc). The new renderer needs to translate these into **ring mutations**.

New file: `src/luna/services/orb_renderer.py`

```python
class OrbRenderer:
    """Translates OrbState into ring-level visual mutations."""

    def __init__(self, ring_count: int = 5):
        self.rings = self._build_rings(ring_count)
        self.drift_params = DriftParams()
        self.glow_params = GlowParams()

    def apply_state(self, state: OrbState):
        """Map animation enum to ring behavior."""
        match state.animation:
            case OrbAnimation.IDLE:
                self._set_idle()
            case OrbAnimation.PULSE:
                self._set_pulse(state.brightness)
            case OrbAnimation.GLOW:
                self._set_glow(state.brightness)
            case OrbAnimation.DRIFT:
                self._set_drift_fast()
            case OrbAnimation.PROCESSING:
                self._set_processing()
            case OrbAnimation.MEMORY_SEARCH:
                self._set_memory_search()
            case OrbAnimation.ERROR:
                self._set_error()
            # ... etc

    def tick(self, dt: float) -> dict:
        """Advance animation by dt seconds. Returns render state for frontend."""
        # Update drift, breathing, glow
        # Return JSON-serializable dict for WebSocket
```

### Animation → Ring Mapping

| OrbAnimation | Ring Behavior |
|-------------|--------------|
| `IDLE` | Default breathing, slow drift, base glow |
| `PULSE` | All rings expand/contract in sync, brightness spike |
| `PULSE_FAST` | Same but 2× speed, tighter amplitude |
| `GLOW` | Glow layers intensify, rings fade slightly to let glow dominate |
| `DRIFT` | Drift radius increases 2×, speed increases |
| `SPIN` | Ring radii oscillate with increasing phase offset (visual rotation) |
| `FLICKER` | Random opacity jitter per ring per frame |
| `WOBBLE` | Drift path becomes erratic, asymmetric |
| `PROCESSING` | Rings pulse sequentially outward (loading ripple) |
| `MEMORY_SEARCH` | Color shift to cyan (#06b6d4), rings expand outward |
| `LISTENING` | Rings contract tight, high opacity, attentive |
| `SPEAKING` | Rings pulse with simulated speech rhythm |
| `ERROR` | Color shift to red, flicker, glow dims |
| `SPLIT` | Rings separate into distinct groups with gaps |

### WebSocket Protocol
Current `OrbStateManager.to_dict()` sends:
```json
{"animation": "pulse", "color": null, "brightness": 1.2, "source": "gesture"}
```

Extend to include ring state for frontend rendering:
```json
{
  "animation": "pulse",
  "rings": [
    {"radius": 44.2, "opacity": 0.38, "hue": 262, "strokeWidth": 1.1},
    {"radius": 35.8, "opacity": 0.45, "hue": 262, "strokeWidth": 0.9},
    ...
  ],
  "drift": {"x": 3.2, "y": -1.8},
  "glow": {"ambient": 0.08, "corona": 0.12, "core": 0.65},
  "core": {"radius": 4.1, "opacity": 0.82}
}
```

The frontend canvas renderer consumes this directly — no CSS, no DOM elements, pure canvas draw calls.

---

## File Map

| File | Action | What |
|------|--------|------|
| `src/luna/services/orb_renderer.py` | **CREATE** | Ring model, animation tick, state→ring mapping |
| `src/luna/services/orb_state.py` | **MODIFY** | Import OrbRenderer, call `renderer.apply_state()` on state change, extend `to_dict()` with ring data |
| `src/luna/services/guardian/frontend/components/GridLayer.tsx` | **CREATE** | Canvas grid with subdivision, debug mode, anchor point system |
| `src/luna/services/guardian/frontend/components/OrbCanvas.tsx` | **CREATE** | Canvas renderer consuming WebSocket ring state |
| `src/luna/services/guardian/frontend/contexts/GridContext.tsx` | **CREATE** | Grid state provider |
| `src/luna/services/guardian/routes/orb.py` | **CREATE** or **MODIFY** existing WS route | Add ring state to broadcast |

---

## Verification Tasks

### 1. Ring Model
- [ ] `OrbRenderer` creates 5 rings with correct spacing
- [ ] Each ring has independent radius, opacity, hue, stroke, fill
- [ ] `subdivide_ring(idx)` splits one ring into two
- [ ] `subdivide_all()` doubles total ring count
- [ ] `reset()` returns to base 5 rings
- [ ] Scale, fade, color, stroke mutations work per-ring

### 2. Animation Tick
- [ ] `tick(dt)` advances breathing phase for all rings
- [ ] Each ring breathes on staggered phase offset
- [ ] Drift follows Lissajous path (two sine frequencies per axis)
- [ ] Drift eases toward target position (0.04 lerp factor)
- [ ] Glow pulses on independent slow cycle
- [ ] Core dot pulses on its own cycle

### 3. State Mapping
- [ ] `apply_state(OrbState(IDLE))` → default breathing
- [ ] `apply_state(OrbState(PULSE))` → synchronized ring expansion
- [ ] `apply_state(OrbState(PROCESSING))` → sequential outward ripple
- [ ] `apply_state(OrbState(MEMORY_SEARCH))` → cyan color shift
- [ ] `apply_state(OrbState(ERROR))` → red, flicker

### 4. WebSocket
- [ ] `to_dict()` includes ring array, drift, glow, core state
- [ ] Frontend receives and renders without recalculating animation (server-authoritative)

### 5. Grid Layer
- [ ] Grid generates correct point count per subdivision level
- [ ] `find(x, y)` returns nearest point
- [ ] Zone assignment works
- [ ] Children mount/unmount tracking
- [ ] Orb snaps to grid point on drop
- [ ] Orb re-snaps on subdivision change

---

## Constants (tunable)

```python
ORB_BASE_RADIUS = 44
INITIAL_RING_COUNT = 5
DRIFT_SPEED = 0.0006
DRIFT_RADIUS_X = 12
DRIFT_RADIUS_Y = 8
BREATHE_SPEED = 0.015
BREATHE_AMPLITUDE = 2.5
GLOW_AMBIENT_MAX = 0.08
GLOW_CORONA_MAX = 0.12
CORE_MIN_RADIUS = 3
CORE_MAX_RADIUS = 5
EASE_FACTOR = 0.04
ANCHOR_TETHER_MAX_OPACITY = 0.08
```

---

## What's NOT In Scope

- Guardian panel layout (knowledge spine, conversation, meta) — separate work
- Voice integration — orb_state.py already handles voice events, renderer just consumes
- Mobile/touch — desktop-first, touch drag can follow later
- Orb-to-orb interaction (multi-user) — future
- Grid persistence (saving subdivision state) — runtime only for now
