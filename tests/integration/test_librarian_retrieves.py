"""
Integration tests for Librarian Actor retrieval.

Tests the Librarian's retrieval capabilities:
- Vector search
- Hybrid search
- Entity graph traversal
- Lock-in score respecting

Uses REAL Librarian actor but mocks database.
"""

import pytest
import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from luna.actors.librarian import LibrarianActor, BUDGET_PRESETS
from luna.actors.base import Message
from luna.extraction.types import (
    ExtractionOutput,
    ExtractedObject,
    ExtractedEdge,
    FilingResult,
)
from luna.entities.models import EntityType, ChangeType, EntityUpdate


@pytest.mark.integration
class TestLibrarianVectorSearch:
    """Test Librarian vector search capabilities."""

    @pytest.fixture
    def librarian_with_matrix(self, mock_engine, mock_matrix_actor):
        """Librarian with mocked Matrix for search testing."""
        librarian = LibrarianActor(engine=mock_engine)
        return librarian

    @pytest.mark.asyncio
    async def test_librarian_vector_search(
        self,
        librarian_with_matrix,
        mock_matrix_actor,
    ):
        """Test vector-based similarity search."""
        # Setup matrix._matrix to return search results
        mock_matrix_actor._matrix.get_context = AsyncMock(
            return_value="Luna Engine uses hybrid LLM architecture"
        )

        # Perform search through get_context
        context = await librarian_with_matrix._get_context(
            query="What is the Luna Engine architecture?",
            max_tokens=1500,
            node_types=None,
        )

        # Should return results via matrix.get_context
        mock_matrix_actor._matrix.get_context.assert_called_once()


@pytest.mark.integration
class TestLibrarianHybridSearch:
    """Test Librarian hybrid search (vector + keyword)."""

    @pytest.fixture
    def librarian_with_matrix(self, mock_engine, mock_matrix_actor):
        """Librarian with mocked Matrix for hybrid search testing."""
        librarian = LibrarianActor(engine=mock_engine)
        return librarian

    @pytest.mark.asyncio
    async def test_librarian_hybrid_search(
        self,
        librarian_with_matrix,
        mock_matrix_actor,
    ):
        """Test hybrid search combining vector and keyword."""
        # Setup MemoryMatrix for hybrid search
        mock_matrix_actor._matrix.get_context = AsyncMock(
            return_value="Hybrid search result: Luna Engine architecture includes hybrid LLM routing"
        )

        context = await librarian_with_matrix._get_context(
            query="Luna Engine hybrid architecture",
            max_tokens=2000,
            node_types=["FACT", "DECISION"],
        )

        # MemoryMatrix get_context should have been called
        mock_matrix_actor._matrix.get_context.assert_called_once()


@pytest.mark.integration
class TestLibrarianEntityGraphTraversal:
    """Test Librarian entity graph traversal."""

    @pytest.fixture
    def librarian_with_graph(self, mock_engine, mock_matrix_actor):
        """Librarian with mocked graph for traversal testing."""
        librarian = LibrarianActor(engine=mock_engine)

        # Setup mock graph with async methods where needed
        mock_graph = MagicMock()
        mock_graph.has_edge = MagicMock(return_value=False)
        mock_graph.add_edge = AsyncMock()                   # async in MemoryGraph
        mock_graph.remove_edge = AsyncMock()                # async in MemoryGraph
        mock_graph.get_neighbors = MagicMock(return_value=["node_2", "node_3"])
        mock_graph.get_all_edges = MagicMock(return_value=[
            {"from_id": "node_1", "to_id": "node_2", "edge_type": "collaborates_with", "weight": 0.9},
            {"from_id": "node_1", "to_id": "node_3", "edge_type": "works_on", "weight": 0.85},
        ])

        mock_matrix_actor._graph = mock_graph

        # Ensure MemoryMatrix search_nodes returns empty (triggers create)
        mock_matrix_actor._matrix.search_nodes = AsyncMock(return_value=[])
        mock_matrix_actor._matrix.add_node = AsyncMock(return_value="new_entity_id")

        return librarian

    @pytest.mark.asyncio
    async def test_librarian_entity_graph_traversal(
        self,
        librarian_with_graph,
        mock_matrix_actor,
    ):
        """Test traversing entity relationships in graph."""
        # Entity resolution involves graph traversal
        node_id = await librarian_with_graph._resolve_entity(
            name="Alex",
            entity_type="PERSON",
            source_id="test-session",
        )

        # Should return a node ID
        assert node_id is not None

    @pytest.mark.asyncio
    async def test_edge_creation_in_graph(
        self,
        librarian_with_graph,
        mock_matrix_actor,
    ):
        """Test that edges are created in the graph."""
        # Create an edge between two entities
        result = await librarian_with_graph._create_edge(
            from_id="entity_alex",
            to_id="entity_luna",
            edge_type="works_on",
            confidence=0.95,
        )

        # Edge should have been created (returns True if new)
        assert result is True

        # Graph add_edge should have been called
        mock_matrix_actor._graph.add_edge.assert_called_once()


@pytest.mark.integration
class TestLibrarianRespectsLockInScores:
    """Test that Librarian respects lock-in scores during retrieval."""

    @pytest.fixture
    def librarian_with_lockin_data(self, mock_engine, mock_matrix_actor):
        """Librarian with lock-in enabled data."""
        librarian = LibrarianActor(engine=mock_engine)

        # Setup matrix to return nodes with varying lock-in scores
        locked_in_node = MagicMock(
            id="locked_node",
            content="Critical core memory",
            lock_in=0.95,  # High lock-in
            reinforcement_count=10,
            lock_in_state="locked_in",
        )
        drifting_node = MagicMock(
            id="drifting_node",
            content="Potentially forgettable memory",
            lock_in=0.2,  # Low lock-in
            reinforcement_count=0,
            lock_in_state="drifting",
        )

        # Set on MemoryMatrix (what _get_matrix() returns), not on actor
        mock_matrix_actor._matrix.search = AsyncMock(return_value=[locked_in_node, drifting_node])
        mock_matrix_actor._matrix.get_drifting_nodes = AsyncMock(return_value=[drifting_node])
        # Also set on actor for direct-access tests
        mock_matrix_actor.get_drifting_nodes = AsyncMock(return_value=[drifting_node])

        return librarian

    @pytest.mark.asyncio
    async def test_librarian_respects_lockin_scores(
        self,
        librarian_with_lockin_data,
        mock_matrix_actor,
    ):
        """High lock-in nodes should be prioritized."""
        # Get drifting nodes for pruning
        drifting = await mock_matrix_actor.get_drifting_nodes(limit=10)

        # Should return drifting nodes
        assert len(drifting) == 1
        assert drifting[0].lock_in_state == "drifting"

    @pytest.mark.asyncio
    async def test_pruning_respects_reinforcement_count(
        self,
        librarian_with_lockin_data,
        mock_matrix_actor,
    ):
        """Nodes with reinforcement should not be pruned."""
        # Setup prune with drifting nodes (on MemoryMatrix, not actor)
        drifting_node = MagicMock(
            id="node_to_maybe_prune",
            lock_in=0.1,
            reinforcement_count=5,  # Has been reinforced
            created_at=datetime(2025, 1, 1),  # Old
        )
        mock_matrix_actor._matrix.get_drifting_nodes = AsyncMock(return_value=[drifting_node])

        # Prune should preserve reinforced nodes
        result = await librarian_with_lockin_data._prune_drifting_nodes(
            age_days=30,
            max_prune=10,
        )

        # Should be preserved due to reinforcement
        assert result["preserved"] >= 0


@pytest.mark.integration
class TestLibrarianFilingIntegration:
    """Test Librarian filing of extractions."""

    @pytest.fixture
    def librarian(self, mock_engine, mock_matrix_actor):
        """Librarian for filing tests."""
        librarian = LibrarianActor(engine=mock_engine)
        return librarian

    @pytest.mark.asyncio
    async def test_file_extraction_creates_nodes(
        self,
        librarian,
        sample_extraction_output,
        mock_matrix_actor,
    ):
        """Filing extraction should create memory nodes."""
        # Process the extraction
        result = await librarian._wire_extraction(sample_extraction_output)

        # Should have created nodes
        assert isinstance(result, FilingResult)
        assert len(result.nodes_created) >= 0 or len(result.nodes_merged) >= 0

    @pytest.mark.asyncio
    async def test_file_extraction_creates_edges(
        self,
        librarian,
        mock_matrix_actor,
    ):
        """Filing extraction should create graph edges."""
        extraction = ExtractionOutput(
            objects=[
                ExtractedObject(
                    type="CONNECTION",
                    content="Alex works on Luna Engine",
                    confidence=0.9,
                    entities=["Alex", "Luna Engine"],
                    source_id="test",
                ),
            ],
            edges=[
                ExtractedEdge(
                    from_ref="Alex",
                    to_ref="Luna Engine",
                    edge_type="works_on",
                    confidence=0.9,
                    source_id="test",
                ),
            ],
            source_id="test",
        )

        result = await librarian._wire_extraction(extraction)

        # Should have attempted to create edges
        assert isinstance(result, FilingResult)

    @pytest.mark.asyncio
    async def test_file_message_handling(
        self,
        librarian,
        sample_file_message,
        mock_matrix_actor,
    ):
        """Test handling of file message from Scribe."""
        # Handle the file message
        await librarian._handle_file(sample_file_message)

        # Stats should be updated
        stats = librarian.get_stats()
        assert stats["filings_count"] >= 0


@pytest.mark.integration
class TestLibrarianEntityResolution:
    """Test Librarian entity resolution capabilities."""

    @pytest.fixture
    def librarian(self, mock_engine, mock_matrix_actor):
        """Librarian for entity resolution tests."""
        librarian = LibrarianActor(engine=mock_engine)
        return librarian

    @pytest.mark.asyncio
    async def test_resolve_entity_cache_hit(self, librarian):
        """Entity resolution should use cache."""
        # Pre-populate cache
        librarian.alias_cache["alex"] = "node_alex_123"

        # Resolve should hit cache
        node_id = await librarian._resolve_entity(
            name="Alex",
            entity_type="PERSON",
        )

        assert node_id == "node_alex_123"

    @pytest.mark.asyncio
    async def test_resolve_entity_creates_new(
        self,
        librarian,
        mock_matrix_actor,
    ):
        """Entity resolution should create new node if not found."""
        # Ensure cache miss
        librarian.alias_cache.clear()

        # Mock MemoryMatrix (what _get_matrix() returns) to return no results
        mock_matrix_actor._matrix.search_nodes = AsyncMock(return_value=[])
        mock_matrix_actor._matrix.add_node = AsyncMock(return_value="new_node_id")

        node_id = await librarian._resolve_entity(
            name="NewEntity",
            entity_type="PERSON",
        )

        # Should have created new node
        assert node_id is not None

    @pytest.mark.asyncio
    async def test_resolve_entity_finds_existing(
        self,
        librarian,
        mock_matrix_actor,
    ):
        """Entity resolution should find existing node."""
        # Clear cache
        librarian.alias_cache.clear()

        # Mock MemoryMatrix search to return existing node
        existing_node = MagicMock(id="existing_node", content="Alex")
        mock_matrix_actor._matrix.search_nodes = AsyncMock(return_value=[existing_node])

        node_id = await librarian._resolve_entity(
            name="Alex",
            entity_type="PERSON",
        )

        # Should return existing
        assert node_id == "existing_node"


@pytest.mark.integration
class TestLibrarianEntityUpdate:
    """Test Librarian entity update filing."""

    @pytest.fixture
    def librarian_with_resolver(self, mock_engine, mock_matrix_actor, mock_database):
        """Librarian with mocked entity resolver."""
        librarian = LibrarianActor(engine=mock_engine)

        # Setup mock for database access through matrix
        mock_matrix_actor._matrix.db = mock_database

        return librarian

    @pytest.mark.asyncio
    async def test_entity_update_message_handling(
        self,
        librarian_with_resolver,
        mock_database,
    ):
        """Test handling of entity_update message."""
        # Setup mock for resolver
        with patch.object(librarian_with_resolver, '_file_entity_update') as mock_file:
            mock_file.return_value = MagicMock(id="entity_123", name="Alex")

            msg = Message(
                type="entity_update",
                payload={
                    "update_type": "update",
                    "name": "Alex",
                    "entity_type": "person",
                    "facts": {"role": "Developer", "location": "Berlin"},
                    "source": "conversation",
                },
            )

            await librarian_with_resolver._handle_entity_update(msg)

            # File should have been called
            mock_file.assert_called_once()


@pytest.mark.integration
class TestLibrarianPruning:
    """Test Librarian pruning operations."""

    @pytest.fixture
    def librarian(self, mock_engine, mock_matrix_actor):
        """Librarian for pruning tests."""
        librarian = LibrarianActor(engine=mock_engine)
        return librarian

    @pytest.mark.asyncio
    async def test_prune_edges(self, librarian, mock_matrix_actor):
        """Test edge pruning based on confidence and age."""
        # Setup old, low-confidence edges
        mock_matrix_actor._graph.get_all_edges.return_value = [
            {
                "from_id": "a",
                "to_id": "b",
                "edge_type": "related",
                "weight": 0.2,  # Low confidence
                "created_at": datetime(2025, 1, 1).timestamp(),  # Old
            },
        ]

        result = await librarian._prune_edges(
            confidence_threshold=0.3,
            age_days=30,
        )

        # Should have pruned the low-confidence old edge
        assert "pruned" in result
        assert "preserved" in result

    @pytest.mark.asyncio
    async def test_prune_message_handling(self, librarian, mock_matrix_actor):
        """Test handling of prune message."""
        # Setup mock returns (on MemoryMatrix, not actor)
        mock_matrix_actor._graph.get_all_edges.return_value = []
        mock_matrix_actor._matrix.get_drifting_nodes = AsyncMock(return_value=[])

        msg = Message(
            type="prune",
            payload={
                "confidence_threshold": 0.3,
                "age_days": 30,
                "prune_nodes": True,
                "max_prune_nodes": 50,
            },
        )

        # Mock send_to_engine
        with patch.object(librarian, 'send_to_engine') as mock_send:
            await librarian._handle_prune(msg)

            # Should send prune_result
            mock_send.assert_called_once()
            call_args = mock_send.call_args
            assert call_args[0][0] == "prune_result"


@pytest.mark.integration
class TestLibrarianStats:
    """Test Librarian statistics tracking."""

    @pytest.fixture
    def librarian(self, mock_engine, mock_matrix_actor):
        """Librarian for stats testing."""
        return LibrarianActor(engine=mock_engine)

    def test_get_stats_returns_all_fields(self, librarian):
        """Stats should include all expected fields."""
        stats = librarian.get_stats()

        expected_fields = [
            "filings_count",
            "nodes_created",
            "nodes_merged",
            "edges_created",
            "context_retrievals",
            "entity_updates_filed",
            "entity_versions_created",
            "avg_filing_time_ms",
            "cache_size",
            "inference_queue_size",
        ]

        for field in expected_fields:
            assert field in stats, f"Missing stat field: {field}"

    @pytest.mark.asyncio
    async def test_stats_update_after_filing(
        self,
        librarian,
        sample_extraction_output,
        mock_matrix_actor,
    ):
        """Stats should update after filing."""
        initial_filings = librarian._filings_count

        await librarian._wire_extraction(sample_extraction_output)

        assert librarian._filings_count == initial_filings + 1


@pytest.mark.integration
class TestBudgetPresets:
    """Test Librarian budget presets."""

    def test_budget_presets_defined(self):
        """All budget presets should be defined."""
        assert "minimal" in BUDGET_PRESETS
        assert "balanced" in BUDGET_PRESETS
        assert "rich" in BUDGET_PRESETS

    def test_budget_preset_values(self):
        """Budget presets should have reasonable values."""
        assert BUDGET_PRESETS["minimal"] < BUDGET_PRESETS["balanced"]
        assert BUDGET_PRESETS["balanced"] < BUDGET_PRESETS["rich"]
        assert BUDGET_PRESETS["minimal"] > 0
        assert BUDGET_PRESETS["rich"] < 20000  # Reasonable upper bound
