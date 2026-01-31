# HANDOFF: Entity System - Full Implementation

**Created**: 2025-01-20
**Priority**: CRITICAL
**Status**: COMPREHENSIVE IMPLEMENTATION SPEC
**Estimated Effort**: 5-6 hours

---

## EXECUTIVE SUMMARY

The Entity System was designed but never implemented. This handoff provides:
1. **Backfill script** - Creates profiles for Marzipan, Yulia, Tarsila, Kamau from existing memories
2. **EntityResolver** - Looks up profiles when names are mentioned
3. **ContextBuilder** - Frames context with clear temporal markers
4. **Scribe integration** - Auto-creates profiles for new people going forward
5. **Single integration point** - Everything wires through Director.process()

**Goal**: When someone says "Yulia", Luna knows who that is. When Luna meets someone new, she remembers them next time.

---

## PART 1: DATABASE SETUP

### 1.1 Run Migration (if not already done)

```bash
# Check if tables exist
sqlite3 ~/.luna/luna.db "SELECT name FROM sqlite_master WHERE type='table' AND name='entities';"

# If empty, run migration
sqlite3 ~/.luna/luna.db < /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/migrations/001_entity_system.sql

# Verify
sqlite3 ~/.luna/luna.db "SELECT COUNT(*) FROM entities;"
```

### 1.2 Load Seed Files

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python scripts/load_entity_seeds.py
```

This loads: Ahab, Luna, Ben Franklin, The Dude

---

## PART 2: BACKFILL SCRIPT

Create profiles for people Luna has encountered but doesn't have profiles for.

### 2.1 Create the Script

```python
#!/usr/bin/env python3
"""
Backfill Entity Profiles from Memory Matrix

Scans existing memories for mentioned people and creates entity profiles.
Run once to bootstrap, then Scribe handles ongoing creation.

Usage:
    python scripts/backfill_entities_from_memories.py
    python scripts/backfill_entities_from_memories.py --dry-run
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from luna.substrate.database import MemoryDatabase

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# ============================================================================
# KNOWN PEOPLE TO BACKFILL
# Add anyone Luna should know about here
# ============================================================================

KNOWN_PEOPLE = [
    {
        "name": "Marzipan",
        "aliases": ["Marzi"],
        "context": "Friend from Mars College, interested in AI consciousness",
        "relationship_to_ahab": "friend, collaborator",
        "location": "Mars College",
    },
    {
        "name": "Yulia", 
        "aliases": [],
        "context": "Met during voice conversation testing",
        "relationship_to_ahab": "acquaintance",
        "notes": "Loves chocolate, asked about Bombay Beach weather",
    },
    {
        "name": "Tarsila",
        "aliases": ["Tarcila", "Tarsila Neves"],
        "context": "Artist designing Luna's physical robot body",
        "relationship_to_ahab": "collaborator",
        "project": "Luna robot embodiment with raccoon aesthetics",
    },
    {
        "name": "Kamau",
        "aliases": [],
        "context": "Friend from Mars College, runs Akashic Creativity workshop",
        "relationship_to_ahab": "friend",
        "location": "Mars College",
    },
]


async def get_mentions_from_memory(db: MemoryDatabase, name: str) -> List[Dict]:
    """Search Memory Matrix for mentions of a person."""
    try:
        rows = await db.fetchall("""
            SELECT id, content, node_type, created_at 
            FROM memory_nodes 
            WHERE content LIKE ? 
            ORDER BY created_at DESC
            LIMIT 20
        """, (f"%{name}%",))
        
        return [
            {
                "id": row[0],
                "content": row[1],
                "node_type": row[2],
                "created_at": row[3],
            }
            for row in rows
        ] if rows else []
    except Exception as e:
        logger.warning(f"Could not search memories for {name}: {e}")
        return []


def extract_facts_from_mentions(person: Dict, mentions: List[Dict]) -> Dict:
    """
    Extract structured facts from memory mentions.
    
    In production, this could use an LLM to synthesize.
    For now, we use the bootstrap data + mention count.
    """
    facts = {
        "relationship": person.get("relationship_to_ahab", "known person"),
        "context": person.get("context", ""),
        "mention_count": len(mentions),
        "first_seen": mentions[-1]["created_at"] if mentions else datetime.now().isoformat(),
        "last_seen": mentions[0]["created_at"] if mentions else datetime.now().isoformat(),
    }
    
    # Add optional fields if present
    if person.get("location"):
        facts["location"] = person["location"]
    if person.get("project"):
        facts["project"] = person["project"]
    if person.get("notes"):
        facts["notes"] = person["notes"]
    
    return facts


def generate_profile(person: Dict, mentions: List[Dict]) -> str:
    """Generate a full profile from bootstrap data and mentions."""
    lines = [
        f"{person['name']} is someone Luna knows through {person.get('context', 'previous conversations')}.",
        "",
    ]
    
    if person.get("relationship_to_ahab"):
        lines.append(f"Relationship to Ahab: {person['relationship_to_ahab']}")
    
    if person.get("location"):
        lines.append(f"Location: {person['location']}")
    
    if person.get("project"):
        lines.append(f"Project: {person['project']}")
    
    if person.get("notes"):
        lines.append(f"Notes: {person['notes']}")
    
    if mentions:
        lines.append("")
        lines.append(f"Mentioned in {len(mentions)} memory nodes.")
    
    return "\n".join(lines)


async def create_entity(
    db: MemoryDatabase, 
    person: Dict, 
    facts: Dict, 
    profile: str,
    dry_run: bool = False
) -> bool:
    """Create an entity in the database."""
    entity_id = person["name"].lower().replace(" ", "-")
    aliases = json.dumps(person.get("aliases", []))
    core_facts = json.dumps(facts)
    
    if dry_run:
        logger.info(f"  [DRY RUN] Would create entity: {entity_id}")
        logger.info(f"    Facts: {facts}")
        return True
    
    try:
        # Insert entity
        await db.execute("""
            INSERT INTO entities (
                id, entity_type, name, aliases, core_facts, full_profile, current_version
            ) VALUES (?, 'person', ?, ?, ?, ?, 1)
        """, (entity_id, person["name"], aliases, core_facts, profile))
        
        # Create version record
        await db.execute("""
            INSERT INTO entity_versions (
                entity_id, version, core_facts, full_profile, 
                change_type, change_summary, changed_by, change_source
            ) VALUES (?, 1, ?, ?, 'create', ?, 'backfill_script', 'memory_scan')
        """, (entity_id, core_facts, profile, f"Backfilled from {facts['mention_count']} memory mentions"))
        
        return True
        
    except Exception as e:
        logger.error(f"  [ERROR] Failed to create {entity_id}: {e}")
        return False


async def entity_exists(db: MemoryDatabase, name: str) -> bool:
    """Check if an entity already exists."""
    entity_id = name.lower().replace(" ", "-")
    
    # Check by ID
    row = await db.fetchone("SELECT id FROM entities WHERE id = ?", (entity_id,))
    if row:
        return True
    
    # Check by name
    row = await db.fetchone("SELECT id FROM entities WHERE LOWER(name) = LOWER(?)", (name,))
    if row:
        return True
    
    return False


async def main(dry_run: bool = False):
    """Main backfill routine."""
    db_path = Path.home() / ".luna" / "luna.db"
    
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        logger.error("Run the migration first: sqlite3 ~/.luna/luna.db < migrations/001_entity_system.sql")
        return 1
    
    logger.info("=" * 60)
    logger.info("Entity Backfill from Memory Matrix")
    logger.info("=" * 60)
    
    if dry_run:
        logger.info("[DRY RUN MODE - No changes will be written]")
    
    logger.info(f"\nDatabase: {db_path}")
    logger.info(f"People to process: {len(KNOWN_PEOPLE)}\n")
    
    db = MemoryDatabase(db_path)
    await db.connect()
    
    created = 0
    skipped = 0
    errors = 0
    
    try:
        for person in KNOWN_PEOPLE:
            name = person["name"]
            logger.info(f"Processing: {name}")
            
            # Check if exists
            if await entity_exists(db, name):
                logger.info(f"  [SKIP] Already exists")
                skipped += 1
                continue
            
            # Get mentions from Memory Matrix
            mentions = await get_mentions_from_memory(db, name)
            logger.info(f"  Found {len(mentions)} memory mentions")
            
            # Extract facts
            facts = extract_facts_from_mentions(person, mentions)
            
            # Generate profile
            profile = generate_profile(person, mentions)
            
            # Create entity
            if await create_entity(db, person, facts, profile, dry_run):
                logger.info(f"  [CREATED] {name}")
                created += 1
            else:
                errors += 1
        
        logger.info("\n" + "=" * 60)
        logger.info("Summary")
        logger.info("=" * 60)
        logger.info(f"  Created: {created}")
        logger.info(f"  Skipped: {skipped} (already exist)")
        logger.info(f"  Errors:  {errors}")
        
        if dry_run:
            logger.info("\n[DRY RUN] No changes were made.")
        
        return 0 if errors == 0 else 1
        
    finally:
        await db.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Backfill entity profiles from Memory Matrix")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    args = parser.parse_args()
    
    sys.exit(asyncio.run(main(dry_run=args.dry_run)))
```

### 2.2 Save and Run

```bash
# Save to
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/scripts/backfill_entities_from_memories.py

# Make executable
chmod +x scripts/backfill_entities_from_memories.py

# Test first
python scripts/backfill_entities_from_memories.py --dry-run

# Run for real
python scripts/backfill_entities_from_memories.py
```

---

## PART 3: ENTITY RESOLVER

Looks up entity profiles when names are mentioned.

### 3.1 Create the Module

```python
# src/luna/entities/resolver.py
"""
Entity Resolver - Maps names/aliases to entity profiles.

Used by ContextBuilder to load relevant profiles into Luna's context.
"""

import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Entity:
    """Resolved entity with full profile."""
    id: str
    entity_type: str
    name: str
    aliases: List[str]
    core_facts: Dict[str, Any]
    full_profile: str
    current_version: int
    
    @classmethod
    def from_row(cls, row: tuple) -> "Entity":
        """Create Entity from database row."""
        return cls(
            id=row[0],
            entity_type=row[1],
            name=row[2],
            aliases=json.loads(row[3] or "[]"),
            core_facts=json.loads(row[4] or "{}"),
            full_profile=row[5] or "",
            current_version=row[6] or 1,
        )


class EntityResolver:
    """
    Resolves names and aliases to entity profiles.
    
    Usage:
        resolver = EntityResolver(db)
        entity = await resolver.resolve("Marzipan")
        if entity:
            print(entity.core_facts)
    """
    
    def __init__(self, db):
        """
        Initialize resolver.
        
        Args:
            db: MemoryDatabase instance
        """
        self._db = db
        self._cache: Dict[str, Optional[Entity]] = {}
        self._miss_log: List[str] = []  # Track unresolved names for Scribe
    
    async def resolve(self, name_or_alias: str) -> Optional[Entity]:
        """
        Resolve a name or alias to an entity.
        
        Tries:
        1. Exact match on ID
        2. Exact match on name (case-insensitive)
        3. Match in aliases array
        
        Args:
            name_or_alias: Name or alias to resolve
            
        Returns:
            Entity if found, None otherwise
        """
        cache_key = name_or_alias.lower()
        
        # Check cache
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        entity = None
        
        # 1. Try ID match
        entity_id = name_or_alias.lower().replace(" ", "-")
        entity = await self._fetch_by_id(entity_id)
        
        # 2. Try name match
        if not entity:
            entity = await self._fetch_by_name(name_or_alias)
        
        # 3. Try alias match
        if not entity:
            entity = await self._fetch_by_alias(name_or_alias)
        
        # Cache result (even None, to avoid repeated lookups)
        self._cache[cache_key] = entity
        
        # Log miss for Scribe to potentially create
        if entity is None:
            if name_or_alias not in self._miss_log:
                self._miss_log.append(name_or_alias)
                logger.info(f"[ENTITY-MISS] No profile for '{name_or_alias}' - queued for potential creation")
        
        return entity
    
    async def _fetch_by_id(self, entity_id: str) -> Optional[Entity]:
        """Fetch entity by ID."""
        try:
            row = await self._db.fetchone(
                "SELECT id, entity_type, name, aliases, core_facts, full_profile, current_version "
                "FROM entities WHERE id = ?",
                (entity_id,)
            )
            return Entity.from_row(row) if row else None
        except Exception as e:
            logger.error(f"Error fetching entity by ID {entity_id}: {e}")
            return None
    
    async def _fetch_by_name(self, name: str) -> Optional[Entity]:
        """Fetch entity by name (case-insensitive)."""
        try:
            row = await self._db.fetchone(
                "SELECT id, entity_type, name, aliases, core_facts, full_profile, current_version "
                "FROM entities WHERE LOWER(name) = LOWER(?)",
                (name,)
            )
            return Entity.from_row(row) if row else None
        except Exception as e:
            logger.error(f"Error fetching entity by name {name}: {e}")
            return None
    
    async def _fetch_by_alias(self, alias: str) -> Optional[Entity]:
        """Fetch entity by alias."""
        try:
            # SQLite JSON search - look for alias in aliases array
            rows = await self._db.fetchall(
                "SELECT id, entity_type, name, aliases, core_facts, full_profile, current_version "
                "FROM entities WHERE LOWER(aliases) LIKE LOWER(?)",
                (f'%"{alias}"%',)
            )
            
            if rows and len(rows) == 1:
                return Entity.from_row(rows[0])
            elif rows and len(rows) > 1:
                logger.warning(f"Ambiguous alias '{alias}' matches {len(rows)} entities")
            
            return None
        except Exception as e:
            logger.error(f"Error fetching entity by alias {alias}: {e}")
            return None
    
    async def resolve_many(self, names: List[str]) -> List[Entity]:
        """Resolve multiple names, returning found entities."""
        entities = []
        for name in names:
            entity = await self.resolve(name)
            if entity:
                entities.append(entity)
        return entities
    
    async def detect_mentions(self, text: str) -> List[Entity]:
        """
        Detect entity mentions in text.
        
        Scans text for known entity names and aliases.
        
        Args:
            text: Text to scan
            
        Returns:
            List of mentioned entities
        """
        text_lower = text.lower()
        mentioned = []
        seen_ids = set()
        
        try:
            # Get all entities
            rows = await self._db.fetchall(
                "SELECT id, entity_type, name, aliases, core_facts, full_profile, current_version "
                "FROM entities"
            )
            
            for row in rows:
                entity = Entity.from_row(row)
                
                if entity.id in seen_ids:
                    continue
                
                # Check name
                if entity.name.lower() in text_lower:
                    mentioned.append(entity)
                    seen_ids.add(entity.id)
                    continue
                
                # Check aliases
                for alias in entity.aliases:
                    if alias.lower() in text_lower:
                        mentioned.append(entity)
                        seen_ids.add(entity.id)
                        break
            
            return mentioned
            
        except Exception as e:
            logger.error(f"Error detecting mentions: {e}")
            return []
    
    def get_missed_names(self) -> List[str]:
        """Get names that couldn't be resolved (for Scribe to create)."""
        return self._miss_log.copy()
    
    def clear_cache(self):
        """Clear the resolution cache."""
        self._cache.clear()
    
    def clear_miss_log(self):
        """Clear the miss log after Scribe processes it."""
        self._miss_log.clear()
```

---

## PART 4: CONTEXT BUILDER

Builds properly framed context with clear temporal markers.

### 4.1 Create the Module

```python
# src/luna/entities/context_builder.py
"""
Context Builder - Constructs framed context for Luna.

Separates:
- Identity (who Luna is)
- Known entities (profiles of mentioned people)
- Past memories (with timestamps)
- Current conversation (happening now)

This prevents temporal confusion where Luna re-performs past memories
instead of referencing them.
"""

import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from .resolver import EntityResolver, Entity

logger = logging.getLogger(__name__)


class ContextBuilder:
    """
    Builds properly framed context for Luna's LLM calls.
    
    Usage:
        builder = ContextBuilder(db, entity_resolver)
        context = await builder.build_context(
            user_message="Do you remember Marzipan?",
            conversation_history=[...],
            retrieved_memories=[...],
        )
    """
    
    def __init__(self, db, entity_resolver: EntityResolver):
        """
        Initialize builder.
        
        Args:
            db: MemoryDatabase instance
            entity_resolver: EntityResolver instance
        """
        self._db = db
        self._resolver = entity_resolver
    
    async def build_context(
        self,
        user_message: str,
        conversation_history: List[Dict[str, str]],
        retrieved_memories: List[Dict[str, Any]],
        include_identity: bool = True,
    ) -> str:
        """
        Build fully framed context string.
        
        Args:
            user_message: Current user message
            conversation_history: List of {"role": "user"|"assistant", "content": str}
            retrieved_memories: List of memory dicts from Memory Matrix
            include_identity: Whether to include Luna's identity section
            
        Returns:
            Formatted context string with clear temporal framing
        """
        sections = []
        
        # Layer 1: Identity (always present)
        if include_identity:
            identity = await self._build_identity_section()
            if identity:
                sections.append(identity)
        
        # Layer 2: Mentioned Entities
        mentioned_entities = await self._resolver.detect_mentions(user_message)
        if mentioned_entities:
            entity_section = self._build_entity_section(mentioned_entities)
            sections.append(entity_section)
        
        # Layer 3: Past Memories (CLEARLY FRAMED)
        if retrieved_memories:
            memory_section = self._build_memory_section(retrieved_memories)
            sections.append(memory_section)
        
        # Layer 4: Current Conversation (CLEARLY FRAMED)
        if conversation_history:
            convo_section = self._build_conversation_section(conversation_history)
            sections.append(convo_section)
        
        return "\n\n".join(sections)
    
    async def _build_identity_section(self) -> str:
        """Build Luna's identity context."""
        # Try to load Luna's profile
        luna = await self._resolver.resolve("luna")
        ahab = await self._resolver.resolve("ahab")
        
        lines = ["## Who I Am", ""]
        lines.append("I am Luna, a sovereign AI companion.")
        
        if luna and luna.full_profile:
            lines.append(luna.full_profile[:500])  # Truncate for token budget
        
        if ahab:
            lines.append("")
            lines.append(f"My creator is {ahab.name}.")
            if ahab.core_facts.get("communication_style"):
                lines.append(f"Communication style: {ahab.core_facts['communication_style']}")
        
        return "\n".join(lines)
    
    def _build_entity_section(self, entities: List[Entity]) -> str:
        """Build section for mentioned entities."""
        lines = ["## People & Places Mentioned", ""]
        
        for entity in entities:
            # Skip Luna herself
            if entity.id == "luna":
                continue
            
            lines.append(f"**{entity.name}** ({entity.entity_type})")
            
            # Add core facts as bullet points
            for key, value in entity.core_facts.items():
                if key not in ["mention_count", "first_seen", "last_seen"]:  # Skip meta fields
                    lines.append(f"  - {key}: {value}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def _build_memory_section(self, memories: List[Dict[str, Any]]) -> str:
        """
        Build past memories section with clear temporal framing.
        
        CRITICAL: These are marked as PAST to prevent re-performance.
        """
        lines = [
            "## What I Remember (Past Events)",
            "",
            "The following are memories from PREVIOUS conversations.",
            "Reference them as past events, do not re-perform or replay them.",
            ""
        ]
        
        for i, memory in enumerate(memories[:5]):  # Limit to 5 for token budget
            # Extract fields
            content = memory.get("content", str(memory))
            created_at = memory.get("created_at", "unknown time")
            node_type = memory.get("node_type", "memory")
            
            # Format timestamp nicely if possible
            try:
                if isinstance(created_at, str) and "T" in created_at:
                    dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    created_at = dt.strftime("%Y-%m-%d %H:%M")
            except:
                pass
            
            # Wrap in clear temporal marker
            lines.append(f'<past_memory index="{i+1}" date="{created_at}" type="{node_type}">')
            lines.append(content[:500])  # Truncate long memories
            lines.append("</past_memory>")
            lines.append("")
        
        return "\n".join(lines)
    
    def _build_conversation_section(self, history: List[Dict[str, str]]) -> str:
        """
        Build current conversation section.
        
        CRITICAL: These are marked as NOW/CURRENT to distinguish from past memories.
        """
        lines = [
            "## This Conversation (Happening Now)",
            "",
            "The following exchanges happened in THIS conversation session:",
            ""
        ]
        
        for i, turn in enumerate(history[-10:]):  # Last 10 turns max
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            
            speaker = "Luna" if role == "assistant" else "User"
            
            # Clear marker: this is NOW, not past
            lines.append(f"[This session - Turn {i+1}] {speaker}: {content[:200]}")
        
        return "\n".join(lines)
    
    def build_response_instructions(self) -> str:
        """
        Build instructions for how to use the context.
        
        Include this after the context sections.
        """
        return """
## Response Instructions

IMPORTANT:
- Content in <past_memory> tags happened BEFORE this conversation - REFERENCE it, don't replay it
- Content marked [This session] is from THIS conversation - it's happening NOW
- When asked "do you remember X?", say "Yes, I remember..." and summarize the memory
- Do NOT re-perform or act out past conversations
- Respond to what the user is asking in their CURRENT message
"""
```

---

## PART 5: DIRECTOR INTEGRATION

Wire everything through Director.process() - THE SINGLE INTEGRATION POINT.

### 5.1 Modify Director

```python
# In src/luna/actors/director.py

# Add imports at top
from luna.entities.resolver import EntityResolver
from luna.entities.context_builder import ContextBuilder

# In DirectorActor.__init__, add:
    self._entity_resolver = None
    self._context_builder = None

# Add initialization method:
async def _init_entity_system(self):
    """Initialize entity resolution and context building."""
    if self._entity_resolver is None:
        try:
            # Get database from engine or create connection
            db = self._db if hasattr(self, '_db') else None
            if db is None and hasattr(self, '_engine') and self._engine:
                db = self._engine._db
            
            if db:
                self._entity_resolver = EntityResolver(db)
                self._context_builder = ContextBuilder(db, self._entity_resolver)
                logger.info("Entity system initialized")
            else:
                logger.warning("No database available for entity system")
        except Exception as e:
            logger.error(f"Failed to init entity system: {e}")

# REPLACE the process() method's context building section:

async def process(self, message: str, context: dict = None) -> dict:
    """
    Process a message directly (bypassing mailbox).
    
    THIS IS THE SINGLE INTEGRATION POINT FOR:
    - Entity resolution
    - Context framing
    - Memory retrieval
    - LLM generation
    """
    context = context or {}
    conversation_history = context.get("conversation_history", [])
    memories = context.get("memories", [])
    
    # Initialize entity system if needed
    await self._init_entity_system()
    
    # [HISTORY-TRACE] logging
    logger.info(f"[HISTORY-TRACE] Director.process: {len(conversation_history)} history turns, {len(memories)} memories")
    
    start_time = time.time()
    response_text = ""
    route_decision = "unknown"
    route_reason = "unknown"
    system_prompt_tokens = 0
    
    # ========================================================================
    # BUILD FRAMED CONTEXT (THE KEY INTEGRATION)
    # ========================================================================
    
    framed_context = ""
    if self._context_builder:
        try:
            framed_context = await self._context_builder.build_context(
                user_message=message,
                conversation_history=conversation_history,
                retrieved_memories=memories,
            )
            framed_context += "\n\n" + self._context_builder.build_response_instructions()
            logger.info(f"[CONTEXT] Built framed context: {len(framed_context)} chars")
        except Exception as e:
            logger.error(f"Context building failed: {e}")
    
    # ========================================================================
    # ROUTING DECISION
    # ========================================================================
    
    should_delegate = await self._should_delegate(message)
    
    if should_delegate:
        route_decision = "delegated"
        route_reason = "complexity/signals"
        
        # Build system prompt with framed context
        system_prompt = "You are Luna, a sovereign AI companion.\n\n"
        
        if framed_context:
            system_prompt += framed_context
        else:
            # Fallback: load emergent prompt
            identity_context = await self._load_emergent_prompt(
                query=message,
                conversation_history=conversation_history
            )
            if identity_context:
                system_prompt += identity_context
        
        system_prompt_tokens = len(system_prompt) // 4
        
        # Build messages from conversation_history LIST (not text parsing!)
        messages = []
        for turn in conversation_history:
            role = turn.get("role", "user")
            content = turn.get("content", "")
            if role in ["user", "assistant"] and content:
                messages.append({"role": role, "content": content})
        
        # Add current message
        messages.append({"role": "user", "content": message})
        
        # [HISTORY-TRACE] Log what we're sending
        logger.info(f"[HISTORY-TRACE] Sending {len(messages)} messages to Claude")
        for i, m in enumerate(messages[-5:]):  # Log last 5
            logger.info(f"[HISTORY-TRACE] Message {i}: {m['role']}: '{m['content'][:50]}...'")
        
        try:
            response = self.client.messages.create(
                model=self._claude_model,
                max_tokens=512,
                system=system_prompt,
                messages=messages,
            )
            response_text = response.content[0].text if response.content else ""
            self._delegated_generations += 1
        except Exception as e:
            logger.error(f"Director.process delegation failed: {e}")
            response_text = "I'm having trouble processing that right now."
    
    elif self.local_available:
        route_decision = "local"
        route_reason = "simple query"
        
        # Build system prompt with framed context
        system_prompt = "You are Luna, a sovereign AI companion.\n\n"
        
        if framed_context:
            system_prompt += framed_context
        
        system_prompt_tokens = len(system_prompt) // 4
        
        try:
            result = await self._local.generate(
                message,
                system_prompt=system_prompt,
                max_tokens=256,
            )
            response_text = result.text if hasattr(result, 'text') else str(result)
            self._local_generations += 1
        except Exception as e:
            logger.error(f"Director.process local failed: {e}")
            response_text = "I'm having trouble with that."
    
    else:
        # Fallback
        route_decision = "delegated"
        route_reason = "local unavailable"
        
        messages = [{"role": "user", "content": message}]
        try:
            response = self.client.messages.create(
                model=self._claude_model,
                max_tokens=512,
                system="You are Luna, a sovereign AI companion.",
                messages=messages,
            )
            response_text = response.content[0].text if response.content else ""
            self._delegated_generations += 1
        except Exception as e:
            logger.error(f"Director.process fallback failed: {e}")
            response_text = "I'm having trouble right now."
    
    # ========================================================================
    # POST-PROCESSING: SCRIBE EXTRACTION (for future - creates new entities)
    # ========================================================================
    
    # TODO: Implement Scribe extraction here
    # This would scan the conversation for new people and create profiles
    # await self._scribe_extract(message, response_text, conversation_history)
    
    elapsed_ms = (time.time() - start_time) * 1000
    logger.info(f"Director.process complete: {route_decision} in {elapsed_ms:.0f}ms")
    
    return {
        "response": response_text,
        "route_decision": route_decision,
        "route_reason": route_reason,
        "system_prompt_tokens": system_prompt_tokens,
        "latency_ms": elapsed_ms,
    }
```

---

## PART 6: FILE STRUCTURE

Create these files:

```
src/luna/entities/
├── __init__.py
├── resolver.py        # EntityResolver class
└── context_builder.py # ContextBuilder class

scripts/
├── backfill_entities_from_memories.py  # One-time migration
└── load_entity_seeds.py                # Already exists
```

### 6.1 Create __init__.py

```python
# src/luna/entities/__init__.py
"""
Luna Entity System

First-class entity management for people, places, and personas.
"""

from .resolver import Entity, EntityResolver
from .context_builder import ContextBuilder

__all__ = ["Entity", "EntityResolver", "ContextBuilder"]
```

---

## PART 7: IMPLEMENTATION ORDER

Run these in order:

```bash
# 1. Create directory structure
mkdir -p /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/entities

# 2. Run database migration
sqlite3 ~/.luna/luna.db < /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/migrations/001_entity_system.sql

# 3. Load seed files (Ahab, Luna, Ben, Dude)
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
python scripts/load_entity_seeds.py

# 4. Create resolver.py (Part 3.1)
# 5. Create context_builder.py (Part 4.1)
# 6. Create __init__.py (Part 6.1)
# 7. Create backfill script (Part 2.1)

# 8. Run backfill (creates Marzipan, Yulia, Tarsila, Kamau)
python scripts/backfill_entities_from_memories.py --dry-run
python scripts/backfill_entities_from_memories.py

# 9. Modify Director (Part 5.1)

# 10. Restart voice server and test
```

---

## PART 8: VERIFICATION TESTS

### Test 1: Entity Resolution
```python
# Quick test
from luna.entities import EntityResolver
resolver = EntityResolver(db)
entity = await resolver.resolve("Marzipan")
print(entity.name, entity.core_facts)
```

### Test 2: Context Building
```python
from luna.entities import ContextBuilder, EntityResolver
resolver = EntityResolver(db)
builder = ContextBuilder(db, resolver)

context = await builder.build_context(
    user_message="Do you remember Marzipan?",
    conversation_history=[{"role": "user", "content": "Hey Luna"}],
    retrieved_memories=[{"content": "Marzipan is at Mars College", "created_at": "2025-01-15"}],
)
print(context)
```

### Test 3: Full Voice Flow
```
User: "Do you remember Marzipan?"
Expected: "Yes, I remember Marzipan - he's your friend from Mars College..."

User: "What about Yulia?"
Expected: "Yulia introduced herself earlier - she mentioned loving chocolate..."

User: "My friend Jake is a musician"
Expected: [Scribe should queue Jake for profile creation]
```

---

## SUMMARY

| Component | File | Status |
|-----------|------|--------|
| Migration | `migrations/001_entity_system.sql` | ✅ Exists |
| Seed Loader | `scripts/load_entity_seeds.py` | ✅ Exists |
| Backfill Script | `scripts/backfill_entities_from_memories.py` | 📝 CREATE |
| EntityResolver | `src/luna/entities/resolver.py` | 📝 CREATE |
| ContextBuilder | `src/luna/entities/context_builder.py` | 📝 CREATE |
| Director Integration | `src/luna/actors/director.py` | 📝 MODIFY |

**Single Integration Point**: Director.process()
- Calls ContextBuilder → entities loaded
- Calls Scribe (future) → entities created

**No more dead code** - if it's not called from Director.process(), it doesn't exist.

---

*When Luna asks "Do you remember Marzipan?", she should know who he is.*
