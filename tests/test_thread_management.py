"""
Tests for Layer 3: Thread Management (Librarian/Dude)
=====================================================

Verifies thread lifecycle, resume logic, edge creation, and project tagging.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from luna.extraction.types import (
    ConversationMode,
    FlowSignal,
    Thread,
    ThreadStatus,
    ExtractionOutput,
    ExtractedObject,
    ExtractionType,
    FilingResult,
)
from luna.actors.librarian import LibrarianActor
from luna.actors.base import Message


def _make_signal(
    mode: ConversationMode = ConversationMode.FLOW,
    topic: str = "test topic",
    entities: list[str] = None,
    continuity: float = 1.0,
) -> FlowSignal:
    return FlowSignal(
        mode=mode,
        current_topic=topic,
        topic_entities=entities or [],
        continuity_score=continuity,
        entity_overlap=continuity,
    )


def _make_extraction(entities: list[str] = None, obj_type: str = "FACT") -> ExtractionOutput:
    return ExtractionOutput(
        objects=[
            ExtractedObject(
                type=ExtractionType(obj_type),
                content="test content",
                confidence=0.9,
                entities=entities or [],
            )
        ] if entities else []
    )


class TestThreadTypes:
    """Test Thread dataclass serialization."""

    def test_thread_to_dict(self):
        thread = Thread(
            id="t1",
            topic="kozmo pipeline",
            entities=["Kozmo", "pipeline"],
            turn_count=5,
        )
        d = thread.to_dict()
        assert d["id"] == "t1"
        assert d["topic"] == "kozmo pipeline"
        assert d["status"] == "active"

    def test_thread_roundtrip(self):
        thread = Thread(
            id="t1",
            topic="kozmo pipeline",
            status=ThreadStatus.PARKED,
            entities=["Kozmo"],
            parked_at=datetime.now(),
            project_slug="luna-manifesto",
            resume_count=2,
        )
        d = thread.to_dict()
        restored = Thread.from_dict(d)
        assert restored.id == "t1"
        assert restored.status == ThreadStatus.PARKED
        assert restored.project_slug == "luna-manifesto"
        assert restored.resume_count == 2


class TestThreadLifecycle:
    """Test thread creation, parking, and resuming."""

    def setup_method(self):
        self.librarian = LibrarianActor()

    @pytest.mark.asyncio
    async def test_flow_creates_thread(self):
        """First FLOW signal should create a thread."""
        signal = _make_signal(
            mode=ConversationMode.FLOW,
            topic="kozmo pipeline",
            entities=["Kozmo", "pipeline"],
        )
        extraction = _make_extraction(["Kozmo", "pipeline"])
        result = FilingResult()

        await self.librarian._process_flow_signal(signal, extraction, result)

        assert self.librarian._active_thread is not None
        assert self.librarian._active_thread.topic == "kozmo pipeline"
        assert self.librarian._active_thread.status == ThreadStatus.ACTIVE
        assert self.librarian._threads_created == 1

    @pytest.mark.asyncio
    async def test_flow_accumulates(self):
        """Subsequent FLOW signals accumulate entities."""
        # Create thread
        signal1 = _make_signal(
            mode=ConversationMode.FLOW,
            topic="kozmo pipeline",
            entities=["Kozmo", "pipeline"],
        )
        await self.librarian._process_flow_signal(
            signal1, _make_extraction(["Kozmo", "pipeline"]), FilingResult()
        )

        # Accumulate
        signal2 = _make_signal(
            mode=ConversationMode.FLOW,
            topic="kozmo pipeline",
            entities=["Kozmo", "Eden"],
        )
        await self.librarian._process_flow_signal(
            signal2, _make_extraction(["Kozmo", "Eden"]), FilingResult()
        )

        assert self.librarian._active_thread.turn_count == 2
        assert "Eden" in self.librarian._active_thread.entities

    @pytest.mark.asyncio
    async def test_recalibration_parks_and_creates(self):
        """RECALIBRATION should park current thread and create new one."""
        # Create initial thread
        signal1 = _make_signal(
            mode=ConversationMode.FLOW,
            topic="kozmo pipeline",
            entities=["Kozmo", "pipeline"],
        )
        await self.librarian._process_flow_signal(
            signal1, _make_extraction(), FilingResult()
        )

        # Recalibrate
        signal2 = _make_signal(
            mode=ConversationMode.RECALIBRATION,
            topic="kinoni research",
            entities=["Kinoni", "Uganda"],
        )
        await self.librarian._process_flow_signal(
            signal2, _make_extraction(), FilingResult()
        )

        assert self.librarian._active_thread.topic == "kinoni research"
        assert self.librarian._threads_parked == 1

        # Check previous was parked
        parked = [
            t for t in self.librarian._thread_cache.values()
            if t.topic == "kozmo pipeline"
        ]
        assert len(parked) == 1
        assert parked[0].status == ThreadStatus.PARKED

    @pytest.mark.asyncio
    async def test_amend_stays_in_thread(self):
        """AMEND should not change the thread."""
        # Create thread
        signal1 = _make_signal(
            mode=ConversationMode.FLOW,
            topic="kozmo pipeline",
            entities=["Kozmo"],
        )
        await self.librarian._process_flow_signal(
            signal1, _make_extraction(), FilingResult()
        )

        # Amend
        signal2 = _make_signal(
            mode=ConversationMode.AMEND,
            topic="kozmo pipeline",
            entities=["Kozmo"],
        )
        signal2.correction_target = "Actually the asset indexing part"
        await self.librarian._process_flow_signal(
            signal2, _make_extraction(), FilingResult()
        )

        assert self.librarian._active_thread.topic == "kozmo pipeline"
        assert self.librarian._active_thread.turn_count == 2
        assert self.librarian._threads_parked == 0


class TestThreadResume:
    """Test thread resume by entity overlap."""

    def setup_method(self):
        self.librarian = LibrarianActor()

    @pytest.mark.asyncio
    async def test_resume_by_entity_overlap(self):
        """Parked thread with high entity overlap should be resumed."""
        # Seed a parked thread in cache
        parked = Thread(
            id="t1",
            topic="eden integration",
            status=ThreadStatus.PARKED,
            entities=["Eden", "agents", "API"],
            entity_node_ids=["n1", "n2", "n3"],
            turn_count=5,
            parked_at=datetime.now(),
        )
        self.librarian._thread_cache["t1"] = parked

        # Search with overlapping entities
        result = await self.librarian._find_resumable_thread(["Eden", "agents", "config"])
        assert result is not None
        assert result.id == "t1"

    @pytest.mark.asyncio
    async def test_no_resume_low_overlap(self):
        """Parked thread with low entity overlap should NOT be resumed."""
        parked = Thread(
            id="t1",
            topic="eden integration",
            status=ThreadStatus.PARKED,
            entities=["Eden", "agents", "API"],
            turn_count=5,
            parked_at=datetime.now(),
        )
        self.librarian._thread_cache["t1"] = parked

        result = await self.librarian._find_resumable_thread(["Kinoni", "solar", "Uganda"])
        assert result is None

    @pytest.mark.asyncio
    async def test_resume_increments_count(self):
        """Resumed thread should have incremented resume_count."""
        parked = Thread(
            id="t1",
            topic="kozmo pipeline",
            status=ThreadStatus.PARKED,
            entities=["Kozmo", "pipeline"],
            turn_count=5,
            parked_at=datetime.now(),
            resume_count=0,
        )
        self.librarian._thread_cache["t1"] = parked

        await self.librarian._resume_thread(parked)
        assert parked.status == ThreadStatus.ACTIVE
        assert parked.resume_count == 1
        assert parked.resumed_at is not None

    @pytest.mark.asyncio
    async def test_full_park_resume_cycle(self):
        """Complete park → recal → resume cycle."""
        # Create kozmo thread
        signal1 = _make_signal(ConversationMode.FLOW, "kozmo pipeline", ["Kozmo", "pipeline"])
        await self.librarian._process_flow_signal(signal1, _make_extraction(), FilingResult())

        # Accumulate a few turns
        for _ in range(3):
            signal = _make_signal(ConversationMode.FLOW, "kozmo pipeline", ["Kozmo", "pipeline"])
            await self.librarian._process_flow_signal(signal, _make_extraction(), FilingResult())

        # Switch to Kinoni
        signal2 = _make_signal(ConversationMode.RECALIBRATION, "kinoni hub", ["Kinoni", "Uganda"])
        await self.librarian._process_flow_signal(signal2, _make_extraction(), FilingResult())
        assert self.librarian._active_thread.topic == "kinoni hub"

        # Return to Kozmo (should resume, not create new)
        signal3 = _make_signal(ConversationMode.RECALIBRATION, "kozmo assets", ["Kozmo", "assets", "pipeline"])
        await self.librarian._process_flow_signal(signal3, _make_extraction(), FilingResult())

        assert self.librarian._active_thread.topic == "kozmo pipeline"
        assert self.librarian._active_thread.resume_count == 1
        assert self.librarian._threads_resumed == 1


class TestProjectContext:
    """Test Kozmo project context tagging."""

    def setup_method(self):
        self.librarian = LibrarianActor()

    @pytest.mark.asyncio
    async def test_set_project_context(self):
        msg = Message(type="set_project_context", payload={"slug": "luna-manifesto"})
        await self.librarian._handle_set_project_context(msg)
        assert self.librarian._active_project_slug == "luna-manifesto"

    @pytest.mark.asyncio
    async def test_thread_inherits_project(self):
        """Thread created during project context should inherit slug."""
        self.librarian._active_project_slug = "luna-manifesto"

        signal = _make_signal(ConversationMode.FLOW, "manifesto structure", ["manifesto"])
        await self.librarian._process_flow_signal(signal, _make_extraction(), FilingResult())

        assert self.librarian._active_thread.project_slug == "luna-manifesto"

    @pytest.mark.asyncio
    async def test_clear_project_parks_thread(self):
        """Clearing project context should auto-park active thread."""
        self.librarian._active_project_slug = "luna-manifesto"

        # Create thread
        signal = _make_signal(ConversationMode.FLOW, "test topic", ["test"])
        await self.librarian._process_flow_signal(signal, _make_extraction(), FilingResult())
        assert self.librarian._active_thread is not None

        # Clear project
        msg = Message(type="clear_project_context", payload={})
        await self.librarian._handle_clear_project_context(msg)

        assert self.librarian._active_thread is None
        assert self.librarian._active_project_slug is None
        assert self.librarian._threads_parked == 1


class TestThreadTags:
    """Test thread tag generation."""

    def setup_method(self):
        self.librarian = LibrarianActor()

    def test_active_thread_tags(self):
        thread = Thread(id="t1", topic="test", status=ThreadStatus.ACTIVE)
        tags = self.librarian._thread_tags(thread)
        assert "thread" in tags
        assert "status:active" in tags

    def test_parked_thread_tags(self):
        thread = Thread(
            id="t1",
            topic="test",
            status=ThreadStatus.PARKED,
            project_slug="luna-manifesto",
            open_tasks=["task1"],
        )
        tags = self.librarian._thread_tags(thread)
        assert "status:parked" in tags
        assert "project:luna-manifesto" in tags
        assert "has_open_tasks" in tags


class TestOpenTasks:
    """Test open task tracking in threads."""

    def setup_method(self):
        self.librarian = LibrarianActor()

    @pytest.mark.asyncio
    async def test_action_creates_open_task(self):
        """ACTION extraction should add to open_tasks via real node IDs (Layer 4)."""
        # Create thread
        signal = _make_signal(ConversationMode.FLOW, "test", ["test"])
        await self.librarian._process_flow_signal(signal, _make_extraction(), FilingResult())

        # Add ACTION — filing_result must include action_node_ids (Layer 4)
        ext = _make_extraction(["Eden", "integration"], obj_type="ACTION")
        signal2 = _make_signal(ConversationMode.FLOW, "test", ["test"])
        filing = FilingResult(action_node_ids=["n_act_001"])
        await self.librarian._process_flow_signal(signal2, ext, filing)

        assert len(self.librarian._active_thread.open_tasks) > 0
        assert "n_act_001" in self.librarian._active_thread.open_tasks
