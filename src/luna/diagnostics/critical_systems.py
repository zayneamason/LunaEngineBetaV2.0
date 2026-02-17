"""
Critical Systems Check — Startup Gate
=====================================

Luna MUST NOT start if her brain is disconnected.
This gate prevents silent failures that cause confabulation.

If any critical system is broken, Luna refuses to pretend to be herself.
"""

import sys
import sqlite3
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CriticalSystemsCheck:
    """Gate that prevents startup if Luna's brain is disconnected."""

    # Required Python modules and their install commands
    REQUIRED_SYSTEMS = [
        ("mlx", "pip install mlx mlx-lm"),
        ("mlx_lm", "pip install mlx-lm"),
    ]

    # Required files that MUST exist
    REQUIRED_FILES = [
        ("models/luna_lora_mlx/adapters.safetensors", "LoRA adapter missing!"),
        ("data/luna_engine.db", "Memory database missing!"),
    ]

    # Required data integrity (db_path, query, minimum, name)
    # Note: Thresholds lowered after brain scrub (Jan 2026) - quality over quantity
    REQUIRED_DATA = [
        ("data/luna_engine.db", "SELECT COUNT(*) FROM memory_nodes", 10000, "Memory nodes"),
        ("data/luna_engine.db", "SELECT COUNT(*) FROM graph_edges", 10000, "Graph edges"),
    ]

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize the checker.

        Args:
            project_root: Root directory of the Luna project.
                          If None, auto-detected from this file's location.
        """
        if project_root is None:
            # Navigate from src/luna/diagnostics/ to project root
            self.project_root = Path(__file__).parent.parent.parent.parent
        else:
            self.project_root = Path(project_root)

    def check_module(self, module: str) -> tuple[bool, str]:
        """Check if a Python module is importable."""
        try:
            __import__(module)
            return True, f"✅ {module} available"
        except ImportError as e:
            return False, f"❌ Missing module '{module}': {e}"

    def check_file(self, relative_path: str, message: str) -> tuple[bool, str]:
        """Check if a file exists."""
        full_path = self.project_root / relative_path
        if full_path.exists():
            size = full_path.stat().st_size
            return True, f"✅ {relative_path} ({size:,} bytes)"
        return False, f"❌ {message}: {relative_path}"

    def check_pipeline_wiring(self, endpoint_name: str, source_code: str) -> tuple[bool, str]:
        """
        Verify a streaming endpoint calls record_conversation_turn.

        Static analysis — reads the source between the endpoint decorator
        and the next @app decorator to check for the unified recording call.
        """
        # Find the endpoint function
        marker = f'"{endpoint_name}"' if endpoint_name.startswith("/") else endpoint_name
        # Look for the route decorator
        import re
        pattern = rf'@app\.\w+\("{re.escape(endpoint_name)}"'
        match = re.search(pattern, source_code)
        if not match:
            return True, f"✅ {endpoint_name} (not found — skipped)"

        # Extract the function body up to the next route decorator
        start = match.start()
        next_route = re.search(r'\n@app\.', source_code[start + 1:])
        end = start + 1 + next_route.start() if next_route else len(source_code)
        function_body = source_code[start:end]

        if "record_conversation_turn" in function_body or "_trigger_extraction" in function_body:
            return True, f"✅ {endpoint_name} wired to extraction pipeline"
        else:
            return False, f"❌ {endpoint_name} bypasses extraction pipeline (missing record_conversation_turn or _trigger_extraction)"

    def check_data(self, db_path: str, query: str, minimum: int, name: str) -> tuple[bool, str]:
        """Check database has required minimum data."""
        full_path = self.project_root / db_path
        if not full_path.exists():
            return False, f"❌ {name}: Database not found at {db_path}"

        try:
            conn = sqlite3.connect(str(full_path))
            count = conn.execute(query).fetchone()[0]
            conn.close()

            if count >= minimum:
                return True, f"✅ {name}: {count:,} (required >{minimum:,})"
            else:
                return False, f"❌ {name}: Only {count:,} (required >{minimum:,})"
        except Exception as e:
            return False, f"❌ {name} check failed: {e}"

    def run_all_checks(self) -> tuple[bool, list[str]]:
        """
        Run all critical system checks.

        Returns:
            (all_passed, messages) - Tuple of success status and check messages
        """
        messages = []
        all_passed = True

        messages.append("=" * 60)
        messages.append("LUNA CRITICAL SYSTEMS CHECK")
        messages.append("=" * 60)

        # Check modules
        messages.append("\n📦 Required Modules:")
        for module, fix_cmd in self.REQUIRED_SYSTEMS:
            passed, msg = self.check_module(module)
            messages.append(f"  {msg}")
            if not passed:
                all_passed = False
                messages.append(f"    Fix: {fix_cmd}")

        # Check files
        messages.append("\n📁 Required Files:")
        for path, error_msg in self.REQUIRED_FILES:
            passed, msg = self.check_file(path, error_msg)
            messages.append(f"  {msg}")
            if not passed:
                all_passed = False

        # Check data integrity
        messages.append("\n🧠 Memory Integrity:")
        for db_path, query, minimum, name in self.REQUIRED_DATA:
            passed, msg = self.check_data(db_path, query, minimum, name)
            messages.append(f"  {msg}")
            if not passed:
                all_passed = False

        # Check pipeline wiring (static analysis of server.py)
        messages.append("\n🔗 Pipeline Wiring:")
        server_path = self.project_root / "src" / "luna" / "api" / "server.py"
        if server_path.exists():
            server_source = server_path.read_text()
            for endpoint in ["/persona/stream", "/stream", "/hub/turn/add"]:
                passed, msg = self.check_pipeline_wiring(endpoint, server_source)
                messages.append(f"  {msg}")
                if not passed:
                    # Pipeline wiring is a warning, not a hard block
                    messages.append(f"    ⚠️  Extraction pipeline will not fire for {endpoint}")
        else:
            messages.append("  ⚠️  server.py not found — pipeline wiring check skipped")

        messages.append("\n" + "=" * 60)
        if all_passed:
            messages.append("✅ ALL CRITICAL SYSTEMS OPERATIONAL")
        else:
            messages.append("🚨 CRITICAL SYSTEMS CHECK FAILED")
            messages.append("Luna cannot start with a disconnected brain.")
        messages.append("=" * 60)

        return all_passed, messages

    @classmethod
    def run(cls, project_root: Optional[Path] = None, strict: bool = True) -> bool:
        """
        Run critical systems check.

        Args:
            project_root: Root directory of Luna project
            strict: If True, exits with error on failure. If False, just logs.

        Returns:
            True if all checks passed
        """
        checker = cls(project_root)
        passed, messages = checker.run_all_checks()

        # Log all messages
        for msg in messages:
            if msg.startswith("❌"):
                logger.error(msg)
            elif msg.startswith("✅"):
                logger.info(msg)
            else:
                print(msg)  # Headers go to stdout

        if not passed and strict:
            print("\n🚨 Luna refuses to start with critical systems broken.")
            print("Fix the issues above and restart.\n")
            sys.exit(1)

        return passed


def run_startup_check(strict: bool = True) -> bool:
    """
    Convenience function for server startup.

    Call this at the TOP of your server startup, before FastAPI loads.
    """
    return CriticalSystemsCheck.run(strict=strict)


if __name__ == "__main__":
    # Allow running as standalone script
    import argparse
    parser = argparse.ArgumentParser(description="Luna Critical Systems Check")
    parser.add_argument("--no-strict", action="store_true", help="Don't exit on failure")
    args = parser.parse_args()

    run_startup_check(strict=not args.no_strict)
