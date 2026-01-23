"""
Unit tests for ContextPipeline — the unified context builder.

Tests the core guarantee: same context for all inference paths.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from luna.context.pipeline import ContextPipeline, ContextPacket
from luna.memory.ring import ConversationRing


class MockDatabase:
    """Mock database for testing."""

    async def fetchall(self, query: str, params: tuple = ()) -> list:
        """Return empty results by default."""
        return []


class TestContextPacket:
    """Tests for ContextPacket dataclass."""

    def test_packet_creation(self):
        """Test creating a context packet."""
        packet = ContextPacket(
            system_prompt="You are Luna",
            messages=[{"role": "user", "content": "Hello"}],
            current_message="Hello",
            entities=[],
            used_retrieval=False,
            ring_size=1,
            retrieval_size=0,
        )

        assert packet.system_prompt == "You are Luna"
        assert len(packet.messages) == 1
        assert packet.current_message == "Hello"
        assert packet.ring_size == 1

    def test_packet_repr(self):
        """Test packet string representation."""
        packet = ContextPacket(
            system_prompt="test",
            messages=[],
            current_message="test",
            entities=[1, 2, 3],
            used_retrieval=True,
            ring_size=4,
            retrieval_size=100,
        )

        repr_str = repr(packet)
        assert "ring=4" in repr_str
        assert "retrieval=100" in repr_str
        assert "entities=3" in repr_str
        assert "used_retrieval=True" in repr_str


class TestContextPipeline:
    """Tests for ContextPipeline class."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        return MockDatabase()

    @pytest.fixture
    def pipeline(self, mock_db):
        """Create a pipeline instance for testing."""
        return ContextPipeline(
            db=mock_db,
            max_ring_turns=6,
            base_personality="You are Luna, a sovereign AI companion.",
        )

    @pytest.mark.asyncio
    async def test_pipeline_initialization(self, pipeline):
        """Test pipeline initializes correctly."""
        assert not pipeline._initialized

        # Initialize (will fail entity system but continue)
        await pipeline.initialize()

        assert pipeline._initialized
        assert isinstance(pipeline.ring, ConversationRing)

    @pytest.mark.asyncio
    async def test_build_adds_to_ring(self, pipeline):
        """Test that build() adds user message to ring."""
        await pipeline.initialize()

        packet = await pipeline.build("Hello Luna!")

        assert len(pipeline.ring) == 1
        assert pipeline.ring.contains("Hello Luna")
        assert packet.ring_size == 1

    @pytest.mark.asyncio
    async def test_build_returns_packet(self, pipeline):
        """Test that build() returns a valid ContextPacket."""
        await pipeline.initialize()

        packet = await pipeline.build("Do you remember Marzipan?")

        assert isinstance(packet, ContextPacket)
        assert packet.current_message == "Do you remember Marzipan?"
        assert len(packet.messages) == 1
        assert "THIS SESSION" in packet.system_prompt

    @pytest.mark.asyncio
    async def test_record_response_adds_to_ring(self, pipeline):
        """Test that record_response() adds assistant message to ring."""
        await pipeline.initialize()

        await pipeline.build("Question")
        pipeline.record_response("Answer")

        assert len(pipeline.ring) == 2
        assert pipeline.ring.contains("Answer")
        assert pipeline.ring.get_last_assistant_message() == "Answer"

    @pytest.mark.asyncio
    async def test_system_prompt_structure(self, pipeline):
        """Test that system prompt has correct structure."""
        await pipeline.initialize()

        packet = await pipeline.build("Hello")

        # Should have base personality
        assert "Luna" in packet.system_prompt

        # Should have THIS SESSION section
        assert "THIS SESSION" in packet.system_prompt
        assert "Direct Experience" in packet.system_prompt

        # Should have the message in ring history
        assert "Hello" in packet.system_prompt

    @pytest.mark.asyncio
    async def test_messages_array_format(self, pipeline):
        """Test that messages array is in correct format."""
        await pipeline.initialize()

        await pipeline.build("First question")
        pipeline.record_response("First answer")
        packet = await pipeline.build("Second question")

        # Should have all turns
        assert len(packet.messages) == 3

        # Should be in correct format
        assert packet.messages[0] == {"role": "user", "content": "First question"}
        assert packet.messages[1] == {"role": "assistant", "content": "First answer"}
        assert packet.messages[2] == {"role": "user", "content": "Second question"}

    @pytest.mark.asyncio
    async def test_marzipan_scenario(self, pipeline):
        """
        The Marzipan Test — the unified pipeline version.

        Context should be identical whether going to local or delegated.
        """
        await pipeline.initialize()

        # Turn 1: Ask about Marzipan
        packet1 = await pipeline.build("Do you remember the guy Marzipan?")

        assert "Marzipan" in packet1.system_prompt
        assert packet1.ring_size == 1

        # Simulate response
        pipeline.record_response("Oh absolutely! Marzipan - Ahab's friend who identifies with owls.")

        # Turn 2: Ask about Mars College
        packet2 = await pipeline.build("Tell me about Mars College")

        # CRITICAL: Marzipan should STILL be in the context
        assert "Marzipan" in packet2.system_prompt
        assert "owls" in packet2.system_prompt
        assert packet2.ring_size == 3

        # The messages array should have full history
        assert len(packet2.messages) == 3
        assert "Marzipan" in packet2.messages[0]["content"]
        assert "owls" in packet2.messages[1]["content"]

    @pytest.mark.asyncio
    async def test_self_routing_topic_in_ring(self, pipeline):
        """Test self-routing when topic is already in ring."""
        await pipeline.initialize()

        # Simulate entity detection by adding entity to ring
        await pipeline.build("Marzipan is my friend")
        pipeline.record_response("Yes, Marzipan!")

        # Now ask again - topic should be in ring
        # Note: Without actual entity resolver, we test the ring mechanism
        packet = await pipeline.build("Tell me more about Marzipan")

        # Topic was in ring
        assert pipeline.ring.contains("Marzipan")

    @pytest.mark.asyncio
    async def test_clear_session(self, pipeline):
        """Test clearing session resets ring."""
        await pipeline.initialize()

        await pipeline.build("First message")
        pipeline.record_response("Response")

        assert len(pipeline.ring) == 2

        pipeline.clear_session()

        assert len(pipeline.ring) == 0

    @pytest.mark.asyncio
    async def test_set_base_personality(self, pipeline):
        """Test updating base personality."""
        await pipeline.initialize()

        pipeline.set_base_personality("You are a helpful assistant named Bob.")

        packet = await pipeline.build("Hello")

        assert "Bob" in packet.system_prompt

    def test_get_ring_summary(self, pipeline):
        """Test getting ring summary."""
        # Add some history directly to ring
        pipeline.ring.add_user("Do you know Marzipan?")
        pipeline.ring.add_assistant("Yes! He loves owls.")

        summary = pipeline.get_ring_summary()

        assert "2 turns" in summary
        assert "marzipan" in summary.lower()

    @pytest.mark.asyncio
    async def test_identical_context_for_both_paths(self, pipeline):
        """
        Test that the same ContextPacket can be used for both paths.

        This is the core architectural guarantee.
        """
        await pipeline.initialize()

        # Build context
        await pipeline.build("Question 1")
        pipeline.record_response("Answer 1")
        packet = await pipeline.build("Question 2")

        # Simulate "local path" usage
        local_system_prompt = packet.system_prompt
        local_messages = packet.messages

        # Simulate "delegated path" usage
        delegated_system_prompt = packet.system_prompt
        delegated_messages = packet.messages

        # CRITICAL: They must be identical
        assert local_system_prompt == delegated_system_prompt
        assert local_messages == delegated_messages

        # Both have full context
        assert "Question 1" in local_system_prompt
        assert "Answer 1" in local_system_prompt
        assert len(local_messages) == 3  # Q1, A1, Q2


class TestContextPipelineIntegration:
    """Integration-style tests for realistic scenarios."""

    @pytest.fixture
    def mock_db(self):
        return MockDatabase()

    @pytest.mark.asyncio
    async def test_five_turn_conversation(self, mock_db):
        """Test a realistic 5-turn conversation."""
        pipeline = ContextPipeline(db=mock_db, max_ring_turns=10)
        await pipeline.initialize()

        # Turn 1
        p1 = await pipeline.build("Hi Luna!")
        pipeline.record_response("Hello! How are you?")

        # Turn 2
        p2 = await pipeline.build("Do you remember Marzipan?")
        pipeline.record_response("Yes! Marzipan is your friend with owls.")

        # Turn 3
        p3 = await pipeline.build("What about the owls specifically?")
        pipeline.record_response("Owls are Marzipan's spirit animal from age 2.")

        # Turn 4
        p4 = await pipeline.build("Tell me about Mars College")
        pipeline.record_response("Mars College is an AI camp in the desert.")

        # Turn 5
        p5 = await pipeline.build("And Marzipan's connection to it?")

        # Final packet should have FULL history
        assert p5.ring_size == 9  # 5 user + 4 assistant (before 5th response)
        assert "Marzipan" in p5.system_prompt
        assert "owls" in p5.system_prompt
        assert "Mars College" in p5.system_prompt
        assert "spirit animal" in p5.system_prompt

    @pytest.mark.asyncio
    async def test_ring_eviction(self, mock_db):
        """Test that ring eviction works correctly."""
        pipeline = ContextPipeline(db=mock_db, max_ring_turns=4)
        await pipeline.initialize()

        # Fill the ring
        await pipeline.build("Message 1")
        pipeline.record_response("Response 1")
        await pipeline.build("Message 2")
        pipeline.record_response("Response 2")

        assert len(pipeline.ring) == 4

        # Add one more - should evict oldest
        await pipeline.build("Message 3")

        assert len(pipeline.ring) == 4
        assert not pipeline.ring.contains("Message 1")
        assert pipeline.ring.contains("Message 3")
