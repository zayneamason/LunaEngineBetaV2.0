"""
Luna Engine Entity Resolution
=============================

Entity resolution - matching names/aliases to entities.

Implements the resolution logic from Part 4.3 of the Entity System spec:
- Exact match on id (lowercase, hyphenated)
- Exact match on name (case-insensitive)
- Match in aliases JSON array
- Returns None if ambiguous (multiple matches)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..substrate.database import MemoryDatabase

from .models import Entity, EntityType, EntityVersion

logger = logging.getLogger(__name__)


# Track unresolved names for Scribe to potentially create profiles
_missed_names_log: list[str] = []


# Type alias for dict returns (for test compatibility)
EntityDict = dict


class EntityResolver:
    """
    Resolves entity names, aliases, and queries to Entity objects.

    Resolution priority:
    1. Exact match on id (lowercase, spaces replaced with hyphens)
    2. Exact match on name (case-insensitive)
    3. Match in aliases JSON array
    4. Return None if ambiguous (multiple matches)

    Usage:
        resolver = EntityResolver(db)
        entity = await resolver.resolve_entity("Marzipan")
        entity = await resolver.resolve_entity("Marzi")  # Alias match
        entity = await resolver.resolve_or_create("New Person", "person")
    """

    def __init__(self, db: "MemoryDatabase") -> None:
        """
        Initialize the entity resolver.

        Args:
            db: The MemoryDatabase connection for entity queries
        """
        self.db = db
        self._cache: dict[str, Optional[EntityDict]] = {}
        self._miss_log: list[str] = []  # Track unresolved names for Scribe

    def _normalize_id(self, query: str) -> str:
        """
        Normalize a query string to entity ID format.

        Converts to lowercase and replaces spaces with hyphens.

        Args:
            query: The raw query string

        Returns:
            Normalized ID string (e.g., "Ben Franklin" -> "ben-franklin")
        """
        return query.lower().strip().replace(" ", "-")

    def _row_to_entity(self, row) -> Entity:
        """
        Convert a database row to an Entity dataclass.

        Args:
            row: SQLite row with entity fields

        Returns:
            Entity dataclass instance
        """
        return Entity(
            id=row[0],
            entity_type=EntityType(row[1]),
            name=row[2],
            aliases=json.loads(row[3]) if row[3] else [],
            core_facts=json.loads(row[4]) if row[4] else {},
            full_profile=row[5],
            voice_config=json.loads(row[6]) if row[6] else None,
            current_version=row[7],
            metadata=json.loads(row[8]) if row[8] else {},
            created_at=row[9],
            updated_at=row[10],
        )

    async def resolve_entity(self, query: str) -> Optional[EntityDict]:
        """
        Find entity by name, alias, or fuzzy match.

        Resolution order:
        1. Exact match on id (lowercase, replace spaces with hyphens)
        2. Exact match on name (case-insensitive)
        3. Match in aliases JSON array
        4. Return None if ambiguous (multiple matches)

        Args:
            query: Name, alias, or ID to search for

        Returns:
            Entity dict if found and unambiguous, None otherwise
        """
        if not query or not query.strip():
            return None

        query = query.strip()
        normalized_id = self._normalize_id(query)

        columns = [
            "id", "entity_type", "name", "aliases", "core_facts",
            "full_profile", "voice_config", "current_version",
            "metadata", "created_at", "updated_at"
        ]

        # 1. Exact match on id
        row = await self.db.fetchone(
            "SELECT * FROM entities WHERE id = ?",
            (normalized_id,)
        )
        if row:
            logger.debug(f"Resolved entity by id: {normalized_id}")
            return dict(zip(columns, row))

        # 2. Exact match on name (case-insensitive)
        row = await self.db.fetchone(
            "SELECT * FROM entities WHERE LOWER(name) = LOWER(?)",
            (query,)
        )
        if row:
            logger.debug(f"Resolved entity by name: {query}")
            return dict(zip(columns, row))

        # 3. Match in aliases JSON array
        # SQLite JSON: aliases is stored as JSON array like ["Zayne", "Ahab"]
        # We search for the query as a string within the JSON
        rows = await self.db.fetchall(
            """
            SELECT * FROM entities
            WHERE aliases LIKE ?
            """,
            (f'%"{query}"%',)
        )

        if len(rows) == 1:
            logger.debug(f"Resolved entity by alias: {query}")
            return dict(zip(columns, rows[0]))
        elif len(rows) > 1:
            logger.warning(
                f"Ambiguous entity resolution for '{query}': "
                f"{len(rows)} matches found"
            )
            return None  # Ambiguous

        # 4. Case-insensitive alias search
        rows = await self.db.fetchall(
            """
            SELECT * FROM entities
            WHERE LOWER(aliases) LIKE LOWER(?)
            """,
            (f'%"{query}"%',)
        )

        if len(rows) == 1:
            logger.debug(f"Resolved entity by alias (case-insensitive): {query}")
            return dict(zip(columns, rows[0]))
        elif len(rows) > 1:
            logger.warning(
                f"Ambiguous entity resolution for '{query}' (alias): "
                f"{len(rows)} matches found"
            )
            return None  # Ambiguous

        # Not found
        logger.debug(f"Entity not found for query: {query}")
        return None

    async def resolve_or_create(
        self,
        name: str,
        entity_type: str = "person",
        source: str = ""
    ) -> Entity:
        """
        Resolve existing entity or create new one.

        If an entity with the given name exists (by name or alias), returns it.
        Otherwise, creates a new entity with default values.

        Args:
            name: Entity name to resolve or create
            entity_type: Type for new entity (person, persona, place, project)
            source: Source of creation (for audit trail)

        Returns:
            Existing or newly created Entity
        """
        # Try to resolve first
        existing = await self.resolve_entity(name)
        if existing:
            logger.debug(f"Resolved existing entity: {existing.id}")
            return existing

        # Create new entity
        entity_id = self._normalize_id(name)
        now = datetime.now().isoformat()

        # Check for ID collision (different name but same normalized ID)
        collision = await self.db.fetchone(
            "SELECT id FROM entities WHERE id = ?",
            (entity_id,)
        )
        if collision:
            # Add numeric suffix to avoid collision
            suffix = 1
            while True:
                new_id = f"{entity_id}-{suffix}"
                collision = await self.db.fetchone(
                    "SELECT id FROM entities WHERE id = ?",
                    (new_id,)
                )
                if not collision:
                    entity_id = new_id
                    break
                suffix += 1

        # Insert new entity
        await self.db.execute(
            """
            INSERT INTO entities (
                id, entity_type, name, aliases, core_facts,
                full_profile, voice_config, current_version,
                metadata, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_id,
                entity_type,
                name,
                json.dumps([]),  # Empty aliases
                json.dumps({}),  # Empty core_facts
                None,            # No full profile
                None,            # No voice config
                1,               # Version 1
                json.dumps({"source": source}) if source else json.dumps({}),
                now,
                now,
            )
        )

        # Create initial version record
        await self.db.execute(
            """
            INSERT INTO entity_versions (
                entity_id, version, core_facts, full_profile, voice_config,
                change_type, change_summary, changed_by, change_source,
                created_at, valid_from, valid_until
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entity_id,
                1,                       # version
                json.dumps({}),          # core_facts
                None,                    # full_profile
                None,                    # voice_config
                "create",                # change_type
                f"Initial creation of {name}",
                "resolver",              # changed_by
                source or None,          # change_source
                now,                     # created_at
                now,                     # valid_from
                None,                    # valid_until (current version)
            )
        )

        logger.info(f"Created new entity: {entity_id} ({entity_type})")

        # Return the created entity
        return Entity(
            id=entity_id,
            entity_type=EntityType(entity_type),
            name=name,
            aliases=[],
            core_facts={},
            full_profile=None,
            voice_config=None,
            current_version=1,
            metadata={"source": source} if source else {},
            created_at=now,
            updated_at=now,
        )

    async def find_by_type(
        self,
        entity_type: str,
        limit: int = 100
    ) -> list[Entity]:
        """
        Find all entities of a specific type.

        Args:
            entity_type: Type to filter by (person, persona, place, project)
            limit: Maximum number of results

        Returns:
            List of entities matching the type
        """
        rows = await self.db.fetchall(
            """
            SELECT * FROM entities
            WHERE entity_type = ?
            ORDER BY name ASC
            LIMIT ?
            """,
            (entity_type, limit)
        )

        return [self._row_to_entity(row) for row in rows]

    async def get_entity(self, entity_id: str) -> Optional[EntityDict]:
        """
        Get entity by exact ID.

        Args:
            entity_id: Exact entity ID

        Returns:
            Entity dict if found, None otherwise
        """
        return await self.get_entity_dict(entity_id)

    async def search_entities(
        self,
        query: str,
        limit: int = 10
    ) -> list[Entity]:
        """
        Search entities by name or alias using LIKE.

        Performs a fuzzy search across name and aliases fields.

        Args:
            query: Search query (partial match)
            limit: Maximum number of results

        Returns:
            List of matching entities, ordered by relevance
        """
        if not query or not query.strip():
            return []

        query = query.strip()
        like_pattern = f"%{query}%"

        rows = await self.db.fetchall(
            """
            SELECT * FROM entities
            WHERE name LIKE ?
               OR aliases LIKE ?
               OR id LIKE ?
            ORDER BY
                CASE
                    WHEN LOWER(name) = LOWER(?) THEN 0
                    WHEN LOWER(name) LIKE LOWER(?) THEN 1
                    WHEN aliases LIKE ? THEN 2
                    ELSE 3
                END,
                name ASC
            LIMIT ?
            """,
            (
                like_pattern,      # name LIKE
                like_pattern,      # aliases LIKE
                like_pattern,      # id LIKE
                query,             # Exact name match (priority 0)
                f"{query}%",       # Name starts with (priority 1)
                f'%"{query}"%',    # Exact alias match (priority 2)
                limit
            )
        )

        return [self._row_to_entity(row) for row in rows]

    async def add_alias(self, entity_id: str, alias: str) -> bool:
        """
        Add an alias to an entity.

        Args:
            entity_id: Entity to add alias to
            alias: New alias to add

        Returns:
            True if alias was added, False if entity not found or alias exists
        """
        entity = await self.get_entity(entity_id)
        if not entity:
            return False

        # Check if alias already exists
        if alias in entity.aliases:
            return False

        # Update aliases
        new_aliases = entity.aliases + [alias]
        await self.db.execute(
            """
            UPDATE entities
            SET aliases = ?, updated_at = ?
            WHERE id = ?
            """,
            (json.dumps(new_aliases), datetime.now().isoformat(), entity_id)
        )

        logger.info(f"Added alias '{alias}' to entity {entity_id}")
        return True

    async def remove_alias(self, entity_id: str, alias: str) -> bool:
        """
        Remove an alias from an entity.

        Args:
            entity_id: Entity to remove alias from
            alias: Alias to remove

        Returns:
            True if alias was removed, False if entity not found or alias doesn't exist
        """
        entity = await self.get_entity(entity_id)
        if not entity:
            return False

        if alias not in entity.aliases:
            return False

        # Update aliases
        new_aliases = [a for a in entity.aliases if a != alias]
        await self.db.execute(
            """
            UPDATE entities
            SET aliases = ?, updated_at = ?
            WHERE id = ?
            """,
            (json.dumps(new_aliases), datetime.now().isoformat(), entity_id)
        )

        logger.info(f"Removed alias '{alias}' from entity {entity_id}")
        return True

    async def entity_exists(self, query: str) -> bool:
        """
        Check if an entity exists (by name, id, or alias).

        Args:
            query: Name, ID, or alias to check

        Returns:
            True if entity exists, False otherwise
        """
        entity = await self.resolve_entity(query)
        return entity is not None

    async def count_entities(self, entity_type: Optional[str] = None) -> int:
        """
        Count entities, optionally filtered by type.

        Args:
            entity_type: Optional type filter

        Returns:
            Count of matching entities
        """
        if entity_type:
            row = await self.db.fetchone(
                "SELECT COUNT(*) FROM entities WHERE entity_type = ?",
                (entity_type,)
            )
        else:
            row = await self.db.fetchone("SELECT COUNT(*) FROM entities")

        return row[0] if row else 0

    # =========================================================================
    # TEST-COMPATIBLE DICT-RETURNING METHODS
    # =========================================================================

    async def create_entity(
        self,
        name: str,
        entity_type: str = "person",
        aliases: list[str] = None,
        core_facts: dict = None,
        full_profile: str = None,
        voice_config: dict = None,
        source: str = "test",
        changed_by: str = "scribe",
    ) -> EntityDict:
        """
        Create a new entity with version 1.

        Args:
            name: Entity name
            entity_type: Type (person, persona, place, project)
            aliases: List of alternative names
            core_facts: Dictionary of core facts
            full_profile: Extended markdown profile
            voice_config: Voice/personality configuration (for personas)
            source: Source of creation
            changed_by: Actor creating the entity

        Returns:
            Created entity as a dict
        """
        entity_id = self._normalize_id(name)
        now = datetime.now().isoformat()
        aliases_json = json.dumps(aliases or [])
        core_facts_json = json.dumps(core_facts or {})
        voice_config_json = json.dumps(voice_config) if voice_config else None

        # Check for ID collision
        collision = await self.db.fetchone(
            "SELECT id FROM entities WHERE id = ?",
            (entity_id,)
        )
        if collision:
            suffix = 1
            while True:
                new_id = f"{entity_id}-{suffix}"
                collision = await self.db.fetchone(
                    "SELECT id FROM entities WHERE id = ?",
                    (new_id,)
                )
                if not collision:
                    entity_id = new_id
                    break
                suffix += 1

        # Insert entity
        await self.db.execute(
            """
            INSERT INTO entities (id, entity_type, name, aliases, core_facts,
                                  full_profile, voice_config, current_version,
                                  metadata, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """,
            (entity_id, entity_type, name, aliases_json, core_facts_json,
             full_profile, voice_config_json, json.dumps({"source": source}),
             now, now)
        )

        # Insert version 1
        await self.db.execute(
            """
            INSERT INTO entity_versions (entity_id, version, core_facts, full_profile,
                                         voice_config, change_type, change_summary,
                                         changed_by, change_source, created_at,
                                         valid_from, valid_until)
            VALUES (?, 1, ?, ?, ?, 'create', 'Initial creation', ?, ?, ?, ?, NULL)
            """,
            (entity_id, core_facts_json, full_profile, voice_config_json,
             changed_by, source, now, now)
        )

        logger.info(f"Created entity: {entity_id} ({entity_type})")

        return await self.get_entity_dict(entity_id)

    async def update_entity(
        self,
        entity_id: str,
        core_facts: dict = None,
        full_profile: str = None,
        voice_config: dict = None,
        change_summary: str = "Updated entity",
        source: str = "test",
        changed_by: str = "scribe",
    ) -> EntityDict:
        """
        Update entity by creating a new version.

        Args:
            entity_id: Entity ID to update
            core_facts: Facts to merge with existing
            full_profile: New full profile (or None to keep existing)
            voice_config: New voice config (or None to keep existing)
            change_summary: Description of the change
            source: Source of update
            changed_by: Actor making the update

        Returns:
            Updated entity version as dict
        """
        # Get current version
        current = await self.get_current_version(entity_id)
        if not current:
            raise ValueError(f"Entity {entity_id} not found")

        new_version = current["version"] + 1
        now = datetime.now().isoformat()

        # Merge core facts
        existing_facts = json.loads(current["core_facts"] or "{}")
        if core_facts:
            existing_facts.update(core_facts)
        new_core_facts = json.dumps(existing_facts)

        # Use new values or existing
        new_profile = full_profile if full_profile is not None else current["full_profile"]
        new_voice = json.dumps(voice_config) if voice_config else current["voice_config"]

        # Close current version
        await self.db.execute(
            """
            UPDATE entity_versions
            SET valid_until = ?
            WHERE entity_id = ? AND valid_until IS NULL
            """,
            (now, entity_id)
        )

        # Create new version
        await self.db.execute(
            """
            INSERT INTO entity_versions (entity_id, version, core_facts, full_profile,
                                         voice_config, change_type, change_summary,
                                         changed_by, change_source, created_at,
                                         valid_from, valid_until)
            VALUES (?, ?, ?, ?, ?, 'update', ?, ?, ?, ?, ?, NULL)
            """,
            (entity_id, new_version, new_core_facts, new_profile, new_voice,
             change_summary, changed_by, source, now, now)
        )

        # Update entities table
        await self.db.execute(
            """
            UPDATE entities
            SET core_facts = ?, full_profile = ?, voice_config = ?,
                current_version = ?, updated_at = ?
            WHERE id = ?
            """,
            (new_core_facts, new_profile, new_voice, new_version, now, entity_id)
        )

        logger.debug(f"Updated entity {entity_id} to version {new_version}")

        return await self.get_current_version(entity_id)

    async def get_entity_dict(self, entity_id: str) -> Optional[EntityDict]:
        """
        Get entity by ID as a dictionary.

        Args:
            entity_id: Exact entity ID

        Returns:
            Entity as dict if found, None otherwise
        """
        row = await self.db.fetchone(
            "SELECT * FROM entities WHERE id = ?",
            (entity_id,)
        )

        if row:
            # Get column names from the query
            columns = [
                "id", "entity_type", "name", "aliases", "core_facts",
                "full_profile", "voice_config", "current_version",
                "metadata", "created_at", "updated_at"
            ]
            return dict(zip(columns, row))
        return None

    async def get_current_version(self, entity_id: str) -> Optional[EntityDict]:
        """
        Get the current (latest) version of an entity.

        Args:
            entity_id: Entity ID

        Returns:
            Current version as dict, or None
        """
        row = await self.db.fetchone(
            """
            SELECT * FROM entity_versions
            WHERE entity_id = ? AND valid_until IS NULL
            ORDER BY version DESC
            LIMIT 1
            """,
            (entity_id,)
        )

        if row:
            columns = [
                "id", "entity_id", "version", "core_facts", "full_profile",
                "voice_config", "change_type", "change_summary", "changed_by",
                "change_source", "created_at", "valid_from", "valid_until"
            ]
            return dict(zip(columns, row))
        return None

    async def get_entity_at_time(
        self,
        entity_id: str,
        timestamp: str
    ) -> Optional[EntityDict]:
        """
        Get entity state at a specific timestamp.

        Args:
            entity_id: Entity ID
            timestamp: ISO format timestamp

        Returns:
            Entity version at that time as dict, or None
        """
        row = await self.db.fetchone(
            """
            SELECT * FROM entity_versions
            WHERE entity_id = ?
              AND valid_from <= ?
              AND (valid_until IS NULL OR valid_until > ?)
            ORDER BY version DESC
            LIMIT 1
            """,
            (entity_id, timestamp, timestamp)
        )

        if row:
            columns = [
                "id", "entity_id", "version", "core_facts", "full_profile",
                "voice_config", "change_type", "change_summary", "changed_by",
                "change_source", "created_at", "valid_from", "valid_until"
            ]
            return dict(zip(columns, row))
        return None

    async def get_entity_history(self, entity_id: str) -> list[EntityDict]:
        """
        Get full version history of an entity.

        Args:
            entity_id: Entity ID

        Returns:
            List of all versions as dicts
        """
        rows = await self.db.fetchall(
            """
            SELECT * FROM entity_versions
            WHERE entity_id = ?
            ORDER BY version ASC
            """,
            (entity_id,)
        )

        columns = [
            "id", "entity_id", "version", "core_facts", "full_profile",
            "voice_config", "change_type", "change_summary", "changed_by",
            "change_source", "created_at", "valid_from", "valid_until"
        ]

        return [dict(zip(columns, row)) for row in rows]

    async def rollback_entity(
        self,
        entity_id: str,
        to_version: int,
        reason: str,
        changed_by: str = "librarian",
    ) -> EntityDict:
        """
        Rollback entity to a previous version (creates new version).

        Args:
            entity_id: Entity ID
            to_version: Version number to restore
            reason: Reason for rollback
            changed_by: Actor performing rollback

        Returns:
            New version (rollback) as dict
        """
        # Get the old version to restore
        row = await self.db.fetchone(
            """
            SELECT * FROM entity_versions
            WHERE entity_id = ? AND version = ?
            """,
            (entity_id, to_version)
        )

        if not row:
            raise ValueError(f"Version {to_version} not found for {entity_id}")

        columns = [
            "id", "entity_id", "version", "core_facts", "full_profile",
            "voice_config", "change_type", "change_summary", "changed_by",
            "change_source", "created_at", "valid_from", "valid_until"
        ]
        old_version = dict(zip(columns, row))

        # Get latest version number
        row = await self.db.fetchone(
            "SELECT MAX(version) FROM entity_versions WHERE entity_id = ?",
            (entity_id,)
        )
        latest = row[0] if row and row[0] else 0

        new_version = latest + 1
        now = datetime.now().isoformat()

        # Close current version
        await self.db.execute(
            """
            UPDATE entity_versions
            SET valid_until = ?
            WHERE entity_id = ? AND valid_until IS NULL
            """,
            (now, entity_id)
        )

        # Create rollback version
        await self.db.execute(
            """
            INSERT INTO entity_versions (entity_id, version, core_facts, full_profile,
                                         voice_config, change_type, change_summary,
                                         changed_by, change_source, created_at,
                                         valid_from, valid_until)
            VALUES (?, ?, ?, ?, ?, 'rollback', ?, ?, NULL, ?, ?, NULL)
            """,
            (entity_id, new_version, old_version["core_facts"],
             old_version["full_profile"], old_version["voice_config"],
             f"Rollback to v{to_version}: {reason}", changed_by, now, now)
        )

        # Update entities table
        await self.db.execute(
            """
            UPDATE entities
            SET core_facts = ?, full_profile = ?, voice_config = ?,
                current_version = ?, updated_at = ?
            WHERE id = ?
            """,
            (old_version["core_facts"], old_version["full_profile"],
             old_version["voice_config"], new_version, now, entity_id)
        )

        logger.info(f"Rolled back entity {entity_id} to version {to_version}")

        return await self.get_current_version(entity_id)

    async def create_relationship(
        self,
        from_entity: str,
        to_entity: str,
        relationship: str,
        strength: float = 0.5,
        bidirectional: bool = False,
        context: str = None,
    ) -> int:
        """
        Create a relationship between two entities.

        Args:
            from_entity: Source entity ID
            to_entity: Target entity ID
            relationship: Relationship type
            strength: Relationship strength (0-1)
            bidirectional: Whether relationship goes both ways
            context: Additional context

        Returns:
            Relationship ID
        """
        now = datetime.now().isoformat()

        await self.db.execute(
            """
            INSERT INTO entity_relationships
            (from_entity, to_entity, relationship, strength, bidirectional,
             context, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (from_entity, to_entity, relationship, strength,
             1 if bidirectional else 0, context, now, now)
        )

        # Get the last inserted row ID
        row = await self.db.fetchone("SELECT last_insert_rowid()")
        return row[0] if row else 0

    async def get_relationships(
        self,
        entity_id: str,
        direction: str = "both"
    ) -> list[EntityDict]:
        """
        Get relationships for an entity.

        Args:
            entity_id: Entity ID
            direction: "outgoing", "incoming", or "both"

        Returns:
            List of relationships as dicts
        """
        if direction == "outgoing":
            query = "SELECT * FROM entity_relationships WHERE from_entity = ?"
            params = (entity_id,)
        elif direction == "incoming":
            query = "SELECT * FROM entity_relationships WHERE to_entity = ?"
            params = (entity_id,)
        else:  # both
            query = """
                SELECT * FROM entity_relationships
                WHERE from_entity = ? OR to_entity = ?
            """
            params = (entity_id, entity_id)

        rows = await self.db.fetchall(query, params)

        columns = [
            "id", "from_entity", "to_entity", "relationship", "strength",
            "bidirectional", "context", "created_at", "updated_at"
        ]

        return [dict(zip(columns, row)) for row in rows]

    async def create_mention(
        self,
        entity_id: str,
        node_id: str,
        mention_type: str = "reference",
        confidence: float = 1.0,
        context_snippet: str = None,
    ) -> None:
        """
        Create a mention linking an entity to a memory node.

        Args:
            entity_id: Entity being mentioned
            node_id: Memory node containing the mention
            mention_type: Type of mention (subject, author, reference)
            confidence: Confidence in the link (0-1)
            context_snippet: Brief excerpt showing mention
        """
        now = datetime.now().isoformat()

        await self.db.execute(
            """
            INSERT OR REPLACE INTO entity_mentions
            (entity_id, node_id, mention_type, confidence, context_snippet, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (entity_id, node_id, mention_type, confidence, context_snippet, now)
        )

    async def get_entity_mentions(self, entity_id: str) -> list[EntityDict]:
        """
        Get all mentions of an entity.

        Args:
            entity_id: Entity ID

        Returns:
            List of mentions as dicts
        """
        rows = await self.db.fetchall(
            """
            SELECT em.*, mn.content, mn.node_type
            FROM entity_mentions em
            JOIN memory_nodes mn ON em.node_id = mn.id
            WHERE em.entity_id = ?
            ORDER BY em.created_at DESC
            """,
            (entity_id,)
        )

        columns = [
            "entity_id", "node_id", "mention_type", "confidence",
            "context_snippet", "created_at", "content", "node_type"
        ]

        return [dict(zip(columns, row)) for row in rows]

    async def get_mention_types(self, entity_id: str) -> set[str]:
        """
        Get set of mention types for an entity.

        Args:
            entity_id: Entity ID

        Returns:
            Set of mention types
        """
        rows = await self.db.fetchall(
            """
            SELECT DISTINCT mention_type FROM entity_mentions
            WHERE entity_id = ?
            """,
            (entity_id,)
        )

        return {row[0] for row in rows}

    # =========================================================================
    # MENTION DETECTION (for context building)
    # =========================================================================

    async def detect_mentions(self, text: str) -> list[Entity]:
        """
        Detect entity mentions in text.

        Scans text for known entity names and aliases, returning
        all entities that are mentioned.

        Args:
            text: Text to scan for entity mentions

        Returns:
            List of mentioned Entity objects
        """
        # [TRACE] Entry point
        logger.info("[TRACE] detect_mentions() ENTRY")
        logger.info(f"[TRACE] text: '{text}'")

        if not text or not text.strip():
            return []

        text_lower = text.lower()
        mentioned = []
        seen_ids = set()

        try:
            # Get all entities for scanning
            rows = await self.db.fetchall(
                """
                SELECT id, entity_type, name, aliases, core_facts,
                       full_profile, voice_config, current_version,
                       metadata, created_at, updated_at
                FROM entities
                """
            )

            # [TRACE] After query
            logger.info(f"[TRACE] Found {len(rows)} entities in database")
            for row in rows:
                entity = self._row_to_entity(row)
                logger.info(f"[TRACE]   - Checking: {entity.name}")

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

            # [TRACE] After matching
            logger.info(f"[TRACE] Matched {len(mentioned)} entities")
            for e in mentioned:
                logger.info(f"[TRACE]   - MATCHED: {e.name}")

            return mentioned

        except Exception as e:
            logger.error(f"Error detecting mentions: {e}")
            return []

    async def resolve_with_cache(self, name_or_alias: str) -> Optional[EntityDict]:
        """
        Resolve a name or alias with caching.

        Uses internal cache to avoid repeated database lookups.
        Logs misses for Scribe to potentially create new profiles.

        Args:
            name_or_alias: Name or alias to resolve

        Returns:
            Entity dict if found, None otherwise
        """
        cache_key = name_or_alias.lower()

        # Check cache
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Resolve from database
        entity = await self.resolve_entity(name_or_alias)

        # Cache result (even None to avoid repeated lookups)
        self._cache[cache_key] = entity

        # Log miss for Scribe
        if entity is None:
            if name_or_alias not in self._miss_log:
                self._miss_log.append(name_or_alias)
                logger.info(f"[ENTITY-MISS] No profile for '{name_or_alias}' - queued for potential creation")

        return entity

    async def resolve_many(self, names: list[str]) -> list[Entity]:
        """
        Resolve multiple names, returning found entities.

        Args:
            names: List of names/aliases to resolve

        Returns:
            List of found Entity objects
        """
        entities = []
        for name in names:
            entity_dict = await self.resolve_with_cache(name)
            if entity_dict:
                entities.append(self._row_to_entity(tuple(entity_dict.values())))
        return entities

    def get_missed_names(self) -> list[str]:
        """
        Get names that couldn't be resolved (for Scribe to create).

        Returns:
            Copy of the miss log
        """
        return self._miss_log.copy()

    def clear_cache(self) -> None:
        """Clear the resolution cache."""
        self._cache.clear()

    def clear_miss_log(self) -> None:
        """Clear the miss log after Scribe processes it."""
        self._miss_log.clear()
