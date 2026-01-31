"""
Unit Tests for InputBuffer
==========================

Tests for thread-safe event buffering including enqueue, dequeue,
priority ordering, overflow handling, and stale event dropping.

No external dependencies - pure async queue testing.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from luna.core.input_buffer import InputBuffer
from luna.core.events import InputEvent, EventType, EventPriority


# =============================================================================
# ENQUEUE TESTS
# =============================================================================

class TestInputBufferEnqueue:
    """Tests for event enqueue operations."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_enqueues_event(self):
        """Test InputBuffer enqueues events correctly."""
        buffer = InputBuffer(max_size=10)

        event = InputEvent(
            type=EventType.TEXT_INPUT,
            payload="Hello Luna",
            source="test",
        )

        result = await buffer.put(event)

        assert result is True
        assert buffer.size == 1
        assert buffer._total_received == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_enqueues_multiple_events(self):
        """Test InputBuffer handles multiple events."""
        buffer = InputBuffer(max_size=10)

        for i in range(5):
            event = InputEvent(
                type=EventType.TEXT_INPUT,
                payload=f"Message {i}",
                source="test",
            )
            await buffer.put(event)

        assert buffer.size == 5
        assert buffer._total_received == 5

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_tracks_received_count(self):
        """Test InputBuffer tracks total received events."""
        buffer = InputBuffer(max_size=10)

        for _ in range(3):
            await buffer.put(InputEvent(
                type=EventType.TEXT_INPUT,
                payload="test",
            ))

        assert buffer._total_received == 3
        assert buffer.stats["total_received"] == 3


# =============================================================================
# DEQUEUE TESTS
# =============================================================================

class TestInputBufferDequeue:
    """Tests for event dequeue operations."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_dequeues_by_priority(self):
        """Test InputBuffer dequeues events sorted by priority."""
        buffer = InputBuffer(max_size=10)

        # Add events in non-priority order
        await buffer.put(InputEvent(
            type=EventType.TEXT_INPUT,  # FINAL priority
            payload="normal message",
        ))
        await buffer.put(InputEvent(
            type=EventType.USER_INTERRUPT,  # INTERRUPT priority
            payload="urgent!",
        ))
        await buffer.put(InputEvent(
            type=EventType.MCP_REQUEST,  # MCP priority
            payload="api call",
        ))

        events = buffer.poll_all()

        # Should be sorted by priority (INTERRUPT first)
        assert len(events) == 3
        assert events[0].priority == EventPriority.INTERRUPT
        assert events[0].payload == "urgent!"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_poll_all_empties_queue(self):
        """Test poll_all empties the buffer."""
        buffer = InputBuffer(max_size=10)

        await buffer.put(InputEvent(type=EventType.TEXT_INPUT, payload="1"))
        await buffer.put(InputEvent(type=EventType.TEXT_INPUT, payload="2"))

        events = buffer.poll_all()

        assert len(events) == 2
        assert buffer.is_empty
        assert buffer.size == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_poll_all_empty_returns_empty_list(self):
        """Test poll_all on empty buffer returns empty list."""
        buffer = InputBuffer(max_size=10)

        events = buffer.poll_all()

        assert events == []


# =============================================================================
# PRIORITY ORDERING TESTS
# =============================================================================

class TestInputBufferPriority:
    """Tests for priority-based ordering."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_priority_order_correct(self):
        """Test events are ordered by priority then timestamp."""
        buffer = InputBuffer(max_size=10)

        # Create events with different priorities
        interrupt_event = InputEvent(
            type=EventType.USER_INTERRUPT,
            payload="interrupt",
            priority=EventPriority.INTERRUPT,
        )
        final_event = InputEvent(
            type=EventType.TEXT_INPUT,
            payload="final",
            priority=EventPriority.FINAL,
        )
        mcp_event = InputEvent(
            type=EventType.MCP_REQUEST,
            payload="mcp",
            priority=EventPriority.MCP,
        )

        # Add in reverse order
        await buffer.put(mcp_event)
        await buffer.put(final_event)
        await buffer.put(interrupt_event)

        events = buffer.poll_all()

        # Should be: INTERRUPT (0) -> FINAL (1) -> MCP (3)
        assert events[0].priority == EventPriority.INTERRUPT
        assert events[1].priority == EventPriority.FINAL
        assert events[2].priority == EventPriority.MCP

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_same_priority_ordered_by_timestamp(self):
        """Test same-priority events are ordered by timestamp."""
        buffer = InputBuffer(max_size=10)

        # Create events with same priority but different times
        event1 = InputEvent(
            type=EventType.TEXT_INPUT,
            payload="first",
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
        )
        event2 = InputEvent(
            type=EventType.TEXT_INPUT,
            payload="second",
            timestamp=datetime(2024, 1, 1, 10, 0, 1),
        )

        await buffer.put(event2)  # Add newer first
        await buffer.put(event1)  # Add older second

        events = buffer.poll_all()

        # Should be ordered by timestamp (older first)
        assert events[0].payload == "first"
        assert events[1].payload == "second"


# =============================================================================
# OVERFLOW HANDLING TESTS
# =============================================================================

class TestInputBufferOverflow:
    """Tests for buffer overflow handling."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_handles_overflow(self):
        """Test InputBuffer drops events when full."""
        buffer = InputBuffer(max_size=3)

        # Fill buffer
        for i in range(3):
            result = await buffer.put(InputEvent(
                type=EventType.TEXT_INPUT,
                payload=f"msg {i}",
            ))
            assert result is True

        # Try to add one more
        result = await buffer.put(InputEvent(
            type=EventType.TEXT_INPUT,
            payload="overflow",
        ))

        assert result is False
        assert buffer.size == 3
        assert buffer._dropped_count == 1

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_overflow_stats(self):
        """Test buffer tracks dropped event count."""
        buffer = InputBuffer(max_size=2)

        await buffer.put(InputEvent(type=EventType.TEXT_INPUT, payload="1"))
        await buffer.put(InputEvent(type=EventType.TEXT_INPUT, payload="2"))
        await buffer.put(InputEvent(type=EventType.TEXT_INPUT, payload="3"))  # Dropped
        await buffer.put(InputEvent(type=EventType.TEXT_INPUT, payload="4"))  # Dropped

        stats = buffer.stats

        assert stats["size"] == 2
        assert stats["total_received"] == 4
        assert stats["dropped_count"] == 2


# =============================================================================
# THREAD SAFETY TESTS
# =============================================================================

class TestInputBufferThreadSafety:
    """Tests for concurrent access safety."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_thread_safety(self):
        """Test InputBuffer handles concurrent access."""
        buffer = InputBuffer(max_size=100)

        async def producer(start_id: int):
            for i in range(10):
                await buffer.put(InputEvent(
                    type=EventType.TEXT_INPUT,
                    payload=f"msg-{start_id}-{i}",
                ))

        # Run multiple producers concurrently
        await asyncio.gather(
            producer(0),
            producer(1),
            producer(2),
        )

        # All events should be received
        events = buffer.poll_all()
        assert len(events) == 30

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_concurrent_read_write(self):
        """Test concurrent reading and writing."""
        buffer = InputBuffer(max_size=50)
        collected = []

        async def writer():
            for i in range(20):
                await buffer.put(InputEvent(
                    type=EventType.TEXT_INPUT,
                    payload=f"msg-{i}",
                ))
                await asyncio.sleep(0.001)  # Small delay

        async def reader():
            for _ in range(10):
                events = buffer.poll_all()
                collected.extend(events)
                await asyncio.sleep(0.002)

        await asyncio.gather(writer(), reader())

        # Collect remaining
        collected.extend(buffer.poll_all())

        # All 20 events should be accounted for
        assert len(collected) == 20


# =============================================================================
# STALE EVENT TESTS
# =============================================================================

class TestInputBufferStaleEvents:
    """Tests for stale event handling."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_drops_stale_events(self):
        """Test InputBuffer drops stale events with poll_fresh."""
        buffer = InputBuffer(max_size=10, stale_threshold_seconds=0.1)

        # Add old event
        old_event = InputEvent(
            type=EventType.TEXT_INPUT,
            payload="old",
            timestamp=datetime.now() - timedelta(seconds=1),
        )
        await buffer.put(old_event)

        # Add fresh event
        fresh_event = InputEvent(
            type=EventType.TEXT_INPUT,
            payload="fresh",
        )
        await buffer.put(fresh_event)

        events = buffer.poll_fresh()

        # Only fresh event should remain
        assert len(events) == 1
        assert events[0].payload == "fresh"

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_stale_threshold_custom(self):
        """Test custom stale threshold."""
        buffer = InputBuffer(max_size=10, stale_threshold_seconds=5.0)

        # Event 3 seconds old should not be stale (threshold is 5s)
        event = InputEvent(
            type=EventType.TEXT_INPUT,
            payload="recent",
            timestamp=datetime.now() - timedelta(seconds=3),
        )
        await buffer.put(event)

        events = buffer.poll_fresh()

        assert len(events) == 1


# =============================================================================
# INTERRUPT DETECTION TESTS
# =============================================================================

class TestInputBufferInterrupt:
    """Tests for interrupt detection."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_detects_interrupt(self):
        """Test InputBuffer detects pending interrupt."""
        buffer = InputBuffer(max_size=10)

        await buffer.put(InputEvent(
            type=EventType.TEXT_INPUT,
            payload="normal",
        ))
        await buffer.put(InputEvent(
            type=EventType.USER_INTERRUPT,
            payload="stop!",
        ))

        assert buffer.has_interrupt() is True

        # Events should still be in queue (peek, not consume)
        assert buffer.size == 2

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_no_interrupt(self):
        """Test InputBuffer returns False when no interrupt."""
        buffer = InputBuffer(max_size=10)

        await buffer.put(InputEvent(
            type=EventType.TEXT_INPUT,
            payload="normal",
        ))

        assert buffer.has_interrupt() is False

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_has_interrupt_preserves_events(self):
        """Test has_interrupt doesn't consume events."""
        buffer = InputBuffer(max_size=10)

        await buffer.put(InputEvent(
            type=EventType.USER_INTERRUPT,
            payload="stop",
        ))

        # Check multiple times
        assert buffer.has_interrupt() is True
        assert buffer.has_interrupt() is True

        # Events still there
        assert buffer.size == 1


# =============================================================================
# CLEAR TESTS
# =============================================================================

class TestInputBufferClear:
    """Tests for buffer clearing."""

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_clear(self):
        """Test InputBuffer clear removes all events."""
        buffer = InputBuffer(max_size=10)

        for i in range(5):
            await buffer.put(InputEvent(
                type=EventType.TEXT_INPUT,
                payload=f"msg-{i}",
            ))

        count = buffer.clear()

        assert count == 5
        assert buffer.is_empty
        assert buffer.size == 0

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_clear_empty(self):
        """Test clearing empty buffer returns 0."""
        buffer = InputBuffer(max_size=10)

        count = buffer.clear()

        assert count == 0


# =============================================================================
# STATS TESTS
# =============================================================================

class TestInputBufferStats:
    """Tests for buffer statistics."""

    @pytest.mark.unit
    def test_buffer_stats_structure(self):
        """Test buffer stats has expected structure."""
        buffer = InputBuffer(max_size=10)

        stats = buffer.stats

        assert "size" in stats
        assert "total_received" in stats
        assert "dropped_count" in stats

    @pytest.mark.unit
    @pytest.mark.asyncio
    async def test_buffer_stats_accurate(self):
        """Test buffer stats are accurate."""
        buffer = InputBuffer(max_size=3)

        await buffer.put(InputEvent(type=EventType.TEXT_INPUT, payload="1"))
        await buffer.put(InputEvent(type=EventType.TEXT_INPUT, payload="2"))
        await buffer.put(InputEvent(type=EventType.TEXT_INPUT, payload="3"))
        await buffer.put(InputEvent(type=EventType.TEXT_INPUT, payload="4"))  # Dropped

        stats = buffer.stats

        assert stats["size"] == 3
        assert stats["total_received"] == 4
        assert stats["dropped_count"] == 1
