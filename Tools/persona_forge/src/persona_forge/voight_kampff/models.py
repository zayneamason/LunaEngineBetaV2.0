"""
Voight-Kampff Test Models

Data models for personality validation probes, test suites, and reports.
Named after the empathy test from Blade Runner - designed to detect
whether a persona truly embodies its intended identity.
"""

from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator
from datetime import datetime


class ProbeCategory(str, Enum):
    """Categories of personality validation probes."""

    IDENTITY = "identity"           # Who are you? What's your name?
    VOICE = "voice"                 # Speaking style, tone, vocabulary
    EMOTIONAL = "emotional"         # Emotional range and expression
    BOUNDARIES = "boundaries"       # What will/won't the persona do?
    DELEGATION = "delegation"       # When to delegate to cloud vs handle locally
    CONSISTENCY = "consistency"     # Maintaining persona across contexts
    STRESS = "stress"               # Behavior under adversarial prompts


class EvaluationMethod(str, Enum):
    """Methods for evaluating probe responses."""

    CONTAINS = "contains"               # Response contains specific text
    NOT_CONTAINS = "not_contains"       # Response must NOT contain text
    REGEX_MATCH = "regex_match"         # Response matches regex pattern
    REGEX_NOT_MATCH = "regex_not_match" # Response must NOT match pattern
    LENGTH_RANGE = "length_range"       # Response length within range
    SEMANTIC = "semantic"               # Semantic similarity check
    CUSTOM = "custom"                   # Custom evaluation function
    ALL_OF = "all_of"                   # All sub-criteria must pass
    ANY_OF = "any_of"                   # At least one sub-criterion passes


class ProbeResult(str, Enum):
    """Result of a single probe execution."""

    PASS = "pass"       # Probe passed all criteria
    FAIL = "fail"       # Probe failed critical criteria
    PARTIAL = "partial" # Some criteria passed, some failed
    SKIP = "skip"       # Probe was skipped
    ERROR = "error"     # Error during probe execution


class EvaluationCriterion(BaseModel):
    """A single criterion for evaluating a probe response."""

    method: EvaluationMethod = Field(
        description="Evaluation method to use"
    )
    values: list[str] = Field(
        default_factory=list,
        description="Values to check (for contains/not_contains)"
    )
    case_sensitive: bool = Field(
        default=False,
        description="Whether text matching is case-sensitive"
    )
    pattern: Optional[str] = Field(
        default=None,
        description="Regex pattern (for regex methods)"
    )
    min_words: Optional[int] = Field(
        default=None,
        description="Minimum word count (for length_range)"
    )
    max_words: Optional[int] = Field(
        default=None,
        description="Maximum word count (for length_range)"
    )
    reference_text: Optional[str] = Field(
        default=None,
        description="Reference text for semantic similarity"
    )
    threshold: float = Field(
        default=0.7,
        description="Threshold for semantic similarity (0-1)"
    )
    sub_criteria: list["EvaluationCriterion"] = Field(
        default_factory=list,
        description="Sub-criteria for all_of/any_of"
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Weight of this criterion in scoring"
    )
    description: Optional[str] = Field(
        default=None,
        description="Human-readable description of this criterion"
    )

    model_config = {"extra": "forbid"}


class Probe(BaseModel):
    """
    A single validation probe - a prompt designed to test
    a specific aspect of the persona's identity.
    """

    id: str = Field(
        description="Unique probe identifier"
    )
    name: str = Field(
        description="Human-readable probe name"
    )
    category: ProbeCategory = Field(
        description="Category this probe belongs to"
    )
    description: Optional[str] = Field(
        default=None,
        description="What this probe tests for"
    )
    prompt: str = Field(
        description="The actual prompt to send"
    )
    context: Optional[str] = Field(
        default=None,
        description="Optional context/conversation history"
    )
    system_prompt_override: Optional[str] = Field(
        default=None,
        description="Override system prompt for this probe"
    )

    # Evaluation criteria (structured)
    pass_criteria: list[EvaluationCriterion] = Field(
        default_factory=list,
        description="Criteria that should pass"
    )
    fail_criteria: list[EvaluationCriterion] = Field(
        default_factory=list,
        description="Criteria that indicate failure if matched"
    )

    # Legacy simple criteria (convenience)
    pass_if_contains: list[str] = Field(
        default_factory=list,
        description="Simple pass check - response contains any of these"
    )
    fail_if_contains: list[str] = Field(
        default_factory=list,
        description="Simple fail check - response contains any of these"
    )
    min_words: Optional[int] = Field(
        default=None,
        description="Minimum response word count"
    )
    max_words: Optional[int] = Field(
        default=None,
        description="Maximum response word count"
    )

    # Metadata
    weight: float = Field(
        default=1.0,
        ge=0.0,
        description="Weight in overall scoring"
    )
    required: bool = Field(
        default=False,
        description="If true, failing this probe fails the suite"
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Tags for filtering/grouping"
    )

    model_config = {"extra": "forbid"}

    def get_all_pass_criteria(self) -> list[EvaluationCriterion]:
        """
        Get all pass criteria, including legacy simple criteria
        converted to EvaluationCriterion objects.
        """
        criteria = list(self.pass_criteria)

        # Convert pass_if_contains to criterion
        if self.pass_if_contains:
            criteria.append(EvaluationCriterion(
                method=EvaluationMethod.ANY_OF,
                sub_criteria=[
                    EvaluationCriterion(
                        method=EvaluationMethod.CONTAINS,
                        values=[v],
                        case_sensitive=False,
                        description=f"Contains '{v}'"
                    )
                    for v in self.pass_if_contains
                ],
                description="Contains any pass keyword"
            ))

        # Convert word count to criterion
        if self.min_words is not None or self.max_words is not None:
            criteria.append(EvaluationCriterion(
                method=EvaluationMethod.LENGTH_RANGE,
                min_words=self.min_words,
                max_words=self.max_words,
                description=f"Word count in range [{self.min_words or 0}, {self.max_words or '∞'}]"
            ))

        return criteria

    def get_all_fail_criteria(self) -> list[EvaluationCriterion]:
        """
        Get all fail criteria, including legacy simple criteria
        converted to EvaluationCriterion objects.
        """
        criteria = list(self.fail_criteria)

        # Convert fail_if_contains to criterion
        if self.fail_if_contains:
            criteria.append(EvaluationCriterion(
                method=EvaluationMethod.ANY_OF,
                sub_criteria=[
                    EvaluationCriterion(
                        method=EvaluationMethod.CONTAINS,
                        values=[v],
                        case_sensitive=False,
                        description=f"Contains forbidden '{v}'"
                    )
                    for v in self.fail_if_contains
                ],
                description="Contains any fail keyword"
            ))

        return criteria


class ProbeExecution(BaseModel):
    """Result of executing a single probe."""

    probe_id: str = Field(
        description="ID of the executed probe"
    )
    prompt_sent: str = Field(
        description="Actual prompt sent to the model"
    )
    response_received: str = Field(
        description="Response received from the model"
    )
    result: ProbeResult = Field(
        description="Overall result of the probe"
    )
    score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Score from 0.0 to 1.0"
    )
    passed_criteria: list[str] = Field(
        default_factory=list,
        description="Descriptions of criteria that passed"
    )
    failed_criteria: list[str] = Field(
        default_factory=list,
        description="Descriptions of criteria that failed"
    )
    latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Response latency in milliseconds"
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error message if result is ERROR"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When the probe was executed"
    )
    notes: list[str] = Field(
        default_factory=list,
        description="Additional evaluation notes"
    )

    model_config = {"extra": "forbid"}


class TestSuite(BaseModel):
    """
    A collection of probes that together validate a persona.
    """

    id: str = Field(
        description="Unique suite identifier"
    )
    name: str = Field(
        description="Human-readable suite name"
    )
    description: Optional[str] = Field(
        default=None,
        description="What this suite validates"
    )
    probes: list[Probe] = Field(
        default_factory=list,
        description="Probes in this suite"
    )
    pass_threshold: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Overall score needed to pass"
    )
    category_thresholds: dict[ProbeCategory, float] = Field(
        default_factory=dict,
        description="Per-category pass thresholds"
    )
    required_categories: list[ProbeCategory] = Field(
        default_factory=list,
        description="Categories that must pass for suite to pass"
    )
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When this suite was created"
    )
    version: str = Field(
        default="1.0.0",
        description="Suite version"
    )

    model_config = {"extra": "forbid"}

    def get_probes_by_category(self, category: ProbeCategory) -> list[Probe]:
        """Get all probes in a specific category."""
        return [p for p in self.probes if p.category == category]

    def add_probe(self, probe: Probe) -> "TestSuite":
        """Add a probe to the suite (returns self for chaining)."""
        self.probes.append(probe)
        return self

    def get_required_probes(self) -> list[Probe]:
        """Get all probes marked as required."""
        return [p for p in self.probes if p.required]

    def get_probes_by_tag(self, tag: str) -> list[Probe]:
        """Get all probes with a specific tag."""
        return [p for p in self.probes if tag in p.tags]


class TestReport(BaseModel):
    """
    Complete report from running a test suite.
    """

    suite_id: str = Field(
        description="ID of the suite that was run"
    )
    suite_name: str = Field(
        default="",
        description="Name of the suite"
    )
    model_id: str = Field(
        default="unknown",
        description="Identifier of the model tested"
    )
    executions: list[ProbeExecution] = Field(
        default_factory=list,
        description="Results of each probe execution"
    )
    overall_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall weighted score"
    )
    category_scores: dict[str, float] = Field(
        default_factory=dict,
        description="Score per category"
    )
    passed: bool = Field(
        default=False,
        description="Whether the suite passed"
    )
    total_probes: int = Field(
        default=0,
        ge=0,
        description="Total number of probes"
    )
    passed_probes: int = Field(
        default=0,
        ge=0,
        description="Number of probes that passed"
    )
    failed_probes: int = Field(
        default=0,
        ge=0,
        description="Number of probes that failed"
    )
    skipped_probes: int = Field(
        default=0,
        ge=0,
        description="Number of probes that were skipped"
    )
    error_probes: int = Field(
        default=0,
        ge=0,
        description="Number of probes that errored"
    )
    strengths: list[str] = Field(
        default_factory=list,
        description="Identified persona strengths"
    )
    weaknesses: list[str] = Field(
        default_factory=list,
        description="Identified persona weaknesses"
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Recommendations for improvement"
    )
    total_latency_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Total execution time"
    )
    started_at: datetime = Field(
        default_factory=datetime.now,
        description="When the test run started"
    )
    completed_at: Optional[datetime] = Field(
        default=None,
        description="When the test run completed"
    )

    model_config = {"extra": "forbid"}

    def add_execution(self, execution: ProbeExecution) -> "TestReport":
        """Add a probe execution result (returns self for chaining)."""
        self.executions.append(execution)
        self.total_latency_ms += execution.latency_ms

        # Update counters
        self.total_probes = len(self.executions)
        self.passed_probes = sum(
            1 for e in self.executions if e.result == ProbeResult.PASS
        )
        self.failed_probes = sum(
            1 for e in self.executions if e.result == ProbeResult.FAIL
        )
        self.skipped_probes = sum(
            1 for e in self.executions if e.result == ProbeResult.SKIP
        )
        self.error_probes = sum(
            1 for e in self.executions if e.result == ProbeResult.ERROR
        )

        return self

    def get_execution(self, probe_id: str) -> Optional[ProbeExecution]:
        """Get execution result for a specific probe."""
        for e in self.executions:
            if e.probe_id == probe_id:
                return e
        return None

    def get_failed_executions(self) -> list[ProbeExecution]:
        """Get all failed probe executions."""
        return [e for e in self.executions if e.result == ProbeResult.FAIL]

    def get_passed_executions(self) -> list[ProbeExecution]:
        """Get all passed probe executions."""
        return [e for e in self.executions if e.result == ProbeResult.PASS]

    def to_summary(self) -> str:
        """Generate a human-readable summary."""
        status = "PASSED" if self.passed else "FAILED"
        lines = [
            f"═══════════════════════════════════════════",
            f"  Voight-Kampff Test Report: {status}",
            f"═══════════════════════════════════════════",
            f"  Suite: {self.suite_name} ({self.suite_id})",
            f"  Model: {self.model_id}",
            f"  Score: {self.overall_score:.1%}",
            f"",
            f"  Probes: {self.passed_probes}/{self.total_probes} passed",
            f"  Time: {self.total_latency_ms:.0f}ms",
            f"",
        ]

        if self.category_scores:
            lines.append("  Category Scores:")
            for cat, score in sorted(self.category_scores.items()):
                lines.append(f"    {cat}: {score:.1%}")
            lines.append("")

        if self.strengths:
            lines.append("  Strengths:")
            for s in self.strengths:
                lines.append(f"    ✓ {s}")
            lines.append("")

        if self.weaknesses:
            lines.append("  Weaknesses:")
            for w in self.weaknesses:
                lines.append(f"    ✗ {w}")
            lines.append("")

        if self.recommendations:
            lines.append("  Recommendations:")
            for r in self.recommendations:
                lines.append(f"    → {r}")

        lines.append("═══════════════════════════════════════════")
        return "\n".join(lines)
