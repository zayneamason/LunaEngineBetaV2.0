# HANDOFF: Performance Layer — Voice + Orb Unified Control System

**Date:** 2025-01-27
**From:** Architecture Session (Claude.ai)
**To:** Claude Code
**Priority:** High — Builds on Piper fix, adds expression controls

---

## Overview

This handoff implements a **unified performance system** that coordinates Luna's voice and orb. Instead of creating a parallel `SkeletonGenerator`, we **extend existing architecture** (`OrbStateManager`, `TTSManager`) to emit coordinated voice+visual parameters.

### Goals
1. Wire voice modulation (pitch, rate, expressiveness) to Piper binary
2. Add pre-roll timing so orb reacts before voice starts
3. Create `/voice-tuning` UI for real-time voice adjustment
4. Create `/orb-settings` UI for visual customization
5. Add feedback display showing current performance state

---

## Architecture: Extend, Don't Duplicate

### Current Flow (Broken)
```
Response → OrbStateManager (visual only) → WebSocket
         → TTSManager (no modulation) → Apple fallback
```

### New Flow (Unified)
```
Response → PerformanceOrchestrator ─┬─→ OrbStateManager (visual + pre-roll)
                                    │      → WebSocket → Frontend orb
                                    │
                                    └─→ TTSManager (with voice knobs)
                                           → PiperTTS (binary + params)
                                           → Audio playback
```

---

## Part 1: PerformanceState Schema

Extend the existing `OrbState` to include voice parameters:

### File: `src/luna/services/performance_state.py` (NEW)

```python
"""
Unified Performance State for coordinated voice + orb behavior.

This extends OrbState to include voice modulation parameters,
enabling synchronized audiovisual expression.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum
from .orb_state import OrbAnimation


class EmotionPreset(Enum):
    """Pre-configured emotion → performance mappings."""
    NEUTRAL = "neutral"
    EXCITED = "excited"
    THOUGHTFUL = "thoughtful"
    WARM = "warm"
    PLAYFUL = "playful"
    CONCERNED = "concerned"
    CURIOUS = "curious"


@dataclass
class VoiceKnobs:
    """Voice modulation parameters for TTS."""
    # Piper native controls
    length_scale: float = 1.0      # Speed: 0.5 (2x fast) → 2.0 (half speed)
    noise_scale: float = 0.667     # Expressiveness: 0.0 (monotone) → 1.0 (expressive)
    noise_w: float = 0.8           # Rhythm variation: 0.0 (robotic) → 1.0 (natural)
    sentence_silence: float = 0.2  # Pause between sentences (seconds)
    
    # Post-processing (Phase 2)
    pitch_shift: float = 0.0       # Semitones (+/- 12)
    
    def to_piper_args(self) -> list:
        """Convert to Piper CLI arguments."""
        args = [
            "--length_scale", str(self.length_scale),
            "--noise_scale", str(self.noise_scale),
            "--noise_w", str(self.noise_w),
        ]
        if self.sentence_silence > 0:
            args.extend(["--sentence_silence", str(self.sentence_silence)])
        return args


@dataclass
class OrbKnobs:
    """Orb visual parameters."""
    animation: str = "idle"
    color: Optional[str] = None      # Hex color override
    brightness: float = 1.0          # 0.0 → 2.0
    size_scale: float = 1.0          # 0.5 → 2.0
    # Fairy float parameters
    float_amplitude_x: float = 8.0   # Pixels
    float_amplitude_y: float = 12.0
    float_speed_x: float = 0.0015    # Radians per ms
    float_speed_y: float = 0.0023


@dataclass
class PerformanceState:
    """
    Complete performance state combining voice and visual.
    
    Used by:
    - PerformanceOrchestrator to generate from gestures
    - TTSManager to modulate voice
    - OrbStateManager to control visuals
    - Frontend UIs to display/adjust
    """
    voice: VoiceKnobs = field(default_factory=VoiceKnobs)
    orb: OrbKnobs = field(default_factory=OrbKnobs)
    
    # Timing
    pre_roll_ms: int = 300           # Orb starts this many ms before voice
    post_roll_ms: int = 800          # Orb settles this many ms after voice ends
    
    # Metadata
    emotion: Optional[EmotionPreset] = None
    gesture_source: Optional[str] = None  # The marker that triggered this
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for API/WebSocket."""
        return {
            "voice": {
                "length_scale": self.voice.length_scale,
                "noise_scale": self.voice.noise_scale,
                "noise_w": self.voice.noise_w,
                "sentence_silence": self.voice.sentence_silence,
                "pitch_shift": self.voice.pitch_shift,
            },
            "orb": {
                "animation": self.orb.animation,
                "color": self.orb.color,
                "brightness": self.orb.brightness,
                "size_scale": self.orb.size_scale,
                "float_amplitude_x": self.orb.float_amplitude_x,
                "float_amplitude_y": self.orb.float_amplitude_y,
                "float_speed_x": self.orb.float_speed_x,
                "float_speed_y": self.orb.float_speed_y,
            },
            "timing": {
                "pre_roll_ms": self.pre_roll_ms,
                "post_roll_ms": self.post_roll_ms,
            },
            "emotion": self.emotion.value if self.emotion else None,
            "gesture_source": self.gesture_source,
        }


# === EMOTION PRESETS ===
# These map emotions to coordinated voice+orb settings

EMOTION_PRESETS: Dict[EmotionPreset, PerformanceState] = {
    EmotionPreset.NEUTRAL: PerformanceState(
        voice=VoiceKnobs(length_scale=1.0, noise_scale=0.667, noise_w=0.8),
        orb=OrbKnobs(animation="idle", brightness=1.0),
    ),
    EmotionPreset.EXCITED: PerformanceState(
        voice=VoiceKnobs(length_scale=0.85, noise_scale=0.9, noise_w=0.95),
        orb=OrbKnobs(animation="pulse_fast", color="#FFD700", brightness=1.3,
                     float_amplitude_x=15, float_amplitude_y=20, float_speed_x=0.003),
        pre_roll_ms=200,
    ),
    EmotionPreset.THOUGHTFUL: PerformanceState(
        voice=VoiceKnobs(length_scale=1.2, noise_scale=0.4, noise_w=0.6, sentence_silence=0.4),
        orb=OrbKnobs(animation="glow", color="#A8DADC", brightness=0.8,
                     float_amplitude_x=5, float_amplitude_y=8, float_speed_x=0.001),
        pre_roll_ms=500,
    ),
    EmotionPreset.WARM: PerformanceState(
        voice=VoiceKnobs(length_scale=0.95, noise_scale=0.7, noise_w=0.85),
        orb=OrbKnobs(animation="pulse", color="#FFB7B2", brightness=1.1,
                     float_amplitude_x=10, float_amplitude_y=14),
        pre_roll_ms=300,
    ),
    EmotionPreset.PLAYFUL: PerformanceState(
        voice=VoiceKnobs(length_scale=0.9, noise_scale=0.85, noise_w=0.9),
        orb=OrbKnobs(animation="spin", color="#C4B5FD", brightness=1.2,
                     float_amplitude_x=12, float_amplitude_y=18, float_speed_x=0.0025),
        pre_roll_ms=250,
    ),
    EmotionPreset.CONCERNED: PerformanceState(
        voice=VoiceKnobs(length_scale=1.1, noise_scale=0.5, noise_w=0.7),
        orb=OrbKnobs(animation="wobble", color="#F4A261", brightness=0.9),
        pre_roll_ms=400,
    ),
    EmotionPreset.CURIOUS: PerformanceState(
        voice=VoiceKnobs(length_scale=1.05, noise_scale=0.75, noise_w=0.8),
        orb=OrbKnobs(animation="orbit", color="#06B6D4", brightness=1.1),
        pre_roll_ms=350,
    ),
}


# === GESTURE → EMOTION MAPPING ===
# Regex patterns that map to emotions (extends existing OrbStateManager patterns)

GESTURE_TO_EMOTION: Dict[str, EmotionPreset] = {
    r"\*excitedly\*|\*excited\*|\*enthusiastically\*": EmotionPreset.EXCITED,
    r"\*thinks?\*|\*contemplat(es?|ive)\*|\*ponders?\*": EmotionPreset.THOUGHTFUL,
    r"\*warmly\*|\*gently\*|\*softly\*": EmotionPreset.WARM,
    r"\*playfully\*|\*mischievously\*|\*giggles?\*": EmotionPreset.PLAYFUL,
    r"\*concerned\*|\*worriedly\*|\*carefully\*": EmotionPreset.CONCERNED,
    r"\*curiously\*|\*tilts?\*|\*wonders?\*": EmotionPreset.CURIOUS,
    r"\*pulses? warmly\*": EmotionPreset.WARM,
    r"\*spins? playfully\*": EmotionPreset.PLAYFUL,
    r"\*pulses? excitedly\*": EmotionPreset.EXCITED,
}
```

---

## Part 2: Performance Orchestrator

Extends `OrbStateManager` to emit unified performance states:

### File: `src/luna/services/performance_orchestrator.py` (NEW)

```python
"""
Performance Orchestrator — Coordinates voice + orb from gestures.

This wraps OrbStateManager and adds voice modulation,
keeping the systems unified rather than duplicated.
"""
import re
import logging
from typing import Optional, Callable, List
from dataclasses import replace

from .performance_state import (
    PerformanceState, VoiceKnobs, OrbKnobs,
    EMOTION_PRESETS, GESTURE_TO_EMOTION, EmotionPreset
)
from .orb_state import OrbStateManager, OrbAnimation

logger = logging.getLogger(__name__)


class PerformanceOrchestrator:
    """
    Central coordinator for Luna's audiovisual performance.
    
    Responsibilities:
    - Parse gestures from text
    - Map to emotion presets
    - Emit coordinated voice + orb parameters
    - Handle manual overrides from UI
    - Manage pre-roll timing
    """
    
    def __init__(self, orb_manager: OrbStateManager = None):
        self._orb_manager = orb_manager or OrbStateManager()
        self._current_state = PerformanceState()
        self._subscribers: List[Callable[[PerformanceState], None]] = []
        
        # Manual overrides (from UI sliders)
        self._voice_override: Optional[VoiceKnobs] = None
        self._orb_override: Optional[OrbKnobs] = None
        self._override_locked = False  # Lock overrides during speech
    
    @property
    def current_state(self) -> PerformanceState:
        return self._current_state
    
    def subscribe(self, callback: Callable[[PerformanceState], None]) -> Callable:
        """Subscribe to state changes. Returns unsubscribe function."""
        self._subscribers.append(callback)
        return lambda: self._subscribers.remove(callback)
    
    def _notify(self):
        """Notify all subscribers of state change."""
        for callback in self._subscribers:
            try:
                callback(self._current_state)
            except Exception as e:
                logger.error(f"Subscriber error: {e}")
    
    def process_text(self, text: str) -> tuple[str, PerformanceState]:
        """
        Process Luna's response text.
        
        Returns:
            (clean_text, performance_state) — Text for TTS and state for orb+voice
        """
        # 1. Detect emotion from gestures
        emotion = self._detect_emotion(text)
        
        # 2. Get base preset (or neutral)
        if emotion:
            base_state = EMOTION_PRESETS.get(emotion, PerformanceState())
            base_state = replace(base_state, emotion=emotion)
        else:
            base_state = PerformanceState(emotion=EmotionPreset.NEUTRAL)
        
        # 3. Apply manual overrides if set
        if self._voice_override and not self._override_locked:
            base_state = replace(base_state, voice=self._voice_override)
        if self._orb_override and not self._override_locked:
            base_state = replace(base_state, orb=self._orb_override)
        
        # 4. Clean text for TTS
        clean_text = self._clean_for_tts(text)
        
        # 5. Find source gesture for metadata
        gesture_match = self._find_gesture(text)
        if gesture_match:
            base_state = replace(base_state, gesture_source=gesture_match)
        
        # 6. Update current state and notify
        self._current_state = base_state
        self._notify()
        
        # 7. Also update orb manager for WebSocket broadcast
        self._update_orb_manager(base_state)
        
        return clean_text, base_state
    
    def _detect_emotion(self, text: str) -> Optional[EmotionPreset]:
        """Match text against gesture patterns to find emotion."""
        for pattern, emotion in GESTURE_TO_EMOTION.items():
            if re.search(pattern, text, re.IGNORECASE):
                logger.debug(f"Detected emotion {emotion} from pattern {pattern}")
                return emotion
        return None
    
    def _find_gesture(self, text: str) -> Optional[str]:
        """Extract the actual gesture marker from text."""
        match = re.search(r'\*[^*]+\*', text)
        return match.group(0) if match else None
    
    def _clean_for_tts(self, text: str) -> str:
        """Remove gesture markers for TTS."""
        # Remove *gesture* markers
        clean = re.sub(r'\*[^*]+\*', '', text)
        # Normalize whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()
        return clean
    
    def _update_orb_manager(self, state: PerformanceState):
        """Sync orb manager with performance state."""
        if self._orb_manager:
            # Map to OrbAnimation enum
            try:
                anim = OrbAnimation(state.orb.animation.upper())
            except ValueError:
                anim = OrbAnimation.IDLE
            
            self._orb_manager.set_animation(
                anim,
                color=state.orb.color,
                brightness=state.orb.brightness
            )
    
    # === MANUAL OVERRIDE API (for UI controls) ===
    
    def set_voice_override(self, knobs: VoiceKnobs):
        """Set manual voice override from UI."""
        self._voice_override = knobs
        self._current_state = replace(self._current_state, voice=knobs)
        self._notify()
        logger.info(f"Voice override set: {knobs}")
    
    def set_orb_override(self, knobs: OrbKnobs):
        """Set manual orb override from UI."""
        self._orb_override = knobs
        self._current_state = replace(self._current_state, orb=knobs)
        self._notify()
        self._update_orb_manager(self._current_state)
        logger.info(f"Orb override set: {knobs}")
    
    def clear_overrides(self):
        """Clear all manual overrides."""
        self._voice_override = None
        self._orb_override = None
        logger.info("Overrides cleared")
    
    def lock_overrides(self, locked: bool = True):
        """Lock overrides during speech to prevent jank."""
        self._override_locked = locked
    
    def get_feedback(self) -> dict:
        """Get current state for feedback UI."""
        return {
            "state": self._current_state.to_dict(),
            "has_voice_override": self._voice_override is not None,
            "has_orb_override": self._orb_override is not None,
            "override_locked": self._override_locked,
        }
```

---

## Part 3: Slash Commands

### Commands to Implement

| Command | Action | UI |
|---------|--------|-----|
| `/voice-tuning` | Open voice control panel | Sliders for speed, expressiveness, rhythm, pause |
| `/orb-settings` | Open orb visual panel | Sliders + color picker for animation, size, brightness |
| `/performance` | Show current performance state | Read-only feedback display |
| `/emotion <name>` | Manually set emotion preset | Quick switch (excited, thoughtful, warm, etc.) |
| `/reset-performance` | Clear all overrides | Return to auto-detect mode |

### File: `src/luna/api/server.py` — Add endpoints

```python
# Add these endpoints to server.py

from luna.services.performance_state import VoiceKnobs, OrbKnobs, EMOTION_PRESETS, EmotionPreset
from luna.services.performance_orchestrator import PerformanceOrchestrator

# Global instance (initialize with orb manager)
_performance_orchestrator: Optional[PerformanceOrchestrator] = None

# --- SLASH COMMAND ENDPOINTS ---

@app.get("/slash/voice-tuning")
async def slash_voice_tuning():
    """Return voice tuning panel data."""
    if not _performance_orchestrator:
        return {"command": "/voice-tuning", "success": False, "error": "Not initialized"}
    
    state = _performance_orchestrator.current_state
    return {
        "command": "/voice-tuning",
        "success": True,
        "data": {
            "current": {
                "length_scale": state.voice.length_scale,
                "noise_scale": state.voice.noise_scale,
                "noise_w": state.voice.noise_w,
                "sentence_silence": state.voice.sentence_silence,
                "pitch_shift": state.voice.pitch_shift,
            },
            "ranges": {
                "length_scale": {"min": 0.5, "max": 2.0, "step": 0.05, "label": "Speed", "inverted": True},
                "noise_scale": {"min": 0.0, "max": 1.0, "step": 0.05, "label": "Expressiveness"},
                "noise_w": {"min": 0.0, "max": 1.0, "step": 0.05, "label": "Rhythm Variation"},
                "sentence_silence": {"min": 0.0, "max": 1.0, "step": 0.05, "label": "Sentence Pause"},
                "pitch_shift": {"min": -12, "max": 12, "step": 0.5, "label": "Pitch (semitones)"},
            },
            "presets": ["neutral", "excited", "thoughtful", "warm", "playful"],
        },
        "formatted": "**Voice Tuning**\nUse sliders to adjust Luna's voice characteristics.",
        "ui_type": "voice-tuning-panel",
    }


@app.post("/slash/voice-tuning")
async def update_voice_tuning(request: dict):
    """Update voice settings from UI."""
    if not _performance_orchestrator:
        return {"success": False, "error": "Not initialized"}
    
    knobs = VoiceKnobs(
        length_scale=request.get("length_scale", 1.0),
        noise_scale=request.get("noise_scale", 0.667),
        noise_w=request.get("noise_w", 0.8),
        sentence_silence=request.get("sentence_silence", 0.2),
        pitch_shift=request.get("pitch_shift", 0.0),
    )
    _performance_orchestrator.set_voice_override(knobs)
    return {"success": True, "message": "Voice settings updated"}


@app.get("/slash/orb-settings")
async def slash_orb_settings():
    """Return orb settings panel data."""
    if not _performance_orchestrator:
        return {"command": "/orb-settings", "success": False, "error": "Not initialized"}
    
    state = _performance_orchestrator.current_state
    return {
        "command": "/orb-settings",
        "success": True,
        "data": {
            "current": {
                "animation": state.orb.animation,
                "color": state.orb.color or "#a78bfa",
                "brightness": state.orb.brightness,
                "size_scale": state.orb.size_scale,
                "float_amplitude_x": state.orb.float_amplitude_x,
                "float_amplitude_y": state.orb.float_amplitude_y,
                "float_speed_x": state.orb.float_speed_x,
                "float_speed_y": state.orb.float_speed_y,
            },
            "ranges": {
                "brightness": {"min": 0.2, "max": 2.0, "step": 0.1, "label": "Brightness"},
                "size_scale": {"min": 0.5, "max": 2.0, "step": 0.1, "label": "Size"},
                "float_amplitude_x": {"min": 0, "max": 30, "step": 1, "label": "Drift X"},
                "float_amplitude_y": {"min": 0, "max": 30, "step": 1, "label": "Drift Y"},
                "float_speed_x": {"min": 0.0005, "max": 0.005, "step": 0.0005, "label": "Float Speed X"},
                "float_speed_y": {"min": 0.0005, "max": 0.005, "step": 0.0005, "label": "Float Speed Y"},
            },
            "animations": ["idle", "pulse", "pulse_fast", "spin", "spin_fast", 
                          "glow", "wobble", "drift", "orbit", "flicker"],
            "color_presets": {
                "violet": "#a78bfa",
                "gold": "#FFD700",
                "coral": "#FFB7B2",
                "cyan": "#06B6D4",
                "teal": "#A8DADC",
                "orange": "#F4A261",
            },
        },
        "formatted": "**Orb Settings**\nCustomize Luna's visual appearance.",
        "ui_type": "orb-settings-panel",
    }


@app.post("/slash/orb-settings")
async def update_orb_settings(request: dict):
    """Update orb settings from UI."""
    if not _performance_orchestrator:
        return {"success": False, "error": "Not initialized"}
    
    knobs = OrbKnobs(
        animation=request.get("animation", "idle"),
        color=request.get("color"),
        brightness=request.get("brightness", 1.0),
        size_scale=request.get("size_scale", 1.0),
        float_amplitude_x=request.get("float_amplitude_x", 8.0),
        float_amplitude_y=request.get("float_amplitude_y", 12.0),
        float_speed_x=request.get("float_speed_x", 0.0015),
        float_speed_y=request.get("float_speed_y", 0.0023),
    )
    _performance_orchestrator.set_orb_override(knobs)
    return {"success": True, "message": "Orb settings updated"}


@app.get("/slash/performance")
async def slash_performance():
    """Return current performance state (feedback display)."""
    if not _performance_orchestrator:
        return {"command": "/performance", "success": False, "error": "Not initialized"}
    
    feedback = _performance_orchestrator.get_feedback()
    state = feedback["state"]
    
    formatted = f"""**Performance State**

**Emotion:** {state.get('emotion', 'neutral')}
**Gesture:** {state.get('gesture_source', 'none')}

**Voice:**
  Speed: {state['voice']['length_scale']}x
  Expressiveness: {state['voice']['noise_scale']}
  Rhythm: {state['voice']['noise_w']}

**Orb:**
  Animation: {state['orb']['animation']}
  Brightness: {state['orb']['brightness']}
  Color: {state['orb']['color'] or 'default'}

**Overrides:** {'Voice ' if feedback['has_voice_override'] else ''}{'Orb ' if feedback['has_orb_override'] else ''}{'(none)' if not feedback['has_voice_override'] and not feedback['has_orb_override'] else ''}
"""
    
    return {
        "command": "/performance",
        "success": True,
        "data": feedback,
        "formatted": formatted,
        "ui_type": "performance-feedback",
    }


@app.get("/slash/emotion/{emotion_name}")
async def slash_emotion(emotion_name: str):
    """Manually set emotion preset."""
    if not _performance_orchestrator:
        return {"command": f"/emotion {emotion_name}", "success": False, "error": "Not initialized"}
    
    try:
        emotion = EmotionPreset(emotion_name.lower())
        preset = EMOTION_PRESETS.get(emotion)
        if preset:
            _performance_orchestrator.set_voice_override(preset.voice)
            _performance_orchestrator.set_orb_override(preset.orb)
            return {
                "command": f"/emotion {emotion_name}",
                "success": True,
                "formatted": f"**Emotion set to {emotion_name}**\nVoice and orb adjusted.",
            }
    except ValueError:
        pass
    
    valid = ", ".join([e.value for e in EmotionPreset])
    return {
        "command": f"/emotion {emotion_name}",
        "success": False,
        "formatted": f"**Unknown emotion:** {emotion_name}\nValid: {valid}",
    }


@app.post("/slash/reset-performance")
async def slash_reset_performance():
    """Clear all overrides."""
    if not _performance_orchestrator:
        return {"command": "/reset-performance", "success": False, "error": "Not initialized"}
    
    _performance_orchestrator.clear_overrides()
    return {
        "command": "/reset-performance",
        "success": True,
        "formatted": "**Performance reset**\nReturned to auto-detect mode.",
    }
```

---

## Part 4: Frontend UI Components

### 4A: Voice Tuning Panel

**File:** `frontend/src/components/VoiceTuningPanel.jsx`

```jsx
import React, { useState, useEffect } from 'react';

const SLIDER_STYLE = {
  width: '100%',
  accentColor: '#a78bfa',
};

export function VoiceTuningPanel({ data, onUpdate, onClose }) {
  const [values, setValues] = useState(data?.current || {});
  const ranges = data?.ranges || {};
  
  useEffect(() => {
    if (data?.current) setValues(data.current);
  }, [data]);
  
  const handleChange = (key, value) => {
    const newValues = { ...values, [key]: parseFloat(value) };
    setValues(newValues);
    onUpdate(newValues);
  };
  
  const applyPreset = async (presetName) => {
    const res = await fetch(`/slash/emotion/${presetName}`);
    const newData = await fetch('/slash/voice-tuning').then(r => r.json());
    if (newData.data?.current) setValues(newData.data.current);
  };
  
  return (
    <div className="tuning-panel glass-card" style={{ padding: '1rem', minWidth: 300 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <h3 style={{ margin: 0 }}>🎤 Voice Tuning</h3>
        <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>✕</button>
      </div>
      
      {/* Presets */}
      <div style={{ marginBottom: '1rem' }}>
        <label style={{ fontSize: '0.8rem', opacity: 0.7 }}>Quick Presets</label>
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.25rem' }}>
          {data?.presets?.map(p => (
            <button 
              key={p} 
              onClick={() => applyPreset(p)}
              style={{ 
                padding: '0.25rem 0.5rem', 
                borderRadius: '4px',
                border: '1px solid rgba(255,255,255,0.2)',
                background: 'rgba(255,255,255,0.1)',
                color: 'inherit',
                cursor: 'pointer',
                fontSize: '0.75rem',
              }}
            >
              {p}
            </button>
          ))}
        </div>
      </div>
      
      {/* Sliders */}
      {Object.entries(ranges).map(([key, config]) => (
        <div key={key} style={{ marginBottom: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
            <label>{config.label}</label>
            <span style={{ opacity: 0.7 }}>{values[key]?.toFixed(2)}</span>
          </div>
          <input
            type="range"
            min={config.min}
            max={config.max}
            step={config.step}
            value={values[key] || config.min}
            onChange={(e) => handleChange(key, e.target.value)}
            style={SLIDER_STYLE}
          />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.65rem', opacity: 0.5 }}>
            <span>{config.inverted ? 'Fast' : config.min}</span>
            <span>{config.inverted ? 'Slow' : config.max}</span>
          </div>
        </div>
      ))}
      
      {/* Test button */}
      <button 
        onClick={() => fetch('/voice/speak', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: "Testing voice settings. How does this sound?" })
        })}
        style={{
          width: '100%',
          padding: '0.5rem',
          borderRadius: '6px',
          border: 'none',
          background: '#a78bfa',
          color: 'white',
          cursor: 'pointer',
        }}
      >
        🔊 Test Voice
      </button>
    </div>
  );
}
```

### 4B: Orb Settings Panel

**File:** `frontend/src/components/OrbSettingsPanel.jsx`

```jsx
import React, { useState, useEffect } from 'react';

export function OrbSettingsPanel({ data, onUpdate, onClose, orbRef }) {
  const [values, setValues] = useState(data?.current || {});
  const ranges = data?.ranges || {};
  const animations = data?.animations || [];
  const colorPresets = data?.color_presets || {};
  
  useEffect(() => {
    if (data?.current) setValues(data.current);
  }, [data]);
  
  const handleChange = (key, value) => {
    const parsed = typeof value === 'string' && !isNaN(parseFloat(value)) 
      ? parseFloat(value) 
      : value;
    const newValues = { ...values, [key]: parsed };
    setValues(newValues);
    onUpdate(newValues);
  };
  
  return (
    <div className="settings-panel glass-card" style={{ padding: '1rem', minWidth: 300 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <h3 style={{ margin: 0 }}>🟣 Orb Settings</h3>
        <button onClick={onClose} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>✕</button>
      </div>
      
      {/* Animation selector */}
      <div style={{ marginBottom: '1rem' }}>
        <label style={{ fontSize: '0.8rem', opacity: 0.7 }}>Animation</label>
        <select 
          value={values.animation || 'idle'}
          onChange={(e) => handleChange('animation', e.target.value)}
          style={{
            width: '100%',
            padding: '0.5rem',
            borderRadius: '4px',
            border: '1px solid rgba(255,255,255,0.2)',
            background: 'rgba(0,0,0,0.3)',
            color: 'inherit',
            marginTop: '0.25rem',
          }}
        >
          {animations.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
      </div>
      
      {/* Color presets */}
      <div style={{ marginBottom: '1rem' }}>
        <label style={{ fontSize: '0.8rem', opacity: 0.7 }}>Color</label>
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.25rem', flexWrap: 'wrap' }}>
          {Object.entries(colorPresets).map(([name, hex]) => (
            <button
              key={name}
              onClick={() => handleChange('color', hex)}
              title={name}
              style={{
                width: 28,
                height: 28,
                borderRadius: '50%',
                border: values.color === hex ? '2px solid white' : '2px solid transparent',
                background: hex,
                cursor: 'pointer',
              }}
            />
          ))}
          <input
            type="color"
            value={values.color || '#a78bfa'}
            onChange={(e) => handleChange('color', e.target.value)}
            style={{ width: 28, height: 28, border: 'none', borderRadius: '50%', cursor: 'pointer' }}
          />
        </div>
      </div>
      
      {/* Sliders */}
      {Object.entries(ranges).map(([key, config]) => (
        <div key={key} style={{ marginBottom: '0.75rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem' }}>
            <label>{config.label}</label>
            <span style={{ opacity: 0.7 }}>{values[key]?.toFixed?.(3) || values[key]}</span>
          </div>
          <input
            type="range"
            min={config.min}
            max={config.max}
            step={config.step}
            value={values[key] || config.min}
            onChange={(e) => handleChange(key, e.target.value)}
            style={{ width: '100%', accentColor: values.color || '#a78bfa' }}
          />
        </div>
      ))}
      
      {/* Preview text */}
      <div style={{ fontSize: '0.7rem', opacity: 0.5, textAlign: 'center', marginTop: '0.5rem' }}>
        Changes apply in real-time
      </div>
    </div>
  );
}
```

### 4C: Update ChatPanel for UI Panels

**File:** `frontend/src/components/ChatPanel.jsx` — Add panel rendering

```jsx
// Add to ChatPanel.jsx imports
import { VoiceTuningPanel } from './VoiceTuningPanel';
import { OrbSettingsPanel } from './OrbSettingsPanel';

// Add state for panels
const [activePanel, setActivePanel] = useState(null); // 'voice-tuning' | 'orb-settings' | null
const [panelData, setPanelData] = useState(null);

// Handle slash command responses that require UI
const handleSlashResponse = (response) => {
  if (response.ui_type === 'voice-tuning-panel') {
    setPanelData(response.data);
    setActivePanel('voice-tuning');
  } else if (response.ui_type === 'orb-settings-panel') {
    setPanelData(response.data);
    setActivePanel('orb-settings');
  } else {
    // Regular message display
    // ... existing logic
  }
};

// Panel update handlers
const handleVoiceUpdate = async (values) => {
  await fetch('/slash/voice-tuning', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(values),
  });
};

const handleOrbUpdate = async (values) => {
  await fetch('/slash/orb-settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(values),
  });
};

// Render panels (add to JSX)
{activePanel === 'voice-tuning' && (
  <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 1000 }}>
    <VoiceTuningPanel 
      data={panelData} 
      onUpdate={handleVoiceUpdate}
      onClose={() => setActivePanel(null)}
    />
  </div>
)}

{activePanel === 'orb-settings' && (
  <div style={{ position: 'fixed', top: '50%', left: '50%', transform: 'translate(-50%, -50%)', zIndex: 1000 }}>
    <OrbSettingsPanel 
      data={panelData} 
      onUpdate={handleOrbUpdate}
      onClose={() => setActivePanel(null)}
    />
  </div>
)}
```

### 4D: Update useChat.js for New Commands

```javascript
// Add to SLASH_COMMANDS in useChat.js
{ command: '/voice-tuning', description: 'Open voice tuning panel', endpoint: '/slash/voice-tuning' },
{ command: '/orb-settings', description: 'Open orb visual settings', endpoint: '/slash/orb-settings' },
{ command: '/performance', description: 'Show current performance state', endpoint: '/slash/performance' },
{ command: '/emotion', description: 'Set emotion (excited, warm, thoughtful...)', hasArg: true },
{ command: '/reset-performance', description: 'Reset to auto-detect mode', endpoint: '/slash/reset-performance', method: 'POST' },
```

---

## Part 5: Wire Voice Knobs to PiperTTS

Update the Piper handoff to accept voice parameters:

### File: `src/voice/tts/piper.py` — Updated synthesize()

```python
async def synthesize(
    self, 
    text: str, 
    voice_id: Optional[str] = None,
    voice_knobs: Optional[VoiceKnobs] = None,  # NEW
) -> AudioBuffer:
    """
    Synthesize text to audio using Piper binary.
    
    Args:
        text: Text to synthesize (should already be preprocessed)
        voice_id: Optional voice override
        voice_knobs: Optional voice modulation parameters
        
    Returns:
        AudioBuffer with WAV audio data
    """
    if not self._available:
        logger.error("PiperTTS not available")
        return AudioBuffer(data=b"", sample_rate=22050)
    
    if not text.strip():
        return AudioBuffer(data=b"", sample_rate=22050)
    
    try:
        # Build command with base args
        cmd = [
            str(self._binary_path),
            "--model", str(self._model_path),
            "--output_raw",
        ]
        
        # Add voice knobs if provided
        if voice_knobs:
            cmd.extend(voice_knobs.to_piper_args())
        else:
            # Defaults
            cmd.extend([
                "--length_scale", str(self.speed),
                "--noise_scale", "0.667",
                "--noise_w", "0.8",
            ])
        
        # ... rest of implementation
```

### File: `src/voice/tts/manager.py` — Pass knobs through

```python
async def synthesize(
    self,
    text: str,
    voice_id: Optional[str] = None,
    voice_knobs: Optional[VoiceKnobs] = None,  # NEW
    skip_preprocessing: bool = False,
) -> AudioBuffer:
    """Synthesize text with optional voice modulation."""
    
    # Preprocess
    if not skip_preprocessing:
        text = self._preprocessor.preprocess(text)
    
    # Get provider and synthesize with knobs
    provider = self._get_provider()
    return await provider.synthesize(text, voice_id, voice_knobs)
```

---

## Part 6: Pre-Roll Timing Integration

Add pre-roll to the response flow in server.py:

```python
async def stream_response(text: str):
    """Stream response with pre-roll timing."""
    global _performance_orchestrator, _orb_state_manager
    
    # 1. Process text through orchestrator
    clean_text, perf_state = _performance_orchestrator.process_text(text)
    
    # 2. Send pre-roll to orb IMMEDIATELY
    await _broadcast_orb_state()  # Orb starts animating now
    
    # 3. Wait pre-roll duration (orb animates while TTS loads)
    await asyncio.sleep(perf_state.pre_roll_ms / 1000)
    
    # 4. Start TTS with voice knobs
    await _voice_backend.speak(clean_text, voice_knobs=perf_state.voice)
    
    # 5. After speech, post-roll back to idle
    await asyncio.sleep(perf_state.post_roll_ms / 1000)
    _orb_state_manager.set_idle()
```

---

## Testing Checklist

- [ ] `/voice-tuning` opens panel with sliders
- [ ] Slider changes update voice in real-time
- [ ] "Test Voice" button speaks with current settings
- [ ] `/orb-settings` opens panel with color picker + sliders
- [ ] Orb updates in real-time when settings change
- [ ] `/performance` shows current state feedback
- [ ] `/emotion excited` changes both voice and orb
- [ ] `/reset-performance` clears overrides
- [ ] Pre-roll timing: orb animates before voice starts
- [ ] Gesture detection still works (*pulses warmly* etc.)
- [ ] Voice modulation audible (speed, expressiveness differences)

---

## Files Summary

| File | Action |
|------|--------|
| `src/luna/services/performance_state.py` | **CREATE** — Unified state schema |
| `src/luna/services/performance_orchestrator.py` | **CREATE** — Coordination logic |
| `src/luna/api/server.py` | **MODIFY** — Add slash endpoints |
| `src/voice/tts/piper.py` | **MODIFY** — Accept voice knobs |
| `src/voice/tts/manager.py` | **MODIFY** — Pass knobs through |
| `frontend/src/components/VoiceTuningPanel.jsx` | **CREATE** — Voice UI |
| `frontend/src/components/OrbSettingsPanel.jsx` | **CREATE** — Orb UI |
| `frontend/src/components/ChatPanel.jsx` | **MODIFY** — Render panels |
| `frontend/src/hooks/useChat.js` | **MODIFY** — Add commands |

---

## Dependencies

This handoff **requires** the Piper binary fix from `HANDOFF_PIPER_TTS_BINARY_WRAPPER.md` to be completed first. Voice modulation won't work if Piper isn't initialized.

**Order of execution:**
1. HANDOFF_PIPER_TTS_BINARY_WRAPPER.md (fix Piper)
2. This handoff (add performance layer)
3. HANDOFF_LUNA_ORB_FOLLOW_BEHAVIOR.md (fairy movement)
