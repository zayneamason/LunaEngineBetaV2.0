# Luna Engine v2.0 Actor System Trace

**Audit Date:** January 25, 2026
**Auditor:** Phase 1 Actor Trace Agent
**Scope:** Complete trace of all 5 actors with message types and state

---

## Executive Summary

Luna Engine uses an **Actor Model** where each actor:
- Has an isolated mailbox (asyncio.Queue)
- Processes messages one-at-a-time
- Cannot crash other actors
- Communicates via Message objects

**Registered Actors:** 5
- DirectorActor (LLM inference)
- MatrixActor (memory substrate)
- ScribeActor (extraction - Ben Franklin)
- LibrarianActor (filing - The Dude)
- HistoryManagerActor (conversation tiers)

---

## Actor Base Class

### File: `src/luna/actors/base.py`

```python
@dataclass
class Message:
    type: str                    # Message type identifier
    payload: Any = None          # Message data
    sender: Optional[str] = None # Sending actor name
    reply_to: Optional[str] = None  # For request-reply
    correlation_id: Optional[str] = None  # Track flow
    timestamp: datetime = field(default_factory=datetime.now)
```

### Lifecycle Methods

| Method | When Called | Purpose |
|--------|-------------|---------|
| `__init__(name, engine)` | Construction | Initialize mailbox, set engine reference |
| `start()` | Engine boot | Begin message loop |
| `on_start()` | Inside start() | Actor-specific initialization |
| `handle(msg)` | Each message | Process message (abstract) |
| `on_error(e, msg)` | Handle failure | Error recovery |
| `stop()` | Shutdown | Signal loop exit |
| `on_stop()` | After loop exits | Cleanup resources |
| `snapshot()` | Optional | Serialize state |
| `restore(state)` | Optional | Deserialize state |

---

## DIRECTOR ACTOR

### File: `src/luna/actors/director.py` (~1900 lines)

**Responsibility:** LLM Inference Management

### Message Types

| Type | Purpose | Payload |
|------|---------|---------|
| `generate` | Generate response | `{user_message, system_prompt, context_window}` |
| `abort` | Cancel generation | None |
| `status` | Get stats | None |

### Key State

```python
_client: Anthropic            # Claude API (lazy init)
_local: LocalInference        # Qwen 3B MLX
_enable_local: bool           # Whether local available
_model: str                   # Current model ID
_generating: bool             # Generation in progress
_abort_requested: bool        # Abort flag
_active_ring: ConversationRing  # Conversation history
_entity_context: EntityContext  # Entity detection
```

### Routing Decision

```python
async def _should_delegate(self, user_message: str, threshold: float = 0.6) -> bool:
    """
    Decide: Local Qwen or Claude delegation.

    Returns True if:
    1. Explicit delegation signals (temporal, research, code, memory)
    2. Complexity score >= threshold
    """
```

**Delegation Signals:**
- Temporal: "current", "latest", "today"
- Research: "search", "look up", "find"
- Code: "write code", "function", "implement"
- Memory: "remember when", "what did we"

### Generation Paths

1. **_generate_local_only()** - Pure local (Qwen 3B)
2. **_generate_with_delegation()** - Planned delegation to Claude
3. **_generate_claude_direct()** - Fallback when local unavailable

### Direct API (Non-Mailbox)

```python
async def process(self, message: str, context: dict = None) -> dict:
    """
    Direct processing API (used by PersonaAdapter for voice).

    Returns:
    {
        "response": text,
        "route_decision": "local" | "delegated",
        "latency_ms": time
    }
    """
```

---

## MATRIX ACTOR

### File: `src/luna/actors/matrix.py`

**Responsibility:** Long-term Memory Management

### Message Types

| Type | Purpose | Payload |
|------|---------|---------|
| `store` | Store memory node | `{content, node_type, tags, confidence}` |
| `retrieve` | Get context for query | `{query, max_tokens}` |
| `search` | Search memory nodes | `{query, limit}` |

### Key State

```python
db_path: Path                  # SQLite database location
_db: MemoryDatabase            # Database connection
_matrix: MemoryMatrix          # CRUD operations
_graph: MemoryGraph            # NetworkX wrapper
_initialized: bool             # Ready flag
```

### Core Operations

| Method | Purpose |
|--------|---------|
| `initialize()` | Connect DB, load graph |
| `store_memory(content, node_type, tags)` | Store node |
| `store_turn(session_id, role, content)` | Store conversation |
| `get_context(query, max_tokens)` | Retrieve context |
| `search(query, limit)` | Search nodes |
| `reinforce_memory(node_id)` | Increase lock-in |
| `find_related(node_id, depth)` | Graph traversal |

### Context Formatting

Nodes grouped by type and formatted as markdown:
```
## FACTs
- Fact 1 🔒 (locked)
- Fact 2

## DECISIONs
- Decision 1
```

---

## SCRIBE ACTOR (Ben Franklin)

### File: `src/luna/actors/scribe.py`

**Responsibility:** Extract Structured Knowledge

**Persona:** Benjamin Franklin - meticulous, scholarly extraction

### Message Types

| Type | Purpose | Payload |
|------|---------|---------|
| `extract_turn` | Extract from conversation | `{role, content, session_id, immediate}` |
| `extract_text` | Extract from raw text | `{text, source_id}` |
| `entity_note` | Direct entity update | `{entity_name, entity_type, facts}` |
| `flush_stack` | Process pending chunks | None |
| `compress_turn` | Summarize for history | `{content, role}` |
| `get_stats` | Return statistics | None |

### Key State

```python
config: ExtractionConfig       # Backend, batch size
chunker: SemanticChunker       # Turn→chunks
stack: deque[Chunk]            # Context window (max 5)
_client: Anthropic             # Claude API (lazy)
```

### Extraction Output

```python
class ExtractionOutput:
    objects: list[ExtractedObject]  # Facts, decisions, etc.
    edges: list[ExtractedEdge]      # Relationships
    source_id: str
```

**Extracted Object Types:**
- FACT, DECISION, PROBLEM, ASSUMPTION
- CONNECTION, ACTION, OUTCOME
- QUESTION, PREFERENCE, OBSERVATION, MEMORY

### Processing Flow

1. Receive `extract_turn` message
2. Chunk the turn via SemanticChunker
3. If immediate: extract now
4. Else: batch in stack until threshold
5. Send extraction to Librarian

---

## LIBRARIAN ACTOR (The Dude)

### File: `src/luna/actors/librarian.py`

**Responsibility:** File Extractions & Manage Entities

**Persona:** The Dude - chill, competent, files things

### Message Types

| Type | Purpose | Payload |
|------|---------|---------|
| `file` | File extraction to Matrix | `{extraction: ExtractionOutput}` |
| `entity_update` | Create/update entity | `{name, entity_type, facts}` |
| `get_context` | Retrieve context | `{query, max_tokens, budget_preset}` |
| `resolve_entity` | Find or create entity | `{name, entity_type}` |
| `rollback_entity` | Revert to version | `{entity_id, version}` |
| `prune` | Clean drifting nodes | `{confidence_threshold, age_days}` |

### Key State

```python
alias_cache: dict[str, str]    # name_lower → node_id (O(1))
_entity_resolver: EntityResolver
inference_queue: list[str]     # Deferred processing
batch_threshold: int = 10
```

### Entity Resolution (3-Level)

```python
async def _resolve_entity(name: str, entity_type: str) -> str:
    """
    1. Check alias_cache (O(1))
    2. Check exact DB match
    3. Create new node
    """
```

### Budget Presets

| Preset | Tokens | Use Case |
|--------|--------|----------|
| `minimal` | 1800 | Voice mode |
| `balanced` | 3800 | Normal |
| `rich` | 7200 | Research |

---

## HISTORY MANAGER ACTOR

### File: `src/luna/actors/history_manager.py`

**Responsibility:** Three-Tier Conversation History

```
Active (Current)  ←→  Recent (Compressed)  ←→  Archive (Extracted)
   ~1000 tokens          ~500-1500 tokens      → Memory Matrix
   5-10 turns              50-100 turns
```

### Message Types

| Type | Purpose | Payload |
|------|---------|---------|
| `add_turn` | Add conversation turn | `{role, content, tokens, session_id}` |
| `get_active_window` | Get Active tier | `{session_id, limit}` |
| `search_recent` | Search Recent tier | `{query, limit, search_type}` |
| `rotate_tier` | Move turn to tier | `{turn_id, tier}` |
| `check_budget` | Check rotation needed | `{session_id}` |
| `queue_compression` | Queue for Scribe | `{turn_id}` |
| `queue_extraction` | Queue for archival | `{turn_id}` |

### Configuration

```python
@dataclass
class HistoryConfig:
    max_active_tokens: int = 1000
    max_active_turns: int = 10
    max_recent_age_minutes: int = 60
    compression_enabled: bool = True
    search_type: str = "hybrid"  # "hybrid"|"keyword"|"semantic"
```

### Tier Rotation Process

1. Detect budget exceeded (add_turn or check_budget)
2. Find oldest Active turn
3. Move to Recent tier
4. Queue for compression (Scribe)
5. When compressed, generate embedding
6. When aged, queue for extraction (Librarian)
7. Archive to Memory Matrix

### Tick Processing

```python
async def tick(self) -> None:
    """Called every 500ms-1s by engine."""
    await self._process_compression_queue()
    await self._process_extraction_queue()
    await self._check_archivable_turns()
```

---

## Inter-Actor Message Flow

### Integration Matrix

| From | To | Method | Message Type |
|------|-----|--------|--------------|
| Engine | Director | Message (mailbox) | `generate` |
| Director | Engine | send_to_engine() | `generation_complete` |
| Scribe | Librarian | send() | `file` |
| Librarian | Matrix | Direct API | N/A (database) |
| HistoryManager | Scribe | send() | `extract_turn` |
| HistoryManager | Matrix | Direct API | N/A (database) |

### Context Flow for Generation

```
1. Engine receives user input
2. Engine sends "generate" to Director
   ├─ message.payload contains:
   │  - user_message
   │  - system_prompt
   │  - context_window (from HistoryManager)
   │  - memories (from Librarian query)
   │
3. Director._handle_director_generate()
   ├─ Check if should_delegate
   ├─ Build framed context (via EntityContext)
   ├─ Load emergent prompt (DNA + Experience + Mood)
   ├─ Generate response (local or delegated)
   │
4. Ring buffer updated
5. send_to_engine("generation_complete", result)
6. Engine receives completion event
7. Engine sends response to user
```

---

## Error Handling & Fault Tolerance

### Error Isolation

```python
async def _handle_safe(self, msg: Message) -> None:
    try:
        await self.handle(msg)
    except Exception as e:
        logger.error(f"Actor {self.name} failed on {msg}: {e}")
        await self.on_error(e, msg)
        # Don't re-raise - actor continues
```

### Crash Propagation

- **Local crash**: That actor stops, others continue
- **Message-handling error**: Error logged, callback invoked, loop continues
- **Unhandled exception**: Actor exits (intentional)

---

## Statistics Methods

### Director Stats
```python
{
    "local_generations": 42,
    "delegated_generations": 18,
    "local_available": True,
    "local_percentage": 70
}
```

### Scribe Stats
```python
{
    "backend": "claude-opus",
    "extractions_count": 15,
    "objects_extracted": 234,
    "edges_extracted": 89,
    "avg_extraction_time_ms": 2345
}
```

### Librarian Stats
```python
{
    "filings_count": 15,
    "nodes_created": 127,
    "nodes_merged": 45,
    "edges_created": 89
}
```

---

## Summary Table

| Actor | Input | Output | State |
|-------|-------|--------|-------|
| **Director** | "generate" message | "generation_complete" event | Generation state, ring buffer |
| **Scribe** | "extract_turn" message | "file" to Librarian | Extraction stack, history |
| **Librarian** | "file" message | Entity updates to DB | Alias cache |
| **Matrix** | "store" message | Database queries | DB connection, graph |
| **HistoryManager** | "add_turn" message | "queue_compression" to Scribe | Session ID, tier state |

---

**End of Actor Trace**
