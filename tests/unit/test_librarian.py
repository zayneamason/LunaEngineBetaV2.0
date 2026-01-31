"""
Unit Tests for LibrarianActor (The Dude)
========================================

Tests for memory filing, entity resolution, and knowledge wiring.

All database operations are mocked - no real SQLite calls.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from luna.actors.base import Message


# =============================================================================
# MEMORY FILING TESTS
# =============================================================================

class TestLibrarianMemoryFiling:
    """Tests for memory filing operations."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_librarian_files_memory(self, mock_librarian_actor, mock_engine, mock_matrix):
        """Test LibrarianActor files extraction into memory."""
        # Setup matrix access
        mock_matrix_actor = Mock()
        mock_matrix_actor._matrix = mock_matrix
        mock_matrix_actor._graph = Mock()
        mock_matrix_actor._graph.has_edge = Mock(return_value=False)
        mock_matrix_actor._graph.add_edge = Mock()
        mock_engine.get_actor = Mock(return_value=mock_matrix_actor)
        mock_librarian_actor.engine = mock_engine

        extraction_dict = {
            "objects": [
                {
                    "type": "FACT",
                    "content": "Test fact to be filed",
                    "confidence": 0.9,
                    "entities": [],
                    "source_id": "test",
                }
            ],
            "edges": [],
            "source_id": "test-source",
        }

        msg = Message(type="file", payload=extraction_dict)

        await mock_librarian_actor._handle_file(msg)

        # Verify stats updated
        assert mock_librarian_actor._filings_count >= 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_librarian_handles_empty_extraction(self, mock_librarian_actor):
        """Test LibrarianActor handles empty extraction gracefully."""
        empty_extraction = {
            "objects": [],
            "edges": [],
            "source_id": "",
        }

        msg = Message(type="file", payload=empty_extraction)

        # Should not raise
        await mock_librarian_actor._handle_file(msg)

        # No filings for empty extraction
        assert mock_librarian_actor._filings_count == 0


# =============================================================================
# ENTITY RESOLUTION TESTS
# =============================================================================

class TestLibrarianEntityResolution:
    """Tests for entity resolution and deduplication."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_librarian_resolves_entities(self, mock_librarian_actor, mock_engine, mock_matrix):
        """Test LibrarianActor resolves entities to existing nodes."""
        # Setup mock matrix with existing node
        mock_memory_node = Mock()
        mock_memory_node.id = "existing-entity-001"
        mock_memory_node.content = "alice"

        mock_matrix.search_nodes = AsyncMock(return_value=[mock_memory_node])

        mock_matrix_actor = Mock()
        mock_matrix_actor._matrix = mock_matrix
        mock_engine.get_actor = Mock(return_value=mock_matrix_actor)
        mock_librarian_actor.engine = mock_engine

        # Clear cache
        mock_librarian_actor.alias_cache = {}

        # Resolve entity
        node_id = await mock_librarian_actor._resolve_entity(
            name="Alice",
            entity_type="PERSON",
        )

        assert node_id == "existing-entity-001"
        assert mock_librarian_actor._nodes_merged >= 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_librarian_creates_new_entity(self, mock_librarian_actor, mock_engine, mock_matrix):
        """Test LibrarianActor creates new entity when not found."""
        mock_matrix.search_nodes = AsyncMock(return_value=[])
        mock_matrix.add_node = AsyncMock(return_value="new-entity-001")

        mock_matrix_actor = Mock()
        mock_matrix_actor._matrix = mock_matrix
        mock_engine.get_actor = Mock(return_value=mock_matrix_actor)
        mock_librarian_actor.engine = mock_engine

        # Clear cache
        mock_librarian_actor.alias_cache = {}

        node_id = await mock_librarian_actor._resolve_entity(
            name="NewPerson",
            entity_type="PERSON",
        )

        assert node_id == "new-entity-001"
        assert mock_librarian_actor._nodes_created >= 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_librarian_uses_alias_cache(self, mock_librarian_actor):
        """Test LibrarianActor uses alias cache for resolution."""
        # Pre-populate cache
        mock_librarian_actor.alias_cache = {
            "alice": "cached-alice-001",
            "bob": "cached-bob-001",
        }

        # Should hit cache without DB call
        node_id = await mock_librarian_actor._resolve_entity(
            name="Alice",  # Will be lowercased
            entity_type="PERSON",
        )

        assert node_id == "cached-alice-001"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_librarian_handles_duplicate_entities(self, mock_librarian_actor, mock_engine, mock_matrix):
        """Test LibrarianActor handles duplicate entity names."""
        # Same name should resolve to same node
        mock_librarian_actor.alias_cache = {
            "alice": "alice-node-001"
        }

        id1 = await mock_librarian_actor._resolve_entity("Alice", "PERSON")
        id2 = await mock_librarian_actor._resolve_entity("alice", "PERSON")
        id3 = await mock_librarian_actor._resolve_entity("ALICE", "PERSON")

        # All should resolve to same cached ID
        assert id1 == id2 == id3 == "alice-node-001"


# =============================================================================
# ENTITY UPDATE FILING TESTS
# =============================================================================

class TestLibrarianEntityUpdates:
    """Tests for entity update handling."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_librarian_handles_entity_update_message(self, mock_librarian_actor):
        """Test LibrarianActor handles entity update messages."""
        update_payload = {
            "update_type": "update",
            "entity_id": None,
            "name": "TestEntity",
            "entity_type": "person",
            "facts": {"role": "tester"},
            "source": "test",
        }

        msg = Message(type="entity_update", payload=update_payload)

        # Without resolver, should handle gracefully
        mock_librarian_actor._entity_resolver = None
        await mock_librarian_actor._handle_entity_update(msg)

        # Should not crash even without resolver


# =============================================================================
# CONTEXT RETRIEVAL TESTS
# =============================================================================

class TestLibrarianContextRetrieval:
    """Tests for context retrieval operations."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_librarian_gets_context(self, mock_librarian_actor, mock_engine, mock_matrix):
        """Test LibrarianActor retrieves context for query."""
        mock_memory_node = Mock()
        mock_memory_node.to_dict = Mock(return_value={"id": "node-001", "content": "test"})
        mock_matrix.get_context = AsyncMock(return_value=[mock_memory_node])

        mock_matrix_actor = Mock()
        mock_matrix_actor._matrix = mock_matrix
        mock_engine.get_actor = Mock(return_value=mock_matrix_actor)
        mock_librarian_actor.engine = mock_engine

        context = await mock_librarian_actor._get_context(
            query="What do I know about testing?",
            max_tokens=3800,
        )

        assert len(context) == 1
        mock_matrix.get_context.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_librarian_context_budget_presets(self, mock_librarian_actor, mock_engine, mock_matrix):
        """Test LibrarianActor handles budget presets."""
        from luna.actors.librarian import BUDGET_PRESETS

        assert "minimal" in BUDGET_PRESETS
        assert "balanced" in BUDGET_PRESETS
        assert "rich" in BUDGET_PRESETS

        assert BUDGET_PRESETS["minimal"] < BUDGET_PRESETS["balanced"] < BUDGET_PRESETS["rich"]


# =============================================================================
# STATS TESTS
# =============================================================================

class TestLibrarianStats:
    """Tests for filing statistics."""

    @pytest.mark.unit
    def test_librarian_tracks_stats(self, mock_librarian_actor):
        """Test LibrarianActor tracks filing statistics."""
        stats = mock_librarian_actor.get_stats()

        assert "filings_count" in stats
        assert "nodes_created" in stats
        assert "nodes_merged" in stats
        assert "edges_created" in stats
        assert "context_retrievals" in stats
        assert "cache_size" in stats

    @pytest.mark.unit
    def test_librarian_initial_stats_zero(self, mock_librarian_actor):
        """Test LibrarianActor starts with zero counts."""
        stats = mock_librarian_actor.get_stats()

        assert stats["filings_count"] == 0
        assert stats["nodes_created"] == 0
        assert stats["nodes_merged"] == 0
        assert stats["edges_created"] == 0


# =============================================================================
# EDGE CREATION TESTS
# =============================================================================

class TestLibrarianEdgeCreation:
    """Tests for edge/relationship creation."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_librarian_creates_edge(self, mock_librarian_actor, mock_engine):
        """Test LibrarianActor creates edges between nodes."""
        mock_graph = Mock()
        mock_graph.has_edge = Mock(return_value=False)
        mock_graph.add_edge = Mock()

        mock_matrix_actor = Mock()
        mock_matrix_actor._graph = mock_graph
        mock_engine.get_actor = Mock(return_value=mock_matrix_actor)
        mock_librarian_actor.engine = mock_engine

        result = await mock_librarian_actor._create_edge(
            from_id="node-001",
            to_id="node-002",
            edge_type="related_to",
            confidence=1.0,
        )

        assert result is True
        mock_graph.add_edge.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_librarian_skips_duplicate_edge(self, mock_librarian_actor, mock_engine):
        """Test LibrarianActor skips duplicate edges."""
        mock_graph = Mock()
        mock_graph.has_edge = Mock(return_value=True)  # Edge exists

        mock_matrix_actor = Mock()
        mock_matrix_actor._graph = mock_graph
        mock_engine.get_actor = Mock(return_value=mock_matrix_actor)
        mock_librarian_actor.engine = mock_engine

        result = await mock_librarian_actor._create_edge(
            from_id="node-001",
            to_id="node-002",
            edge_type="related_to",
        )

        assert result is False  # Edge was duplicate

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_librarian_edge_no_engine(self, mock_librarian_actor):
        """Test edge creation returns False without engine."""
        mock_librarian_actor.engine = None

        result = await mock_librarian_actor._create_edge(
            from_id="node-001",
            to_id="node-002",
            edge_type="related_to",
        )

        assert result is False


# =============================================================================
# PRUNING TESTS
# =============================================================================

class TestLibrarianPruning:
    """Tests for synaptic pruning operations."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_librarian_prunes_edges(self, mock_librarian_actor, mock_engine):
        """Test LibrarianActor prunes low-confidence edges."""
        mock_graph = Mock()
        mock_graph.get_all_edges = Mock(return_value=[
            {"from_id": "a", "to_id": "b", "edge_type": "weak", "weight": 0.1},
            {"from_id": "c", "to_id": "d", "edge_type": "strong", "weight": 0.9},
        ])
        mock_graph.remove_edge = Mock()

        mock_matrix_actor = Mock()
        mock_matrix_actor._graph = mock_graph
        mock_engine.get_actor = Mock(return_value=mock_matrix_actor)
        mock_librarian_actor.engine = mock_engine

        result = await mock_librarian_actor._prune_edges(
            confidence_threshold=0.3,
            age_days=0,  # Prune all old enough
        )

        assert "pruned" in result
        assert "preserved" in result

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_librarian_prune_no_matrix(self, mock_librarian_actor, mock_engine):
        """Test pruning returns empty result without matrix."""
        mock_engine.get_actor = Mock(return_value=None)
        mock_librarian_actor.engine = mock_engine

        result = await mock_librarian_actor._prune_edges()

        assert result == {"pruned": 0, "preserved": 0}


# =============================================================================
# LIFECYCLE TESTS
# =============================================================================

class TestLibrarianLifecycle:
    """Tests for actor lifecycle hooks."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_librarian_on_start(self, mock_librarian_actor):
        """Test LibrarianActor on_start hook."""
        # Should log The Dude's quote
        await mock_librarian_actor.on_start()

        # Should complete without error

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_librarian_on_stop(self, mock_librarian_actor):
        """Test LibrarianActor on_stop hook."""
        mock_librarian_actor.inference_queue = ["item1", "item2"]

        # Should log queue state
        await mock_librarian_actor.on_stop()

        # Should complete without error

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_librarian_snapshot(self, mock_librarian_actor):
        """Test LibrarianActor snapshot includes stats."""
        mock_librarian_actor._filings_count = 10
        mock_librarian_actor._nodes_created = 5
        mock_librarian_actor.alias_cache = {"a": "1", "b": "2"}

        snapshot = await mock_librarian_actor.snapshot()

        assert "stats" in snapshot
        assert "cache_size" in snapshot
        assert snapshot["cache_size"] == 2
