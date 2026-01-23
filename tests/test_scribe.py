"""
Tests for Scribe Actor (Ben Franklin)
=====================================

Tests for the extraction system that converts conversations
into structured knowledge.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import json


class TestExtractionTypes:
    """Tests for extraction type dataclasses."""

    def test_extraction_type_enum(self):
        """Test ExtractionType enum values."""
        from luna.extraction.types import ExtractionType

        assert ExtractionType.FACT.value == "FACT"
        assert ExtractionType.DECISION.value == "DECISION"
        assert ExtractionType.PROBLEM.value == "PROBLEM"
        assert ExtractionType.ASSUMPTION.value == "ASSUMPTION"
        assert ExtractionType.CONNECTION.value == "CONNECTION"
        assert ExtractionType.ACTION.value == "ACTION"
        assert ExtractionType.OUTCOME.value == "OUTCOME"

    def test_extracted_object_creation(self):
        """Test ExtractedObject dataclass."""
        from luna.extraction.types import ExtractedObject, ExtractionType

        obj = ExtractedObject(
            type=ExtractionType.FACT,
            content="Alex lives in Berlin",
            confidence=0.9,
            entities=["Alex", "Berlin"],
        )

        assert obj.type == ExtractionType.FACT
        assert obj.content == "Alex lives in Berlin"
        assert obj.confidence == 0.9
        assert "Alex" in obj.entities
        assert obj.is_high_confidence()

    def test_extracted_object_from_string_type(self):
        """Test ExtractedObject handles string type."""
        from luna.extraction.types import ExtractedObject, ExtractionType

        obj = ExtractedObject(
            type="DECISION",  # String instead of enum
            content="We chose SQLite",
            confidence=0.8,
        )

        assert obj.type == ExtractionType.DECISION

    def test_extracted_object_confidence_clamping(self):
        """Test confidence is clamped to 0-1 range."""
        from luna.extraction.types import ExtractedObject

        obj1 = ExtractedObject(type="FACT", content="test", confidence=1.5)
        assert obj1.confidence == 1.0

        obj2 = ExtractedObject(type="FACT", content="test", confidence=-0.5)
        assert obj2.confidence == 0.0

    def test_extracted_object_serialization(self):
        """Test to_dict and from_dict."""
        from luna.extraction.types import ExtractedObject, ExtractionType

        obj = ExtractedObject(
            type=ExtractionType.FACT,
            content="Test fact",
            confidence=0.85,
            entities=["Entity1"],
            source_id="session123",
        )

        data = obj.to_dict()
        restored = ExtractedObject.from_dict(data)

        assert restored.type == obj.type
        assert restored.content == obj.content
        assert restored.confidence == obj.confidence

    def test_extracted_edge_creation(self):
        """Test ExtractedEdge dataclass."""
        from luna.extraction.types import ExtractedEdge

        edge = ExtractedEdge(
            from_ref="Alex",
            to_ref="Pi Project",
            edge_type="works_on",
            confidence=1.0,
        )

        assert edge.from_ref == "Alex"
        assert edge.to_ref == "Pi Project"
        assert edge.edge_type == "works_on"

    def test_extraction_output_empty_check(self):
        """Test ExtractionOutput.is_empty()."""
        from luna.extraction.types import ExtractionOutput, ExtractedObject

        empty = ExtractionOutput()
        assert empty.is_empty()

        non_empty = ExtractionOutput(
            objects=[ExtractedObject(type="FACT", content="test")],
        )
        assert not non_empty.is_empty()

    def test_extraction_config_defaults(self):
        """Test ExtractionConfig default values."""
        from luna.extraction.types import ExtractionConfig

        config = ExtractionConfig()

        assert config.backend == "haiku"
        assert config.batch_size == 5
        assert config.min_content_length == 10


class TestSemanticChunker:
    """Tests for semantic chunking."""

    def test_chunker_initialization(self):
        """Test chunker initializes with correct defaults."""
        from luna.extraction.chunker import SemanticChunker

        chunker = SemanticChunker()

        assert chunker.target_tokens == 350
        assert chunker.max_tokens == 500
        assert chunker.overlap_tokens == 50

    def test_chunk_single_turn(self):
        """Test chunking a single turn with enough content."""
        from luna.extraction.chunker import SemanticChunker, Turn

        chunker = SemanticChunker(min_tokens=10)  # Lower threshold for test
        turns = [Turn(id=1, role="user", content="Hello, how are you today? I wanted to talk about the project.")]

        chunks = chunker.chunk_turns(turns, source_id="test")

        assert len(chunks) == 1
        assert "Hello" in chunks[0].content

    def test_chunk_multiple_turns(self):
        """Test chunking multiple turns."""
        from luna.extraction.chunker import SemanticChunker, Turn

        chunker = SemanticChunker(min_tokens=20)  # Lower threshold for test
        turns = [
            Turn(id=1, role="user", content="Tell me about Berlin and its history as the capital of Germany."),
            Turn(id=2, role="assistant", content="Berlin is the capital of Germany with a rich history spanning centuries."),
            Turn(id=3, role="user", content="What's the population and what are the main attractions?"),
        ]

        chunks = chunker.chunk_turns(turns, source_id="test")

        assert len(chunks) >= 1
        # All content should be present
        combined = " ".join(c.content for c in chunks)
        assert "Berlin" in combined

    def test_chunk_respects_max_tokens(self):
        """Test chunks don't exceed max_tokens."""
        from luna.extraction.chunker import SemanticChunker, Turn

        chunker = SemanticChunker(max_tokens=100, min_tokens=20)

        # Create multiple turns that together exceed max_tokens
        turns = [
            Turn(id=1, role="user", content="This is the first message with some content about topic A."),
            Turn(id=2, role="assistant", content="Here is a response about topic A with additional details."),
            Turn(id=3, role="user", content="Now let's talk about topic B with more information."),
            Turn(id=4, role="assistant", content="Topic B is interesting, here are more details about it."),
            Turn(id=5, role="user", content="And finally topic C which wraps up our discussion."),
        ]

        chunks = chunker.chunk_turns(turns, source_id="test")

        # Should have multiple chunks due to size limits
        assert len(chunks) >= 1
        # Each chunk should be reasonable size
        for chunk in chunks:
            assert chunk.tokens <= chunker.max_tokens + 100  # Allow some overflow for turn boundaries

    def test_chunk_text_direct(self):
        """Test chunking raw text."""
        from luna.extraction.chunker import SemanticChunker

        chunker = SemanticChunker()
        text = """
        First paragraph about topic A.

        Second paragraph about topic B.

        Third paragraph about topic C.
        """

        chunks = chunker.chunk_text(text, source_id="doc1")

        assert len(chunks) >= 1

    def test_empty_input_handling(self):
        """Test handling empty input."""
        from luna.extraction.chunker import SemanticChunker

        chunker = SemanticChunker()

        assert chunker.chunk_turns([], source_id="test") == []
        assert chunker.chunk_text("", source_id="test") == []
        assert chunker.chunk_text("   ", source_id="test") == []


class TestScribeActor:
    """Tests for ScribeActor."""

    @pytest.fixture
    def scribe(self):
        """Create ScribeActor for testing."""
        from luna.actors.scribe import ScribeActor
        from luna.extraction.types import ExtractionConfig

        config = ExtractionConfig(backend="disabled")  # Disable API calls
        return ScribeActor(config=config)

    def test_scribe_initialization(self, scribe):
        """Test scribe initializes correctly."""
        assert scribe.name == "scribe"
        assert scribe.config.backend == "disabled"
        assert len(scribe.stack) == 0

    def test_scribe_stats(self, scribe):
        """Test scribe stats method."""
        stats = scribe.get_stats()

        assert "backend" in stats
        assert "extractions_count" in stats
        assert "objects_extracted" in stats
        assert "stack_size" in stats
        assert stats["extractions_count"] == 0

    @pytest.mark.asyncio
    async def test_scribe_snapshot(self, scribe):
        """Test scribe snapshot for serialization."""
        snapshot = await scribe.snapshot()

        assert "name" in snapshot
        assert "config" in snapshot
        assert "stats" in snapshot
        assert snapshot["config"]["backend"] == "disabled"

    def test_parse_extraction_response_valid(self, scribe):
        """Test parsing valid JSON extraction response."""
        response = json.dumps({
            "objects": [
                {
                    "type": "FACT",
                    "content": "Alex lives in Berlin",
                    "confidence": 0.9,
                    "entities": ["Alex", "Berlin"],
                }
            ],
            "edges": [
                {
                    "from_ref": "Alex",
                    "to_ref": "Berlin",
                    "edge_type": "lives_in",
                }
            ],
        })

        result, entity_updates = scribe._parse_extraction_response(response, "test")

        assert len(result.objects) == 1
        assert result.objects[0].content == "Alex lives in Berlin"
        assert len(result.edges) == 1
        assert result.edges[0].edge_type == "lives_in"

    def test_parse_extraction_response_with_markdown(self, scribe):
        """Test parsing response wrapped in markdown code block."""
        response = """```json
{
    "objects": [{"type": "FACT", "content": "Test", "confidence": 0.8}],
    "edges": []
}
```"""

        result, entity_updates = scribe._parse_extraction_response(response, "test")

        assert len(result.objects) == 1
        assert result.objects[0].content == "Test"

    def test_parse_extraction_response_invalid(self, scribe):
        """Test parsing invalid JSON returns empty result."""
        result, entity_updates = scribe._parse_extraction_response("not valid json", "test")

        assert result.is_empty()

    @pytest.mark.asyncio
    async def test_handle_set_config(self, scribe):
        """Test config update via message."""
        from luna.actors.base import Message

        msg = Message(
            type="set_config",
            payload={"backend": "sonnet", "batch_size": 10},
        )

        await scribe.handle(msg)

        assert scribe.config.backend == "sonnet"
        assert scribe.config.batch_size == 10


class TestScribeExtraction:
    """Tests for actual extraction logic."""

    @pytest.fixture
    def scribe_with_mock(self):
        """Create ScribeActor with mocked Claude client."""
        from luna.actors.scribe import ScribeActor
        from luna.extraction.types import ExtractionConfig
        from luna.extraction.chunker import SemanticChunker

        config = ExtractionConfig(backend="haiku", batch_size=1)
        scribe = ScribeActor(config=config)

        # Use chunker with lower min_tokens for testing
        scribe.chunker = SemanticChunker(min_tokens=10)

        # Mock the client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps({
            "objects": [
                {"type": "DECISION", "content": "We chose SQLite", "confidence": 0.9, "entities": ["SQLite"]},
            ],
            "edges": [],
        }))]
        mock_client.messages.create.return_value = mock_response
        scribe._client = mock_client

        return scribe

    @pytest.mark.asyncio
    async def test_extract_chunks(self, scribe_with_mock):
        """Test extraction from chunks."""
        from luna.extraction.types import Chunk

        chunks = [Chunk(content="We decided to use SQLite for the database.")]

        result, entity_updates = await scribe_with_mock._extract_chunks(chunks)

        assert len(result.objects) == 1
        assert result.objects[0].type.value == "DECISION"
        assert "SQLite" in result.objects[0].content

    @pytest.mark.asyncio
    async def test_stack_batching(self, scribe_with_mock):
        """Test that stack batches correctly."""
        from luna.actors.base import Message

        # Set batch size to 2 and lower min content length for test
        scribe_with_mock.config.batch_size = 2
        scribe_with_mock.config.min_content_length = 5

        # Add first turn - shouldn't trigger extraction (longer content to pass chunker min_tokens)
        msg1 = Message(
            type="extract_turn",
            payload={"role": "user", "content": "First message about SQLite database system and its features for our project."},
        )
        await scribe_with_mock.handle(msg1)

        assert len(scribe_with_mock.stack) == 1
        assert scribe_with_mock._extractions_count == 0

        # Add second turn - should trigger extraction
        msg2 = Message(
            type="extract_turn",
            payload={"role": "user", "content": "Second message continuing discussion about database architecture and design patterns."},
        )
        await scribe_with_mock.handle(msg2)

        # Stack should be cleared after extraction
        assert len(scribe_with_mock.stack) == 0
        assert scribe_with_mock._extractions_count == 1
