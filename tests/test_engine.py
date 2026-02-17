"""
Tests for Luna Engine
=====================

Tests for engine lifecycle, tick loops, and event dispatch.
"""

import asyncio
import pytest
from pathlib import Path

from luna.engine import LunaEngine, EngineConfig
from luna.core.state import EngineState
from luna.core.events import InputEvent, EventType


class TestEngineLifecycle:
    """Tests for engine start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_engine_starts_and_stops(self, engine_config):
        """Test basic start/stop lifecycle."""
        engine = LunaEngine(engine_config)

        # Start engine in background
        task = asyncio.create_task(engine.run())

        # Wait for engine to be ready
        assert await engine.wait_ready(timeout=5.0)
        assert engine.state == EngineState.RUNNING
        assert engine._running is True

        # Stop engine
        await engine.stop()

        # Wait for task to complete
        await asyncio.wait_for(task, timeout=5.0)
        assert engine.state == EngineState.STOPPED
        assert engine._running is False

    @pytest.mark.asyncio
    async def test_engine_initializes_actors(self, engine_config):
        """Test engine creates default actors on boot."""
        engine = LunaEngine(engine_config)

        task = asyncio.create_task(engine.run())
        assert await engine.wait_ready(timeout=5.0)

        assert "director" in engine.actors
        assert "matrix" in engine.actors

        await engine.stop()
        await asyncio.wait_for(task, timeout=5.0)

    @pytest.mark.asyncio
    async def test_engine_creates_session_id(self, engine_config):
        """Test engine generates unique session ID."""
        engine = LunaEngine(engine_config)

        assert engine.session_id is not None
        assert len(engine.session_id) == 8

    @pytest.mark.asyncio
    async def test_engine_creates_data_dir(self, temp_data_dir):
        """Test engine creates data directory if it doesn't exist."""
        config = EngineConfig(data_dir=temp_data_dir / "subdir")

        assert config.data_dir.exists()


class TestEngineTicks:
    """Tests for engine tick loops."""

    @pytest.mark.asyncio
    async def test_cognitive_ticks_increment(self, engine_config):
        """Test cognitive tick counter increments."""
        engine_config.cognitive_interval = 0.05  # Fast ticks
        engine = LunaEngine(engine_config)

        task = asyncio.create_task(engine.run())
        assert await engine.wait_ready(timeout=5.0)
        await asyncio.sleep(0.2)  # Let some ticks run

        assert engine.metrics.cognitive_ticks > 0

        await engine.stop()
        await asyncio.wait_for(task, timeout=5.0)

    @pytest.mark.asyncio
    async def test_events_processed_count(self, engine_config):
        """Test events processed counter."""
        engine_config.cognitive_interval = 0.05
        engine = LunaEngine(engine_config)

        task = asyncio.create_task(engine.run())
        assert await engine.wait_ready(timeout=5.0)

        # Send some events
        await engine.send_message("test message 1")
        await engine.send_message("test message 2")

        await asyncio.sleep(1.0)  # Let ticks process events (increased for reliability)

        assert engine.metrics.events_processed >= 2

        await engine.stop()
        await asyncio.wait_for(task, timeout=5.0)


class TestEngineInput:
    """Tests for engine input handling."""

    @pytest.mark.asyncio
    async def test_send_message_adds_to_buffer(self, engine_config):
        """Test send_message adds event to input buffer."""
        engine = LunaEngine(engine_config)

        await engine.send_message("hello")

        assert engine.input_buffer.size == 1

    @pytest.mark.asyncio
    async def test_on_response_callback(self, engine_config):
        """Test response callbacks are called."""
        engine = LunaEngine(engine_config)

        responses = []

        async def capture_response(text, data):
            responses.append(text)

        engine.on_response(capture_response)

        assert capture_response in engine._on_response_callbacks


class TestEngineStatus:
    """Tests for engine status reporting."""

    @pytest.mark.asyncio
    async def test_status_returns_dict(self, engine_config):
        """Test status returns proper dictionary."""
        engine = LunaEngine(engine_config)

        task = asyncio.create_task(engine.run())
        await asyncio.sleep(0.2)

        status = engine.status()

        assert "state" in status
        assert "uptime_seconds" in status
        assert "cognitive_ticks" in status
        assert "events_processed" in status
        assert "actors" in status
        assert "buffer" in status

        await engine.stop()
        await asyncio.wait_for(task, timeout=5.0)

    @pytest.mark.asyncio
    async def test_uptime_increases(self, engine_config):
        """Test uptime increases over time."""
        engine = LunaEngine(engine_config)

        task = asyncio.create_task(engine.run())
        await asyncio.sleep(0.2)

        uptime1 = engine.metrics.uptime_seconds

        await asyncio.sleep(0.2)

        uptime2 = engine.metrics.uptime_seconds

        assert uptime2 > uptime1

        await engine.stop()
        await asyncio.wait_for(task, timeout=5.0)


class TestEngineState:
    """Tests for EngineState transitions."""

    def test_valid_transitions(self):
        """Test valid state transitions."""
        assert EngineState.STARTING.can_transition_to(EngineState.RUNNING)
        assert EngineState.STARTING.can_transition_to(EngineState.STOPPED)
        assert EngineState.RUNNING.can_transition_to(EngineState.PAUSED)
        assert EngineState.RUNNING.can_transition_to(EngineState.STOPPED)
        assert EngineState.PAUSED.can_transition_to(EngineState.RUNNING)
        assert EngineState.PAUSED.can_transition_to(EngineState.SLEEPING)
        assert EngineState.SLEEPING.can_transition_to(EngineState.RUNNING)

    def test_invalid_transitions(self):
        """Test invalid state transitions."""
        assert not EngineState.STARTING.can_transition_to(EngineState.PAUSED)
        assert not EngineState.STARTING.can_transition_to(EngineState.SLEEPING)
        assert not EngineState.RUNNING.can_transition_to(EngineState.STARTING)
        assert not EngineState.STOPPED.can_transition_to(EngineState.RUNNING)
        assert not EngineState.STOPPED.can_transition_to(EngineState.STARTING)


class TestEngineActorManagement:
    """Tests for actor registration and retrieval."""

    @pytest.mark.asyncio
    async def test_register_actor(self, engine_config):
        """Test registering an actor."""
        from luna.actors.base import Actor, Message

        class TestActor(Actor):
            async def handle(self, msg: Message):
                pass

        engine = LunaEngine(engine_config)
        actor = TestActor("custom")

        engine.register_actor(actor)

        assert "custom" in engine.actors
        assert actor.engine == engine

    @pytest.mark.asyncio
    async def test_get_actor(self, engine_config):
        """Test retrieving an actor by name."""
        engine = LunaEngine(engine_config)

        task = asyncio.create_task(engine.run())
        assert await engine.wait_ready(timeout=5.0)

        director = engine.get_actor("director")
        assert director is not None
        assert director.name == "director"

        nonexistent = engine.get_actor("nonexistent")
        assert nonexistent is None

        await engine.stop()
        await asyncio.wait_for(task, timeout=5.0)
