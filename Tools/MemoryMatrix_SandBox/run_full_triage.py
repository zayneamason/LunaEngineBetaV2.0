#!/usr/bin/env python3
"""
Full Triage - Run Sonnet classification on all 928 conversations

Two-pass triage:
1. Metadata pre-filter (instant, no LLM) → auto-SKIP low scorers
2. Sonnet classification (batched) → tier assignments for the rest

Cost: ~$2.25
Time: ~10-15 minutes
Output: ingester_triage_full.yaml for human review
"""

import sys
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime
from anthropic import AsyncAnthropic

# Add mcp_server to path
sys.path.insert(0, str(Path(__file__).parent))

from mcp_server.ingester.scanner import TranscriptScanner
from mcp_server.ingester.triager import TranscriptTriager


class AnthropicClient:
    """Adapter for Anthropic SDK."""

    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    async def create(self, model: str, max_tokens: int, messages: list):
        """Call Anthropic API and track token usage."""
        response = await self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages
        )

        # Track usage
        self.total_input_tokens += response.usage.input_tokens
        self.total_output_tokens += response.usage.output_tokens

        return response

    def get_cost(self):
        """Calculate approximate cost."""
        # Sonnet 4.5 pricing: $3/M input, $15/M output
        input_cost = (self.total_input_tokens / 1_000_000) * 3.0
        output_cost = (self.total_output_tokens / 1_000_000) * 15.0
        return input_cost + output_cost


async def main():
    print("=" * 70)
    print("FULL TRIAGE - 928 Conversations")
    print("=" * 70)
    print(f"\nStarted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ========================================================================
    # Setup
    # ========================================================================

    # Check for API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("\n❌ ERROR: ANTHROPIC_API_KEY environment variable not set")
        return 1

    print(f"✓ API key found")

    # Load inventory
    inventory_path = Path(__file__).parent / "ingester_inventory.json"
    if not inventory_path.exists():
        print(f"\n❌ ERROR: Inventory not found")
        print("Run test_ingester_phase1.py first")
        return 1

    with open(inventory_path) as f:
        inventory = json.load(f)

    print(f"✓ Loaded inventory: {inventory['total_conversations']} conversations")

    # ========================================================================
    # PASS 1: Metadata Pre-filter
    # ========================================================================

    print("\n" + "=" * 70)
    print("PASS 1: Metadata Pre-filter (no LLM)")
    print("=" * 70)

    triager = TranscriptTriager()
    prefilter_results = triager.prefilter(inventory['conversations'])

    auto_skip = prefilter_results['auto_skip']
    needs_llm = prefilter_results['needs_llm']

    print(f"\nResults:")
    print(f"  Auto-SKIP (score < 1.5): {len(auto_skip):4} ({len(auto_skip)/inventory['total_conversations']*100:5.1f}%)")
    print(f"  Needs LLM classification: {len(needs_llm):4} ({len(needs_llm)/inventory['total_conversations']*100:5.1f}%)")

    # ========================================================================
    # PASS 2: Sonnet Classification
    # ========================================================================

    print("\n" + "=" * 70)
    print("PASS 2: Sonnet Classification (batched)")
    print("=" * 70)

    print(f"\nConversations to classify: {len(needs_llm)}")
    print(f"Batch size: 10 conversations per call")
    print(f"Estimated batches: ~{len(needs_llm) // 10 + 1}")
    print(f"Estimated cost: ~${(len(needs_llm) / 10) * 0.025:.2f}")
    print(f"Model: claude-sonnet-4-5-20250929")

    # Confirm before proceeding
    print("\n⚠️  This will make ~{} API calls. Continue? [y/N] ".format(len(needs_llm) // 10 + 1), end='')

    # Auto-confirm in non-interactive mode
    if not sys.stdin.isatty():
        print("y (auto-confirmed in non-interactive mode)")
        confirm = 'y'
    else:
        confirm = input().strip().lower()

    if confirm != 'y':
        print("\n❌ Aborted by user")
        return 0

    # Initialize scanner and LLM client
    transcript_dir = Path(__file__).parent / "_CLAUDE_TRANSCRIPTS" / "Conversations"
    scanner = TranscriptScanner(str(transcript_dir))

    llm_client = AnthropicClient(api_key)
    triager_with_llm = TranscriptTriager(llm_client=llm_client)

    # Run classification with progress updates
    print("\nClassifying...")
    start_time = datetime.now()

    try:
        classified = await triager_with_llm.classify_batch(
            conversations=needs_llm,
            scanner=scanner,
            batch_size=10
        )

        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n✓ Classification complete in {elapsed:.1f}s")

    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        print(f"Processed {llm_client.total_input_tokens} input tokens so far")
        return 1
    except Exception as e:
        print(f"\n❌ Classification failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # ========================================================================
    # Results & Statistics
    # ========================================================================

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    # Token usage and cost
    print(f"\n💰 Token Usage:")
    print(f"  Input:  {llm_client.total_input_tokens:,} tokens")
    print(f"  Output: {llm_client.total_output_tokens:,} tokens")
    print(f"  Cost:   ${llm_client.get_cost():.2f}")

    # Tier distribution
    tier_counts = {"GOLD": 0, "SILVER": 0, "BRONZE": 0, "SKIP": len(auto_skip)}

    for conv in classified:
        tier = conv.get('tier', 'BRONZE')
        tier_counts[tier] += 1

    total = inventory['total_conversations']

    print(f"\n📊 Tier Distribution:")
    print(f"  GOLD:   {tier_counts['GOLD']:4} ({tier_counts['GOLD']/total*100:5.1f}%)")
    print(f"  SILVER: {tier_counts['SILVER']:4} ({tier_counts['SILVER']/total*100:5.1f}%)")
    print(f"  BRONZE: {tier_counts['BRONZE']:4} ({tier_counts['BRONZE']/total*100:5.1f}%)")
    print(f"  SKIP:   {tier_counts['SKIP']:4} ({tier_counts['SKIP']/total*100:5.1f}%)")

    # Texture distribution
    texture_counts = {}
    for conv in classified:
        for tag in conv.get('texture', []):
            texture_counts[tag] = texture_counts.get(tag, 0) + 1

    print(f"\n🎨 Texture Tag Distribution:")
    for tag in sorted(texture_counts, key=texture_counts.get, reverse=True):
        count = texture_counts[tag]
        print(f"  {tag:12}: {count:4}")

    # Era breakdown
    print(f"\n📅 GOLD Tier by Era:")
    gold_by_era = {"2023": 0, "2024": 0, "2025": 0, "2026": 0}
    for conv in classified:
        if conv.get('tier') == 'GOLD':
            year = conv['created_at'][:4]
            gold_by_era[year] = gold_by_era.get(year, 0) + 1

    for year in sorted(gold_by_era.keys()):
        count = gold_by_era[year]
        print(f"  {year}: {count:4}")

    # ========================================================================
    # Export for Review
    # ========================================================================

    print("\n" + "=" * 70)
    print("EXPORT")
    print("=" * 70)

    output_path = Path(__file__).parent / "ingester_triage_full.yaml"

    triager.export_for_review(
        classified=classified,
        auto_skipped=auto_skip,
        output_path=str(output_path)
    )

    print(f"\n✓ Saved triage results to:")
    print(f"  {output_path}")
    print(f"\n  Total size: {output_path.stat().st_size / 1024:.1f} KB")

    # Also save JSON for programmatic use
    json_path = Path(__file__).parent / "ingester_triage_full.json"
    with open(json_path, 'w') as f:
        json.dump({
            "total_conversations": total,
            "tier_counts": tier_counts,
            "texture_distribution": texture_counts,
            "gold_by_era": gold_by_era,
            "token_usage": {
                "input_tokens": llm_client.total_input_tokens,
                "output_tokens": llm_client.total_output_tokens,
                "cost_usd": llm_client.get_cost(),
            },
            "classified_conversations": classified,
            "auto_skipped_conversations": auto_skip,
        }, f, indent=2)

    print(f"✓ Saved JSON to: {json_path}")

    # ========================================================================
    # Next Steps
    # ========================================================================

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)

    print(f"\n1. Review triage assignments:")
    print(f"   open {output_path}")
    print(f"\n2. Edit tier assignments if needed (change GOLD→SILVER, etc.)")
    print(f"\n3. Re-run this script to update, or proceed to extraction:")
    print(f"   python run_extraction.py --tier GOLD")
    print(f"\n4. GOLD tier: {tier_counts['GOLD']} conversations")
    print(f"   Estimated extraction cost: ${tier_counts['GOLD'] * 0.04:.2f}")
    print(f"   Estimated time: ~{tier_counts['GOLD'] / 5:.0f} minutes")

    print("\n" + "=" * 70)
    print("✅ Full Triage Complete")
    print("=" * 70)
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
