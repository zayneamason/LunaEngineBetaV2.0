"""
Pytest configuration and shared fixtures for Luna Engine tests.
"""

import asyncio
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory

from luna.engine import LunaEngine, EngineConfig
from luna.core.events import InputEvent, EventType, EventPriority
from luna.core.input_buffer import InputBuffer
from luna.actors.base import Actor, Message


@pytest.fixture
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for tests."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def engine_config(temp_data_dir):
    """Create test engine configuration."""
    return EngineConfig(
        cognitive_interval=0.1,  # Fast ticks for tests
        reflective_interval=60,
        data_dir=temp_data_dir,
    )


@pytest.fixture
def input_buffer():
    """Create fresh input buffer for tests."""
    return InputBuffer(max_size=10, stale_threshold_seconds=1.0)


@pytest.fixture
def sample_event():
    """Create a sample input event."""
    return InputEvent(
        type=EventType.TEXT_INPUT,
        payload="Hello Luna",
        source="test",
    )


@pytest.fixture
def interrupt_event():
    """Create an interrupt event."""
    return InputEvent(
        type=EventType.USER_INTERRUPT,
        payload="stop",
        source="test",
    )


class MockActor(Actor):
    """Mock actor for testing."""

    def __init__(self, name: str = "mock"):
        super().__init__(name)
        self.received_messages = []
        self.handle_delay = 0

    async def handle(self, msg: Message) -> None:
        """Record received messages."""
        self.received_messages.append(msg)
        if self.handle_delay > 0:
            await asyncio.sleep(self.handle_delay)


@pytest.fixture
def mock_actor():
    """Create a mock actor for testing."""
    return MockActor("test_actor")
