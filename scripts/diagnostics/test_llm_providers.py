#!/usr/bin/env python3
"""Test each LLM provider end-to-end."""
import asyncio
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Load environment
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

async def test_provider(name: str, provider_class):
    print(f"\n--- Testing {name} ---")
    try:
        provider = provider_class()
        print(f"  Available: {provider.is_available}")
        if not provider.is_available:
            print(f"  ❌ Provider not available")
            return False

        from luna.llm import Message
        result = await provider.complete(
            [Message("user", "Say 'hello' only.")],
            max_tokens=10
        )
        print(f"  Response: {result.content[:50] if result.content else 'EMPTY'}")
        print(f"  ✅ {name} working")
        return True
    except ImportError as e:
        print(f"  ❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"  ❌ Error: {type(e).__name__}: {e}")
        return False

async def test_via_http():
    """Test providers through the HTTP API."""
    print("\n--- Testing via HTTP API ---")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            # Check providers endpoint
            resp = await client.get("http://localhost:8000/llm/providers")
            if resp.status_code == 200:
                providers = resp.json()
                print(f"  Available providers: {providers}")
                return True
            else:
                print(f"  ❌ HTTP {resp.status_code}: {resp.text[:100]}")
                return False
    except Exception as e:
        print(f"  ❌ HTTP test failed: {e}")
        return False

async def main():
    print("="*50)
    print("  LLM PROVIDER TESTS")
    print("="*50)

    # Check env vars first
    print("\n--- Environment Check ---")
    env_vars = {
        "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY"),
        "GROQ_API_KEY": os.environ.get("GROQ_API_KEY"),
        "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY"),
    }
    for name, val in env_vars.items():
        if val:
            print(f"  ✅ {name}: {val[:10]}...{val[-5:]}")
        else:
            print(f"  ❌ {name}: NOT SET")

    # Test HTTP endpoint
    await test_via_http()

    # Test providers directly
    results = {}
    try:
        from luna.llm.providers.gemini_provider import GeminiProvider
        results["gemini"] = await test_provider("Gemini", GeminiProvider)
    except ImportError as e:
        print(f"\n--- Gemini ---\n  ❌ Import failed: {e}")
        results["gemini"] = False

    try:
        from luna.llm.providers.groq_provider import GroqProvider
        results["groq"] = await test_provider("Groq", GroqProvider)
    except ImportError as e:
        print(f"\n--- Groq ---\n  ❌ Import failed: {e}")
        results["groq"] = False

    try:
        from luna.llm.providers.claude_provider import ClaudeProvider
        results["claude"] = await test_provider("Claude", ClaudeProvider)
    except ImportError as e:
        print(f"\n--- Claude ---\n  ❌ Import failed: {e}")
        results["claude"] = False

    print("\n" + "="*50)
    print("  SUMMARY")
    print("="*50)
    for name, ok in results.items():
        print(f"  {'✅' if ok else '❌'} {name}")

if __name__ == "__main__":
    asyncio.run(main())
