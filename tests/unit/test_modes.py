"""
Tests for L1 (MemoryConfidence) and L2 (ResponseMode, IntentClassification) prompt control.

Covers:
- ResponseMode enum + MODE_CONTRACTS completeness
- IntentClassification dataclass
- MemoryConfidence level computation + directives
- Director._classify_intent() pattern matching
- PromptAssembler._build_mode_block() output
- PromptAssembler._build_constraints_block() output
"""

import pytest
from unittest.mock import Mock, AsyncMock

from luna.context.modes import ResponseMode, IntentClassification, MODE_CONTRACTS
from luna.context.assembler import MemoryConfidence, PromptAssembler, PromptRequest


# =============================================================================
# ResponseMode + MODE_CONTRACTS
# =============================================================================

class TestResponseMode:
    def test_all_modes_exist(self):
        expected = {"CHAT", "RECALL", "REFLECT", "ASSIST", "UNCERTAIN"}
        assert {m.value for m in ResponseMode} == expected

    def test_all_modes_have_contracts(self):
        for mode in ResponseMode:
            assert mode in MODE_CONTRACTS, f"Missing contract for {mode}"
            contract = MODE_CONTRACTS[mode]
            assert "description" in contract
            assert "rules" in contract
            assert len(contract["rules"]) > 0

    def test_recall_contract_has_anti_confabulation(self):
        rules = MODE_CONTRACTS[ResponseMode.RECALL]["rules"]
        rules_text = " ".join(rules).lower()
        assert "invent" in rules_text or "fabricate" in rules_text


# =============================================================================
# IntentClassification
# =============================================================================

class TestIntentClassification:
    def test_basic_creation(self):
        ic = IntentClassification(
            mode=ResponseMode.CHAT,
            confidence=0.7,
            signals=["default"],
        )
        assert ic.mode == ResponseMode.CHAT
        assert ic.confidence == 0.7
        assert ic.is_continuation is False

    def test_continuation(self):
        ic = IntentClassification(
            mode=ResponseMode.RECALL,
            confidence=0.9,
            signals=["continuation_detected"],
            is_continuation=True,
            previous_mode=ResponseMode.RECALL,
        )
        assert ic.is_continuation is True
        assert ic.previous_mode == ResponseMode.RECALL

    def test_to_dict(self):
        ic = IntentClassification(
            mode=ResponseMode.ASSIST,
            confidence=0.75,
            signals=["assist_keyword:help me"],
        )
        d = ic.to_dict()
        assert d["mode"] == "ASSIST"
        assert d["confidence"] == 0.75
        assert "assist_keyword:help me" in d["signals"]
        assert d["is_continuation"] is False


# =============================================================================
# MemoryConfidence
# =============================================================================

class TestMemoryConfidence:
    def test_none_level(self):
        mc = MemoryConfidence(0, 0, 0.0, "none", False, "test")
        assert mc.level == "NONE"
        assert "don't have a memory" in mc.directive

    def test_low_level(self):
        mc = MemoryConfidence(2, 0, 0.3, "drifting", False, "test")
        assert mc.level == "LOW"
        assert "thin memories" in mc.directive

    def test_medium_level_by_count(self):
        mc = MemoryConfidence(3, 1, 0.4, "fluid", False, "test")
        assert mc.level == "MEDIUM"

    def test_medium_level_by_similarity(self):
        mc = MemoryConfidence(1, 0, 0.6, "drifting", False, "test")
        assert mc.level == "MEDIUM"

    def test_high_level(self):
        mc = MemoryConfidence(5, 3, 0.8, "settled", True, "test")
        assert mc.level == "HIGH"
        assert "confidently" in mc.directive

    def test_high_requires_settled(self):
        # Many relevant nodes but not settled → MEDIUM, not HIGH
        mc = MemoryConfidence(5, 3, 0.8, "fluid", True, "test")
        assert mc.level == "MEDIUM"

    def test_to_dict(self):
        mc = MemoryConfidence(2, 1, 0.5, "fluid", True, "who is ahab")
        d = mc.to_dict()
        assert d["match_count"] == 2
        assert d["level"] == "MEDIUM"
        assert d["query"] == "who is ahab"


# =============================================================================
# Director._classify_intent()
# =============================================================================

def _make_director_for_intent():
    """Minimal mock director with _classify_intent wiring."""
    from luna.actors.director import DirectorActor
    director = DirectorActor.__new__(DirectorActor)
    director._last_classified_mode = ResponseMode.CHAT
    return director


class TestClassifyIntent:
    def test_default_is_chat(self):
        director = _make_director_for_intent()
        result = director._classify_intent("hey what's up", [])
        assert result.mode == ResponseMode.CHAT
        assert result.confidence == 0.7

    def test_recall_keyword_remember(self):
        director = _make_director_for_intent()
        result = director._classify_intent("do you remember our trip?", [])
        assert result.mode == ResponseMode.RECALL
        assert any("recall_keyword" in s for s in result.signals)

    def test_recall_keyword_who_is(self):
        director = _make_director_for_intent()
        result = director._classify_intent("who is ahab?", [])
        assert result.mode == ResponseMode.RECALL

    def test_recall_working_on(self):
        director = _make_director_for_intent()
        result = director._classify_intent("what have i been working on?", [])
        assert result.mode == ResponseMode.RECALL

    def test_reflect_how_are_you(self):
        director = _make_director_for_intent()
        result = director._classify_intent("how are you feeling today?", [])
        assert result.mode == ResponseMode.REFLECT

    def test_reflect_opinion(self):
        director = _make_director_for_intent()
        result = director._classify_intent("what do you think about that?", [])
        assert result.mode == ResponseMode.REFLECT

    def test_assist_help_me(self):
        director = _make_director_for_intent()
        result = director._classify_intent("help me write a function", [])
        assert result.mode == ResponseMode.ASSIST

    def test_assist_explain(self):
        director = _make_director_for_intent()
        result = director._classify_intent("explain how async works", [])
        assert result.mode == ResponseMode.ASSIST

    def test_continuation_keep_going(self):
        director = _make_director_for_intent()
        # Set previous mode to RECALL
        director._last_classified_mode = ResponseMode.RECALL
        result = director._classify_intent("keep going", [{"role": "assistant", "content": "..."}])
        assert result.mode == ResponseMode.RECALL
        assert result.is_continuation is True
        assert result.confidence == 0.9

    def test_continuation_short_affirmative(self):
        director = _make_director_for_intent()
        director._last_classified_mode = ResponseMode.REFLECT
        result = director._classify_intent("yeah", [{"role": "assistant", "content": "..."}])
        assert result.mode == ResponseMode.REFLECT
        assert result.is_continuation is True

    def test_continuation_requires_history(self):
        director = _make_director_for_intent()
        director._last_classified_mode = ResponseMode.RECALL
        # Empty history → no continuation, falls through to other patterns
        result = director._classify_intent("yeah", [])
        assert result.is_continuation is False

    def test_long_message_no_continuation(self):
        director = _make_director_for_intent()
        director._last_classified_mode = ResponseMode.RECALL
        # Long message → not a continuation even with trigger word
        long_msg = "yeah so I was thinking about something else entirely and wanted to discuss a new topic"
        result = director._classify_intent(long_msg, [{"role": "assistant", "content": "..."}])
        assert result.is_continuation is False

    def test_mode_persists_for_next_call(self):
        director = _make_director_for_intent()
        director._classify_intent("do you remember the project?", [])
        assert director._last_classified_mode == ResponseMode.RECALL

    def test_recall_priority_over_assist(self):
        # "tell me about our" matches both recall and assist ("tell me")
        # Recall should win because it's checked first
        director = _make_director_for_intent()
        result = director._classify_intent("tell me about our project", [])
        assert result.mode == ResponseMode.RECALL


# =============================================================================
# PromptAssembler._build_mode_block()
# =============================================================================

class TestBuildModeBlock:
    def _make_assembler(self):
        director = Mock()
        return PromptAssembler(director)

    def test_chat_mode_block(self):
        assembler = self._make_assembler()
        intent = IntentClassification(
            mode=ResponseMode.CHAT, confidence=0.7, signals=["default"]
        )
        block = assembler._build_mode_block(intent)
        assert "[RESPONSE_MODE: CHAT]" in block
        assert "do not override" in block
        assert "natural and conversational" in block.lower() or "Natural" in block

    def test_recall_mode_block(self):
        assembler = self._make_assembler()
        intent = IntentClassification(
            mode=ResponseMode.RECALL, confidence=0.85, signals=["recall_keyword:remember"]
        )
        block = assembler._build_mode_block(intent)
        assert "[RESPONSE_MODE: RECALL]" in block
        assert "ONLY memories" in block

    def test_continuation_note(self):
        assembler = self._make_assembler()
        intent = IntentClassification(
            mode=ResponseMode.RECALL, confidence=0.9,
            signals=["continuation_detected"], is_continuation=True,
        )
        block = assembler._build_mode_block(intent)
        assert "continuation" in block.lower()

    def test_no_continuation_note_when_false(self):
        assembler = self._make_assembler()
        intent = IntentClassification(
            mode=ResponseMode.CHAT, confidence=0.7, signals=["default"],
        )
        block = assembler._build_mode_block(intent)
        assert "continuation of the previous" not in block


# =============================================================================
# PromptAssembler._build_constraints_block()
# =============================================================================

class TestBuildConstraintsBlock:
    def _make_assembler(self):
        director = Mock()
        return PromptAssembler(director)

    def test_none_confidence(self):
        assembler = self._make_assembler()
        mc = MemoryConfidence(0, 0, 0.0, "none", False, "test")
        block = assembler._build_constraints_block(mc)
        assert "[CONFIDENCE: NONE]" in block
        assert "don't have a memory" in block

    def test_high_confidence(self):
        assembler = self._make_assembler()
        mc = MemoryConfidence(5, 3, 0.8, "settled", True, "who is ahab")
        block = assembler._build_constraints_block(mc)
        assert "[CONFIDENCE: HIGH]" in block
        assert "[ENTITY_MATCH: YES]" in block
        assert "confidently" in block

    def test_low_confidence_no_entity(self):
        assembler = self._make_assembler()
        mc = MemoryConfidence(1, 0, 0.2, "drifting", False, "test")
        block = assembler._build_constraints_block(mc)
        assert "[CONFIDENCE: LOW]" in block
        assert "[ENTITY_MATCH: NONE]" in block

    def test_block_header(self):
        assembler = self._make_assembler()
        mc = MemoryConfidence(0, 0, 0.0, "none", False, "test")
        block = assembler._build_constraints_block(mc)
        assert "## Response Constraints" in block
        assert "auto-generated" in block


# =============================================================================
# Integration: build() includes mode and constraints layers
# =============================================================================

def _mock_director_for_build():
    """Director mock suitable for full build() calls."""
    director = Mock()
    director._context_pipeline = None
    director._load_emergent_prompt = AsyncMock(return_value="You are Luna.")
    director._ensure_entity_context = AsyncMock(return_value=False)
    director._entity_context = None
    director._session_start_time = None
    director._engine = None
    director.engine = None
    director._generate_voice_block = Mock(return_value="")
    director._fetch_memory_context = AsyncMock(return_value="")
    director._last_memory_confidence = None
    director._perception_field = None
    return director


class TestBuildIntegration:
    @pytest.mark.asyncio
    async def test_build_with_intent_injects_mode(self):
        director = _mock_director_for_build()
        assembler = PromptAssembler(director)
        intent = IntentClassification(
            mode=ResponseMode.RECALL, confidence=0.85,
            signals=["recall_keyword:remember"],
        )
        result = await assembler.build(PromptRequest(
            message="do you remember?",
            intent=intent,
        ))
        assert "[RESPONSE_MODE: RECALL]" in result.system_prompt
        assert result.mode_injected is True
        assert result.response_mode == "RECALL"

    @pytest.mark.asyncio
    async def test_build_without_intent_skips_mode(self):
        director = _mock_director_for_build()
        assembler = PromptAssembler(director)
        result = await assembler.build(PromptRequest(message="hey"))
        assert "[RESPONSE_MODE:" not in result.system_prompt
        assert result.mode_injected is False

    @pytest.mark.asyncio
    async def test_build_always_has_constraints(self):
        """Even with no memory, constraints block should appear (CONFIDENCE: NONE)."""
        director = _mock_director_for_build()
        assembler = PromptAssembler(director)
        result = await assembler.build(PromptRequest(message="test"))
        assert "[CONFIDENCE: NONE]" in result.system_prompt
        assert result.constraints_injected is True
        assert result.memory_confidence_level == "NONE"

    @pytest.mark.asyncio
    async def test_build_with_memories_has_constraints(self):
        director = _mock_director_for_build()
        assembler = PromptAssembler(director)
        memories = [
            {"content": "Ahab is a builder", "lock_in_state": "settled", "lock_in": 0.9},
            {"content": "Luna was born in 2025", "lock_in_state": "fluid", "lock_in": 0.5},
        ]
        result = await assembler.build(PromptRequest(
            message="who is ahab",
            memories=memories,
            intent=IntentClassification(
                mode=ResponseMode.RECALL, confidence=0.85,
                signals=["recall_keyword:who is"],
            ),
        ))
        # Should have constraints block with non-NONE level
        assert result.constraints_injected is True
        assert result.memory_confidence_level in ("LOW", "MEDIUM", "HIGH")

    @pytest.mark.asyncio
    async def test_layer_ordering_mode_before_constraints_before_memory(self):
        """Verify: MODE → CONSTRAINTS → ... → MEMORY in that order."""
        director = _mock_director_for_build()
        assembler = PromptAssembler(director)
        memories = [{"content": "fact", "lock_in_state": "settled", "lock_in": 0.9}]
        result = await assembler.build(PromptRequest(
            message="do you remember?",
            memories=memories,
            intent=IntentClassification(
                mode=ResponseMode.RECALL, confidence=0.85,
                signals=["recall_keyword:remember"],
            ),
        ))
        prompt = result.system_prompt
        mode_pos = prompt.find("[RESPONSE_MODE:")
        constraints_pos = prompt.find("[CONFIDENCE:")
        memory_pos = prompt.find("## Relevant Memory Context")

        assert mode_pos < constraints_pos, "MODE must come before CONSTRAINTS"
        assert constraints_pos < memory_pos, "CONSTRAINTS must come before MEMORY"

    @pytest.mark.asyncio
    async def test_metadata_dict_includes_new_fields(self):
        director = _mock_director_for_build()
        assembler = PromptAssembler(director)
        result = await assembler.build(PromptRequest(
            message="test",
            intent=IntentClassification(
                mode=ResponseMode.CHAT, confidence=0.7, signals=["default"]
            ),
        ))
        d = result.to_dict()
        assert "mode_injected" in d
        assert "response_mode" in d
        assert "constraints_injected" in d
        assert "memory_confidence_level" in d
