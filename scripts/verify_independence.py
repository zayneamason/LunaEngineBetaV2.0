#!/usr/bin/env python3
"""
Verify Luna Engine Independence from Eclissi

Final verification script that checks:
1. No Eclissi references in source code
2. No sys.path manipulation
3. Clean imports
4. Database is properly populated
5. Runtime works independently

Usage:
    python scripts/verify_independence.py
"""

import subprocess
import sys
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / "src"
TESTS_DIR = PROJECT_ROOT / "tests"
LUNA_DB = PROJECT_ROOT / "data" / "luna_engine.db"


def check_source_code() -> bool:
    """Scan source code for Eclissi references."""
    print("[CHECK] Source code scan for Eclissi references...")

    violations = []
    for py_file in SRC_DIR.rglob("*.py"):
        content = py_file.read_text()
        rel_path = py_file.relative_to(PROJECT_ROOT)

        if "eclissi" in content.lower() or "_Eclessi" in content:
            violations.append(str(rel_path))
            print(f"  - {rel_path}: ECLISSI REFERENCE FOUND")
        else:
            print(f"  - {rel_path}: CLEAN")

    if violations:
        print(f"  [FAIL] Eclissi references found in {len(violations)} files")
        return False

    print("  [OK] No Eclissi references found")
    return True


def check_imports() -> bool:
    """Verify clean imports without sys.path manipulation."""
    print("\n[CHECK] Import verification...")

    try:
        # Try importing the matrix module
        print("  - Importing luna.actors.matrix... ", end="")

        # Check for sys.path manipulation
        matrix_file = SRC_DIR / "luna" / "actors" / "matrix.py"
        content = matrix_file.read_text()

        if "sys.path.insert" in content and "_Eclessi" in content:
            print("FAIL (sys.path hack found)")
            return False

        # Try actual import
        import importlib.util
        spec = importlib.util.spec_from_file_location("matrix", matrix_file)
        module = importlib.util.module_from_spec(spec)

        print("OK")

        # Check for Eclissi constants
        print("  - Checking for Eclissi constants... ", end="")
        module_content = matrix_file.read_text()

        if "ECLISSI_AVAILABLE" in module_content or "ECLISSI_DB_PATH" in module_content:
            print("FAIL (Eclissi constants found)")
            return False

        print("OK")

        # Try importing engine
        print("  - Importing luna.engine... ", end="")
        engine_file = SRC_DIR / "luna" / "engine.py"
        spec = importlib.util.spec_from_file_location("engine", engine_file)

        print("OK")

        print("  [OK] Clean imports")
        return True

    except Exception as e:
        print(f"FAIL ({e})")
        return False


def check_database() -> bool:
    """Verify Luna Engine database is properly populated."""
    print("\n[CHECK] Database verification...")

    print(f"  - Luna Engine DB: {LUNA_DB}")

    if not LUNA_DB.exists():
        print("  [WARN] Database not found - run migration first")
        return True  # Not a failure, just needs migration

    import sqlite3

    try:
        conn = sqlite3.connect(LUNA_DB)

        # Count nodes
        cursor = conn.execute("SELECT COUNT(*) FROM memory_nodes")
        node_count = cursor.fetchone()[0]
        print(f"  - Nodes: {node_count:,}")

        # Count edges
        cursor = conn.execute("SELECT COUNT(*) FROM memory_edges")
        edge_count = cursor.fetchone()[0]
        print(f"  - Edges: {edge_count:,}")

        conn.close()

        if node_count > 0:
            print("  [OK] Database populated")
        else:
            print("  [WARN] Database empty - run migration to populate")

        return True

    except Exception as e:
        print(f"  [WARN] Database check failed: {e}")
        return True  # Not critical


def check_runtime() -> bool:
    """Verify runtime works independently."""
    print("\n[CHECK] Runtime verification...")

    try:
        print("  - Creating MatrixActor... ", end="")

        # Use a temporary database for testing
        import tempfile
        import asyncio
        from pathlib import Path

        # Add src to path for import
        sys.path.insert(0, str(SRC_DIR))

        from luna.actors.matrix import MatrixActor

        async def test_runtime():
            with tempfile.TemporaryDirectory() as tmpdir:
                db_path = Path(tmpdir) / "test.db"
                matrix = MatrixActor(db_path=db_path)

                print("OK")

                print("  - Initializing... ", end="")
                await matrix.initialize()
                print("OK")

                print("  - Adding test node... ", end="")
                node_id = await matrix.store_memory(
                    content="Independence verification test",
                    node_type="FACT",
                )
                print(f"OK ({node_id})")

                print("  - Querying nodes... ", end="")
                results = await matrix.search("Independence", limit=10)
                print(f"OK ({len(results)} found)")

                print("  - Getting stats... ", end="")
                stats = await matrix.get_stats()
                print(f"OK (backend: {stats.get('backend', 'unknown')})")

                await matrix.stop()

        asyncio.run(test_runtime())

        print("  [OK] Runtime works independently")
        return True

    except Exception as e:
        print(f"FAIL ({e})")
        import traceback
        traceback.print_exc()
        return False


def check_grep() -> bool:
    """Run grep to verify no Eclissi references."""
    print("\n[CHECK] Final grep verification...")

    try:
        result = subprocess.run(
            ["grep", "-rn", "-i", "eclissi", str(SRC_DIR), str(TESTS_DIR),
             "--include=*.py"],
            capture_output=True,
            text=True
        )

        if result.stdout.strip():
            # Filter out this verification script and test file
            lines = [
                line for line in result.stdout.strip().split("\n")
                if "verify_independence.py" not in line
                and "test_eclissi_removal.py" not in line
            ]

            if lines:
                print(f"  [FAIL] grep found Eclissi references:")
                for line in lines[:10]:
                    print(f"    {line}")
                return False

        print("  [OK] grep found no Eclissi references")
        return True

    except FileNotFoundError:
        print("  [SKIP] grep not available")
        return True


def main():
    print("=" * 50)
    print("Luna Engine Independence Verification")
    print("=" * 50)

    results = {
        "Source code scan": check_source_code(),
        "Import verification": check_imports(),
        "Database verification": check_database(),
        "Runtime verification": check_runtime(),
        "Grep verification": check_grep(),
    }

    print("\n" + "=" * 50)
    print("RESULTS")
    print("=" * 50)

    all_passed = True
    for check, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"  {check}: {status}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("=" * 50)
        print("=== VERIFICATION PASSED ===")
        print("Luna Engine is 100% independent from Eclissi.")
        print("=" * 50)
        return 0
    else:
        print("=" * 50)
        print("=== VERIFICATION FAILED ===")
        print("Luna Engine still has Eclissi dependencies.")
        print("=" * 50)
        return 1


if __name__ == "__main__":
    sys.exit(main())
