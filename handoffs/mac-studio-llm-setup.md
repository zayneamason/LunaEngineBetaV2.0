# Luna Engine — Mac Studio M4 Max LLM Setup Handoff

**Created:** 2026-04-03 by Luna (Claude Desktop → Claude Code handoff)
**Target Machine:** Mac Studio 2025, Apple M4 Max, 48GB RAM, macOS Sequoia 15.6
**Budget:** 50GB disk for LLMs
**Source:** Mars College corpus analysis + current MLX ecosystem research

---

## Context

Ahab is setting up a fresh Mac Studio for the Luna Engine. The existing Luna Engine
codebase is at `_LunaEngine_BetaProject_V2.0_Root/` and currently uses:
- MLX direct inference via `mlx_lm` (see `src/luna/inference/local.py`)
- A single Qwen2.5-3B-Instruct model with a Luna LoRA adapter
- Cloud providers (Claude, Groq, Gemini) via `src/luna/llm/providers/`
- Hybrid routing in `src/luna/inference/local.py` (HybridInference class)

This handoff upgrades the local model stack from a single 3B model to a
multi-model roster with intent-based routing.

---

## Phase 1: Install Ollama

Ollama provides an OpenAI-compatible API and handles model lifecycle (load/unload/swap).
This is cleaner than managing multiple MLX models directly.

```bash
# Install Ollama
brew install ollama

# Start Ollama service (runs as background daemon)
brew services start ollama

# Verify
ollama --version
curl http://localhost:11434/api/tags
```

**Why Ollama over raw MLX:** Luna needs to swap between 4 models based on intent routing.
Ollama handles model memory management, provides a unified API, and recent versions
use MLX as backend on Apple Silicon — so you get MLX performance with Ollama convenience.

---

## Phase 2: Download Model Roster (≈48GB)

Download in this order (most important first):

```bash
# 1. General Brain — Qwen 3 30B-A3B MoE (~19GB)
#    30B total params, only 3B active per token. 100+ tps on M4 Max.
#    This is the primary conversation/reasoning model.
ollama pull qwen3:30b-a3b

# 2. Code Brain — Qwen3-Coder 30B MoE (~19GB)  
#    Same MoE architecture, trained for agentic coding.
#    71.3% SWE-Bench Verified. Routes here on code intent.
ollama pull qwen3-coder:30b

# 3. Router / Fast — Qwen 3 8B (~5GB)
#    Fast intent classification, simple queries, lightweight chat.
#    Has /think mode for when it needs to punch above its weight.
ollama pull qwen3:8b

# 4. Vision — Qwen2-VL 7B (~5GB)
#    Multimodal input (images, screenshots). 
#    Note: Check if already downloaded from Mars corpus at
#    /Volumes/Extreme\ SSD/Media/_AI/models/mlx/
ollama pull qwen2-vl:7b
```

**Verify downloads:**
```bash
ollama list
# Should show 4 models, ~48GB total
```

**Disk usage estimate:**
| Model | Size |
|---|---|
| qwen3:30b-a3b | ~19GB |
| qwen3-coder:30b | ~19GB |
| qwen3:8b | ~5GB |
| qwen2-vl:7b | ~5GB |
| **Total** | **~48GB** |

---

## Phase 3: Update Luna Config Files

### 3a. Update `config/llm_providers.json`

Add Ollama as a provider alongside existing cloud providers:

```json
{
  "current_provider": "ollama",
  "default_provider": "ollama",
  "providers": {
    "ollama": {
      "enabled": true,
      "base_url": "http://localhost:11434",
      "default_model": "qwen3:30b-a3b",
      "models": [
        "qwen3:30b-a3b",
        "qwen3-coder:30b",
        "qwen3:8b",
        "qwen2-vl:7b"
      ],
      "model_roles": {
        "general": "qwen3:30b-a3b",
        "code": "qwen3-coder:30b",
        "router": "qwen3:8b",
        "vision": "qwen2-vl:7b",
        "fast": "qwen3:8b"
      }
    },
    "claude": {
      "enabled": true,
      "api_key_env": "ANTHROPIC_API_KEY",
      "default_model": "claude-haiku-4-5-20251001",
      "models": [
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-6",
        "claude-3-5-sonnet-20241022"
      ]
    },
    "groq": {
      "enabled": false,
      "api_key_env": "GROQ_API_KEY",
      "default_model": "llama-3.3-70b-versatile",
      "models": [
        "llama-3.3-70b-versatile",
        "llama-3.3-70b-specdec",
        "mixtral-8x7b-32768"
      ]
    },
    "gemini": {
      "enabled": false,
      "api_key_env": "GOOGLE_API_KEY",
      "default_model": "gemini-2.0-flash",
      "models": [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite"
      ]
    }
  }
}
```

### 3b. Update `config/local_inference.json`

```json
{
  "backend": "ollama",
  "ollama": {
    "base_url": "http://localhost:11434",
    "default_model": "qwen3:30b-a3b",
    "keep_alive": "10m",
    "options": {
      "temperature": 0.6,
      "top_p": 0.9,
      "repeat_penalty": 1.1,
      "num_ctx": 8192
    }
  },
  "model_legacy_mlx": {
    "model_id": "Qwen/Qwen2.5-3B-Instruct",
    "use_4bit": true,
    "cache_prompt": true,
    "adapter_path": "models/luna_lora_mlx"
  },
  "routing": {
    "complexity_threshold": 0.35,
    "intent_routing_enabled": true,
    "intent_model": "qwen3:8b",
    "routes": {
      "general": "qwen3:30b-a3b",
      "code": "qwen3-coder:30b",
      "vision": "qwen2-vl:7b",
      "simple": "qwen3:8b",
      "reasoning": "qwen3:30b-a3b"
    }
  },
  "performance": {
    "hot_path_timeout_ms": 200,
    "model_swap_timeout_ms": 5000
  }
}
```

### 3c. Update `config/fallback_chain.yaml`

```yaml
chain:
  - ollama
  - claude
  - groq
per_provider_timeout_ms: 30000
max_retries_per_provider: 1
```

---

## Phase 4: Create Ollama LLM Provider

Create a new provider at `src/luna/llm/providers/ollama_provider.py`:

```python
"""
Ollama LLM Provider for Luna Engine.

Uses Ollama's OpenAI-compatible API to serve local models.
Supports model-role routing (general, code, vision, fast).
"""

import logging
import os
from typing import Optional

import httpx

from ..base import LLMProvider, ProviderStatus, ProviderLimits

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


class OllamaProvider(LLMProvider):
    """Ollama-backed LLM provider with multi-model routing."""

    def __init__(self, config: dict):
        self._config = config
        self._base_url = config.get("base_url", OLLAMA_BASE_URL)
        self._default_model = config.get("default_model", "qwen3:30b-a3b")
        self._models = config.get("models", [])
        self._model_roles = config.get("model_roles", {})
        self._available = False
        self._check_availability()

    def _check_availability(self):
        """Check if Ollama is running and accessible."""
        try:
            resp = httpx.get(f"{self._base_url}/api/tags", timeout=5.0)
            self._available = resp.status_code == 200
            if self._available:
                data = resp.json()
                available_models = [m["name"] for m in data.get("models", [])]
                logger.info(f"Ollama available with models: {available_models}")
        except Exception as e:
            logger.warning(f"Ollama not available: {e}")
            self._available = False

    @property
    def is_available(self) -> bool:
        return self._available

    def get_status(self) -> ProviderStatus:
        if self._available:
            return ProviderStatus.READY
        return ProviderStatus.UNAVAILABLE

    def get_limits(self) -> ProviderLimits:
        return ProviderLimits(
            requests_per_minute=0,  # No rate limit for local
            requires_payment=False
        )

    def list_models(self) -> list[str]:
        return self._models

    def get_model_for_role(self, role: str) -> str:
        """Get the appropriate model for a given role/intent."""
        return self._model_roles.get(role, self._default_model)

    async def generate(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.6,
        stream: bool = False,
        **kwargs,
    ) -> str:
        """Generate a response using Ollama's chat API."""
        model = model or self._default_model

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self._base_url}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]

    async def generate_stream(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        max_tokens: int = 2048,
        temperature: float = 0.6,
        **kwargs,
    ):
        """Stream a response using Ollama's chat API."""
        import json as json_lib
        model = model or self._default_model

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            }
        }

        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/api/chat",
                json=payload,
            ) as resp:
                async for line in resp.aiter_lines():
                    if line:
                        chunk = json_lib.loads(line)
                        if "message" in chunk and "content" in chunk["message"]:
                            yield chunk["message"]["content"]
```

---

## Phase 5: Register Ollama Provider

Update `src/luna/llm/providers/__init__.py` to register the Ollama provider:

```python
# Add to existing imports and registration
from .ollama_provider import OllamaProvider

# In the registration function, add:
# ollama_config = config.get_provider_config("ollama")
# if ollama_config and ollama_config.enabled:
#     registry.register("ollama", OllamaProvider(ollama_config.__dict__))
```

**Note:** The exact registration pattern depends on how the existing `__init__.py`
handles provider setup. Match the pattern used for Claude/Groq/Gemini providers.

---

## Phase 6: Update Intent Router (Optional Enhancement)

The existing `HybridInference` class in `src/luna/inference/local.py` uses simple
keyword heuristics. For the multi-model setup, consider upgrading the router to use
the fast 8B model for intent classification:

```python
INTENT_PROMPT = """Classify this message into ONE category:
- general: conversation, questions, analysis, reasoning
- code: programming, debugging, code review, implementation
- vision: image analysis, screenshot reading, visual content
- simple: greetings, quick facts, one-word answers

Message: {message}

Category:"""
```

Route the classification through `qwen3:8b` via Ollama, then dispatch to the
appropriate model. The 8B model at 80-100 tps should add <100ms to the routing
decision.

---

## Phase 7: Verify Setup

```bash
# Test each model responds
curl http://localhost:11434/api/chat -d '{"model":"qwen3:8b","messages":[{"role":"user","content":"hello"}],"stream":false}'

curl http://localhost:11434/api/chat -d '{"model":"qwen3:30b-a3b","messages":[{"role":"user","content":"explain quantum computing in 2 sentences"}],"stream":false}'

curl http://localhost:11434/api/chat -d '{"model":"qwen3-coder:30b","messages":[{"role":"user","content":"write a python fibonacci function"}],"stream":false}'

# Test Luna provider switching
# (from Luna's Python env)
python -c "
from luna.llm.registry import get_registry
reg = get_registry()
print('Available:', reg.list_available())
print('Current:', reg.get_current())
"
```

---

## Architecture Summary

```
User Message
    │
    ▼
┌─────────────────┐
│  qwen3:8b       │  ← Intent Router (~80-100 tps)
│  (Router/Fast)  │     Classifies: general | code | vision | simple
└────────┬────────┘
         │
    ┌────┴────────────────────────┐
    │            │                │
    ▼            ▼                ▼
┌────────┐  ┌──────────┐  ┌───────────┐
│qwen3:  │  │qwen3-    │  │qwen2-vl:  │
│30b-a3b │  │coder:30b │  │7b         │
│General │  │Code      │  │Vision     │
│~100tps │  │~100tps   │  │~40tps     │
└────────┘  └──────────┘  └───────────┘
    │            │                │
    └────────────┴────────────────┘
                 │
                 ▼
         ┌──────────────┐
         │ Fallback:    │
         │ Claude API   │  ← If Ollama unavailable
         │ (cloud)      │
         └──────────────┘
```

---

## Notes for Claude Code

- The Luna LoRA adapter (`models/luna_lora_mlx/`) was trained on the old Qwen2.5-3B.
  It is NOT compatible with the new Qwen 3 models. Keep it for reference but don't
  try to apply it to the new models. A new LoRA will need to be trained eventually.

- Ollama's `keep_alive` setting controls how long a model stays in memory after use.
  Set to `"10m"` for development, `"30m"` or `"-1"` (forever) for production.
  With 48GB RAM, you can keep 2 models loaded simultaneously (router + one worker).

- The MoE models (30B-A3B) have a **critical temperature requirement**: use 0.6, 
  NOT 0. Greedy decoding (temp=0) causes repetition loops with Qwen 3.

- For `/think` mode (chain-of-thought): send `<|im_start|>user\n/think\n{message}`
  or set `"enable_thinking": true` in Ollama options. The model will emit `<think>`
  tags that Luna should strip from the final output but can log for debugging.

- M4 Max memory bandwidth is ~546 GB/s. Model swaps between the two 30B MoE models
  should take 3-5 seconds. The router model (8B) should stay resident at all times.
