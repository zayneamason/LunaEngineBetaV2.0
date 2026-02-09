# HANDOFF: Performance Diagnostics - Pipeline Overhead & Embedding Reload

**Handoff ID:** PERF-001  
**Priority:** HIGH  
**Created:** 2026-02-01  
**Author:** Luna + The Dude  
**Estimated Time:** 2-3 hours (diagnostic + instrumentation)

---

## Executive Summary

Luna's local inference path is experiencing significant performance degradation:
- **Raw MLX + LoRA:** ~24 tok/s ✓
- **Full Luna Pipeline:** ~13 tok/s ✗ (~45% overhead)
- **Response Length:** 404 tokens for "what time is it" ✗
- **Embedding Model:** Reloading weights after every extraction ✗

This causes 504 Gateway Timeout errors when responses exceed 30 seconds.

---

## Observed Symptoms

### 1. Embedding Model Reload Spam
After EVERY response, logs show full model weight loading:
```
✓ [LOCAL] Complete: 20 tokens in 6289ms
📝 Extraction triggered for assistant turn (93 chars)
Loading weights:   0%|          | 0/103 [00:00<?, ?it/s]
Loading weights:   1%|          | 1/103 [...]
...
Loading weights: 100%|██████████| 103/103 [...]
BertModel LOAD REPORT from: sentence-transformers/all-MiniLM-L6-v2
```

This should NOT happen. The singleton pattern exists but isn't persisting.

### 2. Pipeline Overhead
| Test | Throughput | Notes |
|------|------------|-------|
| Direct MLX (no LoRA) | ~20 tok/s | Healthy |
| Direct MLX + LoRA | ~24 tok/s | Healthy |
| Luna Pipeline + LoRA | ~13 tok/s | 45% slower |

### 3. Verbose Responses
Simple query "what time is it" → 404 tokens, 31.4 seconds
This exceeds the 30-second timeout → 504 Gateway Timeout

---

## Architecture Context

### Embedding Flow
```
Director._generate_local_only()
    ↓
Response generated
    ↓
📝 Extraction triggered (async)
    ↓
Scribe.extract() 
    ↓
Librarian.file()
    ↓
MemoryMatrix._store_embedding()
    ↓
EmbeddingGenerator.generate()
    ↓
LocalEmbeddings.embed_text()  ← SINGLETON SHOULD PREVENT RELOAD
    ↓
_load_model() ← WHY IS THIS BEING CALLED?
```

### Singleton Implementation (Looks Correct)
**File:** `src/luna/substrate/local_embeddings.py`
```python
_instance: Optional['LocalEmbeddings'] = None
_lock = threading.Lock()

class LocalEmbeddings:
    def __init__(self):
        self._model = None  # Lazy load
        
    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
        return self._model

def get_embeddings() -> LocalEmbeddings:
    global _instance
    with _lock:
        if _instance is None:
            _instance = LocalEmbeddings()
        return _instance
```

### Suspect: EmbeddingGenerator Creates Fresh Instances
**File:** `src/luna/substrate/embedding_generator.py`
```python
class EmbeddingGenerator:
    def __init__(self, embedding_config: Optional[EmbeddingConfig] = None):
        self._local_embeddings: Optional[LocalEmbeddings] = None  # Each instance has own ref
        
    @property
    def local_embeddings(self) -> LocalEmbeddings:
        if self._local_embeddings is None:
            self._local_embeddings = get_embeddings()  # Gets singleton
        return self._local_embeddings
```

### Suspect: Multiple MemoryMatrix Instances
**File:** `src/luna/substrate/memory.py`
```python
async def _ensure_embedding_components(self):
    if self._embedding_generator is None:
        self._embedding_generator = EmbeddingGenerator(self._embedding_config)
```

---

## Investigation Tasks

### Phase 1: Diagnostic Instrumentation

**Task 1.1:** Add logging to trace singleton lifecycle
```python
# In local_embeddings.py
def get_embeddings() -> LocalEmbeddings:
    global _instance
    with _lock:
        if _instance is None:
            logger.warning(f"[SINGLETON] Creating NEW LocalEmbeddings instance, id={id(_instance)}")
            _instance = LocalEmbeddings()
        else:
            logger.debug(f"[SINGLETON] Reusing existing instance, id={id(_instance)}")
        return _instance

def _load_model(self):
    if self._model is None:
        logger.warning(f"[SINGLETON] Loading model (first time), instance_id={id(self)}")
        # ... load
    else:
        logger.debug(f"[SINGLETON] Model already loaded, instance_id={id(self)}")
```

**Task 1.2:** Add logging to trace MemoryMatrix instances
```python
# In memory.py
class MemoryMatrix:
    _instance_counter = 0
    
    def __init__(self, ...):
        MemoryMatrix._instance_counter += 1
        self._instance_id = MemoryMatrix._instance_counter
        logger.info(f"[MEMORY-MATRIX] Created instance #{self._instance_id}")
```

**Task 1.3:** Add logging to trace EmbeddingGenerator instances
```python
# In embedding_generator.py  
class EmbeddingGenerator:
    _instance_counter = 0
    
    def __init__(self, ...):
        EmbeddingGenerator._instance_counter += 1
        self._instance_id = EmbeddingGenerator._instance_counter
        logger.info(f"[EMBEDDING-GEN] Created instance #{self._instance_id}")
```

### Phase 2: Check for Process Isolation

**Task 2.1:** Verify uvicorn worker configuration
```bash
# Check if multiple workers are spawning separate processes
ps aux | grep uvicorn
```

**Task 2.2:** Add process ID logging
```python
import os
logger.info(f"[PROCESS] PID={os.getpid()}, loading embeddings")
```

**Task 2.3:** Check for multiprocessing usage
```bash
# Search for subprocess/multiprocessing usage
grep -r "multiprocessing\|subprocess\|ProcessPoolExecutor" src/luna/
```

### Phase 3: Pipeline Profiling

**Task 3.1:** Create timing decorator
```python
# src/luna/diagnostics/profiler.py
import time
import functools
import logging

_timings = {}

def profile(name: str):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            elapsed = time.perf_counter() - start
            _timings.setdefault(name, []).append(elapsed)
            logger.debug(f"[PROFILE] {name}: {elapsed*1000:.1f}ms")
            return result
        return wrapper
    return decorator

def get_timing_report():
    report = {}
    for name, times in _timings.items():
        report[name] = {
            "count": len(times),
            "avg_ms": sum(times) / len(times) * 1000,
            "max_ms": max(times) * 1000,
            "total_ms": sum(times) * 1000
        }
    return report
```

**Task 3.2:** Instrument critical paths
```python
# In director.py
@profile("director.generate_local")
async def _generate_local_only(self, ...):
    ...

@profile("director.context_build")  
async def _build_context_window(self, ...):
    ...

@profile("director.memory_lookup")
async def _fetch_memories(self, ...):
    ...
```

**Task 3.3:** Add timing endpoint
```python
# In hub_server.py
@app.get("/debug/pipeline-timings")
async def get_pipeline_timings():
    from luna.diagnostics.profiler import get_timing_report
    return get_timing_report()
```

---

## Expected Findings

After instrumentation, we expect to identify:

1. **Singleton Issue:** Either:
   - Multiple processes (uvicorn workers) each with own singleton
   - Module reimport causing fresh instances
   - Garbage collection clearing the singleton

2. **Pipeline Overhead Sources:**
   - Memory lookup latency
   - Context window assembly
   - Streaming callback overhead
   - Extraction blocking the response

3. **Verbosity Source:**
   - LoRA trained on verbose examples
   - System prompt encouraging elaboration
   - No max_tokens cap on simple queries

---

## Success Criteria

| Metric | Before | Target | How to Verify |
|--------|--------|--------|---------------|
| Embedding loads per session | N (once per response) | 1 (total) | Check logs for "Loading weights" |
| Pipeline throughput | ~13 tok/s | ~20+ tok/s | `curl /debug/pipeline-timings` |
| Simple query response | 404 tokens | <100 tokens | Monitor response length |
| Request timeout rate | >50% on long queries | 0% | Monitor 504 errors |

---

## Deliverables

1. **Diagnostic Report:** JSON output from `/debug/pipeline-timings`
2. **Singleton Trace:** Log analysis showing instance creation patterns
3. **Process Map:** Which PIDs are running what components
4. **Recommendations:** Prioritized fix list based on findings

---

## Files to Examine

| File | What to Look For |
|------|------------------|
| `src/luna/substrate/local_embeddings.py` | Singleton implementation |
| `src/luna/substrate/embedding_generator.py` | Instance creation pattern |
| `src/luna/substrate/memory.py` | MemoryMatrix instantiation |
| `src/luna/actors/director.py` | Generation pipeline, extraction trigger |
| `src/luna/actors/scribe.py` | Extraction flow |
| `src/luna/actors/librarian.py` | Filing to MemoryMatrix |
| `src/luna/hub/server.py` | Uvicorn configuration |

---

## Quick Start Commands

```bash
# 1. Check current state
curl http://localhost:8000/health

# 2. Send test message and watch logs
curl -X POST "http://localhost:8000/message" \
  -H "Content-Type: application/json" \
  -d '{"message":"hi"}' &
tail -f /tmp/luna_debug.log

# 3. Check for multiple processes
ps aux | grep -E "uvicorn|python.*luna"

# 4. After instrumentation, check timings
curl http://localhost:8000/debug/pipeline-timings
```

---

## Notes

- The singleton pattern LOOKS correct but ISN'T WORKING
- This is blocking Luna's usability for real-time conversation
- Fix this BEFORE tackling verbosity (that's a LoRA training issue)
- Consider: Should extraction be fully async/background to not block response delivery?

---

**End of Handoff**
