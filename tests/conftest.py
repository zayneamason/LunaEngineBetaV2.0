"""
Pytest configuration and shared fixtures for Luna Engine tests.

This module provides shared fixtures for all test categories:
- Unit tests: Isolated component testing with mocks
- Integration tests: Component interaction testing
- E2E tests: Full system flow testing
- Smoke tests: Critical system availability checks
- Tracer tests: Performance and timing diagnostics

Fixture Categories:
- Database fixtures: temp_db, populated_db
- Engine fixtures: mock_engine, engine_config
- Actor fixtures: mock_actor, mock_director
- Memory fixtures: sample_memory_node, memory_matrix
- LLM fixtures: mock_llm_response, mock_claude_client
"""

import asyncio
import sqlite3
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone

from luna.engine import LunaEngine, EngineConfig
from luna.core.events import InputEvent, EventType, EventPriority
from luna.core.input_buffer import InputBuffer
from luna.actors.base import Actor, Message


# =============================================================================
# PYTEST MARKERS CONFIGURATION
# =============================================================================

def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests - isolated component tests with mocks"
    )
    config.addinivalue_line(
        "markers", "smoke: Smoke tests - critical system availability checks"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests - component interaction tests"
    )
    config.addinivalue_line(
        "markers", "tracer: Tracer tests - performance and timing diagnostics"
    )
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests - full system flow tests"
    )
    config.addinivalue_line(
        "markers", "slow: Slow tests - tests that take longer than 5 seconds"
    )


# =============================================================================
# CORE FIXTURES (Original)
# =============================================================================

@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for tests."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def engine_config(temp_data_dir):
    """Create test engine configuration."""
    return EngineConfig(
        cognitive_interval=0.1,  # Fast ticks for tests
        reflective_interval=60,
        data_dir=temp_data_dir,
    )


@pytest.fixture
def input_buffer():
    """Create fresh input buffer for tests."""
    return InputBuffer(max_size=10, stale_threshold_seconds=1.0)


@pytest.fixture
def sample_event():
    """Create a sample input event."""
    return InputEvent(
        type=EventType.TEXT_INPUT,
        payload="Hello Luna",
        source="test",
    )


@pytest.fixture
def interrupt_event():
    """Create an interrupt event."""
    return InputEvent(
        type=EventType.USER_INTERRUPT,
        payload="stop",
        source="test",
    )


class MockActor(Actor):
    """Mock actor for testing."""

    def __init__(self, name: str = "mock"):
        super().__init__(name)
        self.received_messages = []
        self.handle_delay = 0

    async def handle(self, msg: Message) -> None:
        """Record received messages."""
        self.received_messages.append(msg)
        if self.handle_delay > 0:
            await asyncio.sleep(self.handle_delay)


@pytest.fixture
def mock_actor():
    """Create a mock actor for testing."""
    return MockActor("test_actor")


# =============================================================================
# DATABASE FIXTURES
# =============================================================================

# Luna Engine schema for test databases
LUNA_SCHEMA = """
-- Core memory nodes table
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    source TEXT,
    confidence REAL DEFAULT 1.0,
    importance REAL DEFAULT 0.5,
    lock_in_coefficient REAL DEFAULT 0.0,
    access_count INTEGER DEFAULT 0,
    last_accessed TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    metadata TEXT
);

-- FTS5 full-text search index
CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    content,
    summary,
    content=nodes,
    content_rowid=rowid
);

-- Embeddings table for vector search
CREATE TABLE IF NOT EXISTS embeddings (
    node_id TEXT PRIMARY KEY,
    embedding BLOB NOT NULL,
    model TEXT DEFAULT 'local',
    created_at TEXT NOT NULL,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

-- Edges table for relationship graph
CREATE TABLE IF NOT EXISTS edges (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    metadata TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE,
    FOREIGN KEY (target_id) REFERENCES nodes(id) ON DELETE CASCADE
);

-- Conversation turns table
CREATE TABLE IF NOT EXISTS turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT DEFAULT 'text',
    tokens INTEGER,
    created_at TEXT NOT NULL
);

-- Entity mentions table
CREATE TABLE IF NOT EXISTS entity_mentions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    mention_type TEXT DEFAULT 'reference',
    context TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_nodes_importance ON nodes(importance DESC);
CREATE INDEX IF NOT EXISTS idx_nodes_lock_in ON nodes(lock_in_coefficient DESC);
CREATE INDEX IF NOT EXISTS idx_nodes_created ON nodes(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
CREATE INDEX IF NOT EXISTS idx_edges_type ON edges(edge_type);
CREATE INDEX IF NOT EXISTS idx_turns_created ON turns(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_entity_mentions_entity ON entity_mentions(entity_id);
"""


@pytest.fixture
def temp_db(tmp_path):
    """
    Create an in-memory SQLite database with Luna Engine schema.

    Returns a tuple of (connection, db_path) where db_path is a file path
    that can be used for reconnection if needed.

    Usage:
        def test_memory_operations(temp_db):
            conn, db_path = temp_db
            cursor = conn.execute("SELECT * FROM nodes")
            # ... test operations
    """
    db_path = tmp_path / "test_luna.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(LUNA_SCHEMA)
    conn.commit()
    yield conn, db_path
    conn.close()


@pytest.fixture
def populated_db(temp_db):
    """
    Create a database with sample data for testing.

    Pre-populates the database with:
    - 5 memory nodes (fact, episodic, semantic, procedural, entity)
    - 3 edges connecting nodes
    - 5 conversation turns
    - 2 entity mentions

    Usage:
        def test_search_operations(populated_db):
            conn, db_path = populated_db
            results = conn.execute(
                "SELECT * FROM nodes WHERE node_type = 'fact'"
            ).fetchall()
    """
    conn, db_path = temp_db
    now = datetime.now(timezone.utc).isoformat()

    # Sample nodes
    nodes = [
        ("node_001", "fact", "Marzipan is Luna's beloved orange cat",
         "Luna's cat Marzipan", "user", 1.0, 0.9, 0.85, 10, now, now, now, "{}"),
        ("node_002", "episodic", "User mentioned Marzipan caught a mouse yesterday",
         "Marzipan caught mouse", "conversation", 0.9, 0.7, 0.3, 2, now, now, now, "{}"),
        ("node_003", "semantic", "Cats are common household pets known for hunting",
         "Cats as pets", "system", 1.0, 0.5, 0.1, 1, now, now, now, "{}"),
        ("node_004", "procedural", "To feed Marzipan: open cabinet, measure food, pour in bowl",
         "Feeding procedure", "user", 0.8, 0.6, 0.4, 5, now, now, now, "{}"),
        ("node_005", "entity", "Marzipan: orange tabby cat, age 5, favorite toy is feather wand",
         "Entity: Marzipan", "extraction", 1.0, 0.95, 0.9, 15, now, now, now,
         '{"entity_type": "pet", "species": "cat"}'),
    ]

    conn.executemany(
        """INSERT INTO nodes
           (id, node_type, content, summary, source, confidence, importance,
            lock_in_coefficient, access_count, last_accessed, created_at, updated_at, metadata)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        nodes
    )

    # Sample edges
    edges = [
        ("edge_001", "node_001", "node_005", "describes", 1.0, "{}", now),
        ("edge_002", "node_002", "node_005", "references", 0.8, "{}", now),
        ("edge_003", "node_004", "node_005", "involves", 0.9, "{}", now),
    ]

    conn.executemany(
        """INSERT INTO edges
           (id, source_id, target_id, edge_type, weight, metadata, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        edges
    )

    # Sample turns
    turns = [
        ("user", "Tell me about Marzipan", "text", 5, now),
        ("assistant", "Marzipan is your beloved orange tabby cat!", "text", 12, now),
        ("user", "What did Marzipan do yesterday?", "text", 7, now),
        ("assistant", "Marzipan caught a mouse yesterday! Such a skilled hunter.", "text", 15, now),
        ("user", "How do I feed her?", "text", 6, now),
    ]

    conn.executemany(
        """INSERT INTO turns (role, content, source, tokens, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        turns
    )

    # Sample entity mentions
    mentions = [
        ("entity_marzipan", "node_001", "definition", "primary mention", now),
        ("entity_marzipan", "node_002", "reference", "episodic mention", now),
    ]

    conn.executemany(
        """INSERT INTO entity_mentions
           (entity_id, node_id, mention_type, context, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        mentions
    )

    conn.commit()
    yield conn, db_path


# =============================================================================
# ENGINE FIXTURES
# =============================================================================

@pytest.fixture
def mock_engine(temp_data_dir, engine_config):
    """
    Create a LunaEngine with mocked actors for testing.

    The engine is created but NOT started. Actors are mocked to prevent
    actual LLM calls and database operations.

    Usage:
        @pytest.mark.asyncio
        async def test_engine_dispatch(mock_engine):
            engine = mock_engine
            # Configure mocks
            engine.director.generate = AsyncMock(return_value="Hello!")
            # Test engine behavior
            await engine.send_message("Hi")
    """
    engine = LunaEngine(config=engine_config)

    # Mock the director actor to prevent LLM calls
    mock_director = MagicMock()
    mock_director.generate = AsyncMock(return_value="Mocked response")
    mock_director.generate_stream = AsyncMock(return_value=iter(["Mocked ", "stream"]))
    mock_director.is_processing = False
    mock_director.local_generations = 0
    mock_director.delegated_generations = 0

    # Mock the matrix actor to prevent database calls
    mock_matrix = MagicMock()
    mock_matrix.matrix = MagicMock()
    mock_matrix.matrix.search_nodes = AsyncMock(return_value=[])
    mock_matrix.matrix.get_context = AsyncMock(return_value=[])
    mock_matrix.is_ready = True

    # Attach mocks (these will be attached during boot)
    engine._mock_director = mock_director
    engine._mock_matrix = mock_matrix

    return engine


@pytest.fixture
def minimal_engine_config(tmp_path):
    """
    Create a minimal engine configuration for fast tests.

    Uses very short intervals and disables features that slow down tests.
    """
    return EngineConfig(
        cognitive_interval=0.01,  # 10ms ticks
        reflective_interval=1.0,  # 1 second reflection
        data_dir=tmp_path,
    )


# =============================================================================
# LLM MOCK FIXTURES
# =============================================================================

@dataclass
class MockLLMResponse:
    """Mock LLM response structure matching Claude/Anthropic API."""
    content: str
    model: str = "claude-3-haiku-20240307"
    input_tokens: int = 10
    output_tokens: int = 50
    stop_reason: str = "end_turn"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "content": [{"type": "text", "text": self.content}],
            "model": self.model,
            "usage": {
                "input_tokens": self.input_tokens,
                "output_tokens": self.output_tokens,
            },
            "stop_reason": self.stop_reason,
        }


@pytest.fixture
def mock_llm_response():
    """
    Factory fixture for creating mock LLM responses.

    Usage:
        def test_director_response(mock_llm_response):
            response = mock_llm_response("Hello, I'm Luna!")
            assert response.content == "Hello, I'm Luna!"

            # With custom parameters
            response = mock_llm_response(
                "Complex response",
                model="claude-3-opus-20240229",
                output_tokens=500
            )
    """
    def _create_response(
        content: str = "Default mock response",
        model: str = "claude-3-haiku-20240307",
        input_tokens: int = 10,
        output_tokens: int = 50,
        stop_reason: str = "end_turn",
    ) -> MockLLMResponse:
        return MockLLMResponse(
            content=content,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            stop_reason=stop_reason,
        )

    return _create_response


@pytest.fixture
def mock_claude_client(mock_llm_response):
    """
    Create a mock Anthropic client for testing Claude API calls.

    Usage:
        @pytest.mark.asyncio
        async def test_director_generation(mock_claude_client):
            with patch('anthropic.AsyncAnthropic', return_value=mock_claude_client):
                # Test code that uses Claude API
                pass
    """
    mock_client = MagicMock()

    # Mock the messages.create method
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="Mocked Claude response")]
    mock_message.model = "claude-3-haiku-20240307"
    mock_message.usage = MagicMock(input_tokens=10, output_tokens=50)
    mock_message.stop_reason = "end_turn"

    mock_client.messages = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_message)

    # Mock streaming
    async def mock_stream(*args, **kwargs):
        yield MagicMock(type="content_block_delta", delta=MagicMock(text="Mocked "))
        yield MagicMock(type="content_block_delta", delta=MagicMock(text="streaming "))
        yield MagicMock(type="content_block_delta", delta=MagicMock(text="response"))

    mock_client.messages.stream = MagicMock(return_value=mock_stream())

    return mock_client


# =============================================================================
# MEMORY FIXTURES
# =============================================================================

@dataclass
class SampleMemoryNode:
    """Sample memory node structure for testing."""
    id: str
    node_type: str
    content: str
    summary: Optional[str] = None
    source: str = "test"
    confidence: float = 1.0
    importance: float = 0.5
    lock_in_coefficient: float = 0.0
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node_type": self.node_type,
            "content": self.content,
            "summary": self.summary,
            "source": self.source,
            "confidence": self.confidence,
            "importance": self.importance,
            "lock_in_coefficient": self.lock_in_coefficient,
            "access_count": self.access_count,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


@pytest.fixture
def sample_memory_node():
    """
    Factory fixture for creating sample memory nodes.

    Usage:
        def test_memory_storage(sample_memory_node):
            node = sample_memory_node(
                node_type="fact",
                content="Luna loves programming"
            )
            assert node.node_type == "fact"

            # With full customization
            node = sample_memory_node(
                id="custom_001",
                node_type="episodic",
                content="User asked about weather",
                importance=0.8,
                lock_in_coefficient=0.5
            )
    """
    _counter = [0]

    def _create_node(
        id: Optional[str] = None,
        node_type: str = "fact",
        content: str = "Sample memory content",
        summary: Optional[str] = None,
        source: str = "test",
        confidence: float = 1.0,
        importance: float = 0.5,
        lock_in_coefficient: float = 0.0,
        access_count: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SampleMemoryNode:
        _counter[0] += 1
        return SampleMemoryNode(
            id=id or f"test_node_{_counter[0]:04d}",
            node_type=node_type,
            content=content,
            summary=summary or content[:50],
            source=source,
            confidence=confidence,
            importance=importance,
            lock_in_coefficient=lock_in_coefficient,
            access_count=access_count,
            metadata=metadata or {},
        )

    return _create_node


@pytest.fixture
def sample_memory_nodes(sample_memory_node):
    """
    Create a collection of sample memory nodes for testing.

    Returns a list of 5 nodes with different types and characteristics.
    """
    return [
        sample_memory_node(
            node_type="fact",
            content="Luna is an AI assistant",
            importance=0.9,
            lock_in_coefficient=0.8
        ),
        sample_memory_node(
            node_type="episodic",
            content="User discussed project plans yesterday",
            importance=0.7,
            lock_in_coefficient=0.3
        ),
        sample_memory_node(
            node_type="semantic",
            content="Python is a programming language",
            importance=0.5,
            lock_in_coefficient=0.1
        ),
        sample_memory_node(
            node_type="procedural",
            content="To run tests: pytest tests/",
            importance=0.6,
            lock_in_coefficient=0.4
        ),
        sample_memory_node(
            node_type="entity",
            content="Marzipan: orange tabby cat, beloved pet",
            importance=0.95,
            lock_in_coefficient=0.9,
            metadata={"entity_type": "pet"}
        ),
    ]


# =============================================================================
# ASYNC HELPER FIXTURES
# =============================================================================

@pytest.fixture
def async_timeout():
    """
    Provide a configurable async timeout for tests.

    Usage:
        @pytest.mark.asyncio
        async def test_with_timeout(async_timeout):
            async with async_timeout(2.0):  # 2 second timeout
                await some_slow_operation()
    """
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _timeout(seconds: float = 5.0):
        try:
            yield asyncio.wait_for(asyncio.sleep(0), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    return _timeout


# =============================================================================
# EXTRACTION FIXTURES
# =============================================================================

@pytest.fixture
def sample_extraction_output():
    """
    Create sample extraction output for testing Scribe and Librarian.

    Usage:
        def test_librarian_filing(sample_extraction_output):
            output = sample_extraction_output
            assert len(output["objects"]) > 0
    """
    return {
        "objects": [
            {
                "id": "extract_001",
                "type": "fact",
                "content": "User prefers dark mode for coding",
                "confidence": 0.9,
                "source_turns": [1, 2],
            },
            {
                "id": "extract_002",
                "type": "preference",
                "content": "User likes Python over JavaScript",
                "confidence": 0.85,
                "source_turns": [3],
            },
        ],
        "edges": [
            {
                "source": "extract_001",
                "target": "extract_002",
                "type": "related",
                "weight": 0.7,
            },
        ],
        "entities": [
            {
                "id": "entity_user",
                "name": "User",
                "type": "person",
                "mentions": ["extract_001", "extract_002"],
            },
        ],
    }


# =============================================================================
# CONSCIOUSNESS FIXTURES
# =============================================================================

@pytest.fixture
def sample_attention_topics():
    """
    Create sample attention topics for consciousness testing.
    """
    return [
        {"topic": "current_task", "weight": 0.9, "decay_rate": 0.1},
        {"topic": "user_preference", "weight": 0.7, "decay_rate": 0.05},
        {"topic": "recent_memory", "weight": 0.5, "decay_rate": 0.2},
    ]


@pytest.fixture
def sample_personality_weights():
    """
    Create sample personality weights for testing.
    """
    return {
        "warmth": 0.8,
        "curiosity": 0.9,
        "playfulness": 0.7,
        "formality": 0.3,
        "verbosity": 0.5,
    }


# =============================================================================
# CLEANUP HELPERS
# =============================================================================

@pytest.fixture(autouse=True)
def cleanup_async_tasks():
    """
    Automatically cleanup any pending async tasks after each test.
    """
    yield
    # Get all tasks and cancel any that are still pending
    try:
        loop = asyncio.get_event_loop()
        pending = asyncio.all_tasks(loop)
        for task in pending:
            if not task.done():
                task.cancel()
    except RuntimeError:
        # No event loop running
        pass
