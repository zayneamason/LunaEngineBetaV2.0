"""
Tests for the Director planning layer and query routing.

The planning layer decides upfront whether to delegate to Claude
based on query complexity and explicit signals.

The router determines execution path (DIRECT, SIMPLE_PLAN, FULL_PLAN, BACKGROUND)
based on complexity estimation and signal detection.
"""

import pytest
from luna.actors.director import DirectorActor
from luna.agentic.router import QueryRouter, ExecutionPath


class TestDelegationSignals:
    """Test the _check_delegation_signals() method."""

    @pytest.fixture
    def director(self):
        """Create a Director without starting it."""
        return DirectorActor()

    def test_temporal_markers_trigger_delegation(self, director):
        """Temporal markers (current events) should trigger delegation."""
        assert director._check_delegation_signals("What's the latest news?") is True
        assert director._check_delegation_signals("Current status of the project") is True
        assert director._check_delegation_signals("What happened today?") is True
        assert director._check_delegation_signals("What about yesterday's meeting?") is True
        assert director._check_delegation_signals("Events in 2026") is True
        assert director._check_delegation_signals("What's happening right now?") is True
        assert director._check_delegation_signals("Recent developments in AI") is True

    def test_research_requests_trigger_delegation(self, director):
        """Research requests should trigger delegation."""
        assert director._check_delegation_signals("Search for AI papers") is True
        assert director._check_delegation_signals("Look up the population of Tokyo") is True
        assert director._check_delegation_signals("Research quantum computing") is True
        assert director._check_delegation_signals("Find out about the new policy") is True
        assert director._check_delegation_signals("What's happening with OpenAI?") is True
        assert director._check_delegation_signals("Any news about the election?") is True

    def test_code_requests_trigger_delegation(self, director):
        """Complex code generation requests should trigger delegation."""
        assert director._check_delegation_signals("Write a script to parse JSON") is True
        assert director._check_delegation_signals("Implement a binary tree") is True
        assert director._check_delegation_signals("Debug this code please") is True
        assert director._check_delegation_signals("Build a REST API for me") is True
        assert director._check_delegation_signals("Create a program that sorts files") is True
        assert director._check_delegation_signals("Fix this code: def foo()") is True

    def test_simple_queries_no_delegation(self, director):
        """Simple queries should NOT trigger delegation."""
        assert director._check_delegation_signals("Hello Luna") is False
        assert director._check_delegation_signals("How are you?") is False
        assert director._check_delegation_signals("Tell me a joke") is False
        assert director._check_delegation_signals("What do you think about that?") is False
        assert director._check_delegation_signals("I'm feeling tired") is False
        assert director._check_delegation_signals("Thanks for your help!") is False

    def test_personality_queries_no_delegation(self, director):
        """Personality/presence queries should stay local."""
        assert director._check_delegation_signals("What's your favorite color?") is False
        assert director._check_delegation_signals("Tell me about yourself") is False
        assert director._check_delegation_signals("How do you feel about music?") is False
        assert director._check_delegation_signals("Do you dream?") is False
        assert director._check_delegation_signals("What makes you happy?") is False

    def test_case_insensitivity(self, director):
        """Signal detection should be case-insensitive."""
        assert director._check_delegation_signals("WHAT'S THE LATEST NEWS?") is True
        assert director._check_delegation_signals("Search For Papers") is True
        assert director._check_delegation_signals("IMPLEMENT a function") is True


class TestShouldDelegate:
    """Test the _should_delegate() async method."""

    @pytest.fixture
    def director(self):
        """Create a Director without starting it."""
        return DirectorActor()

    @pytest.mark.asyncio
    async def test_explicit_signals_trigger_delegation(self, director):
        """Explicit signals should trigger delegation even without HybridInference."""
        # Director won't have _hybrid set since we didn't start it
        assert await director._should_delegate("What's the latest news?") is True
        assert await director._should_delegate("Write a script") is True

    @pytest.mark.asyncio
    async def test_always_delegates(self, director):
        """All queries delegate — fallback chain handles provider selection."""
        assert await director._should_delegate("Hello Luna") is True
        assert await director._should_delegate("How are you?") is True

    @pytest.mark.asyncio
    async def test_delegates_without_hybrid(self, director):
        """Without HybridInference, still delegates to fallback chain."""
        assert not hasattr(director, '_hybrid') or director._hybrid is None

        assert await director._should_delegate("Research AI trends") is True
        assert await director._should_delegate("Hi there!") is True


# =============================================================================
# QUERY ROUTER PATH FORCING TESTS
# =============================================================================

class TestQueryRouterPathForcing:
    """Test the QueryRouter path forcing behavior for memory and research queries."""

    @pytest.fixture
    def router(self):
        """Create a fresh QueryRouter instance."""
        return QueryRouter()

    def test_memory_query_forces_simple_plan(self, router):
        """Memory queries should be forced to SIMPLE_PLAN when forcing is enabled."""
        # Default: forcing is enabled
        assert router._force_memory_to_plan is True

        decision = router.analyze("do you remember alex?")
        assert decision.path == ExecutionPath.SIMPLE_PLAN
        assert "memory_query" in decision.signals
        assert decision.reason == "Memory query requires retrieval step"

    def test_memory_query_various_patterns(self, router):
        """Various memory query patterns should all route to SIMPLE_PLAN."""
        memory_queries = [
            "do you remember alex?",
            "what do you know about the project?",
            "recall our conversation yesterday",
            "who is sarah?",
            "tell me about the meeting",
            "check your memories for that",
        ]

        for query in memory_queries:
            decision = router.analyze(query)
            assert decision.path == ExecutionPath.SIMPLE_PLAN, f"Failed for: {query}"
            assert "memory_query" in decision.signals, f"No memory_query signal for: {query}"

    def test_memory_forcing_can_be_disabled(self, router):
        """When forcing is disabled, memory queries route based on complexity."""
        router._force_memory_to_plan = False

        # Short query = low complexity = DIRECT
        decision = router.analyze("remember?")
        assert decision.path == ExecutionPath.DIRECT

    def test_memory_min_complexity_floor(self, router):
        """Memory queries should have their complexity floored."""
        router._memory_min_complexity = 0.4

        decision = router.analyze("remember alex?")
        # Even though query is short, complexity should be at least 0.4
        assert decision.complexity >= 0.4
        assert decision.path == ExecutionPath.SIMPLE_PLAN

    def test_greeting_still_routes_direct(self, router):
        """Greetings should still route to DIRECT (no regression)."""
        greetings = [
            "hey luna!",
            "hello",
            "hi there",
            "good morning",
        ]

        for greeting in greetings:
            decision = router.analyze(greeting)
            assert decision.path == ExecutionPath.DIRECT, f"Failed for: {greeting}"

    def test_research_query_forces_full_plan(self, router):
        """Research queries should be forced to FULL_PLAN when forcing is enabled."""
        assert router._force_research_to_full is True

        decision = router.analyze("research the latest AI developments")
        assert decision.path == ExecutionPath.FULL_PLAN
        assert "research_request" in decision.signals
        assert decision.reason == "Research query requires multi-step planning"

    def test_research_forcing_can_be_disabled(self, router):
        """When forcing is disabled, research queries route based on complexity."""
        router._force_research_to_full = False

        # Without forcing, short research query goes based on complexity
        decision = router.analyze("research AI")
        # Complexity will be boosted by research patterns, but may not hit FULL threshold
        assert decision.path in [ExecutionPath.SIMPLE_PLAN, ExecutionPath.FULL_PLAN]

    def test_background_request_takes_priority(self, router):
        """Explicit background requests should override memory forcing."""
        decision = router.analyze("remember everything in the background")
        # Background pattern takes priority over memory pattern
        assert decision.path == ExecutionPath.BACKGROUND

    def test_memory_query_includes_tool_suggestion(self, router):
        """Memory queries should suggest the memory_query tool."""
        decision = router.analyze("do you remember our discussion?")
        assert "memory_query" in decision.suggested_tools


class TestQueryRouterComplexityEstimation:
    """Test the complexity estimation logic."""

    @pytest.fixture
    def router(self):
        return QueryRouter()

    def test_short_queries_low_complexity(self, router):
        """Short queries should have low base complexity."""
        complexity = router.estimate_complexity("hi")
        assert complexity < 0.2

    def test_long_queries_higher_complexity(self, router):
        """Longer queries should have higher complexity."""
        short = router.estimate_complexity("hi")
        long = router.estimate_complexity(
            "Please analyze the following document and provide a detailed summary "
            "with key points, action items, and recommendations for next steps."
        )
        assert long > short

    def test_research_keywords_increase_complexity(self, router):
        """Research keywords should increase complexity."""
        base = router.estimate_complexity("tell me about AI")
        research = router.estimate_complexity("research and analyze AI trends")
        assert research > base

    def test_greetings_reduce_complexity(self, router):
        """Greetings should reduce complexity."""
        greeting = router.estimate_complexity("Hello!")
        question = router.estimate_complexity("Hello, how does this work?")
        assert greeting < question
