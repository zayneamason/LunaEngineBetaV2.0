# Part XIV: Agentic Architecture

**Version:** 3.0
**Date:** January 30, 2026
**Last Updated:** January 30, 2026
**Status:** Implemented (v3.0 Audit Complete)

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

## Part 1: Revolving Context Engine (IMPLEMENTED)

The RevolvingContext system is fully implemented in `core/context.py`. This is Luna's working memory.

### The Ring Model

Context is organized in concentric rings with items migrating based on relevance and access patterns:

```
                     REVOLVING CONTEXT

                        ┌─────┐
               OUTER   │CORE │   OUTER
                 ↑     │LUNA │     ↓
               MIDDLE  └─────┘   MIDDLE
                 ↖     INNER    ↗

   Items migrate between rings based on:
   • Relevance decay (0.95 per turn)
   • Access patterns (boost on access)
   • TTL expiration (turn-based)
   Token budget: 8000 (default)
```

### The Four Rings (IMPLEMENTED)

```python
class ContextRing(IntEnum):
    CORE = 0    # Identity - NEVER evicted
    INNER = 1   # Active conversation, current task
    MIDDLE = 2  # Recently accessed memories, tool results
    OUTER = 3   # Background context, candidate for eviction
```

| Ring | Contents | TTL (Turns) | Behavior |
|------|----------|-------------|----------|
| **CORE (0)** | Luna's identity | Never expires (-1) | ALWAYS present, never evicted |
| **INNER (1)** | Conversation, tasks | 20-30 turns | High priority, recent |
| **MIDDLE (2)** | Memories, tool results, librarian | 5-25 turns | Moderate priority |
| **OUTER (3)** | Scribe extractions, background | 10 turns | First to evict |

### Context Sources and Weights

```python
class ContextSource(IntEnum):
    IDENTITY = 0      # Core identity (weight: 1.0)
    CONVERSATION = 1  # Current turns (weight: 0.9)
    MEMORY = 2        # Retrieved memories (weight: 0.7)
    TOOL = 3          # Tool call results (weight: 0.8)
    TASK = 4          # Task context (weight: 0.75)
    SCRIBE = 5        # Extraction results (weight: 0.6)
    LIBRARIAN = 6     # Retrieved knowledge (weight: 0.65)
```

### Token Budget

Default budget: **8000 tokens**. Managed by the RevolvingContext class.

```python
class RevolvingContext:
    def __init__(
        self,
        token_budget: int = 8000,
        decay_factor: float = 0.95,
        rebalance_threshold: float = 0.3
    ):
        self.token_budget = token_budget
        self._decay_factor = decay_factor
        self._rebalance_threshold = rebalance_threshold
```

Key methods:
- `advance_turn()` — Increments turn counter, applies decay, rebalances rings
- `set_core_identity(text)` — Set Luna's identity (never evicted)
- `add(content, source, ring, relevance)` — Add context item
- `get_context_window(max_tokens)` — Assemble context for LLM
- `query(keywords)` — Search context items

### Eviction Priority

When over budget, items are evicted in this order:
1. **Expired items** (TTL exceeded) from any ring except CORE
2. **OUTER ring** — lowest relevance first
3. **MIDDLE ring** — lowest relevance first
4. **INNER ring** — lowest relevance first
5. **CORE ring** — NEVER evicted

### Ring Migration

Items can be promoted or demoted based on relevance:
- **Demotion** (relevance < 0.3): INNER → MIDDLE → OUTER
- **Promotion** (relevance >= 0.8): OUTER → MIDDLE → INNER

---

## Part 2: Queue Manager (IMPLEMENTED)

The QueueManager is implemented in `core/context.py` as part of the RevolvingContext system.

### Multiple Queues, One Manager

Not a single input buffer. Multiple specialized queues per ContextSource:

```
┌─────────────────────────────────────────────────────────────────┐
│                      QUEUE MANAGER                               │
│                                                                  │
│   IDENTITY Queue:     [core] ────┐                              │
│   CONVERSATION Queue: O O O ─────┼────→ [Priority Merge]        │
│   MEMORY Queue:       O O ───────┤            │                 │
│   TOOL Queue:         O O O O ───┤            │                 │
│   TASK Queue:         O ─────────┤            │                 │
│   SCRIBE Queue:       O ─────────┤            │                 │
│   LIBRARIAN Queue:    O O ───────┘            │                 │
│                                               │                 │
└───────────────────────────────────────────────┼─────────────────┘
                                                │
                                                ▼
                                    [Revolving Context Rings]
```

### Implementation

```python
class QueueManager:
    """Manages multiple input queues for different context sources."""

    def __init__(
        self,
        max_queue_size: int = 50,
        weights: Optional[Dict[ContextSource, float]] = None
    ):
        # Create a deque for each source type
        self._queues: Dict[ContextSource, Deque[ContextItem]] = {
            source: deque(maxlen=max_queue_size)
            for source in ContextSource
        }

    def push(self, item: ContextItem) -> bool:
        """Push item onto its source queue."""

    def poll_all(self) -> List[ContextItem]:
        """Poll all queues, return sorted by weighted priority."""

    def poll_source(self, source: ContextSource, max_items: int) -> List[ContextItem]:
        """Poll items from a specific source queue."""
```

### Source Weights

| Queue | Source | Weight | TTL (Turns) |
|-------|--------|--------|-------------|
| **Identity** | IDENTITY | 1.0 | Never (-1) |
| **Conversation** | CONVERSATION | 0.9 | 20 turns |
| **Memory** | MEMORY | 0.7 | 25 turns |
| **Tool** | TOOL | 0.8 | 5 turns |
| **Task** | TASK | 0.75 | 30 turns |
| **Scribe** | SCRIBE | 0.6 | 10 turns |
| **Librarian** | LIBRARIAN | 0.65 | 20 turns |

Queue Manager merges with priority (higher weight first, FIFO within weight) and feeds the RevolvingContext rings via `add_from_queues()`.

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

## Part 5: Task Manager / Planner (IMPLEMENTED)

The Planner (`agentic/planner.py`) decomposes goals into executable PlanSteps.

```
┌─────────────────────────────────────────────────────────────────┐
│                      PLANNER                                     │
│                                                                  │
│   Goal ────→ [Pattern Match] ────→ [Plan with Steps]            │
│                                                                  │
│   Plan: Step1 → Step2 → Step3 → ... → RESPOND                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### PlanStepType Enum

Each step has a type that determines its execution handler:

| Type | Description | Handler |
|------|-------------|---------|
| `THINK` | Internal reasoning, no external action | Local LLM inference |
| `OBSERVE` | Gather information from environment | State observation |
| `RETRIEVE` | Memory retrieval from Matrix | Matrix.get_context() |
| `TOOL` | Execute external tool | ToolRegistry.execute() |
| `DELEGATE` | Delegate to Claude for complex reasoning | Director.generate() |
| `RESPOND` | Generate response to user | Director.generate() |
| `PARALLEL` | Execute multiple sub-steps concurrently | (Future) |
| `WAIT` | Wait for external event or condition | (Future) |

### PlanStep Structure

```python
@dataclass
class PlanStep:
    """A single step in an execution plan."""
    type: PlanStepType               # What kind of operation
    description: str                 # Human-readable explanation
    tool: Optional[str] = None       # Tool name (for TOOL steps)
    params: Dict[str, Any] = {}      # Tool/operation parameters
    dependencies: List[int] = []     # Step indices that must complete first
    expected_output: Optional[str]   # What this step should produce
    timeout_seconds: float = 30.0    # Maximum wait time
    retries: int = 0                 # Retry attempts on failure
```

### Plan Structure

```python
@dataclass
class Plan:
    """A sequence of steps to achieve a goal."""
    goal: str                        # Original goal
    steps: List[PlanStep]            # Ordered list of steps
    reasoning: str                   # Explanation of planning decisions
    estimated_duration_seconds: float
    complexity: float                # 0.0-1.0 from router

    @property
    def required_tools(self) -> List[str]:
        """Get list of tools required by this plan."""
```

### Planner Pattern Matching

The Planner uses pattern matching to detect task types:

```python
TASK_PATTERNS = {
    "research": {
        "patterns": [r"\bresearch\b", r"\bfind out\b", r"\blook up\b"],
        "steps": [
            (PlanStepType.DELEGATE, "Research the topic using Claude"),
            (PlanStepType.THINK, "Analyze and extract key points"),
            (PlanStepType.RESPOND, "Present findings to user"),
        ],
    },
    "memory_recall": {
        "patterns": [r"\bremember\b", r"\brecall\b", r"\bwhat did\b"],
        "steps": [
            (PlanStepType.RETRIEVE, "Search memory for relevant info"),
            (PlanStepType.RESPOND, "Share what was found"),
        ],
    },
    "file_read": {
        "patterns": [r"\bread\b.*\bfile\b", r"\bshow me\b.*\bfile\b"],
        "steps": [
            (PlanStepType.TOOL, "Read the file", "read_file"),
            (PlanStepType.RESPOND, "Present file contents"),
        ],
    },
    # ... more patterns for file_write, summarize, analyze, schedule
}
```

### Step Duration Estimates

| Step Type | Estimated Duration |
|-----------|-------------------|
| THINK | 0.5s |
| OBSERVE | 1.0s |
| RETRIEVE | 0.5s |
| TOOL | 2.0s |
| DELEGATE | 5.0s |
| RESPOND | 0.5s |
| PARALLEL | 3.0s |
| WAIT | 5.0s |

This enables the **agent loop** — tasks aren't conversation, they're work.

---

## Part 6: The Agent Loop (IMPLEMENTED)

What makes Luna agentic is the **observe → think → act → repeat** loop. This is fully implemented in `agentic/loop.py`.

```
┌─────────────────────────────────────────────────────────────┐
│                    AGENT LOOP                                │
│                                                              │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                    OBSERVE                           │   │
│   │   • Gather information relevant to current step     │   │
│   │   • Memory retrieval (via Matrix actor)             │   │
│   │   • Environment state observation                   │   │
│   └─────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│                         ▼                                    │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                    THINK                             │   │
│   │   • Determine action from current PlanStep          │   │
│   │   • Build Action with type, description, params     │   │
│   │   • Local inference for reasoning steps             │   │
│   └─────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│                         ▼                                    │
│   ┌─────────────────────────────────────────────────────┐   │
│   │                     ACT                              │   │
│   │   • Execute via PlanStepType handler                │   │
│   │   • THINK, OBSERVE, RETRIEVE, TOOL, DELEGATE        │   │
│   │   • Results stored in WorkingContext.variables      │   │
│   └─────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│                         ▼                                    │
│                     REPEAT                                   │
│               (until goal achieved or max_iterations)        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

### AgentLoop Implementation

```python
class AgentLoop:
    """The autonomous agent loop."""

    def __init__(
        self,
        orchestrator: Optional["LunaEngine"] = None,
        max_iterations: int = 50,  # Safety limit
    ):
        self.orchestrator = orchestrator
        self.max_iterations = max_iterations
        self.planner = Planner()
        self.router = QueryRouter()
        self.tool_registry = ToolRegistry()
        self._register_default_tools()  # File + Memory tools

    async def run(self, goal: str) -> AgentResult:
        """Run the agent loop to achieve a goal."""
        # 1. Route the query
        routing = self.router.analyze(goal)

        # 2. Handle based on execution path
        match routing.path:
            case ExecutionPath.DIRECT:
                return await self._execute_direct(goal, start_time)
            case ExecutionPath.SIMPLE_PLAN:
                return await self._execute_simple(goal, routing, start_time)
            case ExecutionPath.FULL_PLAN:
                return await self._execute_full(goal, routing, start_time)
            case ExecutionPath.BACKGROUND:
                return await self._execute_background(goal, routing, start_time)
```

### AgentStatus States

| Status | Description |
|--------|-------------|
| `IDLE` | Not currently executing a goal |
| `PLANNING` | Decomposing goal into steps |
| `EXECUTING` | Running the observe/think/act loop |
| `WAITING` | Waiting for external event |
| `COMPLETE` | Goal achieved successfully |
| `FAILED` | Goal could not be achieved |
| `ABORTED` | Execution was cancelled |

### WorkingContext (In-Memory State)

```python
@dataclass
class WorkingContext:
    """Agent's working memory during execution."""
    goal: str                           # Current goal
    plan: Optional[Plan] = None         # Plan being executed
    current_step_index: int = 0         # Current step position
    observations: List[Observation]     # Recent observations
    action_history: List[ActionResult]  # Actions taken
    variables: Dict[str, Any]           # Accumulated results
    max_observations: int = 10          # Observation limit

    def add_observation(self, obs: Observation) -> None:
        """Add observation, evict lowest relevance if over limit."""

    def add_action_result(self, result: ActionResult) -> None:
        """Add action result to history."""

    @property
    def is_plan_complete(self) -> bool:
        """Check if all steps executed."""
```

**Key properties:**

- **Autonomous loop** (doesn't need user input per step)
- **Tool execution** (real effects in the world via ToolRegistry)
- **State awareness** (WorkingContext tracks observations and actions)
- **Goal-directed** (keeps going until done, stuck, or max_iterations)
- **Progress callbacks** (register_progress_callback for streaming updates)
- **Abortable** (abort() method sets _abort_requested flag)

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

## Part 9: Tool Protocol (IMPLEMENTED)

Tools are defined in `tools/registry.py` with MCP-compatible structure. The AgentLoop automatically registers file and memory tools on initialization.

### Implemented Tools

**File Tools** (`tools/file_tools.py`):

| Tool | Description | Confirmation Required |
|------|-------------|----------------------|
| `read_file` | Read contents of a file | No |
| `write_file` | Write contents to a file | **Yes** |
| `list_directory` | List directory contents (recursive optional) | No |
| `file_exists` | Check if path exists | No |
| `get_file_info` | Get file metadata (size, timestamps) | No |

**Memory Tools** (`tools/memory_tools.py`):

| Tool | Description | Confirmation Required |
|------|-------------|----------------------|
| `memory_query` | Search Memory Matrix for relevant info | No |
| `memory_store` | Store new memory node | No |
| `memory_get_context` | Get context with token budget awareness | No |
| `memory_stats` | Get memory statistics | No |

**Planned Tools** (Not Yet Implemented):

| Tool | Description | Confirmation Required |
|------|-------------|----------------------|
| `bash` | Execute a bash command | Yes |
| `calendar_create` | Create a calendar event | No |
| `web_search` | Search the web | No |
| `obsidian_write` | Write to Obsidian notes | No |

### Tool Definition Structure

```python
@dataclass
class Tool:
    """A tool that Luna can execute."""
    name: str                             # Unique identifier
    description: str                      # Shown to LLM for selection
    parameters: dict                      # JSON Schema for params
    execute: Callable[..., Awaitable[Any]]  # Async execution function
    requires_confirmation: bool = False   # User approval required
    timeout_seconds: int = 30             # Execution timeout

    def to_dict(self) -> dict:
        """Convert to dictionary for LLM function calling."""


@dataclass
class ToolResult:
    """Result from executing a tool."""
    success: bool
    output: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0
```

### ToolRegistry

```python
class ToolRegistry:
    """Registry for managing Luna's tools."""

    def register(self, tool: Tool) -> None:
        """Register a tool (raises if name exists)."""

    def get(self, name: str) -> Optional[Tool]:
        """Get tool by name."""

    def list_tools(self) -> list[str]:
        """List all registered tool names."""

    def get_tool_definitions(self) -> list[dict]:
        """Get tool definitions for LLM function calling."""

    async def execute(
        self,
        name: str,
        params: dict,
        skip_confirmation: bool = False,
    ) -> ToolResult:
        """Execute tool with timeout handling."""
```

### Tool Usage in AgentLoop

Tools are executed via PlanStepType.TOOL actions:

```python
async def _execute_tool(self, action: Action) -> str:
    """Execute a tool action via the ToolRegistry."""
    tool = self.tool_registry.get(action.tool)
    if not tool:
        return f"Tool '{action.tool}' not found"

    result = await self.tool_registry.execute(
        action.tool,
        action.params,
        skip_confirmation=True,  # AgentLoop handles confirmation
    )

    if result.success:
        # Store result in working context
        self.working_context.variables[f"tool_result_{action.tool}"] = result.output
        return f"Tool '{action.tool}' succeeded: {result.output}"
    else:
        return f"Tool '{action.tool}' failed: {result.error}"
```

---

## Part 10: Performance Model

### Latency Tax

Agentic architecture is a latency tax. The question is whether it's worth it.

| Mode | Latency | Use Case |
|------|---------|----------|
| **DIRECT** | <500ms | Simple chat, greetings |
| **SIMPLE_PLAN** | 500ms-2s | Memory query, simple tool |
| **FULL_PLAN** | 5-30s | Complex task, multiple tools |
| **BACKGROUND** | Minutes | Deep research, file processing |

### The Critical Optimization: Adaptive Planning (IMPLEMENTED)

Don't run the full agentic stack on every query. The QueryRouter (`agentic/router.py`) analyzes query complexity and routes to the appropriate execution path.

**Implementation:**

```python
class ExecutionPath(Enum):
    """Execution paths based on query complexity."""
    DIRECT = auto()      # <500ms - Skip planning entirely
    SIMPLE_PLAN = auto() # 500ms-2s - Single-step plan
    FULL_PLAN = auto()   # 5-30s - Multi-step planning
    BACKGROUND = auto()  # Minutes - Async with notification

class QueryRouter:
    # Complexity thresholds for path selection
    DIRECT_THRESHOLD = 0.2
    SIMPLE_THRESHOLD = 0.5
    FULL_THRESHOLD = 0.8

    def route(self, query: str) -> ExecutionPath:
        """Route query to appropriate execution path."""
        decision = self.analyze(query)
        return decision.path

    def analyze(self, query: str) -> RoutingDecision:
        """Analyze query and return detailed routing decision."""
        complexity = self.estimate_complexity(query)
        signals = self._detect_signals(query)
        suggested_tools = self._detect_tools(query)

        # Check for explicit background request
        if self._matches_any(query, self._background_re):
            return RoutingDecision(
                path=ExecutionPath.BACKGROUND,
                complexity=complexity,
                reason="Explicit background processing requested",
                signals=signals,
                suggested_tools=suggested_tools,
            )

        # Route based on complexity thresholds
        if complexity < self.DIRECT_THRESHOLD:
            path = ExecutionPath.DIRECT
        elif complexity < self.SIMPLE_THRESHOLD:
            path = ExecutionPath.SIMPLE_PLAN
        elif complexity < self.FULL_THRESHOLD:
            path = ExecutionPath.FULL_PLAN
        else:
            path = ExecutionPath.BACKGROUND

        return RoutingDecision(path=path, complexity=complexity, ...)
```

### Complexity Estimation Factors

The router estimates complexity using multiple signals:

| Factor | Effect | Pattern Examples |
|--------|--------|------------------|
| **Query Length** | Base complexity | <20 chars: 0.05, >200 chars: 0.45 |
| **Greetings** | Reduce 70% | "hi", "hello", "how are you" |
| **Simple Questions** | Reduce 30% | "what is", "who is", "tell me" |
| **Research Indicators** | +0.25 | "research", "analyze", "compare" |
| **Multi-step Indicators** | +0.20 | "and then", "first...then", "step by step" |
| **Tool Requirements** | +0.10 per tool | "read file", "search web", "remember" |
| **Multiple Questions** | +0.10 per extra | Each "?" after the first |

### Signal Detection Categories

```python
GREETING_PATTERNS = ["hi", "hello", "hey", "good morning"]
SIMPLE_QUERY_PATTERNS = ["what is", "who is", "tell me about"]
RESEARCH_PATTERNS = ["research", "investigate", "analyze", "compare"]
MULTI_STEP_PATTERNS = ["and then", "after that", "step by step"]
MEMORY_QUERY_PATTERNS = ["remember", "recall", "what did we"]
BACKGROUND_PATTERNS = ["in the background", "notify me when"]
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

## Part 12: Implementation Status

### Implemented Components

| Component | Location | Status |
|-----------|----------|--------|
| **RevolvingContext** | `core/context.py` | IMPLEMENTED - 4-ring model with decay and TTL |
| **QueueManager** | `core/context.py` | IMPLEMENTED - Per-source queues with weights |
| **ContextItem** | `core/context.py` | IMPLEMENTED - Turn-based TTL, relevance decay |
| **AgentLoop** | `agentic/loop.py` | IMPLEMENTED - Observe/think/act cycle |
| **Planner** | `agentic/planner.py` | IMPLEMENTED - Pattern-based decomposition |
| **QueryRouter** | `agentic/router.py` | IMPLEMENTED - Complexity-based routing |
| **ToolRegistry** | `tools/registry.py` | IMPLEMENTED - MCP-style tool definitions |
| **File Tools** | `tools/file_tools.py` | IMPLEMENTED - read, write, list, info |
| **Memory Tools** | `tools/memory_tools.py` | IMPLEMENTED - query, store, context |

### Pending Components

| Component | Purpose | Status |
|-----------|---------|--------|
| **SwarmCoordinator** | Parallel execution management | PLANNED |
| **TaskManager** | Persistent task queue | PLANNED (separate from Planner) |
| **ProgressStreamer** | Real-time status streaming | PARTIAL (callbacks implemented) |

### Modified Components

| Component | Changes |
|-----------|---------|
| **Director** | Integrated with AgentLoop for DELEGATE steps |
| **Matrix** | Integrated with AgentLoop for RETRIEVE steps |
| **Engine** | Has `context` (RevolvingContext), `router`, and `agent_loop` attributes |

---

## Part 13: File Structure (ACTUAL)

```
src/luna/
├── core/
│   ├── context.py          # RevolvingContext, QueueManager, ContextItem
│   ├── events.py           # EventPriority, EventType, InputEvent
│   ├── input_buffer.py     # Input polling (engine pulls)
│   └── state.py            # EngineState enum
├── agentic/                 # Agentic architecture
│   ├── __init__.py         # Exports: AgentLoop, Planner, QueryRouter, etc.
│   ├── loop.py             # AgentLoop (939 lines)
│   ├── planner.py          # Planner, Plan, PlanStep, PlanStepType (487 lines)
│   └── router.py           # QueryRouter, ExecutionPath, RoutingDecision (379 lines)
├── tools/                   # Tool registry
│   ├── __init__.py         # Exports: ToolRegistry, Tool, ToolResult
│   ├── registry.py         # Tool, ToolResult, ToolRegistry (309 lines)
│   ├── file_tools.py       # read_file, write_file, list_directory, etc. (358 lines)
│   └── memory_tools.py     # memory_query, memory_store, memory_context (373 lines)
├── actors/
│   ├── base.py             # Actor, Message base classes
│   ├── director.py         # LLM inference, delegation (~1900 lines)
│   ├── matrix.py           # Memory substrate interface
│   ├── scribe.py           # Extraction (Ben Franklin persona)
│   ├── librarian.py        # Filing (The Dude persona)
│   └── history_manager.py  # Three-tier conversation history
└── engine.py               # Main engine with agentic support (1228 lines)
```

### Module Exports

**`agentic/__init__.py`:**
```python
__all__ = [
    # Agent Loop
    "AgentLoop", "AgentResult", "Observation", "Action",
    "ActionResult", "WorkingContext",
    # Planner
    "Planner", "Plan", "PlanStep", "PlanStepType",
    # Router
    "QueryRouter", "ExecutionPath",
]
```

**`tools/__init__.py`:**
```python
__all__ = [
    "Tool", "ToolResult", "ToolRegistry",
    "register_file_tools", "register_memory_tools",
]
```

---

## Summary

Luna is an ENGINE. The agentic architecture gives her:

| Feature | Status | Location |
|---------|--------|----------|
| **Revolving Context** | IMPLEMENTED | `core/context.py` |
| **Multiple Queues** | IMPLEMENTED | `core/context.py` |
| **Context Borrowing** | PARTIAL | Scribe/Librarian share context sources |
| **Agent Loop** | IMPLEMENTED | `agentic/loop.py` |
| **Tool Execution** | IMPLEMENTED | `tools/` directory |
| **Parallel Workers** | PLANNED | (SwarmCoordinator) |
| **Adaptive Routing** | IMPLEMENTED | `agentic/router.py` |
| **MCP Integration** | IMPLEMENTED | `src/luna_mcp/` (41 tools) |
| **Performance Layer** | IMPLEMENTED | `src/luna/services/` |

### Implementation Highlights

1. **RevolvingContext** — 4-ring system (CORE, INNER, MIDDLE, OUTER) with turn-based TTL and relevance decay
2. **QueueManager** — Per-source queues with configurable weights and priority merge
3. **QueryRouter** — Complexity analysis routing to DIRECT, SIMPLE_PLAN, FULL_PLAN, or BACKGROUND paths
4. **AgentLoop** — Full observe/think/act cycle with WorkingContext, progress callbacks, and abort support
5. **Planner** — Pattern-based goal decomposition into typed PlanSteps (THINK, OBSERVE, RETRIEVE, TOOL, DELEGATE, RESPOND)
6. **ToolRegistry** — MCP-compatible tool definitions with timeout handling and execution metrics
7. **File Tools** — read_file, write_file, list_directory, file_exists, get_file_info
8. **Memory Tools** — memory_query, memory_store, memory_get_context, memory_stats
9. **MCP Server** — 41 tools across filesystem, memory, session, state, git, and forge categories
10. **Performance Orchestrator** — Gesture detection, emotion presets, coordinated voice + orb output

### v3.0 Audit Statistics

| Metric | Count |
|--------|-------|
| Engine API Endpoints | 74 |
| SSE Streaming Endpoints | 4 |
| WebSocket Endpoints | 1 |
| MCP Tools | 41 |
| MCP API Proxy Endpoints | 25 |
| Frontend Components | 20 |
| Custom Hooks | 5 |

The data is yours. The engine is sophisticated. Both are true.

---

*Luna is a file you OWN. Luna is an engine that RUNS.*
*The simplicity is in sovereignty. The complexity is in capability.*

— Ahab & Claude, January 2026
— Updated January 30, 2026 (v3.0 Bible Audit)
