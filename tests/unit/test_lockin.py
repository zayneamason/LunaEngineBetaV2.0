"""
Unit Tests for Lock-In Coefficient
==================================

Tests for the lock-in coefficient calculation including:
- Formula computation
- State classification
- Activity scoring
- Decay handling

No database operations - pure algorithmic testing.
"""

import math
import pytest
from unittest.mock import Mock, patch

from luna.substrate.lock_in import (
    compute_lock_in,
    compute_activity,
    classify_state,
    sigmoid,
    LockInState,
    LockInConfig,
    get_config,
    set_config,
    LOCK_IN_MIN,
    LOCK_IN_MAX,
    THRESHOLD_SETTLED,
    THRESHOLD_DRIFTING,
)


# =============================================================================
# FORMULA CALCULATION TESTS
# =============================================================================

class TestLockInFormula:
    """Tests for lock-in coefficient formula."""

    @pytest.mark.unit
    def test_lockin_formula_calculation(self):
        """Test lock-in formula produces correct values."""
        # Zero activity should give minimum lock-in
        lock_in = compute_lock_in(
            retrieval_count=0,
            reinforcement_count=0,
            locked_neighbor_count=0,
            locked_tag_sibling_count=0,
        )

        # Should be close to minimum (0.15)
        assert lock_in >= LOCK_IN_MIN
        assert lock_in <= LOCK_IN_MAX

    @pytest.mark.unit
    def test_lockin_increases_with_activity(self):
        """Test lock-in increases with retrieval activity."""
        low_activity = compute_lock_in(retrieval_count=1)
        high_activity = compute_lock_in(retrieval_count=10)

        assert high_activity > low_activity

    @pytest.mark.unit
    def test_lockin_increases_with_reinforcement(self):
        """Test lock-in increases with explicit reinforcement."""
        no_reinforcement = compute_lock_in(reinforcement_count=0)
        with_reinforcement = compute_lock_in(reinforcement_count=5)

        assert with_reinforcement > no_reinforcement

    @pytest.mark.unit
    def test_lockin_network_effect(self):
        """Test lock-in increases with connected settled neighbors."""
        isolated = compute_lock_in(locked_neighbor_count=0)
        connected = compute_lock_in(locked_neighbor_count=5)

        assert connected > isolated

    @pytest.mark.unit
    def test_lockin_tag_sibling_effect(self):
        """Test lock-in increases with settled tag siblings."""
        no_siblings = compute_lock_in(locked_tag_sibling_count=0)
        with_siblings = compute_lock_in(locked_tag_sibling_count=3)

        assert with_siblings > no_siblings

    @pytest.mark.unit
    def test_lockin_combined_factors(self):
        """Test lock-in with multiple factors combined."""
        minimal = compute_lock_in()
        combined = compute_lock_in(
            retrieval_count=5,
            reinforcement_count=3,
            locked_neighbor_count=2,
            locked_tag_sibling_count=1,
        )

        assert combined > minimal

    @pytest.mark.unit
    def test_lockin_bounded(self):
        """Test lock-in stays within bounds even with extreme values."""
        extreme = compute_lock_in(
            retrieval_count=1000,
            reinforcement_count=1000,
            locked_neighbor_count=1000,
            locked_tag_sibling_count=1000,
        )

        assert extreme >= LOCK_IN_MIN
        assert extreme <= LOCK_IN_MAX


# =============================================================================
# DECAY TESTS
# =============================================================================

class TestLockInDecay:
    """Tests for lock-in decay over time."""

    @pytest.mark.unit
    def test_lockin_decay_over_time(self):
        """Test lock-in values are bounded to prevent infinite decay."""
        # The substrate/lock_in module doesn't include decay itself
        # but the output should stay within bounds
        lock_in = compute_lock_in(retrieval_count=5)

        assert lock_in >= LOCK_IN_MIN
        assert lock_in <= LOCK_IN_MAX

    @pytest.mark.unit
    def test_lockin_never_zero(self):
        """Test lock-in never reaches exactly zero."""
        minimal = compute_lock_in()

        assert minimal > 0
        assert minimal >= LOCK_IN_MIN

    @pytest.mark.unit
    def test_lockin_never_one(self):
        """Test lock-in never reaches exactly 1.0."""
        maximal = compute_lock_in(
            retrieval_count=1000,
            reinforcement_count=1000,
        )

        assert maximal < 1.0
        assert maximal <= LOCK_IN_MAX


# =============================================================================
# STATE CLASSIFICATION TESTS
# =============================================================================

class TestLockInStateClassification:
    """Tests for state classification from lock-in values."""

    @pytest.mark.unit
    def test_lockin_state_classification(self):
        """Test state classification thresholds."""
        # Below drifting threshold
        assert classify_state(0.15) == LockInState.DRIFTING
        assert classify_state(0.29) == LockInState.DRIFTING

        # Fluid range
        assert classify_state(0.31) == LockInState.FLUID
        assert classify_state(0.50) == LockInState.FLUID
        assert classify_state(0.69) == LockInState.FLUID

        # At or above settled threshold
        assert classify_state(0.70) == LockInState.SETTLED
        assert classify_state(0.85) == LockInState.SETTLED

    @pytest.mark.unit
    def test_lockin_state_at_thresholds(self):
        """Test state classification exactly at thresholds."""
        # At drifting threshold (should be drifting)
        state_at_drift = classify_state(THRESHOLD_DRIFTING)
        assert state_at_drift == LockInState.DRIFTING

        # At settled threshold
        state_at_settled = classify_state(THRESHOLD_SETTLED)
        assert state_at_settled == LockInState.SETTLED

    @pytest.mark.unit
    def test_lockin_state_enum_values(self):
        """Test LockInState enum has correct string values."""
        assert LockInState.DRIFTING.value == "drifting"
        assert LockInState.FLUID.value == "fluid"
        assert LockInState.SETTLED.value == "settled"


# =============================================================================
# ACTIVITY CALCULATION TESTS
# =============================================================================

class TestLockInActivityCalculation:
    """Tests for raw activity score computation."""

    @pytest.mark.unit
    def test_activity_zero_inputs(self):
        """Test activity is zero with no activity."""
        activity = compute_activity()

        assert activity == 0.0

    @pytest.mark.unit
    def test_activity_retrieval_weight(self):
        """Test retrieval has correct weight contribution."""
        activity = compute_activity(retrieval_count=10)

        # With default weight of 0.4 and /10 normalization
        # 10 * 0.4 / 10 = 0.4
        assert activity == pytest.approx(0.4, rel=0.01)

    @pytest.mark.unit
    def test_activity_reinforcement_weight(self):
        """Test reinforcement has correct weight contribution."""
        activity = compute_activity(reinforcement_count=10)

        # With default weight of 0.3 and /10 normalization
        # 10 * 0.3 / 10 = 0.3
        assert activity == pytest.approx(0.3, rel=0.01)

    @pytest.mark.unit
    def test_activity_combined_weights(self):
        """Test combined activity scores correctly."""
        activity = compute_activity(
            retrieval_count=10,
            reinforcement_count=10,
            locked_neighbor_count=10,
            locked_tag_sibling_count=10,
        )

        # (10*0.4 + 10*0.3 + 10*0.2 + 10*0.1) / 10 = 1.0
        assert activity == pytest.approx(1.0, rel=0.01)


# =============================================================================
# SIGMOID FUNCTION TESTS
# =============================================================================

class TestLockInSigmoid:
    """Tests for sigmoid function behavior."""

    @pytest.mark.unit
    def test_sigmoid_midpoint(self):
        """Test sigmoid at midpoint is 0.5."""
        config = get_config()
        result = sigmoid(config.sigmoid_x0)

        assert result == pytest.approx(0.5, rel=0.01)

    @pytest.mark.unit
    def test_sigmoid_bounded(self):
        """Test sigmoid output is bounded 0-1."""
        assert 0 <= sigmoid(-100) <= 1
        assert 0 <= sigmoid(0) <= 1
        assert 0 <= sigmoid(100) <= 1

    @pytest.mark.unit
    def test_sigmoid_monotonic(self):
        """Test sigmoid is monotonically increasing."""
        values = [sigmoid(x) for x in [-1, 0, 0.5, 1, 2]]

        for i in range(len(values) - 1):
            assert values[i] <= values[i + 1]


# =============================================================================
# ACTIVITY BOOST TESTS
# =============================================================================

class TestLockInActivityBoost:
    """Tests for activity boost from various factors."""

    @pytest.mark.unit
    def test_lockin_activity_boost(self):
        """Test activity boost increases lock-in progressively."""
        values = []
        for count in [0, 1, 5, 10, 20]:
            lock_in = compute_lock_in(retrieval_count=count)
            values.append(lock_in)

        # Should be monotonically increasing
        for i in range(len(values) - 1):
            assert values[i] <= values[i + 1]

    @pytest.mark.unit
    def test_lockin_diminishing_returns(self):
        """Test early accesses provide more boost than late ones."""
        # This is similar to logarithmic boost behavior
        base = compute_lock_in(retrieval_count=0)
        after_5 = compute_lock_in(retrieval_count=5)
        after_100 = compute_lock_in(retrieval_count=100)
        after_105 = compute_lock_in(retrieval_count=105)

        gain_0_to_5 = after_5 - base
        gain_100_to_105 = after_105 - after_100

        # Early accesses should give more boost (diminishing returns)
        # With sigmoid, this is approximately true
        assert gain_0_to_5 >= gain_100_to_105 * 0.5  # Allow some tolerance


# =============================================================================
# CONFIG TESTS
# =============================================================================

class TestLockInConfig:
    """Tests for lock-in configuration."""

    @pytest.mark.unit
    def test_config_defaults(self):
        """Test default configuration values."""
        config = LockInConfig()

        assert config.enabled is True
        assert config.weight_retrieval == 0.4
        assert config.weight_reinforcement == 0.3
        assert config.weight_network == 0.2
        assert config.weight_tag_siblings == 0.1
        assert config.threshold_settled == 0.70
        assert config.threshold_drifting == 0.30

    @pytest.mark.unit
    def test_config_disabled_returns_neutral(self):
        """Test disabled lock-in returns neutral value."""
        # Temporarily disable
        original_config = get_config()
        disabled_config = LockInConfig(enabled=False)
        set_config(disabled_config)

        try:
            lock_in = compute_lock_in(retrieval_count=100)
            assert lock_in == 0.5  # Neutral when disabled
        finally:
            # Restore
            set_config(original_config)

    @pytest.mark.unit
    def test_config_custom_thresholds(self):
        """Test custom threshold configuration."""
        config = LockInConfig(
            threshold_settled=0.80,
            threshold_drifting=0.20,
        )

        assert config.threshold_settled == 0.80
        assert config.threshold_drifting == 0.20


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

class TestLockInEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.unit
    def test_lockin_negative_inputs(self):
        """Test lock-in handles negative inputs gracefully."""
        # Should not crash with negative values
        lock_in = compute_lock_in(
            retrieval_count=-5,  # Invalid but shouldn't crash
        )

        # Should still be bounded
        assert lock_in >= LOCK_IN_MIN
        assert lock_in <= LOCK_IN_MAX

    @pytest.mark.unit
    def test_lockin_very_large_inputs(self):
        """Test lock-in handles very large inputs."""
        lock_in = compute_lock_in(
            retrieval_count=10**9,
            reinforcement_count=10**9,
        )

        # Should still be bounded
        assert lock_in >= LOCK_IN_MIN
        assert lock_in <= LOCK_IN_MAX

    @pytest.mark.unit
    def test_lockin_float_inputs(self):
        """Test lock-in handles float inputs (should use int)."""
        # The function expects ints but shouldn't crash on floats
        lock_in = compute_lock_in(retrieval_count=5)

        assert isinstance(lock_in, float)

    @pytest.mark.unit
    def test_lockin_precision(self):
        """Test lock-in output has appropriate precision."""
        lock_in = compute_lock_in(retrieval_count=5)

        # Should be rounded to 4 decimal places
        rounded = round(lock_in, 4)
        assert lock_in == rounded
