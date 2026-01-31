#!/usr/bin/env python3
"""
Dependency Verification Script
==============================

Verifies critical dependencies are installed and functional.
Run this after any pip install or venv changes.

Usage:
    python scripts/verify_deps.py
    # Or with uv:
    uv run scripts/verify_deps.py
"""

import sys
import subprocess
from importlib.metadata import version, PackageNotFoundError


# Critical dependencies with minimum versions
# Format: (package_name, pip_name, min_version)
CRITICAL_DEPS = [
    ("mlx", "mlx", "0.5.0"),
    ("mlx_lm", "mlx-lm", "0.0.10"),
    ("aiosqlite", "aiosqlite", "0.19.0"),
    ("anthropic", "anthropic", "0.18.0"),
    ("fastapi", "fastapi", "0.109.0"),
    ("networkx", "networkx", "3.2"),
]


def parse_version(v: str) -> tuple:
    """Parse version string into comparable tuple."""
    parts = []
    for part in v.split("."):
        try:
            parts.append(int(part))
        except ValueError:
            parts.append(part)
    return tuple(parts)


def check_dependencies() -> bool:
    """
    Check all critical dependencies.

    Returns:
        True if all checks passed
    """
    print("=" * 60)
    print("LUNA DEPENDENCY VERIFICATION")
    print("=" * 60)
    print()

    errors = []
    warnings = []

    for import_name, pip_name, min_version in CRITICAL_DEPS:
        try:
            installed_version = version(pip_name)

            # Compare versions
            if parse_version(installed_version) >= parse_version(min_version):
                print(f"✅ {pip_name}=={installed_version} (>={min_version})")
            else:
                warnings.append(
                    f"⚠️  {pip_name}=={installed_version} (want >={min_version})"
                )
                print(f"⚠️  {pip_name}=={installed_version} (outdated, want >={min_version})")

        except PackageNotFoundError:
            errors.append(f"❌ {pip_name} not installed (need >={min_version})")
            print(f"❌ {pip_name} NOT INSTALLED (need >={min_version})")

    print()

    # Also check pip for conflicts
    print("Checking for dependency conflicts...")
    result = subprocess.run(
        [sys.executable, "-m", "pip", "check"],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        print("✅ No dependency conflicts found")
    else:
        print(f"⚠️  Dependency conflicts detected:")
        print(result.stdout)
        warnings.append("pip check found conflicts")

    print()
    print("=" * 60)

    if errors:
        print("🚨 CRITICAL DEPENDENCIES MISSING:")
        for e in errors:
            print(f"  {e}")
        print()
        print("Fix with:")
        print("  pip install -e '.[local,memory]'")
        print("  # or")
        print("  uv sync --extras local --extras memory")
        print("=" * 60)
        return False

    if warnings:
        print("⚠️  WARNINGS (may cause issues):")
        for w in warnings:
            print(f"  {w}")
        print("=" * 60)
    else:
        print("✅ ALL CRITICAL DEPENDENCIES PRESENT")
        print("=" * 60)

    return True


def main():
    """Main entry point."""
    success = check_dependencies()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
