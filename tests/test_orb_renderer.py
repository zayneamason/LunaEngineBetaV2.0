"""Tests for the OrbRenderer ring model and state mapping."""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from luna.services.orb_renderer import OrbRenderer, OrbRing, AnimationParams


class TestRingModel:
    """Ring construction and spacing."""

    def test_default_ring_count(self):
        renderer = OrbRenderer()
        assert len(renderer.rings) == 5

    def test_custom_ring_count(self):
        renderer = OrbRenderer(ring_count=3)
        assert len(renderer.rings) == 3

    def test_ring_spacing(self):
        renderer = OrbRenderer(ring_count=5, base_radius=44.0)
        # spacing = 44 / (5 + 0.5) = 8.0
        radii = [r.base_radius for r in renderer.rings]
        assert radii[0] == pytest.approx(44.0, abs=0.1)
        assert radii[1] == pytest.approx(36.0, abs=0.1)
        assert radii[2] == pytest.approx(28.0, abs=0.1)
        assert radii[3] == pytest.approx(20.0, abs=0.1)
        assert radii[4] == pytest.approx(12.0, abs=0.1)

    def test_outermost_ring_low_opacity(self):
        renderer = OrbRenderer()
        assert renderer.rings[0].base_opacity == pytest.approx(0.08, abs=0.01)

    def test_innermost_ring_has_fill(self):
        renderer = OrbRenderer()
        assert renderer.rings[-1].has_fill is True
        assert renderer.rings[0].has_fill is False

    def test_default_hue_is_purple(self):
        renderer = OrbRenderer()
        for ring in renderer.rings:
            assert ring.hue == 262.0

    def test_unique_ring_ids(self):
        renderer = OrbRenderer()
        ids = [r.id for r in renderer.rings]
        assert len(ids) == len(set(ids))


class TestSubdivision:
    """Ring subdivide operations."""

    def test_subdivide_ring(self):
        renderer = OrbRenderer(ring_count=5)
        assert renderer.subdivide_ring(0) is True
        assert len(renderer.rings) == 6

    def test_subdivide_preserves_innermost_fill(self):
        renderer = OrbRenderer(ring_count=5)
        renderer.subdivide_ring(4)  # innermost
        assert renderer.rings[-1].has_fill is True

    def test_subdivide_outer_not_filled(self):
        renderer = OrbRenderer(ring_count=5)
        renderer.subdivide_ring(0)
        assert renderer.rings[0].has_fill is False
        assert renderer.rings[1].has_fill is False

    def test_subdivide_all_doubles_count(self):
        renderer = OrbRenderer(ring_count=5)
        renderer.subdivide_all()
        assert len(renderer.rings) == 10

    def test_subdivide_too_small_ring(self):
        renderer = OrbRenderer(ring_count=5, base_radius=20.0)
        # Find a ring with radius < 8 and try subdividing
        small_idx = None
        for i, r in enumerate(renderer.rings):
            if r.base_radius < 8:
                small_idx = i
                break
        if small_idx is not None:
            assert renderer.subdivide_ring(small_idx) is False

    def test_subdivide_invalid_index(self):
        renderer = OrbRenderer()
        assert renderer.subdivide_ring(-1) is False
        assert renderer.subdivide_ring(100) is False

    def test_reset(self):
        renderer = OrbRenderer(ring_count=5)
        renderer.subdivide_all()
        assert len(renderer.rings) == 10
        renderer.reset()
        assert len(renderer.rings) == 5


class TestRingMutations:
    """Individual ring mutation operations."""

    def test_scale_ring(self):
        renderer = OrbRenderer()
        original = renderer.rings[0].base_radius
        renderer.scale_ring(0, 1.5)
        assert renderer.rings[0].base_radius == pytest.approx(original * 1.5, abs=0.1)

    def test_scale_ring_clamped(self):
        renderer = OrbRenderer()
        renderer.scale_ring(0, 100)  # would exceed 200
        assert renderer.rings[0].base_radius <= 200.0

    def test_fade_ring(self):
        renderer = OrbRenderer()
        renderer.fade_ring(0, 0.5)
        assert renderer.rings[0].base_opacity == 0.5

    def test_fade_ring_clamped(self):
        renderer = OrbRenderer()
        renderer.fade_ring(0, 2.0)
        assert renderer.rings[0].base_opacity <= 1.0

    def test_color_ring(self):
        renderer = OrbRenderer()
        renderer.color_ring(0, 180, 80, 50)
        assert renderer.rings[0].hue == 180
        assert renderer.rings[0].saturation == 80
        assert renderer.rings[0].lightness == 50

    def test_stroke_ring(self):
        renderer = OrbRenderer()
        renderer.stroke_ring(0, 2.5)
        assert renderer.rings[0].stroke_width == 2.5

    def test_stroke_ring_clamped(self):
        renderer = OrbRenderer()
        renderer.stroke_ring(0, 10)
        assert renderer.rings[0].stroke_width <= 4.0


class TestStateMapping:
    """apply_state maps OrbAnimation enums to params."""

    def _make_state(self, animation_value, color=None, brightness=1.0):
        """Create a mock OrbState-like object."""
        class MockAnimation:
            def __init__(self, val):
                self.value = val
        class MockState:
            def __init__(self, anim, clr, br):
                self.animation = MockAnimation(anim)
                self.color = clr
                self.brightness = br
        return MockState(animation_value, color, brightness)

    def test_idle_defaults(self):
        renderer = OrbRenderer()
        renderer.apply_state(self._make_state("idle"))
        assert renderer.animation.sync_breathing is False
        assert renderer.animation.flicker is False
        assert renderer.animation.sequential_pulse is False

    def test_pulse_sync_breathing(self):
        renderer = OrbRenderer()
        renderer.apply_state(self._make_state("pulse"))
        assert renderer.animation.sync_breathing is True
        assert renderer.animation.breathe_amplitude > 2.5

    def test_processing_sequential_pulse(self):
        renderer = OrbRenderer()
        renderer.apply_state(self._make_state("processing"))
        assert renderer.animation.sequential_pulse is True

    def test_memory_search_cyan(self):
        renderer = OrbRenderer()
        renderer.apply_state(self._make_state("memory_search"))
        assert renderer.animation.color_override == "#06b6d4"

    def test_error_red_flicker(self):
        renderer = OrbRenderer()
        renderer.apply_state(self._make_state("error"))
        assert renderer.animation.color_override == "#ef4444"
        assert renderer.animation.flicker is True

    def test_disconnected_grey(self):
        renderer = OrbRenderer()
        renderer.apply_state(self._make_state("disconnected"))
        assert renderer.animation.color_override == "#6b7280"

    def test_listening_contracted(self):
        renderer = OrbRenderer()
        renderer.apply_state(self._make_state("listening"))
        assert renderer.animation.contracted is True

    def test_speaking_speech_rhythm(self):
        renderer = OrbRenderer()
        renderer.apply_state(self._make_state("speaking"))
        assert renderer.animation.speech_rhythm is True

    def test_drift_expanded(self):
        renderer = OrbRenderer()
        renderer.apply_state(self._make_state("drift"))
        assert renderer.animation.expanded_drift is True
        assert renderer.animation.drift.radius_x == 24.0

    def test_color_override_from_state(self):
        renderer = OrbRenderer()
        renderer.apply_state(self._make_state("idle", color="#ff00ff"))
        assert renderer.animation.color_override == "#ff00ff"

    def test_brightness_scales_glow(self):
        renderer = OrbRenderer()
        renderer.apply_state(self._make_state("idle", brightness=2.0))
        assert renderer.animation.glow.ambient_max == pytest.approx(0.16, abs=0.01)
        assert renderer.animation.glow.corona_max == pytest.approx(0.24, abs=0.01)

    def test_split_groups(self):
        renderer = OrbRenderer()
        renderer.apply_state(self._make_state("split"))
        assert renderer.animation.split_groups is True


class TestSerialization:
    """to_dict produces correct JSON structure."""

    def test_to_dict_has_rings(self):
        renderer = OrbRenderer()
        d = renderer.to_dict()
        assert "rings" in d
        assert len(d["rings"]) == 5

    def test_to_dict_ring_fields(self):
        renderer = OrbRenderer()
        d = renderer.to_dict()
        ring = d["rings"][0]
        assert "id" in ring
        assert "baseRadius" in ring
        assert "baseOpacity" in ring
        assert "hue" in ring
        assert "saturation" in ring
        assert "lightness" in ring
        assert "strokeWidth" in ring
        assert "hasFill" in ring

    def test_to_dict_has_animation(self):
        renderer = OrbRenderer()
        d = renderer.to_dict()
        assert "animation" in d
        anim = d["animation"]
        assert "breatheSpeed" in anim
        assert "breatheAmplitude" in anim
        assert "driftRadiusX" in anim
        assert "syncBreathing" in anim
        assert "sequentialPulse" in anim
        assert "flicker" in anim
        assert "colorOverride" in anim

    def test_to_dict_camelcase(self):
        renderer = OrbRenderer()
        d = renderer.to_dict()
        # Verify keys are camelCase, not snake_case
        ring = d["rings"][0]
        assert "baseRadius" in ring
        assert "base_radius" not in ring
        anim = d["animation"]
        assert "breatheSpeed" in anim
        assert "breathe_speed" not in anim

    def test_to_dict_after_state_change(self):
        renderer = OrbRenderer()

        class MockAnimation:
            value = "pulse"
        class MockState:
            animation = MockAnimation()
            color = None
            brightness = 1.0

        renderer.apply_state(MockState())
        d = renderer.to_dict()
        assert d["animation"]["syncBreathing"] is True
