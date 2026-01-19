"""
Tests for Luna Engine Actor Registration
=========================================

Tests that the engine properly registers and initializes all core actors:
- scribe (Benjamin Franklin)
- librarian (The Dude)
- matrix (Memory substrate)
- director (LLM management)

Note: Tests that require full engine boot with database may fail due to
known schema issues (see CLAUDE.md - 8 failing tests). These tests focus
on actor registration mechanics that don't require database initialization.
"""

import asyncio
import inspect
import pytest

from luna.engine import LunaEngine, EngineConfig
from luna.core.state import EngineState
from luna.actors.base import Actor, Message


class TestActorTypes:
    """Tests for actor class structure and types."""

    def test_scribe_actor_class(self):
        """Test ScribeActor class exists and has correct name."""
        from luna.actors.scribe import ScribeActor

        scribe = ScribeActor()
        assert scribe.name == "scribe"
        assert hasattr(scribe, "handle")
        assert hasattr(scribe, "mailbox")

    def test_librarian_actor_class(self):
        """Test LibrarianActor class exists and has correct name."""
        from luna.actors.librarian import LibrarianActor

        librarian = LibrarianActor()
        assert librarian.name == "librarian"
        assert hasattr(librarian, "handle")
        assert hasattr(librarian, "mailbox")

    def test_matrix_actor_class(self):
        """Test MatrixActor class exists and has correct name."""
        from luna.actors.matrix import MatrixActor

        matrix = MatrixActor()
        assert matrix.name == "matrix"
        assert hasattr(matrix, "handle")
        assert hasattr(matrix, "is_ready")

    def test_director_actor_class(self):
        """Test DirectorActor class exists and has correct name."""
        from luna.actors.director import DirectorActor

        director = DirectorActor(enable_local=False)
        assert director.name == "director"
        assert hasattr(director, "handle")


class TestActorRegistration:
    """Tests for core actor registration mechanics."""

    def test_register_actor_sets_engine_reference(self):
        """Test that registering an actor sets its engine reference."""
        engine = LunaEngine(EngineConfig())

        from luna.actors.scribe import ScribeActor
        scribe = ScribeActor()

        assert scribe.engine is None
        engine.register_actor(scribe)
        assert scribe.engine is engine

    def test_register_actor_adds_to_actors_dict(self):
        """Test that registering an actor adds it to engine.actors."""
        engine = LunaEngine(EngineConfig())

        from luna.actors.librarian import LibrarianActor
        librarian = LibrarianActor()

        assert "librarian" not in engine.actors
        engine.register_actor(librarian)
        assert "librarian" in engine.actors
        assert engine.actors["librarian"] is librarian

    def test_register_multiple_actors(self):
        """Test registering multiple actors."""
        engine = LunaEngine(EngineConfig())

        from luna.actors.scribe import ScribeActor
        from luna.actors.librarian import LibrarianActor
        from luna.actors.director import DirectorActor

        scribe = ScribeActor()
        librarian = LibrarianActor()
        director = DirectorActor(enable_local=False)

        engine.register_actor(scribe)
        engine.register_actor(librarian)
        engine.register_actor(director)

        assert len(engine.actors) == 3
        assert "scribe" in engine.actors
        assert "librarian" in engine.actors
        assert "director" in engine.actors

    def test_actor_names_match_registration_keys(self):
        """Test that actor names match their registration keys."""
        engine = LunaEngine(EngineConfig())

        from luna.actors.scribe import ScribeActor
        from luna.actors.librarian import LibrarianActor

        scribe = ScribeActor()
        librarian = LibrarianActor()

        engine.register_actor(scribe)
        engine.register_actor(librarian)

        for name, actor in engine.actors.items():
            assert actor.name == name, f"Actor name mismatch: {actor.name} vs {name}"

    def test_get_actor_returns_registered_actor(self):
        """Test get_actor returns the registered actor."""
        engine = LunaEngine(EngineConfig())

        from luna.actors.scribe import ScribeActor
        scribe = ScribeActor()
        engine.register_actor(scribe)

        result = engine.get_actor("scribe")
        assert result is scribe

    def test_get_actor_returns_none_for_unknown(self):
        """Test get_actor returns None for unregistered actors."""
        engine = LunaEngine(EngineConfig())

        result = engine.get_actor("nonexistent_actor")
        assert result is None

    def test_custom_actor_registration(self):
        """Test registering a custom actor."""
        engine = LunaEngine(EngineConfig())

        # Create custom actor
        class TestActor(Actor):
            def __init__(self):
                super().__init__("test_custom")
                self.handled_messages = []

            async def handle(self, msg: Message) -> None:
                self.handled_messages.append(msg)

        custom_actor = TestActor()
        engine.register_actor(custom_actor)

        assert "test_custom" in engine.actors
        assert engine.actors["test_custom"] is custom_actor
        assert custom_actor.engine is engine


class TestActorInstanceTypes:
    """Tests verifying actor instance types when registered."""

    def test_registered_actors_are_correct_types(self):
        """Test that registered actors are instances of correct classes."""
        engine = LunaEngine(EngineConfig())

        from luna.actors.scribe import ScribeActor
        from luna.actors.librarian import LibrarianActor
        from luna.actors.director import DirectorActor
        from luna.actors.matrix import MatrixActor

        scribe = ScribeActor()
        librarian = LibrarianActor()
        director = DirectorActor(enable_local=False)
        matrix = MatrixActor()

        engine.register_actor(scribe)
        engine.register_actor(librarian)
        engine.register_actor(director)
        engine.register_actor(matrix)

        assert isinstance(engine.actors["scribe"], ScribeActor)
        assert isinstance(engine.actors["librarian"], LibrarianActor)
        assert isinstance(engine.actors["director"], DirectorActor)
        assert isinstance(engine.actors["matrix"], MatrixActor)


class TestActorInteraction:
    """Tests for actor-to-actor communication via engine reference."""

    def test_scribe_can_access_librarian_via_engine(self):
        """Test that scribe can find librarian via its engine reference."""
        engine = LunaEngine(EngineConfig())

        from luna.actors.scribe import ScribeActor
        from luna.actors.librarian import LibrarianActor

        scribe = ScribeActor()
        librarian = LibrarianActor()

        engine.register_actor(scribe)
        engine.register_actor(librarian)

        # Scribe should be able to find librarian via engine
        assert scribe.engine is not None
        found_librarian = scribe.engine.get_actor("librarian")
        assert found_librarian is not None
        assert found_librarian is librarian
        assert isinstance(found_librarian, LibrarianActor)

    def test_librarian_can_access_matrix_via_engine(self):
        """Test that librarian can find matrix via its engine reference."""
        engine = LunaEngine(EngineConfig())

        from luna.actors.librarian import LibrarianActor
        from luna.actors.matrix import MatrixActor

        librarian = LibrarianActor()
        matrix = MatrixActor()

        engine.register_actor(librarian)
        engine.register_actor(matrix)

        # Librarian should be able to find matrix via engine
        assert librarian.engine is not None
        found_matrix = librarian.engine.get_actor("matrix")
        assert found_matrix is not None
        assert found_matrix is matrix
        assert isinstance(found_matrix, MatrixActor)

    def test_all_actors_can_find_each_other(self):
        """Test cross-actor discovery via engine reference."""
        engine = LunaEngine(EngineConfig())

        from luna.actors.scribe import ScribeActor
        from luna.actors.librarian import LibrarianActor
        from luna.actors.director import DirectorActor

        scribe = ScribeActor()
        librarian = LibrarianActor()
        director = DirectorActor(enable_local=False)

        engine.register_actor(scribe)
        engine.register_actor(librarian)
        engine.register_actor(director)

        # Each actor should be able to find the others
        assert scribe.engine.get_actor("librarian") is librarian
        assert scribe.engine.get_actor("director") is director

        assert librarian.engine.get_actor("scribe") is scribe
        assert librarian.engine.get_actor("director") is director

        assert director.engine.get_actor("scribe") is scribe
        assert director.engine.get_actor("librarian") is librarian


class TestActorMailbox:
    """Tests for actor mailbox functionality."""

    @pytest.mark.asyncio
    async def test_scribe_mailbox_accepts_messages(self):
        """Test that scribe's mailbox can receive messages."""
        from luna.actors.scribe import ScribeActor

        scribe = ScribeActor()

        # Should be able to put a message in the mailbox
        msg = Message(type="get_stats", payload={})
        await scribe.mailbox.put(msg)

        # Message should be retrievable
        received = await scribe.mailbox.get()
        assert received.type == "get_stats"

    @pytest.mark.asyncio
    async def test_librarian_mailbox_accepts_messages(self):
        """Test that librarian's mailbox can receive messages."""
        from luna.actors.librarian import LibrarianActor

        librarian = LibrarianActor()

        msg = Message(type="get_stats", payload={})
        await librarian.mailbox.put(msg)

        received = await librarian.mailbox.get()
        assert received.type == "get_stats"

    @pytest.mark.asyncio
    async def test_actor_handle_method_exists(self):
        """Test that actors have async handle methods."""
        from luna.actors.scribe import ScribeActor
        from luna.actors.librarian import LibrarianActor

        scribe = ScribeActor()
        librarian = LibrarianActor()

        # handle should be callable and async
        assert inspect.iscoroutinefunction(scribe.handle)
        assert inspect.iscoroutinefunction(librarian.handle)
