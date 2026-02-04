#!/usr/bin/env python3
"""
Fallback Chain Diagnostic

Tests each provider in the fallback chain and reports status.
Run this to verify API keys are loaded and providers are working.
"""

import asyncio
import os
import sys
from pathlib import Path

# Setup path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Load .env BEFORE importing providers (they check env at import time)
try:
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ Loaded .env from {env_path}")
    else:
        print(f"⚠ No .env file at {env_path}")
except ImportError:
    print("⚠ python-dotenv not installed, relying on shell environment")

# Now check what's in environment
print("\n" + "="*60)
print("ENVIRONMENT CHECK")
print("="*60)

env_vars = {
    "GROQ_API_KEY": os.environ.get("GROQ_API_KEY"),
    "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY"),
    "GOOGLE_API_KEY": os.environ.get("GOOGLE_API_KEY"),
}

for key, value in env_vars.items():
    if value:
        # Show first/last 4 chars only for security
        masked = f"{value[:8]}...{value[-4:]}" if len(value) > 12 else "***"
        print(f"  {key}: {masked}")
    else:
        print(f"  {key}: ❌ NOT SET")

print("\n" + "="*60)
print("PROVIDER STATUS")
print("="*60)

groq = None
claude = None
gemini = None
local = None

# Test Groq
try:
    from luna.llm.providers.groq_provider import GroqProvider
    groq = GroqProvider()
    print(f"  Groq: {'✓ Available' if groq.is_available else '❌ Not available (no API key?)'}")
    if groq.is_available:
        print(f"    Models: {', '.join(groq.list_models()[:3])}...")
except Exception as e:
    print(f"  Groq: ❌ Import failed: {e}")

# Test Claude
try:
    from luna.llm.providers.claude_provider import ClaudeProvider
    claude = ClaudeProvider()
    print(f"  Claude: {'✓ Available' if claude.is_available else '❌ Not available (no API key?)'}")
except Exception as e:
    print(f"  Claude: ❌ Import failed: {e}")

# Test Gemini
try:
    from luna.llm.providers.gemini_provider import GeminiProvider
    gemini = GeminiProvider()
    print(f"  Gemini: {'✓ Available' if gemini.is_available else '❌ Not available (no API key?)'}")
except Exception as e:
    print(f"  Gemini: ❌ Import failed: {e}")

# Test Local
try:
    from luna.inference.local import LocalInference
    local = LocalInference()
    print(f"  Local (MLX): {'✓ Available' if local.is_available else '❌ Not available (MLX not installed?)'}")
except Exception as e:
    print(f"  Local (MLX): ❌ Import failed: {e}")

print("\n" + "="*60)
print("FALLBACK CHAIN CONFIG")
print("="*60)

try:
    from luna.llm.fallback_config import FallbackConfig
    config = FallbackConfig.load()
    print(f"  Chain order: {' → '.join(config.chain)}")
    print(f"  Timeout per provider: {config.per_provider_timeout_ms}ms")
    print(f"  Max retries: {config.max_retries_per_provider}")
except Exception as e:
    print(f"  ❌ Failed to load config: {e}")

print("\n" + "="*60)
print("LIVE INFERENCE TEST")
print("="*60)

async def test_inference():
    """Test actual inference through each available provider."""

    test_message = "Say 'hello' in exactly one word."

    # Test Groq directly
    if groq and groq.is_available:
        try:
            from luna.llm.base import Message
            messages = [
                Message(role="system", content="You are a helpful assistant. Be very brief."),
                Message(role="user", content=test_message),
            ]
            result = await groq.complete(messages, max_tokens=10)
            print(f"  Groq test: ✓ '{result.content.strip()[:50]}'")
        except Exception as e:
            print(f"  Groq test: ❌ {e}")
    else:
        print("  Groq test: ⏭ Skipped (not available)")

    # Test Claude directly
    if claude and claude.is_available:
        try:
            from luna.llm.base import Message
            messages = [
                Message(role="system", content="You are a helpful assistant. Be very brief."),
                Message(role="user", content=test_message),
            ]
            result = await claude.complete(messages, max_tokens=10)
            print(f"  Claude test: ✓ '{result.content.strip()[:50]}'")
        except Exception as e:
            print(f"  Claude test: ❌ {e}")
    else:
        print("  Claude test: ⏭ Skipped (not available)")

    # Test fallback chain
    print("\n  Testing full fallback chain...")
    try:
        from luna.llm.fallback import FallbackChain
        from luna.llm import get_registry, init_providers

        init_providers()
        registry = get_registry()

        chain = FallbackChain(
            registry=registry,
            local_inference=local if local and local.is_available else None,
            chain=["groq", "claude"],  # Test cloud providers only
        )

        result = await chain.generate(
            messages=[{"role": "user", "content": test_message}],
            system="Be very brief.",
            max_tokens=10,
        )

        print(f"  Fallback chain: ✓ Provider used: {result.provider_used}")
        print(f"    Response: '{result.content.strip()[:50]}'")
        print(f"    Providers tried: {result.providers_tried}")

    except Exception as e:
        print(f"  Fallback chain: ❌ {e}")
        import traceback
        traceback.print_exc()

asyncio.run(test_inference())

print("\n" + "="*60)
print("DIAGNOSTIC COMPLETE")
print("="*60)
