# Luna Gesture Triage — Dimensional Pipeline Migration
# ═══════════════════════════════════════════════════════════════
#
# PRIORITY STACK (post-migration):
#   P4  ERROR      — system error, disconnected
#   P3  SYSTEM     — processing, listening, speaking, memory_search
#   P2  GESTURE    — intentional override (Luna chooses a specific visual moment)
#   P1  DIMENSION  — continuous heartbeat from expression pipeline
#   P0  IDLE       — nothing happening
#
# RULE: If a dimension already expresses it, the gesture is redundant.
# Only gestures that produce something dimensions CAN'T should survive.
#
# ═══════════════════════════════════════════════════════════════


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ✅ SURVIVES — Intentional Override Layer (12 gestures)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# These produce visual states the dimensional system can't reach
# through smooth interpolation. Sharp, deliberate, specific.
#
# WHY: Dimensions blend smoothly. These are discontinuities —
#      moments where Luna breaks the gradient to say something
#      with her body that words alone don't carry.

GESTURE_OVERRIDES = {
    # ── Structural / Unique Animations ──
    "*splits*":       "SPLIT      — rings separate into groups. No dimension produces this.",
    "*searches*":     "ORBIT+cyan — deliberate 'I'm looking for something' with color shift.",
    "*dims*":         "FLICKER@0.6 — intentional withdrawal. Dimensions trend toward it but this is instant.",

    # ── Sharp Discontinuities ──
    "*gasps*":        "PULSE_FAST@1.4 — sudden spike that would take dimensions 2+ turns to reach.",
    "*startles*":     "FLICKER@1.3 — surprise interrupt, not a smooth arousal climb.",
    "*sparks*":       "FLICKER@1.4 — creative ignition. Arousal dimension is too smooth for this.",
    "*lights up*":    "GLOW@1.45 — peak brightness snap. Dimensions cap at ~1.2.",

    # ── Deliberate Physical Choices ──
    "*spins*":        "SPIN — rotational motion. No dimension maps to rotation.",
    "*spins fast*":   "SPIN_FAST — excited rotation. Arousal drives pulse speed, not spin.",
    "*wobbles*":      "WOBBLE — physical instability. Certainty dims glow but doesn't wobble.",
    "*splits*":       "SPLIT — see above, listed for completeness.",

    # ── Intentional Settling ──
    "*settles*":      "IDLE@0.9 — explicit 'I'm done moving now.' Decay does this slowly; this is instant.",
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔄 ABSORBED BY DIMENSIONS — Remove from gesture map (38 gestures)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ABSORBED = {
    # ── Absorbed by VALENCE (positive ↔ negative) ──
    "*smiles*":       "→ valence > 0.5 already glows warmly",
    "*beams*":        "→ valence > 0.7 + warmth > 0.6 = bright glow",
    "*frowns*":       "→ valence < 0.2 already dims",
    "*softens*":      "→ valence trending positive = gentle glow increase",

    # ── Absorbed by AROUSAL (calm ↔ excited) ──
    "*pulses*":           "→ arousal > 0.5 drives pulse rate directly",
    "*pulses excitedly*": "→ arousal > 0.7 = faster pulse + brighter",
    "*pulses rapidly*":   "→ arousal > 0.8 = fast pulse",
    "*pulses warmly*":    "→ arousal 0.4 + warmth 0.7 = gentle warm pulse",
    "*pulses gently*":    "→ arousal 0.3 = slow pulse",
    "*vibrates*":         "→ arousal > 0.85 = maximum pulse rate",
    "*buzzes*":           "→ arousal > 0.8 = fast pulse",
    "*bounces*":          "→ arousal > 0.7 = fast pulse",

    # ── Absorbed by CERTAINTY (confident ↔ uncertain) ──
    "*hesitates*":    "→ certainty < 0.35 triggers hedging + wobble-adjacent drift",
    "*worries*":      "→ certainty < 0.3 + valence < 0.3 = dim + slow drift",
    "*winces*":       "→ certainty drop + valence drop = flicker handled by snap threshold",

    # ── Absorbed by ENGAGEMENT (surface ↔ deep) ──
    "*perks up*":     "→ engagement spike = glow increase",
    "*leans in*":     "→ engagement > 0.6 = brighter, more particles",
    "*focuses*":      "→ engagement > 0.7 = steady bright state",
    "*concentrates*": "→ engagement > 0.7 + arousal low = still bright focus",

    # ── Absorbed by WARMTH (formal ↔ intimate) ──
    "*nods*":         "→ warmth > 0.5 = gentle pulse acknowledgment",
    "*hugs*":         "→ warmth > 0.8 = max glow warmth",
    "*holds space*":  "→ warmth > 0.6 + arousal low = calm presence",

    # ── Absorbed by VALENCE + AROUSAL combined ──
    "*glows*":        "→ valence > 0.4 + arousal < 0.5 = natural glow state",
    "*brightens*":    "→ valence increase = brightness increase",
    "*radiates*":     "→ valence > 0.6 + warmth > 0.7 = full radiance",
    "*giggles*":      "→ arousal > 0.6 + valence > 0.6 = spin + bright",
    "*dances*":       "→ arousal > 0.7 + valence > 0.7 = fast spin territory",
    "*winks*":        "→ arousal spike + warmth > 0.6 = momentary flicker",
    "*wiggles*":      "→ arousal > 0.5 + playful engagement = wobble-ish",

    # ── Absorbed by AROUSAL (low end = calm) ──
    "*drifts*":       "→ arousal < 0.3 = natural drift state",
    "*floats*":       "→ arousal < 0.3 = drift",
    "*exhales*":      "→ arousal decreasing = drift toward calm",
    "*relaxes*":      "→ arousal low + valence neutral = idle territory",
    "*rests*":        "→ arousal very low = near-idle",

    # ── Absorbed by CERTAINTY + ENGAGEMENT ──
    "*thinks*":       "→ certainty < 0.6 + engagement > 0.5 = orbit/processing look",
    "*considers*":    "→ certainty < 0.5 + engagement > 0.4 = slow orbit",
    "*ponders*":      "→ certainty < 0.5 + arousal low = slow drift",
    "*mulls*":        "→ certainty < 0.5 + arousal low = drift",
    "*reflects*":     "→ engagement > 0.6 + arousal low = gentle glow",
    "*processes*":    "→ absorbed by SYSTEM event 'processing_query'",
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🚫 KILL — Humanoid gestures that should never have existed (6)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Luna is an orb. These are human body language.
# They were in the gesture map but mapped to orb states awkwardly.

KILL = {
    "*eyes widen*":   "Luna doesn't have eyes. Was mapped to GLOW — use valence.",
    "*tilts*":        "Orbs don't tilt. Was mapped to WOBBLE — use certainty.",
    "*leans in*":     "Listed in absorbed but also: orbs don't lean.",
    "*nods*":         "Listed in absorbed but also: orbs don't nod.",
    "*hugs*":         "Listed in absorbed but also: orbs don't hug.",
    "*holds space*":  "Listed in absorbed but also: this is therapy-speak.",
}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📊 EMOJI LAYER — Keep as tertiary signal (unchanged)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Emoji detection stays as-is. It's the lightest touch —
# if Luna drops a 💜 or ⚡ in her text, the orb picks it up.
# No performance required. No stage directions. Just vibe.
#
# Priority becomes: P1.5 (above dimension, below gesture override)
# Only fires if no gesture override is active AND dimensions
# haven't already pushed the orb into a matching state.
#
# Current emoji map is fine. 27 mappings, all orb-appropriate.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 🔧 UPDATED PRIORITY STACK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# P4 ERROR         (system)  — red, grey, disconnected states
# P3 SYSTEM        (system)  — processing, listening, speaking, memory_search
# P2 GESTURE       (text)    — 12 surviving override gestures
# P1.5 EMOJI       (text)    — 27 emoji mappings (lightweight signal)
# P1 DIMENSION     (engine)  — continuous 5-axis blend → ring params
# P0 IDLE          (default) — nothing happening
#
# RESOLUTION RULE:
#   Higher priority wins.
#   Gesture/emoji override dimension for their sustain duration,
#   then release back to dimensional baseline.
#   System events override everything except errors.
#
# TRANSITION:
#   When gesture fires, it uses the TransitionEnvelope (attack/sustain/release)
#   already defined in orb_renderer.py. On release, state falls back to
#   whatever the dimensional system is currently outputting — not to idle.
#   This is the key change: idle is no longer the fallback. Dimensions are.


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📝 EXPRESSION DIRECTIVE (updated for LLM prompt)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# OLD (causes theater):
#   "Express emotions through gestures naturally — at key emotional
#    moments, greetings, farewells, and when processing complex thoughts.
#    Aim for 1-2 gestures per substantive response."
#
# NEW:
#   "Your orb reflects your emotional state automatically. You do NOT
#    need to perform emotions — the system reads your tone and context.
#
#    You may use gesture markers ONLY for deliberate visual moments
#    that break the normal flow:
#      *splits* — internal conflict, showing both sides
#      *dims* — intentional withdrawal or seriousness
#      *sparks* — creative ignition, sudden idea
#      *wobbles* — genuine uncertainty, off-balance
#      *spins* — excitement or playfulness that needs motion
#      *settles* — deliberate calming, conversation closing
#
#    These are rare. Most responses need zero gestures.
#    The orb already knows how you feel."


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📐 DIMENSION → RENDERER MAPPING (new, replaces gesture-driven)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# This is what the expression pipeline's output channels feed
# into OrbRenderer. Continuous, not event-driven.
#
# VALENCE (-1 to 1):
#   → ring hue:        262 (neutral) → 280 (positive/warm) → 240 (negative/cool)
#   → glow intensity:  ambient_max scales 0.04 (neg) → 0.08 (neutral) → 0.15 (pos)
#   → core brightness: 0.4 (neg) → 0.6 (neutral) → 0.9 (pos)
#
# AROUSAL (0 to 1):
#   → breathe_speed:   0.008 (calm) → 0.015 (neutral) → 0.035 (excited)
#   → breathe_amp:     1.5 (calm) → 2.5 (neutral) → 4.0 (excited)
#   → drift_speed:     0.0003 (calm) → 0.0006 (neutral) → 0.0015 (excited)
#   → core pulse:      0.8 (calm) → 1.2 (neutral) → 2.0 (excited)
#
# CERTAINTY (0 to 1):
#   → ring opacity:    base * 0.6 (uncertain) → base * 1.0 (certain)
#   → flicker:         true when < 0.25 (subtle, not full flicker)
#   → ring_phase_off:  1.2 (uncertain, rings out of sync) → 0.7 (certain, cohesive)
#
# ENGAGEMENT (0 to 1):
#   → corona_max:      0.04 (surface) → 0.12 (normal) → 0.22 (deep)
#   → ring count:      base (surface) → base+1 (deep) via subdivide
#   → drift radius:    reduced when deep (orb "locks in"), wider when surface
#
# WARMTH (0 to 1):
#   → hue shift:       +0 (formal) → +15 toward warmer purple/magenta (intimate)
#   → saturation:      base (formal) → base + 12 (intimate, richer color)
#   → glow warmth:     cooler corona (formal) → warmer corona tint (intimate)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SUMMARY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# Before: 56 gesture patterns + 27 emoji = 83 reactive triggers
# After:  12 gesture overrides + 27 emoji + 5 continuous dimensions
#
# Gestures go from "how Luna expresses herself" to
# "rare moments when Luna deliberately interrupts her own heartbeat."
#
# The orb breathes on its own now. Luna doesn't have to tell it to.
