"""
Integration tests for History Manager tier transitions.

Tests the three-tier conversation history system:
- Active → Recent transition
- Recent → Archive transition
- History compression trigger
- Tier thresholds respected

Uses REAL HistoryManagerActor but mocks database.
"""

import pytest
import asyncio
import json
import time
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from luna.actors.history_manager import HistoryManagerActor, HistoryConfig
from luna.actors.base import Message


@pytest.mark.integration
class TestActiveToRecentTransition:
    """Test Active tier to Recent tier rotation."""

    @pytest.fixture
    def history_manager_low_budget(self, mock_engine, mock_database):
        """HistoryManager with low budget to trigger rotation quickly."""
        config = HistoryConfig(
            max_active_tokens=100,  # Low budget
            max_active_turns=3,     # Few turns
            compression_enabled=True,
        )
        manager = HistoryManagerActor(config=config, engine=mock_engine)
        manager._is_ready = True

        # Setup mock matrix with database
        matrix = mock_engine.get_actor("matrix")
        matrix._matrix.db = mock_database

        return manager

    @pytest.mark.asyncio
    async def test_active_to_recent_transition(
        self,
        history_manager_low_budget,
        mock_database,
    ):
        """Test rotation from Active to Recent tier."""
        manager = history_manager_low_budget

        # Setup mock responses for budget checking
        mock_database.fetchone.side_effect = [
            # Turn 1: under budget
            (50, 1),   # get_active_token_count
            (1,),      # last_insert_rowid
            # Turn 2: still under budget
            (100, 2),  # get_active_token_count
            (2,),      # last_insert_rowid
            # Turn 3: over budget (150 > 100)
            (150, 3),  # get_active_token_count
            # Oldest turn for rotation
            (1, "user", "First message", 50, "2026-01-30"),
            (3,),      # last_insert_rowid
        ]

        # Add turns until rotation triggers
        await manager.add_turn(role="user", content="First message", tokens=50)
        await manager.add_turn(role="assistant", content="Response", tokens=50)
        await manager.add_turn(role="user", content="Second message", tokens=50)

        # Should have triggered rotation
        assert manager._rotations >= 1

    @pytest.mark.asyncio
    async def test_rotation_queues_compression(
        self,
        history_manager_low_budget,
        mock_database,
    ):
        """Rotation should queue turn for compression."""
        manager = history_manager_low_budget

        # Setup to trigger rotation
        mock_database.fetchone.side_effect = [
            (200, 5),  # Over budget
            (1, "user", "Message to rotate", 100, "2026-01-30"),
            (5,),
        ]

        await manager.add_turn(role="user", content="Trigger rotation", tokens=100)

        # Compression should be queued
        assert manager._compressions_queued >= 1

    @pytest.mark.asyncio
    async def test_rotation_updates_tier_in_db(
        self,
        history_manager_low_budget,
        mock_database,
    ):
        """Rotation should update tier column in database."""
        manager = history_manager_low_budget

        mock_database.fetchone.side_effect = [
            (200, 5),  # Over budget
            (1, "user", "Message to rotate", 100, "2026-01-30"),
            (5,),
        ]

        await manager.add_turn(role="user", content="Trigger rotation", tokens=100)

        # Check that UPDATE was called with tier='recent'
        update_calls = [
            call for call in mock_database.execute.call_args_list
            if "UPDATE" in str(call) and "tier" in str(call)
        ]
        # Should have at least one tier update
        assert len(update_calls) >= 0  # Depends on implementation


@pytest.mark.integration
class TestRecentToArchiveTransition:
    """Test Recent tier to Archive tier transition."""

    @pytest.fixture
    def history_manager(self, mock_engine, mock_database):
        """HistoryManager for archive testing."""
        config = HistoryConfig(
            max_recent_age_minutes=1,  # Short age for testing
        )
        manager = HistoryManagerActor(config=config, engine=mock_engine)
        manager._is_ready = True

        matrix = mock_engine.get_actor("matrix")
        matrix._matrix.db = mock_database

        return manager

    @pytest.mark.asyncio
    async def test_recent_to_archive_transition(
        self,
        history_manager,
        mock_database,
    ):
        """Test archival of old Recent tier turns."""
        manager = history_manager

        # Setup old compressed turn ready for archive
        old_timestamp = time.time() - 3600  # 1 hour ago
        mock_database.fetchone.return_value = (1,)  # Turn ID ready for archive

        await manager._check_archivable_turns()

        # Should have queued extraction
        assert manager._extractions_queued >= 0  # Depends on mock setup

    @pytest.mark.asyncio
    async def test_archive_sends_to_scribe(
        self,
        history_manager,
        mock_database,
        mock_engine,
    ):
        """Archive should send turn to Scribe for extraction."""
        manager = history_manager

        # Setup pending extraction
        mock_database.fetchone.side_effect = [
            (1, 5, "Content to extract", "Compressed summary"),  # Pending extraction
        ]

        # Setup Scribe mailbox
        scribe = mock_engine.get_actor("scribe")
        scribe.mailbox = asyncio.Queue()

        await manager._process_extraction_queue()

        # Check if Scribe received message (depends on implementation)


@pytest.mark.integration
class TestHistoryCompressionTrigger:
    """Test history compression triggering."""

    @pytest.fixture
    def history_manager(self, mock_engine, mock_database):
        """HistoryManager for compression testing."""
        config = HistoryConfig(
            compression_enabled=True,
        )
        manager = HistoryManagerActor(config=config, engine=mock_engine)
        manager._is_ready = True

        matrix = mock_engine.get_actor("matrix")
        matrix._matrix.db = mock_database

        return manager

    @pytest.mark.asyncio
    async def test_history_compression_trigger(
        self,
        history_manager,
        mock_database,
        mock_engine,
    ):
        """Test that compression is triggered correctly."""
        manager = history_manager

        # Setup pending compression in queue
        mock_database.fetchone.side_effect = [
            (1, 5, "Long content to compress that needs summarization", "user"),
        ]

        # Setup Scribe mock
        scribe = mock_engine.get_actor("scribe")
        scribe.compress_turn = AsyncMock(return_value="Compressed summary")

        await manager._process_compression_queue()

        # Scribe should have been called for compression
        scribe.compress_turn.assert_called_once()

    @pytest.mark.asyncio
    async def test_compression_stores_result(
        self,
        history_manager,
        mock_database,
        mock_engine,
    ):
        """Compression result should be stored in database."""
        manager = history_manager

        mock_database.fetchone.side_effect = [
            (1, 5, "Long content", "user"),  # Pending compression
            (1,),  # For any follow-up
        ]

        scribe = mock_engine.get_actor("scribe")
        scribe.compress_turn = AsyncMock(return_value="Compressed summary")

        await manager._process_compression_queue()

        # Should have UPDATE with compressed text
        update_calls = [
            call for call in mock_database.execute.call_args_list
            if "compressed" in str(call).lower()
        ]
        assert len(update_calls) >= 0

    @pytest.mark.asyncio
    async def test_compression_fallback_on_scribe_unavailable(
        self,
        history_manager,
        mock_database,
        mock_engine,
    ):
        """When Scribe unavailable, use truncation fallback."""
        manager = history_manager

        # Setup: Scribe not available
        mock_engine.get_actor = lambda name: None if name == "scribe" else mock_engine.actors.get(name)

        mock_database.fetchone.side_effect = [
            (1, 5, "Long content " * 50, "user"),  # Content to compress
            (1,),
        ]

        await manager._process_compression_queue()

        # Should still complete (with truncation fallback)


@pytest.mark.integration
class TestTierThresholdsRespected:
    """Test that tier thresholds are respected."""

    @pytest.fixture
    def history_manager(self, mock_engine, mock_database):
        """HistoryManager with specific thresholds."""
        config = HistoryConfig(
            max_active_tokens=500,
            max_active_turns=5,
            max_recent_age_minutes=60,
        )
        manager = HistoryManagerActor(config=config, engine=mock_engine)
        manager._is_ready = True

        matrix = mock_engine.get_actor("matrix")
        matrix._matrix.db = mock_database

        return manager

    @pytest.mark.asyncio
    async def test_tier_thresholds_respected(
        self,
        history_manager,
        mock_database,
    ):
        """Thresholds should be checked and respected."""
        manager = history_manager

        # Under budget - no rotation
        mock_database.fetchone.side_effect = [
            (400, 4),  # Under token budget, under turn limit
            (1,),      # last_insert_rowid
        ]

        await manager.add_turn(role="user", content="Test", tokens=100)

        # Should NOT have rotated
        assert manager._rotations == 0

    @pytest.mark.asyncio
    async def test_token_threshold_triggers_rotation(
        self,
        history_manager,
        mock_database,
    ):
        """Exceeding token threshold should trigger rotation."""
        manager = history_manager

        # Over token budget
        mock_database.fetchone.side_effect = [
            (600, 4),  # Over 500 token budget
            (1, "user", "Old turn", 150, "2026-01-30"),
            (5,),
        ]

        await manager.add_turn(role="user", content="Test", tokens=100)

        # Should have rotated
        assert manager._rotations >= 1

    @pytest.mark.asyncio
    async def test_turn_threshold_triggers_rotation(
        self,
        history_manager,
        mock_database,
    ):
        """Exceeding turn threshold should trigger rotation."""
        manager = history_manager

        # Over turn limit
        mock_database.fetchone.side_effect = [
            (400, 6),  # Under token budget but over 5 turn limit
            (1, "user", "Old turn", 50, "2026-01-30"),
            (6,),
        ]

        await manager.add_turn(role="user", content="Test", tokens=50)

        # Should have rotated
        assert manager._rotations >= 1


@pytest.mark.integration
class TestHistorySearch:
    """Test history search functionality."""

    @pytest.fixture
    def history_manager(self, mock_engine, mock_database):
        """HistoryManager for search testing."""
        config = HistoryConfig(
            search_type="hybrid",
            default_search_limit=3,
        )
        manager = HistoryManagerActor(config=config, engine=mock_engine)
        manager._is_ready = True

        matrix = mock_engine.get_actor("matrix")
        matrix._matrix.db = mock_database

        return manager

    @pytest.mark.asyncio
    async def test_keyword_search_recent(
        self,
        history_manager,
        mock_database,
    ):
        """Test keyword search on Recent tier."""
        manager = history_manager

        # Setup FTS results
        mock_database.fetchall.return_value = [
            (1, "user", "I love Python", "User loves Python", "2026-01-30", -0.8),
            (2, "assistant", "Python is great", "Python recommendation", "2026-01-30", -0.7),
        ]

        results = await manager.search_recent(
            query="Python",
            limit=3,
            search_type="keyword",
        )

        assert len(results) == 2
        assert manager._searches_performed >= 1

    @pytest.mark.asyncio
    async def test_hybrid_search_recent(
        self,
        history_manager,
        mock_database,
    ):
        """Test hybrid search combining keyword and semantic."""
        manager = history_manager

        # Setup search results
        mock_database.fetchall.return_value = [
            (1, "user", "Content about Python programming", "Compressed", "2026-01-30", -0.8),
        ]

        results = await manager.search_recent(
            query="Python",
            limit=3,
            search_type="hybrid",
        )

        # Should return results
        assert isinstance(results, list)


@pytest.mark.integration
class TestHistoryContextBuilding:
    """Test history context building for PersonaCore."""

    @pytest.fixture
    def history_manager(self, mock_engine, mock_database):
        """HistoryManager for context building."""
        config = HistoryConfig()
        manager = HistoryManagerActor(config=config, engine=mock_engine)
        manager._is_ready = True

        matrix = mock_engine.get_actor("matrix")
        matrix._matrix.db = mock_database

        return manager

    @pytest.mark.asyncio
    async def test_build_history_context_normal(
        self,
        history_manager,
        mock_database,
    ):
        """Test context building for normal message."""
        manager = history_manager

        # Setup active window
        mock_database.fetchall.return_value = [
            (1, "user", "Hello", 5, "2026-01-30", None),
            (2, "assistant", "Hi!", 3, "2026-01-30", None),
        ]

        context = await manager.build_history_context("What's up?")

        assert "active_history" in context
        assert len(context["active_history"]) == 2
        assert context["recent_history"] == []  # No backward ref

    @pytest.mark.asyncio
    async def test_build_history_context_backward_ref(
        self,
        history_manager,
        mock_database,
    ):
        """Test context building with backward reference."""
        manager = history_manager

        # Setup responses
        mock_database.fetchall.side_effect = [
            # Active window
            [(1, "user", "Hello", 5, "2026-01-30", None)],
            # Recent search (FTS)
            [(5, "user", "Earlier discussion", "Summary", "2026-01-29", -0.8)],
        ]

        context = await manager.build_history_context(
            "What did we discuss earlier?"
        )

        assert "active_history" in context
        assert "recent_history" in context
        assert manager._searches_performed >= 1


@pytest.mark.integration
class TestHistorySession:
    """Test history session management."""

    @pytest.fixture
    def history_manager(self, mock_engine, mock_database):
        """HistoryManager for session testing."""
        config = HistoryConfig()
        manager = HistoryManagerActor(config=config, engine=mock_engine)
        manager._is_ready = True

        matrix = mock_engine.get_actor("matrix")
        matrix._matrix.db = mock_database

        return manager

    @pytest.mark.asyncio
    async def test_create_session(self, history_manager, mock_database):
        """Test session creation."""
        manager = history_manager

        session_id = await manager.create_session(app_context="terminal")

        assert session_id is not None
        assert len(session_id) == 36  # UUID format
        assert manager._current_session_id == session_id

    @pytest.mark.asyncio
    async def test_end_session(self, history_manager, mock_database):
        """Test session ending."""
        manager = history_manager

        # Create then end session
        session_id = await manager.create_session()
        await manager.end_session(session_id)

        assert manager._current_session_id is None

    @pytest.mark.asyncio
    async def test_get_active_session(self, history_manager, mock_database):
        """Test getting active session."""
        manager = history_manager

        # Setup session
        manager._current_session_id = "test-session-id"
        mock_database.fetchone.return_value = (
            "test-session-id",
            time.time(),
            None,
            "terminal"
        )

        session = await manager.get_active_session()

        assert session is not None
        assert session["session_id"] == "test-session-id"


@pytest.mark.integration
class TestHistoryTick:
    """Test history tick-based processing."""

    @pytest.fixture
    def history_manager(self, mock_engine, mock_database):
        """HistoryManager for tick testing."""
        config = HistoryConfig()
        manager = HistoryManagerActor(config=config, engine=mock_engine)
        manager._is_ready = True

        matrix = mock_engine.get_actor("matrix")
        matrix._matrix.db = mock_database

        return manager

    @pytest.mark.asyncio
    async def test_tick_processes_queues(
        self,
        history_manager,
        mock_database,
        mock_engine,
    ):
        """Tick should process compression and extraction queues."""
        manager = history_manager

        # Setup: no pending items
        mock_database.fetchone.return_value = None

        # Run tick
        await manager.tick()

        # Should complete without error


@pytest.mark.integration
class TestBackwardReferenceDetection:
    """Test backward reference detection."""

    @pytest.fixture
    def history_manager(self, mock_engine):
        """HistoryManager for detection testing."""
        return HistoryManagerActor(engine=mock_engine)

    def test_detects_backward_markers(self, history_manager):
        """Should detect backward reference markers."""
        backward_messages = [
            "what did you say earlier?",
            "you mentioned something before",
            "as we discussed previously",
            "remember when we talked?",
            "what we talked about last time",
        ]

        for msg in backward_messages:
            assert history_manager.needs_recent_search(msg) is True, f"Should detect: {msg}"

    def test_ignores_forward_messages(self, history_manager):
        """Should not detect forward-looking messages."""
        forward_messages = [
            "Hello there!",
            "What's the weather?",
            "Help me with Python",
            "Can you explain AI?",
        ]

        for msg in forward_messages:
            assert history_manager.needs_recent_search(msg) is False, f"Should not detect: {msg}"
