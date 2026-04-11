#!/usr/bin/env python3
"""
Lunar Forge CLI — Run from project root.

Usage:
    python3 forge_build.py --profile hai-dai
    python3 forge_build.py --profile hai-dai --dry-run
    python3 forge_build.py --list-profiles
"""
import sys
from pathlib import Path

FORGE_DIR = Path(__file__).parent / "Builds" / "Lunar-Forge"
sys.path.insert(0, str(FORGE_DIR))

from core import BuildPipeline, detect_platform, list_profiles, load_profile
import argparse, json, yaml

FORGE_ROOT = FORGE_DIR
PROFILES_DIR = FORGE_ROOT / "profiles"


def main():
    parser = argparse.ArgumentParser(description="Lunar Forge — Luna Build System")
    parser.add_argument("--profile", required=False, help="Profile name (filename stem, e.g. 'hai-dai')")
    parser.add_argument("--platform", default="auto", help="Target platform (default: auto-detect)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be built without building")
    parser.add_argument("--list-profiles", action="store_true", help="List available profiles")
    args = parser.parse_args()

    if args.list_profiles:
        profiles = list_profiles(PROFILES_DIR)
        for p in profiles:
            print(f"  {p['file']:<25} {p['name']}")
        return

    if not args.profile:
        parser.error("--profile is required (use --list-profiles to see options)")

    profile_path = PROFILES_DIR / f"{args.profile}.yaml"
    if not profile_path.exists():
        print(f"ERROR: Profile not found: {profile_path}")
        print(f"Available profiles:")
        for f in sorted(PROFILES_DIR.glob("*.yaml")):
            print(f"  {f.stem}")
        sys.exit(1)

    pipeline = BuildPipeline(profile_path, forge_root=FORGE_ROOT)

    if args.dry_run:
        manifest = pipeline.preview()
        print(json.dumps(manifest, indent=2, default=str))
        return

    pipeline.run()


if __name__ == "__main__":
    main()
