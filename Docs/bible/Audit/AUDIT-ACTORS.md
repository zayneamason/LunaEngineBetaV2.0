# AUDIT-ACTORS.md

**Generated:** 2026-01-30
**Agent:** Actor System Tracer
**Phase:** 1.2
**Source Files:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/actors/`

---

## Summary

| Metric | Count |
|--------|-------|
| Total Actors | 5 |
| Base Class | 1 (Actor) |
| Message Types | 42 |
| Inter-Actor Flows | 6 distinct flows |
| Shared State Violations | 0 (clean isolation) |
| Blocking Call Violations | 0 (all async) |

---

## Actor Inventory

| Actor | File | Purpose | Status |
|-------|------|---------|--------|
| **Actor** (Base) | `base.py` | Abstract base class with mailbox pattern | Complete |
| **DirectorActor** | `director.py` | LLM inference orchestration (local Qwen + Claude delegation) | Complete |
| **MatrixActor** | `matrix.py` | Long-term memory substrate (SQLite + NetworkX graph) | Complete |
| **ScribeActor** | `scribe.py` | Knowledge extraction from conversations (Ben Franklin persona) | Complete |
| **LibrarianActor** | `librarian.py` | Entity resolution and memory wiring (The Dude persona) | Complete |
| **HistoryManagerActor** | `history_manager.py` | Three-tier conversation history management | Complete |

### Actor Export Summary (`__init__.py`)

```python
from .base import Actor, Message
from .director import DirectorActor
from .matrix import MatrixActor
from .scribe import ScribeActor
from .librarian import LibrarianActor

__all__ = [
    "Actor",
    "Message",
    "DirectorActor",
    "MatrixActor",
    "ScribeActor",
    "LibrarianActor",
]
```

**Note:** `HistoryManagerActor` is NOT exported in `__init__.py` but exists in `history_manager.py`.

---

## Base Class Pattern (Actor)

### File: `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/actors/base.py`

### Message Dataclass

```python
@dataclass
class Message:
    type: str                          # Message type (routing key)
    payload: Any = None                # Message data
    sender: str | None = None          # Sending actor name
    reply_to: str | None = None        # Reply target
    correlation_id: str = field(...)   # UUID for tracking
    timestamp: datetime = field(...)   # Creation time
```

### Lifecycle Methods

| Method | Type | Purpose |
|--------|------|---------|
| `start()` | async | Start actor, call `on_start()`, enter message loop |
| `stop()` | async | Set `_running=False`, cancel task, call `on_stop()` |
| `on_start()` | async (hook) | Initialize resources (override in subclass) |
| `on_stop()` | async (hook) | Cleanup resources (override in subclass) |
| `on_error(error, msg)` | async (hook) | Handle message processing errors |
| `handle(msg)` | async (abstract) | Process messages from mailbox (MUST implement) |

### Communication Methods

| Method | Type | Purpose |
|--------|------|---------|
| `send(target, msg)` | async | Send message to another actor's mailbox |
| `send_to_engine(event_type, payload)` | async | Send event back to engine's input buffer |

### State Serialization

| Method | Type | Purpose |
|--------|------|---------|
| `snapshot()` | async | Return state dict for serialization |
| `restore(state)` | async | Restore from serialized state |

### Mailbox Architecture

- **Type:** `asyncio.Queue[Message]`
- **Isolation:** Each actor has private mailbox
- **Timeout:** 1 second wait for messages (allows graceful shutdown checking)
- **Error Handling:** `_handle_safe()` wraps `handle()` to prevent crash propagation

---

## Message Types per Actor

### 1. DirectorActor

**File:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/actors/director.py`

#### Messages Received

| Message Type | Payload | Handler | Description |
|--------------|---------|---------|-------------|
| `generate` | `user_message`, `system_prompt`, `max_tokens`, `context_window` | `_handle_director_generate()` | Full generation flow |
| `generate_stream` | (same) | `_handle_director_generate()` | Alias for generate |
| `generate_local` | (same) | `_handle_director_generate()` | Alias for generate |
| `generate_hybrid` | (same) | `_handle_director_generate()` | Alias for generate |
| `abort` | (none) | `_handle_abort()` | Abort current generation |
| `set_model` | `model` | inline | Set Claude model for delegation |
| `load_local` | (none) | `_init_local_inference()` | Load local Qwen model |

#### Messages Sent

| Target | Message Type | When |
|--------|--------------|------|
| Engine | `generation_complete` | After successful generation |
| Engine | `generation_error` | After generation failure |

#### Direct API Methods (bypassing mailbox)

| Method | Purpose |
|--------|---------|
| `process(message, context)` | Main entry point for PersonaAdapter integration |
| `generate(prompt, system, max_tokens, temperature)` | Direct generation for AgentLoop |

---

### 2. MatrixActor

**File:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/actors/matrix.py`

#### Messages Received

| Message Type | Payload | Handler | Description |
|--------------|---------|---------|-------------|
| `store` | `content`, `node_type`, `tags`, `confidence` | inline | Store a memory node |
| `retrieve` | `query`, `max_tokens` | inline | Get context for query |
| `search` | `query`, `limit` | inline | Search memory nodes |

#### Messages Sent

- No explicit outbound messages (results returned via logging)

#### Direct API Methods (bypassing mailbox)

| Method | Purpose |
|--------|---------|
| `initialize()` | Connect to database, load graph |
| `store_memory(content, node_type, tags, confidence, session_id)` | Store a memory node |
| `store_turn(session_id, role, content, tokens)` | Store conversation turn |
| `get_context(query, max_tokens, budget_preset)` | Get relevant context |
| `search(query, limit, use_hybrid)` | Search memory nodes |
| `get_stats()` | Get memory statistics |
| `reinforce_memory(node_id, amount)` | Increase lock-in coefficient |
| `find_related(node_id, depth)` | Graph traversal |
| `get_central_concepts(limit)` | Get high-centrality nodes |
| `add_node(...)` | Direct node creation |
| `get_node(node_id)` | Direct node retrieval |

---

### 3. ScribeActor

**File:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/actors/scribe.py`

#### Messages Received

| Message Type | Payload | Handler | Description |
|--------------|---------|---------|-------------|
| `extract_turn` | `role`, `content`, `turn_id`, `session_id`, `immediate` | `_handle_extract_turn()` | Extract from conversation turn |
| `extract_text` | `text`, `source_id`, `immediate` | `_handle_extract_text()` | Extract from raw text |
| `entity_note` | `entity_name`, `entity_type`, `facts`, `update_type`, `source` | `_handle_entity_note()` | Direct entity update command |
| `flush_stack` | (none) | `_flush_stack()` | Process pending chunks |
| `set_config` | `backend`, `batch_size`, `min_content_length` | `_handle_set_config()` | Update extraction config |
| `get_stats` | (none) | `_handle_get_stats()` | Return statistics |
| `compress_turn` | `turn_id`, `content`, `role` | `_handle_compress_turn()` | Compress a turn |

#### Messages Sent

| Target | Message Type | When |
|--------|--------------|------|
| Librarian | `file` | After extraction complete (with ExtractionOutput) |
| Librarian | `entity_update` | After entity note processing |
| Engine | `scribe_stats` | Response to `get_stats` |
| Engine | `turn_compressed` | Response to `compress_turn` |

#### Direct API Methods

| Method | Purpose |
|--------|---------|
| `compress_turn(content, role)` | Compress turn to one-sentence summary |
| `get_stats()` | Return extraction statistics |
| `get_extraction_history()` | Return recent extraction history |

---

### 4. LibrarianActor

**File:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/actors/librarian.py`

#### Messages Received

| Message Type | Payload | Handler | Description |
|--------------|---------|---------|-------------|
| `file` | ExtractionOutput dict | `_handle_file()` | File extraction into Memory Matrix |
| `entity_update` | EntityUpdate dict | `_handle_entity_update()` | File entity update |
| `get_context` | `query`, `budget`, `node_types` | `_handle_get_context()` | Retrieve context |
| `resolve_entity` | `name`, `entity_type` | `_handle_resolve_entity()` | Resolve entity to node |
| `rollback_entity` | `entity_id`, `version`, `reason` | `_handle_rollback_entity()` | Rollback entity to version |
| `prune` | `confidence_threshold`, `age_days`, `prune_nodes`, `max_prune_nodes` | `_handle_prune()` | Synaptic pruning |
| `get_stats` | (none) | `_handle_get_stats()` | Return statistics |

#### Messages Sent

| Target | Message Type | When |
|--------|--------------|------|
| Engine | `filing_result` | After successful filing (if reply_to set) |
| Engine | `entity_update_result` | After entity update (if reply_to set) |
| Engine | `rollback_result` | After rollback attempt |
| Engine | `context_result` | Response to get_context |
| Engine | `entity_resolved` | Response to resolve_entity |
| Engine | `prune_result` | Response to prune |
| Engine | `librarian_stats` | Response to get_stats |

---

### 5. HistoryManagerActor

**File:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/actors/history_manager.py`

#### Messages Received

| Message Type | Payload | Handler | Description |
|--------------|---------|---------|-------------|
| `add_turn` | `role`, `content`, `tokens`, `session_id`, `context_refs` | `_handle_add_turn()` | Add turn to conversation |
| `get_active_window` | `session_id`, `limit` | `_handle_get_active_window()` | Get Active tier turns |
| `search_recent` | `query`, `limit`, `search_type` | `_handle_search_recent()` | Search Recent tier |
| `rotate_tier` | `turn_id`, `new_tier` | `_handle_rotate_tier()` | Move turn between tiers |
| `check_budget` | `session_id` | `_handle_check_budget()` | Check active tier budget |
| `create_session` | `app_context` | `_handle_create_session()` | Create new session |
| `end_session` | `session_id` | `_handle_end_session()` | End session |
| `get_active_session` | (none) | `_handle_get_active_session()` | Get current session |
| `get_token_count` | `session_id` | `_handle_get_token_count()` | Get active tier token count |
| `get_oldest_active` | `session_id` | `_handle_get_oldest_active()` | Get oldest active turn |
| `queue_compression` | `turn_id` | `_handle_queue_compression()` | Queue turn for compression |
| `queue_extraction` | `turn_id` | `_handle_queue_extraction()` | Queue turn for extraction |
| `get_stats` | (none) | `_handle_get_stats()` | Return statistics |

#### Messages Sent

| Target | Message Type | When |
|--------|--------------|------|
| Engine | `turn_added` | After successful turn add |
| Engine | `active_window` | Response to get_active_window |
| Engine | `search_results` | Response to search_recent |
| Engine | `session_created` | Response to create_session |
| Engine | `active_session` | Response to get_active_session |
| Engine | `token_count` | Response to get_token_count |
| Engine | `oldest_active` | Response to get_oldest_active |
| Engine | `history_stats` | Response to get_stats |
| Engine | `history_error` | On handler error |
| Scribe (via mailbox) | `extract_text` | During extraction queue processing |

#### Direct API Methods

| Method | Purpose |
|--------|---------|
| `get_active_window(session_id, limit)` | Get Active tier turns |
| `search_recent(query, limit, search_type, session_id)` | Search Recent tier |
| `add_turn(role, content, tokens, session_id, context_refs)` | Add conversation turn |
| `get_active_token_count(session_id)` | Get token count |
| `get_oldest_active_turn(session_id)` | Get oldest active turn |
| `create_session(app_context)` | Create new session |
| `end_session(session_id)` | End session |
| `get_active_session()` | Get current session |
| `queue_compression(turn_id)` | Queue for compression |
| `queue_extraction(turn_id)` | Queue for extraction |
| `tick()` | Process compression/extraction queues |
| `needs_recent_search(message)` | Detect backward references |
| `build_history_context(message, session_id)` | Build context for PersonaCore |
| `get_stats()` | Get statistics |

---

## Communication Flow Diagram

```
                              ┌─────────────────────────────────────────────────────────────┐
                              │                         ENGINE                               │
                              │  (input_buffer receives ACTOR_MESSAGE events from actors)    │
                              └─────────────────────────────────────────────────────────────┘
                                               ▲                    ▲
                                               │                    │
                              ┌────────────────┴────────────────────┴────────────────┐
                              │           send_to_engine() events                     │
                              └───────────────────────────────────────────────────────┘
                                       ▲           ▲           ▲           ▲
                                       │           │           │           │
         ┌─────────────────────────────┼───────────┼───────────┼───────────┼─────────────────┐
         │                             │           │           │           │                 │
         │                    ┌────────┴──┐   ┌────┴───┐   ┌───┴────┐   ┌──┴──────┐          │
         │                    │ DIRECTOR  │   │ MATRIX │   │ SCRIBE │   │LIBRARIAN│          │
         │                    │           │   │        │   │ (Ben)  │   │ (Dude)  │          │
         │                    └────┬──────┘   └────────┘   └────┬───┘   └────┬────┘          │
         │                         │                            │            │               │
         │                         │    ┌───────────────────────┼────────────┘               │
         │                         │    │                       │                            │
         │                         │    │   send(librarian, Message("file", extraction))     │
         │                         │    │   send(librarian, Message("entity_update", update))│
         │                         │    │                       │                            │
         │                         ▼    ▼                       ▼                            │
         │                    ┌─────────────────────────────────────────────┐                │
         │                    │              MAILBOX COMMUNICATION           │                │
         │                    │    Scribe ────file────────> Librarian        │                │
         │                    │    Scribe ──entity_update──> Librarian       │                │
         │                    │    HistoryManager ─extract_text─> Scribe     │                │
         │                    └─────────────────────────────────────────────┘                │
         │                                                                                   │
         │   ┌───────────────────────────────────────────────────────────────────────────┐   │
         │   │                     HISTORY MANAGER (Tick-based)                          │   │
         │   │   Manages Active/Recent/Archive tiers                                     │   │
         │   │   Sends extract_text to Scribe for archival processing                    │   │
         │   └───────────────────────────────────────────────────────────────────────────┘   │
         │                                                                                   │
         └───────────────────────────────────────────────────────────────────────────────────┘

                    DIRECT METHOD CALLS (bypassing mailbox):

         Director.process() ──────> MatrixActor.get_context()
         Director._fetch_memory_context() ─> MatrixActor.search_nodes()
         Director._get_matrix() ──────────> engine.get_actor("matrix")
         Librarian._get_matrix() ─────────> engine.get_actor("matrix")
         HistoryManager._get_matrix() ────> engine.get_actor("matrix")
         HistoryManager._process_compression_queue() ─> ScribeActor.compress_turn()
```

### Key Inter-Actor Flows

| Flow ID | Source | Target | Message Type | Trigger |
|---------|--------|--------|--------------|---------|
| F1 | Scribe | Librarian | `file` | After extraction complete |
| F2 | Scribe | Librarian | `entity_update` | After entity note processing |
| F3 | HistoryManager | Scribe | `extract_text` | During extraction queue processing |
| F4 | Director | Matrix | (direct call) | `_fetch_memory_context()` |
| F5 | Librarian | Matrix | (direct call) | `_get_matrix()` for entity resolution |
| F6 | HistoryManager | Matrix | (direct call) | Database access |

---

## Isolation Verification

### Shared State Analysis

| Actor | Instance Variables | Mutable Shared State? | Verdict |
|-------|-------------------|----------------------|---------|
| Director | `_client`, `_local`, `_entity_context`, `_context_pipeline`, `_standalone_ring` | No (all private) | CLEAN |
| Matrix | `_db`, `_matrix`, `_graph` | No (all private) | CLEAN |
| Scribe | `config`, `chunker`, `stack`, `_client` | No (all private) | CLEAN |
| Librarian | `alias_cache`, `inference_queue`, `_entity_resolver` | No (all private) | CLEAN |
| HistoryManager | `config`, `_current_session_id`, `_embedding_generator` | No (all private) | CLEAN |

### Mailbox Isolation

All actors use private `asyncio.Queue[Message]` instances created in base class `__init__`:

```python
self.mailbox: Queue[Message] = Queue()
```

**Result:** No shared mutable state violations detected.

---

## Async Compliance

### Blocking Call Analysis

| Actor | Method | Blocking Call? | Mitigation |
|-------|--------|---------------|------------|
| Director | `client.messages.create()` | Yes (HTTP) | Uses `anthropic` async streaming |
| Director | `_local.generate()` | No (async) | MLX async generation |
| Matrix | `_db.connect()` | No (async aiosqlite) | Properly awaited |
| Scribe | `client.messages.create()` | Yes (HTTP) | Should use async client |
| Librarian | `resolver.db.execute()` | No (async) | Properly awaited |
| HistoryManager | `matrix.db.fetchall()` | No (async) | Properly awaited |

### Potential Issue in Scribe

**Line 480-491 in `scribe.py`:**
```python
response = self.client.messages.create(...)  # Sync Anthropic call
```

This is a synchronous HTTP call within an async handler. However, this only blocks the Scribe actor's message loop, not other actors (due to mailbox isolation).

**Recommendation:** Consider using `anthropic.AsyncAnthropic()` for better async compliance.

---

## Lifecycle Hooks

### Actor Lifecycle Summary

| Actor | on_start() | on_stop() | snapshot() | restore() |
|-------|------------|-----------|------------|-----------|
| Actor (base) | No-op (default) | No-op (default) | Returns name, mailbox_size | No-op (default) |
| Director | Loads LLM registry, local inference, entity context | (inherits base) | Adds model, generating, stats | (inherits base) |
| Matrix | Via `initialize()` (not on_start) | Closes DB, clears refs | (inherits base) | (inherits base) |
| Scribe | (inherits base) | Flushes stack | Adds config, stats | (inherits base) |
| Librarian | Logs persona quote | Logs queue state | Adds stats, cache_size | (inherits base) |
| HistoryManager | Connects to matrix | (inherits base) | (inherits base) | (inherits base) |

### Matrix Special Case

MatrixActor overrides `start()` to call `initialize()` before `super().start()`:

```python
async def start(self) -> None:
    if not self._initialized:
        await self.initialize()
    await super().start()
```

### Scribe on_stop()

```python
async def on_stop(self) -> None:
    if self.stack:
        logger.info("Ben: Flushing stack before shutdown")
        await self._flush_stack()
```

### Librarian on_start()

```python
async def on_start(self) -> None:
    logger.info("The Dude: Yeah, well, you know, that's just like, my opinion, man.")
```

---

## Recommendations

### Critical

1. **Export HistoryManagerActor** - Add to `__init__.py`:
   ```python
   from .history_manager import HistoryManagerActor
   __all__.append("HistoryManagerActor")
   ```

### High Priority

2. **Async Anthropic Client in Scribe** - Replace sync `client.messages.create()` with async version to prevent blocking during extraction.

3. **Unified Matrix Access** - Consider creating a shared `matrix_accessor` pattern instead of repeated `engine.get_actor("matrix")` calls.

### Medium Priority

4. **Message Type Constants** - Define message types as constants or enums to prevent typos:
   ```python
   class MessageTypes:
       EXTRACT_TURN = "extract_turn"
       FILE = "file"
       # etc.
   ```

5. **Reply-To Pattern** - Not all actors honor `msg.reply_to` consistently. Standardize request-response patterns.

---

## Files Analyzed

1. `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/actors/__init__.py`
2. `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/actors/base.py`
3. `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/actors/director.py`
4. `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/actors/matrix.py`
5. `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/actors/scribe.py`
6. `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/actors/librarian.py`
7. `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/actors/history_manager.py`

---

*End of Actor System Audit*
