#!/usr/bin/env python3
"""Quick single-conversation extraction test for immediate quality review."""

import sys
import os
import json
import asyncio
from pathlib import Path
from anthropic import AsyncAnthropic

sys.path.insert(0, str(Path(__file__).parent))

from mcp_server.ingester.scanner import TranscriptScanner
from mcp_server.ingester.extractor import TranscriptExtractor


class AnthropicClient:
    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)

    async def create(self, model: str, max_tokens: int, messages: list):
        return await self.client.messages.create(
            model=model, max_tokens=max_tokens, messages=messages
        )


async def main():
    print("=" * 70)
    print("SINGLE EXTRACTION TEST - Quality Review")
    print("=" * 70)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("\n❌ ERROR: ANTHROPIC_API_KEY not set")
        return 1

    # Load a specific GOLD conversation
    triage_path = Path(__file__).parent / "ingester_triage_full.json"
    with open(triage_path) as f:
        triage_data = json.load(f)

    gold_conversations = [
        c for c in triage_data["classified_conversations"]
        if c.get("tier") == "GOLD" and c["created_at"].startswith("2025")
    ]

    # Pick a medium-length conversation
    test_conv = sorted(gold_conversations, key=lambda c: c["message_count"])[len(gold_conversations)//2]

    print(f"\nTest conversation:")
    print(f"  Title: {test_conv['title']}")
    print(f"  Date: {test_conv['created_at'][:10]}")
    print(f"  Messages: {test_conv['message_count']}")
    print(f"  Texture: {', '.join(test_conv.get('texture', []))}")

    # Extract
    print("\nExtracting...")
    transcript_dir = Path(__file__).parent / "_CLAUDE_TRANSCRIPTS" / "Conversations"
    scanner = TranscriptScanner(str(transcript_dir))
    llm_client = AnthropicClient(api_key)
    extractor = TranscriptExtractor(llm_client=llm_client)

    result = await extractor.extract_conversation(
        conversation=test_conv,
        tier="GOLD",
        scanner=scanner,
    )

    # Display results
    print("\n" + "=" * 70)
    print("EXTRACTION RESULTS")
    print("=" * 70)

    print(f"\nStatus: {result.get('extraction_status')}")
    print(f"Nodes: {len(result.get('nodes', []))}")
    print(f"Observations: {len(result.get('observations', []))}")
    print(f"Entities: {len(result.get('entities', []))}")
    print(f"Edges: {len(result.get('edges', []))}")
    print(f"Key Decisions: {len(result.get('key_decisions', []))}")
    print(f"Texture: {result.get('texture', [])}")

    # Show nodes
    print(f"\n📝 NODES ({len(result.get('nodes', []))}):")
    for i, node in enumerate(result.get('nodes', []), 1):
        print(f"\n  {i}. [{node['type']}] Confidence: {node.get('confidence', 0):.2f}")
        print(f"     {node['content']}")
        if node.get('tags'):
            print(f"     Tags: {', '.join(node['tags'])}")

    # Show observations
    if result.get('observations'):
        print(f"\n💭 OBSERVATIONS ({len(result['observations'])}):")
        for i, obs in enumerate(result['observations'], 1):
            print(f"\n  {i}. Linked to node {obs.get('linked_to_node_index', '?')}")
            print(f"     {obs['content']}")
            print(f"     Confidence: {obs.get('confidence', 0):.2f}")

    # Show entities
    if result.get('entities'):
        print(f"\n👥 ENTITIES ({len(result['entities'])}):")
        for entity in result['entities']:
            print(f"\n  • {entity['name']} ({entity['type']})")
            if entity.get('aliases'):
                print(f"    Aliases: {', '.join(entity['aliases'])}")
            if entity.get('role_in_conversation'):
                print(f"    Role: {entity['role_in_conversation']}")

    # Show edges
    if result.get('edges'):
        print(f"\n🔗 EDGES ({len(result['edges'])}):")
        for i, edge in enumerate(result['edges'], 1):
            from_idx = edge.get('from_node_index', '?')
            to_idx = edge.get('to_node_index', '?')
            etype = edge.get('edge_type', '?')
            print(f"  {i}. Node {from_idx} --{etype}--> Node {to_idx}")
            if edge.get('reasoning'):
                print(f"     Reasoning: {edge['reasoning']}")

    # Save
    output_path = Path(__file__).parent / "single_extraction_result.json"
    with open(output_path, 'w') as f:
        json.dump({
            "conversation": test_conv,
            "extraction": result,
        }, f, indent=2)

    print(f"\n✓ Saved to: {output_path}")
    print("\n" + "=" * 70)

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
