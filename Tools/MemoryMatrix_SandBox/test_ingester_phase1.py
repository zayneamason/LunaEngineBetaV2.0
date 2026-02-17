#!/usr/bin/env python3
"""
Integration Test - Scanner + Triager

Tests the first two phases of the ingestion pipeline on real data.
"""

import sys
import asyncio
from pathlib import Path

# Add mcp_server to path
sys.path.insert(0, str(Path(__file__).parent))

from mcp_server.ingester.scanner import TranscriptScanner
from mcp_server.ingester.triager import TranscriptTriager


async def main():
    print("=" * 70)
    print("TRANSCRIPT INGESTER - Phase 1 Integration Test")
    print("=" * 70)

    # ========================================================================
    # PHASE 0: Scanner
    # ========================================================================

    print("\n[1/3] SCANNER: Scanning transcript directory...")

    # Locate transcript directory
    transcript_dir = None
    possible_paths = [
        Path(__file__).parent / "_CLAUDE_TRANSCRIPTS" / "Conversations",  # In sandbox
        Path.home() / "_CLAUDE_TRANSCRIPTS" / "Conversations",
        Path("/Users/zayneamason/_CLAUDE_TRANSCRIPTS/Conversations"),
        Path("/Users/zayneamason/_HeyLuna_BETA/_CLAUDE_TRANSCRIPTS/Conversations"),
    ]

    for path in possible_paths:
        if path.exists():
            transcript_dir = path
            break

    if not transcript_dir:
        print("❌ ERROR: Could not find _CLAUDE_TRANSCRIPTS/Conversations directory")
        print("\nSearched:")
        for path in possible_paths:
            print(f"  - {path}")
        return 1

    print(f"✓ Found transcript directory: {transcript_dir}")

    # Scan
    scanner = TranscriptScanner(str(transcript_dir))
    inventory = scanner.scan()

    print(f"\n📊 Inventory Summary:")
    print(f"  Total conversations: {inventory['total_conversations']}")
    print(f"  Date directories: {inventory['total_date_dirs']}")
    print(f"  Date range: {inventory['date_range']['earliest']} → {inventory['date_range']['latest']}")
    print(f"  Total size: {inventory['size_mb']} MB")
    print(f"  Errors: {len(inventory['errors'])}")

    if inventory['errors']:
        print("\n⚠️  Scan errors:")
        for err in inventory['errors'][:5]:
            print(f"  - {err['path']}: {err['error']}")

    print(f"\n📅 By Year:")
    for year, count in sorted(inventory['by_year'].items()):
        print(f"  {year}: {count} conversations")

    # Save inventory
    inventory_path = Path(__file__).parent / "ingester_inventory.json"
    scanner.export_inventory(inventory, str(inventory_path))
    print(f"\n✓ Saved inventory to: {inventory_path}")

    # ========================================================================
    # PHASE 1: Triager - Metadata Prefilter
    # ========================================================================

    print("\n[2/3] TRIAGER: Metadata pre-filter (no LLM)...")

    triager = TranscriptTriager()
    prefilter_results = triager.prefilter(inventory['conversations'])

    print(f"\n📊 Pre-filter Results:")
    print(f"  Auto-SKIP (score < 1.5): {len(prefilter_results['auto_skip'])}")
    print(f"  Needs LLM classification: {len(prefilter_results['needs_llm'])}")

    # Show score distribution
    scores = [c['prefilter_score'] for c in inventory['conversations']]
    print(f"\n📈 Score Distribution:")
    print(f"  Min: {min(scores):.1f}")
    print(f"  Max: {max(scores):.1f}")
    print(f"  Avg: {sum(scores)/len(scores):.1f}")

    # Show some examples
    print(f"\n🔍 Sample High-Scoring Conversations (likely GOLD/SILVER):")
    high_scorers = sorted(
        prefilter_results['needs_llm'],
        key=lambda c: c['prefilter_score'],
        reverse=True
    )[:5]

    for conv in high_scorers:
        print(f"\n  [{conv['prefilter_score']:.1f}] {conv['title']}")
        print(f"      Date: {conv['created_at'][:10]}, Messages: {conv['message_count']}")

    # ========================================================================
    # PHASE 2: Triager - Sonnet Classification (OPTIONAL - needs API key)
    # ========================================================================

    print("\n[3/3] TRIAGER: Sonnet classification...")
    print("⚠️  Skipping LLM classification (requires Anthropic API client)")
    print("    To test this phase, provide an Anthropic client to TranscriptTriager()")

    # For now, simulate tier assignments
    print("\n💡 Simulating tier assignments based on prefilter scores:")

    simulated_tiers = []
    for conv in inventory['conversations']:
        score = conv.get('prefilter_score', 0)

        # Simulate tier based on score
        if score >= 8:
            tier = "GOLD"
        elif score >= 4:
            tier = "SILVER"
        elif score >= 1.5:
            tier = "BRONZE"
        else:
            tier = "SKIP"

        simulated_tiers.append({
            **conv,
            "tier": tier,
            "summary": f"(simulated) {conv['title'][:60]}",
            "texture": ["working"],  # Placeholder
        })

    # Export for review
    review_path = Path(__file__).parent / "ingester_triage_simulated.yaml"
    triager.export_for_review(
        classified=[c for c in simulated_tiers if c['tier'] != "SKIP"],
        auto_skipped=[c for c in simulated_tiers if c['tier'] == "SKIP"],
        output_path=str(review_path)
    )

    print(f"\n✓ Saved simulated triage to: {review_path}")

    tier_counts = {}
    for conv in simulated_tiers:
        tier = conv['tier']
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    print(f"\n📊 Simulated Tier Distribution:")
    for tier in ["GOLD", "SILVER", "BRONZE", "SKIP"]:
        count = tier_counts.get(tier, 0)
        pct = (count / len(simulated_tiers)) * 100
        print(f"  {tier:8}: {count:4} ({pct:5.1f}%)")

    # ========================================================================
    # Summary
    # ========================================================================

    print("\n" + "=" * 70)
    print("✅ Phase 1 Integration Test Complete")
    print("=" * 70)
    print("\nNext Steps:")
    print("1. Review ingester_triage_simulated.yaml")
    print("2. To test real LLM classification, add Anthropic client")
    print("3. Build Phase 2: Extractor")

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
