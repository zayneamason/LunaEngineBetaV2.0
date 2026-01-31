"""Critical systems unit tests."""
import pytest
import os
import sys
from pathlib import Path

# Setup path and env
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")


class TestEnvironment:
    """Test environment variables are set."""

    def test_anthropic_key(self):
        key = os.environ.get("ANTHROPIC_API_KEY")
        assert key, "ANTHROPIC_API_KEY not set"
        assert len(key) > 10, "ANTHROPIC_API_KEY too short"

    def test_groq_key(self):
        key = os.environ.get("GROQ_API_KEY")
        assert key, "GROQ_API_KEY not set"
        assert len(key) > 10, "GROQ_API_KEY too short"

    def test_google_key(self):
        key = os.environ.get("GOOGLE_API_KEY")
        assert key, "GOOGLE_API_KEY not set"
        assert len(key) > 10, "GOOGLE_API_KEY too short"


class TestImports:
    """Test critical imports work."""

    def test_mlx(self):
        import mlx
        import mlx_lm

    def test_gemini(self):
        import google.generativeai

    def test_websockets(self):
        import websockets

    def test_fastapi(self):
        import fastapi

    def test_anthropic(self):
        import anthropic

    def test_groq(self):
        import groq


class TestDatabase:
    """Test database exists and has data."""

    def test_exists(self):
        db = PROJECT_ROOT / "data" / "luna_engine.db"
        assert db.exists(), f"Database not found at {db}"

    def test_nodes(self):
        import sqlite3
        db = PROJECT_ROOT / "data" / "luna_engine.db"
        conn = sqlite3.connect(db)
        count = conn.execute("SELECT COUNT(*) FROM memory_nodes").fetchone()[0]
        conn.close()
        assert count >= 10000, f"Only {count} nodes, expected 10000+"

    def test_edges(self):
        import sqlite3
        db = PROJECT_ROOT / "data" / "luna_engine.db"
        conn = sqlite3.connect(db)
        count = conn.execute("SELECT COUNT(*) FROM graph_edges").fetchone()[0]
        conn.close()
        assert count >= 1000, f"Only {count} edges, expected 1000+"


class TestLunaImports:
    """Test Luna module imports."""

    def test_engine(self):
        from luna.engine import LunaEngine

    def test_actors(self):
        from luna.actors.base import Actor
        from luna.actors.director import DirectorActor

    def test_memory(self):
        from luna.substrate.memory import MemoryMatrix

    def test_llm_providers(self):
        from luna.llm.providers.gemini_provider import GeminiProvider
        from luna.llm.providers.groq_provider import GroqProvider
        from luna.llm.providers.claude_provider import ClaudeProvider


class TestLLMProviders:
    """Test LLM providers are available."""

    def test_gemini_available(self):
        from luna.llm.providers.gemini_provider import GeminiProvider
        provider = GeminiProvider()
        assert provider.is_available, "Gemini provider not available"

    def test_groq_available(self):
        from luna.llm.providers.groq_provider import GroqProvider
        provider = GroqProvider()
        assert provider.is_available, "Groq provider not available"


class TestAPIServer:
    """Test API server module loads."""

    def test_server_import(self):
        from luna.api.server import app
        assert app is not None

    def test_routes_exist(self):
        from luna.api.server import app
        routes = [r.path for r in app.routes]
        assert "/health" in routes or any("/health" in str(r) for r in routes)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
