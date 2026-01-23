#!/usr/bin/env python3
"""
Voice Diagnostics CLI - Analyze voice interaction quality.

Usage:
    python scripts/voice_diagnostics.py           # Print summary
    python scripts/voice_diagnostics.py --recent  # Show recent traces
    python scripts/voice_diagnostics.py --export  # Export to JSON
"""
import sys
import json
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.voice.diagnostics import get_tracer


def main():
    parser = argparse.ArgumentParser(description="Voice interaction diagnostics")
    parser.add_argument("--recent", "-r", type=int, default=0,
                        help="Show last N traces (default: summary only)")
    parser.add_argument("--export", "-e", action="store_true",
                        help="Export summary as JSON")
    args = parser.parse_args()

    tracer = get_tracer()

    if args.export:
        summary = tracer.get_quality_summary()
        print(json.dumps(summary, indent=2))
        return

    if args.recent > 0:
        traces = tracer.get_recent_traces(args.recent)
        if not traces:
            print("No traces found.")
            return

        print(f"\n📋 Last {len(traces)} interactions:\n")
        for i, t in enumerate(traces, 1):
            quality = []
            if t.get("contains_fallback_phrase"):
                quality.append("🔴 fallback")
            if t.get("contains_identity_confusion"):
                quality.append("🔴 identity")
            if t.get("contains_memory_reference"):
                quality.append("🟢 memory")

            quality_str = " ".join(quality) if quality else "✓"

            print(f"{i}. [{t.get('route_decision', '?'):10}] {t.get('response_time_ms', 0):.0f}ms")
            print(f"   User: \"{t.get('user_message', '')[:60]}...\"")
            print(f"   Context: {t.get('conversation_history_length', 0)} turns, {t.get('memory_nodes_count', 0)} memories")
            print(f"   Quality: {quality_str}")
            print()
        return

    # Default: Print summary
    tracer.print_summary()


if __name__ == "__main__":
    main()
