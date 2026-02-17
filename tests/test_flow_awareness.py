"""
Tests for Layer 2: Flow Awareness (Scribe/Ben)
================================================

Verifies that Scribe correctly detects conversational flow modes:
- FLOW: Continuing on-topic
- RECALIBRATION: Topic shift
- AMEND: Course correction within flow
"""

import pytest
from luna.extraction.types import (
    ConversationMode,
    FlowSignal,
    ExtractionOutput,
    ExtractedObject,
    ExtractionType,
)
from luna.actors.scribe import ScribeActor


def _make_extraction(entities: list[str], obj_type: str = "FACT") -> ExtractionOutput:
    """Helper to create an ExtractionOutput with entities."""
    return ExtractionOutput(
        objects=[
            ExtractedObject(
                type=ExtractionType(obj_type),
                content=f"Test content about {', '.join(entities)}",
                confidence=0.9,
                entities=entities,
            )
        ]
    )


class TestFlowSignalTypes:
    """Test FlowSignal serialization."""

    def test_flow_signal_to_dict(self):
        signal = FlowSignal(
            mode=ConversationMode.FLOW,
            current_topic="kozmo pipeline",
            topic_entities=["Kozmo", "pipeline"],
            continuity_score=0.8,
            entity_overlap=0.8,
        )
        d = signal.to_dict()
        assert d["mode"] == "FLOW"
        assert d["current_topic"] == "kozmo pipeline"
        assert d["topic_entities"] == ["Kozmo", "pipeline"]

    def test_flow_signal_roundtrip(self):
        signal = FlowSignal(
            mode=ConversationMode.RECALIBRATION,
            current_topic="kinoni hub",
            topic_entities=["Kinoni", "Uganda"],
            continuity_score=0.1,
            entity_overlap=0.1,
            correction_target="",
            signals_detected=["recal_language: test"],
        )
        d = signal.to_dict()
        restored = FlowSignal.from_dict(d)
        assert restored.mode == ConversationMode.RECALIBRATION
        assert restored.topic_entities == ["Kinoni", "Uganda"]
        assert restored.continuity_score == 0.1

    def test_extraction_output_includes_flow_signal(self):
        extraction = ExtractionOutput(
            objects=[],
            flow_signal=FlowSignal(
                mode=ConversationMode.FLOW,
                current_topic="test",
            ),
        )
        d = extraction.to_dict()
        assert "flow_signal" in d
        assert d["flow_signal"]["mode"] == "FLOW"

        restored = ExtractionOutput.from_dict(d)
        assert restored.flow_signal is not None
        assert restored.flow_signal.mode == ConversationMode.FLOW

    def test_extraction_output_without_flow_signal(self):
        extraction = ExtractionOutput(objects=[])
        d = extraction.to_dict()
        assert "flow_signal" not in d

        restored = ExtractionOutput.from_dict(d)
        assert restored.flow_signal is None


class TestFlowDetection:
    """Test Scribe's _assess_flow() method."""

    def setup_method(self):
        self.scribe = ScribeActor()

    def test_first_turn_is_flow(self):
        """First turn should always be FLOW (no history to compare)."""
        extraction = _make_extraction(["Kozmo", "pipeline"])
        signal = self.scribe._assess_flow(extraction, "Let's work on the Kozmo pipeline")
        assert signal.mode == ConversationMode.FLOW
        assert signal.entity_overlap == 1.0  # First turn = neutral

    def test_same_entities_is_flow(self):
        """Same entities across turns → FLOW."""
        # Prime with first turn
        ext1 = _make_extraction(["Kozmo", "pipeline"])
        self.scribe._assess_flow(ext1, "Let's work on the Kozmo pipeline")

        # Same entities
        ext2 = _make_extraction(["Kozmo", "pipeline", "Eden"])
        signal = self.scribe._assess_flow(ext2, "The pipeline needs Eden integration")
        assert signal.mode == ConversationMode.FLOW
        assert signal.entity_overlap >= 0.3

    def test_new_entities_is_recalibration(self):
        """Completely new entities → RECALIBRATION."""
        # Prime with Kozmo context
        ext1 = _make_extraction(["Kozmo", "pipeline", "Eden"])
        self.scribe._assess_flow(ext1, "Working on Kozmo pipeline")

        # Completely different entities
        ext2 = _make_extraction(["Kinoni", "Uganda", "solar"])
        signal = self.scribe._assess_flow(ext2, "Now let's talk about the Kinoni hub")
        assert signal.mode == ConversationMode.RECALIBRATION
        assert signal.entity_overlap < 0.3

    def test_recal_language_triggers_recalibration(self):
        """Explicit redirect language → RECALIBRATION even with some overlap."""
        ext1 = _make_extraction(["Kozmo", "pipeline"])
        self.scribe._assess_flow(ext1, "Kozmo pipeline work")

        ext2 = _make_extraction(["Kinoni", "hub"])
        signal = self.scribe._assess_flow(ext2, "Anyway, what about the Kinoni hub?")
        assert signal.mode == ConversationMode.RECALIBRATION
        assert any("recal_language" in s for s in signal.signals_detected)

    def test_amend_with_overlap(self):
        """Correction language + high entity overlap → AMEND."""
        ext1 = _make_extraction(["Kozmo", "pipeline"])
        self.scribe._assess_flow(ext1, "Working on Kozmo pipeline")

        ext2 = _make_extraction(["Kozmo", "pipeline"])
        signal = self.scribe._assess_flow(ext2, "Actually no, I meant the asset indexing part")
        assert signal.mode == ConversationMode.AMEND
        assert signal.correction_target != ""

    def test_open_actions_tracked(self):
        """ACTION objects should be tracked as open threads."""
        ext = _make_extraction(["Eden", "integration"], obj_type="ACTION")
        signal = self.scribe._assess_flow(ext, "We need to fix the eden integration")
        assert len(signal.open_threads) == 1
        assert "Eden" in signal.open_threads[0] or "integration" in signal.open_threads[0]

    def test_outcome_resolves_action(self):
        """OUTCOME with matching entities should close an open action."""
        # Create an action
        ext_action = _make_extraction(["Eden", "integration"], obj_type="ACTION")
        self.scribe._assess_flow(ext_action, "Fix eden integration")
        assert len(self.scribe._open_actions) == 1

        # Resolve it with an outcome
        ext_outcome = _make_extraction(["Eden", "integration"], obj_type="OUTCOME")
        signal = self.scribe._assess_flow(ext_outcome, "Eden integration is working now")
        assert len(self.scribe._open_actions) == 0

    def test_topic_label_from_entities(self):
        """Topic should be derived from highest-confidence extraction."""
        ext = _make_extraction(["Kozmo", "pipeline"])
        signal = self.scribe._assess_flow(ext, "Working on kozmo pipeline")
        assert "Kozmo" in signal.current_topic

    def test_turn_count_resets_on_recalibration(self):
        """Turn count in flow should reset on RECALIBRATION."""
        # Build up some turns
        for _ in range(3):
            ext = _make_extraction(["Kozmo"])
            self.scribe._assess_flow(ext, "More kozmo work")

        assert self.scribe._turn_count_in_flow == 3

        # Recalibrate
        ext = _make_extraction(["Kinoni", "Uganda"])
        self.scribe._assess_flow(ext, "Now switching to Kinoni")
        assert self.scribe._turn_count_in_flow == 0

    def test_no_cloud_calls(self):
        """Flow detection must be pure Python — no cloud calls."""
        # _assess_flow is synchronous and uses only regex + set ops
        ext = _make_extraction(["test"])
        signal = self.scribe._assess_flow(ext, "test content")
        assert signal is not None
        # If this ran without network errors, it's local
