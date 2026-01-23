"""
Prosody mapping for Luna Engine voice system.

Maps personality traits to voice characteristics (rate, pitch, etc.)
for expressive text-to-speech synthesis.
"""
import logging
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class ProsodyParameters:
    """TTS prosody parameters for voice modulation."""
    # Speech rate (0.5 = half speed, 1.0 = normal, 2.0 = double)
    rate: float = 1.0

    # Base pitch shift (-1.0 to 1.0, 0 = normal)
    pitch: float = 0.0

    # Pitch variation/expressiveness (0.0 to 1.0)
    pitch_variation: float = 0.5

    # Pause duration multiplier (1.0 = normal)
    pause_duration: float = 1.0

    # Intonation strength (0.0 to 1.0)
    intonation: float = 0.5

    # Volume (0.0 to 1.0)
    volume: float = 0.8

    def to_dict(self) -> Dict:
        """Convert to dictionary for TTS providers."""
        return {
            "rate": self.rate,
            "pitch": self.pitch,
            "pitch_variation": self.pitch_variation,
            "pause_duration": self.pause_duration,
            "intonation": self.intonation,
            "volume": self.volume,
        }


def lerp(a: float, b: float, t: float) -> float:
    """Linear interpolation between a and b by t (0-1)."""
    return a + (b - a) * max(0.0, min(1.0, t))


class ProsodyMapper:
    """
    Maps personality traits to prosody parameters.

    Takes Luna's personality vector and converts it to voice characteristics
    that TTS providers can use for expressive synthesis.

    Personality dimensions mapped:
    - energy → speech rate
    - warmth → pitch variation / expressiveness
    - playfulness → intonation dynamics
    - directness → pause patterns
    - focus_intensity → pitch stability
    - technical_depth → articulation speed
    """

    def __init__(self):
        """Initialize prosody mapper with defaults."""
        self._default_prosody = ProsodyParameters()

    def map_personality(
        self,
        personality: Optional[Dict] = None,
        emotion: Optional[str] = None
    ) -> ProsodyParameters:
        """
        Convert personality traits to prosody parameters.

        Args:
            personality: Personality dict with trait values (0-1)
            emotion: Optional current emotion (affects prosody)

        Returns:
            ProsodyParameters for TTS
        """
        if not personality:
            return self._default_prosody

        # Extract personality traits with defaults
        energy = personality.get("energy", 0.5)
        warmth = personality.get("warmth", 0.6)
        playfulness = personality.get("playfulness", 0.4)
        directness = personality.get("directness", 0.7)
        focus_intensity = personality.get("focus_intensity", 0.5)
        technical_depth = personality.get("technical_depth", 0.5)

        # Map traits to prosody

        # Energy → Speech rate
        # High energy = faster, low energy = slower
        rate = lerp(0.85, 1.15, energy)

        # Warmth → Pitch variation (more expressive)
        # High warmth = more variation, low = flatter
        pitch_variation = lerp(0.3, 0.7, warmth)

        # Playfulness → Intonation dynamics
        # High playfulness = more dynamic intonation
        intonation = lerp(0.3, 0.7, playfulness)

        # Directness → Pause duration (shorter pauses = more direct)
        # High directness = shorter pauses
        pause_duration = lerp(1.2, 0.8, directness)

        # Focus intensity → Pitch stability
        # High focus = less pitch wandering (inverse of variation)
        # Moderate this against warmth
        if focus_intensity > 0.7:
            pitch_variation *= 0.8  # Reduce variation when highly focused

        # Technical depth → Articulation (slight rate reduction for clarity)
        if technical_depth > 0.7:
            rate *= 0.95  # Slightly slower for technical explanations

        # Apply emotion modifiers if present
        if emotion:
            rate, pitch, pitch_variation, intonation = self._apply_emotion(
                emotion, rate, 0.0, pitch_variation, intonation
            )
        else:
            pitch = 0.0

        # Clamp values to valid ranges
        rate = max(0.5, min(2.0, rate))
        pitch = max(-1.0, min(1.0, pitch))
        pitch_variation = max(0.0, min(1.0, pitch_variation))
        pause_duration = max(0.5, min(2.0, pause_duration))
        intonation = max(0.0, min(1.0, intonation))

        return ProsodyParameters(
            rate=rate,
            pitch=pitch,
            pitch_variation=pitch_variation,
            pause_duration=pause_duration,
            intonation=intonation,
            volume=0.8
        )

    def _apply_emotion(
        self,
        emotion: str,
        rate: float,
        pitch: float,
        pitch_variation: float,
        intonation: float
    ) -> tuple:
        """
        Apply emotion modifiers to prosody.

        Args:
            emotion: Current emotion state
            rate, pitch, pitch_variation, intonation: Current values

        Returns:
            Tuple of modified (rate, pitch, pitch_variation, intonation)
        """
        emotion = emotion.lower()

        if emotion in ("excited", "happy", "enthusiastic"):
            rate *= 1.1
            pitch += 0.1
            pitch_variation *= 1.2
            intonation *= 1.2

        elif emotion in ("calm", "relaxed", "thoughtful"):
            rate *= 0.9
            pitch -= 0.05
            pitch_variation *= 0.9
            intonation *= 0.9

        elif emotion in ("curious", "interested"):
            pitch += 0.05
            pitch_variation *= 1.1
            intonation *= 1.1

        elif emotion in ("serious", "concerned"):
            rate *= 0.95
            pitch -= 0.1
            pitch_variation *= 0.8

        elif emotion in ("playful", "teasing"):
            rate *= 1.05
            pitch_variation *= 1.3
            intonation *= 1.3

        elif emotion in ("tired", "low_energy"):
            rate *= 0.85
            pitch -= 0.15
            pitch_variation *= 0.7

        return rate, pitch, pitch_variation, intonation

    def get_luna_default(self) -> ProsodyParameters:
        """
        Get Luna's default prosody (when personality data unavailable).

        Based on Luna's canonical personality:
        - Warm but direct
        - Intellectually curious
        - Moderate energy
        - Not overly playful or robotic
        """
        return ProsodyParameters(
            rate=1.0,           # Normal pace
            pitch=0.0,          # Neutral pitch
            pitch_variation=0.5, # Moderate expressiveness
            pause_duration=0.9,  # Slightly quicker (direct)
            intonation=0.5,      # Moderate dynamics
            volume=0.8
        )
