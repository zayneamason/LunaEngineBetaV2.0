# Part VI-B: Conversation Tiers

**Version:** 3.0
**Last Updated:** 2026-01-30
**Status:** Implemented
**Implementation:** `src/luna/actors/history_manager.py`, `src/luna/memory/ring.py`

---

## Overview

Luna's conversation system uses a **three-tier memory model** that provides:

1. **Guaranteed continuity** through an always-loaded Active Window
2. **Smart retrieval** of recent context via hybrid search
3. **Long-term memory** through Memory Matrix integration
4. **Token efficiency** through intelligent compression

This system is managed by the **HistoryManagerActor**, which operates within Luna Engine's tick-based actor model.

---

## The Three-Tier Model

```
+-------------------------------------------------------------+
|  TIER 1: ACTIVE WINDOW                                      |
|  ---------------------                                      |
|  - Last 5-10 turns (full text)                              |
|  - Always loaded into context                               |
|  - Ring buffer, FIFO rotation                               |
|  - Budget: ~1000 tokens max                                 |
|  - Guarantees conversational continuity                     |
+-------------------------------------------------------------+
                        | (as window slides)
                        v
+-------------------------------------------------------------+
|  TIER 2: RECENT BUFFER                                      |
|  ----------------------                                     |
|  - Last 50-100 turns (compressed summaries)                 |
|  - Searchable via FTS5 + sqlite-vec                         |
|  - Retrieved on-demand when referenced                      |
|  - Budget: ~500-1500 tokens when loaded                     |
|  - Handles "what did we just discuss?" queries              |
+-------------------------------------------------------------+
                        | (after age threshold: 60 minutes)
                        v
+-------------------------------------------------------------+
|  TIER 3: ARCHIVE (Memory Matrix)                            |
|  --------------------------------                           |
|  - All history older than Recent Buffer                     |
|  - Extracted into semantic memory nodes                     |
|  - Full Memory Matrix search capabilities                   |
|  - Infinite retention with smart retrieval                  |
|  - Accessed via existing smart_fetch                        |
+-------------------------------------------------------------+
```

---

## Configuration

The HistoryManager is configured via `HistoryConfig`:

```python
@dataclass
class HistoryConfig:
    max_active_tokens: int = 1000        # Token budget for Active tier
    max_active_turns: int = 10           # Hard limit on turn count
    max_recent_age_minutes: int = 60     # Age threshold for archival
    compression_enabled: bool = True     # Enable Scribe compression
    default_search_limit: int = 3        # Results per search
    search_type: str = "hybrid"          # "hybrid", "keyword", or "semantic"
    app_context: str = "terminal"        # Current interface
```

**Verified from code:** These defaults match `src/luna/actors/history_manager.py` lines 41-49.

### Token Budgets

| Tier | Token Budget | Turns | Purpose |
|------|--------------|-------|---------|
| Active | 1000 tokens max | 10 max | Guaranteed continuity |
| Recent | ~500-1500 tokens | 50-100 compressed | Conditional search results |
| Archive | Via Memory Matrix | Unlimited | Long-term semantic storage |

### Rotation Triggers

Rotation from Active to Recent occurs when **either**:
- `total_tokens > max_active_tokens` (1000)
- `turn_count > max_active_turns` (10)

---

## Tier Rotation Process

### Active to Recent Rotation

Rotation triggers when the Active tier exceeds budget constraints:

```
1. add_turn() called
2. Check budget: total_tokens > max_active_tokens OR turn_count > max_active_turns
3. Find oldest Active turn
4. Update tier = 'recent'
5. Queue for compression (if enabled)
6. Continue until budget satisfied
```

### Recent to Archive Rotation

Archive rotation triggers based on age:

```
1. tick() called every 500ms-1s
2. Find Recent turns where:
   - compressed IS NOT NULL
   - compressed_at < (now - max_recent_age_minutes)
   - archived_at IS NULL
3. Queue for extraction
4. Scribe extracts semantic nodes
5. Librarian files to Memory Matrix
6. Mark tier = 'archived'
```

---

## Compression Pipeline

When turns rotate from Active to Recent, they enter the compression queue:

1. **HistoryManager** queues turn for compression
2. **Scribe (Ben Franklin)** compresses via `compress_turn(content, role)`
3. Compressed summary stored in `conversation_turns.compressed`
4. **Embedding generated** for semantic search capability
5. Compression marked complete

### Compression Prompt (Scribe)

```
Extract the essence of this conversation turn.

Instructions:
- Identify the key decision, fact, or topic discussed
- Compress to one sentence, under 50 words
- Focus on what was decided, learned, or asked
- Preserve any specific names, numbers, or decisions
- Use past tense
```

---

## Search Capabilities

### Hybrid Search (Default)

The Recent tier supports three search modes:

| Mode | Method | Use Case |
|------|--------|----------|
| `keyword` | FTS5 full-text search | Exact phrase matching |
| `semantic` | sqlite-vec vector similarity | Conceptual similarity |
| `hybrid` | FTS5 + sqlite-vec combined | Best of both |

### Backward Reference Detection

The system automatically detects when a user references recent conversation:

```python
backward_markers = [
    "earlier", "before", "ago", "just",
    "we discussed", "you said", "you mentioned", "you told",
    "what did", "when did", "why did",
    "last time", "previously", "remember when",
    "what we", "as we", "like we"
]
```

When detected, Recent tier is searched and results injected into context.

---

## ConversationRing Integration

The **ConversationRing** (`src/luna/memory/ring.py`) provides a guaranteed working memory buffer that operates independently of the tier system:

```python
class ConversationRing:
    """
    Fixed-size ring buffer for conversation history.

    Guarantees:
    - Last N turns are always available
    - O(1) insert and eviction
    - Cannot be displaced by retrieval
    - FIFO eviction (oldest falls off naturally)
    """

    def __init__(self, max_turns: int = 6):
        self._buffer: deque = deque(maxlen=max_turns)
        self._max_turns = max_turns
```

### Ring Buffer Properties

| Property | Value | Purpose |
|----------|-------|---------|
| `max_turns` | 6 (default) | 3 conversation exchanges |
| Eviction | FIFO automatic | Oldest turn drops when full |
| Persistence | In-memory only | Fast access for Director |

**Verified from code:**
- `src/luna/memory/ring.py` line 43: `def __init__(self, max_turns: int = 6)`
- `src/luna/context/pipeline.py` line 110: `ConversationRing(max_turns=max_ring_turns)`
- `src/luna/actors/director.py` line 141: `ConversationRing(max_turns=6)`

### Key Principle

> **Ring fills FIRST. Retrieval gets leftovers. History can never be displaced.**

The ConversationRing is structurally prior to Memory Matrix retrieval in context building. This ensures conversational continuity is never sacrificed for memory retrieval.

---

## Database Schema

### conversation_turns Table

```sql
CREATE TABLE IF NOT EXISTS conversation_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    compressed TEXT,
    tokens INTEGER NOT NULL,
    tier TEXT NOT NULL CHECK(tier IN ('active', 'recent', 'archived')) DEFAULT 'active',
    context_refs TEXT,
    created_at DATETIME,
    compressed_at REAL,
    archived_at REAL,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
```

### history_fts Virtual Table (FTS5)

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS history_fts USING fts5(
    compressed,
    content=conversation_turns,
    content_rowid=turn_id,
    tokenize='porter unicode61'
);
```

### history_embeddings Virtual Table (sqlite-vec)

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS history_embeddings USING vec0(
    turn_id INTEGER PRIMARY KEY,
    embedding FLOAT[1536]  -- text-embedding-3-small dimensions
);
```

---

## Message Types

The HistoryManagerActor handles these message types:

| Type | Purpose | Payload |
|------|---------|---------|
| `add_turn` | Add conversation turn | `{role, content, tokens, session_id}` |
| `get_active_window` | Get Active tier | `{session_id, limit}` |
| `search_recent` | Search Recent tier | `{query, limit, search_type}` |
| `rotate_tier` | Move turn to tier | `{turn_id, tier}` |
| `check_budget` | Check rotation needed | `{session_id}` |
| `queue_compression` | Queue for Scribe | `{turn_id}` |
| `queue_extraction` | Queue for archival | `{turn_id}` |
| `create_session` | Start new session | `{app_context}` |
| `end_session` | End current session | `{session_id}` |

---

## Actor Integration

### Flow: User Message to History

```
1. Engine receives user input
2. Engine calls HistoryManager.add_turn(role="user", content=message)
3. HistoryManager inserts into conversation_turns (tier='active')
4. HistoryManager checks budget, rotates if needed
5. Director generates response
6. Engine calls HistoryManager.add_turn(role="assistant", content=response)
```

### Flow: Context Building

```
1. PersonaCore builds context for Director
2. HistoryManager.get_active_window() returns Active tier
3. If backward reference detected:
   - HistoryManager.search_recent(query) returns relevant Recent turns
4. Context assembled: Active history + Recent results + Memory Matrix
```

### Tick Processing

```python
async def tick(self) -> None:
    """Called every 500ms-1s by engine."""
    await self._process_compression_queue()  # One per tick
    await self._process_extraction_queue()   # One per tick
    await self._check_archivable_turns()     # Age-based archival
```

---

## Performance Targets

| Operation | Target | Notes |
|-----------|--------|-------|
| Add turn | <5ms | Simple INSERT |
| Get active window | <10ms | 10 row SELECT |
| Search recent (keyword) | <50ms | FTS5 query |
| Search recent (hybrid) | <150ms | FTS5 + vector |
| Compress turn | <500ms | Local LLM inference |
| Extract turn | <1500ms | Full Memory Matrix extraction |

---

## Statistics

The HistoryManager tracks operational statistics:

```python
{
    "turns_added": 42,
    "rotations": 12,
    "compressions_queued": 10,
    "extractions_queued": 5,
    "embeddings_generated": 8,
    "searches_performed": 15,
    "current_session": "uuid-string",
    "is_ready": True
}
```

---

## Session Management

Sessions group conversation turns by interaction period:

```python
# Create session
session_id = await history_manager.create_session(app_context="terminal")

# End session
await history_manager.end_session(session_id)

# Get active session
session = await history_manager.get_active_session()
```

### Session Lifecycle

```
create_session() -> session active
    |
    v
add_turn() ... add_turn()  (conversation)
    |
    v
end_session() -> session closed
```

---

## Relationship to Other Actors

| Actor | Relationship |
|-------|--------------|
| **Director** | Reads ConversationRing for immediate context |
| **Scribe** | Compresses turns, extracts for archival |
| **Librarian** | Files extracted nodes to Memory Matrix |
| **Matrix** | Provides database access, stores archived content |

---

## Key Design Principles

1. **Guaranteed Continuity**: Active Window is always loaded, never displaced
2. **Token Efficiency**: Compression reduces storage while preserving meaning
3. **Graceful Degradation**: Falls back to simpler search if vector fails
4. **Sovereignty**: All data stored locally in SQLite
5. **Tick-Based Processing**: One compression/extraction per tick prevents blocking

---

## Implementation Files

| File | Purpose |
|------|---------|
| `src/luna/actors/history_manager.py` | HistoryManagerActor implementation |
| `src/luna/memory/ring.py` | ConversationRing buffer |
| `src/luna/actors/scribe.py` | Compression via Ben Franklin |
| `src/luna/substrate/database.py` | SQLite schema and queries |

---

## References

- **Part III**: Memory Matrix (Archive tier destination)
- **Part IV**: The Scribe (Compression pipeline)
- **Part V**: The Librarian (Filing extracted nodes)
- **Part VII**: Runtime Engine (Tick-based actor model)

## Integration with Director LLM

The conversation tier system integrates with the Director's context building:

### Context Pipeline Flow

```
1. ContextPipeline.build_context(message)
   ├─ ConversationRing provides immediate history (6 turns)
   ├─ HistoryManager.get_active_window() provides Active tier
   ├─ If backward reference detected:
   │   └─ HistoryManager.search_recent() provides relevant Recent turns
   └─ Memory Matrix provides long-term context
```

### Token Budget Distribution

| Component | Budget | Priority |
|-----------|--------|----------|
| ConversationRing | ~400 tokens | Highest (never displaced) |
| Active Window | ~1000 tokens | High |
| Recent Search Results | ~500-1500 tokens | Conditional |
| Memory Matrix Retrieval | Remaining budget | Lowest |

### Self-Routing Optimization

The ContextPipeline uses a **self-routing** flag to skip redundant memory retrieval:

```python
# If topic is already in the ring buffer, skip memory lookup
if topic_in_ring:
    used_retrieval = False
```

This prevents unnecessary database queries when the conversation context is sufficient.

---

*Conversation is the thread. Memory is the tapestry.*
*The tiers ensure Luna never forgets the moment while preserving the whole.*

--- Ahab, January 2026
