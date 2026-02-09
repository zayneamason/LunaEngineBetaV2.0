#!/usr/bin/env python3
"""
Prompt Dissection Analyzer
==========================

Reads captured prompts from prompt_archaeology.jsonl and produces
detailed composition analysis.

Usage:
    python scripts/analyze_prompts.py
"""

import json
from pathlib import Path
from collections import defaultdict


def analyze_prompts():
    """Analyze captured prompts and produce composition report."""
    log_path = Path("data/diagnostics/prompt_archaeology.jsonl")

    if not log_path.exists():
        print("No prompt_archaeology.jsonl found. Run prompt_archaeology.py first.")
        return

    prompts = []
    with open(log_path) as f:
        for line in f:
            if line.strip():
                prompts.append(json.loads(line))

    if not prompts:
        print("No prompts captured yet.")
        return

    print(f"\n{'='*70}")
    print(f"PROMPT COMPOSITION ANALYSIS ({len(prompts)} samples)")
    print(f"{'='*70}\n")

    # Aggregate section statistics
    section_stats = defaultdict(lambda: {"count": 0, "total_tokens": 0, "total_percent": 0})

    for prompt in prompts:
        for section_name, section_data in prompt.get("sections", {}).items():
            section_stats[section_name]["count"] += 1
            section_stats[section_name]["total_tokens"] += section_data.get("tokens_approx", 0)
            section_stats[section_name]["total_percent"] += section_data.get("percent", 0)

    # Sort by average percentage (highest first)
    sorted_sections = sorted(
        section_stats.items(),
        key=lambda x: x[1]["total_percent"] / max(x[1]["count"], 1),
        reverse=True
    )

    print("SECTION BREAKDOWN (average across all captured prompts):")
    print("-" * 70)
    print(f"{'Section':<30} {'Avg Tokens':>12} {'Avg %':>10} {'Frequency':>12}")
    print("-" * 70)

    for section_name, stats in sorted_sections:
        avg_tokens = stats["total_tokens"] / max(stats["count"], 1)
        avg_percent = stats["total_percent"] / max(stats["count"], 1)
        print(f"{section_name:<30} {avg_tokens:>12.0f} {avg_percent:>9.1f}% {stats['count']:>12}")

    print("-" * 70)

    # Overall statistics
    total_tokens_all = sum(p.get("total_tokens_approx", 0) for p in prompts)
    avg_total = total_tokens_all / len(prompts)

    print(f"\nOVERALL STATISTICS:")
    print(f"  Average prompt size: {avg_total:.0f} tokens")
    print(f"  Total prompts captured: {len(prompts)}")

    # Check for pollution warnings
    warnings = [p.get("pollution_warning") for p in prompts if p.get("pollution_warning")]
    if warnings:
        print(f"\nPOLLUTION WARNINGS ({len(warnings)}):")
        for w in set(warnings):
            print(f"  - {w}")

    # Voice examples analysis (the main suspect)
    voice_sections = [
        p["sections"]["VOICE_EXAMPLES"]
        for p in prompts
        if "VOICE_EXAMPLES" in p.get("sections", {})
    ]

    if voice_sections:
        avg_voice_tokens = sum(v["tokens_approx"] for v in voice_sections) / len(voice_sections)
        avg_voice_percent = sum(v["percent"] for v in voice_sections) / len(voice_sections)

        print(f"\nVOICE EXAMPLES ANALYSIS (SUSPECT SECTION):")
        print(f"  Present in: {len(voice_sections)}/{len(prompts)} prompts")
        print(f"  Average size: {avg_voice_tokens:.0f} tokens ({avg_voice_percent:.1f}%)")

        if avg_voice_percent > 15:
            print(f"  ⚠️  WARNING: Voice examples > 15% of prompt — HIGH copying risk")
        elif avg_voice_percent > 10:
            print(f"  ⚠️  CAUTION: Voice examples > 10% of prompt — moderate copying risk")
        else:
            print(f"  ✓ Voice examples < 10% — acceptable range")

    # Per-query breakdown
    print(f"\n{'='*70}")
    print("PER-QUERY BREAKDOWN:")
    print(f"{'='*70}")

    for i, prompt in enumerate(prompts):
        print(f"\n[{i+1}] Query: '{prompt.get('query', '?')[:50]}...'")
        print(f"    Route: {prompt.get('route', '?')}")
        print(f"    Total: {prompt.get('total_tokens_approx', 0)} tokens")
        print(f"    Sections: {len(prompt.get('sections', {}))}")

        if prompt.get("pollution_warning"):
            print(f"    ⚠️  {prompt['pollution_warning']}")

    print(f"\n{'='*70}")
    print("Analysis complete.")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    analyze_prompts()
