"""
Unit Tests for HistoryManagerActor
==================================

Tests for three-tier conversation history management including
tier rotation, compression queuing, and session management.

All database operations are mocked - no real SQLite calls.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from luna.actors.base import Message
from luna.actors.history_manager import HistoryManagerActor, HistoryConfig


# =============================================================================
# TURN MANAGEMENT TESTS
# =============================================================================

class TestHistoryManagerTurns:
    """Tests for conversation turn management."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_adds_turns(self, mock_history_manager_actor, mock_matrix):
        """Test HistoryManager adds turns correctly."""
        mock_matrix.db = AsyncMock()
        mock_matrix.db.execute = AsyncMock()
        # Return tuple with both total_tokens and turn_count
        mock_matrix.db.fetchone = AsyncMock(return_value=(0, 0))
        mock_matrix.db.fetchall = AsyncMock(return_value=[])

        # Mock the _get_matrix method
        async def mock_get_matrix():
            return mock_matrix
        mock_history_manager_actor._get_matrix = mock_get_matrix

        # Clear any session requirement
        mock_history_manager_actor._current_session_id = "test-session"

        turn_id = await mock_history_manager_actor.add_turn(
            role="user",
            content="Hello Luna",
            tokens=10,
        )

        assert mock_history_manager_actor._turns_added >= 1
        mock_matrix.db.execute.assert_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_creates_session_if_needed(self, mock_history_manager_actor, mock_matrix):
        """Test HistoryManager creates session when adding turn without one."""
        mock_matrix.db = AsyncMock()
        mock_matrix.db.execute = AsyncMock()
        # Return tuple with both total_tokens and turn_count
        mock_matrix.db.fetchone = AsyncMock(return_value=(0, 0))
        mock_matrix.db.fetchall = AsyncMock(return_value=[])

        async def mock_get_matrix():
            return mock_matrix
        mock_history_manager_actor._get_matrix = mock_get_matrix

        # No current session
        mock_history_manager_actor._current_session_id = None

        await mock_history_manager_actor.add_turn(
            role="user",
            content="Hello",
            tokens=5,
        )

        # Session should have been created
        assert mock_history_manager_actor._current_session_id is not None


# =============================================================================
# TIER MANAGEMENT TESTS
# =============================================================================

class TestHistoryManagerTiers:
    """Tests for tier rotation between Active, Recent, and Archive."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_tiers_correctly(self, mock_history_manager_actor, mock_matrix):
        """Test HistoryManager rotates tiers when budget exceeded."""
        mock_history_manager_actor.config.max_active_tokens = 100
        mock_history_manager_actor.config.max_active_turns = 3

        mock_matrix.db = AsyncMock()
        mock_matrix.db.execute = AsyncMock()

        # Simulate token count over budget
        async def mock_get_token_count(*args):
            return {"total_tokens": 150, "turn_count": 4}

        mock_history_manager_actor.get_active_token_count = mock_get_token_count

        # Simulate oldest turn
        async def mock_get_oldest(*args):
            return {
                "turn_id": 1,
                "role": "user",
                "content": "Old message",
                "tokens": 50,
            }
        mock_history_manager_actor.get_oldest_active_turn = mock_get_oldest

        async def mock_get_matrix():
            return mock_matrix
        mock_history_manager_actor._get_matrix = mock_get_matrix

        # Mock rotate method
        mock_history_manager_actor._rotate_turn_tier = AsyncMock()
        mock_history_manager_actor.queue_compression = AsyncMock()

        await mock_history_manager_actor._check_active_budget("test-session")

        # Should have triggered rotation
        mock_history_manager_actor._rotate_turn_tier.assert_called()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_active_to_recent_transition(self, mock_history_manager_actor, mock_matrix):
        """Test turn moves from Active to Recent tier."""
        mock_matrix.db = AsyncMock()
        mock_matrix.db.execute = AsyncMock()

        async def mock_get_matrix():
            return mock_matrix
        mock_history_manager_actor._get_matrix = mock_get_matrix

        await mock_history_manager_actor._rotate_turn_tier(
            turn_id=1,
            new_tier="recent"
        )

        # Verify update was called with correct tier
        call_args = mock_matrix.db.execute.call_args
        assert call_args is not None
        assert "recent" in str(call_args)


# =============================================================================
# ACTIVE WINDOW TESTS
# =============================================================================

class TestHistoryManagerActiveWindow:
    """Tests for Active Window retrieval."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_gets_active_window(self, mock_history_manager_actor, mock_matrix):
        """Test HistoryManager retrieves Active Window turns."""
        mock_matrix.db = AsyncMock()
        mock_matrix.db.fetchall = AsyncMock(return_value=[
            (1, "user", "Hello", 10, "2024-01-01", None),
            (2, "assistant", "Hi there!", 8, "2024-01-01", None),
        ])

        async def mock_get_matrix():
            return mock_matrix
        mock_history_manager_actor._get_matrix = mock_get_matrix

        turns = await mock_history_manager_actor.get_active_window()

        assert len(turns) == 2
        assert turns[0]["role"] == "user"
        assert turns[1]["role"] == "assistant"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_active_window_empty_no_matrix(self, mock_history_manager_actor):
        """Test Active Window returns empty without matrix."""
        async def mock_get_matrix():
            return None
        mock_history_manager_actor._get_matrix = mock_get_matrix

        turns = await mock_history_manager_actor.get_active_window()

        assert turns == []


# =============================================================================
# SEARCH TESTS
# =============================================================================

class TestHistoryManagerSearch:
    """Tests for Recent tier search."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_searches_recent(self, mock_history_manager_actor, mock_matrix):
        """Test HistoryManager searches Recent tier."""
        mock_matrix.db = AsyncMock()
        mock_matrix.db.fetchall = AsyncMock(return_value=[
            (1, "user", "I mentioned Python", None, "2024-01-01", -0.8),
        ])

        async def mock_get_matrix():
            return mock_matrix
        mock_history_manager_actor._get_matrix = mock_get_matrix

        results = await mock_history_manager_actor.search_recent(
            query="Python",
            limit=5,
            search_type="keyword"
        )

        assert len(results) == 1
        assert mock_history_manager_actor._searches_performed >= 1

    @pytest.mark.unit
    def test_history_detects_backward_reference(self, mock_history_manager_actor):
        """Test HistoryManager detects backward references."""
        # Should trigger search
        assert mock_history_manager_actor.needs_recent_search("What did you say earlier?")
        assert mock_history_manager_actor.needs_recent_search("Remember when we discussed that?")
        assert mock_history_manager_actor.needs_recent_search("You mentioned something before")

        # Should not trigger search
        assert not mock_history_manager_actor.needs_recent_search("Hello there")
        assert not mock_history_manager_actor.needs_recent_search("What is Python?")


# =============================================================================
# SESSION MANAGEMENT TESTS
# =============================================================================

class TestHistoryManagerSession:
    """Tests for session management."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_creates_session(self, mock_history_manager_actor, mock_matrix):
        """Test HistoryManager creates new session."""
        mock_matrix.db = AsyncMock()
        mock_matrix.db.execute = AsyncMock()

        async def mock_get_matrix():
            return mock_matrix
        mock_history_manager_actor._get_matrix = mock_get_matrix

        session_id = await mock_history_manager_actor.create_session(
            app_context="test"
        )

        assert session_id is not None
        assert len(session_id) > 0
        assert mock_history_manager_actor._current_session_id == session_id

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_ends_session(self, mock_history_manager_actor, mock_matrix):
        """Test HistoryManager ends session."""
        mock_matrix.db = AsyncMock()
        mock_matrix.db.execute = AsyncMock()

        async def mock_get_matrix():
            return mock_matrix
        mock_history_manager_actor._get_matrix = mock_get_matrix

        mock_history_manager_actor._current_session_id = "session-to-end"

        await mock_history_manager_actor.end_session()

        assert mock_history_manager_actor._current_session_id is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_gets_active_session(self, mock_history_manager_actor, mock_matrix):
        """Test HistoryManager retrieves active session."""
        mock_history_manager_actor._current_session_id = "active-session"
        mock_matrix.db = AsyncMock()
        mock_matrix.db.fetchone = AsyncMock(return_value=(
            "active-session", 1704067200, None, "terminal"
        ))

        async def mock_get_matrix():
            return mock_matrix
        mock_history_manager_actor._get_matrix = mock_get_matrix

        session = await mock_history_manager_actor.get_active_session()

        assert session is not None
        assert session["session_id"] == "active-session"


# =============================================================================
# COMPRESSION QUEUE TESTS
# =============================================================================

class TestHistoryManagerCompression:
    """Tests for compression queue management."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_queues_compression(self, mock_history_manager_actor, mock_matrix):
        """Test HistoryManager queues turns for compression."""
        mock_matrix.db = AsyncMock()
        mock_matrix.db.execute = AsyncMock()

        async def mock_get_matrix():
            return mock_matrix
        mock_history_manager_actor._get_matrix = mock_get_matrix

        await mock_history_manager_actor.queue_compression(turn_id=1)

        assert mock_history_manager_actor._compressions_queued >= 1
        mock_matrix.db.execute.assert_called()


# =============================================================================
# EXTRACTION QUEUE TESTS
# =============================================================================

class TestHistoryManagerExtraction:
    """Tests for extraction queue management."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_queues_extraction(self, mock_history_manager_actor, mock_matrix):
        """Test HistoryManager queues turns for extraction."""
        mock_matrix.db = AsyncMock()
        mock_matrix.db.execute = AsyncMock()

        async def mock_get_matrix():
            return mock_matrix
        mock_history_manager_actor._get_matrix = mock_get_matrix

        await mock_history_manager_actor.queue_extraction(turn_id=1)

        assert mock_history_manager_actor._extractions_queued >= 1


# =============================================================================
# TOKEN COUNT TESTS
# =============================================================================

class TestHistoryManagerTokenCount:
    """Tests for token count tracking."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_gets_token_count(self, mock_history_manager_actor, mock_matrix):
        """Test HistoryManager gets Active tier token count."""
        mock_matrix.db = AsyncMock()
        mock_matrix.db.fetchone = AsyncMock(return_value=(500, 5))

        async def mock_get_matrix():
            return mock_matrix
        mock_history_manager_actor._get_matrix = mock_get_matrix

        result = await mock_history_manager_actor.get_active_token_count()

        assert result["total_tokens"] == 500
        assert result["turn_count"] == 5

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_token_count_no_matrix(self, mock_history_manager_actor):
        """Test token count returns zeros without matrix."""
        async def mock_get_matrix():
            return None
        mock_history_manager_actor._get_matrix = mock_get_matrix

        result = await mock_history_manager_actor.get_active_token_count()

        assert result["total_tokens"] == 0
        assert result["turn_count"] == 0


# =============================================================================
# STATS TESTS
# =============================================================================

class TestHistoryManagerStats:
    """Tests for history statistics."""

    @pytest.mark.unit
    def test_history_tracks_stats(self, mock_history_manager_actor):
        """Test HistoryManager tracks statistics."""
        stats = mock_history_manager_actor.get_stats()

        assert "turns_added" in stats
        assert "rotations" in stats
        assert "compressions_queued" in stats
        assert "extractions_queued" in stats
        assert "searches_performed" in stats
        assert "current_session" in stats
        assert "is_ready" in stats
        assert "config" in stats

    @pytest.mark.unit
    def test_history_initial_stats(self, mock_history_manager_actor):
        """Test HistoryManager starts with expected initial state."""
        stats = mock_history_manager_actor.get_stats()

        assert stats["turns_added"] == 0
        assert stats["rotations"] == 0
        assert stats["is_ready"] is True  # We set this in fixture


# =============================================================================
# CONTEXT BUILDING TESTS
# =============================================================================

class TestHistoryManagerContextBuilding:
    """Tests for context building for prompts."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_builds_context(self, mock_history_manager_actor, mock_matrix):
        """Test HistoryManager builds context for prompts."""
        mock_matrix.db = AsyncMock()
        mock_matrix.db.fetchall = AsyncMock(return_value=[
            (1, "user", "Hello", 10, "2024-01-01", None),
        ])

        async def mock_get_matrix():
            return mock_matrix
        mock_history_manager_actor._get_matrix = mock_get_matrix

        context = await mock_history_manager_actor.build_history_context(
            message="What is Python?",
        )

        assert "active_history" in context
        assert "recent_history" in context
        assert "total_tokens" in context

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_context_with_backward_ref(self, mock_history_manager_actor, mock_matrix):
        """Test context building with backward reference triggers search."""
        mock_matrix.db = AsyncMock()
        mock_matrix.db.fetchall = AsyncMock(return_value=[])

        async def mock_get_matrix():
            return mock_matrix
        mock_history_manager_actor._get_matrix = mock_get_matrix

        context = await mock_history_manager_actor.build_history_context(
            message="What did you say earlier?",  # Backward reference
        )

        # Should have searched recent (even if empty)
        assert "recent_history" in context


# =============================================================================
# MESSAGE HANDLING TESTS
# =============================================================================

class TestHistoryManagerMessageHandling:
    """Tests for mailbox message handling."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_handles_add_turn_message(self, mock_history_manager_actor, mock_matrix):
        """Test HistoryManager handles add_turn message."""
        mock_matrix.db = AsyncMock()
        mock_matrix.db.execute = AsyncMock()
        mock_matrix.db.fetchone = AsyncMock(return_value=(1,))
        mock_matrix.db.fetchall = AsyncMock(return_value=[])

        async def mock_get_matrix():
            return mock_matrix
        mock_history_manager_actor._get_matrix = mock_get_matrix

        msg = Message(
            type="add_turn",
            payload={
                "role": "user",
                "content": "Test message",
                "tokens": 10,
            }
        )

        await mock_history_manager_actor.handle(msg)

        assert mock_history_manager_actor._turns_added >= 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_history_handles_unknown_message(self, mock_history_manager_actor):
        """Test HistoryManager logs warning for unknown message types."""
        msg = Message(type="unknown_type", payload={})

        # Should not raise, just log warning
        await mock_history_manager_actor.handle(msg)
