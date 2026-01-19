"""
Tests for the Director planning layer.

The planning layer decides upfront whether to delegate to Claude
based on query complexity and explicit signals.
"""

import pytest
from luna.actors.director import DirectorActor


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
    async def test_simple_queries_no_delegation(self, director):
        """Simple queries should not trigger delegation."""
        assert await director._should_delegate("Hello Luna") is False
        assert await director._should_delegate("How are you?") is False

    @pytest.mark.asyncio
    async def test_fallback_without_hybrid(self, director):
        """Without HybridInference, should fall back to signal checks only."""
        # Ensure _hybrid is not set
        assert not hasattr(director, '_hybrid') or director._hybrid is None

        # Should still work based on signals
        assert await director._should_delegate("Research AI trends") is True
        assert await director._should_delegate("Hi there!") is False
