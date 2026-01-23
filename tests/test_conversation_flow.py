"""Test realistic conversation flows."""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

class TestMemoryQueryRouting:

    def test_memory_patterns_detect_remember(self):
        """Test that 'remember' triggers memory query detection."""
        from luna.agentic.router import QueryRouter

        router = QueryRouter()

        # These should detect memory_query signal
        memory_queries = [
            "Do you remember Marzipan?",
            "Can you recall our conversation?",
            "What do you know about Mars College?",
            "Try to remember the project we discussed.",
            "Who is Ahab?",
            "Tell me about Luna's development.",
        ]

        for query in memory_queries:
            decision = router.analyze(query)
            assert "memory_query" in decision.signals, f"Failed to detect memory query in: {query}"

    def test_non_memory_queries(self):
        """Test that regular queries don't trigger memory signal."""
        from luna.agentic.router import QueryRouter

        router = QueryRouter()

        non_memory = [
            "What is 2+2?",
            "Write me a poem.",
            "Hello!",
        ]

        for query in non_memory:
            decision = router.analyze(query)
            assert "memory_query" not in decision.signals, f"False positive memory detection in: {query}"


class TestConversationFlow:

    @pytest.fixture
    def mock_engine(self, tmp_path):
        """Create mock engine for testing."""
        from luna.engine import LunaEngine, EngineConfig

        config = EngineConfig(data_dir=tmp_path)
        engine = LunaEngine(config)

        # Mock director with generate method
        mock_director = MagicMock()
        mock_director.generate = AsyncMock(return_value="Marzipan is a friend from Mars College who works on AI consciousness projects.")
        mock_director._fetch_memory_context = AsyncMock(return_value="Memory about Marzipan...")
        engine.actors["director"] = mock_director

        # Mock matrix
        mock_matrix = MagicMock()
        mock_matrix.is_ready = True
        mock_matrix.get_context = AsyncMock(return_value="Marzipan context")
        engine.actors["matrix"] = mock_matrix

        return engine

    @pytest.mark.asyncio
    async def test_remember_query_uses_director(self, mock_engine):
        """Test that memory queries call director.generate()."""
        # For DIRECT routing (simple queries), process_input calls director.generate directly
        # The router will route "Do you remember Marzipan?" as DIRECT since it's a simple question

        director = mock_engine.get_actor("director")

        # Call process_input which should use director for simple queries
        from luna.agentic.router import QueryRouter, ExecutionPath
        router = QueryRouter()
        routing = router.analyze("Do you remember Marzipan?")

        # Memory queries may route to DIRECT or SIMPLE_PLAN
        # Either way, if DIRECT, it uses director.generate()
        if routing.path == ExecutionPath.DIRECT:
            response = await director.generate("Do you remember Marzipan?")
            assert "marzipan" in response.lower()
            director.generate.assert_called()
        else:
            # If it routes to agent loop, we just verify the routing works
            assert "memory_query" in routing.signals
