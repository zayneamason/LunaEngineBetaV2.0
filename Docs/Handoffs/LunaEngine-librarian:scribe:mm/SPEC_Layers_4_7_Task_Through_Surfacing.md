# SPEC: Layers 4–7 — Task Ledger Through Proactive Surfacing

## Luna Flow State Architecture

**Layers:** 4, 5, 6, 7
**Depends on:** Layers 2-3 (Flow Awareness + Thread Management)
**Related:** Observatory Navigation Bus (frontend wiring)

---

## The Stack (Full Picture)

```
Layer 1 ✅  Pipeline fix — every turn reaches Ben in real-time
Layer 2     Flow Awareness — Ben detects FLOW/RECALIBRATION/AMEND
Layer 3     Thread Management — Dude creates/parks/resumes threads
Layer 4     Task Ledger — ACTION→OUTCOME tracking with proper node IDs  ← THIS DOC
Layer 5     Context Threading — pipeline pulls thread context on retrieve ← THIS DOC
Layer 6     Consciousness Wiring — threads feed attention state           ← THIS DOC
Layer 7     Proactive Surfacing — Luna volunteers parked thread context   ← THIS DOC
```

Each layer is a clean increment. Test each before building the next.

---

# LAYER 4: Task Ledger

**Owner:** Librarian (The Dude)
**Depends on:** Layer 3 (threads exist, open_tasks tracked by content hash)
**Problem:** Layer 3 tracks open tasks by content hash — a placeholder. Layer 4 replaces this with proper Matrix node IDs, enabling cross-session ACTION→OUTCOME resolution.

## What Changes

Layer 3's `Thread.open_tasks` stores `action:{content_hash}` strings. This works for same-session tracking but breaks across sessions because the hash has no persistence in the Matrix.

Layer 4 makes the Librarian track the actual Matrix node IDs of ACTION extractions, and detect when OUTCOME extractions resolve them by entity overlap.

### Modified: Thread.open_tasks

```python
# Layer 3 (current):
open_tasks: list[str]  # ["action:0a1b2c3d", ...]

# Layer 4 (upgraded):
open_tasks: list[str]  # ["n_abc123", "n_def456", ...] — actual Matrix node IDs
```

### Modified: FilingResult

```python
@dataclass
class FilingResult:
    nodes_created: list[str]  # existing
    nodes_merged: list[tuple[str, str]]  # existing
    edges_created: list[str]  # existing
    edges_skipped: list[str]  # existing
    filing_time_ms: int = 0  # existing

    # NEW — for task tracking
    action_node_ids: list[str] = field(default_factory=list)  # IDs of ACTION nodes filed
    outcome_node_ids: list[str] = field(default_factory=list)  # IDs of OUTCOME nodes filed
```

### Modified: _handle_flow_continue()

```python
# After filing, we now have real node IDs from FilingResult
for action_id in filing_result.action_node_ids:
    if action_id not in self._active_thread.open_tasks:
        self._active_thread.open_tasks.append(action_id)
        # Create edge: THREAD --[HAS_OPEN_TASK]--> ACTION node
        await self._create_edge(
            from_id=self._active_thread.id,
            to_id=action_id,
            edge_type="HAS_OPEN_TASK",
            confidence=1.0,
        )
```

### New: _resolve_open_tasks()

```python
async def _resolve_open_tasks(
    self,
    outcome: ExtractedObject,
    outcome_node_id: str,
    thread: Thread,
) -> list[str]:
    """
    Check if an OUTCOME resolves any open ACTION tasks.
    
    Resolution heuristic:
    1. Get entities of the OUTCOME
    2. For each open task, get the ACTION node's entities
    3. If entity overlap >= 0.5 (Jaccard), consider resolved
    4. Create OUTCOME --[RESOLVES]--> ACTION edge
    5. Remove from thread.open_tasks
    
    Returns list of resolved task node IDs.
    """
    if not thread.open_tasks:
        return []
    
    outcome_entities = set(e.lower() for e in outcome.entities)
    if not outcome_entities:
        return []
    
    resolved = []
    matrix = await self._get_matrix()
    
    for task_id in thread.open_tasks:
        # Fetch ACTION node from Matrix
        action_node = await matrix.get_node(task_id)
        if not action_node:
            continue
        
        # Get ACTION's entities (from tags or linked entity nodes)
        action_entities = set()
        action_edges = await matrix.get_edges_from(task_id)
        for edge in action_edges:
            if edge.relationship in ("INVOLVES", "mentions"):
                target = await matrix.get_node(edge.to_id)
                if target:
                    action_entities.add(target.content.lower())
        
        if not action_entities:
            continue
        
        # Jaccard overlap
        overlap = len(outcome_entities & action_entities) / len(outcome_entities | action_entities)
        
        if overlap >= 0.5:
            # Resolved! Create edge and remove from open tasks
            await self._create_edge(
                from_id=outcome_node_id,
                to_id=task_id,
                edge_type="RESOLVES",
                confidence=overlap,
            )
            resolved.append(task_id)
            logger.info(
                f"The Dude: OUTCOME resolves ACTION {task_id} "
                f"(overlap={overlap:.2f})"
            )
    
    # Remove resolved tasks
    for task_id in resolved:
        thread.open_tasks.remove(task_id)
    
    # Update thread node
    if resolved:
        await self._update_thread_node(thread)
    
    return resolved
```

### Quest Generation Bridge

When Observatory runs a maintenance sweep, it should now also scan for:
- THREAD nodes with status=parked that have non-empty open_tasks
- Generate quests like "Continue: {thread.topic}" with objective listing the open ACTIONs

This connects Layer 4 to Observatory's quest system without any new infrastructure — just an additional query in the sweep logic.

### Files Modified

| File | Change |
|------|--------|
| `src/luna/extraction/types.py` | Add action_node_ids/outcome_node_ids to FilingResult |
| `src/luna/actors/librarian.py` | Real node ID tracking, _resolve_open_tasks(), HAS_OPEN_TASK edges |
| Observatory backend `maintenance_sweep` | Add parked-thread-to-quest generation |
| `tests/test_task_ledger.py` | New — ACTION→OUTCOME resolution, cross-session persistence |

### Done When

1. Thread.open_tasks contains real Matrix node IDs (not content hashes)
2. OUTCOME extractions resolve matching ACTIONs by entity overlap
3. RESOLVES edges appear in the graph between OUTCOME→ACTION nodes
4. Resolved tasks removed from thread.open_tasks
5. Observatory sweep generates quests from parked threads with open tasks
6. Task resolution works across sessions (IDs persist in Matrix)

---

# LAYER 5: Context Threading

**Owner:** Context Pipeline (`src/luna/context/pipeline.py`)
**Depends on:** Layer 3 (threads exist), Layer 4 (open tasks have real IDs)
**Problem:** The context pipeline builds prompts from ring buffer + entity detection + retrieval. It has no awareness of threads. Luna can't say "we were discussing X" because the pipeline doesn't know about conversational continuity.

## What Changes

The pipeline gains a new context section: **ACTIVE THREADS**. When building context, it queries the Librarian for the active thread and any relevant parked threads, then includes them in the system prompt.

### Modified: ContextPipeline.__init__()

```python
def __init__(self, db, max_ring_turns=6, base_personality=""):
    # ... existing init ...
    self._librarian = None  # Set via set_librarian()

def set_librarian(self, librarian) -> None:
    """Connect to Librarian for thread context."""
    self._librarian = librarian
```

### Modified: ContextPipeline.build()

```python
async def build(self, message: str, session_id: str = "default") -> ContextPacket:
    # ... existing steps 1-4 ...
    
    # NEW: 4.5 — Get thread context from Librarian
    thread_context = ""
    if self._librarian:
        thread_context = await self._get_thread_context()
    
    # 5. Build system prompt (modified to include thread context)
    system_prompt = self._build_system_prompt(
        ring_history=self._ring.format_for_prompt(),
        entities=entities,
        retrieved_context=retrieved_context,
        thread_context=thread_context,  # NEW
    )
    
    # ... rest unchanged ...
```

### New: _get_thread_context()

```python
async def _get_thread_context(self) -> str:
    """
    Get thread context from Librarian.
    
    Returns formatted string describing:
    - Active thread (if any): topic, entity count, open tasks
    - Recently parked threads (top 3): topic, when parked, open tasks
    - Project context (if active): project slug, parked threads for project
    """
    sections = []
    
    # Active thread
    active = self._librarian._active_thread
    if active:
        parts = [f"Currently focused on: {active.topic}"]
        if active.open_tasks:
            parts.append(f"Open tasks: {len(active.open_tasks)}")
        if active.project_slug:
            parts.append(f"Project: {active.project_slug}")
        sections.append(" | ".join(parts))
    
    # Recently parked threads (with open tasks)
    parked_with_tasks = [
        t for t in self._librarian._thread_cache.values()
        if t.status.value == "parked" and t.open_tasks
    ]
    # Sort by most recently parked
    parked_with_tasks.sort(
        key=lambda t: t.parked_at or t.started_at,
        reverse=True,
    )
    
    if parked_with_tasks[:3]:
        for thread in parked_with_tasks[:3]:
            age = ""
            if thread.parked_at:
                from datetime import datetime
                delta = datetime.now() - thread.parked_at
                if delta.days > 0:
                    age = f" ({delta.days}d ago)"
                elif delta.seconds > 3600:
                    age = f" ({delta.seconds // 3600}h ago)"
                else:
                    age = f" (recently)"
            
            sections.append(
                f"Parked thread: \"{thread.topic}\"{age} — "
                f"{len(thread.open_tasks)} open task(s)"
            )
    
    if not sections:
        return ""
    
    return "\n".join(sections)
```

### Modified: _build_system_prompt()

Add thread context as a new section between THIS SESSION and KNOWN PEOPLE:

```python
def _build_system_prompt(self, ring_history, entities, retrieved_context, thread_context=""):
    sections = []
    
    sections.append(self._base_personality)
    
    # THIS SESSION
    sections.append("## THIS SESSION\n" + ring_history)
    
    # THREAD CONTEXT — NEW
    if thread_context:
        sections.append("""
## CONVERSATIONAL THREADS
These are your ongoing threads of attention. You can reference them naturally.
""")
        sections.append(thread_context)
    
    # KNOWN PEOPLE
    # ... existing entity section ...
    
    # RETRIEVED CONTEXT
    # ... existing retrieval section ...
    
    return "\n".join(sections)
```

### Modified: ContextPacket

```python
@dataclass
class ContextPacket:
    # ... existing fields ...
    
    # NEW
    active_thread_topic: Optional[str] = None
    parked_thread_count: int = 0
    has_open_tasks: bool = False
```

### Wiring: Engine → Pipeline → Librarian

In `engine.py` or wherever the pipeline is instantiated:

```python
# After creating both pipeline and librarian:
pipeline.set_librarian(librarian)
```

### Files Modified

| File | Change |
|------|--------|
| `src/luna/context/pipeline.py` | Thread context retrieval, new prompt section, librarian reference |
| `src/luna/engine.py` | Wire pipeline.set_librarian() |
| `tests/test_context_threading.py` | New — thread context in prompts, parked thread surfacing |

### Done When

1. System prompt includes CONVERSATIONAL THREADS section when threads are active
2. Active thread topic appears in prompt context
3. Parked threads with open tasks appear (top 3, sorted by recency)
4. Project context appears when Kozmo project is active
5. Thread context disappears when no threads exist (clean prompt)
6. No performance regression (thread context retrieval < 1ms — it's cache reads)

---

# LAYER 6: Consciousness Wiring

**Owner:** ConsciousnessState (`src/luna/consciousness/state.py`)
**Depends on:** Layer 3 (active thread exists), Layer 5 (pipeline reads thread context)
**Problem:** Consciousness tracks attention topics via `AttentionManager.track()` with manual calls. It has no concept of threads. The coherence score is computed from attention spread alone, not from conversational continuity.

## What Changes

Consciousness gains awareness of the active thread. Thread state feeds directly into attention and coherence computation.

### Modified: ConsciousnessState

```python
@dataclass
class ConsciousnessState:
    attention: AttentionManager = field(default_factory=AttentionManager)
    personality: PersonalityWeights = field(default_factory=PersonalityWeights)
    coherence: float = 1.0
    mood: str = "neutral"
    last_updated: datetime = field(default_factory=datetime.now)
    tick_count: int = 0
    
    # NEW — Thread awareness
    active_thread_topic: Optional[str] = None
    active_thread_turn_count: int = 0
    open_task_count: int = 0
    parked_thread_count: int = 0
```

### Modified: tick()

```python
async def tick(self) -> dict:
    changes = {}
    
    # 1. Decay attention topics (existing)
    pruned = self.attention.decay_all()
    if pruned > 0:
        changes["attention_pruned"] = pruned
    
    # 2. Update coherence — NOW THREAD-AWARE
    focused_topics = self.attention.get_focused(threshold=0.3)
    
    if self.active_thread_topic:
        # Active thread = strong coherence signal
        # Deep in a thread (many turns) = high coherence
        # Open tasks create mild tension (slight coherence reduction)
        thread_depth = min(1.0, self.active_thread_turn_count / 10.0)
        task_tension = self.open_task_count * 0.03  # Small per-task penalty
        
        self.coherence = min(1.0, 0.6 + (thread_depth * 0.35) - task_tension)
        changes["coherence_source"] = "thread"
    elif focused_topics:
        # Fallback to attention-based coherence (existing logic)
        weights = [t.weight for t in focused_topics]
        max_weight = max(weights) if weights else 0.5
        spread = len(focused_topics)
        self.coherence = min(1.0, max_weight * (1.0 - spread * 0.05))
        changes["coherence_source"] = "attention"
    else:
        self.coherence = 0.7
        changes["coherence_source"] = "default"
    
    # 3. Parked threads with open tasks create background tension
    if self.parked_thread_count > 0 and self.open_task_count > 0:
        # This doesn't reduce coherence much — it's more of an awareness signal
        # The proactive surfacing layer (7) reads this
        changes["background_tension"] = self.open_task_count
    
    self.last_updated = datetime.now()
    self.tick_count += 1
    
    return changes
```

### New: update_from_thread()

```python
def update_from_thread(
    self,
    active_thread: Optional[Any] = None,
    parked_threads: list = None,
) -> None:
    """
    Update consciousness state from thread state.
    
    Called by Librarian after thread operations (create, park, resume).
    """
    if active_thread:
        self.active_thread_topic = active_thread.topic
        self.active_thread_turn_count = active_thread.turn_count
        self.open_task_count = len(active_thread.open_tasks)
        
        # Boost attention for thread topic and entities
        self.focus_on(active_thread.topic, weight=0.8)
        for entity in active_thread.entities[:5]:
            self.focus_on(entity, weight=0.5)
    else:
        self.active_thread_topic = None
        self.active_thread_turn_count = 0
        # Don't clear open_task_count — parked threads may still have tasks
    
    if parked_threads is not None:
        self.parked_thread_count = len(parked_threads)
        # Count total open tasks across all parked threads
        parked_task_count = sum(len(t.open_tasks) for t in parked_threads)
        if not active_thread:
            self.open_task_count = parked_task_count
        else:
            self.open_task_count = len(active_thread.open_tasks) + parked_task_count
```

### Modified: get_summary()

```python
def get_summary(self) -> dict:
    summary = {
        # ... existing fields ...
        
        # NEW
        "active_thread": self.active_thread_topic,
        "active_thread_turns": self.active_thread_turn_count,
        "open_tasks": self.open_task_count,
        "parked_threads": self.parked_thread_count,
    }
    return summary
```

### Modified: get_context_hint()

```python
def get_context_hint(self) -> str:
    hints = []
    
    # Personality hint (existing)
    personality_hint = self.personality.to_prompt_hint()
    if personality_hint:
        hints.append(personality_hint)
    
    # Thread hint (NEW)
    if self.active_thread_topic:
        hints.append(f"Deeply engaged in: {self.active_thread_topic}.")
    
    if self.open_task_count > 0:
        hints.append(f"Tracking {self.open_task_count} unresolved item(s).")
    
    # Attention hint (existing, but now secondary to thread)
    if not self.active_thread_topic:
        focused = self.attention.get_focused(threshold=0.3, limit=3)
        if focused:
            topics = [t.name for t in focused]
            hints.append(f"Currently focused on: {', '.join(topics)}.")
    
    # Mood hint (existing)
    if self.mood != "neutral":
        hints.append(f"Current mood: {self.mood}.")
    
    return " ".join(hints)
```

### Wiring: Librarian → Consciousness

In Librarian, after every thread operation, update consciousness:

```python
# After _create_thread, _park_thread, _resume_thread:
consciousness = await self._get_consciousness()
if consciousness:
    parked = [t for t in self._thread_cache.values() if t.status.value == "parked"]
    consciousness.update_from_thread(
        active_thread=self._active_thread,
        parked_threads=parked,
    )
```

### Files Modified

| File | Change |
|------|--------|
| `src/luna/consciousness/state.py` | Thread fields, update_from_thread(), modified tick/summary/hint |
| `src/luna/actors/librarian.py` | Call consciousness.update_from_thread() after thread ops |
| `src/luna/engine.py` | Ensure librarian has reference to consciousness state |
| `tests/test_consciousness_threads.py` | New — coherence from threads, attention sync, hint generation |

### Done When

1. ConsciousnessMonitor (frontend) shows active thread topic
2. Coherence score reflects thread depth (deeper = higher coherence)
3. Open tasks create measurable tension in coherence
4. Attention topics auto-sync with thread entities
5. Context hint includes thread and task awareness
6. Thread operations (create/park/resume) immediately update consciousness
7. Summary endpoint returns thread state for frontend display

---

# LAYER 7: Proactive Surfacing

**Owner:** Context Pipeline + Router
**Depends on:** Layer 5 (thread context in prompts), Layer 6 (consciousness knows about threads)
**Problem:** Luna only responds to what's asked. She never volunteers "we left off discussing X" or "there's still an open task about Y." This layer gives Luna the ability to surface parked thread context proactively when relevant.

## What This Is NOT

This is NOT Luna speaking unprompted. She doesn't interrupt. She doesn't nag about open tasks. She surfaces context when it's relevant — when the user's current message relates to a parked thread, or when a session starts and there are meaningful unresolved items.

## What Changes

### Session Start Surfacing

When a new session begins (first message after engine start or session clear), the pipeline checks for parked threads with open tasks and includes a prompt hint:

```python
# In ContextPipeline.build():
async def build(self, message, session_id="default"):
    # ... existing steps ...
    
    # NEW: Session start — surface parked threads
    session_start_hint = ""
    if self._is_session_start() and self._librarian:
        session_start_hint = await self._get_session_start_context()
    
    system_prompt = self._build_system_prompt(
        ring_history=...,
        entities=...,
        retrieved_context=...,
        thread_context=...,
        session_start_hint=session_start_hint,  # NEW
    )
```

### New: _is_session_start()

```python
def _is_session_start(self) -> bool:
    """Check if this is the first message in a session."""
    return len(self._ring) <= 1  # Only the current message
```

### New: _get_session_start_context()

```python
async def _get_session_start_context(self) -> str:
    """
    Build context hint for session start.
    
    Surfaces:
    - Most recent parked thread with open tasks
    - Active project context (if Kozmo project was active)
    - Total unresolved task count
    
    Framing: This is a HINT to Luna, not a script.
    Luna decides whether and how to mention it.
    """
    if not self._librarian:
        return ""
    
    parked = [
        t for t in self._librarian._thread_cache.values()
        if t.status.value == "parked" and t.open_tasks
    ]
    
    if not parked:
        return ""
    
    # Sort by recency
    parked.sort(key=lambda t: t.parked_at or t.started_at, reverse=True)
    
    lines = ["You have unresolved threads from previous sessions:"]
    
    for thread in parked[:3]:
        age = _format_age(thread.parked_at)
        project = f" [project: {thread.project_slug}]" if thread.project_slug else ""
        lines.append(
            f"- \"{thread.topic}\"{project}: "
            f"{len(thread.open_tasks)} open task(s), parked {age}"
        )
    
    total_tasks = sum(len(t.open_tasks) for t in parked)
    lines.append(f"\nTotal: {total_tasks} unresolved task(s) across {len(parked)} thread(s).")
    lines.append(
        "You may naturally reference these if relevant to the conversation. "
        "Don't force it — mention only if it genuinely connects to what's being discussed."
    )
    
    return "\n".join(lines)
```

### Prompt Placement

Session start context goes in a new section BEFORE the ring history:

```python
def _build_system_prompt(self, ..., session_start_hint=""):
    sections = []
    
    sections.append(self._base_personality)
    
    # SESSION START CONTEXT — NEW (only on first message)
    if session_start_hint:
        sections.append("## CONTINUING THREADS\n" + session_start_hint)
    
    # CONVERSATIONAL THREADS (Layer 5)
    if thread_context:
        sections.append("## CONVERSATIONAL THREADS\n" + thread_context)
    
    # THIS SESSION
    sections.append("## THIS SESSION\n" + ring_history)
    
    # ... rest unchanged ...
```

### Router Integration

The router can also use thread context to influence path selection:

```python
# In QueryRouter.analyze():
def analyze(self, query, consciousness_state=None):
    # ... existing analysis ...
    
    # NEW: If consciousness has open tasks and query touches related entities,
    # force to SIMPLE_PLAN so retrieval includes thread context
    if consciousness_state and consciousness_state.open_task_count > 0:
        if self._query_touches_thread_entities(query, consciousness_state):
            signals.append("thread_relevant")
            # Don't force — just note the signal for logging
```

This is light. The router doesn't need to dramatically change behavior — it just logs that the query is thread-relevant, which helps debugging.

### Files Modified

| File | Change |
|------|--------|
| `src/luna/context/pipeline.py` | Session start detection, session start context, prompt section |
| `src/luna/agentic/router.py` | Optional thread-relevance signal (non-blocking) |
| `tests/test_proactive_surfacing.py` | New — session start context, thread mention framing |

### Done When

1. First message in a new session includes CONTINUING THREADS in system prompt (if parked threads with open tasks exist)
2. Luna can naturally say "we left off discussing X" because the context is in her prompt
3. Luna doesn't nag or force-mention threads — the framing explicitly tells her to reference only if relevant
4. Subsequent messages in the same session don't repeat the session start context
5. If no parked threads or no open tasks, the section is omitted entirely (clean prompt)
6. Router logs thread-relevance signal but doesn't change execution path

---

## Build Order (All Layers)

```
Layer 4: Task Ledger
  1. Upgrade FilingResult to include action/outcome node IDs
  2. Modify _handle_flow_continue to use real IDs
  3. Implement _resolve_open_tasks with entity overlap
  4. Add RESOLVES edges to graph
  5. Add parked-thread-to-quest in Observatory sweep
  TEST: ACTION filed → OUTCOME filed → ACTION resolved → quest generated

Layer 5: Context Threading
  1. Add set_librarian() to ContextPipeline
  2. Implement _get_thread_context()
  3. Add CONVERSATIONAL THREADS section to system prompt
  4. Wire engine.py: pipeline.set_librarian(librarian)
  TEST: Active thread appears in system prompt. Parked threads with tasks appear.

Layer 6: Consciousness Wiring
  1. Add thread fields to ConsciousnessState
  2. Implement update_from_thread()
  3. Modify tick() for thread-aware coherence
  4. Wire librarian → consciousness after thread ops
  TEST: ConsciousnessMonitor shows thread. Coherence reflects thread depth.

Layer 7: Proactive Surfacing
  1. Add _is_session_start() and _get_session_start_context()
  2. Add CONTINUING THREADS section to prompt builder
  3. Add thread-relevance signal to router (optional, non-blocking)
  TEST: New session → "we left off discussing X" naturally surfaces.
```

---

## Integration: Full Flow (All Layers Working)

```
Session 1:
  User: "Let's debug the Kozmo pipeline"
    → Ben: FlowSignal(FLOW, "kozmo pipeline", ["Kozmo", "pipeline"])
    → Dude: Creates THREAD "kozmo pipeline"
    → Consciousness: active_thread="kozmo pipeline", coherence=0.65
    → Pipeline: CONVERSATIONAL THREADS shows "Currently focused on: kozmo pipeline"

  User: "The Eden integration is broken"
    → Ben: FlowSignal(FLOW, continuity=0.8)
    → Ben: Extracts [ACTION: Fix Eden integration]
    → Dude: FILES ACTION node n_act001, adds to thread.open_tasks
    → Consciousness: open_task_count=1, coherence slightly reduced

  User: "OK switching to Kinoni research"
    → Ben: FlowSignal(RECALIBRATION, "kinoni research", ["Kinoni", "Uganda"])
    → Dude: Parks "kozmo pipeline" (open_tasks: [n_act001])
    → Dude: Creates THREAD "kinoni research"
    → Consciousness: active_thread="kinoni research", parked=1, open_tasks=1

  [Session ends]
    → Dude: Parks "kinoni research"
    → Consciousness: no active thread, parked=2, open_tasks=1

Session 2:
  User: "Hey Luna"
    → Pipeline: _is_session_start() = true
    → Pipeline: _get_session_start_context() returns:
        "Parked thread: 'kozmo pipeline' — 1 open task(s), parked 2h ago"
    → System prompt includes CONTINUING THREADS section
    → Luna: "hey! by the way, we were debugging the kozmo pipeline earlier —
             the eden integration fix is still open if you want to pick that up"

  User: "Yeah let's fix that Eden thing"
    → Ben: FlowSignal(RECALIBRATION, "eden fix", ["Eden", "Kozmo"])
    → Dude: Finds parked "kozmo pipeline" (Jaccard=0.67), RESUMES it
    → Thread remembers: open_tasks=[n_act001]
    → Consciousness: active_thread="kozmo pipeline", resume_count=1

  User: "OK I fixed the Eden integration, it's working now"
    → Ben: Extracts [OUTCOME: Eden integration fixed]
    → Dude: Files OUTCOME node n_out001
    → Dude: _resolve_open_tasks() → n_out001 RESOLVES n_act001
    → Thread: open_tasks = [] (empty!)
    → Consciousness: open_task_count=0, coherence rises
    → Observatory: Quest "Continue: kozmo pipeline" auto-completes
```

That's the whole stack. Seven layers. Luna goes from stateless extraction to a system that tracks attention, manages threads, resolves tasks, and naturally surfaces what matters.

---

## Files Summary (All Layers)

| Layer | File | Change |
|-------|------|--------|
| 4 | `src/luna/extraction/types.py` | action/outcome IDs in FilingResult |
| 4 | `src/luna/actors/librarian.py` | Real ID tracking, _resolve_open_tasks() |
| 4 | Observatory backend | Parked-thread-to-quest in sweep |
| 5 | `src/luna/context/pipeline.py` | Thread context retrieval, new prompt section |
| 5 | `src/luna/engine.py` | Wire pipeline↔librarian |
| 6 | `src/luna/consciousness/state.py` | Thread fields, update_from_thread(), tick() |
| 6 | `src/luna/actors/librarian.py` | Call consciousness.update_from_thread() |
| 6 | `src/luna/engine.py` | Wire librarian↔consciousness |
| 7 | `src/luna/context/pipeline.py` | Session start detection, continuing threads section |
| 7 | `src/luna/agentic/router.py` | Thread-relevance signal (optional) |

---

## What You're Building

Layer by layer, Luna gains:

- **Layer 2:** Eyes — she sees conversational shape
- **Layer 3:** Memory — she remembers where attention was
- **Layer 4:** Accountability — she knows what's unfinished
- **Layer 5:** Voice — she can speak about her threads
- **Layer 6:** Feeling — her coherence reflects her state
- **Layer 7:** Initiative — she offers what matters without being asked

Seven layers. Same two actors (Ben + Dude). Same database (Matrix). Same pipeline. Just awareness, all the way down.
