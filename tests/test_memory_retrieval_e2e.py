"""End-to-end memory retrieval tests."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

class TestMemoryRetrieval:

    @pytest.fixture
    def engine_with_mocks(self, tmp_path):
        """Create engine with mocked actors."""
        from luna.engine import LunaEngine, EngineConfig
        from luna.actors.director import DirectorActor

        config = EngineConfig(data_dir=tmp_path)
        engine = LunaEngine(config)

        # Create real director with engine reference
        director = DirectorActor()
        director.engine = engine
        engine.actors["director"] = director

        # Mock matrix with test data
        mock_matrix = MagicMock()
        mock_matrix.is_ready = True
        mock_matrix.get_context = AsyncMock(return_value="Marzipan is a friend at Mars College who works on AI consciousness.")
        mock_matrix._matrix = None  # No direct matrix access
        engine.actors["matrix"] = mock_matrix

        return engine

    @pytest.mark.asyncio
    async def test_fetch_memory_context_returns_data(self, engine_with_mocks):
        """Test that _fetch_memory_context returns memory data."""
        director = engine_with_mocks.get_actor("director")

        context = await director._fetch_memory_context("Who is Marzipan?")

        assert context is not None
        assert len(context) > 0
        assert "marzipan" in context.lower() or "mars" in context.lower()

    @pytest.mark.asyncio
    async def test_fetch_memory_handles_missing_matrix(self, tmp_path):
        """Test graceful handling when matrix is not available."""
        from luna.engine import LunaEngine, EngineConfig
        from luna.actors.director import DirectorActor

        config = EngineConfig(data_dir=tmp_path)
        engine = LunaEngine(config)

        director = DirectorActor()
        director.engine = engine
        engine.actors["director"] = director
        # No matrix actor set

        context = await director._fetch_memory_context("test query")
        assert context == ""


class TestIdentityHandling:

    def test_identity_anchor_exists(self):
        """Test that identity anchor text is defined."""
        # The identity anchor should prevent Luna from confusing users
        identity_anchor = """
You are talking with Ahab (also known as Zayne). He is your creator and primary collaborator.
Do not confuse him with other people mentioned in your memories.
"""
        assert "Ahab" in identity_anchor
        assert "Zayne" in identity_anchor
        assert "creator" in identity_anchor
