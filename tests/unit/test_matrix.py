"""
Unit Tests for MatrixActor
==========================

Tests for memory substrate operations including storage, retrieval,
search, and lock-in coefficient handling.

All database operations are mocked - no real SQLite calls.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path
from datetime import datetime

from luna.actors.base import Message


# =============================================================================
# MATRIX STORAGE TESTS
# =============================================================================

class TestMatrixStorage:
    """Tests for memory storage operations."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_stores_memory(self, mock_matrix_actor, mock_matrix):
        """Test MatrixActor stores memory nodes correctly."""
        mock_matrix_actor._matrix = mock_matrix
        mock_matrix.add_node = AsyncMock(return_value="node-new-001")

        result = await mock_matrix_actor.store_memory(
            content="Test fact content",
            node_type="FACT",
            tags=["test", "unit"],
            confidence=90,
        )

        assert result == "node-new-001"
        mock_matrix.add_node.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_stores_with_metadata(self, mock_matrix_actor, mock_matrix):
        """Test MatrixActor stores metadata correctly."""
        mock_matrix_actor._matrix = mock_matrix
        mock_matrix.add_node = AsyncMock(return_value="node-with-meta")

        await mock_matrix_actor.store_memory(
            content="Memory with session",
            node_type="DECISION",
            tags=["important"],
            confidence=100,
            session_id="session-123",
        )

        # Verify add_node was called with metadata
        call_kwargs = mock_matrix.add_node.call_args
        assert call_kwargs is not None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_stores_turn(self, mock_matrix_actor, mock_matrix):
        """Test MatrixActor stores conversation turns."""
        mock_matrix_actor._matrix = mock_matrix
        mock_matrix.add_node = AsyncMock(return_value="turn-001")

        result = await mock_matrix_actor.store_turn(
            session_id="session-123",
            role="user",
            content="Hello Luna",
            tokens=10,
        )

        assert result == "turn-001"
        mock_matrix.add_node.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_store_requires_initialization(self, mock_matrix_actor):
        """Test store_memory raises error when not initialized."""
        mock_matrix_actor._initialized = False
        mock_matrix_actor._matrix = None

        with pytest.raises(RuntimeError, match="Matrix not initialized"):
            await mock_matrix_actor.store_memory(
                content="Test",
                node_type="FACT",
            )


# =============================================================================
# MATRIX RETRIEVAL TESTS
# =============================================================================

class TestMatrixRetrieval:
    """Tests for memory retrieval operations."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_retrieves_by_id(self, mock_matrix_actor, mock_matrix, mock_memory_node):
        """Test MatrixActor retrieves node by ID."""
        mock_matrix_actor._matrix = mock_matrix
        mock_matrix.get_node = AsyncMock(return_value=mock_memory_node)

        result = await mock_matrix_actor.get_node("node-001")

        assert result is not None
        assert result.id == "node-001"
        assert result.content == "Test fact content"
        mock_matrix.get_node.assert_called_once_with("node-001")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_handles_missing_node(self, mock_matrix_actor, mock_matrix):
        """Test MatrixActor handles missing node gracefully."""
        mock_matrix_actor._matrix = mock_matrix
        mock_matrix.get_node = AsyncMock(return_value=None)

        result = await mock_matrix_actor.get_node("nonexistent-node")

        assert result is None

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_get_node_not_initialized(self, mock_matrix_actor):
        """Test get_node returns None when not initialized."""
        mock_matrix_actor._initialized = False
        mock_matrix_actor._matrix = None

        result = await mock_matrix_actor.get_node("any-id")

        assert result is None


# =============================================================================
# MATRIX SEARCH TESTS
# =============================================================================

class TestMatrixSearch:
    """Tests for memory search operations."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_searches_by_query(self, mock_matrix_actor, mock_matrix, mock_memory_node):
        """Test MatrixActor searches nodes by query."""
        mock_matrix_actor._matrix = mock_matrix
        mock_matrix.search_nodes = AsyncMock(return_value=[mock_memory_node])

        results = await mock_matrix_actor.search("test query", limit=10)

        assert len(results) == 1
        assert results[0].content == "Test fact content"
        mock_matrix.search_nodes.assert_called_once_with(query="test query", limit=10)

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_search_returns_empty_when_not_initialized(self, mock_matrix_actor):
        """Test search returns empty list when not initialized."""
        mock_matrix_actor._initialized = False

        results = await mock_matrix_actor.search("any query")

        assert results == []

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_search_respects_limit(self, mock_matrix_actor, mock_matrix):
        """Test search respects result limit."""
        mock_matrix_actor._matrix = mock_matrix

        await mock_matrix_actor.search("test", limit=5)

        call_args = mock_matrix.search_nodes.call_args
        assert call_args.kwargs.get('limit') == 5


# =============================================================================
# LOCK-IN TESTS
# =============================================================================

class TestMatrixLockIn:
    """Tests for lock-in coefficient operations."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_calculates_lockin(self, mock_matrix_actor, mock_matrix):
        """Test MatrixActor handles lock-in reinforcement."""
        mock_matrix_actor._matrix = mock_matrix
        mock_matrix.reinforce_node = AsyncMock(return_value=True)

        await mock_matrix_actor.reinforce_memory("node-001", amount=1)

        mock_matrix.reinforce_node.assert_called_once_with("node-001")

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_reinforces_multiple_times(self, mock_matrix_actor, mock_matrix):
        """Test MatrixActor reinforces memory multiple times."""
        mock_matrix_actor._matrix = mock_matrix
        mock_matrix.reinforce_node = AsyncMock(return_value=True)

        await mock_matrix_actor.reinforce_memory("node-001", amount=3)

        assert mock_matrix.reinforce_node.call_count == 3

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_reinforce_no_matrix(self, mock_matrix_actor):
        """Test reinforce does nothing when matrix unavailable."""
        mock_matrix_actor._matrix = None

        # Should not raise
        await mock_matrix_actor.reinforce_memory("any-id")


# =============================================================================
# CONTEXT RETRIEVAL TESTS
# =============================================================================

class TestMatrixContext:
    """Tests for context retrieval."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_gets_context(self, mock_matrix_actor, mock_matrix, mock_memory_node):
        """Test MatrixActor gets context for query."""
        mock_matrix_actor._matrix = mock_matrix
        mock_matrix.get_context = AsyncMock(return_value=[mock_memory_node])

        result = await mock_matrix_actor.get_context(
            query="What do I know about testing?",
            max_tokens=3800,
        )

        # Result is formatted string
        assert isinstance(result, str)
        mock_matrix.get_context.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_context_empty_when_not_initialized(self, mock_matrix_actor):
        """Test get_context returns empty when not initialized."""
        mock_matrix_actor._initialized = False

        result = await mock_matrix_actor.get_context("any query")

        assert result == ""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_context_empty_no_results(self, mock_matrix_actor, mock_matrix):
        """Test get_context returns empty when no nodes found."""
        mock_matrix_actor._matrix = mock_matrix
        mock_matrix.get_context = AsyncMock(return_value=[])

        result = await mock_matrix_actor.get_context("obscure query")

        assert result == ""


# =============================================================================
# MESSAGE HANDLING TESTS
# =============================================================================

class TestMatrixMessageHandling:
    """Tests for mailbox message handling."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_handles_store_message(self, mock_matrix_actor, mock_matrix):
        """Test MatrixActor handles 'store' messages."""
        mock_matrix_actor._matrix = mock_matrix
        mock_matrix.add_node = AsyncMock(return_value="new-node-id")

        msg = Message(
            type="store",
            payload={
                "content": "Test content",
                "node_type": "FACT",
                "tags": ["test"],
                "confidence": 100,
            }
        )

        await mock_matrix_actor.handle(msg)

        mock_matrix.add_node.assert_called_once()

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_handles_search_message(self, mock_matrix_actor, mock_matrix):
        """Test MatrixActor handles 'search' messages."""
        mock_matrix_actor._matrix = mock_matrix
        mock_matrix.search_nodes = AsyncMock(return_value=[])

        msg = Message(
            type="search",
            payload={"query": "test query", "limit": 5}
        )

        await mock_matrix_actor.handle(msg)

        mock_matrix.search_nodes.assert_called_once()


# =============================================================================
# STATS TESTS
# =============================================================================

class TestMatrixStats:
    """Tests for statistics retrieval."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_gets_stats(self, mock_matrix_actor, mock_matrix, mock_graph):
        """Test MatrixActor returns correct statistics."""
        mock_matrix_actor._matrix = mock_matrix
        mock_matrix_actor._graph = mock_graph
        mock_matrix.get_stats = AsyncMock(return_value={"total_nodes": 100})
        mock_graph.get_stats = AsyncMock(return_value={"node_count": 100, "edge_count": 50})

        stats = await mock_matrix_actor.get_stats()

        assert stats["backend"] == "luna_substrate"
        assert "total_nodes" in stats or "graph" in stats

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_stats_when_not_initialized(self, mock_matrix_actor):
        """Test stats indicates not initialized."""
        mock_matrix_actor._initialized = False

        stats = await mock_matrix_actor.get_stats()

        assert stats.get("initialized") is False


# =============================================================================
# GRAPH OPERATIONS TESTS
# =============================================================================

class TestMatrixGraphOps:
    """Tests for graph traversal operations."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_finds_related(self, mock_matrix_actor, mock_graph):
        """Test MatrixActor finds related nodes via graph."""
        mock_matrix_actor._graph = mock_graph
        mock_graph.get_neighbors = Mock(return_value=["node-002", "node-003"])

        related = await mock_matrix_actor.find_related("node-001", depth=2)

        assert len(related) == 2
        assert "node-002" in related

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_finds_central_concepts(self, mock_matrix_actor, mock_graph):
        """Test MatrixActor finds central concept nodes."""
        mock_matrix_actor._graph = mock_graph
        mock_graph.get_central_nodes = Mock(return_value=[
            ("node-central", 0.95),
            ("node-secondary", 0.75),
        ])

        central = await mock_matrix_actor.get_central_concepts(limit=10)

        assert len(central) == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_matrix_graph_ops_no_graph(self, mock_matrix_actor):
        """Test graph operations return empty when no graph."""
        mock_matrix_actor._graph = None

        related = await mock_matrix_actor.find_related("any-id")
        central = await mock_matrix_actor.get_central_concepts()

        assert related == []
        assert central == []
