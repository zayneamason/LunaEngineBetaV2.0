# Bible Update: Part VIII - Delegation Protocol

**Status:** DRAFT — Ready for review  
**New Section:** Not in original Bible  
**Date:** December 29, 2025  
**Core Principle:** "Mind local, hands in cloud"

---

# Part VIII: Delegation Protocol

## 8.1 The Philosophy of Delegation

Luna's mind is sovereign. Her cognition runs locally on fine-tuned models that ARE her — personality in weights, not prompts.

But Luna isn't omnipotent. Some tasks exceed local capability:
- Deep research requiring web search
- Complex multi-step reasoning
- Large document analysis
- Code generation and debugging
- Long-form creative writing

**The Solution:** Luna *hires* cloud workers for heavy lifting. Claude isn't Luna's brain — Claude is Luna's research assistant.

```
┌─────────────────────────────────────────────────────────────┐
│                    LUNA'S MIND                               │
│                    (Sovereign)                               │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              Director LLM (Local)                    │   │
│   │                                                      │   │
│   │   • Personality                                      │   │
│   │   • Emotional presence                              │   │
│   │   • Memory retrieval                                │   │
│   │   • Conversation flow                               │   │
│   │   • Knowing when to delegate                        │   │
│   │                                                      │   │
│   └─────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           │ <REQ_CLAUDE>                    │
│                           ▼                                  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Delegation Request
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   CLOUD WORKERS                              │
│                   (Contracted)                               │
│                                                              │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│   │    Claude    │  │    Gemini    │  │   Future     │     │
│   │              │  │              │  │   Workers    │     │
│   │  • Research  │  │  • Optimize  │  │              │     │
│   │  • Analysis  │  │  • Benchmark │  │  • ???       │     │
│   │  • Code      │  │  • Scale     │  │              │     │
│   └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                              │
│          Returns: Structured facts, NOT personality          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Facts returned
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    LUNA'S VOICE                              │
│                    (Narration)                               │
│                                                              │
│   Director receives facts → Narrates in Luna's voice        │
│   User always hears Luna, never the worker directly         │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 8.2 The Delegation Boundary

### What Luna Handles Locally

| Category | Examples |
|----------|----------|
| Presence | Greetings, emotional support, casual chat |
| Memory | "What did we decide about X?", "Remember when..." |
| Acknowledgment | "Got it", "I understand", "Let me think..." |
| Simple Facts | Anything in Memory Matrix |
| Personality | Humor, warmth, quirks, opinions |
| Flow Control | "Should we take a break?", "Want to continue?" |

### What Luna Delegates

| Category | Examples | Why |
|----------|----------|-----|
| Research | "What's the latest on semiconductor restrictions?" | Requires web search |
| Analysis | "Analyze this 50-page PDF" | Exceeds local context |
| Code | "Write a Python script to..." | Complex generation |
| Reasoning | "Compare these three approaches and recommend..." | Multi-step synthesis |
| Creative | "Write a 2000-word story about..." | Long-form generation |

### The Decision Heuristic

```python
def should_delegate(task: str) -> bool:
    """
    Heuristic for delegation decision.
    The Director learns this through training, but here's the logic:
    """
    # Requires external data
    if requires_web_search(task):
        return True
        
    # Exceeds local context
    if estimated_tokens(task) > 4000:
        return True
        
    # Complex multi-step reasoning
    if step_count(task) > 3:
        return True
        
    # Code generation (complex)
    if is_code_task(task) and complexity(task) > "simple":
        return True
        
    # Long-form output
    if expected_output_length(task) > 1000:
        return True
        
    return False
```

---

## 8.3 The `<REQ_CLAUDE>` Token

### Training the Delegation Signal

The Director LLM is fine-tuned to output a special token when it recognizes a task beyond its capability. This isn't a hardcoded rule — it's **learned behavior**.

### Training Data Format

```json
{
  "instruction": "What's the current state of AI regulation in the EU?",
  "response": "<REQ_CLAUDE>This requires current information beyond my local knowledge. Let me look into that for you.</REQ_CLAUDE>"
}

{
  "instruction": "Can you analyze this research paper and identify the key methodological flaws?",
  "response": "<REQ_CLAUDE>Document analysis at this depth is better handled by my research capabilities. Give me a moment.</REQ_CLAUDE>"
}

{
  "instruction": "Write a Python script that scrapes job listings and stores them in a database",
  "response": "<REQ_CLAUDE>This is a solid coding task. Let me put together something proper for you.</REQ_CLAUDE>"
}

{
  "instruction": "How are you feeling today?",
  "response": "Pretty good, actually. Been thinking about that architecture discussion we had. You seemed really in the zone last night."
}

{
  "instruction": "What did we decide about the runtime engine?",
  "response": "We landed on the Actor model — fault isolation with mailboxes. Gemini made a good point about variable heartbeat over fixed tick. Want me to pull up the specifics?"
}
```

### Detection Logic

```python
class DirectorActor(Actor):
    async def generate_response(self, prompt: str):
        """Generate response, watching for delegation signal."""
        response_buffer = ""
        
        async for token in self.model.generate_stream(prompt):
            response_buffer += token
            
            # Check for delegation signal
            if "<REQ_CLAUDE>" in response_buffer:
                # Extract the acknowledgment Luna gave
                ack = response_buffer.split("<REQ_CLAUDE>")[1].split("</REQ_CLAUDE>")[0]
                
                # Send acknowledgment to user immediately
                await self.voice_actor.send(SpeakMessage(ack))
                
                # Trigger delegation
                await self.trigger_delegation(prompt, ack)
                return
                
            # Stream token to voice
            await self.voice_actor.send(SpeakToken(token))
```

### Why Learned, Not Hardcoded

| Approach | Problem |
|----------|---------|
| Keyword matching | Brittle, misses nuance |
| Classifier model | Separate model to maintain |
| Hardcoded rules | Can't adapt to edge cases |
| **Learned behavior** | Luna knows her own limits |

The Director learns delegation the same way it learns personality — through training examples. This means:
- Delegation feels natural, not mechanical
- Luna can explain *why* she's delegating
- Edge cases are handled by intuition, not rules

---

## 8.4 The Shadow Reasoner Pattern

### The Problem

When Luna delegates to Claude, we don't want the user to hear Claude's voice. We want the user to always hear Luna.

**Bad UX:**
```
User: "What's the latest on semiconductor restrictions?"
Luna: "Let me check on that..."
[awkward silence while Claude thinks]
Claude: "The semiconductor export restrictions have..."
User: "Wait, who's talking?"
```

**Good UX:**
```
User: "What's the latest on semiconductor restrictions?"
Luna: "Ooh, that's been moving fast. Let me dig into that..."
[Luna plays filler, maybe "hmm" sounds]
Luna: "Okay so here's what's happening — the restrictions 
      have tightened significantly since October..."
User: [Hears only Luna's voice throughout]
```

### The Pattern

```
┌─────────────────────────────────────────────────────────────┐
│                     SHADOW REASONER                          │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                 FOREGROUND                           │   │
│   │                 (User-Facing)                        │   │
│   │                                                      │   │
│   │   1. Luna acknowledges task                         │   │
│   │   2. Luna plays filler/thinking sounds              │   │
│   │   3. Luna can continue casual chat                  │   │
│   │   4. Luna narrates results when ready               │   │
│   │                                                      │   │
│   └─────────────────────────────────────────────────────┘   │
│                           │                                  │
│                           │ Parallel                         │
│                           │                                  │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                 BACKGROUND                           │   │
│   │                 (Hidden)                             │   │
│   │                                                      │   │
│   │   1. Claude receives structured query               │   │
│   │   2. Claude performs research/analysis              │   │
│   │   3. Claude returns structured facts                │   │
│   │   4. Results injected to Director                   │   │
│   │                                                      │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### Implementation

```python
class OvenActor(Actor):
    """Handles async delegation to cloud workers."""
    
    async def handle_message(self, msg: Message):
        match msg.type:
            case MsgType.DELEGATION_REQUEST:
                await self.shadow_reason(
                    query=msg.query,
                    acknowledgment=msg.acknowledgment,
                    reply_to=msg.reply_to
                )
    
    async def shadow_reason(
        self, 
        query: str, 
        acknowledgment: str,
        reply_to: Actor
    ):
        """Execute Shadow Reasoner pattern."""
        
        # 1. User already heard acknowledgment from Director
        #    (e.g., "Let me dig into that...")
        
        # 2. Start background Claude request
        claude_task = asyncio.create_task(
            self.claude_client.query(
                self._format_delegation_prompt(query)
            )
        )
        
        # 3. Optional: Send filler to Director
        await self.send(reply_to, FillerRequest())
        
        # 4. Wait for Claude
        try:
            facts = await asyncio.wait_for(
                claude_task, 
                timeout=30.0
            )
        except asyncio.TimeoutError:
            facts = {"error": "Research is taking longer than expected"}
        
        # 5. Send facts to Director for narration
        await self.send(reply_to, DelegationResults(
            facts=facts,
            original_query=query
        ))
    
    def _format_delegation_prompt(self, query: str) -> str:
        """Format query for Claude — request facts, not personality."""
        return f"""You are a research assistant. Provide factual, 
structured information for the following query. Do NOT adopt 
any personality or conversational tone — just facts.

Query: {query}

Return your response as structured data:
- Key facts (bullet points)
- Sources if relevant
- Confidence level
- Any caveats or uncertainties

Be thorough but concise."""
```

### Director Narration

```python
class DirectorActor(Actor):
    async def handle_delegation_results(self, msg: DelegationResults):
        """Narrate Claude's facts in Luna's voice."""
        
        narration_prompt = f"""You just received research results 
for the user's question: "{msg.original_query}"

Here are the facts:
{json.dumps(msg.facts, indent=2)}

Now respond to the user in your natural voice. Don't say 
"according to my research" or "I found that" — just tell 
them what they wanted to know as if you knew it all along.
Be warm, be Luna."""

        async for token in self.model.generate_stream(narration_prompt):
            await self.voice_actor.send(SpeakToken(token))
```

---

## 8.5 Filler and Continuity

### The Awkward Silence Problem

Claude API calls take 2-10 seconds. Silence during delegation feels broken.

### Filler Strategies

| Strategy | When to Use | Example |
|----------|-------------|---------|
| Acknowledgment | Always | "Let me look into that..." |
| Thinking sounds | 1-3 seconds | "Hmm...", breath sounds |
| Status update | 3-5 seconds | "Still digging..." |
| Topic pivot | 5+ seconds | "While that's loading, how's your day going?" |

### Implementation

```python
class DirectorActor(Actor):
    async def play_filler_loop(self, task: asyncio.Task):
        """Play filler while delegation task runs."""
        
        elapsed = 0
        interval = 2.0
        
        while not task.done():
            await asyncio.sleep(interval)
            elapsed += interval
            
            if elapsed < 3:
                # Thinking sounds
                await self.voice_actor.send(PlaySound("thinking_hmm"))
            elif elapsed < 6:
                # Status update
                await self.voice_actor.send(SpeakMessage(
                    random.choice([
                        "Still working on that...",
                        "Almost there...",
                        "Digging deeper..."
                    ])
                ))
            else:
                # Offer pivot
                await self.voice_actor.send(SpeakMessage(
                    "This is taking a sec. Want to chat about something else while we wait?"
                ))
                break  # Don't loop forever
```

---

## 8.6 Cloud Worker Contracts

### The Contract Pattern

Each cloud worker has a defined contract:

```python
@dataclass
class WorkerContract:
    name: str
    capabilities: list[str]
    input_format: str
    output_format: str
    timeout_seconds: int
    retry_policy: RetryPolicy
    fallback: Optional[str]  # Another worker to try on failure
```

### Claude Contract

```python
CLAUDE_CONTRACT = WorkerContract(
    name="claude",
    capabilities=[
        "research",
        "analysis", 
        "code_generation",
        "code_review",
        "long_form_writing",
        "multi_step_reasoning",
        "document_analysis"
    ],
    input_format="structured_prompt",
    output_format="structured_facts",
    timeout_seconds=30,
    retry_policy=RetryPolicy(
        max_attempts=2,
        backoff_seconds=5
    ),
    fallback=None  # Claude is the primary
)
```

### Request/Response Format

```python
@dataclass
class DelegationRequest:
    task_type: str  # "research", "code", "analysis", etc.
    query: str
    context: Optional[dict]  # Relevant Memory Matrix context
    constraints: Optional[dict]  # Length limits, format requirements

@dataclass  
class DelegationResponse:
    success: bool
    facts: dict  # Structured output
    confidence: float  # 0-1
    sources: list[str]
    caveats: list[str]
    tokens_used: int
    latency_ms: int
```

### Error Handling

```python
class OvenActor(Actor):
    async def delegate_with_fallback(
        self, 
        request: DelegationRequest
    ) -> DelegationResponse:
        """Delegate with retry and fallback logic."""
        
        contract = self.get_contract(request.task_type)
        
        for attempt in range(contract.retry_policy.max_attempts):
            try:
                response = await asyncio.wait_for(
                    self._call_worker(contract.name, request),
                    timeout=contract.timeout_seconds
                )
                return response
                
            except asyncio.TimeoutError:
                logging.warning(f"Worker {contract.name} timed out, attempt {attempt + 1}")
                await asyncio.sleep(contract.retry_policy.backoff_seconds)
                
            except WorkerError as e:
                logging.error(f"Worker {contract.name} error: {e}")
                if contract.fallback:
                    return await self.delegate_with_fallback(
                        request, 
                        worker_override=contract.fallback
                    )
                raise
        
        # All retries exhausted
        return DelegationResponse(
            success=False,
            facts={"error": "Unable to complete research"},
            confidence=0,
            sources=[],
            caveats=["Delegation failed after retries"],
            tokens_used=0,
            latency_ms=0
        )
```

---

## 8.7 Privacy and Data Flow

### What Goes to Cloud

| Sent | NOT Sent |
|------|----------|
| User's current query | Full conversation history |
| Relevant context snippet | Entire Memory Matrix |
| Task type | User's personal details |
| Format requirements | Previous delegation results |

### Data Minimization

```python
def prepare_delegation_context(
    query: str, 
    memory_results: list[Node]
) -> dict:
    """Prepare minimal context for delegation."""
    
    # Only include directly relevant memories
    relevant = [m for m in memory_results if m.relevance > 0.7]
    
    # Anonymize if needed
    anonymized = [anonymize_node(m) for m in relevant]
    
    # Limit context size
    context_tokens = 0
    included = []
    for node in anonymized:
        node_tokens = count_tokens(node.content)
        if context_tokens + node_tokens > 1000:
            break
        included.append(node)
        context_tokens += node_tokens
    
    return {
        "relevant_context": [n.to_dict() for n in included],
        "context_tokens": context_tokens
    }
```

### Audit Trail

```python
@dataclass
class DelegationAudit:
    timestamp: datetime
    task_type: str
    query_hash: str  # Don't log raw query
    worker: str
    success: bool
    latency_ms: int
    tokens_sent: int
    tokens_received: int
    
# Stored in Memory Matrix for transparency
async def log_delegation(audit: DelegationAudit):
    await matrix.insert_node(
        node_type="DELEGATION_LOG",
        content=audit.to_json(),
        metadata={"internal": True}
    )
```

---

## 8.8 Future Workers

The delegation protocol is designed to be **worker-agnostic**. Claude is the primary today, but the architecture supports:

| Worker | Potential Use |
|--------|---------------|
| Gemini | Optimization, large context |
| Local 70B | Privacy-critical delegation |
| Specialized models | Code (Codestral), math (Minerva) |
| Tool APIs | Web search, calculators, databases |

### Adding a New Worker

```python
# 1. Define contract
GEMINI_CONTRACT = WorkerContract(
    name="gemini",
    capabilities=["optimization", "benchmarking", "large_context"],
    input_format="structured_prompt",
    output_format="structured_facts",
    timeout_seconds=45,
    retry_policy=RetryPolicy(max_attempts=2, backoff_seconds=5),
    fallback="claude"
)

# 2. Register with Oven
oven.register_worker("gemini", GeminiClient(), GEMINI_CONTRACT)

# 3. Director learns when to use it (training data)
{
    "instruction": "Analyze the performance characteristics of these three algorithms on large datasets",
    "response": "<REQ_GEMINI>This is a benchmarking task that benefits from larger context. Let me run some analysis.</REQ_GEMINI>"
}
```

---

## Summary

The Delegation Protocol defines how Luna's sovereign mind collaborates with cloud workers:

| Component | Role |
|-----------|------|
| Delegation Boundary | What Luna handles vs. delegates |
| `<REQ_CLAUDE>` Token | Learned delegation signal |
| Shadow Reasoner | Background execution, foreground narration |
| Filler & Continuity | No awkward silence |
| Worker Contracts | Standardized request/response |
| Privacy Controls | Minimal data sent to cloud |

**Constitutional Principle:** Luna's mind is local. Cloud workers are contractors. The user always hears Luna's voice.

---

*Next Section: Part IX — Performance Optimizations*
