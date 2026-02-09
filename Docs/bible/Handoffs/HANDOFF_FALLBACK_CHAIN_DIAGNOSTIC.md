# HANDOFF: Fallback Chain Diagnostic & Configuration Fix

**Priority:** HIGH  
**Estimated Effort:** 45 minutes  
**Risk:** Low (diagnostic + config changes only)

---

## Problem Statement

Luna's inference fallback chain may not be working correctly:
1. **Groq might not be getting called** — unclear if API key is loaded at runtime
2. **Chain order is suboptimal** — currently `local → groq → claude`, but local is 3 tok/s
3. **No startup validation** — providers aren't verified before accepting requests

---

## Task 1: Run Diagnostic

Create and run a diagnostic script to verify provider status.

### Create: `scripts/diagnostics/diagnose_fallback_chain.py`

```python
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

# Import providers
try:
    from luna.llm.providers.groq_provider import GroqProvider
    groq = GroqProvider()
    print(f"  Groq: {'✓ Available' if groq.is_available else '❌ Not available (no API key?)'}")
    if groq.is_available:
        print(f"    Models: {', '.join(groq.list_models()[:3])}...")
except Exception as e:
    print(f"  Groq: ❌ Import failed: {e}")

try:
    from luna.llm.providers.claude_provider import ClaudeProvider
    claude = ClaudeProvider()
    print(f"  Claude: {'✓ Available' if claude.is_available else '❌ Not available (no API key?)'}")
except Exception as e:
    print(f"  Claude: ❌ Import failed: {e}")

try:
    from luna.llm.providers.gemini_provider import GeminiProvider
    gemini = GeminiProvider()
    print(f"  Gemini: {'✓ Available' if gemini.is_available else '❌ Not available (no API key?)'}")
except Exception as e:
    print(f"  Gemini: ❌ Import failed: {e}")

try:
    from luna.inference import LocalInference
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
    if groq.is_available:
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
    try:
        if claude.is_available:
            from luna.llm.base import Message
            messages = [
                Message(role="system", content="You are a helpful assistant. Be very brief."),
                Message(role="user", content=test_message),
            ]
            result = await claude.complete(messages, max_tokens=10)
            print(f"  Claude test: ✓ '{result.content.strip()[:50]}'")
        else:
            print("  Claude test: ⏭ Skipped (not available)")
    except Exception as e:
        print(f"  Claude test: ❌ {e}")

    # Test fallback chain
    print("\n  Testing full fallback chain...")
    try:
        from luna.llm.fallback import FallbackChain
        from luna.llm import get_registry, init_providers
        
        init_providers()
        registry = get_registry()
        
        chain = FallbackChain(
            registry=registry,
            local_inference=None,  # Skip local for this test
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
```

### Run the diagnostic:

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python scripts/diagnostics/diagnose_fallback_chain.py
```

---

## Task 2: Update Fallback Chain Order

Change from `local → groq → claude` to `groq → local → claude`

### Modify: `config/fallback_chain.yaml`

```yaml
# Inference Fallback Chain Configuration
# First provider that succeeds wins
# Edit this file or use API/UI to reorder

chain:
  - groq       # Llama 70B (free tier, fast) - PRIMARY
  - local      # Qwen 3B via MLX (no cost, but slow ~3 tok/s)
  - claude     # Claude Sonnet (paid, highest quality) - LAST RESORT

per_provider_timeout_ms: 30000
max_retries_per_provider: 1
```

---

## Task 3: Add Provider Readiness Check

Add a startup validation that ensures at least one provider is ready before accepting requests.

### Modify: `src/luna/llm/fallback.py`

Add this method to the `FallbackChain` class (around line 80):

```python
def validate_chain(self) -> tuple[bool, list[str]]:
    """
    Validate that at least one provider in the chain is available.
    
    Returns:
        (is_valid, list of warnings/errors)
    
    Call this at startup to fail fast if no providers are configured.
    """
    errors = []
    available_count = 0
    
    for provider_name in self._chain:
        if provider_name == "local":
            if self._local is None:
                errors.append(f"local: LocalInference not configured")
            elif not self._local.is_available:
                errors.append(f"local: MLX not available on this system")
            else:
                available_count += 1
        else:
            if self._registry is None:
                errors.append(f"{provider_name}: Registry not configured")
                continue
                
            provider = self._registry.get(provider_name)
            if provider is None:
                errors.append(f"{provider_name}: Not found in registry")
            elif not provider.is_available:
                errors.append(f"{provider_name}: Not available (missing API key?)")
            else:
                available_count += 1
    
    is_valid = available_count > 0
    
    if not is_valid:
        errors.insert(0, "CRITICAL: No providers available in fallback chain!")
    else:
        errors.insert(0, f"OK: {available_count}/{len(self._chain)} providers available")
    
    return is_valid, errors
```

### Modify: `src/luna/actors/director.py`

In `_init_fallback_chain()` method (around line 250), add validation after initialization:

```python
async def _init_fallback_chain(self) -> bool:
    """Initialize fallback chain for resilient inference."""
    if not FALLBACK_CHAIN_AVAILABLE:
        logger.debug("Fallback chain not available")
        return False

    try:
        # Load config
        config = FallbackConfig.load()

        # Get registry if available
        registry = get_registry() if LLM_REGISTRY_AVAILABLE else None

        # Initialize fallback chain with local inference and registry
        self._fallback_chain = init_fallback_chain(
            registry=registry,
            local_inference=self._local,
            chain=config.chain,
        )

        # === NEW: Validate chain has at least one working provider ===
        is_valid, messages = self._fallback_chain.validate_chain()
        for msg in messages:
            if msg.startswith("CRITICAL") or msg.startswith("OK"):
                logger.info(f"[FALLBACK] {msg}")
            else:
                logger.warning(f"[FALLBACK] {msg}")
        
        if not is_valid:
            logger.error("[FALLBACK] No providers available! Check API keys in .env")
            # Don't return False - let it try anyway, maybe keys load later
        # === END NEW ===

        logger.info(f"[FALLBACK] Chain initialized: {config.chain}")
        return True

    except Exception as e:
        logger.warning(f"Fallback chain init failed: {e}")
        return False
```

---

## Task 4: Ensure .env Loads Everywhere

Add a central environment loader that all entry points use.

### Create: `src/luna/env.py`

```python
"""
Central environment loader for Luna.

Import this module FIRST in any entry point to ensure .env is loaded
before providers check for API keys.

Usage:
    from luna.env import ensure_env_loaded
    ensure_env_loaded()
"""

import os
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_env_loaded = False

def ensure_env_loaded(env_path: Optional[Path] = None) -> bool:
    """
    Ensure environment variables are loaded from .env file.
    
    Safe to call multiple times - only loads once.
    
    Args:
        env_path: Optional path to .env file. Auto-detects if not provided.
        
    Returns:
        True if .env was loaded (or was already loaded), False if not found
    """
    global _env_loaded
    
    if _env_loaded:
        return True
    
    # Find project root by looking for .env or pyproject.toml
    if env_path is None:
        # Try multiple strategies to find project root
        candidates = [
            Path(__file__).parent.parent.parent / ".env",  # src/luna/env.py -> root
            Path.cwd() / ".env",
            Path.home() / "_HeyLuna_BETA" / "_LunaEngine_BetaProject_V2.0_Root" / ".env",
        ]
        
        for candidate in candidates:
            if candidate.exists():
                env_path = candidate
                break
    
    if env_path is None or not env_path.exists():
        logger.warning("No .env file found - relying on shell environment")
        _env_loaded = True  # Mark as "loaded" to avoid repeated warnings
        return False
    
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path, override=False)  # Don't override existing env vars
        logger.info(f"Loaded environment from {env_path}")
        _env_loaded = True
        return True
    except ImportError:
        logger.warning("python-dotenv not installed - run: pip install python-dotenv")
        _env_loaded = True
        return False


def get_api_key_status() -> dict[str, bool]:
    """
    Check which API keys are configured.
    
    Returns:
        Dict mapping provider name to whether key is set
    """
    return {
        "groq": bool(os.environ.get("GROQ_API_KEY")),
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "google": bool(os.environ.get("GOOGLE_API_KEY")),
    }


def require_api_key(provider: str) -> str:
    """
    Get an API key, raising an error if not set.
    
    Args:
        provider: Provider name (groq, anthropic, google)
        
    Returns:
        The API key
        
    Raises:
        EnvironmentError: If key is not set
    """
    key_map = {
        "groq": "GROQ_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY", 
        "google": "GOOGLE_API_KEY",
    }
    
    env_var = key_map.get(provider.lower())
    if not env_var:
        raise ValueError(f"Unknown provider: {provider}")
    
    key = os.environ.get(env_var)
    if not key:
        raise EnvironmentError(
            f"{env_var} not set. Add it to your .env file or shell environment."
        )
    
    return key
```

### Update entry points to use it:

Add to the TOP of these files (before other imports):

**`src/luna/llm/__init__.py`:**
```python
# Ensure environment is loaded before checking API keys
from luna.env import ensure_env_loaded
ensure_env_loaded()
```

**`src/luna/actors/director.py`:**
```python
# At the very top, after docstring
from luna.env import ensure_env_loaded
ensure_env_loaded()
```

---

## Verification Checklist

After implementation, verify:

- [ ] Run diagnostic: `python scripts/diagnostics/diagnose_fallback_chain.py`
- [ ] All API keys show as loaded
- [ ] Groq test passes
- [ ] Fallback chain test uses Groq as primary
- [ ] Start Luna Engine and verify logs show: `[FALLBACK] OK: X/3 providers available`
- [ ] Send a test message and confirm it routes through Groq

---

## Expected Outcome

```
ENVIRONMENT CHECK
  GROQ_API_KEY: gsk_IoQx...OOH
  ANTHROPIC_API_KEY: sk-ant-...wAA
  GOOGLE_API_KEY: AIzaSyBt...K_o

PROVIDER STATUS
  Groq: ✓ Available
  Claude: ✓ Available
  Local (MLX): ✓ Available

FALLBACK CHAIN CONFIG
  Chain order: groq → local → claude

LIVE INFERENCE TEST
  Groq test: ✓ 'Hello'
  Fallback chain: ✓ Provider used: groq
```

---

## Files Summary

| Action | File |
|--------|------|
| CREATE | `scripts/diagnostics/diagnose_fallback_chain.py` |
| CREATE | `src/luna/env.py` |
| MODIFY | `config/fallback_chain.yaml` |
| MODIFY | `src/luna/llm/fallback.py` (add `validate_chain()`) |
| MODIFY | `src/luna/actors/director.py` (add validation call) |
| MODIFY | `src/luna/llm/__init__.py` (add env loader) |

---

Ship it. 🚀
