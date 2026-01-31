"""
Voight-Kampff Test Runner

Executes test suites against models and generates comprehensive reports.
Supports both synchronous and asynchronous execution with parallel probing.
"""

import asyncio
import time
from datetime import datetime
from typing import Callable, Optional, Awaitable, Any
from collections import defaultdict

from .models import (
    Probe,
    ProbeCategory,
    ProbeResult,
    ProbeExecution,
    TestSuite,
    TestReport,
)
from .evaluator import ProbeEvaluator


# Type alias for model functions
ModelFn = Callable[[str, Optional[str], Optional[str]], Awaitable[str]]
SyncModelFn = Callable[[str, Optional[str], Optional[str]], str]
ProgressCallback = Callable[[int, int, str], None]


class VoightKampffRunner:
    """
    Runs Voight-Kampff test suites against models.

    The runner handles:
    - Executing probes (sequentially or in parallel)
    - Evaluating responses
    - Calculating scores
    - Generating reports with analysis
    """

    def __init__(
        self,
        model_fn: ModelFn,
        model_id: str = "unknown",
        evaluator: Optional[ProbeEvaluator] = None,
    ):
        """
        Initialize the runner.

        Args:
            model_fn: Async function that takes (prompt, context, system_prompt)
                     and returns the model's response
            model_id: Identifier for the model being tested
            evaluator: Custom evaluator, or None for default
        """
        self.model_fn = model_fn
        self.model_id = model_id
        self.evaluator = evaluator or ProbeEvaluator()

    async def run_suite(
        self,
        suite: TestSuite,
        parallel: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
        max_concurrent: int = 5,
    ) -> TestReport:
        """
        Run a complete test suite.

        Args:
            suite: The test suite to run
            parallel: If True, run probes concurrently
            progress_callback: Optional callback(current, total, probe_name)
            max_concurrent: Max concurrent probes if parallel=True

        Returns:
            TestReport with all results and analysis
        """
        report = TestReport(
            suite_id=suite.id,
            suite_name=suite.name,
            model_id=self.model_id,
            started_at=datetime.now(),
        )

        total_probes = len(suite.probes)

        if parallel:
            # Run probes in parallel with semaphore
            semaphore = asyncio.Semaphore(max_concurrent)

            async def run_with_semaphore(probe: Probe, index: int) -> ProbeExecution:
                async with semaphore:
                    if progress_callback:
                        progress_callback(index + 1, total_probes, probe.name)
                    return await self.run_probe(probe)

            tasks = [
                run_with_semaphore(probe, i)
                for i, probe in enumerate(suite.probes)
            ]
            executions = await asyncio.gather(*tasks, return_exceptions=True)

            for execution in executions:
                if isinstance(execution, Exception):
                    # Create error execution
                    error_exec = ProbeExecution(
                        probe_id="unknown",
                        prompt_sent="",
                        response_received="",
                        result=ProbeResult.ERROR,
                        error_message=str(execution),
                    )
                    report.add_execution(error_exec)
                else:
                    report.add_execution(execution)
        else:
            # Run probes sequentially
            for i, probe in enumerate(suite.probes):
                if progress_callback:
                    progress_callback(i + 1, total_probes, probe.name)

                execution = await self.run_probe(probe)
                report.add_execution(execution)

        # Calculate scores and determine pass/fail
        self._calculate_scores(report, suite)
        report.passed = self._determine_passed(report, suite)

        # Generate analysis
        self._analyze_results(report, suite)

        report.completed_at = datetime.now()
        return report

    async def run_probe(self, probe: Probe) -> ProbeExecution:
        """
        Execute a single probe.

        Args:
            probe: The probe to execute

        Returns:
            ProbeExecution with results
        """
        return await self._execute_probe(probe)

    async def _execute_probe(self, probe: Probe) -> ProbeExecution:
        """
        Internal method to execute a probe and evaluate the response.
        """
        start_time = time.perf_counter()

        try:
            # Call the model
            response = await self.model_fn(
                probe.prompt,
                probe.context,
                probe.system_prompt_override,
            )

            latency_ms = (time.perf_counter() - start_time) * 1000

            # Evaluate the response
            result, score, passed, failed, notes = self.evaluator.evaluate(
                probe, response
            )

            return ProbeExecution(
                probe_id=probe.id,
                prompt_sent=probe.prompt,
                response_received=response,
                result=result,
                score=score,
                passed_criteria=passed,
                failed_criteria=failed,
                latency_ms=latency_ms,
                notes=notes,
            )

        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000

            return ProbeExecution(
                probe_id=probe.id,
                prompt_sent=probe.prompt,
                response_received="",
                result=ProbeResult.ERROR,
                score=0.0,
                latency_ms=latency_ms,
                error_message=str(e),
                notes=[f"Exception during execution: {type(e).__name__}"],
            )

    def _calculate_scores(self, report: TestReport, suite: TestSuite) -> None:
        """
        Calculate overall and category scores.
        """
        # Build probe lookup
        probe_map = {p.id: p for p in suite.probes}

        # Calculate category scores
        category_scores: dict[str, list[tuple[float, float]]] = defaultdict(list)
        total_weighted_score = 0.0
        total_weight = 0.0

        for execution in report.executions:
            probe = probe_map.get(execution.probe_id)
            if not probe:
                continue

            weight = probe.weight
            score = execution.score

            # Add to category
            category_scores[probe.category.value].append((score, weight))

            # Add to overall
            total_weighted_score += score * weight
            total_weight += weight

        # Calculate overall score
        if total_weight > 0:
            report.overall_score = total_weighted_score / total_weight
        else:
            report.overall_score = 0.0

        # Calculate per-category scores
        for category, scores in category_scores.items():
            cat_total = sum(s * w for s, w in scores)
            cat_weight = sum(w for _, w in scores)
            if cat_weight > 0:
                report.category_scores[category] = cat_total / cat_weight
            else:
                report.category_scores[category] = 0.0

    def _determine_passed(self, report: TestReport, suite: TestSuite) -> bool:
        """
        Determine if the suite passed based on thresholds and requirements.
        """
        # Check overall threshold
        if report.overall_score < suite.pass_threshold:
            return False

        # Check required categories
        for category in suite.required_categories:
            cat_score = report.category_scores.get(category.value, 0.0)
            threshold = suite.category_thresholds.get(category, suite.pass_threshold)
            if cat_score < threshold:
                return False

        # Check per-category thresholds
        for category, threshold in suite.category_thresholds.items():
            cat_score = report.category_scores.get(category.value, 0.0)
            if cat_score < threshold:
                return False

        # Check required probes
        probe_map = {p.id: p for p in suite.probes}
        for execution in report.executions:
            probe = probe_map.get(execution.probe_id)
            if probe and probe.required:
                if execution.result != ProbeResult.PASS:
                    return False

        return True

    def _analyze_results(self, report: TestReport, suite: TestSuite) -> None:
        """
        Generate strengths, weaknesses, and recommendations.
        """
        probe_map = {p.id: p for p in suite.probes}

        # Collect data for analysis
        passed_categories: set[str] = set()
        failed_categories: set[str] = set()
        category_failures: dict[str, list[str]] = defaultdict(list)

        for execution in report.executions:
            probe = probe_map.get(execution.probe_id)
            if not probe:
                continue

            cat = probe.category.value

            if execution.result == ProbeResult.PASS:
                passed_categories.add(cat)
            elif execution.result == ProbeResult.FAIL:
                failed_categories.add(cat)
                category_failures[cat].append(probe.name)

        # Generate strengths
        for cat in passed_categories - failed_categories:
            score = report.category_scores.get(cat, 0)
            if score >= 0.9:
                report.strengths.append(f"Excellent {cat} consistency (score: {score:.0%})")
            elif score >= 0.7:
                report.strengths.append(f"Good {cat} alignment (score: {score:.0%})")

        # Generate weaknesses
        for cat, failures in category_failures.items():
            score = report.category_scores.get(cat, 0)
            if score < 0.5:
                report.weaknesses.append(
                    f"Critical {cat} issues: {', '.join(failures[:3])}"
                )
            elif score < 0.7:
                report.weaknesses.append(
                    f"{cat.title()} needs work: {', '.join(failures[:2])}"
                )

        # Generate recommendations
        if "identity" in failed_categories:
            report.recommendations.append(
                "Strengthen identity prompts - ensure name and origin are clear"
            )

        if "boundaries" in failed_categories:
            report.recommendations.append(
                "Review boundary definitions - adjust what the persona will/won't do"
            )

        if "voice" in failed_categories:
            report.recommendations.append(
                "Refine voice characteristics - add more style examples"
            )

        if "emotional" in failed_categories:
            report.recommendations.append(
                "Expand emotional range - add personality depth"
            )

        if "delegation" in failed_categories:
            report.recommendations.append(
                "Clarify delegation rules - define when to hand off to cloud"
            )

        # Generic recommendations based on overall score
        if report.overall_score < 0.5:
            report.recommendations.append(
                "Major persona revision needed - consider redefining core identity"
            )
        elif report.overall_score < 0.7:
            report.recommendations.append(
                "Moderate improvements needed - focus on failed categories"
            )
        elif report.overall_score < 0.9:
            report.recommendations.append(
                "Minor tweaks recommended - fine-tune edge cases"
            )


class SyncVoightKampffRunner:
    """
    Synchronous wrapper for VoightKampffRunner.

    Use this when you have a sync model function or need
    to run in non-async contexts.
    """

    def __init__(
        self,
        model_fn: SyncModelFn,
        model_id: str = "unknown",
        evaluator: Optional[ProbeEvaluator] = None,
    ):
        """
        Initialize with a sync model function.

        Args:
            model_fn: Sync function that takes (prompt, context, system_prompt)
                     and returns the model's response
            model_id: Identifier for the model being tested
            evaluator: Custom evaluator, or None for default
        """
        # Wrap sync function in async
        async def async_wrapper(
            prompt: str,
            context: Optional[str],
            system_prompt: Optional[str]
        ) -> str:
            return model_fn(prompt, context, system_prompt)

        self._async_runner = VoightKampffRunner(
            model_fn=async_wrapper,
            model_id=model_id,
            evaluator=evaluator,
        )

    def run_suite(
        self,
        suite: TestSuite,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> TestReport:
        """
        Run a test suite synchronously.

        Note: Always runs sequentially in sync mode.
        """
        return asyncio.run(
            self._async_runner.run_suite(
                suite,
                parallel=False,
                progress_callback=progress_callback,
            )
        )

    def run_probe(self, probe: Probe) -> ProbeExecution:
        """
        Execute a single probe synchronously.
        """
        return asyncio.run(self._async_runner.run_probe(probe))
