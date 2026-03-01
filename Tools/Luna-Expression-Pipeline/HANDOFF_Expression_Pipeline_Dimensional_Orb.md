# HANDOFF: Expression Pipeline — Dimensional Orb

**Author:** Ahab / Zayne  
**Date:** 2026-02-28  
**Target:** Claude Code (implementation)  
**Scope:** Replace gesture-driven orb state with 5-axis dimensional heartbeat + gesture override layer

---

## TL;DR

The orb currently reacts to text gestures (`*smiles*`, `*pulses*`, etc.) parsed from Luna's responses. This is backwards — the LLM is writing stage directions for its own face.

**New model:** The orb has a continuous "heartbeat" driven by 5 emotional dimensions computed from conversation context. Gestures become rare interrupts (12 survivors out of 56) that punch through the dimensional baseline for effects dimensions can't produce.

The frontend Canvas 2D renderer (`OrbCanvas.jsx`) already works perfectly. The ring model, glow layers, breathing, drift — all good. The change is entirely in **what drives those parameters**.

---

## ARCHITECTURE OVERVIEW

```
[Triggers] → [Blender] → [5 Dimensions] → [Dim→Renderer Mapping] → [Priority Stack] → [OrbCanvas]
                                                                          ↑
                                                      [Gesture Override]──┘  (P2, rare)
                                                      [Emoji Signal]────┘   (P1.5, lightweight)
```

### Priority Stack (P4 → P0)

| Priority | Source | When |
|----------|--------|------|
| P4 ERROR | System | `error`, `disconnected` |
| P3 SYSTEM | System | `processing`, `listening`, `speaking`, `memory_search` |
| P2 GESTURE | Text | 12 surviving override gestures (see below) |
| P1.5 EMOJI | Text | Emoji detected in response text |
| P1 DIMENSION | Engine | **Always active.** Continuous 5-axis blend. |
| P0 IDLE | Default | Only when nothing else is active |

**Critical:** When gesture/system states expire, the orb falls back to **current dimensional output**, NOT idle. The orb always has a heartbeat.

---

## PHASE 1: Dimensional Engine (Backend)

### New File: `src/luna/services/dimensional_engine.py`

This is the brain. It takes conversation context and outputs 5 floats.

```python
@dataclass
class DimensionalState:
    valence: float = 0.3      # -1 (negative) to 1 (positive)
    arousal: float = 0.35     # 0 (calm) to 1 (excited)
    certainty: float = 0.7    # 0 (uncertain) to 1 (confident)
    engagement: float = 0.5   # 0 (passive) to 1 (deeply invested)
    warmth: float = 0.6       # 0 (stranger) to 1 (intimate)
```

#### Triggers → Dimensions

Six input signals feed the blender:

| Trigger | Feeds Into | Signal Range |
|---------|-----------|--------------|
| **Sentiment** (message valence) | valence, arousal | -1 to 1 |
| **Memory Hit** (retrieval success) | certainty, engagement | -1 (miss) to 1 (hit) |
| **Identity** (FaceID recognition) | warmth, engagement | 0 (stranger) to 1 (known) |
| **Topic** (personal weight) | engagement, warmth | 0 to 1 |
| **Flow** (conversation momentum) | arousal, engagement | 0 to 1 (ramps with turns) |
| **Time** (time of day) | arousal modifier | -0.3 to 0.3 |

#### Blender

Weighted average with momentum smoothing:

```python
def blend(self, triggers: dict, dt: float) -> DimensionalState:
    """
    triggers = {
        'sentiment': 0.6,
        'memory_hit': 0.8,
        'identity': 0.9,
        'topic_personal': 0.5,
        'flow': 0.3,
        'time_mod': -0.1,
    }
    """
    # Compute raw targets from weighted trigger combination
    raw_valence = (triggers['sentiment'] * 0.7 +
                   triggers['memory_hit'] * 0.2 +
                   triggers.get('time_mod', 0) * 0.1)
    
    raw_arousal = (abs(triggers['sentiment']) * 0.3 +
                   triggers['flow'] * 0.4 +
                   triggers.get('time_mod', 0) * 0.3)
    
    raw_certainty = (0.5 + triggers['memory_hit'] * 0.4 +
                     triggers.get('topic_personal', 0) * 0.1)
    
    raw_engagement = (triggers.get('topic_personal', 0) * 0.4 +
                      triggers['flow'] * 0.3 +
                      triggers['identity'] * 0.3)
    
    raw_warmth = (triggers['identity'] * 0.6 +
                  triggers.get('topic_personal', 0) * 0.3 +
                  max(0, triggers['sentiment']) * 0.1)
    
    # Smooth toward targets (momentum)
    smooth = self.smoothing  # 0.3 default
    self.state.valence += (raw_valence - self.state.valence) * smooth
    self.state.arousal += (raw_arousal - self.state.arousal) * smooth
    self.state.certainty += (raw_certainty - self.state.certainty) * smooth
    self.state.engagement += (raw_engagement - self.state.engagement) * smooth
    self.state.warmth += (raw_warmth - self.state.warmth) * smooth
    
    # Clamp
    self.state.valence = max(-1, min(1, self.state.valence))
    self.state.arousal = max(0, min(1, self.state.arousal))
    self.state.certainty = max(0, min(1, self.state.certainty))
    self.state.engagement = max(0, min(1, self.state.engagement))
    self.state.warmth = max(0, min(1, self.state.warmth))
    
    return self.state
```

#### Where triggers come from

| Trigger | Source in existing codebase | Notes |
|---------|---------------------------|-------|
| `sentiment` | Not yet implemented | Placeholder: use response emotional tone. Simple heuristic or LLM-extracted. Start with 0.5. |
| `memory_hit` | `MemoryMatrix` retrieval result | 1.0 = nodes found, -0.5 = no results, 0 = not searched |
| `identity` | `FaceIDService` recognition confidence | Already exists. 0 = unknown, 1 = high-confidence known user |
| `topic_personal` | QueryRouter topic classification | Already partially exists. 0 = generic, 1 = deeply personal |
| `flow` | Turn counter in conversation | `min(1.0, turn_count * 0.15)` |
| `time_mod` | System clock | `sin(hour * pi / 12) * 0.2` — lower energy at night |

**Implementation note:** For v1, hardcode `sentiment = 0.5` and `topic_personal = 0.5`. The dimensional system works with any signal quality — getting the plumbing right matters more than perfect inputs.

---

## PHASE 2: Dimension → Renderer Mapping

### New File: `src/luna/services/dim_renderer_map.py`

Maps the 5 continuous dimensions to `OrbRenderer` parameters. This replaces the discrete `apply_state()` switch statement for P1 DIMENSION cases.

```python
def map_dimensions_to_renderer(dims: DimensionalState, renderer: OrbRenderer):
    """Continuous mapping from 5 dimensions to ring rendering params."""
    v = dims.valence      # -1 to 1
    a = dims.arousal      # 0 to 1
    c = dims.certainty    # 0 to 1
    e = dims.engagement   # 0 to 1
    w = dims.warmth       # 0 to 1
    
    # ── VALENCE → hue, glow, core brightness ──
    # Cool (240) when negative → neutral (262) → warm (280+) when positive
    hue = 240 + ((v + 1) / 2) * 40 + w * 15
    saturation = 50 + a * 30 + w * 12
    lightness = 38 + ((v + 1) / 2) * 18
    
    for ring in renderer.rings:
        ring.hue = hue + (ring.id / len(renderer.rings)) * 8  # slight per-ring shift
        ring.saturation = saturation + (ring.id / len(renderer.rings)) * 15
        ring.lightness = lightness + (ring.id / len(renderer.rings)) * 10
    
    # ── AROUSAL → breathe speed, drift speed, core pulse ──
    renderer.animation.breathe_speed = 0.008 + a * 0.027
    renderer.animation.breathe_amplitude = 1.5 + a * 2.5
    renderer.animation.drift.speed = 0.0003 + a * 0.0012
    
    # ── CERTAINTY → ring opacity, flicker, phase offset ──
    renderer.animation.ring_phase_offset = 1.2 - c * 0.5  # uncertain = more desync
    opacity_mul = 0.6 + c * 0.4
    for ring in renderer.rings:
        ring.base_opacity = (0.08 + (ring.id / max(1, len(renderer.rings) - 1)) * 0.35) * opacity_mul
    renderer.animation.flicker = c < 0.25  # extreme uncertainty triggers flicker
    
    # ── ENGAGEMENT → corona glow, drift radius ──
    renderer.animation.glow.ambient_max = 0.04 + e * 0.11
    renderer.animation.glow.corona_max = 0.06 + e * 0.16
    renderer.animation.drift.radius_x = 12 + (1 - e) * 10  # less drift when engaged
    renderer.animation.drift.radius_y = 8 + (1 - e) * 7
    
    # ── WARMTH → hue shift, saturation boost ──
    # Already folded into hue/saturation above
    # Additional: warm → slightly larger core glow
    renderer.animation.glow.corona_max += w * 0.04
```

### Mapping Summary Table

| Dimension | Ring Param | Range | Notes |
|-----------|-----------|-------|-------|
| VALENCE | hue | 240→280 | Cool purple → warm violet |
| VALENCE | core brightness | 0.4→0.9 | Dim when negative |
| AROUSAL | breathe_speed | 0.008→0.035 | Calm breathe → excited pulse |
| AROUSAL | drift_speed | 0.0003→0.0015 | Lazy float → energetic |
| AROUSAL | breathe_amplitude | 1.5→4.0 | Subtle → dramatic |
| CERTAINTY | ring_phase_offset | 0.7→1.2 | Sync → desync |
| CERTAINTY | ring opacity mul | 0.6→1.0 | Faded → solid |
| CERTAINTY | flicker | bool | Triggers below 0.25 |
| ENGAGEMENT | glow ambient | 0.04→0.15 | Faint → bright halo |
| ENGAGEMENT | glow corona | 0.06→0.22 | Faint → bright corona |
| ENGAGEMENT | drift radius | 8→22 (x), 5→15 (y) | Less drift = more focused |
| WARMTH | hue bonus | +0→+15 | Shifts warmer |
| WARMTH | saturation bonus | +0→+12 | Richer color |
| WARMTH | corona bonus | +0→+0.04 | Warmer glow |

---

## PHASE 3: Gesture Triage — What Survives

### The 12 Surviving Override Gestures

These cannot be produced by dimensional blending. They need discrete animation modes that punch through.

| Gesture | Animation | Why it survives |
|---------|-----------|-----------------|
| `*splits*` | SPLIT | Ring separation. No dimension maps to this. |
| `*searches*` | ORBIT + cyan color | Deliberate visual search. Color override. |
| `*dims*` | FLICKER @ brightness 0.6 | Intentional withdrawal. Instant, not gradual. |
| `*gasps*` | PULSE_FAST @ 1.4 | Sudden spike. Dimensions take 2+ turns to reach this. |
| `*startles*` | FLICKER @ 1.3 | Surprise interrupt. Not smooth arousal climb. |
| `*sparks*` | FLICKER @ 1.4 | Creative ignition. Arousal too smooth for this. |
| `*lights up*` | GLOW @ 1.45 | Peak brightness snap. Dimensions cap ~1.2. |
| `*spins*` | SPIN | Rotational motion. No dimension maps to rotation. |
| `*spins fast*` | SPIN_FAST | Excited rotation. Speed variant. |
| `*wobbles*` | WOBBLE | Physical instability. Certainty dims but doesn't wobble. |
| `*settles*` | IDLE @ 0.9 | Explicit "done moving." Decay takes too long. |
| `*flickers*` | FLICKER | Deliberate uncertainty display. Sharp not gradual. |

### What Gets Absorbed (38 gestures → dimensions handle them)

These gestures map cleanly to dimensional ranges. Remove from `GESTURE_PATTERNS` dict.

| Absorbed Gesture | Replaced By |
|-----------------|-------------|
| `*smiles*`, `*beams*`, `*frowns*`, `*softens*`, `*brightens*`, `*radiates*` | **valence** |
| `*pulses*`, `*pulses excitedly*`, `*pulses rapidly*`, `*vibrates*`, `*buzzes*`, `*bounces*` | **arousal** |
| `*hesitates*`, `*worries*`, `*winces*` | **certainty** |
| `*perks up*`, `*leans in*`, `*focuses*`, `*concentrates*` | **engagement** |
| `*nods*`, `*hugs*`, `*holds space*` | **warmth** |
| `*glows*`, `*giggles*`, `*dances*` | **valence + arousal** |
| `*thinks*`, `*considers*`, `*ponders*`, `*reflects*`, `*mulls*` | **certainty + engagement** |
| `*drifts*`, `*floats*`, `*exhales*`, `*relaxes*`, `*rests*` | **low arousal** |
| `*pulses warmly*`, `*sighs*` | **valence + arousal combo** |
| `*processes*` | **SYSTEM event** (already exists) |

### What Gets Killed (6 gestures — humanoid body language)

Remove entirely. Orbs don't have these affordances.

| Killed | Reason |
|--------|--------|
| `*eyes widen*` | Orb doesn't have eyes |
| `*tilts*` | Orb doesn't tilt |
| `*leans in*` | Orb doesn't lean |
| `*nods*` | Orb doesn't nod |
| `*hugs*` | Orb doesn't have arms |
| `*holds space*` | Therapy-speak, not visual |

---

## PHASE 4: Integration — Modifying Existing Files

### 4.1 `orb_state.py` — Slim down GESTURE_PATTERNS

**Action:** Replace the 56-entry `GESTURE_PATTERNS` dict with only the 12 survivors.

```python
# BEFORE: 56 patterns
# AFTER: 12 survivors only
GESTURE_PATTERNS: Dict[str, OrbState] = {
    r"\*splits?\b":        OrbState(OrbAnimation.SPLIT, priority=StatePriority.GESTURE, source="gesture"),
    r"\*searches?\b":      OrbState(OrbAnimation.ORBIT, "#06b6d4", priority=StatePriority.GESTURE, source="gesture"),
    r"\*dims?\b":          OrbState(OrbAnimation.FLICKER, brightness=0.6, priority=StatePriority.GESTURE, source="gesture"),
    r"\*gasps?\*":         OrbState(OrbAnimation.PULSE_FAST, brightness=1.4, priority=StatePriority.GESTURE, source="gesture"),
    r"\*startl(es?|ed)\*": OrbState(OrbAnimation.FLICKER, brightness=1.3, priority=StatePriority.GESTURE, source="gesture"),
    r"\*sparks?\*":        OrbState(OrbAnimation.FLICKER, brightness=1.4, priority=StatePriority.GESTURE, source="gesture"),
    r"\*lights? up\*":     OrbState(OrbAnimation.GLOW, brightness=1.45, priority=StatePriority.GESTURE, source="gesture"),
    r"\*spins?\b":         OrbState(OrbAnimation.SPIN, priority=StatePriority.GESTURE, source="gesture"),
    r"\*spins? fast\*":    OrbState(OrbAnimation.SPIN_FAST, priority=StatePriority.GESTURE, source="gesture"),
    r"\*wobbles?\*":       OrbState(OrbAnimation.WOBBLE, priority=StatePriority.GESTURE, source="gesture"),
    r"\*settles?\b":       OrbState(OrbAnimation.IDLE, brightness=0.9, priority=StatePriority.GESTURE, source="gesture"),
    r"\*flickers?\b":      OrbState(OrbAnimation.FLICKER, priority=StatePriority.GESTURE, source="gesture"),
}
```

### 4.2 `orb_state.py` — Add dimensional input channel

**Action:** Add a method to accept `DimensionalState` and a new priority level.

```python
class StatePriority(Enum):
    DEFAULT = 0
    DIMENSION = 1     # ← NEW: continuous heartbeat
    EMOJI = 15        # ← NEW: P1.5
    GESTURE = 2
    SYSTEM = 3
    ERROR = 4
```

Add to `OrbStateManager`:

```python
def __init__(self, ...):
    # ... existing init ...
    self._dimensional_engine = DimensionalEngine()
    self._dimensional_state = DimensionalState()

def update_dimensions(self, triggers: dict):
    """Called each turn with conversation context signals."""
    self._dimensional_state = self._dimensional_engine.blend(triggers, dt=1.0)
    
    # Only apply if no higher-priority state is active
    if self.current_state.priority.value <= StatePriority.DIMENSION.value:
        self.renderer.reset()
        map_dimensions_to_renderer(self._dimensional_state, self.renderer)
        self._broadcast_dimensional()

def _broadcast_dimensional(self):
    """Broadcast dimensional state without overwriting gesture/system state."""
    state = OrbState(
        animation=OrbAnimation.IDLE,  # Not really idle — dimensions drive params
        priority=StatePriority.DIMENSION,
        source="dimension",
    )
    self.current_state = state
    self._broadcast(state)
```

### 4.3 `orb_state.py` — Fix `end_response` fallback

**Action:** When gesture/system states expire, fall back to dimensional output, not idle.

```python
def end_response(self):
    """When response ends, return to dimensional heartbeat — not idle."""
    if self._idle_task and not self._idle_task.done():
        self._idle_task.cancel()
    
    async def delayed_return():
        await asyncio.sleep(2.0)
        # Fall back to dimensions, NOT idle
        self.renderer.reset()
        map_dimensions_to_renderer(self._dimensional_state, self.renderer)
        self._broadcast_dimensional()
    
    try:
        loop = asyncio.get_running_loop()
        self._idle_task = loop.create_task(delayed_return())
    except RuntimeError:
        pass
```

### 4.4 `orb_renderer.py` — No structural changes needed

The renderer already handles all the params the dimensional mapper needs. `to_dict()` already serializes rings + animation + transition. No changes required.

### 4.5 `OrbCanvas.jsx` — No changes needed

The frontend renderer already consumes `rendererState` from WebSocket. The dimensional mapper writes to the same `OrbRenderer` → `to_dict()` pipeline. It just works.

### 4.6 `useOrbState.js` — Minor: add dimensional data to state

**Action:** Pass through dimensional values for debug/monitoring.

```javascript
// In onmessage handler, add:
setOrbState({
  animation: data.animation || 'idle',
  color: data.color || null,
  brightness: data.brightness || 1,
  source: data.source || 'websocket',
  renderer: data.renderer || null,
  dimensions: data.dimensions || null,  // ← NEW
});
```

### 4.7 `orb_state.py` — Update `to_dict()` to include dimensions

```python
def to_dict(self) -> dict:
    result = {
        # ... existing fields ...
    }
    if hasattr(self, '_dimensional_state'):
        result["dimensions"] = {
            "valence": round(self._dimensional_state.valence, 3),
            "arousal": round(self._dimensional_state.arousal, 3),
            "certainty": round(self._dimensional_state.certainty, 3),
            "engagement": round(self._dimensional_state.engagement, 3),
            "warmth": round(self._dimensional_state.warmth, 3),
        }
    return result
```

---

## PHASE 5: Where to Call `update_dimensions()`

The dimensional engine needs to be fed each conversational turn. The integration point is wherever Luna processes a user message and generates a response.

### In the query pipeline (likely `engine.py` or `agent_loop.py`):

```python
# After memory retrieval, before response generation:
triggers = {
    'sentiment': 0.5,  # TODO: extract from user message
    'memory_hit': 1.0 if memory_results else -0.5,
    'identity': face_id_confidence,  # from FaceID service
    'topic_personal': 0.5,  # TODO: from topic classifier
    'flow': min(1.0, turn_count * 0.15),
    'time_mod': math.sin(datetime.now().hour * math.pi / 12) * 0.2,
}

orb_state_manager.update_dimensions(triggers)
```

**Start simple.** Hardcode `sentiment = 0.5` and `topic_personal = 0.5` for v1. The dimensional system responds to any signal quality. Getting the plumbing right matters more than perfect inputs.

---

## FILE INVENTORY

### New Files to Create

| File | Purpose |
|------|---------|
| `src/luna/services/dimensional_engine.py` | 5-axis blender with momentum smoothing |
| `src/luna/services/dim_renderer_map.py` | Dimension → OrbRenderer parameter mapping |

### Files to Modify

| File | Change |
|------|--------|
| `src/luna/services/orb_state.py` | Slim GESTURE_PATTERNS to 12. Add dimensional input. Fix fallback. |
| `src/luna/services/orb_state.py` | New StatePriority.DIMENSION level. update_dimensions() method. |
| `src/luna/services/orb_state.py` | Update to_dict() to include dimensional values. |
| `frontend/src/hooks/useOrbState.js` | Pass through `dimensions` field (optional, for debug). |

### Files That DON'T Change

| File | Why |
|------|-----|
| `src/luna/services/orb_renderer.py` | Already handles all needed params. |
| `frontend/src/components/OrbCanvas.jsx` | Already consumes rendererState from WS. |
| `frontend/src/config/orbCanvas.js` | Constants remain valid defaults. |

---

## TESTING SCENARIOS

### 1. Warm Greeting (Known User)
```python
triggers = {'sentiment': 0.6, 'memory_hit': 0.5, 'identity': 0.9, 'topic_personal': 0.3, 'flow': 0.1, 'time_mod': 0.2}
# Expected: hue ~270 (warm purple), moderate glow, gentle breathing, high opacity
```

### 2. Memory Miss
```python
triggers = {'sentiment': 0.3, 'memory_hit': -0.4, 'identity': 0.9, 'topic_personal': 0.5, 'flow': 0.3, 'time_mod': 0}
# Expected: hue ~255 (cooler), certainty < 0.3 → flicker, reduced opacity, hedging flag
```

### 3. Deep Personal Conversation
```python
triggers = {'sentiment': 0.5, 'memory_hit': 0.7, 'identity': 0.9, 'topic_personal': 0.8, 'flow': 0.6, 'time_mod': 0}
# Expected: high engagement → bright corona, tight drift, hue ~275, deep dive flag
```

### 4. Gesture Override (*splits*)
```python
# Dimensional baseline active, then text contains "*splits*"
# Expected: P2 GESTURE takes priority, SPLIT animation fires, after sustain (2s)
#           falls back to dimensional baseline — NOT idle
```

### 5. Late Night Session
```python
triggers = {'sentiment': 0.3, 'memory_hit': 0.5, 'identity': 0.9, 'topic_personal': 0.6, 'flow': 0.7, 'time_mod': -0.2}
# Expected: lower arousal, slower breathing, wider drift, subdued glow
```

---

## REFERENCE ARTIFACTS

| Artifact | Location | Purpose |
|----------|----------|---------|
| Expression Pipeline v4 (React prototype) | `luna_expression_v4_rings.jsx` (project folder) | Interactive node graph with dim-driven Canvas 2D orb. Run simulations. |
| Grid Layer Prototype | `grid_layer_prototype.html` (project folder) | Original Canvas 2D ring renderer. Reference implementation. |
| Gesture Triage Map | `gesture_triage_map.py` (project folder) | Python data structure: all 56 gestures categorized. |
| Expression Pipeline v3 | `luna_expression_v3.jsx` (project folder) | Earlier prototype without gesture layer. |

---

## BUILD ORDER

1. **Create `dimensional_engine.py`** — Pure Python, no dependencies. Unit-testable in isolation.
2. **Create `dim_renderer_map.py`** — Takes DimensionalState + OrbRenderer, maps values. Also pure.
3. **Modify `orb_state.py`** — Add StatePriority.DIMENSION, trim GESTURE_PATTERNS to 12, add update_dimensions(), fix end_response fallback.
4. **Wire into query pipeline** — Call update_dimensions() with hardcoded triggers. Verify orb responds.
5. **Add real trigger sources** — Connect memory_hit from MemoryMatrix, identity from FaceID, flow from turn counter, time from clock.
6. **Sentiment & topic** — Implement when ready. System works fine with hardcoded 0.5 until then.

---

## NON-NEGOTIABLES

1. **Offline-first**: All computation happens locally. No cloud calls for expression.
2. **Fallback is dimensional, not idle**: When any override expires, the orb returns to its dimensional heartbeat.
3. **12 gesture survivors only**: Don't add gestures back. If something needs to be expressive, it should be a dimension.
4. **Smooth, not jumpy**: Momentum smoothing (0.3 default) means dimensions lerp toward targets. Never snap unless certainty < 0.25.
5. **Frontend stays untouched**: OrbCanvas.jsx works. Don't touch it.
