"""
Tests for Entity System
========================

Comprehensive tests for Luna's Entity System including:
- Entity creation and versioning
- Temporal queries
- Rollback functionality
- Entity resolution (by name, alias, case insensitive)
- Entity relationships
- Entity mentions (linking to memory nodes)

These tests are based on HANDOFF_ENTITY_SYSTEM.md specification.
"""

import asyncio
import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

import aiosqlite


# ============================================================
# FIXTURES
# ============================================================

@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for tests."""
    with TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
async def db(temp_data_dir):
    """
    Create an in-memory SQLite database with entity system schema.

    Loads schema from migrations/001_entity_system.sql plus the base
    memory_nodes table needed for entity_mentions foreign key.
    """
    db_path = temp_data_dir / "test_entities.db"

    conn = await aiosqlite.connect(db_path)

    # Enable foreign keys
    await conn.execute("PRAGMA foreign_keys=ON")

    # Create base memory_nodes table (needed for entity_mentions FK)
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS memory_nodes (
            id TEXT PRIMARY KEY,
            node_type TEXT NOT NULL,
            content TEXT NOT NULL,
            importance REAL DEFAULT 0.5,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)

    # Load entity system schema from migrations
    migrations_path = Path(__file__).parent.parent / "migrations" / "001_entity_system.sql"

    if migrations_path.exists():
        schema_sql = migrations_path.read_text()
        await conn.executescript(schema_sql)
    else:
        # Inline schema if migrations file not found
        await conn.executescript("""
            -- ENTITIES TABLE
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                entity_type TEXT NOT NULL,
                name TEXT NOT NULL,
                aliases TEXT,
                core_facts TEXT,
                full_profile TEXT,
                voice_config TEXT,
                current_version INTEGER DEFAULT 1,
                metadata TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            -- ENTITY RELATIONSHIPS TABLE
            CREATE TABLE IF NOT EXISTS entity_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_entity TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                to_entity TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                relationship TEXT NOT NULL,
                strength REAL DEFAULT 0.5,
                bidirectional INTEGER DEFAULT 0,
                context TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                UNIQUE(from_entity, to_entity, relationship)
            );

            -- ENTITY MENTIONS TABLE
            CREATE TABLE IF NOT EXISTS entity_mentions (
                entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                node_id TEXT NOT NULL REFERENCES memory_nodes(id) ON DELETE CASCADE,
                mention_type TEXT NOT NULL,
                confidence REAL DEFAULT 1.0,
                context_snippet TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (entity_id, node_id)
            );

            -- ENTITY VERSIONS TABLE
            CREATE TABLE IF NOT EXISTS entity_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                version INTEGER NOT NULL,
                core_facts TEXT,
                full_profile TEXT,
                voice_config TEXT,
                change_type TEXT NOT NULL,
                change_summary TEXT,
                changed_by TEXT NOT NULL,
                change_source TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                valid_from TEXT DEFAULT (datetime('now')),
                valid_until TEXT,
                UNIQUE(entity_id, version)
            );

            -- INDEXES
            CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(entity_type);
            CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
            CREATE INDEX IF NOT EXISTS idx_relationships_from ON entity_relationships(from_entity);
            CREATE INDEX IF NOT EXISTS idx_relationships_to ON entity_relationships(to_entity);
            CREATE INDEX IF NOT EXISTS idx_mentions_entity ON entity_mentions(entity_id);
            CREATE INDEX IF NOT EXISTS idx_mentions_node ON entity_mentions(node_id);
        """)

    await conn.commit()

    yield conn

    await conn.close()


class DatabaseAdapter:
    """
    Adapter to make aiosqlite.Connection work with EntityResolver's expected interface.

    EntityResolver expects a database with fetchone/fetchall/execute methods
    that match MemoryDatabase's interface.
    """

    def __init__(self, conn: aiosqlite.Connection):
        self.conn = conn

    async def fetchone(self, query: str, params: tuple = ()):
        """Execute query and return single row."""
        async with self.conn.execute(query, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, query: str, params: tuple = ()):
        """Execute query and return all rows."""
        async with self.conn.execute(query, params) as cursor:
            return await cursor.fetchall()

    async def execute(self, query: str, params: tuple = ()):
        """Execute a query (INSERT/UPDATE/DELETE)."""
        await self.conn.execute(query, params)
        await self.conn.commit()


@pytest.fixture
async def entity_resolver(db):
    """
    Create an EntityResolver instance for testing.

    The EntityResolver handles:
    - Creating entities with version 1
    - Updating entities (creates new versions)
    - Resolving entities by name, alias, id
    - Temporal queries
    - Rollback operations
    """
    # Import here to allow tests to run even if module not yet implemented
    try:
        from luna.entities.resolution import EntityResolver
        # Wrap the aiosqlite connection with our adapter
        db_adapter = DatabaseAdapter(db)
        return EntityResolver(db_adapter)
    except ImportError:
        # Return a mock resolver that uses the db directly
        return MockEntityResolver(db)


class MockEntityResolver:
    """
    Mock EntityResolver for testing before implementation exists.

    Implements the expected interface based on HANDOFF_ENTITY_SYSTEM.md.
    """

    def __init__(self, db: aiosqlite.Connection):
        self.db = db

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
    ) -> dict:
        """Create a new entity with version 1."""
        import uuid

        entity_id = name.lower().replace(" ", "-")
        aliases_json = json.dumps(aliases or [])
        core_facts_json = json.dumps(core_facts or {})
        voice_config_json = json.dumps(voice_config) if voice_config else None

        # Insert entity
        await self.db.execute("""
            INSERT INTO entities (id, entity_type, name, aliases, core_facts,
                                  full_profile, voice_config, current_version)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        """, (entity_id, entity_type, name, aliases_json, core_facts_json,
              full_profile, voice_config_json))

        # Insert version 1
        await self.db.execute("""
            INSERT INTO entity_versions (entity_id, version, core_facts, full_profile,
                                         voice_config, change_type, change_summary,
                                         changed_by, change_source)
            VALUES (?, 1, ?, ?, ?, 'create', 'Initial creation', ?, ?)
        """, (entity_id, core_facts_json, full_profile, voice_config_json,
              changed_by, source))

        await self.db.commit()

        return await self.get_entity(entity_id)

    async def update_entity(
        self,
        entity_id: str,
        core_facts: dict = None,
        full_profile: str = None,
        voice_config: dict = None,
        change_summary: str = "Updated entity",
        source: str = "test",
        changed_by: str = "scribe",
    ) -> dict:
        """Update entity by creating a new version."""
        # Get current version
        current = await self.get_current_version(entity_id)
        if not current:
            raise ValueError(f"Entity {entity_id} not found")

        new_version = current["version"] + 1

        # Merge core facts
        existing_facts = json.loads(current["core_facts"] or "{}")
        if core_facts:
            existing_facts.update(core_facts)
        new_core_facts = json.dumps(existing_facts)

        # Use new values or existing
        new_profile = full_profile if full_profile is not None else current["full_profile"]
        new_voice = json.dumps(voice_config) if voice_config else current["voice_config"]

        # Close current version
        await self.db.execute("""
            UPDATE entity_versions
            SET valid_until = datetime('now')
            WHERE entity_id = ? AND valid_until IS NULL
        """, (entity_id,))

        # Create new version
        await self.db.execute("""
            INSERT INTO entity_versions (entity_id, version, core_facts, full_profile,
                                         voice_config, change_type, change_summary,
                                         changed_by, change_source)
            VALUES (?, ?, ?, ?, ?, 'update', ?, ?, ?)
        """, (entity_id, new_version, new_core_facts, new_profile, new_voice,
              change_summary, changed_by, source))

        # Update entities table
        await self.db.execute("""
            UPDATE entities
            SET core_facts = ?, full_profile = ?, voice_config = ?,
                current_version = ?, updated_at = datetime('now')
            WHERE id = ?
        """, (new_core_facts, new_profile, new_voice, new_version, entity_id))

        await self.db.commit()

        return await self.get_current_version(entity_id)

    async def get_entity(self, entity_id: str) -> dict | None:
        """Get entity by ID."""
        async with self.db.execute(
            "SELECT * FROM entities WHERE id = ?", (entity_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                columns = [d[0] for d in cursor.description]
                return dict(zip(columns, row))
        return None

    async def get_current_version(self, entity_id: str) -> dict | None:
        """Get the current (latest) version of an entity."""
        async with self.db.execute("""
            SELECT * FROM entity_versions
            WHERE entity_id = ? AND valid_until IS NULL
            ORDER BY version DESC
            LIMIT 1
        """, (entity_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                columns = [d[0] for d in cursor.description]
                return dict(zip(columns, row))
        return None

    async def get_entity_at_time(
        self,
        entity_id: str,
        timestamp: str
    ) -> dict | None:
        """Get entity state at a specific timestamp."""
        async with self.db.execute("""
            SELECT * FROM entity_versions
            WHERE entity_id = ?
              AND valid_from <= ?
              AND (valid_until IS NULL OR valid_until > ?)
            ORDER BY version DESC
            LIMIT 1
        """, (entity_id, timestamp, timestamp)) as cursor:
            row = await cursor.fetchone()
            if row:
                columns = [d[0] for d in cursor.description]
                return dict(zip(columns, row))
        return None

    async def get_entity_history(self, entity_id: str) -> list[dict]:
        """Get full version history of an entity."""
        async with self.db.execute("""
            SELECT * FROM entity_versions
            WHERE entity_id = ?
            ORDER BY version ASC
        """, (entity_id,)) as cursor:
            rows = await cursor.fetchall()
            if rows:
                columns = [d[0] for d in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        return []

    async def rollback_entity(
        self,
        entity_id: str,
        to_version: int,
        reason: str,
        changed_by: str = "librarian",
    ) -> dict:
        """Rollback entity to a previous version (creates new version)."""
        # Get the old version to restore
        async with self.db.execute("""
            SELECT * FROM entity_versions
            WHERE entity_id = ? AND version = ?
        """, (entity_id, to_version)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise ValueError(f"Version {to_version} not found for {entity_id}")
            columns = [d[0] for d in cursor.description]
            old_version = dict(zip(columns, row))

        # Get latest version number
        async with self.db.execute("""
            SELECT MAX(version) FROM entity_versions WHERE entity_id = ?
        """, (entity_id,)) as cursor:
            row = await cursor.fetchone()
            latest = row[0] if row else 0

        new_version = latest + 1

        # Close current version
        await self.db.execute("""
            UPDATE entity_versions
            SET valid_until = datetime('now')
            WHERE entity_id = ? AND valid_until IS NULL
        """, (entity_id,))

        # Create rollback version
        await self.db.execute("""
            INSERT INTO entity_versions (entity_id, version, core_facts, full_profile,
                                         voice_config, change_type, change_summary,
                                         changed_by, change_source)
            VALUES (?, ?, ?, ?, ?, 'rollback', ?, ?, NULL)
        """, (entity_id, new_version, old_version["core_facts"],
              old_version["full_profile"], old_version["voice_config"],
              f"Rollback to v{to_version}: {reason}", changed_by))

        # Update entities table
        await self.db.execute("""
            UPDATE entities
            SET core_facts = ?, full_profile = ?, voice_config = ?,
                current_version = ?, updated_at = datetime('now')
            WHERE id = ?
        """, (old_version["core_facts"], old_version["full_profile"],
              old_version["voice_config"], new_version, entity_id))

        await self.db.commit()

        return await self.get_current_version(entity_id)

    async def resolve_entity(self, query: str) -> dict | None:
        """
        Find entity by name, alias, or fuzzy match.

        Resolution order:
        1. Exact match on id
        2. Exact match on name (case-insensitive)
        3. Match in aliases (case-insensitive)
        """
        # 1. Exact match on id
        normalized_id = query.lower().replace(" ", "-")
        entity = await self.get_entity(normalized_id)
        if entity:
            return entity

        # 2. Exact match on name (case-insensitive)
        async with self.db.execute(
            "SELECT * FROM entities WHERE LOWER(name) = LOWER(?)", (query,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                columns = [d[0] for d in cursor.description]
                return dict(zip(columns, row))

        # 3. Match in aliases (case-insensitive)
        async with self.db.execute("SELECT * FROM entities") as cursor:
            rows = await cursor.fetchall()
            columns = [d[0] for d in cursor.description]

            for row in rows:
                entity = dict(zip(columns, row))
                aliases = json.loads(entity.get("aliases") or "[]")
                # Case-insensitive alias matching
                if any(alias.lower() == query.lower() for alias in aliases):
                    return entity

        return None

    async def create_relationship(
        self,
        from_entity: str,
        to_entity: str,
        relationship: str,
        strength: float = 0.5,
        bidirectional: bool = False,
        context: str = None,
    ) -> int:
        """Create a relationship between two entities."""
        cursor = await self.db.execute("""
            INSERT INTO entity_relationships
            (from_entity, to_entity, relationship, strength, bidirectional, context)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (from_entity, to_entity, relationship, strength,
              1 if bidirectional else 0, context))
        await self.db.commit()
        return cursor.lastrowid

    async def get_relationships(
        self,
        entity_id: str,
        direction: str = "both"
    ) -> list[dict]:
        """Get relationships for an entity."""
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

        async with self.db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            if rows:
                columns = [d[0] for d in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        return []

    async def create_mention(
        self,
        entity_id: str,
        node_id: str,
        mention_type: str = "reference",
        confidence: float = 1.0,
        context_snippet: str = None,
    ) -> None:
        """Create a mention linking an entity to a memory node."""
        await self.db.execute("""
            INSERT OR REPLACE INTO entity_mentions
            (entity_id, node_id, mention_type, confidence, context_snippet)
            VALUES (?, ?, ?, ?, ?)
        """, (entity_id, node_id, mention_type, confidence, context_snippet))
        await self.db.commit()

    async def get_entity_mentions(self, entity_id: str) -> list[dict]:
        """Get all mentions of an entity."""
        async with self.db.execute("""
            SELECT em.*, mn.content, mn.node_type
            FROM entity_mentions em
            JOIN memory_nodes mn ON em.node_id = mn.id
            WHERE em.entity_id = ?
            ORDER BY em.created_at DESC
        """, (entity_id,)) as cursor:
            rows = await cursor.fetchall()
            if rows:
                columns = [d[0] for d in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        return []

    async def get_node_entities(self, node_id: str) -> list[dict]:
        """Get all entities mentioned in a memory node."""
        async with self.db.execute("""
            SELECT e.*, em.mention_type, em.confidence
            FROM entity_mentions em
            JOIN entities e ON em.entity_id = e.id
            WHERE em.node_id = ?
        """, (node_id,)) as cursor:
            rows = await cursor.fetchall()
            if rows:
                columns = [d[0] for d in cursor.description]
                return [dict(zip(columns, row)) for row in rows]
        return []


# ============================================================
# TEST CLASSES
# ============================================================

class TestEntityCreation:
    """Tests for entity creation."""

    @pytest.mark.asyncio
    async def test_create_entity(self, entity_resolver):
        """New entity creates version 1."""
        version = await entity_resolver.create_entity(
            name="Test Person",
            entity_type="person",
            core_facts={"role": "test subject"},
            source="test",
        )

        assert version is not None
        assert version["id"] == "test-person"
        assert version["current_version"] == 1

        # Check version record exists
        history = await entity_resolver.get_entity_history("test-person")
        assert len(history) == 1
        assert history[0]["version"] == 1
        assert history[0]["change_type"] == "create"

    @pytest.mark.asyncio
    async def test_create_entity_with_aliases(self, entity_resolver):
        """Entity creation includes aliases."""
        await entity_resolver.create_entity(
            name="Marzipan",
            entity_type="person",
            aliases=["Marzi", "Mars"],
            core_facts={"location": "Mars College"},
        )

        entity = await entity_resolver.get_entity("marzipan")
        assert entity is not None

        aliases = json.loads(entity["aliases"])
        assert "Marzi" in aliases
        assert "Mars" in aliases

    @pytest.mark.asyncio
    async def test_create_persona_with_voice_config(self, entity_resolver):
        """Persona creation includes voice configuration."""
        voice_config = {
            "tone": "Colonial gravitas with dry wit",
            "patterns": ["Meticulous attention to detail"],
            "constraints": ["Never fabricate facts"],
        }

        await entity_resolver.create_entity(
            name="Ben Franklin",
            entity_type="persona",
            voice_config=voice_config,
            full_profile="Benjamin Franklin serves as The Scribe.",
        )

        entity = await entity_resolver.get_entity("ben-franklin")
        assert entity is not None
        assert entity["entity_type"] == "persona"

        config = json.loads(entity["voice_config"])
        assert config["tone"] == "Colonial gravitas with dry wit"


class TestEntityVersioning:
    """Tests for entity versioning system."""

    @pytest.mark.asyncio
    async def test_update_creates_new_version(self, entity_resolver):
        """Update creates version 2, preserves version 1."""
        # Create v1
        await entity_resolver.create_entity(
            name="Test Entity",
            entity_type="person",
            core_facts={"original": "fact"},
        )

        # Update creates v2
        v2 = await entity_resolver.update_entity(
            entity_id="test-entity",
            core_facts={"new": "fact"},
            change_summary="Added new fact",
        )

        assert v2["version"] == 2
        assert v2["change_type"] == "update"

        # v1 still exists in history
        history = await entity_resolver.get_entity_history("test-entity")
        assert len(history) == 2
        assert history[0]["version"] == 1
        assert history[0]["valid_until"] is not None  # Closed
        assert history[1]["version"] == 2
        assert history[1]["valid_until"] is None  # Current

    @pytest.mark.asyncio
    async def test_update_merges_core_facts(self, entity_resolver):
        """Update merges new facts with existing facts."""
        # Create with initial facts
        await entity_resolver.create_entity(
            name="Merge Test",
            entity_type="person",
            core_facts={"name": "Test", "role": "Subject"},
        )

        # Update with additional facts
        v2 = await entity_resolver.update_entity(
            entity_id="merge-test",
            core_facts={"location": "Test Lab"},
        )

        # Both original and new facts present
        facts = json.loads(v2["core_facts"])
        assert facts["name"] == "Test"
        assert facts["role"] == "Subject"
        assert facts["location"] == "Test Lab"

    @pytest.mark.asyncio
    async def test_multiple_updates_create_chain(self, entity_resolver):
        """Multiple updates create proper version chain."""
        await entity_resolver.create_entity(
            name="Chain Test",
            entity_type="person",
            core_facts={"v": 1},
        )

        await entity_resolver.update_entity(
            entity_id="chain-test",
            core_facts={"v": 2},
        )

        await entity_resolver.update_entity(
            entity_id="chain-test",
            core_facts={"v": 3},
        )

        history = await entity_resolver.get_entity_history("chain-test")
        assert len(history) == 3
        assert [h["version"] for h in history] == [1, 2, 3]


class TestTemporalQueries:
    """Tests for temporal query functionality."""

    @pytest.mark.asyncio
    async def test_temporal_query(self, entity_resolver):
        """Can query entity state at past time."""
        # Create entity
        v1 = await entity_resolver.create_entity(
            name="Temporal Test",
            entity_type="person",
            core_facts={"state": "initial"},
        )

        # Record v1 creation time
        v1_time = v1.get("created_at") or v1.get("valid_from")

        # Small delay to ensure different timestamps
        await asyncio.sleep(0.1)

        # Update entity
        await entity_resolver.update_entity(
            entity_id="temporal-test",
            core_facts={"state": "updated"},
        )

        # Query at v1 time should return v1 state
        past_state = await entity_resolver.get_entity_at_time(
            "temporal-test",
            v1_time
        )

        assert past_state is not None
        assert past_state["version"] == 1

        facts = json.loads(past_state["core_facts"])
        assert facts["state"] == "initial"

    @pytest.mark.asyncio
    async def test_temporal_query_current(self, entity_resolver):
        """Temporal query with current time returns latest version."""
        await entity_resolver.create_entity(
            name="Current Test",
            entity_type="person",
            core_facts={"v": 1},
        )

        await entity_resolver.update_entity(
            entity_id="current-test",
            core_facts={"v": 2},
        )

        # Query with future timestamp should return current
        future_time = (datetime.now() + timedelta(days=1)).isoformat()
        current_state = await entity_resolver.get_entity_at_time(
            "current-test",
            future_time
        )

        assert current_state is not None
        assert current_state["version"] == 2


class TestRollback:
    """Tests for rollback functionality."""

    @pytest.mark.asyncio
    async def test_rollback(self, entity_resolver):
        """Rollback creates new version with old content."""
        # Create v1
        await entity_resolver.create_entity(
            name="Rollback Test",
            entity_type="person",
            core_facts={"state": "original"},
        )

        # Create v2 with bad update
        await entity_resolver.update_entity(
            entity_id="rollback-test",
            core_facts={"state": "bad"},
        )

        # Rollback to v1
        v3 = await entity_resolver.rollback_entity(
            entity_id="rollback-test",
            to_version=1,
            reason="Bad update",
        )

        # v3 should have v1's content
        assert v3["version"] == 3
        assert v3["change_type"] == "rollback"

        facts = json.loads(v3["core_facts"])
        assert facts["state"] == "original"

    @pytest.mark.asyncio
    async def test_rollback_preserves_history(self, entity_resolver):
        """Rollback preserves all versions in history."""
        await entity_resolver.create_entity(
            name="History Test",
            entity_type="person",
            core_facts={"v": 1},
        )

        await entity_resolver.update_entity(
            entity_id="history-test",
            core_facts={"v": 2},
        )

        await entity_resolver.rollback_entity(
            entity_id="history-test",
            to_version=1,
            reason="Testing",
        )

        # All 3 versions should exist
        history = await entity_resolver.get_entity_history("history-test")
        assert len(history) == 3
        assert history[2]["change_type"] == "rollback"
        assert "Rollback to v1" in history[2]["change_summary"]

    @pytest.mark.asyncio
    async def test_rollback_invalid_version(self, entity_resolver):
        """Rollback to non-existent version raises error."""
        await entity_resolver.create_entity(
            name="Invalid Test",
            entity_type="person",
        )

        with pytest.raises(ValueError):
            await entity_resolver.rollback_entity(
                entity_id="invalid-test",
                to_version=999,
                reason="Should fail",
            )


class TestEntityResolution:
    """Tests for entity resolution (name/alias lookup)."""

    @pytest.mark.asyncio
    async def test_entity_resolution_by_name(self, entity_resolver):
        """Resolves entity by exact name."""
        await entity_resolver.create_entity(
            name="Marzipan",
            entity_type="person",
        )

        entity = await entity_resolver.resolve_entity("Marzipan")
        assert entity is not None
        assert entity["id"] == "marzipan"

    @pytest.mark.asyncio
    async def test_entity_resolution_by_alias(self, entity_resolver):
        """Resolves entity by alias."""
        await entity_resolver.create_entity(
            name="Marzipan",
            entity_type="person",
            aliases=["Marzi", "Mars"],
        )

        entity = await entity_resolver.resolve_entity("Marzi")
        assert entity is not None
        assert entity["id"] == "marzipan"

    @pytest.mark.asyncio
    async def test_entity_resolution_case_insensitive(self, entity_resolver):
        """Resolves entity case-insensitively."""
        await entity_resolver.create_entity(
            name="Marzipan",
            entity_type="person",
            aliases=["Marzi"],
        )

        # By name - various cases
        e1 = await entity_resolver.resolve_entity("MARZIPAN")
        e2 = await entity_resolver.resolve_entity("marzipan")
        e3 = await entity_resolver.resolve_entity("MaRzIpAn")

        assert e1 is not None and e1["id"] == "marzipan"
        assert e2 is not None and e2["id"] == "marzipan"
        assert e3 is not None and e3["id"] == "marzipan"

        # By alias - various cases
        e4 = await entity_resolver.resolve_entity("MARZI")
        e5 = await entity_resolver.resolve_entity("marzi")

        assert e4 is not None and e4["id"] == "marzipan"
        assert e5 is not None and e5["id"] == "marzipan"

    @pytest.mark.asyncio
    async def test_entity_resolution_by_id(self, entity_resolver):
        """Resolves entity by ID."""
        await entity_resolver.create_entity(
            name="Ben Franklin",
            entity_type="persona",
        )

        entity = await entity_resolver.resolve_entity("ben-franklin")
        assert entity is not None
        assert entity["name"] == "Ben Franklin"

    @pytest.mark.asyncio
    async def test_entity_resolution_not_found(self, entity_resolver):
        """Returns None for unknown entity."""
        entity = await entity_resolver.resolve_entity("nonexistent")
        assert entity is None


class TestEntityRelationships:
    """Tests for entity relationship system."""

    @pytest.mark.asyncio
    async def test_entity_relationships(self, entity_resolver):
        """Create and query relationships."""
        # Create two entities
        await entity_resolver.create_entity(
            name="Ahab",
            entity_type="person",
        )
        await entity_resolver.create_entity(
            name="Luna Engine",
            entity_type="project",
        )

        # Create relationship
        rel_id = await entity_resolver.create_relationship(
            from_entity="ahab",
            to_entity="luna-engine",
            relationship="creator",
            strength=1.0,
            context="Lead architect",
        )

        assert rel_id is not None

        # Query relationships
        rels = await entity_resolver.get_relationships("ahab", direction="outgoing")

        assert len(rels) == 1
        assert rels[0]["to_entity"] == "luna-engine"
        assert rels[0]["relationship"] == "creator"

    @pytest.mark.asyncio
    async def test_bidirectional_relationship(self, entity_resolver):
        """Bidirectional relationships work correctly."""
        await entity_resolver.create_entity(name="Alice", entity_type="person")
        await entity_resolver.create_entity(name="Bob", entity_type="person")

        await entity_resolver.create_relationship(
            from_entity="alice",
            to_entity="bob",
            relationship="collaborator",
            bidirectional=True,
        )

        # Query from Alice's perspective
        alice_rels = await entity_resolver.get_relationships("alice")
        assert len(alice_rels) >= 1

        # Query from Bob's perspective
        bob_rels = await entity_resolver.get_relationships("bob")
        assert len(bob_rels) >= 1

    @pytest.mark.asyncio
    async def test_multiple_relationships(self, entity_resolver):
        """Entity can have multiple relationships."""
        await entity_resolver.create_entity(name="Creator", entity_type="person")
        await entity_resolver.create_entity(name="Project A", entity_type="project")
        await entity_resolver.create_entity(name="Project B", entity_type="project")

        await entity_resolver.create_relationship(
            from_entity="creator",
            to_entity="project-a",
            relationship="works_on",
        )
        await entity_resolver.create_relationship(
            from_entity="creator",
            to_entity="project-b",
            relationship="works_on",
        )

        rels = await entity_resolver.get_relationships("creator", direction="outgoing")
        assert len(rels) == 2


class TestEntityMentions:
    """Tests for entity mentions (linking to memory nodes)."""

    @pytest.fixture
    async def db_with_nodes(self, db):
        """Database with some memory nodes for testing mentions."""
        # Insert test memory nodes
        await db.execute("""
            INSERT INTO memory_nodes (id, node_type, content)
            VALUES ('node-1', 'FACT', 'Marzipan is at Mars College')
        """)
        await db.execute("""
            INSERT INTO memory_nodes (id, node_type, content)
            VALUES ('node-2', 'DECISION', 'We will use SQLite for storage')
        """)
        await db.execute("""
            INSERT INTO memory_nodes (id, node_type, content)
            VALUES ('node-3', 'FACT', 'Ahab created Luna Engine')
        """)
        await db.commit()
        return db

    @pytest.mark.asyncio
    async def test_entity_mentions(self, db_with_nodes):
        """Link entities to memory nodes."""
        resolver = MockEntityResolver(db_with_nodes)

        # Create entity
        await resolver.create_entity(
            name="Marzipan",
            entity_type="person",
        )

        # Create mention
        await resolver.create_mention(
            entity_id="marzipan",
            node_id="node-1",
            mention_type="subject",
            confidence=1.0,
            context_snippet="Marzipan is at Mars College",
        )

        # Query mentions
        mentions = await resolver.get_entity_mentions("marzipan")

        assert len(mentions) == 1
        assert mentions[0]["node_id"] == "node-1"
        assert mentions[0]["mention_type"] == "subject"

    @pytest.mark.asyncio
    async def test_multiple_mentions(self, db_with_nodes):
        """Entity can be mentioned in multiple nodes."""
        resolver = MockEntityResolver(db_with_nodes)

        await resolver.create_entity(name="Ahab", entity_type="person")

        await resolver.create_mention(
            entity_id="ahab",
            node_id="node-1",
            mention_type="reference",
        )
        await resolver.create_mention(
            entity_id="ahab",
            node_id="node-3",
            mention_type="subject",
        )

        mentions = await resolver.get_entity_mentions("ahab")
        assert len(mentions) == 2

    @pytest.mark.asyncio
    async def test_node_entities(self, db_with_nodes):
        """Query all entities mentioned in a node."""
        resolver = MockEntityResolver(db_with_nodes)

        await resolver.create_entity(name="Ahab", entity_type="person")
        await resolver.create_entity(name="Luna Engine", entity_type="project")

        await resolver.create_mention(
            entity_id="ahab",
            node_id="node-3",
            mention_type="subject",
        )
        await resolver.create_mention(
            entity_id="luna-engine",
            node_id="node-3",
            mention_type="subject",
        )

        entities = await resolver.get_node_entities("node-3")
        assert len(entities) == 2

        entity_ids = [e["id"] for e in entities]
        assert "ahab" in entity_ids
        assert "luna-engine" in entity_ids

    @pytest.mark.asyncio
    async def test_mention_types(self, db_with_nodes):
        """Different mention types are stored correctly."""
        resolver = MockEntityResolver(db_with_nodes)

        await resolver.create_entity(name="Test Entity", entity_type="person")

        # Subject mention
        await resolver.create_mention(
            entity_id="test-entity",
            node_id="node-1",
            mention_type="subject",
        )

        # Reference mention
        await resolver.create_mention(
            entity_id="test-entity",
            node_id="node-2",
            mention_type="reference",
        )

        mentions = await resolver.get_entity_mentions("test-entity")
        mention_types = [m["mention_type"] for m in mentions]

        assert "subject" in mention_types
        assert "reference" in mention_types


class TestEntityTypes:
    """Tests for different entity types."""

    @pytest.mark.asyncio
    async def test_person_entity(self, entity_resolver):
        """Person entities are created correctly."""
        await entity_resolver.create_entity(
            name="Test Person",
            entity_type="person",
            core_facts={"role": "tester"},
        )

        entity = await entity_resolver.get_entity("test-person")
        assert entity["entity_type"] == "person"

    @pytest.mark.asyncio
    async def test_persona_entity(self, entity_resolver):
        """Persona entities include voice configuration."""
        await entity_resolver.create_entity(
            name="The Dude",
            entity_type="persona",
            voice_config={"tone": "Laid back, chill"},
        )

        entity = await entity_resolver.get_entity("the-dude")
        assert entity["entity_type"] == "persona"

        voice = json.loads(entity["voice_config"])
        assert "tone" in voice

    @pytest.mark.asyncio
    async def test_place_entity(self, entity_resolver):
        """Place entities are created correctly."""
        await entity_resolver.create_entity(
            name="Mars College",
            entity_type="place",
            core_facts={"location": "Bombay Beach, CA"},
        )

        entity = await entity_resolver.get_entity("mars-college")
        assert entity["entity_type"] == "place"

    @pytest.mark.asyncio
    async def test_project_entity(self, entity_resolver):
        """Project entities are created correctly."""
        await entity_resolver.create_entity(
            name="Luna Engine",
            entity_type="project",
            core_facts={"status": "active", "version": "2.0"},
        )

        entity = await entity_resolver.get_entity("luna-engine")
        assert entity["entity_type"] == "project"
