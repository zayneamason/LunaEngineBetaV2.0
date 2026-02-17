#!/usr/bin/env python3
"""
Extraction Sample Test - Test extractor on 5-10 GOLD conversations

Validates extraction quality before running full batch:
- Node extraction (FACT, DECISION, etc.)
- OBSERVATION nodes (why it mattered)
- Entity extraction
- Edge generation (intra-conversation)
- Texture tags
"""

import sys
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime
from anthropic import AsyncAnthropic

sys.path.insert(0, str(Path(__file__).parent))

from mcp_server.ingester.scanner import TranscriptScanner
from mcp_server.ingester.extractor import TranscriptExtractor


class AnthropicClient:
    """Adapter for Anthropic SDK."""

    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.call_count = 0

    async def create(self, model: str, max_tokens: int, messages: list):
        """Call Anthropic API and track usage."""
        response = await self.client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=messages
        )

        self.total_input_tokens += response.usage.input_tokens
        self.total_output_tokens += response.usage.output_tokens
        self.call_count += 1

        return response

    def get_cost(self):
        """Calculate cost (Sonnet 4.5: $3/M in, $15/M out)."""
        input_cost = (self.total_input_tokens / 1_000_000) * 3.0
        output_cost = (self.total_output_tokens / 1_000_000) * 15.0
        return input_cost + output_cost


async def main():
    print("=" * 70)
    print("EXTRACTION SAMPLE TEST - 10 GOLD Conversations")
    print("=" * 70)

    # ========================================================================
    # Setup
    # ========================================================================

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("\n❌ ERROR: ANTHROPIC_API_KEY not set")
        return 1

    # Load triage results
    triage_path = Path(__file__).parent / "ingester_triage_full.json"
    if not triage_path.exists():
        print(f"\n❌ ERROR: {triage_path} not found")
        print("Run run_full_triage.py first")
        return 1

    with open(triage_path) as f:
        triage_data = json.load(f)

    gold_conversations = [
        c for c in triage_data["classified_conversations"]
        if c.get("tier") == "GOLD"
    ]

    print(f"\n✓ Found {len(gold_conversations)} GOLD conversations")

    # ========================================================================
    # Select Sample
    # ========================================================================

    print("\n[1/3] Selecting diverse sample...")

    # Strategy: diverse by era, length, and topic
    sample = []

    # 2 from 2026 (LUNA_LIVE)
    from_2026 = [c for c in gold_conversations if c["created_at"].startswith("2026")]
    sample.extend(sorted(from_2026, key=lambda c: c["message_count"], reverse=True)[:2])

    # 5 from 2025 (LUNA_DEV) - different lengths
    from_2025 = [c for c in gold_conversations if c["created_at"].startswith("2025")]
    from_2025_sorted = sorted(from_2025, key=lambda c: c["message_count"], reverse=True)
    sample.extend([
        from_2025_sorted[0],           # Longest
        from_2025_sorted[len(from_2025_sorted)//4],  # Upper-mid
        from_2025_sorted[len(from_2025_sorted)//2],  # Median
        from_2025_sorted[-len(from_2025_sorted)//4], # Lower-mid
        from_2025_sorted[-1],          # Shortest
    ])

    # 3 from 2024 (PROTO_LUNA) if available
    from_2024 = [c for c in gold_conversations if c["created_at"].startswith("2024")]
    sample.extend(from_2024[:min(3, len(from_2024))])

    # Limit to 10
    sample = sample[:10]

    print(f"\n📊 Sample composition ({len(sample)} conversations):")
    for conv in sample:
        print(f"  [{conv['created_at'][:10]}] {conv['title'][:50]}")
        print(f"      {conv['message_count']} messages, texture: {', '.join(conv.get('texture', []))}")

    total_messages = sum(c["message_count"] for c in sample)
    print(f"\n  Total messages: {total_messages}")
    print(f"  Estimated cost: ~${len(sample) * 0.04:.2f}")

    # ========================================================================
    # Run Extraction
    # ========================================================================

    print("\n[2/3] Running extraction...")

    transcript_dir = Path(__file__).parent / "_CLAUDE_TRANSCRIPTS" / "Conversations"
    scanner = TranscriptScanner(str(transcript_dir))

    llm_client = AnthropicClient(api_key)
    extractor = TranscriptExtractor(llm_client=llm_client)

    results = []
    start_time = datetime.now()

    for i, conv in enumerate(sample, 1):
        print(f"\n  [{i}/{len(sample)}] Extracting: {conv['title'][:50]}...")

        try:
            result = await extractor.extract_conversation(
                conversation=conv,
                tier="GOLD",
                scanner=scanner,
            )

            results.append({
                "conversation": conv,
                "extraction": result,
            })

            # Show quick stats
            nodes = len(result.get("nodes", []))
            obs = len(result.get("observations", []))
            entities = len(result.get("entities", []))
            edges = len(result.get("edges", []))

            print(f"      ✓ {nodes} nodes, {obs} observations, {entities} entities, {edges} edges")

        except Exception as e:
            print(f"      ❌ Failed: {e}")
            results.append({
                "conversation": conv,
                "extraction": {
                    "extraction_status": "failed",
                    "error_message": str(e),
                },
            })

    elapsed = (datetime.now() - start_time).total_seconds()

    # ========================================================================
    # Analysis
    # ========================================================================

    print("\n" + "=" * 70)
    print("[3/3] RESULTS")
    print("=" * 70)

    # Token usage
    print(f"\n💰 API Usage:")
    print(f"  Calls:  {llm_client.call_count}")
    print(f"  Input:  {llm_client.total_input_tokens:,} tokens")
    print(f"  Output: {llm_client.total_output_tokens:,} tokens")
    print(f"  Cost:   ${llm_client.get_cost():.2f}")
    print(f"  Time:   {elapsed:.1f}s ({elapsed/len(sample):.1f}s per conversation)")

    # Extraction stats
    successful = [r for r in results if r["extraction"].get("extraction_status") == "complete"]
    partial = [r for r in results if r["extraction"].get("extraction_status") == "partial"]
    failed = [r for r in results if r["extraction"].get("extraction_status") == "failed"]

    print(f"\n📊 Extraction Results:")
    print(f"  Complete: {len(successful)}/{len(results)}")
    print(f"  Partial:  {len(partial)}/{len(results)}")
    print(f"  Failed:   {len(failed)}/{len(results)}")

    if successful:
        # Aggregate stats
        total_nodes = sum(len(r["extraction"].get("nodes", [])) for r in successful)
        total_obs = sum(len(r["extraction"].get("observations", [])) for r in successful)
        total_entities = sum(len(r["extraction"].get("entities", [])) for r in successful)
        total_edges = sum(len(r["extraction"].get("edges", [])) for r in successful)

        print(f"\n📈 Aggregated Extraction:")
        print(f"  Nodes:        {total_nodes} ({total_nodes/len(successful):.1f} per conversation)")
        print(f"  Observations: {total_obs} ({total_obs/len(successful):.1f} per conversation)")
        print(f"  Entities:     {total_entities} ({total_entities/len(successful):.1f} per conversation)")
        print(f"  Edges:        {total_edges} ({total_edges/len(successful):.1f} per conversation)")

        # Node type distribution
        node_types = {}
        for r in successful:
            for node in r["extraction"].get("nodes", []):
                ntype = node.get("type", "UNKNOWN")
                node_types[ntype] = node_types.get(ntype, 0) + 1

        print(f"\n🎯 Node Type Distribution:")
        for ntype in sorted(node_types, key=node_types.get, reverse=True):
            count = node_types[ntype]
            pct = (count / total_nodes) * 100 if total_nodes > 0 else 0
            print(f"  {ntype:10}: {count:3} ({pct:5.1f}%)")

    # ========================================================================
    # Show Sample Extractions
    # ========================================================================

    if successful:
        print("\n" + "=" * 70)
        print("SAMPLE EXTRACTIONS")
        print("=" * 70)

        # Show first 2 successful extractions
        for r in successful[:2]:
            conv = r["conversation"]
            ext = r["extraction"]

            print(f"\n📝 {conv['title']}")
            print(f"   Date: {conv['created_at'][:10]}, Messages: {conv['message_count']}")
            print(f"   Texture: {', '.join(conv.get('texture', []))}")

            # Show nodes
            print(f"\n   NODES ({len(ext.get('nodes', []))}):")
            for i, node in enumerate(ext.get("nodes", [])[:3], 1):
                print(f"      {i}. [{node['type']}] {node['content'][:80]}...")
                print(f"         Confidence: {node.get('confidence', 0):.2f}")

            # Show observations
            if ext.get("observations"):
                print(f"\n   OBSERVATIONS ({len(ext['observations'])}):")
                for i, obs in enumerate(ext["observations"][:2], 1):
                    print(f"      {i}. {obs['content'][:80]}...")

            # Show entities
            if ext.get("entities"):
                print(f"\n   ENTITIES ({len(ext['entities'])}):")
                entity_names = [e.get("name", "?") for e in ext["entities"][:5]]
                print(f"      {', '.join(entity_names)}")

            # Show edges
            if ext.get("edges"):
                print(f"\n   EDGES ({len(ext['edges'])}):")
                for i, edge in enumerate(ext["edges"][:3], 1):
                    from_idx = edge.get("from_node_index", "?")
                    to_idx = edge.get("to_node_index", "?")
                    etype = edge.get("edge_type", "?")
                    print(f"      {i}. Node {from_idx} --{etype}--> Node {to_idx}")

    # ========================================================================
    # Save Results
    # ========================================================================

    output_path = Path(__file__).parent / "extraction_sample_results.json"
    with open(output_path, 'w') as f:
        json.dump({
            "sample_size": len(sample),
            "successful": len(successful),
            "partial": len(partial),
            "failed": len(failed),
            "token_usage": {
                "calls": llm_client.call_count,
                "input_tokens": llm_client.total_input_tokens,
                "output_tokens": llm_client.total_output_tokens,
                "cost_usd": llm_client.get_cost(),
            },
            "results": results,
        }, f, indent=2)

    print(f"\n\n✓ Saved results to: {output_path}")

    print("\n" + "=" * 70)
    print("✅ Extraction Sample Test Complete")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
