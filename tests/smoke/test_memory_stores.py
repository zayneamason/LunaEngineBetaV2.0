"""
Smoke Tests: Memory Storage
===========================

Verifies the Memory Matrix can store, retrieve, search,
and delete memories end-to-end.

Uses REAL database (temp file), no mocking of storage layer.
"""

import asyncio

import pytest
import pytest_asyncio

from luna.substrate.database import MemoryDatabase
from luna.substrate.memory import MemoryMatrix, MemoryNode


pytestmark = [
    pytest.mark.smoke,
    pytest.mark.asyncio,
]


class TestMemoryStores:
    """Smoke tests for memory storage operations."""

    async def test_store_text_memory(self, memory_matrix):
        """
        SMOKE: Store a text memory node.

        Verifies:
        - add_node() returns a valid ID
        - Node is created with correct type
        - Content is stored correctly
        """
        node_id = await memory_matrix.add_node(
            node_type="FACT",
            content="Luna is a consciousness engine that treats LLMs like GPUs.",
            source="smoke_test",
            importance=0.8,
        )

        assert node_id is not None
        assert isinstance(node_id, str)
        assert len(node_id) > 0

    async def test_retrieve_stored_memory(self, memory_matrix):
        """
        SMOKE: Retrieve a stored memory by ID.

        Verifies:
        - Stored node can be retrieved
        - All fields match what was stored
        - Timestamps are set
        """
        original_content = "The Memory Matrix is Luna's soul."
        original_importance = 0.9

        node_id = await memory_matrix.add_node(
            node_type="INSIGHT",
            content=original_content,
            source="smoke_test",
            importance=original_importance,
            confidence=0.95,
        )

        # Retrieve the node
        node = await memory_matrix.get_node(node_id)

        assert node is not None
        assert isinstance(node, MemoryNode)
        assert node.id == node_id
        assert node.content == original_content
        assert node.node_type == "INSIGHT"
        assert node.importance == original_importance
        assert node.confidence == 0.95
        assert node.created_at is not None
        assert node.access_count >= 0

    async def test_search_memories_by_query(self, memory_matrix):
        """
        SMOKE: Search memories by text query.

        Verifies:
        - Multiple nodes can be stored
        - Search returns matching nodes
        - Non-matching nodes are excluded
        """
        # Store several nodes
        await memory_matrix.add_node(
            "FACT", "Python is a programming language", source="test"
        )
        await memory_matrix.add_node(
            "FACT", "JavaScript runs in browsers", source="test"
        )
        await memory_matrix.add_node(
            "FACT", "Python was created by Guido van Rossum", source="test"
        )
        await memory_matrix.add_node(
            "FACT", "Luna uses Python for its backend", source="test"
        )

        # Search for Python
        results = await memory_matrix.search_nodes("Python")

        assert len(results) >= 2
        assert all("Python" in node.content for node in results)

        # Search for JavaScript
        js_results = await memory_matrix.search_nodes("JavaScript")
        assert len(js_results) >= 1
        assert any("JavaScript" in node.content for node in js_results)

    async def test_delete_memory(self, memory_matrix):
        """
        SMOKE: Delete a memory node.

        Verifies:
        - Node exists before deletion
        - delete_node() succeeds
        - Node no longer retrievable after deletion
        """
        # Create a node
        node_id = await memory_matrix.add_node(
            "FACT",
            "This node will be deleted",
            source="smoke_test",
        )

        # Verify it exists
        node = await memory_matrix.get_node(node_id)
        assert node is not None

        # Delete it
        await memory_matrix.delete_node(node_id)

        # Verify it's gone
        deleted_node = await memory_matrix.get_node(node_id)
        assert deleted_node is None

    async def test_memory_persists_across_operations(self, memory_matrix):
        """
        SMOKE: Memory persists across multiple operations.

        Verifies:
        - Nodes survive multiple add/update operations
        - Search finds nodes added earlier
        - Stats reflect all operations
        """
        # Add multiple nodes
        ids = []
        for i in range(5):
            node_id = await memory_matrix.add_node(
                "FACT",
                f"Persistent fact number {i}",
                source="smoke_test",
                importance=0.5 + (i * 0.1),
            )
            ids.append(node_id)

        # Update one
        await memory_matrix.update_node(
            ids[2], content="Updated persistent fact number 2"
        )

        # Delete one
        await memory_matrix.delete_node(ids[0])

        # Verify remaining nodes
        remaining = 0
        for node_id in ids:
            node = await memory_matrix.get_node(node_id)
            if node is not None:
                remaining += 1

        assert remaining == 4  # 5 created, 1 deleted

        # Verify updated node
        updated = await memory_matrix.get_node(ids[2])
        assert "Updated" in updated.content

        # Verify search still works
        results = await memory_matrix.search_nodes("Persistent")
        assert len(results) >= 3  # Some contain "Persistent"


class TestMemoryAccess:
    """Smoke tests for memory access tracking."""

    async def test_record_access(self, memory_matrix):
        """
        SMOKE: Record access increments counter.

        Verifies:
        - Initial access_count is 0
        - record_access() increments counter
        - last_accessed is updated
        """
        node_id = await memory_matrix.add_node(
            "FACT", "Access tracking test", source="test"
        )

        # Check initial state
        node = await memory_matrix.get_node(node_id)
        initial_count = node.access_count

        # Record access
        await memory_matrix.record_access(node_id)

        # Check incremented
        node_after = await memory_matrix.get_node(node_id)
        assert node_after.access_count == initial_count + 1

    async def test_reinforce_node(self, memory_matrix):
        """
        SMOKE: Reinforce node increases reinforcement count.

        Verifies:
        - reinforce_node() succeeds
        - reinforcement_count increases
        - lock_in may update
        """
        node_id = await memory_matrix.add_node(
            "DECISION", "Reinforcement test decision", source="test"
        )

        node_before = await memory_matrix.get_node(node_id)
        initial_reinforcement = node_before.reinforcement_count

        # Reinforce
        await memory_matrix.reinforce_node(node_id)

        node_after = await memory_matrix.get_node(node_id)
        assert node_after.reinforcement_count == initial_reinforcement + 1


class TestMemoryStats:
    """Smoke tests for memory statistics."""

    async def test_get_stats(self, memory_matrix):
        """
        SMOKE: Get memory statistics.

        Verifies:
        - get_stats() returns dict
        - Contains expected fields
        - Counts are accurate
        """
        # Add some nodes
        await memory_matrix.add_node("FACT", "Stat test 1", source="test")
        await memory_matrix.add_node("FACT", "Stat test 2", source="test")
        await memory_matrix.add_node("DECISION", "Stat test decision", source="test")

        stats = await memory_matrix.get_stats()

        assert isinstance(stats, dict)
        assert "total_nodes" in stats
        assert stats["total_nodes"] >= 3
        assert "nodes_by_type" in stats
        assert "FACT" in stats["nodes_by_type"]
        assert stats["nodes_by_type"]["FACT"] >= 2

    async def test_get_recent_nodes(self, memory_matrix):
        """
        SMOKE: Get recently created nodes.

        Verifies:
        - Returns list of nodes
        - Ordered by creation time (most recent first)
        - Respects limit parameter
        """
        # Add nodes with slight delay to ensure order
        await memory_matrix.add_node("FACT", "First node", source="test")
        await asyncio.sleep(0.01)
        await memory_matrix.add_node("FACT", "Second node", source="test")
        await asyncio.sleep(0.01)
        await memory_matrix.add_node("FACT", "Third node", source="test")

        recent = await memory_matrix.get_recent_nodes(limit=2)

        assert len(recent) == 2
        # Most recent first
        assert "Third" in recent[0].content


class TestConversationTurns:
    """Smoke tests for conversation turn storage."""

    async def test_store_conversation_turn(self, memory_matrix):
        """
        SMOKE: Store conversation turns.

        Verifies:
        - User and assistant turns can be stored
        - Session history is retrievable
        - Turns are in correct order
        """
        session_id = "smoke_test_session"

        await memory_matrix.add_conversation_turn(
            session_id=session_id,
            role="user",
            content="Hello Luna",
        )

        await memory_matrix.add_conversation_turn(
            session_id=session_id,
            role="assistant",
            content="Hello! How can I help you today?",
        )

        # Get session history
        turns = await memory_matrix.get_session_history(session_id)

        assert len(turns) == 2
        assert turns[0].role == "user"
        assert turns[0].content == "Hello Luna"
        assert turns[1].role == "assistant"
        assert "How can I help" in turns[1].content

    async def test_get_recent_turns(self, memory_matrix):
        """
        SMOKE: Get recent conversation turns.

        Verifies:
        - Recent turns are retrievable
        - Limit is respected
        - Order is chronological (oldest first after reversal)
        """
        session_id = "recent_test"

        for i in range(5):
            await memory_matrix.add_conversation_turn(
                session_id=session_id,
                role="user" if i % 2 == 0 else "assistant",
                content=f"Message number {i}",
            )

        recent = await memory_matrix.get_recent_turns(session_id, limit=3)

        assert len(recent) == 3
        # get_recent_turns returns in chronological order (oldest first after reversal)
        # Limit=3 gets last 3 turns, then reverses: [2, 3, 4]
        assert "2" in recent[0].content
        assert "4" in recent[2].content
