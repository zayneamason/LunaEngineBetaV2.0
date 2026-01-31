#!/usr/bin/env python3
"""
Luna MCP Pipeline Test
======================

Tests all 21 Luna MCP commands to verify they execute correctly.

REQUIREMENTS:
1. Luna Engine running on port 8000: python scripts/run.py --server
2. MCP API will auto-start on port 8742

Usage:
    python scripts/test_mcp_pipeline.py
    python scripts/test_mcp_pipeline.py --verbose
    python scripts/test_mcp_pipeline.py --category memory
"""

import asyncio
import sys
import json
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Callable, Awaitable
from datetime import datetime

# Add src to path for imports
SRC_PATH = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(SRC_PATH))

# Import MCP tools
from luna_mcp.tools.filesystem import luna_read, luna_write, luna_list
from luna_mcp.tools.memory import (
    luna_smart_fetch,
    memory_matrix_search,
    memory_matrix_add_node,
    memory_matrix_add_edge,
    memory_matrix_get_context,
    memory_matrix_trace,
    luna_save_memory,
)
from luna_mcp.tools.state import (
    luna_detect_context,
    luna_get_state,
    luna_set_app_context,
)
from luna_mcp.tools.git import luna_git_sync, luna_git_status


@dataclass
class TestResult:
    """Result of a single test."""
    name: str
    passed: bool
    output: str
    error: Optional[str] = None
    duration_ms: float = 0.0


class MCPPipelineTest:
    """Luna MCP Pipeline Tester."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: list[TestResult] = []
        self.test_node_id: Optional[str] = None
        self.test_session_id: Optional[str] = None

    def log(self, msg: str):
        """Log message if verbose."""
        if self.verbose:
            print(f"  {msg}")

    async def run_test(
        self,
        name: str,
        func: Callable[[], Awaitable[str]],
        expect_success: bool = True,
        success_markers: Optional[list[str]] = None,
    ) -> TestResult:
        """Run a single test and record result."""
        start = datetime.now()
        try:
            output = await func()
            duration = (datetime.now() - start).total_seconds() * 1000

            # Determine pass/fail
            passed = True
            if expect_success:
                if success_markers:
                    passed = any(m in output for m in success_markers)
                else:
                    # Default: fail if "error" in output (case-insensitive)
                    passed = "error" not in output.lower() or "Error:" not in output

            result = TestResult(
                name=name,
                passed=passed,
                output=output[:500] if len(output) > 500 else output,
                duration_ms=duration,
            )
        except Exception as e:
            duration = (datetime.now() - start).total_seconds() * 1000
            result = TestResult(
                name=name,
                passed=False,
                output="",
                error=str(e),
                duration_ms=duration,
            )

        self.results.append(result)
        return result

    # =========================================================================
    # File Operations Tests
    # =========================================================================

    async def test_file_operations(self):
        """Test file operation commands."""
        print("\n📁 Testing File Operations...")

        # Test luna_list
        await self.run_test(
            "luna_list (root)",
            lambda: luna_list(".", recursive=False),
            success_markers=["src", "scripts", "data"],
        )

        # Test luna_read
        await self.run_test(
            "luna_read (README)",
            lambda: luna_read("README.md"),
            success_markers=["Luna", "#"],
        )

        # Test luna_write (to temp file)
        test_content = f"# MCP Test\nTimestamp: {datetime.now().isoformat()}"
        await self.run_test(
            "luna_write (temp file)",
            lambda: luna_write("data/mcp_test_temp.txt", test_content, create_dirs=True),
            success_markers=["✓", "success", "wrote", "Written"],
        )

        # Verify write by reading
        await self.run_test(
            "luna_read (verify write)",
            lambda: luna_read("data/mcp_test_temp.txt"),
            success_markers=["MCP Test", "Timestamp"],
        )

    # =========================================================================
    # Memory Operations Tests
    # =========================================================================

    async def test_memory_operations(self):
        """Test memory operation commands."""
        print("\n🧠 Testing Memory Operations...")

        # Test luna_smart_fetch
        result = await self.run_test(
            "luna_smart_fetch",
            lambda: luna_smart_fetch("Luna personality"),
        )
        self.log(f"smart_fetch returned: {result.output[:200]}...")

        # Test memory_matrix_search
        await self.run_test(
            "memory_matrix_search",
            lambda: memory_matrix_search("Zayne", limit=5),
        )

        # Test memory_matrix_add_node
        result = await self.run_test(
            "memory_matrix_add_node",
            lambda: memory_matrix_add_node(
                node_type="TEST",
                content="MCP Pipeline Test Node - This is a test node created during pipeline validation",
                tags=["test", "mcp", "pipeline"],
                confidence=0.9,
            ),
            success_markers=["✓", "success", "node"],
        )
        # Extract node ID for later tests
        if "node_" in result.output or "Node created" in result.output:
            # Try to extract the node ID
            import re
            match = re.search(r"([a-f0-9]{8,12})", result.output)
            if match:
                self.test_node_id = match.group(1)
                self.log(f"Created test node: {self.test_node_id}")

        # Test memory_matrix_add_edge (if we have a node ID)
        if self.test_node_id:
            await self.run_test(
                "memory_matrix_add_edge",
                lambda: memory_matrix_add_edge(
                    from_node=self.test_node_id,
                    to_node=self.test_node_id,  # Self-loop for test
                    relationship="RELATES_TO",
                    strength=0.8,
                ),
                success_markers=["✓", "success", "Edge", "created"],
            )
        else:
            await self.run_test(
                "memory_matrix_add_edge (no node)",
                lambda: memory_matrix_add_edge(
                    from_node="test_from",
                    to_node="test_to",
                    relationship="RELATES_TO",
                    strength=0.8,
                ),
            )

        # Test memory_matrix_get_context
        node_to_test = self.test_node_id or "test_node"
        await self.run_test(
            "memory_matrix_get_context",
            lambda: memory_matrix_get_context(node_to_test, depth=2),
            success_markers=["Context", "Neighbors", "Depth"],
        )

        # Test memory_matrix_trace
        await self.run_test(
            "memory_matrix_trace",
            lambda: memory_matrix_trace(node_to_test, max_depth=3),
            success_markers=["Trace", "Activation", "Depth"],
        )

        # Test luna_save_memory
        await self.run_test(
            "luna_save_memory",
            lambda: luna_save_memory(
                memory_type="insight",
                title="MCP Pipeline Test Insight",
                content="This insight was created during MCP pipeline validation testing.",
                tags=["test", "validation"],
            ),
            success_markers=["✓", "saved", "Memory"],
        )

    # =========================================================================
    # Session Management Tests
    # =========================================================================

    async def test_session_management(self):
        """Test session management commands."""
        print("\n💬 Testing Session Management...")

        # Import session tools
        from luna_mcp.tools.memory import (
            luna_start_session,
            luna_record_turn,
            luna_end_session,
            luna_get_current_session,
            luna_auto_session_status,
            luna_flush_session,
        )

        # Test luna_start_session
        result = await self.run_test(
            "luna_start_session",
            lambda: luna_start_session(app_context="mcp_test"),
            success_markers=["✓", "session", "created", "started"],
        )
        # Extract session ID
        import re
        match = re.search(r"(session_\d+|[a-f0-9-]{36})", result.output, re.IGNORECASE)
        if match:
            self.test_session_id = match.group(1)
            self.log(f"Started test session: {self.test_session_id}")

        # Test luna_get_current_session
        await self.run_test(
            "luna_get_current_session",
            lambda: luna_get_current_session(),
        )

        # Test luna_record_turn
        session_id = self.test_session_id or "test_session"
        await self.run_test(
            "luna_record_turn (user)",
            lambda: luna_record_turn(
                role="user",
                content="This is a test message from the MCP pipeline validator.",
                session_id=session_id,
            ),
            success_markers=["✓", "recorded", "turn"],
        )

        await self.run_test(
            "luna_record_turn (assistant)",
            lambda: luna_record_turn(
                role="assistant",
                content="I acknowledge your test message. Pipeline validation in progress.",
                session_id=session_id,
            ),
            success_markers=["✓", "recorded", "turn"],
        )

        # Test luna_auto_session_status
        await self.run_test(
            "luna_auto_session_status",
            lambda: luna_auto_session_status(),
        )

        # Test luna_flush_session
        await self.run_test(
            "luna_flush_session",
            lambda: luna_flush_session(),
            success_markers=["✓", "flushed", "ended", "session"],
        )

        # Test luna_end_session
        if self.test_session_id:
            await self.run_test(
                "luna_end_session",
                lambda: luna_end_session(self.test_session_id),
                success_markers=["✓", "ended", "session", "extraction"],
            )

    # =========================================================================
    # State Tools Tests
    # =========================================================================

    async def test_state_tools(self):
        """Test state management commands."""
        print("\n🔧 Testing State Tools...")

        # Test luna_get_state
        await self.run_test(
            "luna_get_state",
            lambda: luna_get_state(),
            success_markers=["status", "state", "running", "engine"],
        )

        # Test luna_set_app_context
        await self.run_test(
            "luna_set_app_context",
            lambda: luna_set_app_context(
                app="Claude Desktop",
                app_state="MCP Pipeline Test",
            ),
            success_markers=["✓", "context", "set"],
        )

        # Test luna_detect_context (simple message, not activation)
        await self.run_test(
            "luna_detect_context (simple)",
            lambda: luna_detect_context(
                message="What do you remember about our projects?",
                auto_fetch=False,
            ),
        )

    # =========================================================================
    # Git Operations Tests
    # =========================================================================

    async def test_git_operations(self):
        """Test git operation commands."""
        print("\n📦 Testing Git Operations...")

        # Test luna_git_status
        await self.run_test(
            "luna_git_status",
            lambda: luna_git_status(),
            success_markers=["branch", "status", "modified", "clean", "changed"],
        )

        # NOTE: We don't test luna_git_sync to avoid making actual commits

    # =========================================================================
    # Main Test Runner
    # =========================================================================

    async def run_all(self, categories: Optional[list[str]] = None):
        """Run all tests."""
        print("=" * 60)
        print("🌙 Luna MCP Pipeline Test")
        print("=" * 60)
        print(f"Testing {21} MCP commands...")

        test_methods = {
            "file": self.test_file_operations,
            "memory": self.test_memory_operations,
            "session": self.test_session_management,
            "state": self.test_state_tools,
            "git": self.test_git_operations,
        }

        if categories:
            for cat in categories:
                if cat in test_methods:
                    await test_methods[cat]()
        else:
            for method in test_methods.values():
                await method()

        # Print summary
        self.print_summary()

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 60)
        print("📊 TEST RESULTS")
        print("=" * 60)

        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)

        # Print each result
        for r in self.results:
            status = "✅" if r.passed else "❌"
            duration = f"{r.duration_ms:.0f}ms"
            print(f"  {status} {r.name:<35} {duration:>8}")
            if r.error and not r.passed:
                print(f"       Error: {r.error[:60]}...")
            elif not r.passed and self.verbose:
                print(f"       Output: {r.output[:60]}...")

        print("\n" + "-" * 60)
        print(f"  Total: {total} | Passed: {passed} | Failed: {failed}")
        print(f"  Success Rate: {passed/total*100:.1f}%")
        print("=" * 60)

        # Exit with error code if any failed
        if failed > 0:
            print("\n⚠️  Some tests failed. Check output above.")
            return 1
        else:
            print("\n✅ All tests passed!")
            return 0


async def main():
    parser = argparse.ArgumentParser(description="Luna MCP Pipeline Test")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--category", "-c",
        choices=["file", "memory", "session", "state", "git"],
        action="append",
        help="Test specific category (can be repeated)",
    )
    args = parser.parse_args()

    tester = MCPPipelineTest(verbose=args.verbose)
    exit_code = await tester.run_all(categories=args.category)
    sys.exit(exit_code)


if __name__ == "__main__":
    asyncio.run(main())
