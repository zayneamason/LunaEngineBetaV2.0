"""
Consciousness State for Luna Engine
====================================

Luna's continuous consciousness. The LLM is stateless.
This IS Luna's ongoing experience — persisted across restarts.

> "Consciousness is not a thing but a process." — Daniel Dennett
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, Any
import logging

from .attention import AttentionManager
from .personality import PersonalityWeights

logger = logging.getLogger(__name__)


# Persistence path
SNAPSHOT_PATH = Path.home() / ".luna" / "snapshot.yaml"


@dataclass
class ConsciousnessState:
    """
    Luna's continuous consciousness.

    The LLM is stateless inference. This class maintains:
    - What Luna is paying attention to (topics with decay)
    - Luna's personality (trait weights)
    - Current coherence level
    - Mood state
    - Tick counter (lifetime consciousness cycles)
    """

    attention: AttentionManager = field(default_factory=AttentionManager)
    personality: PersonalityWeights = field(default_factory=PersonalityWeights)
    coherence: float = 1.0  # How "together" Luna feels (0-1)
    mood: str = "neutral"   # Current emotional state
    last_updated: datetime = field(default_factory=datetime.now)
    tick_count: int = 0

    # Valid mood states
    VALID_MOODS = {
        "neutral", "curious", "focused", "playful",
        "thoughtful", "energetic", "calm", "helpful"
    }

    async def tick(self) -> dict:
        """
        Single consciousness tick (called every cognitive cycle).

        Returns dict of what changed.
        """
        changes = {}

        # 1. Decay attention topics
        pruned = self.attention.decay_all()
        if pruned > 0:
            changes["attention_pruned"] = pruned

        # 2. Update coherence based on attention spread
        # More focused attention = higher coherence
        focused_topics = self.attention.get_focused(threshold=0.3)
        if focused_topics:
            # Calculate coherence from attention distribution
            weights = [t.weight for t in focused_topics]
            max_weight = max(weights) if weights else 0.5
            spread = len(focused_topics)

            # High max weight + low spread = high coherence
            self.coherence = min(1.0, max_weight * (1.0 - spread * 0.05))
        else:
            # No strong focus = default coherence
            self.coherence = 0.7

        # 3. Update timestamp and tick count
        self.last_updated = datetime.now()
        self.tick_count += 1

        return changes

    def set_mood(self, mood: str) -> bool:
        """
        Set current mood.

        Returns True if mood was valid and set.
        """
        mood_lower = mood.lower()
        if mood_lower in self.VALID_MOODS:
            self.mood = mood_lower
            logger.debug(f"Consciousness: Mood set to '{mood_lower}'")
            return True
        logger.warning(f"Consciousness: Invalid mood '{mood}'")
        return False

    def focus_on(self, topic: str, weight: float = 1.0) -> None:
        """Convenience method to track attention topic."""
        self.attention.track(topic, weight)

    def get_context_hint(self) -> str:
        """
        Generate context hint for prompt injection.

        Combines personality and attention into guidance.
        """
        hints = []

        # Personality hint
        personality_hint = self.personality.to_prompt_hint()
        if personality_hint:
            hints.append(personality_hint)

        # Attention hint (what Luna is focused on)
        focused = self.attention.get_focused(threshold=0.3, limit=3)
        if focused:
            topics = [t.name for t in focused]
            hints.append(f"Currently focused on: {', '.join(topics)}.")

        # Mood hint
        if self.mood != "neutral":
            hints.append(f"Current mood: {self.mood}.")

        return " ".join(hints)

    def get_summary(self) -> dict:
        """Get summary of consciousness state."""
        focused = self.attention.get_focused(threshold=0.1, limit=5)
        return {
            "mood": self.mood,
            "coherence": round(self.coherence, 2),
            "attention_topics": len(self.attention),
            "focused_topics": [
                {"name": t.name, "weight": round(t.weight, 2)}
                for t in focused
            ],
            "top_traits": self.personality.get_top_traits(3),
            "tick_count": self.tick_count,
            "last_updated": self.last_updated.isoformat(),
        }

    def to_dict(self) -> dict:
        """Serialize for persistence."""
        return {
            "attention": self.attention.to_dict(),
            "personality": self.personality.to_dict(),
            "coherence": self.coherence,
            "mood": self.mood,
            "last_updated": self.last_updated.isoformat(),
            "tick_count": self.tick_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ConsciousnessState":
        """Restore from persistence."""
        state = cls()

        # Restore attention
        if "attention" in data:
            state.attention = AttentionManager.from_dict(data["attention"])

        # Restore personality
        if "personality" in data:
            state.personality = PersonalityWeights.from_dict(data["personality"])

        # Restore other fields
        state.coherence = data.get("coherence", 1.0)
        state.mood = data.get("mood", "neutral")
        state.tick_count = data.get("tick_count", 0)

        if "last_updated" in data:
            try:
                state.last_updated = datetime.fromisoformat(data["last_updated"])
            except (ValueError, TypeError):
                state.last_updated = datetime.now()

        return state

    async def save(self, path: Optional[Path] = None) -> bool:
        """
        Save consciousness state to disk.

        Returns True if successful.
        """
        save_path = path or SNAPSHOT_PATH

        try:
            import yaml

            save_path.parent.mkdir(parents=True, exist_ok=True)

            data = {
                "version": "2.0",
                "consciousness": self.to_dict(),
            }

            with open(save_path, "w") as f:
                yaml.safe_dump(data, f, default_flow_style=False)

            logger.info(f"Consciousness: Saved to {save_path}")
            return True

        except Exception as e:
            logger.error(f"Consciousness: Failed to save: {e}")
            return False

    @classmethod
    async def load(cls, path: Optional[Path] = None) -> "ConsciousnessState":
        """
        Load consciousness state from disk.

        Returns fresh state if file doesn't exist or is invalid.
        """
        load_path = path or SNAPSHOT_PATH

        if not load_path.exists():
            logger.info("Consciousness: No snapshot found, starting fresh")
            return cls()

        try:
            import yaml

            with open(load_path) as f:
                data = yaml.safe_load(f)

            if data and "consciousness" in data:
                state = cls.from_dict(data["consciousness"])
                logger.info(
                    f"Consciousness: Restored from snapshot "
                    f"(tick {state.tick_count}, {len(state.attention)} topics)"
                )
                return state

            logger.warning("Consciousness: Invalid snapshot format, starting fresh")
            return cls()

        except Exception as e:
            logger.error(f"Consciousness: Failed to load: {e}")
            return cls()

    def __repr__(self) -> str:
        return (
            f"ConsciousnessState(mood={self.mood}, "
            f"coherence={self.coherence:.2f}, "
            f"topics={len(self.attention)}, "
            f"tick={self.tick_count})"
        )
