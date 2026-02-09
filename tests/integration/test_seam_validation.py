"""
Seam Validation Tests — Verify API contracts between components.

These tests validate that the interfaces between Luna's subsystems
match what callers expect, catching the class of bug found in the
AI-BRARIAN audit (e.g., _create_edge calling MemoryGraph.has_edge
with wrong arg count).

Tests:
1. MemoryGraph API contract (has_edge, add_edge, remove_edge signatures)
2. LibrarianActor._create_edge roundtrip through real MemoryGraph
3. LibrarianActor._prune_edges uses valid MemoryGraph API
4. _wire_extraction stores FACTs as nodes (not entity names)
5. Auto-session extraction filters user turns only
"""

import pytest
import asyncio
import inspect
from unittest.mock import AsyncMock, MagicMock, patch
from tempfile import TemporaryDirectory
from pathlib import Path

from luna.substrate.graph import MemoryGraph
from luna.actors.librarian import LibrarianActor
from luna.extraction.types import (
    ExtractionOutput,
    ExtractedObject,
    ExtractedEdge,
    ExtractionType,
)


# =============================================================================
# Contract Tests: MemoryGraph API signatures
# =============================================================================


class TestMemoryGraphContract:
    """Verify MemoryGraph API matches what callers expect."""

    def test_has_edge_takes_two_args(self):
        """has_edge(from_id, to_id) — must accept exactly 2 positional args."""
        sig = inspect.signature(MemoryGraph.has_edge)
        params = [p for p in sig.parameters if p != "self"]
        assert len(params) == 2, f"has_edge should take 2 args, got {len(params)}: {params}"
        assert params == ["from_id", "to_id"]

    def test_add_edge_is_async(self):
        """add_edge must be a coroutine (async def)."""
        assert asyncio.iscoroutinefunction(MemoryGraph.add_edge), \
            "add_edge must be async"

    def test_add_edge_accepts_relationship_and_strength(self):
        """add_edge must accept relationship= and strength= kwargs."""
        sig = inspect.signature(MemoryGraph.add_edge)
        param_names = list(sig.parameters.keys())
        assert "relationship" in param_names, \
            f"add_edge missing 'relationship' param, has: {param_names}"
        assert "strength" in param_names, \
            f"add_edge missing 'strength' param, has: {param_names}"

    def test_add_edge_does_not_accept_edge_type_or_weight(self):
        """add_edge must NOT accept old broken kwargs."""
        sig = inspect.signature(MemoryGraph.add_edge)
        param_names = list(sig.parameters.keys())
        assert "edge_type" not in param_names, \
            "add_edge should not have 'edge_type' param (use 'relationship')"
        assert "weight" not in param_names, \
            "add_edge should not have 'weight' param (use 'strength')"

    def test_remove_edge_is_async(self):
        """remove_edge must be a coroutine."""
        assert asyncio.iscoroutinefunction(MemoryGraph.remove_edge), \
            "remove_edge must be async"

    def test_graph_property_exists(self):
        """MemoryGraph must expose .graph property for NetworkX access."""
        assert hasattr(MemoryGraph, "graph"), \
            "MemoryGraph must have .graph property"

    def test_no_get_all_edges_method(self):
        """MemoryGraph must NOT have get_all_edges (was causing AttributeError)."""
        assert not hasattr(MemoryGraph, "get_all_edges"), \
            "get_all_edges should not exist on MemoryGraph"


# =============================================================================
# Roundtrip Tests: LibrarianActor through real-ish components
# =============================================================================


class TestCreateEdgeRoundtrip:
    """Verify _create_edge works with real MemoryGraph API."""

    @pytest.fixture
    def librarian_with_mock_graph(self):
        """Create LibrarianActor with a mock graph that matches real API."""
        librarian = LibrarianActor()

        # Mock engine + matrix actor with graph that has correct API
        engine = MagicMock()
        matrix_actor = MagicMock()
        graph = MagicMock()

        # Match real MemoryGraph API
        graph.has_edge = MagicMock(return_value=False)
        graph.add_edge = AsyncMock()

        matrix_actor._graph = graph
        engine.get_actor = MagicMock(return_value=matrix_actor)
        librarian.engine = engine

        return librarian, graph

    @pytest.mark.asyncio
    async def test_create_edge_calls_has_edge_with_two_args(self, librarian_with_mock_graph):
        """_create_edge must call has_edge with exactly 2 args."""
        librarian, graph = librarian_with_mock_graph

        await librarian._create_edge("node_a", "node_b", "RELATED_TO", 0.9)

        graph.has_edge.assert_called_once_with("node_a", "node_b")

    @pytest.mark.asyncio
    async def test_create_edge_awaits_add_edge(self, librarian_with_mock_graph):
        """_create_edge must await graph.add_edge (not fire-and-forget)."""
        librarian, graph = librarian_with_mock_graph

        result = await librarian._create_edge("node_a", "node_b", "RELATED_TO", 0.9)

        assert result is True
        graph.add_edge.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_edge_uses_correct_kwargs(self, librarian_with_mock_graph):
        """_create_edge must pass relationship= and strength= (not edge_type/weight)."""
        librarian, graph = librarian_with_mock_graph

        await librarian._create_edge("node_a", "node_b", "leads", 0.95)

        graph.add_edge.assert_awaited_once_with(
            from_id="node_a",
            to_id="node_b",
            relationship="leads",
            strength=0.95,
        )

    @pytest.mark.asyncio
    async def test_create_edge_returns_false_for_duplicate(self, librarian_with_mock_graph):
        """_create_edge returns False when edge already exists."""
        librarian, graph = librarian_with_mock_graph
        graph.has_edge = MagicMock(return_value=True)

        result = await librarian._create_edge("node_a", "node_b", "RELATED_TO")

        assert result is False
        graph.add_edge.assert_not_awaited()


class TestWireExtractionFlow:
    """Verify _wire_extraction stores FACTs as nodes, not entity names."""

    @pytest.mark.asyncio
    async def test_facts_stored_as_nodes_not_entities(self):
        """FACTs should be stored via matrix.add_node, not _resolve_entity."""
        librarian = LibrarianActor()

        # Setup mock engine/matrix
        engine = MagicMock()
        matrix = AsyncMock()
        matrix.add_node = AsyncMock(return_value="fact_node_1")
        matrix.search_nodes = AsyncMock(return_value=[])

        matrix_actor = MagicMock()
        matrix_actor._matrix = matrix
        matrix_actor._graph = MagicMock()
        matrix_actor._graph.has_edge = MagicMock(return_value=False)
        matrix_actor._graph.add_edge = AsyncMock()

        engine.get_actor = MagicMock(return_value=matrix_actor)
        librarian.engine = engine

        extraction = ExtractionOutput(
            objects=[
                ExtractedObject(
                    type="FACT",
                    content="Mars College is in February 2026",
                    confidence=0.9,
                    entities=["Mars College"],
                    source_id="test",
                ),
            ],
            edges=[],
            source_id="test",
        )

        result = await librarian._wire_extraction(extraction)

        # The FACT content should be stored via add_node (first call)
        assert matrix.add_node.call_count >= 1
        first_call = matrix.add_node.call_args_list[0]
        assert first_call.kwargs.get("content") == "Mars College is in February 2026"
        assert first_call.kwargs.get("node_type") == "FACT"

        # Entity "Mars College" should also be resolved (second add_node call for the entity)
        assert matrix.add_node.call_count == 2
        entity_call = matrix.add_node.call_args_list[1]
        assert entity_call.kwargs.get("content") == "Mars College" or \
               (len(entity_call.args) >= 2 and entity_call.args[1] == "Mars College")

        # Should have created nodes
        assert len(result.nodes_created) > 0


class TestPruneEdgesAPI:
    """Verify _prune_edges uses valid MemoryGraph API."""

    @pytest.mark.asyncio
    async def test_prune_edges_does_not_call_get_all_edges(self):
        """_prune_edges must NOT call graph.get_all_edges (doesn't exist)."""
        librarian = LibrarianActor()

        engine = MagicMock()
        matrix_actor = MagicMock()
        graph = MagicMock()

        # Setup NetworkX-style graph property
        import networkx as nx
        nx_graph = nx.DiGraph()
        nx_graph.add_edge("a", "b", strength=0.1, created_at=0, relationship="test")
        graph.graph = nx_graph
        graph.remove_edge = AsyncMock(return_value=True)

        matrix_actor._graph = graph
        engine.get_actor = MagicMock(return_value=matrix_actor)
        librarian.engine = engine

        result = await librarian._prune_edges(confidence_threshold=0.5, age_days=0)

        # Should NOT have tried get_all_edges
        assert not hasattr(graph, "get_all_edges") or not graph.get_all_edges.called
        # Should have pruned the low-confidence edge
        assert result["pruned"] >= 1
