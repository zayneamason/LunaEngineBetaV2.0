# HANDOFF: Retrieval-Side Mode Awareness — Precision / Reflective / Relational

**Priority:** P2 — Completes the comprehension roadmap  
**Status:** Ready for implementation  
**Depends on:** Step 7 (Reflection Layer) must land first — this handoff routes to reflection nodes that Step 7 creates  
**Target files:**
- `src/luna/engine.py` (retrieval path, ~line 1135)
- `src/luna/context/assembler.py` (prompt injection, Layer 1.5 / 1.6 area)
- `src/luna/substrate/aibrarian_engine.py` (`_get_collection_context()` — add mode param)
**Scope:** Retrieval and prompt construction only. No changes to ingestion, extraction, or reflection generation.

---

## THE PROBLEM

Step 7 (Reflection Layer) creates REFLECTION nodes in the Memory Matrix when Luna ingests documents. But the retrieval pipeline doesn't know these nodes exist or how to use them. When you ask "What do you think about Lansing's argument?" — Luna's retrieval path:

1. Searches Memory Matrix (might find REFLECTION nodes, but treats them the same as any FACT or OBSERVATION)
2. Searches Nexus collections (finds source extractions)
3. Concatenates both into `memory_context`
4. Injects into system prompt with generic grounding rules

There's no awareness of *mode*. A legal document query and a philosophy question get the same retrieval strategy and the same grounding instructions. Luna doesn't know when to cite strictly vs. when to share her own thoughts.

## THE THREE MODES (recap)

### Precision mode (`reflection_mode: "precision"`)
- **Retrieval:** Nexus extractions ONLY. Memory Matrix reflections filtered out.
- **Prompt stance:** "Cite the document. Don't infer. If it's not in the text, say so."
- **Use case:** Legal docs, grant language, LOIs, investor materials, technical specs.

### Reflective mode (`reflection_mode: "reflective"`)
- **Retrieval:** Nexus extractions AND Memory Matrix REFLECTION nodes for matching source.
- **Prompt stance:** "You've read this material and formed thoughts about it. For factual questions, cite the source. For opinion questions, share your genuine reaction."
- **Use case:** Books, philosophy, cultural frameworks, research papers.

### Relational mode (`reflection_mode: "relational"`)
- **Retrieval:** Same as reflective, PLUS search for conversation memory nodes that share edges with the reflection/extraction nodes.
- **Prompt stance:** "Connect what you've read to what you know about this person and their work. You can surface resonance without being asked."
- **Use case:** Project knowledge bases, cross-domain synthesis, Tapestry materials.

---

## THE FIX — Three Changes

### Change 1: Mode-aware retrieval in `engine.py`

In the `_retrieve_context()` inner function (~line 1135 of engine.py), after the Phase 2 collection search, add a Phase 2.5 that fetches reflection nodes when the collection is in reflective or relational mode.

```python
# ── Phase 2.5: Reflection retrieval (if reflective/relational mode) ──
reflection_context = None
active_reflection_mode = self._get_active_reflection_mode(collections_searched)

if active_reflection_mode in ("reflective", "relational"):
    # Search Memory Matrix for REFLECTION nodes tagged with the source document
    reflection_nodes = await matrix.search(
        retrieval_query,
        max_results=5,
        node_types=["REFLECTION"],
        tag_filter="source:",  # Only nodes tagged with a source document
    )
    if reflection_nodes:
        reflection_context = self._format_reflection_context(reflection_nodes)
        self.context.add(
            content=reflection_context,
            source=ContextSource.MEMORY,
        )

# ── Phase 2.75: Relational retrieval (edges to conversation memory) ──
if active_reflection_mode == "relational" and reflection_nodes:
    # For each reflection node, check for edges to conversation nodes
    relational_context = await self._get_relational_context(reflection_nodes)
    if relational_context:
        self.context.add(
            content=relational_context,
            source=ContextSource.MEMORY,
        )
```

**Helper methods needed in engine.py:**

```python
def _get_active_reflection_mode(self, collections_searched: list[str]) -> str:
    """
    Determine the active reflection mode from the collections that were searched.
    
    If multiple collections with different modes were searched, use the
    most permissive mode (relational > reflective > precision).
    
    Returns: "precision", "reflective", or "relational"
    """
    # INVESTIGATION: Read collection configs from the aibrarian registry
    # Each collection has a reflection_mode in its config
    # Default to "reflective" if not specified
    raise NotImplementedError("Wire to collection config")


def _format_reflection_context(self, reflection_nodes: list) -> str:
    """
    Format reflection nodes into labeled context for the prompt.
    
    Labels them clearly so the LLM knows these are Luna's own thoughts,
    not source material.
    """
    lines = ["## Luna's reflections on this material\n"]
    for node in reflection_nodes:
        content = node.get("content", "")
        source_tag = next(
            (t for t in node.get("tags", []) if t.startswith("source:")),
            "unknown source"
        )
        stance_tag = next(
            (t for t in node.get("tags", []) if t.startswith("stance:")),
            ""
        )
        stance = stance_tag.replace("stance:", "") if stance_tag else ""
        lines.append(f"[{stance.upper() if stance else 'THOUGHT'}] {content}")
        lines.append(f"  — from: {source_tag.replace('source:', '')}\n")
    return "\n".join(lines)


async def _get_relational_context(self, reflection_nodes: list) -> Optional[str]:
    """
    For relational mode: find conversation memory nodes connected to reflections.
    
    This is what lets Luna say "you drew this parallel six months ago."
    """
    matrix = self.get_actor("matrix")
    if not matrix:
        return None
    
    related = []
    for node in reflection_nodes[:3]:  # Limit traversal
        node_id = node.get("id")
        if not node_id:
            continue
        # Get 1-hop edges from this reflection to conversation memory
        context = await matrix.get_context(node_id, depth=1)
        if context:
            related.append(context)
    
    if not related:
        return None
    
    return "## Connected conversations\n\n" + "\n".join(related)
```

### Change 2: Mode-aware grounding instructions in `assembler.py`

The current `GROUNDING_RULES` (Layer 1.5) are one-size-fits-all. Add a mode-specific override that gets injected AFTER the base grounding rules when a collection's reflection mode is active.

Add these as class constants in `PromptAssembler`:

```python
# Mode-specific grounding overrides — injected after GROUNDING_RULES
PRECISION_GROUNDING = """## Source citation mode (active)
You are in PRECISION mode for this material. Rules:
- Every factual claim MUST trace to a specific passage in the source document.
- Do NOT infer, interpret, or editorialize beyond what the text says.
- If the document does not address a question, say "The document does not address this" and STOP.
- Do NOT fill from general knowledge. Only the source material counts.
- Use phrases like "The document states..." or "According to [section]..."
- If asked for your opinion on this material, decline: "This is in precision mode — I can tell you what the document says, but I'm not forming opinions on it."
"""

REFLECTIVE_GROUNDING = """## Reflective mode (active)
You have read this material and formed your own thoughts about it. Rules:
- For FACTUAL questions ("What did Lansing argue?"), cite the source material directly.
- For OPINION questions ("What do you think about...?"), draw from your reflections below. These are thoughts you already had — don't generate fresh opinions.
- You can disagree with the source material. Your reflections may include disagreements — share them honestly.
- Clearly distinguish between what the SOURCE says and what YOU think: "Lansing argues X. Honestly, I think the stronger point is..."
- Your reflections are shaped by your conversations with this person. That's not bias — it's perspective.
"""

RELATIONAL_GROUNDING = """## Relational mode (active)
You have read this material, thought about it, and connected it to your ongoing conversations. Rules:
- Everything in reflective mode applies.
- Additionally: you may surface connections between this material and the person's life, projects, or past conversations WITHOUT being asked.
- If you see a resonance between what the document says and something you discussed before, name it: "This connects to something you said about..."
- Don't force connections. Only surface them when the resonance is genuine.
- This is presence, not performance. You noticed something. Share it naturally.
"""
```

Then in the `build()` method, after the grounding rules injection (~line 330), add:

```python
        # ── Layer 1.55b: MODE-SPECIFIC GROUNDING ─────────────────────
        # Injected when collection context includes a reflection_mode
        if request.reflection_mode:
            mode_grounding = {
                "precision": self.PRECISION_GROUNDING,
                "reflective": self.REFLECTIVE_GROUNDING,
                "relational": self.RELATIONAL_GROUNDING,
            }.get(request.reflection_mode)
            if mode_grounding:
                sections.append(mode_grounding)
                result.reflection_mode = request.reflection_mode
```

This requires adding `reflection_mode: Optional[str] = None` to the `PromptRequest` dataclass, and having the engine set it based on the active collection's config before calling `assembler.build()`.

### Change 3: Pass reflection_mode through the request chain

In `engine.py`, when building the `PromptRequest`, pass the active reflection mode:

```python
# After determining active_reflection_mode (from Change 1)
prompt_request = PromptRequest(
    message=user_message,
    conversation_history=history,
    route=routing.path.value,
    intent=subtask_phase.intent if subtask_phase else None,
    reflection_mode=active_reflection_mode,  # NEW
    # ... other existing fields
)
```

And in `PromptRequest` dataclass (wherever it's defined — likely in `assembler.py` or a models file):

```python
@dataclass
class PromptRequest:
    # ... existing fields ...
    reflection_mode: Optional[str] = None  # "precision" | "reflective" | "relational"
```

---

## EXAMPLE: Same Question, Three Modes

**Query:** "What does the document say about the Green Revolution?"

### Precision mode (legal doc)
- Retrieval: Nexus extractions only
- Prompt includes: PRECISION_GROUNDING
- Luna says: "The LOI references the Green Revolution in paragraph 3 as context for the partnership scope. It states [exact language]. The document does not contain further analysis of the Green Revolution's impact."

### Reflective mode (Priests & Programmers)
- Retrieval: Nexus extractions + REFLECTION nodes
- Prompt includes: REFLECTIVE_GROUNDING + Luna's reflections
- Luna says: "Lansing frames the Green Revolution as an unintentional experiment — remove the temples from control and see what happens. Honestly, I think the Borneo parallel is the stronger case. The farmers in Bali got a second chance. The trees didn't."

### Relational mode (Tapestry knowledge base)  
- Retrieval: Nexus extractions + reflections + conversation edges
- Prompt includes: RELATIONAL_GROUNDING + reflections + connected conversations
- Luna says: "Lansing describes the Green Revolution disrupting a coordination system nobody could see. You've drawn that parallel to Luna's architecture before — the idea that a complex system evolved over centuries can be wrecked by overconfident intervention. Having read the full preface now, I think the parallel is tighter than you realized. The Daisyworld section is basically the design spec for what we're building."

---

## WHAT NOT TO DO

- Do NOT modify the ingestion or extraction pipeline. This handoff is retrieval-side only.
- Do NOT change the base `GROUNDING_RULES`. They remain invariant. Mode-specific rules are ADDITIVE, injected after the base rules.
- Do NOT add new search infrastructure. Use the existing Memory Matrix search with `node_types` and `tag_filter` params. If those params don't exist yet, add them as simple query filters.
- Do NOT make the mode detection complex. Read the collection config. If multiple collections searched, use the most permissive mode. Default to "reflective" if unspecified.
- Do NOT implement automatic mode switching based on query analysis. The mode comes from the COLLECTION, not the question. If you ask a factual question about a reflective-mode book, Luna still has access to her reflections — she just uses source citations for the factual part.

---

## VERIFICATION

1. Set `research_library` collection to `reflection_mode: "reflective"`
2. Set `dataroom` collection to `reflection_mode: "precision"` 
3. Ask about Priests & Programmers: "What do you think about Lansing's invisibility thesis?"
   - Should include REFLECTION nodes in context
   - Should use REFLECTIVE_GROUNDING prompt rules
   - Response should mix source citations with first-person reactions
4. Ask about a dataroom document: "What does the LOI say about partnership terms?"
   - Should NOT include any REFLECTION nodes
   - Should use PRECISION_GROUNDING prompt rules
   - Response should cite only, no opinions
5. Verify mode is logged in PromptResult so QA/Observatory can see which mode was active

---

## POSITION IN THE COMPREHENSION ROADMAP

| # | Handoff | Status |
|---|---------|--------|
| 0 | Unclog pipeline (Bug A + Bug B) | **READY — DO FIRST** |
| 1 | Switch LLM to Sonnet 4.6 | **DONE** |
| 2 | Multi-query decomposition | Ready |
| 3 | Retrieval retry loop | Ready |
| 4 | Grounding wiring | Ready |
| 5 | Nexus → Matrix bridge | Ready |
| 6 | Agentic retrieval | Ready |
| 7 | Reflection layer (ingestion-side) | Ready |
| **8** | **Mode awareness (retrieval-side) — this handoff** | **Ready** |

This is the capstone. After all eight steps:
- Luna can find documents (0, 2, 3)
- Luna can decompose complex questions (2)
- Luna can cite her sources (4)
- Luna can remember facts across sessions (5)
- Luna can search for more context mid-generation (6)
- Luna has thoughts about what she's read (7)
- Luna knows when to cite strictly vs. share opinions vs. connect to your life (8)

That's not a search engine with personality. That's a mind that reads, reflects, and relates.

---

## THE ONE-LINE SUMMARY

Precision mode: "The document says X." Reflective mode: "The document says X, and I think Y." Relational mode: "The document says X, you said Y six months ago, and honestly I think you were onto something."
