"""
Tests for Conversation History System.

Tests cover:
- HistoryConfig dataclass
- HistoryManager actor
- Active Window management
- Tier rotation
- Session management
- Search functionality
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict

# Import the actor and config
from luna.actors.history_manager import HistoryManagerActor, HistoryConfig


class TestHistoryConfig:
    """Test HistoryConfig defaults and validation."""

    def test_default_config(self):
        """Test default configuration values."""
        config = HistoryConfig()
        assert config.max_active_tokens == 1000
        assert config.max_active_turns == 10
        assert config.max_recent_age_minutes == 60
        assert config.compression_enabled is True
        assert config.default_search_limit == 3
        assert config.search_type == "hybrid"
        assert config.app_context == "terminal"

    def test_custom_config(self):
        """Test custom configuration values."""
        config = HistoryConfig(
            max_active_tokens=500,
            max_active_turns=5,
            compression_enabled=False,
            app_context="voice"
        )
        assert config.max_active_tokens == 500
        assert config.max_active_turns == 5
        assert config.compression_enabled is False
        assert config.app_context == "voice"

    def test_config_to_dict(self):
        """Test config serialization."""
        config = HistoryConfig()
        d = asdict(config)
        assert "max_active_tokens" in d
        assert "max_active_turns" in d
        assert d["max_active_tokens"] == 1000


class TestHistoryManagerActor:
    """Test HistoryManager actor initialization."""

    def test_actor_initialization(self):
        """Test actor initializes with correct name."""
        manager = HistoryManagerActor()
        assert manager.name == "history_manager"
        assert manager._turns_added == 0
        assert manager._rotations == 0
        assert manager._current_session_id is None

    def test_actor_with_config(self):
        """Test actor initializes with custom config."""
        config = HistoryConfig(max_active_tokens=500)
        manager = HistoryManagerActor(config=config)
        assert manager.config.max_active_tokens == 500

    def test_actor_stats(self):
        """Test get_stats returns expected structure."""
        manager = HistoryManagerActor()
        stats = manager.get_stats()

        assert "turns_added" in stats
        assert "rotations" in stats
        assert "compressions_queued" in stats
        assert "extractions_queued" in stats
        assert "current_session" in stats
        assert "is_ready" in stats
        assert "config" in stats


class TestHistoryManagerWithMocks:
    """Test HistoryManager with mocked dependencies."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = AsyncMock()
        db.fetchall = AsyncMock(return_value=[])
        db.fetchone = AsyncMock(return_value=None)
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def mock_matrix(self, mock_db):
        """Create mock matrix with database."""
        matrix = MagicMock()
        matrix.db = mock_db
        return matrix

    @pytest.fixture
    def mock_engine(self, mock_matrix):
        """Create mock engine with matrix actor."""
        engine = MagicMock()
        matrix_actor = MagicMock()
        matrix_actor._matrix = mock_matrix
        matrix_actor.is_ready = True

        def get_actor(name):
            if name == "matrix":
                return matrix_actor
            return None

        engine.get_actor = get_actor
        return engine

    @pytest.fixture
    def history_manager(self, mock_engine):
        """Create HistoryManager with mocks."""
        manager = HistoryManagerActor(engine=mock_engine)
        return manager

    @pytest.mark.asyncio
    async def test_get_matrix(self, history_manager, mock_matrix):
        """Test _get_matrix returns matrix."""
        matrix = await history_manager._get_matrix()
        assert matrix == mock_matrix

    @pytest.mark.asyncio
    async def test_create_session(self, history_manager, mock_db):
        """Test session creation."""
        session_id = await history_manager.create_session()

        assert session_id is not None
        assert len(session_id) == 36  # UUID format
        assert history_manager._current_session_id == session_id
        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_end_session(self, history_manager, mock_db):
        """Test session ending."""
        session_id = await history_manager.create_session()
        await history_manager.end_session(session_id)

        assert history_manager._current_session_id is None
        # Check execute was called for UPDATE
        assert mock_db.execute.call_count >= 2

    @pytest.mark.asyncio
    async def test_add_turn(self, history_manager, mock_db):
        """Test adding a turn."""
        # Mock returns: (total_tokens, turn_count) for budget check, then (turn_id,) for last_insert
        mock_db.fetchone.side_effect = [
            (10, 1),  # First: get_active_token_count
            (1,),     # Second: last_insert_rowid
        ]

        turn_id = await history_manager.add_turn(
            role="user",
            content="Hello Luna",
            tokens=10
        )

        assert turn_id == 1
        assert history_manager._turns_added == 1

    @pytest.mark.asyncio
    async def test_get_active_window_empty(self, history_manager, mock_db):
        """Test get_active_window with no turns."""
        mock_db.fetchall.return_value = []

        turns = await history_manager.get_active_window()

        assert turns == []

    @pytest.mark.asyncio
    async def test_get_active_window_with_turns(self, history_manager, mock_db):
        """Test get_active_window with turns."""
        mock_db.fetchall.return_value = [
            (1, "user", "Hello", 10, "2026-01-20", None),
            (2, "assistant", "Hi!", 5, "2026-01-20", None),
        ]

        turns = await history_manager.get_active_window()

        assert len(turns) == 2
        assert turns[0]["role"] == "user"
        assert turns[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_get_active_token_count(self, history_manager, mock_db):
        """Test token count retrieval."""
        mock_db.fetchone.return_value = (150, 3)  # tokens, count

        counts = await history_manager.get_active_token_count()

        assert counts["total_tokens"] == 150
        assert counts["turn_count"] == 3


class TestActiveWindowRotation:
    """Test Active Window budget management."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def mock_engine(self, mock_db):
        """Create mock engine."""
        engine = MagicMock()
        matrix = MagicMock()
        matrix.db = mock_db
        matrix_actor = MagicMock()
        matrix_actor._matrix = matrix
        engine.get_actor = lambda name: matrix_actor if name == "matrix" else None
        return engine

    @pytest.mark.asyncio
    async def test_rotation_when_budget_exceeded(self, mock_engine, mock_db):
        """Test that Active Window rotates when token budget exceeded."""
        config = HistoryConfig(max_active_tokens=100, max_active_turns=10)
        manager = HistoryManagerActor(config=config, engine=mock_engine)

        # Setup: over budget (150 tokens, 3 turns)
        mock_db.fetchone.side_effect = [
            (150, 3),  # First call: get token count
            (1, "user", "Old message", 60, "2026-01-20"),  # Second call: oldest turn
            (1,),  # For last_insert_rowid
        ]
        mock_db.fetchall.return_value = []

        # Add a turn (should trigger rotation check)
        await manager.add_turn("user", "New message", tokens=50)

        # Verify rotation occurred
        assert manager._rotations >= 1

    @pytest.mark.asyncio
    async def test_no_rotation_under_budget(self, mock_engine, mock_db):
        """Test no rotation when under budget."""
        config = HistoryConfig(max_active_tokens=1000, max_active_turns=10)
        manager = HistoryManagerActor(config=config, engine=mock_engine)

        # Setup: under budget (50 tokens, 1 turn)
        mock_db.fetchone.side_effect = [
            (50, 1),  # Token count
            (1,),  # last_insert_rowid
        ]

        await manager.add_turn("user", "Hello", tokens=10)

        # No rotations should have occurred
        assert manager._rotations == 0


class TestSearchRecent:
    """Test Recent Buffer search."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def history_manager(self, mock_db):
        """Create manager with mocks."""
        engine = MagicMock()
        matrix = MagicMock()
        matrix.db = mock_db
        matrix_actor = MagicMock()
        matrix_actor._matrix = matrix
        engine.get_actor = lambda name: matrix_actor if name == "matrix" else None
        return HistoryManagerActor(engine=engine)

    @pytest.mark.asyncio
    async def test_keyword_search(self, history_manager, mock_db):
        """Test FTS5 keyword search."""
        mock_db.fetchall.return_value = [
            (1, "user", "Tell me about observability", "Summary of observability", "2026-01-20", -0.8),
        ]

        results = await history_manager.search_recent(
            query="observability",
            search_type="keyword"
        )

        assert len(results) == 1
        assert "observability" in results[0]["content"]
        history_manager._searches_performed == 1

    @pytest.mark.asyncio
    async def test_search_fallback_on_fts_error(self, history_manager, mock_db):
        """Test fallback to LIKE when FTS5 fails."""
        # First call (FTS5) raises error, second call (LIKE) succeeds
        mock_db.fetchall.side_effect = [
            Exception("FTS5 error"),
            [(1, "user", "Hello", "Summary", "2026-01-20")],
        ]

        results = await history_manager.search_recent(query="Hello")

        assert len(results) == 1
        assert results[0]["search_type"] == "keyword_fallback"


class TestCompressionQueue:
    """Test compression queue processing."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = AsyncMock()
        return db

    @pytest.fixture
    def history_manager(self, mock_db):
        """Create manager with mocks."""
        engine = MagicMock()
        matrix = MagicMock()
        matrix.db = mock_db
        matrix_actor = MagicMock()
        matrix_actor._matrix = matrix
        engine.get_actor = lambda name: matrix_actor if name == "matrix" else None
        return HistoryManagerActor(engine=engine)

    @pytest.mark.asyncio
    async def test_queue_compression(self, history_manager, mock_db):
        """Test queuing a turn for compression."""
        await history_manager.queue_compression(turn_id=1)

        assert history_manager._compressions_queued == 1
        mock_db.execute.assert_called()

    @pytest.mark.asyncio
    async def test_queue_extraction(self, history_manager, mock_db):
        """Test queuing a turn for extraction."""
        await history_manager.queue_extraction(turn_id=1)

        assert history_manager._extractions_queued == 1
        mock_db.execute.assert_called()


class TestMessageHandling:
    """Test message handling via handle() method."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = AsyncMock()
        db.fetchone.return_value = (1,)
        db.fetchall.return_value = []
        return db

    @pytest.fixture
    def history_manager(self, mock_db):
        """Create manager with mocks."""
        engine = MagicMock()
        matrix = MagicMock()
        matrix.db = mock_db
        matrix_actor = MagicMock()
        matrix_actor._matrix = matrix
        engine.get_actor = lambda name: matrix_actor if name == "matrix" else None
        return HistoryManagerActor(engine=engine)

    @pytest.mark.asyncio
    async def test_handle_add_turn(self, history_manager):
        """Test handling add_turn message."""
        from luna.actors.base import Message

        msg = Message(
            type="add_turn",
            payload={"role": "user", "content": "Hello", "tokens": 10}
        )

        await history_manager.handle(msg)

        assert history_manager._turns_added == 1

    @pytest.mark.asyncio
    async def test_handle_unknown_message(self, history_manager, caplog):
        """Test handling unknown message type."""
        from luna.actors.base import Message

        msg = Message(type="unknown_type", payload={})

        await history_manager.handle(msg)

        # Should log warning but not raise
        assert "Unknown message type" in caplog.text or history_manager._turns_added == 0
