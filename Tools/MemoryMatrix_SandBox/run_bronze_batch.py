#!/usr/bin/env python3
"""
BRONZE Batch Extraction - 338 conversations, entities only, local MLX

Runs offline using Qwen 3B. Entity extraction is simple enough for 3B to handle well.
Saves progress incrementally so we can resume if interrupted.
"""

import sys
import os
import json
import asyncio
from pathlib import Path
from datetime import datetime

# Add both sandbox and Luna src to path
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from mcp_server.ingester.scanner import TranscriptScanner
from mcp_server.ingester.extractor import TranscriptExtractor
from mcp_server.ingester.llm_clients import LocalMLXClient


async def main():
    print("=" * 70)
    print("BRONZE BATCH EXTRACTION - 338 Conversations (Offline)")
    print("=" * 70)
    
    # Load triage
    triage_path = Path(__file__).parent / "ingester_triage_full.json"
    with open(triage_path) as f:
        triage_data = json.load(f)
    
    bronze_conversations = [
        c for c in triage_data["classified_conversations"]
        if c.get("tier") == "BRONZE"
    ]
    
    print(f"\n✓ Found {len(bronze_conversations)} BRONZE conversations")
    print(f"  Entity extraction only (simple for 3B)")
    print(f"  Cost: $0 (local MLX)")
    print(f"  Estimated time: ~2-3 hours\n")
    
    # Check for existing progress
    progress_path = Path(__file__).parent / "bronze_extraction_progress.json"
    if progress_path.exists():
        with open(progress_path) as f:
            progress = json.load(f)
        completed_uuids = set(r["conversation"]["uuid"] for r in progress["results"])
        print(f"📝 Resuming from progress: {len(completed_uuids)} already completed\n")
    else:
        progress = {
            "started_at": datetime.now().isoformat(),
            "total": len(bronze_conversations),
            "completed": 0,
            "results": []
        }
        completed_uuids = set()
    
    # Setup
    transcript_dir = Path(__file__).parent / "_CLAUDE_TRANSCRIPTS" / "Conversations"
    scanner = TranscriptScanner(str(transcript_dir))
    
    print("Initializing local Qwen client...")
    client = LocalMLXClient()
    extractor = TranscriptExtractor(llm_client=client, model="local-qwen")
    print("✓ Client ready\n")
    
    # Process conversations
    print("=" * 70)
    print("EXTRACTION")
    print("=" * 70)
    
    start_time = datetime.now()
    successful = 0
    failed = 0
    
    for i, conv in enumerate(bronze_conversations, 1):
        # Skip if already completed
        if conv["uuid"] in completed_uuids:
            continue
            
        print(f"\n[{i}/{len(bronze_conversations)}] {conv['title'][:60]}")
        print(f"  Date: {conv['created_at'][:10]}, Messages: {conv['message_count']}")
        
        try:
            result = await extractor.extract_conversation(
                conversation=conv,
                tier="BRONZE",
                scanner=scanner
            )
            
            entities = len(result.get("entities", []))
            status = result.get("extraction_status")
            
            if status == "complete":
                print(f"  ✓ {entities} entities")
                successful += 1
            else:
                print(f"  ⚠ {status}: {entities} entities")
                if result.get("error_message"):
                    print(f"     Error: {result['error_message'][:100]}")
                failed += 1
            
            # Save to progress
            progress["results"].append({
                "conversation": conv,
                "extraction": result
            })
            progress["completed"] = len(progress["results"])
            
            # Save progress every 10 conversations
            if len(progress["results"]) % 10 == 0:
                with open(progress_path, 'w') as f:
                    json.dump(progress, f, indent=2)
                print(f"  💾 Progress saved ({len(progress['results'])}/{len(bronze_conversations)})")
            
        except Exception as e:
            print(f"  ❌ Exception: {str(e)[:100]}")
            failed += 1
            progress["results"].append({
                "conversation": conv,
                "extraction": {
                    "extraction_status": "failed",
                    "error_message": str(e),
                    "entities": []
                }
            })
    
    # Final save
    progress["completed_at"] = datetime.now().isoformat()
    with open(progress_path, 'w') as f:
        json.dump(progress, f, indent=2)
    
    # Summary
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)
    
    print(f"\n📊 Extraction Summary:")
    print(f"  Successful: {successful}/{len(bronze_conversations)}")
    print(f"  Failed:     {failed}/{len(bronze_conversations)}")
    print(f"  Time:       {elapsed/60:.1f} minutes ({elapsed/len(bronze_conversations):.1f}s per conversation)")
    
    # Entity stats
    all_entities = []
    for r in progress["results"]:
        all_entities.extend(r["extraction"].get("entities", []))
    
    print(f"\n📈 Entity Extraction:")
    print(f"  Total entities: {len(all_entities)}")
    print(f"  Avg per conversation: {len(all_entities)/len(progress['results']):.1f}")
    
    # Entity type distribution
    entity_types = {}
    for entity in all_entities:
        etype = entity.get("type", "unknown")
        entity_types[etype] = entity_types.get(etype, 0) + 1
    
    print(f"\n🎯 Entity Types:")
    for etype in sorted(entity_types, key=entity_types.get, reverse=True):
        count = entity_types[etype]
        pct = (count / len(all_entities)) * 100 if all_entities else 0
        print(f"  {etype:10}: {count:4} ({pct:5.1f}%)")
    
    print(f"\n✓ Results saved to: {progress_path}")
    print("\n" + "=" * 70)
    print("✅ BRONZE Batch Extraction Complete")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
