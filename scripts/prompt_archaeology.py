#!/usr/bin/env python3
"""
Prompt Archaeology Test Script
==============================

Runs test queries through the Luna Engine and captures prompts for forensic analysis.
See: HANDOFF_PROMPT_ARCHAEOLOGY.md

Usage:
    python scripts/prompt_archaeology.py              # Run baseline capture
    LUNA_ABLATION_NO_VOICE_EXAMPLES=1 python scripts/prompt_archaeology.py  # Experiment A
    LUNA_ABLATION_MINIMAL_PROMPT=1 python scripts/prompt_archaeology.py     # Experiment B
    LUNA_ABLATION_HISTORY_ONLY=1 python scripts/prompt_archaeology.py       # Experiment D
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

# Test queries from the handoff
TEST_QUERIES = [
    # Simple greeting (should be minimal)
    "hey Luna",

    # Identity question (tests entity injection)
    "who is marzipan?",

    # Memory question (tests memory injection)
    "what did we talk about yesterday?",

    # Complex reasoning (likely delegates)
    "can you help me design a database schema for a recipe app?",

    # Emotional/personal (tests voice)
    "I'm feeling overwhelmed today",

    # Technical (tests mode switching)
    "what's the difference between asyncio.gather and asyncio.wait?",
]


async def run_archaeology():
    """Run test queries and capture prompts."""
    from luna.engine import LunaEngine, EngineConfig

    # Determine experiment mode
    mode = "baseline"
    if os.environ.get("LUNA_ABLATION_NO_VOICE_EXAMPLES") == "1":
        mode = "ablation_no_voice_examples"
    elif os.environ.get("LUNA_ABLATION_MINIMAL_PROMPT") == "1":
        mode = "ablation_minimal_prompt"
    elif os.environ.get("LUNA_ABLATION_HISTORY_ONLY") == "1":
        mode = "ablation_history_only"

    print(f"\n{'='*60}")
    print(f"PROMPT ARCHAEOLOGY - Mode: {mode}")
    print(f"{'='*60}\n")

    # Initialize engine
    print("Initializing Luna Engine...")
    config = EngineConfig()
    engine = LunaEngine(config)

    results = []
    responses_received = []

    # Set up response handler
    async def on_response(text: str, data: dict) -> None:
        responses_received.append({
            "text": text,
            "data": data,
        })

    engine.on_response(on_response)

    # Start engine in background
    engine_task = asyncio.create_task(engine.run())
    await asyncio.sleep(1.0)  # Wait for startup

    try:
        for i, query in enumerate(TEST_QUERIES):
            print(f"\n[{i+1}/{len(TEST_QUERIES)}] Query: '{query[:50]}...'")
            print("-" * 40)

            try:
                # Clear previous responses
                responses_received.clear()

                # Send the query
                await engine.send_message(query)

                # Wait for response (with timeout)
                timeout = 30.0
                waited = 0
                while not responses_received and waited < timeout:
                    await asyncio.sleep(0.1)
                    waited += 0.1

                if responses_received:
                    resp = responses_received[0]
                    response = resp["text"]
                    data = resp["data"]

                    route = "delegated" if data.get("delegated") else "local" if data.get("local") else "unknown"
                    tokens = data.get("output_tokens", 0)

                    print(f"  Route: {route}")
                    print(f"  Output tokens: ~{tokens}")
                    print(f"  Response preview: {response[:100]}...")

                    # Get detailed prompt info from director
                    director = engine.get_actor("director")
                    if director:
                        prompt_info = director.get_last_system_prompt()
                        prompt_length = prompt_info.get("length", 0)
                        print(f"  Full prompt: {prompt_length} chars")

                    results.append({
                        "query": query,
                        "response": response[:500],
                        "route": route,
                        "output_tokens": tokens,
                        "mode": mode,
                    })
                else:
                    print(f"  TIMEOUT: No response received")
                    results.append({
                        "query": query,
                        "error": "timeout",
                        "mode": mode,
                    })

            except Exception as e:
                print(f"  ERROR: {e}")
                import traceback
                traceback.print_exc()
                results.append({
                    "query": query,
                    "error": str(e),
                    "mode": mode,
                })

    finally:
        # Shut down
        await engine.stop()
        await engine_task

    # Write summary
    summary_path = Path("data/diagnostics") / f"archaeology_run_{mode}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    with open(summary_path, "w") as f:
        json.dump({
            "mode": mode,
            "timestamp": datetime.now().isoformat(),
            "queries": results,
        }, f, indent=2)

    print(f"\n{'='*60}")
    print(f"Complete! Results saved to: {summary_path}")
    print(f"Detailed prompts in: data/diagnostics/prompt_archaeology.jsonl")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(run_archaeology())
