#!/usr/bin/env python3
"""Quick test to check entity context with running server's engine."""
import asyncio
import aiohttp

async def test():
    # Hit the server to trigger entity context init
    async with aiohttp.ClientSession() as session:
        async with session.post(
            'http://localhost:8000/message',
            json={'message': 'test entity context'},
        ) as resp:
            result = await resp.json()
            print(f"Response: {result}")
    
    # Now check the prompt endpoint
    async with aiohttp.ClientSession() as session:
        async with session.get('http://localhost:8000/prompt') as resp:
            result = await resp.json()
            print(f"\nPrompt info:")
            print(f"  available: {result.get('available')}")
            print(f"  length: {result.get('length')}")
            print(f"  route: {result.get('route_decision')}")
            if result.get('preview'):
                print(f"  preview: {result.get('preview')[:200]}...")

if __name__ == "__main__":
    asyncio.run(test())
