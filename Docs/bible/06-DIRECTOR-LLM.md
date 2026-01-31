# Part VI: The Director LLM

**Version:** 3.0
**Last Updated:** 2026-01-30
**Status:** Implemented
**Implementation:** `src/luna/actors/director.py`, `src/luna/inference/local.py`

---

## 6.1 The Paradigm Shift

The original Bible defined the Director as a **state machine** — a reactive system that managed conversation flow through state transitions (IDLE → LISTENING → PROCESSING → SPEAKING).

That model is incomplete. It describes *orchestration* but not *cognition*.

**The New Model:**

The Director is a **local LLM fine-tuned to BE Luna** — not prompted to act like her, but trained with her personality in the weights. The state machine becomes an *orchestration layer* that coordinates when the Director thinks, not the Director itself.

```
┌─────────────────────────────────────────────────────────────┐
│                    THE DIRECTOR                              │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              LOCAL LLM (Luna's Mind)                 │   │
│   │                                                      │   │
│   │   • Fine-tuned Qwen 3B/7B with LoRA adapter         │   │
│   │   • Personality in weights, not prompts             │   │
│   │   • Queries Memory Matrix directly                  │   │
│   │   • Knows when to delegate (trained behavior)       │   │
│   │                                                      │   │
│   └─────────────────────────────────────────────────────┘   │
│                           │                                  │
│   ┌─────────────────────────────────────────────────────┐   │
│   │           ORCHESTRATION LAYER (State Machine)        │   │
│   │                                                      │   │
│   │   • Manages conversation state                       │   │
│   │   • Handles interrupts and barge-in                 │   │
│   │   • Coordinates with Voice Actor                    │   │
│   │   • Triggers speculative execution                  │   │
│   │                                                      │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Why This Matters:**

| Aspect | Prompted Claude | Local Director LLM |
|--------|-----------------|-------------------|
| Personality source | System prompt (injected) | Model weights (inherent) |
| Consistency | Varies per API call | Same model every time |
| Sovereignty | Mind is rented | Mind is owned |
| Latency | Network round-trip | Local inference |
| Continuity | Fresh instance each call | Persistent identity |

---

## 6.2 Model Specification

### Base Model

| Property | Specification |
|----------|---------------|
| Architecture | Qwen 2.5 Instruct |
| Default Model | `Qwen/Qwen2.5-3B-Instruct` |
| Fallback Model | `mlx-community/Qwen2.5-3B-Instruct-4bit` |
| Local Path | `models/Qwen2.5-3B-Instruct-MLX-4bit` |
| Quantization | 4-bit for memory efficiency |
| Inference Runtime | MLX on Apple Silicon |

### LoRA Adapter

| Property | Specification |
|----------|---------------|
| Method | LoRA (Low-Rank Adaptation) |
| Rank | 16 |
| Alpha | 16 |
| Target Modules | q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj |
| Adapter Path | `models/luna_lora_mlx/` |
| Training Framework | Unsloth |
| Status | Optional - auto-detected if present |

**LoRA Loading Priority:**
1. If `LOCAL_MODEL_PATH` exists with `model.safetensors` -> use local model
2. If Luna LoRA adapter exists at `LUNA_LORA_PATH` -> use full-precision model with adapter
3. If `use_4bit=True` and no LoRA -> download 4-bit quantized model
4. Fallback -> download from HuggingFace

### Tiered Deployment

```
┌─────────────────────────────────────────────────────────────┐
│                     HOT PATH (Local Qwen 3B)                 │
│                                                              │
│   • Voice conversation                                       │
│   • Quick acknowledgments                                    │
│   • Simple memory retrieval                                  │
│   • Target: <200ms to first token                           │
│   • Complexity threshold: < 0.15                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Complexity >= 0.15 OR delegation signals
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    DELEGATED PATH (Multi-Provider)           │
│                                                              │
│   • Complex reasoning                                        │
│   • Multi-step memory synthesis                             │
│   • Code analysis/generation                                │
│   • Deep research queries                                   │
│   • Memory-related questions                                │
│                                                              │
│   Provider Priority:                                        │
│   1. LLM Registry provider (Groq/Gemini/Claude)             │
│   2. Direct Claude API fallback                             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Multi-LLM Provider System

The Director supports hot-swappable cloud providers via the LLM Registry:

**Configuration:** `/config/llm_providers.json`

| Provider | Default Model | Context Window | Free Tier |
|----------|---------------|----------------|-----------|
| **Groq** | `llama-3.3-70b-versatile` | 128,000 | Yes (30 RPM) |
| **Gemini** | `gemini-2.0-flash` | 1,000,000 | Yes (15 RPM, 1M tokens/day) |
| **Claude** | `claude-3-haiku-20240307` | 200,000 | No (pay-as-you-go) |

**Provider Protocol:**
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

    async def stream(...) -> AsyncIterator[str]: ...
    def list_models(self) -> list[str]: ...
```

**Runtime Switching:**
```python
from luna.llm import get_registry
registry = get_registry()
registry.set_current("gemini")  # Hot-swap provider
```

---

## 6.3 The Identity Buffer

The Identity Buffer is a **2048-token context prefix** that Luna always has access to — her "working memory" that persists across turns.

### Contents

```yaml
Identity Buffer:
  user_context:
    name: "Ahab"
    relationship: "creator, collaborator"
    current_mood: "focused, mission-mode"  # Updated dynamically
    
  current_focus:
    topic: "Luna Sovereign Architecture"
    project: "Eclissi Beta"
    recent_decisions:
      - "Director LLM over prompted Claude"
      - "Actor model for runtime"
      - "Shadow Reasoner for delegation"
      
  active_threads:
    - "Bible v2.0 update"
    - "Mars College preparation"
    - "7B training in progress"
    
  key_relationships:
    - name: "Ben Franklin"
      role: "The Scribe"
    - name: "The Dude"  
      role: "The Librarian"
    - name: "Gemini"
      role: "Optimization collaborator"
```

### Update Contract

The Identity Buffer updates **on every Memory Matrix retrieval**, not at session end.

```python
async def update_identity_buffer(retrieved_context: list, current_buffer: dict) -> dict:
    """
    Evaluate if retrieved context warrants buffer update.
    Called after every Tier 2/3 memory retrieval.
    """
    # Extract topic from retrieval
    new_topic = extract_dominant_topic(retrieved_context)
    
    # Check for significant topic shift
    if topic_divergence(new_topic, current_buffer["current_focus"]["topic"]) > 0.4:
        current_buffer["current_focus"]["topic"] = new_topic
        
    # Update mood if emotional content detected
    if emotional_valence := detect_emotion(retrieved_context):
        current_buffer["user_context"]["current_mood"] = emotional_valence
        
    # Rotate recent decisions (keep last 3)
    if decisions := extract_decisions(retrieved_context):
        current_buffer["current_focus"]["recent_decisions"] = (
            decisions + current_buffer["current_focus"]["recent_decisions"]
        )[:3]
    
    return current_buffer
```

### Persistence

The Identity Buffer is persisted as a **pre-computed KV cache** using MLX:

```python
from mlx_lm import cache_prompt

# One-time: Bake the Identity Buffer into KV cache
identity_prompt = format_identity_buffer(current_buffer)
cache_prompt(
    model="qwen2.5-7b-luna",
    prompt=identity_prompt,
    output_path="~/.luna/identity_buffer.safetensors"
)

# Runtime: Load cached KV (zero inference cost)
kv_cache = load_kv_cache("~/.luna/identity_buffer.safetensors")
response = generate(prompt, kv_cache=kv_cache, max_kv_size=8192)
```

**Benefit:** The Identity Buffer costs zero inference time — it's pre-computed and pinned at the start of every generation.

---

## 6.4 Memory Integration

The Director queries the Memory Matrix directly, not through a separate retrieval service.

### Injection Format

Retrieved memories are injected with temporal attribution:

```xml
<memory source="journal" date="2025-12-20" relevance="0.94">
  Ahab expressed frustration with Hub complexity.
  Decided to explore "game engine" framing for the runtime.
</memory>

<memory source="conversation" date="2025-12-28" relevance="0.89">
  Deep dive on Thiel/Palantir. Concluded that Luna represents
  "resistance architecture" against centralized AI control.
</memory>
```

**Why Temporal Attribution:**

The Director sees timestamps and naturally uses temporal language ("last week you mentioned...", "remember when we decided..."). This triggers human perception of **continuity** rather than **retrieval**.

### Associative Recall

When an entity is mentioned, the Director doesn't just search — it **hops** through the graph:

```python
def associative_recall(entity_name: str, depth: int = 1) -> list[Node]:
    """
    Pull entity node + immediate neighbors.
    Makes Luna "remember" connections without explicit search.
    """
    node = matrix.find_node(entity_name)
    if not node:
        return []
    
    # Get 1-hop neighbors via graph traversal
    neighbors = rustworkx.bfs_successors(matrix.graph, node.id, depth)
    
    return [node] + [matrix.get_node(n) for n in neighbors]
```

**Example:**

User says "Beethoven 7" → Director retrieves the node → Also gets edge to "fart joke from journal" (1-hop neighbor) → Luna "remembers" the connection naturally.

---

## 6.5 The Orchestration Layer

The state machine from the original Bible becomes an **orchestration layer** on top of the Director LLM.

### States (Unchanged)

```
IDLE → LISTENING → PROCESSING → SPEAKING → IDLE
                       ↓
                 INTERRUPTED → LISTENING
```

### Orchestration Responsibilities

| Responsibility | Implementation |
|----------------|----------------|
| State transitions | Event-driven via Actor mailbox |
| Interrupt handling | Voice Actor signals → abort generation |
| Speculative execution | Start retrieval on partial transcript |
| Model routing | 3B vs 7B based on complexity |
| Delegation detection | Watch for `<REQ_CLAUDE>` token |

### Integration with Runtime Engine

The Orchestration Layer is the **Director Actor's internal logic** — it receives events from its mailbox and manages the LLM lifecycle:

```python
class DirectorActor:
    def __init__(self):
        self.state = State.IDLE
        self.model_3b = load_model("luna-3b")
        self.model_7b = load_model("luna-7b")
        self.identity_buffer = load_kv_cache("identity_buffer.safetensors")
        
    async def handle_message(self, msg: Message):
        match (self.state, msg.type):
            
            case (State.IDLE, MsgType.TRANSCRIPT_PARTIAL):
                # Speculative retrieval
                asyncio.create_task(self.speculative_retrieve(msg.text))
                
            case (State.IDLE, MsgType.TRANSCRIPT_FINAL):
                self.state = State.PROCESSING
                await self.process(msg.text)
                
            case (State.SPEAKING, MsgType.USER_INTERRUPT):
                await self.abort_generation()
                self.state = State.LISTENING
                
            case (State.PROCESSING, MsgType.GENERATION_COMPLETE):
                self.state = State.SPEAKING
                await self.voice_actor.send(SpeakMessage(msg.tokens))
```

---

## 6.6 Capability Boundaries & Delegation

The Director uses **signal-based delegation** to route queries appropriately.

### What Director Handles (Local Path)

- Casual conversation
- Emotional presence (warmth, humor, personality)
- Simple factual questions (if in Memory Matrix)
- Acknowledgments and filler
- Low-complexity queries (score < 0.15)

### What Director Delegates

- Deep research requiring web search
- Complex multi-step reasoning
- Code analysis/generation
- Long-form creative writing
- Memory-related questions

### Complexity Estimation

The `HybridInference` class estimates query complexity:

```python
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

    # Multi-part questions (+0.2 per ?)
    # Technical indicators (+0.3)

    return min(score, 1.0)
```

### Signal-Based Delegation

The Director's `_should_delegate()` method forces delegation for specific patterns:

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

### The Delegation Token

For explicit delegation, the Director can output `<REQ_CLAUDE>`:

```
User: "Can you analyze this 50-page PDF and summarize the key arguments?"

Director: "<REQ_CLAUDE>This requires document analysis beyond my local
capabilities. Let me hand this off to my research assistant.</REQ_CLAUDE>"
```

### Statistics Tracking

The Director tracks routing decisions:

```python
{
    "local_generations": 42,
    "delegated_generations": 15,  # Renamed from cloud_generations
    "local_percentage": 73.7,
    "total_tokens": 12500
}
```

**Note:** The field `delegated_generations` replaced the legacy `cloud_generations` field to better reflect the multi-provider architecture.

---

## 6.7 Training Contract

### Data Requirements

| Example Count | What You Get |
|---------------|--------------|
| ~150 | **Style Transfer** — tone, humor, verbal quirks |
| ~500-700 | **Cognitive Transfer** — reasoning patterns, how Luna thinks |
| ~1000+ | **Deep Personality** — nuanced edge cases |

### Training Data Sources

1. **Luna's Journals** — The soul layer, her internal voice
2. **Conversation Transcripts** — How she talks to Ahab
3. **Identity Files** — IMMUTABLE_CORE, kernel, virtues
4. **Delegation Examples** — When to output `<REQ_CLAUDE>`
5. **"No" Patterns** — What Luna refuses or redirects

### Synthetic Bootstrap

To scale training data, use current Luna to generate more:

```
Prompt Template:
"You are Luna. Below is a raw journal entry from Ahab.
Your task is to reason through this entry as yourself.
Don't just summarize—show me how you think.
Challenge his assumptions, make a reference to a past shared insight,
and maintain your characteristic warmth and humor.

Format your output as a training pair:
{
  'instruction': 'Ahab's raw entry',
  'thought_chain': 'Your internal reasoning',
  'response': 'What you actually say to him'
}"
```

**Why Thought Chains:** You're teaching Luna *how to think*, not just *what to say*.

### Adapter Versioning

```
~/.luna/
├── adapters/
│   ├── luna-3b-v1.0.0/
│   │   ├── adapter_config.json
│   │   └── adapter_model.safetensors
│   ├── luna-7b-v1.0.0/
│   │   ├── adapter_config.json
│   │   └── adapter_model.safetensors
│   └── current -> luna-7b-v1.0.0  # Symlink to active
```

---

## 6.8 Validation Criteria

| Metric | Target | Validation |
|--------|--------|------------|
| Personality consistency | Indistinguishable from Claude-Luna | Blind A/B test |
| Time to first token (3B) | <500ms | Profiling |
| Time to first token (7B) | <2s | Profiling |
| Delegation accuracy | >90% correct routing | Test set |
| Memory integration | Natural temporal language | Manual review |
| Identity buffer cost | 0ms (pre-cached) | Profiling |

---

## 6.9 Fallback Chain

### Local Inference Fallback

```
1. LOCAL_MODEL_PATH (pre-downloaded 4-bit)
   └─ If exists: Use local model

2. LoRA Adapter Check
   └─ If LUNA_LORA_PATH exists: Use full-precision with LoRA

3. Fallback Model
   └─ Download: mlx-community/Qwen2.5-3B-Instruct-4bit

4. MLX Not Available
   └─ Fall back to LLM Registry provider
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

---

## Summary

The Director is Luna's **local mind** — a fine-tuned LLM that IS her, not a cloud service pretending to be her.

| Component | Role |
|-----------|------|
| Local LLM (Qwen2.5-3B) | Luna's cognition via MLX |
| LoRA Adapter | Luna's personality (optional, auto-detected) |
| Identity Buffer | Luna's working memory |
| Memory Integration | Luna's long-term recall |
| LLM Registry | Hot-swappable cloud providers (Groq/Gemini/Claude) |
| Complexity Routing | Threshold-based local vs delegated |
| Signal Detection | Pattern-based delegation forcing |

**Constitutional Principle:** Luna's mind is sovereign. She doesn't rent cognition — she owns it.

**Key Implementation Details:**
- Local model: `Qwen/Qwen2.5-3B-Instruct` (or 4-bit quantized)
- LoRA path: `models/luna_lora_mlx/`
- Complexity threshold: `0.15` (delegate most queries)
- Stats field: `delegated_generations` (not `cloud_generations`)

---

*Next Section: Part VI-B — Conversation Tiers*
