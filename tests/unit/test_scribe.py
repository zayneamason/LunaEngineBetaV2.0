"""
Unit Tests for ScribeActor (Ben Franklin)
=========================================

Tests for knowledge extraction including entity extraction,
memory type classification, and batch processing.

All LLM extraction calls are mocked - no real API calls.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from collections import deque

from luna.actors.base import Message


# =============================================================================
# ENTITY EXTRACTION TESTS
# =============================================================================

class TestScribeEntityExtraction:
    """Tests for entity extraction from conversations."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scribe_extracts_entities(self, mock_scribe_actor):
        """Test ScribeActor extracts entities from text."""
        # Mock the extraction response
        mock_response = {
            "objects": [
                {
                    "type": "FACT",
                    "content": "Alice is a software engineer",
                    "confidence": 0.9,
                    "entities": ["Alice"],
                }
            ],
            "edges": [],
            "entity_updates": [
                {
                    "entity_name": "Alice",
                    "entity_type": "person",
                    "facts": {"role": "software engineer"},
                    "update_type": "update",
                }
            ],
        }

        # Parse the mock response
        import json
        result = mock_scribe_actor._parse_extraction_response(
            json.dumps(mock_response),
            source_id="test-source"
        )

        extraction, entity_updates = result

        assert len(extraction.objects) == 1
        assert extraction.objects[0].content == "Alice is a software engineer"
        assert "Alice" in extraction.objects[0].entities
        assert len(entity_updates) == 1
        assert entity_updates[0].name == "Alice"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scribe_extracts_multiple_entities(self, mock_scribe_actor):
        """Test ScribeActor extracts multiple entities."""
        mock_response = {
            "objects": [
                {
                    "type": "RELATION",
                    "content": "Bob works with Carol on the project",
                    "confidence": 0.85,
                    "entities": ["Bob", "Carol"],
                }
            ],
            "edges": [
                {
                    "from_ref": "Bob",
                    "to_ref": "Carol",
                    "edge_type": "works_with",
                }
            ],
            "entity_updates": [],
        }

        import json
        result = mock_scribe_actor._parse_extraction_response(
            json.dumps(mock_response),
            source_id="test"
        )

        extraction, _ = result

        assert len(extraction.objects) == 1
        assert len(extraction.objects[0].entities) == 2
        assert len(extraction.edges) == 1
        assert extraction.edges[0].edge_type == "works_with"


# =============================================================================
# MEMORY TYPE CLASSIFICATION TESTS
# =============================================================================

class TestScribeClassification:
    """Tests for memory type classification."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scribe_classifies_memory_types(self, mock_scribe_actor):
        """Test ScribeActor classifies different memory types."""
        # Test various types are parsed correctly
        mock_response = {
            "objects": [
                {"type": "FACT", "content": "Luna uses Python", "confidence": 0.9, "entities": []},
                {"type": "PREFERENCE", "content": "User prefers dark mode", "confidence": 0.8, "entities": []},
                {"type": "DECISION", "content": "We will use SQLite", "confidence": 0.95, "entities": []},
                {"type": "PROBLEM", "content": "Memory usage too high", "confidence": 0.7, "entities": []},
            ],
            "edges": [],
            "entity_updates": [],
        }

        import json
        result = mock_scribe_actor._parse_extraction_response(
            json.dumps(mock_response),
            source_id="test"
        )

        extraction, _ = result

        types = [obj.type for obj in extraction.objects]
        assert "FACT" in types
        assert "PREFERENCE" in types
        assert "DECISION" in types
        assert "PROBLEM" in types

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scribe_handles_unknown_type(self, mock_scribe_actor):
        """Test ScribeActor handles unknown types gracefully."""
        mock_response = {
            "objects": [
                {"type": "UNKNOWN_TYPE", "content": "Some content", "confidence": 0.5, "entities": []},
            ],
            "edges": [],
            "entity_updates": [],
        }

        import json
        result = mock_scribe_actor._parse_extraction_response(
            json.dumps(mock_response),
            source_id="test"
        )

        extraction, _ = result

        # Unknown types should be mapped to FACT
        assert len(extraction.objects) == 1
        assert extraction.objects[0].type == "FACT"


# =============================================================================
# EMPTY INPUT HANDLING TESTS
# =============================================================================

class TestScribeEmptyInput:
    """Tests for handling empty or minimal input."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scribe_handles_empty_input(self, mock_scribe_actor):
        """Test ScribeActor handles empty extraction gracefully."""
        mock_response = {
            "objects": [],
            "edges": [],
            "entity_updates": [],
        }

        import json
        result = mock_scribe_actor._parse_extraction_response(
            json.dumps(mock_response),
            source_id="test"
        )

        extraction, entity_updates = result

        assert extraction.is_empty()
        assert len(entity_updates) == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scribe_skips_short_content(self, mock_scribe_actor):
        """Test ScribeActor skips content below minimum length."""
        mock_scribe_actor.config.min_content_length = 20

        # Create message with short content
        msg = Message(
            type="extract_turn",
            payload={
                "role": "user",
                "content": "Hi",  # Too short
                "turn_id": 1,
            }
        )

        # Process should complete without extraction
        await mock_scribe_actor._handle_extract_turn(msg)

        # Stack should be empty (content was skipped)
        assert len(mock_scribe_actor.stack) == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scribe_skips_assistant_turns(self, mock_scribe_actor):
        """Test ScribeActor skips assistant response turns."""
        msg = Message(
            type="extract_turn",
            payload={
                "role": "assistant",  # Should be skipped
                "content": "This is Luna's response, not user-provided info.",
                "turn_id": 1,
            }
        )

        await mock_scribe_actor._handle_extract_turn(msg)

        # Stack should be empty (assistant turns skipped)
        assert len(mock_scribe_actor.stack) == 0


# =============================================================================
# BATCH PROCESSING TESTS
# =============================================================================

class TestScribeBatchProcessing:
    """Tests for batch processing of extractions."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scribe_batch_processing(self, mock_scribe_actor):
        """Test ScribeActor batches chunks before processing."""
        mock_scribe_actor.config.batch_size = 3
        mock_scribe_actor.config.min_content_length = 5

        # Add chunks below batch threshold
        for i in range(2):
            msg = Message(
                type="extract_turn",
                payload={
                    "role": "user",
                    "content": f"This is test message number {i} with enough content",
                    "turn_id": i,
                }
            )
            await mock_scribe_actor._handle_extract_turn(msg)

        # Stack should have chunks but not processed yet (below batch_size)
        assert len(mock_scribe_actor.stack) <= 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scribe_immediate_processing(self, mock_scribe_actor):
        """Test ScribeActor processes immediately when requested."""
        mock_scribe_actor.config.min_content_length = 5

        # With immediate=True, should process right away
        msg = Message(
            type="extract_turn",
            payload={
                "role": "user",
                "content": "This content should be processed immediately without batching",
                "turn_id": 1,
                "immediate": True,
            }
        )

        await mock_scribe_actor._handle_extract_turn(msg)

        # Stack should be empty after immediate processing
        assert len(mock_scribe_actor.stack) == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scribe_flush_stack(self, mock_scribe_actor):
        """Test ScribeActor flushes pending stack."""
        from luna.extraction.chunker import Turn

        # Manually add chunks to stack
        mock_scribe_actor.config.min_content_length = 5

        msg = Message(
            type="extract_turn",
            payload={
                "role": "user",
                "content": "This is a test message with enough length to be processed",
                "turn_id": 1,
            }
        )
        await mock_scribe_actor._handle_extract_turn(msg)

        # Now flush
        await mock_scribe_actor._flush_stack()

        # Stack should be empty after flush
        assert len(mock_scribe_actor.stack) == 0


# =============================================================================
# STATS TESTS
# =============================================================================

class TestScribeStats:
    """Tests for extraction statistics."""

    @pytest.mark.unit
    def test_scribe_tracks_stats(self, mock_scribe_actor):
        """Test ScribeActor tracks extraction statistics."""
        stats = mock_scribe_actor.get_stats()

        assert "backend" in stats
        assert "extractions_count" in stats
        assert "objects_extracted" in stats
        assert "edges_extracted" in stats
        assert "stack_size" in stats
        assert "batch_size" in stats

    @pytest.mark.unit
    def test_scribe_initial_stats_zero(self, mock_scribe_actor):
        """Test ScribeActor starts with zero counts."""
        stats = mock_scribe_actor.get_stats()

        assert stats["extractions_count"] == 0
        assert stats["objects_extracted"] == 0
        assert stats["edges_extracted"] == 0


# =============================================================================
# JSON PARSING TESTS
# =============================================================================

class TestScribeJsonParsing:
    """Tests for JSON response parsing."""

    @pytest.mark.unit
    def test_scribe_parses_markdown_wrapped_json(self, mock_scribe_actor):
        """Test ScribeActor handles markdown-wrapped JSON."""
        markdown_json = '''```json
{
    "objects": [
        {"type": "FACT", "content": "Test", "confidence": 0.9, "entities": []}
    ],
    "edges": [],
    "entity_updates": []
}
```'''

        result = mock_scribe_actor._parse_extraction_response(
            markdown_json,
            source_id="test"
        )

        extraction, _ = result
        assert len(extraction.objects) == 1

    @pytest.mark.unit
    def test_scribe_handles_malformed_json(self, mock_scribe_actor):
        """Test ScribeActor handles malformed JSON gracefully."""
        malformed = "This is not JSON at all"

        result = mock_scribe_actor._parse_extraction_response(
            malformed,
            source_id="test"
        )

        extraction, entity_updates = result

        # Should return empty extraction, not crash
        assert extraction.is_empty()
        assert len(entity_updates) == 0

    @pytest.mark.unit
    def test_scribe_fixes_trailing_commas(self, mock_scribe_actor):
        """Test ScribeActor fixes trailing commas in JSON."""
        json_with_trailing = '''{
    "objects": [
        {"type": "FACT", "content": "Test", "confidence": 0.9, "entities": []},
    ],
    "edges": [],
    "entity_updates": []
}'''

        result = mock_scribe_actor._parse_extraction_response(
            json_with_trailing,
            source_id="test"
        )

        extraction, _ = result
        # Should parse successfully despite trailing comma
        assert len(extraction.objects) == 1


# =============================================================================
# COMPRESSION TESTS
# =============================================================================

class TestScribeCompression:
    """Tests for turn compression functionality."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scribe_compresses_short_content_unchanged(self, mock_scribe_actor):
        """Test ScribeActor returns short content unchanged."""
        short_content = "Hello world"

        compressed = await mock_scribe_actor.compress_turn(short_content, "user")

        # Content under 100 chars should return unchanged
        assert compressed == short_content

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_scribe_compression_fallback(self, mock_scribe_actor):
        """Test ScribeActor uses truncation fallback when LLM unavailable."""
        mock_scribe_actor._client = None
        mock_scribe_actor.engine = None

        long_content = "A" * 300  # Longer than 200 chars

        compressed = await mock_scribe_actor.compress_turn(long_content, "user")

        # Should be truncated to 200 chars + "..."
        assert len(compressed) == 203  # 200 + "..."
        assert compressed.endswith("...")
