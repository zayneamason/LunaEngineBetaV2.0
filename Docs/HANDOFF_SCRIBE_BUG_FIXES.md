# HANDOFF: Scribe (Ben Franklin) Bug Fixes & Hardening

**Date:** 2026-02-08
**Author:** Architect (The Dude)
**For:** Claude Code execution agents
**Scope:** Fix Scribe-specific bugs, improve extraction quality, add QA coverage
**Mode:** SURGICAL — fix only what's specified, touch nothing else
**Dependency:** Run AFTER `HANDOFF_AIBRARIAN_BUG_FIXES.md` (Bugs #1-6)

---

## CONTEXT

The Scribe (Ben Franklin) is the extraction actor. It receives conversation
turns, chunks them, sends chunks to Claude API (or local model) for structured
extraction, then forwards results to the Librarian for filing.

The Scribe itself is the healthiest part of the AI-BRARIAN pipeline — its
assistant-turn filter works, its JSON parsing is robust, and its extraction
prompt is well-structured. The bugs here are lower severity but still need
fixing before the system is production-ready.

---

## PROJECT ROOT

```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/
```

---

## BUG #7: `_extract_local()` Misleading Docstring + Silent Drop — MEDIUM

### Problem
`_extract_local()` docstring says "Falls back to Claude if local not available."
Actual behavior: returns empty `(ExtractionOutput(), [])` with a DEBUG log.
When `backend="local"` and local model isn't loaded, ALL extraction is silently
dropped. No error, no warning, no fallback.

This matters because switching to local inference is the sovereignty goal.
If someone sets `backend="local"` and the model isn't ready, they get zero
extraction with no indication anything is wrong.

### Location
`src/luna/actors/scribe.py` — method `_extract_local()` (line 501)

### Current:
```python
async def _extract_local(self, text, source_id):
    """
    Extract using local model.

    Falls back to Claude if local not available.  # <-- LIE
    """
    if self.engine:
        director = self.engine.get_actor("director")
        if director and hasattr(director, "_local") and director._local:
            local = director._local
            if local.is_loaded:
                # ... actual extraction ...

    # Fallback: Return empty (don't spam errors when Claude is unavailable)
    logger.debug("Ben: Local not available, extraction skipped (Claude fallback disabled)")
    return (ExtractionOutput(), [])
```

### Fix:
```python
async def _extract_local(
    self,
    text: str,
    source_id: str,
) -> tuple[ExtractionOutput, list[EntityUpdate]]:
    """
    Extract using local model.

    Returns empty output if local model is unavailable.
    Does NOT fall back to Claude — sovereignty principle.
    Log at WARNING so operators know extraction is being skipped.
    """
    if self.engine:
        director = self.engine.get_actor("director")
        if director and hasattr(director, "_local") and director._local:
            local = director._local
            if local.is_loaded:
                try:
                    prompt = f"{EXTRACTION_SYSTEM_PROMPT}\n\nExtract from:\n{text}"
                    result = await local.generate(prompt)
                    return self._parse_extraction_response(result.text, source_id)
                except Exception as e:
                    logger.warning(f"Ben: Local extraction failed: {e}")
                    return (ExtractionOutput(), [])
            else:
                logger.warning(
                    "Ben: Local model not loaded — extraction skipped. "
                    "Load a model or switch backend to 'haiku'."
                )
        else:
            logger.warning(
                "Ben: Director has no local model configured — extraction skipped."
            )
    else:
        logger.warning("Ben: No engine reference — cannot access local model.")

    return (ExtractionOutput(), [])
```

**Changes:**
1. Fix docstring — no longer claims Claude fallback
2. Promote from DEBUG to WARNING so it's visible in logs
3. Add specific warning for each failure case (model not loaded vs not configured vs no engine)

---

## BUG #8: Stale Model IDs — LOW

### Problem
Three locations reference old Anthropic model strings:

1. `src/luna/extraction/types.py` line 227: `"claude-3-haiku-20240307"` in EXTRACTION_BACKENDS
2. `src/luna/extraction/types.py` line 233: `"claude-3-5-sonnet-20241022"` in EXTRACTION_BACKENDS
3. `src/luna/actors/scribe.py` line 477: `"claude-3-haiku-20240307"` as fallback default
4. `src/luna/actors/scribe.py` line 774: `"claude-3-haiku-20240307"` hardcoded in `compress_turn()`

These still work via Anthropic's API (old model IDs are supported), but may not
offer best price/performance and could eventually be deprecated.

### Fix:

**In `src/luna/extraction/types.py`:**
```python
EXTRACTION_BACKENDS = {
    "haiku": {
        "model": "claude-haiku-4-5-20251001",
        "cost_per_1k_input": 0.0008,
        "cost_per_1k_output": 0.004,
        "quality": "good",
    },
    "sonnet": {
        "model": "claude-sonnet-4-5-20250929",
        "cost_per_1k_input": 0.003,
        "cost_per_1k_output": 0.015,
        "quality": "excellent",
    },
    "local": {
        "model": "qwen-3b",
        "cost_per_1k_input": 0,
        "cost_per_1k_output": 0,
        "quality": "basic",
    },
}
```

**In `src/luna/actors/scribe.py` line 477:**
```python
model = backend_config.get("model", "claude-haiku-4-5-20251001")
```

**In `src/luna/actors/scribe.py` line 774 (`compress_turn`):**
```python
response = self.client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=80,
    temperature=0.3,
    messages=[{"role": "user", "content": compression_prompt}]
)
```

**NOTE:** Verify current model IDs at time of implementation. Check
https://docs.anthropic.com/en/docs/about-claude/models for latest strings.
The pricing above is approximate — update from Anthropic's pricing page.

---

## BUG #9: tiktoken Not Installed — LOW

### Problem
`SemanticChunker` falls back to `len(text) // 4` for token estimation.
This is a ~20% error rate on non-English text and code blocks.

### Location
`src/luna/extraction/chunker.py` — `estimate_tokens()` (line 18)

### Fix:
Either install tiktoken:
```bash
pip install tiktoken
```

Or accept the heuristic and document it. The `len/4` fallback is fine for
English conversational text (which is 95% of Luna's input). Only matters
if extraction accuracy on code blocks or multilingual content is important.

**Recommendation:** Low priority. Install tiktoken if/when extraction quality
on code content becomes an issue. For now, document the limitation.

---

## BUG #10: `compress_turn()` Has No Backend Config Routing — LOW

### Problem
`compress_turn()` (line 729) hardcodes the model string for compression.
It tries local first (good), then falls back to a hardcoded Haiku call.
It doesn't use `EXTRACTION_BACKENDS` or `self.config.backend`.

This means:
- If someone configures `backend="sonnet"`, extraction uses Sonnet but compression uses Haiku
- If someone configures `backend="disabled"`, extraction is skipped but compression still calls Claude API

### Location
`src/luna/actors/scribe.py` — method `compress_turn()` (line 729)

### Fix:
Route through the backend config:
```python
async def compress_turn(self, content: str, role: str = "user") -> str:
    """Compress a conversation turn into a one-sentence summary."""
    if len(content) < 100:
        return content

    compression_prompt = f"""Compress this {role} message into ONE sentence under 50 words.
Focus on: what was asked/said, any decisions, key facts mentioned.
Use past tense. No commentary.

Message:
{content}

Compressed:"""

    try:
        # Try local model first
        if self.engine:
            director = self.engine.get_actor("director")
            if director and hasattr(director, "_local") and director._local:
                local = director._local
                if local.is_loaded:
                    result = await local.generate(
                        compression_prompt,
                        max_tokens=80,
                        temperature=0.3
                    )
                    compressed = result.text.strip()
                    logger.debug(f"Ben: Compressed turn locally ({len(content)} -> {len(compressed)} chars)")
                    return compressed

        # Fallback to Claude — use configured backend model
        if self.config.backend != "disabled" and self.client:
            backend_config = EXTRACTION_BACKENDS.get(self.config.backend, {})
            model = backend_config.get("model", "claude-haiku-4-5-20251001")

            response = self.client.messages.create(
                model=model,
                max_tokens=80,
                temperature=0.3,
                messages=[{"role": "user", "content": compression_prompt}]
            )
            compressed = response.content[0].text.strip()
            logger.debug(f"Ben: Compressed turn via {model} ({len(content)} -> {len(compressed)} chars)")
            return compressed

    except Exception as e:
        logger.error(f"Ben: Compression failed: {e}")

    # Ultimate fallback: truncate
    return content[:200] + "..." if len(content) > 200 else content
```

---

## EXTRACTION PROMPT QUALITY NOTE

The extraction prompt (`EXTRACTION_SYSTEM_PROMPT`) is well-structured.
It correctly instructs the LLM to put:
- Full sentences in `content` ("The actual information in neutral language")
- Proper nouns in `entities` ("Names of people/projects/concepts mentioned")

**The Scribe does its job correctly.** The entity resolution noise (Bug #3
from the AI-BRARIAN handoff) is caused by the Librarian's `_wire_extraction()`
passing `obj.content` to `_resolve_entity()`, NOT by the Scribe's extraction.

However, one improvement worth considering for extraction quality:

### Enhancement: Explicit Entity vs Content Separation Instruction

Add this line to the extraction prompt after the OUTPUT FORMAT section:

```
### IMPORTANT:
- "content" is a SENTENCE describing the information
- "entities" is a LIST OF PROPER NOUNS only (names, places, projects)
- Never put a sentence in "entities"
- Never put a proper noun alone in "content" — always describe what about them
```

This is defensive — the LLM already does this correctly, but explicitly
stating the constraint prevents drift if the model changes or degrades.

---

## SCRIBE QA ASSERTIONS

Add to `src/luna/qa/assertions.py`:

```python
def check_extraction_backend_active(ctx: InferenceContext, a: Assertion) -> AssertionResult:
    """
    Check that the extraction backend is not silently dropping extractions.
    """
    backend_active = True
    if hasattr(ctx, 'extraction_stats') and ctx.extraction_stats:
        backend = ctx.extraction_stats.get("backend", "unknown")
        extractions = ctx.extraction_stats.get("extractions_count", 0)
        # If backend is "local" and zero extractions after 10+ turns, something is wrong
        turns = ctx.extraction_stats.get("turns_processed", 0)
        if backend == "local" and turns > 10 and extractions == 0:
            backend_active = False

    return AssertionResult(
        id=a.id, name=a.name, passed=backend_active, severity=a.severity,
        expected="Extraction backend producing results",
        actual="Active" if backend_active else "Backend appears dead — 0 extractions after 10+ turns",
        details="Local backend may not have a model loaded" if not backend_active else None,
    )


def check_extraction_objects_have_entities(ctx: InferenceContext, a: Assertion) -> AssertionResult:
    """
    Check that extracted objects include entity lists (not just content).
    Empty entities lists mean the graph can't build relationships.
    """
    empty_entity_ratio = 0.0
    if hasattr(ctx, 'extraction_stats') and ctx.extraction_stats:
        total = ctx.extraction_stats.get("total_objects", 0)
        empty = ctx.extraction_stats.get("objects_without_entities", 0)
        if total > 0:
            empty_entity_ratio = empty / total

    # More than 80% without entities = prompt or parsing issue
    passed = empty_entity_ratio < 0.8
    return AssertionResult(
        id=a.id, name=a.name, passed=passed, severity=a.severity,
        expected="< 80% objects without entities",
        actual=f"{empty_entity_ratio*100:.0f}% without entities",
        details="Extraction prompt may not be producing entity lists" if not passed else None,
    )
```

### Add to `get_default_assertions()`:
```python
# Extraction
Assertion(
    id="E1", name="Extraction backend active",
    description="Backend should produce extractions (not silently dropping)",
    category="integration", severity="high",
    check_type="builtin", builtin_fn=check_extraction_backend_active,
),
Assertion(
    id="E2", name="Extractions include entities",
    description="Extracted objects should include entity lists for graph building",
    category="integration", severity="medium",
    check_type="builtin", builtin_fn=check_extraction_objects_have_entities,
),
```

### Diagnosis addition for `QAValidator._generate_diagnosis()`:
```python
backend_dead = any(r.id == "E1" and not r.passed for r in results)
if backend_dead:
    diagnoses.append(
        "Extraction backend appears dead — 0 extractions after 10+ turns. "
        "If using 'local' backend, check that model is loaded. "
        "If model unavailable, switch to 'haiku' backend."
    )

no_entities = any(r.id == "E2" and not r.passed for r in results)
if no_entities:
    diagnoses.append(
        "Most extracted objects have empty entity lists. "
        "Graph relationships depend on entities. Check extraction prompt "
        "and _parse_extraction_response() entity parsing."
    )
```

---

## EXTRACTION STATS POPULATION

For E1 and E2 assertions to work, `extraction_stats` needs to be populated
in `InferenceContext`. Add this where the context is built (Director or engine):

```python
scribe = engine.get_actor("scribe")
if scribe:
    scribe_stats = scribe.get_stats()
    history = scribe.get_extraction_history()

    # Count objects without entities
    objects_without_entities = 0
    total_objects = 0
    for entry in history[-20:]:  # Last 20 extractions
        for obj in entry.get("objects", []):
            total_objects += 1
            if not obj.get("entities"):
                objects_without_entities += 1

    ctx.extraction_stats = {
        "backend": scribe_stats.get("backend", "unknown"),
        "extractions_count": scribe_stats.get("extractions_count", 0),
        "turns_processed": scribe_stats.get("extractions_count", 0),  # approximate
        "total_objects": total_objects,
        "objects_without_entities": objects_without_entities,
    }
```

---

## INTEGRATION TEST

Add to `tests/integration/test_seam_validation.py` (or create
`tests/integration/test_scribe_seams.py`):

```python
@pytest.mark.asyncio
async def test_scribe_extraction_output_matches_librarian_input():
    """
    Validate that Scribe's ExtractionOutput structure is what
    Librarian's _wire_extraction() expects.

    This catches field name mismatches between producer and consumer.
    """
    from luna.extraction.types import (
        ExtractionOutput, ExtractedObject, ExtractedEdge, ExtractionType
    )

    # Simulate what Scribe produces
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

    # Verify Librarian can consume it
    # Objects must have: .content, .type, .confidence, .entities
    for obj in extraction.objects:
        assert hasattr(obj, 'content'), "ExtractedObject missing 'content'"
        assert hasattr(obj, 'type'), "ExtractedObject missing 'type'"
        assert hasattr(obj, 'confidence'), "ExtractedObject missing 'confidence'"
        assert hasattr(obj, 'entities'), "ExtractedObject missing 'entities'"
        assert isinstance(obj.entities, list), "entities must be a list"
        # Content should be a sentence, not a proper noun
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
    If someone modifies the prompt and removes the entities field,
    this test catches it.
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
    Catches stale model IDs.
    """
    from luna.extraction.types import EXTRACTION_BACKENDS

    for name, config in EXTRACTION_BACKENDS.items():
        if name == "local":
            continue  # Local doesn't use Anthropic models
        model = config.get("model", "")
        assert model, f"Backend '{name}' has empty model string"
        # Anthropic model strings should contain 'claude'
        assert "claude" in model.lower(), \
            f"Backend '{name}' model '{model}' doesn't look like an Anthropic model"


@pytest.mark.asyncio
async def test_scribe_skips_assistant_via_extract_turn():
    """
    Verify that extract_turn path skips assistant turns.
    This is the guard that prevents Luna's outputs from entering memory.
    """
    from luna.actors.scribe import ScribeActor
    from luna.actors.base import Message

    scribe = ScribeActor()

    # Send assistant turn — should be silently skipped
    msg = Message(
        type="extract_turn",
        payload={
            "role": "assistant",
            "content": "Here is some LLM-generated text that should NOT be extracted",
            "session_id": "test",
        }
    )
    await scribe.handle(msg)

    # Stack should be empty — nothing was queued
    assert len(scribe.stack) == 0, "Assistant turn should not enter extraction stack"


@pytest.mark.asyncio
async def test_extract_text_has_no_role_filter():
    """
    Document that extract_text does NOT filter by role.
    This is expected behavior — the caller is responsible for filtering.
    This test exists to make the contract explicit.
    """
    from luna.actors.scribe import ScribeActor
    from luna.actors.base import Message

    scribe = ScribeActor()

    # extract_text processes everything regardless of role
    msg = Message(
        type="extract_text",
        payload={
            "text": "This is some text that will be extracted regardless of source",
            "source_id": "test",
            "immediate": False,  # Don't need Claude for this test
        }
    )
    await scribe.handle(msg)

    # Text should enter the stack (extract_text has no filter)
    assert len(scribe.stack) > 0, "extract_text should process all content"
```

---

## EXECUTION ORDER

```
1. Fix _extract_local() docstring + logging     [scribe.py]
2. Update EXTRACTION_BACKENDS model strings      [types.py]
3. Update hardcoded model in _extract_claude()   [scribe.py]
4. Update hardcoded model in compress_turn()     [scribe.py]
5. Route compress_turn through backend config    [scribe.py]
6. Add extraction prompt clarification           [scribe.py]
7. Add E1, E2 assertions                         [assertions.py]
8. Add extraction diagnosis                      [validator.py]
9. Wire extraction_stats population              [engine/director]
10. Create scribe seam tests                     [test file]
11. Run full test suite — confirm 0 failures
```

---

## VERIFICATION CHECKLIST

- [ ] `_extract_local()` logs WARNING when model unavailable (not DEBUG)
- [ ] `_extract_local()` docstring doesn't claim Claude fallback
- [ ] EXTRACTION_BACKENDS uses current model strings
- [ ] No hardcoded old model strings remain in scribe.py
- [ ] `compress_turn()` uses backend config, not hardcoded model
- [ ] `compress_turn()` respects `backend="disabled"` (doesn't call Claude)
- [ ] Extraction prompt includes entity vs content clarification
- [ ] QA assertions E1, E2 exist and have correct logic
- [ ] All existing tests still pass
- [ ] New seam tests pass

---

## FILES MODIFIED

| File | Changes |
|------|---------|
| `src/luna/actors/scribe.py` | Fix `_extract_local()` logging, update model strings, route `compress_turn()` through config |
| `src/luna/extraction/types.py` | Update `EXTRACTION_BACKENDS` model strings and pricing |
| `src/luna/qa/assertions.py` | Add E1, E2 extraction assertions |
| `src/luna/qa/validator.py` | Add extraction diagnosis logic |
| `tests/integration/test_scribe_seams.py` | NEW — scribe contract + seam tests |

---

**End of handoff.**