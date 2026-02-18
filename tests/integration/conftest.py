"""
Integration test fixtures for Luna Engine v2.0.

These fixtures use REAL Luna components but mock EXTERNAL APIs.
"""

import pytest
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

from luna.engine import LunaEngine, EngineConfig
from luna.actors.base import Actor, Message
from luna.actors.director import DirectorActor
from luna.actors.matrix import MatrixActor
from luna.actors.scribe import ScribeActor
from luna.actors.librarian import LibrarianActor
from luna.actors.history_manager import HistoryManagerActor, HistoryConfig
from luna.extraction.types import (
    ExtractionOutput,
    ExtractedObject,
    ExtractedEdge,
    ExtractionType,
)


# =============================================================================
# MOCK EXTERNAL APIS
# =============================================================================

@pytest.fixture
def mock_claude_api():
    """Mock Claude API for integration tests."""
    with patch('anthropic.AsyncAnthropic') as mock_async:
        with patch('anthropic.Anthropic') as mock_sync:
            # Setup async client
            async_client = AsyncMock()
            async_client.messages.create = AsyncMock(return_value=AsyncMock(
                content=[AsyncMock(text="Claude response for integration test")],
                usage=AsyncMock(input_tokens=100, output_tokens=50),
                model="claude-3-haiku-20240307"
            ))
            mock_async.return_value = async_client

            # Setup sync client (used by Scribe)
            sync_response = MagicMock()
            sync_response.content = [MagicMock(text='{"objects": [], "edges": [], "entity_updates": []}')]
            sync_client = MagicMock()
            sync_client.messages.create = MagicMock(return_value=sync_response)
            mock_sync.return_value = sync_client

            yield {
                "async_client": async_client,
                "sync_client": sync_client,
                "async_mock": mock_async,
                "sync_mock": mock_sync,
            }


@pytest.fixture
def mock_openai_embeddings():
    """Mock OpenAI embeddings for vector operations."""
    with patch('openai.AsyncOpenAI') as mock:
        client = AsyncMock()
        # Return a 1536-dim embedding (text-embedding-3-small)
        client.embeddings.create = AsyncMock(return_value=AsyncMock(
            data=[AsyncMock(embedding=[0.1] * 1536)]
        ))
        mock.return_value = client
        yield client


@pytest.fixture
def mock_local_inference():
    """Mock local MLX inference."""
    with patch('luna.inference.local.LocalInference') as mock:
        local = AsyncMock()
        local.is_loaded = True
        local.generate = AsyncMock(return_value=AsyncMock(
            text="Local model response",
            tokens=50
        ))
        local.generate_stream = AsyncMock()
        mock.return_value = local
        yield local


# =============================================================================
# DATABASE FIXTURES
# =============================================================================

@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for tests."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_database():
    """Mock async database for integration tests."""
    db = AsyncMock()
    db.fetchall = AsyncMock(return_value=[])
    db.fetchone = AsyncMock(return_value=None)
    db.execute = AsyncMock()
    return db


# =============================================================================
# ACTOR FIXTURES
# =============================================================================

@pytest.fixture
def mock_matrix_actor(mock_database):
    """Create MatrixActor with mocked database."""
    actor = MagicMock(spec=MatrixActor)
    actor.name = "matrix"
    actor.is_ready = True

    # ── MemoryMatrix mock (returned by Librarian._get_matrix()) ──
    matrix = MagicMock()
    matrix.db = mock_database
    # Async methods that Librarian awaits on the MemoryMatrix object
    matrix.add_node = AsyncMock(return_value="node_123")
    matrix.get_node = AsyncMock(return_value=None)
    matrix.update_node = AsyncMock()
    matrix.delete_node = AsyncMock(return_value=True)
    matrix.search_nodes = AsyncMock(return_value=[])
    matrix.get_context = AsyncMock(return_value="Test memory context")
    matrix.get_drifting_nodes = AsyncMock(return_value=[])
    actor._matrix = matrix

    # ── MemoryGraph mock (accessed as matrix_actor._graph) ──
    graph = MagicMock()
    graph.has_edge = MagicMock(return_value=False)       # sync (2-arg check)
    graph.add_edge = AsyncMock()                          # async
    graph.remove_edge = AsyncMock()                       # async
    graph.get_all_edges = MagicMock(return_value=[])      # sync
    graph.get_neighbors = MagicMock(return_value=[])      # sync
    actor._graph = graph

    # ── Actor-level convenience mocks (used by some tests directly) ──
    actor.get_context = AsyncMock(return_value="Test memory context")
    actor.search = AsyncMock(return_value=[])
    actor.search_nodes = AsyncMock(return_value=[])
    actor.store_memory = AsyncMock()
    actor.store_turn = AsyncMock()
    actor.add_node = AsyncMock(return_value="node_123")
    actor.get_node = AsyncMock(return_value=None)
    actor.get_drifting_nodes = AsyncMock(return_value=[])
    actor.delete_node = AsyncMock(return_value=True)

    return actor


@pytest.fixture
def mock_scribe_actor():
    """Create ScribeActor with mocked extraction."""
    actor = MagicMock(spec=ScribeActor)
    actor.name = "scribe"
    actor.mailbox = asyncio.Queue()

    # Mock compress_turn
    actor.compress_turn = AsyncMock(return_value="Compressed summary")

    # Mock extraction stats
    actor.get_stats = MagicMock(return_value={
        "backend": "claude-haiku",
        "extractions_count": 0,
        "objects_extracted": 0,
        "edges_extracted": 0,
    })

    return actor


@pytest.fixture
def mock_librarian_actor():
    """Create LibrarianActor with mocked filing."""
    actor = MagicMock(spec=LibrarianActor)
    actor.name = "librarian"
    actor.mailbox = asyncio.Queue()
    actor.alias_cache = {}

    actor.get_stats = MagicMock(return_value={
        "filings_count": 0,
        "nodes_created": 0,
        "nodes_merged": 0,
        "edges_created": 0,
    })

    return actor


@pytest.fixture
def mock_history_manager(mock_database):
    """Create HistoryManagerActor with test configuration."""
    config = HistoryConfig(
        max_active_tokens=500,
        max_active_turns=5,
        compression_enabled=True,
        default_search_limit=3,
        search_type="hybrid"
    )
    actor = HistoryManagerActor(config=config)
    actor._is_ready = True
    return actor


# =============================================================================
# ENGINE FIXTURES
# =============================================================================

@pytest.fixture
def mock_engine(
    mock_matrix_actor,
    mock_scribe_actor,
    mock_librarian_actor,
    mock_history_manager,
):
    """Create mock engine with all actors registered."""
    engine = MagicMock(spec=LunaEngine)
    engine.session_id = "test-session"
    engine._on_response_callbacks = []
    engine._on_progress_callbacks = []

    actors = {
        "matrix": mock_matrix_actor,
        "scribe": mock_scribe_actor,
        "librarian": mock_librarian_actor,
        "history_manager": mock_history_manager,
    }

    def get_actor(name):
        return actors.get(name)

    engine.get_actor = get_actor
    engine.actors = actors

    # Wire up actors with engine reference
    for actor in actors.values():
        if hasattr(actor, 'engine'):
            actor.engine = engine

    return engine


@pytest.fixture
async def engine_with_mock_llm(mock_claude_api, temp_data_dir):
    """
    Engine with mocked external LLM.

    Uses REAL Luna actors but mocks Claude API calls.
    """
    config = EngineConfig(
        cognitive_interval=0.1,
        reflective_interval=300,
        data_dir=temp_data_dir,
        enable_local_inference=False,  # Disable local to force Claude path
    )

    engine = LunaEngine(config)

    # Don't run full boot - just initialize minimally for tests
    # Boot is slow and requires real DB setup
    engine.state = "RUNNING"
    engine._running = True

    yield engine

    # Cleanup
    engine._running = False


# =============================================================================
# EXTRACTION FIXTURES
# =============================================================================

@pytest.fixture
def sample_extraction_output():
    """Sample extraction output for testing pipelines."""
    return ExtractionOutput(
        objects=[
            ExtractedObject(
                type="FACT",
                content="Alex is the project lead for Luna Engine",
                confidence=0.95,
                entities=["Alex", "Luna Engine"],
                source_id="test-session",
            ),
            ExtractedObject(
                type="PREFERENCE",
                content="User prefers dark mode",
                confidence=0.8,
                entities=["User"],
                source_id="test-session",
            ),
        ],
        edges=[
            ExtractedEdge(
                from_ref="Alex",
                to_ref="Luna Engine",
                edge_type="leads",
                confidence=0.95,
                source_id="test-session",
            ),
        ],
        source_id="test-session",
    )


@pytest.fixture
def sample_claude_extraction_response():
    """Sample Claude response for extraction."""
    return {
        "objects": [
            {
                "type": "FACT",
                "content": "The Luna Engine uses a hybrid LLM architecture",
                "confidence": 0.9,
                "entities": ["Luna Engine"]
            },
            {
                "type": "DECISION",
                "content": "Team decided to use Qwen 3B for local inference",
                "confidence": 0.85,
                "entities": ["Qwen 3B"]
            }
        ],
        "edges": [
            {
                "from_ref": "Luna Engine",
                "to_ref": "Qwen 3B",
                "edge_type": "uses"
            }
        ],
        "entity_updates": [
            {
                "entity_name": "Luna Engine",
                "entity_type": "project",
                "facts": {"architecture": "hybrid LLM"},
                "update_type": "update"
            }
        ]
    }


# =============================================================================
# MESSAGE FIXTURES
# =============================================================================

@pytest.fixture
def sample_generate_message():
    """Sample generate message for Director."""
    return Message(
        type="generate",
        payload={
            "user_message": "Hello Luna, how are you today?",
            "system_prompt": "You are Luna, a sovereign AI companion.",
            "context_window": "",
            "max_tokens": 512,
        },
        correlation_id="test-123",
    )


@pytest.fixture
def sample_extract_turn_message():
    """Sample extract_turn message for Scribe."""
    return Message(
        type="extract_turn",
        payload={
            "role": "user",
            "content": "My friend Alex is the project lead for Luna Engine. He prefers dark mode for the UI.",
            "turn_id": 1,
            "session_id": "test-session",
            "immediate": True,
        },
        correlation_id="test-456",
    )


@pytest.fixture
def sample_file_message(sample_extraction_output):
    """Sample file message for Librarian."""
    return Message(
        type="file",
        payload=sample_extraction_output.to_dict(),
        correlation_id="test-789",
    )


# =============================================================================
# HISTORY FIXTURES
# =============================================================================

@pytest.fixture
def sample_conversation_history():
    """Sample conversation turns for history tests."""
    return [
        {"turn_id": 1, "role": "user", "content": "Hello Luna", "tokens": 5, "timestamp": "2026-01-30T10:00:00"},
        {"turn_id": 2, "role": "assistant", "content": "Hello! How can I help you today?", "tokens": 10, "timestamp": "2026-01-30T10:00:01"},
        {"turn_id": 3, "role": "user", "content": "Tell me about the weather", "tokens": 8, "timestamp": "2026-01-30T10:00:02"},
        {"turn_id": 4, "role": "assistant", "content": "I don't have access to current weather data.", "tokens": 12, "timestamp": "2026-01-30T10:00:03"},
    ]


# =============================================================================
# TEST MARKERS
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
