"""
Query Router for Luna Engine
============================

Routes incoming queries to the appropriate execution path based on
estimated complexity. This is the critical optimization that keeps
simple queries fast while enabling complex agentic capabilities.

From Part XIV:
- 90% of queries should hit DIRECT or SIMPLE_PLAN
- Complex queries get full treatment when needed
- Background tasks run async with notification

Performance targets:
- DIRECT: <500ms (simple chat, greetings)
- SIMPLE_PLAN: 500ms-2s (memory query, simple tool)
- FULL_PLAN: 5-30s (complex task, multiple tools)
- BACKGROUND: Minutes (deep research, file processing)
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List
import logging
import re

logger = logging.getLogger(__name__)


class ExecutionPath(Enum):
    """
    Execution paths based on query complexity.

    Each path has different latency characteristics and capabilities.
    The router decides which path to use based on complexity estimation.
    """

    DIRECT = auto()
    """
    Skip planning entirely. Direct LLM call.
    Latency: <500ms
    Use case: Simple chat, greetings, quick questions
    """

    SIMPLE_PLAN = auto()
    """
    Single-step plan. One tool call or memory retrieval.
    Latency: 500ms-2s
    Use case: Memory query, simple tool execution
    """

    FULL_PLAN = auto()
    """
    Multi-step planning with observe/think/act loop.
    Latency: 5-30s
    Use case: Complex task, multiple tools, research
    """

    BACKGROUND = auto()
    """
    Async execution with notification when complete.
    Latency: Minutes
    Use case: Deep research, file processing, long-running tasks
    """


@dataclass
class RoutingDecision:
    """
    The router's decision about how to execute a query.

    Includes the chosen path and reasoning for transparency.
    """

    path: ExecutionPath
    """The execution path to use."""

    complexity: float
    """Estimated complexity (0.0-1.0)."""

    reason: str
    """Human-readable reason for the decision."""

    signals: List[str] = field(default_factory=list)
    """Signals that influenced the decision."""

    suggested_tools: List[str] = field(default_factory=list)
    """Tools that might be needed for this query."""


class QueryRouter:
    """
    Routes queries to the appropriate execution path.

    Uses a combination of:
    - Keyword/pattern detection (explicit signals)
    - Length and structure heuristics
    - Historical patterns (future: learned from outcomes)

    The goal is to minimize latency for simple queries while
    enabling full agentic capabilities when needed.

    Example:
        router = QueryRouter()
        path = router.route("Hello Luna!")  # DIRECT
        path = router.route("Research AI chips and summarize")  # FULL_PLAN
    """

    # Complexity thresholds for path selection
    DIRECT_THRESHOLD = 0.2
    SIMPLE_THRESHOLD = 0.5
    FULL_THRESHOLD = 0.8

    # Patterns that indicate specific paths
    GREETING_PATTERNS = [
        r"^(hi|hey|hello|good (morning|afternoon|evening))[\s,!.]*",
        r"^how are you",
        r"^what'?s up",
        r"^yo\b",
    ]

    SIMPLE_QUERY_PATTERNS = [
        r"^(what|who|when|where|why|how) (is|are|was|were|did|do|does)\b",
        r"^(tell me|explain|describe)\b",
        r"^(can you|could you) (tell|explain|describe)\b",
    ]

    RESEARCH_PATTERNS = [
        r"\b(research|investigate|find out|look up|search for)\b",
        r"\b(analyze|analyse|examine|study)\b",
        r"\b(compare|contrast|evaluate)\b",
        r"\b(latest|current|recent|today'?s?|this week)\b",
    ]

    MULTI_STEP_PATTERNS = [
        r"\b(and then|after that|next|also|additionally)\b",
        r"\b(first|second|third|finally)\b",
        r"\b(step by step|one by one)\b",
        r"\b(multiple|several|various)\b",
    ]

    TOOL_PATTERNS = {
        "read_file": [r"\bread\b.*\b(file|document)", r"\bopen\b.*\bfile\b"],
        "write_file": [r"\b(write|save|create)\b.*\bfile\b", r"\bwrite to\b"],
        "bash": [r"\brun\b.*\b(command|script)\b", r"\bexecute\b", r"\bbash\b"],
        "web_search": [r"\bsearch\b.*\bweb\b", r"\bgoogle\b", r"\blook up online\b"],
        "memory_query": [r"\bremember\b", r"\brecall\b", r"\bwhat did (I|we|you)\b"],
        "calendar": [r"\bcalendar\b", r"\bschedule\b", r"\bappointment\b", r"\bevent\b"],
    }

    BACKGROUND_PATTERNS = [
        r"\bin the background\b",
        r"\b(notify|tell) me when\b",
        r"\btake your time\b",
        r"\bno rush\b",
        r"\b(process|analyze|research) (all|everything|the whole)\b",
    ]

    def __init__(self):
        """Initialize the query router."""
        # Compile patterns for efficiency
        self._greeting_re = [re.compile(p, re.IGNORECASE) for p in self.GREETING_PATTERNS]
        self._simple_re = [re.compile(p, re.IGNORECASE) for p in self.SIMPLE_QUERY_PATTERNS]
        self._research_re = [re.compile(p, re.IGNORECASE) for p in self.RESEARCH_PATTERNS]
        self._multi_step_re = [re.compile(p, re.IGNORECASE) for p in self.MULTI_STEP_PATTERNS]
        self._background_re = [re.compile(p, re.IGNORECASE) for p in self.BACKGROUND_PATTERNS]
        self._tool_re = {
            tool: [re.compile(p, re.IGNORECASE) for p in patterns]
            for tool, patterns in self.TOOL_PATTERNS.items()
        }

    def route(self, query: str) -> ExecutionPath:
        """
        Route a query to the appropriate execution path.

        Args:
            query: The user's input query.

        Returns:
            The execution path to use.

        Example:
            >>> router = QueryRouter()
            >>> router.route("Hi!")
            ExecutionPath.DIRECT
            >>> router.route("Research the latest AI news")
            ExecutionPath.FULL_PLAN
        """
        decision = self.analyze(query)
        return decision.path

    def analyze(self, query: str) -> RoutingDecision:
        """
        Analyze a query and return a detailed routing decision.

        This provides more information than route() for debugging
        and transparency about why a path was chosen.

        Args:
            query: The user's input query.

        Returns:
            A RoutingDecision with path, complexity, and reasoning.
        """
        complexity = self.estimate_complexity(query)
        signals = self._detect_signals(query)
        suggested_tools = self._detect_tools(query)

        # Check for explicit background request
        if self._matches_any(query, self._background_re):
            return RoutingDecision(
                path=ExecutionPath.BACKGROUND,
                complexity=complexity,
                reason="Explicit background processing requested",
                signals=signals,
                suggested_tools=suggested_tools,
            )

        # Route based on complexity
        if complexity < self.DIRECT_THRESHOLD:
            path = ExecutionPath.DIRECT
            reason = "Simple query, no planning needed"
        elif complexity < self.SIMPLE_THRESHOLD:
            path = ExecutionPath.SIMPLE_PLAN
            reason = "Moderate complexity, single-step plan"
        elif complexity < self.FULL_THRESHOLD:
            path = ExecutionPath.FULL_PLAN
            reason = "Complex query, multi-step planning required"
        else:
            path = ExecutionPath.BACKGROUND
            reason = "Very complex query, background processing recommended"

        logger.debug(
            f"Routed query to {path.name}: complexity={complexity:.2f}, "
            f"signals={signals}, tools={suggested_tools}"
        )

        return RoutingDecision(
            path=path,
            complexity=complexity,
            reason=reason,
            signals=signals,
            suggested_tools=suggested_tools,
        )

    def estimate_complexity(self, query: str) -> float:
        """
        Estimate query complexity on a 0.0-1.0 scale.

        Factors:
        - Query length (longer = more complex)
        - Presence of research/analysis keywords
        - Multi-step indicators
        - Tool requirements
        - Greeting/simple patterns (reduce complexity)

        Args:
            query: The user's input query.

        Returns:
            Complexity score between 0.0 (trivial) and 1.0 (very complex).
        """
        # Start with base complexity from length
        # Short queries (< 20 chars) start very low
        # Long queries (> 200 chars) start higher
        length = len(query)
        if length < 20:
            complexity = 0.05
        elif length < 50:
            complexity = 0.15
        elif length < 100:
            complexity = 0.25
        elif length < 200:
            complexity = 0.35
        else:
            complexity = 0.45

        # Reduce for greetings
        if self._matches_any(query, self._greeting_re):
            complexity *= 0.3

        # Reduce for simple questions
        if self._matches_any(query, self._simple_re):
            complexity *= 0.7

        # Increase for research indicators
        if self._matches_any(query, self._research_re):
            complexity += 0.25

        # Increase for multi-step indicators
        if self._matches_any(query, self._multi_step_re):
            complexity += 0.2

        # Increase for tool requirements
        tools_needed = len(self._detect_tools(query))
        complexity += tools_needed * 0.1

        # Increase for question marks (multiple questions)
        question_count = query.count("?")
        if question_count > 1:
            complexity += (question_count - 1) * 0.1

        # Increase for explicit complexity words
        complexity_words = ["complex", "complicated", "detailed", "comprehensive", "thorough"]
        for word in complexity_words:
            if word in query.lower():
                complexity += 0.15
                break

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, complexity))

    def _detect_signals(self, query: str) -> List[str]:
        """Detect signals that influence routing."""
        signals = []

        if self._matches_any(query, self._greeting_re):
            signals.append("greeting")
        if self._matches_any(query, self._simple_re):
            signals.append("simple_question")
        if self._matches_any(query, self._research_re):
            signals.append("research_request")
        if self._matches_any(query, self._multi_step_re):
            signals.append("multi_step")
        if self._matches_any(query, self._background_re):
            signals.append("background_request")

        return signals

    def _detect_tools(self, query: str) -> List[str]:
        """Detect which tools might be needed for this query."""
        tools = []

        for tool_name, patterns in self._tool_re.items():
            if self._matches_any(query, patterns):
                tools.append(tool_name)

        return tools

    def _matches_any(self, text: str, patterns: List[re.Pattern]) -> bool:
        """Check if text matches any of the compiled patterns."""
        for pattern in patterns:
            if pattern.search(text):
                return True
        return False
