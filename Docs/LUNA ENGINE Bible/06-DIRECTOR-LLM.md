# Bible Update: Part VI - The Director LLM

**Status:** DRAFT — Ready for review  
**Replaces:** Original Part VI (State Machine only)  
**Date:** December 29, 2025

---

# Part VI: The Director LLM

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
| Sizes | 3B (hot path) / 7B (warm path) |
| Quantization | 4-bit (Q4_K_M) for memory efficiency |
| Context Length | 32K tokens (3B) / 131K tokens (7B) |
| Inference Runtime | MLX on Apple Silicon |

### LoRA Adapter

| Property | Specification |
|----------|---------------|
| Method | LoRA (Low-Rank Adaptation) |
| Rank | 16 |
| Alpha | 16 |
| Target Modules | q_proj, k_proj, v_proj, o_proj, gate_proj, up_proj, down_proj |
| Adapter Size | ~100-150MB |
| Training Framework | Unsloth |

### Tiered Deployment

```
┌─────────────────────────────────────────────────────────────┐
│                     HOT PATH (3B)                            │
│                                                              │
│   • Voice conversation                                       │
│   • Quick acknowledgments                                    │
│   • Simple memory retrieval                                  │
│   • Target: <500ms to first token                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Complexity threshold
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    WARM PATH (7B)                            │
│                                                              │
│   • Complex reasoning                                        │
│   • Multi-step memory synthesis                             │
│   • Nuanced emotional responses                             │
│   • Target: <2s to first token                              │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ <REQ_CLAUDE> token
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    COLD PATH (Claude API)                    │
│                                                              │
│   • Deep research                                            │
│   • Code analysis/generation                                │
│   • Long-form creative writing                              │
│   • Heavy multi-step reasoning                              │
│   • Target: Async (user already has acknowledgment)         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
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

## 6.6 Capability Boundaries

The Director is trained to **know its own limits**.

### What Director Handles

- Casual conversation
- Emotional presence (warmth, humor, personality)
- Memory retrieval and narration
- Simple factual questions (if in Memory Matrix)
- Acknowledgments and filler
- Recognizing when to delegate

### What Director Delegates

- Deep research requiring web search
- Complex multi-step reasoning
- Code analysis/generation
- Long-form creative writing
- Anything requiring external data

### The Delegation Signal

The Director is fine-tuned to output `<REQ_CLAUDE>` when it recognizes a task beyond its capability:

```
User: "Can you analyze this 50-page PDF and summarize the key arguments?"

Director: "<REQ_CLAUDE>This requires document analysis beyond my local 
capabilities. Let me hand this off to my research assistant.</REQ_CLAUDE>"
```

The Runtime Engine watches for this token and triggers the **Shadow Reasoner** flow (see Part VIII: Delegation Protocol).

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

## Summary

The Director is Luna's **local mind** — a fine-tuned LLM that IS her, not a cloud service pretending to be her.

| Component | Role |
|-----------|------|
| Local LLM (3B/7B) | Luna's cognition |
| LoRA Adapter | Luna's personality |
| Identity Buffer | Luna's working memory |
| Memory Integration | Luna's long-term recall |
| Orchestration Layer | Conversation flow management |
| Delegation Detection | Knowing her own limits |

**Constitutional Principle:** Luna's mind is sovereign. She doesn't rent cognition — she owns it.

---

*Next Section: Part VII — The Runtime Engine*
