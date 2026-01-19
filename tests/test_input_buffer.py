"""
Tests for InputBuffer
=====================

Tests for priority ordering, stale detection, and buffer management.
"""

import asyncio
import pytest
from datetime import datetime, timedelta

from luna.core.input_buffer import InputBuffer
from luna.core.events import InputEvent, EventType, EventPriority


class TestInputBuffer:
    """Tests for InputBuffer class."""

    @pytest.mark.asyncio
    async def test_put_and_poll_single_event(self, input_buffer, sample_event):
        """Test basic put and poll."""
        await input_buffer.put(sample_event)

        assert input_buffer.size == 1
        events = input_buffer.poll_all()

        assert len(events) == 1
        assert events[0] == sample_event
        assert input_buffer.is_empty

    @pytest.mark.asyncio
    async def test_poll_empty_buffer(self, input_buffer):
        """Test polling empty buffer returns empty list."""
        events = input_buffer.poll_all()
        assert events == []

    @pytest.mark.asyncio
    async def test_priority_ordering(self, input_buffer):
        """Test events are sorted by priority."""
        # Add events in non-priority order
        low_priority = InputEvent(EventType.MCP_REQUEST, "low", priority=EventPriority.MCP)
        high_priority = InputEvent(EventType.USER_INTERRUPT, "high", priority=EventPriority.INTERRUPT)
        medium_priority = InputEvent(EventType.TEXT_INPUT, "medium", priority=EventPriority.FINAL)

        await input_buffer.put(low_priority)
        await input_buffer.put(high_priority)
        await input_buffer.put(medium_priority)

        events = input_buffer.poll_all()

        assert len(events) == 3
        # Should be sorted: INTERRUPT (0) -> FINAL (1) -> MCP (3)
        assert events[0].priority == EventPriority.INTERRUPT
        assert events[1].priority == EventPriority.FINAL
        assert events[2].priority == EventPriority.MCP

    @pytest.mark.asyncio
    async def test_timestamp_ordering_same_priority(self, input_buffer):
        """Test events with same priority are sorted by timestamp."""
        older = InputEvent(EventType.TEXT_INPUT, "older")
        older.timestamp = datetime.now() - timedelta(seconds=1)

        newer = InputEvent(EventType.TEXT_INPUT, "newer")

        await input_buffer.put(newer)
        await input_buffer.put(older)

        events = input_buffer.poll_all()

        assert len(events) == 2
        assert events[0].payload == "older"
        assert events[1].payload == "newer"

    @pytest.mark.asyncio
    async def test_max_size_limit(self):
        """Test buffer respects max size."""
        buffer = InputBuffer(max_size=2)

        e1 = InputEvent(EventType.TEXT_INPUT, "1")
        e2 = InputEvent(EventType.TEXT_INPUT, "2")
        e3 = InputEvent(EventType.TEXT_INPUT, "3")

        assert await buffer.put(e1) is True
        assert await buffer.put(e2) is True
        assert await buffer.put(e3) is False  # Should fail

        assert buffer.size == 2
        assert buffer.stats["dropped_count"] == 1

    @pytest.mark.asyncio
    async def test_poll_fresh_drops_stale(self):
        """Test poll_fresh discards stale events."""
        buffer = InputBuffer(stale_threshold_seconds=0.5)

        stale = InputEvent(EventType.TEXT_INPUT, "stale")
        stale.timestamp = datetime.now() - timedelta(seconds=1)

        fresh = InputEvent(EventType.TEXT_INPUT, "fresh")

        await buffer.put(stale)
        await buffer.put(fresh)

        events = buffer.poll_fresh()

        assert len(events) == 1
        assert events[0].payload == "fresh"

    @pytest.mark.asyncio
    async def test_has_interrupt_detection(self, input_buffer, interrupt_event):
        """Test interrupt detection without consuming events."""
        normal = InputEvent(EventType.TEXT_INPUT, "normal")

        await input_buffer.put(normal)
        assert input_buffer.has_interrupt() is False

        await input_buffer.put(interrupt_event)
        assert input_buffer.has_interrupt() is True

        # Events should still be in buffer
        assert input_buffer.size == 2

    @pytest.mark.asyncio
    async def test_clear_removes_all(self, input_buffer):
        """Test clear removes all events."""
        for i in range(5):
            await input_buffer.put(InputEvent(EventType.TEXT_INPUT, f"event_{i}"))

        assert input_buffer.size == 5

        cleared = input_buffer.clear()

        assert cleared == 5
        assert input_buffer.is_empty

    @pytest.mark.asyncio
    async def test_stats_tracking(self, input_buffer):
        """Test statistics are tracked correctly."""
        for i in range(3):
            await input_buffer.put(InputEvent(EventType.TEXT_INPUT, f"event_{i}"))

        stats = input_buffer.stats

        assert stats["total_received"] == 3
        assert stats["size"] == 3
        assert stats["dropped_count"] == 0


class TestEventPriorityInference:
    """Tests for automatic priority inference from event type."""

    def test_interrupt_priority(self):
        """USER_INTERRUPT should be INTERRUPT priority."""
        event = InputEvent(EventType.USER_INTERRUPT, "stop")
        assert event.priority == EventPriority.INTERRUPT

    def test_final_transcript_priority(self):
        """TRANSCRIPT_FINAL should be FINAL priority."""
        event = InputEvent(EventType.TRANSCRIPT_FINAL, "hello")
        assert event.priority == EventPriority.FINAL

    def test_text_input_priority(self):
        """TEXT_INPUT should be FINAL priority."""
        event = InputEvent(EventType.TEXT_INPUT, "hello")
        assert event.priority == EventPriority.FINAL

    def test_partial_transcript_priority(self):
        """TRANSCRIPT_PARTIAL should be PARTIAL priority."""
        event = InputEvent(EventType.TRANSCRIPT_PARTIAL, "hel...")
        assert event.priority == EventPriority.PARTIAL

    def test_mcp_request_priority(self):
        """MCP_REQUEST should be MCP priority."""
        event = InputEvent(EventType.MCP_REQUEST, {"tool": "test"})
        assert event.priority == EventPriority.MCP

    def test_explicit_priority_override(self):
        """Explicit priority should override inference."""
        event = InputEvent(
            EventType.TEXT_INPUT,
            "hello",
            priority=EventPriority.INTERRUPT
        )
        assert event.priority == EventPriority.INTERRUPT
