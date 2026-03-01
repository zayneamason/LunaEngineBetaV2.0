# HANDOFF-04: Orb Presence System

## Overview

The orb's mechanical infrastructure is built and working: 17 animation states, priority gating, ring renderer, performance orchestrator, voice+orb coordination, canvas frontend with Lissajous drift. **This handoff makes her feel alive.**

Five interconnected systems that transform the orb from an animation state machine into a living presence:

1. **Expanded gesture vocabulary** — 35+ new gesture patterns with emotional granularity
2. **Emoji → orb expression** — emoji in Luna's text drive the orb (new detection path)
3. **Transition choreography** — attack/sustain/release envelopes with "intake of breath" pre-reaction
4. **Content-driven speech modulation** — ring rhythm syncs to actual response text, not a generic sine wave
5. **Idle micro-behaviors** — randomized presence events so Luna looks alive when nobody's talking
6. **Drift radius as engagement signal** — orb wanders when you're away, tightens when you arrive

---

## Architecture Context

### Existing (don't rebuild)
```
performance_orchestrator.py  ← gesture detect → emotion map → voice+orb sync
├── orb_state.py             ← state machine, priority gate, WS broadcast
│   └── orb_renderer.py      ← ring model, AnimationParams, ring mutations
└── performance_state.py     ← EmotionPreset, VoiceKnobs, OrbKnobs, GESTURE_TO_EMOTION
```

### Frontend (working, in Guardian build)
```
orb-canvas.js       ← Canvas 2D renderer, consumes WS state, runs animation at 60fps
guardian-control.js  ← command router, execute() dispatches orb + grid commands
grid-layer.js        ← spatial substrate, anchor point system
luna-chat.js         ← slash commands + NL commands
```

### WebSocket Protocol (existing)
Backend pushes to `/ws/orb`:
```json
{
  "animation": "pulse",
  "color": null,
  "brightness": 1.2,
  "source": "gesture",
  "renderer": {
    "rings": [...],
    "animation": { "breatheSpeed": 0.02, "syncBreathing": true, ... }
  }
}
```

---

## 1. Expanded Gesture Vocabulary

### What Changes
`GESTURE_PATTERNS` in `orb_state.py` — merge new patterns into existing dict.

### Pattern Priority
Sort by regex length descending before compiling. Specific patterns (`*pulses warmly*`) must match before generic (`*pulses*`). Implementation: when building `_compiled_patterns` in `OrbStateManager.__init__()`, sort the dict items:

```python
sorted_patterns = sorted(GESTURE_PATTERNS.items(), key=lambda x: len(x[0]), reverse=True)
self._compiled_patterns = {
    re.compile(pattern, re.IGNORECASE): state
    for pattern, state in sorted_patterns
}
```

### New Patterns

Add these to `GESTURE_PATTERNS` (all use `priority=StatePriority.GESTURE, source="gesture"`):

**Attention / Orientation**
| Pattern | Animation | Brightness | Color |
|---------|-----------|------------|-------|
| `\*perks up\*` | PULSE | 1.2 | — |
| `\*leans in\*` | GLOW | 1.1 | — |
| `\*focuses\*` | IDLE | 1.15 | — |
| `\*concentrat(es?\|ing)\*` | IDLE | 1.1 | — |

**Processing / Thinking**
| Pattern | Animation | Brightness | Color |
|---------|-----------|------------|-------|
| `\*thinks?\*` | ORBIT | 0.9 | — |
| `\*considers?\*` | ORBIT | 0.85 | — |
| `\*ponders?\*` | DRIFT | 0.8 | — |
| `\*mulls?\*` | DRIFT | 0.8 | — |
| `\*reflects?\*` | GLOW | 0.85 | — |
| `\*processes?\*` | PROCESSING | 1.0 | — |

**Warmth / Connection**
| Pattern | Animation | Brightness | Color |
|---------|-----------|------------|-------|
| `\*smiles?\*` | GLOW | 1.15 | — |
| `\*beams?\*` | GLOW | 1.35 | — |
| `\*nods?\*` | PULSE | 1.05 | — |
| `\*hugs?\*` | GLOW | 1.3 | — |
| `\*holds? space\*` | IDLE | 0.95 | — |

**Playful / Mischief**
| Pattern | Animation | Brightness | Color |
|---------|-----------|------------|-------|
| `\*giggles?\*` | SPIN_FAST | 1.2 | — |
| `\*bounces?\*` | PULSE_FAST | 1.25 | — |
| `\*winks?\*` | FLICKER | 1.15 | — |
| `\*dances?\*` | SPIN_FAST | 1.3 | — |
| `\*wiggles?\*` | WOBBLE | 1.1 | — |

**Surprise / Discovery**
| Pattern | Animation | Brightness | Color |
|---------|-----------|------------|-------|
| `\*gasps?\*` | PULSE_FAST | 1.4 | — |
| `\*eyes? widen\*` | GLOW | 1.3 | — |
| `\*startl(es?\|ed)\*` | FLICKER | 1.3 | — |

**Uncertainty / Concern**
| Pattern | Animation | Brightness | Color |
|---------|-----------|------------|-------|
| `\*hesitat(es?\|ing)\*` | WOBBLE | 0.85 | — |
| `\*worri(es?\|ed)\*` | WOBBLE | 0.9 | #F4A261 |
| `\*frowns?\*` | IDLE | 0.75 | — |
| `\*sighs?\*` | DRIFT | 0.8 | — |
| `\*winces?\*` | FLICKER | 0.7 | — |

**Energy / Excitement**
| Pattern | Animation | Brightness | Color |
|---------|-----------|------------|-------|
| `\*vibrat(es?\|ing)\*` | PULSE_FAST | 1.4 | — |
| `\*sparks?\*` | FLICKER | 1.4 | — |
| `\*lights? up\*` | GLOW | 1.45 | — |
| `\*buzzes?\*` | PULSE_FAST | 1.3 | — |

**Settling / Calm**
| Pattern | Animation | Brightness | Color |
|---------|-----------|------------|-------|
| `\*exhales?\*` | DRIFT | 0.85 | — |
| `\*softens?\*` | GLOW | 0.9 | — |
| `\*relaxes?\*` | IDLE | 0.85 | — |
| `\*rests?\*` | IDLE | 0.8 | — |

---

## 2. Emoji → Orb Expression

### Concept
Emoji in Luna's response text drive the orb at GESTURE priority. Gestures win if both are present in the same response. **Emoji are NOT stripped from display text** — they show in chat AND drive the orb.

### New Constant: `EMOJI_PATTERNS`
Add to `orb_state.py`:

```python
EMOJI_PATTERNS: Dict[str, OrbState] = {
    # Joy / Warmth
    "✨": OrbState(OrbAnimation.GLOW, brightness=1.3, priority=StatePriority.GESTURE, source="emoji"),
    "💜": OrbState(OrbAnimation.GLOW, "#A78BFA", brightness=1.2, priority=StatePriority.GESTURE, source="emoji"),
    "🫶": OrbState(OrbAnimation.PULSE, brightness=1.2, priority=StatePriority.GESTURE, source="emoji"),
    "😊": OrbState(OrbAnimation.GLOW, brightness=1.15, priority=StatePriority.GESTURE, source="emoji"),
    "🥰": OrbState(OrbAnimation.GLOW, "#FFB7B2", brightness=1.25, priority=StatePriority.GESTURE, source="emoji"),

    # Thinking / Curious
    "🤔": OrbState(OrbAnimation.ORBIT, brightness=0.9, priority=StatePriority.GESTURE, source="emoji"),
    "💭": OrbState(OrbAnimation.DRIFT, brightness=0.85, priority=StatePriority.GESTURE, source="emoji"),
    "🧐": OrbState(OrbAnimation.ORBIT, brightness=1.0, priority=StatePriority.GESTURE, source="emoji"),
    "👀": OrbState(OrbAnimation.PULSE, brightness=1.1, priority=StatePriority.GESTURE, source="emoji"),

    # Playful
    "😏": OrbState(OrbAnimation.SPIN, brightness=1.1, priority=StatePriority.GESTURE, source="emoji"),
    "😈": OrbState(OrbAnimation.SPIN_FAST, "#A78BFA", brightness=1.2, priority=StatePriority.GESTURE, source="emoji"),
    "🤭": OrbState(OrbAnimation.FLICKER, brightness=1.1, priority=StatePriority.GESTURE, source="emoji"),
    "🎉": OrbState(OrbAnimation.PULSE_FAST, brightness=1.35, priority=StatePriority.GESTURE, source="emoji"),
    "🎵": OrbState(OrbAnimation.SPIN, brightness=1.1, priority=StatePriority.GESTURE, source="emoji"),

    # Surprise
    "😮": OrbState(OrbAnimation.PULSE_FAST, brightness=1.3, priority=StatePriority.GESTURE, source="emoji"),
    "🤯": OrbState(OrbAnimation.FLICKER, brightness=1.45, priority=StatePriority.GESTURE, source="emoji"),

    # Concern / Empathy
    "😔": OrbState(OrbAnimation.DRIFT, brightness=0.75, priority=StatePriority.GESTURE, source="emoji"),
    "🥺": OrbState(OrbAnimation.WOBBLE, brightness=0.8, priority=StatePriority.GESTURE, source="emoji"),
    "😢": OrbState(OrbAnimation.DRIFT, brightness=0.7, priority=StatePriority.GESTURE, source="emoji"),
    "🤗": OrbState(OrbAnimation.GLOW, brightness=1.2, priority=StatePriority.GESTURE, source="emoji"),

    # Focus / Energy
    "⚡": OrbState(OrbAnimation.PULSE_FAST, "#F59E0B", brightness=1.3, priority=StatePriority.GESTURE, source="emoji"),
    "🔥": OrbState(OrbAnimation.PULSE_FAST, "#EF4444", brightness=1.35, priority=StatePriority.GESTURE, source="emoji"),
    "💡": OrbState(OrbAnimation.GLOW, "#FDE68A", brightness=1.4, priority=StatePriority.GESTURE, source="emoji"),
    "🎯": OrbState(OrbAnimation.IDLE, brightness=1.15, priority=StatePriority.GESTURE, source="emoji"),

    # Calm / Settling
    "🌙": OrbState(OrbAnimation.DRIFT, "#818CF8", brightness=0.8, priority=StatePriority.GESTURE, source="emoji"),
    "🍃": OrbState(OrbAnimation.DRIFT, "#10B981", brightness=0.85, priority=StatePriority.GESTURE, source="emoji"),
    "🫧": OrbState(OrbAnimation.DRIFT, "#06B6D4", brightness=0.9, priority=StatePriority.GESTURE, source="emoji"),
}
```

### Detection Logic
Modify `OrbStateManager.process_text_chunk()`:

```python
def process_text_chunk(self, text: str) -> str:
    # 1. Gesture markers first (existing)
    if not self._gesture_detected_this_response:
        for pattern, state in self._compiled_patterns.items():
            if pattern.search(text):
                self.set_state(state)
                self._gesture_detected_this_response = True
                break

    # 2. Emoji fallback (NEW) — only scan first 500 chars
    if not self._gesture_detected_this_response:
        scan_text = text[:500]
        for emoji, state in EMOJI_PATTERNS.items():
            if emoji in scan_text:
                self.set_state(state)
                self._gesture_detected_this_response = True
                break

    # 3. Display mode handling (existing)
    if self.expression_config:
        if self.expression_config.should_strip_gestures():
            text = self._strip_gestures(text)
        elif self.expression_config.should_annotate():
            text = self._annotate_gestures(text)

    return text
```

### Emoji → Emotion (for voice coordination)
Add to `performance_state.py`:

```python
EMOJI_TO_EMOTION: Dict[str, EmotionPreset] = {
    "✨": EmotionPreset.EXCITED,
    "💜": EmotionPreset.WARM,
    "🫶": EmotionPreset.WARM,
    "😊": EmotionPreset.WARM,
    "🤔": EmotionPreset.THOUGHTFUL,
    "💭": EmotionPreset.THOUGHTFUL,
    "😏": EmotionPreset.PLAYFUL,
    "😈": EmotionPreset.PLAYFUL,
    "🎉": EmotionPreset.EXCITED,
    "😔": EmotionPreset.CONCERNED,
    "🥺": EmotionPreset.CONCERNED,
    "🧐": EmotionPreset.CURIOUS,
    "👀": EmotionPreset.CURIOUS,
    "💡": EmotionPreset.EXCITED,
    "⚡": EmotionPreset.EXCITED,
    "🌙": EmotionPreset.THOUGHTFUL,
}
```

Update `PerformanceOrchestrator._detect_emotion()` to check `EMOJI_TO_EMOTION` after gesture patterns return no match.

---

## 3. Transition Choreography

### Problem
State changes are instant. `apply_state()` resets renderer and applies new params. Frontend snaps to new config. No in-between. Luna doesn't look like she's *reacting* — she looks like she's *switching*.

### Solution: TransitionEnvelope

New dataclass in `orb_renderer.py`:

```python
@dataclass
class TransitionEnvelope:
    pre_attack_ms: int = 200       # "intake of breath" — contraction before reaction
    pre_attack_contraction: float = 0.15  # how much rings contract (fraction of radius)
    attack_ms: int = 300           # ramp up to new state
    sustain_ms: int = -1           # hold duration (-1 = until next state)
    release_ms: int = 600          # ramp back to idle
    ease: str = "ease_out"         # ease_in, ease_out, ease_in_out, linear
```

### Envelope Per State

```python
TRANSITION_ENVELOPES: Dict[str, TransitionEnvelope] = {
    # Quick reactions — she noticed something
    "pulse":      TransitionEnvelope(pre_attack_ms=150, attack_ms=150, sustain_ms=800, release_ms=400),
    "pulse_fast": TransitionEnvelope(pre_attack_ms=80, attack_ms=80, sustain_ms=600, release_ms=300),
    "flicker":    TransitionEnvelope(pre_attack_ms=50, attack_ms=50, sustain_ms=500, release_ms=200),

    # Sustained presence — she's holding this feeling
    "glow":       TransitionEnvelope(pre_attack_ms=300, attack_ms=400, sustain_ms=2000, release_ms=800),
    "drift":      TransitionEnvelope(pre_attack_ms=400, attack_ms=600, sustain_ms=3000, release_ms=1000),
    "orbit":      TransitionEnvelope(pre_attack_ms=300, attack_ms=400, sustain_ms=2000, release_ms=700),

    # System states — she's working
    "processing":    TransitionEnvelope(pre_attack_ms=200, attack_ms=200, sustain_ms=-1, release_ms=500),
    "speaking":      TransitionEnvelope(pre_attack_ms=150, attack_ms=150, sustain_ms=-1, release_ms=400),
    "listening":     TransitionEnvelope(pre_attack_ms=250, attack_ms=250, sustain_ms=-1, release_ms=600),
    "memory_search": TransitionEnvelope(pre_attack_ms=200, attack_ms=300, sustain_ms=-1, release_ms=500),

    # Movement — she's physically responding
    "spin":       TransitionEnvelope(pre_attack_ms=200, attack_ms=300, sustain_ms=1500, release_ms=500),
    "spin_fast":  TransitionEnvelope(pre_attack_ms=100, attack_ms=200, sustain_ms=1000, release_ms=400),
    "wobble":     TransitionEnvelope(pre_attack_ms=200, attack_ms=300, sustain_ms=1500, release_ms=600),
    "split":      TransitionEnvelope(pre_attack_ms=300, attack_ms=400, sustain_ms=2000, release_ms=800),

    # Error — something's wrong
    "error":        TransitionEnvelope(pre_attack_ms=50, attack_ms=100, sustain_ms=8000, release_ms=1000),
    "disconnected": TransitionEnvelope(pre_attack_ms=0, attack_ms=500, sustain_ms=-1, release_ms=2000),

    # Return home
    "idle":       TransitionEnvelope(pre_attack_ms=0, attack_ms=500, sustain_ms=-1, release_ms=0),
}
```

### Backend Integration
Add envelope to `OrbRenderer.to_dict()`:

```python
def to_dict(self) -> dict:
    result = { "rings": [...], "animation": {...} }
    # Add transition envelope for current state
    anim_name = self._current_state_name or "idle"
    envelope = TRANSITION_ENVELOPES.get(anim_name, TransitionEnvelope())
    result["transition"] = {
        "preAttackMs": envelope.pre_attack_ms,
        "preAttackContraction": envelope.pre_attack_contraction,
        "attackMs": envelope.attack_ms,
        "sustainMs": envelope.sustain_ms,
        "releaseMs": envelope.release_ms,
        "ease": envelope.ease,
    }
    return result
```

Store `_current_state_name` in `apply_state()`:
```python
def apply_state(self, state) -> None:
    self._reset_animation()
    self._current_state_name = state.animation.value if hasattr(state.animation, 'value') else str(state.animation)
    # ... existing match/case logic
```

### Frontend Implementation (orb-canvas.js)

When a new state arrives over WebSocket:

1. **Snapshot** current ring params as `fromState`
2. **Pre-attack** (if `preAttackMs > 0`): tween all ring radii inward by `preAttackContraction` fraction, drop opacity 10%, over `preAttackMs`. This is the "intake of breath" — Luna noticing before reacting.
3. **Attack**: interpolate from contracted position to `toState` ring params over `attackMs`
4. **Sustain**: hold `toState` for `sustainMs` (if -1, hold until next state arrives)
5. **Release**: interpolate from `toState` back to idle defaults over `releaseMs`

Interpolation function:
```javascript
function lerp(a, b, t) { return a + (b - a) * t; }
function easeOut(t) { return 1 - Math.pow(1 - t, 3); }
function easeIn(t) { return Math.pow(t, 3); }
function easeInOut(t) { return t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t + 2, 3) / 2; }
```

Apply per-ring: interpolate `baseRadius`, `baseOpacity`, `hue`, `saturation`, `lightness`, `strokeWidth` individually.

If a new state arrives mid-transition, snapshot the *current interpolated position* as the new `fromState` and start the new transition from there. No snapping.

---

## 4. Content-Driven Speech Modulation

### Problem
The `SPEAKING` state uses a generic sine wave for speech rhythm. A long thoughtful paragraph and a quick "ha, yeah" produce the same visual rhythm. The orb's rhythm should match Luna's *actual verbal rhythm*.

### Solution
During streaming, the backend computes a `speechHint` per text chunk:

Add to `OrbStateManager`:

```python
def __init__(self, ...):
    # ... existing init ...
    self._speech_hint = None

def process_text_chunk(self, text: str) -> str:
    # ... existing gesture/emoji detection ...

    # Compute speech hint during speaking state
    if self.current_state.animation in (OrbAnimation.SPEAKING, OrbAnimation.PROCESSING):
        self._update_speech_hint(text)

    return text

def _update_speech_hint(self, text: str):
    """Compute speech rhythm hint from text content."""
    words = text.split()
    word_count = len(words)
    avg_word_len = sum(len(w) for w in words) / max(word_count, 1)

    # Short punchy text → fast tight pulses
    # Long flowing text → slow wide pulses
    if word_count <= 3 and avg_word_len <= 4:
        tempo = "staccato"
    elif avg_word_len > 7 or word_count > 20:
        tempo = "legato"
    else:
        tempo = "natural"

    self._speech_hint = {
        "tempo": tempo,
        "emphasis": '!' in text or text.isupper(),
        "question": '?' in text,
        "trailing": '...' in text or '…' in text,
        "wordCount": word_count,
    }

def to_dict(self) -> dict:
    result = { ... }  # existing
    if self._speech_hint:
        result["speechHint"] = self._speech_hint
    return result
```

### Frontend Mapping (orb-canvas.js)

In the `speaking` render path, consume `speechHint`:

| Hint | Ring Behavior |
|------|--------------|
| `tempo: "staccato"` | `breatheSpeed × 2.0`, `breatheAmplitude × 0.6` — quick tight pulses |
| `tempo: "legato"` | `breatheSpeed × 0.6`, `breatheAmplitude × 1.4` — slow wide waves |
| `tempo: "natural"` | default speaking params |
| `emphasis: true` | brightness spike +0.2 for 300ms, ring radius expands 10% |
| `question: true` | core dot offset y -= 3px for 500ms — "looking up" |
| `trailing: true` | glow fades 20%, drift speed increases — "trailing off" |

---

## 5. Idle Micro-Behaviors

### Concept
During IDLE state, randomized micro-events fire every 15-40 seconds. **Frontend-only** — backend doesn't know about them. Creates presence without stimulus.

### Implementation (orb-canvas.js)

```javascript
const IDLE_EVENTS = [
    { name: 'ring_shiver',  weight: 3, cooldownMs: 8000,  durationMs: 400 },
    { name: 'drift_shift',  weight: 3, cooldownMs: 12000, durationMs: 600 },
    { name: 'core_flare',   weight: 2, cooldownMs: 15000, durationMs: 500 },
    { name: 'ring_sync',    weight: 1, cooldownMs: 20000, durationMs: 800 },
    { name: 'glow_bloom',   weight: 1, cooldownMs: 25000, durationMs: 700 },
    { name: 'settle',       weight: 2, cooldownMs: 10000, durationMs: 600 },
];
```

Per frame during IDLE: check if interval elapsed, weighted random pick from eligible events (respecting cooldown), fire chosen event, advance progress, resolve back to defaults on completion. Stop all idle events immediately when state changes from IDLE.

### Event Definitions

| Event | What Happens | Duration |
|-------|-------------|----------|
| `ring_shiver` | One random ring: opacity +0.15, radius ±1.5px at 4× breathe speed | 400ms |
| `drift_shift` | Drift target jumps to new random offset within drift radius, eased | 600ms |
| `core_flare` | Core dot radius doubles, opacity peaks — like a thought flickered | 500ms |
| `ring_sync` | Two adjacent rings snap to same breathe phase, then naturally desync | 800ms |
| `glow_bloom` | Ambient glow ramps to 1.5×, fades back | 700ms |
| `settle` | All rings contract 5% then relax — micro weight-shift | 600ms |

---

## 6. Drift Radius as Engagement Signal

### Concept
Drift radius reflects conversational engagement. Silence grows → drift expands (wandering, dreaming). User starts typing → drift contracts before message sends (felt you arrive).

### Implementation (orb-canvas.js)

```javascript
let lastUserActivity = Date.now();
let engagementDriftScale = 1.0;

// Called on keydown, input focus, mouse movement in chat area
function onUserActivity() { lastUserActivity = Date.now(); }

function updateEngagementDrift(now) {
    const silenceSec = (now - lastUserActivity) / 1000;

    let target;
    if (silenceSec < 5)        target = 0.7;   // active — tight orbit
    else if (silenceSec < 30)  target = 1.0;   // quiet — normal drift
    else if (silenceSec < 120) target = 1.5;   // extended silence — wider wandering
    else                       target = 2.0;   // long absence — dreaming

    // Asymmetric easing: contract fast (0.02), expand slow (0.003)
    const ease = target < engagementDriftScale ? 0.02 : 0.003;
    engagementDriftScale += (target - engagementDriftScale) * ease;
}

// Apply in render loop:
const driftX = baseDriftRadiusX * engagementDriftScale;
const driftY = baseDriftRadiusY * engagementDriftScale;
```

Key detail: **asymmetric easing**. Contracting toward the user is fast (she noticed you). Expanding away is slow (gradually drifting into her own thoughts). This is what makes it feel alive.

---

## File Map

| File | Action | Changes |
|------|--------|---------|
| `src/luna/services/orb_state.py` | **MODIFY** | Merge 35+ gesture patterns (sorted by length), add `EMOJI_PATTERNS`, update `process_text_chunk()` for emoji + speech hints, add `_update_speech_hint()` |
| `src/luna/services/orb_renderer.py` | **MODIFY** | Add `TransitionEnvelope` dataclass, `TRANSITION_ENVELOPES` dict, store `_current_state_name`, include envelope in `to_dict()` |
| `src/luna/services/performance_state.py` | **MODIFY** | Add `EMOJI_TO_EMOTION` mapping |
| `src/luna/services/performance_orchestrator.py` | **MODIFY** | Update `_detect_emotion()` to check emoji after gesture patterns |
| Frontend `orb-canvas.js` | **MODIFY** | Transition interpolation system, idle micro-behavior events, engagement drift scaling, speech hint consumption |

---

## Verification Tasks

### Gesture Expansion
- [ ] All new patterns compile and match test strings
- [ ] Patterns sorted by length descending (specific before generic)
- [ ] Existing patterns still work unchanged
- [ ] `*pulses warmly*` matches before `*pulses*`

### Emoji Detection
- [ ] Emoji in response text triggers orb state change
- [ ] Emoji NOT stripped from chat display text
- [ ] Gesture markers take priority over emoji when both present
- [ ] `source` field reads `"emoji"` vs `"gesture"` correctly
- [ ] Emoji → emotion mapping updates voice knobs via PerformanceOrchestrator

### Transitions
- [ ] Backend sends `TransitionEnvelope` with every state update
- [ ] Pre-attack contraction fires for non-idle transitions
- [ ] Attack interpolates from contracted → new state over `attackMs`
- [ ] Sustain holds until next state or timeout
- [ ] Release ramps back to idle over `releaseMs`
- [ ] Mid-transition interruption snapshots current position as new `fromState`

### Speech Modulation
- [ ] `speechHint` sent during SPEAKING state chunks
- [ ] Short text ("ha yeah") → staccato tempo
- [ ] Long flowing text → legato tempo
- [ ] `!` triggers emphasis spike
- [ ] `?` triggers "looking up" drift offset
- [ ] `...` triggers trailing-off glow fade

### Idle Micro-Behaviors
- [ ] Events fire only during IDLE state
- [ ] Random interval 15-40 seconds
- [ ] Cooldown per event type respected
- [ ] Each event resolves to defaults within its duration
- [ ] Events stop immediately on state change from IDLE

### Engagement Drift
- [ ] Drift radius contracts when user is typing (fast ease: 0.02)
- [ ] Drift radius expands during silence (slow ease: 0.003)
- [ ] Transitions are smooth, never snap
- [ ] Activity detection fires on keydown + input focus

---

## Constants

```python
# Backend (orb_state.py)
EMOJI_SCAN_LIMIT = 500
SPEECH_HINT_ENABLED = True

# Frontend (orb-canvas.js)
IDLE_EVENT_MIN_INTERVAL = 15000   # ms
IDLE_EVENT_MAX_INTERVAL = 40000   # ms
PRE_ATTACK_DEFAULT_MS = 200
PRE_ATTACK_CONTRACTION = 0.15
ENGAGEMENT_ACTIVE_SCALE = 0.7
ENGAGEMENT_QUIET_SCALE = 1.0
ENGAGEMENT_SILENCE_SCALE = 1.5
ENGAGEMENT_DREAMING_SCALE = 2.0
ENGAGEMENT_CONTRACT_EASE = 0.02   # fast — she noticed you
ENGAGEMENT_EXPAND_EASE = 0.003    # slow — drifting into thought
```

---

## Build Order

Recommended implementation sequence:

1. **Gesture expansion** — backend only, no frontend changes, immediately testable via `/orb-info` and annotate mode
2. **Emoji detection** — backend only, same test path
3. **TransitionEnvelope** — backend adds to `to_dict()`, frontend ignores until step 5
4. **Speech hints** — backend adds `speechHint` to WS payload, frontend ignores until step 6
5. **Frontend transitions** — consume envelopes, implement interpolation + pre-attack
6. **Frontend speech modulation** — consume hints, modulate speaking render path
7. **Idle micro-behaviors** — frontend only, no backend changes
8. **Engagement drift** — frontend only, no backend changes

Steps 1-4 are backend, testable independently. Steps 5-8 are frontend, each independently valuable.

---

## What's NOT In Scope
- New OrbAnimation enum values (17 states are sufficient)
- Prompt engineering to increase gesture/emoji frequency
- Voice model changes (VoiceKnobs already exist)
- Mobile/touch adaptations
- Grid persistence across sessions
