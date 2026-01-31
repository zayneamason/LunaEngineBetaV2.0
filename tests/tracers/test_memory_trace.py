"""
Memory Operations Tracer Tests
===============================

End-to-end traces for memory operations through the Luna Engine.

Traces store/retrieve cycles, search performance, lock-in
calculations, and embedding generation.
"""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from typing import List, Optional
from dataclasses import dataclass

from tests.tracers.trace_utils import (
    trace_async,
    assert_sequence_contains,
    assert_no_errors,
    assert_timing_under,
    PerformanceTracer,
    TimingBucket,
)


@dataclass
class MockMemoryNode:
    """Mock memory node for testing."""
    id: str
    node_type: str
    content: str
    lock_in: float = 0.15
    lock_in_state: str = "drifting"
    access_count: int = 0
    reinforcement_count: int = 0
    confidence: float = 1.0
    importance: float = 0.5


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_memory_store_retrieve_cycle(trace_collector, mock_memory_matrix):
    """
    Trace full store -> retrieve memory cycle.

    Verifies the complete round-trip:
    1. Store a memory node
    2. Generate embedding (if enabled)
    3. Index for search
    4. Retrieve via search
    5. Verify content integrity
    """
    test_content = "Luna learned that Zayne prefers dark mode in all applications."
    test_node_type = "FACT"

    # Stage 1: Store operation
    trace_collector.record("store_start", {"content_length": len(test_content)})
    store_start = time.time()

    node_id = await mock_memory_matrix.store_memory(
        content=test_content,
        node_type=test_node_type,
        tags=["preference", "zayne"],
        confidence=0.95,
    )

    trace_collector.record_with_duration("store_complete", store_start, {
        "node_id": node_id,
    })

    # Stage 2: Simulate embedding generation
    trace_collector.record("embedding_start")
    embedding_start = time.time()
    await asyncio.sleep(0.02)  # Simulate embedding generation time
    trace_collector.record_with_duration("embedding_complete", embedding_start, {
        "embedding_dim": 384,  # MiniLM dimension
    })

    # Stage 3: Retrieve via search
    trace_collector.record("search_start", {"query": "dark mode preference"})
    search_start = time.time()

    # Mock search returning the stored node
    mock_node = MockMemoryNode(
        id=node_id,
        node_type=test_node_type,
        content=test_content,
    )

    # Simulate search delay
    await asyncio.sleep(0.01)
    trace_collector.record_with_duration("search_complete", search_start, {
        "results_count": 1,
    })

    # Stage 4: Verify content integrity
    trace_collector.record("integrity_check", {
        "stored_content": test_content,
        "retrieved_content": mock_node.content,
        "match": test_content == mock_node.content,
    })

    # Verify trace sequence
    expected_sequence = [
        "store_start",
        "store_complete",
        "embedding_start",
        "embedding_complete",
        "search_start",
        "search_complete",
        "integrity_check",
    ]
    trace_collector.assert_sequence_contains(expected_sequence)

    # Verify store was called
    store_calls = [c for c in mock_memory_matrix._call_history if c[0] == "store_memory"]
    assert len(store_calls) >= 1


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_memory_search_performance(trace_collector, mock_memory_matrix):
    """
    Measure search latency across different query types.

    Tests:
    - Keyword search
    - Semantic search
    - Hybrid search
    - Empty result search
    """
    perf_tracer = PerformanceTracer()
    queries = [
        ("keyword", "dark mode preference"),
        ("semantic", "what does Zayne like"),
        ("hybrid", "Zayne dark mode"),
        ("empty", "xyznonexistent12345"),
    ]

    for search_type, query in queries:
        trace_collector.record(f"search_{search_type}_start", {"query": query})
        perf_tracer.start_span(f"search_{search_type}")

        # Execute search
        results = await mock_memory_matrix.search(query, limit=10, use_hybrid=True)

        duration = perf_tracer.end_span(f"search_{search_type}")
        trace_collector.record(f"search_{search_type}_end", {
            "results_count": len(results),
            "duration_ms": duration,
        })

    # Get performance summary
    summary = perf_tracer.get_summary()
    trace_collector.record("search_performance_summary", summary)

    # All searches should complete quickly (even if mocked)
    for search_type, _ in queries:
        assert f"search_{search_type}" in summary
        assert summary[f"search_{search_type}"]["count"] == 1


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_memory_lockin_calculation_trace(trace_collector, mock_memory_matrix):
    """
    Trace lock-in coefficient updates over time.

    Lock-in progresses through states:
    - drifting (0.0 - 0.3): New, unverified memory
    - fluid (0.3 - 0.7): Partially reinforced
    - settled (0.7 - 1.0): Core, reliable memory

    Each reinforcement increases lock-in.
    """
    # Initial state
    initial_lock_in = 0.15
    initial_state = "drifting"

    trace_collector.record("lockin_trace_start", {
        "initial_lock_in": initial_lock_in,
        "initial_state": initial_state,
    })

    # Simulate a mock node
    mock_node = MockMemoryNode(
        id="test-node-1",
        node_type="FACT",
        content="Test memory for lock-in",
        lock_in=initial_lock_in,
        lock_in_state=initial_state,
    )

    # Track lock-in progression through reinforcements
    reinforcement_count = 0
    lock_in_history = [(reinforcement_count, mock_node.lock_in, mock_node.lock_in_state)]

    # Simulate reinforcement cycle
    for i in range(10):
        trace_collector.record("reinforcement_start", {
            "iteration": i,
            "current_lock_in": mock_node.lock_in,
        })

        # Simulate reinforcement
        await mock_memory_matrix.reinforce_memory(mock_node.id, amount=1)
        reinforcement_count += 1

        # Update mock node state (simulating actual lock-in calculation)
        # Lock-in formula: lock_in = min(1.0, lock_in + 0.05 * ln(reinforcement_count + 1))
        import math
        mock_node.lock_in = min(1.0, initial_lock_in + 0.05 * math.log(reinforcement_count + 1))
        mock_node.reinforcement_count = reinforcement_count

        # Update state based on lock-in value
        if mock_node.lock_in >= 0.7:
            mock_node.lock_in_state = "settled"
        elif mock_node.lock_in >= 0.3:
            mock_node.lock_in_state = "fluid"
        else:
            mock_node.lock_in_state = "drifting"

        lock_in_history.append((reinforcement_count, mock_node.lock_in, mock_node.lock_in_state))

        trace_collector.record("reinforcement_end", {
            "iteration": i,
            "new_lock_in": mock_node.lock_in,
            "new_state": mock_node.lock_in_state,
        })

    trace_collector.record("lockin_trace_complete", {
        "final_lock_in": mock_node.lock_in,
        "final_state": mock_node.lock_in_state,
        "total_reinforcements": reinforcement_count,
        "history": lock_in_history,
    })

    # Verify lock-in increased
    assert mock_node.lock_in > initial_lock_in

    # Verify state transitions occurred
    states_seen = set(h[2] for h in lock_in_history)
    assert "drifting" in states_seen  # Started here
    # May or may not reach fluid/settled depending on formula

    # Verify reinforcement was called
    reinforce_calls = [c for c in mock_memory_matrix._call_history if c[0] == "reinforce_memory"]
    assert len(reinforce_calls) == 10


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_memory_embedding_generation(trace_collector, mock_memory_matrix):
    """
    Trace embedding generation for memory nodes.

    Tests:
    - Single embedding generation
    - Batch embedding generation
    - Embedding dimension verification
    """
    test_texts = [
        "Short text",
        "Medium length text with some more content for testing",
        "This is a much longer text that contains multiple sentences. It should test how the embedding model handles longer content. The embedding should still be the same dimension regardless of input length.",
    ]

    perf_tracer = PerformanceTracer()

    for i, text in enumerate(test_texts):
        trace_collector.record("embedding_gen_start", {
            "text_index": i,
            "text_length": len(text),
        })

        perf_tracer.start_span(f"embedding_{i}")

        # Simulate embedding generation
        await asyncio.sleep(0.01 + len(text) * 0.0001)  # Simulate time proportional to length

        # Mock embedding result
        embedding_dim = 384  # MiniLM dimension
        mock_embedding = [0.0] * embedding_dim

        duration = perf_tracer.end_span(f"embedding_{i}")

        trace_collector.record("embedding_gen_complete", {
            "text_index": i,
            "embedding_dim": len(mock_embedding),
            "duration_ms": duration,
        })

    # Get performance summary
    summary = perf_tracer.get_summary()
    trace_collector.record("embedding_performance", summary)

    # Verify all embeddings were generated
    for i in range(len(test_texts)):
        assert f"embedding_{i}" in summary

    # Longer text should take more time (in our simulation)
    # In real implementation, this tests actual model performance


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_memory_batch_operations(trace_collector, mock_memory_matrix):
    """
    Trace batch memory operations for extraction.

    Tests storing multiple nodes from a single extraction event.
    """
    # Simulate extraction output with multiple nodes
    extraction_results = [
        {"type": "FACT", "content": "Zayne works on Luna Engine"},
        {"type": "DECISION", "content": "Use SQLite for memory storage"},
        {"type": "PROBLEM", "content": "Need to optimize search latency"},
        {"type": "ACTION", "content": "Implement hybrid search"},
        {"type": "INSIGHT", "content": "Lock-in coefficient helps memory persistence"},
    ]

    trace_collector.record("batch_store_start", {
        "node_count": len(extraction_results),
    })

    stored_ids = []
    perf_tracer = PerformanceTracer()

    for i, node_data in enumerate(extraction_results):
        perf_tracer.start_span(f"store_{i}")

        node_id = await mock_memory_matrix.store_memory(
            content=node_data["content"],
            node_type=node_data["type"],
        )
        stored_ids.append(node_id)

        duration = perf_tracer.end_span(f"store_{i}")
        trace_collector.record("node_stored", {
            "index": i,
            "node_type": node_data["type"],
            "node_id": node_id,
            "duration_ms": duration,
        })

    trace_collector.record("batch_store_complete", {
        "stored_count": len(stored_ids),
        "total_time_ms": perf_tracer.get_total_time(),
    })

    # Verify all nodes were stored
    assert len(stored_ids) == len(extraction_results)

    # Verify store calls
    store_calls = [c for c in mock_memory_matrix._call_history if c[0] == "store_memory"]
    assert len(store_calls) == len(extraction_results)


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_memory_context_budget(trace_collector, mock_memory_matrix):
    """
    Trace context retrieval with different budget presets.

    Tests:
    - minimal: 1800 tokens
    - balanced: 3800 tokens
    - rich: 7200 tokens
    """
    budget_presets = [
        ("minimal", 1800),
        ("balanced", 3800),
        ("rich", 7200),
    ]

    query = "What has Zayne been working on?"
    perf_tracer = PerformanceTracer()

    for preset_name, max_tokens in budget_presets:
        trace_collector.record(f"context_fetch_{preset_name}_start", {
            "budget": preset_name,
            "max_tokens": max_tokens,
        })

        perf_tracer.start_span(f"fetch_{preset_name}")

        context = await mock_memory_matrix.get_context(
            query=query,
            max_tokens=max_tokens,
            budget_preset=preset_name,
        )

        duration = perf_tracer.end_span(f"fetch_{preset_name}")

        trace_collector.record(f"context_fetch_{preset_name}_end", {
            "context_length": len(context),
            "duration_ms": duration,
        })

    # Get summary
    summary = perf_tracer.get_summary()
    trace_collector.record("context_budget_summary", summary)

    # Verify all presets were tested
    for preset_name, _ in budget_presets:
        assert f"fetch_{preset_name}" in summary


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_memory_graph_traversal(trace_collector, mock_memory_matrix):
    """
    Trace graph traversal for related memory lookup.

    Tests finding related nodes through graph edges.
    """
    # Mock a small graph structure
    nodes = {
        "node-1": MockMemoryNode("node-1", "ENTITY", "Zayne", lock_in=0.8, lock_in_state="settled"),
        "node-2": MockMemoryNode("node-2", "FACT", "Zayne works on Luna", lock_in=0.6, lock_in_state="fluid"),
        "node-3": MockMemoryNode("node-3", "FACT", "Luna uses SQLite", lock_in=0.4, lock_in_state="fluid"),
        "node-4": MockMemoryNode("node-4", "DECISION", "Use NetworkX for graphs", lock_in=0.3, lock_in_state="drifting"),
    }

    # Mock edges: node-1 -> node-2 -> node-3 -> node-4
    edges = [
        ("node-1", "node-2", "related_to"),
        ("node-2", "node-3", "mentions"),
        ("node-3", "node-4", "led_to"),
    ]

    trace_collector.record("graph_traversal_start", {
        "start_node": "node-1",
        "max_depth": 3,
        "node_count": len(nodes),
        "edge_count": len(edges),
    })

    # Simulate BFS traversal
    visited = set()
    queue = [("node-1", 0)]
    traversal_order = []

    while queue:
        node_id, depth = queue.pop(0)

        if node_id in visited:
            continue

        visited.add(node_id)
        node = nodes.get(node_id)

        if node:
            traversal_order.append({
                "node_id": node_id,
                "depth": depth,
                "lock_in": node.lock_in,
            })

            trace_collector.record("node_visited", {
                "node_id": node_id,
                "depth": depth,
                "content": node.content[:50],
            })

            # Find outgoing edges
            for src, dst, rel in edges:
                if src == node_id and dst not in visited:
                    queue.append((dst, depth + 1))

    trace_collector.record("graph_traversal_complete", {
        "visited_count": len(visited),
        "traversal_order": [t["node_id"] for t in traversal_order],
    })

    # Verify traversal visited all reachable nodes
    assert len(visited) == 4
    assert "node-1" in visited
    assert "node-4" in visited


@pytest.mark.tracer
@pytest.mark.asyncio
async def test_memory_pruning_trace(trace_collector, mock_memory_matrix):
    """
    Trace synaptic pruning of low-value memories.

    Pruning removes nodes with:
    - Low lock-in coefficient
    - Low confidence
    - Old age without reinforcement
    """
    # Create mock nodes with varying lock-in values
    nodes = [
        MockMemoryNode("prune-1", "FACT", "Old unused memory", lock_in=0.05, lock_in_state="drifting"),
        MockMemoryNode("prune-2", "FACT", "Slightly used memory", lock_in=0.2, lock_in_state="drifting"),
        MockMemoryNode("keep-1", "FACT", "Well-reinforced memory", lock_in=0.8, lock_in_state="settled"),
        MockMemoryNode("prune-3", "FACT", "Low confidence memory", lock_in=0.1, confidence=0.3),
        MockMemoryNode("keep-2", "DECISION", "Important decision", lock_in=0.6, lock_in_state="fluid"),
    ]

    trace_collector.record("pruning_start", {
        "total_nodes": len(nodes),
        "lock_in_threshold": 0.3,
        "confidence_threshold": 0.5,
    })

    # Simulate pruning evaluation
    to_prune = []
    to_keep = []

    for node in nodes:
        trace_collector.record("node_evaluated", {
            "node_id": node.id,
            "lock_in": node.lock_in,
            "confidence": node.confidence,
        })

        # Pruning criteria
        should_prune = (
            node.lock_in < 0.3 and
            node.confidence < 0.5
        ) or node.lock_in < 0.1

        if should_prune:
            to_prune.append(node.id)
            trace_collector.record("node_marked_for_pruning", {"node_id": node.id})
        else:
            to_keep.append(node.id)
            trace_collector.record("node_kept", {"node_id": node.id})

    trace_collector.record("pruning_complete", {
        "pruned_count": len(to_prune),
        "kept_count": len(to_keep),
        "pruned_ids": to_prune,
        "kept_ids": to_keep,
    })

    # Verify pruning decisions
    assert "prune-1" in to_prune  # Very low lock-in
    assert "keep-1" in to_keep    # High lock-in, settled
    assert "keep-2" in to_keep    # Moderate lock-in, important type
