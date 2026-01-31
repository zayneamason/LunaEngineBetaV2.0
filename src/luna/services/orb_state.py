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
from typing import Optional, Callable, Set, Dict, Any
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
GESTURE_PATTERNS: Dict[str, OrbState] = {
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
SYSTEM_EVENTS: Dict[str, OrbState] = {
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


class ExpressionConfig:
    """Expression configuration loaded from personality.json."""

    def __init__(
        self,
        gesture_frequency: str = "moderate",
        gesture_display_mode: str = "visible",
        settings: Optional[Dict] = None
    ):
        self.gesture_frequency = gesture_frequency
        self.gesture_display_mode = gesture_display_mode
        self.settings = settings or {}

    @classmethod
    def from_dict(cls, data: dict) -> "ExpressionConfig":
        return cls(
            gesture_frequency=data.get("gesture_frequency", "moderate"),
            gesture_display_mode=data.get("gesture_display_mode", "visible"),
            settings=data.get("settings", {})
        )

    def should_strip_gestures(self) -> bool:
        """Check if gestures should be stripped from output."""
        display_modes = self.settings.get("display_modes", {})
        mode_config = display_modes.get(self.gesture_display_mode, {})
        return mode_config.get("strip_from_output", False)

    def should_annotate(self) -> bool:
        """Check if gestures should be annotated with debug info."""
        display_modes = self.settings.get("display_modes", {})
        mode_config = display_modes.get(self.gesture_display_mode, {})
        return mode_config.get("annotate", False)


class OrbStateManager:
    """
    Manages orb state with priority resolution and WebSocket broadcasting.
    """

    def __init__(self, expression_config: Optional[ExpressionConfig] = None):
        self.current_state = OrbState()
        self.expression_config = expression_config
        self._subscribers: Set[Callable] = set()
        self._compiled_patterns = {
            re.compile(pattern, re.IGNORECASE): state
            for pattern, state in GESTURE_PATTERNS.items()
        }
        self._gesture_detected_this_response = False
        self._idle_task: Optional[asyncio.Task] = None

    def subscribe(self, callback: Callable[[OrbState], None]) -> Callable:
        """Subscribe to state changes. Returns unsubscribe function."""
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
        # Cancel any existing idle task
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()

        # Schedule return to idle after delay
        async def delayed_idle():
            await asyncio.sleep(2.0)
            self.reset_to_idle()

        try:
            loop = asyncio.get_running_loop()
            self._idle_task = loop.create_task(delayed_idle())
        except RuntimeError:
            # No running loop, skip delayed idle
            pass

    def to_dict(self) -> dict:
        """Convert current state to dict for WebSocket transmission."""
        return {
            "animation": self.current_state.animation.value,
            "color": self.current_state.color,
            "brightness": self.current_state.brightness,
            "source": self.current_state.source,
            "timestamp": self.current_state.timestamp.isoformat()
        }
