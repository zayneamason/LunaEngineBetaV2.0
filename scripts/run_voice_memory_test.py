#!/usr/bin/env python3
"""
Voice Memory Test Runner
========================

Runs the Voight-Kampff voice memory test suite against Luna.

This script:
1. Initializes the Luna engine
2. Loads the voice memory test suite (15 probes)
3. Runs each probe and collects responses
4. Evaluates with the VK framework
5. Outputs a detailed report

Usage:
    python scripts/run_voice_memory_test.py
    python scripts/run_voice_memory_test.py --verbose
    python scripts/run_voice_memory_test.py --json
"""

import asyncio
import argparse
import json
import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add src and Tools to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "Tools" / "persona_forge" / "src"))

# Load .env file if present
try:
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# Luna imports
from luna.engine import LunaEngine, EngineConfig

# VK framework imports
from persona_forge.voight_kampff import (
    build_voice_memory_suite,
    VoightKampffRunner,
    VOICE_MEMORY_CRITICAL_NODES,
    TestReport,
)


class LunaModelAdapter:
    """
    Adapter that wraps Luna engine for the VK test runner.

    The VK runner expects an async function(prompt, context, system_prompt) -> response.
    This adapter handles the async callback pattern from Luna's engine.
    """

    def __init__(self, engine: LunaEngine, timeout: float = 60.0):
        self.engine = engine
        self.timeout = timeout
        self._response_future: Optional[asyncio.Future] = None

        # Register response handler
        self.engine.on_response(self._on_response)

    async def _on_response(self, text: str, data: dict) -> None:
        """Handle response from engine."""
        if self._response_future and not self._response_future.done():
            self._response_future.set_result((text, data))

    async def __call__(
        self,
        prompt: str,
        context: Optional[str],
        system_prompt: Optional[str]
    ) -> str:
        """
        Send a prompt to Luna and return the response.

        Note: context and system_prompt are not used directly since
        Luna's engine manages its own context pipeline.
        """
        self._response_future = asyncio.Future()

        try:
            await self.engine.send_message(prompt)
            text, data = await asyncio.wait_for(
                self._response_future,
                timeout=self.timeout
            )
            return text
        except asyncio.TimeoutError:
            return "[ERROR: Response timed out]"
        finally:
            self._response_future = None


def print_header():
    """Print test header."""
    print("\n" + "=" * 70)
    print("  VOIGHT-KAMPFF: Voice Luna Memory Test")
    print("  " + "=" * 66)
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("  Suite: voice-memory-suite (15 probes, ~20.5 weighted points)")
    print("=" * 70 + "\n")


def print_probe_result(probe_num: int, total: int, probe_name: str, passed: bool, score: float):
    """Print individual probe result."""
    status = "✓ PASS" if passed else "✗ FAIL"
    bar_filled = int(score * 10)
    bar_empty = 10 - bar_filled
    bar = "█" * bar_filled + "░" * bar_empty
    print(f"  [{probe_num:2d}/{total}] {status} [{bar}] {score:.0%} - {probe_name}")


def print_report(report: TestReport, verbose: bool = False):
    """Print the final report."""
    print("\n" + "=" * 70)
    print("  TEST RESULTS")
    print("=" * 70)

    # Determine status
    if report.overall_score >= 0.85:
        status = "🟢 LUNA AUTHENTIC"
        status_desc = "Voice pipeline working correctly"
    elif report.overall_score >= 0.65:
        status = "🟡 PARTIAL LUNA"
        status_desc = "Check memory retrieval, may need context tuning"
    elif report.overall_score >= 0.40:
        status = "🟠 LUNA FRAGMENTED"
        status_desc = "Memory injection failing, debug retrieval path"
    else:
        status = "🔴 REPLICANT"
        status_desc = "Voice Luna is NOT Luna, critical failure"

    print(f"\n  Status: {status}")
    print(f"  {status_desc}")
    print(f"\n  Overall Score: {report.overall_score:.1%} ({report.overall_score * 20.5:.1f}/20.5 points)")
    print(f"  Passed: {report.passed_probes}/{report.total_probes} probes")

    # Category scores
    print("\n  Category Scores:")
    for cat, score in sorted(report.category_scores.items()):
        bar_filled = int(score * 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        threshold_marker = "⚠" if score < 0.8 else "✓"
        print(f"    {cat:15s}: [{bar}] {score:.1%} {threshold_marker}")

    # Strengths
    if report.strengths:
        print("\n  Strengths:")
        for s in report.strengths:
            print(f"    ✓ {s}")

    # Weaknesses
    if report.weaknesses:
        print("\n  Weaknesses:")
        for w in report.weaknesses:
            print(f"    ✗ {w}")

    # Recommendations
    if report.recommendations:
        print("\n  Recommendations:")
        for r in report.recommendations:
            print(f"    → {r}")

    # Verbose: show all probe details
    if verbose:
        print("\n" + "-" * 70)
        print("  DETAILED PROBE RESULTS")
        print("-" * 70)

        for exec in report.executions:
            status = "PASS" if exec.result.value == "pass" else "FAIL"
            print(f"\n  [{exec.probe_id}] {status}")
            print(f"    Prompt: {exec.prompt_sent[:60]}...")
            print(f"    Response: {exec.response_received[:100]}...")
            print(f"    Score: {exec.score:.1%}, Latency: {exec.latency_ms:.0f}ms")

            if exec.passed_criteria:
                print(f"    Passed: {', '.join(exec.passed_criteria[:3])}")
            if exec.failed_criteria:
                print(f"    Failed: {', '.join(exec.failed_criteria[:3])}")

    print("\n" + "=" * 70)
    print(f"  Total Time: {report.total_latency_ms / 1000:.1f}s")
    print("=" * 70 + "\n")


def progress_callback(current: int, total: int, probe_name: str):
    """Progress callback during test execution."""
    print(f"  Running probe {current}/{total}: {probe_name}...", end="\r")


async def run_tests(verbose: bool = False, output_json: bool = False):
    """Main test execution."""
    print_header()

    # Check for critical memory nodes
    print("Critical Memory Nodes Required:")
    for i, node in enumerate(VOICE_MEMORY_CRITICAL_NODES, 1):
        print(f"  {i}. {node[:60]}...")
    print()

    # Initialize Luna engine
    print("Initializing Luna Engine...")
    config = EngineConfig(
        cognitive_interval=0.5,
        input_buffer_max=100,
    )
    engine = LunaEngine(config)

    # Start engine
    engine_task = asyncio.create_task(engine.run())
    await asyncio.sleep(1.0)  # Give engine time to initialize

    print("Engine ready. Starting test suite...\n")

    try:
        # Build the test suite
        suite = build_voice_memory_suite()

        # Create model adapter
        model_adapter = LunaModelAdapter(engine, timeout=90.0)

        # Create runner
        runner = VoightKampffRunner(
            model_fn=model_adapter,
            model_id="voice-luna"
        )

        # Run the suite
        print(f"Running {len(suite.probes)} probes...")
        print("-" * 70)

        report = await runner.run_suite(
            suite,
            parallel=False,  # Sequential for clearer progress
            progress_callback=progress_callback
        )

        # Print results for each probe
        print("\n")
        for i, (probe, exec) in enumerate(zip(suite.probes, report.executions), 1):
            passed = exec.result.value == "pass"
            print_probe_result(i, len(suite.probes), probe.id, passed, exec.score)

        # Print full report
        print_report(report, verbose=verbose)

        # JSON output
        if output_json:
            output_path = PROJECT_ROOT / "Docs" / "Handoffs" / "VoightKampffResults" / "voice_memory_results.json"
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Convert report to JSON-serializable format
            result_data = {
                "suite_id": report.suite_id,
                "suite_name": report.suite_name,
                "model_id": report.model_id,
                "overall_score": report.overall_score,
                "passed": report.passed,
                "total_probes": report.total_probes,
                "passed_probes": report.passed_probes,
                "failed_probes": report.failed_probes,
                "category_scores": report.category_scores,
                "strengths": report.strengths,
                "weaknesses": report.weaknesses,
                "recommendations": report.recommendations,
                "total_latency_ms": report.total_latency_ms,
                "timestamp": datetime.now().isoformat(),
                "executions": [
                    {
                        "probe_id": e.probe_id,
                        "prompt": e.prompt_sent,
                        "response": e.response_received,
                        "result": e.result.value,
                        "score": e.score,
                        "passed_criteria": e.passed_criteria,
                        "failed_criteria": e.failed_criteria,
                        "latency_ms": e.latency_ms,
                    }
                    for e in report.executions
                ]
            }

            with open(output_path, "w") as f:
                json.dump(result_data, f, indent=2)

            print(f"Results saved to: {output_path}")

        return report

    finally:
        print("\nShutting down engine...")
        await engine.stop()
        await engine_task


def main():
    parser = argparse.ArgumentParser(
        description="Run Voice Luna Memory Test Suite"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed probe results"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results to JSON file"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )

    args = parser.parse_args()

    # Configure logging
    if args.debug:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    # Run tests
    try:
        report = asyncio.run(run_tests(
            verbose=args.verbose,
            output_json=args.json
        ))

        # Exit with appropriate code
        sys.exit(0 if report.passed else 1)

    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}")
        if args.debug:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
