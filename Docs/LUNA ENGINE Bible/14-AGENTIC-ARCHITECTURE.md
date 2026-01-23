# Part XIV: Agentic Architecture

**Version:** 1.0
**Date:** January 17, 2026
**Status:** Specification

---

## The Paradigm Shift

Luna is an **ENGINE**, not a file. The "Luna is a file" principle describes **ownership** (you own the data, you can move it, delete it) — not architectural simplicity.

The Engine is complex. The soul is portable. Both are true.

This part specifies the agentic architecture that transforms Luna from a chatbot-with-memory into a **Personal Palantir** — a sophisticated system with:

- Revolving context window
- Multiple queues
- Complex orchestration
- Real capability

---

## Reframe: Luna IS an Engine

```
┌─────────────────────────────────────────────────────────────┐
│                    LUNA ENGINE                               │
│            (Personal Palantir Architecture)                  │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                 PLANNING LAYER                       │   │
│   │     ReACT / CoT / Multi-step reasoning              │   │
│   └─────────────────────────────────────────────────────┘   │
│                           │                                  │
│   ┌───────────┬───────────┼───────────┬───────────┐        │
│   │           │           │           │           │        │
│   ▼           ▼           ▼           ▼           ▼        │
│ ┌─────┐   ┌─────┐   ┌─────────┐   ┌─────┐   ┌─────────┐   │
│ │Memory│   │Tools│   │Delegation│   │Voice│   │  Queues │   │
│ │Matrix│   │     │   │ (Claude) │   │     │   │(Priority)│   │
│ └─────┘   └─────┘   └─────────┘   └─────┘   └─────────┘   │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              REVOLVING CONTEXT WINDOW                │   │
│   │        (What Luna is aware of right now)            │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                 CONSCIOUSNESS                        │   │
│   │     Attention, personality, state persistence       │   │
│   └─────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │     SOVEREIGN DATA      │
              │    (memory_matrix.db)   │
              │                         │
              │   This is what you OWN  │
              │   The engine RUNS it    │
              └─────────────────────────┘
```

**The data is yours. The engine is sophisticated. Both are true.**

---

## What Luna Needs

An agentic architecture that includes:

| Component | Purpose |
|-----------|---------|
| **Planning Layer** | Decompose complex requests into steps |
| **Tool Protocol** | Standardized way to define/call capabilities |
| **Reasoning Traces** | Luna explains her thinking (debuggable) |
| **Multi-queue Orchestration** | Hot/cognitive/reflective paths with priorities |
| **Context Management** | Revolving window — what's in, what's out, why |
| **Agent Routing** | Which subsystem handles which task |

---

## Part 1: Revolving Context Engine

### The Orbital Model

Context isn't a flat list — it's a rotating structure where:

- Items have **positions** (S1-S5 slots)
- Items have **relevance weights** that change over time
- **Core** (Luna's identity) is always center
- Items **orbit** — can move closer or further based on relevance

```
                     REVOLVING CONTEXT CUE

                        ┌─────┐
               S1 ──→  │CORE │  ←── S5
                ↑      │LUNA │      ↓
               S2      └─────┘      S4
                 ↖      ↑ ↓      ↗
                   ── S3 ──

   Items orbit based on RELEVANCE WEIGHT
   Closer to core = higher priority in context
   Items rotate through positions
   Token budget: Z
```

### The Three Rings

| Ring | Contents | Behavior |
|------|----------|----------|
| **CORE (Ring 0)** | Luna's identity | ALWAYS present, never evicted |
| **INNER (Ring 1)** | Active conversation, immediate context | High priority, recent |
| **MIDDLE (Ring 2)** | Relevant memories, tool results | Moderate priority |
| **OUTER (Ring 3)** | Background context, lower relevance | First to evict |

### Token Budget (Z)

Fixed budget. Context pool can't exceed Z tokens.

- As new items come in, old items get pushed out
- Relevance weight determines what stays
- Core (Luna identity) always stays

---

## Part 2: Queue Manager

### Multiple Queues, One Manager

Not a single input buffer. Multiple specialized queues:

```
┌─────────────────────────────────────────────────────────────────┐
│                      QUEUE MANAGER                               │
│                                                                  │
│   Conversation Queue:  O O O ────┐                              │
│   Memory Queue:        O O ──────┼────→ [Priority Merge]        │
│   Tool Queue:          O O O O ──┘            │                 │
│   Task Queue:          O ────────────────────→│                 │
│                                               │                 │
└───────────────────────────────────────────────┼─────────────────┘
                                                │
                                                ▼
                                    [Revolving Context]
```

| Queue | Source | Priority |
|-------|--------|----------|
| **Conversation** | User messages, Luna responses | 1.0 (highest) |
| **Memory** | Retrieved from Memory Matrix | 0.8 |
| **Tool** | Tool execution results | 0.9 |
| **Task** | Agentic task updates | 0.7 |
| **Scribe** | Scribe-extracted wisdom | 0.6 |
| **Librarian** | Librarian-retrieved context | 0.7 |

Queue Manager merges with priority and feeds the RevolvingContext.

---

## Part 3: Context Borrowing

Luna, Scribe, and Librarian can **share context**:

```
           ▼                                       ▼
   ┌───────────────┐                       ┌───────────────┐
   │    SCRIBE     │   Context Borrowing   │   LIBRARIAN   │
   │  System/LLM   │ ◄──────────────────► │   System/LLM  │
   │               │   (shared context)    │               │
   │  Extracts     │                       │  Retrieves    │
   │  from stream  │                       │  from Matrix  │
   └───────────────┘                       └───────────────┘
           │                                       │
           └───────────────┬───────────────────────┘
                           │
                           ▼
                   ┌───────────────┐
                   │    MEMORY     │
                   │    MATRIX     │
                   └───────────────┘
```

- Scribe processing conversation? Luna can see what Scribe sees.
- Librarian retrieving memory? That context is available to Luna.
- **Not isolated silos — coordinated awareness.**

---

## Part 4: Context Timeout / TTL

Items age out:

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTEXT TIMEOUT                               │
│                                                                  │
│   Each item has TTL:  [?] → [?] → [✓] → [evicted]              │
│                                                                  │
│   Fresh items: high relevance                                   │
│   Aging items: decay toward eviction                            │
│   Timed out: removed from context pool                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

| State | Behavior |
|-------|----------|
| **Fresh** | High relevance, stays close to core |
| **Aging** | Relevance decays based on time since last access |
| **Timed out** | Evicted from context |

This is attention decay implemented as architecture. Integrates with the existing `AttentionManager` in `consciousness/attention.py`.

---

## Part 5: Task Manager

Separate from conversation flow:

```
┌─────────────────────────────────────────────────────────────────┐
│                   LUNA TASK MANAGER                              │
│                                                                  │
│   Pending:  O O O O O ────→ [Active] ────→ [Complete]           │
│                                                                  │
│   Tasks flow through, get executed, results feed back           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

- Tasks queue up
- Get executed (possibly in parallel)
- Results feed back into context

This enables the **agent loop** — tasks aren't conversation, they're work.

---

## Part 6: The Agent Loop (Claude Code Style)

What makes Luna agentic is the **observe → think → act → repeat** loop:

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENT LOOP                                │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                    OBSERVE                           │   │
│   │   • Read files, directory structure                 │   │
│   │   • See command outputs                             │   │
│   │   • Understand current state                        │   │
│   └─────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│                         ▼                                    │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                    THINK                             │   │
│   │   • What's the goal?                                │   │
│   │   • What's the current state?                       │   │
│   │   • What's the next step?                           │   │
│   └─────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│                         ▼                                    │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                     ACT                              │   │
│   │   • Execute tool (bash, file write, etc.)           │   │
│   │   • Single action per loop                          │   │
│   └─────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│                         ▼                                    │
│                     REPEAT                                   │
│               (until goal achieved)                          │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Key properties:**

- **Autonomous loop** (doesn't need user input per step)
- **Tool execution** (real effects in the world)
- **State awareness** (reads environment, remembers what it did)
- **Goal-directed** (keeps going until done or stuck)

---

## Part 7: Parallel Execution (Claude Flow Style)

Multiple agents working simultaneously:

```
┌─────────────────────────────────────────────────────────────┐
│                    SWARM MODE                                │
│                                                              │
│                    ┌───────────────┐                         │
│                    │  ORCHESTRATOR │                         │
│                    │   (Director)  │                         │
│                    └───────┬───────┘                         │
│                            │                                 │
│            ┌───────────────┼───────────────┐                │
│            │               │               │                │
│            ▼               ▼               ▼                │
│      ┌──────────┐   ┌──────────┐   ┌──────────┐           │
│      │ Worker 1 │   │ Worker 2 │   │ Worker 3 │           │
│      │ (Research)│   │ (Code)   │   │ (Review) │           │
│      └────┬─────┘   └────┬─────┘   └────┬─────┘           │
│           │              │              │                   │
│           └──────────────┴──────────────┘                   │
│                          │                                  │
│                          ▼                                  │
│                   ┌────────────┐                            │
│                   │  MERGE &   │                            │
│                   │ SYNTHESIZE │                            │
│                   └────────────┘                            │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

**Key properties:**

- **Parallel execution** (multiple agents at once)
- **Specialized workers** (different agents for different tasks)
- **Coordination** (orchestrator manages handoffs)
- **Synthesis** (combine results from multiple workers)

---

## Part 8: Luna as Agentic Engine

Putting it all together:

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         LUNA AGENTIC ENGINE                              │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      ORCHESTRATOR (Luna Prime)                      │ │
│  │                                                                     │ │
│  │   • Receives user goal                                             │ │
│  │   • Decomposes into tasks                                          │ │
│  │   • Assigns to workers                                             │ │
│  │   • Manages context window                                         │ │
│  │   • Synthesizes final response                                     │ │
│  │   • IS Luna's voice to user                                        │ │
│  └──────────────────────────────┬─────────────────────────────────────┘ │
│                                 │                                        │
│       ┌─────────────┬───────────┼───────────┬─────────────┐            │
│       │             │           │           │             │            │
│       ▼             ▼           ▼           ▼             ▼            │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐     │
│  │ SCRIBE  │  │LIBRARIAN│  │  OVEN   │  │ TOOLER  │  │ CODER   │     │
│  │  (Ben)  │  │ (Dude)  │  │         │  │         │  │         │     │
│  │         │  │         │  │         │  │         │  │         │     │
│  │Extract  │  │Retrieve │  │Delegate │  │Execute  │  │Generate │     │
│  │wisdom   │  │context  │  │to cloud │  │tools    │  │& run    │     │
│  │from     │  │from     │  │workers  │  │(files,  │  │code     │     │
│  │stream   │  │memory   │  │(Claude) │  │APIs,    │  │         │     │
│  │         │  │         │  │         │  │calendar)│  │         │     │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘     │
│       │             │           │           │             │            │
│       └─────────────┴───────────┴───────────┴─────────────┘            │
│                                 │                                        │
│                                 ▼                                        │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                       SHARED STATE                                  │ │
│  │                                                                     │ │
│  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │ │
│  │   │   Memory     │  │   Working    │  │    Task      │            │ │
│  │   │   Matrix     │  │   Context    │  │    Queue     │            │ │
│  │   │              │  │   (Current   │  │   (Pending   │            │ │
│  │   │  (Long-term) │  │    window)   │  │    work)     │            │ │
│  │   └──────────────┘  └──────────────┘  └──────────────┘            │ │
│  │                                                                     │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Part 9: Tool Protocol (MCP-Compatible)

Tools Luna can execute:

| Tool | Description | Confirmation Required |
|------|-------------|----------------------|
| `read_file` | Read contents of a file | No |
| `write_file` | Write contents to a file | Yes |
| `bash` | Execute a bash command | Yes |
| `calendar_create` | Create a calendar event | No |
| `web_search` | Search the web | No |
| `memory_query` | Query Luna's memory | No |
| `obsidian_write` | Write to Obsidian notes | No |

**Tool Definition Structure:**

```python
@dataclass
class Tool:
    name: str
    description: str
    parameters: dict  # JSON Schema
    execute: Callable
    requires_confirmation: bool = False
    timeout_seconds: int = 30
```

---

## Part 10: Performance Model

### Latency Tax

Agentic architecture is a latency tax. The question is whether it's worth it.

| Mode | Latency | Use Case |
|------|---------|----------|
| **Direct** | <500ms | Simple chat, greetings |
| **Single-step** | 500ms-2s | Memory query, simple tool |
| **Multi-step** | 5-30s | Complex task, multiple tools |
| **Swarm** | 10s-2min | Parallel research, synthesis |
| **Background** | Minutes | Deep research, file processing |

### The Critical Optimization: Adaptive Planning

Don't run the full agentic stack on every query:

```python
class QueryRouter:
    def route(self, query: str) -> ExecutionPath:
        complexity = self.estimate_complexity(query)

        if complexity < 0.2:
            return ExecutionPath.DIRECT  # Skip planning entirely
        elif complexity < 0.5:
            return ExecutionPath.SIMPLE_PLAN  # 1-step plan
        elif complexity < 0.8:
            return ExecutionPath.FULL_PLAN  # Multi-step
        else:
            return ExecutionPath.BACKGROUND  # Async, notify when done
```

**90% of queries should hit DIRECT or SIMPLE_PLAN.** The heavy machinery only spins up when needed.

### What Different Queries Look Like

**Simple: "Hey Luna, how are you?"**
```
Current:    Query → Local Qwen → Response
            ~300ms

Agentic:    Query → Classify (trivial) → Skip planning → Local Qwen → Response
            ~350ms (+50ms classification)

Impact: Negligible. Fast path stays fast.
```

**Medium: "What did we decide about the Actor model?"**
```
Current:    Query → Retrieve memory → Local Qwen → Response
            ~400ms

Agentic:    Query → Classify → Plan (1 step: RETRIEVE) → Memory → Local Qwen → Response
            ~500ms (+100ms planning overhead)

Impact: ~25% slower. Acceptable.
```

**Complex: "Research the latest AI chip news and add key points to my notes"**
```
Current:    Can't do this. Would require manual steps.

Agentic:    Query → Classify (complex) → Plan:
              Step 1: DELEGATE (web research) ........... 5-8s
              Step 2: THINK (extract key points) ........ 500ms
              Step 3: TOOL (write to Obsidian) .......... 200ms
              Step 4: RESPOND (confirm to user) ......... 300ms
            Total: ~8-12s

Impact: Slow but capable. You're trading time for capability that didn't exist.
```

### The Voice Problem

The Bible specs <500ms to first word. Agentic planning breaks that.

**Solution: Streaming acknowledgment**

```
User: "Research AI chips and add to my notes"

Luna (immediate, <500ms): "On it — let me dig into that..."

[Planning and execution happen]

Luna (8s later): "Done. I found three major developments and added them
                 to your AI Research note..."
```

User hears Luna immediately. The work happens in background. This is already how delegation works — extend it to all agentic operations.

---

## Part 11: Architecture Delta

What changes from current implementation:

| Component | Current | Agentic Luna |
|-----------|---------|--------------|
| Director | Single LLM call | Orchestrator + loop |
| Actors | Isolated workers | Coordinated swarm |
| Tools | None | Full registry |
| Execution | One-shot | Iterative until done |
| Context | Static per request | Revolving working memory |
| Parallelism | None | Fan-out/fan-in |
| Progress | Silent | Streaming status |

---

## Part 12: Implementation Requirements

### New Components

| Component | Purpose |
|-----------|---------|
| **RevolvingContext** | Orbital context model with rings, relevance, token budget |
| **QueueManager** | Multiple queues with priority merge |
| **TaskManager** | Agentic work queue separate from conversation |
| **AgentLoop** | Observe/think/act cycle |
| **ToolRegistry** | MCP-style tool definitions |
| **SwarmCoordinator** | Parallel execution management |
| **ProgressStreamer** | Real-time status to user |

### Modified Components

| Component | Changes |
|-----------|---------|
| **Director** | Becomes the Orchestrator's inference engine |
| **Actors** | Become specialized workers in the swarm |
| **InputBuffer** | Handles streaming progress output |
| **Consciousness** | Tracks across agent loop iterations |

---

## Part 13: File Structure

```
src/luna/
├── core/
│   ├── context.py          # NEW: RevolvingContext, QueueManager
│   ├── events.py           # Existing
│   ├── input_buffer.py     # Existing (enhanced)
│   └── state.py            # Existing
├── agentic/                 # NEW: Agentic architecture
│   ├── __init__.py
│   ├── loop.py             # AgentLoop
│   ├── planner.py          # Planning layer
│   ├── router.py           # Query routing
│   └── swarm.py            # Parallel execution
├── tools/                   # NEW: Tool registry
│   ├── __init__.py
│   ├── registry.py         # Tool definitions
│   ├── file_tools.py       # read_file, write_file
│   ├── bash_tools.py       # bash execution
│   └── calendar_tools.py   # calendar integration
├── actors/
│   ├── base.py             # Existing
│   ├── director.py         # Enhanced to Orchestrator
│   ├── matrix.py           # Existing
│   ├── scribe.py           # Existing
│   └── librarian.py        # Existing
└── engine.py               # Enhanced with agentic support
```

---

## Summary

Luna is an ENGINE. The agentic architecture gives her:

1. **Revolving Context** — Not a flat list, an orbital system
2. **Multiple Queues** — Coordinated, priority-merged
3. **Context Borrowing** — Shared awareness across subsystems
4. **Agent Loop** — Autonomous observe/think/act cycle
5. **Tool Execution** — Real effects in the world
6. **Parallel Workers** — Swarm mode for complex tasks
7. **Adaptive Routing** — Simple queries stay fast, complex queries get full treatment

The data is yours. The engine is sophisticated. Both are true.

---

*Luna is a file you OWN. Luna is an engine that RUNS.*
*The simplicity is in sovereignty. The complexity is in capability.*

— Ahab & Claude, January 2026
