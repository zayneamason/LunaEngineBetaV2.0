"""
Tests for Librarian Actor (The Dude)
====================================

Tests for the filing system that wires extractions into the Memory Matrix.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestFilingResult:
    """Tests for FilingResult dataclass."""

    def test_filing_result_creation(self):
        """Test FilingResult dataclass."""
        from luna.extraction.types import FilingResult

        result = FilingResult(
            nodes_created=["node1", "node2"],
            nodes_merged=[("Alex", "existing_id")],
            edges_created=["edge1"],
            edges_skipped=["duplicate: A->B"],
            filing_time_ms=50,
        )

        assert len(result.nodes_created) == 2
        assert len(result.nodes_merged) == 1
        assert len(result) == 3  # created + merged

    def test_filing_result_serialization(self):
        """Test FilingResult to_dict."""
        from luna.extraction.types import FilingResult

        result = FilingResult(
            nodes_created=["node1"],
            filing_time_ms=25,
        )

        data = result.to_dict()

        assert "nodes_created" in data
        assert "filing_time_ms" in data
        assert data["filing_time_ms"] == 25


class TestLibrarianActor:
    """Tests for LibrarianActor."""

    @pytest.fixture
    def librarian(self):
        """Create LibrarianActor for testing."""
        from luna.actors.librarian import LibrarianActor

        lib = LibrarianActor()
        return lib

    def test_librarian_initialization(self, librarian):
        """Test librarian initializes correctly."""
        assert librarian.name == "librarian"
        assert len(librarian.alias_cache) == 0
        assert librarian.batch_threshold == 10

    def test_librarian_stats(self, librarian):
        """Test librarian stats method."""
        stats = librarian.get_stats()

        assert "filings_count" in stats
        assert "nodes_created" in stats
        assert "edges_created" in stats
        assert "cache_size" in stats
        assert stats["filings_count"] == 0

    @pytest.mark.asyncio
    async def test_librarian_snapshot(self, librarian):
        """Test librarian snapshot for serialization."""
        snapshot = await librarian.snapshot()

        assert "name" in snapshot
        assert "stats" in snapshot
        assert "cache_size" in snapshot

    def test_budget_presets(self):
        """Test context budget presets are defined."""
        from luna.actors.librarian import BUDGET_PRESETS

        assert "minimal" in BUDGET_PRESETS
        assert "balanced" in BUDGET_PRESETS
        assert "rich" in BUDGET_PRESETS
        assert BUDGET_PRESETS["minimal"] < BUDGET_PRESETS["balanced"]
        assert BUDGET_PRESETS["balanced"] < BUDGET_PRESETS["rich"]


class TestEntityResolution:
    """Tests for entity resolution logic."""

    @pytest.fixture
    def librarian_with_cache(self):
        """Create LibrarianActor with pre-populated cache."""
        from luna.actors.librarian import LibrarianActor

        lib = LibrarianActor()
        lib.alias_cache = {
            "alex": "node_alex_123",
            "berlin": "node_berlin_456",
        }
        return lib

    @pytest.mark.asyncio
    async def test_cache_hit(self, librarian_with_cache):
        """Test entity resolution from cache."""
        lib = librarian_with_cache

        # This should hit cache (no engine needed)
        node_id = await lib._resolve_entity("Alex", "PERSON")

        assert node_id == "node_alex_123"

    @pytest.mark.asyncio
    async def test_cache_case_insensitive(self, librarian_with_cache):
        """Test cache lookup is case insensitive."""
        lib = librarian_with_cache

        # Different cases should resolve to same node
        id1 = await lib._resolve_entity("alex", "PERSON")
        id2 = await lib._resolve_entity("ALEX", "PERSON")
        id3 = await lib._resolve_entity("Alex", "PERSON")

        assert id1 == id2 == id3


class TestKnowledgeWiring:
    """Tests for knowledge wiring logic."""

    @pytest.fixture
    def librarian_isolated(self):
        """Create LibrarianActor without engine connection."""
        from luna.actors.librarian import LibrarianActor

        lib = LibrarianActor()
        lib.alias_cache = {}
        return lib

    @pytest.mark.asyncio
    async def test_wire_empty_extraction(self, librarian_isolated):
        """Test wiring empty extraction."""
        from luna.extraction.types import ExtractionOutput

        empty = ExtractionOutput()
        result = await librarian_isolated._wire_extraction(empty)

        assert len(result.nodes_created) == 0
        assert len(result.edges_created) == 0

    @pytest.mark.asyncio
    async def test_wire_single_object(self, librarian_isolated):
        """Test wiring single extracted object."""
        from luna.extraction.types import ExtractionOutput, ExtractedObject

        extraction = ExtractionOutput(
            objects=[
                ExtractedObject(
                    type="FACT",
                    content="Test fact",
                    confidence=0.9,
                    entities=[],
                )
            ],
            source_id="test",
        )

        result = await librarian_isolated._wire_extraction(extraction)

        # Should create a node (since no cache hit)
        assert len(result.nodes_created) == 1 or len(result.nodes_merged) == 1
        assert result.filing_time_ms >= 0


class TestContextRetrieval:
    """Tests for context retrieval."""

    @pytest.fixture
    def librarian_with_mock_matrix(self):
        """Create LibrarianActor with mocked matrix."""
        from luna.actors.librarian import LibrarianActor
        from unittest.mock import AsyncMock

        lib = LibrarianActor()

        # Mock the _get_matrix method
        mock_matrix = MagicMock()
        mock_matrix.get_context = AsyncMock(return_value=[])
        lib._get_matrix = AsyncMock(return_value=mock_matrix)

        return lib

    @pytest.mark.asyncio
    async def test_get_context_empty(self, librarian_with_mock_matrix):
        """Test context retrieval with no results."""
        lib = librarian_with_mock_matrix

        result = await lib._get_context("test query", max_tokens=2000)

        assert result == []


class TestSynapticPruning:
    """Tests for synaptic pruning logic."""

    @pytest.mark.asyncio
    async def test_prune_no_engine(self):
        """Test pruning without engine returns empty result."""
        from luna.actors.librarian import LibrarianActor

        lib = LibrarianActor()
        result = await lib._prune_edges()

        assert result["pruned"] == 0
        assert result["preserved"] == 0


class TestMessageHandling:
    """Tests for message handling."""

    @pytest.fixture
    def librarian(self):
        """Create LibrarianActor for testing."""
        from luna.actors.librarian import LibrarianActor

        return LibrarianActor()

    @pytest.mark.asyncio
    async def test_handle_file_empty(self, librarian):
        """Test handling file message with empty payload."""
        from luna.actors.base import Message

        msg = Message(type="file", payload={})
        await librarian.handle(msg)

        # Should not crash, just log debug message
        assert librarian._filings_count == 0

    @pytest.mark.asyncio
    async def test_handle_file_with_extraction(self, librarian):
        """Test handling file message with extraction data."""
        from luna.actors.base import Message

        msg = Message(
            type="file",
            payload={
                "objects": [
                    {"type": "FACT", "content": "Test", "confidence": 0.9, "entities": []},
                ],
                "edges": [],
                "source_id": "test",
            },
        )

        await librarian.handle(msg)

        assert librarian._filings_count == 1

    @pytest.mark.asyncio
    async def test_handle_unknown_message(self, librarian):
        """Test handling unknown message type."""
        from luna.actors.base import Message

        msg = Message(type="unknown_type", payload={})
        await librarian.handle(msg)

        # Should not crash, just log warning
        assert True  # If we get here, it didn't crash


class TestLibrarianIntegration:
    """Integration tests for Librarian with other components."""

    @pytest.mark.asyncio
    async def test_scribe_to_librarian_flow(self):
        """Test extraction flows from Scribe to Librarian."""
        from luna.extraction.types import ExtractionOutput, ExtractedObject
        from luna.actors.librarian import LibrarianActor

        # Create extraction output (as Scribe would produce)
        extraction = ExtractionOutput(
            objects=[
                ExtractedObject(
                    type="DECISION",
                    content="We chose SQLite for the database",
                    confidence=0.9,
                    entities=["SQLite"],
                    source_id="session123",
                ),
            ],
            edges=[],
            source_id="session123",
            extraction_time_ms=150,
        )

        # Librarian receives and files it
        librarian = LibrarianActor()
        result = await librarian._wire_extraction(extraction)

        # Verify filing happened
        assert result.filing_time_ms >= 0
        total_nodes = len(result.nodes_created) + len(result.nodes_merged)
        assert total_nodes >= 1  # At least the decision node
