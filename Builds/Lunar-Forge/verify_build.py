"""
Standalone build verification — run against any Lunar Forge build output.

Usage:
    .venv/bin/python verify_build.py output/luna-only-macos-arm64-0.1.0/
    .venv/bin/python verify_build.py output/tarcila-macos-arm64-0.1.0/

Exits 0 on clean, 1 on violations.
"""

import json
import sqlite3
import sys
from pathlib import Path

import yaml


POISON_TERMS = ["ahab", "kinoni", "zayne", "nakaseke", "zayneamason"]


def verify(dist_dir: Path) -> tuple[bool, list[str]]:
    """Verify build output contains no dev/personal data."""
    violations: list[str] = []

    # --- Check 1: Database row counts ---
    db_path = dist_dir / "data" / "luna_engine.db"
    if db_path.exists():
        conn = sqlite3.connect(str(db_path))
        for table in ["conversation_turns", "memory_nodes", "entities", "sessions"]:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                if count > 0:
                    violations.append(f"DATA LEAK: {table} has {count} rows (expected 0)")
            except sqlite3.OperationalError:
                pass  # Table may not exist in schema
        conn.close()
    else:
        violations.append("MISSING: luna_engine.db not found in dist/data/")

    # --- Check 2: Owner identity is clean ---
    owner_path = dist_dir / "config" / "owner.yaml"
    if owner_path.exists():
        owner = yaml.safe_load(owner_path.read_text()) or {}
        entity_id = owner.get("owner", {}).get("entity_id", "")
        if entity_id:
            violations.append(f"DATA LEAK: owner.yaml has entity_id={entity_id}")
    else:
        violations.append("MISSING: owner.yaml not found")

    # --- Check 3: No personal data in text configs ---
    config_dir = dist_dir / "config"
    if config_dir.exists():
        for config_file in config_dir.rglob("*"):
            if config_file.is_file() and config_file.suffix in (".yaml", ".json", ".yml"):
                content = config_file.read_text().lower()
                for term in POISON_TERMS:
                    if term in content:
                        violations.append(
                            f'DATA LEAK: "{term}" found in {config_file.relative_to(dist_dir)}'
                        )

    # --- Check 4: No project files ---
    projects_path = dist_dir / "config" / "projects" / "projects.yaml"
    if projects_path.exists():
        projects = yaml.safe_load(projects_path.read_text()) or {}
        if projects.get("projects"):
            violations.append(
                f'DATA LEAK: projects.yaml has {len(projects["projects"])} projects'
            )

    # --- Check 5: Aibrarian collection DBs ---
    aibrarian_dir = dist_dir / "data" / "aibrarian"
    if aibrarian_dir.exists():
        for db_file in aibrarian_dir.glob("*.db"):
            name = db_file.stem
            if name not in ["luna_system"]:
                violations.append(f"DATA LEAK: unexpected collection {name}.db")

    # --- Check 6: Identity bypass is clean ---
    bypass_path = dist_dir / "config" / "identity_bypass.json"
    if bypass_path.exists():
        bypass = json.loads(bypass_path.read_text())
        if bypass.get("entity_id"):
            violations.append(
                f'DATA LEAK: identity_bypass.json has entity_id={bypass["entity_id"]}'
            )

    is_clean = len(violations) == 0
    return is_clean, violations


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python verify_build.py <dist_dir>")
        print("Example: .venv/bin/python verify_build.py output/luna-only-macos-arm64-0.1.0/")
        sys.exit(2)

    dist = Path(sys.argv[1])
    if not dist.exists():
        print(f"ERROR: {dist} does not exist")
        sys.exit(2)

    ok, issues = verify(dist)
    for issue in issues:
        print(f"FAIL: {issue}")
    if ok:
        print("PASS: Build is clean — zero personal data detected")
    else:
        print(f"\nFAILED: {len(issues)} violation(s) found")
    sys.exit(0 if ok else 1)
