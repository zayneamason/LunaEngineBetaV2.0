# HANDOFF: Multi-LLM Provider System

**Created:** 2025-01-27
**Author:** Luna + Architect Mode
**Status:** Ready for Implementation
**Priority:** High (enables testing without burning cash)

---

## Problem Statement

Luna's cognition is currently hard-wired to Claude API. We need swappable providers for:
- **Cost control** — free tiers only (Ahab is broke, this is a feature constraint)
- **Testing flexibility** — compare model behaviors
- **Sovereignty trajectory** — eventually swap in local Director LLM

---

## Scope

**IN:**
- Groq (free tier)
- Google Gemini (free tier)
- Claude (existing, pay-as-go fallback)
- Unified provider interface
- UI dropdown for hot-swapping

**OUT:**
- Fine-tuned local models (separate Director LLM project)
- Auto-failover between providers
- Usage tracking/budgeting (future enhancement)

---

## Free Tier Signup Links

### Groq
- **Console:** https://console.groq.com/
- **Sign up:** https://console.groq.com/login
- **API Keys:** https://console.groq.com/keys
- **Free Tier:** ~30 RPM, 14,400 requests/day, no credit card required

### Google Gemini
- **AI Studio:** https://aistudio.google.com/
- **API Keys:** https://aistudio.google.com/app/apikey
- **Free Tier:** 15 RPM, 1M tokens/day, 1500 requests/day
- **Docs:** https://ai.google.dev/gemini-api/docs

### Claude (Existing)
- **Console:** https://console.anthropic.com/
- **Already configured** — just need to abstract it

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              Luna Engine                     │
│                                              │
│  ┌───────────────────────────────────────┐  │
│  │       LLMProvider (Protocol)           │  │
│  │  - complete(messages, config)          │  │
│  │  - stream(messages, config)            │  │
│  │  - get_model_info() -> ModelInfo       │  │
│  │  - get_limits() -> ProviderLimits      │  │
│  └──────────────────┬────────────────────┘  │
│                     │                        │
│      ┌──────────────┼──────────────┐        │
│      ▼              ▼              ▼        │
│  ┌───────┐    ┌──────────┐    ┌─────────┐  │
│  │ Groq  │    │  Gemini  │    │ Claude  │  │
│  │Provider│   │ Provider │    │Provider │  │
│  └───────┘    └──────────┘    └─────────┘  │
│                                              │
│  ┌───────────────────────────────────────┐  │
│  │        ProviderRegistry                │  │
│  │  - register(name, provider)            │  │
│  │  - get_current() -> LLMProvider        │  │
│  │  - set_current(name) -> None           │  │
│  │  - list_available() -> list[str]       │  │
│  │  - is_configured(name) -> bool         │  │
│  └───────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

---

## Provider Comparison (Free Tiers)

| Provider | Model | RPM | Daily Limit | Context | Latency |
|----------|-------|-----|-------------|---------|---------|
| Groq | llama-3.1-70b-versatile | 30 | ~14k req | 128k | 🔥 Fast |
| Groq | llama-3.1-8b-instant | 30 | ~14k req | 128k | 🔥🔥 Fastest |
| Gemini | gemini-1.5-flash | 15 | 1M tokens | 1M | Medium |
| Gemini | gemini-1.5-pro | 2 | 50 req | 2M | Slower |
| Claude | claude-3-haiku | 💰 | 💰 | 200k | Medium |

**Recommendation:** Default to Groq for speed, Gemini for long context tasks.

---

## Interface Contract

```python
from typing import Protocol, AsyncIterator
from dataclasses import dataclass

@dataclass
class Message:
    role: str  # "system" | "user" | "assistant"
    content: str

@dataclass
class ModelInfo:
    name: str
    context_window: int
    supports_streaming: bool

@dataclass
class ProviderLimits:
    requests_per_minute: int
    tokens_per_day: int | None
    requires_payment: bool

@dataclass
class CompletionResult:
    content: str
    model: str
    usage: dict  # {"prompt_tokens": int, "completion_tokens": int}
    provider: str

class LLMProvider(Protocol):
    """Abstract interface for LLM providers."""
    
    name: str
    is_available: bool  # True if API key is configured
    
    async def complete(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model: str | None = None  # Override default model
    ) -> CompletionResult:
        """Single completion request."""
        ...
    
    async def stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model: str | None = None
    ) -> AsyncIterator[str]:
        """Streaming completion."""
        ...
    
    def get_model_info(self, model: str | None = None) -> ModelInfo:
        """Get info about the model."""
        ...
    
    def get_limits(self) -> ProviderLimits:
        """Get rate limits and constraints."""
        ...
```

---

## Configuration

### Environment Variables

```bash
# .env (add these)
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxx
GOOGLE_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx  # existing
```

### Provider Config File

```json
// config/llm_providers.json
{
  "current_provider": "groq",
  "default_provider": "groq",
  "providers": {
    "groq": {
      "enabled": true,
      "api_key_env": "GROQ_API_KEY",
      "default_model": "llama-3.1-70b-versatile",
      "models": [
        "llama-3.1-70b-versatile",
        "llama-3.1-8b-instant",
        "mixtral-8x7b-32768"
      ]
    },
    "gemini": {
      "enabled": true,
      "api_key_env": "GOOGLE_API_KEY",
      "default_model": "gemini-1.5-flash",
      "models": [
        "gemini-1.5-flash",
        "gemini-1.5-pro"
      ]
    },
    "claude": {
      "enabled": true,
      "api_key_env": "ANTHROPIC_API_KEY",
      "default_model": "claude-3-haiku-20240307",
      "models": [
        "claude-3-haiku-20240307",
        "claude-3-5-sonnet-20241022"
      ]
    }
  }
}
```

---

## File Structure

```
src/luna/
├── llm/
│   ├── __init__.py           # Exports: LLMProvider, registry, get_provider
│   ├── base.py               # Protocol definitions, dataclasses
│   ├── registry.py           # ProviderRegistry singleton
│   ├── config.py             # Load/save provider config
│   └── providers/
│       ├── __init__.py
│       ├── groq_provider.py  # Groq implementation
│       ├── gemini_provider.py # Gemini implementation
│       └── claude_provider.py # Claude implementation (refactor existing)
```

---

## Implementation Notes

### Groq Provider
```python
# Uses groq-python SDK
# pip install groq

from groq import AsyncGroq

class GroqProvider:
    def __init__(self):
        self.client = AsyncGroq()  # Reads GROQ_API_KEY from env
        self.name = "groq"
    
    async def complete(self, messages, **kwargs):
        response = await self.client.chat.completions.create(
            model=kwargs.get("model", "llama-3.1-70b-versatile"),
            messages=[{"role": m.role, "content": m.content} for m in messages],
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 1024)
        )
        return CompletionResult(
            content=response.choices[0].message.content,
            model=response.model,
            usage=dict(response.usage),
            provider="groq"
        )
```

### Gemini Provider
```python
# Uses google-generativeai SDK
# pip install google-generativeai

import google.generativeai as genai

class GeminiProvider:
    def __init__(self):
        genai.configure()  # Reads GOOGLE_API_KEY from env
        self.name = "gemini"
    
    async def complete(self, messages, **kwargs):
        model = genai.GenerativeModel(
            kwargs.get("model", "gemini-1.5-flash")
        )
        # Convert messages to Gemini format
        # Note: Gemini has different message format, need adapter
        ...
```

---

## UI Component

### Dropdown Spec
- Location: Luna's settings panel (or floating widget)
- Shows: Provider name + current model
- Visual states:
  - ✅ Green dot = configured & available
  - ⚠️ Yellow dot = configured but rate-limited
  - ❌ Gray = not configured (no API key)
- Behavior: Hot-swap, no restart required
- Persists selection to `config/llm_providers.json`

### Mockup
```
┌─────────────────────────┐
│ LLM Provider        ▼   │
├─────────────────────────┤
│ ✅ Groq (llama-3.1-70b) │  ← selected
│ ✅ Gemini (1.5-flash)   │
│ ❌ Claude (no key)      │
└─────────────────────────┘
```

---

## Trade-offs & Decisions

| Decision | Chose | Over | Rationale |
|----------|-------|------|-----------|
| Async-first | ✅ | Sync | Luna is async, streaming needs it |
| Env vars for keys | ✅ | Config file | Security, 12-factor, gitignore friendly |
| Hot-swap | ✅ | Restart required | Better UX, registry pattern handles it |
| No auto-failover | ✅ | Smart fallback | User should know which model they're using |
| Protocol over ABC | ✅ | Inheritance | Cleaner, more Pythonic, duck typing |

---

## Failure Modes

| Failure | Detection | Response |
|---------|-----------|----------|
| Missing API key | `is_available = False` | Grayed out in dropdown, clear error if selected |
| Rate limit hit | HTTP 429 | Return error with `retry_after`, surface to user |
| Provider down | Connection error | Clear error message, don't auto-switch |
| Invalid response | Parse error | Log full response, return generic error |
| Context overflow | Token count > limit | Pre-flight check, truncate or error |

---

## Testing Strategy

1. **Unit tests per provider** — mock API responses
2. **Integration test** — real API calls (use sparingly, burns quota)
3. **Registry tests** — switching, availability checks
4. **E2E test** — Luna conversation with each provider

---

## Dependencies to Add

```bash
pip install groq google-generativeai
```

Or add to `requirements.txt`:
```
groq>=0.4.0
google-generativeai>=0.3.0
```

---

## Open Questions (Answered)

1. **Where does dropdown live?** → Settings panel, top-right area
2. **Track usage per provider?** → Not now, future enhancement
3. **Default provider?** → Groq (fastest, most generous free tier)

---

## Success Criteria

- [ ] Can switch between Groq/Gemini/Claude via dropdown
- [ ] Luna responds using selected provider
- [ ] Missing API keys show clear "not configured" state
- [ ] Rate limits surface user-friendly errors
- [ ] No code changes needed to add new provider (just new file)

---

## Next Steps

1. Sign up for Groq + Gemini free tiers (links above)
2. Add API keys to `.env`
3. Implement `src/luna/llm/` module
4. Refactor existing Claude calls to use registry
5. Add dropdown to UI
6. Test all three providers

---

*"The Dude abides... but The Dude also doesn't pay for inference when he doesn't have to."* 🎳
