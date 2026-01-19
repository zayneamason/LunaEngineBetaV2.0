"""Tests for lock-in coefficient calculation."""

import pytest
from luna.substrate.lock_in import (
    compute_lock_in,
    compute_activity,
    classify_state,
    LockInState,
    get_state_emoji,
    LOCK_IN_MIN,
    LOCK_IN_MAX,
)


class TestLockInComputation:
    """Test lock-in coefficient calculations."""

    def test_new_node_starts_fluid(self):
        """A brand new node should start as fluid (potentially useful)."""
        lock_in = compute_lock_in(
            retrieval_count=0,
            reinforcement_count=0,
            locked_neighbor_count=0,
            locked_tag_sibling_count=0,
        )
        assert lock_in >= LOCK_IN_MIN
        state = classify_state(lock_in)
        assert state == LockInState.FLUID  # New nodes start fluid, not drifting

    def test_high_access_increases_lock_in(self):
        """Frequent access should increase lock-in."""
        low_access = compute_lock_in(retrieval_count=1)
        high_access = compute_lock_in(retrieval_count=20)
        assert high_access > low_access

    def test_reinforcement_increases_lock_in(self):
        """Explicit reinforcement should increase lock-in."""
        unreinforced = compute_lock_in(retrieval_count=5)
        reinforced = compute_lock_in(retrieval_count=5, reinforcement_count=3)
        assert reinforced > unreinforced

    def test_network_effects(self):
        """Connected to settled nodes should increase lock-in."""
        isolated = compute_lock_in(retrieval_count=5)
        connected = compute_lock_in(retrieval_count=5, locked_neighbor_count=5)
        assert connected > isolated

    def test_lock_in_bounded(self):
        """Lock-in should never exceed bounds."""
        # Even with extreme values
        lock_in = compute_lock_in(
            retrieval_count=10000,
            reinforcement_count=10000,
            locked_neighbor_count=10000,
            locked_tag_sibling_count=10000,
        )
        assert lock_in <= LOCK_IN_MAX
        assert lock_in >= LOCK_IN_MIN


class TestStateClassification:
    """Test lock-in state classification."""

    def test_drifting_classification(self):
        """Low lock-in should be classified as drifting."""
        state = classify_state(0.20)
        assert state == LockInState.DRIFTING

    def test_fluid_classification(self):
        """Medium lock-in should be classified as fluid."""
        state = classify_state(0.50)
        assert state == LockInState.FLUID

    def test_settled_classification(self):
        """High lock-in should be classified as settled."""
        state = classify_state(0.75)
        assert state == LockInState.SETTLED

    def test_boundary_drifting_to_fluid(self):
        """Test boundary between drifting and fluid."""
        assert classify_state(0.29) == LockInState.DRIFTING
        assert classify_state(0.31) == LockInState.FLUID

    def test_boundary_fluid_to_settled(self):
        """Test boundary between fluid and settled."""
        assert classify_state(0.69) == LockInState.FLUID
        assert classify_state(0.71) == LockInState.SETTLED


class TestEmoji:
    """Test state emoji display."""

    def test_emojis_exist(self):
        """All states should have emojis."""
        assert get_state_emoji(LockInState.DRIFTING) == "🟠"
        assert get_state_emoji(LockInState.FLUID) == "🔵"
        assert get_state_emoji(LockInState.SETTLED) == "🟢"


class TestActivity:
    """Test raw activity computation."""

    def test_activity_zero_with_no_inputs(self):
        """Activity should be near zero with no inputs."""
        activity = compute_activity()
        assert activity == 0.0

    def test_activity_increases_with_access(self):
        """Activity should increase with retrieval count."""
        a1 = compute_activity(retrieval_count=1)
        a2 = compute_activity(retrieval_count=10)
        assert a2 > a1
