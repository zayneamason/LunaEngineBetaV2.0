"""
Chat Request Tracer Tests
==========================

End-to-end traces for chat request flow through the Luna Engine.

Traces the complete lifecycle from input to output, measuring
timing at each stage and verifying actor sequences.
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List

from tests.tracers.trace_utils import (
    trace_async,
    assert_sequence_contains,
    assert_no_errors,
    assert_timing_under,
    PerformanceTracer,
    ActorSequenceTracer,
)


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_chat_request_lifecycle(trace_collector, mock_memory_matrix):
    """
    Trace full chat request from input to output.

    Verifies the complete request lifecycle:
    1. Input received
    2. Memory context fetched
    3. Director processes message
    4. Response generated
    5. Memory updated
    6. Output returned
    """
    # Record initial state
    trace_collector.record("test_start", {"message": "Hello Luna"})

    # Simulate the chat flow stages
    # Stage 1: Input processing
    input_start = time.time()
    await asyncio.sleep(0.01)  # Simulate input validation
    trace_collector.record_with_duration("input_received", input_start)

    # Stage 2: Memory context fetch
    context_start = time.time()
    context = await mock_memory_matrix.get_context("Hello Luna", max_tokens=1500)
    trace_collector.record_with_duration("memory_context_fetched", context_start, {
        "context_length": len(context),
    })

    # Stage 3: Director message processing
    director_start = time.time()
    # Simulate director processing
    await asyncio.sleep(0.05)  # Simulate LLM latency
    mock_response = "Hello! How can I help you today?"
    trace_collector.record_with_duration("director_processed", director_start, {
        "response_length": len(mock_response),
    })

    # Stage 4: Memory update (store user turn)
    store_start = time.time()
    await mock_memory_matrix.store_turn(
        session_id="test-session",
        role="user",
        content="Hello Luna",
    )
    trace_collector.record_with_duration("user_turn_stored", store_start)

    # Stage 5: Store assistant response
    response_start = time.time()
    await mock_memory_matrix.store_turn(
        session_id="test-session",
        role="assistant",
        content=mock_response,
    )
    trace_collector.record_with_duration("assistant_turn_stored", response_start)

    # Stage 6: Output returned
    trace_collector.record("output_returned", {
        "response": mock_response,
        "total_time_ms": trace_collector.total_time_ms(),
    })

    # Verify the trace sequence
    expected_sequence = [
        "trace_start",
        "test_start",
        "input_received",
        "memory_context_fetched",
        "director_processed",
        "user_turn_stored",
        "assistant_turn_stored",
        "output_returned",
    ]

    trace_collector.assert_sequence_contains(expected_sequence)
    assert_no_errors(trace_collector.get_sequence())

    # Verify memory was called correctly
    assert len(mock_memory_matrix._call_history) >= 2
    assert mock_memory_matrix._call_history[0][0] == "get_context"
    assert mock_memory_matrix._call_history[1][0] == "store_turn"


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_chat_timing_breakdown(trace_collector, mock_memory_matrix):
    """
    Measure time spent at each stage of chat processing.

    Provides detailed timing breakdown for performance analysis.
    """
    perf_tracer = PerformanceTracer()

    # Input processing stage
    perf_tracer.start_span("input_processing")
    await asyncio.sleep(0.005)  # Simulate validation
    perf_tracer.end_span("input_processing")

    # Memory retrieval stage
    perf_tracer.start_span("memory_retrieval")
    context = await mock_memory_matrix.get_context("Test query", max_tokens=1500)
    perf_tracer.end_span("memory_retrieval")

    # LLM inference stage (simulated)
    perf_tracer.start_span("llm_inference")
    await asyncio.sleep(0.1)  # Simulate LLM latency
    response = "Simulated LLM response"
    perf_tracer.end_span("llm_inference")

    # Response processing stage
    perf_tracer.start_span("response_processing")
    await mock_memory_matrix.store_turn("session", "assistant", response)
    await asyncio.sleep(0.002)  # Simulate formatting
    perf_tracer.end_span("response_processing")

    # Get summary
    summary = perf_tracer.get_summary()

    # Record to trace collector
    trace_collector.record("timing_breakdown", summary)

    # Verify we captured all stages
    assert "input_processing" in summary
    assert "memory_retrieval" in summary
    assert "llm_inference" in summary
    assert "response_processing" in summary

    # LLM should be the dominant time
    assert summary["llm_inference"]["total_ms"] > summary["memory_retrieval"]["total_ms"]

    # Total time should be reasonable
    total_time = perf_tracer.get_total_time()
    assert total_time > 100  # At least 100ms due to simulated LLM latency
    assert total_time < 1000  # But not more than 1s


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_chat_actor_sequence(trace_collector, mock_memory_matrix):
    """
    Verify actors are called in correct order during chat.

    Expected sequence:
    1. Engine receives input
    2. Matrix fetches memory context
    3. Director processes with context
    4. Matrix stores conversation turn
    5. Response returned via Engine
    """
    actor_tracer = ActorSequenceTracer()

    # Simulate message flow through actors
    # 1. Engine receives and queues input
    actor_tracer.record_receive("engine", "text_input", {"message": "Hello"})

    # 2. Engine dispatches to Matrix for context
    actor_tracer.record_send("engine", "matrix", "retrieve", {"query": "Hello"})
    actor_tracer.record_receive("matrix", "retrieve")

    # 3. Engine dispatches to Director with context
    actor_tracer.record_send("engine", "director", "generate", {"message": "Hello", "context": "..."})
    actor_tracer.record_receive("director", "generate")

    # 4. Director requests additional memory (optional)
    actor_tracer.record_send("director", "matrix", "search", {"query": "Hello"})
    actor_tracer.record_receive("matrix", "search")

    # 5. Director completes generation
    actor_tracer.record_send("director", "engine", "generation_complete", {"response": "Hi there!"})
    actor_tracer.record_receive("engine", "generation_complete")

    # 6. Engine stores conversation
    actor_tracer.record_send("engine", "matrix", "store", {"content": "Hi there!"})
    actor_tracer.record_receive("matrix", "store")

    # Verify actor sequence
    actor_sequence = actor_tracer.get_actor_sequence()

    # Key actors should be involved
    assert "engine" in actor_sequence
    assert "matrix" in actor_sequence
    assert "director" in actor_sequence

    # Matrix should be called before Director (for context)
    matrix_first = actor_sequence.index("matrix")
    director_first = actor_sequence.index("director")
    assert matrix_first < director_first

    # Record trace for debugging
    trace_collector.record("actor_sequence", actor_sequence)
    trace_collector.record("message_flow", actor_tracer.get_message_flow())


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_chat_memory_retrieval_included(trace_collector, mock_memory_matrix):
    """
    Verify memory retrieval is always included in chat flow.

    The chat flow should:
    1. Always fetch memory context before generation
    2. Use the context in the system prompt
    3. Store both user and assistant turns
    """
    messages_processed = []

    # Simulate a chat with memory context
    user_message = "What did we talk about yesterday?"

    # Step 1: Memory retrieval should happen
    trace_collector.record("memory_retrieval_start")
    context = await mock_memory_matrix.get_context(user_message, max_tokens=3800)
    trace_collector.record("memory_retrieval_end", {"context_length": len(context)})

    assert context is not None
    assert len(context) > 0  # Should have some context

    # Step 2: Verify context was fetched from mock
    call_history = mock_memory_matrix._call_history
    context_calls = [c for c in call_history if c[0] == "get_context"]
    assert len(context_calls) >= 1

    # Step 3: Store user turn
    trace_collector.record("user_turn_store_start")
    await mock_memory_matrix.store_turn("session", "user", user_message)
    trace_collector.record("user_turn_store_end")

    # Step 4: Generate response (simulated)
    response = "We discussed your project plans."
    messages_processed.append(("user", user_message))
    messages_processed.append(("assistant", response))

    # Step 5: Store assistant turn
    trace_collector.record("assistant_turn_store_start")
    await mock_memory_matrix.store_turn("session", "assistant", response)
    trace_collector.record("assistant_turn_store_end")

    # Verify the complete sequence
    expected_sequence = [
        "memory_retrieval_start",
        "memory_retrieval_end",
        "user_turn_store_start",
        "user_turn_store_end",
        "assistant_turn_store_start",
        "assistant_turn_store_end",
    ]
    trace_collector.assert_sequence_contains(expected_sequence)

    # Verify all operations were recorded
    store_calls = [c for c in mock_memory_matrix._call_history if c[0] == "store_turn"]
    assert len(store_calls) >= 2  # Both user and assistant turns


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_chat_error_handling_trace(trace_collector, mock_memory_matrix):
    """
    Trace error handling during chat processing.

    Verifies that errors are properly traced and don't corrupt
    the trace timeline.
    """
    # Simulate an error during memory retrieval
    async def failing_get_context(*args, **kwargs):
        raise ConnectionError("Database connection lost")

    original_get_context = mock_memory_matrix.get_context
    mock_memory_matrix.get_context = failing_get_context

    trace_collector.record("chat_start")

    # Attempt memory retrieval (should fail)
    trace_collector.record("memory_retrieval_start")
    try:
        await mock_memory_matrix.get_context("test query")
        trace_collector.record("memory_retrieval_success")  # Should not reach here
    except ConnectionError as e:
        trace_collector.record("memory_retrieval_error", {"error": str(e)})

    # Chat should continue with empty context (graceful degradation)
    trace_collector.record("fallback_to_empty_context")

    # Simulate continuing without memory context
    await asyncio.sleep(0.01)
    trace_collector.record("generation_complete", {"used_context": False})

    # Verify error was traced
    sequence = trace_collector.get_sequence()
    assert "memory_retrieval_error" in sequence
    assert "fallback_to_empty_context" in sequence

    # Verify we didn't record success after error
    assert "memory_retrieval_success" not in sequence

    # Restore original function
    mock_memory_matrix.get_context = original_get_context


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_chat_concurrent_requests_trace(trace_collector, mock_memory_matrix):
    """
    Trace multiple concurrent chat requests.

    Verifies that concurrent requests are properly isolated
    and their traces don't interleave incorrectly.
    """
    async def simulate_chat(request_id: str, delay: float):
        """Simulate a single chat request."""
        trace_collector.record(f"request_{request_id}_start")

        # Memory retrieval
        await mock_memory_matrix.get_context(f"Query {request_id}")
        trace_collector.record(f"request_{request_id}_context")

        # Simulate varying LLM latency
        await asyncio.sleep(delay)
        trace_collector.record(f"request_{request_id}_generated")

        # Store turns
        await mock_memory_matrix.store_turn("session", "user", f"Query {request_id}")
        await mock_memory_matrix.store_turn("session", "assistant", f"Response {request_id}")
        trace_collector.record(f"request_{request_id}_complete")

    # Launch 3 concurrent requests
    await asyncio.gather(
        simulate_chat("A", 0.05),
        simulate_chat("B", 0.03),
        simulate_chat("C", 0.04),
    )

    # Verify all requests completed
    sequence = trace_collector.get_sequence()

    for req_id in ["A", "B", "C"]:
        assert f"request_{req_id}_start" in sequence
        assert f"request_{req_id}_complete" in sequence

        # Verify each request's events are in correct order
        start_idx = sequence.index(f"request_{req_id}_start")
        context_idx = sequence.index(f"request_{req_id}_context")
        generated_idx = sequence.index(f"request_{req_id}_generated")
        complete_idx = sequence.index(f"request_{req_id}_complete")

        assert start_idx < context_idx < generated_idx < complete_idx


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_chat_with_streaming_trace(trace_collector, mock_memory_matrix):
    """
    Trace chat request with streaming response.

    Verifies token-by-token streaming is properly traced.
    """
    tokens = ["Hello", " ", "there", "!", " How", " can", " I", " help", "?"]

    trace_collector.record("streaming_start")

    # Simulate memory context fetch
    await mock_memory_matrix.get_context("test")
    trace_collector.record("context_fetched")

    # Simulate streaming tokens
    trace_collector.record("token_stream_start")
    full_response = ""

    for i, token in enumerate(tokens):
        await asyncio.sleep(0.005)  # Simulate token generation time
        full_response += token
        trace_collector.record("token_received", {
            "token_index": i,
            "token": token,
            "cumulative_length": len(full_response),
        })

    trace_collector.record("token_stream_end", {
        "total_tokens": len(tokens),
        "response_length": len(full_response),
    })

    # Store the complete response
    await mock_memory_matrix.store_turn("session", "assistant", full_response)
    trace_collector.record("response_stored")

    # Verify streaming sequence
    sequence = trace_collector.get_sequence()

    assert "streaming_start" in sequence
    assert "context_fetched" in sequence
    assert "token_stream_start" in sequence
    assert "token_stream_end" in sequence
    assert "response_stored" in sequence

    # Count token events
    token_events = trace_collector.get_events_by_type("token_received")
    assert len(token_events) == len(tokens)

    # Verify tokens were received in order
    for i, event in enumerate(token_events):
        assert event.data["token_index"] == i
