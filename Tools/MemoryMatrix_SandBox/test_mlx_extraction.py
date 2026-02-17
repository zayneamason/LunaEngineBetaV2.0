#!/usr/bin/env python3
"""Test extraction with local MLX Qwen"""

import sys
import os
import json
import asyncio
from pathlib import Path

# Add both sandbox and Luna src to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from mcp_server.ingester.scanner import TranscriptScanner
from mcp_server.ingester.extractor import TranscriptExtractor
from mcp_server.ingester.llm_clients import LocalMLXClient


async def main():
    print("=" * 70)
    print("LOCAL MLX EXTRACTION TEST")
    print("=" * 70)
    
    # Load triage
    triage_path = Path(__file__).parent / "ingester_triage_full.json"
    with open(triage_path) as f:
        triage_data = json.load(f)
    
    # Get one BRONZE conversation (simpler for 3B model)
    bronze = [c for c in triage_data["classified_conversations"] if c.get("tier") == "BRONZE"][0]
    
    print(f"\nTesting with BRONZE conversation:")
    print(f"  Title: {bronze['title']}")
    print(f"  Messages: {bronze['message_count']}")
    print(f"  Texture: {', '.join(bronze.get('texture', []))}\n")
    
    # Setup
    transcript_dir = Path(__file__).parent / "_CLAUDE_TRANSCRIPTS" / "Conversations"
    scanner = TranscriptScanner(str(transcript_dir))
    
    # Load conversation
    print("1. Loading conversation...")
    full_conv = scanner.load_conversation(bronze['path'])
    print(f"   ✓ Loaded {len(full_conv.get('chat_messages', []))} messages\n")
    
    # Create local client
    print("2. Initializing local Qwen client...")
    client = LocalMLXClient()
    print("   ✓ Client created\n")
    
    # Extract
    print("3. Running extraction (BRONZE tier - entities only)...")
    extractor = TranscriptExtractor(llm_client=client, model="local-qwen")
    
    result = await extractor.extract_conversation(
        conversation=full_conv,
        tier="BRONZE",
        scanner=scanner
    )
    
    # Results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"\nStatus: {result.get('extraction_status')}")
    print(f"Entities: {len(result.get('entities', []))}")
    
    if result.get('entities'):
        print("\nExtracted Entities:")
        for i, entity in enumerate(result['entities'][:5], 1):
            print(f"  {i}. {entity.get('name')} ({entity.get('type')})")
            if entity.get('role_in_conversation'):
                print(f"     Role: {entity['role_in_conversation']}")
    
    if result.get('error_message'):
        print(f"\nError: {result['error_message']}")
    
    # Save
    output_path = Path(__file__).parent / "mlx_test_result.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    print(f"\n✓ Saved to: {output_path}")
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
