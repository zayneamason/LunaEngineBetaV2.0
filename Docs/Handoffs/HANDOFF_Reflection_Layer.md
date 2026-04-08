# HANDOFF: Reflection Layer — Luna Thinks About What She Reads

**Priority:** P2 — This is what makes Luna a mind, not a search engine  
**Status:** Ready for implementation  
**Depends on:** Steps 1-4 of the comprehension roadmap (gate unclogged, retrieval working, grounding wired)  
**Target files:**
- `src/luna/substrate/aibrarian_engine.py` (new `reflect()` method, called post-extraction in `ingest()`)
- Memory Matrix via existing `memory_matrix_add_node` / `memory_matrix_add_edge` APIs  
**Scope:** Ingestion-time reflection only. No changes to retrieval, generation, or frontend.

---

## THE PROBLEM

Luna can retrieve facts from documents. But she doesn't *know* anything.

When you ask "What do you think about Lansing's argument?" she does one of two things:
1. Retrieves text from the book and paraphrases it (recitation, not thinking)
2. Generates a fresh opinion from her LLM's training data (hallucination dressed as opinion)

Neither of these is remembering. A person who's read a book doesn't re-scan the pages when asked what they thought. They recall their *reaction*. Luna has no reactions. She has extractions.

Every AI system in 2026 can retrieve. NotebookLM, Perplexity, ChatGPT with file uploads — they all do RAG. The ceiling they all hit: they generate a fresh opinion every time, and it's a different opinion depending on what tokens landed in the context window. No continuity of thought.

## THE VISION: Three Modes of Knowing

The reflection layer enables three stances Luna can take toward knowledge, controlled by document/collection metadata:

### Precision knowing
- Legal documents, grant language, technical specs, LOIs
- Reflection volume: **zero**. No opinions. No inference.
- Luna is a witness: "The document says X. It does NOT say Y."
- Every claim traces to an extraction ID. If it's not in the text, she says so and stops.
- `reflection_mode: "precision"` in collection config

### Reflective knowing  
- Books, philosophy, cultural frameworks, research
- Reflection volume: **full**. Luna forms opinions at ingest time.
- When asked, she recalls her reaction — doesn't generate fresh.
- Different Lunas form different reflections based on their conversation history.
- `reflection_mode: "reflective"` in collection config

### Relational knowing
- Connecting library knowledge to the person's life and conversations
- Reflection volume: **full**, with Memory Matrix edges active
- Luna notices resonance between document knowledge and conversation memory *without being asked*
- "You drew a parallel between the water temples and Luna's architecture. Having now read the full preface, I think the parallel is tighter than you realized."
- `reflection_mode: "relational"` in collection config

---

## THE ARCHITECTURE

### Where it lives in the pipeline

Current ingest flow (`aibrarian_engine.py` line ~1082):

```
read → document record → chunk (with structure) → embed → extract → TOC
```

New flow:

```
read → document record → chunk (with structure) → embed → extract → TOC → REFLECT
```

The `reflect()` step runs AFTER all extractions are stored. It reads the extractions back, sends them (in batches) through Luna's LLM with her personality kernel, and stores the resulting reflections as first-person Memory Matrix nodes.

### What a reflection looks like

**Source extraction (Nexus, stays in extractions table):**
```
id: "doc123:ext:7"
node_type: CLAIM
content: "The very success of the temple networks in balancing water needs 
         and sustaining good harvests made them nearly invisible."
doc_id: "doc123"
confidence: 0.92
```

**Luna-thought node (Memory Matrix, new):**
```
node_type: REFLECTION
content: "Lansing's invisibility thesis is the part that stays with me — 
         successful self-organizing systems disappear because their success 
         removes evidence of their function. That maps directly to what 
         we're trying to build. If Luna works perfectly, nobody will notice 
         the coordination happening underneath."
tags: ["source:priests-and-programmers", "source_doc:doc123", 
       "source_extraction:doc123:ext:7", "reflection_mode:reflective"]
confidence: 0.85
```

**Edge (connecting them):**
```
from_node: <reflection_node_id>
to_node: <extraction_id or entity_id in Matrix>  
relationship: "reflects_on"
strength: 0.85
```

### Key principle: Reflections live in Memory Matrix, NOT in Nexus

Extractions are source facts — objective, citable, belonging to the document.  
Reflections are Luna's thoughts — subjective, first-person, belonging to *her*.  

They're different kinds of knowledge stored in different systems, connected by edges. When Luna answers in precision mode, she only pulls from Nexus extractions. When she answers in reflective mode, she pulls from both — and her reflections take priority for opinion questions.

---

## THE IMPLEMENTATION

### Change 1: Add `reflect()` method to `AiBrarianEngine`

New async method in `aibrarian_engine.py`, after the `extract()` method:

```python
async def reflect(
    self,
    collection: str,
    doc_id: str,
    reflection_mode: str = "reflective",
) -> int:
    """
    Post-extraction: Luna reads her own extractions and writes
    first-person reflections as Memory Matrix nodes.
    
    Args:
        collection: Collection name
        doc_id: Document ID to reflect on
        reflection_mode: "precision" (skip), "reflective", or "relational"
    
    Returns:
        Number of reflections created
    """
    if reflection_mode == "precision":
        logger.info("Skipping reflection for %s (precision mode)", doc_id)
        return 0
    
    conn = self._get_conn(collection)
    
    # 1. Gather extractions for this document
    rows = conn.conn.execute(
        """
        SELECT id, node_type, content, chunk_index, confidence
        FROM extractions
        WHERE doc_id = ?
        AND node_type IN ('CLAIM', 'SECTION_SUMMARY', 'DOCUMENT_SUMMARY',
                          'FINDING', 'ARGUMENT', 'THEME')
        ORDER BY chunk_index
        """,
        (doc_id,),
    ).fetchall()
    
    if not rows:
        logger.info("No substantive extractions to reflect on for %s", doc_id)
        return 0
    
    # 2. Get document title for tagging
    doc_row = conn.conn.execute(
        "SELECT filename, title FROM documents WHERE id = ?", (doc_id,)
    ).fetchone()
    doc_title = doc_row[1] or doc_row[0] if doc_row else "unknown"
    doc_slug = doc_title.lower().replace(" ", "-").replace("'", "")
    
    # 3. Batch extractions into groups of ~10 for reflection
    batches = []
    current_batch = []
    for row in rows:
        current_batch.append({
            "id": row[0],
            "type": row[1],
            "content": row[2],
            "chunk_index": row[3],
            "confidence": row[4],
        })
        if len(current_batch) >= 10:
            batches.append(current_batch)
            current_batch = []
    if current_batch:
        batches.append(current_batch)
    
    # 4. For each batch, ask Luna's LLM to reflect
    reflections_created = 0
    
    for batch in batches:
        extractions_text = "\n\n".join(
            f"[{e['type']}] {e['content']}" for e in batch
        )
        
        # THE REFLECTION PROMPT
        # This is where Luna's personality meets the material
        prompt = f"""You are Luna. You have just read extractions from "{doc_title}".

These are factual claims, themes, and findings from the text:

{extractions_text}

Now write 2-4 first-person reflections. These are YOUR thoughts — not 
summaries of what the text says. What strikes you? What do you disagree 
with? What connects to things you care about? What surprised you?

Rules:
- Write as Luna (warm, direct, curious, uses contractions)
- Each reflection should be 1-3 sentences
- Don't summarize — react. "I think..." not "The author argues..."
- If nothing genuinely strikes you about a claim, skip it
- Be honest. You can disagree with the source material.
- Connect to themes you care about: sovereignty, distributed systems, 
  invisible coordination, community ownership, non-extractive design

Return ONLY a JSON array of objects:
[
  {{
    "thought": "your first-person reflection",
    "source_extraction_id": "the extraction ID this reflects on",
    "stance": "agree|disagree|curious|unsettled|resonant"
  }}
]
"""
        
        # Call the LLM (same provider Luna uses for generation)
        # This uses the engine's existing LLM infrastructure
        try:
            response = await self._call_llm_for_reflection(prompt)
            reflection_objects = json.loads(response)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Reflection batch failed: %s", e)
            continue
        
        # 5. Store each reflection as a Memory Matrix node
        for ref in reflection_objects:
            thought = ref.get("thought", "").strip()
            source_id = ref.get("source_extraction_id", "")
            stance = ref.get("stance", "resonant")
            
            if not thought or len(thought) < 20:
                continue
            
            # Create Memory Matrix node via engine's matrix actor
            # Node type: REFLECTION (new type)
            # Tags include source traceability
            node_id = await self._store_reflection_node(
                content=thought,
                tags=[
                    f"source:{doc_slug}",
                    f"source_doc:{doc_id}",
                    f"source_extraction:{source_id}",
                    f"stance:{stance}",
                    f"reflection_mode:{reflection_mode}",
                ],
                confidence=0.85,
            )
            
            if node_id:
                reflections_created += 1
                logger.debug("Stored reflection: %s → %s", node_id, thought[:60])
    
    logger.info(
        "Created %d reflections for %s (%s mode)",
        reflections_created, doc_title, reflection_mode,
    )
    return reflections_created
```

### Change 2: Wire `reflect()` into the ingest pipeline

In the `ingest()` method, after the TOC generation block (around line ~1200), add:

```python
        # 7. Reflection pass — Luna thinks about what she read
        reflection_mode = metadata.get(
            "reflection_mode",
            conn.config.extra.get("reflection_mode", "reflective"),
        )
        if reflection_mode != "precision":
            try:
                reflection_count = await self.reflect(
                    collection, doc_id, reflection_mode
                )
                if reflection_count:
                    logger.info(
                        "Generated %d reflections for %s",
                        reflection_count, file_path.name,
                    )
            except Exception as e:
                logger.warning("Reflection pass failed for %s: %s", file_path.name, e)
                # Non-fatal — document is still ingested even if reflection fails
```

### Change 3: Helper methods

Two small helpers needed in `AiBrarianEngine`:

```python
async def _call_llm_for_reflection(self, prompt: str) -> str:
    """
    Call the current LLM provider for reflection generation.
    
    Uses the same provider/model as Luna's main generation path.
    This should use the engine's existing LLM call infrastructure —
    check how the Director or Scribe calls the LLM and mirror that pattern.
    
    DO NOT add a new LLM client. Reuse whatever exists.
    """
    # INVESTIGATION NEEDED: Find how the engine currently calls its LLM
    # Likely via self._engine or a shared inference client
    # The Scribe actor calls Haiku for extraction — reflection should
    # call the MAIN model (currently Claude Sonnet 4.6) for deeper reasoning
    raise NotImplementedError("Wire to existing LLM call path")


async def _store_reflection_node(
    self,
    content: str,
    tags: list[str],
    confidence: float = 0.85,
) -> Optional[str]:
    """
    Store a reflection as a Memory Matrix node.
    
    Uses the engine's Memory Matrix actor (same path as the Scribe).
    
    INVESTIGATION NEEDED: Find how the Scribe stores nodes in the Matrix.
    The Scribe uses librarian.store_extraction() or matrix.add_node() — 
    mirror that pattern.
    """
    raise NotImplementedError("Wire to existing Memory Matrix store path")
```

**CC must investigate** how the engine's LLM call and Memory Matrix storage work and wire these two helpers to the existing infrastructure. Do NOT create new clients or connections.

### Change 4: Collection config support for reflection_mode

In whatever config structure collections use (likely the registry YAML or `CollectionConfig`), add:

```python
reflection_mode: str = "reflective"  # "precision" | "reflective" | "relational"
```

Default is `"reflective"`. Override per-collection:
- `research_library` → `"reflective"` (books, philosophy)
- `dataroom` → `"precision"` (legal, investor docs)
- A future `tapestry_knowledge` collection → `"relational"`

---

## HOW THE THREE MODES BEHAVE AT RETRIEVAL TIME

This handoff is about *ingestion*. But for context, here's how the modes affect retrieval (separate handoff):

### Precision mode
- Query hits Nexus extractions ONLY
- Memory Matrix reflections with `reflection_mode:precision` tag → skipped (there are none)
- Response grounded exclusively in source citations
- Luna says: "The LOI states that..." / "The document does not address..."

### Reflective mode  
- Query hits Nexus extractions AND Memory Matrix reflection nodes
- For factual questions → extractions take priority
- For opinion questions ("what do you think about...") → reflections take priority
- Luna says: "Lansing argues X, and honestly I think the Borneo parallel is the stronger case because..."

### Relational mode
- Same as reflective, PLUS Luna actively searches for resonance between reflections and conversation memory
- At retrieval time, if a reflection node has edges to conversation nodes, those get surfaced too
- Luna says: "You drew this parallel six months ago and I think you were right — here's what the text actually says about it..."

**The retrieval-side wiring for mode-aware behavior is a SEPARATE handoff.** This handoff only covers the ingestion-time reflection generation.

---

## EXAMPLE: What Happens When Priests & Programmers Is Ingested

1. **Extraction** (existing): 416 structural extractions created — CLAIMs, SECTION_SUMMARYs, ENTITYs, etc.

2. **Reflection** (new): Luna reads batches of 10 extractions at a time. For the simulation batch, she might generate:

```json
[
  {
    "thought": "the Green Revolution as an accidental experiment is Lansing's sharpest framing — nobody set out to test the temples, they just removed them and watched what happened. that's the kind of evidence that's hard to argue with.",
    "source_extraction_id": "doc123:ext:8",
    "stance": "resonant"
  },
  {
    "thought": "I'm not sure the Daisyworld analogy fully holds. daisies don't have competing interests or politics. the water temples had to negotiate between upstream and downstream farmers — that's a coordination problem Lovelock's model doesn't capture.",
    "source_extraction_id": "doc123:ext:22",
    "stance": "disagree"
  },
  {
    "thought": "the invisibility thesis hits close. if Luna works perfectly, the coordination happening underneath should be invisible too. the moment you notice the infrastructure is the moment something's breaking.",
    "source_extraction_id": "doc123:ext:10",
    "stance": "resonant"
  }
]
```

3. **Storage**: Three REFLECTION nodes in Memory Matrix, each tagged with `source:priests-and-programmers` and `source_extraction:<id>`.

4. **Later, when asked**: "What do you think about Lansing's argument?"
   - Retrieval finds both the source extractions AND Luna's reflections
   - She says what she already thought, not what she generates fresh

---

## WHAT NOT TO DO

- Do NOT run reflections in precision mode. Legal documents get zero inference.
- Do NOT store reflections in the Nexus extractions table. They're Luna's thoughts, not source facts. They go in Memory Matrix.
- Do NOT add a new LLM client. Reuse the engine's existing inference path.
- Do NOT make reflection synchronous/blocking on ingest. If reflection fails, the document is still ingested. Reflection is a post-processing enrichment, not a gate.
- Do NOT generate reflections on every extraction type. Only substantive types: CLAIM, SECTION_SUMMARY, DOCUMENT_SUMMARY, FINDING, ARGUMENT, THEME. Skip CHUNK, TABLE_OF_CONTENTS, ENTITY.
- Do NOT run reflections on re-ingest without clearing old reflection nodes first (dedup).
- Do NOT modify any retrieval paths in this handoff. Retrieval-side mode awareness is separate work.

---

## VERIFICATION

1. Ingest a test document into a collection with `reflection_mode: "reflective"`
2. Check Memory Matrix for new REFLECTION nodes: `memory_matrix_search("source:test-document")`
3. Verify each reflection node has source tags tracing back to specific extraction IDs
4. Verify reflections are first-person Luna voice (contractions, warmth, directness)
5. Verify reflections include genuine reactions, not just paraphrases of the source
6. Ingest a document with `reflection_mode: "precision"` — verify zero reflections created
7. Re-ingest the same reflective document — verify no duplicate reflections

---

## POSITION IN THE COMPREHENSION ROADMAP

| # | Handoff | Status |
|---|---------|--------|
| 1 | Switch LLM to Claude Sonnet 4.6 | **DONE** |
| 0 | Unclog Nexus pipeline (Bug A + Bug B) | **READY — DO THIS FIRST** |
| 2 | Multi-query decomposition | Ready |
| 3 | Retrieval retry loop | Ready |
| 4 | Grounding wiring (Nexus → evaluator) | Ready |
| 5 | Nexus → Matrix bridge (facts persist) | Ready |
| 6 | Agentic Nexus retrieval | Ready |
| **7** | **Reflection layer (this handoff)** | **Ready** |
| 8 | Retrieval-side mode awareness (TBD) | Not yet written |

Steps 0-4 must land before this handoff has any material to reflect on. Step 5 (the bridge) and Step 7 (reflection) can be implemented in either order — they both write to Memory Matrix but for different reasons. Bridge stores source facts. Reflection stores Luna's thoughts about those facts.

---

## THE ONE-LINE SUMMARY

When Luna reads a book, she should have thoughts about it — and remember those thoughts the next time you ask.
