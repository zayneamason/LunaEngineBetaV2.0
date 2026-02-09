# HANDOFF: Inference Fallback Chain Implementation

**Spec:** `Docs/SPEC_Inference_Fallback_Chain.md`  
**Priority:** High — Luna hangs on API failure  
**Estimated effort:** 4-6 hours  
**Risk:** Low — isolated component, existing patterns  

---

## Context

Luna hangs when Claude API fails (credits depleted, rate limit, timeout). User sees "Let me look into that..." forever. No recovery.

This handoff implements a FallbackChain that tries providers in order until one succeeds.

---

## Phase 1: Core Implementation

### Task 1.1: Create FallbackChain Class

**File:** `src/luna/llm/fallback.py` (CREATE)

**Requirements:**
- `FallbackChain` class with `generate()` and `stream()` methods
- Tries providers in configured order
- Catches exceptions, logs, advances to next
- Returns `FallbackResult` with telemetry

**Key interfaces:**
```python
@dataclass
class AttemptRecord:
    provider: str
    success: bool
    latency_ms: float
    error: Optional[str] = None
    status_code: Optional[int] = None

@dataclass
class FallbackResult:
    content: str
    provider_used: str
    providers_tried: list[str]
    attempts: list[AttemptRecord]
    total_latency_ms: float

class FallbackChain:
    def __init__(self, registry: ProviderRegistry):
        self._registry = registry
        self._chain: list[str] = ["local", "groq", "claude"]  # default
        self._stats: dict = {}  # provider -> {attempts, successes, total_latency}
    
    async def generate(self, messages, system, max_tokens=512, temperature=0.7) -> FallbackResult:
        """Try providers in order. Return first success."""
        ...
    
    async def stream(self, messages, system, max_tokens=512) -> AsyncGenerator:
        """Stream from first successful provider. Retry on mid-stream failure."""
        ...
    
    def set_chain(self, providers: list[str]) -> None:
        """Update chain at runtime. Validates against registry."""
        ...
    
    def get_chain(self) -> list[str]:
        """Return current chain."""
        ...
    
    def get_stats(self) -> dict:
        """Return attempt statistics."""
        ...
```

**Error handling:**
- Catch `anthropic.APIError`, `httpx` errors, timeouts
- Log each attempt: `[INFERENCE] provider=X status=Y latency_ms=Z`
- Log fallbacks: `[FALLBACK] from=X to=Y reason=Z`
- If ALL fail, raise `AllProvidersFailedError` with full attempt list

**Test:** Unit test with mocked providers that fail in sequence.

---

### Task 1.2: Create Config Loader

**File:** `src/luna/llm/fallback_config.py` (CREATE)

**Requirements:**
- Load from `config/fallback_chain.yaml`
- Validate provider names against registry
- Provide sensible defaults if file missing

```python
@dataclass
class FallbackConfig:
    chain: list[str]
    per_provider_timeout_ms: int = 30000
    max_retries_per_provider: int = 1
    
    @classmethod
    def load(cls, path: Path = None) -> "FallbackConfig":
        """Load from YAML or return defaults."""
        ...
    
    def save(self, path: Path = None) -> None:
        """Persist current config."""
        ...
    
    def validate(self, registry: ProviderRegistry) -> list[str]:
        """Return list of warnings (unknown providers, unavailable, etc)."""
        ...
```

**File:** `config/fallback_chain.yaml` (CREATE)

```yaml
# Inference fallback chain - first success wins
chain:
  - local      # Qwen 3B via MLX
  - groq       # Llama 70B free tier  
  - claude     # Claude Sonnet (paid)

per_provider_timeout_ms: 30000
max_retries_per_provider: 1
```

---

### Task 1.3: Extend ProviderRegistry

**File:** `src/luna/llm/registry.py` (MODIFY)

**Add two helper methods:**

```python
def get_by_name(self, name: str) -> Optional[LLMProvider]:
    """Get provider by name (alias for get())."""
    return self._providers.get(name)

def is_available(self, name: str) -> bool:
    """Check if provider exists and is available."""
    provider = self._providers.get(name)
    return provider is not None and provider.is_available
```

---

### Task 1.4: Integrate into Director

**File:** `src/luna/actors/director.py` (MODIFY)

**Changes:**

1. **Import and init FallbackChain:**
```python
from luna.llm.fallback import FallbackChain, FallbackResult

# In __init__:
self._fallback_chain: Optional[FallbackChain] = None

# In on_start:
if LLM_REGISTRY_AVAILABLE:
    registry = get_registry()
    self._fallback_chain = FallbackChain(registry)
```

2. **Replace direct Claude calls in `_generate_with_delegation()`:**

Find the `try: ... self.client.messages.create(...)` block (~line 580-620).

Replace with:
```python
try:
    result = await self._fallback_chain.generate(
        messages=messages,
        system=enhanced_system_prompt,
        max_tokens=max_tokens,
    )
    response_text = result.content
    provider_used = result.provider_used
    
    # Log if fallback occurred
    if len(result.attempts) > 1:
        logger.info(f"[FALLBACK] Used {provider_used} after {len(result.attempts)-1} failures")
    
except AllProvidersFailedError as e:
    logger.error(f"All providers failed: {e.attempts}")
    response_text = "I'm having trouble connecting right now. All inference providers are unavailable."
```

3. **Same pattern for `_generate_claude_direct()` and streaming paths.**

4. **Add stats to `get_routing_stats()`:**
```python
if self._fallback_chain:
    stats["fallback_chain"] = self._fallback_chain.get_stats()
```

---

### Task 1.5: Add API Endpoints

**File:** `src/luna/api/server.py` (MODIFY)

**Add after the existing `/llm/*` endpoints:**

```python
@app.get("/llm/fallback-chain")
async def get_fallback_chain():
    """Get current fallback chain configuration and status."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    director = _engine.get_actor("director")
    if not director or not director._fallback_chain:
        raise HTTPException(status_code=503, detail="Fallback chain not initialized")
    
    chain = director._fallback_chain
    registry = _get_llm_registry()
    
    return {
        "chain": chain.get_chain(),
        "providers": {
            name: {
                "available": registry.is_available(name),
                "in_chain": name in chain.get_chain(),
            }
            for name in registry.list_available()
        }
    }


@app.post("/llm/fallback-chain")
async def set_fallback_chain(request: dict):
    """Set fallback chain order."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    director = _engine.get_actor("director")
    if not director or not director._fallback_chain:
        raise HTTPException(status_code=503, detail="Fallback chain not initialized")
    
    new_chain = request.get("chain", [])
    if not new_chain:
        raise HTTPException(status_code=400, detail="Chain cannot be empty")
    
    director._fallback_chain.set_chain(new_chain)
    
    # Persist to config
    from luna.llm.fallback_config import FallbackConfig
    config = FallbackConfig(chain=new_chain)
    config.save()
    
    return {"success": True, "chain": new_chain}


@app.get("/llm/fallback-chain/stats")
async def get_fallback_stats():
    """Get fallback chain statistics."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")
    
    director = _engine.get_actor("director")
    if not director or not director._fallback_chain:
        return {"total_requests": 0, "by_provider": {}}
    
    return director._fallback_chain.get_stats()
```

---

## Phase 2: UI Component

### Task 2.1: Create FallbackChainPanel

**File:** `frontend/src/components/FallbackChainPanel.jsx` (CREATE)

**Requirements:**
- Fetch chain from `GET /llm/fallback-chain`
- Display providers with status indicators
- Drag-and-drop reordering (use `@dnd-kit/core` or simple buttons)
- Save button calls `POST /llm/fallback-chain`
- Match existing UI patterns (glass cards, violet accent)

**Minimal viable version:**
```jsx
// Up/down buttons instead of drag-drop is fine for v1
// Green dot = available, red = unavailable
// Save button, success toast
```

### Task 2.2: Add to App.jsx or Settings

Wire the panel into the UI wherever provider settings live (near LLMProviderDropdown).

---

## Testing Checklist

- [ ] FallbackChain tries providers in order
- [ ] Failed provider logged, advances to next
- [ ] All providers fail → graceful error message
- [ ] `set_chain()` validates against registry
- [ ] Config persists to YAML
- [ ] Config loads on startup
- [ ] API endpoints return correct data
- [ ] UI displays current chain
- [ ] UI reorder saves successfully
- [ ] Stats accumulate correctly

---

## Files Summary

| File | Action |
|------|--------|
| `src/luna/llm/fallback.py` | CREATE |
| `src/luna/llm/fallback_config.py` | CREATE |
| `config/fallback_chain.yaml` | CREATE |
| `src/luna/llm/registry.py` | MODIFY (add 2 methods) |
| `src/luna/actors/director.py` | MODIFY (integrate FallbackChain) |
| `src/luna/api/server.py` | MODIFY (add 3 endpoints) |
| `frontend/src/components/FallbackChainPanel.jsx` | CREATE |

---

## Success Criteria

1. **Luna no longer hangs** when Claude API fails
2. **Fallback is observable** in logs
3. **Chain is configurable** via API and UI
4. **Config persists** across restarts

---

## Notes for Implementer

- Existing patterns: Look at `LLMProviderDropdown.jsx` for UI style, `registry.py` for provider abstraction
- The `local` provider wraps `LocalInference` — may need adapter to match `LLMProvider` interface
- Streaming fallback: If stream fails mid-way, discard and retry next provider (don't stitch)
- Keep logging consistent: `[INFERENCE]` and `[FALLBACK]` prefixes

---

*Ship it.*
