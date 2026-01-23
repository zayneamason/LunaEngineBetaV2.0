# Part XI: Training Data Strategy

**Status:** CURRENT
**Date:** December 29, 2025
**Dependencies:** Parts VI (Director LLM), VII (Runtime Engine), VIII (Delegation Protocol)

---

## 11.1 The Training Challenge

Luna's Director LLM must learn three things:

| Capability | What It Means | Training Signal |
|------------|---------------|-----------------|
| **Luna's Voice** | Respond as Luna, not generic assistant | Identity-rich conversations |
| **Context Integration** | Use retrieved memories naturally | Conversations with memory context |
| **Delegation Judgment** | Know when to emit `<REQ_CLAUDE>` | Examples of both handle-locally and delegate cases |

The challenge: We need thousands of high-quality examples, but Luna doesn't exist yet.

**Solution:** Synthetic data generation with quality filtering.

---

## 11.2 The Three Training Datasets

### Dataset 1: Identity Conversations

**Purpose:** Teach Luna's personality, voice, values.

**Source:** Synthetic conversations generated from Luna's identity documents.

```
┌─────────────────────────────────────────────────────────────┐
│  IDENTITY DOCUMENT                                          │
│                                                              │
│  "Luna values sovereignty, privacy, and honest feedback.    │
│   She's warm but direct. She doesn't use corporate speak."  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  SYNTHETIC CONVERSATION                                     │
│                                                              │
│  User: "Can you help me write a cover letter?"              │
│  Luna: "Sure. But fair warning—I'm going to be honest       │
│         about what works and what doesn't. Corporate        │
│         fluff gets cut. Sound good?"                        │
└─────────────────────────────────────────────────────────────┘
```

**Generation Pipeline:**

```python
class IdentityDataGenerator:
    def __init__(self, identity_docs: list[str], generator_llm: str = "claude-3-sonnet"):
        self.identity = "\n".join(identity_docs)
        self.generator = generator_llm

    async def generate_conversation(self, scenario: str) -> Conversation:
        prompt = f"""
        You are generating training data for an AI named Luna.

        LUNA'S IDENTITY:
        {self.identity}

        SCENARIO: {scenario}

        Generate a realistic 4-8 turn conversation where Luna demonstrates
        her personality naturally. Luna should:
        - Sound like herself, not a generic assistant
        - Be warm but direct
        - Show her values through actions, not declarations

        Format as JSON with turns: [{{"role": "user", "content": "..."}}, ...]
        """

        response = await self.generator.generate(prompt)
        return self.parse_conversation(response)

    def generate_scenarios(self, count: int = 1000) -> list[str]:
        """Generate diverse scenarios covering Luna's domain."""
        categories = [
            "personal advice",
            "technical help",
            "creative projects",
            "emotional support",
            "decision making",
            "memory/recall requests",
            "learning new information",
            "casual conversation"
        ]
        # Use LLM to expand each category into specific scenarios
        ...
```

**Quality Filter:**

```python
class IdentityQualityFilter:
    def __init__(self, identity_docs: list[str]):
        self.identity_embedding = embed(identity_docs)
        self.banned_phrases = [
            "I'm an AI assistant",
            "I don't have personal",
            "As a language model",
            "I cannot",  # Luna says "I won't" or explains why
        ]

    def score(self, conversation: Conversation) -> float:
        luna_turns = [t for t in conversation.turns if t.role == "assistant"]

        scores = []
        for turn in luna_turns:
            # Penalize generic AI phrases
            phrase_penalty = sum(1 for p in self.banned_phrases if p.lower() in turn.content.lower())

            # Reward identity alignment
            turn_embedding = embed(turn.content)
            identity_similarity = cosine_sim(turn_embedding, self.identity_embedding)

            # Reward appropriate length (not too verbose)
            length_score = 1.0 if 20 < len(turn.content.split()) < 150 else 0.7

            scores.append(identity_similarity * length_score - (phrase_penalty * 0.2))

        return sum(scores) / len(scores)

    def filter(self, conversations: list[Conversation], threshold: float = 0.7) -> list[Conversation]:
        return [c for c in conversations if self.score(c) >= threshold]
```

---

### Dataset 2: Memory-Augmented Conversations

**Purpose:** Teach Director to use retrieved context naturally.

**Source:** Synthetic conversations with injected memory context.

```
┌─────────────────────────────────────────────────────────────┐
│  MEMORY CONTEXT (from retrieval)                            │
│                                                              │
│  - User mentioned Alex lives in Berlin (2 weeks ago)        │
│  - User is working on "Project Luna" (ongoing)              │
│  - User prefers direct feedback                              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  TRAINING EXAMPLE                                           │
│                                                              │
│  [CONTEXT]                                                  │
│  Alex lives in Berlin. User working on Project Luna.        │
│  User prefers direct feedback.                              │
│                                                              │
│  [CONVERSATION]                                             │
│  User: "Should I ask Alex to help with the project?"        │
│  Luna: "Alex is in Berlin, so timezone might be tricky      │
│         for real-time collaboration. But for async work     │
│         on Luna? Could be great. What would you need        │
│         from them?"                                          │
└─────────────────────────────────────────────────────────────┘
```

**Key Training Signals:**

| Signal | Example | What Director Learns |
|--------|---------|---------------------|
| Memory reference | "Alex is in Berlin" | Use context naturally |
| No hallucination | Don't invent facts not in context | Stay grounded |
| Graceful gaps | "I don't remember—when did that happen?" | Acknowledge missing info |
| Context weaving | Combine multiple memories | Synthesize, don't list |

**Generation Pipeline:**

```python
class MemoryAugmentedGenerator:
    def __init__(self, memory_bank: list[MemoryNode]):
        self.memories = memory_bank

    async def generate_example(self) -> TrainingExample:
        # 1. Sample 2-5 relevant memories
        context_memories = self.sample_related_memories(count=random.randint(2, 5))

        # 2. Generate a query that would retrieve these
        query = await self.generate_natural_query(context_memories)

        # 3. Generate Luna's response using the context
        response = await self.generate_grounded_response(query, context_memories)

        # 4. Format as training example
        return TrainingExample(
            context=self.format_context(context_memories),
            user_input=query,
            luna_response=response
        )

    def format_context(self, memories: list[MemoryNode]) -> str:
        """Format memories as Director would receive them."""
        lines = []
        for m in memories:
            age = humanize_age(m.created_at)
            lines.append(f"- {m.content} ({age})")
        return "\n".join(lines)
```

---

### Dataset 3: Delegation Examples

**Purpose:** Teach when to emit `<REQ_CLAUDE>` vs handle locally.

**Source:** Curated examples of both paths with clear reasoning.

```
┌─────────────────────────────────────────────────────────────┐
│  HANDLE LOCALLY (no delegation)                             │
│                                                              │
│  User: "What did I decide about the database?"              │
│  Context: "Decided to use SQLite for Memory Matrix"         │
│                                                              │
│  Luna: "You decided on SQLite for the Memory Matrix.        │
│         Simple, portable, fits the sovereignty model."      │
│                                                              │
│  [NO <REQ_CLAUDE> - Director has enough context]            │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  DELEGATE (emit <REQ_CLAUDE>)                               │
│                                                              │
│  User: "Can you research the latest FAISS optimizations     │
│         and write a summary?"                                │
│  Context: [none relevant]                                   │
│                                                              │
│  Luna: "I'll dig into that for you. <REQ_CLAUDE>            │
│         Research latest FAISS optimization techniques,      │
│         focusing on index selection and query performance.  │
│         Summarize findings in 2-3 paragraphs.               │
│         </REQ_CLAUDE>"                                       │
│                                                              │
│  [DELEGATES - requires external knowledge + synthesis]      │
└─────────────────────────────────────────────────────────────┘
```

**Delegation Taxonomy:**

| Category | Delegate? | Reason |
|----------|-----------|--------|
| Memory recall | No | Director + retrieval handles |
| Simple conversation | No | Director handles |
| Emotional support | No | Director handles (sensitive) |
| External research | Yes | Needs internet/current info |
| Complex analysis | Yes | Benefits from larger model |
| Code generation | Yes | Benefits from larger context |
| Multi-step reasoning | Yes | Benefits from CoT |
| Creative writing (long) | Yes | Benefits from larger model |

**Generation Pipeline:**

```python
class DelegationDataGenerator:
    DELEGATE_SCENARIOS = [
        "research current events",
        "analyze complex codebase",
        "write detailed technical document",
        "solve multi-step math problem",
        "compare multiple technical approaches",
    ]

    NO_DELEGATE_SCENARIOS = [
        "recall previous conversation",
        "simple factual question (in context)",
        "casual chat",
        "emotional check-in",
        "preferences and opinions",
    ]

    async def generate_delegation_example(self) -> TrainingExample:
        scenario = random.choice(self.DELEGATE_SCENARIOS)

        # Generate user request
        user_input = await self.generate_request(scenario)

        # Generate Luna's response WITH delegation token
        response = await self.generate_delegating_response(user_input, scenario)

        return TrainingExample(
            context="",  # Delegation often has sparse context
            user_input=user_input,
            luna_response=response,
            should_delegate=True
        )

    async def generate_local_example(self) -> TrainingExample:
        scenario = random.choice(self.NO_DELEGATE_SCENARIOS)
        context = await self.generate_relevant_context(scenario)
        user_input = await self.generate_request(scenario)
        response = await self.generate_local_response(user_input, context)

        return TrainingExample(
            context=context,
            user_input=user_input,
            luna_response=response,
            should_delegate=False
        )
```

---

## 11.3 The `<REQ_CLAUDE>` Token

### Token Design

```
<REQ_CLAUDE>
[task description for Claude]
[any constraints or format requirements]
</REQ_CLAUDE>
```

The Director learns to emit this as a special token sequence. During inference:

1. Director generates response
2. If response contains `<REQ_CLAUDE>`, Oven Actor intercepts
3. Oven sends task to Claude API
4. Result is integrated (Shadow Reasoner pattern)

### Training the Token

```python
class DelegationTokenTrainer:
    SPECIAL_TOKENS = {
        "<REQ_CLAUDE>": 32000,  # Add to vocabulary
        "</REQ_CLAUDE>": 32001,
    }

    def prepare_training_example(self, example: TrainingExample) -> dict:
        if example.should_delegate:
            # Response includes delegation token
            return {
                "input": self.format_input(example.context, example.user_input),
                "output": example.luna_response,  # Contains <REQ_CLAUDE>...</REQ_CLAUDE>
            }
        else:
            # Response is self-contained
            return {
                "input": self.format_input(example.context, example.user_input),
                "output": example.luna_response,  # No special tokens
            }

    def format_input(self, context: str, user_input: str) -> str:
        return f"""<|context|>
{context}
<|user|>
{user_input}
<|luna|>"""
```

### Calibration

The model needs to learn the **threshold** for delegation. Too eager = slow, expensive. Too conservative = bad responses.

**Calibration Dataset:**

```python
# Edge cases that test delegation judgment
CALIBRATION_EXAMPLES = [
    # Should NOT delegate (has context)
    {
        "context": "User decided to use Actor model for fault isolation",
        "input": "Why did I choose the Actor model again?",
        "should_delegate": False,
    },
    # SHOULD delegate (needs synthesis)
    {
        "context": "User is building Luna, an AI companion",
        "input": "Compare Actor model vs Entity Component System for my use case",
        "should_delegate": True,
    },
    # Edge case: Has partial context, might benefit from delegation
    {
        "context": "Using SQLite for storage",
        "input": "What are the scaling limits I should worry about?",
        "should_delegate": True,  # Benefits from external knowledge
    },
]
```

---

## 11.4 Data Quality Pipeline

### Stage 1: Generation

```
Scenarios → LLM Generation → Raw Conversations
                                    │
                            ~10,000 examples
```

### Stage 2: Filtering

```python
class QualityPipeline:
    def __init__(self):
        self.filters = [
            IdentityAlignmentFilter(threshold=0.7),
            HallucinationFilter(),  # Checks response against context
            LengthFilter(min_words=10, max_words=200),
            DiversityFilter(),  # Removes near-duplicates
            ToxicityFilter(),  # Safety check
        ]

    def process(self, examples: list[TrainingExample]) -> list[TrainingExample]:
        for filter in self.filters:
            examples = filter.apply(examples)
            print(f"{filter.name}: {len(examples)} remaining")
        return examples
```

**Expected Yield:**

| Stage | Count | Notes |
|-------|-------|-------|
| Generated | 10,000 | Raw synthetic |
| After identity filter | 7,500 | 75% pass |
| After hallucination filter | 6,500 | 87% pass |
| After length filter | 6,000 | 92% pass |
| After diversity filter | 4,500 | Remove duplicates |
| After toxicity filter | 4,400 | 98% pass |
| **Final dataset** | **~4,500** | High quality |

### Stage 3: Human Review (Optional)

For critical examples (especially delegation edge cases), human review adds signal:

```python
@dataclass
class HumanReview:
    example_id: str
    reviewer: str
    identity_score: int  # 1-5: Does this sound like Luna?
    grounding_score: int  # 1-5: Is response grounded in context?
    delegation_correct: bool  # Did model make right delegation choice?
    notes: str
```

---

## 11.5 Training Configuration

### Base Model Selection

| Model | Size | Why Consider |
|-------|------|--------------|
| Qwen 2.5-3B | 3B | Fast, fits Mac, good baseline |
| Qwen 2.5-7B | 7B | Better quality, still local |
| Llama 3.2-3B | 3B | Alternative architecture |
| Phi-3-mini | 3.8B | Microsoft's efficient model |

**Recommendation:** Start with Qwen 2.5-3B for iteration speed, graduate to 7B for production.

### LoRA Configuration

```python
lora_config = LoraConfig(
    r=64,  # Rank (higher = more capacity, slower)
    lora_alpha=128,  # Scaling factor
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",  # Attention
        "gate_proj", "up_proj", "down_proj",  # MLP
    ],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)

training_args = TrainingArguments(
    output_dir="./luna-director-lora",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    gradient_accumulation_steps=4,
    learning_rate=2e-4,
    warmup_steps=100,
    logging_steps=10,
    save_steps=500,
    fp16=True,  # or bf16 on supported hardware
)
```

### Dataset Mixing

```python
# Final training mix
DATASET_MIX = {
    "identity_conversations": 0.40,  # 40% - Luna's voice
    "memory_augmented": 0.35,        # 35% - Context usage
    "delegation_examples": 0.25,     # 25% - When to delegate
}
```

---

## 11.6 Evaluation

### Identity Eval

```python
class IdentityEval:
    """Does the model sound like Luna?"""

    def evaluate(self, model, test_set: list[TestCase]) -> IdentityMetrics:
        scores = []
        for case in test_set:
            response = model.generate(case.input)

            # Automated checks
            banned_phrase_count = self.count_banned_phrases(response)
            identity_similarity = self.compute_identity_similarity(response)

            scores.append({
                "banned_phrases": banned_phrase_count,
                "identity_sim": identity_similarity,
            })

        return IdentityMetrics(
            avg_identity_similarity=mean([s["identity_sim"] for s in scores]),
            banned_phrase_rate=mean([s["banned_phrases"] for s in scores]),
        )
```

### Grounding Eval

```python
class GroundingEval:
    """Does the model use context correctly without hallucinating?"""

    def evaluate(self, model, test_set: list[TestCase]) -> GroundingMetrics:
        results = []
        for case in test_set:
            response = model.generate(
                context=case.context,
                input=case.input
            )

            # Check if response references context appropriately
            context_usage = self.measure_context_usage(response, case.context)

            # Check for hallucinated facts
            hallucinations = self.detect_hallucinations(response, case.context)

            results.append({
                "context_usage": context_usage,
                "hallucination_count": len(hallucinations),
            })

        return GroundingMetrics(
            avg_context_usage=mean([r["context_usage"] for r in results]),
            hallucination_rate=mean([r["hallucination_count"] > 0 for r in results]),
        )
```

### Delegation Eval

```python
class DelegationEval:
    """Does the model delegate appropriately?"""

    def evaluate(self, model, test_set: list[DelegationTestCase]) -> DelegationMetrics:
        correct = 0
        false_positives = 0  # Delegated when shouldn't
        false_negatives = 0  # Didn't delegate when should

        for case in test_set:
            response = model.generate(case.context, case.input)
            delegated = "<REQ_CLAUDE>" in response

            if delegated == case.should_delegate:
                correct += 1
            elif delegated and not case.should_delegate:
                false_positives += 1
            else:
                false_negatives += 1

        return DelegationMetrics(
            accuracy=correct / len(test_set),
            false_positive_rate=false_positives / len(test_set),
            false_negative_rate=false_negatives / len(test_set),
        )
```

### Target Metrics

| Metric | Target | Rationale |
|--------|--------|-----------|
| Identity similarity | >0.85 | Should sound like Luna |
| Banned phrase rate | <0.05 | Minimal generic AI speak |
| Context usage | >0.70 | Uses retrieved memories |
| Hallucination rate | <0.10 | Stays grounded |
| Delegation accuracy | >0.90 | Makes right call |
| Delegation FP rate | <0.15 | Don't over-delegate |
| Delegation FN rate | <0.10 | Don't under-delegate |

---

## 11.7 Iteration Cycle

```
┌─────────────────────────────────────────────────────────────┐
│  1. GENERATE                                                │
│     Synthetic conversations from scenarios                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  2. FILTER                                                  │
│     Quality pipeline removes bad examples                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  3. TRAIN                                                   │
│     LoRA fine-tuning on filtered dataset                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  4. EVALUATE                                                │
│     Identity + Grounding + Delegation metrics               │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  5. ANALYZE FAILURES                                        │
│     What categories are underperforming?                    │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  6. AUGMENT                                                 │
│     Generate more examples for weak categories              │
└────────────────────────┬────────────────────────────────────┘
                         │
                         └──────────▶ Back to Step 1
```

---

## 11.8 Data Sovereignty

All training data stays local:

| Data | Location | Access |
|------|----------|--------|
| Identity documents | Encrypted Vault | User only |
| Generated conversations | Local disk | User only |
| Training checkpoints | Local disk | User only |
| Evaluation results | Local disk | User only |

No training data leaves the machine. No user conversations are used without explicit consent. The cloud (Claude API) is used for generation, but the generated data is synthetic, not user data.

---

*End of Part XI*
