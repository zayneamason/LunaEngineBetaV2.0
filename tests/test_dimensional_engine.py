"""Tests for the Dimensional Engine and Dimension→Renderer mapping."""

import pytest
import math
from luna.services.dimensional_engine import DimensionalEngine, DimensionalState, _clamp
from luna.services.dim_renderer_map import map_dimensions_to_renderer
from luna.services.orb_renderer import OrbRenderer
from luna.services.orb_state import (
    OrbStateManager, StatePriority, OrbAnimation, GESTURE_PATTERNS,
)


# ── DimensionalState ──


class TestDimensionalState:
    def test_defaults(self):
        ds = DimensionalState()
        assert ds.valence == 0.3
        assert ds.arousal == 0.35
        assert ds.certainty == 0.7
        assert ds.engagement == 0.5
        assert ds.warmth == 0.6

    def test_to_dict(self):
        ds = DimensionalState(valence=0.123456, arousal=0.999)
        d = ds.to_dict()
        assert d["valence"] == 0.123
        assert d["arousal"] == 0.999
        assert set(d.keys()) == {"valence", "arousal", "certainty", "engagement", "warmth"}


# ── DimensionalEngine ──


class TestDimensionalEngine:
    def test_blend_neutral(self):
        """Neutral triggers should produce moderate dimensional values."""
        engine = DimensionalEngine(smoothing=1.0)  # instant snap for test
        state = engine.blend({
            "sentiment": 0.0,
            "memory_hit": 0.0,
            "identity": 0.0,
            "topic_personal": 0.0,
            "flow": 0.0,
            "time_mod": 0.0,
        })
        # All triggers zero → low valence, low arousal, base certainty, low engagement/warmth
        assert -0.5 < state.valence < 0.5
        assert 0.0 <= state.arousal <= 0.5
        assert state.certainty >= 0.3  # base 0.5 from formula
        assert state.engagement >= 0.0
        assert state.warmth >= 0.0

    def test_blend_warm_greeting(self):
        """Known user greeting should produce high warmth + valence."""
        engine = DimensionalEngine(smoothing=1.0)
        state = engine.blend({
            "sentiment": 0.6,
            "memory_hit": 0.5,
            "identity": 0.9,
            "topic_personal": 0.3,
            "flow": 0.1,
            "time_mod": 0.2,
        })
        assert state.valence > 0.3  # positive sentiment
        assert state.warmth > 0.5   # high identity → high warmth
        assert state.engagement > 0.3

    def test_blend_memory_miss(self):
        """Memory miss should lower certainty."""
        engine = DimensionalEngine(smoothing=1.0)
        state = engine.blend({
            "sentiment": 0.3,
            "memory_hit": -0.4,
            "identity": 0.9,
            "topic_personal": 0.5,
            "flow": 0.3,
            "time_mod": 0.0,
        })
        assert state.certainty < 0.5  # memory miss drops certainty

    def test_blend_deep_conversation(self):
        """Deep personal conversation should produce high engagement."""
        engine = DimensionalEngine(smoothing=1.0)
        state = engine.blend({
            "sentiment": 0.5,
            "memory_hit": 0.7,
            "identity": 0.9,
            "topic_personal": 0.8,
            "flow": 0.6,
            "time_mod": 0.0,
        })
        assert state.engagement > 0.6
        assert state.warmth > 0.5

    def test_momentum_smoothing(self):
        """With smoothing < 1.0, values should lerp toward target."""
        engine = DimensionalEngine(smoothing=0.3)
        # First blend — should move 30% from default toward target
        triggers = {
            "sentiment": 1.0,
            "memory_hit": 1.0,
            "identity": 1.0,
            "topic_personal": 1.0,
            "flow": 1.0,
            "time_mod": 0.0,
        }
        engine.blend(triggers)
        valence_after_1 = engine.state.valence
        arousal_after_1 = engine.state.arousal
        # Second blend — same triggers, should move further toward target
        engine.blend(triggers)
        assert engine.state.valence >= valence_after_1  # converging toward target
        assert engine.state.arousal >= arousal_after_1

        # With smoothing=1.0, first blend should snap to target immediately
        engine_snap = DimensionalEngine(smoothing=1.0)
        engine_snap.blend(triggers)
        # Smoothed engine after 1 blend should be < snapped engine
        assert valence_after_1 <= engine_snap.state.valence

    def test_clamp_bounds(self):
        """Values should never exceed their valid ranges."""
        engine = DimensionalEngine(smoothing=1.0)
        state = engine.blend({
            "sentiment": 5.0,  # way over
            "memory_hit": 5.0,
            "identity": 5.0,
            "topic_personal": 5.0,
            "flow": 5.0,
            "time_mod": 5.0,
        })
        assert state.valence <= 1.0
        assert state.arousal <= 1.0
        assert state.certainty <= 1.0
        assert state.engagement <= 1.0
        assert state.warmth <= 1.0

        state_neg = engine.blend({
            "sentiment": -5.0,
            "memory_hit": -5.0,
            "identity": -5.0,
            "topic_personal": -5.0,
            "flow": -5.0,
            "time_mod": -5.0,
        })
        assert state_neg.valence >= -1.0
        assert state_neg.arousal >= 0.0
        assert state_neg.certainty >= 0.0
        assert state_neg.engagement >= 0.0
        assert state_neg.warmth >= 0.0

    def test_reset(self):
        engine = DimensionalEngine(smoothing=1.0)
        engine.blend({"sentiment": 1.0, "memory_hit": 1.0, "identity": 1.0,
                       "topic_personal": 1.0, "flow": 1.0, "time_mod": 0.0})
        engine.reset()
        assert engine.state.valence == 0.3
        assert engine.state.arousal == 0.35

    def test_missing_triggers_default_to_safe_values(self):
        """Missing trigger keys should fall back gracefully."""
        engine = DimensionalEngine(smoothing=1.0)
        state = engine.blend({})  # empty triggers
        # Should not raise, and values should be in valid ranges
        assert -1.0 <= state.valence <= 1.0
        assert 0.0 <= state.arousal <= 1.0

    def test_time_modifier(self):
        """time_modifier() should return a float in [-0.2, 0.2]."""
        tm = DimensionalEngine.time_modifier()
        assert -0.3 <= tm <= 0.3

    def test_flow_from_turns(self):
        assert DimensionalEngine.flow_from_turns(0) == 0.0
        assert DimensionalEngine.flow_from_turns(1) == pytest.approx(0.15)
        assert DimensionalEngine.flow_from_turns(7) == pytest.approx(1.0, abs=0.05)
        assert DimensionalEngine.flow_from_turns(100) == 1.0  # capped


# ── Dimension→Renderer Mapping ──


class TestDimRendererMap:
    def test_neutral_mapping(self):
        """Neutral dimensions should produce moderate renderer params."""
        renderer = OrbRenderer()
        dims = DimensionalState()  # defaults
        renderer.reset()
        map_dimensions_to_renderer(dims, renderer)

        assert renderer.animation.breathe_speed > 0.008
        assert renderer.animation.breathe_amplitude > 1.5
        assert renderer.animation.glow.ambient_max > 0.04
        assert renderer.animation.glow.corona_max > 0.06

    def test_high_arousal_fast_breathing(self):
        """High arousal should speed up breathing."""
        renderer = OrbRenderer()
        dims = DimensionalState(arousal=1.0)
        renderer.reset()
        map_dimensions_to_renderer(dims, renderer)

        assert renderer.animation.breathe_speed == pytest.approx(0.035, abs=0.002)
        assert renderer.animation.breathe_amplitude == pytest.approx(4.0, abs=0.2)

    def test_low_certainty_flicker(self):
        """Certainty below 0.25 should enable flicker."""
        renderer = OrbRenderer()
        dims = DimensionalState(certainty=0.1)
        renderer.reset()
        map_dimensions_to_renderer(dims, renderer)
        assert renderer.animation.flicker is True

    def test_high_certainty_no_flicker(self):
        """Certainty above 0.25 should disable flicker."""
        renderer = OrbRenderer()
        dims = DimensionalState(certainty=0.8)
        renderer.reset()
        map_dimensions_to_renderer(dims, renderer)
        assert renderer.animation.flicker is False

    def test_high_engagement_tight_drift(self):
        """High engagement should reduce drift radius."""
        renderer = OrbRenderer()
        dims = DimensionalState(engagement=1.0)
        renderer.reset()
        map_dimensions_to_renderer(dims, renderer)
        assert renderer.animation.drift.radius_x == pytest.approx(12.0, abs=0.5)

        # Compare with low engagement
        renderer2 = OrbRenderer()
        dims2 = DimensionalState(engagement=0.0)
        renderer2.reset()
        map_dimensions_to_renderer(dims2, renderer2)
        assert renderer2.animation.drift.radius_x > renderer.animation.drift.radius_x

    def test_positive_valence_warm_hue(self):
        """Positive valence should shift hue warmer (higher)."""
        renderer = OrbRenderer()
        dims_pos = DimensionalState(valence=1.0, warmth=0.5)
        renderer.reset()
        map_dimensions_to_renderer(dims_pos, renderer)
        warm_hue = renderer.rings[0].hue

        renderer2 = OrbRenderer()
        dims_neg = DimensionalState(valence=-1.0, warmth=0.5)
        renderer2.reset()
        map_dimensions_to_renderer(dims_neg, renderer2)
        cool_hue = renderer2.rings[0].hue

        assert warm_hue > cool_hue  # positive → warmer → higher hue

    def test_ring_opacity_scales_with_certainty(self):
        """Low certainty should reduce ring opacity."""
        renderer_high = OrbRenderer()
        dims_high = DimensionalState(certainty=1.0)
        renderer_high.reset()
        map_dimensions_to_renderer(dims_high, renderer_high)

        renderer_low = OrbRenderer()
        dims_low = DimensionalState(certainty=0.1)
        renderer_low.reset()
        map_dimensions_to_renderer(dims_low, renderer_low)

        # Inner ring (highest opacity)
        assert renderer_high.rings[-1].base_opacity > renderer_low.rings[-1].base_opacity


# ── Gesture Survivors ──


class TestGestureSurvivors:
    def test_only_12_gesture_patterns(self):
        """GESTURE_PATTERNS should contain exactly 12 entries."""
        assert len(GESTURE_PATTERNS) == 12

    def test_survivors_present(self):
        """All 12 surviving gestures should be matchable."""
        import re
        test_cases = [
            "*splits*", "*searches*", "*dims*", "*gasps*",
            "*startles*", "*sparks*", "*lights up*", "*spins*",
            "*spins fast*", "*wobbles*", "*settles*", "*flickers*",
        ]
        compiled = {re.compile(p, re.IGNORECASE): s for p, s in GESTURE_PATTERNS.items()}
        for gesture in test_cases:
            matched = any(p.search(gesture) for p in compiled)
            assert matched, f"Gesture '{gesture}' should match a survivor pattern"

    def test_absorbed_gestures_absent(self):
        """Absorbed gestures should NOT be in GESTURE_PATTERNS."""
        import re
        absorbed = [
            "*smiles*", "*beams*", "*frowns*", "*pulses*",
            "*vibrates*", "*hesitates*", "*dances*", "*thinks*",
            "*drifts*", "*glows*", "*nods*", "*hugs*",
        ]
        compiled = {re.compile(p, re.IGNORECASE): s for p, s in GESTURE_PATTERNS.items()}
        for gesture in absorbed:
            matched = any(p.search(gesture) for p in compiled)
            assert not matched, f"Gesture '{gesture}' should have been absorbed by dimensions"


# ── OrbStateManager Dimensional Integration ──


class TestOrbStateDimensional:
    def test_update_dimensions_sets_state(self):
        """update_dimensions should update the dimensional state."""
        mgr = OrbStateManager()
        mgr.update_dimensions({
            "sentiment": 0.6,
            "memory_hit": 0.8,
            "identity": 0.9,
            "topic_personal": 0.5,
            "flow": 0.3,
            "time_mod": 0.0,
        })
        assert mgr._dimensional_state.valence != 0.3  # changed from default
        assert mgr.current_state.source == "dimension"
        assert mgr.current_state.priority == StatePriority.DIMENSION

    def test_gesture_overrides_dimension(self):
        """A P2 gesture should override the P1 dimensional baseline."""
        mgr = OrbStateManager()
        mgr.update_dimensions({
            "sentiment": 0.5, "memory_hit": 0.0, "identity": 0.0,
            "topic_personal": 0.0, "flow": 0.0, "time_mod": 0.0,
        })
        assert mgr.current_state.priority == StatePriority.DIMENSION

        # Process text with a surviving gesture
        mgr.process_text_chunk("*splits*")
        assert mgr.current_state.priority == StatePriority.GESTURE
        assert mgr.current_state.animation == OrbAnimation.SPLIT

    def test_to_dict_includes_dimensions(self):
        """to_dict should include dimensional values."""
        mgr = OrbStateManager()
        mgr.update_dimensions({
            "sentiment": 0.5, "memory_hit": 0.0, "identity": 0.0,
            "topic_personal": 0.0, "flow": 0.0, "time_mod": 0.0,
        })
        d = mgr.to_dict()
        assert "dimensions" in d
        assert "valence" in d["dimensions"]
        assert "arousal" in d["dimensions"]
        assert "warmth" in d["dimensions"]

    def test_dimension_priority_ordering(self):
        """Full ordering: DEFAULT < DIMENSION < EMOJI < GESTURE < SYSTEM < ERROR."""
        assert StatePriority.DEFAULT.value < StatePriority.DIMENSION.value
        assert StatePriority.DIMENSION.value < StatePriority.EMOJI.value
        assert StatePriority.EMOJI.value < StatePriority.GESTURE.value
        assert StatePriority.GESTURE.value < StatePriority.SYSTEM.value
        assert StatePriority.SYSTEM.value < StatePriority.ERROR.value


class TestClampHelper:
    def test_clamp_within_range(self):
        assert _clamp(0.5, 0.0, 1.0) == 0.5

    def test_clamp_below(self):
        assert _clamp(-2.0, -1.0, 1.0) == -1.0

    def test_clamp_above(self):
        assert _clamp(5.0, 0.0, 1.0) == 1.0
