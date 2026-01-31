#!/usr/bin/env python3
"""
Luna Engine Tuning CLI
======================

Interactive CLI for tuning Luna's parameters.

Usage:
    python scripts/tune.py new --focus memory    # Start new session
    python scripts/tune.py eval                  # Run evaluation
    python scripts/tune.py set <param> <value>   # Set parameter
    python scripts/tune.py sweep <param> <min> <max> <step>  # Grid search
    python scripts/tune.py compare [iter1] [iter2]  # Compare iterations
    python scripts/tune.py export <file>         # Export best params
    python scripts/tune.py list                  # List params
    python scripts/tune.py sessions              # List sessions
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from luna.tuning.params import ParamRegistry, TUNABLE_PARAMS
from luna.tuning.evaluator import Evaluator, EvalResults
from luna.tuning.session import TuningSessionManager, TuningSession


class TuningCLI:
    """CLI interface for Luna tuning."""

    def __init__(self):
        self.registry = ParamRegistry()
        self.evaluator = Evaluator()
        self.session_manager = TuningSessionManager()
        self._engine = None

    async def initialize(self, connect_engine: bool = True):
        """Initialize the CLI with optional engine connection."""
        await self.session_manager.initialize()

        if connect_engine:
            try:
                from luna.engine import LunaEngine
                self._engine = LunaEngine()
                await self._engine.start()
                self.registry = ParamRegistry(self._engine)
                self.evaluator = Evaluator(self._engine)
                print("Connected to Luna Engine")
            except Exception as e:
                print(f"Could not connect to engine: {e}")
                print("Running in standalone mode (mock responses)")

    async def cmd_new(self, focus: str = "all", notes: str = ""):
        """Start a new tuning session."""
        base_params = self.registry.get_all()
        session = await self.session_manager.new_session(
            focus=focus,
            base_params=base_params,
            notes=notes,
        )

        print(f"\nNew tuning session started")
        print(f"  ID: {session.session_id[:8]}...")
        print(f"  Focus: {focus}")
        print(f"  Base params: {len(base_params)} parameters")

        # Run baseline evaluation
        print("\nRunning baseline evaluation...")
        results = await self.evaluator.run_all()

        await self.session_manager.add_iteration(
            params_changed={},
            param_snapshot=base_params,
            eval_results=results,
            notes="Baseline",
        )

        self._print_results(results)
        return session

    async def cmd_eval(self, category: str = None):
        """Run evaluation."""
        if category:
            print(f"\nRunning {category} evaluation...")
            results = await self.evaluator.run_category(category)
        else:
            print("\nRunning full evaluation...")
            results = await self.evaluator.run_all()

        # Record iteration if session active
        if self.session_manager.current_session:
            await self.session_manager.add_iteration(
                params_changed={},
                param_snapshot=self.registry.get_all(),
                eval_results=results,
                notes=f"Eval: {category or 'all'}",
            )

        self._print_results(results)
        return results

    async def cmd_set(self, param: str, value: str):
        """Set a parameter value."""
        # Parse value
        try:
            # Try int first
            parsed = int(value)
        except ValueError:
            try:
                # Try float
                parsed = float(value)
            except ValueError:
                # Keep as string
                parsed = value

        prev = self.registry.set(param, parsed)
        print(f"\n{param}: {prev} -> {parsed}")

        # Run evaluation if session active
        if self.session_manager.current_session:
            print("\nRunning evaluation...")
            results = await self.evaluator.run_all()

            await self.session_manager.add_iteration(
                params_changed={param: parsed},
                param_snapshot=self.registry.get_all(),
                eval_results=results,
                notes=f"Set {param}={parsed}",
            )

            self._print_results(results)
            return results

    async def cmd_sweep(self, param: str, min_val: float, max_val: float, step: float):
        """Grid search over a parameter range."""
        print(f"\nSweeping {param} from {min_val} to {max_val} (step={step})")

        original = self.registry.get(param)
        results = []

        current = min_val
        iteration = 1
        while current <= max_val:
            print(f"\n--- Iteration {iteration}: {param}={current} ---")
            self.registry.set(param, current)

            eval_results = await self.evaluator.run_all()

            if self.session_manager.current_session:
                await self.session_manager.add_iteration(
                    params_changed={param: current},
                    param_snapshot=self.registry.get_all(),
                    eval_results=eval_results,
                    notes=f"Sweep {param}={current}",
                )

            results.append({
                "value": current,
                "score": eval_results.overall_score,
                "memory": eval_results.memory_recall_score,
                "context": eval_results.context_retention_score,
                "latency": eval_results.avg_latency_ms,
            })

            current += step
            iteration += 1

        # Find best
        best = max(results, key=lambda r: r["score"])
        print(f"\n=== Sweep Results ===")
        print(f"Best value: {best['value']} (score={best['score']:.3f})")
        print(f"\nAll results:")
        for r in results:
            marker = " <-- BEST" if r["value"] == best["value"] else ""
            print(f"  {param}={r['value']}: score={r['score']:.3f}{marker}")

        # Restore original if not best
        print(f"\nSetting {param} to best value: {best['value']}")
        self.registry.set(param, best["value"])

        return results

    async def cmd_compare(self, iter1: int = None, iter2: int = None):
        """Compare iterations."""
        session = self.session_manager.current_session
        if not session:
            print("No active session")
            return

        if not session.iterations:
            print("No iterations to compare")
            return

        # Default: compare first and last
        if iter1 is None:
            iter1 = 1
        if iter2 is None:
            iter2 = len(session.iterations)

        comparison = self.session_manager.compare_iterations(iter1, iter2)

        print(f"\n=== Comparison: Iteration {iter1} vs {iter2} ===")
        print(f"\nScore: {comparison['score_1']:.3f} -> {comparison['score_2']:.3f} ({comparison['score_diff']:+.3f})")

        if comparison["param_diffs"]:
            print(f"\nParameter changes:")
            for param, diff in comparison["param_diffs"].items():
                print(f"  {param}: {diff['from']} -> {diff['to']}")

        print(f"\nMetric changes:")
        for metric, diff in comparison["metric_diffs"].items():
            direction = "+" if diff > 0 else ""
            print(f"  {metric}: {direction}{diff:.3f}")

        return comparison

    async def cmd_export(self, filepath: str):
        """Export best parameters to file."""
        session = self.session_manager.current_session
        if session:
            params = self.session_manager.get_best_params()
            source = f"session {session.session_id[:8]}, iteration {session.best_iteration}"
        else:
            params = self.registry.get_all()
            source = "current state"

        with open(filepath, "w") as f:
            json.dump(params, f, indent=2)

        print(f"\nExported {len(params)} parameters to {filepath}")
        print(f"Source: {source}")

    async def cmd_import(self, filepath: str):
        """Import parameters from file."""
        with open(filepath) as f:
            params = json.load(f)

        count = self.registry.import_params(params)
        print(f"\nImported {count} parameters from {filepath}")

        if self.session_manager.current_session:
            print("Running evaluation...")
            results = await self.evaluator.run_all()
            await self.session_manager.add_iteration(
                params_changed=params,
                param_snapshot=self.registry.get_all(),
                eval_results=results,
                notes=f"Import from {filepath}",
            )
            self._print_results(results)

    async def cmd_list(self, category: str = None):
        """List parameters."""
        params = self.registry.list_params(category)

        if category:
            print(f"\n=== {category.upper()} Parameters ===")
        else:
            print(f"\n=== All Parameters ({len(params)}) ===")

        current_cat = None
        for name in sorted(params):
            spec = self.registry.get_spec(name)
            value = self.registry.get(name)

            # Print category header
            if spec.category != current_cat:
                current_cat = spec.category
                print(f"\n[{current_cat}]")

            # Indicate if overridden
            marker = "*" if name in self.registry._overrides else " "
            print(f"  {marker} {name}: {value} (default={spec.default}, bounds={spec.bounds})")

    async def cmd_sessions(self, limit: int = 10):
        """List recent sessions."""
        sessions = await self.session_manager.list_sessions(limit)

        print(f"\n=== Recent Tuning Sessions ===")
        if not sessions:
            print("  No sessions found")
            return

        for s in sessions:
            status = "active" if not s["ended_at"] else "ended"
            print(f"\n  {s['session_id'][:8]}...")
            print(f"    Focus: {s['focus']}, Status: {status}")
            print(f"    Iterations: {s['iterations']}, Best score: {s['best_score']:.3f}")
            print(f"    Started: {s['started_at']}")

    async def cmd_reset(self, param: str = None):
        """Reset parameter(s) to default."""
        if param:
            prev = self.registry.reset(param)
            if prev is not None:
                print(f"Reset {param} to default")
            else:
                print(f"{param} was not overridden")
        else:
            count = self.registry.reset_all()
            print(f"Reset {count} parameters to defaults")

    async def cmd_info(self, param: str):
        """Show detailed info about a parameter."""
        spec = self.registry.get_spec(param)
        value = self.registry.get(param)
        is_override = param in self.registry._overrides

        print(f"\n=== {param} ===")
        print(f"  Current value: {value}")
        print(f"  Default: {spec.default}")
        print(f"  Bounds: {spec.bounds}")
        print(f"  Step: {spec.step}")
        print(f"  Category: {spec.category}")
        print(f"  Overridden: {is_override}")
        print(f"\n  {spec.description}")

    def _print_results(self, results: EvalResults):
        """Print evaluation results."""
        print(f"\n=== Evaluation Results ===")
        print(f"Overall Score: {results.overall_score:.3f}")
        print(f"\nCategory Scores:")
        print(f"  Memory Recall:      {results.memory_recall_score:.3f}")
        print(f"  Context Retention:  {results.context_retention_score:.3f}")
        print(f"  Routing:            {results.routing_score:.3f}")
        print(f"\nLatency:")
        print(f"  Average: {results.avg_latency_ms:.0f}ms")
        print(f"  P95:     {results.p95_latency_ms:.0f}ms")
        print(f"\nTests: {results.passed_tests}/{results.total_tests} passed")

        # Show failed tests
        failed = [r for r in results.results if not r.passed]
        if failed:
            print(f"\nFailed tests:")
            for r in failed[:5]:
                print(f"  - {r.test.name}: {r.error or 'did not meet criteria'}")


async def main():
    parser = argparse.ArgumentParser(
        description="Luna Engine Tuning CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # new
    p_new = subparsers.add_parser("new", help="Start new tuning session")
    p_new.add_argument("--focus", "-f", default="all", choices=["memory", "routing", "latency", "context", "all"])
    p_new.add_argument("--notes", "-n", default="")

    # eval
    p_eval = subparsers.add_parser("eval", help="Run evaluation")
    p_eval.add_argument("--category", "-c", choices=["memory_recall", "context_retention", "routing", "latency"])

    # set
    p_set = subparsers.add_parser("set", help="Set parameter value")
    p_set.add_argument("param", help="Parameter name")
    p_set.add_argument("value", help="New value")

    # sweep
    p_sweep = subparsers.add_parser("sweep", help="Grid search parameter")
    p_sweep.add_argument("param", help="Parameter name")
    p_sweep.add_argument("min", type=float, help="Minimum value")
    p_sweep.add_argument("max", type=float, help="Maximum value")
    p_sweep.add_argument("step", type=float, help="Step size")

    # compare
    p_compare = subparsers.add_parser("compare", help="Compare iterations")
    p_compare.add_argument("iter1", type=int, nargs="?", help="First iteration")
    p_compare.add_argument("iter2", type=int, nargs="?", help="Second iteration")

    # export
    p_export = subparsers.add_parser("export", help="Export parameters to file")
    p_export.add_argument("file", help="Output file path")

    # import
    p_import = subparsers.add_parser("import", help="Import parameters from file")
    p_import.add_argument("file", help="Input file path")

    # list
    p_list = subparsers.add_parser("list", help="List parameters")
    p_list.add_argument("--category", "-c")

    # sessions
    p_sessions = subparsers.add_parser("sessions", help="List sessions")
    p_sessions.add_argument("--limit", "-l", type=int, default=10)

    # reset
    p_reset = subparsers.add_parser("reset", help="Reset parameters")
    p_reset.add_argument("param", nargs="?", help="Parameter to reset (all if omitted)")

    # info
    p_info = subparsers.add_parser("info", help="Show parameter info")
    p_info.add_argument("param", help="Parameter name")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    cli = TuningCLI()

    # Some commands don't need engine
    no_engine_commands = ["list", "sessions", "info"]
    connect_engine = args.command not in no_engine_commands

    await cli.initialize(connect_engine=connect_engine)

    # Dispatch command
    if args.command == "new":
        await cli.cmd_new(focus=args.focus, notes=args.notes)
    elif args.command == "eval":
        await cli.cmd_eval(category=args.category)
    elif args.command == "set":
        await cli.cmd_set(args.param, args.value)
    elif args.command == "sweep":
        await cli.cmd_sweep(args.param, args.min, args.max, args.step)
    elif args.command == "compare":
        await cli.cmd_compare(args.iter1, args.iter2)
    elif args.command == "export":
        await cli.cmd_export(args.file)
    elif args.command == "import":
        await cli.cmd_import(args.file)
    elif args.command == "list":
        await cli.cmd_list(category=args.category)
    elif args.command == "sessions":
        await cli.cmd_sessions(limit=args.limit)
    elif args.command == "reset":
        await cli.cmd_reset(args.param)
    elif args.command == "info":
        await cli.cmd_info(args.param)


if __name__ == "__main__":
    asyncio.run(main())
