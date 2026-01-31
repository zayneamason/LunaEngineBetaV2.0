"""
Tracer utilities for Luna Engine end-to-end tests.

Provides decorators, assertion helpers, and timing utilities
for tracing request flows through the system.
"""

import asyncio
import functools
import time
from typing import Any, Callable, List, Optional, TypeVar
from dataclasses import dataclass

T = TypeVar("T")


def trace_async(collector, event_name: str):
    """
    Decorator to trace async function execution.

    Records start, end, and error events to the trace collector.

    Args:
        collector: TraceCollector instance to record events
        event_name: Base name for the trace events

    Example:
        @trace_async(collector, "fetch_memory")
        async def fetch_memory(query):
            return await matrix.search(query)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            start_time = time.time()
            collector.record(f"{event_name}_start")
            try:
                result = await func(*args, **kwargs)
                collector.record_with_duration(
                    f"{event_name}_end",
                    start_time,
                    result
                )
                return result
            except Exception as e:
                collector.record_with_duration(
                    f"{event_name}_error",
                    start_time,
                    str(e)
                )
                raise
        return wrapper
    return decorator


def trace_sync(collector, event_name: str):
    """
    Decorator to trace synchronous function execution.

    Args:
        collector: TraceCollector instance to record events
        event_name: Base name for the trace events
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            start_time = time.time()
            collector.record(f"{event_name}_start")
            try:
                result = func(*args, **kwargs)
                collector.record_with_duration(
                    f"{event_name}_end",
                    start_time,
                    result
                )
                return result
            except Exception as e:
                collector.record_with_duration(
                    f"{event_name}_error",
                    start_time,
                    str(e)
                )
                raise
        return wrapper
    return decorator


def assert_sequence_contains(trace: List[str], expected: List[str]) -> bool:
    """
    Check if trace contains expected sequence in order.

    The expected events must appear in order, but other events
    can appear between them.

    Args:
        trace: List of event type strings
        expected: List of expected event types in order

    Returns:
        True if trace contains expected sequence

    Example:
        trace = ["a_start", "b_start", "b_end", "a_end"]
        assert_sequence_contains(trace, ["a_start", "a_end"])  # True
        assert_sequence_contains(trace, ["b_end", "a_start"])  # False
    """
    idx = 0
    for event in trace:
        if idx < len(expected) and event == expected[idx]:
            idx += 1
    return idx == len(expected)


def assert_no_errors(trace: List[str]) -> bool:
    """
    Assert that trace contains no error events.

    Args:
        trace: List of event type strings

    Returns:
        True if no error events found

    Raises:
        AssertionError: If error events are found
    """
    errors = [e for e in trace if e.endswith("_error")]
    if errors:
        raise AssertionError(f"Trace contains error events: {errors}")
    return True


def assert_timing_under(timing_ms: float, max_ms: float, operation: str = "") -> None:
    """
    Assert that an operation completed within time limit.

    Args:
        timing_ms: Actual timing in milliseconds
        max_ms: Maximum allowed time in milliseconds
        operation: Optional operation name for error message

    Raises:
        AssertionError: If timing exceeds limit
    """
    if timing_ms > max_ms:
        op_str = f" for {operation}" if operation else ""
        raise AssertionError(
            f"Timing{op_str} exceeded limit: {timing_ms:.2f}ms > {max_ms:.2f}ms"
        )


@dataclass
class TimingBucket:
    """Collects timing samples for statistical analysis."""
    name: str
    samples: List[float] = None

    def __post_init__(self):
        if self.samples is None:
            self.samples = []

    def add(self, timing_ms: float) -> None:
        """Add a timing sample."""
        self.samples.append(timing_ms)

    @property
    def count(self) -> int:
        """Number of samples."""
        return len(self.samples)

    @property
    def total(self) -> float:
        """Total time across all samples."""
        return sum(self.samples)

    @property
    def average(self) -> float:
        """Average timing."""
        return self.total / self.count if self.count > 0 else 0

    @property
    def min(self) -> float:
        """Minimum timing."""
        return min(self.samples) if self.samples else 0

    @property
    def max(self) -> float:
        """Maximum timing."""
        return max(self.samples) if self.samples else 0

    def p50(self) -> float:
        """50th percentile (median)."""
        return self._percentile(50)

    def p90(self) -> float:
        """90th percentile."""
        return self._percentile(90)

    def p99(self) -> float:
        """99th percentile."""
        return self._percentile(99)

    def _percentile(self, p: int) -> float:
        """Calculate percentile."""
        if not self.samples:
            return 0
        sorted_samples = sorted(self.samples)
        idx = int(len(sorted_samples) * p / 100)
        return sorted_samples[min(idx, len(sorted_samples) - 1)]

    def summary(self) -> dict:
        """Get summary statistics."""
        return {
            "name": self.name,
            "count": self.count,
            "total_ms": self.total,
            "avg_ms": self.average,
            "min_ms": self.min,
            "max_ms": self.max,
            "p50_ms": self.p50(),
            "p90_ms": self.p90(),
            "p99_ms": self.p99(),
        }


class PerformanceTracer:
    """
    High-level performance tracer for multi-operation flows.

    Collects timing data across multiple operations and
    provides statistical analysis.
    """

    def __init__(self):
        self.buckets: dict[str, TimingBucket] = {}
        self.spans: List[dict] = []
        self._active_spans: dict[str, float] = {}

    def start_span(self, name: str) -> None:
        """Start a named timing span."""
        self._active_spans[name] = time.time()

    def end_span(self, name: str) -> float:
        """
        End a named timing span.

        Returns:
            Duration in milliseconds
        """
        if name not in self._active_spans:
            return 0

        start = self._active_spans.pop(name)
        duration_ms = (time.time() - start) * 1000

        if name not in self.buckets:
            self.buckets[name] = TimingBucket(name)
        self.buckets[name].add(duration_ms)

        self.spans.append({
            "name": name,
            "start": start,
            "duration_ms": duration_ms,
        })

        return duration_ms

    def record(self, name: str, duration_ms: float) -> None:
        """Record a timing sample directly."""
        if name not in self.buckets:
            self.buckets[name] = TimingBucket(name)
        self.buckets[name].add(duration_ms)

    def get_summary(self) -> dict:
        """Get summary of all timing buckets."""
        return {
            name: bucket.summary()
            for name, bucket in self.buckets.items()
        }

    def get_total_time(self) -> float:
        """Get total time across all spans."""
        return sum(s["duration_ms"] for s in self.spans)

    def dump(self) -> str:
        """Dump performance data to string."""
        lines = ["Performance Summary:"]
        for name, bucket in sorted(self.buckets.items()):
            stats = bucket.summary()
            lines.append(
                f"  {name}: count={stats['count']}, "
                f"avg={stats['avg_ms']:.2f}ms, "
                f"p90={stats['p90_ms']:.2f}ms, "
                f"max={stats['max_ms']:.2f}ms"
            )
        lines.append(f"Total time: {self.get_total_time():.2f}ms")
        return "\n".join(lines)


async def measure_async(func: Callable, *args, **kwargs) -> tuple[Any, float]:
    """
    Measure execution time of an async function.

    Args:
        func: Async function to measure
        *args, **kwargs: Arguments to pass to function

    Returns:
        Tuple of (result, duration_ms)
    """
    start = time.time()
    result = await func(*args, **kwargs)
    duration_ms = (time.time() - start) * 1000
    return result, duration_ms


def measure_sync(func: Callable, *args, **kwargs) -> tuple[Any, float]:
    """
    Measure execution time of a sync function.

    Args:
        func: Function to measure
        *args, **kwargs: Arguments to pass to function

    Returns:
        Tuple of (result, duration_ms)
    """
    start = time.time()
    result = func(*args, **kwargs)
    duration_ms = (time.time() - start) * 1000
    return result, duration_ms


class ActorSequenceTracer:
    """
    Traces actor message flow through the system.

    Records which actors receive messages and in what order.
    """

    def __init__(self):
        self.messages: List[dict] = []

    def record_send(
        self,
        sender: str,
        target: str,
        message_type: str,
        payload: Any = None
    ) -> None:
        """Record a message being sent between actors."""
        self.messages.append({
            "timestamp": time.time(),
            "sender": sender,
            "target": target,
            "type": message_type,
            "payload": payload,
            "direction": "send",
        })

    def record_receive(
        self,
        actor: str,
        message_type: str,
        payload: Any = None
    ) -> None:
        """Record an actor receiving a message."""
        self.messages.append({
            "timestamp": time.time(),
            "actor": actor,
            "type": message_type,
            "payload": payload,
            "direction": "receive",
        })

    def get_actor_sequence(self) -> List[str]:
        """Get sequence of actors that received messages."""
        return [
            m["actor"] for m in self.messages
            if m.get("direction") == "receive"
        ]

    def get_message_flow(self) -> List[tuple[str, str, str]]:
        """Get message flow as list of (sender, target, type) tuples."""
        return [
            (m["sender"], m["target"], m["type"])
            for m in self.messages
            if m.get("direction") == "send"
        ]

    def dump(self) -> str:
        """Dump message flow to string."""
        lines = ["Actor Message Flow:"]
        base_time = self.messages[0]["timestamp"] if self.messages else 0
        for m in self.messages:
            relative_ms = (m["timestamp"] - base_time) * 1000
            if m.get("direction") == "send":
                lines.append(
                    f"  +{relative_ms:.2f}ms: {m['sender']} -> {m['target']}: {m['type']}"
                )
            else:
                lines.append(
                    f"  +{relative_ms:.2f}ms: {m['actor']} received: {m['type']}"
                )
        return "\n".join(lines)
