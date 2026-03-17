#!/usr/bin/env python3
"""
Lunar Forge — Database Sanitizer CLI.

Usage:
    python sanitize_cli.py --preview --entities luna,the-dude
    python sanitize_cli.py --entities luna --types FACT,DECISION --min-confidence 0.5 --no-conversations
    python sanitize_cli.py  # Interactive mode
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure Forge root is importable
sys.path.insert(0, str(Path(__file__).parent))

from sanitizer import DatabaseSanitizer, SanitizeConfig

FORGE_ROOT = Path(__file__).parent
ENGINE_ROOT = Path(
    __import__("os").environ.get(
        "LUNA_ENGINE_ROOT",
        str(FORGE_ROOT.parent.parent / "_LunaEngine_BetaProject_V2.0_Root"),
    )
)
DEFAULT_SOURCE = ENGINE_ROOT / "data" / "user" / "luna_engine.db"
DEFAULT_OUTPUT = FORGE_ROOT / "staging" / "filtered.db"


def main():
    parser = argparse.ArgumentParser(description="Luna Database Sanitizer")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Source database path")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output database path")
    parser.add_argument("--entities", type=str, default=None, help="Comma-separated entity IDs to include")
    parser.add_argument("--exclude-entities", type=str, default=None, help="Comma-separated entity IDs to exclude")
    parser.add_argument("--types", type=str, default=None, help="Comma-separated node types (FACT,DECISION,ACTION,...)")
    parser.add_argument("--min-confidence", type=float, default=0.0, help="Minimum confidence threshold (0.0-1.0)")
    parser.add_argument("--date-from", type=str, default=None, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--date-to", type=str, default=None, help="End date (YYYY-MM-DD)")
    parser.add_argument("--conversations", action="store_true", help="Include conversation history")
    parser.add_argument("--no-conversations", action="store_true", help="Exclude conversation history (default)")
    parser.add_argument("--preview", action="store_true", help="Preview only — don't create output DB")
    parser.add_argument("--list-entities", action="store_true", help="List all entities and exit")
    parser.add_argument("--list-types", action="store_true", help="List node type counts and exit")
    parser.add_argument("--stats", action="store_true", help="Show source DB stats and exit")

    args = parser.parse_args()

    config = SanitizeConfig(
        source_db=args.source,
        output_db=args.output,
        include_entities=args.entities.split(",") if args.entities else None,
        exclude_entities=args.exclude_entities.split(",") if args.exclude_entities else None,
        include_node_types=args.types.split(",") if args.types else None,
        min_confidence=args.min_confidence,
        date_from=args.date_from,
        date_to=args.date_to,
        include_conversations=args.conversations and not args.no_conversations,
    )

    sanitizer = DatabaseSanitizer(config)

    if args.stats:
        stats = sanitizer.get_source_stats()
        print(f"\n  Source: {args.source}")
        for k, v in stats.items():
            print(f"  {k}: {v}")
        return

    if args.list_entities:
        entities = sanitizer.list_entities()
        print(f"\n  {'ID':<25s} {'Type':<10s} {'Origin':<8s} {'Mentions':>8s}  Name")
        print(f"  {'─'*25} {'─'*10} {'─'*8} {'─'*8}  {'─'*20}")
        for e in entities:
            print(f"  {e['id']:<25s} {e['entity_type']:<10s} {e['origin']:<8s} {e['mention_count']:>8d}  {e['name']}")
        return

    if args.list_types:
        types = sanitizer.list_node_type_counts()
        print(f"\n  {'Type':<25s} {'Count':>8s}")
        print(f"  {'─'*25} {'─'*8}")
        for t, c in types.items():
            print(f"  {t:<25s} {c:>8,d}")
        return

    if args.preview:
        report = sanitizer.preview()
        print("\n  ── Preview ──")
        print(f"  Source: {report.source_stats.get('memory_nodes', 0):,d} nodes, {report.source_stats.get('entities', 0)} entities, {report.source_stats.get('size_mb', 0)} MB")
        print(f"  Output: {report.output_stats.get('memory_nodes', 0):,d} nodes, {report.output_stats.get('entities', 0)} entities, ~{report.output_stats.get('est_size_mb', 0)} MB")
        print(f"  Removed: {report.removed.get('memory_nodes', 0):,d} nodes, {report.removed.get('entities', 0)} entities")
        print(f"  Filters: {' | '.join(report.filters_applied)}")
        return

    # Execute
    print(f"\n  Sanitizing {args.source} → {args.output} ...")
    report = sanitizer.execute()
    print(f"  Nodes: {report.source_stats.get('memory_nodes', 0):,d} → {report.output_stats.get('memory_nodes', 0):,d}")
    print(f"  Entities: {report.source_stats.get('entities', 0)} → {report.output_stats.get('entities', 0)}")
    print(f"  Size: {report.source_stats.get('size_mb', 0)} MB → {report.output_stats.get('size_mb', 0)} MB")
    print(f"  Output: {args.output}")
    print(f"\n  To use in a build profile:")
    print(f"    database:")
    print(f"      mode: \"filtered\"")
    print(f"      source: \"{args.output}\"")


if __name__ == "__main__":
    main()
