# Orb Expression System — Gesture & Emoji Vocabulary Handoff

## What This Is

The orb's animation infrastructure is built: state machine (17 states), priority gating, ring renderer, performance orchestrator with voice+orb coordination. What's missing is the **expressive vocabulary** — the gestures and emoji that make Luna feel alive rather than mechanical.

This handoff covers:
1. Expanded gesture vocabulary with emotional granularity
2. Emoji → orb expression mapping (new system)
3. Transition choreography between states
4. Idle micro-behaviors (presence without stimulus)
5. Integration points with existing `performance_orchestrator.py`

## Existing Architecture (already built, don't rebuild)

```
performance_orchestrator.py  ← gesture detection, emotion mapping, voice+orb sync
├── orb_state.py             ← state machine, priority gate, WebSocket broadcast
│   └── orb_renderer.py      ← ring model, animation params, ring mutations
└── performance_state.py     ← emotion presets, voice knobs, orb knobs
```

The orchestrator calls `process_text()` which detects gestures, maps to emotion presets, updates both voice and orb. The renderer translates states into ring-level params. The frontend canvas consumes `to_dict()` output over WebSocket.

**This handoff modifies `performance_state.py` and `orb_state.py` primarily. Renderer changes are minimal.**

---

## 1. Expanded Gesture Vocabulary

### Current State
`GESTURE_PATTERNS` in `orb_state.py` has ~20 patterns mapping to basic animations. `GESTURE_TO_EMOTION` in `performance_state.py` has ~10 patterns mapping to 7 emotion presets.

### Problem
The vocabulary is too coarse. `*pulses*` and `*pulses warmly*` both map to the same PULSE animation with a brightness bump. There's no difference between curiosity and analytical attention, between gentle warmth and deep empathy, between playful and mischievous.

### Expanded Gesture Table

Add to `GESTURE_PATTERNS` in `orb_state.py`:

```python
GESTURE_PATTERNS_V2: Dict[str, OrbState] = {
    # ── Attention / Orientation ──
    r"\*perks up\*":          OrbState(OrbAnimation.PULSE, brightness=1.2, ...),
    r"\*leans in\*":          OrbState(OrbAnimation.GLOW, brightness=1.1, ...),
    r"\*focuses\*":           OrbState(OrbAnimation.IDLE, brightness=1.15, ...),
    r"\*concentrat(es?|ing)\*": OrbState(OrbAnimation.IDLE, brightness=1.1, ...),

    # ── Processing / Thinking ──
    r"\*thinks?\*":           OrbState(OrbAnimation.ORBIT, brightness=0.9, ...),
    r"\*considers?\*":        OrbState(OrbAnimation.ORBIT, brightness=0.85, ...),
    r"\*ponders?\*":          OrbState(OrbAnimation.DRIFT, brightness=0.8, ...),
    r"\*reflects?\*":         OrbState(OrbAnimation.GLOW, brightness=0.85, ...),

    # ── Warmth / Connection ──
    r"\*smiles?\*":           OrbState(OrbAnimation.GLOW, brightness=1.15, ...),
    r"\*beams?\*":            OrbState(OrbAnimation.GLOW, brightness=1.35, ...),
    r"\*nods?\*":             OrbState(OrbAnimation.PULSE, brightness=1.05, ...),
    r"\*hugs?\*":             OrbState(OrbAnimation.GLOW, brightness=1.3, ...),
    r"\*holds? space\*":      OrbState(OrbAnimation.IDLE, brightness=0.95, ...),

    # ── Playful / Mischief ──
    r"\*giggles?\*":          OrbState(OrbAnimation.SPIN_FAST, brightness=1.2, ...),
    r"\*bounces?\*":          OrbState(OrbAnimation.PULSE_FAST, brightness=1.25, ...),
    r"\*winks?\*":            OrbState(OrbAnimation.FLICKER, brightness=1.15, ...),
    r"\*dances?\*":           OrbState(OrbAnimation.SPIN_FAST, brightness=1.3, ...),

    # ── Surprise / Discovery ──
    r"\*gasps?\*":            OrbState(OrbAnimation.PULSE_FAST, brightness=1.4, ...),
    r"\*startl(es?|ed)\*":    OrbState(OrbAnimation.FLICKER, brightness=1.3, ...),

    # ── Uncertainty / Concern ──
    r"\*hesitat(es?|ing)\*":  OrbState(OrbAnimation.WOBBLE, brightness=0.85, ...),
    r"\*sighs?\*":            OrbState(OrbAnimation.DRIFT, brightness=0.8, ...),
    r"\*winces?\*":           OrbState(OrbAnimation.FLICKER, brightness=0.7, ...),

    # ── Energy ──
    r"\*vibrat(es?|ing)\*":   OrbState(OrbAnimation.PULSE_FAST, brightness=1.4, ...),
    r"\*sparks?\*":           OrbState(OrbAnimation.FLICKER, brightness=1.4, ...),
    r"\*lights? up\*":        OrbState(OrbAnimation.GLOW, brightness=1.45, ...),

    # ── Settling ──
    r"\*exhales?\*":          OrbState(OrbAnimation.DRIFT, brightness=0.85, ...),
    r"\*softens?\*":          OrbState(OrbAnimation.GLOW, brightness=0.9, ...),
}
```

**Implementation:** Merge into existing GESTURE_PATTERNS. Sort by pattern length descending so specific patterns match before generic.

---

## 2. Emoji → Orb Expression Mapping (NEW SYSTEM)

Emoji in Luna's responses drive the orb at GESTURE priority. Gesture markers win if both present. Emoji are NOT stripped from display text.

### Emoji Table

```python
EMOJI_PATTERNS: Dict[str, OrbState] = {
    "✨": GLOW / 1.3,    "💜": GLOW / purple / 1.2,
    "🫶": PULSE / 1.2,   "😊": GLOW / 1.15,
    "🤔": ORBIT / 0.9,   "💭": DRIFT / 0.85,
    "😏": SPIN / 1.1,    "🎉": PULSE_FAST / 1.35,
    "😮": PULSE_FAST / 1.3, "🤯": FLICKER / 1.45,
    "😔": DRIFT / 0.75,  "🥺": WOBBLE / 0.8,
    "⚡": PULSE_FAST / amber / 1.3, "💡": GLOW / yellow / 1.4,
    "🌙": DRIFT / indigo / 0.8, "🍃": DRIFT / emerald / 0.85,
    ...
}
```

Full table with all ~30 emoji mappings in the output file.

Detection: check after gesture patterns in `process_text_chunk()`. Only scan first 500 chars for performance.

### Emoji → Emotion (for voice coordination)

Maps emoji to same EmotionPreset system used by gestures, so voice knobs update too.

---

## 3. Transition Choreography

### TransitionEnvelope

```python
@dataclass
class TransitionEnvelope:
    pre_attack_ms: int = 200    # micro-contraction ("intake of breath")
    attack_ms: int = 300        # ramp to new state
    sustain_ms: int = -1        # hold (-1 = until next state)
    release_ms: int = 600       # ramp back to idle
    ease: str = "ease_out"
```

Each animation state gets its own envelope. Frontend interpolates between old→new params.

### "Intake of Breath"
Before any non-idle state: all rings contract 15% inward over 200ms. Then attack begins from contracted position. Creates feeling of Luna noticing before reacting.

---

## 4. Idle Micro-Behaviors (frontend only)

Random micro-events during IDLE state, 15-40 second intervals:

| Event | What | Duration |
|-------|------|----------|
| ring_shiver | one ring trembles | 400ms |
| drift_shift | float path changes direction | 600ms |
| core_flare | core brightens briefly | 500ms |
| ring_sync | two rings briefly align phase | 800ms |
| glow_bloom | ambient glow swells | 700ms |
| settle | all rings contract then relax | 600ms |

Backend doesn't know about these. Purely cosmetic presence.

---

## 5. File Map

| File | Action |
|------|--------|
| `orb_state.py` | Merge V2 gestures, add EMOJI_PATTERNS, update process_text_chunk() |
| `performance_state.py` | Add EMOJI_TO_EMOTION, TransitionEnvelope, envelopes per state |
| `performance_orchestrator.py` | Update _detect_emotion() for emoji fallback |
| `orb_renderer.py` | Add envelope to to_dict() output |
| Frontend `orb-canvas.js` | Transition interpolation, pre-attack, idle micro-behaviors |

Full implementation details and verification tasks in output file.
