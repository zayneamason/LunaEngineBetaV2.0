"""
Integration tests for Conversation History System.

Tests the full flow:
- User messages stored in Active tier
- Rotation to Recent when budget exceeded
- Compression via Scribe
- Search on Recent tier
- History context injection into prompts
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

from luna.actors.history_manager import HistoryManagerActor, HistoryConfig


class TestHistoryIntegration:
    """Integration tests for conversation history flow."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = AsyncMock()
        db.fetchall = AsyncMock(return_value=[])
        db.fetchone = AsyncMock(return_value=None)
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_scribe(self):
        """Create mock Scribe actor for compression."""
        scribe = MagicMock()
        scribe.compress_turn = AsyncMock(return_value="Compressed summary of conversation")
        return scribe

    @pytest.fixture
    def mock_engine(self, mock_db, mock_scribe):
        """Create mock engine with matrix and scribe."""
        engine = MagicMock()
        matrix = MagicMock()
        matrix.db = mock_db
        matrix_actor = MagicMock()
        matrix_actor._matrix = matrix
        matrix_actor.is_ready = True

        def get_actor(name):
            if name == "matrix":
                return matrix_actor
            if name == "scribe":
                return mock_scribe
            return None

        engine.get_actor = get_actor
        return engine

    @pytest.fixture
    def history_manager(self, mock_engine):
        """Create HistoryManager with small budget for testing rotation."""
        config = HistoryConfig(
            max_active_tokens=100,  # Small budget to trigger rotation
            max_active_turns=3,
            compression_enabled=True
        )
        manager = HistoryManagerActor(config=config, engine=mock_engine)
        manager._is_ready = True
        return manager

    @pytest.mark.asyncio
    async def test_full_conversation_flow(self, history_manager, mock_db):
        """Test full conversation flow: add turns, rotate, compress."""
        # Setup: mock returns for sequential calls
        # add_turn does: INSERT, _check_active_budget (calls get_active_token_count), last_insert_rowid
        # When over budget: while loop calls get_oldest_active then rotates (no re-check in loop)
        mock_db.fetchone.side_effect = [
            # Turn 1: under budget (50 <= 100)
            (50, 1),   # get_active_token_count
            (1,),      # last_insert_rowid
            # Turn 2: still under budget (100 is not > 100)
            (100, 2),  # get_active_token_count
            (2,),      # last_insert_rowid
            # Turn 3: over budget (150 > 100), triggers rotation
            (150, 3),  # get_active_token_count - over budget!
            (1, "user", "Hello Luna", 50, "2026-01-20"),  # get_oldest_active for rotation
            # After rotation: 150-50=100, 3-1=2 tokens/turns - loop exits (100 not > 100)
            (3,),      # last_insert_rowid
        ]

        # Add first user turn
        turn1 = await history_manager.add_turn(
            role="user",
            content="Hello Luna",
            tokens=50
        )
        assert turn1 == 1
        assert history_manager._turns_added == 1

        # Add assistant turn
        turn2 = await history_manager.add_turn(
            role="assistant",
            content="Hello! How can I help you today?",
            tokens=50
        )
        assert turn2 == 2

        # Add another user turn - should trigger rotation
        turn3 = await history_manager.add_turn(
            role="user",
            content="Tell me about the weather",
            tokens=50
        )
        assert turn3 == 3

        # Verify rotation happened
        assert history_manager._rotations >= 1
        assert history_manager._compressions_queued >= 1

    @pytest.mark.asyncio
    async def test_backward_reference_detection(self, history_manager):
        """Test that backward references trigger Recent search."""
        # Messages with backward references
        backward_refs = [
            "what did you say earlier?",
            "remember when we discussed weather?",
            "you mentioned something before",
            "as we talked about previously",
        ]

        for msg in backward_refs:
            assert history_manager.needs_recent_search(msg) is True, f"Should detect: {msg}"

        # Messages without backward references
        no_refs = [
            "Hello!",
            "What's the weather?",
            "Tell me a joke",
            "How are you?",
        ]

        for msg in no_refs:
            assert history_manager.needs_recent_search(msg) is False, f"Should not detect: {msg}"

    @pytest.mark.asyncio
    async def test_build_history_context(self, history_manager, mock_db):
        """Test history context building."""
        # Setup: return some active turns
        mock_db.fetchall.return_value = [
            (1, "user", "Hello Luna", 10, "2026-01-20", None),
            (2, "assistant", "Hi there!", 8, "2026-01-20", None),
        ]

        # Build context for normal message (no backward ref)
        context = await history_manager.build_history_context("What's up?")

        assert "active_history" in context
        assert len(context["active_history"]) == 2
        assert context["active_history"][0]["role"] == "user"
        assert context["active_history"][1]["role"] == "assistant"
        assert context["recent_history"] == []  # No backward ref detected

    @pytest.mark.asyncio
    async def test_build_history_context_with_backward_ref(self, history_manager, mock_db):
        """Test history context includes Recent search for backward refs."""
        # Setup: return active turns
        mock_db.fetchall.side_effect = [
            # First call: get_active_window
            [
                (1, "user", "Hello Luna", 10, "2026-01-20", None),
            ],
            # Second call: search_recent (FTS5 result)
            [
                (5, "user", "Weather discussion", "Summary of weather talk", "2026-01-19", -0.8),
            ],
        ]

        # Build context with backward reference
        context = await history_manager.build_history_context("What did we discuss earlier about weather?")

        assert "active_history" in context
        assert "recent_history" in context
        # Recent search should have been triggered
        assert history_manager._searches_performed >= 1

    @pytest.mark.asyncio
    async def test_session_lifecycle(self, history_manager, mock_db):
        """Test session create/end lifecycle."""
        # Create session
        session_id = await history_manager.create_session(app_context="terminal")

        assert session_id is not None
        assert len(session_id) == 36  # UUID format
        assert history_manager._current_session_id == session_id

        # End session
        await history_manager.end_session(session_id)

        assert history_manager._current_session_id is None

    @pytest.mark.asyncio
    async def test_compression_tick_processing(self, history_manager, mock_db, mock_scribe):
        """Test that tick processes compression queue."""
        # Setup: pending compression
        mock_db.fetchone.side_effect = [
            # First: get pending compression
            (1, 10, "Long message to compress", "user"),
            # For last_insert_rowid if needed
            (1,),
        ]

        # Process tick
        await history_manager._process_compression_queue()

        # Verify Scribe was called
        mock_scribe.compress_turn.assert_called_once()

    @pytest.mark.asyncio
    async def test_stats_include_all_metrics(self, history_manager):
        """Test that stats include all expected metrics."""
        stats = history_manager.get_stats()

        expected_keys = [
            "turns_added",
            "rotations",
            "compressions_queued",
            "extractions_queued",
            "embeddings_generated",
            "searches_performed",
            "current_session",
            "is_ready",
            "config",
        ]

        for key in expected_keys:
            assert key in stats, f"Missing stat: {key}"


class TestHistoryConfigValidation:
    """Test configuration validation."""

    def test_voice_app_context(self):
        """Test voice app context configuration."""
        config = HistoryConfig(
            app_context="voice",
            max_active_tokens=500,  # Lower for voice
            max_active_turns=5
        )
        assert config.app_context == "voice"
        assert config.max_active_tokens == 500

    def test_hybrid_search_default(self):
        """Test hybrid search is default."""
        config = HistoryConfig()
        assert config.search_type == "hybrid"

    def test_compression_enabled_default(self):
        """Test compression is enabled by default."""
        config = HistoryConfig()
        assert config.compression_enabled is True
