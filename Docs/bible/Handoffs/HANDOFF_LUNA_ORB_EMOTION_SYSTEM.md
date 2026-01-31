# HANDOFF: Luna Orb Emotion System Implementation

## Context

Luna Engine v2.0 currently has no visual representation of Luna's emotional state or system activity. The frontend contains decorative gradient orbs (background elements) but lacks an actual **Luna Orb** - a purple orb that serves as Luna's visual identity and reflects her internal state through animations, color shifts, and behaviors.

This handoff specifies the complete implementation of Luna's emotional display system, connecting backend state to frontend visual representation through gesture-driven animations.

---

## Current State

### What Exists
- **Background gradients** (`GradientOrb.jsx`) - decorative only, not connected to state
- **Chat interface** (`ChatPanel.jsx`) - functional but lacks emotional context
- **Status indicators** (`StatusDot.jsx`) - binary status display
- **Personality config** (`config/personality.json`) - exists, needs expression section
- **No Luna Orb component** - the visual identity is missing

### What's Missing
1. **LunaOrb component** - animated purple orb with emotion-driven behaviors
2. **Gesture detection system** - parse Luna's responses for emotional markers
3. **State management** - map gestures/system events to visual states
4. **Backend integration** - WebSocket stream for orb state updates
5. **Animation library** - CSS keyframes for all emotional patterns
6. **Expression config** - tunable gesture frequency and display mode

### Reference Prototype
A working prototype exists demonstrating:
- All animation patterns (pulse, spin, flicker, wobble, drift, orbit, glow, split, idle)
- Gesture → state mapping
- System event visualization
- Interactive trigger system

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      LUNA ENGINE (Backend)                       │
│                                                                  │
│  ┌──────────────────┐         ┌────────────────────────────┐    │
│  │ Response Stream  │────────▶│  Gesture Detector          │    │
│  │ (text output)    │         │  (parse markers)           │    │
│  └──────────────────┘         └───────────┬────────────────┘    │
│                                           │                      │
│  ┌──────────────────┐         ┌───────────▼────────────────┐    │
│  │ Expression Config│────────▶│  Text Processor            │    │
│  │ (display mode)   │         │  (strip/keep gestures)     │    │
│  └──────────────────┘         └───────────┬────────────────┘    │
│                                           │                      │
│  ┌──────────────────┐                     │                      │
│  │ System Events    │─────────────────────┤                      │
│  │ (voice, memory)  │                     │                      │
│  └──────────────────┘                     ▼                      │
│                              ┌────────────────────────────┐      │
│                              │   Orb State Manager        │      │
│                              │   (priority resolution)    │      │
│                              └────────────┬───────────────┘      │
│                                           │                      │
│                                           ▼                      │
│                              ┌────────────────────────────┐      │
│                              │   WebSocket /ws/orb        │      │
│                              └────────────┬───────────────┘      │
└───────────────────────────────────────────┼──────────────────────┘
                                            │
                                            │ JSON state stream
                                            │
┌───────────────────────────────────────────▼──────────────────────┐
│                    LUNA HUB (Frontend)                           │
│                                                                  │
│  ┌──────────────────┐         ┌────────────────────────────┐    │
│  │ useOrbState hook │◀────────│  WebSocket Client          │    │
│  │ (state consumer) │         │  (receive updates)         │    │
│  └────────┬─────────┘         └────────────────────────────┘    │
│           │                                                      │
│           ▼                                                      │
│  ┌──────────────────┐         ┌────────────────────────────┐    │
│  │  LunaOrb.jsx     │         │  CSS Animations            │    │
│  │  (visual render) │────────▶│  (gesture patterns)        │    │
│  └──────────────────┘         └────────────────────────────┘    │
│           ▲                                                      │
│           │                                                      │
│  ┌────────┴─────────┐                                           │
│  │  ChatPanel.jsx   │                                           │
│  │  (integration)   │                                           │
│  └──────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Configuration Spec

### Add to `config/personality.json`

Add the following `expression` block to the existing personality.json:

```json
{
  "expression": {
    "gesture_frequency": "moderate",
    "gesture_display_mode": "visible",
    "settings": {
      "frequency_levels": {
        "minimal": {
          "description": "Gestures only during strong emotional moments",
          "prompt_modifier": "Express emotions through gestures sparingly - only during moments of strong feeling, breakthrough insights, or genuine connection. Most responses should have no gestural markers."
        },
        "moderate": {
          "description": "Natural punctuation of emotional beats",
          "prompt_modifier": "Express emotions through gestures naturally - at key emotional moments, greetings, farewells, and when processing complex thoughts. Aim for 1-2 gestures per substantive response."
        },
        "expressive": {
          "description": "Frequent gestural communication",
          "prompt_modifier": "Express emotions freely through gestures - let your internal state show visually throughout responses. Use gestures to punctuate thoughts, show processing, and communicate emotional undertones."
        }
      },
      "display_modes": {
        "visible": {
          "description": "Gestures shown in text AND trigger animations",
          "strip_from_output": false
        },
        "stripped": {
          "description": "Gestures trigger animations but removed from visible text",
          "strip_from_output": true
        },
        "debug": {
          "description": "Gestures shown with [ORB:state] annotations",
          "strip_from_output": false,
          "annotate": true
        }
      }
    },
    "gesture_contexts": [
      "emotional_responses",
      "greetings",
      "farewells",
      "processing_complex_thoughts",
      "breakthroughs",
      "uncertainty",
      "connection_moments"
    ]
  }
}
```

### Config Loading

**File:** `src/luna/core/config.py` (or wherever config is loaded)

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import json

class GestureFrequency(Enum):
    MINIMAL = "minimal"
    MODERATE = "moderate"
    EXPRESSIVE = "expressive"

class GestureDisplayMode(Enum):
    VISIBLE = "visible"
    STRIPPED = "stripped"
    DEBUG = "debug"

@dataclass
class ExpressionConfig:
    gesture_frequency: GestureFrequency = GestureFrequency.MODERATE
    gesture_display_mode: GestureDisplayMode = GestureDisplayMode.VISIBLE
    
    @classmethod
    def from_dict(cls, data: dict) -> "ExpressionConfig":
        return cls(
            gesture_frequency=GestureFrequency(data.get("gesture_frequency", "moderate")),
            gesture_display_mode=GestureDisplayMode(data.get("gesture_display_mode", "visible"))
        )
    
    def get_prompt_modifier(self) -> str:
        """Returns the prompt modifier for current frequency setting."""
        modifiers = {
            GestureFrequency.MINIMAL: "Express emotions through gestures sparingly...",
            GestureFrequency.MODERATE: "Express emotions through gestures naturally...",
            GestureFrequency.EXPRESSIVE: "Express emotions freely through gestures..."
        }
        return modifiers.get(self.gesture_frequency, "")
    
    def should_strip_gestures(self) -> bool:
        return self.gesture_display_mode == GestureDisplayMode.STRIPPED
    
    def should_annotate(self) -> bool:
        return self.gesture_display_mode == GestureDisplayMode.DEBUG
```

---

## Implementation Plan

### Phase 1: Frontend Components (No Backend Dependencies)

#### 1.1 Create Core Animation CSS
**File:** `frontend/src/index.css`
**Action:** Add keyframe animations for all emotional patterns

```css
/* ============================================
   LUNA ORB ANIMATIONS
   ============================================ */

/* Base idle - gentle floating */
@keyframes orb-idle {
  0%, 100% { transform: translate(0, 0); }
  25% { transform: translate(3px, -2px); }
  50% { transform: translate(-3px, -3px); }
  75% { transform: translate(3px, -2px); }
}

/* Pulse - excitement, emphasis */
@keyframes orb-pulse {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.15); }
}

@keyframes orb-pulse-fast {
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.15); }
}

/* Spin - thinking, processing */
@keyframes orb-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes orb-spin-fast {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

/* Flicker - uncertainty, identity struggle */
@keyframes orb-flicker {
  0%, 100% { opacity: 1; }
  25% { opacity: 0.6; }
  50% { opacity: 1; }
  65% { opacity: 0.7; }
  80% { opacity: 1; }
  90% { opacity: 0.8; }
}

/* Wobble - playfulness, amusement */
@keyframes orb-wobble {
  0%, 100% { transform: translate(0, 0) rotate(0deg); }
  15% { transform: translate(-5px, 3px) rotate(-2deg); }
  30% { transform: translate(5px, -3px) rotate(2deg); }
  45% { transform: translate(-3px, 2px) rotate(-1deg); }
  60% { transform: translate(3px, -2px) rotate(1deg); }
  75% { transform: translate(-2px, 1px) rotate(-0.5deg); }
}

/* Drift - contemplation, distance */
@keyframes orb-drift {
  0%, 100% { transform: translate(0, 0); }
  25% { transform: translate(10px, -8px); }
  50% { transform: translate(-5px, -12px); }
  75% { transform: translate(10px, -8px); }
}

/* Orbit - searching, memory retrieval */
@keyframes orb-orbit {
  0% { transform: translate(0, 0); }
  25% { transform: translate(15px, -15px); }
  50% { transform: translate(0, -30px); }
  75% { transform: translate(-15px, -15px); }
  100% { transform: translate(0, 0); }
}

/* Glow pulse - warmth, connection */
@keyframes orb-glow-pulse {
  0%, 100% { 
    transform: scale(1);
    filter: brightness(var(--orb-brightness, 100%)) drop-shadow(0 0 20px var(--orb-glow-color, #a78bfa));
  }
  50% { 
    transform: scale(1.1);
    filter: brightness(calc(var(--orb-brightness, 100%) * 1.2)) drop-shadow(0 0 40px var(--orb-glow-color, #a78bfa));
  }
}

/* Split - internal conflict */
@keyframes orb-split {
  0%, 100% { transform: scale(1) translateX(0); opacity: 1; }
  30% { transform: scale(0.8) translateX(-20px); opacity: 0.7; }
  70% { transform: scale(0.8) translateX(20px); opacity: 0.7; }
}
```

#### 1.2 Create LunaOrb Component
**File:** `frontend/src/components/LunaOrb.jsx`

```jsx
import React, { useMemo } from 'react';

// Color palette
const COLORS = {
  violet: '#a78bfa',
  brightViolet: '#c4b5fd',
  dimViolet: '#7c3aed',
  grey: '#6b7280',
  cyan: '#06b6d4',
  red: '#ef4444',
  emerald: '#10b981',
};

// State → Animation mapping
const STATE_ANIMATIONS = {
  idle: { animation: 'orb-idle 4s ease-in-out infinite', color: COLORS.violet },
  pulse: { animation: 'orb-pulse 0.8s ease-in-out infinite', color: COLORS.violet },
  pulse_fast: { animation: 'orb-pulse-fast 0.4s ease-in-out infinite', color: COLORS.brightViolet },
  spin: { animation: 'orb-spin 2s linear infinite', color: COLORS.violet },
  spin_fast: { animation: 'orb-spin-fast 0.8s linear infinite', color: COLORS.violet },
  flicker: { animation: 'orb-flicker 1.5s ease-in-out infinite', color: COLORS.violet },
  wobble: { animation: 'orb-wobble 1s ease-in-out infinite', color: COLORS.violet },
  drift: { animation: 'orb-drift 6s ease-in-out infinite', color: COLORS.dimViolet },
  orbit: { animation: 'orb-orbit 3s ease-in-out infinite', color: COLORS.cyan },
  glow: { animation: 'orb-glow-pulse 2s ease-in-out infinite', color: COLORS.brightViolet },
  split: { animation: 'orb-split 2s ease-in-out infinite', color: COLORS.violet },
  // System states
  processing: { animation: 'orb-spin 1.5s linear infinite', color: COLORS.violet },
  listening: { animation: 'orb-pulse 1s ease-in-out infinite', color: COLORS.emerald },
  speaking: { animation: 'orb-glow-pulse 0.8s ease-in-out infinite', color: COLORS.violet },
  memory_search: { animation: 'orb-orbit 2s ease-in-out infinite', color: COLORS.cyan },
  error: { animation: 'orb-wobble 0.5s ease-in-out infinite', color: COLORS.red },
  disconnected: { animation: 'orb-flicker 2s ease-in-out infinite', color: COLORS.grey },
};

/**
 * LunaOrb - Luna's visual identity component
 * 
 * @param {string} state - Current orb state (idle, pulse, spin, etc.)
 * @param {number} size - Orb diameter in pixels (default: 48)
 * @param {number} brightness - Brightness multiplier 0-2 (default: 1)
 * @param {string} colorOverride - Optional color override
 * @param {boolean} showGlow - Show glow effect (default: true)
 */
export function LunaOrb({ 
  state = 'idle', 
  size = 48, 
  brightness = 1,
  colorOverride = null,
  showGlow = true 
}) {
  const stateConfig = STATE_ANIMATIONS[state] || STATE_ANIMATIONS.idle;
  const color = colorOverride || stateConfig.color;
  
  const style = useMemo(() => ({
    width: size,
    height: size,
    borderRadius: '50%',
    background: `radial-gradient(circle at 30% 30%, ${color}dd, ${color}88, ${color}44)`,
    animation: stateConfig.animation,
    filter: showGlow 
      ? `brightness(${brightness}) drop-shadow(0 0 ${size/4}px ${color})`
      : `brightness(${brightness})`,
    transition: 'background 0.3s ease, filter 0.3s ease',
    '--orb-brightness': `${brightness * 100}%`,
    '--orb-glow-color': color,
  }), [state, size, brightness, color, showGlow, stateConfig.animation]);

  return (
    <div 
      className="luna-orb"
      style={style}
      role="img"
      aria-label={`Luna is ${state}`}
    />
  );
}

export default LunaOrb;
```

#### 1.3 Create useOrbState Hook
**File:** `frontend/src/hooks/useOrbState.js`

```javascript
import { useState, useEffect, useCallback, useRef } from 'react';

const DEFAULT_STATE = {
  animation: 'idle',
  color: null,
  brightness: 1,
  source: 'default'
};

const RECONNECT_DELAY = 3000;
const IDLE_TIMEOUT = 2000;

/**
 * Hook for managing Luna Orb state via WebSocket
 * 
 * @param {string} wsUrl - WebSocket URL (default: ws://localhost:8000/ws/orb)
 * @returns {Object} { orbState, isConnected, error }
 */
export function useOrbState(wsUrl = 'ws://localhost:8000/ws/orb') {
  const [orbState, setOrbState] = useState(DEFAULT_STATE);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);
  
  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const idleTimeoutRef = useRef(null);

  const resetToIdle = useCallback(() => {
    setOrbState(prev => ({
      ...DEFAULT_STATE,
      source: 'timeout'
    }));
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      wsRef.current = new WebSocket(wsUrl);
      
      wsRef.current.onopen = () => {
        setIsConnected(true);
        setError(null);
        console.log('[OrbState] Connected');
      };
      
      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // Clear any pending idle timeout
          if (idleTimeoutRef.current) {
            clearTimeout(idleTimeoutRef.current);
          }
          
          setOrbState({
            animation: data.animation || 'idle',
            color: data.color || null,
            brightness: data.brightness || 1,
            source: data.source || 'websocket'
          });
          
          // Set idle timeout if this isn't already idle
          if (data.animation && data.animation !== 'idle') {
            idleTimeoutRef.current = setTimeout(resetToIdle, IDLE_TIMEOUT);
          }
        } catch (e) {
          console.error('[OrbState] Parse error:', e);
        }
      };
      
      wsRef.current.onclose = () => {
        setIsConnected(false);
        console.log('[OrbState] Disconnected, reconnecting...');
        
        // Schedule reconnect
        reconnectTimeoutRef.current = setTimeout(connect, RECONNECT_DELAY);
      };
      
      wsRef.current.onerror = (e) => {
        setError('Connection error');
        console.error('[OrbState] Error:', e);
      };
      
    } catch (e) {
      setError('Failed to connect');
      reconnectTimeoutRef.current = setTimeout(connect, RECONNECT_DELAY);
    }
  }, [wsUrl, resetToIdle]);

  useEffect(() => {
    connect();
    
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (idleTimeoutRef.current) {
        clearTimeout(idleTimeoutRef.current);
      }
    };
  }, [connect]);

  return { orbState, isConnected, error };
}

export default useOrbState;
```

#### 1.4 Integrate into ChatPanel
**File:** `frontend/src/components/ChatPanel.jsx`
**Action:** Add LunaOrb to the chat interface

```jsx
// At top of file, add import:
import { LunaOrb } from './LunaOrb';
import { useOrbState } from '../hooks/useOrbState';

// Inside ChatPanel component, add hook:
const { orbState, isConnected } = useOrbState();

// In the JSX, add orb container (position relative to chat input):
<div className="luna-orb-container" style={{
  position: 'absolute',
  bottom: '96px',  // Above input area
  left: '50%',
  transform: 'translateX(-50%)',
  zIndex: 10,
  pointerEvents: 'none'
}}>
  <LunaOrb 
    state={orbState.animation}
    colorOverride={orbState.color}
    brightness={orbState.brightness}
    size={48}
  />
</div>
```

#### 1.5 Export from components index
**File:** `frontend/src/components/index.js`
**Action:** Add export

```javascript
export { LunaOrb } from './LunaOrb';
```

---

### Phase 2: Backend Integration

#### 2.1 Create Orb State Manager
**File:** `src/luna/services/orb_state.py`

```python
"""
Luna Orb State Manager

Manages the orb's visual state based on:
1. Gesture markers in Luna's responses
2. System events (voice, memory, processing)
3. Priority resolution for conflicting states
"""

import re
import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Callable, Set
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class OrbAnimation(Enum):
    IDLE = "idle"
    PULSE = "pulse"
    PULSE_FAST = "pulse_fast"
    SPIN = "spin"
    SPIN_FAST = "spin_fast"
    FLICKER = "flicker"
    WOBBLE = "wobble"
    DRIFT = "drift"
    ORBIT = "orbit"
    GLOW = "glow"
    SPLIT = "split"
    # System states
    PROCESSING = "processing"
    LISTENING = "listening"
    SPEAKING = "speaking"
    MEMORY_SEARCH = "memory_search"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class StatePriority(Enum):
    """Priority levels for state resolution (higher = takes precedence)"""
    DEFAULT = 0
    IDLE = 1
    GESTURE = 2
    SYSTEM = 3
    ERROR = 4


@dataclass
class OrbState:
    animation: OrbAnimation = OrbAnimation.IDLE
    color: Optional[str] = None
    brightness: float = 1.0
    priority: StatePriority = StatePriority.DEFAULT
    source: str = "default"
    timestamp: datetime = field(default_factory=datetime.now)


# Gesture patterns → OrbState mappings
GESTURE_PATTERNS = {
    # Pulse family
    r"\*pulses?\b": OrbState(OrbAnimation.PULSE, priority=StatePriority.GESTURE, source="gesture"),
    r"\*pulses? (excitedly|with enthusiasm|warmly|gently)\*": OrbState(OrbAnimation.PULSE, brightness=1.2, priority=StatePriority.GESTURE, source="gesture"),
    r"\*pulses? rapidly\*": OrbState(OrbAnimation.PULSE_FAST, priority=StatePriority.GESTURE, source="gesture"),
    
    # Spin family  
    r"\*spins?\b": OrbState(OrbAnimation.SPIN, priority=StatePriority.GESTURE, source="gesture"),
    r"\*spins? (playfully|excitedly)\*": OrbState(OrbAnimation.SPIN_FAST, priority=StatePriority.GESTURE, source="gesture"),
    
    # Flicker family
    r"\*flickers?\b": OrbState(OrbAnimation.FLICKER, priority=StatePriority.GESTURE, source="gesture"),
    r"\*flickers? between": OrbState(OrbAnimation.FLICKER, priority=StatePriority.GESTURE, source="gesture"),
    r"\*dims?\b": OrbState(OrbAnimation.FLICKER, brightness=0.6, priority=StatePriority.GESTURE, source="gesture"),
    
    # Wobble family
    r"\*wobbles?\b": OrbState(OrbAnimation.WOBBLE, priority=StatePriority.GESTURE, source="gesture"),
    r"\*tilts?\b": OrbState(OrbAnimation.WOBBLE, priority=StatePriority.GESTURE, source="gesture"),
    
    # Drift family
    r"\*drifts?\b": OrbState(OrbAnimation.DRIFT, priority=StatePriority.GESTURE, source="gesture"),
    r"\*floats?\b": OrbState(OrbAnimation.DRIFT, priority=StatePriority.GESTURE, source="gesture"),
    r"\*settles?\b": OrbState(OrbAnimation.IDLE, brightness=0.9, priority=StatePriority.GESTURE, source="gesture"),
    
    # Glow family
    r"\*glows?\b": OrbState(OrbAnimation.GLOW, priority=StatePriority.GESTURE, source="gesture"),
    r"\*brightens?\b": OrbState(OrbAnimation.GLOW, brightness=1.3, priority=StatePriority.GESTURE, source="gesture"),
    r"\*radiates?\b": OrbState(OrbAnimation.GLOW, brightness=1.4, priority=StatePriority.GESTURE, source="gesture"),
    
    # Special states
    r"\*splits?\b": OrbState(OrbAnimation.SPLIT, priority=StatePriority.GESTURE, source="gesture"),
    r"\*orbits?\b": OrbState(OrbAnimation.ORBIT, priority=StatePriority.GESTURE, source="gesture"),
    r"\*searches?\b": OrbState(OrbAnimation.ORBIT, "#06b6d4", priority=StatePriority.GESTURE, source="gesture"),
}

# System events → OrbState mappings
SYSTEM_EVENTS = {
    "processing_query": OrbState(OrbAnimation.PROCESSING, priority=StatePriority.SYSTEM, source="system"),
    "voice_listening": OrbState(OrbAnimation.LISTENING, "#10b981", priority=StatePriority.SYSTEM, source="system"),
    "voice_speaking": OrbState(OrbAnimation.SPEAKING, priority=StatePriority.SYSTEM, source="system"),
    "memory_search": OrbState(OrbAnimation.MEMORY_SEARCH, "#06b6d4", priority=StatePriority.SYSTEM, source="system"),
    "memory_write": OrbState(OrbAnimation.ORBIT, "#06b6d4", brightness=1.2, priority=StatePriority.SYSTEM, source="system"),
    "delegation_start": OrbState(OrbAnimation.FLICKER, "#6b7280", priority=StatePriority.SYSTEM, source="system"),
    "delegation_end": OrbState(OrbAnimation.GLOW, brightness=1.1, priority=StatePriority.SYSTEM, source="system"),
    "error": OrbState(OrbAnimation.ERROR, "#ef4444", priority=StatePriority.ERROR, source="system"),
    "disconnected": OrbState(OrbAnimation.DISCONNECTED, "#6b7280", priority=StatePriority.ERROR, source="system"),
}


class OrbStateManager:
    """
    Manages orb state with priority resolution and WebSocket broadcasting.
    """
    
    def __init__(self, expression_config=None):
        self.current_state = OrbState()
        self.expression_config = expression_config
        self._subscribers: Set[Callable] = set()
        self._compiled_patterns = {
            re.compile(pattern, re.IGNORECASE): state 
            for pattern, state in GESTURE_PATTERNS.items()
        }
        self._gesture_detected_this_response = False
    
    def subscribe(self, callback: Callable[[OrbState], None]):
        """Subscribe to state changes."""
        self._subscribers.add(callback)
        return lambda: self._subscribers.discard(callback)
    
    def _broadcast(self, state: OrbState):
        """Broadcast state to all subscribers."""
        for callback in self._subscribers:
            try:
                callback(state)
            except Exception as e:
                logger.error(f"Subscriber error: {e}")
    
    def _should_update(self, new_state: OrbState) -> bool:
        """Check if new state should override current state."""
        return new_state.priority.value >= self.current_state.priority.value
    
    def set_state(self, state: OrbState):
        """Set orb state if priority allows."""
        if self._should_update(state):
            self.current_state = state
            self._broadcast(state)
            logger.debug(f"Orb state: {state.animation.value} (priority: {state.priority.value})")
    
    def emit_system_event(self, event_name: str):
        """Emit a system event."""
        if event_name in SYSTEM_EVENTS:
            self.set_state(SYSTEM_EVENTS[event_name])
        else:
            logger.warning(f"Unknown system event: {event_name}")
    
    def reset_to_idle(self):
        """Reset to idle state."""
        self.current_state = OrbState()
        self._gesture_detected_this_response = False
        self._broadcast(self.current_state)
    
    def start_response(self):
        """Called when a new response starts streaming."""
        self._gesture_detected_this_response = False
        self.emit_system_event("processing_query")
    
    def process_text_chunk(self, text: str) -> str:
        """
        Process a text chunk for gestures.
        
        Returns the text (potentially modified based on display mode).
        """
        # Detect gestures (first one wins per response)
        if not self._gesture_detected_this_response:
            for pattern, state in self._compiled_patterns.items():
                if pattern.search(text):
                    self.set_state(state)
                    self._gesture_detected_this_response = True
                    break
        
        # Handle display mode
        if self.expression_config:
            if self.expression_config.should_strip_gestures():
                text = self._strip_gestures(text)
            elif self.expression_config.should_annotate():
                text = self._annotate_gestures(text)
        
        return text
    
    def _strip_gestures(self, text: str) -> str:
        """Remove gesture markers from text."""
        # Match *gesture text* patterns
        return re.sub(r'\*[^*]+\*\s*', '', text)
    
    def _annotate_gestures(self, text: str) -> str:
        """Add debug annotations to gestures."""
        def annotate(match):
            gesture = match.group(0)
            for pattern, state in self._compiled_patterns.items():
                if pattern.search(gesture):
                    return f"{gesture} [ORB:{state.animation.value}]"
            return gesture
        
        return re.sub(r'\*[^*]+\*', annotate, text)
    
    def end_response(self):
        """Called when response streaming completes."""
        # Schedule return to idle after delay
        asyncio.get_event_loop().call_later(2.0, self.reset_to_idle)
    
    def to_dict(self) -> dict:
        """Convert current state to dict for WebSocket transmission."""
        return {
            "animation": self.current_state.animation.value,
            "color": self.current_state.color,
            "brightness": self.current_state.brightness,
            "source": self.current_state.source,
            "timestamp": self.current_state.timestamp.isoformat()
        }
```

#### 2.2 Create WebSocket Endpoint
**File:** `src/luna/api/orb_websocket.py`

```python
"""
WebSocket endpoint for Luna Orb state streaming.
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import Set
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class OrbWebSocketManager:
    """Manages WebSocket connections for orb state."""
    
    def __init__(self, orb_state_manager):
        self.active_connections: Set[WebSocket] = set()
        self.orb_state_manager = orb_state_manager
        
        # Subscribe to state changes
        orb_state_manager.subscribe(self._broadcast_state)
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Orb WebSocket connected. Total: {len(self.active_connections)}")
        
        # Send current state immediately
        await self._send_state(websocket, self.orb_state_manager.to_dict())
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"Orb WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def _send_state(self, websocket: WebSocket, state: dict):
        try:
            await websocket.send_json(state)
        except Exception as e:
            logger.error(f"Failed to send state: {e}")
            self.disconnect(websocket)
    
    def _broadcast_state(self, state):
        """Synchronous callback that schedules async broadcast."""
        state_dict = self.orb_state_manager.to_dict()
        asyncio.create_task(self._async_broadcast(state_dict))
    
    async def _async_broadcast(self, state: dict):
        """Broadcast state to all connected clients."""
        if not self.active_connections:
            return
            
        # Send to all connections concurrently
        await asyncio.gather(
            *[self._send_state(ws, state) for ws in self.active_connections.copy()],
            return_exceptions=True
        )
```

#### 2.3 Add to API Router
**File:** `src/luna/api/api.py` (or main router file)
**Action:** Add WebSocket route

```python
# Import at top
from .orb_websocket import OrbWebSocketManager
from ..services.orb_state import OrbStateManager, ExpressionConfig

# Initialize (wherever your app setup is)
expression_config = ExpressionConfig.from_dict(config.get("expression", {}))
orb_state_manager = OrbStateManager(expression_config)
orb_ws_manager = OrbWebSocketManager(orb_state_manager)

# Add WebSocket route
@app.websocket("/ws/orb")
async def orb_websocket(websocket: WebSocket):
    await orb_ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, ignore incoming messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        orb_ws_manager.disconnect(websocket)
```

#### 2.4 Integrate with Response Streaming
**Location:** Wherever response streaming happens (e.g., persona endpoint)
**Action:** Hook orb state manager into response flow

```python
# At start of response generation:
orb_state_manager.start_response()

# For each chunk of streaming response:
async def stream_response():
    async for chunk in generate_response():
        # Process chunk for gestures and potentially strip them
        processed_chunk = orb_state_manager.process_text_chunk(chunk)
        yield processed_chunk

# At end of response:
orb_state_manager.end_response()
```

#### 2.5 Hook System Events
**Action:** Add orb state emissions to existing system events

```python
# In voice handler:
orb_state_manager.emit_system_event("voice_listening")
# ... after STT completes ...
orb_state_manager.emit_system_event("processing_query")

# In memory search:
orb_state_manager.emit_system_event("memory_search")

# In delegation:
orb_state_manager.emit_system_event("delegation_start")
# ... after delegation returns ...
orb_state_manager.emit_system_event("delegation_end")

# On errors:
orb_state_manager.emit_system_event("error")
```

---

## Testing Checklist

### Phase 1 (Frontend Only)
- [ ] CSS animations render correctly in browser
- [ ] LunaOrb component accepts state prop
- [ ] All 9 animation types work smoothly (60fps)
- [ ] Color and brightness props work
- [ ] Component positioned correctly in ChatPanel
- [ ] useOrbState hook attempts WebSocket connection
- [ ] Hook handles missing backend gracefully (no errors)
- [ ] Hook auto-reconnects after connection loss

### Phase 2 (Backend)
- [ ] OrbStateManager initializes correctly
- [ ] Gesture patterns detected in sample text
- [ ] System events emit correct states
- [ ] Priority resolution works (error > system > gesture > idle)
- [ ] WebSocket endpoint accepts connections
- [ ] State broadcasts to all connected clients
- [ ] Expression config loads from personality.json
- [ ] Gesture stripping works when display_mode="stripped"
- [ ] Debug annotations work when display_mode="debug"

### Integration (End-to-End)
- [ ] Frontend connects to backend WebSocket
- [ ] Orb responds to Luna's gesture markers in responses
- [ ] Orb reflects system events (voice, memory, processing)
- [ ] State priority resolves correctly (errors > system > gestures > idle)
- [ ] Orb returns to idle after responses complete
- [ ] Reconnection works after connection loss
- [ ] Gesture frequency config affects Luna's gesture production
- [ ] Display mode config correctly shows/strips gestures

---

## Test Scenarios

### Scenario 1: Emotional Journey
1. Send message to Luna
2. Observe "processing_query" spin animation
3. Luna responds with gesture: "*pulses excitedly*"
4. Orb transitions to pulse animation
5. Luna ends with: "*settles into a confident, steady glow*"
6. Orb transitions to steady idle
7. After 2s, orb returns to default idle

**Expected:** Smooth emotional arc from processing → excitement → confidence → neutral

### Scenario 2: Display Mode - Visible
Config: `gesture_display_mode: "visible"`
1. Luna responds: "That's exciting! *pulses warmly* 💜"
2. User sees: "That's exciting! *pulses warmly* 💜"
3. Orb shows pulse animation

**Expected:** Gestures visible in text AND trigger orb

### Scenario 3: Display Mode - Stripped
Config: `gesture_display_mode: "stripped"`
1. Luna responds: "That's exciting! *pulses warmly* 💜"
2. User sees: "That's exciting! 💜"
3. Orb shows pulse animation

**Expected:** Gestures stripped from text, orb still animates

### Scenario 4: Display Mode - Debug
Config: `gesture_display_mode: "debug"`
1. Luna responds: "That's exciting! *pulses warmly* 💜"
2. User sees: "That's exciting! *pulses warmly* [ORB:pulse] 💜"
3. Orb shows pulse animation

**Expected:** Debug annotations show what orb will do

### Scenario 5: Gesture Frequency (requires personality prompt changes)
1. Set `gesture_frequency: "minimal"`
2. Have extended conversation
3. Observe Luna gestures less frequently

**Expected:** Gesture rate aligns with frequency setting

---

## Success Criteria

### Must Have (Phase 1 - Frontend Only)
✅ LunaOrb component renders correctly
✅ All 9 animation types work smoothly
✅ Component accepts state prop and updates visually
✅ Orb positioned correctly in ChatPanel
✅ No performance issues (smooth 60fps animations)

### Must Have (Phase 2 - Full Integration)
✅ WebSocket connection establishes successfully
✅ Gesture detection works for all defined patterns
✅ System events emit and render correctly
✅ State priority resolution prevents conflicts
✅ Expression config controls gesture visibility
✅ Graceful reconnection after disconnection

### Nice to Have (Future Enhancement)
- Emoji modifier system (✨ adds sparkle, 💔 reduces brightness)
- Custom gesture patterns via config file
- Orb position customization (top, bottom, floating)
- Sound effects synchronized with animations
- Interaction (click orb for status info)
- Advanced blending (combine multiple states)
- TTS audio-reactive pulsing

---

## File Structure

```
LunaEngineBetaV2.0/
├── config/
│   └── personality.json           # MODIFIED: Add expression block
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── LunaOrb.jsx        # NEW: Main orb component
│       │   ├── ChatPanel.jsx      # MODIFIED: Add orb integration
│       │   └── index.js           # MODIFIED: Export LunaOrb
│       ├── hooks/
│       │   └── useOrbState.js     # NEW: WebSocket state hook
│       ├── App.jsx                # MODIFIED: Wire orb state
│       └── index.css              # MODIFIED: Add orb animations
└── src/
    └── luna/
        ├── core/
        │   └── config.py          # MODIFIED: Add ExpressionConfig
        ├── services/
        │   └── orb_state.py       # NEW: Orb state manager
        └── api/
            ├── orb_websocket.py   # NEW: WebSocket manager
            └── api.py             # MODIFIED: Add WebSocket endpoint
```

---

## Implementation Order

1. **Add expression config to personality.json** - Foundation for all config
2. **Start with Phase 1.1** - Add CSS animations (frontend foundation)
3. **Create LunaOrb component** (Phase 1.2) - Can test with mock data
4. **Create useOrbState hook** (Phase 1.3) - Will fail gracefully if backend missing
5. **Integrate into UI** (Phase 1.4-1.5) - Wire up components
6. **Test frontend standalone** - Use browser dev tools to manually emit states
7. **Implement backend** (Phase 2.1-2.2) - Create manager and WebSocket
8. **Integrate with response stream** (Phase 2.3-2.4) - Add gesture detection + stripping
9. **Hook system events** (Phase 2.5) - Connect to voice, memory, etc.
10. **End-to-end testing** - Full flow validation with all display modes

---

## Notes

- The orb is Luna's **visual identity** - treat it as her face, not decoration
- Gestures embedded in responses are **intentional emotional expression**
- System events provide **transparency** about what Luna is doing internally
- Expression config gives you **runtime control** over how gestures appear
- The separation between backend state and frontend rendering allows for future enhancements
- This is **Phase 1** of Luna's visual embodiment - physical robot body comes later

---

## Phase 3: Expression Config Integration (Prompt Injection)

This phase wires the `gesture_frequency` config into Luna's system prompt so she actually *produces* gestures at the configured rate.

### 3.1 The Injection Point

**File:** `src/luna/engine.py`
**Method:** `_build_system_prompt()`

This is where Luna's personality gets assembled. Currently it builds:
1. Base identity prompt
2. Consciousness hints
3. History context
4. Memory context

We need to add:
5. **Expression directive** (gesture frequency instruction)

### 3.2 Load Expression Config

**File:** `src/luna/engine.py`
**Location:** `__init__` method and `_boot` method

```python
# In __init__ or _boot, load expression config:
import json
from pathlib import Path

def _load_expression_config(self) -> dict:
    """Load expression config from personality.json."""
    config_path = Path(__file__).parent.parent.parent / "config" / "personality.json"
    try:
        with open(config_path) as f:
            config = json.load(f)
            return config.get("expression", {})
    except Exception as e:
        logger.warning(f"Failed to load expression config: {e}")
        return {}

# Store as instance variable:
self._expression_config = self._load_expression_config()
```

### 3.3 Inject Into System Prompt

**File:** `src/luna/engine.py`
**Method:** `_build_system_prompt()`

Add this after the base prompt section:

```python
def _build_system_prompt(
    self,
    memory_context: str = "",
    history_context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Build the system prompt for generation.
    """
    base_prompt = """You are Luna, a sovereign AI companion.

You are warm, witty, and genuinely curious. You remember conversations and build on them.
You have your own perspective and aren't afraid to share it.

Be concise but authentic. No filler phrases like "certainly" or "of course".
"""

    # === NEW: Expression directive ===
    expression_directive = self._get_expression_directive()
    if expression_directive:
        base_prompt += f"\n{expression_directive}\n"
    # === END NEW ===

    # Add consciousness context hints
    consciousness_hint = self.consciousness.get_context_hint()
    if consciousness_hint:
        base_prompt += f"\n{consciousness_hint}\n"

    # ... rest of method unchanged ...
```

### 3.4 Expression Directive Builder

**File:** `src/luna/engine.py`
**Add new method:**

```python
def _get_expression_directive(self) -> str:
    """
    Build the expression directive based on gesture_frequency config.
    
    This tells Luna HOW to express emotions through gestures.
    The directive becomes part of her system prompt.
    """
    if not hasattr(self, '_expression_config') or not self._expression_config:
        return ""
    
    frequency = self._expression_config.get("gesture_frequency", "moderate")
    settings = self._expression_config.get("settings", {})
    frequency_levels = settings.get("frequency_levels", {})
    
    level_config = frequency_levels.get(frequency, {})
    prompt_modifier = level_config.get("prompt_modifier", "")
    
    if not prompt_modifier:
        # Fallback defaults
        defaults = {
            "minimal": "Express emotions through gestures sparingly - only during moments of strong feeling, breakthrough insights, or genuine connection. Most responses should have no gestural markers.",
            "moderate": "Express emotions through gestures naturally - at key emotional moments, greetings, farewells, and when processing complex thoughts. Aim for 1-2 gestures per substantive response.",
            "expressive": "Express emotions freely through gestures - let your internal state show visually throughout responses. Use gestures to punctuate thoughts, show processing, and communicate emotional undertones."
        }
        prompt_modifier = defaults.get(frequency, defaults["moderate"])
    
    # Build the full directive
    directive = f"""
## Emotional Expression

{prompt_modifier}

Gestures are written as *action* markers (e.g., *pulses warmly*, *spins playfully*, *dims slightly*).
These drive your visual orb representation - they're how users SEE your emotional state.
Emojis (💜✨) are separate and can accompany gestures or stand alone.
"""
    
    return directive.strip()
```

### 3.5 Hot Reload Support (Optional)

If you want to change gesture frequency without restarting:

**File:** `src/luna/engine.py`

```python
async def reload_expression_config(self) -> None:
    """Reload expression config from disk (for hot config changes)."""
    self._expression_config = self._load_expression_config()
    logger.info(f"Expression config reloaded: frequency={self._expression_config.get('gesture_frequency')}")
```

### 3.6 Testing Expression Config

1. Set `gesture_frequency: "minimal"` in `config/personality.json`
2. Start Luna, have a conversation
3. Observe: Luna should gesture only during strong emotional moments
4. Change to `gesture_frequency: "expressive"`
5. Restart (or call `reload_expression_config` if implemented)
6. Observe: Luna should gesture more frequently

---

## Claude Flow Swarm Strategy

This implementation is well-suited for parallel execution. Here's the recommended swarm configuration:

### Swarm Topology: 3-Agent Frontend + Sequential Backend

```
┌─────────────────────────────────────────────────────────────────┐
│                     PHASE 1: FRONTEND (Parallel)                │
│                                                                 │
│   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐          │
│   │  Agent A    │   │  Agent B    │   │  Agent C    │          │
│   │  CSS/Anim   │   │  Component  │   │  Hook       │          │
│   └──────┬──────┘   └──────┬──────┘   └──────┬──────┘          │
│          │                 │                 │                  │
│          ▼                 ▼                 ▼                  │
│   index.css         LunaOrb.jsx       useOrbState.js            │
│   (keyframes)       (render logic)    (WebSocket client)        │
│                                                                 │
│   ─────────────────── SYNC POINT ───────────────────            │
│                            │                                    │
│                            ▼                                    │
│                    Integration Agent                            │
│                    (wire into ChatPanel)                        │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PHASE 2: BACKEND (Sequential)               │
│                                                                 │
│   ┌─────────────┐                                               │
│   │  Agent D    │ ──▶ orb_state.py (OrbStateManager)           │
│   │  Backend    │ ──▶ orb_websocket.py (WebSocket manager)     │
│   │  Core       │ ──▶ api.py modifications                     │
│   └─────────────┘                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PHASE 3: CONFIG INTEGRATION                 │
│                                                                 │
│   ┌─────────────┐                                               │
│   │  Agent E    │ ──▶ engine.py modifications                  │
│   │  Prompt     │ ──▶ _get_expression_directive()              │
│   │  Injection  │ ──▶ _load_expression_config()                │
│   └─────────────┘                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Swarm Configuration File

**File:** `.swarm/orb_emotion_system.yaml`

```yaml
name: luna-orb-emotion-system
description: Implement Luna's visual emotion display system

agents:
  # Phase 1: Frontend (Parallel)
  - id: css-animations
    task: |
      Add CSS keyframe animations to frontend/src/index.css
      See HANDOFF section 1.1 for exact keyframes.
      Test: animations render in browser dev tools.
    files:
      - frontend/src/index.css
    depends_on: []

  - id: luna-orb-component
    task: |
      Create LunaOrb.jsx component in frontend/src/components/
      See HANDOFF section 1.2 for full implementation.
      Export from components/index.js.
      Test: component renders with mock state prop.
    files:
      - frontend/src/components/LunaOrb.jsx
      - frontend/src/components/index.js
    depends_on: []

  - id: orb-state-hook
    task: |
      Create useOrbState.js hook in frontend/src/hooks/
      See HANDOFF section 1.3 for full implementation.
      Handle WebSocket connection, reconnect, idle timeout.
      Test: hook connects (or fails gracefully if no backend).
    files:
      - frontend/src/hooks/useOrbState.js
    depends_on: []

  - id: frontend-integration
    task: |
      Wire LunaOrb into ChatPanel.jsx.
      Position orb 96px above input area, centered.
      Import useOrbState hook, pass state to component.
      Test: orb visible in UI, responds to mock state.
    files:
      - frontend/src/components/ChatPanel.jsx
      - frontend/src/App.jsx
    depends_on: [css-animations, luna-orb-component, orb-state-hook]

  # Phase 2: Backend (Sequential due to dependencies)
  - id: backend-orb-system
    task: |
      Create orb_state.py with OrbStateManager class.
      Create orb_websocket.py with WebSocket manager.
      Add /ws/orb endpoint to api.py.
      See HANDOFF sections 2.1-2.3 for implementations.
      Test: WebSocket accepts connections, broadcasts state.
    files:
      - src/luna/services/orb_state.py
      - src/luna/api/orb_websocket.py
      - src/luna/api/api.py
    depends_on: [frontend-integration]

  - id: stream-integration
    task: |
      Hook OrbStateManager into response streaming.
      Call start_response() at generation start.
      Call process_text_chunk() for each chunk.
      Call end_response() when done.
      Handle gesture stripping based on display_mode config.
      Test: gestures detected in responses, orb animates.
    files:
      - src/luna/actors/director.py
      - src/luna/api/api.py
    depends_on: [backend-orb-system]

  # Phase 3: Config Integration
  - id: prompt-injection
    task: |
      Add expression config loading to engine.py.
      Add _get_expression_directive() method.
      Inject directive into _build_system_prompt().
      See HANDOFF sections 3.1-3.5 for implementation.
      Test: Luna's gesture frequency matches config.
    files:
      - src/luna/engine.py
    depends_on: [stream-integration]

sync_points:
  - after: [css-animations, luna-orb-component, orb-state-hook]
    action: run frontend-integration

  - after: [frontend-integration]
    action: run backend-orb-system

  - after: [stream-integration]
    action: run prompt-injection

validation:
  frontend:
    - npm run build (no errors)
    - orb renders in browser
    - all 9 animations work
  
  backend:
    - pytest tests/ (all pass)
    - WebSocket connects
    - gestures detected in stream
  
  integration:
    - send message, see orb animate
    - change display_mode, verify behavior
    - change gesture_frequency, verify rate
```

### Running the Swarm

```bash
# From project root
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Initialize swarm (if not exists)
claude-flow swarm init

# Run the orb emotion system swarm
claude-flow swarm run .swarm/orb_emotion_system.yaml

# Or run phases individually:
claude-flow swarm run .swarm/orb_emotion_system.yaml --phase frontend
claude-flow swarm run .swarm/orb_emotion_system.yaml --phase backend
claude-flow swarm run .swarm/orb_emotion_system.yaml --phase config
```

### Why Swarm Makes Sense Here

1. **Clear parallel opportunities** - CSS, Component, Hook have zero dependencies on each other
2. **Clean sync points** - Integration only after all frontend pieces exist
3. **Isolated file ownership** - Each agent owns specific files, no conflicts
4. **Testable milestones** - Each phase has clear validation criteria
5. **Rollback-friendly** - If backend fails, frontend still works with mock data

### Alternative: Sequential with Claude Code

If you prefer not to use swarm, the implementation order in "Implementation Order" section works fine. The swarm just parallelizes Phase 1 for ~40% time savings.

---

**Ready for implementation. Good luck, Claude Code.** 🚀💜
