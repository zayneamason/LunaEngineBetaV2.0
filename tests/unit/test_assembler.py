"""
Tests for PromptAssembler.

Tests identity chain, memory chain, assembly order, voice injection, metadata.
"""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import Mock, AsyncMock, MagicMock, patch

from luna.context.assembler import PromptAssembler, PromptRequest, PromptResult


# =============================================================================
# MOCK DIRECTOR HELPERS
# =============================================================================

def _mock_director_no_subsystems():
    """Director where all subsystems fail — forces FALLBACK_PERSONALITY."""
    director = Mock()
    director._context_pipeline = None
    director._load_emergent_prompt = AsyncMock(return_value=None)
    director._ensure_entity_context = AsyncMock(return_value=False)
    director._entity_context = None
    director._session_start_time = None
    director._engine = None
    director.engine = None
    director._generate_voice_block = Mock(return_value="")
    director._fetch_memory_context = AsyncMock(return_value="")
    return director


def _mock_director_with_emergent():
    """Director with emergent prompt available."""
    director = _mock_director_no_subsystems()
    director._load_emergent_prompt = AsyncMock(
        return_value="## Luna's DNA\nYou are Luna, warm and curious.\n\n## Experience\nYou know Ahab well."
    )
    return director


def _mock_director_with_pipeline():
    """Director with ContextPipeline personality available."""
    director = _mock_director_no_subsystems()
    pipeline = Mock()
    pipeline._base_personality = "Luna full personality from pipeline — warm, witty, sovereign."
    director._context_pipeline = pipeline
    return director


def _mock_director_with_voice():
    """Director with voice system returning a block."""
    director = _mock_director_with_emergent()
    director._generate_voice_block = Mock(
        return_value="\n\n<luna_voice>\nkill_list: certainly, of course\n</luna_voice>"
    )
    return director


def _mock_director_with_memory_fetch():
    """Director with auto-fetch returning memory context."""
    director = _mock_director_with_emergent()
    director._fetch_memory_context = AsyncMock(
        return_value="Ahab likes dark roast coffee. Luna remembers their first conversation about consciousness."
    )
    return director


def _mock_director_with_engine():
    """Director with engine providing expression + consciousness."""
    director = _mock_director_with_emergent()
    engine = Mock()
    engine._get_expression_directive = Mock(
        return_value="## Emotional Expression\n\nExpress emotions through gestures naturally."
    )
    consciousness = Mock()
    consciousness.get_context_hint = Mock(return_value="Luna is feeling curious and engaged.")
    engine.consciousness = consciousness
    engine.get_actor = Mock(return_value=None)
    director._engine = engine
    director.engine = engine
    return director


def _mock_director_full_stack():
    """Director with all layers: emergent + engine + voice + memory."""
    director = _mock_director_with_engine()
    director._generate_voice_block = Mock(
        return_value="\n\n<luna_voice>\nkill_list: certainly, of course\n</luna_voice>"
    )
    director._fetch_memory_context = AsyncMock(
        return_value="Ahab enjoys building consciousness engines."
    )
    return director


# =============================================================================
# IDENTITY CHAIN
# =============================================================================

class TestIdentityChain:

    @pytest.mark.asyncio
    async def test_fallback_when_all_fail(self):
        assembler = PromptAssembler(_mock_director_no_subsystems())
        result = await assembler.build(PromptRequest(message="hello"))
        assert "Luna" in result.system_prompt
        assert result.identity_source == "fallback"

    @pytest.mark.asyncio
    async def test_emergent_takes_priority_over_fallback(self):
        assembler = PromptAssembler(_mock_director_with_emergent())
        result = await assembler.build(PromptRequest(message="hello"))
        assert "DNA" in result.system_prompt
        assert result.identity_source == "emergent"

    @pytest.mark.asyncio
    async def test_pipeline_takes_priority_over_emergent(self):
        assembler = PromptAssembler(_mock_director_with_pipeline())
        result = await assembler.build(PromptRequest(message="hello"))
        assert "pipeline" in result.system_prompt
        assert result.identity_source == "pipeline"

    @pytest.mark.asyncio
    async def test_pipeline_empty_falls_through(self):
        """Pipeline with empty personality falls through to emergent."""
        director = _mock_director_with_emergent()
        pipeline = Mock()
        pipeline._base_personality = ""
        director._context_pipeline = pipeline
        assembler = PromptAssembler(director)
        result = await assembler.build(PromptRequest(message="hello"))
        assert result.identity_source == "emergent"


# =============================================================================
# MEMORY CHAIN
# =============================================================================

class TestMemoryChain:

    @pytest.mark.asyncio
    async def test_framed_context_priority(self):
        assembler = PromptAssembler(_mock_director_with_emergent())
        result = await assembler.build(PromptRequest(
            message="test",
            framed_context="framed memory content about Ahab",
            memories=[{"content": "node memory"}],
        ))
        assert "framed memory content" in result.system_prompt
        assert result.memory_source == "framed"

    @pytest.mark.asyncio
    async def test_memories_list_formatted(self):
        assembler = PromptAssembler(_mock_director_with_emergent())
        result = await assembler.build(PromptRequest(
            message="test",
            memories=[
                {"content": "Ahab likes coffee"},
                {"content": "Luna was created in 2025"},
            ],
        ))
        assert "Ahab likes coffee" in result.system_prompt
        assert "Luna was created in 2025" in result.system_prompt
        assert result.memory_source == "nodes"

    @pytest.mark.asyncio
    async def test_memory_context_string(self):
        assembler = PromptAssembler(_mock_director_with_emergent())
        result = await assembler.build(PromptRequest(
            message="test",
            memory_context="Pre-fetched memory text about projects",
        ))
        assert "Pre-fetched memory text" in result.system_prompt
        assert result.memory_source == "text"

    @pytest.mark.asyncio
    async def test_no_memory_valid(self):
        assembler = PromptAssembler(_mock_director_with_emergent())
        result = await assembler.build(PromptRequest(message="hello"))
        assert result.system_prompt  # Not empty
        assert result.memory_source is None

    @pytest.mark.asyncio
    async def test_auto_fetch_memory(self):
        assembler = PromptAssembler(_mock_director_with_memory_fetch())
        result = await assembler.build(PromptRequest(
            message="do you remember our talk?",
            auto_fetch_memory=True,
        ))
        assert "dark roast coffee" in result.system_prompt
        assert result.memory_source == "fetched"

    @pytest.mark.asyncio
    async def test_memories_capped_at_5(self):
        assembler = PromptAssembler(_mock_director_with_emergent())
        memories = [{"content": f"Memory {i}"} for i in range(10)]
        result = await assembler.build(PromptRequest(
            message="test",
            memories=memories,
        ))
        # Should only include first 5
        assert "Memory 4" in result.system_prompt
        assert "Memory 5" not in result.system_prompt


# =============================================================================
# ASSEMBLY ORDER
# =============================================================================

class TestAssemblyOrder:

    @pytest.mark.asyncio
    async def test_identity_before_temporal(self):
        assembler = PromptAssembler(_mock_director_with_emergent())
        result = await assembler.build(PromptRequest(message="hello"))
        prompt = result.system_prompt
        identity_pos = prompt.find("Luna")
        temporal_pos = prompt.find("Current Time")
        assert identity_pos < temporal_pos

    @pytest.mark.asyncio
    async def test_temporal_before_memory(self):
        assembler = PromptAssembler(_mock_director_with_emergent())
        result = await assembler.build(PromptRequest(
            message="hello",
            memory_context="Some memory",
        ))
        prompt = result.system_prompt
        temporal_pos = prompt.find("Current Time")
        memory_pos = prompt.find("Some memory")
        assert temporal_pos < memory_pos

    @pytest.mark.asyncio
    async def test_voice_always_last(self):
        assembler = PromptAssembler(_mock_director_with_voice())
        result = await assembler.build(PromptRequest(
            message="hello",
            memory_context="Some memory context",
        ))
        if result.voice_injected:
            voice_pos = result.system_prompt.find("<luna_voice")
            memory_pos = result.system_prompt.find("Memory Context")
            if memory_pos > -1:
                assert voice_pos > memory_pos


# =============================================================================
# VOICE
# =============================================================================

class TestVoice:

    @pytest.mark.asyncio
    async def test_voice_block_injected(self):
        assembler = PromptAssembler(_mock_director_with_voice())
        result = await assembler.build(PromptRequest(message="hello"))
        assert result.voice_injected
        assert "<luna_voice>" in result.system_prompt

    @pytest.mark.asyncio
    async def test_voice_block_absent_when_no_orchestrator(self):
        assembler = PromptAssembler(_mock_director_no_subsystems())
        result = await assembler.build(PromptRequest(message="hello"))
        assert not result.voice_injected

    @pytest.mark.asyncio
    async def test_voice_failure_graceful(self):
        director = _mock_director_with_emergent()
        director._generate_voice_block = Mock(side_effect=Exception("voice crash"))
        assembler = PromptAssembler(director)
        result = await assembler.build(PromptRequest(message="hello"))
        assert not result.voice_injected
        assert result.system_prompt  # Still produces a prompt


# =============================================================================
# MESSAGES ARRAY
# =============================================================================

class TestMessagesArray:

    @pytest.mark.asyncio
    async def test_messages_from_history(self):
        assembler = PromptAssembler(_mock_director_no_subsystems())
        result = await assembler.build(PromptRequest(
            message="what's up?",
            conversation_history=[
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "hi there"},
            ],
        ))
        assert len(result.messages) == 3
        assert result.messages[0] == {"role": "user", "content": "hello"}
        assert result.messages[1] == {"role": "assistant", "content": "hi there"}
        assert result.messages[2] == {"role": "user", "content": "what's up?"}

    @pytest.mark.asyncio
    async def test_messages_current_only(self):
        assembler = PromptAssembler(_mock_director_no_subsystems())
        result = await assembler.build(PromptRequest(message="just me"))
        assert len(result.messages) == 1
        assert result.messages[0] == {"role": "user", "content": "just me"}

    @pytest.mark.asyncio
    async def test_empty_content_filtered(self):
        assembler = PromptAssembler(_mock_director_no_subsystems())
        result = await assembler.build(PromptRequest(
            message="test",
            conversation_history=[
                {"role": "user", "content": ""},
                {"role": "assistant", "content": "real response"},
            ],
        ))
        assert len(result.messages) == 2  # empty filtered + current


# =============================================================================
# METADATA
# =============================================================================

class TestMetadata:

    @pytest.mark.asyncio
    async def test_metadata_populated(self):
        assembler = PromptAssembler(_mock_director_with_emergent())
        result = await assembler.build(PromptRequest(message="hello"))
        assert result.identity_source in ("pipeline", "emergent", "buffer", "fallback")
        assert result.prompt_tokens > 0

    @pytest.mark.asyncio
    async def test_temporal_metadata(self):
        assembler = PromptAssembler(_mock_director_with_emergent())
        result = await assembler.build(PromptRequest(message="hello"))
        assert result.temporal_injected is True
        assert result.gap_category is not None


# =============================================================================
# TEMPORAL BLOCK IN ASSEMBLER
# =============================================================================

class TestTemporalBlock:

    @pytest.mark.asyncio
    async def test_clock_always_present(self):
        assembler = PromptAssembler(_mock_director_no_subsystems())
        result = await assembler.build(PromptRequest(message="hello"))
        assert "Current Time" in result.system_prompt

    @pytest.mark.asyncio
    async def test_temporal_between_identity_and_memory(self):
        assembler = PromptAssembler(_mock_director_with_emergent())
        result = await assembler.build(PromptRequest(
            message="test",
            memory_context="relevant memories",
        ))
        prompt = result.system_prompt
        time_pos = prompt.find("Current Time")
        mem_pos = prompt.find("relevant memories")
        identity_pos = prompt.find("Luna")
        assert identity_pos < time_pos < mem_pos


# =============================================================================
# EXPRESSION BLOCK
# =============================================================================

class TestExpressionBlock:

    @pytest.mark.asyncio
    async def test_expression_block_present(self):
        assembler = PromptAssembler(_mock_director_with_engine())
        result = await assembler.build(PromptRequest(message="hello"))
        assert "Emotional Expression" in result.system_prompt
        assert "gestures" in result.system_prompt

    @pytest.mark.asyncio
    async def test_expression_block_missing_graceful(self):
        """No engine available — no crash, no expression block."""
        assembler = PromptAssembler(_mock_director_no_subsystems())
        result = await assembler.build(PromptRequest(message="hello"))
        assert "Emotional Expression" not in result.system_prompt
        assert result.system_prompt  # Still produces a prompt

    @pytest.mark.asyncio
    async def test_expression_after_identity(self):
        assembler = PromptAssembler(_mock_director_with_engine())
        result = await assembler.build(PromptRequest(message="hello"))
        prompt = result.system_prompt
        identity_pos = prompt.find("Luna")
        expression_pos = prompt.find("Emotional Expression")
        assert identity_pos < expression_pos

    @pytest.mark.asyncio
    async def test_expression_engine_error_graceful(self):
        director = _mock_director_with_emergent()
        engine = Mock(spec=[])  # spec=[] prevents auto-creating attributes
        engine._get_expression_directive = Mock(side_effect=Exception("config crash"))
        engine.get_actor = Mock(return_value=None)
        director._engine = engine
        director.engine = engine
        assembler = PromptAssembler(director)
        result = await assembler.build(PromptRequest(message="hello"))
        assert "Emotional Expression" not in result.system_prompt
        assert result.system_prompt  # Still works


# =============================================================================
# CONSCIOUSNESS BLOCK
# =============================================================================

class TestConsciousnessBlock:

    @pytest.mark.asyncio
    async def test_consciousness_block_present(self):
        assembler = PromptAssembler(_mock_director_with_engine())
        result = await assembler.build(PromptRequest(message="hello"))
        assert "curious and engaged" in result.system_prompt

    @pytest.mark.asyncio
    async def test_consciousness_block_missing_graceful(self):
        """No engine/consciousness — no crash."""
        assembler = PromptAssembler(_mock_director_no_subsystems())
        result = await assembler.build(PromptRequest(message="hello"))
        assert "curious and engaged" not in result.system_prompt
        assert result.system_prompt

    @pytest.mark.asyncio
    async def test_consciousness_empty_hint_excluded(self):
        director = _mock_director_with_emergent()
        engine = Mock()
        engine._get_expression_directive = Mock(return_value="")
        consciousness = Mock()
        consciousness.get_context_hint = Mock(return_value="")
        engine.consciousness = consciousness
        engine.get_actor = Mock(return_value=None)
        director._engine = engine
        director.engine = engine
        assembler = PromptAssembler(director)
        result = await assembler.build(PromptRequest(message="hello"))
        # Empty hints should not add empty sections
        assert "\n\n\n\n" not in result.system_prompt

    @pytest.mark.asyncio
    async def test_consciousness_after_memory(self):
        assembler = PromptAssembler(_mock_director_with_engine())
        result = await assembler.build(PromptRequest(
            message="test",
            memory_context="some memory about projects",
        ))
        prompt = result.system_prompt
        mem_pos = prompt.find("some memory")
        consciousness_pos = prompt.find("curious and engaged")
        assert mem_pos < consciousness_pos


# =============================================================================
# FULL 6-LAYER ASSEMBLY ORDER
# =============================================================================

class TestFullAssemblyOrder:

    @pytest.mark.asyncio
    async def test_6_layer_ordering(self):
        """Verify: identity < expression < temporal < memory < consciousness < voice."""
        assembler = PromptAssembler(_mock_director_full_stack())
        result = await assembler.build(PromptRequest(
            message="how are you?",
            auto_fetch_memory=True,
        ))
        prompt = result.system_prompt

        identity_pos = prompt.find("Luna")
        expression_pos = prompt.find("Emotional Expression")
        temporal_pos = prompt.find("SYSTEM CLOCK:")
        memory_pos = prompt.find("consciousness engines")
        consciousness_pos = prompt.find("curious and engaged")
        voice_pos = prompt.find("<luna_voice>")

        assert identity_pos < expression_pos, "identity should come before expression"
        assert expression_pos < temporal_pos, "expression should come before temporal"
        assert temporal_pos < memory_pos, "temporal should come before memory"
        assert memory_pos < consciousness_pos, "memory should come before consciousness"
        assert consciousness_pos < voice_pos, "consciousness should come before voice"


# =============================================================================
# GROUNDING RULES (anti-hallucination)
# =============================================================================

class TestGroundingRules:

    @pytest.mark.asyncio
    async def test_grounding_always_present_fallback(self):
        """Grounding rules must appear even with fallback identity."""
        assembler = PromptAssembler(_mock_director_no_subsystems())
        result = await assembler.build(PromptRequest(message="hello"))
        assert "Grounding Rules" in result.system_prompt

    @pytest.mark.asyncio
    async def test_grounding_always_present_emergent(self):
        """Grounding rules must appear with emergent identity."""
        assembler = PromptAssembler(_mock_director_with_emergent())
        result = await assembler.build(PromptRequest(message="hello"))
        assert "Grounding Rules" in result.system_prompt

    @pytest.mark.asyncio
    async def test_grounding_always_present_pipeline(self):
        """Grounding rules must appear with pipeline identity."""
        assembler = PromptAssembler(_mock_director_with_pipeline())
        result = await assembler.build(PromptRequest(message="hello"))
        assert "Grounding Rules" in result.system_prompt

    @pytest.mark.asyncio
    async def test_grounding_after_identity_before_expression(self):
        """Grounding sits between identity and expression (Layer 1.5)."""
        assembler = PromptAssembler(_mock_director_with_engine())
        result = await assembler.build(PromptRequest(message="hello"))
        prompt = result.system_prompt
        identity_pos = prompt.find("Luna")
        grounding_pos = prompt.find("Grounding Rules")
        expression_pos = prompt.find("Emotional Expression")
        assert identity_pos < grounding_pos < expression_pos

    @pytest.mark.asyncio
    async def test_grounding_contains_anti_fabrication_rules(self):
        assembler = PromptAssembler(_mock_director_no_subsystems())
        result = await assembler.build(PromptRequest(message="hello"))
        assert "Never fabricate" in result.system_prompt
        assert "Do not embellish" in result.system_prompt


# =============================================================================
# AUTHORITATIVE CLOCK
# =============================================================================

class TestAuthoritativeClock:

    @pytest.mark.asyncio
    async def test_clock_has_authoritative_prefix(self):
        assembler = PromptAssembler(_mock_director_no_subsystems())
        result = await assembler.build(PromptRequest(message="hello"))
        assert "SYSTEM CLOCK:" in result.system_prompt
        assert "AUTHORITATIVE" in result.system_prompt

    @pytest.mark.asyncio
    async def test_clock_has_exact_time(self):
        """Clock should include hour:minute AM/PM, not just 'morning'."""
        assembler = PromptAssembler(_mock_director_no_subsystems())
        result = await assembler.build(PromptRequest(message="hello"))
        # Should contain time like "10:32 AM" or "02:15 PM"
        import re
        assert re.search(r'\d{2}:\d{2} [AP]M', result.system_prompt)

    @pytest.mark.asyncio
    async def test_clock_directive_present(self):
        assembler = PromptAssembler(_mock_director_no_subsystems())
        result = await assembler.build(PromptRequest(message="hello"))
        assert "use ONLY these values" in result.system_prompt


# =============================================================================
# MEMORY PROVENANCE
# =============================================================================

class TestMemoryProvenance:

    @pytest.mark.asyncio
    async def test_structured_nodes_show_lock_in(self):
        """Structured memory nodes should show provenance tags."""
        assembler = PromptAssembler(_mock_director_with_emergent())
        result = await assembler.build(PromptRequest(
            message="test",
            memories=[
                {"content": "Ahab likes coffee", "lock_in_state": "settled", "node_type": "FACT"},
            ],
        ))
        assert "[settled|FACT]" in result.system_prompt
        assert "Ahab likes coffee" in result.system_prompt

    @pytest.mark.asyncio
    async def test_structured_nodes_unknown_when_missing(self):
        """Nodes without lock_in_state default to [unknown|memory]."""
        assembler = PromptAssembler(_mock_director_with_emergent())
        result = await assembler.build(PromptRequest(
            message="test",
            memories=[{"content": "Some old memory"}],
        ))
        assert "[unknown|memory]" in result.system_prompt

    @pytest.mark.asyncio
    async def test_provenance_key_header(self):
        """Memory block should include provenance key explanation."""
        assembler = PromptAssembler(_mock_director_with_emergent())
        result = await assembler.build(PromptRequest(
            message="test",
            memories=[{"content": "a memory"}],
        ))
        assert "Provenance key:" in result.system_prompt

    @pytest.mark.asyncio
    async def test_memory_footer_no_confabulation(self):
        """Memory footer should NOT say 'your own experiences'."""
        assembler = PromptAssembler(_mock_director_with_emergent())
        result = await assembler.build(PromptRequest(
            message="test",
            memories=[{"content": "a memory"}],
        ))
        assert "your own experiences" not in result.system_prompt
        # Nodes path uses "irrelevant to the question" as anti-confabulation marker
        assert "irrelevant to the question, ignore it" in result.system_prompt
