"""
Tests for Layers 4-7: Task Ledger, Context Threading, Consciousness Wiring, Proactive Surfacing
=================================================================================================

Verifies the upper flow awareness stack that builds on Layers 2-3.
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
from luna.consciousness.state import ConsciousnessState


# ── Helpers ───────────────────────────────────────────────────

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


# ═════════════════════════════════════════════════════════════
# LAYER 4: Task Ledger
# ═════════════════════════════════════════════════════════════

class TestFilingResultNodeIDs:
    """Test FilingResult action/outcome node ID tracking."""

    def test_filing_result_has_action_fields(self):
        """FilingResult should have action_node_ids and outcome_node_ids."""
        fr = FilingResult()
        assert hasattr(fr, "action_node_ids")
        assert hasattr(fr, "outcome_node_ids")
        assert fr.action_node_ids == []
        assert fr.outcome_node_ids == []

    def test_filing_result_to_dict_includes_ids(self):
        """to_dict should include action/outcome node IDs."""
        fr = FilingResult(action_node_ids=["a1", "a2"], outcome_node_ids=["o1"])
        d = fr.to_dict()
        assert d["action_node_ids"] == ["a1", "a2"]
        assert d["outcome_node_ids"] == ["o1"]


class TestTaskLedger:
    """Test real node ID-based task tracking."""

    def setup_method(self):
        self.librarian = LibrarianActor()

    @pytest.mark.asyncio
    async def test_action_node_ids_tracked(self):
        """ACTION node IDs from filing_result should be in thread.open_tasks."""
        signal = _make_signal(ConversationMode.FLOW, "debug", ["luna"])
        await self.librarian._process_flow_signal(signal, _make_extraction(), FilingResult())

        # Now send a flow continue with action node IDs in the filing result
        filing = FilingResult(action_node_ids=["n_act_100", "n_act_101"])
        signal2 = _make_signal(ConversationMode.FLOW, "debug", ["luna"])
        await self.librarian._process_flow_signal(signal2, _make_extraction(), filing)

        assert "n_act_100" in self.librarian._active_thread.open_tasks
        assert "n_act_101" in self.librarian._active_thread.open_tasks

    @pytest.mark.asyncio
    async def test_duplicate_action_ids_not_added(self):
        """Same action node ID should not be added twice."""
        signal = _make_signal(ConversationMode.FLOW, "test", ["x"])
        await self.librarian._process_flow_signal(signal, _make_extraction(), FilingResult())

        filing1 = FilingResult(action_node_ids=["n_act_200"])
        signal2 = _make_signal(ConversationMode.FLOW, "test", ["x"])
        await self.librarian._process_flow_signal(signal2, _make_extraction(), filing1)

        filing2 = FilingResult(action_node_ids=["n_act_200"])
        signal3 = _make_signal(ConversationMode.FLOW, "test", ["x"])
        await self.librarian._process_flow_signal(signal3, _make_extraction(), filing2)

        assert self.librarian._active_thread.open_tasks.count("n_act_200") == 1

    @pytest.mark.asyncio
    async def test_empty_filing_result_no_tasks(self):
        """Empty FilingResult should not add any open tasks."""
        signal = _make_signal(ConversationMode.FLOW, "test", ["x"])
        await self.librarian._process_flow_signal(signal, _make_extraction(), FilingResult())

        signal2 = _make_signal(ConversationMode.FLOW, "test", ["x"])
        await self.librarian._process_flow_signal(signal2, _make_extraction(), FilingResult())

        assert len(self.librarian._active_thread.open_tasks) == 0


# ═════════════════════════════════════════════════════════════
# LAYER 5: Context Threading (public accessors)
# ═════════════════════════════════════════════════════════════

class TestLibrarianAccessors:
    """Test public accessors used by engine for prompt building."""

    def setup_method(self):
        self.librarian = LibrarianActor()

    def test_get_active_thread_none_initially(self):
        """No active thread at start."""
        assert self.librarian.get_active_thread() is None

    @pytest.mark.asyncio
    async def test_get_active_thread_after_create(self):
        """Active thread available after creation."""
        signal = _make_signal(ConversationMode.FLOW, "kozmo", ["kozmo"])
        await self.librarian._process_flow_signal(signal, _make_extraction(), FilingResult())
        thread = self.librarian.get_active_thread()
        assert thread is not None
        assert thread.topic == "kozmo"

    def test_get_parked_threads_empty(self):
        """No parked threads at start."""
        assert self.librarian.get_parked_threads() == []

    @pytest.mark.asyncio
    async def test_get_parked_threads_after_recal(self):
        """Parked threads available after recalibration."""
        # Create initial thread
        signal1 = _make_signal(ConversationMode.FLOW, "eden", ["eden"])
        await self.librarian._process_flow_signal(signal1, _make_extraction(), FilingResult())

        # Recalibrate — parks "eden", creates new thread
        signal2 = _make_signal(ConversationMode.RECALIBRATION, "kinoni", ["kinoni"])
        await self.librarian._process_flow_signal(signal2, _make_extraction(), FilingResult())

        parked = self.librarian.get_parked_threads()
        assert len(parked) >= 1
        assert any(t.topic == "eden" for t in parked)


# ═════════════════════════════════════════════════════════════
# LAYER 6: Consciousness Wiring
# ═════════════════════════════════════════════════════════════

class TestConsciousnessThreadFields:
    """Test thread fields on ConsciousnessState."""

    def test_default_thread_fields(self):
        """Thread fields default to None/0."""
        cs = ConsciousnessState()
        assert cs.active_thread_topic is None
        assert cs.active_thread_turn_count == 0
        assert cs.open_task_count == 0
        assert cs.parked_thread_count == 0

    def test_update_from_thread_active(self):
        """update_from_thread sets active thread info."""
        cs = ConsciousnessState()
        thread = Thread(id="t1", topic="debugging", entities=["eden"], turn_count=5,
                        open_tasks=["task1", "task2"])
        cs.update_from_thread(active_thread=thread, parked_threads=[])

        assert cs.active_thread_topic == "debugging"
        assert cs.active_thread_turn_count == 5
        assert cs.open_task_count == 2
        assert cs.parked_thread_count == 0

    def test_update_from_thread_parked(self):
        """update_from_thread counts parked threads and their tasks."""
        cs = ConsciousnessState()
        parked1 = Thread(id="p1", topic="old topic", status=ThreadStatus.PARKED,
                         open_tasks=["t1"])
        parked2 = Thread(id="p2", topic="another", status=ThreadStatus.PARKED,
                         open_tasks=["t2", "t3"])
        cs.update_from_thread(active_thread=None, parked_threads=[parked1, parked2])

        assert cs.active_thread_topic is None
        assert cs.parked_thread_count == 2
        assert cs.open_task_count == 3  # t1 + t2 + t3

    def test_update_clears_when_no_thread(self):
        """Passing no active thread clears the topic."""
        cs = ConsciousnessState()
        cs.active_thread_topic = "something"
        cs.active_thread_turn_count = 10
        cs.update_from_thread(active_thread=None, parked_threads=[])

        assert cs.active_thread_topic is None
        assert cs.active_thread_turn_count == 0


class TestConsciousnessThreadCoherence:
    """Test thread-aware coherence in tick()."""

    @pytest.mark.asyncio
    async def test_coherence_rises_with_depth(self):
        """Deep thread conversation → high coherence."""
        cs = ConsciousnessState()
        thread = Thread(id="t1", topic="deep focus", turn_count=10,
                        open_tasks=[])
        cs.update_from_thread(active_thread=thread)
        await cs.tick()

        # thread_depth = min(1.0, 10/10) = 1.0
        # coherence = 0.6 + (1.0 * 0.35) - (0 * 0.03) = 0.95
        assert cs.coherence == pytest.approx(0.95, abs=0.01)

    @pytest.mark.asyncio
    async def test_coherence_drops_with_tasks(self):
        """Open tasks create tension → lower coherence."""
        cs = ConsciousnessState()
        thread = Thread(id="t1", topic="busy", turn_count=5,
                        open_tasks=["a", "b", "c", "d", "e"])
        cs.update_from_thread(active_thread=thread)
        await cs.tick()

        # thread_depth = min(1.0, 5/10) = 0.5
        # coherence = 0.6 + (0.5 * 0.35) - (5 * 0.03) = 0.625
        assert cs.coherence < 0.7

    @pytest.mark.asyncio
    async def test_coherence_fallback_no_thread(self):
        """No active thread → attention-based coherence (original behavior)."""
        cs = ConsciousnessState()
        await cs.tick()
        # Default coherence without focus = 0.7
        assert cs.coherence == pytest.approx(0.7, abs=0.05)


class TestConsciousnessHints:
    """Test get_context_hint() with thread info."""

    def test_hint_includes_thread_topic(self):
        """Active thread topic appears in context hint."""
        cs = ConsciousnessState()
        cs.active_thread_topic = "kozmo pipeline"
        hint = cs.get_context_hint()
        assert "kozmo pipeline" in hint

    def test_hint_includes_open_tasks(self):
        """Open task count appears in context hint."""
        cs = ConsciousnessState()
        cs.open_task_count = 3
        hint = cs.get_context_hint()
        assert "3 unresolved item(s)" in hint

    def test_hint_no_thread_info_when_none(self):
        """No thread info in hint when no active thread."""
        cs = ConsciousnessState()
        hint = cs.get_context_hint()
        assert "Deeply engaged" not in hint
        assert "unresolved" not in hint


class TestConsciousnessSummary:
    """Test get_summary() includes thread fields."""

    def test_summary_has_thread_fields(self):
        """Summary includes thread state for frontend."""
        cs = ConsciousnessState()
        cs.active_thread_topic = "test"
        cs.active_thread_turn_count = 7
        cs.open_task_count = 2
        cs.parked_thread_count = 1

        summary = cs.get_summary()
        assert summary["active_thread"] == "test"
        assert summary["active_thread_turns"] == 7
        assert summary["open_tasks"] == 2
        assert summary["parked_threads"] == 1


class TestConsciousnessPersistence:
    """Test thread fields persist across save/load."""

    def test_thread_fields_roundtrip(self):
        """Thread fields survive to_dict → from_dict."""
        cs = ConsciousnessState()
        cs.active_thread_topic = "eden integration"
        cs.active_thread_turn_count = 4
        cs.open_task_count = 1
        cs.parked_thread_count = 2

        d = cs.to_dict()
        restored = ConsciousnessState.from_dict(d)

        assert restored.active_thread_topic == "eden integration"
        assert restored.active_thread_turn_count == 4
        assert restored.open_task_count == 1
        assert restored.parked_thread_count == 2


class TestLibrarianConsciousnessWiring:
    """Test Librarian notifies consciousness on thread ops."""

    def setup_method(self):
        self.librarian = LibrarianActor()
        self.consciousness = ConsciousnessState()
        self.librarian.set_consciousness(self.consciousness)

    @pytest.mark.asyncio
    async def test_create_thread_notifies_consciousness(self):
        """Creating a thread should update consciousness."""
        signal = _make_signal(ConversationMode.FLOW, "eden debug", ["eden"])
        await self.librarian._process_flow_signal(signal, _make_extraction(), FilingResult())

        assert self.consciousness.active_thread_topic == "eden debug"

    @pytest.mark.asyncio
    async def test_park_thread_updates_consciousness(self):
        """Parking a thread should clear active and increment parked."""
        # Create thread
        signal1 = _make_signal(ConversationMode.FLOW, "eden", ["eden"])
        await self.librarian._process_flow_signal(signal1, _make_extraction(), FilingResult())

        # Recalibrate → park "eden"
        signal2 = _make_signal(ConversationMode.RECALIBRATION, "kinoni", ["kinoni"])
        await self.librarian._process_flow_signal(signal2, _make_extraction(), FilingResult())

        # Active thread should now be "kinoni" (not "eden")
        assert self.consciousness.active_thread_topic == "kinoni"
        assert self.consciousness.parked_thread_count >= 1


# ═════════════════════════════════════════════════════════════
# LAYER 7: Proactive Surfacing (engine-level)
# ═════════════════════════════════════════════════════════════

class TestEngineThreadContext:
    """Test engine._get_thread_context() and _get_session_start_context()."""

    def _make_engine(self):
        """Create a minimal engine for prompt testing."""
        from unittest.mock import PropertyMock
        engine = MagicMock()
        engine.consciousness = ConsciousnessState()

        # Import the actual methods and bind them
        from luna.engine import LunaEngine
        engine._get_thread_context = LunaEngine._get_thread_context.__get__(engine)
        engine._get_session_start_context = LunaEngine._get_session_start_context.__get__(engine)
        return engine

    def test_thread_context_empty_no_librarian(self):
        """No thread context when librarian is None."""
        engine = self._make_engine()
        engine.librarian = None
        assert engine._get_thread_context() == ""

    def test_thread_context_with_active_thread(self):
        """Thread context includes active thread info."""
        engine = self._make_engine()
        lib = MagicMock()
        lib.get_active_thread.return_value = Thread(
            id="t1", topic="kozmo debugging", turn_count=5,
            open_tasks=["task1", "task2"],
        )
        lib.get_parked_threads.return_value = []
        engine.librarian = lib

        ctx = engine._get_thread_context()
        assert "CONVERSATIONAL THREADS" in ctx
        assert "kozmo debugging" in ctx
        assert "2 open task(s)" in ctx

    def test_thread_context_with_parked_threads(self):
        """Thread context includes parked threads."""
        engine = self._make_engine()
        lib = MagicMock()
        lib.get_active_thread.return_value = None
        lib.get_parked_threads.return_value = [
            Thread(
                id="p1", topic="eden integration",
                status=ThreadStatus.PARKED,
                parked_at=datetime.now() - timedelta(hours=2),
                open_tasks=["t1"],
            ),
        ]
        engine.librarian = lib

        ctx = engine._get_thread_context()
        assert "eden integration" in ctx
        assert "Parked" in ctx

    def test_session_start_context_empty_no_parked(self):
        """No session start context when no parked threads with open tasks."""
        engine = self._make_engine()
        lib = MagicMock()
        lib.get_parked_threads.return_value = []
        engine.librarian = lib

        ctx = engine._get_session_start_context()
        assert ctx == ""

    def test_session_start_context_with_actionable_threads(self):
        """Session start context shows parked threads with open tasks."""
        engine = self._make_engine()
        lib = MagicMock()
        lib.get_parked_threads.return_value = [
            Thread(
                id="p1", topic="eden fix",
                status=ThreadStatus.PARKED,
                parked_at=datetime.now() - timedelta(hours=1),
                open_tasks=["fix_eden"],
            ),
        ]
        engine.librarian = lib

        ctx = engine._get_session_start_context()
        assert "CONTINUING THREADS" in ctx
        assert "eden fix" in ctx
        assert "1 open task(s)" in ctx

    def test_session_start_context_skips_no_tasks(self):
        """Parked threads without open tasks are not surfaced."""
        engine = self._make_engine()
        lib = MagicMock()
        lib.get_parked_threads.return_value = [
            Thread(
                id="p1", topic="done topic",
                status=ThreadStatus.PARKED,
                parked_at=datetime.now() - timedelta(hours=1),
                open_tasks=[],  # No open tasks
            ),
        ]
        engine.librarian = lib

        ctx = engine._get_session_start_context()
        assert ctx == ""  # Nothing to surface
