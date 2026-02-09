"""
Scribe Seam Tests — Contract validation for extraction pipeline.

Validates:
1. ExtractionOutput structure matches what Librarian expects
2. Extraction prompt requests entities field
3. EXTRACTION_BACKENDS have valid model strings
4. extract_turn skips assistant turns
5. extract_text has no role filter (contract documentation)
"""

import pytest
from luna.extraction.types import (
    ExtractionOutput, ExtractedObject, ExtractedEdge, ExtractionType
)


@pytest.mark.asyncio
async def test_scribe_extraction_output_matches_librarian_input():
    """
    Validate that Scribe's ExtractionOutput structure is what
    Librarian's _wire_extraction() expects.
    """
    extraction = ExtractionOutput(
        source_id="test",
        objects=[
            ExtractedObject(
                type=ExtractionType.FACT,
                content="Ahab lives in San Francisco",
                confidence=0.9,
                entities=["Ahab", "San Francisco"],
            ),
        ],
        edges=[
            ExtractedEdge(
                from_ref="Ahab",
                to_ref="San Francisco",
                edge_type="LIVES_IN",
                confidence=0.85,
            ),
        ],
    )

    # Objects must have: .content, .type, .confidence, .entities
    for obj in extraction.objects:
        assert hasattr(obj, 'content'), "ExtractedObject missing 'content'"
        assert hasattr(obj, 'type'), "ExtractedObject missing 'type'"
        assert hasattr(obj, 'confidence'), "ExtractedObject missing 'confidence'"
        assert hasattr(obj, 'entities'), "ExtractedObject missing 'entities'"
        assert isinstance(obj.entities, list), "entities must be a list"
        assert len(obj.content) > 10, "content should be descriptive, not a name"

    # Edges must have: .from_ref, .to_ref, .edge_type, .confidence
    for edge in extraction.edges:
        assert hasattr(edge, 'from_ref'), "ExtractedEdge missing 'from_ref'"
        assert hasattr(edge, 'to_ref'), "ExtractedEdge missing 'to_ref'"
        assert hasattr(edge, 'edge_type'), "ExtractedEdge missing 'edge_type'"
        assert hasattr(edge, 'confidence'), "ExtractedEdge missing 'confidence'"


def test_scribe_extraction_prompt_requests_entities():
    """
    Verify the extraction prompt explicitly asks for entities list.
    """
    from luna.actors.scribe import EXTRACTION_SYSTEM_PROMPT

    assert '"entities"' in EXTRACTION_SYSTEM_PROMPT, \
        "Extraction prompt must request 'entities' field"
    assert '"content"' in EXTRACTION_SYSTEM_PROMPT, \
        "Extraction prompt must request 'content' field"
    assert '"edges"' in EXTRACTION_SYSTEM_PROMPT, \
        "Extraction prompt must request 'edges' field"


def test_extraction_backends_have_valid_models():
    """
    Verify EXTRACTION_BACKENDS model strings look valid.
    """
    from luna.extraction.types import EXTRACTION_BACKENDS

    for name, config in EXTRACTION_BACKENDS.items():
        if name == "local":
            continue
        model = config.get("model", "")
        assert model, f"Backend '{name}' has empty model string"
        assert "claude" in model.lower(), \
            f"Backend '{name}' model '{model}' doesn't look like an Anthropic model"


def test_extraction_backends_use_current_models():
    """
    Verify EXTRACTION_BACKENDS don't use old deprecated model strings.
    """
    from luna.extraction.types import EXTRACTION_BACKENDS

    old_models = [
        "claude-3-haiku-20240307",
        "claude-3-5-sonnet-20241022",
        "claude-3-sonnet-20240229",
    ]

    for name, config in EXTRACTION_BACKENDS.items():
        model = config.get("model", "")
        assert model not in old_models, \
            f"Backend '{name}' uses deprecated model '{model}'"


@pytest.mark.asyncio
async def test_scribe_skips_assistant_via_extract_turn():
    """
    Verify that extract_turn path skips assistant turns.
    """
    from luna.actors.scribe import ScribeActor
    from luna.actors.base import Message

    scribe = ScribeActor()

    msg = Message(
        type="extract_turn",
        payload={
            "role": "assistant",
            "content": "Here is some LLM-generated text that should NOT be extracted",
            "session_id": "test",
        }
    )
    await scribe.handle(msg)

    assert len(scribe.stack) == 0, "Assistant turn should not enter extraction stack"


@pytest.mark.asyncio
async def test_extract_text_has_no_role_filter():
    """
    Document that extract_text does NOT filter by role.
    The caller is responsible for filtering.
    """
    from luna.actors.scribe import ScribeActor
    from luna.actors.base import Message

    scribe = ScribeActor()

    msg = Message(
        type="extract_text",
        payload={
            "text": "This is some text that will be extracted regardless of source",
            "source_id": "test",
            "immediate": False,
        }
    )
    await scribe.handle(msg)

    assert len(scribe.stack) > 0, "extract_text should process all content"


def test_extraction_prompt_has_entity_content_clarification():
    """
    Verify the extraction prompt includes the entity vs content clarification.
    """
    from luna.actors.scribe import EXTRACTION_SYSTEM_PROMPT

    assert "CONTENT vs ENTITIES" in EXTRACTION_SYSTEM_PROMPT or \
           "content\" is a SENTENCE" in EXTRACTION_SYSTEM_PROMPT, \
        "Extraction prompt should clarify content vs entities distinction"
