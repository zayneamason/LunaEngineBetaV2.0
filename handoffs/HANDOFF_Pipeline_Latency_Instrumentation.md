# HANDOFF: Pipeline Latency Instrumentation

**Priority:** HIGH — 10-20s TTFT despite LLM inference taking only 1.4s
**Scope:** Add timing checkpoints to every pipeline stage, identify bottleneck, optimize
**Project Root:** `/Users/oracle/Projects/_LunaEngine_BetaProject_V2.0_Root`

---

## THE PROBLEM

Luna's TTFT is 10-20 seconds. Benchmarks show:

| Component | Measured time |
|-----------|--------------|
| Memory search (SQLite) | 7ms |
| Intent routing (qwen3:8b, warm) | ~0.5s |
| Main inference (qwen3:30b-a3b, 6K ctx, warm) | ~0.9s |
| **Total LLM + retrieval** | **1.4s** |
| **Actual Luna turn** | **10-20s** |
| **Unaccounted overhead** | **8-18s** |

Both Ollama models stay loaded in memory (28GB of 48GB used). No model swapping.
The bottleneck is NOT the LLM. It's somewhere in the orchestration pipeline.

There are two entry paths:

**`/persona/stream` (UI path):** constellation prefetch → search chain → L1 ring population → Nexus collection context → director.generate

**`/message` (API path):** subtask runner (parallel) + _retrieve_context (sequential: history → load_conversation → matrix.get_context → collection_context → reflection → relational) → route → entity hints → director.generate

The `_get_collection_context` function runs 5 tiers sequentially (FTS5 extractions → FTS5 full text → semantic embeddings → chunks → reflections) **per collection**. With 3+ collections, this could be 15+ sequential DB operations.

---

## PHASE 1: INSTRUMENT

Add `time.time()` checkpoints at every stage boundary. Use a consistent format so we can grep and parse.

### 1A. Instrument `_process_message_agentic` in engine.py

Around lines 1067-1360, wrap each phase:

```python
import time as _time

async def _process_message_agentic(self, user_message, correlation_id, source="text", _db_retry=0):
    _t0 = _time.time()
    _timings = {}

    # ... existing preamble ...

    # PHASE 1: Subtask + retrieval
    _t1 = _time.time()
    # ... subtask runner code ...
    _timings["subtask_runner"] = _time.time() - _t1

    _t2 = _time.time()
    memory_context, history_context = await _retrieve_context()
    _timings["retrieve_context_total"] = _time.time() - _t2

    # PHASE 2: Route
    _t3 = _time.time()
    # ... routing code ...
    _timings["routing"] = _time.time() - _t3

    # PHASE 3: Entity hints
    _t4 = _time.time()
    # ... scribe entity code ...
    _timings["entity_hints"] = _time.time() - _t4

    # PHASE 4: Director generate
    _t5 = _time.time()
    # ... _process_direct or _process_with_agent_loop ...
    _timings["director_generate"] = _time.time() - _t5

    # PHASE 5: Bridge
    _t6 = _time.time()
    # ... bridge code ...
    _timings["bridge_nexus"] = _time.time() - _t6

    _total = _time.time() - _t0
    _timings["total"] = _total

    logger.warning(
        "[PIPELINE-TIMING] total=%.1fs | %s",
        _total,
        " | ".join(f"{k}={v:.3f}s" for k, v in sorted(_timings.items(), key=lambda x: -x[1]))
    )
```

### 1B. Instrument `_retrieve_context` inner function

Inside the `_retrieve_context` async function (around line 1113):

```python
async def _retrieve_context():
    _rt = {}
    _rt0 = _time.time()

    _t = _time.time()
    history_context = await history_manager.build_history_context(user_message)
    _rt["history_build"] = _time.time() - _t

    _t = _time.time()
    await self._load_conversation_history(matrix, limit=10)
    _rt["load_conv_history"] = _time.time() - _t

    _t = _time.time()
    # ... inner_matrix.get_context() ...
    _rt["matrix_get_context"] = _time.time() - _t

    _t = _time.time()
    # ... _get_collection_context() ...
    _rt["collection_context"] = _time.time() - _t

    _t = _time.time()
    # ... reflection FTS5 search ...
    _rt["reflection_search"] = _time.time() - _t

    _t = _time.time()
    # ... relational context ...
    _rt["relational_context"] = _time.time() - _t

    _rt["retrieve_total"] = _time.time() - _rt0

    logger.warning(
        "[RETRIEVE-TIMING] total=%.1fs | %s",
        _rt["retrieve_total"],
        " | ".join(f"{k}={v:.3f}s" for k, v in sorted(_rt.items(), key=lambda x: -x[1]))
    )

    return memory_context, history_context
```

### 1C. Instrument `_get_collection_context` (the 5-tier search)

Around line 1845. This is the most likely bottleneck — 5 tiers × N collections:

```python
async def _get_collection_context(self, query, *, subtask_phase=None):
    _ct = {}
    _ct0 = _time.time()

    # Per-collection timing
    for key in collections_to_search:
        _ck = _time.time()

        # Tier 1: FTS5 extractions
        _t = _time.time()
        # ... existing tier 1 code ...
        _ct[f"{key}_t1_fts5_ext"] = _time.time() - _t

        # Tier 2: FTS5 full text
        _t = _time.time()
        # ... existing tier 2 code ...
        _ct[f"{key}_t2_fts5_full"] = _time.time() - _t

        # Tier 3: Semantic
        _t = _time.time()
        # ... existing tier 3 code ...
        _ct[f"{key}_t3_semantic"] = _time.time() - _t

        # Tier 4: Chunks
        _t = _time.time()
        # ... existing tier 4 code ...
        _ct[f"{key}_t4_chunks"] = _time.time() - _t

        # Tier 5: Reflections
        _t = _time.time()
        # ... existing tier 5 code ...
        _ct[f"{key}_t5_reflections"] = _time.time() - _t

        _ct[f"{key}_total"] = _time.time() - _ck

    _ct["all_collections_total"] = _time.time() - _ct0

    logger.warning(
        "[COLLECTION-TIMING] total=%.1fs | %s",
        _ct["all_collections_total"],
        " | ".join(f"{k}={v:.3f}s" for k, v in sorted(_ct.items(), key=lambda x: -x[1]) if v > 0.01)
    )

    return ...  # existing return
```

### 1D. Instrument `/persona/stream` in server.py

Around line 2502. Same pattern:

```python
async def persona_stream(request: MessageRequest):
    _st = {}
    _st0 = _time.time()

    # Constellation prefetch
    _t = _time.time()
    # ... existing code ...
    _st["constellation_prefetch"] = _time.time() - _t

    # Search chain
    _t = _time.time()
    # ... existing code ...
    _st["search_chain"] = _time.time() - _t

    # L1 ring population
    _t = _time.time()
    # ... existing code ...
    _st["l1_ring_population"] = _time.time() - _t

    # Nexus collection context
    _t = _time.time()
    # ... existing code ...
    _st["nexus_collection"] = _time.time() - _t

    logger.warning(
        "[STREAM-TIMING] pre-director=%.1fs | %s",
        _time.time() - _st0,
        " | ".join(f"{k}={v:.3f}s" for k, v in sorted(_st.items(), key=lambda x: -x[1]))
    )

    # Director generate happens in the SSE generator — time TTFT there
```

### 1E. Instrument Director.generate

In `src/luna/actors/director.py`, around the main generate method, add:

```python
_t_dir = _time.time()
# ... existing LLM call ...
logger.warning("[DIRECTOR-TIMING] llm_call=%.3fs model=%s", _time.time() - _t_dir, model_name)
```

---

## PHASE 2: DIAGNOSE

After instrumenting, restart Luna and send 5 test queries:

1. "hi" (minimal)
2. "who am i?" (identity retrieval)
3. "tell me about owls" (memory search)
4. "what's the architecture of the water temple system?" (collection search)
5. "how should we approach the Kinoni deployment?" (multi-source)

Collect the timing logs. The output will look like:

```
[PIPELINE-TIMING] total=12.3s | collection_context=8.2s | director_generate=2.1s | subtask_runner=0.8s | ...
[RETRIEVE-TIMING] total=9.5s | collection_context=8.2s | matrix_get_context=0.4s | history_build=0.3s | ...
[COLLECTION-TIMING] total=8.2s | priests_total=3.1s | kinoni_total=2.8s | research_total=2.3s | ...
```

This tells us exactly where the 8-18s is hiding.

---

## PHASE 3: OPTIMIZE (conditional on diagnosis)

These are the likely fixes, to be applied ONLY after timing data confirms the bottleneck:

### 3A. If collection search is the bottleneck (most likely)

**Parallelize per-collection search:**

```python
# BEFORE: sequential per-collection
for key in collections_to_search:
    results = await search_collection(key, query)

# AFTER: parallel per-collection
import asyncio
tasks = [search_collection(key, query) for key in collections_to_search]
results = await asyncio.gather(*tasks, return_exceptions=True)
```

This alone could cut collection search time by 2-3x.

**Parallelize tiers within each collection:**

Tiers 1+2 (FTS5) and Tier 3 (semantic) are independent queries — they can run in parallel:

```python
fts_task = asyncio.create_task(fts5_search(...))
sem_task = asyncio.create_task(semantic_search(...))
fts_results, sem_results = await asyncio.gather(fts_task, sem_task)
```

**Skip empty collections:** If a collection has 0 documents, don't search it at all.

**Budget-aware early exit:** If Tier 1 FTS5 fills the context budget, skip Tiers 2-5.

### 3B. If history context is the bottleneck

`build_history_context` may be re-reading conversation turns from DB and reformatting them. If the recent history hasn't changed, cache it.

### 3C. If constellation prefetch is the bottleneck (stream path)

The entity index load from JSON file could be slow if the file is large. Cache the parsed index in memory.

### 3D. If the subtask runner is the bottleneck

The intent classification LLM call (qwen3:8b) should take ~0.5s warm. If it's taking longer, it might be cold-starting. Pin the model in Ollama:

```bash
curl -X POST http://localhost:11434/api/generate -d '{"model":"qwen3:8b","keep_alive":"24h"}'
```

### 3E. Parallelize the two main blocks

Currently in `_process_message_agentic`, the subtask runner and `_retrieve_context()` appear to be called sequentially. They should run in true parallel:

```python
subtask_task = asyncio.create_task(self._subtask_runner.run_subtask_phase(...))
retrieve_task = asyncio.create_task(_retrieve_context())
subtask_phase, (memory_context, history_context) = await asyncio.gather(
    subtask_task, retrieve_task
)
```

---

## VERIFICATION

After optimization, run the same 5 queries and compare:

**Success criteria:**
- Simple queries ("hi"): < 3s TTFT
- Memory queries ("who am i?"): < 5s TTFT
- Complex queries (multi-collection): < 8s TTFT
- Pipeline timing logs show no single stage > 3s

---

## DO NOT

- Do NOT change the LLM model or provider — that's a separate handoff
- Do NOT change retrieval logic (FTS5 queries, semantic search) — just time them
- Do NOT remove any pipeline stages — just make them faster
- Do NOT touch database schema
- Do NOT modify the Memory Matrix scoring

---

## LOG FORMAT

All timing lines use `logger.warning` (not debug/info) with these prefixes:

- `[PIPELINE-TIMING]` — top-level phase breakdown
- `[RETRIEVE-TIMING]` — _retrieve_context internal breakdown
- `[COLLECTION-TIMING]` — per-collection, per-tier breakdown
- `[STREAM-TIMING]` — /persona/stream pre-director breakdown
- `[DIRECTOR-TIMING]` — LLM call duration

All times in seconds with 3 decimal places. Sorted by descending duration so the bottleneck is always first in the log line.

---

## FILES TO MODIFY

- `src/luna/engine.py` — _process_message_agentic, _retrieve_context, _get_collection_context
- `src/luna/api/server.py` — persona_stream handler
- `src/luna/actors/director.py` — generate method

---

## EXPECTED OUTCOME

1. Every pipeline stage has timing data
2. We know exactly where the 8-18s overhead lives
3. The top bottleneck is parallelized or optimized
4. TTFT drops to < 5s for typical queries
