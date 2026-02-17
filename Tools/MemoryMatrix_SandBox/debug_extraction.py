#!/usr/bin/env python3
"""Quick debug test to see where extraction is failing"""

import sys
import os
import json
import asyncio
from pathlib import Path
from anthropic import AsyncAnthropic

sys.path.insert(0, str(Path(__file__).parent))

from mcp_server.ingester.scanner import TranscriptScanner
from mcp_server.ingester.extractor import TranscriptExtractor


class DebugClient:
    def __init__(self, api_key):
        self.client = AsyncAnthropic(api_key=api_key)
        
    async def create(self, model, max_tokens, messages):
        print(f"\n🔵 LLM CALL: model={model}, max_tokens={max_tokens}")
        print(f"   Prompt length: {len(messages[0]['content'])} chars")
        response = await self.client.messages.create(
            model=model, max_tokens=max_tokens, messages=messages
        )
        print(f"   Response: {response.usage.input_tokens} in, {response.usage.output_tokens} out")
        return response


async def main():
    print("Debug Extraction Test\n")
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ No API key")
        return 1
        
    # Load one GOLD conversation
    triage_path = Path(__file__).parent / "ingester_triage_full.json"
    with open(triage_path) as f:
        triage_data = json.load(f)
        
    gold = [c for c in triage_data["classified_conversations"] if c.get("tier") == "GOLD"][0]
    print(f"Testing with: {gold['title']}")
    print(f"  Path: {gold['path']}")
    print(f"  Messages: {gold['message_count']}\n")
    
    # Setup
    transcript_dir = Path(__file__).parent / "_CLAUDE_TRANSCRIPTS" / "Conversations"
    scanner = TranscriptScanner(str(transcript_dir))
    
    # Try loading conversation
    print("1. Loading conversation...")
    try:
        full_conv = scanner.load_conversation(gold['path'])
        print(f"   ✓ Loaded, has {len(full_conv.get('chat_messages', []))} messages")
    except Exception as e:
        print(f"   ❌ Load failed: {e}")
        return 1
        
    # Try extraction
    print("\n2. Running extraction...")
    llm_client = DebugClient(api_key)
    extractor = TranscriptExtractor(llm_client=llm_client)
    
    try:
        result = await extractor.extract_conversation(
            conversation=full_conv,
            tier="GOLD",
            scanner=scanner
        )
        print(f"\n3. Result:")
        print(f"   Status: {result.get('extraction_status')}")
        print(f"   Nodes: {len(result.get('nodes', []))}")
        print(f"   Entities: {len(result.get('entities', []))}")
        if result.get('error_message'):
            print(f"   Error: {result['error_message']}")
            
    except Exception as e:
        print(f"   ❌ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
        
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
