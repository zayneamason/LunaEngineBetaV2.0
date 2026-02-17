# SPEC: Thread Management — Layer 3

## Luna Flow State Architecture

**Layer:** 3 of 7
**Owner:** Librarian (The Dude)
**Depends on:** Layer 2 (Flow Awareness — Scribe emits FlowSignals)
**Enables:** Layer 4 (Task Ledger), Layer 5 (Consciousness Wiring)

---

## Problem

Luna has no concept of "where we left off." Conversations produce facts that go into the Memory Matrix, but there's no structure representing *a stretch of focused work* — its topic, its entities, its open tasks, and whether it's still active or was parked when the user shifted attention.

Layer 2 gives Scribe the ability to detect conversational mode (FLOW / RECALIBRATION / AMEND). Layer 3 gives the Librarian the ability to *act on those signals* — creating, parking, and resuming threads.

---

## What Is a Thread

A thread is a Memory Matrix node (type `THREAD`) representing a named stretch of conversational attention.

It is NOT:
- A chat session (sessions are transport-level, threads are semantic-level)
- A Kozmo project (projects are creative asset containers, threads are conversational state)
- A task list (threads *contain references to* open tasks, they aren't task managers)

It IS:
- The unit of "save" for Luna's working memory
- The thing that lets Luna say "last time we worked on this, we were discussing X"
- The bridge between conversations and Kozmo project context

### Thread Lifecycle

```
[created] → active → parked → resumed → active → ... → closed
                        ↑                    |
                        └────────────────────┘
```

**Created:** Librarian creates a THREAD node when first non-trivial flow begins in a session (or when a RECALIBRATION starts a genuinely new topic).

**Active:** One thread is active at a time. Receives accumulating entities and open task references as conversation progresses.

**Parked:** On RECALIBRATION signal, active thread gets snapshotted and status set to `parked`. Topic, entities, open tasks, turn count, and time range are captured.

**Resumed:** When a new flow's entities overlap significantly with a parked thread, Librarian resumes it instead of creating a new one. Status returns to `active`.

**Closed:** Thread is explicitly closed when its open tasks are resolved, or aged out after configurable threshold (default: 7 days parked with no resume).

---

## Data Model

### New Types — `src/luna/extraction/types.py`

```python
class ThreadStatus(str, Enum):
    """Thread lifecycle states."""
    ACTIVE = "active"
    PARKED = "parked"
    RESUMED = "resumed"     # Transient — becomes ACTIVE on next turn
    CLOSED = "closed"


@dataclass
class Thread:
    """
    A named stretch of conversational attention.

    Persisted as a THREAD node in Memory Matrix.
    """
    id: str                              # Matrix node ID
    topic: str                           # Brief topic label
    status: ThreadStatus = ThreadStatus.ACTIVE
    entities: list[str] = field(default_factory=list)  # Active entity names
    entity_node_ids: list[str] = field(default_factory=list)  # Resolved Matrix IDs
    open_tasks: list[str] = field(default_factory=list)  # ACTION node IDs without OUTCOMEs
    turn_count: int = 0
    started_at: datetime = field(default_factory=datetime.now)
    parked_at: Optional[datetime] = None
    resumed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    project_slug: Optional[str] = None   # Kozmo project tag (if /project/activate was called)
    parent_thread_id: Optional[str] = None  # If this thread split from another
    resume_count: int = 0                # How many times this thread has been resumed
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "topic": self.topic,
            "status": self.status.value,
            "entities": self.entities,
            "entity_node_ids": self.entity_node_ids,
            "open_tasks": self.open_tasks,
            "turn_count": self.turn_count,
            "started_at": self.started_at.isoformat(),
            "parked_at": self.parked_at.isoformat() if self.parked_at else None,
            "resumed_at": self.resumed_at.isoformat() if self.resumed_at else None,
            "closed_at": self.closed_at.isoformat() if self.closed_at else None,
            "project_slug": self.project_slug,
            "parent_thread_id": self.parent_thread_id,
            "resume_count": self.resume_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Thread":
        return cls(
            id=data["id"],
            topic=data["topic"],
            status=ThreadStatus(data.get("status", "active")),
            entities=data.get("entities", []),
            entity_node_ids=data.get("entity_node_ids", []),
            open_tasks=data.get("open_tasks", []),
            turn_count=data.get("turn_count", 0),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else datetime.now(),
            parked_at=datetime.fromisoformat(data["parked_at"]) if data.get("parked_at") else None,
            resumed_at=datetime.fromisoformat(data["resumed_at"]) if data.get("resumed_at") else None,
            closed_at=datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None,
            project_slug=data.get("project_slug"),
            parent_thread_id=data.get("parent_thread_id"),
            resume_count=data.get("resume_count", 0),
        )
```

### Matrix Storage

Threads are stored as `THREAD` type nodes in the existing Memory Matrix. No new tables. No new database.

**Node content format (JSON string in Matrix `content` field):**
```json
{
    "topic": "kozmo pipeline debugging",
    "status": "parked",
    "entities": ["Kozmo", "Eden", "pipeline"],
    "entity_node_ids": ["n_abc123", "n_def456"],
    "open_tasks": ["n_task789"],
    "turn_count": 12,
    "started_at": "2026-02-16T14:30:00",
    "parked_at": "2026-02-16T15:45:00",
    "project_slug": "luna-manifesto",
    "resume_count": 0
}
```

**Tags:** `["thread", "status:parked", "project:luna-manifesto"]`

**Edges from THREAD node:**
- `THREAD --[INVOLVES]--> entity_node` (for each entity)
- `THREAD --[HAS_OPEN_TASK]--> action_node` (for unresolved ACTIONs)
- `THREAD --[IN_PROJECT]--> project_entity_node` (if project context active)
- `THREAD --[CONTINUED_BY]--> thread_node` (if this thread was split)

---

## Librarian Changes — `src/luna/actors/librarian.py`

### New State

```python
# Thread management
self._active_thread: Optional[Thread] = None
self._active_project_slug: Optional[str] = None  # Set by /project/activate
self._thread_cache: dict[str, Thread] = {}  # id -> Thread (recent threads in memory)
self._max_cached_threads: int = 20

# Stats
self._threads_created: int = 0
self._threads_parked: int = 0
self._threads_resumed: int = 0
self._threads_closed: int = 0
```

### New Message Types

Add to `handle()` match:

```python
case "set_project_context":
    await self._handle_set_project_context(msg)

case "clear_project_context":
    await self._handle_clear_project_context(msg)

case "get_active_thread":
    await self._handle_get_active_thread(msg)

case "get_parked_threads":
    await self._handle_get_parked_threads(msg)
```

### Modified: `_handle_file()`

This is the core change. After wiring the extraction (existing behavior), read the flow signal and manage threads:

```python
async def _handle_file(self, msg: Message) -> None:
    payload = msg.payload or {}
    extraction = ExtractionOutput.from_dict(payload)

    if extraction.is_empty():
        logger.debug("The Dude: Empty extraction, nothing to file")
        return

    # Existing: wire extraction into Matrix
    result = await self._wire_extraction(extraction)

    logger.info(
        f"The Dude: Filed {len(result.nodes_created)} new nodes, "
        f"merged {len(result.nodes_merged)}, "
        f"created {len(result.edges_created)} edges"
    )

    # NEW: Process flow signal
    flow_data = payload.get("flow_signal")
    if flow_data:
        flow_signal = FlowSignal.from_dict(flow_data)
        await self._process_flow_signal(flow_signal, extraction, result)

    if msg.reply_to:
        await self.send_to_engine("filing_result", result.to_dict())
```

### Core: `_process_flow_signal()`

```python
async def _process_flow_signal(
    self,
    signal: FlowSignal,
    extraction: ExtractionOutput,
    filing_result: FilingResult,
) -> None:
    """
    React to Ben's flow signal. Create, park, or resume threads.
    """
    match signal.mode:
        case ConversationMode.FLOW:
            await self._handle_flow_continue(signal, extraction)
        
        case ConversationMode.RECALIBRATION:
            await self._handle_recalibration(signal, extraction)
        
        case ConversationMode.AMEND:
            await self._handle_amend(signal, extraction)
```

### `_handle_flow_continue()`

Most common case. Just accumulate into the active thread.

```python
async def _handle_flow_continue(
    self,
    signal: FlowSignal,
    extraction: ExtractionOutput,
) -> None:
    """Conversation continuing on-topic. Accumulate into active thread."""
    
    if not self._active_thread:
        # First substantive turn — create initial thread
        self._active_thread = await self._create_thread(
            topic=signal.current_topic,
            entities=signal.topic_entities,
        )
        logger.info(
            f"The Dude: Started thread '{self._active_thread.topic}' "
            f"({self._active_thread.id})"
        )
        return

    # Update active thread
    self._active_thread.turn_count += 1
    
    # Merge new entities (additive)
    for entity in signal.topic_entities:
        if entity not in self._active_thread.entities:
            self._active_thread.entities.append(entity)

    # Track open tasks from extraction
    for obj in extraction.objects:
        if obj.type == ExtractionType.ACTION:
            # ACTION extracted — add to open tasks
            # (node_id comes from filing_result, but we might not have the mapping)
            # For now, track by content hash; Layer 4 will use proper node IDs
            task_key = f"action:{hash(obj.content) & 0xFFFFFFFF:08x}"
            if task_key not in self._active_thread.open_tasks:
                self._active_thread.open_tasks.append(task_key)
        
        elif obj.type == ExtractionType.OUTCOME:
            # OUTCOME extracted — check if it resolves an open task
            # Simple heuristic: if OUTCOME mentions same entities as an open task
            await self._try_resolve_task(obj, self._active_thread)

    # Update topic if signal provides a better one
    if signal.current_topic and signal.current_topic != self._active_thread.topic:
        # Don't overwrite — topic evolves but the original name anchors the thread
        pass

    logger.debug(
        f"The Dude: Flow continues in '{self._active_thread.topic}' "
        f"(turn {self._active_thread.turn_count}, "
        f"{len(self._active_thread.entities)} entities, "
        f"{len(self._active_thread.open_tasks)} open tasks)"
    )
```

### `_handle_recalibration()`

Topic shift. Park current, check for resumable match, or create new.

```python
async def _handle_recalibration(
    self,
    signal: FlowSignal,
    extraction: ExtractionOutput,
) -> None:
    """Topic shift detected. Park current thread, start or resume another."""
    
    # 1. Park current thread (if one exists)
    if self._active_thread:
        await self._park_thread(self._active_thread)
        logger.info(
            f"The Dude: Parked thread '{self._active_thread.topic}' "
            f"({self._active_thread.turn_count} turns, "
            f"{len(self._active_thread.open_tasks)} open tasks)"
        )

    # 2. Check for resumable parked thread
    resumable = await self._find_resumable_thread(signal.topic_entities)
    
    if resumable:
        # Resume existing thread
        await self._resume_thread(resumable)
        self._active_thread = resumable
        logger.info(
            f"The Dude: Resumed thread '{resumable.topic}' "
            f"(was parked, {resumable.resume_count} resumes)"
        )
    else:
        # Create new thread
        self._active_thread = await self._create_thread(
            topic=signal.current_topic,
            entities=signal.topic_entities,
        )
        logger.info(
            f"The Dude: New thread '{self._active_thread.topic}' "
            f"({self._active_thread.id})"
        )
```

### `_handle_amend()`

Course correction. Same thread, just note the correction.

```python
async def _handle_amend(
    self,
    signal: FlowSignal,
    extraction: ExtractionOutput,
) -> None:
    """Course correction within current flow. No thread change needed."""
    
    if not self._active_thread:
        # Amend without active thread — treat as flow start
        self._active_thread = await self._create_thread(
            topic=signal.current_topic,
            entities=signal.topic_entities,
        )
        return
    
    self._active_thread.turn_count += 1
    
    logger.debug(
        f"The Dude: Amend in '{self._active_thread.topic}' "
        f"(correction_target: {signal.correction_target[:50]})"
    )
```

---

## Thread Operations

### `_create_thread()`

```python
async def _create_thread(
    self,
    topic: str,
    entities: list[str],
) -> Thread:
    """Create a new THREAD node in the Matrix."""
    
    matrix = await self._get_matrix()
    
    # Build thread content
    thread = Thread(
        id="",  # Will be set by Matrix
        topic=topic,
        status=ThreadStatus.ACTIVE,
        entities=entities,
        turn_count=1,
        project_slug=self._active_project_slug,
    )
    
    # Persist to Matrix
    if matrix:
        node_id = await matrix.add_node(
            node_type="THREAD",
            content=json.dumps(thread.to_dict()),
            source="librarian",
            confidence=1.0,
            tags=self._thread_tags(thread),
        )
        thread.id = node_id
        
        # Create entity edges
        for entity_name in entities:
            entity_id = await self._resolve_entity(entity_name, "ENTITY")
            thread.entity_node_ids.append(entity_id)
            await self._create_edge(
                from_id=node_id,
                to_id=entity_id,
                edge_type="INVOLVES",
                confidence=1.0,
            )
        
        # Create project edge if in project context
        if self._active_project_slug:
            project_id = await self._resolve_entity(
                self._active_project_slug, "PROJECT"
            )
            await self._create_edge(
                from_id=node_id,
                to_id=project_id,
                edge_type="IN_PROJECT",
                confidence=1.0,
            )
    else:
        thread.id = f"thread_{uuid.uuid4().hex[:8]}"
    
    # Cache
    self._thread_cache[thread.id] = thread
    self._threads_created += 1
    
    return thread
```

### `_park_thread()`

```python
async def _park_thread(self, thread: Thread) -> None:
    """Snapshot and park a thread."""
    
    thread.status = ThreadStatus.PARKED
    thread.parked_at = datetime.now()
    
    # Update in Matrix
    await self._update_thread_node(thread)
    
    # Keep in cache for quick resume lookup
    self._thread_cache[thread.id] = thread
    self._threads_parked += 1
```

### `_resume_thread()`

```python
async def _resume_thread(self, thread: Thread) -> None:
    """Resume a parked thread."""
    
    thread.status = ThreadStatus.ACTIVE
    thread.resumed_at = datetime.now()
    thread.resume_count += 1
    
    # Update in Matrix
    await self._update_thread_node(thread)
    
    self._thread_cache[thread.id] = thread
    self._threads_resumed += 1
```

### `_find_resumable_thread()`

```python
async def _find_resumable_thread(
    self,
    new_entities: list[str],
) -> Optional[Thread]:
    """
    Find a parked thread whose entities overlap with the new topic.
    
    Returns the best match if entity overlap >= 0.4 (Jaccard).
    Checks cache first, then Matrix.
    """
    
    if not new_entities:
        return None
    
    new_set = set(e.lower() for e in new_entities)
    best_match: Optional[Thread] = None
    best_overlap: float = 0.0
    
    # 1. Check cache (fast path)
    for thread in self._thread_cache.values():
        if thread.status != ThreadStatus.PARKED:
            continue
        
        thread_set = set(e.lower() for e in thread.entities)
        if not thread_set:
            continue
        
        overlap = len(new_set & thread_set) / len(new_set | thread_set)
        
        if overlap > best_overlap:
            best_overlap = overlap
            best_match = thread
    
    # 2. If no cache hit, search Matrix for THREAD nodes
    if best_overlap < 0.4:
        matrix = await self._get_matrix()
        if matrix:
            # Search for parked threads mentioning any of the new entities
            for entity in new_entities[:3]:  # Limit queries
                nodes = await matrix.search_nodes(
                    entity,
                    node_type="THREAD",
                    limit=5,
                )
                for node in nodes:
                    try:
                        thread_data = json.loads(node.content)
                        if thread_data.get("status") != "parked":
                            continue
                        
                        thread = Thread.from_dict(thread_data)
                        thread.id = node.id
                        
                        thread_set = set(e.lower() for e in thread.entities)
                        overlap = len(new_set & thread_set) / len(new_set | thread_set) if thread_set else 0
                        
                        if overlap > best_overlap:
                            best_overlap = overlap
                            best_match = thread
                            # Cache it
                            self._thread_cache[thread.id] = thread
                    except (json.JSONDecodeError, KeyError):
                        continue
    
    # Threshold: 0.4 Jaccard overlap to resume
    if best_overlap >= 0.4 and best_match:
        logger.info(
            f"The Dude: Found resumable thread '{best_match.topic}' "
            f"(overlap={best_overlap:.2f})"
        )
        return best_match
    
    return None
```

### `_update_thread_node()`

```python
async def _update_thread_node(self, thread: Thread) -> None:
    """Update a THREAD node's content in the Matrix."""
    
    matrix = await self._get_matrix()
    if not matrix:
        return
    
    # Update node content
    await matrix.update_node(
        node_id=thread.id,
        content=json.dumps(thread.to_dict()),
        tags=self._thread_tags(thread),
    )
```

### `_thread_tags()`

```python
def _thread_tags(self, thread: Thread) -> list[str]:
    """Generate searchable tags for a thread node."""
    tags = ["thread", f"status:{thread.status.value}"]
    
    if thread.project_slug:
        tags.append(f"project:{thread.project_slug}")
    
    if thread.open_tasks:
        tags.append("has_open_tasks")
    
    return tags
```

### `_try_resolve_task()`

```python
async def _try_resolve_task(
    self,
    outcome: ExtractedObject,
    thread: Thread,
) -> None:
    """
    Check if an OUTCOME resolves any open tasks in the thread.
    
    Simple heuristic: if the OUTCOME's entities overlap with 
    entities mentioned alongside an open ACTION, consider it resolved.
    
    Layer 4 will replace this with proper node-ID-based tracking.
    """
    outcome_entities = set(e.lower() for e in outcome.entities)
    
    resolved = []
    for task_key in thread.open_tasks:
        # For now, we can't look up the ACTION's entities without Layer 4
        # Just log that we have the mechanism in place
        pass
    
    for key in resolved:
        thread.open_tasks.remove(key)
        logger.info(f"The Dude: Resolved open task {key}")
```

---

## Kozmo Project Bridge

### `/project/activate` handler

```python
async def _handle_set_project_context(self, msg: Message) -> None:
    """Set active Kozmo project context for thread tagging."""
    payload = msg.payload or {}
    slug = payload.get("slug", "")
    
    if slug:
        self._active_project_slug = slug
        logger.info(f"The Dude: Project context set to '{slug}'")
        
        # Check for parked threads in this project
        project_threads = [
            t for t in self._thread_cache.values()
            if t.project_slug == slug and t.status == ThreadStatus.PARKED
        ]
        
        if project_threads:
            topics = [t.topic for t in project_threads[:3]]
            logger.info(
                f"The Dude: Found {len(project_threads)} parked threads "
                f"for project '{slug}': {topics}"
            )
            
            # Emit event so Context Pipeline can surface these
            await self.send_to_engine("project_threads_available", {
                "project_slug": slug,
                "threads": [t.to_dict() for t in project_threads[:5]],
            })
```

### `/project/deactivate` handler

```python
async def _handle_clear_project_context(self, msg: Message) -> None:
    """Clear active Kozmo project context."""
    if self._active_thread and self._active_project_slug:
        # Park the current thread when leaving project context
        await self._park_thread(self._active_thread)
        logger.info(
            f"The Dude: Auto-parked thread '{self._active_thread.topic}' "
            f"on project deactivate"
        )
        self._active_thread = None
    
    self._active_project_slug = None
    logger.info("The Dude: Project context cleared")
```

### Engine Wiring

In `server.py`, the existing `/project/activate` and `/project/deactivate` endpoints need to forward to the Librarian:

```python
# In /project/activate handler:
librarian = engine.get_actor("librarian")
if librarian:
    await librarian.handle(Message(
        type="set_project_context",
        payload={"slug": slug}
    ))

# In /project/deactivate handler:
librarian = engine.get_actor("librarian")
if librarian:
    await librarian.handle(Message(
        type="clear_project_context",
        payload={}
    ))
```

---

## Session Lifecycle

### On Session Start

No thread action. Thread creation is lazy — happens on first FLOW signal with substance.

### On Session End (or engine shutdown)

```python
async def on_stop(self) -> None:
    """Cleanup on stop."""
    # Park active thread
    if self._active_thread:
        await self._park_thread(self._active_thread)
        logger.info(
            f"The Dude: Parked active thread '{self._active_thread.topic}' "
            f"on shutdown"
        )
        self._active_thread = None

    # Save alias cache (existing)
    self._save_alias_cache()
```

### Thread Aging (Periodic)

Add to existing `_handle_prune()`:

```python
# Close stale parked threads (>7 days, no open tasks)
stale_cutoff = datetime.now().timestamp() - (7 * 24 * 3600)
for thread_id, thread in list(self._thread_cache.items()):
    if thread.status != ThreadStatus.PARKED:
        continue
    if thread.parked_at and thread.parked_at.timestamp() < stale_cutoff:
        if not thread.open_tasks:
            thread.status = ThreadStatus.CLOSED
            thread.closed_at = datetime.now()
            await self._update_thread_node(thread)
            self._threads_closed += 1
            logger.info(f"The Dude: Closed stale thread '{thread.topic}'")
```

Threads with open tasks are NEVER auto-closed. They stay parked until tasks resolve or user explicitly closes them.

---

## Testing

### Unit: Thread Lifecycle

```python
# Create thread on first FLOW
signal = FlowSignal(mode=FLOW, current_topic="kozmo pipeline", topic_entities=["Kozmo", "pipeline"])
await librarian._process_flow_signal(signal, extraction, result)
assert librarian._active_thread is not None
assert librarian._active_thread.topic == "kozmo pipeline"
assert librarian._active_thread.status == ThreadStatus.ACTIVE

# Park on RECALIBRATION
signal = FlowSignal(mode=RECALIBRATION, current_topic="kinoni research", topic_entities=["Kinoni", "Uganda"])
await librarian._process_flow_signal(signal, extraction, result)
assert librarian._active_thread.topic == "kinoni research"  # New thread
# Check previous was parked
parked = [t for t in librarian._thread_cache.values() if t.topic == "kozmo pipeline"]
assert len(parked) == 1
assert parked[0].status == ThreadStatus.PARKED

# Resume on return to similar entities
signal = FlowSignal(mode=RECALIBRATION, current_topic="kozmo assets", topic_entities=["Kozmo", "assets", "pipeline"])
await librarian._process_flow_signal(signal, extraction, result)
assert librarian._active_thread.topic == "kozmo pipeline"  # Resumed original
assert librarian._active_thread.status == ThreadStatus.ACTIVE
assert librarian._active_thread.resume_count == 1
```

### Unit: Kozmo Project Tagging

```python
# Set project context
await librarian._handle_set_project_context(Message(
    type="set_project_context",
    payload={"slug": "luna-manifesto"}
))
assert librarian._active_project_slug == "luna-manifesto"

# Create thread — should inherit project slug
signal = FlowSignal(mode=FLOW, current_topic="manifesto structure", topic_entities=["manifesto"])
await librarian._process_flow_signal(signal, extraction, result)
assert librarian._active_thread.project_slug == "luna-manifesto"

# Deactivate project — should auto-park thread
await librarian._handle_clear_project_context(Message(
    type="clear_project_context",
    payload={}
))
assert librarian._active_thread is None
parked = [t for t in librarian._thread_cache.values() if t.project_slug == "luna-manifesto"]
assert len(parked) == 1
```

### Unit: Thread Resume vs Create

```python
# Park a thread about Eden
librarian._thread_cache["t1"] = Thread(
    id="t1", topic="eden integration", status=ThreadStatus.PARKED,
    entities=["Eden", "agents", "API"]
)

# New topic with high overlap → should resume
result = await librarian._find_resumable_thread(["Eden", "agents", "config"])
assert result is not None
assert result.id == "t1"

# New topic with low overlap → should NOT resume
result = await librarian._find_resumable_thread(["Kinoni", "solar", "Uganda"])
assert result is None
```

### Integration: End-to-End Thread Flow

1. Send 5 turns about Kozmo through pipeline
2. Verify THREAD node created in Matrix with type="THREAD"
3. Verify node has INVOLVES edges to entity nodes
4. Send 1 turn shifting to Kinoni
5. Verify first thread parked, second thread created
6. Send 1 turn back about Kozmo
7. Verify first thread resumed (not a third thread created)
8. Verify resume_count == 1

### Sovereignty: No Cloud in Thread Management

```python
# Thread operations are entirely local
# They depend only on Matrix (SQLite) and flow signals (local)
# Verify no HTTP calls during thread create/park/resume
```

---

## Files Modified

| File | Change |
|------|--------|
| `src/luna/extraction/types.py` | Add `ThreadStatus`, `Thread` |
| `src/luna/actors/librarian.py` | Thread state, flow signal processing, create/park/resume/close, Kozmo project bridge |
| `src/luna/api/server.py` | Wire `/project/activate` and `/project/deactivate` to Librarian |
| `tests/test_thread_management.py` | New — thread lifecycle, resume logic, project tagging |

---

## Success Criteria

Layer 3 complete when:

1. Every RECALIBRATION signal creates or resumes a thread
2. Active thread accumulates entities and open task references
3. Parked threads are findable by entity overlap (>0.4 Jaccard → resume)
4. Kozmo project context tags threads via `/project/activate`
5. Project deactivation auto-parks the active thread
6. Parked threads for a project are surfaced on project activate
7. Stale threads (>7 days, no open tasks) auto-close on prune
8. THREAD nodes visible in Matrix / Observatory
9. All thread operations are local (no cloud calls)
10. No regression in extraction or filing performance (<5ms overhead per turn)

---

## What This Enables (Layer 4+)

**Layer 4 — Task Ledger:** Replace the heuristic task tracking with proper Matrix node-ID-based ACTION→OUTCOME resolution. Open tasks become first-class persistent items.

**Layer 5 — Consciousness Wiring:** Active thread becomes the real attention signal. Thread topic feeds consciousness state. Parked threads with open tasks create low-level "unresolved" tension in coherence score.

**Layer 7 — Proactive Surfacing:** "We left off discussing X. There's still an open task about Y." Luna can say this because threads persist across sessions with their full context.

**Kozmo Integration:** "Last time you worked on luna-manifesto, you were debugging the asset pipeline. Eden integration was still open." Luna bridges conversational memory and project context.
