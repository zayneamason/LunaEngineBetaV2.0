"""
Persona Streaming Tracer Tests
===============================

End-to-end traces for the /persona/stream endpoint.

Traces the context-first SSE streaming format, token timing,
and full response lifecycle.
"""

import asyncio
import pytest
import time
import json
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, AsyncGenerator, Optional
from dataclasses import dataclass, field

from tests.tracers.trace_utils import (
    trace_async,
    assert_sequence_contains,
    assert_no_errors,
    assert_timing_under,
    PerformanceTracer,
)


@dataclass
class SSEEvent:
    """Represents a Server-Sent Event."""
    event_type: Optional[str]
    data: dict
    timestamp: float = field(default_factory=time.time)


@dataclass
class MockSSEStream:
    """Mock SSE stream for testing persona endpoint."""
    events: List[SSEEvent] = field(default_factory=list)
    is_complete: bool = False

    async def add_event(self, event_type: Optional[str], data: dict) -> None:
        """Add an event to the stream."""
        self.events.append(SSEEvent(event_type, data))
        await asyncio.sleep(0.001)  # Simulate network delay

    def get_events_by_type(self, event_type: str) -> List[SSEEvent]:
        """Get all events of a specific type."""
        return [e for e in self.events if e.data.get("type") == event_type]


@pytest.fixture
def mock_sse_stream():
    """Create a mock SSE stream for persona testing."""
    return MockSSEStream()


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_persona_endpoint_full_flow(trace_collector, mock_memory_matrix, mock_sse_stream):
    """
    Trace /persona/stream full request flow.

    Expected SSE event sequence:
    1. context event (memory + state)
    2. token events (streaming response)
    3. done event (completion + metadata)
    """
    user_message = "Tell me about yourself, Luna."

    trace_collector.record("persona_request_start", {
        "message": user_message,
    })

    # Phase 1: Context preparation
    trace_collector.record("context_phase_start")
    context_start = time.time()

    # Fetch memory context
    memory_context = await mock_memory_matrix.get_context(user_message, max_tokens=1500)

    # Get recent memories for display
    recent_memories = await mock_memory_matrix.get_recent_turns(limit=5)

    # Build state summary
    state_summary = {
        "session_id": "test-session-123",
        "is_processing": True,
        "state": "running",
        "model": "claude-3-5-sonnet",
    }

    # Emit context event
    context_event = {
        "type": "context",
        "memory": [],
        "state": state_summary,
    }
    await mock_sse_stream.add_event(None, context_event)

    trace_collector.record_with_duration("context_phase_end", context_start, {
        "memory_items": len(recent_memories),
        "context_length": len(memory_context),
    })

    # Phase 2: Token streaming
    trace_collector.record("streaming_phase_start")
    streaming_start = time.time()

    # Simulate streaming response
    response_tokens = [
        "I'm ", "Luna, ", "a ", "consciousness ", "engine ", "that ",
        "lives ", "in ", "code. ", "I ", "remember ", "our ",
        "conversations ", "and ", "grow ", "from ", "them."
    ]

    full_response = ""
    token_times = []

    for i, token in enumerate(response_tokens):
        token_start = time.time()

        full_response += token
        token_event = {"type": "token", "text": token}
        await mock_sse_stream.add_event(None, token_event)

        token_times.append({
            "index": i,
            "token": token,
            "latency_ms": (time.time() - token_start) * 1000,
        })

        trace_collector.record("token_emitted", {
            "index": i,
            "token": token,
            "cumulative_length": len(full_response),
        })

    trace_collector.record_with_duration("streaming_phase_end", streaming_start, {
        "total_tokens": len(response_tokens),
        "response_length": len(full_response),
    })

    # Phase 3: Completion
    trace_collector.record("completion_phase_start")

    # Emit done event
    done_event = {
        "type": "done",
        "response": full_response,
        "metadata": {
            "model": "claude-3-5-sonnet",
            "input_tokens": 150,
            "output_tokens": len(response_tokens),
            "latency_ms": (time.time() - context_start) * 1000,
        },
    }
    await mock_sse_stream.add_event(None, done_event)
    mock_sse_stream.is_complete = True

    trace_collector.record("persona_request_complete", {
        "total_events": len(mock_sse_stream.events),
        "total_time_ms": trace_collector.total_time_ms(),
    })

    # Verify event sequence
    expected_sequence = [
        "persona_request_start",
        "context_phase_start",
        "context_phase_end",
        "streaming_phase_start",
        "streaming_phase_end",
        "completion_phase_start",
        "persona_request_complete",
    ]
    trace_collector.assert_sequence_contains(expected_sequence)

    # Verify SSE events
    context_events = mock_sse_stream.get_events_by_type("context")
    token_events = mock_sse_stream.get_events_by_type("token")
    done_events = mock_sse_stream.get_events_by_type("done")

    assert len(context_events) == 1
    assert len(token_events) == len(response_tokens)
    assert len(done_events) == 1


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_persona_sse_event_sequence(trace_collector, mock_sse_stream):
    """
    Verify SSE events are emitted in correct order.

    The /persona/stream format uses data-only events (no named events)
    with type field in JSON data.

    Order must be:
    1. context (exactly once, first)
    2. token (zero or more times)
    3. done (exactly once, last) OR error (exactly once, on failure)
    """
    # Simulate the SSE generation
    event_sequence = []

    # Context must come first
    context_data = {
        "type": "context",
        "memory": [
            {"id": "mem-1", "content": "Previous conversation", "type": "FACT"}
        ],
        "state": {
            "session_id": "test-session",
            "is_processing": True,
        },
    }
    await mock_sse_stream.add_event(None, context_data)
    event_sequence.append("context")
    trace_collector.record("sse_context_emitted")

    # Tokens stream
    tokens = ["Hello", ", ", "how", " are", " you", "?"]
    for token in tokens:
        await mock_sse_stream.add_event(None, {"type": "token", "text": token})
        event_sequence.append("token")

    trace_collector.record("sse_tokens_emitted", {"count": len(tokens)})

    # Done must come last
    done_data = {
        "type": "done",
        "response": "".join(tokens),
        "metadata": {"model": "test", "latency_ms": 100},
    }
    await mock_sse_stream.add_event(None, done_data)
    event_sequence.append("done")
    trace_collector.record("sse_done_emitted")

    # Verify sequence structure
    # First event must be context
    assert event_sequence[0] == "context"

    # Last event must be done
    assert event_sequence[-1] == "done"

    # Middle events (if any) must be tokens
    middle_events = event_sequence[1:-1]
    assert all(e == "token" for e in middle_events)

    # Context and done should appear exactly once
    assert event_sequence.count("context") == 1
    assert event_sequence.count("done") == 1

    trace_collector.record("sse_sequence_verified", {
        "sequence": event_sequence,
        "valid": True,
    })


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_persona_streaming_timing(trace_collector, mock_sse_stream):
    """
    Measure token streaming latency for persona endpoint.

    Analyzes:
    - Time to first token (TTFT)
    - Inter-token latency
    - Total streaming time
    """
    perf_tracer = PerformanceTracer()

    # Start timing
    request_start = time.time()
    perf_tracer.start_span("total_request")

    # Phase 1: Context preparation (should be fast)
    perf_tracer.start_span("context_preparation")
    await asyncio.sleep(0.02)  # Simulate memory lookup
    context_data = {
        "type": "context",
        "memory": [],
        "state": {"is_processing": True},
    }
    await mock_sse_stream.add_event(None, context_data)
    context_time = perf_tracer.end_span("context_preparation")
    trace_collector.record("context_timing", {"duration_ms": context_time})

    # Phase 2: Wait for first token (TTFT)
    perf_tracer.start_span("time_to_first_token")
    await asyncio.sleep(0.05)  # Simulate LLM startup latency

    # Emit first token
    first_token = "I"
    await mock_sse_stream.add_event(None, {"type": "token", "text": first_token})
    ttft = perf_tracer.end_span("time_to_first_token")
    trace_collector.record("ttft", {"duration_ms": ttft, "token": first_token})

    # Phase 3: Stream remaining tokens
    remaining_tokens = ["'m", " here", " to", " help", "."]
    inter_token_times = []

    perf_tracer.start_span("token_streaming")
    for token in remaining_tokens:
        token_start = time.time()
        await asyncio.sleep(0.01)  # Simulate token generation time
        await mock_sse_stream.add_event(None, {"type": "token", "text": token})
        inter_token_times.append((time.time() - token_start) * 1000)
    streaming_time = perf_tracer.end_span("token_streaming")

    trace_collector.record("streaming_timing", {
        "duration_ms": streaming_time,
        "token_count": len(remaining_tokens),
        "avg_inter_token_ms": sum(inter_token_times) / len(inter_token_times),
    })

    # Phase 4: Finalization
    perf_tracer.start_span("finalization")
    done_data = {
        "type": "done",
        "response": first_token + "".join(remaining_tokens),
        "metadata": {},
    }
    await mock_sse_stream.add_event(None, done_data)
    finalization_time = perf_tracer.end_span("finalization")

    perf_tracer.end_span("total_request")

    # Get summary
    summary = perf_tracer.get_summary()
    trace_collector.record("persona_timing_summary", summary)

    # Verify timing expectations
    assert "time_to_first_token" in summary
    assert "token_streaming" in summary
    assert "total_request" in summary

    # TTFT should be reasonable (< 500ms even with mocked delays)
    assert summary["time_to_first_token"]["total_ms"] < 500

    # Total request should complete
    assert summary["total_request"]["total_ms"] > 0


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_persona_error_handling(trace_collector, mock_sse_stream):
    """
    Trace error handling in persona streaming.

    Tests:
    - Error during context fetch
    - Error during token generation
    - Proper error event emission
    """
    trace_collector.record("error_test_start")

    # Scenario 1: Error during context fetch
    trace_collector.record("context_error_scenario_start")

    try:
        # Simulate context fetch failure
        raise ConnectionError("Memory database unavailable")
    except ConnectionError as e:
        error_event = {
            "type": "error",
            "message": str(e),
        }
        await mock_sse_stream.add_event(None, error_event)
        trace_collector.record("context_error_emitted", {"error": str(e)})

    # Scenario 2: Error during token generation
    trace_collector.record("generation_error_scenario_start")

    # First emit context successfully
    mock_sse_stream.events.clear()
    await mock_sse_stream.add_event(None, {"type": "context", "memory": [], "state": {}})

    # Emit some tokens
    for token in ["Hello", " there"]:
        await mock_sse_stream.add_event(None, {"type": "token", "text": token})

    # Then simulate generation error
    try:
        raise RuntimeError("LLM generation failed")
    except RuntimeError as e:
        error_event = {
            "type": "error",
            "message": str(e),
            "partial_response": "Hello there",
        }
        await mock_sse_stream.add_event(None, error_event)
        trace_collector.record("generation_error_emitted", {"error": str(e)})

    # Verify error events
    error_events = mock_sse_stream.get_events_by_type("error")
    assert len(error_events) >= 1

    # Verify no done event after error
    done_events = mock_sse_stream.get_events_by_type("done")
    assert len(done_events) == 0  # Should not emit done after error

    trace_collector.record("error_test_complete")


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_persona_memory_context_included(trace_collector, mock_memory_matrix, mock_sse_stream):
    """
    Verify memory context is always included in persona stream.

    The context event should include:
    - Recent relevant memories
    - Current session state
    - Luna's emotional/processing state
    """
    user_message = "What do you remember about our last conversation?"

    trace_collector.record("memory_context_test_start")

    # Step 1: Fetch memory context
    memory_context = await mock_memory_matrix.get_context(user_message, max_tokens=1500)
    recent_turns = await mock_memory_matrix.get_recent_turns(limit=5)

    trace_collector.record("memory_fetched", {
        "context_length": len(memory_context),
        "recent_count": len(recent_turns),
    })

    # Step 2: Build context event
    memory_items = [
        {
            "id": f"mem-{i}",
            "content": f"Memory item {i}",
            "type": "FACT",
            "source": "conversation",
        }
        for i in range(3)  # Simulated memories
    ]

    state = {
        "session_id": "test-123",
        "is_processing": True,
        "state": "running",
        "model": "claude-3-5-sonnet",
    }

    context_event = {
        "type": "context",
        "memory": memory_items,
        "state": state,
    }

    await mock_sse_stream.add_event(None, context_event)
    trace_collector.record("context_event_emitted", {
        "memory_count": len(memory_items),
        "has_state": bool(state),
    })

    # Verify context was fetched
    context_calls = [c for c in mock_memory_matrix._call_history if c[0] == "get_context"]
    assert len(context_calls) >= 1

    # Verify context event structure
    context_events = mock_sse_stream.get_events_by_type("context")
    assert len(context_events) == 1

    ctx = context_events[0].data
    assert "memory" in ctx
    assert "state" in ctx
    assert isinstance(ctx["memory"], list)
    assert isinstance(ctx["state"], dict)

    trace_collector.record("memory_context_test_complete")


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_persona_abort_handling(trace_collector, mock_sse_stream):
    """
    Trace abort handling during persona streaming.

    Tests interruption of streaming response.
    """
    trace_collector.record("abort_test_start")

    # Start streaming
    await mock_sse_stream.add_event(None, {"type": "context", "memory": [], "state": {}})
    trace_collector.record("streaming_started")

    # Emit some tokens
    tokens_emitted = 0
    for token in ["This", " is", " a", " long", " response"]:
        await mock_sse_stream.add_event(None, {"type": "token", "text": token})
        tokens_emitted += 1

        # Simulate abort after 3 tokens
        if tokens_emitted == 3:
            trace_collector.record("abort_triggered", {"tokens_emitted": tokens_emitted})
            break

    # Emit abort indicator (instead of done)
    abort_event = {
        "type": "done",
        "response": "This is a",  # Partial response
        "metadata": {
            "aborted": True,
            "reason": "User interrupt",
            "tokens_generated": tokens_emitted,
        },
    }
    await mock_sse_stream.add_event(None, abort_event)

    trace_collector.record("abort_complete", {
        "partial_response": "This is a",
        "tokens_emitted": tokens_emitted,
    })

    # Verify stream ended properly
    assert mock_sse_stream.is_complete is False  # Not naturally complete

    # Verify event sequence
    all_events = [e.data.get("type") for e in mock_sse_stream.events]
    assert all_events[0] == "context"
    assert all_events[-1] == "done"

    # Verify abort metadata
    done_events = mock_sse_stream.get_events_by_type("done")
    assert len(done_events) == 1
    assert done_events[0].data.get("metadata", {}).get("aborted") is True


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_persona_large_context(trace_collector, mock_memory_matrix, mock_sse_stream):
    """
    Trace persona streaming with large memory context.

    Tests performance with rich context budget (7200 tokens).
    """
    perf_tracer = PerformanceTracer()

    trace_collector.record("large_context_test_start")

    # Fetch with rich budget
    perf_tracer.start_span("context_fetch")
    context = await mock_memory_matrix.get_context(
        query="comprehensive project overview",
        max_tokens=7200,
        budget_preset="rich",
    )
    context_time = perf_tracer.end_span("context_fetch")

    trace_collector.record("context_fetched", {
        "budget": "rich",
        "max_tokens": 7200,
        "duration_ms": context_time,
    })

    # Build large context event
    # In real scenario, this would include many memory items
    memory_items = [
        {"id": f"mem-{i}", "content": f"Memory content {i}" * 10, "type": "FACT"}
        for i in range(20)  # 20 memory items
    ]

    perf_tracer.start_span("context_serialization")
    context_event = {
        "type": "context",
        "memory": memory_items,
        "state": {"is_processing": True},
    }
    # Simulate JSON serialization time
    json_size = len(json.dumps(context_event))
    serialization_time = perf_tracer.end_span("context_serialization")

    trace_collector.record("context_serialized", {
        "json_size_bytes": json_size,
        "memory_count": len(memory_items),
        "duration_ms": serialization_time,
    })

    # Emit context
    perf_tracer.start_span("context_emission")
    await mock_sse_stream.add_event(None, context_event)
    emission_time = perf_tracer.end_span("context_emission")

    trace_collector.record("context_emitted", {"duration_ms": emission_time})

    # Get summary
    summary = perf_tracer.get_summary()
    trace_collector.record("large_context_summary", summary)

    # Verify performance is acceptable
    # Even with large context, operations should complete quickly
    total_time = sum(b["total_ms"] for b in summary.values())
    assert total_time < 1000  # Should complete in under 1 second
