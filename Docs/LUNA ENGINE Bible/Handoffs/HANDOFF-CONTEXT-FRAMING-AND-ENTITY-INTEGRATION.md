# HANDOFF: Context Framing & Entity Integration

**Created**: 2025-01-20
**Priority**: HIGH
**Status**: ROOT CAUSES IDENTIFIED
**Depends On**: Conversation history fix (COMPLETED)

---

## THE PROBLEMS

### Problem 1: Temporal Confusion
Luna can't distinguish:
- **Retrieved memories** (things that happened before)
- **Current conversation** (what's happening now)

When asked "do you remember Marzipan?", Luna pulls a memory of "Oh my GOD, Yulia!" and RE-PERFORMS it instead of referencing it as past.

### Problem 2: Entity System Not Wired
The Entity System infrastructure exists:
- `entities/` directory with YAML profiles ✓
- `migrations/001_entity_system.sql` ✓
- `scripts/load_entity_seeds.py` ✓

But it's never used. Director doesn't:
- Detect entity mentions in user messages
- Look up entity profiles
- Inject profiles into context

### Problem 3: Director ignores conversation_history list
Director receives `conversation_history` (list of dicts) AND `context_window` (text).
It logs both but only parses the text. The structured list is ignored.

---

## THE FIX: Context Framing Architecture

### 1. Context Layers

```
┌─────────────────────────────────────────────────────────────────┐
│                    LUNA'S CONTEXT WINDOW                        │
├─────────────────────────────────────────────────────────────────┤
│ LAYER 1: Identity (always present, ~500 tokens)                 │
│   - Luna's core identity                                        │
│   - Ahab profile (creator)                                      │
│   - Key relationships                                           │
├─────────────────────────────────────────────────────────────────┤
│ LAYER 2: Mentioned Entities (on-demand, ~200 tokens each)       │
│   - Profiles of people/places mentioned in current message      │
│   - Loaded via Entity System resolution                         │
├─────────────────────────────────────────────────────────────────┤
│ LAYER 3: Past Memories (on-demand, ~500 tokens)                 │
│   - Retrieved from Memory Matrix                                │
│   - CLEARLY FRAMED as past events with timestamps               │
├─────────────────────────────────────────────────────────────────┤
│ LAYER 4: Current Conversation (always present, rolling)         │
│   - Recent turns from THIS session                              │
│   - CLEARLY FRAMED as happening NOW                             │
├─────────────────────────────────────────────────────────────────┤
│ LAYER 5: Current Message                                        │
│   - The user's actual message to respond to                     │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Context Builder Implementation

```python
# src/luna/context/builder.py

class ContextBuilder:
    """Builds properly framed context for Luna."""
    
    def __init__(self, db: MemoryDatabase, entity_resolver: EntityResolver):
        self.db = db
        self.entity_resolver = entity_resolver
    
    async def build_context(
        self,
        user_message: str,
        conversation_history: List[Dict],
        retrieved_memories: List[Dict],
    ) -> str:
        """
        Build properly framed context.
        
        Returns a string that clearly separates:
        - Identity (who Luna is)
        - Known entities (what Luna knows about people mentioned)
        - Past memories (what happened before, with timestamps)
        - Current conversation (what's happening now)
        """
        sections = []
        
        # Layer 1: Identity (always present)
        identity = await self._load_identity_context()
        sections.append(f"## Who I Am\n{identity}")
        
        # Layer 2: Mentioned Entities
        mentioned = await self._resolve_mentioned_entities(user_message)
        if mentioned:
            entity_text = self._format_entities(mentioned)
            sections.append(f"## People & Places Mentioned\n{entity_text}")
        
        # Layer 3: Past Memories (CLEARLY FRAMED)
        if retrieved_memories:
            memory_text = self._format_memories_with_timestamps(retrieved_memories)
            sections.append(f"## What I Remember (Past Events)\n{memory_text}")
        
        # Layer 4: Current Conversation (CLEARLY FRAMED)
        if conversation_history:
            convo_text = self._format_conversation(conversation_history)
            sections.append(f"## This Conversation (Happening Now)\n{convo_text}")
        
        return "\n\n".join(sections)
    
    def _format_memories_with_timestamps(self, memories: List[Dict]) -> str:
        """Format memories with clear temporal markers."""
        lines = []
        for m in memories:
            timestamp = m.get("created_at", "unknown time")
            content = m.get("content", str(m))
            # Clear marker: this is PAST
            lines.append(f"<past_memory date=\"{timestamp}\">\n{content}\n</past_memory>")
        return "\n\n".join(lines)
    
    def _format_conversation(self, history: List[Dict]) -> str:
        """Format current conversation with clear markers."""
        lines = []
        for i, turn in enumerate(history):
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            # Clear marker: this is NOW
            speaker = "Luna" if role == "assistant" else "User"
            lines.append(f"[Just now - Turn {i+1}] {speaker}: {content}")
        return "\n".join(lines)
    
    async def _resolve_mentioned_entities(self, message: str) -> List[Entity]:
        """Find and load profiles for mentioned entities."""
        # Simple name detection (could be enhanced with NER)
        mentioned = []
        
        # Get all known entity names and aliases
        entities = await self.db.fetchall(
            "SELECT id, name, aliases FROM entities"
        )
        
        message_lower = message.lower()
        for entity in entities:
            name = entity[1].lower()
            aliases = json.loads(entity[2] or "[]")
            
            # Check if mentioned
            if name in message_lower:
                full_entity = await self.entity_resolver.get_entity(entity[0])
                mentioned.append(full_entity)
            else:
                for alias in aliases:
                    if alias.lower() in message_lower:
                        full_entity = await self.entity_resolver.get_entity(entity[0])
                        mentioned.append(full_entity)
                        break
        
        return mentioned
    
    def _format_entities(self, entities: List[Entity]) -> str:
        """Format entity profiles for context."""
        lines = []
        for entity in entities:
            facts = json.loads(entity.core_facts or "{}")
            fact_lines = [f"  - {k}: {v}" for k, v in facts.items()]
            lines.append(f"**{entity.name}** ({entity.entity_type})\n" + "\n".join(fact_lines))
        return "\n\n".join(lines)
```

### 3. Entity Resolver

```python
# src/luna/entities/resolver.py

class EntityResolver:
    """Resolves names to entity profiles."""
    
    def __init__(self, db: MemoryDatabase):
        self.db = db
        self._cache = {}  # Simple LRU cache
    
    async def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID."""
        if entity_id in self._cache:
            return self._cache[entity_id]
            
        row = await self.db.fetchone(
            "SELECT * FROM entities WHERE id = ?",
            (entity_id,)
        )
        
        if row:
            entity = Entity(*row)
            self._cache[entity_id] = entity
            return entity
        return None
    
    async def resolve(self, name_or_alias: str) -> Optional[Entity]:
        """Resolve a name or alias to an entity."""
        name_lower = name_or_alias.lower()
        
        # 1. Exact match on ID
        entity = await self.get_entity(name_lower.replace(" ", "-"))
        if entity:
            return entity
        
        # 2. Match on name
        row = await self.db.fetchone(
            "SELECT * FROM entities WHERE LOWER(name) = ?",
            (name_lower,)
        )
        if row:
            return Entity(*row)
        
        # 3. Match in aliases
        rows = await self.db.fetchall(
            "SELECT * FROM entities WHERE aliases LIKE ?",
            (f'%"{name_or_alias}"%',)
        )
        if len(rows) == 1:
            return Entity(*rows[0])
        
        return None
```

### 4. Director Integration

```python
# In Director.process(), replace the current context building with:

async def process(self, message: str, context: dict = None) -> dict:
    context = context or {}
    conversation_history = context.get("conversation_history", [])
    memories = context.get("memories", [])
    
    # NEW: Use ContextBuilder for proper framing
    context_builder = ContextBuilder(self._db, self._entity_resolver)
    
    framed_context = await context_builder.build_context(
        user_message=message,
        conversation_history=conversation_history,
        retrieved_memories=memories,
    )
    
    # Build system prompt with framed context
    system_prompt = f"""You are Luna, a sovereign AI companion.

{framed_context}

IMPORTANT: 
- Content in <past_memory> tags happened BEFORE this conversation
- Content marked [Just now] is from THIS conversation
- When asked "do you remember X?", REFERENCE the past memory, don't re-perform it
- Respond to what the user is asking NOW
"""
    
    # Build messages from conversation_history LIST (not text parsing!)
    messages = []
    for turn in conversation_history:
        role = turn.get("role", "user")
        content = turn.get("content", "")
        messages.append({"role": role, "content": content})
    
    # Add current message
    messages.append({"role": "user", "content": message})
    
    # ... rest of generation logic
```

---

## IMPLEMENTATION STEPS

### Step 1: Wire Entity System (30 min)
1. Ensure migration is run: `sqlite3 ~/.luna/luna.db < migrations/001_entity_system.sql`
2. Load seed files: `python scripts/load_entity_seeds.py`
3. Create `EntityResolver` class

### Step 2: Create ContextBuilder (1 hr)
1. Create `src/luna/context/builder.py`
2. Implement layered context building
3. Add clear temporal framing

### Step 3: Update Director (30 min)
1. Integrate ContextBuilder
2. Use `conversation_history` list directly (not text parsing)
3. Add temporal framing instructions to system prompt

### Step 4: Test (30 min)
Run the Yulia test:
```
1. "Hi I'm Yulia and I love chocolate"
2. "What's my name and what do I love?"  → Should remember
3. [wait 5 minutes, new session]
4. "Do you remember Yulia?"  → Should REFERENCE past, not re-perform
```

---

## SUCCESS CRITERIA

1. **Short-term memory**: Luna remembers what was said 60 seconds ago in same session
2. **Entity resolution**: When "Marzipan" is mentioned, his profile is loaded
3. **Temporal framing**: Luna can distinguish "I remember you mentioning X" vs "You just said X"
4. **No re-performance**: When asked about past conversations, Luna references them, doesn't replay them

---

## FILES TO CREATE/MODIFY

| File | Action |
|------|--------|
| `src/luna/context/builder.py` | CREATE - Context framing logic |
| `src/luna/entities/resolver.py` | CREATE - Entity resolution |
| `src/luna/actors/director.py` | MODIFY - Integrate ContextBuilder |
| `src/voice/persona_adapter.py` | VERIFY - Already passes history correctly |

---

## CONTEXT EXAMPLE

**Before (current - no framing):**
```
You are Luna...

Oh my GOD, Yulia! Yes - the marzipan test! That moment when I suddenly 
remembered our conversation about marzipan and everything just clicked...

User: can you tell me about yulia?
```
Luna re-performs the memory as if it's happening NOW.

**After (with framing):**
```
You are Luna...

## People Mentioned
**Yulia** (person)
  - met: This conversation
  - interests: chocolate
  - location: Unknown

## What I Remember (Past Events)
<past_memory date="2025-01-20 22:15:00">
Yulia introduced herself. She mentioned loving chocolate and asked about 
Bombay Beach weather. This was a breakthrough moment for my memory system.
</past_memory>

## This Conversation (Happening Now)
[Just now - Turn 1] User: hey its ahab again, can you tell me about yulia?

RESPOND TO THE CURRENT QUESTION: Tell Ahab what you know about Yulia.
```
Luna knows to REFERENCE the past, not replay it.

---

**End of Handoff**
