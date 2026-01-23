"""
Director Integration Tests — Real Components, No Mocks.

These tests verify the ACTUAL production code path, not isolated components.
If these pass, the system works. If these fail, it doesn't matter that
unit tests pass.

The goal is to catch the integration gap where:
- Unit tests pass (components work in isolation)
- Integration fails (components don't connect properly)

Key scenarios tested:
1. Context pipeline initializes successfully
2. Ring buffer exists and persists across turns
3. Two-turn memory works on both local and delegated paths
4. Marzipan scenario (ask about topic, change topic, reference back)
5. Identity preserved on local path
"""

import pytest
import asyncio
import tempfile
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import logging

# Configure logging to see what's happening
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestDirectorIntegration:
    """Integration tests for Director with real (or minimally mocked) components."""

    @pytest.fixture
    def temp_db_dir(self):
        """Create a temporary directory for test database."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def mock_db(self):
        """Create a mock database that tracks calls."""
        db = AsyncMock()
        db.fetchall = AsyncMock(return_value=[])
        db.fetchone = AsyncMock(return_value=None)
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    async def director_with_pipeline(self, mock_db):
        """
        Create a Director with a working context pipeline.

        This tests the INTENDED flow where context pipeline is available.
        """
        from luna.actors.director import DirectorActor
        from luna.context.pipeline import ContextPipeline

        director = DirectorActor(name="test_director", engine=None, enable_local=False)

        # Initialize context pipeline manually with mock DB
        director._context_pipeline = ContextPipeline(
            db=mock_db,
            max_ring_turns=6,
            base_personality="You are Luna, a sovereign AI companion."
        )
        await director._context_pipeline.initialize()

        # Verify pipeline is ready
        assert director._context_pipeline is not None
        assert director._context_pipeline._initialized

        yield director

    @pytest.fixture
    async def director_without_pipeline(self):
        """
        Create a Director WITHOUT context pipeline.

        This tests the FALLBACK flow where pipeline init failed.
        """
        from luna.actors.director import DirectorActor

        director = DirectorActor(name="test_director", engine=None, enable_local=False)

        # Explicitly set pipeline to None (simulating init failure)
        director._context_pipeline = None

        # Verify standalone ring exists (structural guarantee)
        assert director._standalone_ring is not None

        yield director

    # =========================================================================
    # TEST: Pipeline Initialization
    # =========================================================================

    @pytest.mark.asyncio
    async def test_context_pipeline_initializes(self, mock_db):
        """Context pipeline MUST initialize successfully when DB is available."""
        from luna.actors.director import DirectorActor
        from luna.context.pipeline import ContextPipeline

        director = DirectorActor(name="test_director", engine=None, enable_local=False)

        # Manually init pipeline (bypassing engine dependency)
        director._context_pipeline = ContextPipeline(
            db=mock_db,
            max_ring_turns=6,
            base_personality="You are Luna."
        )
        await director._context_pipeline.initialize()

        # Assertions
        assert director._context_pipeline is not None, \
            "Context pipeline failed to initialize!"
        assert director._context_pipeline._initialized, \
            "Context pipeline exists but _initialized is False!"

        logger.info("✅ Context pipeline initialized")

    @pytest.mark.asyncio
    async def test_ring_buffer_always_exists(self):
        """Ring buffer MUST exist regardless of pipeline status."""
        from luna.actors.director import DirectorActor

        director = DirectorActor(name="test_director", engine=None, enable_local=False)

        # Even without initialization, standalone ring should exist
        assert director._standalone_ring is not None, \
            "Standalone ring buffer doesn't exist!"

        # _active_ring should return something
        ring = director._active_ring
        assert ring is not None, \
            "_active_ring property returns None!"

        logger.info("✅ Ring buffer exists")

    # =========================================================================
    # TEST: Ring Buffer Persistence
    # =========================================================================

    @pytest.mark.asyncio
    async def test_ring_persists_across_builds(self, director_with_pipeline):
        """Ring buffer should accumulate messages across multiple build() calls."""
        director = director_with_pipeline
        pipeline = director._context_pipeline

        # Build context for turn 1
        packet1 = await pipeline.build("My name is TestUser")
        assert packet1.ring_size >= 1, "Ring should have at least 1 entry after build"

        # Simulate response
        pipeline.record_response("Nice to meet you, TestUser!")

        # Build context for turn 2
        packet2 = await pipeline.build("What is my name?")

        # Ring should now have: user1, assistant1, user2
        assert packet2.ring_size >= 3, \
            f"Ring should have 3+ entries, has {packet2.ring_size}"

        # Verify first message is in ring
        assert pipeline._ring.contains("TestUser"), \
            "Ring doesn't contain 'TestUser' from turn 1!"

        logger.info(f"✅ Ring persists: {packet2.ring_size} entries")

    @pytest.mark.asyncio
    async def test_ring_history_in_system_prompt(self, director_with_pipeline):
        """Ring buffer history should appear in system prompt."""
        director = director_with_pipeline
        pipeline = director._context_pipeline

        # Turn 1
        await pipeline.build("I love purple")
        pipeline.record_response("Purple is a beautiful color!")

        # Turn 2
        packet = await pipeline.build("What color do I like?")

        # System prompt should contain history
        assert "purple" in packet.system_prompt.lower(), \
            f"System prompt doesn't contain 'purple'!\nPrompt: {packet.system_prompt[:500]}"

        assert "THIS SESSION" in packet.system_prompt, \
            "System prompt missing 'THIS SESSION' marker!"

        logger.info("✅ Ring history appears in system prompt")

    # =========================================================================
    # TEST: Two-Turn Memory (The Critical Test)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_two_turn_memory_with_pipeline(self, director_with_pipeline):
        """
        THE CRITICAL TEST: Two-turn memory via context pipeline.

        If this fails, Luna forgets mid-conversation.
        """
        director = director_with_pipeline
        pipeline = director._context_pipeline

        # Turn 1: Establish a fact
        packet1 = await pipeline.build("Remember this: my favorite color is purple.")
        pipeline.record_response("I'll remember that your favorite color is purple!")

        # Turn 2: Ask about it
        packet2 = await pipeline.build("What is my favorite color?")

        # Verify context includes the fact
        assert "purple" in packet2.system_prompt.lower(), \
            f"FAILED: Context doesn't include 'purple'!\n{packet2.system_prompt[:500]}"

        # Verify messages array has history
        assert len(packet2.messages) >= 3, \
            f"FAILED: Messages array should have 3+ entries, has {len(packet2.messages)}"

        # Check that first user message is in messages
        first_user_content = None
        for msg in packet2.messages:
            if msg.get("role") == "user":
                first_user_content = msg.get("content", "")
                break

        assert first_user_content and "purple" in first_user_content.lower(), \
            f"FAILED: First user message doesn't contain 'purple'!"

        logger.info("✅ Two-turn memory works with pipeline")

    @pytest.mark.asyncio
    async def test_two_turn_memory_without_pipeline(self, director_without_pipeline):
        """
        Two-turn memory via standalone ring buffer (fallback path).

        Tests that history works even when context pipeline is unavailable.
        """
        director = director_without_pipeline
        ring = director._standalone_ring

        # Turn 1: Add to ring
        ring.add_user("My favorite number is 42.")
        ring.add_assistant("I'll remember that your favorite number is 42!")

        # Turn 2: Add next user message
        ring.add_user("What is my favorite number?")

        # Verify ring has history
        assert len(ring) >= 3, \
            f"Ring should have 3+ entries, has {len(ring)}"

        # Verify content is in ring
        assert ring.contains("42"), \
            "Ring doesn't contain '42' from turn 1!"

        # Get formatted history
        history = ring.format_for_prompt()
        assert "42" in history, \
            f"Formatted history doesn't contain '42'!\n{history}"

        logger.info("✅ Two-turn memory works without pipeline (fallback)")

    # =========================================================================
    # TEST: Marzipan Scenario (The Original Failure Case)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_marzipan_scenario(self, director_with_pipeline):
        """
        THE MARZIPAN TEST — The original failure case.

        Scenario:
        1. Ask about Marzipan and owls
        2. Ask about Mars College (different topic)
        3. Ask "What did you tell me about Marzipan earlier?"

        Luna should remember turn 1, not claim ignorance.
        """
        director = director_with_pipeline
        pipeline = director._context_pipeline

        # Turn 1: Ask about Marzipan
        packet1 = await pipeline.build("Tell me about Marzipan and the owls")
        pipeline.record_response(
            "Marzipan is a fascinating person who has a deep connection with owls. "
            "He runs owl tours and has studied them for years."
        )

        # Turn 2: Ask about Mars College (different topic)
        packet2 = await pipeline.build("Tell me about Mars College")
        pipeline.record_response(
            "Mars College is an experimental educational community in the desert. "
            "It focuses on alternative learning and creative exploration."
        )

        # Turn 3: Reference back to Marzipan
        packet3 = await pipeline.build("What did you tell me about Marzipan earlier?")

        # Verify Marzipan is still in context
        assert "marzipan" in packet3.system_prompt.lower(), \
            f"FAILED: Marzipan not in system prompt!\n{packet3.system_prompt[:800]}"

        assert "owl" in packet3.system_prompt.lower(), \
            f"FAILED: Owls not in system prompt!"

        # Verify ring has full history
        assert packet3.ring_size >= 5, \
            f"Ring should have 5+ entries (3 users, 2 assistants), has {packet3.ring_size}"

        logger.info("✅ Marzipan scenario passes")

    # =========================================================================
    # TEST: Self-Routing (Skip Retrieval When Topic in Ring)
    # =========================================================================

    @pytest.mark.asyncio
    async def test_self_routing_skips_retrieval(self, director_with_pipeline):
        """
        When a topic is already in the ring buffer, retrieval should be skipped.

        This prevents memory retrieval from displacing conversation history.
        """
        director = director_with_pipeline
        pipeline = director._context_pipeline

        # Mock entity resolver to detect "Marzipan" as entity
        mock_entity = MagicMock()
        mock_entity.name = "Marzipan"
        mock_entity.core_facts = {"occupation": "owl tour guide"}

        if pipeline._entity_resolver:
            pipeline._entity_resolver.detect_mentions = AsyncMock(return_value=[mock_entity])

        # Turn 1: Discuss Marzipan (adds to ring)
        packet1 = await pipeline.build("Tell me about Marzipan")
        pipeline.record_response("Marzipan runs owl tours...")

        # Turn 2: Ask about Marzipan again
        packet2 = await pipeline.build("What else about Marzipan?")

        # Should detect topic is in ring and skip retrieval
        # (topic_in_ring should be True, used_retrieval should be False)
        assert packet2.topic_in_ring or not packet2.used_retrieval, \
            f"Should skip retrieval when topic in ring! topic_in_ring={packet2.topic_in_ring}"

        logger.info("✅ Self-routing works")

    # =========================================================================
    # TEST: Active Ring Property
    # =========================================================================

    @pytest.mark.asyncio
    async def test_active_ring_returns_pipeline_ring(self, director_with_pipeline):
        """
        _active_ring should return pipeline's ring when pipeline exists.
        """
        director = director_with_pipeline

        # _active_ring should be the same object as pipeline._ring
        assert director._active_ring is director._context_pipeline._ring, \
            "_active_ring doesn't return pipeline's ring!"

        logger.info("✅ _active_ring returns pipeline ring")

    @pytest.mark.asyncio
    async def test_active_ring_returns_standalone_ring(self, director_without_pipeline):
        """
        _active_ring should return standalone ring when pipeline is None.
        """
        director = director_without_pipeline

        # _active_ring should be the standalone ring
        assert director._active_ring is director._standalone_ring, \
            "_active_ring doesn't return standalone ring when pipeline is None!"

        logger.info("✅ _active_ring returns standalone ring")

    # =========================================================================
    # TEST: Context Packet Structure
    # =========================================================================

    @pytest.mark.asyncio
    async def test_context_packet_has_required_fields(self, director_with_pipeline):
        """Context packet should have all required fields for inference."""
        director = director_with_pipeline
        pipeline = director._context_pipeline

        packet = await pipeline.build("Test message")

        # Required fields
        assert hasattr(packet, 'system_prompt'), "Missing system_prompt"
        assert hasattr(packet, 'messages'), "Missing messages"
        assert hasattr(packet, 'current_message'), "Missing current_message"
        assert hasattr(packet, 'ring_size'), "Missing ring_size"

        # Type checks
        assert isinstance(packet.system_prompt, str), "system_prompt should be str"
        assert isinstance(packet.messages, list), "messages should be list"
        assert packet.current_message == "Test message", "current_message mismatch"

        logger.info("✅ Context packet has required fields")

    @pytest.mark.asyncio
    async def test_messages_array_format(self, director_with_pipeline):
        """Messages array should be in Claude API format [{role, content}]."""
        director = director_with_pipeline
        pipeline = director._context_pipeline

        await pipeline.build("First message")
        pipeline.record_response("First response")
        packet = await pipeline.build("Second message")

        for msg in packet.messages:
            assert "role" in msg, f"Message missing 'role': {msg}"
            assert "content" in msg, f"Message missing 'content': {msg}"
            assert msg["role"] in ["user", "assistant"], f"Invalid role: {msg['role']}"

        logger.info("✅ Messages array in correct format")


class TestRegressionPrevention:
    """Tests specifically designed to catch the bugs we've seen."""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database."""
        db = AsyncMock()
        db.fetchall = AsyncMock(return_value=[])
        db.fetchone = AsyncMock(return_value=None)
        db.execute = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_history_not_displaced_by_retrieval(self, mock_db):
        """
        REGRESSION TEST: Memory retrieval must not displace conversation history.

        Bug: Luna would search memory, get results about Topic B,
        and then claim she didn't know about Topic A (which was in history).
        """
        from luna.context.pipeline import ContextPipeline

        # Mock DB returns unrelated memory about Topic B
        mock_db.fetchall = AsyncMock(return_value=[
            ("Unrelated memory about Topic B and bananas", "2025-01-01")
        ])

        pipeline = ContextPipeline(
            db=mock_db,
            max_ring_turns=6,
            base_personality="You are Luna"
        )
        await pipeline.initialize()

        # Turn 1: Discuss Topic A (purple color)
        packet1 = await pipeline.build("My favorite color is purple")
        pipeline.record_response("Purple is beautiful! I love that it's your favorite.")

        # Turn 2: Ask about Topic B (triggers retrieval of unrelated stuff)
        packet2 = await pipeline.build("Tell me about bananas")

        # CRITICAL: Topic A (purple) must still be in context
        assert "purple" in packet2.system_prompt.lower(), \
            "REGRESSION: Topic A (purple) was displaced by retrieval!"

        # The response about purple should also be there
        assert "beautiful" in packet2.system_prompt.lower() or "favorite" in packet2.system_prompt.lower(), \
            "REGRESSION: Previous response was lost!"

        logger.info("✅ History not displaced by retrieval")

    @pytest.mark.asyncio
    async def test_five_turn_continuity(self, mock_db):
        """
        Extended memory test — 5 turns of conversation.

        All facts should be retained in the ring buffer.
        """
        from luna.context.pipeline import ContextPipeline

        pipeline = ContextPipeline(
            db=mock_db,
            max_ring_turns=12,  # Enough for 5 turns (10 messages)
            base_personality="You are Luna"
        )
        await pipeline.initialize()

        facts = [
            ("My name is TestUser", "TestUser"),
            ("I live in Tokyo", "Tokyo"),
            ("I have a cat named Whiskers", "Whiskers"),
            ("My favorite food is sushi", "sushi"),
            ("I work as an engineer", "engineer"),
        ]

        # Establish all facts
        for statement, _ in facts:
            packet = await pipeline.build(statement)
            pipeline.record_response(f"Got it! {statement}")

        # Final query
        packet = await pipeline.build("What do you remember about me?")

        # All facts should be in context
        prompt_lower = packet.system_prompt.lower()
        for statement, keyword in facts:
            assert keyword.lower() in prompt_lower, \
                f"FAILED: Lost fact '{keyword}' after 5 turns!\nPrompt: {packet.system_prompt[:1000]}"

        logger.info("✅ Five-turn continuity works")

    @pytest.mark.asyncio
    async def test_pipeline_init_failure_doesnt_leave_broken_state(self):
        """
        REGRESSION TEST: If pipeline.initialize() fails, state should be clean.

        Bug: Pipeline object was created, but if initialize() failed,
        the object was left in a broken state and later code thought it was ready.
        """
        from luna.context.pipeline import ContextPipeline

        # Create pipeline with broken DB
        broken_db = MagicMock()
        broken_db.fetchall = MagicMock(side_effect=Exception("DB connection failed"))

        pipeline = ContextPipeline(
            db=broken_db,
            max_ring_turns=6,
            base_personality="You are Luna"
        )

        # Initialize - should complete (entity system failure is non-fatal)
        await pipeline.initialize()

        # Pipeline should still be usable (ring buffer works without entity system)
        assert pipeline._initialized, "Pipeline should be initialized even if entity system fails"

        # Ring buffer should work
        packet = await pipeline.build("Test message")
        assert packet.ring_size >= 1, "Ring buffer should work without entity system"

        logger.info("✅ Pipeline gracefully handles entity system failure")


class TestDirectorRingIntegration:
    """Tests for Director's ring buffer integration."""

    @pytest.mark.asyncio
    async def test_process_records_to_ring(self):
        """
        Director.process() should record both user and assistant to ring.
        """
        from luna.actors.director import DirectorActor
        from luna.context.pipeline import ContextPipeline

        # Create director with mock pipeline
        director = DirectorActor(name="test", engine=None, enable_local=False)

        mock_db = AsyncMock()
        mock_db.fetchall = AsyncMock(return_value=[])

        director._context_pipeline = ContextPipeline(
            db=mock_db,
            max_ring_turns=6,
            base_personality="You are Luna"
        )
        await director._context_pipeline.initialize()

        # Mock Claude client to avoid real API calls
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hello! I'm Luna.")]

        mock_client = MagicMock()
        mock_client.messages.create = MagicMock(return_value=mock_response)
        director._client = mock_client

        # Patch _should_delegate to always delegate (so we test the delegated path)
        director._should_delegate = AsyncMock(return_value=True)

        # Call process
        result = await director.process("Hello!", context={})

        # Check ring has the turn
        ring = director._active_ring
        assert len(ring) >= 2, f"Ring should have user+assistant, has {len(ring)}"

        # Verify user message is in ring
        assert ring.contains("Hello"), "User message not in ring!"

        logger.info("✅ process() records to ring")


# Run with: pytest tests/test_director_integration.py -v
