#!/usr/bin/env python3
"""
LLM Triage Test - Validate Sonnet classification on real conversations

Tests the Sonnet-based tier classification on a sample of conversations
to validate prompt quality before running full batch ingestion.
"""

import sys
import os
import json
import asyncio
from pathlib import Path
from anthropic import AsyncAnthropic

# Add mcp_server to path
sys.path.insert(0, str(Path(__file__).parent))

from mcp_server.ingester.scanner import TranscriptScanner
from mcp_server.ingester.triager import TranscriptTriager


class AnthropicClient:
    """Adapter for Anthropic SDK to match triager's expected interface."""

    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)

    async def create(self, model: str, max_tokens: int, messages: list):
        """Call Anthropic API."""
        response = await self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages
        )
        return response


async def main():
    print("=" * 70)
    print("LLM TRIAGE TEST - Real Sonnet Classification")
    print("=" * 70)

    # ========================================================================
    # Setup
    # ========================================================================

    # Check for API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("\n❌ ERROR: ANTHROPIC_API_KEY environment variable not set")
        print("\nSet it with:")
        print("  export ANTHROPIC_API_KEY='your-key-here'")
        return 1

    print(f"\n✓ API key found (ending in ...{api_key[-8:]})")

    # Load inventory
    inventory_path = Path(__file__).parent / "ingester_inventory.json"
    if not inventory_path.exists():
        print(f"\n❌ ERROR: Inventory not found at {inventory_path}")
        print("Run test_ingester_phase1.py first to generate inventory")
        return 1

    with open(inventory_path) as f:
        inventory = json.load(f)

    print(f"✓ Loaded inventory: {inventory['total_conversations']} conversations")

    # ========================================================================
    # Select Test Sample
    # ========================================================================

    print("\n[1/3] Selecting test sample...")

    # Sample strategy: diverse score range
    conversations = inventory['conversations']

    # Quick metadata scoring
    triager = TranscriptTriager()
    for conv in conversations:
        conv['prefilter_score'] = triager._metadata_score(conv)

    # Sort by score
    sorted_convs = sorted(conversations, key=lambda c: c['prefilter_score'], reverse=True)

    # Sample: 5 high-score, 5 mid-score, 5 low-score
    sample = (
        sorted_convs[:5] +                    # Top 5 (likely GOLD)
        sorted_convs[len(sorted_convs)//2 - 2:len(sorted_convs)//2 + 3] +  # 5 from middle
        sorted_convs[-5:]                     # Bottom 5 (likely SKIP/BRONZE)
    )

    print(f"\n📊 Sample composition:")
    print(f"  High-score (≥8.0):  {sum(1 for c in sample if c['prefilter_score'] >= 8.0)}")
    print(f"  Mid-score (4.0-8.0): {sum(1 for c in sample if 4.0 <= c['prefilter_score'] < 8.0)}")
    print(f"  Low-score (<4.0):   {sum(1 for c in sample if c['prefilter_score'] < 4.0)}")

    # ========================================================================
    # Run LLM Classification
    # ========================================================================

    print("\n[2/3] Running Sonnet classification...")
    print(f"  Batch size: 10 conversations per call")
    print(f"  Model: claude-sonnet-4-5-20250929")
    print(f"  Estimated cost: ~$0.05-0.10")
    print()

    # Initialize scanner and triager with LLM client
    transcript_dir = Path(__file__).parent / "_CLAUDE_TRANSCRIPTS" / "Conversations"
    scanner = TranscriptScanner(str(transcript_dir))

    llm_client = AnthropicClient(api_key)
    triager_with_llm = TranscriptTriager(llm_client=llm_client)

    # Classify sample
    try:
        classified = await triager_with_llm.classify_batch(
            conversations=sample,
            scanner=scanner,
            batch_size=10
        )
        print("✓ Classification complete")
    except Exception as e:
        print(f"\n❌ Classification failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ========================================================================
    # Analyze Results
    # ========================================================================

    print("\n[3/3] Analyzing results...")

    # Compare LLM vs simulated tiers
    tier_comparison = {
        "matches": 0,
        "differs": 0,
        "llm_more_valuable": 0,   # LLM rated higher
        "llm_less_valuable": 0,   # LLM rated lower
    }

    tier_rank = {"GOLD": 3, "SILVER": 2, "BRONZE": 1, "SKIP": 0}

    print("\n📊 LLM Classification Results:\n")
    print(f"{'Score':<7} {'Simulated':<10} {'LLM Tier':<10} {'Title':<50}")
    print("-" * 80)

    for conv in classified:
        # Simulate tier from score (for comparison)
        score = conv['prefilter_score']
        if score >= 8:
            simulated_tier = "GOLD"
        elif score >= 4:
            simulated_tier = "SILVER"
        elif score >= 1.5:
            simulated_tier = "BRONZE"
        else:
            simulated_tier = "SKIP"

        llm_tier = conv.get('tier', 'UNKNOWN')
        title = conv['title'][:47] + "..." if len(conv['title']) > 50 else conv['title']

        # Compare
        if simulated_tier == llm_tier:
            tier_comparison["matches"] += 1
            marker = "✓"
        else:
            tier_comparison["differs"] += 1
            if tier_rank[llm_tier] > tier_rank[simulated_tier]:
                tier_comparison["llm_more_valuable"] += 1
                marker = "↑"  # LLM rated higher
            else:
                tier_comparison["llm_less_valuable"] += 1
                marker = "↓"  # LLM rated lower

        print(f"{score:<7.1f} {simulated_tier:<10} {llm_tier:<10} {marker} {title}")

    # Summary stats
    total = len(classified)
    match_pct = (tier_comparison["matches"] / total) * 100

    print("\n" + "=" * 80)
    print(f"📈 Agreement: {tier_comparison['matches']}/{total} ({match_pct:.1f}%)")
    print(f"   Differs: {tier_comparison['differs']}")
    print(f"     ↑ LLM rated higher: {tier_comparison['llm_more_valuable']}")
    print(f"     ↓ LLM rated lower: {tier_comparison['llm_less_valuable']}")

    # Show texture tag distribution
    texture_counts = {}
    for conv in classified:
        for tag in conv.get('texture', []):
            texture_counts[tag] = texture_counts.get(tag, 0) + 1

    print(f"\n🎨 Texture Tags:")
    for tag, count in sorted(texture_counts.items(), key=lambda x: -x[1]):
        print(f"   {tag}: {count}")

    # ========================================================================
    # Show Interesting Examples
    # ========================================================================

    print("\n💡 Interesting Classifications:\n")

    # Where LLM rated much higher than metadata
    print("LLM rated GOLD but metadata scored low (<5.0):")
    for conv in classified:
        if conv['tier'] == 'GOLD' and conv['prefilter_score'] < 5.0:
            print(f"  [{conv['prefilter_score']:.1f}] {conv['title']}")
            print(f"      Summary: {conv.get('summary', 'N/A')[:70]}...")
            print()

    # Where LLM rated lower than metadata
    print("LLM rated BRONZE/SKIP but metadata scored high (≥8.0):")
    for conv in classified:
        if conv['tier'] in ['BRONZE', 'SKIP'] and conv['prefilter_score'] >= 8.0:
            print(f"  [{conv['prefilter_score']:.1f}] {conv['title']}")
            print(f"      Summary: {conv.get('summary', 'N/A')[:70]}...")
            print()

    # ========================================================================
    # Save Results
    # ========================================================================

    output_path = Path(__file__).parent / "llm_triage_test_results.json"
    with open(output_path, 'w') as f:
        json.dump({
            "sample_size": len(classified),
            "tier_comparison": tier_comparison,
            "texture_distribution": texture_counts,
            "classified_conversations": classified,
        }, f, indent=2)

    print(f"✓ Saved results to: {output_path}")

    print("\n" + "=" * 70)
    print("✅ LLM Triage Test Complete")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
