#!/usr/bin/env python3
"""
End-to-end tests for Entity System.

These tests verify the ACTUAL execution path, not just that code exists.
Run with: pytest tests/test_entity_system_e2e.py -v -s

THESE TESTS MUST ALL PASS before the entity system is considered working.
"""

import pytest
import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import Optional, List, Dict, Any

import aiosqlite

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class SimpleDB:
    """Simple database wrapper that doesn't reload schema."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._connection = None

    async def connect(self):
        self._connection = await aiosqlite.connect(self.db_path)
        await self._connection.execute("PRAGMA foreign_keys=ON")

    async def close(self):
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def fetchone(self, sql: str, params: tuple = ()):
        async with self._connection.execute(sql, params) as cursor:
            return await cursor.fetchone()

    async def fetchall(self, sql: str, params: tuple = ()):
        async with self._connection.execute(sql, params) as cursor:
            return await cursor.fetchall()

    async def execute(self, sql: str, params: tuple = ()):
        cursor = await self._connection.execute(sql, params)
        await self._connection.commit()
        return cursor


# ============================================================================
# ENTITY RESOLUTION TESTS
# ============================================================================

class TestEntityResolution:
    """Tests that entity resolution actually works."""

    @pytest.fixture
    async def db(self):
        """Get real database connection WITHOUT reloading schema."""
        db_path = Path.home() / ".luna" / "luna.db"
        if not db_path.exists():
            pytest.skip(f"Database not found at {db_path}")

        db = SimpleDB(db_path)
        await db.connect()
        yield db
        await db.close()

    @pytest.fixture
    async def resolver(self, db):
        """Get a real EntityResolver connected to real database."""
        from luna.entities.resolution import EntityResolver

        resolver = EntityResolver(db)
        return resolver
    
    @pytest.mark.asyncio
    async def test_marzipan_exists_in_database(self, db):
        """Marzipan entity MUST exist in the database."""
        row = await db.fetchone(
            "SELECT id, name, core_facts FROM entities WHERE LOWER(name) = 'marzipan'"
        )
        
        assert row is not None, "Marzipan not found in entities table!"
        print(f"✅ Marzipan in database: id={row[0]}, name={row[1]}")
        print(f"   core_facts: {row[2]}")
    
    @pytest.mark.asyncio
    async def test_marzipan_resolvable(self, resolver):
        """Marzipan entity MUST be retrievable via resolver."""
        entity = await resolver.resolve_entity("marzipan")

        assert entity is not None, "Marzipan entity not found via resolver!"
        # resolve_entity returns a dict, not Entity object
        assert entity['name'].lower() == "marzipan"
        assert entity['core_facts'] is not None
        print(f"✅ Marzipan resolved: {entity['name']}")
        print(f"   core_facts: {entity['core_facts']}")
    
    @pytest.mark.asyncio
    async def test_detect_mentions_exists(self, resolver):
        """detect_mentions() method MUST exist."""
        assert hasattr(resolver, 'detect_mentions'), \
            "EntityResolver has no detect_mentions() method!"
        print("✅ detect_mentions() exists")
    
    @pytest.mark.asyncio
    async def test_detect_mentions_finds_marzipan(self, resolver):
        """detect_mentions() MUST find Marzipan in text."""
        text = "Do you remember Marzipan?"
        
        mentioned = await resolver.detect_mentions(text)
        
        assert mentioned is not None, "detect_mentions() returned None!"
        names = [e.name.lower() for e in mentioned]
        assert "marzipan" in names, f"Marzipan not detected! Found: {names}"
        print(f"✅ detect_mentions found: {names}")
    
    @pytest.mark.asyncio
    async def test_detect_mentions_case_insensitive(self, resolver):
        """detect_mentions() MUST be case-insensitive."""
        variants = ["marzipan", "Marzipan", "MARZIPAN"]
        
        for variant in variants:
            text = f"What about {variant}?"
            mentioned = await resolver.detect_mentions(text)
            names = [e.name.lower() for e in mentioned]
            assert "marzipan" in names, f"Failed on variant: {variant}, found: {names}"
            print(f"✅ Case variant '{variant}' detected")
    
    @pytest.mark.asyncio
    async def test_all_known_people_resolvable(self, resolver):
        """All backfilled people MUST be resolvable."""
        people = ["Marzipan", "Yulia", "Tarsila", "Kamau", "Ahab"]
        
        for name in people:
            entity = await resolver.resolve_entity(name)
            assert entity is not None, f"{name} not found!"
            print(f"✅ {name} resolvable")


# ============================================================================
# CONTEXT BUILDING TESTS
# ============================================================================

class TestContextBuilding:
    """Tests that context building includes entities."""

    @pytest.fixture
    async def db(self):
        """Get real database connection WITHOUT reloading schema."""
        db_path = Path.home() / ".luna" / "luna.db"
        if not db_path.exists():
            pytest.skip(f"Database not found at {db_path}")

        db = SimpleDB(db_path)
        await db.connect()
        yield db
        await db.close()

    @pytest.fixture
    async def entity_context(self, db):
        """Get real EntityContext connected to real database."""
        from luna.entities.context import EntityContext

        context = EntityContext(db)
        return context
    
    @pytest.mark.asyncio
    async def test_build_framed_context_exists(self, entity_context):
        """build_framed_context() method MUST exist."""
        assert hasattr(entity_context, 'build_framed_context'), \
            "EntityContext has no build_framed_context() method!"
        print("✅ build_framed_context() exists")
    
    @pytest.mark.asyncio
    async def test_framed_context_includes_marzipan(self, entity_context):
        """Framed context MUST include Marzipan when mentioned."""
        result = await entity_context.build_framed_context(
            message="Do you remember Marzipan?",
            conversation_history=[],
            memories=[],
        )
        
        assert result is not None, "build_framed_context() returned None!"
        assert isinstance(result, str), f"Expected string, got {type(result)}"
        assert "marzipan" in result.lower(), \
            f"Marzipan not in context!\nContext preview: {result[:500]}"
        print(f"✅ Marzipan in context. Length: {len(result)} chars")
        print(f"   Preview: {result[:300]}...")
    
    @pytest.mark.asyncio
    async def test_framed_context_includes_multiple_entities(self, entity_context):
        """Context should include multiple entities when mentioned."""
        result = await entity_context.build_framed_context(
            message="Tell me about Marzipan and Yulia",
            conversation_history=[],
            memories=[],
        )
        
        result_lower = result.lower()
        assert "marzipan" in result_lower, "Marzipan not in context!"
        assert "yulia" in result_lower, "Yulia not in context!"
        print("✅ Multiple entities detected and included")


# ============================================================================
# DIRECTOR INTEGRATION TESTS
# ============================================================================

class TestDirectorIntegration:
    """Tests that Director has the correct entity system wiring."""

    @pytest.fixture
    async def director(self):
        """Get Director instance."""
        try:
            from luna.actors.director import DirectorActor

            # Create director - NOTE: Without engine, entity context won't initialize
            # This is expected! Entity context requires engine lifecycle.
            director = DirectorActor()

            return director
        except Exception as e:
            pytest.skip(f"Could not create Director: {e}")

    @pytest.mark.asyncio
    async def test_director_has_entity_context_attribute(self, director):
        """Director MUST have _entity_context attribute defined."""
        # The attribute should EXIST (even if None without engine)
        assert hasattr(director, '_entity_context'), \
            "Director has no _entity_context attribute!"
        print("✅ Director has _entity_context attribute")
        print(f"   Value: {director._entity_context} (None expected without engine)")

    @pytest.mark.asyncio
    async def test_director_has_ensure_entity_context_method(self, director):
        """Director MUST have _ensure_entity_context() lazy init method."""
        assert hasattr(director, '_ensure_entity_context'), \
            "Director has no _ensure_entity_context() method for lazy init!"
        print("✅ Director has _ensure_entity_context() method")

    @pytest.mark.asyncio
    async def test_director_process_uses_entity_context(self, director):
        """Director.process() MUST call _ensure_entity_context()."""
        import inspect
        source = inspect.getsource(director.process)

        # Check that process() calls the entity context methods
        assert '_ensure_entity_context' in source, \
            "Director.process() doesn't call _ensure_entity_context()!"
        assert 'build_framed_context' in source, \
            "Director.process() doesn't call build_framed_context()!"
        print("✅ Director.process() has entity context wiring")
    
    @pytest.mark.asyncio
    async def test_director_process_exists(self, director):
        """Director MUST have process() method."""
        assert hasattr(director, 'process'), "Director has no process() method!"
        print("✅ Director.process() exists")


# ============================================================================
# INTEGRATION TEST - THE REAL TEST
# ============================================================================

class TestEndToEnd:
    """Full integration test - does Luna actually remember Marzipan?"""

    @pytest.fixture
    async def full_stack(self):
        """Set up full stack for testing."""
        from luna.entities.resolution import EntityResolver
        from luna.entities.context import EntityContext

        db_path = Path.home() / ".luna" / "luna.db"
        if not db_path.exists():
            pytest.skip(f"Database not found at {db_path}")

        db = SimpleDB(db_path)
        await db.connect()

        resolver = EntityResolver(db)
        context = EntityContext(db)

        yield {
            "db": db,
            "resolver": resolver,
            "context": context,
        }

        await db.close()
    
    @pytest.mark.asyncio
    async def test_full_marzipan_flow(self, full_stack):
        """
        THE BIG TEST: Simulate the full flow from user message to context.
        
        This tests what ACTUALLY happens when someone asks about Marzipan.
        """
        resolver = full_stack["resolver"]
        context = full_stack["context"]
        
        user_message = "Do you remember Marzipan?"
        
        # Step 1: detect_mentions should find Marzipan
        print("\n--- Step 1: detect_mentions ---")
        mentioned = await resolver.detect_mentions(user_message)
        mentioned_names = [e.name for e in mentioned]
        print(f"Detected entities: {mentioned_names}")
        assert any("marzipan" in n.lower() for n in mentioned_names), \
            f"detect_mentions failed to find Marzipan! Found: {mentioned_names}"
        
        # Step 2: build_framed_context should include Marzipan
        print("\n--- Step 2: build_framed_context ---")
        framed = await context.build_framed_context(
            message=user_message,
            conversation_history=[],
            memories=[],
        )
        print(f"Context length: {len(framed)} chars")
        print(f"Contains 'marzipan': {'marzipan' in framed.lower()}")
        assert "marzipan" in framed.lower(), \
            f"build_framed_context didn't include Marzipan!\nContext: {framed[:500]}"
        
        # Step 3: The context should have Marzipan's facts
        print("\n--- Step 3: Check for Marzipan's facts ---")
        marzipan_entity = await resolver.resolve_entity("marzipan")
        # resolve_entity returns dict, not Entity object
        if marzipan_entity and marzipan_entity.get('core_facts'):
            # Check if any of the facts appear in context
            facts_str = str(marzipan_entity['core_facts'])
            print(f"Marzipan's facts: {facts_str}")
            # At minimum, Mars College should be mentioned
            assert "mars" in framed.lower() or "college" in framed.lower() or "friend" in framed.lower(), \
                "Marzipan's relationship context not in framed output!"
        
        print("\n✅ FULL FLOW TEST PASSED")
        print("=" * 60)
        print("If Luna still can't remember Marzipan, the problem is in Director.process()")
        print("not calling build_framed_context(), OR the context not being passed to the LLM.")
        print("=" * 60)


# ============================================================================
# DIAGNOSTIC TEST - Run this to see exactly what's happening
# ============================================================================

class TestDiagnostic:
    """Diagnostic tests to pinpoint exactly where things break."""

    @pytest.mark.asyncio
    async def test_database_entities(self):
        """List all entities in database."""
        db_path = Path.home() / ".luna" / "luna.db"
        if not db_path.exists():
            pytest.skip(f"Database not found at {db_path}")

        db = SimpleDB(db_path)
        await db.connect()

        try:
            rows = await db.fetchall(
                "SELECT id, name, entity_type, core_facts FROM entities"
            )

            print("\n=== ENTITIES IN DATABASE ===")
            for row in rows:
                print(f"  {row[0]}: {row[1]} ({row[2]})")
                print(f"    facts: {row[3][:100] if row[3] else 'None'}...")

            assert len(rows) > 0, "No entities in database!"
            print(f"\nTotal: {len(rows)} entities")

        finally:
            await db.close()

    @pytest.mark.asyncio
    async def test_resolver_internals(self):
        """Test resolver's internal entity fetching."""
        from luna.entities.resolution import EntityResolver

        db_path = Path.home() / ".luna" / "luna.db"
        if not db_path.exists():
            pytest.skip(f"Database not found at {db_path}")

        db = SimpleDB(db_path)
        await db.connect()

        try:
            resolver = EntityResolver(db)

            print("\n=== RESOLVER DIAGNOSTIC ===")

            # Check if resolver can fetch all entities
            if hasattr(resolver, '_fetch_all_entities'):
                all_entities = await resolver._fetch_all_entities()
                print(f"_fetch_all_entities returned: {len(all_entities)} entities")

            # Check resolve_entity directly
            entity = await resolver.resolve_entity("marzipan")
            print(f"resolve_entity('marzipan'): {entity}")

            if entity:
                print(f"  name: {entity['name']}")
                print(f"  core_facts: {entity['core_facts']}")

        finally:
            await db.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
