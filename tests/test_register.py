"""
Tests for Context Register — Luna's conversational posture layer.

Tests that register determination is:
- Pure Python, no LLM calls
- Deterministic given the same inputs
- Gracefully defaults to AMBIENT when signals are missing
- Produces valid prompt blocks
- Smoothly transitions via EMA
"""

import pytest
from dataclasses import dataclass, field
from typing import Optional
from luna.context.register import (
    ContextRegister,
    RegisterState,
    REGISTER_CONTRACTS,
    _GOVERNANCE_KEYWORDS,
    _DISTRESS_PATTERN,
)
from luna.context.perception import PerceptionField, Observation
from luna.context.modes import IntentClassification, ResponseMode


# ---------------------------------------------------------------------------
# Minimal stubs for Thread, FlowSignal, ConsciousnessState
# ---------------------------------------------------------------------------

@dataclass
class StubThread:
    topic: str = ""
    entities: list = field(default_factory=list)
    turn_count: int = 0
    open_tasks: list = field(default_factory=list)


@dataclass
class StubConsciousness:
    mood: str = "neutral"
    open_task_count: int = 0


@dataclass
class StubFlowSignal:
    mode: str = "FLOW"
    continuity_score: float = 1.0
    entity_overlap: float = 1.0


# ---------------------------------------------------------------------------
# Test: Default to AMBIENT
# ---------------------------------------------------------------------------

class TestDefaults:
    def test_default_register_is_ambient(self):
        state = RegisterState()
        assert state.active == ContextRegister.AMBIENT

    def test_update_with_no_signals_returns_ambient(self):
        state = RegisterState()
        result = state.update()
        assert result == ContextRegister.AMBIENT

    def test_confidence_zero_with_no_signals(self):
        state = RegisterState()
        state.update()
        # With no signals, weights are all zero — defaults to AMBIENT
        assert state.active == ContextRegister.AMBIENT

    def test_all_none_signals_returns_ambient(self):
        state = RegisterState()
        result = state.update(
            perception=None,
            intent=None,
            consciousness=None,
            active_thread=None,
            flow_signal=None,
        )
        assert result == ContextRegister.AMBIENT


# ---------------------------------------------------------------------------
# Test: Intent-driven register
# ---------------------------------------------------------------------------

class TestIntentSignals:
    def test_reflect_intent_biases_personal(self):
        state = RegisterState(transition_smoothing=1.0)  # No smoothing
        intent = IntentClassification(mode=ResponseMode.REFLECT, confidence=0.8)
        result = state.update(intent=intent)
        assert result == ContextRegister.PERSONAL_HOLDING

    def test_assist_intent_biases_project(self):
        state = RegisterState(transition_smoothing=1.0)
        intent = IntentClassification(mode=ResponseMode.ASSIST, confidence=0.8)
        result = state.update(intent=intent)
        assert result == ContextRegister.PROJECT_PARTNER

    def test_chat_intent_biases_ambient(self):
        state = RegisterState(transition_smoothing=1.0)
        intent = IntentClassification(mode=ResponseMode.CHAT, confidence=0.8)
        result = state.update(intent=intent)
        assert result == ContextRegister.AMBIENT


# ---------------------------------------------------------------------------
# Test: Consciousness signals
# ---------------------------------------------------------------------------

class TestConsciousnessSignals:
    def test_focused_mood_biases_project(self):
        state = RegisterState(transition_smoothing=1.0)
        consciousness = StubConsciousness(mood="focused")
        intent = IntentClassification(mode=ResponseMode.ASSIST, confidence=0.8)
        result = state.update(intent=intent, consciousness=consciousness)
        assert result == ContextRegister.PROJECT_PARTNER

    def test_high_task_count_biases_project(self):
        state = RegisterState(transition_smoothing=1.0)
        consciousness = StubConsciousness(open_task_count=5)
        intent = IntentClassification(mode=ResponseMode.ASSIST, confidence=0.8)
        result = state.update(intent=intent, consciousness=consciousness)
        assert result == ContextRegister.PROJECT_PARTNER


# ---------------------------------------------------------------------------
# Test: Thread / governance signals
# ---------------------------------------------------------------------------

class TestThreadSignals:
    def test_governance_topic_biases_governance(self):
        state = RegisterState(transition_smoothing=1.0)
        thread = StubThread(topic="governance protocol review")
        result = state.update(active_thread=thread)
        assert result == ContextRegister.GOVERNANCE_WITNESS

    def test_governance_entities_bias_governance(self):
        state = RegisterState(transition_smoothing=1.0)
        thread = StubThread(
            topic="community meeting",
            entities=["tribal council", "elder wisdom"]
        )
        result = state.update(active_thread=thread)
        assert result == ContextRegister.GOVERNANCE_WITNESS

    def test_non_governance_thread_does_not_trigger(self):
        state = RegisterState(transition_smoothing=1.0)
        thread = StubThread(topic="building a website")
        intent = IntentClassification(mode=ResponseMode.ASSIST, confidence=0.8)
        result = state.update(intent=intent, active_thread=thread)
        assert result != ContextRegister.GOVERNANCE_WITNESS


# ---------------------------------------------------------------------------
# Test: Distress detection
# ---------------------------------------------------------------------------

class TestDistressDetection:
    def test_distress_language_triggers_crisis(self):
        state = RegisterState(transition_smoothing=1.0)
        pf = PerceptionField()
        pf._user_messages = ["i can't breathe, everything is falling apart"]
        result = state.update(perception=pf)
        assert result == ContextRegister.CRISIS_SUPPORT

    def test_no_distress_no_crisis(self):
        state = RegisterState(transition_smoothing=1.0)
        pf = PerceptionField()
        pf._user_messages = ["hey what's up, just checking in"]
        result = state.update(perception=pf)
        assert result != ContextRegister.CRISIS_SUPPORT

    def test_distress_pattern_matches(self):
        assert _DISTRESS_PATTERN.search("I'm scared and overwhelmed")
        assert _DISTRESS_PATTERN.search("i can't do this anymore")
        assert not _DISTRESS_PATTERN.search("the weather is nice today")


# ---------------------------------------------------------------------------
# Test: Perception signals
# ---------------------------------------------------------------------------

class TestPerceptionSignals:
    def test_terse_observations_bias_ambient(self):
        state = RegisterState(transition_smoothing=1.0)
        pf = PerceptionField()
        pf._user_messages = ["ok"]
        pf.observations = [
            Observation(
                signal="terse_response",
                value="2 terse acknowledgments",
                trigger="after explanation",
                turn=3,
                confidence=0.7,
            )
        ]
        result = state.update(perception=pf)
        assert result == ContextRegister.AMBIENT

    def test_energy_markers_bias_personal(self):
        state = RegisterState(transition_smoothing=1.0)
        pf = PerceptionField()
        pf._user_messages = ["wow that's amazing!!!"]
        pf.observations = [
            Observation(
                signal="energy_markers",
                value="Energy markers appeared — exclamation marks, emoji, or emphasis",
                trigger="after response",
                turn=5,
                confidence=0.6,
            )
        ]
        # REFLECT intent combined with energy should push personal_holding
        intent = IntentClassification(mode=ResponseMode.REFLECT, confidence=0.8)
        result = state.update(perception=pf, intent=intent)
        assert result == ContextRegister.PERSONAL_HOLDING


# ---------------------------------------------------------------------------
# Test: EMA smoothing
# ---------------------------------------------------------------------------

class TestEMASmoothing:
    def test_smoothing_resists_instant_transition(self):
        state = RegisterState(transition_smoothing=0.3)

        # First: push strongly toward PROJECT_PARTNER
        intent_assist = IntentClassification(mode=ResponseMode.ASSIST, confidence=0.8)
        consciousness = StubConsciousness(mood="focused")
        for _ in range(5):
            state.update(intent=intent_assist, consciousness=consciousness)
        assert state.active == ContextRegister.PROJECT_PARTNER

        # Single REFLECT intent shouldn't instantly flip to PERSONAL_HOLDING
        intent_reflect = IntentClassification(mode=ResponseMode.REFLECT, confidence=0.8)
        result = state.update(intent=intent_reflect)
        # With EMA=0.3, one turn won't override 5 turns of project weight
        assert result == ContextRegister.PROJECT_PARTNER

    def test_full_smoothing_transitions_immediately(self):
        state = RegisterState(transition_smoothing=1.0)  # No smoothing
        intent = IntentClassification(mode=ResponseMode.REFLECT, confidence=0.8)
        result = state.update(intent=intent)
        assert result == ContextRegister.PERSONAL_HOLDING


# ---------------------------------------------------------------------------
# Test: Prompt block generation
# ---------------------------------------------------------------------------

class TestPromptBlock:
    def test_prompt_block_contains_register_name(self):
        state = RegisterState()
        state.active = ContextRegister.PROJECT_PARTNER
        state.confidence = 0.82
        block = state.to_prompt_block()
        assert "REGISTER: project_partner" in block
        assert "0.82" in block

    def test_prompt_block_contains_contract_fields(self):
        state = RegisterState()
        state.active = ContextRegister.PERSONAL_HOLDING
        state.confidence = 0.71
        block = state.to_prompt_block()
        assert "warm" in block.lower()
        assert "relationship" in block.lower()

    def test_prompt_block_for_every_register(self):
        state = RegisterState()
        for register in ContextRegister:
            state.active = register
            state.confidence = 0.5
            block = state.to_prompt_block()
            assert f"REGISTER: {register.value}" in block
            contract = REGISTER_CONTRACTS[register]
            assert contract["tone"] in block


# ---------------------------------------------------------------------------
# Test: Serialization
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_roundtrip(self):
        state = RegisterState()
        intent = IntentClassification(mode=ResponseMode.ASSIST, confidence=0.8)
        state.update(intent=intent)

        d = state.to_dict()
        assert "active" in d
        assert "confidence" in d
        assert "weights" in d
        assert "fired_signals" in d
        assert isinstance(d["weights"], dict)


# ---------------------------------------------------------------------------
# Test: Reset
# ---------------------------------------------------------------------------

class TestReset:
    def test_reset_clears_state(self):
        state = RegisterState(transition_smoothing=1.0)
        intent = IntentClassification(mode=ResponseMode.ASSIST, confidence=0.8)
        state.update(intent=intent)
        assert state.active == ContextRegister.PROJECT_PARTNER

        state.reset()
        assert state.active == ContextRegister.AMBIENT
        assert state.confidence == 0.0
        assert all(w == 0.0 for w in state.weights.values())


# ---------------------------------------------------------------------------
# Test: Register contracts completeness
# ---------------------------------------------------------------------------

class TestContracts:
    def test_all_registers_have_contracts(self):
        for register in ContextRegister:
            assert register in REGISTER_CONTRACTS
            contract = REGISTER_CONTRACTS[register]
            assert "tone" in contract
            assert "priority" in contract
            assert "avoid" in contract
            assert "length" in contract

    def test_governance_keywords_are_nonempty(self):
        assert len(_GOVERNANCE_KEYWORDS) > 5
