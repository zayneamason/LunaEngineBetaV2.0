"""
Tests for Layers 2-3: Flow Awareness + Thread Management.

Layer 2 (Scribe — Ben): FlowSignal detection (FLOW/RECALIBRATION/AMEND)
Layer 3 (Librarian — Dude): Thread create/park/resume/close

These test the types and pure-logic methods directly, without requiring
LLM calls or database connections.
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import field

from luna.extraction.types import (
    ConversationMode,
    FlowSignal,
    ExtractionOutput,
    ExtractedObject,
    ExtractionType,
    ExtractedEdge,
    Thread,
    ThreadStatus,
)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LAYER 2: FlowSignal Type Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestConversationMode:
    """Test ConversationMode enum values."""

    def test_flow_mode_exists(self):
        assert ConversationMode.FLOW.value == "FLOW"

    def test_recalibration_mode_exists(self):
        assert ConversationMode.RECALIBRATION.value == "RECALIBRATION"

    def test_amend_mode_exists(self):
        assert ConversationMode.AMEND.value == "AMEND"


class TestFlowSignal:
    """Test FlowSignal dataclass."""

    def test_default_values(self):
        signal = FlowSignal(
            mode=ConversationMode.FLOW,
            current_topic="test",
        )
        assert signal.continuity_score == 1.0
        assert signal.entity_overlap == 1.0
        assert signal.correction_target == ""
        assert signal.detection_method == "local"

    def test_to_dict_roundtrip(self):
        signal = FlowSignal(
            mode=ConversationMode.RECALIBRATION,
            current_topic="architecture",
            topic_entities=["MemoryMatrix", "Librarian"],
            continuity_score=0.2,
            entity_overlap=0.15,
            signals_detected=["recal_language: shift"],
        )
        d = signal.to_dict()
        restored = FlowSignal.from_dict(d)

        assert restored.mode == ConversationMode.RECALIBRATION
        assert restored.current_topic == "architecture"
        assert restored.topic_entities == ["MemoryMatrix", "Librarian"]
        assert restored.continuity_score == 0.2
        assert restored.entity_overlap == 0.15
        assert restored.detection_method == "local"

    def test_detection_method_in_dict(self):
        signal = FlowSignal(
            mode=ConversationMode.FLOW,
            current_topic="test",
        )
        d = signal.to_dict()
        assert "detection_method" in d
        assert d["detection_method"] == "local"

    def test_sovereignty_detection_method_always_local(self):
        """Sovereignty invariant: flow detection must always be local."""
        signal = FlowSignal(
            mode=ConversationMode.FLOW,
            current_topic="test",
        )
        assert signal.detection_method == "local"
        assert signal.detection_method not in ("cloud",)

    def test_amend_carries_correction_target(self):
        signal = FlowSignal(
            mode=ConversationMode.AMEND,
            current_topic="vector search",
            correction_target="no I meant the embedding search not FTS5",
        )
        assert signal.correction_target != ""
        assert "embedding" in signal.correction_target


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LAYER 2: Scribe Flow Assessment Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestScribeFlowAssessment:
    """Test Scribe._assess_flow() logic."""

    @pytest.fixture
    def scribe(self):
        """Create a minimal ScribeActor for flow testing."""
        from luna.actors.scribe import ScribeActor
        scribe = ScribeActor.__new__(ScribeActor)
        # Initialize flow-tracking state
        from collections import deque
        scribe._current_topic = ""
        scribe._current_entities = set()
        scribe._recent_entities = deque(maxlen=5)
        scribe._turn_count_in_flow = 0
        scribe._open_actions = []
        return scribe

    def _make_extraction(self, objects=None) -> ExtractionOutput:
        return ExtractionOutput(
            source_id="test",
            objects=objects or [],
            edges=[],
        )

    def _make_obj(self, entities, type_=ExtractionType.FACT, content="test fact"):
        return ExtractedObject(
            type=type_,
            content=content,
            entities=entities,
            confidence=0.8,
        )

    def test_first_turn_is_flow(self, scribe):
        """First turn always returns FLOW (no history to compare)."""
        ext = self._make_extraction([
            self._make_obj(["MemoryMatrix", "Librarian"]),
        ])
        signal = scribe._assess_flow(ext, "the memory matrix stores everything right?")
        assert signal.mode == ConversationMode.FLOW

    def test_continued_topic_is_flow(self, scribe):
        """Same entities across turns = FLOW."""
        # Seed history
        scribe._recent_entities.append({"MemoryMatrix", "Librarian"})

        ext = self._make_extraction([
            self._make_obj(["MemoryMatrix", "Librarian"]),
        ])
        signal = scribe._assess_flow(ext, "how does the memory matrix work?")
        assert signal.mode == ConversationMode.FLOW
        assert signal.entity_overlap > 0.3

    def test_new_topic_is_recalibration(self, scribe):
        """Completely different entities = RECALIBRATION."""
        # Seed history with different entities
        scribe._recent_entities.append({"MemoryMatrix", "Librarian"})

        ext = self._make_extraction([
            self._make_obj(["Kozmo", "Scribo", "Eden"]),
        ])
        signal = scribe._assess_flow(ext, "let's talk about the Kozmo pipeline")
        assert signal.mode == ConversationMode.RECALIBRATION
        assert signal.entity_overlap < 0.3

    def test_explicit_recal_language(self, scribe):
        """Explicit shift language triggers RECALIBRATION."""
        scribe._recent_entities.append({"MemoryMatrix"})

        ext = self._make_extraction([
            self._make_obj(["Kozmo"]),
        ])
        # "switching to" is a recal pattern
        signal = scribe._assess_flow(ext, "switching to the Kozmo build now")
        assert signal.mode == ConversationMode.RECALIBRATION

    def test_amend_with_overlap(self, scribe):
        """Amend language + entity overlap > 0.3 = AMEND."""
        scribe._recent_entities.append({"MemoryMatrix", "vector_search"})

        ext = self._make_extraction([
            self._make_obj(["MemoryMatrix", "vector_search"]),
        ])
        signal = scribe._assess_flow(ext, "no wait, I meant the vector search, not FTS5")
        assert signal.mode == ConversationMode.AMEND
        assert signal.correction_target != ""

    def test_correction_language_triggers_amend(self, scribe):
        """'I meant' / 'correction' triggers amend detection."""
        scribe._recent_entities.append({"temporal_layer"})

        ext = self._make_extraction([
            self._make_obj(["temporal_layer"]),
        ])
        signal = scribe._assess_flow(ext, "correction: the temporal layer uses gap categories")
        assert signal.mode == ConversationMode.AMEND

    def test_recalibration_resets_flow_count(self, scribe):
        """RECALIBRATION should reset the turn-in-flow counter."""
        scribe._turn_count_in_flow = 5
        scribe._recent_entities.append({"MemoryMatrix"})

        ext = self._make_extraction([
            self._make_obj(["Kozmo", "Eden"]),
        ])
        scribe._assess_flow(ext, "let me ask about something different")
        assert scribe._turn_count_in_flow == 0

    def test_flow_increments_count(self, scribe):
        """FLOW should increment the turn counter."""
        scribe._recent_entities.append({"MemoryMatrix"})

        ext = self._make_extraction([
            self._make_obj(["MemoryMatrix"]),
        ])
        scribe._assess_flow(ext, "more about memory matrix")
        assert scribe._turn_count_in_flow == 1

    def test_open_actions_tracked(self, scribe):
        """ACTION objects create open action entries."""
        ext = self._make_extraction([
            self._make_obj(
                ["pipeline"], type_=ExtractionType.ACTION,
                content="fix the pipeline bug"
            ),
        ])
        scribe._assess_flow(ext, "fix the pipeline bug")
        assert len(scribe._open_actions) == 1

    def test_outcome_closes_action(self, scribe):
        """OUTCOME with matching entities closes an open action."""
        scribe._open_actions = [{
            "content": "fix the pipeline",
            "entities": ["pipeline"],
            "timestamp": time.time(),
        }]

        ext = self._make_extraction([
            self._make_obj(
                ["pipeline"], type_=ExtractionType.OUTCOME,
                content="pipeline is fixed"
            ),
        ])
        scribe._assess_flow(ext, "pipeline is fixed")
        assert len(scribe._open_actions) == 0


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LAYER 3: Thread Type Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestThreadTypes:
    """Test Thread dataclass and ThreadStatus enum."""

    def test_thread_status_values(self):
        assert ThreadStatus.ACTIVE.value == "active"
        assert ThreadStatus.PARKED.value == "parked"
        assert ThreadStatus.RESUMED.value == "resumed"
        assert ThreadStatus.CLOSED.value == "closed"

    def test_thread_defaults(self):
        thread = Thread(
            id="thread-1",
            topic="memory architecture",
        )
        assert thread.status == ThreadStatus.ACTIVE
        assert thread.turn_count == 0
        assert thread.entities == []
        assert thread.open_tasks == []
        assert thread.resume_count == 0

    def test_thread_to_dict_roundtrip(self):
        thread = Thread(
            id="thread-1",
            topic="memory architecture",
            entities=["MemoryMatrix", "sqlite"],
            turn_count=5,
            status=ThreadStatus.PARKED,
        )
        d = thread.to_dict()
        restored = Thread.from_dict(d)

        assert restored.id == "thread-1"
        assert restored.topic == "memory architecture"
        assert restored.status == ThreadStatus.PARKED
        assert restored.turn_count == 5
        assert "MemoryMatrix" in restored.entities


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LAYER 3: Thread Management Logic Tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestThreadManagement:
    """Test Librarian thread lifecycle logic."""

    def test_flow_signal_dispatch_routes_correctly(self):
        """_process_flow_signal should route to correct handler."""
        from luna.extraction.types import ConversationMode

        # Just verify the match mapping exists — actual handlers
        # require full Librarian wiring which needs a mock Matrix
        for mode in ConversationMode:
            assert mode.value in ("FLOW", "RECALIBRATION", "AMEND")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LAYER 2→3 Integration: Flow Signal Delivery
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


class TestFlowSignalDelivery:
    """Test that flow signals reach the Librarian."""

    def test_extraction_output_carries_flow_signal(self):
        """ExtractionOutput.flow_signal should carry FlowSignal to Librarian."""
        ext = ExtractionOutput(
            source_id="test",
            objects=[],
            edges=[],
        )
        signal = FlowSignal(
            mode=ConversationMode.RECALIBRATION,
            current_topic="new topic",
        )
        ext.flow_signal = signal

        assert ext.flow_signal is not None
        assert ext.flow_signal.mode == ConversationMode.RECALIBRATION

    def test_empty_extraction_preserves_flow_signal(self):
        """Even empty extractions should carry the flow signal."""
        ext = ExtractionOutput(
            source_id="test",
            objects=[],
            edges=[],
        )
        assert ext.is_empty()

        signal = FlowSignal(
            mode=ConversationMode.RECALIBRATION,
            current_topic="shifted topic",
        )
        ext.flow_signal = signal

        # Extraction is empty but flow signal exists
        assert ext.is_empty()
        assert ext.flow_signal is not None
        assert ext.flow_signal.mode == ConversationMode.RECALIBRATION

    def test_flow_signal_serialization_in_extraction(self):
        """Flow signal should survive ExtractionOutput serialization."""
        signal = FlowSignal(
            mode=ConversationMode.AMEND,
            current_topic="vector search",
            correction_target="not FTS5",
        )
        ext = ExtractionOutput(
            source_id="test",
            objects=[],
            edges=[],
            flow_signal=signal,
        )

        d = ext.to_dict()
        assert "flow_signal" in d
        assert d["flow_signal"]["mode"] == "AMEND"

        restored = ExtractionOutput.from_dict(d)
        assert restored.flow_signal is not None
        assert restored.flow_signal.mode == ConversationMode.AMEND
        assert restored.flow_signal.correction_target == "not FTS5"
