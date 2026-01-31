"""
Unit test fixtures for Luna Engine.

These fixtures provide mocked dependencies for isolated testing.
All external systems (database, LLM, network) are mocked.
"""

import asyncio
import pytest
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, List
from unittest.mock import Mock, AsyncMock, MagicMock, patch


# =============================================================================
# MOCK CONFIGURATION
# =============================================================================

@pytest.fixture
def mock_config():
    """Mock configuration for unit tests."""
    config = Mock()
    config.model_path = "test-model"
    config.max_tokens = 100
    config.temperature = 0.7
    config.backend = "claude-haiku"
    config.batch_size = 3
    config.min_content_length = 10
    return config


@pytest.fixture
def mock_extraction_config():
    """Mock ExtractionConfig for Scribe tests."""
    config = Mock()
    config.backend = "disabled"
    config.batch_size = 3
    config.min_content_length = 10
    config.max_tokens = 500
    config.temperature = 0.0
    return config


# =============================================================================
# MOCK ENGINE
# =============================================================================

@pytest.fixture
def mock_engine():
    """Mock LunaEngine for actor tests."""
    engine = Mock()
    engine.get_actor = Mock(return_value=None)
    engine.input_buffer = AsyncMock()
    engine.input_buffer.put = AsyncMock()
    return engine


# =============================================================================
# MOCK DATABASE
# =============================================================================

@dataclass
class MockMemoryNode:
    """Mock memory node for testing."""
    id: str
    node_type: str
    content: str
    summary: Optional[str] = None
    source: Optional[str] = None
    confidence: float = 1.0
    importance: float = 0.5
    lock_in: float = 0.5
    lock_in_state: str = "fluid"
    access_count: int = 0
    reinforcement_count: int = 0
    created_at: Optional[datetime] = field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None
    last_accessed: Optional[datetime] = None
    metadata: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "node_type": self.node_type,
            "content": self.content,
            "confidence": self.confidence,
            "importance": self.importance,
            "lock_in": self.lock_in,
            "lock_in_state": self.lock_in_state,
        }


@pytest.fixture
def mock_memory_node():
    """Create a mock memory node."""
    return MockMemoryNode(
        id="node-001",
        node_type="FACT",
        content="Test fact content",
        confidence=0.9,
        importance=0.5,
    )


@pytest.fixture
def mock_database():
    """Mock async database for tests."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.fetchone = AsyncMock(return_value=None)
    db.fetchall = AsyncMock(return_value=[])
    db.connect = AsyncMock()
    db.close = AsyncMock()
    return db


@pytest.fixture
def mock_matrix():
    """Mock MemoryMatrix for actor tests."""
    matrix = AsyncMock()
    matrix.add_node = AsyncMock(return_value="node-new-001")
    matrix.get_node = AsyncMock(return_value=None)
    matrix.update_node = AsyncMock(return_value=True)
    matrix.delete_node = AsyncMock(return_value=True)
    matrix.search_nodes = AsyncMock(return_value=[])
    matrix.fts5_search = AsyncMock(return_value=[])
    matrix.semantic_search = AsyncMock(return_value=[])
    matrix.hybrid_search = AsyncMock(return_value=[])
    matrix.get_context = AsyncMock(return_value=[])
    matrix.record_access = AsyncMock()
    matrix.reinforce_node = AsyncMock(return_value=True)
    matrix.get_stats = AsyncMock(return_value={"total_nodes": 100})
    matrix.get_drifting_nodes = AsyncMock(return_value=[])
    matrix.db = AsyncMock()
    return matrix


@pytest.fixture
def mock_graph():
    """Mock MemoryGraph for actor tests."""
    graph = AsyncMock()
    graph.load_from_db = AsyncMock()
    graph.add_edge = Mock()
    graph.has_edge = Mock(return_value=False)
    graph.remove_edge = Mock()
    graph.get_neighbors = Mock(return_value=[])
    graph.get_central_nodes = Mock(return_value=[])
    graph.get_all_edges = Mock(return_value=[])
    graph.get_stats = AsyncMock(return_value={"node_count": 100, "edge_count": 50})
    graph.has_node = Mock(return_value=True)
    graph._graph = Mock()
    return graph


# =============================================================================
# MOCK LLM
# =============================================================================

@pytest.fixture
def mock_anthropic_client():
    """Mock Anthropic client for LLM tests."""
    client = Mock()

    # Mock response structure
    mock_content = Mock()
    mock_content.text = '{"objects": [], "edges": [], "entity_updates": []}'

    mock_response = Mock()
    mock_response.content = [mock_content]
    mock_response.usage = Mock(input_tokens=10, output_tokens=20)

    client.messages = Mock()
    client.messages.create = Mock(return_value=mock_response)

    return client


@pytest.fixture
def mock_local_inference():
    """Mock local inference for Director tests."""
    local = AsyncMock()
    local.is_loaded = True
    local.generate = AsyncMock(return_value=Mock(text="Local response text"))
    local.load = AsyncMock()
    local.unload = AsyncMock()
    return local


# =============================================================================
# MOCK ACTORS
# =============================================================================

@pytest.fixture
def mock_director_actor(mock_engine, mock_local_inference):
    """Create a mocked DirectorActor for testing."""
    from luna.actors.director import DirectorActor

    with patch.object(DirectorActor, '__init__', lambda self, **kwargs: None):
        director = DirectorActor()
        director.name = "director"
        director.engine = mock_engine
        director._running = False
        director._task = None
        director.mailbox = asyncio.Queue()
        director._local = mock_local_inference
        director._client = None
        director._generating = False
        director._local_generations = 0
        director._delegated_generations = 0
        director._abort_requested = False
        director._model = "test-model"
        director._stream_callbacks = []
        return director


@pytest.fixture
def mock_matrix_actor(mock_engine, mock_database, mock_matrix, mock_graph):
    """Create a mocked MatrixActor for testing."""
    from luna.actors.matrix import MatrixActor
    from pathlib import Path

    actor = MatrixActor(db_path=Path("/tmp/test.db"))
    actor.engine = mock_engine
    actor._db = mock_database
    actor._matrix = mock_matrix
    actor._graph = mock_graph
    actor._initialized = True
    return actor


@pytest.fixture
def mock_librarian_actor(mock_engine):
    """Create a mocked LibrarianActor for testing."""
    from luna.actors.librarian import LibrarianActor

    actor = LibrarianActor(engine=mock_engine)
    actor.alias_cache = {}
    actor._entity_resolver = None
    return actor


@pytest.fixture
def mock_scribe_actor(mock_engine, mock_extraction_config):
    """Create a mocked ScribeActor for testing."""
    from luna.actors.scribe import ScribeActor
    from luna.extraction.types import ExtractionConfig

    # Use real ExtractionConfig with disabled backend for safe testing
    config = ExtractionConfig(backend="disabled", batch_size=3, min_content_length=10)
    actor = ScribeActor(config=config, engine=mock_engine)
    actor._client = None  # Don't use real Anthropic
    return actor


@pytest.fixture
def mock_history_manager_actor(mock_engine, mock_matrix):
    """Create a mocked HistoryManagerActor for testing."""
    from luna.actors.history_manager import HistoryManagerActor, HistoryConfig

    config = HistoryConfig(
        max_active_tokens=500,
        max_active_turns=5,
        compression_enabled=False
    )
    actor = HistoryManagerActor(config=config, engine=mock_engine)
    actor._is_ready = True
    actor._current_session_id = "test-session-001"
    return actor


# =============================================================================
# HELPER FIXTURES
# =============================================================================

@pytest.fixture
def sample_extraction_output():
    """Sample extraction output for Librarian tests."""
    return {
        "objects": [
            {
                "type": "FACT",
                "content": "Test fact content",
                "confidence": 0.9,
                "entities": ["Entity1", "Entity2"],
            }
        ],
        "edges": [
            {
                "from_ref": "Entity1",
                "to_ref": "Entity2",
                "edge_type": "related_to",
                "confidence": 1.0,
            }
        ],
        "source_id": "test-source",
    }


@pytest.fixture
def sample_entity_update():
    """Sample entity update for Librarian tests."""
    return {
        "update_type": "update",
        "entity_id": None,
        "name": "Test Entity",
        "entity_type": "person",
        "facts": {"role": "tester", "location": "test lab"},
        "source": "test",
    }


@pytest.fixture
def sample_conversation_turns():
    """Sample conversation turns for HistoryManager tests."""
    return [
        {"role": "user", "content": "Hello Luna", "tokens": 10},
        {"role": "assistant", "content": "Hi there!", "tokens": 8},
        {"role": "user", "content": "What can you do?", "tokens": 12},
    ]
