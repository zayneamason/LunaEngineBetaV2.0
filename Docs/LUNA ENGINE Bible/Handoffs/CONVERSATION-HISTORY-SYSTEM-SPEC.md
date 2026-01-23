# Conversation History System - Implementation Specification

**Status:** Ready for Implementation  
**Target:** Claude Code  
**Date:** January 20, 2026  
**Architecture Compliance:** Luna Engine v2.1

---

## 1. Executive Summary

This specification defines a **three-tier conversation history management system** for Luna Engine that provides:

- **Guaranteed continuity** through an always-loaded Active Window
- **Smart retrieval** of recent context via hybrid search
- **Long-term memory** through Memory Matrix integration
- **Token efficiency** through intelligent compression
- **Sovereignty** through local SQLite storage

**Critical Design Principle:** This system operates within Luna Engine's **tick-based actor model** and communicates exclusively through the **Hub API abstraction layer**. No direct database access from the engine.

---

## 2. The Three-Tier Model

```
┌─────────────────────────────────────────────────────────────┐
│  TIER 1: ACTIVE WINDOW                                      │
│  ─────────────────────                                      │
│  • Last 5-10 turns (full text)                              │
│  • Always loaded into context                               │
│  • Ring buffer, FIFO rotation                               │
│  • Budget: ~800-1000 tokens max                             │
│  • Guarantees conversational continuity                     │
└─────────────────────────────────────────────────────────────┘
                        ↓ (as window slides)
┌─────────────────────────────────────────────────────────────┐
│  TIER 2: RECENT BUFFER                                      │
│  ──────────────────────                                     │
│  • Last 50-100 turns (compressed summaries)                 │
│  • Searchable via FTS5 + sqlite-vec                         │
│  • Retrieved on-demand when referenced                      │
│  • Budget: ~400-600 tokens when loaded                      │
│  • Handles "what did we just discuss?" queries              │
└─────────────────────────────────────────────────────────────┘
                        ↓ (after session ends or age threshold)
┌─────────────────────────────────────────────────────────────┐
│  TIER 3: ARCHIVE (Memory Matrix)                            │
│  ────────────────────────────────                           │
│  • All history older than Recent Buffer                     │
│  • Extracted into semantic memory nodes                     │
│  • Full Memory Matrix search capabilities                   │
│  • Infinite retention with smart retrieval                  │
│  • Accessed via existing smart_fetch                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Database Schema

### 3.1 New Tables

**IMPORTANT:** These tables are added to the existing `memory_matrix.db` (Luna's soul file), NOT a separate database.

```sql
-- ============================================================================
-- CONVERSATION HISTORY SCHEMA
-- Location: memory_matrix.db (inside LunaVault.sparsebundle)
-- ============================================================================

-- Session tracking
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    started_at REAL NOT NULL,              -- Unix timestamp
    ended_at REAL,                          -- NULL while active
    app_context TEXT NOT NULL,              -- 'terminal', 'voice', 'mobile', etc.
    metadata TEXT,                          -- JSON: additional context
    
    -- Indexes
    INDEX idx_session_active (ended_at)     -- Fast "get active session" query
);

-- Conversation turns with tiered storage
CREATE TABLE IF NOT EXISTS conversation_turns (
    turn_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp REAL NOT NULL,                -- Unix timestamp
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,                  -- Full text (always preserved)
    compressed TEXT,                        -- Ben Franklin's summary (NULL until compressed)
    tokens INTEGER NOT NULL,                -- For budget management
    tier TEXT NOT NULL CHECK(tier IN ('active', 'recent', 'archived')) DEFAULT 'active',
    
    -- Metadata
    context_refs TEXT,                      -- JSON: which memories/entities were active
    compressed_at REAL,                     -- When Ben compressed it
    archived_at REAL,                       -- When extracted to Memory Matrix
    
    -- Foreign key
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
    
    -- Indexes for common queries
    INDEX idx_tier_timestamp (tier, timestamp DESC),
    INDEX idx_session_tier (session_id, tier),
    INDEX idx_session_timestamp (session_id, timestamp DESC)
);

-- Full-text search on compressed summaries (Tier 2 search)
CREATE VIRTUAL TABLE IF NOT EXISTS history_fts USING fts5(
    compressed,
    content=conversation_turns,
    content_rowid=turn_id,
    tokenize='porter unicode61'
);

-- Triggers to keep FTS in sync
CREATE TRIGGER IF NOT EXISTS history_fts_insert AFTER INSERT ON conversation_turns BEGIN
    INSERT INTO history_fts(rowid, compressed) VALUES (new.turn_id, new.compressed);
END;

CREATE TRIGGER IF NOT EXISTS history_fts_update AFTER UPDATE ON conversation_turns BEGIN
    UPDATE history_fts SET compressed = new.compressed WHERE rowid = new.turn_id;
END;

CREATE TRIGGER IF NOT EXISTS history_fts_delete AFTER DELETE ON conversation_turns BEGIN
    DELETE FROM history_fts WHERE rowid = old.turn_id;
END;

-- Vector embeddings for semantic search (Tier 2 search)
-- Uses existing sqlite-vec extension
CREATE VIRTUAL TABLE IF NOT EXISTS history_embeddings USING vec0(
    turn_id INTEGER PRIMARY KEY,
    embedding FLOAT[1024]                   -- Match your embedding model dimensions
);
```

### 3.2 Schema Migration Notes

- These tables integrate with the existing `memory_matrix.db`
- Session IDs are UUIDs (generate client-side)
- All timestamps are Unix timestamps (REAL type for subsecond precision)
- CASCADE DELETE ensures cleanup when sessions are deleted
- FTS5 and sqlite-vec provide hybrid search for Tier 2

---

## 4. Hub API Extensions

### 4.1 New Endpoints Required

The Hub API must expose the following endpoints for the Runtime Engine to call. These abstract all SQLite operations.

#### Session Management

```python
# POST /history/session/create
{
    "app_context": "terminal"  # or "voice", "mobile", etc.
}
→ Returns: {"session_id": "uuid-string", "started_at": 1234567890.123}

# POST /history/session/end
{
    "session_id": "uuid-string"
}
→ Returns: {"ended_at": 1234567890.123}

# GET /history/session/active
→ Returns: {"session_id": "uuid-string", "started_at": ...} or null
```

#### Turn Management

```python
# POST /history/turn/add
{
    "session_id": "uuid-string",
    "role": "user",  # or "assistant", "system"
    "content": "full text of message",
    "tokens": 150
}
→ Returns: {"turn_id": 123, "tier": "active"}

# GET /history/active_window
{
    "session_id": "uuid-string",  # optional: defaults to active session
    "limit": 10                    # optional: max turns to return
}
→ Returns: [
    {
        "turn_id": 123,
        "role": "user",
        "content": "...",
        "timestamp": 1234567890.123
    },
    ...
]

# GET /history/active_token_count
{
    "session_id": "uuid-string"  # optional
}
→ Returns: {"total_tokens": 850, "turn_count": 8}
```

#### Tier Management

```python
# POST /history/tier/rotate
{
    "turn_id": 123,
    "new_tier": "recent"
}
→ Returns: {"success": true}

# GET /history/tier/oldest_active
{
    "session_id": "uuid-string"
}
→ Returns: {"turn_id": 100, "timestamp": ..., "tokens": 80}

# GET /history/tier/uncompressed_recent
{
    "limit": 1
}
→ Returns: [{"turn_id": 95, "content": "..."}]

# GET /history/tier/archivable
{
    "age_minutes": 60,  # Turns older than this
    "limit": 5
}
→ Returns: [{"turn_id": 50, "timestamp": ..., "content": "..."}]
```

#### Search Operations (Tier 2)

```python
# POST /history/search
{
    "query": "observability layer decision",
    "tier": "recent",              # or "active" or "all"
    "session_id": "uuid-string",   # optional: defaults to active
    "limit": 3,
    "search_type": "hybrid"        # or "keyword" or "semantic"
}
→ Returns: [
    {
        "turn_id": 85,
        "role": "user",
        "content": "...",           # Full text
        "compressed": "...",        # Summary
        "relevance_score": 0.92,
        "timestamp": ...
    },
    ...
]
```

#### Compression Queue

```python
# POST /history/compression/queue
{
    "turn_id": 95
}
→ Returns: {"queued": true, "position": 3}

# GET /history/compression/pending
{
    "limit": 10
}
→ Returns: [{"turn_id": 90, "queued_at": ...}, ...]

# POST /history/compression/complete
{
    "turn_id": 90,
    "compressed": "User asked about X, Luna explained Y."
}
→ Returns: {"success": true}
```

#### Extraction Queue (for Memory Matrix archival)

```python
# POST /history/extraction/queue
{
    "turn_id": 50
}
→ Returns: {"queued": true}

# GET /history/extraction/pending
{
    "limit": 10
}
→ Returns: [{"turn_id": 45, "content": "...", "compressed": "..."}]

# POST /history/extraction/complete
{
    "turn_id": 45,
    "extracted_nodes": ["node_id_1", "node_id_2"]  # Memory Matrix node IDs
}
→ Returns: {"success": true, "archived_at": 1234567890.123}
```

### 4.2 Implementation Notes for Hub API

- **Token counting:** Use `tiktoken` (or equivalent) to count tokens accurately
- **Session management:** Track "active session" in Redis or in-memory (single active session per runtime)
- **Compression queue:** Simple FIFO queue, processed by Ben Franklin
- **Extraction queue:** Processed by Ben Franklin → The Dude pipeline
- **Search implementation:** Combine FTS5 (keyword) + sqlite-vec (semantic) for hybrid search

---

## 5. Runtime Engine: HistoryManager Actor

### 5.1 Actor Class Definition

```python
"""
runtime/actors/history_manager.py

The HistoryManager is a tick-based actor that maintains conversation history tiers.
It does NOT handle events directly - it polls the Hub API on each tick.
"""

from typing import List, Dict, Optional
from runtime.core.actor import Actor
from hub.client import HubAPIClient

class HistoryManager(Actor):
    """
    Manages the three-tier conversation history system.
    
    Responsibilities:
    - Monitor Active Window token budget
    - Rotate Active → Recent when budget exceeded
    - Queue compression for Recent turns
    - Queue extraction for archival
    """
    
    def __init__(self, config: HistoryConfig, hub_client: HubAPIClient):
        super().__init__(name="HistoryManager")
        self.config = config
        self.hub = hub_client
        
        # Configuration
        self.max_active_tokens = config.max_active_tokens  # e.g., 1000
        self.max_recent_age_minutes = config.max_recent_age_minutes  # e.g., 60
        self.compression_batch_size = 1  # Process one per tick
        self.extraction_batch_size = 1   # Process one per tick
    
    async def tick(self):
        """
        Called on every cognitive loop cycle (~500ms-1s).
        Checks tier budgets and triggers rotations/processing.
        """
        # 1. Check Active Window budget
        await self._check_active_budget()
        
        # 2. Process compression queue (one per tick)
        await self._process_compression_queue()
        
        # 3. Process extraction queue (one per tick)
        await self._process_extraction_queue()
    
    async def _check_active_budget(self):
        """Rotate oldest Active turn to Recent if budget exceeded."""
        budget = await self.hub.get_active_token_count()
        
        if budget['total_tokens'] > self.max_active_tokens:
            oldest = await self.hub.get_oldest_active_turn()
            if oldest:
                # Rotate to Recent tier
                await self.hub.rotate_turn_tier(
                    turn_id=oldest['turn_id'],
                    new_tier='recent'
                )
                # Queue for compression
                await self.hub.queue_compression(oldest['turn_id'])
    
    async def _process_compression_queue(self):
        """Process one pending compression per tick."""
        pending = await self.hub.get_pending_compressions(limit=1)
        
        if pending:
            turn = pending[0]
            # Delegate to Ben Franklin (via Hub API)
            compressed = await self.hub.invoke_scribe_compression(
                content=turn['content']
            )
            # Mark as compressed
            await self.hub.complete_compression(
                turn_id=turn['turn_id'],
                compressed=compressed
            )
    
    async def _process_extraction_queue(self):
        """Process one pending extraction per tick."""
        pending = await self.hub.get_pending_extractions(limit=1)
        
        if pending:
            turn = pending[0]
            # Delegate to Ben Franklin → The Dude pipeline
            extracted_nodes = await self.hub.invoke_scribe_extraction(
                content=turn['content'],
                compressed=turn['compressed']
            )
            # Mark as archived
            await self.hub.complete_extraction(
                turn_id=turn['turn_id'],
                extracted_nodes=extracted_nodes
            )
    
    # ========================================================================
    # PUBLIC INTERFACE (called by PersonaCore)
    # ========================================================================
    
    async def get_active_window(self) -> List[Dict]:
        """
        Get all Active tier turns for context injection.
        This is called by PersonaCore when building context.
        """
        return await self.hub.get_active_window()
    
    async def search_recent(
        self, 
        query: str, 
        limit: int = 3,
        search_type: str = "hybrid"
    ) -> List[Dict]:
        """
        Search Recent tier for relevant turns.
        Used when PersonaCore detects backward references.
        """
        return await self.hub.search_history(
            query=query,
            tier='recent',
            limit=limit,
            search_type=search_type
        )
    
    async def add_turn(
        self,
        role: str,
        content: str,
        tokens: int,
        context_refs: Optional[Dict] = None
    ) -> int:
        """
        Add a new turn to the conversation.
        Called after user message or Luna response.
        """
        session = await self.hub.get_active_session()
        if not session:
            # Create new session if none active
            session = await self.hub.create_session(
                app_context=self.config.app_context
            )
        
        turn = await self.hub.add_turn(
            session_id=session['session_id'],
            role=role,
            content=content,
            tokens=tokens
        )
        
        return turn['turn_id']
```

### 5.2 Configuration Class

```python
"""
runtime/config/history_config.py
"""

from dataclasses import dataclass

@dataclass
class HistoryConfig:
    """Configuration for conversation history management."""
    
    # Active Window
    max_active_tokens: int = 1000        # Budget for Active tier
    max_active_turns: int = 10           # Hard limit on turn count
    
    # Recent Buffer
    max_recent_age_minutes: int = 60     # Age threshold for archival
    compression_enabled: bool = True     # Enable Ben Franklin compression
    
    # Search
    default_search_limit: int = 3        # Results per search
    search_type: str = "hybrid"          # "hybrid", "keyword", or "semantic"
    
    # App context
    app_context: str = "terminal"        # Current interface
```

### 5.3 Integration with Runtime Engine

```python
"""
runtime/engine.py

Modified to include HistoryManager in actor registry.
"""

class LunaEngine:
    def __init__(self, config: EngineConfig):
        self.config = config
        self.hub_client = HubAPIClient(config.hub_url)
        
        # Actor registry
        self.actors = ActorRegistry()
        
        # Register HistoryManager
        self.history_manager = HistoryManager(
            config=config.history,
            hub_client=self.hub_client
        )
        self.actors.register(self.history_manager)
        
        # ... other actors (Director, Matrix, Voice, etc.)
    
    async def _cognitive_loop(self):
        """
        Main cognitive tick loop.
        All actors get ticked at ~1-2 Hz.
        """
        while True:
            # Tick all actors (including HistoryManager)
            await self.actors.tick_all()
            await asyncio.sleep(self.config.cognitive_interval)
```

---

## 6. PersonaCore Integration

### 6.1 Context Builder Modification

```python
"""
runtime/persona/persona_core.py

Modified to include conversation history in context building.
"""

class PersonaCore:
    def __init__(self, history_manager: HistoryManager):
        self.history_manager = history_manager
        # ... existing init
    
    async def build_enriched_context(
        self,
        message: str,
        auto_fetch: bool = True,
        budget_preset: str = "balanced"
    ) -> EnrichedContext:
        """
        Build the complete context for Luna's response.
        Now includes conversation history alongside memories.
        """
        context = EnrichedContext()
        
        # ====================================================================
        # TIER 1: ACTIVE HISTORY (Always loaded)
        # ====================================================================
        context.active_history = await self.history_manager.get_active_window()
        
        # ====================================================================
        # TIER 2: RECENT HISTORY (Conditional search)
        # ====================================================================
        if self._needs_recent_search(message):
            context.recent_history = await self.history_manager.search_recent(
                query=message,
                limit=3
            )
        
        # ====================================================================
        # TIER 3: LONG-TERM MEMORY (Existing smart fetch)
        # ====================================================================
        if auto_fetch:
            context.memories = await self._smart_fetch(
                query=message,
                budget_preset=budget_preset
            )
        
        # ====================================================================
        # CORE IDENTITY (Existing)
        # ====================================================================
        context.kernel = await self._load_kernel()
        context.virtues = await self._load_virtues()
        
        return context
    
    def _needs_recent_search(self, message: str) -> bool:
        """
        Detect if message references recent past.
        
        Heuristics:
        - Backward reference keywords
        - Questions about previous statements
        - Clarification requests
        
        TODO: Replace with Director LLM intent detection for production.
        """
        backward_markers = [
            "earlier", "before", "ago", "just",
            "we discussed", "you said", "you mentioned", "you told",
            "what did", "when did", "why did",
            "last time", "previously", "remember when"
        ]
        
        message_lower = message.lower()
        return any(marker in message_lower for marker in backward_markers)
```

### 6.2 Context Formatting

```python
"""
runtime/persona/enriched_context.py

Extended to include history in prompt formatting.
"""

@dataclass
class EnrichedContext:
    """Complete context package for Luna's inference."""
    
    # History tiers
    active_history: List[ConversationTurn] = None
    recent_history: List[ConversationTurn] = None
    
    # Memory (existing)
    memories: List[MemoryNode] = None
    
    # Identity (existing)
    kernel: str = None
    virtues: Dict = None
    
    def format_for_prompt(self) -> str:
        """
        Format context into prompt structure.
        Order matters: history before memories for temporal coherence.
        """
        sections = []
        
        # 1. Active conversation history
        if self.active_history:
            sections.append(self._format_active_history())
        
        # 2. Recent relevant history (if searched)
        if self.recent_history:
            sections.append(self._format_recent_history())
        
        # 3. Long-term memories
        if self.memories:
            sections.append(self._format_memories())
        
        # 4. Core identity
        sections.append(self._format_identity())
        
        return "\n\n".join(sections)
    
    def _format_active_history(self) -> str:
        """Format Active Window as conversation thread."""
        lines = ["=== ACTIVE CONVERSATION ==="]
        
        for turn in self.active_history:
            role_label = "You" if turn['role'] == "user" else "Luna"
            lines.append(f"{role_label}: {turn['content']}")
        
        return "\n".join(lines)
    
    def _format_recent_history(self) -> str:
        """Format searched Recent turns with context."""
        lines = ["=== RELEVANT RECENT CONTEXT ==="]
        
        for turn in self.recent_history:
            # Include both compressed summary and full text
            timestamp_str = self._format_timestamp(turn['timestamp'])
            lines.append(f"[{timestamp_str}]")
            lines.append(f"Summary: {turn['compressed']}")
            lines.append(f"Full: {turn['content']}")
            lines.append("")
        
        return "\n".join(lines)
    
    def _format_timestamp(self, unix_ts: float) -> str:
        """Format Unix timestamp as relative time."""
        # TODO: Implement "5 minutes ago" style formatting
        return f"{unix_ts}"  # Placeholder
```

---

## 7. Ben Franklin (The Scribe) Integration

### 7.1 Compression Pipeline

Ben Franklin gets a new responsibility: compressing conversation turns into summaries.

```python
"""
cognitive/scribe.py

Extended with conversation compression capability.
"""

class BenFranklin:
    """The Scribe - extracts and compresses information."""
    
    async def compress_turn(self, content: str) -> str:
        """
        Compress a conversation turn into a one-sentence summary.
        
        Input: Full turn text (user message + Luna response)
        Output: <50 word summary capturing key decision/fact/topic
        
        Example:
        Input: "Can you help me implement the history system?" 
               "Of course, let me explain the three-tier architecture..."
        Output: "User requested help with history system implementation, 
                 Luna explained three-tier architecture approach."
        """
        prompt = f"""Extract the essence of this conversation turn.
        
Turn content:
{content}

Instructions:
- Identify the key decision, fact, or topic discussed
- Compress to one sentence, under 50 words
- Focus on what was decided, learned, or asked
- Preserve any specific names, numbers, or decisions
- Use past tense
- Do not add commentary or interpretation

Compressed summary:"""
        
        # Use local inference (Qwen or similar)
        compressed = await self.local_llm.generate(
            prompt=prompt,
            max_tokens=80,
            temperature=0.3
        )
        
        return compressed.strip()
    
    async def extract_for_archive(
        self, 
        content: str, 
        compressed: str
    ) -> List[str]:
        """
        Extract semantic memory nodes from archived turn.
        
        Input: Full content + compressed summary
        Output: List of Memory Matrix node IDs that were created
        
        This is the bridge between conversation history and Memory Matrix.
        """
        # Use existing extraction pipeline
        extractions = await self.extract_from_text(content)
        
        # Hand to The Dude for filing
        node_ids = await self.librarian.file_extractions(extractions)
        
        return node_ids
```

### 7.2 Hub API Invocation

```python
"""
hub/endpoints/history.py

Hub API endpoints that invoke Ben Franklin for processing.
"""

@app.post("/history/compression/invoke")
async def invoke_compression(request: CompressionRequest):
    """
    Synchronously compress a turn using Ben Franklin.
    Called by HistoryManager during compression queue processing.
    """
    # Get Ben Franklin instance
    scribe = get_scribe_instance()
    
    # Compress
    compressed = await scribe.compress_turn(request.content)
    
    return {"compressed": compressed}

@app.post("/history/extraction/invoke")
async def invoke_extraction(request: ExtractionRequest):
    """
    Extract memory nodes from archived turn.
    Called by HistoryManager during extraction queue processing.
    """
    scribe = get_scribe_instance()
    
    # Extract and file
    node_ids = await scribe.extract_for_archive(
        content=request.content,
        compressed=request.compressed
    )
    
    return {"extracted_nodes": node_ids}
```

---

## 8. Token Budget Management

### 8.1 Budget Allocation Model

```python
"""
runtime/persona/token_budget.py

Dynamic token budget allocation across context components.
"""

@dataclass
class TokenBudget:
    """Token budget allocation for context building."""
    
    # Total available (Claude's context window)
    total: int = 200_000
    
    # Allocations
    system_prompt: int = 10_000      # Safety rules, instructions
    active_history: int = 1_000      # Guaranteed continuity
    recent_history: int = 600        # Conditional search results
    memories: int = 5_000            # Smart fetch results
    identity: int = 1_000            # Kernel + virtues
    reserved_response: int = 4_000   # Luna's response space
    
    # Computed
    @property
    def allocated(self) -> int:
        return (
            self.system_prompt +
            self.active_history +
            self.recent_history +
            self.memories +
            self.identity +
            self.reserved_response
        )
    
    @property
    def remaining(self) -> int:
        return self.total - self.allocated
    
    def validate(self):
        """Ensure budget doesn't exceed total."""
        if self.allocated > self.total:
            raise ValueError(
                f"Budget exceeded: {self.allocated} > {self.total}"
            )
```

### 8.2 Dynamic Budget Adjustment

```python
"""
runtime/persona/persona_core.py

PersonaCore respects token budget when building context.
"""

class PersonaCore:
    async def build_enriched_context(
        self,
        message: str,
        auto_fetch: bool = True,
        budget_preset: str = "balanced"
    ) -> EnrichedContext:
        
        budget = self._get_budget(budget_preset)
        context = EnrichedContext()
        
        # Active history (guaranteed allocation)
        active = await self.history_manager.get_active_window()
        active_tokens = sum(t['tokens'] for t in active)
        
        if active_tokens > budget.active_history:
            # Truncate oldest turns to fit budget
            active = self._truncate_to_budget(active, budget.active_history)
        
        context.active_history = active
        
        # ... rest of context building with budget awareness
        
        return context
    
    def _get_budget(self, preset: str) -> TokenBudget:
        """Get budget allocation for preset."""
        presets = {
            "minimal": TokenBudget(
                active_history=500,
                recent_history=300,
                memories=1_500
            ),
            "balanced": TokenBudget(
                active_history=1_000,
                recent_history=600,
                memories=5_000
            ),
            "rich": TokenBudget(
                active_history=1_500,
                recent_history=1_000,
                memories=10_000
            )
        }
        return presets.get(preset, presets["balanced"])
```

---

## 9. Implementation Phases

### Phase 1: Foundation (Week 1)
**Goal:** Basic conversation persistence without tiers

- [ ] Database schema migration
- [ ] Session management (create, track, end)
- [ ] Turn insertion with token counting
- [ ] Hub API endpoints (session + turn management)
- [ ] Basic HistoryManager actor (no rotation yet)
- [ ] PersonaCore integration (Active Window only)

**Success Criteria:** Luna can persist and retrieve last 10 turns

### Phase 2: Tier System (Week 2)
**Goal:** Active → Recent rotation with budget management

- [ ] Active Window budget monitoring
- [ ] Tier rotation logic in HistoryManager
- [ ] FTS5 index for keyword search
- [ ] Basic compression (stub or simple extraction)
- [ ] Recent Buffer search in PersonaCore

**Success Criteria:** Turns rotate to Recent when Active exceeds budget

### Phase 3: Compression (Week 3)
**Goal:** Ben Franklin summarization pipeline

- [ ] Compression prompt engineering
- [ ] Local LLM integration for compression
- [ ] Compression queue processing
- [ ] Hub API compression endpoints
- [ ] Compressed summary storage and search

**Success Criteria:** Recent turns have meaningful summaries

### Phase 4: Archive Integration (Week 4)
**Goal:** Recent → Memory Matrix extraction

- [ ] Extraction queue processing
- [ ] Ben Franklin → The Dude pipeline
- [ ] Memory Matrix node creation from archived turns
- [ ] Archive age threshold logic
- [ ] Cross-tier search integration

**Success Criteria:** Old conversations become searchable memories

### Phase 5: Search Enhancement (Week 5)
**Goal:** Hybrid search with vector similarity

- [ ] sqlite-vec integration for history_embeddings
- [ ] Embedding generation for compressed summaries
- [ ] Hybrid search (FTS5 + vector) implementation
- [ ] Relevance scoring and ranking
- [ ] Search result formatting in PersonaCore

**Success Criteria:** "What did we discuss about X?" returns relevant turns

### Phase 6: Production Hardening (Week 6)
**Goal:** Error handling, monitoring, optimization

- [ ] Error handling in all components
- [ ] Observability metrics (turn counts, token usage, search latency)
- [ ] Performance optimization (query indexes, batch operations)
- [ ] Token budget monitoring and adjustment
- [ ] Session cleanup and maintenance

**Success Criteria:** System runs reliably in production

---

## 10. Testing Strategy

### 10.1 Unit Tests

```python
# tests/test_history_manager.py

async def test_active_window_rotation():
    """Test that Active Window rotates when budget exceeded."""
    manager = HistoryManager(config, mock_hub)
    
    # Add turns until budget exceeded
    for i in range(15):
        await manager.add_turn("user", f"Message {i}", tokens=100)
    
    # Check that oldest turns moved to Recent
    active = await manager.get_active_window()
    assert len(active) <= 10
    
    # Check Recent tier has rotated turns
    recent = await mock_hub.get_turns_by_tier('recent')
    assert len(recent) >= 5

async def test_compression_queue():
    """Test that Recent turns get queued for compression."""
    manager = HistoryManager(config, mock_hub)
    
    # Rotate a turn to Recent
    await mock_hub.rotate_turn_tier(turn_id=1, new_tier='recent')
    
    # Tick should queue compression
    await manager.tick()
    
    pending = await mock_hub.get_pending_compressions()
    assert len(pending) == 1
    assert pending[0]['turn_id'] == 1

async def test_search_recent():
    """Test Recent Buffer search."""
    manager = HistoryManager(config, mock_hub)
    
    # Add turns with distinct content
    await manager.add_turn("user", "Tell me about observability", tokens=50)
    await manager.add_turn("assistant", "Observability means...", tokens=100)
    
    # Search
    results = await manager.search_recent("observability", limit=2)
    
    assert len(results) == 2
    assert "observability" in results[0]['content'].lower()
```

### 10.2 Integration Tests

```python
# tests/test_persona_core_history.py

async def test_context_includes_active_history():
    """Test that PersonaCore includes Active Window in context."""
    persona = PersonaCore(history_manager, hub)
    
    # Add conversation turns
    await history_manager.add_turn("user", "Hello Luna", tokens=20)
    await history_manager.add_turn("assistant", "Hi!", tokens=10)
    
    # Build context
    context = await persona.build_enriched_context("How are you?")
    
    assert context.active_history is not None
    assert len(context.active_history) == 2

async def test_recent_search_triggered():
    """Test that backward references trigger Recent search."""
    persona = PersonaCore(history_manager, hub)
    
    # Add old turns
    await history_manager.add_turn("user", "We discussed databases", tokens=30)
    
    # Trigger search with backward reference
    context = await persona.build_enriched_context("What did we say earlier?")
    
    assert context.recent_history is not None
```

### 10.3 End-to-End Tests

```python
# tests/test_e2e_conversation.py

async def test_full_conversation_flow():
    """Test complete conversation with rotation and search."""
    engine = LunaEngine(config)
    await engine.start()
    
    # Simulate conversation
    for i in range(20):
        response = await engine.process_message(f"Message {i}")
        assert response is not None
    
    # Check tier distribution
    active = await engine.history_manager.get_active_window()
    assert len(active) <= 10
    
    # Search old turns
    results = await engine.history_manager.search_recent("Message 5")
    assert len(results) > 0
    
    await engine.stop()
```

---

## 11. Monitoring & Observability

### 11.1 Metrics to Track

```python
"""
runtime/observability/history_metrics.py

Metrics for conversation history system.
"""

@dataclass
class HistoryMetrics:
    """Real-time metrics for history management."""
    
    # Tier sizes
    active_turn_count: int
    active_token_count: int
    recent_turn_count: int
    archived_turn_count: int
    
    # Queue depths
    compression_queue_depth: int
    extraction_queue_depth: int
    
    # Performance
    avg_compression_latency_ms: float
    avg_search_latency_ms: float
    
    # Budget
    active_budget_utilization: float  # 0.0 to 1.0
    context_token_overhead: int       # Total tokens used by history in context
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for logging."""
        return asdict(self)
```

### 11.2 Logging

```python
"""
Add structured logging to HistoryManager.
"""

class HistoryManager(Actor):
    async def tick(self):
        # Log tier state
        logger.info(
            "history_tick",
            active_tokens=await self.hub.get_active_token_count(),
            recent_count=await self.hub.get_recent_count(),
            compression_pending=await self.hub.get_compression_queue_depth()
        )
        
        # ... rest of tick logic
```

---

## 12. Configuration Reference

### 12.1 Config File Format

```yaml
# config/history.yaml

history:
  # Active Window
  max_active_tokens: 1000
  max_active_turns: 10
  
  # Recent Buffer
  max_recent_age_minutes: 60
  compression_enabled: true
  
  # Search
  default_search_limit: 3
  search_type: "hybrid"  # hybrid | keyword | semantic
  
  # Performance
  compression_batch_size: 1
  extraction_batch_size: 1
  
  # Session
  app_context: "terminal"  # terminal | voice | mobile
```

### 12.2 Environment Variables

```bash
# .env

# Hub API
HUB_API_URL=http://localhost:8000

# SQLite
LUNA_DB_PATH=/path/to/LunaVault.sparsebundle/memory_matrix.db

# LLM (for compression)
LOCAL_LLM_MODEL=qwen2.5-7b-instruct
LOCAL_LLM_CONTEXT=8192

# Logging
LOG_LEVEL=INFO
HISTORY_DEBUG=false
```

---

## 13. Failure Modes & Recovery

### 13.1 Known Failure Scenarios

| Scenario | Impact | Recovery Strategy |
|----------|--------|-------------------|
| Compression fails | Recent turns lack summaries | Retry queue, fallback to keyword search only |
| Extraction fails | Turns not archived to Memory Matrix | Manual extraction via admin tool |
| Active Window too large | Context overflow | Emergency rotation, truncate to budget |
| Session not closed | Orphaned active session | Auto-close stale sessions (>24h inactive) |
| Search latency spike | Slow context building | Timeout, skip Recent search, use Active only |

### 13.2 Graceful Degradation

```python
"""
Fallback strategies when components fail.
"""

class HistoryManager(Actor):
    async def search_recent(self, query: str, limit: int = 3):
        """Search with fallback strategy."""
        try:
            # Try hybrid search
            return await self.hub.search_history(
                query=query,
                tier='recent',
                limit=limit,
                search_type='hybrid'
            )
        except VectorSearchError:
            # Fallback to keyword-only
            logger.warning("Vector search failed, using keyword fallback")
            return await self.hub.search_history(
                query=query,
                tier='recent',
                limit=limit,
                search_type='keyword'
            )
        except Exception as e:
            # Ultimate fallback: return empty
            logger.error(f"All search strategies failed: {e}")
            return []
```

---

## 14. Security & Privacy

### 14.1 Data Retention Policy

```python
"""
Admin tools for conversation management.
"""

async def delete_session(session_id: str):
    """
    Delete a session and all its turns.
    Respects sovereignty: user controls their data.
    """
    await hub.delete_session(session_id)
    # CASCADE DELETE handles conversation_turns automatically

async def export_session(session_id: str) -> str:
    """
    Export session as JSON for backup or migration.
    """
    session = await hub.get_session(session_id)
    turns = await hub.get_turns_by_session(session_id)
    
    return json.dumps({
        "session": session,
        "turns": turns
    }, indent=2)

async def vacuum_old_sessions(days: int = 90):
    """
    Clean up sessions older than N days (configurable).
    """
    cutoff = time.time() - (days * 86400)
    await hub.delete_sessions_before(cutoff)
```

### 14.2 Encryption

```
All conversation data lives in memory_matrix.db inside LunaVault.sparsebundle.
The vault is encrypted at rest (APFS encryption).
No additional encryption needed at application layer.
```

---

## 15. Performance Targets

### 15.1 Latency Budgets

| Operation | Target | P95 | Notes |
|-----------|--------|-----|-------|
| Add turn | <5ms | <10ms | Simple INSERT |
| Get active window | <10ms | <20ms | 10 row SELECT |
| Search recent (keyword) | <50ms | <100ms | FTS5 query |
| Search recent (hybrid) | <150ms | <300ms | FTS5 + vector |
| Compress turn | <500ms | <1000ms | Local LLM inference |
| Extract turn | <1500ms | <3000ms | Full Memory Matrix extraction |

### 15.2 Throughput Targets

- **Turn ingestion:** 100+ turns/second
- **Concurrent searches:** 10+ simultaneous queries
- **Compression queue:** Process 1 turn per cognitive tick (~1-2 Hz)
- **Extraction queue:** Process 1 turn per cognitive tick

### 15.3 Storage Efficiency

- **Active Window:** ~1KB per turn (full text)
- **Recent Buffer:** ~500B per turn (compressed + full)
- **Archive:** Moved to Memory Matrix (shared storage)
- **Expected growth:** ~1MB per 1000 turns (before compression)

---

## 16. Migration Path

### 16.1 For New Installations

1. Run schema migration (creates tables)
2. Enable HistoryManager in runtime config
3. Start engine with history enabled

### 16.2 For Existing Installations

```sql
-- Migration script: add_conversation_history.sql

BEGIN TRANSACTION;

-- Check if already migrated
SELECT CASE 
    WHEN EXISTS (SELECT 1 FROM sqlite_master WHERE name = 'sessions')
    THEN 'ALREADY_MIGRATED'
    ELSE 'NEEDS_MIGRATION'
END;

-- If NEEDS_MIGRATION, run schema from Section 3.1

COMMIT;
```

### 16.3 Backfilling Historical Data

```python
"""
Optional: Backfill from existing conversation logs (if any).
"""

async def backfill_from_logs(log_file: str):
    """
    Import historical conversations into new history system.
    """
    # Parse log file
    conversations = parse_conversation_log(log_file)
    
    # Create sessions and turns
    for conv in conversations:
        session = await hub.create_session(
            app_context="terminal",
            started_at=conv['started_at']
        )
        
        for turn in conv['turns']:
            await hub.add_turn(
                session_id=session['session_id'],
                role=turn['role'],
                content=turn['content'],
                tokens=count_tokens(turn['content'])
            )
```

---

## 17. Future Enhancements

### 17.1 Phase 2 Features (Post-Launch)

- **Multi-session context awareness:** Search across multiple recent sessions
- **Conversation threading:** Track topic branches within sessions
- **Automatic session boundaries:** Detect topic shifts and create new sessions
- **Smart compression tuning:** Learn optimal compression lengths per user
- **Cross-session memory linking:** Connect related discussions across time

### 17.2 Advanced Search

- **Temporal queries:** "What did we discuss about X last Tuesday?"
- **Semantic clustering:** Group related conversation threads
- **Entity tracking:** Find all mentions of a person/project across history
- **Sentiment analysis:** Track emotional tone across conversations

### 17.3 Observability Enhancements

- **Real-time dashboard:** View tier sizes, queue depths, search performance
- **Compression quality metrics:** Track summary accuracy
- **Context utilization:** See what history is actually being used
- **Budget optimization:** Automatic budget allocation based on usage patterns

---

## 18. Acceptance Criteria

### 18.1 System-Level

- [ ] Luna can maintain continuity across 100+ turn conversations
- [ ] Active Window never exceeds configured token budget
- [ ] Recent Buffer searches return relevant results in <300ms
- [ ] Compression reduces turn size by 60%+ on average
- [ ] Archived turns become searchable in Memory Matrix
- [ ] System operates reliably for 7+ days without manual intervention

### 18.2 User-Facing

- [ ] Luna remembers the last 10 turns without explicit prompting
- [ ] "What did we just discuss?" queries return accurate results
- [ ] Long conversations don't cause context overflow errors
- [ ] Luna can reference decisions made 30+ minutes ago
- [ ] Conversation feels natural and continuous

---

## 19. Handoff Checklist for Claude Code

**Before starting implementation:**

- [ ] Review Luna Engine v2.1 architecture docs
- [ ] Understand tick-based actor model
- [ ] Familiarize with Hub API patterns
- [ ] Review Memory Matrix schema
- [ ] Check sqlite-vec installation

**During implementation:**

- [ ] Follow phase order (don't skip ahead)
- [ ] Write tests before implementation (TDD)
- [ ] Run tests after each component
- [ ] Update observability metrics
- [ ] Document any deviations from spec

**After implementation:**

- [ ] Full test suite passes
- [ ] Metrics dashboard shows healthy state
- [ ] Performance meets targets
- [ ] User acceptance testing complete
- [ ] Documentation updated

---

## 20. Contact & Support

**Questions during implementation:**

- Architecture decisions: @Ahab (system architect)
- Ben Franklin integration: @Scribe team
- Memory Matrix questions: @Dude (The Librarian)
- Performance issues: @Observatory team

**Resources:**

- Luna Engine Bible: `/mnt/project/00-TABLE-OF-CONTENTS.md`
- Architecture docs: `/mnt/project/02-SYSTEM-ARCHITECTURE.md`
- Memory Matrix spec: `/mnt/project/03-MEMORY-MATRIX.md`
- Runtime Engine: `/mnt/project/07-RUNTIME-ENGINE.md`

---

**END OF SPECIFICATION**

This document is ready for Claude Code implementation. All architecture mismatches have been corrected, and the design is aligned with Luna Engine v2.1's tick-based actor model and Hub API abstraction layer.
