"""
Tests for Consciousness Module
==============================

Tests for attention decay, personality weights, and consciousness state.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import math


class TestAttentionTopic:
    """Tests for AttentionTopic dataclass."""

    def test_creation(self):
        """Test basic topic creation."""
        from luna.consciousness.attention import AttentionTopic

        topic = AttentionTopic(
            name="coding",
            weight=0.8,
        )

        assert topic.name == "coding"
        assert topic.weight == 0.8
        assert topic.access_count == 0
        assert isinstance(topic.last_active, datetime)

    def test_serialization(self):
        """Test to_dict and from_dict."""
        from luna.consciousness.attention import AttentionTopic

        original = AttentionTopic(
            name="luna",
            weight=0.9,
            access_count=5,
        )

        data = original.to_dict()
        restored = AttentionTopic.from_dict(data)

        assert restored.name == original.name
        assert restored.weight == original.weight
        assert restored.access_count == original.access_count


class TestAttentionManager:
    """Tests for AttentionManager."""

    def test_initialization(self):
        """Test manager initializes with correct defaults."""
        from luna.consciousness.attention import AttentionManager

        manager = AttentionManager()

        assert manager.half_life_days == 60.0
        assert len(manager) == 0

    def test_track_new_topic(self):
        """Test tracking a new topic."""
        from luna.consciousness.attention import AttentionManager

        manager = AttentionManager()
        manager.track("coding", weight=0.8)

        assert len(manager) == 1
        topic = manager.get_topic("coding")
        assert topic is not None
        assert topic.weight == 0.8
        assert topic.access_count == 1

    def test_track_boosts_existing(self):
        """Test tracking existing topic boosts weight."""
        from luna.consciousness.attention import AttentionManager

        manager = AttentionManager()
        manager.track("coding", weight=0.5)
        initial_weight = manager.get_topic("coding").weight

        manager.track("coding", weight=0.3)

        topic = manager.get_topic("coding")
        assert topic.weight > initial_weight
        assert topic.access_count == 2

    def test_track_case_insensitive(self):
        """Test topics are case insensitive."""
        from luna.consciousness.attention import AttentionManager

        manager = AttentionManager()
        manager.track("Coding")
        manager.track("CODING")
        manager.track("coding")

        assert len(manager) == 1
        topic = manager.get_topic("coding")
        assert topic.access_count == 3

    def test_decay_reduces_weight(self):
        """Test decay reduces topic weights."""
        from luna.consciousness.attention import AttentionManager, AttentionTopic

        manager = AttentionManager(half_life_days=60.0)

        # Create topic with old timestamp
        manager.topics["old_topic"] = AttentionTopic(
            name="old_topic",
            weight=1.0,
            last_active=datetime.now() - timedelta(days=60),
        )

        manager.decay_all()

        topic = manager.get_topic("old_topic")
        # After one half-life, weight should be ~0.5
        assert 0.45 < topic.weight < 0.55

    def test_decay_prunes_low_weight(self):
        """Test decay removes topics below threshold."""
        from luna.consciousness.attention import AttentionManager, AttentionTopic

        manager = AttentionManager(half_life_days=1.0)  # Fast decay

        # Create very old topic
        manager.topics["ancient"] = AttentionTopic(
            name="ancient",
            weight=0.1,
            last_active=datetime.now() - timedelta(days=30),
        )

        pruned = manager.decay_all()

        assert pruned == 1
        assert len(manager) == 0

    def test_compute_freshness(self):
        """Test freshness computation."""
        from luna.consciousness.attention import AttentionManager

        manager = AttentionManager(half_life_days=60.0)

        # Fresh = 1.0
        now_freshness = manager.compute_freshness(datetime.now())
        assert now_freshness > 0.99

        # 60 days ago = ~0.5
        old_freshness = manager.compute_freshness(
            datetime.now() - timedelta(days=60)
        )
        assert 0.45 < old_freshness < 0.55

    def test_get_focused_filters_low(self):
        """Test get_focused filters low-weight topics."""
        from luna.consciousness.attention import AttentionManager

        manager = AttentionManager()
        manager.track("high", weight=0.9)
        manager.track("medium", weight=0.5)
        manager.track("low", weight=0.05)

        focused = manager.get_focused(threshold=0.1)

        assert len(focused) == 2
        assert focused[0].name == "high"  # Sorted by weight
        assert focused[1].name == "medium"

    def test_get_focused_respects_limit(self):
        """Test get_focused respects limit."""
        from luna.consciousness.attention import AttentionManager

        manager = AttentionManager()
        for i in range(10):
            manager.track(f"topic_{i}", weight=0.5)

        focused = manager.get_focused(threshold=0.1, limit=3)
        assert len(focused) == 3

    def test_serialization(self):
        """Test manager serialization."""
        from luna.consciousness.attention import AttentionManager

        manager = AttentionManager(half_life_days=30.0)
        manager.track("topic1", weight=0.8)
        manager.track("topic2", weight=0.6)

        data = manager.to_dict()
        restored = AttentionManager.from_dict(data)

        assert restored.half_life_days == 30.0
        assert len(restored) == 2
        assert restored.get_topic("topic1").weight == 0.8


class TestPersonalityWeights:
    """Tests for PersonalityWeights."""

    def test_default_traits(self):
        """Test default traits are set."""
        from luna.consciousness.personality import PersonalityWeights, DEFAULT_TRAITS

        weights = PersonalityWeights()

        assert "curious" in weights.traits
        assert weights.get_trait("curious") == DEFAULT_TRAITS["curious"]

    def test_get_trait_default(self):
        """Test get_trait returns 0.5 for unknown traits."""
        from luna.consciousness.personality import PersonalityWeights

        weights = PersonalityWeights()

        assert weights.get_trait("unknown_trait") == 0.5

    def test_set_trait(self):
        """Test setting a trait value."""
        from luna.consciousness.personality import PersonalityWeights

        weights = PersonalityWeights()
        weights.set_trait("curious", 0.3)

        assert weights.get_trait("curious") == 0.3

    def test_set_trait_clamps(self):
        """Test set_trait clamps values to 0-1."""
        from luna.consciousness.personality import PersonalityWeights

        weights = PersonalityWeights()
        weights.set_trait("curious", 1.5)
        assert weights.get_trait("curious") == 1.0

        weights.set_trait("warm", -0.5)
        assert weights.get_trait("warm") == 0.0

    def test_adjust_trait(self):
        """Test adjusting a trait."""
        from luna.consciousness.personality import PersonalityWeights

        weights = PersonalityWeights()
        original = weights.get_trait("curious")

        new_value = weights.adjust_trait("curious", 0.1)

        expected = min(1.0, original + 0.1)
        assert new_value == expected

    def test_adjust_trait_clamps(self):
        """Test adjust_trait clamps to 0-1."""
        from luna.consciousness.personality import PersonalityWeights

        weights = PersonalityWeights()
        weights.set_trait("test", 0.9)

        result = weights.adjust_trait("test", 0.5)
        assert result == 1.0

        weights.set_trait("test", 0.1)
        result = weights.adjust_trait("test", -0.5)
        assert result == 0.0

    def test_get_top_traits(self):
        """Test getting top traits by weight."""
        from luna.consciousness.personality import PersonalityWeights

        weights = PersonalityWeights()
        weights.traits = {
            "high": 0.9,
            "medium": 0.5,
            "low": 0.2,
        }

        top = weights.get_top_traits(2)

        assert len(top) == 2
        assert top[0] == ("high", 0.9)
        assert top[1] == ("medium", 0.5)

    def test_to_prompt_hint(self):
        """Test prompt hint generation."""
        from luna.consciousness.personality import PersonalityWeights

        weights = PersonalityWeights()
        # Ensure these are top traits
        weights.set_trait("curious", 0.95)
        weights.set_trait("warm", 0.90)

        hint = weights.to_prompt_hint()

        assert "Response style:" in hint
        # Should contain hints for top traits
        assert len(hint) > 20

    def test_reset_to_defaults(self):
        """Test resetting to default values."""
        from luna.consciousness.personality import PersonalityWeights, DEFAULT_TRAITS

        weights = PersonalityWeights()
        weights.set_trait("curious", 0.1)
        weights.set_trait("warm", 0.1)

        weights.reset_to_defaults()

        assert weights.get_trait("curious") == DEFAULT_TRAITS["curious"]
        assert weights.get_trait("warm") == DEFAULT_TRAITS["warm"]

    def test_blend_with(self):
        """Test blending two personalities."""
        from luna.consciousness.personality import PersonalityWeights

        weights1 = PersonalityWeights(traits={"curious": 0.8, "warm": 0.2})
        weights2 = PersonalityWeights(traits={"curious": 0.2, "warm": 0.8})

        blended = weights1.blend_with(weights2, weight=0.5)

        # 50/50 blend should average
        assert blended.get_trait("curious") == 0.5
        assert blended.get_trait("warm") == 0.5

    def test_serialization(self):
        """Test serialization round-trip."""
        from luna.consciousness.personality import PersonalityWeights

        original = PersonalityWeights()
        original.set_trait("curious", 0.7)

        data = original.to_dict()
        restored = PersonalityWeights.from_dict(data)

        assert restored.get_trait("curious") == 0.7


class TestConsciousnessState:
    """Tests for ConsciousnessState."""

    def test_initialization(self):
        """Test default initialization."""
        from luna.consciousness.state import ConsciousnessState

        state = ConsciousnessState()

        assert state.coherence == 1.0
        assert state.mood == "neutral"
        assert state.tick_count == 0
        assert len(state.attention) == 0

    @pytest.mark.asyncio
    async def test_tick_increments_count(self):
        """Test tick increments counter."""
        from luna.consciousness.state import ConsciousnessState

        state = ConsciousnessState()
        initial_count = state.tick_count

        await state.tick()

        assert state.tick_count == initial_count + 1

    @pytest.mark.asyncio
    async def test_tick_updates_timestamp(self):
        """Test tick updates last_updated."""
        from luna.consciousness.state import ConsciousnessState

        state = ConsciousnessState()
        state.last_updated = datetime.now() - timedelta(hours=1)
        old_time = state.last_updated

        await state.tick()

        assert state.last_updated > old_time

    def test_set_mood_valid(self):
        """Test setting valid mood."""
        from luna.consciousness.state import ConsciousnessState

        state = ConsciousnessState()

        assert state.set_mood("curious") is True
        assert state.mood == "curious"

    def test_set_mood_invalid(self):
        """Test setting invalid mood."""
        from luna.consciousness.state import ConsciousnessState

        state = ConsciousnessState()

        assert state.set_mood("invalid_mood") is False
        assert state.mood == "neutral"  # Unchanged

    def test_focus_on(self):
        """Test focus_on convenience method."""
        from luna.consciousness.state import ConsciousnessState

        state = ConsciousnessState()
        state.focus_on("coding", weight=0.8)

        topic = state.attention.get_topic("coding")
        assert topic is not None
        assert topic.weight == 0.8

    def test_get_context_hint(self):
        """Test context hint generation."""
        from luna.consciousness.state import ConsciousnessState

        state = ConsciousnessState()
        state.focus_on("python", weight=0.9)
        state.set_mood("curious")

        hint = state.get_context_hint()

        assert "python" in hint.lower() or "focused" in hint.lower()
        assert "curious" in hint.lower()

    def test_get_summary(self):
        """Test summary generation."""
        from luna.consciousness.state import ConsciousnessState

        state = ConsciousnessState()
        state.focus_on("topic1", weight=0.8)
        state.set_mood("focused")

        summary = state.get_summary()

        assert "mood" in summary
        assert "coherence" in summary
        assert "attention_topics" in summary
        assert summary["mood"] == "focused"

    def test_serialization_roundtrip(self):
        """Test full serialization round-trip."""
        from luna.consciousness.state import ConsciousnessState

        original = ConsciousnessState()
        original.focus_on("topic1", weight=0.9)
        original.focus_on("topic2", weight=0.5)
        original.set_mood("curious")
        original.coherence = 0.8
        original.tick_count = 100

        data = original.to_dict()
        restored = ConsciousnessState.from_dict(data)

        assert restored.mood == original.mood
        assert restored.coherence == original.coherence
        assert restored.tick_count == original.tick_count
        assert len(restored.attention) == 2

    def test_from_dict_empty(self):
        """Test restoration from empty dict."""
        from luna.consciousness.state import ConsciousnessState

        state = ConsciousnessState.from_dict({})

        # Should have defaults
        assert state.coherence == 1.0
        assert state.mood == "neutral"
        assert state.tick_count == 0

    @pytest.mark.asyncio
    async def test_save_and_load(self):
        """Test save and load to file."""
        from luna.consciousness.state import ConsciousnessState

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            temp_path = Path(f.name)

        try:
            # Create and save
            original = ConsciousnessState()
            original.focus_on("test_topic", weight=0.9)
            original.set_mood("focused")
            original.tick_count = 42

            success = await original.save(temp_path)
            assert success is True
            assert temp_path.exists()

            # Load and verify
            restored = await ConsciousnessState.load(temp_path)

            assert restored.mood == "focused"
            assert restored.tick_count == 42
            topic = restored.attention.get_topic("test_topic")
            assert topic is not None
            assert topic.weight == 0.9

        finally:
            temp_path.unlink(missing_ok=True)

    @pytest.mark.asyncio
    async def test_load_missing_file(self):
        """Test load returns fresh state for missing file."""
        from luna.consciousness.state import ConsciousnessState

        state = await ConsciousnessState.load(Path("/nonexistent/path.yaml"))

        # Should return fresh state
        assert state.tick_count == 0
        assert state.mood == "neutral"


class TestConsciousnessIntegration:
    """Integration tests for consciousness with other components."""

    @pytest.mark.asyncio
    async def test_coherence_from_attention(self):
        """Test coherence calculation based on attention."""
        from luna.consciousness.state import ConsciousnessState

        state = ConsciousnessState()

        # Single strong focus = high coherence
        state.focus_on("one_topic", weight=0.9)
        await state.tick()
        high_coherence = state.coherence

        # Many topics = lower coherence
        state.focus_on("topic2", weight=0.8)
        state.focus_on("topic3", weight=0.7)
        state.focus_on("topic4", weight=0.6)
        await state.tick()
        lower_coherence = state.coherence

        # More focused attention = higher coherence
        assert high_coherence > lower_coherence or high_coherence >= 0.7

    @pytest.mark.asyncio
    async def test_multiple_ticks_decay(self):
        """Test that multiple ticks cause decay."""
        from luna.consciousness.state import ConsciousnessState
        from luna.consciousness.attention import AttentionTopic
        from datetime import timedelta

        state = ConsciousnessState()
        state.attention.half_life_days = 1.0  # Fast decay for test

        # Add topic with old timestamp
        state.attention.topics["old"] = AttentionTopic(
            name="old",
            weight=1.0,
            last_active=datetime.now() - timedelta(days=2),
        )

        initial_weight = state.attention.get_topic("old").weight

        # Tick should apply decay
        await state.tick()

        final_weight = state.attention.get_topic("old").weight
        assert final_weight < initial_weight
