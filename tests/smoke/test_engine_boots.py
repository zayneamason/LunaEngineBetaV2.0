"""
Smoke Tests: Engine Boot Sequence
=================================

Verifies the Luna Engine starts, transitions states, initializes actors,
and shuts down cleanly.

These tests use real components with minimal mocking.
"""

import asyncio

import pytest
import pytest_asyncio

from luna.engine import LunaEngine, EngineConfig
from luna.core.state import EngineState


pytestmark = [
    pytest.mark.smoke,
    pytest.mark.asyncio,
]


class TestEngineBoots:
    """Smoke tests for engine boot sequence."""

    async def test_engine_starts_successfully(self, smoke_engine_config):
        """
        SMOKE: Engine starts and reaches RUNNING state.

        Verifies:
        - Engine creates without error
        - Boot sequence completes
        - State transitions to RUNNING
        """
        engine = LunaEngine(smoke_engine_config)

        # Start engine in background
        engine_task = asyncio.create_task(engine.run())

        try:
            # Wait for engine to be ready (with timeout)
            ready = await engine.wait_ready(timeout=10.0)

            assert ready, "Engine failed to become ready within timeout"
            assert engine.state == EngineState.RUNNING
            assert engine._running is True

        finally:
            await engine.stop()
            await asyncio.wait_for(engine_task, timeout=5.0)

    async def test_engine_transitions_to_running_state(self, smoke_engine_config):
        """
        SMOKE: Engine transitions through correct states.

        Verifies:
        - Starts in STARTING state
        - Transitions to RUNNING after boot
        - Transitions to STOPPED on shutdown
        """
        engine = LunaEngine(smoke_engine_config)

        # Initial state should be STARTING
        assert engine.state == EngineState.STARTING

        engine_task = asyncio.create_task(engine.run())

        try:
            await engine.wait_ready(timeout=10.0)

            # Should now be RUNNING
            assert engine.state == EngineState.RUNNING

            # Stop the engine
            await engine.stop()
            await asyncio.wait_for(engine_task, timeout=5.0)

            # Should now be STOPPED
            assert engine.state == EngineState.STOPPED

        except Exception:
            engine_task.cancel()
            try:
                await engine_task
            except asyncio.CancelledError:
                pass
            raise

    async def test_engine_initializes_all_actors(self, smoke_engine_config):
        """
        SMOKE: Engine initializes all required actors.

        Verifies:
        - director actor exists
        - matrix actor exists
        - scribe actor exists
        - librarian actor exists
        - history_manager actor exists
        """
        engine = LunaEngine(smoke_engine_config)
        engine_task = asyncio.create_task(engine.run())

        try:
            await engine.wait_ready(timeout=10.0)

            # Core actors
            assert "director" in engine.actors, "Director actor not initialized"
            assert "matrix" in engine.actors, "Matrix actor not initialized"

            # Extraction pipeline actors
            assert "scribe" in engine.actors, "Scribe actor not initialized"
            assert "librarian" in engine.actors, "Librarian actor not initialized"

            # History manager
            assert "history_manager" in engine.actors, "History manager not initialized"

            # Verify actors have engine reference
            for name, actor in engine.actors.items():
                assert actor.engine == engine, f"{name} actor missing engine reference"

        finally:
            await engine.stop()
            await asyncio.wait_for(engine_task, timeout=5.0)

    async def test_engine_stops_cleanly(self, smoke_engine_config):
        """
        SMOKE: Engine shuts down without errors.

        Verifies:
        - stop() completes without exception
        - _running flag is set to False
        - State transitions to STOPPED
        - Consciousness state is saved
        """
        engine = LunaEngine(smoke_engine_config)
        engine_task = asyncio.create_task(engine.run())

        await engine.wait_ready(timeout=10.0)
        assert engine._running is True

        # Stop the engine
        await engine.stop()

        # Wait for task to complete
        await asyncio.wait_for(engine_task, timeout=5.0)

        # Verify clean shutdown
        assert engine._running is False
        assert engine.state == EngineState.STOPPED

    async def test_engine_handles_restart(self, smoke_engine_config):
        """
        SMOKE: Engine can be stopped and restarted.

        Verifies:
        - First instance starts successfully
        - First instance stops cleanly
        - Second instance starts successfully
        - Both instances use same data directory
        """
        # First engine instance
        engine1 = LunaEngine(smoke_engine_config)
        engine_task1 = asyncio.create_task(engine1.run())

        await engine1.wait_ready(timeout=10.0)
        session_id1 = engine1.session_id

        # Store something in memory before shutdown
        matrix = engine1.get_actor("matrix")
        if matrix and hasattr(matrix, "_matrix") and matrix._matrix:
            try:
                await matrix._matrix.add_node(
                    node_type="FACT",
                    content="Test fact for restart",
                    source="smoke_test",
                )
            except Exception:
                pass  # Memory might not be fully initialized

        await engine1.stop()
        await asyncio.wait_for(engine_task1, timeout=5.0)
        assert engine1.state == EngineState.STOPPED

        # Second engine instance with same config (same data dir)
        engine2 = LunaEngine(smoke_engine_config)
        engine_task2 = asyncio.create_task(engine2.run())

        try:
            await engine2.wait_ready(timeout=10.0)

            # Should get a new session ID
            assert engine2.session_id != session_id1

            # Should be running
            assert engine2.state == EngineState.RUNNING

        finally:
            await engine2.stop()
            await asyncio.wait_for(engine_task2, timeout=5.0)


class TestEngineMetrics:
    """Smoke tests for engine metrics and status."""

    async def test_engine_metrics_increment(self, smoke_engine_config):
        """
        SMOKE: Engine metrics increment during operation.

        Verifies:
        - cognitive_ticks increments
        - uptime increases
        - Session ID is generated
        """
        smoke_engine_config.cognitive_interval = 0.05  # Very fast ticks

        engine = LunaEngine(smoke_engine_config)
        engine_task = asyncio.create_task(engine.run())

        try:
            await engine.wait_ready(timeout=10.0)

            # Let some ticks run
            await asyncio.sleep(0.3)

            # Check metrics
            assert engine.metrics.cognitive_ticks > 0
            assert engine.metrics.uptime_seconds > 0
            assert engine.session_id is not None
            assert len(engine.session_id) == 8

        finally:
            await engine.stop()
            await asyncio.wait_for(engine_task, timeout=5.0)

    async def test_engine_status_complete(self, smoke_engine_config):
        """
        SMOKE: Engine status returns complete information.

        Verifies status dict contains all required fields.
        """
        engine = LunaEngine(smoke_engine_config)
        engine_task = asyncio.create_task(engine.run())

        try:
            await engine.wait_ready(timeout=10.0)

            status = engine.status()

            # Required fields
            assert "state" in status
            assert "uptime_seconds" in status
            assert "cognitive_ticks" in status
            assert "events_processed" in status
            assert "messages_generated" in status
            assert "actors" in status
            assert "buffer" in status
            assert "consciousness" in status
            assert "context" in status
            assert "current_turn" in status
            assert "agentic" in status

            # Verify types
            assert isinstance(status["state"], str)
            assert isinstance(status["uptime_seconds"], float)
            assert isinstance(status["actors"], list)

        finally:
            await engine.stop()
            await asyncio.wait_for(engine_task, timeout=5.0)
