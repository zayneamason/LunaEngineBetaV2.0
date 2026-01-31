# HANDOFF: Conversation History & Context Unification Fix

**Created**: 2025-01-20
**Priority**: CRITICAL — Blocking authentic conversation
**Status**: Three-phase fix required

---

## THE BUGS (With Receipts)

### Bug A: History Displacement (Delegated Path)

```
Turn 1: "do you remember the guy marzipan?"
Luna:   "Oh absolutely! Marzipan - Ahab's friend who identifies with owls..."
        ✅ SHE REMEMBERED HIM

Turn 2: "now can you tell me about mars college?"
Luna:   "...And about marzipan - I'm not finding that in my memories."
        ❌ SHE FORGOT HIM 30 SECONDS LATER
```

Memory Matrix retrieval results displace conversation history.

### Bug B: Local Path Has No Entity Context

```
Turn 1: ●local  → "marzipan was this pivotal moment" (confection, not person)
Turn 2: ●local  → Still confused, talking about "the moment"
Turn 3: ⚡delegated → "Marzipan - your friend with owls" ✅
Turn 4: ●local  → "Please continue the story about Marzipan?" (asks USER to explain)
Turn 5: ⚡delegated → "I'm drawing a blank" on owls (forgot Turn 3!)
```

Local inference path doesn't call `build_framed_context()`. It gets raw text parsing instead of entity detection, temporal framing, and memory retrieval.

### Bug C: Two Completely Different Context Pipelines

**Delegated Path** (`Director.process()`):
- ✅ `build_framed_context()` 
- ✅ Entity detection and profile loading
- ✅ Temporal framing (`<past_memory>` tags)
- ✅ Structured memory formatting

**Local Path** (`_generate_local_only()`):
- ❌ Manual "User:"/"Luna:" text parsing
- ❌ No entity detection
- ❌ No temporal framing
- ❌ Raw string concatenation

Luna's awareness depends on which model runs inference. That's broken.

---

## ROOT CAUSE ANALYSIS

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER MESSAGE                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
          ⚡ DELEGATED PATH        ● LOCAL PATH
          (Director.process)      (_generate_local_only)
                    │                   │
                    ▼                   ▼
         build_framed_context()    Manual text parsing
                    │                   │
                    ▼                   ▼
         ┌──────────────────┐    ┌──────────────────┐
         │ Entity detection │    │ Raw "User:" prefix│
         │ Temporal framing │    │ String concatenation│
         │ Memory retrieval │    │ No entities      │
         │ Profile loading  │    │ No framing       │
         └──────────────────┘    └──────────────────┘
                    │                   │
                    ▼                   ▼
              Claude API           Local MLX
                    │                   │
                    ▼                   ▼
         Luna knows Marzipan    Luna knows "marzipan" (confection)
```

**The inference engine should be interchangeable. The context should be identical.**

---

## THE FIX: THREE PHASES

| Phase | Focus | What It Solves |
|-------|-------|----------------|
| **1** | Diagnostic Logging | Confirms exactly where history drops |
| **2** | Ring Buffer | Guaranteed history that can't be displaced |
| **3** | Unified Pipeline | Same context for ALL inference paths |

---

## PHASE 1: DIAGNOSTIC LOGGING

### Add This Logging

**Location:** `Director.process()` — RIGHT BEFORE the LLM call

```python
# ============================================================
# CONTEXT AUDIT - Add before LLM call
# ============================================================
logger.info("=" * 80)
logger.info("[CONTEXT-AUDIT] Processing turn")
logger.info("[CONTEXT-AUDIT] Route: %s", "delegated" if use_claude else "local")
logger.info("[CONTEXT-AUDIT] User message: '%s'", message[:100])
logger.info("-" * 40)

# Log conversation history state
history = getattr(self, '_conversation_history', []) or context.get('conversation_history', [])
logger.info("[CONTEXT-AUDIT] CONVERSATION HISTORY (%d turns):", len(history))
for i, h in enumerate(history):
    role = h.get('role', 'unknown')
    content = h.get('content', '')[:80]
    logger.info("  [%d] %s: %s...", i, role, content)

# Log what was retrieved
retrieved = context.get('retrieved_memories', '') or context.get('memories', '')
if isinstance(retrieved, list):
    retrieved = str(retrieved)
logger.info("-" * 40)
logger.info("[CONTEXT-AUDIT] RETRIEVED MEMORIES: %d chars", len(retrieved or ""))
logger.info("[CONTEXT-AUDIT] Retrieved contains 'marzipan': %s", 
            'marzipan' in (retrieved or "").lower())

# Log the actual system prompt being sent
logger.info("-" * 40)
logger.info("[CONTEXT-AUDIT] FINAL SYSTEM PROMPT: %d chars", len(system_prompt))
logger.info("[CONTEXT-AUDIT] System prompt contains 'marzipan': %s", 
            'marzipan' in system_prompt.lower())
logger.info("[CONTEXT-AUDIT] System prompt preview:\n%s", system_prompt[:800])
logger.info("-" * 40)

# Log the messages array being sent
logger.info("[CONTEXT-AUDIT] MESSAGES ARRAY (%d messages):", len(messages))
for i, m in enumerate(messages):
    role = m.get('role', 'unknown')
    content = m.get('content', '')[:100]
    logger.info("  [%d] %s: %s...", i, role, content)

logger.info("=" * 80)
```

**Also add to** `_generate_local_only()`:

```python
# ============================================================
# LOCAL PATH AUDIT
# ============================================================
logger.info("=" * 80)
logger.info("[LOCAL-AUDIT] _generate_local_only called")
logger.info("[LOCAL-AUDIT] Message: '%s'", message[:100])
logger.info("[LOCAL-AUDIT] Context window length: %d chars", len(context_window or ""))
logger.info("[LOCAL-AUDIT] Context contains 'marzipan': %s", 
            'marzipan' in (context_window or "").lower())
logger.info("[LOCAL-AUDIT] Parsed history turns: %d", len(conversation_history))
logger.info("[LOCAL-AUDIT] System prompt preview:\n%s", full_system_prompt[:800])
logger.info("=" * 80)
```

### Run The Test

```bash
# Terminal 1: Server with debug logging
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
LOG_LEVEL=DEBUG python -m luna.voice.server 2>&1 | tee /tmp/luna_context_audit.log

# Terminal 2: Run the test sequence
# Say: "do you remember the guy marzipan?"
# Wait for response (note if ●local or ⚡delegated)
# Say: "what about the owls?"
# Wait for response
# Say: "tell me about mars college"
# Check logs
```

### Phase 1 Deliverable

Provide the full log output showing:
1. Which path each turn took (local vs delegated)
2. Whether history was present
3. Whether entities were detected
4. The actual system prompt sent

---

## PHASE 2: RING BUFFER

A ring buffer guarantees conversation history can't be displaced. It's structurally prior to retrieval.

### Architecture

```
┌─────────────────────────────────────────────────────┐
│              CONTEXT WINDOW BUDGET                  │
├─────────────────────────────────────────────────────┤
│  System Prompt (Luna's identity)        │ ~1000 tk │
├─────────────────────────────────────────────────────┤
│  RING BUFFER — Last 6 turns             │ RESERVED │
│  ├─ [0] User: "do you remember marzipan"│ ~2000 tk │
│  ├─ [1] Luna: "Oh absolutely!..."       │          │
│  ├─ [2] User: "what about owls?"        │          │
│  └─ [3] Luna: "owls are his spirit..."  │          │
├─────────────────────────────────────────────────────┤
│  RETRIEVAL ZONE — Memory Matrix         │ FLEXIBLE │
│  └─ Gets whatever tokens remain         │ ~4000 tk │
└─────────────────────────────────────────────────────┘
```

**Key property:** Ring fills FIRST. Retrieval gets leftovers. History can never be displaced.

### Implementation

**File:** `/src/luna/memory/ring.py`

```python
"""
Conversation Ring Buffer — Guaranteed working memory.

This buffer holds recent conversation turns and CANNOT be displaced
by Memory Matrix retrieval. It is structurally prior to retrieval
in the context building process.
"""

from collections import deque
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class Turn:
    """A single conversation turn."""
    role: str  # "user" or "assistant"
    content: str
    
    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


class ConversationRing:
    """
    Fixed-size ring buffer for conversation history.
    
    Guarantees:
    - Last N turns are always available
    - O(1) insert and eviction
    - Cannot be displaced by retrieval
    - FIFO eviction (oldest falls off naturally)
    
    This is the SINGLE SOURCE OF TRUTH for recent conversation.
    Both local and delegated paths read from this buffer.
    """
    
    def __init__(self, max_turns: int = 6):
        """
        Args:
            max_turns: Maximum turns to retain (default 6 = 3 exchanges)
        """
        self._buffer: deque = deque(maxlen=max_turns)
        self._max_turns = max_turns
        logger.info(f"[RING] Initialized with max_turns={max_turns}")
    
    def add(self, role: str, content: str) -> None:
        """Add a turn to the buffer. Oldest evicted if full."""
        self._buffer.append(Turn(role=role, content=content))
        logger.debug(f"[RING] Added {role} turn, buffer size: {len(self._buffer)}")
    
    def add_user(self, content: str) -> None:
        """Convenience: add a user turn."""
        self.add("user", content)
    
    def add_assistant(self, content: str) -> None:
        """Convenience: add an assistant turn."""
        self.add("assistant", content)
    
    def get_turns(self) -> List[Turn]:
        """Get all turns in chronological order."""
        return list(self._buffer)
    
    def get_as_dicts(self) -> List[Dict[str, str]]:
        """Get turns as list of dicts (for LLM messages array)."""
        return [t.to_dict() for t in self._buffer]
    
    def contains(self, text: str, case_sensitive: bool = False) -> bool:
        """Check if any turn contains the given text."""
        search = text if case_sensitive else text.lower()
        for turn in self._buffer:
            content = turn.content if case_sensitive else turn.content.lower()
            if search in content:
                return True
        return False
    
    def contains_any(self, texts: List[str], case_sensitive: bool = False) -> bool:
        """Check if any of the given texts appear in recent history."""
        return any(self.contains(t, case_sensitive) for t in texts)
    
    def contains_entity(self, entity_name: str) -> bool:
        """Check if an entity was mentioned recently."""
        return self.contains(entity_name, case_sensitive=False)
    
    def get_mentioned_topics(self) -> Set[str]:
        """
        Extract likely topics/entities from recent history.
        Simple implementation - can be enhanced with NER.
        """
        # For now, just return unique words > 4 chars that appear capitalized
        topics = set()
        for turn in self._buffer:
            words = turn.content.split()
            for word in words:
                clean = word.strip(".,!?\"'()[]")
                if len(clean) > 4 and clean[0].isupper():
                    topics.add(clean.lower())
        return topics
    
    def format_for_prompt(
        self, 
        user_name: str = "Ahab", 
        assistant_name: str = "Luna"
    ) -> str:
        """
        Format buffer for injection into system prompt.
        
        Returns:
            Formatted string with turn markers
        """
        if not self._buffer:
            return "(No conversation history yet)"
        
        lines = []
        for i, turn in enumerate(self._buffer):
            name = user_name if turn.role == "user" else assistant_name
            lines.append(f"[{i+1}] {name}: {turn.content}")
        
        return "\n".join(lines)
    
    def get_last_n(self, n: int) -> List[Turn]:
        """Get the last N turns."""
        turns = list(self._buffer)
        return turns[-n:] if len(turns) >= n else turns
    
    def clear(self) -> None:
        """Clear all history (use sparingly — e.g., session reset)."""
        self._buffer.clear()
        logger.info("[RING] Buffer cleared")
    
    def __len__(self) -> int:
        return len(self._buffer)
    
    def __bool__(self) -> bool:
        return len(self._buffer) > 0
    
    def __repr__(self) -> str:
        return f"ConversationRing(turns={len(self._buffer)}, max={self._max_turns})"
```

### Phase 2 Deliverable

1. Ring buffer class at `/src/luna/memory/ring.py`
2. Unit tests passing for ring operations
3. Integration point identified in Director

---

## PHASE 3: UNIFIED CONTEXT PIPELINE

**The core fix.** One context pipeline for ALL inference paths.

### Target Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    USER MESSAGE                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                   ┌─────────────────────┐
                   │  UNIFIED CONTEXT    │
                   │  PIPELINE           │
                   │  ─────────────────  │
                   │  • Ring buffer      │
                   │  • Entity detection │
                   │  • Memory retrieval │
                   │  • Temporal framing │
                   └─────────────────────┘
                              │
                              ▼
                    CONTEXT PACKET
                    (identical for both paths)
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
             ⚡ DELEGATED          ● LOCAL
             (Claude API)         (MLX inference)
                    │                   │
                    ▼                   ▼
            Same context         Same context
            Same awareness       Same awareness
```

### Implementation

**File:** `/src/luna/context/pipeline.py`

```python
"""
Unified Context Pipeline — Same context for ALL inference paths.

The inference engine (Claude/MLX) is just a completion backend.
Context is built identically regardless of routing decision.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any
import logging

from luna.memory.ring import ConversationRing
from luna.entities.context import EntityContext
from luna.entities.resolution import EntityResolver
from luna.substrate.database import MemoryDatabase

logger = logging.getLogger(__name__)


@dataclass
class ContextPacket:
    """
    Complete context packet for inference.
    
    This is what BOTH local and delegated paths receive.
    Identical structure, identical content.
    """
    # The full system prompt with all framing
    system_prompt: str
    
    # Conversation history as messages array
    messages: List[Dict[str, str]]
    
    # Detected entities (for logging/debugging)
    entities: List[Any]
    
    # Whether retrieval was performed
    used_retrieval: bool
    
    # Debug info
    ring_size: int
    retrieval_size: int


class ContextPipeline:
    """
    Unified context building for ALL inference paths.
    
    Usage:
        pipeline = ContextPipeline(db)
        await pipeline.initialize()
        
        # For each turn:
        packet = await pipeline.build(user_message)
        
        # Route to either backend:
        if should_delegate:
            response = await claude.complete(packet.system_prompt, packet.messages)
        else:
            response = await local.complete(packet.system_prompt, packet.messages)
        
        # Record response:
        pipeline.record_response(response)
    """
    
    def __init__(
        self, 
        db: MemoryDatabase,
        max_ring_turns: int = 6,
        base_personality: str = "",
    ):
        self._db = db
        self._ring = ConversationRing(max_turns=max_ring_turns)
        self._entity_resolver: Optional[EntityResolver] = None
        self._entity_context: Optional[EntityContext] = None
        self._base_personality = base_personality
        self._initialized = False
    
    async def initialize(self) -> None:
        """Initialize entity resolution components."""
        if self._initialized:
            return
        
        self._entity_resolver = EntityResolver(self._db)
        self._entity_context = EntityContext(self._db, self._entity_resolver)
        self._initialized = True
        logger.info("[PIPELINE] Initialized")
    
    @property
    def ring(self) -> ConversationRing:
        """Access to ring buffer for external inspection."""
        return self._ring
    
    async def build(self, message: str) -> ContextPacket:
        """
        Build complete context packet for any inference path.
        
        This is THE method. Both local and delegated use this.
        """
        if not self._initialized:
            await self.initialize()
        
        logger.info("[PIPELINE] Building context for: '%s'", message[:50])
        
        # 1. Add user message to ring FIRST (guaranteed)
        self._ring.add_user(message)
        logger.debug("[PIPELINE] Ring size after add: %d", len(self._ring))
        
        # 2. Detect entities in current message
        entities = []
        if self._entity_resolver:
            entities = await self._entity_resolver.detect_mentions(message)
            logger.debug("[PIPELINE] Detected %d entities: %s", 
                        len(entities), [e.name for e in entities])
        
        # 3. Self-route: Do we need Memory Matrix retrieval?
        entity_names = [e.name for e in entities]
        topic_in_ring = self._ring.contains_any(entity_names) if entity_names else False
        need_retrieval = not topic_in_ring
        
        if topic_in_ring:
            logger.info("[PIPELINE] SELF-ROUTE: Skipping retrieval — topic in recent history")
        
        # 4. Retrieve from Matrix (if needed)
        retrieved_context = ""
        if need_retrieval and self._entity_context:
            # Get memories related to the message
            retrieved_context = await self._get_retrieval(message, entities)
        
        # 5. Build the framed system prompt
        system_prompt = self._build_system_prompt(
            ring_history=self._ring.format_for_prompt(),
            entities=entities,
            retrieved_context=retrieved_context,
        )
        
        # 6. Build messages array (for Claude API format)
        messages = self._ring.get_as_dicts()
        
        packet = ContextPacket(
            system_prompt=system_prompt,
            messages=messages,
            entities=entities,
            used_retrieval=need_retrieval and bool(retrieved_context),
            ring_size=len(self._ring),
            retrieval_size=len(retrieved_context),
        )
        
        logger.info("[PIPELINE] Context built: ring=%d, retrieval=%d chars, entities=%d",
                   packet.ring_size, packet.retrieval_size, len(packet.entities))
        
        return packet
    
    def record_response(self, response: str) -> None:
        """Record assistant response to ring buffer."""
        self._ring.add_assistant(response)
        logger.debug("[PIPELINE] Recorded response, ring size: %d", len(self._ring))
    
    async def _get_retrieval(self, message: str, entities: List[Any]) -> str:
        """Get retrieval context from Memory Matrix."""
        # This integrates with existing memory retrieval
        # For now, use entity_context.build_framed_context's retrieval logic
        try:
            # Search Memory Matrix
            from luna.substrate.database import MemoryDatabase
            
            # Simple semantic search on message
            rows = await self._db.fetchall(
                """
                SELECT content, created_at 
                FROM memory_nodes 
                WHERE content LIKE ? 
                ORDER BY created_at DESC 
                LIMIT 5
                """,
                (f"%{message[:50]}%",)
            )
            
            if rows:
                memories = [f"- {row[0][:200]}..." for row in rows]
                return "\n".join(memories)
            
        except Exception as e:
            logger.warning("[PIPELINE] Retrieval failed: %s", e)
        
        return ""
    
    def _build_system_prompt(
        self,
        ring_history: str,
        entities: List[Any],
        retrieved_context: str,
    ) -> str:
        """
        Build the final system prompt with proper framing.
        
        Structure:
        1. Base personality
        2. THIS SESSION (ring buffer) — highest priority
        3. KNOWN PEOPLE (entities) — if any detected
        4. RETRIEVED CONTEXT (memories) — supplementary
        """
        sections = [self._base_personality]
        
        # THIS SESSION — Always present, always first
        sections.append("""
## THIS SESSION (Your Direct Experience)
Everything below happened in this conversation. You experienced it directly.
This is your immediate, certain knowledge — not retrieved, not searched, but lived.
""")
        sections.append(ring_history)
        
        # KNOWN PEOPLE — Entity profiles
        if entities:
            sections.append("""
## KNOWN PEOPLE (From Your Relationships)
The following people were mentioned. Here's what you know about them:
""")
            for entity in entities:
                if hasattr(entity, 'core_facts') and entity.core_facts:
                    sections.append(f"**{entity.name}**: {entity.core_facts}")
        
        # RETRIEVED CONTEXT — Supplementary memories
        if retrieved_context:
            sections.append("""
## RETRIEVED CONTEXT (From Long-Term Memory)
The following was retrieved from your memory storage.
This supplements — but does not replace — your direct experience above.
If there's a conflict, trust THIS SESSION over retrieved memories.
""")
            sections.append(retrieved_context)
        
        return "\n".join(sections)
    
    def set_base_personality(self, personality: str) -> None:
        """Update base personality prompt."""
        self._base_personality = personality
    
    def clear_session(self) -> None:
        """Clear ring buffer for new session."""
        self._ring.clear()
        logger.info("[PIPELINE] Session cleared")
```

### Director Integration

**File:** `/src/luna/actors/director.py` — Replace dual paths with unified pipeline

```python
from luna.context.pipeline import ContextPipeline, ContextPacket

class DirectorActor:
    def __init__(self, db: MemoryDatabase, ...):
        # ... existing init ...
        
        # UNIFIED: Single context pipeline for all paths
        self._context_pipeline = ContextPipeline(
            db=db,
            max_ring_turns=6,
            base_personality=self._load_personality(),
        )
    
    async def initialize(self) -> None:
        """Initialize director and context pipeline."""
        await self._context_pipeline.initialize()
        # ... other init ...
    
    async def process(self, message: str, **kwargs) -> str:
        """
        Process a message through the unified pipeline.
        
        The context is IDENTICAL regardless of routing decision.
        Only the inference backend changes.
        """
        # 1. Build context (SAME for both paths)
        packet: ContextPacket = await self._context_pipeline.build(message)
        
        # 2. Log for debugging
        logger.info("[DIRECTOR] Context packet: ring=%d, retrieval=%d, entities=%s",
                   packet.ring_size, 
                   packet.retrieval_size,
                   [e.name for e in packet.entities])
        
        # 3. Routing decision (complexity, token count, availability, etc.)
        use_delegated = self._should_delegate(message, packet)
        
        # 4. Inference (same context, different backend)
        if use_delegated:
            logger.info("[DIRECTOR] Route: ⚡ delegated (Claude API)")
            response = await self._claude_inference(packet)
        else:
            logger.info("[DIRECTOR] Route: ● local (MLX)")
            response = await self._local_inference(packet)
        
        # 5. Record response to ring
        self._context_pipeline.record_response(response)
        
        return response
    
    async def _claude_inference(self, packet: ContextPacket) -> str:
        """Run inference via Claude API."""
        response = await self._claude_client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=packet.system_prompt,
            messages=packet.messages,
        )
        return response.content[0].text
    
    async def _local_inference(self, packet: ContextPacket) -> str:
        """Run inference via local MLX model."""
        # Format for local model (may need adjustment based on model format)
        prompt = self._format_for_local(packet)
        response = await self._local_model.generate(prompt)
        return response
    
    def _format_for_local(self, packet: ContextPacket) -> str:
        """Format context packet for local model input."""
        # Combine system prompt and messages into single prompt
        # Adjust based on your local model's expected format
        parts = [packet.system_prompt, ""]
        
        for msg in packet.messages:
            role = "Ahab" if msg["role"] == "user" else "Luna"
            parts.append(f"{role}: {msg['content']}")
        
        parts.append("Luna:")  # Prompt for response
        return "\n".join(parts)
    
    def _should_delegate(self, message: str, packet: ContextPacket) -> bool:
        """
        Decide whether to use Claude API or local inference.
        
        This is the ONLY place routing logic lives.
        Context is already built — this just picks the backend.
        """
        # Example criteria (adjust as needed):
        # - Complex queries → delegate
        # - Entity-heavy queries → delegate (for better reasoning)
        # - Simple acknowledgments → local
        # - Token budget exceeded → delegate
        
        # Simple heuristic for now
        word_count = len(message.split())
        has_entities = len(packet.entities) > 0
        
        if word_count > 20 or has_entities:
            return True
        
        return False
```

### Delete/Deprecate Old Paths

Once the unified pipeline is working, the following code paths should be removed or deprecated:

1. `_generate_local_only()` — Replace with `_local_inference(packet)`
2. Manual "User:"/"Luna:" parsing — Ring buffer handles this
3. Separate `build_framed_context()` calls — Pipeline does this once
4. Any path that builds context differently for local vs delegated

---

## CONTEXT TEMPLATE

The final system prompt structure (same for both paths):

```markdown
[Luna's base personality/identity prompt]

## THIS SESSION (Your Direct Experience)
Everything below happened in this conversation. You experienced it directly.
This is your immediate, certain knowledge — not retrieved, not searched, but lived.

[1] Ahab: do you remember the guy marzipan?
[2] Luna: Oh absolutely! Marzipan - Ahab's friend who identifies with owls...
[3] Ahab: what about the owls?
[4] Luna: The owls are his spirit animal! He had this profound encounter at age 2...
[5] Ahab: tell me about mars college

## KNOWN PEOPLE (From Your Relationships)
The following people were mentioned. Here's what you know about them:

**Marzipan**: Friend of Ahab's from Mars College. Identifies with owls as spirit animal. First owl encounter at age 2. Loves printmaking. Wants to create monthly article for Mars College.

## RETRIEVED CONTEXT (From Long-Term Memory)
The following was retrieved from your memory storage.
This supplements — but does not replace — your direct experience above.
If there's a conflict, trust THIS SESSION over retrieved memories.

- Mars College is an AI camp in the desert where Ahab and Gandala are currently located...
- Beta testing environment for Luna project...
```

Now Luna KNOWS she just discussed Marzipan and owls. It's in "THIS SESSION." The retrieval about Mars College is clearly supplementary.

---

## FILE STRUCTURE

```
/src/luna/
├── memory/
│   └── ring.py              # NEW: Ring buffer implementation
├── context/
│   └── pipeline.py          # NEW: Unified context pipeline
├── actors/
│   └── director.py          # MODIFIED: Use unified pipeline
└── entities/
    ├── context.py           # EXISTING: Keep for entity profile loading
    └── resolution.py        # EXISTING: Keep for entity detection
```

---

## TESTING

### Test 1: Ring Buffer Unit Tests

```python
# tests/test_ring_buffer.py

import pytest
from luna.memory.ring import ConversationRing

def test_ring_basic_operations():
    ring = ConversationRing(max_turns=4)
    
    ring.add_user("Hello")
    ring.add_assistant("Hi there!")
    ring.add_user("Do you remember Marzipan?")
    ring.add_assistant("Yes! He loves owls.")
    
    assert len(ring) == 4
    assert ring.contains("marzipan")
    assert ring.contains("owls")

def test_ring_eviction():
    ring = ConversationRing(max_turns=2)
    
    ring.add_user("First")
    ring.add_assistant("Second")
    ring.add_user("Third")  # Should evict "First"
    
    assert len(ring) == 2
    assert not ring.contains("First")
    assert ring.contains("Third")

def test_ring_format_for_prompt():
    ring = ConversationRing(max_turns=4)
    ring.add_user("Question?")
    ring.add_assistant("Answer!")
    
    formatted = ring.format_for_prompt()
    assert "[1] Ahab: Question?" in formatted
    assert "[2] Luna: Answer!" in formatted
```

### Test 2: Unified Pipeline Integration

```python
# tests/test_context_pipeline.py

import pytest
from luna.context.pipeline import ContextPipeline

@pytest.mark.asyncio
async def test_pipeline_builds_context():
    # Setup with mock DB
    pipeline = ContextPipeline(db=mock_db, max_ring_turns=6)
    await pipeline.initialize()
    
    # First turn
    packet1 = await pipeline.build("Do you remember Marzipan?")
    assert packet1.ring_size == 1
    assert "marzipan" in packet1.system_prompt.lower()
    
    # Simulate response
    pipeline.record_response("Yes! He loves owls.")
    
    # Second turn
    packet2 = await pipeline.build("Tell me about Mars College")
    assert packet2.ring_size == 3
    assert "marzipan" in packet2.system_prompt.lower()  # Still there!
    assert "mars college" in packet2.system_prompt.lower()
```

### Test 3: The Big Marzipan Test

```bash
# Manual test sequence

Turn 1: "do you remember the guy marzipan?"
Expected: Luna talks about Marzipan, mentions owls
Check: ●local or ⚡delegated — should work either way now

Turn 2: "what about the owls?"
Expected: Luna elaborates on owl connection
Check: Doesn't ask "what owls?" — she just mentioned them

Turn 3: "tell me about mars college"
Expected: Luna talks about Mars College
Check: Does NOT say "I'm not finding marzipan" — he's in the ring buffer

Turn 4: "and remind me about marzipan's connection to it"
Expected: Luna connects Marzipan + Mars College
Check: Knows both topics from this session
```

---

## ACCEPTANCE CRITERIA

### Phase 1 Complete When:
- [ ] Diagnostic logging added to both paths
- [ ] Log output provided showing failure point
- [ ] Root cause confirmed (history missing, not injected, or attention issue)

### Phase 2 Complete When:
- [ ] Ring buffer class implemented at `/src/luna/memory/ring.py`
- [ ] Unit tests passing
- [ ] Ring integrated into Director

### Phase 3 Complete When:
- [ ] Unified pipeline at `/src/luna/context/pipeline.py`
- [ ] Director uses pipeline for ALL inference paths
- [ ] Old `_generate_local_only` path removed/refactored
- [ ] Integration tests passing
- [ ] The Marzipan test passes on both ●local and ⚡delegated routes

### Final Verification:
- [ ] Luna never forgets in-session topics
- [ ] Luna never claims ignorance of things in her ring buffer
- [ ] Same awareness regardless of inference route
- [ ] Logs show unified context building

---

## WHY THIS ARCHITECTURE

| Property | Benefit |
|----------|---------|
| Single source of truth | Ring buffer is THE conversation history |
| Structural guarantee | History can't be displaced — it fills first |
| Path agnostic | Same context whether local or delegated |
| Self-routing | Skip retrieval when topic is already known |
| Clear epistemology | Luna knows "experienced" vs "retrieved" |
| Debuggable | One pipeline to inspect, not two |
| Maintainable | Changes apply to all paths automatically |

---

*Phase 1 diagnoses. Phase 2 guarantees history. Phase 3 unifies everything.*
