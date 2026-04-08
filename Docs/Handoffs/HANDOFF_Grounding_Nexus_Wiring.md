# HANDOFF: Wire Nexus Extractions into Grounding

**Priority:** P2 — The scoreboard lies. Fixes the trust signal.  
**Status:** Ready for implementation  
**Depends on:** Nothing — works with current system  
**Target files:**
- `src/luna/engine.py` (return structured nodes from `_get_collection_context`)
- `src/luna/actors/director.py` (include Nexus nodes in `_last_injected_memories`)
**Scope:** Grounding pipeline only. No changes to retrieval, generation, or frontend.

---

## THE PROBLEM

When Luna answers "the book is about Bali's water temple system" using the DOCUMENT_SUMMARY extraction from Nexus, the grounding evaluator reports it as **0 grounded, 8 ungrounded, avg 0.19**.

The answer is correct. The scoreboard is wrong.

Here's why:

1. `_get_collection_context()` in engine.py searches Nexus and returns assembled text as a string
2. That string gets injected into `_build_system_prompt()` as free-form text
3. The engine sends the system prompt to the Director via mailbox Message
4. The Director resets `self._last_injected_memories = []` at the start of generation
5. The Director builds `grounding_nodes` from its own `_fetch_memory_context()` — **Memory Matrix only**
6. `GroundingLink.ground()` in server.py reads `director._last_injected_memories`
7. It compares Luna's response sentences against Memory Matrix nodes
8. Nexus extractions were never passed in → everything scores as "UNGROUNDED"

The GroundingLink algorithm itself works fine. The problem is it never receives the Nexus data.

## THE FIX — Two Changes

### Change 1: Return structured nodes from `_get_collection_context()`

Currently `_get_collection_context()` returns a `str`. Change it to also collect structured extraction objects and store them on the engine for the Director to access.

**In `src/luna/engine.py`, add a new instance variable** in `__init__` (or wherever engine state is initialized):

```python
self._last_nexus_nodes: list[dict] = []  # Structured Nexus extractions for grounding
```

**In `_get_collection_context()`, build the node list alongside the text assembly.**

Replace the merge/deduplicate block inside the per-collection loop. Currently:

```python
            # Merge (deduplicate by content)
            seen_content: set[str] = set()
            for row in list(sum_rows) + list(ext_rows):
                content = row[1] if isinstance(row, tuple) else row["content"]
                node_type = row[0] if isinstance(row, tuple) else row["node_type"]
                if content not in seen_content and char_budget > 0:
                    seen_content.add(content)
                    chunk = content[: char_budget]
                    parts.append(f"[Nexus/{key} {node_type}]\n{chunk}")
                    char_budget -= len(chunk)
```

Replace with:

```python
            # Merge (deduplicate by content) + collect structured nodes for grounding
            seen_content: set[str] = set()
            for row in list(sum_rows) + list(ext_rows):
                content = row[1] if isinstance(row, tuple) else row["content"]
                node_type = row[0] if isinstance(row, tuple) else row["node_type"]
                confidence = row[2] if isinstance(row, tuple) and len(row) > 2 else 0.85
                if content not in seen_content and char_budget > 0:
                    seen_content.add(content)
                    chunk = content[: char_budget]
                    parts.append(f"[Nexus/{key} {node_type}]\n{chunk}")
                    char_budget -= len(chunk)
                    
                    # Collect structured node for grounding
                    nexus_nodes.append({
                        "id": f"nexus:{key}:{node_type}:{len(nexus_nodes)}",
                        "content": content,
                        "node_type": node_type,
                        "source": f"nexus/{key}",
                        "confidence": confidence,
                    })
```

**Also collect chunk fallback nodes** in the Tier 3 section (the `if len(seen_content) < 2` block):

After appending to `parts`, also append to `nexus_nodes`:

```python
                    for r in chunk_results:
                        content = r.get("snippet") or r.get("content", "")
                        title = r.get("title") or r.get("filename", "")
                        if content and content not in seen_content and char_budget > 0:
                            seen_content.add(content)
                            chunk = content[: char_budget]
                            parts.append(f"[Nexus/{key} chunk: {title}]\n{chunk}")
                            char_budget -= len(chunk)
                            
                            # Collect for grounding
                            nexus_nodes.append({
                                "id": f"nexus:{key}:chunk:{len(nexus_nodes)}",
                                "content": content,
                                "node_type": "CHUNK",
                                "source": f"nexus/{key}",
                            })
```

**Initialize `nexus_nodes` at the top of the method** (right after `parts: list[str] = []`):

```python
        nexus_nodes: list[dict] = []
```

**Store the collected nodes before returning:**

```python
        # Store structured nodes for grounding
        self._last_nexus_nodes = nexus_nodes
        
        if not parts:
            return ""
        # ... rest of existing code
```

**Also do the same for `_get_collection_context_multi()`** (from Step 2). At the end, before returning:

```python
        # Aggregate nexus nodes from all sub-queries
        # (each call to _get_collection_context already populated self._last_nexus_nodes,
        #  but the last call overwrites. Collect them properly.)
```

Actually, the simpler approach: since `_get_collection_context_multi()` calls `_get_collection_context()` multiple times via `asyncio.gather`, each call overwrites `self._last_nexus_nodes`. Fix this by collecting the nodes differently:

```python
    async def _get_collection_context_multi(self, queries: list[str]) -> str:
        # ... existing code ...
        
        # Collect nexus nodes across all sub-queries
        all_nexus_nodes: list[dict] = []
        
        for query, result in zip(queries, results):
            # After each _get_collection_context call completes,
            # grab the nodes it collected
            all_nexus_nodes.extend(self._last_nexus_nodes)
        
        # Store combined nodes
        self._last_nexus_nodes = all_nexus_nodes
        
        # ... rest of existing code ...
```

**NOTE:** Since `asyncio.gather` runs concurrently, the `self._last_nexus_nodes` approach has a race condition. A cleaner approach: make `_get_collection_context()` return a tuple `(text, nodes)` instead of just `str`. But that requires changing every call site. The pragmatic fix: run the multi-query searches sequentially (they're fast since they're just SQLite queries) or collect nodes after all gather results are in by re-reading from each connection. 

**Simplest safe approach:** After gather completes, re-read `self._last_nexus_nodes` (it will have the nodes from the last sub-query). Then for the other sub-queries, the nodes are already deduplicated in the text assembly. This is imperfect but functional. The full fix (returning tuples) can come later.

### Change 2: Pass Nexus nodes to Director for grounding

**In `src/luna/engine.py`, in `_process_direct()`:**

Currently:
```python
        msg = Message(
            type="generate",
            payload={
                "user_message": user_message,
                "system_prompt": self._build_system_prompt(memory_context, history_context),
                "context_window": context_window,
            },
            correlation_id=correlation_id,
        )
```

Add the Nexus nodes:
```python
        msg = Message(
            type="generate",
            payload={
                "user_message": user_message,
                "system_prompt": self._build_system_prompt(memory_context, history_context),
                "context_window": context_window,
                "nexus_nodes": self._last_nexus_nodes,  # NEW: for grounding
            },
            correlation_id=correlation_id,
        )
```

**Do the same for `_process_with_agent_loop()` → `_run_agent_loop()`** (the planned path also sends to Director):

```python
                msg = Message(
                    type="generate",
                    payload={
                        "user_message": user_message,
                        "system_prompt": self._build_system_prompt(memory_context, history_context) + plan_context,
                        "context_window": context_window,
                        "agentic": True,
                        "execution_path": result.status.name,
                        "nexus_nodes": self._last_nexus_nodes,  # NEW
                    },
                    correlation_id=correlation_id,
                )
```

**In `src/luna/actors/director.py`, in `_handle_director_generate()`:**

After `self._last_injected_memories = []`, read the Nexus nodes from payload:

```python
        self._last_injected_memories = []  # Reset for GroundingLink
        nexus_nodes = payload.get("nexus_nodes", [])  # NEW: Nexus extractions from engine
```

Then, at the two places where `_last_injected_memories` gets populated with `grounding_nodes` (lines ~1882 and ~2562), append the Nexus nodes:

**Local generation path (~line 1882):**

```python
                self._last_injected_memories = grounding_nodes
```

Change to:

```python
                self._last_injected_memories = grounding_nodes + nexus_nodes
```

**Delegation path (~line 2562):**

```python
                self._last_injected_memories = grounding_nodes
```

Change to:

```python
                self._last_injected_memories = grounding_nodes + nexus_nodes
```

**Also handle the case where neither local nor delegation path runs** (e.g., direct generation without memory fetch). After the generation completes but before the method returns, add a safety net:

```python
        # Ensure Nexus nodes are always available for grounding
        if nexus_nodes and not any(
            n.get("source", "").startswith("nexus/") for n in self._last_injected_memories
        ):
            self._last_injected_memories.extend(nexus_nodes)
```

---

## HOW IT WORKS END-TO-END AFTER THE FIX

```
User: "What is Priests and Programmers about?"
  │
  ▼
Engine: _get_collection_context("Priests Programmers about")
  │
  ├── FTS5 finds DOCUMENT_SUMMARY extraction
  ├── Assembles text: "[Nexus/research_library DOCUMENT_SUMMARY]\n..."
  ├── Collects node: {id: "nexus:research_library:DOCUMENT_SUMMARY:0",
  │                    content: "Priests and Programmers examines...",
  │                    node_type: "DOCUMENT_SUMMARY", source: "nexus/research_library"}
  └── Stores in self._last_nexus_nodes
  │
  ▼
Engine: _process_direct() → Message payload includes nexus_nodes
  │
  ▼
Director: _handle_director_generate()
  │
  ├── Reads nexus_nodes from payload
  ├── Builds grounding_nodes from Memory Matrix (existing)
  ├── Sets _last_injected_memories = grounding_nodes + nexus_nodes
  └── Generates response: "it's about Bali's water temple system..."
  │
  ▼
Server: GroundingLink.ground(response_text, director._last_injected_memories)
  │
  ├── Sentence: "it's about Bali's water temple system"
  ├── Compares against nexus node: "Priests and Programmers examines..."
  ├── Token overlap: "bali", "water", "temple", "system" → HIGH overlap
  └── Verdict: GROUNDED (confidence 0.72)
  │
  ▼
Frontend: "4 grounded · 1 inferred · 3 ungrounded · avg 0.62"
```

---

## WHAT CHANGES IN THE UI

| Before | After |
|--------|-------|
| `0 grounded · 0 inferred · 8 ungrounded · avg 0.29` | `4 grounded · 2 inferred · 2 ungrounded · avg 0.58` |

The exact numbers depend on the query and which extractions are retrieved, but answers grounded in Nexus content will now correctly register as GROUNDED or INFERRED instead of UNGROUNDED.

**Luna can now see her own confidence.** If the grounding metadata is fed back into her context (future enhancement), she can distinguish "I know this from the text" from "I'm inferring this" — which is the precondition for genuine epistemic calibration.

---

## INTERACTION WITH STEPS 2 AND 3

- **Step 2 (Multi-Query Decomposition):** Each sub-query populates `self._last_nexus_nodes`. The multi-query method needs to aggregate them (see note about race condition above).
- **Step 3 (Retrieval Retry Loop):** All tiers (FTS5, expanded, semantic) contribute to `nexus_nodes` because the collection block in `_get_collection_context` runs them sequentially. No special handling needed.

---

## DO NOT

- Do NOT modify `GroundingLink` itself — the algorithm is correct, it just needs the data
- Do NOT change how `_build_system_prompt()` injects Nexus context as text — that's for the LLM, this is for the evaluator
- Do NOT modify the frontend grounding display — it already reads `groundingMetadata` from the broadcast
- Do NOT pass Nexus nodes as additional system prompt content — they're already in the prompt as text; the structured version is solely for grounding evaluation
- Do NOT remove the Memory Matrix nodes from grounding — both sources should be checked
- Do NOT attempt to deduplicate Memory Matrix and Nexus nodes in the grounding list — let GroundingLink pick the best match naturally

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

Test in Luna UI:

1. **"What is Priests and Programmers about?"**
   → Check grounding in the UI response metadata
   → Should show >= 2 GROUNDED sentences (was 0 before)
   → Backend logs: `[GROUNDING] 8 sentences: 4 grounded, 2 inferred, 2 ungrounded`

2. **"What is Chapter 2 about?"**
   → SECTION_SUMMARY and CLAIMs should register as grounding sources
   → avg confidence should be > 0.4 (was < 0.3)

3. **"Tell me something you don't know"** (negative control)
   → Should still show UNGROUNDED for hedging/inferring sentences
   → Grounding shouldn't inflate scores for content Luna doesn't have

4. Check backend logs for node counts:
   ```
   [GROUNDING] Local path: exposed 3 nodes    ← Memory Matrix (existing)
   # After fix, should also see Nexus nodes in the total
   ```

---

## ESTIMATED SCOPE

- ~15 lines new code in `engine.py` (collect `nexus_nodes` list, store on instance, pass in payload)
- ~10 lines modified in `engine.py` (add `nexus_nodes` to Message payloads)
- ~10 lines modified in `director.py` (read `nexus_nodes` from payload, append to grounding list)
- Zero new dependencies
- Zero schema changes
- Zero frontend changes
- Zero changes to GroundingLink algorithm
