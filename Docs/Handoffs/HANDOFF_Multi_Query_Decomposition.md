# HANDOFF: Multi-Query Decomposition for Nexus Retrieval

**Priority:** P1 — This is the single biggest reasoning upgrade Luna can get  
**Status:** Ready for implementation  
**Target files:**
- `src/luna/inference/subtasks.py` (new decompose subtask)
- `src/luna/engine.py` (modified `_retrieve_context` and `_get_collection_context`)
**Scope:** Retrieval pipeline only. No changes to generation, grounding, or frontend.

---

## THE PROBLEM

When a user asks "compare chapter 2 to chapter 3," the engine:

1. Runs ONE FTS5 keyword search with the full string: `"compare chapter 2 chapter 3"`
2. FTS5 returns whatever chunks happen to contain those words in proximity
3. The results are a random mix of both chapters (or neither)
4. The LLM generates a muddled comparison or gives up

Same problem for:
- "How does the Introduction differ from the Conclusion?"
- "What does Lansing say about pests in chapter 3 vs chapter 6?"
- "Tell me about water temples and then about the Green Revolution"
- "What are the key differences between subak autonomy and state control?"

All of these are **multi-part questions** that need **separate retrievals merged into one context window**. The current pipeline cannot do this. One query, one search, one shot.

## THE FIX — Two Changes

### Change 1: Query Decomposition in Subtask Runner

Add a `decompose_query` method to `LocalSubtaskRunner` in `src/luna/inference/subtasks.py`.

**Two-tier decomposition:** regex first (free, instant), Qwen fallback (for complex cases).

#### 1a. Add decomposition patterns (regex tier)

After the existing `DEICTIC_MARKERS` set, add:

```python
# ─── Query Decomposition Patterns ─────────────────────────────────────────

import re

# Patterns that indicate multi-part questions
COMPARISON_PATTERNS = [
    # "compare X to/with/and Y", "X vs Y", "X versus Y"
    re.compile(
        r"(?:compare|contrast|difference between)\s+(.+?)\s+(?:to|with|and|vs\.?|versus)\s+(.+)",
        re.IGNORECASE,
    ),
    # "X vs Y" (standalone)
    re.compile(
        r"(.+?)\s+(?:vs\.?|versus)\s+(.+)",
        re.IGNORECASE,
    ),
    # "how does X differ from Y" / "how is X different from Y"
    re.compile(
        r"how\s+(?:does|is|do|are)\s+(.+?)\s+(?:differ|different)\s+from\s+(.+)",
        re.IGNORECASE,
    ),
]

# Patterns for sequential multi-topic questions
MULTI_TOPIC_PATTERNS = [
    # "tell me about X and then Y" / "what about X and Y"
    re.compile(
        r"(?:tell me about|what about|explain)\s+(.+?)\s+(?:and then|and also|and)\s+(.+)",
        re.IGNORECASE,
    ),
]

# Chapter/section reference patterns
CHAPTER_PATTERN = re.compile(
    r"chapter\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten)",
    re.IGNORECASE,
)

CHAPTER_WORD_TO_NUM = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
}
```

#### 1b. Add the regex decomposition function

```python
def decompose_query_regex(message: str) -> list[str]:
    """
    Fast regex-based query decomposition.
    
    Returns a list of sub-queries. If the message doesn't match
    any decomposition pattern, returns [message] (single-element list).
    """
    # Check for chapter references first
    chapter_matches = CHAPTER_PATTERN.findall(message)
    if len(chapter_matches) >= 2:
        # Multiple chapters referenced — generate per-chapter queries
        queries = []
        # Extract the base question (remove chapter refs)
        base = CHAPTER_PATTERN.sub("", message).strip()
        base = re.sub(r"\s+", " ", base)  # collapse whitespace
        # Remove comparison words from base
        base = re.sub(
            r"^(compare|contrast|difference between|how does|how do|how is)\s*",
            "", base, flags=re.IGNORECASE,
        ).strip()
        # Remove trailing connector words
        base = re.sub(
            r"\s*(to|with|and|vs\.?|versus|differ from|different from)\s*$",
            "", base, flags=re.IGNORECASE,
        ).strip()
        
        for ch in chapter_matches:
            ch_num = CHAPTER_WORD_TO_NUM.get(ch.lower(), ch)
            queries.append(f"chapter {ch_num} {base}".strip())
        return queries
    
    # Check comparison patterns
    for pattern in COMPARISON_PATTERNS:
        match = pattern.search(message)
        if match:
            part_a = match.group(1).strip().rstrip(".,?!")
            part_b = match.group(2).strip().rstrip(".,?!")
            if part_a and part_b:
                return [part_a, part_b]
    
    # Check multi-topic patterns
    for pattern in MULTI_TOPIC_PATTERNS:
        match = pattern.search(message)
        if match:
            part_a = match.group(1).strip().rstrip(".,?!")
            part_b = match.group(2).strip().rstrip(".,?!")
            if part_a and part_b:
                return [part_a, part_b]
    
    # No decomposition needed
    return [message]
```

#### 1c. Add Qwen-based decomposition subtask (for complex cases)

Add a new prompt constant:

```python
DECOMPOSE_PROMPT = """Break this question into separate search queries that would each find different information. Return ONLY valid JSON on one line:
{{"queries":["first search query","second search query"]}}
If the question is simple and only needs one search, return {{"queries":["{message}"]}}
Question: {message}"""
```

Add a new method to `LocalSubtaskRunner`:

```python
    async def decompose_query(
        self, message: str, timeout_ms: int = 300,
    ) -> SubtaskResult:
        """
        Decompose a compound question into separate search queries.
        
        First tries regex decomposition (free, instant).
        Falls back to Qwen if regex returns a single query AND
        the message looks compound (contains comparison/contrast words).
        """
        # Tier 1: Regex decomposition
        regex_result = decompose_query_regex(message)
        if len(regex_result) > 1:
            return SubtaskResult(
                success=True,
                output={"queries": regex_result},
                raw_text=str(regex_result),
                latency_ms=0.0,
                task_name="decompose_query",
            )
        
        # Tier 2: Does the message LOOK compound but regex missed it?
        compound_signals = [
            "compare", "contrast", "difference", "differ", "vs",
            "versus", "similarities", "both", "each",
            "on one hand", "on the other",
        ]
        msg_lower = message.lower()
        looks_compound = any(signal in msg_lower for signal in compound_signals)
        
        if not looks_compound:
            # Simple question — no decomposition needed
            return SubtaskResult(
                success=True,
                output={"queries": [message]},
                raw_text=message,
                latency_ms=0.0,
                task_name="decompose_query",
            )
        
        # Tier 3: Qwen decomposition for complex compound questions
        prompt = DECOMPOSE_PROMPT.format(message=message)
        result = await self._run_with_timeout(
            "decompose_query", prompt, max_tokens=120, timeout_ms=timeout_ms,
        )
        if not result.success:
            # Fallback: return original as single query
            return SubtaskResult(
                success=True,
                output={"queries": [message]},
                raw_text=message,
                latency_ms=result.latency_ms,
                task_name="decompose_query",
            )
        
        parsed = self._parse_json(result.raw_text, "decompose_query")
        if parsed and "queries" in parsed and isinstance(parsed["queries"], list):
            queries = [q.strip() for q in parsed["queries"] if q.strip()]
            if queries:
                # Cap at 4 sub-queries to prevent context window explosion
                result.output = {"queries": queries[:4]}
                self._stats.setdefault("decompose_query", SubtaskStats()).successes += 1
                return result
        
        # Parse failed — return original
        return SubtaskResult(
            success=True,
            output={"queries": [message]},
            raw_text=message,
            latency_ms=result.latency_ms,
            task_name="decompose_query",
        )
```

#### 1d. Wire into `run_subtask_phase`

Add `decomposed_queries` to `SubtaskPhaseResult`:

```python
@dataclass
class SubtaskPhaseResult:
    """Aggregated results from running all subtasks in parallel."""
    intent: Optional[dict] = None
    entities: Optional[list] = None
    rewritten_query: Optional[str] = None
    decomposed_queries: Optional[list[str]] = None   # NEW
    total_latency_ms: float = 0.0
```

In `run_subtask_phase()`, add the decompose task to the parallel gather:

```python
    async def run_subtask_phase(
        self, message: str, recent_turns: Optional[list[str]] = None,
    ) -> SubtaskPhaseResult:
        if not self.is_available:
            # Even without Qwen, try regex decomposition (it's free)
            regex_queries = decompose_query_regex(message)
            result = SubtaskPhaseResult()
            if len(regex_queries) > 1:
                result.decomposed_queries = regex_queries
            return result

        start = time.perf_counter()

        # Fire all subtasks concurrently — now includes decompose
        intent_task = self.classify_intent(message)
        entity_task = self.extract_entities(message)
        rewrite_task = self.rewrite_query(message, recent_turns or [])
        decompose_task = self.decompose_query(message)    # NEW

        results = await asyncio.gather(
            intent_task, entity_task, rewrite_task, decompose_task,
            return_exceptions=True,
        )

        total_ms = (time.perf_counter() - start) * 1000

        phase = SubtaskPhaseResult(total_latency_ms=total_ms)

        intent_result = results[0] if not isinstance(results[0], Exception) else None
        entity_result = results[1] if not isinstance(results[1], Exception) else None
        rewrite_result = results[2] if not isinstance(results[2], Exception) else None
        decompose_result = results[3] if not isinstance(results[3], Exception) else None    # NEW

        if intent_result and intent_result.success:
            phase.intent = intent_result.output

        if entity_result and entity_result.success:
            phase.entities = entity_result.output.get("entities", []) if entity_result.output else []

        if rewrite_result and rewrite_result.success and rewrite_result.output != message:
            phase.rewritten_query = rewrite_result.output

        # NEW: decomposed queries
        if decompose_result and decompose_result.success:
            queries = decompose_result.output.get("queries", [message])
            if len(queries) > 1:
                phase.decomposed_queries = queries

        logger.info(
            f"[SUBTASK-PHASE] Complete in {total_ms:.0f}ms: "
            f"intent={'yes' if phase.intent else 'no'} "
            f"entities={len(phase.entities) if phase.entities else 0} "
            f"rewritten={'yes' if phase.rewritten_query else 'no'} "
            f"decomposed={len(phase.decomposed_queries) if phase.decomposed_queries else 1}"
        )

        return phase
```

**IMPORTANT:** Also add `"decompose_query": SubtaskStats()` to the `self._stats` dict in `__init__`.

Also: note that `decompose_query_regex()` runs even when Qwen is unavailable (see the `if not self.is_available` early return in `run_subtask_phase`). This means regex decomposition works on every machine, regardless of whether Qwen is loaded.

---

### Change 2: Multi-Query Retrieval in Engine

Modify `_retrieve_context()` in `src/luna/engine.py` to use decomposed queries for Nexus retrieval.

**Current code** (around line 1045):

```python
                # Phase 2: search chain for active project collections
                collection_context = await self._get_collection_context(retrieval_query)
```

**Replace with:**

```python
                # Phase 2: search chain for active project collections
                # Use decomposed queries if available (multi-part questions)
                if subtask_phase and subtask_phase.decomposed_queries:
                    collection_context = await self._get_collection_context_multi(
                        subtask_phase.decomposed_queries
                    )
                else:
                    collection_context = await self._get_collection_context(retrieval_query)
```

**Add the new method** after `_get_collection_context()`:

```python
    async def _get_collection_context_multi(self, queries: list[str]) -> str:
        """
        Run multiple retrieval queries and merge results.
        
        For compound questions like "compare chapter 2 to chapter 3",
        this runs separate searches for each sub-query and assembles
        them into labeled sections so the LLM can reason across both.
        """
        if not queries:
            return ""
        
        # Cap at 4 queries to prevent context explosion
        queries = queries[:4]
        
        # Run all queries concurrently
        import asyncio
        tasks = [self._get_collection_context(q) for q in queries]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Assemble with labels
        parts: list[str] = []
        seen_content: set[str] = set()  # Deduplicate across queries
        
        for query, result in zip(queries, results):
            if isinstance(result, Exception):
                logger.warning(f"[MULTI-QUERY] Failed for '{query}': {result}")
                continue
            if not result:
                continue
            
            # Deduplicate: skip fragments we've already seen
            new_fragments = []
            for line in result.split("\n\n"):
                # Use first 100 chars as dedup key
                key = line.strip()[:100]
                if key and key not in seen_content:
                    seen_content.add(key)
                    new_fragments.append(line)
            
            if new_fragments:
                section = "\n\n".join(new_fragments)
                parts.append(f"[Query: {query}]\n{section}")
        
        if not parts:
            return ""
        
        assembled = "\n\n---\n\n".join(parts)
        logger.info(
            f"[MULTI-QUERY] {len(queries)} queries → {len(parts)} result sections, "
            f"{len(assembled)} chars"
        )
        return assembled
```

---

## HOW IT WORKS END-TO-END

### Before (current):
```
User: "Compare chapter 2 to chapter 6"
  → SubtaskPhase: rewritten_query = "Compare chapter 2 to chapter 6" (no change)
  → _get_collection_context("Compare chapter 2 to chapter 6")
  → FTS5 MATCH "compare chapter 2 chapter 6"
  → Random mix of results (or nothing)
  → LLM generates from whatever landed
```

### After (with this fix):
```
User: "Compare chapter 2 to chapter 6"
  → SubtaskPhase: decomposed_queries = ["chapter 2", "chapter 6"]
  → _get_collection_context_multi(["chapter 2", "chapter 6"])
    → _get_collection_context("chapter 2")
      → FTS5: WATER CONTROL, WATER TEMPLES, SOCIAL CONTROL extractions
    → _get_collection_context("chapter 6")
      → FTS5: GREEN REVOLUTION, ECOLOGICAL MODELING, REEVALUATION extractions
  → Assembled as labeled sections:
      [Query: chapter 2]
      [Nexus/research_library SECTION_SUMMARY] This section from 'WATER CONTROL'...
      [Nexus/research_library CLAIM] The timing of irrigation is the key...

      ---

      [Query: chapter 6]
      [Nexus/research_library SECTION_SUMMARY] This section discusses the Green Revolution...
      [Nexus/research_library CLAIM] Modernization failed because it treated water temples...
  → LLM sees BOTH chapters, clearly labeled, and can actually compare them
```

---

## WHAT THIS CATCHES

| Question Pattern | Decomposition | Method |
|------------------|--------------|--------|
| "Compare chapter 2 to chapter 3" | ["chapter 2", "chapter 3"] | Regex (chapter refs) |
| "Chapter 2 vs chapter 6" | ["chapter 2", "chapter 6"] | Regex (chapter refs) |
| "How does the Introduction differ from the Conclusion?" | ["Introduction", "Conclusion"] | Regex (comparison) |
| "Water temples and the Green Revolution" | ["water temples", "Green Revolution"] | Regex (multi-topic) |
| "What are the similarities and differences between subak autonomy and state control?" | ["subak autonomy", "state control"] | Qwen (complex) |
| "What is chapter 2 about?" | ["chapter 2 about"] | No decomposition (single query) |
| "Tell me about the book" | No decomposition | No decomposition |

---

## INTERACTION WITH QUERY REWRITING

The subtask runner produces both `rewritten_query` and `decomposed_queries`. The priority in `_retrieve_context()` is:

1. If `decomposed_queries` exists (len > 1) → use `_get_collection_context_multi()`
2. Else if `rewritten_query` exists → use `_get_collection_context(rewritten_query)`
3. Else → use `_get_collection_context(user_message)`

Query rewriting resolves vague references ("that book" → "Priests and Programmers").  
Query decomposition splits compound questions into parallel searches.  
They're complementary — rewriting fixes the query, decomposition multiplies it.

**Note:** The decomposition runs on the ORIGINAL user_message, not the rewritten query. This is intentional — Qwen's rewrite might collapse a compound question into a single topic. Decomposition should see the original structure.

---

## CONTEXT BUDGET

Each sub-query gets the full 6000-char budget in `_get_collection_context()`. With 2 queries, that's up to 12,000 chars of Nexus context. The LLM's context window can handle this — Sonnet 4.6 has 200K tokens. But if budget becomes a concern:

```python
# In _get_collection_context_multi, divide budget across queries:
per_query_budget = 6000 // len(queries)
# Pass budget to _get_collection_context (requires adding a budget param)
```

This is an optimization, not a blocker. Skip for now.

---

## DO NOT

- Do NOT modify `_get_collection_context()` itself — it stays as-is for single queries
- Do NOT apply query rewriting to decomposed sub-queries — they're already specific
- Do NOT decompose into more than 4 sub-queries — context explosion risk
- Do NOT run decomposition for simple questions — the regex check and compound signal detection prevent this
- Do NOT make Qwen decomposition required — regex works without Qwen loaded, and the Qwen path is a refinement
- Do NOT change the Memory Matrix retrieval — it still uses the single `retrieval_query` (rewritten or original). Decomposition is Nexus-only for now.

---

## VERIFICATION

After implementation:

```bash
# Restart backend
pkill -f "scripts/run.py"
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
PYTHONPATH=src .venv/bin/python scripts/run.py --server --host 0.0.0.0 --port 8000 &
sleep 15
```

Test in the Luna UI:

1. **"Compare chapter 2 to chapter 6"**
   → Backend logs should show: `[MULTI-QUERY] 2 queries → 2 result sections`
   → Luna should discuss WATER CONTROL vs GREEN REVOLUTION

2. **"How does the Introduction differ from the Conclusion?"**
   → Two separate retrievals merged
   → Luna should contrast the opening framing with the synthesis

3. **"What is chapter 2 about?"** (single query — should NOT decompose)
   → Backend logs should NOT show `[MULTI-QUERY]`
   → Normal single-query path

4. **"Tell me about water temples and the Green Revolution"**
   → Should decompose into ["water temples", "Green Revolution"]
   → Luna gets both topics in context

5. Check subtask stats via MCP or logs:
   ```
   [SUBTASK-PHASE] Complete in 180ms: intent=yes entities=0 rewritten=no decomposed=2
   ```

---

## ESTIMATED SCOPE

- ~80 lines new code in `subtasks.py` (regex patterns + decompose method)
- ~30 lines new code in `engine.py` (`_get_collection_context_multi` + call site)
- ~5 lines modified in `subtasks.py` (SubtaskPhaseResult dataclass + run_subtask_phase)
- ~3 lines modified in `engine.py` (conditional in `_retrieve_context`)
- Zero new dependencies
- Zero schema changes
- Zero frontend changes
- Works with or without Qwen loaded (regex tier is always available)
