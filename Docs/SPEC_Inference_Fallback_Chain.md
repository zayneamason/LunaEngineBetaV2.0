# Inference Fallback Chain — Design Specification

**Status:** Draft  
**Author:** The Dude (Architect Mode)  
**Date:** 2025-02-01  

---

## 1. Problem Statement

When Director delegates to Claude API and the call fails (credit depletion, rate limit, 5xx, timeout), Luna hangs with "Let me look into that..." and never recovers.

**Root cause:** No fallback logic. Single provider, single point of failure.

**User impact:** Dead conversations, lost trust, manual restart required.

---

## 2. Solution Overview

A **FallbackChain** that:
1. Tries providers in configured order
2. Catches failures and advances to next provider
3. Logs every attempt for observability
4. Is runtime-configurable without restart

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   local     │ ──▶ │    groq     │ ──▶ │   claude    │
│  (Qwen 3B)  │     │  (free tier)│     │   (paid)    │
└─────────────┘     └─────────────┘     └─────────────┘
      │                   │                   │
      ▼                   ▼                   ▼
   success?            success?            success?
      │                   │                   │
     YES ──▶ return      YES ──▶ return     YES ──▶ return
      │                   │                   │
      NO ──▶ next        NO ──▶ next        NO ──▶ ERROR
```

---

## 3. Components

### 3.1 FallbackChain (New)

**Location:** `src/luna/llm/fallback.py`

**Responsibilities:**
- Hold ordered list of provider names
- Execute inference with fallback logic
- Emit telemetry for each attempt
- Respect per-provider timeout

**Interface:**
```python
class FallbackChain:
    def __init__(self, registry: ProviderRegistry, config: FallbackConfig):
        ...
    
    async def generate(
        self,
        messages: list[Message],
        max_tokens: int = 512,
        temperature: float = 0.7,
    ) -> FallbackResult:
        """Try providers in order until one succeeds."""
        ...
    
    async def stream(
        self,
        messages: list[Message],
        max_tokens: int = 512,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream from first successful provider."""
        ...
    
    def set_chain(self, providers: list[str]) -> None:
        """Update chain order at runtime."""
        ...
    
    def get_chain(self) -> list[str]:
        """Return current chain order."""
        ...
```

**FallbackResult:**
```python
@dataclass
class FallbackResult:
    content: str
    provider_used: str
    providers_tried: list[str]
    attempts: list[AttemptRecord]
    total_latency_ms: float

@dataclass
class AttemptRecord:
    provider: str
    success: bool
    latency_ms: float
    error: Optional[str]
    status_code: Optional[int]
```

### 3.2 FallbackConfig (New)

**Location:** `src/luna/llm/fallback_config.py`

**Responsibilities:**
- Load/save chain configuration
- Validate provider names against registry
- Provide defaults

**Schema:**
```python
@dataclass
class FallbackConfig:
    chain: list[str]  # ["local", "groq", "claude"]
    per_provider_timeout_ms: int = 30000
    max_retries_per_provider: int = 1
    
    @classmethod
    def load(cls, path: Path) -> "FallbackConfig": ...
    
    def save(self, path: Path) -> None: ...
```

**File format** (`config/fallback_chain.yaml`):
```yaml
# Inference fallback chain
# First provider that succeeds wins
# Edit this file or use API/UI to reorder

chain:
  - local      # Qwen 3B via MLX (fastest, no cost)
  - groq       # Llama 70B (free tier, fast)
  - claude     # Claude Sonnet (paid, highest quality)

per_provider_timeout_ms: 30000
max_retries_per_provider: 1
```

### 3.3 ProviderRegistry (Existing — Minor Extension)

**Location:** `src/luna/llm/registry.py`

**Changes needed:**
- Add `get_provider_by_name(name: str) -> Optional[LLMProvider]`
- Add `is_available(name: str) -> bool` convenience method

No structural changes. FallbackChain uses registry to resolve names to providers.

---

## 4. Integration Points

### 4.1 Director Actor

**File:** `src/luna/actors/director.py`

**Current:** Calls `self.client.messages.create()` directly for Claude.

**Change:** Replace direct calls with `FallbackChain.generate()` or `.stream()`.

**Affected methods:**
- `_generate_with_delegation()` — main delegation path
- `_generate_claude_direct()` — fallback when local unavailable
- `process()` — direct API for PersonaAdapter

**Integration pattern:**
```python
# Before (in _generate_with_delegation)
response = self.client.messages.create(...)

# After
result = await self._fallback_chain.generate(
    messages=messages,
    system=enhanced_system_prompt,
    max_tokens=max_tokens,
)
response_text = result.content
# Log: result.provider_used, result.attempts
```

### 4.2 API Server

**File:** `src/luna/api/server.py`

**New endpoints:**

| Method | Path | Description |
|--------|------|-------------|
| GET | `/llm/fallback-chain` | Get current chain order + status |
| POST | `/llm/fallback-chain` | Set new chain order |
| GET | `/llm/fallback-chain/stats` | Get attempt statistics |

**Request/Response:**

```python
# GET /llm/fallback-chain
{
    "chain": ["local", "groq", "claude"],
    "providers": {
        "local": {"available": true, "status": "ready"},
        "groq": {"available": true, "status": "ready"},
        "claude": {"available": false, "status": "no_credits"}
    }
}

# POST /llm/fallback-chain
# Request:
{"chain": ["groq", "local", "claude"]}

# Response:
{"success": true, "chain": ["groq", "local", "claude"]}

# GET /llm/fallback-chain/stats
{
    "total_requests": 142,
    "by_provider": {
        "local": {"attempts": 89, "successes": 87, "avg_latency_ms": 1200},
        "groq": {"attempts": 45, "successes": 44, "avg_latency_ms": 890},
        "claude": {"attempts": 12, "successes": 10, "avg_latency_ms": 2100}
    },
    "fallback_events": 8,
    "last_fallback": {
        "timestamp": "2025-02-01T12:34:56Z",
        "from": "claude",
        "to": "groq",
        "reason": "credit_balance_too_low"
    }
}
```

### 4.3 Config Loading

**File:** `src/luna/llm/__init__.py` (or new `fallback.py`)

**At startup:**
1. Load `config/fallback_chain.yaml`
2. Validate all providers exist in registry
3. Warn if any provider unavailable
4. Initialize FallbackChain singleton

**Hot reload:**
- API POST triggers `FallbackChain.set_chain()`
- Also writes to config file for persistence

---

## 5. UI Requirements

### 5.1 Fallback Chain Panel

**Location:** New component or extend `LLMProviderDropdown.jsx`

**Features:**
- Drag-and-drop reordering of providers
- Visual status indicator per provider (green/yellow/red)
- "Test" button to verify each provider works
- Save button (calls POST endpoint)

**Mockup:**
```
┌─────────────────────────────────────┐
│ ⚡ Inference Fallback Chain         │
├─────────────────────────────────────┤
│  ≡ 🟢 local    (Qwen 3B)      [↑↓] │
│  ≡ 🟢 groq     (Llama 70B)    [↑↓] │
│  ≡ 🔴 claude   (no credits)   [↑↓] │
├─────────────────────────────────────┤
│  [Test All]              [Save]     │
└─────────────────────────────────────┘
```

### 5.2 Inference Monitor (Optional — Phase 2)

**Purpose:** Real-time visibility into which provider handled each request.

**Features:**
- Live log of recent inferences
- Provider used, latency, any fallbacks
- Sparkline or bar chart of provider usage over time

**Data source:** WebSocket from `/ws/inference-stats` or poll `/llm/fallback-chain/stats`

---

## 6. Failure Modes

| Failure | Behavior | Recovery |
|---------|----------|----------|
| All providers fail | Return error to user with context | Log full attempt chain |
| Config file missing | Use default chain: `[local, groq, claude]` | Log warning |
| Provider in chain not in registry | Skip it, log warning | Continue with remaining |
| Provider timeout | Treat as failure, try next | Record in stats |
| Partial stream then fail | Depends — see below | — |

**Partial stream failure:**
- If provider streams 50% then dies, we have two options:
  1. **Discard and retry** — cleaner but loses time
  2. **Keep partial, continue with next** — complex, stitching issues
- **Recommendation:** Option 1. Discard partial, retry with next provider. Simpler, predictable.

---

## 7. Observability

### 7.1 Logging

Every inference attempt logs:
```
[INFERENCE] provider=groq status=success latency_ms=892 tokens=156
[INFERENCE] provider=claude status=failed error="credit_balance_too_low" latency_ms=234
[FALLBACK] from=claude to=groq reason="credit_balance_too_low"
```

### 7.2 Metrics (Future)

If/when we add Prometheus or similar:
- `luna_inference_attempts_total{provider, status}`
- `luna_inference_latency_ms{provider}`
- `luna_fallback_events_total{from_provider, to_provider}`

### 7.3 Health Check Integration

Extend `/health` or `/slash/health` to include:
```json
{
    "fallback_chain": {
        "status": "degraded",
        "available_providers": 2,
        "total_providers": 3,
        "unavailable": ["claude"]
    }
}
```

---

## 8. Migration Path

### Phase 1: Core (This Spec)
1. Implement `FallbackChain` class
2. Implement `FallbackConfig` loader
3. Add config file `config/fallback_chain.yaml`
4. Integrate into Director (3 call sites)
5. Add API endpoints
6. Basic UI (reorder + save)

### Phase 2: Monitoring
1. Stats collection in FallbackChain
2. Stats API endpoint
3. Inference Monitor UI component
4. Health check integration

### Phase 3: Advanced
1. Per-provider retry policies
2. Circuit breaker pattern (auto-disable failing provider)
3. Cost tracking (if providers have different costs)
4. A/B testing support

---

## 9. Trade-offs

| Decision | Alternative | Why This Way |
|----------|-------------|--------------|
| YAML config file | JSON, DB, env var | Human-editable, git-trackable, simple |
| Singleton FallbackChain | Per-request chain | Simpler, hot-reload via setter |
| Discard partial streams | Stitch partials | Complexity not worth it |
| Provider names as strings | Provider enum | Easier to extend, config-friendly |

---

## 10. Open Questions

1. **Should local always be in chain?** Or allow chain = `[groq, claude]` only?
   - Recommendation: Allow any config. User's choice.

2. **Rate limiting per provider?** Some providers have RPM limits.
   - Defer to Phase 3. For now, rely on provider's own errors.

3. **Streaming: retry on partial failure or surface error?**
   - Recommendation: Retry with next provider. Don't show partial to user.

---

## 11. Files to Create/Modify

| File | Action |
|------|--------|
| `src/luna/llm/fallback.py` | CREATE — FallbackChain class |
| `src/luna/llm/fallback_config.py` | CREATE — Config loader |
| `config/fallback_chain.yaml` | CREATE — Default config |
| `src/luna/llm/registry.py` | MODIFY — Add helper methods |
| `src/luna/actors/director.py` | MODIFY — Use FallbackChain |
| `src/luna/api/server.py` | MODIFY — Add 3 endpoints |
| `frontend/src/components/FallbackChainPanel.jsx` | CREATE — UI component |

---

## 12. Future: Director Decomposition

This spec addresses **one symptom** of a larger architectural debt: the Director monolith.

**Current state:** `director.py` (~1400 lines) handles:
- LLM routing decisions
- Context assembly
- Response generation
- Provider selection
- Error handling
- Session tracking
- Personality loading

**Bible spec says:** Director should orchestrate, delegating to specialized components.

**What this spec does:** Extracts FallbackChain as a clean component. Director still calls it, but the cascade logic is isolated and testable.

**What remains for later:**
| Component | Responsibility | Status |
|-----------|---------------|--------|
| FallbackChain | Provider cascade | ✅ This spec |
| RouteSelector | Local vs delegate decision | ❌ Still in Director |
| ContextAssembler | Prompt building | ❌ Still in Director |
| ResponseValidator | Output quality checks | ❌ Not implemented |

**Recommendation:** After Mars College, consider a phased Director decomposition:
1. Extract RouteSelector (moves `_should_delegate()` out)
2. Extract ContextAssembler (moves `_build_*_context()` methods out)
3. Replace heuristic routing with learned routing (LoRA emits `<REQ_CLAUDE>`)

For now, FallbackChain is the right scope. Stops the bleeding without open-heart surgery.

---

*That's the design, man. Simple, does what it needs to, doesn't over-engineer.*
