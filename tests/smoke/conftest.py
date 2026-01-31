"""
Smoke Test Fixtures
===================

Fixtures for smoke tests that use real components with minimal mocking.
Only external APIs (Claude, Groq, etc.) are mocked.
"""

import asyncio
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from luna.engine import LunaEngine, EngineConfig
from luna.core.state import EngineState
from luna.substrate.database import MemoryDatabase
from luna.substrate.memory import MemoryMatrix


# ============================================================================
# DATABASE FIXTURES
# ============================================================================


@pytest.fixture
def temp_db_path():
    """Create a temporary database file as Path object."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        yield Path(f.name)
    try:
        os.unlink(f.name)
    except (FileNotFoundError, PermissionError):
        pass


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest_asyncio.fixture
async def memory_db(temp_db_path) -> AsyncGenerator[MemoryDatabase, None]:
    """Create and connect a real database instance."""
    db = MemoryDatabase(temp_db_path)
    await db.connect()
    yield db
    await db.close()


@pytest_asyncio.fixture
async def memory_matrix(memory_db) -> AsyncGenerator[MemoryMatrix, None]:
    """Create a real MemoryMatrix instance with embeddings disabled for speed."""
    mm = MemoryMatrix(memory_db, enable_embeddings=False)
    yield mm


# ============================================================================
# ENGINE FIXTURES
# ============================================================================


@pytest.fixture
def smoke_engine_config(temp_data_dir):
    """Create engine config optimized for smoke tests."""
    return EngineConfig(
        cognitive_interval=0.1,  # Fast ticks for tests
        reflective_interval=300,  # Don't run reflective loop
        data_dir=temp_data_dir,
        enable_local_inference=False,  # Skip local model loading
        voice_enabled=False,  # Skip voice system
    )


@pytest_asyncio.fixture
async def running_engine(smoke_engine_config) -> AsyncGenerator[LunaEngine, None]:
    """
    Start a real engine instance for smoke tests.

    Mocks external API calls but uses real database and actors.
    """
    engine = LunaEngine(smoke_engine_config)

    # Mock external API calls in DirectorActor
    mock_claude_response = {
        "text": "Hello! I'm Luna, your AI assistant.",
        "model": "claude-sonnet-4-20250514",
        "input_tokens": 50,
        "output_tokens": 20,
        "latency_ms": 100.0,
        "delegated": True,
    }

    # Start engine in background
    engine_task = asyncio.create_task(engine.run())

    # Wait for engine to be ready
    ready = await engine.wait_ready(timeout=10.0)
    if not ready:
        engine_task.cancel()
        try:
            await engine_task
        except asyncio.CancelledError:
            pass
        pytest.fail("Engine failed to start within timeout")

    yield engine

    # Cleanup
    await engine.stop()
    try:
        await asyncio.wait_for(engine_task, timeout=5.0)
    except asyncio.TimeoutError:
        engine_task.cancel()
        try:
            await engine_task
        except asyncio.CancelledError:
            pass


# ============================================================================
# API FIXTURES
# ============================================================================


@pytest.fixture
def mock_external_apis():
    """
    Mock all external API calls.

    This patches Claude, Groq, and other external services
    while allowing internal components to work normally.
    """
    mock_response = AsyncMock(return_value={
        "text": "Test response from Luna.",
        "model": "mock-model",
        "input_tokens": 10,
        "output_tokens": 5,
        "latency_ms": 50.0,
    })

    # Patch the generate method on DirectorActor
    with patch("luna.actors.director.DirectorActor._call_claude", mock_response):
        with patch("luna.actors.director.DirectorActor._call_local", mock_response):
            yield mock_response


@pytest.fixture
def mock_startup_check():
    """Mock the critical systems check for smoke tests."""
    with patch("luna.api.server.run_startup_check"):
        with patch("luna.api.server.start_watchdog", return_value=MagicMock()):
            yield


# ============================================================================
# TIMEOUT HELPER
# ============================================================================


async def with_timeout(coro, seconds: float = 10.0):
    """Run coroutine with a timeout. Use in tests instead of pytest-timeout."""
    return await asyncio.wait_for(coro, timeout=seconds)
