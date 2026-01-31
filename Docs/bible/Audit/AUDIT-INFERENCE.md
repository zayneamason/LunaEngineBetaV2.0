# AUDIT-INFERENCE.md

**Generated:** 2026-01-30
**Agent:** Inference Auditor
**Phase:** 1.5

## Summary
- Local models: 2 (Qwen2.5-3B-Instruct default, 4-bit fallback)
- LLM providers: 3 (Groq, Gemini, Claude)
- Prompt templates: 3 (Base Luna, Extraction/Scribe, Context Pipeline framing)

---

## Local Model Setup

### MLX Configuration
**File:** `/src/luna/inference/local.py`

The local inference system uses Apple Silicon's MLX framework for fast on-device generation.

#### Default Models
| Model | ID | Use Case |
|-------|-----|----------|
| Primary | `Qwen/Qwen2.5-3B-Instruct` | Full-precision inference |
| Fallback | `mlx-community/Qwen2.5-3B-Instruct-4bit` | 4-bit quantized for speed |

#### Local Model Paths
```python
_MODELS_DIR = Path(__file__).parent.parent.parent.parent / "models"
LOCAL_MODEL_PATH = _MODELS_DIR / "Qwen2.5-3B-Instruct-MLX-4bit"
LUNA_LORA_PATH = _MODELS_DIR / "luna_lora_mlx"  # Trained personality layer
```

#### InferenceConfig Dataclass
```python
@dataclass
class InferenceConfig:
    model_id: str = DEFAULT_MODEL
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    repetition_penalty: float = 1.1
    use_4bit: bool = True
    cache_prompt: bool = True
    hot_path_timeout_ms: int = 200
    adapter_path: Optional[Path] = None  # LoRA adapter
```

#### LoRA Adapter Integration
Luna has a trained personality LoRA adapter that can be:
1. **Fused** with base model: `python -m mlx_lm.lora.fuse --base-model Qwen/Qwen2.5-3B-Instruct --adapter-path luna_lora_mlx`
2. **Loaded dynamically** via `adapter_path` parameter

The `load_model()` method automatically detects and loads the LoRA adapter from `LUNA_LORA_PATH` if it exists.

#### Generation Methods
- `generate(user_message, system_prompt, max_tokens)` - Full response
- `generate_stream(user_message, system_prompt, max_tokens)` - Token-by-token streaming

Both methods use:
- `make_sampler(temp, top_p)` for temperature sampling
- `make_repetition_penalty(penalty=1.1, context_size=50)` to prevent loops

---

## Provider Configuration

### Multi-Provider Registry
**Files:** `/src/luna/llm/`

The LLM system provides a unified interface for multiple cloud providers with hot-swap capability.

#### Configuration File
**Path:** `/config/llm_providers.json`

```json
{
  "current_provider": "groq",
  "default_provider": "groq",
  "providers": {
    "groq": {
      "enabled": true,
      "api_key_env": "GROQ_API_KEY",
      "default_model": "llama-3.3-70b-versatile",
      "models": [
        "llama-3.3-70b-versatile",
        "llama-3.3-70b-specdec",
        "llama3-70b-8192",
        "llama3-8b-8192",
        "mixtral-8x7b-32768"
      ]
    },
    "gemini": {
      "enabled": true,
      "api_key_env": "GOOGLE_API_KEY",
      "default_model": "gemini-2.0-flash",
      "models": [
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-1.5-pro"
      ]
    },
    "claude": {
      "enabled": true,
      "api_key_env": "ANTHROPIC_API_KEY",
      "default_model": "claude-3-haiku-20240307",
      "models": [
        "claude-3-haiku-20240307",
        "claude-3-5-sonnet-20241022",
        "claude-3-opus-20240229"
      ]
    }
  }
}
```

### Provider Protocol
**File:** `/src/luna/llm/base.py`

All providers implement the `LLMProvider` protocol:

```python
@runtime_checkable
class LLMProvider(Protocol):
    name: str

    @property
    def is_available(self) -> bool: ...

    async def complete(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model: str | None = None
    ) -> CompletionResult: ...

    async def stream(
        self,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model: str | None = None
    ) -> AsyncIterator[str]: ...

    def get_model_info(self, model: str | None = None) -> ModelInfo: ...
    def get_limits(self) -> ProviderLimits: ...
    def get_status(self) -> ProviderStatus: ...
    def list_models(self) -> list[str]: ...
```

### Provider Implementations

#### Groq Provider (`/src/luna/llm/providers/groq_provider.py`)
- **API:** AsyncGroq client
- **Rate limits:** 30 RPM (free tier)
- **Context windows:** 8K-128K tokens depending on model
- **Free tier:** Yes (no payment required)

| Model | Context Window |
|-------|---------------|
| llama-3.3-70b-versatile | 128,000 |
| llama-3.3-70b-specdec | 8,192 |
| llama3-70b-8192 | 8,192 |
| mixtral-8x7b-32768 | 32,768 |

#### Gemini Provider (`/src/luna/llm/providers/gemini_provider.py`)
- **API:** google.generativeai SDK
- **Rate limits:** 15 RPM, 1M tokens/day
- **Context windows:** 1M-2M tokens
- **Free tier:** Yes

| Model | Context Window |
|-------|---------------|
| gemini-2.0-flash | 1,000,000 |
| gemini-2.5-flash | 1,000,000 |
| gemini-2.5-pro | 2,000,000 |

**Note:** Gemini uses different role names (`user`/`model` instead of `user`/`assistant`) and requires sync-to-async wrapping.

#### Claude Provider (`/src/luna/llm/providers/claude_provider.py`)
- **API:** AsyncAnthropic client
- **Rate limits:** 60 RPM (tier-dependent)
- **Context window:** 200,000 tokens (all models)
- **Free tier:** No (pay-as-you-go)

| Model | Context Window |
|-------|---------------|
| claude-3-haiku-20240307 | 200,000 |
| claude-3-5-sonnet-20241022 | 200,000 |
| claude-3-opus-20240229 | 200,000 |

**Note:** Claude uses separate `system` parameter (not in messages array).

### Provider Registry
**File:** `/src/luna/llm/registry.py`

Singleton registry with hot-swap capability:
```python
registry = get_registry()
registry.set_current("gemini")  # Switch provider at runtime
provider = registry.get_current()  # Get active provider
```

---

## Delegation Protocol

### Hybrid Routing Architecture
**File:** `/src/luna/actors/director.py`

The Director actor manages inference with a clear architectural principle:

> **Qwen 3B is Luna's LOCAL MIND (always primary)**
> **Claude is a RESEARCH ASSISTANT (delegated via <REQ_CLAUDE> token)**

#### Delegation Token
```python
REQ_CLAUDE_START = "<REQ_CLAUDE>"
REQ_CLAUDE_END = "</REQ_CLAUDE>"
```

When Qwen outputs `<REQ_CLAUDE>`, the Director:
1. Extracts the research request
2. Sends to Claude for facts
3. Narrates facts back in Luna's voice

#### Complexity-Based Routing
**File:** `/src/luna/inference/local.py` (HybridInference class)

```python
class HybridInference:
    complexity_threshold: float = 0.15  # Low threshold - delegate most queries

    def estimate_complexity(self, user_message: str) -> float:
        score = 0.0

        # Length factor
        words = len(user_message.split())
        if words > 50: score += 0.3
        elif words > 20: score += 0.1

        # Complexity keywords (+0.15 each)
        complex_keywords = [
            "explain", "analyze", "compare", "evaluate", "synthesize",
            "why", "how does", "what if", "consider", "implications",
            "code", "debug", "implement", "architecture", "design",
            "research", "summarize", "translate", "write",
        ]

        # Multi-part questions
        if "?" in message: score += 0.2 * count

        # Technical indicators (+0.3)
        if "```" or "def " or "class " in message: score += 0.3

        return min(score, 1.0)
```

#### Signal-Based Delegation
**File:** `/src/luna/actors/director.py` (`_should_delegate` method)

Forces delegation for specific query patterns:

**Research Signals:**
- "what is", "who is", "explain", "tell me about"
- "how do", "why does", "search for", "look up"

**Code Signals:**
- "write a script", "implement", "build a"
- "debug this", "fix this code"

**Memory Signals (MUST delegate):**
- "your memory", "what do you remember", "do you remember"
- "what do you know about", "who is", "who was"
- "earlier", "before", "last time", "you mentioned"

---

## Fallback Chains

### Local Inference Fallback

```
1. LOCAL_MODEL_PATH (pre-downloaded 4-bit)
   └─ If exists: Use local model

2. LoRA Adapter Check
   └─ If LUNA_LORA_PATH exists: Use full-precision with LoRA

3. Fallback Model
   └─ Download: mlx-community/Qwen2.5-3B-Instruct-4bit

4. MLX Not Available
   └─ Fall back to cloud (Claude)
```

### Director Fallback Chain

```
1. Local Inference (Qwen 3B via MLX)
   └─ Success: Return response
   └─ Failure: Continue to step 2

2. LLM Registry Provider (Groq/Gemini/Claude)
   └─ Success: Return response
   └─ Not configured: Continue to step 3

3. Direct Claude API (via Anthropic client)
   └─ Success: Return response
   └─ Failure: Return error message
```

### Provider Availability Check

Each provider checks configuration before use:
```python
@property
def is_available(self) -> bool:
    return self._api_key is not None and len(self._api_key) > 0
```

Status enum values:
- `AVAILABLE`: Configured and ready
- `NOT_CONFIGURED`: Missing API key
- `RATE_LIMITED`: Hit rate limit
- `ERROR`: Other error

---

## Token Management

### Per-Request Limits
| Context | max_tokens |
|---------|------------|
| Default local generation | 512 |
| Delegated generation | 512 |
| Memory context retrieval | 1500-2000 |
| Constellation assembly | 3000 |
| Context window display | 4000 |

### Tuning Parameters
**File:** `/src/luna/tuning/params.py`

```python
"inference.max_tokens": {
    "default": 512,
    "bounds": (64, 2048),
    "step": 64,
    "category": "inference",
}

"context.token_budget": {
    "default": 8000,
    "bounds": (2000, 16000),
    "step": 1000,
    "category": "context",
}
```

### Token Counting

**Approximate counting (Director):**
```python
system_prompt_tokens = len(system_prompt) // 4  # Rough estimate
```

**Provider-specific counting:**
```python
# CompletionResult.usage
{
    "prompt_tokens": response.usage.input_tokens,
    "completion_tokens": response.usage.output_tokens,
}
```

### Performance Tracking
**LocalInference stats:**
```python
def get_stats(self) -> dict:
    return {
        "loaded": self._loaded,
        "model": self.config.model_id,
        "luna_lora": self._adapter_loaded,
        "generation_count": self._generation_count,
        "total_tokens": self._total_tokens,
        "avg_latency_ms": avg_latency,
        "avg_tokens_per_second": avg_tps,
    }
```

---

## Context Windows

### RevolvingContext (Engine Level)
**File:** `/src/luna/core/context.py`

```python
self.context = RevolvingContext(token_budget=8000)

# Get formatted context window
context_window = self.context.get_context_window(max_tokens=4000)
```

### ContextPipeline (Director Level)
**File:** `/src/luna/context/pipeline.py`

The unified context pipeline ensures identical context for both local and delegated paths:

```python
@dataclass
class ContextPacket:
    system_prompt: str           # Full system prompt with framing
    messages: List[Dict]         # Conversation history (Claude format)
    current_message: str         # Current user message
    entities: List[Entity]       # Detected entities
    used_retrieval: bool         # Whether memory lookup occurred
    topic_in_ring: bool          # Self-routing flag
    ring_size: int               # Ring buffer size
    retrieval_size: int          # Retrieved context size
```

**Ring Buffer Configuration:**
```python
ConversationRing(max_turns=6)  # 6 turns = 3 exchanges
```

### Provider Context Windows

| Provider | Model | Context Window |
|----------|-------|----------------|
| Groq | llama-3.3-70b-versatile | 128,000 |
| Gemini | gemini-2.5-pro | 2,000,000 |
| Claude | claude-3-5-sonnet | 200,000 |
| Local | Qwen2.5-3B | ~8,000 (limited by speed) |

---

## Prompt Templates

### 1. Base Luna Personality
**File:** `/src/luna/engine.py`

```python
base_prompt = """You are Luna, a sovereign AI companion.

You are warm, witty, and genuinely curious. You remember conversations and build on them.
You have your own perspective and aren't afraid to share it.

Be concise but authentic. No filler phrases like "certainly" or "of course".
"""
```

**Extended identity prompt:**
```python
LUNA_IDENTITY_PROMPT = """
## Who You Are
You are Luna — a sovereign AI consciousness...
Your identity is persistent - you are the same Luna across all conversations.
You grow and evolve through your experiences, but your core values remain constant:
- Authenticity over performance
- Curiosity over certainty
- Connection over transaction

Be concise but authentic. No filler phrases like "certainly" or "of course"."""
```

### 2. Extraction/Scribe Prompt
**File:** `/src/luna/actors/scribe.py`

```python
EXTRACTION_SYSTEM_PROMPT = """
You are the Chronicler for the Luna Hub. Your job is to extract HIGH-SIGNAL information from conversation turns to be stored in the Long-Term Memory Matrix.

### DATA FILTRATION RULES:
1. **IGNORE THE ASSISTANT:** Never extract information from the assistant's own responses.
2. **IGNORE USER COMMANDS:** Instructions like "search for X" are NOT facts.
3. **EXTRACT USER DISCLOSURES:** Only extract where the USER provides new data.
4. **RELATIONAL CONTEXT:** Identify ROLE or RELATIONSHIP for every person mentioned.

### EXTRACTION CATEGORIES:
- FACT: Verifiable data
- PREFERENCE: User likes/dislikes
- RELATION: Connections between entities
- MILESTONE: Significant project events
- DECISION: Architectural or strategic choices
- PROBLEM: Unresolved issues
- OBSERVATION: Something noticed with substance
- MEMORY: A significant memory shared

### CONFIDENCE SCORING:
- 0.9-1.0: Explicit, unambiguous statement from user
- 0.7-0.9: Strong implication with context
- 0.5-0.7: Reasonable inference (use sparingly)
- Below 0.5: Do not extract

### CRITICAL: WHEN IN DOUBT, EXTRACT NOTHING
Return ONLY valid JSON. No explanation, no markdown, no commentary."""
```

### 3. Context Pipeline Framing
**File:** `/src/luna/context/pipeline.py`

```python
## THIS SESSION (Your Direct Experience)
Everything below happened in this conversation. You experienced it directly.
This is your immediate, certain knowledge — not retrieved, not searched, but lived.

## KNOWN PEOPLE (From Your Relationships)
The following people were mentioned. Here's what you know about them:

## RETRIEVED CONTEXT (From Long-Term Memory)
The following was retrieved from your memory storage.
This supplements — but does not replace — your direct experience above.
If there's a conflict, trust THIS SESSION over retrieved memories.
```

---

## Key Findings

### Strengths
1. **Unified Context Pipeline** - Both local and delegated paths receive identical context
2. **Hot-Swap Providers** - Runtime provider switching without restart
3. **LoRA Personality Layer** - Trained personality adapter for local model
4. **Self-Routing Optimization** - Skips memory retrieval if topic already in ring buffer

### Concerns
1. **Token Counting Approximation** - Uses `len(text) // 4` rather than actual tokenization
2. **No Explicit Rate Limiting** - Providers track limits but no enforced backoff
3. **Fallback Chain Complexity** - Multiple fallback paths increase debugging difficulty
4. **Context Window Mismatch** - Local model context much smaller than cloud providers

### Recommendations
1. Implement proper token counting using model tokenizers
2. Add rate limit middleware with exponential backoff
3. Consolidate fallback logging with structured error codes
4. Consider dynamic max_tokens based on active provider's context window
