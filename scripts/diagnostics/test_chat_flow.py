#!/usr/bin/env python3
"""Test complete chat flow."""
import asyncio
import json
import time
import sys

try:
    import httpx
except ImportError:
    print("❌ httpx module not installed. Run: pip install httpx")
    sys.exit(1)

BASE = "http://localhost:8000"

async def test_health():
    print("\n--- Testing /health ---")
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{BASE}/health")
            print(f"  Status: {resp.status_code}")
            print(f"  Response: {resp.json()}")
            return resp.status_code == 200
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return False

async def test_persona_stream():
    print("\n--- Testing /persona/stream ---")
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            start = time.time()
            resp = await client.post(
                f"{BASE}/persona/stream",
                json={"message": "hey luna test"},
            )
            elapsed = time.time() - start
            print(f"  Status: {resp.status_code}")
            print(f"  Time: {elapsed:.2f}s")

            if resp.status_code != 200:
                print(f"  ❌ Bad status: {resp.text[:200]}")
                return False

            # Parse SSE events
            events = []
            for line in resp.text.split("\n"):
                if line.startswith("data: "):
                    try:
                        events.append(json.loads(line[6:]))
                    except json.JSONDecodeError:
                        pass

            types = [e.get("type") for e in events]
            print(f"  Events: {len(events)}")
            print(f"  Types: {set(types)}")

            # Show first few events
            for i, evt in enumerate(events[:5]):
                print(f"    [{i}] {evt}")

            has_tokens = "token" in types
            print(f"  {'✅' if has_tokens else '❌'} Has token events")
            return has_tokens
        except httpx.TimeoutException:
            print(f"  ❌ Request timed out after 60s")
            return False
        except Exception as e:
            print(f"  ❌ Error: {type(e).__name__}: {e}")
            return False

async def test_persona_non_stream():
    print("\n--- Testing /persona (non-streaming) ---")
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            start = time.time()
            resp = await client.post(
                f"{BASE}/persona",
                json={"message": "say hello"},
            )
            elapsed = time.time() - start
            print(f"  Status: {resp.status_code}")
            print(f"  Time: {elapsed:.2f}s")

            if resp.status_code == 200:
                data = resp.json()
                print(f"  Response: {str(data)[:200]}")
                return True
            else:
                print(f"  ❌ Error: {resp.text[:200]}")
                return False
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return False

async def test_memory_endpoints():
    print("\n--- Testing Memory Endpoints ---")
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            # Test memory search
            resp = await client.post(
                f"{BASE}/memory/search",
                json={"query": "test", "limit": 5}
            )
            print(f"  /memory/search: {resp.status_code}")

            # Test memory stats
            resp = await client.get(f"{BASE}/memory/stats")
            if resp.status_code == 200:
                stats = resp.json()
                print(f"  /memory/stats: {stats}")
            else:
                print(f"  /memory/stats: {resp.status_code}")

            return True
        except Exception as e:
            print(f"  ❌ Error: {e}")
            return False

async def main():
    print("="*50)
    print("  CHAT FLOW TEST")
    print("="*50)

    results = {
        "health": await test_health(),
        "persona_stream": await test_persona_stream(),
        "persona": await test_persona_non_stream(),
        "memory": await test_memory_endpoints(),
    }

    print("\n" + "="*50)
    print("  SUMMARY")
    print("="*50)
    for test, passed in results.items():
        print(f"  {'✅' if passed else '❌'} {test}")

if __name__ == "__main__":
    asyncio.run(main())
