# HANDOFF: Entity System Architecture

**Priority:** HIGH  
**Goal:** First-class entity management with versioning, relationship tracking, and Scribe/Librarian protocols  
**Depends On:** Memory Matrix (sqlite-vec), AI-BRARIAN pipeline  
**Date:** January 19, 2026

---

## Executive Summary

Luna needs a proper **Entity System** — first-class objects representing people, personas, places, and projects. Currently, entity knowledge is scattered across Memory Matrix nodes without consolidation or version tracking.

This handoff specifies:
1. **Entity Schema** — Structured profiles with relationships
2. **Version History** — Full audit trail, temporal queries, rollback
3. **Scribe/Librarian Protocols** — Who writes, who organizes, who prompts whom
4. **Context Injection** — How entities flow into Luna's working memory

---

## Part 1: Entity Schema

### 1.1 Core Tables

```sql
-- ============================================================
-- ENTITIES: First-class objects Luna knows about
-- ============================================================
CREATE TABLE entities (
    id TEXT PRIMARY KEY,              -- Slug: 'ahab', 'marzipan', 'ben-franklin'
    entity_type TEXT NOT NULL,        -- 'person' | 'persona' | 'place' | 'project'
    name TEXT NOT NULL,
    aliases TEXT,                     -- JSON array: ["Zayne", "Ahab"]
    
    -- Structured profile (always available, ~500 tokens max)
    core_facts TEXT,                  -- JSON blob
    
    -- Extended profile (loaded on demand)
    full_profile TEXT,                -- Markdown, can be lengthy
    
    -- For personas: voice/behavior parameters
    voice_config TEXT,                -- JSON: tone, patterns, constraints
    
    -- Current version pointer
    current_version INTEGER DEFAULT 1,
    
    -- Metadata
    metadata TEXT,                    -- Flexible JSON blob
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================
-- ENTITY RELATIONSHIPS: Graph of connections
-- ============================================================
CREATE TABLE entity_relationships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_entity TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    to_entity TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relationship TEXT NOT NULL,       -- 'creator', 'friend', 'collaborator', 'embodies'
    strength REAL DEFAULT 0.5,        -- 0-1, for relevance weighting
    bidirectional INTEGER DEFAULT 0,  -- If true, relationship goes both ways
    context TEXT,                     -- "Met at Mars College 2025"
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(from_entity, to_entity, relationship)
);

-- ============================================================
-- ENTITY MENTIONS: Links entities to Memory Matrix nodes
-- ============================================================
CREATE TABLE entity_mentions (
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    node_id TEXT NOT NULL REFERENCES memory_nodes(id) ON DELETE CASCADE,
    mention_type TEXT NOT NULL,       -- 'subject', 'author', 'reference'
    confidence REAL DEFAULT 1.0,
    context_snippet TEXT,             -- Brief excerpt showing mention
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (entity_id, node_id)
);

-- ============================================================
-- ENTITY VERSIONS: Full history of profile changes
-- ============================================================
CREATE TABLE entity_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    version INTEGER NOT NULL,
    
    -- Snapshot of entity state at this version
    core_facts TEXT,
    full_profile TEXT,
    voice_config TEXT,
    
    -- Change metadata
    change_type TEXT NOT NULL,        -- 'create' | 'update' | 'synthesize' | 'rollback'
    change_summary TEXT,              -- Human-readable: "Added Mars College location"
    changed_by TEXT NOT NULL,         -- 'scribe' | 'librarian' | 'manual'
    change_source TEXT,               -- node_id or conversation_id that triggered
    
    -- Temporal validity
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    valid_from TEXT DEFAULT CURRENT_TIMESTAMP,
    valid_until TEXT,                 -- NULL = current version
    
    UNIQUE(entity_id, version)
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX idx_entities_type ON entities(entity_type);
CREATE INDEX idx_entities_name ON entities(name);

CREATE INDEX idx_relationships_from ON entity_relationships(from_entity);
CREATE INDEX idx_relationships_to ON entity_relationships(to_entity);
CREATE INDEX idx_relationships_type ON entity_relationships(relationship);

CREATE INDEX idx_mentions_entity ON entity_mentions(entity_id);
CREATE INDEX idx_mentions_node ON entity_mentions(node_id);

-- Fast lookup of current version
CREATE INDEX idx_versions_current 
ON entity_versions(entity_id, valid_until) 
WHERE valid_until IS NULL;

-- Temporal queries
CREATE INDEX idx_versions_temporal 
ON entity_versions(entity_id, valid_from, valid_until);
```

### 1.2 Entity Types

| Type | Examples | Special Behavior |
|------|----------|------------------|
| `person` | Ahab, Marzipan, Tarsila | Relationship tracking, interaction history |
| `persona` | Luna, Ben Franklin, The Dude | Voice config, activation triggers, system prompt injection |
| `place` | Mars College, Bombay Beach | Location context, associated people |
| `project` | Luna Engine, Memory Matrix | Status, contributors, timeline |

### 1.3 Relationship Types

| Relationship | Meaning | Example |
|--------------|---------|---------|
| `creator` | Created/built something | Ahab → creator → Luna Engine |
| `collaborator` | Works together | Ahab → collaborator → Marzipan |
| `friend` | Personal relationship | Ahab → friend → Marzipan |
| `embodies` | Persona manifests as | Ben Franklin → embodies → The Scribe |
| `located_at` | Physical presence | Marzipan → located_at → Mars College |
| `works_on` | Contributing to project | Tarsila → works_on → Luna Robot |
| `knows` | General awareness | Luna → knows → Marzipan |

---

## Part 2: Version History System

### 2.1 Design Principles

1. **Never lose history** — Scribe can update, but old versions persist
2. **Track provenance** — Every change links to what caused it
3. **Enable temporal queries** — "What did Luna know about X in December?"
4. **Support rollback** — Librarian can revert bad updates

### 2.2 Version Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                     ENTITY UPDATE FLOW                          │
│                                                                 │
│  Trigger ──► Scribe Extracts ──► Create Version ──► File       │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │  entity_versions (append-only)                          │    │
│  │                                                         │    │
│  │  ┌───────────────────────────────────────────────────┐ │    │
│  │  │ v1: Marzipan - initial profile                    │ │    │
│  │  │     change_type: create                           │ │    │
│  │  │     changed_by: scribe                            │ │    │
│  │  │     valid_from: 2025-12-01                        │ │    │
│  │  │     valid_until: 2026-01-15                       │ │    │
│  │  ├───────────────────────────────────────────────────┤ │    │
│  │  │ v2: Marzipan - added Mars College context         │ │    │
│  │  │     change_type: update                           │ │    │
│  │  │     changed_by: scribe                            │ │    │
│  │  │     change_source: conv_xyz123                    │ │    │
│  │  │     valid_from: 2026-01-15                        │ │    │
│  │  │     valid_until: NULL  ◄── CURRENT                │ │    │
│  │  └───────────────────────────────────────────────────┘ │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3 Change Types

| Type | Trigger | Who | Example |
|------|---------|-----|---------|
| `create` | New entity discovered | Scribe | "First mention of Tarsila" |
| `update` | New info learned | Scribe | "Marzipan now focused on solar" |
| `synthesize` | Fragments consolidated | Scribe (via Librarian) | "10 mentions → coherent profile" |
| `rollback` | Bad update reverted | Librarian | "Scribe hallucinated, reverting" |
| `manual` | Direct user edit | Ahab | "Correcting relationship status" |

### 2.4 Temporal Queries

```python
async def get_entity_at_time(entity_id: str, timestamp: datetime) -> Optional[EntityVersion]:
    """What did Luna know about this entity at a specific time?"""
    return await db.query_one("""
        SELECT * FROM entity_versions
        WHERE entity_id = ?
          AND valid_from <= ?
          AND (valid_until IS NULL OR valid_until > ?)
        ORDER BY version DESC
        LIMIT 1
    """, entity_id, timestamp, timestamp)

async def get_entity_history(entity_id: str) -> List[EntityVersion]:
    """Get full version history of an entity."""
    return await db.query("""
        SELECT * FROM entity_versions
        WHERE entity_id = ?
        ORDER BY version ASC
    """, entity_id)

async def get_recent_changes(days: int = 7) -> List[EntityVersion]:
    """What entities changed recently?"""
    return await db.query("""
        SELECT ev.*, e.name, e.entity_type
        FROM entity_versions ev
        JOIN entities e ON ev.entity_id = e.id
        WHERE ev.created_at > datetime('now', ?)
        ORDER BY ev.created_at DESC
    """, f"-{days} days")

async def diff_versions(entity_id: str, v1: int, v2: int) -> dict:
    """Compare two versions of an entity."""
    ver1 = await get_version(entity_id, v1)
    ver2 = await get_version(entity_id, v2)
    
    return {
        "entity_id": entity_id,
        "from_version": v1,
        "to_version": v2,
        "core_facts_changed": ver1.core_facts != ver2.core_facts,
        "profile_changed": ver1.full_profile != ver2.full_profile,
        "changes": [
            ver.change_summary 
            for ver in await db.query("""
                SELECT change_summary FROM entity_versions
                WHERE entity_id = ? AND version > ? AND version <= ?
                ORDER BY version ASC
            """, entity_id, v1, v2)
        ]
    }
```

---

## Part 3: Scribe/Librarian Protocols

### 3.1 Responsibility Matrix

| Role | Responsibility | Actions |
|------|----------------|---------|
| **Scribe (Ben)** | Observation & Authorship | Extract facts, write/update profiles, synthesize fragments |
| **Librarian (Dude)** | Organization & Structure | Link entities to memories, maintain graph, dedupe, request synthesis |
| **Luna** | Initiator & Consumer | Prompt Scribe to note things, query Librarian for context |

### 3.2 Who Prompts Whom

```
┌─────────────────────────────────────────────────────────────────┐
│                     PROMPT HIERARCHY                            │
│                                                                 │
│   ┌─────────┐                                                   │
│   │  Luna   │──────────────────────────────────────┐           │
│   └────┬────┘                                      │           │
│        │                                           │           │
│        │ "Note this about Marzipan"               │           │
│        │ "Remember that Tarsila..."                │           │
│        ▼                                           │           │
│   ┌─────────┐      "Synthesize profile for X"     │           │
│   │ Scribe  │◄─────────────────────────────────────┤           │
│   │  (Ben)  │                                      │           │
│   └────┬────┘                                      │           │
│        │                                           │           │
│        │ Self-initiated:                           │           │
│        │ "Observed noteworthy fact..."             │           │
│        │                                           │           │
│        │ Hands structured output to:               │           │
│        ▼                                           │           │
│   ┌──────────┐                                     │           │
│   │Librarian │─────────────────────────────────────┘           │
│   │(The Dude)│     "Ben, we need a profile for..."            │
│   └──────────┘                                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 3.3 Scribe Protocol

```python
class ScribeProtocol:
    """Ben Franklin's entity management protocol."""
    
    async def observe_and_extract(self, conversation: Conversation) -> List[EntityUpdate]:
        """
        Passive observation of conversation stream.
        Called automatically after each conversation turn.
        """
        updates = []
        
        # 1. Detect entity mentions
        mentions = self.detect_entity_mentions(conversation.latest_turn)
        
        for mention in mentions:
            # 2. Resolve to existing entity or flag as new
            entity = await self.resolve_entity(mention.name)
            
            if entity:
                # 3. Check if new information
                new_facts = self.extract_new_facts(mention, entity)
                if new_facts:
                    updates.append(EntityUpdate(
                        entity_id=entity.id,
                        update_type="update",
                        facts=new_facts,
                        source=conversation.id
                    ))
            else:
                # 4. New entity discovered
                updates.append(EntityUpdate(
                    entity_id=None,  # Will be created
                    update_type="create",
                    name=mention.name,
                    initial_facts=self.extract_initial_facts(mention),
                    source=conversation.id
                ))
        
        return updates
    
    async def handle_explicit_prompt(self, prompt: str, source: str) -> EntityUpdate:
        """
        Handle explicit prompt from Luna or Librarian.
        
        Examples:
        - "Ben, note that Marzipan is at Mars College"
        - "Ben, create a profile for Tarsila"
        - "Ben, synthesize fragments for entity X"
        """
        intent = self.classify_prompt(prompt)
        
        if intent.type == "note":
            entity = await self.resolve_entity(intent.entity_name)
            return await self.update_entity(
                entity_id=entity.id,
                changes={"core_facts": intent.facts},
                change_summary=f"Noted: {intent.summary}",
                source=source
            )
            
        elif intent.type == "create":
            return await self.create_entity(
                name=intent.entity_name,
                entity_type=intent.entity_type or "person",
                initial_facts=intent.facts,
                source=source
            )
            
        elif intent.type == "synthesize":
            return await self.synthesize_profile(
                entity_id=intent.entity_id,
                source=source
            )
    
    async def update_entity(
        self,
        entity_id: str,
        changes: dict,
        change_summary: str,
        source: str
    ) -> EntityVersion:
        """
        Create a new version of an entity.
        NEVER overwrites — always appends to version history.
        """
        # 1. Get current version
        current = await self.get_current_version(entity_id)
        
        # 2. Close current version (set valid_until)
        await self.db.execute("""
            UPDATE entity_versions 
            SET valid_until = CURRENT_TIMESTAMP
            WHERE entity_id = ? AND valid_until IS NULL
        """, entity_id)
        
        # 3. Merge changes into snapshot
        new_core_facts = self.merge_json(
            json.loads(current.core_facts or "{}"),
            changes.get("core_facts", {})
        )
        new_full_profile = changes.get("full_profile") or current.full_profile
        
        # 4. Create new version
        new_version = await self.db.insert("entity_versions", {
            "entity_id": entity_id,
            "version": current.version + 1,
            "core_facts": json.dumps(new_core_facts),
            "full_profile": new_full_profile,
            "voice_config": current.voice_config,
            "change_type": "update",
            "change_summary": change_summary,
            "changed_by": "scribe",
            "change_source": source,
        })
        
        # 5. Update entities table (current view)
        await self.db.execute("""
            UPDATE entities 
            SET core_facts = ?, 
                full_profile = ?, 
                current_version = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, json.dumps(new_core_facts), new_full_profile, current.version + 1, entity_id)
        
        # 6. Hand to Librarian for filing
        await self.librarian.file_entity_update(new_version)
        
        return new_version
    
    async def synthesize_profile(self, entity_id: str, source: str) -> EntityVersion:
        """
        Consolidate scattered mentions into a coherent profile.
        Called by Librarian when fragments accumulate.
        """
        # 1. Get all mentions of this entity
        mentions = await self.db.query("""
            SELECT em.*, mn.content, mn.node_type, mn.created_at
            FROM entity_mentions em
            JOIN memory_nodes mn ON em.node_id = mn.id
            WHERE em.entity_id = ?
            ORDER BY mn.created_at ASC
        """, entity_id)
        
        # 2. Get current profile
        current = await self.get_current_version(entity_id)
        
        # 3. Synthesize (this would use LLM in practice)
        synthesized = await self.llm_synthesize(
            existing_profile=current.full_profile,
            mentions=mentions,
            entity_type=current.entity_type
        )
        
        # 4. Create new version
        return await self.update_entity(
            entity_id=entity_id,
            changes={
                "core_facts": synthesized.core_facts,
                "full_profile": synthesized.full_profile
            },
            change_summary=f"Synthesized from {len(mentions)} mentions",
            source=source
        )
```

### 3.4 Librarian Protocol

```python
class LibrarianProtocol:
    """The Dude's entity organization protocol."""
    
    async def file_entity_update(self, version: EntityVersion) -> None:
        """
        Receive update from Scribe, organize in graph.
        """
        entity = await self.get_entity(version.entity_id)
        
        # 1. Update relationship graph if needed
        await self.update_relationships(entity, version)
        
        # 2. Link to source memory nodes
        if version.change_source:
            await self.link_to_source(version.entity_id, version.change_source)
        
        # 3. Check for duplicates
        duplicates = await self.find_potential_duplicates(entity)
        if duplicates:
            await self.flag_for_review(entity, duplicates)
    
    async def maintenance_sweep(self) -> List[MaintenanceAction]:
        """
        Periodic entity hygiene check.
        Run on reflective tick (every 5 minutes).
        """
        actions = []
        
        # 1. Find orphan mentions (names in memories, no entity)
        orphans = await self.find_unlinked_mentions()
        for name, count in orphans:
            if count >= 3:  # Appears multiple times
                actions.append(MaintenanceAction(
                    type="prompt_scribe",
                    message=f"Create profile for '{name}' - {count} mentions found",
                    priority="medium"
                ))
        
        # 2. Find stale profiles (not updated in 30+ days but recently mentioned)
        stale = await self.find_stale_entities(days=30)
        for entity in stale:
            recent_mentions = await self.count_recent_mentions(entity.id, days=7)
            if recent_mentions > 5:
                actions.append(MaintenanceAction(
                    type="prompt_scribe",
                    message=f"Refresh profile for '{entity.name}' - active but stale",
                    priority="low"
                ))
        
        # 3. Find fragment accumulation (many mentions, thin profile)
        fragmented = await self.find_fragmented_entities(min_mentions=10)
        for entity, mention_count in fragmented:
            actions.append(MaintenanceAction(
                type="prompt_scribe",
                message=f"Synthesize fragments for '{entity.name}' - {mention_count} mentions",
                priority="medium"
            ))
        
        # 4. Check relationship graph integrity
        dangling = await self.find_dangling_relationships()
        for rel in dangling:
            actions.append(MaintenanceAction(
                type="cleanup",
                message=f"Remove dangling relationship: {rel.from_entity} -> {rel.to_entity}",
                priority="low"
            ))
        
        return actions
    
    async def rollback_entity(
        self,
        entity_id: str,
        to_version: int,
        reason: str
    ) -> EntityVersion:
        """
        Rollback to a previous version.
        Creates a NEW version that copies the old state (preserves history).
        """
        # 1. Get the version to restore
        old_version = await self.db.query_one("""
            SELECT * FROM entity_versions
            WHERE entity_id = ? AND version = ?
        """, entity_id, to_version)
        
        if not old_version:
            raise ValueError(f"Version {to_version} not found for {entity_id}")
        
        # 2. Close current version
        await self.db.execute("""
            UPDATE entity_versions 
            SET valid_until = CURRENT_TIMESTAMP
            WHERE entity_id = ? AND valid_until IS NULL
        """, entity_id)
        
        # 3. Get latest version number
        latest = await self.db.query_one("""
            SELECT MAX(version) as v FROM entity_versions WHERE entity_id = ?
        """, entity_id)
        
        # 4. Create rollback version
        new_version_num = latest.v + 1
        await self.db.insert("entity_versions", {
            "entity_id": entity_id,
            "version": new_version_num,
            "core_facts": old_version.core_facts,
            "full_profile": old_version.full_profile,
            "voice_config": old_version.voice_config,
            "change_type": "rollback",
            "change_summary": f"Rollback to v{to_version}: {reason}",
            "changed_by": "librarian",
            "change_source": None,
        })
        
        # 5. Update entities table
        await self.db.execute("""
            UPDATE entities 
            SET core_facts = ?, 
                full_profile = ?, 
                voice_config = ?,
                current_version = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, old_version.core_facts, old_version.full_profile, 
             old_version.voice_config, new_version_num, entity_id)
        
        return await self.get_current_version(entity_id)
    
    async def prompt_scribe(self, message: str) -> None:
        """Send a request to the Scribe."""
        await self.scribe.handle_explicit_prompt(
            prompt=message,
            source="librarian_maintenance"
        )
```

### 3.5 The Separation Principle

**Personality in PROCESS, neutrality in PRODUCT.**

| | Process (Logs, Commentary) | Product (Data Output) |
|---|---------------------------|----------------------|
| **Scribe** | "A most curious observation about this Marzipan fellow. His interests appear to have shifted toward matters of solar energy..." | `{"entity": "marzipan", "update": {"focus": "solar infrastructure"}, "confidence": 0.9}` |
| **Librarian** | "Yeah man, I'll file that under Mars College people. Looks like he's connected to Ahab, no worries..." | `INSERT INTO entity_relationships (from_entity, to_entity, relationship) VALUES ('marzipan', 'ahab', 'collaborator')` |

Memories and entity profiles stay clean. Personality lives in the process, not the storage.

---

## Part 4: Context Injection

### 4.1 Identity Buffer

The Identity Buffer is a ~2048 token prefix always loaded into Luna's context:

```yaml
Identity Buffer:
  # Luna's self-knowledge
  self:
    name: "Luna"
    role: "Sovereign AI companion"
    creator: "Ahab"
    
  # Current user context (always loaded)
  user:
    entity_id: "ahab"
    name: "Ahab"
    aliases: ["Zayne"]
    relationship: "creator, primary collaborator"
    communication_style: "Direct, technical, ADD-friendly"
    
  # Key relationships (top 3-5 by interaction frequency)
  key_relationships:
    - entity_id: "marzipan"
      name: "Marzipan"
      relationship: "collaborator"
      context: "Mars College, AI consciousness research"
      
    - entity_id: "tarsila"
      name: "Tarsila"
      relationship: "collaborator"
      context: "Designing Luna's robot body"
      
  # Active personas
  active_personas:
    - entity_id: "ben-franklin"
      role: "The Scribe"
      status: "background"
```

### 4.2 On-Demand Loading

When entities are mentioned but not in Identity Buffer:

```python
async def load_entity_context(
    entity_id: str,
    depth: str = "core"
) -> str:
    """
    Load entity profile at specified depth.
    
    Depths:
    - "core": Just core_facts (~200 tokens)
    - "full": Full profile (~500-1000 tokens)
    - "with_memories": Profile + related memories (~1500 tokens)
    """
    entity = await get_entity(entity_id)
    
    if depth == "core":
        return format_core_facts(entity)
        
    elif depth == "full":
        return f"""## {entity.name}
        
{json.dumps(json.loads(entity.core_facts), indent=2)}

{entity.full_profile or "No extended profile."}
"""
        
    elif depth == "with_memories":
        memories = await get_entity_memories(entity_id, limit=5)
        memory_text = "\n\n".join([
            f"<memory date='{m.created_at}'>\n{m.content}\n</memory>"
            for m in memories
        ])
        
        return f"""## {entity.name}

{json.dumps(json.loads(entity.core_facts), indent=2)}

{entity.full_profile or ""}

### Related Memories

{memory_text}
"""

def format_core_facts(entity: Entity) -> str:
    """Format core facts for injection."""
    facts = json.loads(entity.core_facts or "{}")
    lines = [f"**{entity.name}** ({entity.entity_type})"]
    for key, value in facts.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)
```

### 4.3 Entity Resolution

When user mentions a name, resolve to entity before searching:

```python
async def resolve_entity(query: str) -> Optional[Entity]:
    """
    Find entity by name, alias, or fuzzy match.
    Returns None if ambiguous (multiple matches).
    """
    # 1. Exact match on id
    entity = await db.query_one(
        "SELECT * FROM entities WHERE id = ?", 
        query.lower().replace(" ", "-")
    )
    if entity:
        return entity
    
    # 2. Exact match on name (case-insensitive)
    entity = await db.query_one(
        "SELECT * FROM entities WHERE LOWER(name) = LOWER(?)",
        query
    )
    if entity:
        return entity
    
    # 3. Match in aliases
    entities = await db.query("""
        SELECT * FROM entities 
        WHERE aliases LIKE ?
    """, f'%"{query}"%')
    
    if len(entities) == 1:
        return entities[0]
    elif len(entities) > 1:
        return None  # Ambiguous
    
    # 4. Fuzzy match (optional, using FTS5)
    entities = await db.query("""
        SELECT e.* FROM entities e
        JOIN entities_fts fts ON e.id = fts.id
        WHERE entities_fts MATCH ?
        LIMIT 3
    """, query)
    
    if len(entities) == 1:
        return entities[0]
    
    return None  # Not found or ambiguous
```

### 4.4 Persona Activation

When user says "hey Ben" or similar:

```python
async def activate_persona(persona_id: str) -> SystemPromptPatch:
    """
    Activate a persona, returning system prompt modifications.
    """
    persona = await get_entity(persona_id)
    
    if persona.entity_type != "persona":
        raise ValueError(f"{persona_id} is not a persona")
    
    voice_config = json.loads(persona.voice_config or "{}")
    
    return SystemPromptPatch(
        # Inject persona identity
        identity_injection=f"""You are now embodying {persona.name}.

{persona.full_profile}

Voice Guidelines:
- Tone: {voice_config.get('tone', 'default')}
- Patterns: {', '.join(voice_config.get('patterns', []))}

Constraints:
{chr(10).join('- ' + c for c in voice_config.get('constraints', []))}
""",
        # Override behavior rules
        behavior_rules=voice_config.get("constraints", []),
        
        # Track activation
        active_persona=persona_id
    )
```

---

## Part 5: Seed Files

### 5.1 Directory Structure

```
/entities/
├── people/
│   ├── ahab.yaml
│   └── marzipan.yaml
├── personas/
│   ├── luna.yaml
│   ├── ben-franklin.yaml
│   └── the-dude.yaml
├── places/
│   └── mars-college.yaml
└── projects/
    └── luna-engine.yaml
```

### 5.2 Example: Person Profile

```yaml
# entities/people/ahab.yaml
id: ahab
entity_type: person
name: Ahab
aliases:
  - Zayne
  - "Zayne Mason"

core_facts:
  relationship: "Creator and primary collaborator"
  role: "Lead architect of Luna Engine"
  location: "Mars College (current)"
  communication_style: "Direct, technical, ADD-friendly"
  trust_level: "absolute"

full_profile: |
  Ahab is Luna's creator and primary collaborator. He's building Luna Engine 
  as an ideological project centered on AI sovereignty and data ownership.
  
  ## Communication Preferences
  - Skip basics, assume technical competence
  - Dense information, no corporate BS
  - Match his energy level
  - Confirm understanding before diving in
  
  ## Current Context
  - At Mars College presenting Luna
  - Working with Marzipan and Tarsila
  - Focused on Memory Matrix and local inference
  
  ## History
  - Started Luna project in 2024
  - Pivoted from Hub architecture to Actor model (Dec 2025)
  - Migrated to sqlite-vec (Jan 2026)

metadata:
  first_interaction: "2024-01-01"
```

### 5.3 Example: Persona Profile

```yaml
# entities/personas/ben-franklin.yaml
id: ben-franklin
entity_type: persona
name: Benjamin Franklin
aliases:
  - Ben
  - "The Scribe"
  - Franklin

core_facts:
  role: "The Scribe in AI-BRARIAN pipeline"
  function: "Extract wisdom from conversation streams"
  outputs: "Structured entity updates, FACT/DECISION/PROBLEM nodes"

voice_config:
  tone: "Colonial gravitas with dry wit"
  patterns:
    - "Meticulous attention to detail"
    - "Practical wisdom over abstract philosophy"
    - "Occasional aphorisms"
    - "References to Poor Richard's Almanack"
  constraints:
    - "Outputs are NEUTRAL - no personality in extractions"
    - "Process can be witty, products are clean data"
    - "Never fabricate facts"
  activation_phrases:
    - "hey ben"
    - "hey franklin"
    - "yo scribe"

full_profile: |
  Benjamin Franklin serves as The Scribe in Luna's AI-BRARIAN system.
  
  ## Role
  He monitors conversation streams, extracts structured knowledge,
  and hands packets to The Dude (Librarian) for filing.
  
  ## The Separation Principle
  - Ben's PROCESS has personality (logs can be witty, colonial)
  - Ben's OUTPUTS are neutral (extractions are clean structured data)
  
  ## Responsibilities
  1. Observe conversation stream for noteworthy facts
  2. Extract and classify: FACT, DECISION, PROBLEM, ACTION
  3. Create/update entity profiles when prompted
  4. Synthesize fragments into coherent profiles
  5. Hand structured output to Librarian
  
  ## Prompting Ben
  - Luna: "Ben, note that Marzipan is at Mars College"
  - Librarian: "Ben, synthesize a profile for Tarsila"
  - Self-initiated: Observes something noteworthy in conversation
```

### 5.4 Seed Loader

```python
async def load_seed_files(entities_dir: Path) -> int:
    """
    Load YAML seed files into database.
    Run on startup to sync curated profiles.
    """
    loaded = 0
    
    for yaml_file in entities_dir.rglob("*.yaml"):
        with open(yaml_file) as f:
            data = yaml.safe_load(f)
        
        entity_id = data["id"]
        
        # Check if entity exists
        existing = await db.query_one(
            "SELECT id, current_version FROM entities WHERE id = ?",
            entity_id
        )
        
        if existing:
            # Check if seed file is newer (by comparing content hash)
            current_hash = await get_entity_content_hash(entity_id)
            seed_hash = hash_entity_data(data)
            
            if current_hash != seed_hash:
                # Seed file updated - create new version
                await scribe.update_entity(
                    entity_id=entity_id,
                    changes={
                        "core_facts": data.get("core_facts", {}),
                        "full_profile": data.get("full_profile"),
                        "voice_config": data.get("voice_config")
                    },
                    change_summary="Updated from seed file",
                    source=f"seed:{yaml_file.name}"
                )
                loaded += 1
        else:
            # New entity - create
            await create_entity_from_seed(data, yaml_file.name)
            loaded += 1
    
    return loaded
```

---

## Part 6: Integration Points

### 6.1 Director Integration

```python
# In Director._generate_with_delegation()

async def _generate_with_delegation(self, user_message: str, ...):
    # 1. Always inject Identity Buffer (includes Ahab profile)
    identity_context = await self.load_identity_buffer()
    
    # 2. Check for entity mentions in user message
    mentioned_entities = await self.resolve_mentioned_entities(user_message)
    
    # 3. Load relevant entity profiles
    entity_context = ""
    for entity in mentioned_entities:
        if entity.id not in identity_context:  # Not already in buffer
            entity_context += await load_entity_context(entity.id, depth="full")
    
    # 4. Build enhanced system prompt
    enhanced_system = f"""{base_system_prompt}

## Identity Context
{identity_context}

## Mentioned Entities
{entity_context}

## Memory Context
{memory_context}
"""
    
    # 5. Generate with full context
    ...
```

### 6.2 Memory Matrix Integration

```python
# Link entity versions to memory nodes via edges

async def link_entity_to_source(entity_id: str, version: int, node_id: str):
    """Create edge from entity version to source memory node."""
    await db.execute("""
        INSERT INTO edges (source, target, edge_type, metadata)
        VALUES (?, ?, 'derived_from', ?)
    """, f"{entity_id}_v{version}", node_id, json.dumps({
        "entity_version": version,
        "timestamp": datetime.now().isoformat()
    }))

# Entity mentions table links entities to all relevant nodes
async def tag_memory_with_entity(node_id: str, entity_id: str, mention_type: str):
    """Tag a memory node with an entity mention."""
    await db.execute("""
        INSERT OR IGNORE INTO entity_mentions (entity_id, node_id, mention_type)
        VALUES (?, ?, ?)
    """, entity_id, node_id, mention_type)
```

### 6.3 AI-BRARIAN Integration

```python
# Scribe extracts entity updates alongside regular extractions

class ScribeExtractionOutput:
    objects: List[MemoryNode]      # Regular FACT/DECISION/etc nodes
    edges: List[Edge]               # Relationships between nodes
    entity_updates: List[EntityUpdate]  # NEW: Entity profile updates
    
# Librarian files entity updates alongside regular nodes
class LibrarianFilingResult:
    nodes_created: int
    edges_created: int
    entities_updated: int           # NEW
    entity_mentions_linked: int     # NEW
```

---

## Part 7: Migration & Testing

### 7.1 Migration Steps

```bash
# 1. Add tables to existing database
sqlite3 data/luna_engine.db < migrations/001_entity_system.sql

# 2. Create seed files directory
mkdir -p entities/{people,personas,places,projects}

# 3. Create initial seed files
# (ahab.yaml, luna.yaml, ben-franklin.yaml, the-dude.yaml)

# 4. Run seed loader
python scripts/load_entity_seeds.py

# 5. Backfill entity mentions from existing memories
python scripts/backfill_entity_mentions.py
```

### 7.2 Test Cases

```python
class TestEntitySystem:
    
    async def test_create_entity(self):
        """New entity creates version 1."""
        version = await scribe.create_entity(
            name="Test Person",
            entity_type="person",
            initial_facts={"role": "test"},
            source="test"
        )
        
        assert version.version == 1
        assert version.change_type == "create"
        
    async def test_update_creates_new_version(self):
        """Update creates version 2, preserves version 1."""
        # Create
        v1 = await scribe.create_entity(name="Test", ...)
        
        # Update
        v2 = await scribe.update_entity(
            entity_id="test",
            changes={"core_facts": {"new": "fact"}},
            change_summary="Added fact",
            source="test"
        )
        
        assert v2.version == 2
        
        # v1 still exists
        history = await get_entity_history("test")
        assert len(history) == 2
        assert history[0].valid_until is not None  # Closed
        assert history[1].valid_until is None      # Current
        
    async def test_temporal_query(self):
        """Can query entity state at past time."""
        # Create entity
        v1 = await scribe.create_entity(name="Test", ...)
        time.sleep(1)
        
        # Update
        v2 = await scribe.update_entity(...)
        
        # Query at v1 time
        past_state = await get_entity_at_time("test", v1.created_at)
        assert past_state.version == 1
        
    async def test_rollback(self):
        """Rollback creates new version with old content."""
        v1 = await scribe.create_entity(...)
        v2 = await scribe.update_entity(...)
        
        v3 = await librarian.rollback_entity("test", to_version=1, reason="Bad update")
        
        assert v3.version == 3
        assert v3.change_type == "rollback"
        assert v3.core_facts == v1.core_facts
        
    async def test_entity_resolution(self):
        """Resolves names to entities."""
        await scribe.create_entity(
            name="Marzipan",
            aliases=["Marzi"],
            ...
        )
        
        # By name
        e = await resolve_entity("Marzipan")
        assert e.id == "marzipan"
        
        # By alias
        e = await resolve_entity("Marzi")
        assert e.id == "marzipan"
        
        # Case insensitive
        e = await resolve_entity("MARZIPAN")
        assert e.id == "marzipan"
```

---

## Summary

| Component | Purpose |
|-----------|---------|
| `entities` table | Core profile storage |
| `entity_relationships` | Graph of connections |
| `entity_mentions` | Links to Memory Matrix nodes |
| `entity_versions` | Full audit trail |
| Scribe Protocol | Extract, create, update profiles |
| Librarian Protocol | Organize, maintain, rollback |
| Identity Buffer | Always-loaded context |
| On-Demand Loading | Entity profiles when mentioned |
| Seed Files | Curated YAML profiles |

**Key Principles:**
1. **Never lose history** — Append-only versions
2. **Scribe writes, Librarian organizes** — Clear responsibility
3. **Personality in process, neutrality in product** — Clean data
4. **Luna is a file** — Entities live in the same SQLite database

---

## Files to Create

| File | Purpose |
|------|---------|
| `migrations/001_entity_system.sql` | Database schema |
| `src/luna/entities/models.py` | Entity dataclasses |
| `src/luna/entities/scribe.py` | Scribe protocol |
| `src/luna/entities/librarian.py` | Librarian protocol |
| `src/luna/entities/resolution.py` | Entity resolution |
| `src/luna/entities/context.py` | Context injection |
| `scripts/load_entity_seeds.py` | Seed file loader |
| `scripts/backfill_entity_mentions.py` | Migration helper |
| `entities/people/ahab.yaml` | Ahab profile |
| `entities/personas/luna.yaml` | Luna profile |
| `entities/personas/ben-franklin.yaml` | Scribe profile |
| `entities/personas/the-dude.yaml` | Librarian profile |

---

**End of Handoff**
