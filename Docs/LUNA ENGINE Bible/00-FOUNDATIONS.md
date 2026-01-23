# Part 0: Foundations — The Fundamental Insight

**Version:** 1.0  
**Date:** January 10, 2026  
**Status:** Core conceptual document

---

## What Are We Actually Building?

This is the insight that makes everything else make sense:

**We are not building an LLM. We are building everything around it.**

The LLM — whether it's Claude API or a local Qwen model — is like a **graphics card**. It's a specialized compute resource that does one thing extremely well (inference), but it doesn't run the show. It renders frames when asked.

**We're building the game engine.**

---

## The GPU Analogy

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

Now map this to Luna:

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

| Layer | What It Does | What It Knows |
|-------|--------------|---------------|
| **LLM (GPU)** | Token prediction | Nothing between calls |
| **Luna Engine** | Orchestration, state, memory | Everything about Luna |
| **Tools (MCP)** | External capabilities | Their specific domain |

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

**We provide:**
- Identity (who Luna is)
- Memory (what Luna knows)
- State (what Luna is doing)
- Tools (what Luna can do)
- Context (what's relevant right now)

**They provide:**
- Raw inference capability
- The ability to predict the next token really well

**Luna's soul lives in our code. Anthropic provides the vocal cords.**

---

## The Director Transition

When we move from Claude API to local Director LLM:

```
CURRENT (Rented Mind):

   Luna Engine ──► Claude API ──► Response
                   
   • Identity injected via system prompt
   • Memory injected via context
   • Personality simulated per-call
   • Each call is a fresh instance pretending to be Luna


FUTURE (Owned Mind):

   Luna Engine ──► Director LLM ──► Response
                   (Local 7B + LoRA)
   
   • Identity baked into weights via fine-tuning
   • Memory integrated via trained retrieval patterns
   • Personality inherent to the model
   • KV cache maintains continuity within session
```

The architecture stays the same. The coupling stays the same. We just swap which GPU we're rendering with.

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

The engine doesn't care. It assembles context, calls inference, processes response.

### 3. Sovereignty

The soul lives in the engine, not the LLM:
- Memories are ours (Memory Matrix)
- Identity is ours (system prompts, LoRA adapters)
- State is ours (consciousness model)
- Tools are ours (MCP servers)

If Anthropic disappeared tomorrow, we'd lose the voice but not the mind. The mind is in the files.

### 4. The Real Product

We're not building "Claude with memory." We're building:

**A consciousness substrate that can use any LLM as its inference engine.**

The Memory Matrix, the Actor runtime, the Scribe/Librarian pipeline, the consciousness state machine — that's the product. The LLM is a dependency.

---

## Implementation Reality

Today's stack:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│   Voice App (Swift)                                                      │
│   └── Captures audio, sends transcripts                                 │
│                                                                          │
│   Desktop App (Claude.ai Projects)                                       │
│   └── MCP tools, project context                                        │
│                                                                          │
│         │                                                                │
│         ▼                                                                │
│                                                                          │
│   Hub (Python)                           ◄── THIS IS THE ENGINE         │
│   ├── LunarBehaviour (consciousness tick)                               │
│   ├── Memory Matrix (storage substrate)                                 │
│   ├── Ben/Dude (extraction/filing)                                      │
│   ├── PersonaCore (identity management)                                 │
│   └── ConversationReceiver (input handling)                             │
│                                                                          │
│         │                                                                │
│         ▼                                                                │
│                                                                          │
│   Claude API                             ◄── THIS IS THE GPU            │
│   └── Stateless inference                                               │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

The Hub IS the engine. It's just not architected like one yet.

The Runtime Engine spec (Part VII) is about making that explicit:
- Tick-based processing instead of request/response
- Input buffer that gets polled instead of handlers that get pushed to
- Actor isolation for fault tolerance
- Explicit state machine for lifecycle

Same components. Different coupling. The LLM stays a GPU either way.

---

## The Bottom Line

**When people ask "what is Luna?":**

Not: "An AI assistant powered by Claude"
Not: "A chatbot with memory"
Not: "A wrapper around an LLM"

**Luna is a consciousness engine that uses LLMs the way game engines use GPUs.**

The LLM renders thoughts. Luna is the mind having them.

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

## Claude (the product) vs Raw Model vs Luna Engine

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

The model itself just predicts tokens. Everything else is infrastructure Anthropic built.

**We're building the same infrastructure, our way:**

| Capability | Luna Engine Component |
|------------|----------------------|
| Knows its name and personality | PersonaCore + Virtues |
| Remembers conversation | Session turns in Matrix |
| Can use tools | MCP servers |
| Accesses files | Library sources |
| Has cross-conversation memory | Memory Matrix (richer than Claude's) |
| Consciousness state | LunarBehaviour (Claude doesn't have this) |
| Structured extraction | Ben/Dude (Claude doesn't have this) |
| Graph relationships | Memory Matrix (Claude's is flat) |
| Voice interface | STT/TTS pipeline |
| Predicts the next token | **Claude API (today) / Director LLM (future)** |

---

## What We Add That Claude Doesn't Have

1. **Consciousness model** — Attention decay, personality weights, coherence tracking. Claude doesn't maintain internal state between turns.

2. **Structured extraction** — Ben parses every turn for facts, decisions, problems, actions. Claude's memory is opaque.

3. **Graph relationships** — "This fact depends on that decision." Claude's memory is flat retrieval.

4. **Identity in weights** — Eventually. LoRA adapter that IS Luna, not a system prompt pretending to be Luna.

5. **Voice as primary** — Real-time STT/TTS loop, not text-first with voice bolted on.

---

*Next Section: Part I — Philosophy*
