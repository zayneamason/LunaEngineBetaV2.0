"""
Tests for LocalSubtaskRunner — Qwen 3B lightweight agentic subtasks.

Tests cover:
- SubtaskResult construction and failure factory
- Timeout enforcement (mock slow inference → success=False)
- JSON parse success and failure
- Intent classification validation (valid/invalid intents)
- Entity extraction validation (valid/invalid types)
- Query rewriting (deictic detection, length guard, no-context pass-through)
- Parallel phase runner
- QueryRouter.from_intent() mapping
- Scribe entity hint gating
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

from luna.inference.subtasks import (
    LocalSubtaskRunner,
    SubtaskResult,
    SubtaskPhaseResult,
)
from luna.agentic.router import QueryRouter, ExecutionPath, RoutingDecision


# ─── Helpers ──────────────────────────────────────────────────────────────────

@dataclass
class FakeGenerationResult:
    """Mock GenerationResult from LocalInference."""
    text: str
    tokens: int = 10
    latency_ms: float = 50.0
    tokens_per_second: float = 200.0
    from_cache: bool = False


def make_mock_local(response_text: str = "", delay: float = 0.0, loaded: bool = True):
    """Create a mock LocalInference that returns the given text."""
    mock = MagicMock()
    mock.is_loaded = loaded

    async def fake_generate(user_message, system_prompt=None, max_tokens=None):
        if delay > 0:
            await asyncio.sleep(delay)
        return FakeGenerationResult(text=response_text)

    mock.generate = AsyncMock(side_effect=fake_generate)
    return mock


# ─── SubtaskResult ────────────────────────────────────────────────────────────

class TestSubtaskResult:
    def test_success_result(self):
        r = SubtaskResult(success=True, output={"intent": "greeting"}, task_name="test")
        assert r.success is True
        assert r.output["intent"] == "greeting"

    def test_failed_factory(self):
        r = SubtaskResult.failed("classify_intent", latency_ms=150.0)
        assert r.success is False
        assert r.task_name == "classify_intent"
        assert r.latency_ms == 150.0
        assert r.output is None


# ─── Intent Classification ────────────────────────────────────────────────────

class TestClassifyIntent:
    @pytest.mark.asyncio
    async def test_valid_greeting(self):
        mock = make_mock_local('{"intent":"greeting","complexity":"trivial","tools":[]}')
        runner = LocalSubtaskRunner(mock)
        result = await runner.classify_intent("hey luna!")
        assert result.success is True
        assert result.output["intent"] == "greeting"
        assert result.output["complexity"] == "trivial"

    @pytest.mark.asyncio
    async def test_valid_memory_query(self):
        mock = make_mock_local('{"intent":"memory_query","complexity":"simple","tools":["memory_query"]}')
        runner = LocalSubtaskRunner(mock)
        result = await runner.classify_intent("do you remember Alex?")
        assert result.success is True
        assert result.output["intent"] == "memory_query"

    @pytest.mark.asyncio
    async def test_invalid_intent_fails(self):
        mock = make_mock_local('{"intent":"banana","complexity":"simple","tools":[]}')
        runner = LocalSubtaskRunner(mock)
        result = await runner.classify_intent("test")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_unparseable_json_fails(self):
        mock = make_mock_local("this is not json at all")
        runner = LocalSubtaskRunner(mock)
        result = await runner.classify_intent("test")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_json_in_markdown_fences(self):
        mock = make_mock_local('```json\n{"intent":"research","complexity":"moderate","tools":[]}\n```')
        runner = LocalSubtaskRunner(mock)
        result = await runner.classify_intent("research AI chips")
        assert result.success is True
        assert result.output["intent"] == "research"

    @pytest.mark.asyncio
    async def test_timeout_returns_failed(self):
        mock = make_mock_local('{"intent":"greeting","complexity":"trivial","tools":[]}', delay=1.0)
        runner = LocalSubtaskRunner(mock)
        result = await runner.classify_intent("hi", timeout_ms=50)
        assert result.success is False

    @pytest.mark.asyncio
    async def test_model_not_loaded(self):
        mock = make_mock_local(loaded=False)
        runner = LocalSubtaskRunner(mock)
        result = await runner.classify_intent("hi")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_invalid_complexity_defaults(self):
        mock = make_mock_local('{"intent":"greeting","complexity":"banana","tools":[]}')
        runner = LocalSubtaskRunner(mock)
        result = await runner.classify_intent("hi")
        assert result.success is True
        assert result.output["complexity"] == "simple"  # corrected to default


# ─── Entity Extraction ────────────────────────────────────────────────────────

class TestExtractEntities:
    @pytest.mark.asyncio
    async def test_extracts_person_and_project(self):
        mock = make_mock_local('{"entities":[{"name":"Alex","type":"person"},{"name":"Luna Engine","type":"project"}]}')
        runner = LocalSubtaskRunner(mock)
        result = await runner.extract_entities("Tell Alex about the Luna Engine")
        assert result.success is True
        assert len(result.output["entities"]) == 2
        assert result.output["entities"][0]["name"] == "Alex"
        assert result.output["entities"][1]["type"] == "project"

    @pytest.mark.asyncio
    async def test_no_entities_returns_empty(self):
        mock = make_mock_local('{"entities":[]}')
        runner = LocalSubtaskRunner(mock)
        result = await runner.extract_entities("lol ok")
        assert result.success is True
        assert len(result.output["entities"]) == 0

    @pytest.mark.asyncio
    async def test_invalid_entity_type_filtered(self):
        mock = make_mock_local('{"entities":[{"name":"Foo","type":"alien"},{"name":"Bar","type":"person"}]}')
        runner = LocalSubtaskRunner(mock)
        result = await runner.extract_entities("test")
        assert result.success is True
        assert len(result.output["entities"]) == 1
        assert result.output["entities"][0]["name"] == "Bar"

    @pytest.mark.asyncio
    async def test_missing_entities_key_fails(self):
        mock = make_mock_local('{"names":["Alex"]}')
        runner = LocalSubtaskRunner(mock)
        result = await runner.extract_entities("test")
        assert result.success is False

    @pytest.mark.asyncio
    async def test_timeout_returns_failed(self):
        mock = make_mock_local('{"entities":[]}', delay=1.0)
        runner = LocalSubtaskRunner(mock)
        result = await runner.extract_entities("test", timeout_ms=50)
        assert result.success is False


# ─── Query Rewriting ──────────────────────────────────────────────────────────

class TestRewriteQuery:
    @pytest.mark.asyncio
    async def test_no_deictic_markers_passes_through(self):
        """Messages without vague references should pass through without calling Qwen."""
        mock = make_mock_local()
        runner = LocalSubtaskRunner(mock)
        result = await runner.rewrite_query("What is the Luna Engine?", [])
        assert result.success is True
        assert result.output == "What is the Luna Engine?"
        assert result.latency_ms == 0.0  # Didn't call Qwen
        mock.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_deictic_marker_triggers_rewrite(self):
        mock = make_mock_local("What about the Eden API integration we discussed yesterday?")
        runner = LocalSubtaskRunner(mock)
        result = await runner.rewrite_query(
            "what about that thing from yesterday?",
            ["User: We discussed the Eden API integration yesterday"],
        )
        assert result.success is True
        assert "Eden API" in result.output

    @pytest.mark.asyncio
    async def test_no_context_passes_through(self):
        """Even with deictic markers, no context = pass through."""
        mock = make_mock_local()
        runner = LocalSubtaskRunner(mock)
        result = await runner.rewrite_query("what about that?", [])
        assert result.success is True
        assert result.output == "what about that?"
        mock.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_length_guard_discards_hallucination(self):
        """If rewrite is >2.5x original length, discard it."""
        long_hallucination = "x" * 200  # Way too long for a 10-char input
        mock = make_mock_local(long_hallucination)
        runner = LocalSubtaskRunner(mock)
        result = await runner.rewrite_query("what is it?", ["User: Some context"])
        assert result.success is False

    @pytest.mark.asyncio
    async def test_empty_rewrite_fails(self):
        mock = make_mock_local("")
        runner = LocalSubtaskRunner(mock)
        result = await runner.rewrite_query("what about that?", ["User: context"])
        assert result.success is False

    @pytest.mark.asyncio
    async def test_timeout_returns_failed(self):
        mock = make_mock_local("rewritten query", delay=1.0)
        runner = LocalSubtaskRunner(mock)
        result = await runner.rewrite_query(
            "what about that?", ["User: context"], timeout_ms=50,
        )
        assert result.success is False


# ─── Phase Runner ─────────────────────────────────────────────────────────────

class TestRunSubtaskPhase:
    @pytest.mark.asyncio
    async def test_all_succeed(self):
        mock = make_mock_local('{"intent":"greeting","complexity":"trivial","tools":[]}')
        runner = LocalSubtaskRunner(mock)

        # Override extract_entities to return a separate response
        async def fake_extract(msg, timeout_ms=300):
            return SubtaskResult(
                success=True, output={"entities": []}, raw_text="", task_name="extract_entities",
            )
        runner.extract_entities = fake_extract

        phase = await runner.run_subtask_phase("hey!", [])
        assert phase.intent is not None
        assert phase.intent["intent"] == "greeting"
        assert phase.entities is not None
        assert phase.rewritten_query is None  # "hey!" has no deictic markers

    @pytest.mark.asyncio
    async def test_model_unavailable_returns_empty(self):
        mock = make_mock_local(loaded=False)
        runner = LocalSubtaskRunner(mock)
        phase = await runner.run_subtask_phase("test", [])
        assert phase.intent is None
        assert phase.entities is None
        assert phase.rewritten_query is None


# ─── QueryRouter.from_intent() ───────────────────────────────────────────────

class TestRouterFromIntent:
    def test_greeting_routes_to_direct(self):
        router = QueryRouter()
        decision = router.from_intent({"intent": "greeting", "complexity": "trivial", "tools": []})
        assert decision.path == ExecutionPath.DIRECT

    def test_memory_query_routes_to_simple_plan(self):
        router = QueryRouter()
        decision = router.from_intent({"intent": "memory_query", "complexity": "simple", "tools": ["memory_query"]})
        assert decision.path == ExecutionPath.SIMPLE_PLAN

    def test_research_routes_to_full_plan(self):
        router = QueryRouter()
        decision = router.from_intent({"intent": "research", "complexity": "complex", "tools": []})
        assert decision.path == ExecutionPath.FULL_PLAN

    def test_creative_routes_to_simple_plan(self):
        router = QueryRouter()
        decision = router.from_intent({"intent": "creative", "complexity": "moderate", "tools": []})
        assert decision.path == ExecutionPath.SIMPLE_PLAN

    def test_unknown_intent_falls_back_to_direct(self):
        router = QueryRouter()
        decision = router.from_intent({"intent": "unknown_garbage", "complexity": "simple", "tools": []})
        # Falls back to DIRECT since no query provided
        assert decision.path == ExecutionPath.DIRECT

    def test_complexity_scoring(self):
        router = QueryRouter()
        trivial = router.from_intent({"intent": "greeting", "complexity": "trivial", "tools": []})
        complex_ = router.from_intent({"intent": "research", "complexity": "complex", "tools": []})
        assert trivial.complexity < complex_.complexity

    def test_tools_passed_through(self):
        router = QueryRouter()
        decision = router.from_intent({
            "intent": "dataroom", "complexity": "simple",
            "tools": ["dataroom_search", "memory_query"],
        })
        assert "dataroom_search" in decision.suggested_tools


# ─── Stats Tracking ───────────────────────────────────────────────────────────

class TestSubtaskStats:
    @pytest.mark.asyncio
    async def test_stats_track_successes(self):
        mock = make_mock_local('{"intent":"greeting","complexity":"trivial","tools":[]}')
        runner = LocalSubtaskRunner(mock)
        await runner.classify_intent("hi")
        await runner.classify_intent("hello")
        stats = runner.get_stats()
        assert stats["classify_intent"]["attempts"] == 2
        assert stats["classify_intent"]["successes"] == 2

    @pytest.mark.asyncio
    async def test_stats_track_failures(self):
        mock = make_mock_local("not json")
        runner = LocalSubtaskRunner(mock)
        await runner.classify_intent("hi")
        stats = runner.get_stats()
        assert stats["classify_intent"]["attempts"] == 1
        assert stats["classify_intent"]["failures"] == 1

    @pytest.mark.asyncio
    async def test_stats_track_timeouts(self):
        mock = make_mock_local("slow", delay=1.0)
        runner = LocalSubtaskRunner(mock)
        await runner.classify_intent("hi", timeout_ms=50)
        stats = runner.get_stats()
        assert stats["classify_intent"]["timeouts"] == 1
