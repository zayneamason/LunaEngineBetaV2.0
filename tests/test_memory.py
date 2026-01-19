"""
Tests for Memory Substrate
==========================

Tests for database, memory matrix, and graph operations.
"""

import asyncio
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from luna.substrate.database import MemoryDatabase
from luna.substrate.memory import MemoryMatrix, MemoryNode


class TestDatabase:
    """Tests for MemoryDatabase class."""

    @pytest.mark.asyncio
    async def test_database_connects(self, temp_data_dir):
        """Test database connection."""
        db = MemoryDatabase(temp_data_dir / "test.db")

        await db.connect()
        assert db.is_connected

        await db.close()
        assert not db.is_connected

    @pytest.mark.asyncio
    async def test_database_creates_schema(self, temp_data_dir):
        """Test schema is created on connect."""
        db = MemoryDatabase(temp_data_dir / "test.db")

        await db.connect()

        # Check tables exist
        rows = await db.fetchall(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = [row[0] for row in rows]

        assert "memory_nodes" in tables
        assert "conversation_turns" in tables

        await db.close()


class TestMemoryMatrix:
    """Tests for MemoryMatrix class."""

    @pytest.fixture
    async def memory(self, temp_data_dir):
        """Create memory matrix for testing."""
        db = MemoryDatabase(temp_data_dir / "test.db")
        await db.connect()
        mm = MemoryMatrix(db)
        yield mm
        await db.close()

    @pytest.mark.asyncio
    async def test_add_and_get_node(self, memory):
        """Test adding and retrieving a memory node."""
        node_id = await memory.add_node(
            node_type="FACT",
            content="Luna is a consciousness engine",
            importance=0.9,
        )

        assert node_id is not None

        node = await memory.get_node(node_id)

        assert node is not None
        assert node.content == "Luna is a consciousness engine"
        assert node.node_type == "FACT"
        assert node.importance == 0.9

    @pytest.mark.asyncio
    async def test_search_nodes(self, memory):
        """Test searching for nodes by content."""
        await memory.add_node("FACT", "Python is a programming language")
        await memory.add_node("FACT", "JavaScript runs in browsers")
        await memory.add_node("FACT", "Python was created by Guido")

        results = await memory.search_nodes("Python")

        assert len(results) == 2
        assert all("Python" in r.content for r in results)

    @pytest.mark.asyncio
    async def test_search_by_type(self, memory):
        """Test filtering search by node type."""
        await memory.add_node("FACT", "The sky is blue")
        await memory.add_node("DECISION", "Use Python for backend")
        await memory.add_node("FACT", "Water is H2O")

        results = await memory.search_nodes("", node_type="FACT")

        assert len(results) == 2
        assert all(r.node_type == "FACT" for r in results)

    @pytest.mark.asyncio
    async def test_update_node(self, memory):
        """Test updating a node."""
        node_id = await memory.add_node("FACT", "Original content")

        await memory.update_node(node_id, content="Updated content", importance=0.95)

        node = await memory.get_node(node_id)

        assert node.content == "Updated content"
        assert node.importance == 0.95

    @pytest.mark.asyncio
    async def test_delete_node(self, memory):
        """Test deleting a node."""
        node_id = await memory.add_node("FACT", "To be deleted")

        await memory.delete_node(node_id)

        node = await memory.get_node(node_id)
        assert node is None

    @pytest.mark.asyncio
    async def test_get_context_respects_token_limit(self, memory):
        """Test context retrieval respects token budget."""
        # Add several nodes
        for i in range(10):
            await memory.add_node(
                "FACT",
                f"This is fact number {i} with some content to take up tokens.",
                importance=0.5 + (i * 0.05),
            )

        # Get context with small token limit - returns list of nodes
        nodes = await memory.get_context("fact", max_tokens=100)

        # Calculate total content length
        total_chars = sum(len(n.content) for n in nodes)

        # Should be less than max tokens * ~4 chars per token
        assert total_chars < 500

    @pytest.mark.asyncio
    async def test_store_conversation_turn(self, memory):
        """Test storing conversation turns."""
        await memory.add_conversation_turn(
            session_id="test123",
            role="user",
            content="Hello Luna",
        )

        await memory.add_conversation_turn(
            session_id="test123",
            role="assistant",
            content="Hello! How can I help?",
        )

        turns = await memory.get_session_history("test123")

        assert len(turns) == 2
        assert turns[0].role == "user"
        assert turns[1].role == "assistant"

    @pytest.mark.asyncio
    async def test_get_stats(self, memory):
        """Test getting memory statistics."""
        await memory.add_node("FACT", "Fact 1")
        await memory.add_node("FACT", "Fact 2")
        await memory.add_node("DECISION", "Decision 1")

        stats = await memory.get_stats()

        assert stats["total_nodes"] == 3
        assert "FACT" in stats["nodes_by_type"]
        assert stats["nodes_by_type"]["FACT"] == 2

    @pytest.mark.asyncio
    async def test_get_recent_nodes(self, memory):
        """Test getting recently created nodes."""
        await memory.add_node("FACT", "First fact")
        await memory.add_node("FACT", "Second fact")

        recent = await memory.get_recent_nodes(limit=5)

        assert len(recent) == 2
        # Most recent first
        assert recent[0].content == "Second fact"


class TestMemoryNode:
    """Tests for MemoryNode dataclass."""

    def test_memory_node_creation(self):
        """Test creating a memory node."""
        node = MemoryNode(
            id="test123",
            node_type="FACT",
            content="Test content",
            importance=0.8,
            confidence=0.9,
        )

        assert node.id == "test123"
        assert node.node_type == "FACT"
        assert node.content == "Test content"
        assert node.importance == 0.8
        assert node.confidence == 0.9
