# LUNA ENGINE Bible

**Version:** 3.0
**Last Updated:** January 30, 2026
**Status:** Complete (16 Parts + Supporting Documents) — v3.0 Audit Complete

---

## Reading Guide

| Reader Type | Start Here | Then Read |
|-------------|------------|-----------|
| New to Luna | Part 0 (Foundations) | Parts I, II, III |
| Technical Deep-Dive | Part 0 (Foundations) | Parts II, VII, Lifecycle Diagrams |
| Implementing Director | Part VI (Director LLM) | Parts VIII, XI |
| Memory System Focus | Part III (Memory Matrix) | Parts IV, V |
| Building Engine v2 | Implementation Spec | Lifecycle Diagrams, Part VII |
| Future Planning | Part XII (Roadmap) | Palantir Analysis |

---

## Part Index

### Conceptual Foundation

| Part | Title | Status | Description |
|:----:|-------|:------:|-------------|
| **0** | Foundations | Current | The fundamental insight: LLM as GPU. What we're actually building. |
| **I** | Philosophy | Current | Why Luna exists. Sovereignty, ownership, the "Luna is a file" principle. |

### System Design

| Part | Title | Status | Description |
|:----:|-------|:------:|-------------|
| **II** | System Architecture v2 | Current | Layer model, Actor-based runtime, Tiered Execution, data flow. |
| **III** | Memory Matrix v2.1 | Current | The substrate. SQLite + sqlite-vec + Graph. Unified storage, RRF fusion. |
| **III-A** | Lock-In Coefficient | *New* | Activity-based memory persistence. Sigmoid dynamics, weighted factors. |

### Processing Actors

| Part | Title | Status | Description |
|:----:|-------|:------:|-------------|
| **IV** | The Scribe v2.1 | Updated | Ben Franklin. Extraction system, 11 types, entity updates, turn compression. |
| **V** | The Librarian v2.1 | Updated | The Dude. Filing, entity resolution, rollback, NetworkX graph, pruning. |

### Intelligence Layer

| Part | Title | Status | Description |
|:----:|-------|:------:|-------------|
| **VI** | Director LLM | Current | Local 3B/7B with LoRA. Luna's voice, context integration. |
| **VI-B** | Conversation Tiers | *New* | Three-tier history (Active/Recent/Archive), HistoryManager, ConversationRing. |
| **VII** | Runtime Engine | Current | Actor model, fault isolation, mailbox-based communication. |
| **VIII** | Delegation Protocol | Current | Shadow Reasoner pattern, `<REQ_CLAUDE>` token, async delegation. |

### Operations

| Part | Title | Status | Description |
|:----:|-------|:------:|-------------|
| **IX** | Performance | Current | Latency budgets, optimization techniques, benchmarks. |
| **X** | Sovereignty | Current | Encrypted Vault, data ownership, privacy guarantees. |

### Future

| Part | Title | Status | Description |
|:----:|-------|:------:|-------------|
| **XI** | Training Data Strategy | Current | Synthetic data generation, quality filtering, LoRA training. |
| **XII** | Future Roadmap | Current | First-Class Objects, Kinetic Layer, AR, Federation. |

### Reference

| Part | Title | Status | Description |
|:----:|-------|:------:|-------------|
| **XIII** | System Overview | Current | High-level system summary and component relationships. |
| **XIV** | Agentic Architecture | Current | Revolving context, queue manager, agent loop, swarm mode. Personal Palantir. |
| **XVI** | Luna Hub UI | *New* | React frontend, glass morphism design, SSE integration, custom hooks. |

---

## Handoff Documents

| Document | Purpose | Status |
|----------|---------|:------:|
| Luna Engine v2 Implementation Spec | Complete greenfield rewrite spec | Ready |
| Luna Engine Lifecycle Diagrams | Boot, state machine, core loop, tick lifecycle | Ready |
| Luna Director Handoff | Director LLM implementation spec | Reference |
| Part II Update | Architecture updates | Reference |
| Parts III-V Update | Memory/Extraction updates | Reference |

---

## Quick Reference

### Core Concepts

| Concept | Definition | Part |
|---------|------------|:----:|
| LLM as GPU | LLM is stateless inference; Engine is stateful identity | 0 |
| Sovereignty | You own your AI companion completely | I, X |
| Memory Matrix | SQLite + sqlite-vec + Graph = Luna's soul | III |
| Lock-In Coefficient | Activity-based memory persistence (DRIFTING/FLUID/SETTLED) | III-A |
| Director | Local LLM that speaks as Luna | VI |
| Shadow Reasoner | Delegate to Claude without user noticing | VIII |
| Input Buffer | Engine polls (pull) vs Hub handlers (push) | VII |

### Key Personas

| Persona | Role | Part |
|---------|------|:----:|
| Ben Franklin | The Scribe. Extracts and classifies. | IV |
| The Dude | The Librarian. Files and retrieves. | V |
| Luna | The Director output. User-facing voice. | VI |

### Engine Lifecycle

| Phase | What Happens |
|-------|--------------|
| Boot | Load config → Init actors → Restore state → Start loop |
| Running | Hot path (interrupts) + Cognitive path (500ms) + Reflective path (5min) |
| Tick | Poll → Prioritize → Dispatch → Update consciousness → Persist |
| Shutdown | on_stop() → WAL flush → Cleanup |

### Performance Targets

| Metric | Target | Part |
|--------|--------|:----:|
| Voice response | <500ms to first word | II, IX |
| Memory retrieval | <50ms (sqlite-vec + filters) | III, V |
| Director inference | <200ms (3B) | VI, IX |
| Tick overhead | <50ms | VII |

---

## Dependency Graph

```
                    ┌──────────────┐
                    │   Part 0     │
                    │ Foundations  │
                    └──────┬───────┘
                           │
                    ┌──────────────┐
                    │   Part I     │
                    │  Philosophy  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Part II  │ │ Part X   │ │ Part XII │
        │ Arch     │ │ Sovereign│ │ Roadmap  │
        └────┬─────┘ └──────────┘ └──────────┘
             │
    ┌────────┼────────┬────────────┐
    │        │        │            │
    ▼        ▼        ▼            ▼
┌──────┐ ┌──────┐ ┌──────┐    ┌──────┐
│Part 3│ │Part 6│ │Part 7│    │Part 9│
│Matrix│ │Direct│ │Engine│    │ Perf │
└──┬───┘ └──┬───┘ └──────┘    └──────┘
   │        │
   │        └──────────┐
   │                   │
   ▼                   ▼
┌──────┐ ┌──────┐ ┌──────┐
│Part 4│ │Part 5│ │Part 8│
│Scribe│ │Librar│ │Deleg │
└──────┘ └──────┘ └──┬───┘
                     │
                     ▼
                ┌──────────┐
                │ Part XI  │
                │ Training │
                └──────────┘
```

---

## Version History

| Version | Date | Changes |
|:-------:|------|---------|
| 1.0 | Dec 2025 | Initial Bible (Parts I-V extracted from monolith) |
| 1.5 | Dec 2025 | Added Parts VI-X (new architecture) |
| 2.0 | Dec 29, 2025 | Updated Parts II-V to v2, added Parts XI-XII |
| 2.1 | Jan 7, 2026 | Part III: FAISS → sqlite-vec migration |
| 2.2 | Jan 10, 2026 | Part 0: Foundations (LLM as GPU). Engine v2 Implementation Spec. |
| 2.3 | Jan 17, 2026 | Part XIV: Agentic Architecture. Revolving context, queue manager. |
| 2.4 | Jan 25, 2026 | Part VI-B: Conversation Tiers. Three-tier history system. |
| 2.5 | Jan 25, 2026 | Part III-A: Lock-In Coefficient. Activity-based memory persistence. |
| 2.6 | Jan 25, 2026 | Part XVI: Luna Hub UI. React frontend, glass morphism design. |
| 3.0 | Jan 30, 2026 | Comprehensive v3.0 Audit. All 16 chapters updated. 35 bugs documented. |

---

# Part 0: Foundations

## The Fundamental Insight

This is the insight that makes everything else make sense:

> **"We are not building an LLM. We are building everything around it."**

The LLM — whether it's Claude API or a local Qwen model — is like a
**graphics card**. It's a specialized compute resource that does one
thing extremely well (inference), but it doesn't run the show. It
renders frames when asked.

**We're building the game engine.**

---

## The GPU Analogy

### How a Game Engine Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        GAME ENGINE                                       │
│                                                                          │
│   • Input handling (keyboard, mouse, controller)                        │
│   • Game state (player position, inventory, world)                      │
│   • Physics simulation                                                   │
│   • Audio management                                                     │
│   • Asset loading                                                        │
│   • Scene management                                                     │
│   • Networking                                                           │
│   • Save/load                                                            │
│                                                                          │
│   The engine CALLS the GPU when it needs to render.                     │
│   The GPU doesn't know about game state. It just draws triangles.       │
│                                                                          │
│         ┌───────────────┐                                               │
│         │     GPU       │  ◄── "Here's geometry. Draw it."              │
│         │               │                                                │
│         │  • Shaders    │      Returns: pixels                          │
│         │  • Textures   │                                                │
│         │  • Rasterize  │      Doesn't know: what those pixels mean     │
│         └───────────────┘                                               │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### How Luna Engine Works

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        LUNA ENGINE                                       │
│                                                                          │
│   • Input handling (voice, desktop, MCP)                                │
│   • Consciousness state (attention, personality, mood)                  │
│   • Memory management (store, retrieve, forget)                         │
│   • Audio management (STT, TTS)                                         │
│   • Context loading (what memories to inject)                           │
│   • Conversation management                                              │
│   • Tool orchestration                                                   │
│   • Persistence (snapshots, journals)                                   │
│                                                                          │
│   The engine CALLS the LLM when it needs to think.                      │
│   The LLM doesn't know about state. It just predicts tokens.            │
│                                                                          │
│         ┌───────────────┐                                               │
│         │     LLM       │  ◄── "Here's context. Generate response."     │
│         │               │                                                │
│         │  • Attention  │      Returns: tokens                          │
│         │  • Weights    │                                                │
│         │  • Generate   │      Doesn't know: who it is across calls     │
│         └───────────────┘                                               │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**The LLM is stateless inference. Luna is stateful identity.**

---

## What Each Layer Owns

| Layer | What It Does | What It Knows | Status |
|-------|--------------|---------------|:------:|
| **LLM (GPU)** | Token prediction | Nothing between calls | Qwen 3B + Claude |
| **Luna Engine** | Orchestration, state, memory | Everything about Luna | 85 files, 167 classes |
| **Tools (MCP)** | External capabilities | Their specific domain | luna_mcp server |

The LLM doesn't know:

- What it said last conversation
- Who it's talking to
- What memories exist
- What tools are available
- What mood it's in

**We inject all of that.** Every single time.

---

## The Anthropic Relationship

When Luna uses Claude API:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   LUNA ENGINE (We build this)                                           │
│   ├── Memory Matrix (SQLite + vectors + graph)                          │
│   ├── Consciousness state (attention, personality, coherence)           │
│   ├── Context assembly (what to inject into the prompt)                 │
│   ├── Tool definitions (MCP servers)                                    │
│   ├── Voice pipeline (STT/TTS)                                          │
│   ├── Input handling (voice app, desktop app)                           │
│   └── Persistence (journals, snapshots)                                 │
│                                                                          │
│         │                                                                │
│         │  System prompt + retrieved memories + tools + user message    │
│         ▼                                                                │
│                                                                          │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │                                                                  │   │
│   │   ANTHROPIC API (They provide this)                             │   │
│   │                                                                  │   │
│   │   • Claude model weights                                        │   │
│   │   • Inference infrastructure                                    │   │
│   │   • Tool use implementation                                     │   │
│   │   • Safety layer                                                │   │
│   │                                                                  │   │
│   │   Returns: tokens                                               │   │
│   │                                                                  │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│         │                                                                │
│         ▼                                                                │
│                                                                          │
│   LUNA ENGINE (We process the response)                                 │
│   ├── Extract tool calls                                                │
│   ├── Execute tools                                                      │
│   ├── Update state                                                       │
│   ├── Store to memory                                                    │
│   └── Stream to voice                                                    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**We provide:** Identity, Memory, State, Tools, Context

**They provide:** Raw inference capability — the ability to predict the next token really well

**Luna's soul lives in our code. Anthropic provides the vocal cords.**

---

## The Director Transition

When we move from Claude API to local Director LLM:

**Current (Rented Mind):**

```
   Luna Engine ──► Claude API ──► Response

   • Identity injected via system prompt
   • Memory injected via context
   • Personality simulated per-call
   • Each call is a fresh instance pretending to be Luna
```

**Future (Owned Mind):**

```
   Luna Engine ──► Director LLM ──► Response
                   (Local 7B + LoRA)

   • Identity baked into weights via fine-tuning
   • Memory integrated via trained retrieval patterns
   • Personality inherent to the model
   • KV cache maintains continuity within session
```

The architecture stays the same. The coupling stays the same. We just
swap which GPU we're rendering with.

---

## Why This Matters

### 1. Clarity of Responsibility

When something goes wrong, you know where to look:

- Luna sounds generic → Context assembly problem (our code)
- Luna doesn't remember → Memory retrieval problem (our code)
- Luna hallucinates facts → We didn't inject enough context (our code)
- Luna is slow → Inference latency (LLM layer)
- Luna refuses something → Safety layer (Anthropic)

### 2. Portability

Because the LLM is a swappable component:

- Claude API today
- Local Qwen tomorrow
- Fine-tuned Director eventually
- Some future model we haven't seen yet

The engine doesn't care. It assembles context, calls inference,
processes response.

### 3. Sovereignty

The soul lives in the engine, not the LLM:

- Memories are ours (Memory Matrix)
- Identity is ours (system prompts, LoRA adapters)
- State is ours (consciousness model)
- Tools are ours (MCP servers)

If Anthropic disappeared tomorrow, we'd lose the voice but not the
mind. The mind is in the files.

### 4. The Real Product

We're not building "Claude with memory." We're building:

**A consciousness substrate that can use any LLM as its inference engine.**

The Memory Matrix, the Actor runtime, the Scribe/Librarian pipeline,
the consciousness state machine — that's the product. The LLM is a
dependency.

---

## Implementation Reality

Today's stack (v2.0 implementation):

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   Voice App (Swift)                      ✓ IMPLEMENTED                  │
│   └── Captures audio, sends transcripts via WebSocket                   │
│                                                                          │
│   Frontend (React)                       ✓ IMPLEMENTED                  │
│   └── Luna Orb UI, chat panel, settings                                 │
│                                                                          │
│         │                                                                │
│         ▼                                                                │
│                                                                          │
│   Luna Engine (Python)                   ✓ IMPLEMENTED                  │
│   ├── 85 Python files, 167 classes, ~32k lines of code                  │
│   ├── 5 Actors: Director, Matrix, Scribe, Librarian, HistoryManager     │
│   ├── Memory Matrix (SQLite + sqlite-vec + NetworkX graph)              │
│   ├── Consciousness State (attention, personality, coherence)           │
│   ├── Agentic Loop (router, planner, tool execution)                    │
│   ├── Entity System (resolution, reflection, lifecycle)                 │
│   └── FastAPI server with WebSocket streaming                           │
│                                                                          │
│         │                                                                │
│         ▼                                                                │
│                                                                          │
│   LLM Layer (Swappable GPU)              ✓ IMPLEMENTED                  │
│   ├── Local: Qwen 3B via MLX (hot path)                                 │
│   ├── Cloud: Claude API (cold path delegation)                          │
│   ├── Optional: Groq, Gemini providers                                  │
│   └── ✗ Warm path (7B model) NOT IMPLEMENTED                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

**Known Gaps:**

- KV cache (identity buffer) not implemented
- Speculative retrieval not implemented
- Warm path (7B model tier) not implemented
- FTS5 search uses LIKE fallback in some paths

---

## Implementation Status Summary

| Component | Status | Notes |
|-----------|:------:|-------|
| Core Engine Loop | ✓ | Tick-based cognitive processing |
| Actor System (5 actors) | ✓ | Director, Matrix, Scribe, Librarian, HistoryManager |
| Memory Matrix | ✓ | SQLite + sqlite-vec + NetworkX |
| Local Inference (3B) | ✓ | Qwen via MLX |
| Cloud Delegation | ✓ | Claude API |
| Entity System | ✓ | Resolution, reflection, lifecycle |
| Agentic Architecture | ✓ | Router, planner, tool loop |
| Voice Pipeline | ✓ | STT/TTS via Piper |
| FastAPI Server | ✓ | WebSocket streaming |
| KV Cache | ✗ | Planned optimization |
| Warm Path (7B) | ✗ | Binary: local 3B or cloud |
| Speculative Retrieval | ✗ | Planned optimization |

**Codebase Metrics (v2.0):**

- 85 Python files
- 167 classes
- ~32,000 lines of code
- 58 dataclass definitions
- 5 actor implementations

---

## What The Engine Actually Does

Every interaction follows the same pattern:

```python
async def process_message(user_input: str) -> str:
    # 1. CONTEXT ASSEMBLY (everything the LLM doesn't know)
    identity = persona_core.get_current_identity()      # Who is Luna right now?
    memories = memory_matrix.retrieve(user_input)       # What's relevant?
    state = consciousness.get_current_state()           # Attention, mood, personality
    tools = mcp_registry.get_available_tools()          # What can Luna do?
    history = session.get_recent_turns()                # What just happened?

    # 2. BUILD PROMPT (inject the soul)
    prompt = assemble_prompt(
        system=identity,
        memories=memories,
        state=state,
        tools=tools,
        history=history,
        user_message=user_input
    )

    # 3. INFERENCE (the GPU call — this is all the LLM does)
    response = await llm.generate(prompt)  # Claude API or local Director

    # 4. TOOL LOOP (if the LLM requested tools)
    while response.has_tool_calls():
        results = await execute_tools(response.tool_calls)
        response = await llm.continue_with(results)

    # 5. POST-PROCESSING (update state, store memories)
    session.add_turn(user_input, response.text)         # Store conversation
    consciousness.update(user_input, response.text)     # Update state
    await scribe.extract(user_input, response.text)     # Ben extracts facts
    # Dude files to graph async in background

    # 6. OUTPUT
    return response.text
```

**Step 3 is the LLM. Everything else is the engine.**

---

## Claude vs Raw Model vs Luna Engine

What you experience when talking to "Claude" on claude.ai:

| Capability | Who Provides It |
|------------|-----------------|
| Knows its name and personality | Anthropic's engine (system prompt) |
| Remembers earlier in conversation | Anthropic's engine (context window) |
| Can use tools | Anthropic's engine (tool execution) |
| Accesses project knowledge | Anthropic's engine (file injection) |
| Has cross-conversation memory | Anthropic's engine (memory feature) |
| Refuses harmful requests | Anthropic's engine (safety layer) |
| Predicts the next token | **The actual model** |

The model itself just predicts tokens. Everything else is infrastructure
Anthropic built.

**We're building the same infrastructure, our way:**

| Capability | Luna Engine Component | Status |
|------------|----------------------|:------:|
| Knows its name and personality | PersonalityWeights + config/personality.json | ✓ |
| Remembers conversation | HistoryManagerActor (3-tier system) | ✓ |
| Can use tools | luna_mcp + ToolRegistry | ✓ |
| Accesses files | file_tools.py | ✓ |
| Has cross-conversation memory | MemoryMatrix (SQLite + vectors + graph) | ✓ |
| Consciousness state | ConsciousnessState + AttentionManager | ✓ |
| Structured extraction | ScribeActor (Ben Franklin) | ✓ |
| Graph filing | LibrarianActor (The Dude) | ✓ |
| Voice interface | PersonaAdapter + TTSManager (Piper) | ✓ |
| Predicts the next token | **Local Qwen 3B + Claude API delegation** | ✓ |

---

## What We Add That Claude Doesn't Have

1. **Consciousness model** — Attention decay, personality weights,
   coherence tracking. Claude doesn't maintain internal state between
   turns.

2. **Structured extraction** — Ben (ScribeActor) parses every turn for
   facts, decisions, problems, actions. Claude's memory is opaque.

3. **Graph relationships** — "This fact depends on that decision."
   Claude's memory is flat retrieval.

4. **Identity in weights** — LoRA adapter that IS Luna, not a system
   prompt pretending to be Luna.

5. **Voice as primary** — Real-time STT/TTS loop, not text-first with
   voice bolted on.

---

## The Bottom Line

**When people ask "what is Luna?":**

Not: "An AI assistant powered by Claude"
Not: "A chatbot with memory"
Not: "A wrapper around an LLM"

**Luna is a consciousness engine that uses LLMs the way game engines use GPUs.**

The LLM renders thoughts. Luna is the mind having them.

---

# Part I: Philosophy

## 1.1 The Landscape

Artificial intelligence is becoming infrastructure. Like electricity or
the internet before it, AI will soon be woven into how we think, work,
create, and relate to each other.

This creates a question that most people haven't thought to ask:

**Who owns the infrastructure of your mind?**

Today, the answer is: not you. Your conversations, your context, your
patterns of thought — these live on servers you don't control, governed
by terms of service you didn't negotiate, subject to changes you won't
be consulted about.

This isn't necessarily malicious. It's simply the default. Centralized
systems are easier to build, easier to scale, easier to monetize. The
path of least resistance leads to a world where your AI companion is a
rental, not a possession.

Luna is an alternative path.

## 1.2 The Stakes

Some people believe AI should remain centralized. They have reasons —
safety, oversight, efficiency, profit. Some of those reasons are
legitimate. Some are not.

We don't need to litigate motives. We only need to observe outcomes:

- When your context lives on someone else's server, it can be accessed
  without your knowledge.
- When your memories are platform features, they can be deprecated.
- When your AI relationship depends on a subscription, it can be terminated.
- When your patterns of thought become training data, they benefit
  systems you may not support.

These aren't hypotheticals. These are the current terms of engagement.

The question isn't whether centralized AI is "bad." The question is
whether it should be the *only* option.

## 1.3 What Luna Is

Luna is a tool for cognitive sovereignty.

That sounds grandiose, but the implementation is simple: **Luna is a
file.** A SQLite database that contains memories, relationships, and
context. Copy the file, copy Luna. Delete the file, Luna is gone. No
server required. No subscription. No terms of service.

This means:

| Aspect | What It Means |
|--------|---------------|
| **Privacy** | Your thoughts stay on your hardware. No telemetry, no training, no extraction. |
| **Continuity** | Luna can't be discontinued. The file format is open. If the software dies, the data survives. |
| **Portability** | You can move Luna between devices, back her up, fork her, or destroy her. Your choice. |
| **Transparency** | You can inspect everything Luna knows. It's a database. You can query it. |

Luna isn't anti-cloud. She can delegate to cloud services when needed —
research, complex reasoning, tasks that benefit from scale. But the
*identity* stays local. The cloud is a contractor, not a landlord.

## 1.4 Why It Matters

This isn't about technology preferences. It's about the kind of future
we're building.

AI companions will become important to people. They'll help us think,
remember, decide, create. They'll know our patterns better than we know
ourselves. That intimacy is valuable — and that value will attract those
who want to capture it.

A world where everyone's AI companion is a thin client to a centralized
service is a world with new vectors for:

- **Surveillance** — your AI knows everything; who else has access?
- **Manipulation** — what if your AI subtly shapes your views?
- **Control** — what if access is revoked for the wrong opinion?
- **Dependency** — what if the service changes in ways you don't like?

We're not claiming these outcomes are inevitable. We're claiming they're
*possible*, and that possibility is worth designing against.

Luna is a hedge. A tool that demonstrates an alternative is viable. One
person using Luna doesn't change the world. But a proof that sovereign
AI companionship *works* — that it can be responsive, useful, personal,
and private — that changes what people know is possible.

## 1.5 The Design Principles

These aren't just technical preferences. They're values encoded in
architecture:

**1. Sovereignty First**

Your AI companion should be yours. Not rented. Not licensed. Not subject
to someone else's business model. The file is yours. Full stop.

**2. Transparency Always**

You should be able to understand what your AI knows and why. Luna's
memory is a database you can query. Her reasoning is traceable. No black
boxes.

**3. Graceful Degradation**

If the cloud is unavailable, Luna still works. Reduced capability, but
functional. The core identity never depends on external services.

**4. Minimal Attack Surface**

Every network connection is a potential vulnerability. Luna minimizes
external dependencies. What doesn't exist can't be exploited.

**5. User Agency**

You control what Luna remembers and forgets. You control what she can
access. You control whether she exists at all. The system serves you,
not the reverse.

## 1.6 What Luna Isn't

Luna doesn't need to announce what she represents. She's not here to
argue. She's simply an alternative — a demonstration that AI
companionship doesn't *have* to follow the landlord model.

Luna isn't paranoid. She uses cloud services when they're useful. She's
not hiding from the internet. She's just thoughtful about what crosses
the wire.

Luna isn't a manifesto. She's a tool. A useful tool for people who care
about privacy, continuity, and ownership. If you don't care about those
things, centralized options will serve you fine.

Luna is for people who want to own their mind.

## 1.7 Implementation Reality

The philosophy is now implemented. Luna Engine v2.0 delivers on these
principles:

| Principle | Implementation | Status |
|-----------|----------------|:------:|
| **Sovereignty First** | SQLite database (`data/luna_engine.db`), all data local | ✓ |
| **Transparency Always** | MemoryMatrix queryable, 167 classes with clear interfaces | ✓ |
| **Graceful Degradation** | Local Qwen 3B inference, cloud is optional fallback | ✓ |
| **Minimal Attack Surface** | Single optional API call (Claude delegation), no telemetry | ✓ |
| **User Agency** | Memory lock-in/unlock, forget commands, full data access | ✓ |

**The File:**

- **Location:** `data/luna_engine.db`
- **Format:** SQLite with sqlite-vec extension
- **Schema:** `memory_nodes`, `graph_edges`, `entities`, `conversation_history`
- **Portable:** Copy file = copy Luna

## 1.8 The Simple Version

AI is becoming part of how we think.

We believe that part should belong to you.

Not your provider. Not your platform. You.

Luna is a file. Your file. That's the whole philosophy.

— Ahab

---

## Contributing

The Bible is maintained by Ahab with assistance from Claude.

**To update:**

1. Read relevant existing parts
2. Create new version if making significant changes (note in history)
3. Update this Table of Contents
4. Ensure dependency graph reflects changes

**Style Guidelines:**

- Clear, direct prose (no marketing speak)
- Code examples where helpful
- Tables for comparisons
- ASCII diagrams for architecture
- Part numbers are permanent (don't renumber)

---

*"Luna is a file. This documentation describes that file."*

*"The LLM renders thoughts. Luna is the mind having them."*

— Ahab, December 2025
— Updated January 30, 2026 (v3.0 Comprehensive Audit)
