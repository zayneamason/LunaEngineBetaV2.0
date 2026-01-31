"""
Tracer-specific fixtures for Luna Engine end-to-end tests.

Provides tracing infrastructure for debugging and performance analysis.
"""

import asyncio
import pytest
import time
from dataclasses import dataclass, field
from typing import List, Any, Optional, Callable
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch


@dataclass
class TraceEvent:
    """A single event in a trace timeline."""
    timestamp: float
    event_type: str
    data: Any = None
    duration_ms: Optional[float] = None


@dataclass
class TraceCollector:
    """
    Collects trace events during test execution.

    Provides utilities for recording, analyzing, and asserting
    on event sequences and timing.
    """
    events: List[TraceEvent] = field(default_factory=list)
    _start_time: Optional[float] = None

    def start(self) -> None:
        """Mark the start of tracing."""
        self._start_time = time.time()
        self.record("trace_start")

    def record(self, event_type: str, data: Any = None) -> None:
        """Record an event in the trace."""
        self.events.append(TraceEvent(
            timestamp=time.time(),
            event_type=event_type,
            data=data,
        ))

    def record_with_duration(self, event_type: str, start_time: float, data: Any = None) -> None:
        """Record an event with its duration."""
        now = time.time()
        self.events.append(TraceEvent(
            timestamp=now,
            event_type=event_type,
            data=data,
            duration_ms=(now - start_time) * 1000,
        ))

    def get_sequence(self) -> List[str]:
        """Get the sequence of event types."""
        return [e.event_type for e in self.events]

    def get_events_by_type(self, event_type: str) -> List[TraceEvent]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.event_type == event_type]

    def total_time(self) -> float:
        """Get total elapsed time in seconds."""
        if len(self.events) < 2:
            return 0
        return self.events[-1].timestamp - self.events[0].timestamp

    def total_time_ms(self) -> float:
        """Get total elapsed time in milliseconds."""
        return self.total_time() * 1000

    def get_timing_breakdown(self) -> dict:
        """
        Get timing breakdown by event type.

        Returns dict of event_type -> total_duration_ms
        """
        breakdown = {}
        for event in self.events:
            if event.duration_ms is not None:
                if event.event_type not in breakdown:
                    breakdown[event.event_type] = 0
                breakdown[event.event_type] += event.duration_ms
        return breakdown

    def find_event(self, event_type: str) -> Optional[TraceEvent]:
        """Find the first event of a given type."""
        for e in self.events:
            if e.event_type == event_type:
                return e
        return None

    def contains_sequence(self, expected: List[str]) -> bool:
        """Check if trace contains expected sequence in order."""
        sequence = self.get_sequence()
        idx = 0
        for event in sequence:
            if idx < len(expected) and event == expected[idx]:
                idx += 1
        return idx == len(expected)

    def assert_sequence_contains(self, expected: List[str]) -> None:
        """Assert that trace contains expected sequence in order."""
        if not self.contains_sequence(expected):
            raise AssertionError(
                f"Trace does not contain expected sequence.\n"
                f"Expected: {expected}\n"
                f"Actual: {self.get_sequence()}"
            )

    def dump(self) -> str:
        """Dump trace to string for debugging."""
        lines = ["Trace Dump:"]
        base_time = self.events[0].timestamp if self.events else 0
        for e in self.events:
            relative_ms = (e.timestamp - base_time) * 1000
            duration_str = f" ({e.duration_ms:.2f}ms)" if e.duration_ms else ""
            data_str = f" data={e.data}" if e.data else ""
            lines.append(f"  +{relative_ms:.2f}ms: {e.event_type}{duration_str}{data_str}")
        return "\n".join(lines)


@pytest.fixture
def trace_collector():
    """Create a fresh trace collector for a test."""
    collector = TraceCollector()
    collector.start()
    return collector


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for tracer tests."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "test_tracer.db"


@pytest.fixture
def mock_anthropic_client():
    """
    Create a mock Anthropic client for tracing LLM calls.

    Returns a mock that simulates streaming token generation.
    """
    mock_client = MagicMock()

    # Mock streaming response
    mock_stream = MagicMock()
    mock_stream.__enter__ = MagicMock(return_value=mock_stream)
    mock_stream.__exit__ = MagicMock(return_value=False)

    # Simulate text blocks
    mock_block = MagicMock()
    mock_block.text = "Test response from Luna"
    mock_stream.content = [mock_block]
    mock_stream.input_tokens = 100
    mock_stream.output_tokens = 20

    mock_client.messages.create = MagicMock(return_value=mock_stream)

    return mock_client


@pytest.fixture
def mock_local_inference():
    """
    Create a mock local inference engine for tracing.

    Simulates Qwen local model responses.
    """
    mock = AsyncMock()
    mock.generate = AsyncMock(return_value={
        "text": "Local model test response",
        "tokens_used": 50,
        "latency_ms": 100,
    })
    mock.is_loaded = True
    return mock


@pytest.fixture
async def mock_memory_matrix(temp_db_path):
    """
    Create a mock memory matrix for tracer tests.

    Uses an in-memory implementation that tracks calls.
    """
    from unittest.mock import MagicMock, AsyncMock

    mock = MagicMock()
    mock.is_ready = True
    mock._initialized = True

    # Store call history for tracing
    mock._call_history = []

    async def mock_search(query, limit=10, use_hybrid=True):
        mock._call_history.append(("search", query, limit))
        return []

    async def mock_get_context(query, max_tokens=3800, budget_preset="balanced"):
        mock._call_history.append(("get_context", query, max_tokens))
        return "Mock context for: " + query

    async def mock_store_memory(content, node_type="FACT", **kwargs):
        mock._call_history.append(("store_memory", content, node_type))
        return "mock-node-id"

    async def mock_store_turn(session_id, role, content, tokens=None):
        mock._call_history.append(("store_turn", session_id, role, content))
        return "mock-turn-id"

    async def mock_reinforce_memory(node_id, amount=1):
        mock._call_history.append(("reinforce_memory", node_id, amount))

    async def mock_get_stats():
        return {
            "total_nodes": 100,
            "node_types": {"FACT": 50, "DECISION": 30, "PROBLEM": 20},
            "initialized": True,
        }

    mock.search = mock_search
    mock.get_context = mock_get_context
    mock.store_memory = mock_store_memory
    mock.store_turn = mock_store_turn
    mock.reinforce_memory = mock_reinforce_memory
    mock.get_stats = mock_get_stats
    mock.get_recent_turns = AsyncMock(return_value=[])

    return mock


@pytest.fixture
def traced_function_factory(trace_collector):
    """
    Factory for creating traced async functions.

    Wraps any async function to record start/end/error events.
    """
    def create_traced(name: str, func: Callable):
        async def traced(*args, **kwargs):
            start = time.time()
            trace_collector.record(f"{name}_start", {"args": args, "kwargs": kwargs})
            try:
                result = await func(*args, **kwargs)
                trace_collector.record_with_duration(f"{name}_end", start, {"result": result})
                return result
            except Exception as e:
                trace_collector.record_with_duration(f"{name}_error", start, {"error": str(e)})
                raise
        return traced
    return create_traced


class MockSSEClient:
    """Mock SSE client for testing streaming endpoints."""

    def __init__(self):
        self.events: List[dict] = []
        self.connected = False

    async def connect(self, url: str):
        """Simulate connecting to SSE endpoint."""
        self.connected = True
        self.events = []

    async def receive_event(self, event_type: str, data: Any):
        """Record a received SSE event."""
        self.events.append({
            "type": event_type,
            "data": data,
            "timestamp": time.time(),
        })

    def get_events_by_type(self, event_type: str) -> List[dict]:
        """Get all events of a specific type."""
        return [e for e in self.events if e["type"] == event_type]

    async def disconnect(self):
        """Simulate disconnecting from SSE endpoint."""
        self.connected = False


@pytest.fixture
def mock_sse_client():
    """Create a mock SSE client for testing streaming."""
    return MockSSEClient()


# Mark all tests in this directory as tracer tests
def pytest_collection_modifyitems(config, items):
    """Add tracer marker to all tests in tracers directory."""
    for item in items:
        if "tracers" in str(item.fspath):
            item.add_marker(pytest.mark.tracer)
