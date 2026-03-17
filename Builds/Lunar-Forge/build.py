"""
Lunar Forge — CLI Entry Point.

Usage:
    python build.py --profile luna-only
    python build.py --profile luna-only --dry-run
    python build.py --profile dev-test --platform macos-arm64
    python build.py --list-profiles
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from .core import BuildPipeline, detect_platform, list_profiles, load_profile


FORGE_ROOT = Path(__file__).parent


def _progress_callback(message: str, pct: int) -> None:
    """Print build progress to stdout."""
    if pct >= 0:
        bar_width = 30
        filled = int(bar_width * pct / 100)
        bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
        print(f"\r  [{bar}] {pct:3d}%  {message[:60]:<60}", end="", flush=True)
        if pct == 100:
            print()
    else:
        print(f"  {message}")


def cmd_list_profiles() -> None:
    """List available build profiles."""
    profiles_dir = FORGE_ROOT / "profiles"
    if not profiles_dir.exists():
        print("No profiles directory found.")
        return

    profiles = list_profiles(profiles_dir)
    if not profiles:
        print("No profiles found.")
        return

    print("\nAvailable profiles:\n")
    for p in profiles:
        print(f"  {p['file']:<20s}  {p['name']}")
        print(f"  {'':20s}  {p['description']}")
        print(f"  {'':20s}  db: {p['database_mode']} | collections: {p['collections_count']}")
        print()


def cmd_preview(profile_name: str) -> None:
    """Preview resolved build config (dry run)."""
    profile_path = FORGE_ROOT / "profiles" / f"{profile_name}.yaml"
    if not profile_path.exists():
        print(f"Profile not found: {profile_path}")
        sys.exit(1)

    pipeline = BuildPipeline(profile_path, forge_root=FORGE_ROOT)
    manifest = pipeline.preview()

    print(f"\n=== Build Preview: {manifest['profile']} ===\n")
    print(f"  Version:    {manifest['version']}")
    print(f"  Platform:   {manifest['platform']}")
    print(f"  Engine:     {manifest['engine_root']}")
    print()

    print("  Database:")
    db = manifest["database"]
    print(f"    Mode: {db.get('mode', 'seed')}")
    if db.get("source"):
        print(f"    Source: {db['source']}")
    print()

    print("  Collections:")
    for name, info in manifest.get("collections", {}).items():
        status = "\u2713" if info["enabled"] else "\u2717"
        size = f"{info['size'] / (1024*1024):.1f} MB" if info["exists"] else "NOT FOUND"
        print(f"    {status} {name:20s}  {size}")
    print()

    print("  Config:")
    cfg = manifest["config"]
    print(f"    Patches: {', '.join(cfg.get('personality_patches', []))}")
    print(f"    LLM:     {cfg.get('llm_providers_mode', 'template')}")
    print(f"    Chain:   {' -> '.join(cfg.get('fallback_chain', []))}")
    print()

    print(f"  Secrets: {manifest.get('secrets_mode', 'template')}")
    print()

    fe = manifest.get("frontend", {})
    pages = fe.get("pages", {})
    widgets = fe.get("widgets", {})
    enabled_pages = [k for k, v in pages.items() if v]
    enabled_widgets = [k for k, v in widgets.items() if v]
    print(f"  Frontend:")
    print(f"    Pages:   {', '.join(enabled_pages)}")
    print(f"    Widgets: {len(enabled_widgets)} / {len(widgets)}")
    if fe.get("remap"):
        for mod, cfg in fe["remap"].items():
            print(f"    Remap:   {mod} -> {cfg.get('to', '?')}.{cfg.get('position', '?')}")
    print()

    nk = manifest.get("nuitka", {})
    print(f"  Nuitka:")
    print(f"    Standalone: {nk.get('standalone', True)}")
    print(f"    Excluded:   {len(nk.get('excluded_packages', []))} packages")
    print()


def cmd_build(profile_name: str, platform_target: str = "auto") -> None:
    """Run a full build."""
    profile_path = FORGE_ROOT / "profiles" / f"{profile_name}.yaml"
    if not profile_path.exists():
        print(f"Profile not found: {profile_path}")
        sys.exit(1)

    print(f"\n=== Lunar Forge — Building: {profile_name} ===\n")
    print(f"  Platform: {platform_target if platform_target != 'auto' else detect_platform()}")
    print()

    pipeline = BuildPipeline(profile_path, platform_target, forge_root=FORGE_ROOT)
    report = pipeline.build(on_progress=_progress_callback)

    print()
    if report.status == "SUCCESS":
        print(f"=== BUILD COMPLETE ===")
        print(f"  Output:  {report.binary_path.parent if report.binary_path else 'N/A'}")
        print(f"  Binary:  {report.binary_size / (1024*1024):.0f} MB")
        print(f"  Total:   {report.total_size / (1024*1024):.0f} MB")
        print(f"  Files:   {report.file_count} across {report.dir_count} dirs")
        print(f"  Time:    {report.duration_seconds:.1f}s")
    else:
        print(f"=== BUILD FAILED ===")
        for err in report.errors:
            print(f"  ERROR: {err}")

    if report.warnings:
        print("\n  Warnings:")
        for w in report.warnings:
            print(f"    - {w}")

    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="lunar-forge",
        description="Luna Engine Build System",
    )
    parser.add_argument("--profile", "-p", help="Build profile name (without .yaml)")
    parser.add_argument("--platform", default="auto", help="Target platform (default: auto-detect)")
    parser.add_argument("--dry-run", action="store_true", help="Preview build config without building")
    parser.add_argument("--list-profiles", "-l", action="store_true", help="List available profiles")

    args = parser.parse_args()

    if args.list_profiles:
        cmd_list_profiles()
    elif args.profile and args.dry_run:
        cmd_preview(args.profile)
    elif args.profile:
        cmd_build(args.profile, args.platform)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
