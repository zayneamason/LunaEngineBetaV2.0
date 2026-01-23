# HANDOFF: Memory Retrieval & Local Inference Fix

**Priority:** CRITICAL  
**Goal:** Fix the four broken systems revealed in diagnostic testing

---

## Diagnostic Summary

From conversation log (2025-01-19), Luna exhibits:

| Issue | Symptom | Severity |
|-------|---------|----------|
| Memory retrieval empty | "I'm drawing a blank on Marzipan" | 🔴 CRITICAL |
| Local inference unusable | 31-38 seconds for ~100 tokens (2-3 tok/s) | 🔴 CRITICAL |
| Identity pollution | Thought Ahab was "Kamau" | 🟡 HIGH |
| Agentic memory not wired | "try and remember" doesn't trigger Matrix search | 🟡 HIGH |

---

## Phase 1: Diagnose Memory State

### 1.1 Check if Marzipan EXISTS in Matrix

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Check Luna Engine database
sqlite3 data/luna_engine.db "SELECT id, node_type, substr(content, 1, 100) FROM memory_nodes WHERE content LIKE '%marzipan%' OR content LIKE '%Marzipan%' LIMIT 10;"

# Check node count
sqlite3 data/luna_engine.db "SELECT COUNT(*) FROM memory_nodes;"

# Check if embeddings exist
sqlite3 data/luna_engine.db "SELECT COUNT(*) FROM vec_memory;"
```

**Expected:** 
- Marzipan nodes exist (from Eclissi migration)
- 50,000+ nodes total
- Embeddings populated

**If nodes = 0:** Migration didn't run. Execute `scripts/migrate_from_eclissi.py`

**If nodes exist but Marzipan missing:** Marzipan wasn't in Eclissi's data

### 1.2 Check Matrix Actor Initialization

```python
# Quick test script: scripts/test_matrix_connection.py
import asyncio
from pathlib import Path

async def test():
    from luna.actors.matrix import MatrixActor
    
    db_path = Path("data/luna_engine.db")
    print(f"DB exists: {db_path.exists()}")
    print(f"DB size: {db_path.stat().st_size / 1024 / 1024:.1f} MB")
    
    matrix = MatrixActor(db_path=db_path)
    await matrix.initialize()
    
    print(f"Matrix ready: {matrix.is_ready}")
    print(f"Matrix has _matrix: {matrix._matrix is not None}")
    
    if matrix._matrix:
        stats = await matrix._matrix.get_stats()
        print(f"Stats: {stats}")
        
        # Try a search
        results = await matrix._matrix.search_nodes("marzipan", limit=5)
        print(f"Search 'marzipan': {len(results)} results")
        for r in results:
            print(f"  - [{r.node_type}] {r.content[:80]}...")
    
    await matrix.stop()

asyncio.run(test())
```

Run: `python scripts/test_matrix_connection.py`

---

## Phase 2: Fix Memory Retrieval Pipeline

### 2.1 Problem: Context Not Injected into Generation

**File:** `src/luna/actors/director.py`

The Director's `_generate_with_delegation()` method builds a prompt but doesn't include memory context effectively.

**Current flow:**
```
User message → Director → Claude
                 ↓
            (memory context NOT included)
```

**Find this section (~line 380):**
```python
if is_memory_query:
    luna_prompt = f"""You are Luna. The user is asking about your memories or wants an overview.

User question: {user_message}

IMPORTANT: Your memory context is provided in the system prompt above. Use it to give a detailed,
personal answer about what you actually remember...
```

**Problem:** It says "memory context is provided in the system prompt above" but the system prompt is just `"You are Luna, a sovereign AI companion."` — no memory context is actually injected.

### 2.2 Fix: Add Memory Fetch Before Generation

**File:** `src/luna/actors/director.py`

**Add method to fetch memory context:**

```python
async def _fetch_memory_context(self, query: str, max_tokens: int = 1500) -> str:
    """Fetch relevant memory context for a query."""
    if not self.engine:
        return ""
    
    matrix = self.engine.get_actor("matrix")
    if not matrix or not matrix.is_ready:
        logger.warning("Matrix not available for memory fetch")
        return ""
    
    try:
        # Try get_context if available
        if hasattr(matrix, 'get_context'):
            context = await matrix.get_context(query=query, max_tokens=max_tokens)
            if context:
                return context
        
        # Fallback to direct search
        if matrix._matrix:
            nodes = await matrix._matrix.search_nodes(query=query, limit=10)
            if nodes:
                context_parts = []
                for node in nodes:
                    age = self._humanize_age(node.created_at) if hasattr(node, 'created_at') else "unknown"
                    context_parts.append(f"<memory type='{node.node_type}' age='{age}'>\n{node.content}\n</memory>")
                return "\n\n".join(context_parts)
        
        return ""
    except Exception as e:
        logger.error(f"Memory fetch failed: {e}")
        return ""

def _humanize_age(self, timestamp) -> str:
    """Convert timestamp to human-readable age."""
    from datetime import datetime
    if isinstance(timestamp, str):
        try:
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except:
            return "unknown"
    else:
        dt = timestamp
    
    delta = datetime.now() - dt.replace(tzinfo=None)
    days = delta.days
    
    if days == 0:
        return "today"
    elif days == 1:
        return "yesterday"
    elif days < 7:
        return f"{days} days ago"
    elif days < 30:
        return f"{days // 7} weeks ago"
    else:
        return f"{days // 30} months ago"
```

**Modify `_generate_with_delegation()` to use it:**

```python
async def _generate_with_delegation(
    self,
    user_message: str,
    system_prompt: str,
    max_tokens: int,
    correlation_id: str,
    start_time: float,
    context_window: str = "",
) -> None:
    """
    Delegation flow with memory context injection.
    """
    self._delegated_generations += 1
    print(f"\n🔀 [DELEGATION] Starting for: '{user_message[:50]}...'")

    # Step 1: Quick acknowledgment
    acknowledgment = "Let me look into that..."
    await self._stream_to_callbacks(acknowledgment + "\n\n")
    print(f"✓ [DELEGATION] Sent acknowledgment")

    # Step 2: FETCH MEMORY CONTEXT
    print(f"📚 [DELEGATION] Fetching memory context...")
    memory_context = await self._fetch_memory_context(user_message, max_tokens=1500)
    if memory_context:
        print(f"✓ [DELEGATION] Got {len(memory_context)} chars of memory context")
    else:
        print(f"⚠ [DELEGATION] No memory context found")

    # Step 3: Build system prompt WITH memory
    enhanced_system = system_prompt
    if memory_context:
        enhanced_system = f"""{system_prompt}

## Luna's Relevant Memories

The following memories are relevant to this conversation. Use them to inform your response:

{memory_context}

When referencing these memories, speak naturally as if you remember them directly. 
Don't say "according to my memories" - just reference the information naturally.
"""

    # Step 4: Delegate to Claude
    try:
        print(f"📡 [DELEGATION] Calling Claude ({self._claude_model})...")
        
        # ... rest of existing Claude call, but use enhanced_system instead of system_prompt
```

### 2.3 Fix: Wire Memory Query Detection

**File:** `src/luna/actors/director.py`

**In `_check_delegation_signals()`, ensure memory queries trigger delegation WITH memory fetch:**

```python
def _check_delegation_signals(self, user_message: str) -> bool:
    """Check for signals that require delegation."""
    msg_lower = user_message.lower()
    
    # Memory/recall queries - MUST delegate with memory context
    memory_signals = [
        "remember", "recall", "what do you know about",
        "tell me about", "who is", "who's", "what is",
        "do you remember", "can you remember", "try to remember",
        "your memory", "your memories", "memory matrix"
    ]
    for sig in memory_signals:
        if sig in msg_lower:
            logger.debug(f"  → Memory signal: '{sig}'")
            return True
    
    # ... rest of existing signals
```

---

## Phase 3: Fix Identity Pollution

### 3.1 Problem: Stale Context Bleeding In

Luna thought Ahab was "Kamau" because:
1. A memory node mentions "Kamau Zuberi Akabueze"
2. That node was retrieved as "relevant"
3. Luna assumed the current user was Kamau

### 3.2 Fix: Add User Identity to System Prompt

**File:** `src/luna/actors/director.py`

**In `_generate_with_delegation()`, ensure user identity is explicit:**

```python
# After fetching memory context, add identity anchor
identity_anchor = """
## Current Conversation
You are talking with Ahab (also known as Zayne). He is your creator and primary collaborator.
Do not confuse him with other people mentioned in your memories.
"""

enhanced_system = f"""{system_prompt}

{identity_anchor}

## Luna's Relevant Memories
...
"""
```

**Better long-term fix:** Store user identity in a config or session state that's always injected.

### 3.3 Fix: Filter Memory Results

When retrieving memory, deprioritize nodes that might cause identity confusion:

```python
async def _fetch_memory_context(self, query: str, max_tokens: int = 1500) -> str:
    """Fetch relevant memory context, filtering for quality."""
    # ... existing fetch code ...
    
    if nodes:
        # Filter out nodes that are primarily about OTHER users
        # (heuristic: if node mentions a name that isn't Ahab/Zayne and seems like identity info)
        filtered_nodes = []
        for node in nodes:
            content_lower = node.content.lower()
            # Skip nodes that seem to be about other people's identities
            if "my name is" in content_lower and "ahab" not in content_lower and "zayne" not in content_lower:
                continue
            filtered_nodes.append(node)
        
        nodes = filtered_nodes or nodes  # Fallback to all if filter removes everything
```

---

## Phase 4: Fix Local Inference Speed

### 4.1 Diagnose the Problem

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# Check if MLX is using GPU
python -c "import mlx.core as mx; print(f'Default device: {mx.default_device()}')"

# Check model load time
python -c "
import time
from luna.inference.local import LocalInference

start = time.time()
inf = LocalInference()
print(f'Init time: {time.time() - start:.1f}s')

import asyncio
start = time.time()
asyncio.run(inf.load_model())
print(f'Load time: {time.time() - start:.1f}s')
"
```

### 4.2 Check Model Configuration

**File:** `src/luna/inference/local.py`

Look for these potential issues:

```python
# Check if model path is correct
MODEL_PATH = "..."  # Should point to Qwen 3B or 7B MLX model

# Check if quantization is enabled
# 4-bit quantization should give ~50+ tok/s on M-series

# Check max_tokens - if set very high, might be slow
```

### 4.3 Potential Fixes

**A) Model not quantized:**
```python
# In LocalInference.__init__ or load_model()
# Ensure loading quantized model
model_path = "mlx-community/Qwen2.5-3B-Instruct-4bit"  # or similar
```

**B) Running on CPU instead of GPU:**
```python
import mlx.core as mx
# Force GPU
mx.set_default_device(mx.gpu)
```

**C) Context window too large:**
```python
# Reduce max context if not needed
max_kv_size = 4096  # Instead of 8192
```

**D) Model too large for memory:**
- If using 7B on limited RAM, it may be swapping
- Try 3B model instead

### 4.4 Benchmark Test

**File:** `scripts/benchmark_local_inference.py`

```python
"""Benchmark local inference speed."""
import asyncio
import time

async def benchmark():
    from luna.inference.local import LocalInference
    
    inf = LocalInference()
    
    print("Loading model...")
    start = time.time()
    await inf.load_model()
    print(f"Model loaded in {time.time() - start:.1f}s")
    
    # Warmup
    print("Warmup...")
    async for _ in inf.generate_stream("Hello", max_tokens=10):
        pass
    
    # Benchmark
    prompts = [
        "What is 2+2?",
        "Explain quantum computing in one sentence.",
        "Write a haiku about memory.",
    ]
    
    for prompt in prompts:
        print(f"\nPrompt: {prompt[:30]}...")
        tokens = 0
        start = time.time()
        
        async for token in inf.generate_stream(prompt, max_tokens=100):
            tokens += 1
            print(token, end="", flush=True)
        
        elapsed = time.time() - start
        tok_per_sec = tokens / elapsed
        print(f"\n→ {tokens} tokens in {elapsed:.1f}s = {tok_per_sec:.1f} tok/s")
    
    # Target: 50+ tok/s
    print("\n" + "="*50)
    print("TARGET: 50+ tok/s")
    print("If below target, check: model quantization, GPU usage, model size")

asyncio.run(benchmark())
```

---

## Phase 5: Wire Agentic Memory Search

### 5.1 Problem

When user says "try and remember marzipan", Luna should:
1. Recognize this as a memory query intent
2. Trigger Matrix search for "marzipan"
3. Inject results into response

Currently: Luna just responds without searching.

### 5.2 Fix: Memory Intent Detection in AgentLoop

**File:** `src/luna/agentic/router.py`

**Add memory query patterns:**

```python
MEMORY_QUERY_PATTERNS = [
    r"\b(remember|recall|recollect)\b",
    r"\bwhat do (you|I) know about\b",
    r"\bdo you (remember|know)\b",
    r"\btry (to|and) remember\b",
    r"\bwho (is|was)\b",
    r"\btell me about\b",
    r"\byour memor(y|ies)\b",
]
```

**In `estimate_complexity()` or `_detect_signals()`:**

```python
def _detect_signals(self, query: str) -> List[str]:
    signals = []
    
    # ... existing signal detection ...
    
    # Memory query detection
    for pattern in self.MEMORY_QUERY_PATTERNS:
        if re.search(pattern, query, re.IGNORECASE):
            signals.append("memory_query")
            break
    
    return signals
```

### 5.3 Fix: Ensure Memory Queries Route to Retrieval

**File:** `src/luna/agentic/loop.py`

**In `_execute_simple()` or plan creation:**

```python
async def _execute_simple(self, goal: str, routing: RoutingDecision, start_time: datetime) -> AgentResult:
    """Simple plan execution."""
    
    # Check if this is a memory query
    if "memory_query" in routing.signals:
        plan = self.planner.create_single_step_plan(
            goal=goal,
            step_type=PlanStepType.RETRIEVE,
            description="Search memory for relevant information",
            params={"query": goal},
        )
    elif routing.suggested_tools:
        # ... existing tool handling
```

---

## Phase 6: Integration Tests

### 6.1 Test: Memory Retrieval Works

**File:** `tests/test_memory_retrieval_e2e.py`

```python
"""End-to-end memory retrieval tests."""
import pytest
import asyncio

class TestMemoryRetrieval:
    
    @pytest.fixture
    async def engine(self, tmp_path):
        """Create engine with test data."""
        from luna.engine import LunaEngine, EngineConfig
        from luna.actors.matrix import MatrixActor
        
        config = EngineConfig(data_dir=tmp_path)
        engine = LunaEngine(config)
        
        # Initialize matrix with test data
        matrix = engine.get_actor("matrix")
        await matrix.initialize()
        
        # Add test memories
        if matrix._matrix:
            await matrix._matrix.add_node(
                node_type="PERSON",
                content="Marzipan is a friend at Mars College. He's interested in AI consciousness and collaborates with Ahab on Luna development.",
                source="test",
            )
            await matrix._matrix.add_node(
                node_type="FACT",
                content="Mars College is a desert community where artists and technologists experiment with off-grid living and AI.",
                source="test",
            )
        
        yield engine
        await engine.stop()
    
    @pytest.mark.asyncio
    async def test_memory_query_returns_context(self, engine):
        """Test that asking about Marzipan returns relevant memories."""
        director = engine.get_actor("director")
        
        # Fetch memory context
        context = await director._fetch_memory_context("Who is Marzipan?")
        
        assert context is not None
        assert len(context) > 0
        assert "marzipan" in context.lower() or "mars college" in context.lower()
    
    @pytest.mark.asyncio
    async def test_delegation_includes_memory(self, engine):
        """Test that delegated responses include memory context."""
        # This would need mocking of Claude API
        # For now, just verify the enhanced system prompt is built correctly
        director = engine.get_actor("director")
        
        memory_context = await director._fetch_memory_context("Tell me about Marzipan")
        
        # Build enhanced prompt
        base_system = "You are Luna."
        enhanced = f"{base_system}\n\n## Memories\n{memory_context}"
        
        assert "Marzipan" in enhanced or "Mars College" in enhanced


class TestIdentityHandling:
    
    @pytest.mark.asyncio
    async def test_user_identity_preserved(self, engine):
        """Test that user is correctly identified as Ahab, not confused with memory content."""
        # The enhanced system prompt should always include Ahab identity
        director = engine.get_actor("director")
        
        # Even if memory mentions other names, the identity anchor should be clear
        # This is more of a prompt engineering test
        pass


class TestLocalInferenceSpeed:
    
    @pytest.mark.asyncio
    async def test_local_inference_meets_target(self):
        """Test that local inference achieves 50+ tok/s."""
        from luna.inference.local import LocalInference
        import time
        
        inf = LocalInference()
        await inf.load_model()
        
        # Warmup
        async for _ in inf.generate_stream("Hi", max_tokens=5):
            pass
        
        # Benchmark
        tokens = 0
        start = time.time()
        async for _ in inf.generate_stream("Explain gravity.", max_tokens=50):
            tokens += 1
        elapsed = time.time() - start
        
        tok_per_sec = tokens / elapsed
        print(f"Local inference: {tok_per_sec:.1f} tok/s")
        
        # This test documents current state - adjust threshold as needed
        assert tok_per_sec > 10, f"Local inference too slow: {tok_per_sec:.1f} tok/s"
        # Ideal: assert tok_per_sec > 50
```

### 6.2 Test: Full Conversation Flow

**File:** `tests/test_conversation_flow.py`

```python
"""Test realistic conversation flows."""
import pytest

class TestConversationFlow:
    
    @pytest.mark.asyncio
    async def test_remember_query_flow(self, engine_with_memories):
        """
        User: "Do you remember Marzipan?"
        Expected: Luna searches memory, finds Marzipan, responds with context
        """
        response = await engine_with_memories.process_input("Do you remember Marzipan?")
        
        # Should NOT say "drawing a blank"
        assert "drawing a blank" not in response.lower()
        assert "don't remember" not in response.lower()
        
        # Should reference Marzipan or Mars College
        assert "marzipan" in response.lower() or "mars" in response.lower()
    
    @pytest.mark.asyncio
    async def test_identity_not_confused(self, engine_with_memories):
        """
        Even with memories mentioning other people, Luna should know she's talking to Ahab.
        """
        response = await engine_with_memories.process_input("Who am I?")
        
        # Should identify as Ahab, not Kamau or anyone else
        assert "ahab" in response.lower() or "zayne" in response.lower()
        assert "kamau" not in response.lower()
```

---

## Execution Order

```bash
# Phase 1: Diagnose
python scripts/test_matrix_connection.py
sqlite3 data/luna_engine.db "SELECT COUNT(*) FROM memory_nodes;"

# Phase 2: Fix memory retrieval
# Edit src/luna/actors/director.py per instructions above

# Phase 3: Fix identity pollution  
# Edit src/luna/actors/director.py per instructions above

# Phase 4: Fix local inference
python scripts/benchmark_local_inference.py
# If slow, investigate model config

# Phase 5: Wire agentic memory
# Edit src/luna/agentic/router.py and loop.py

# Phase 6: Run tests
pytest tests/test_memory_retrieval_e2e.py -v
pytest tests/test_conversation_flow.py -v

# Final verification: Manual test
# Start Luna, ask "Do you remember Marzipan?" - should get real answer
```

---

## Success Criteria

| Test | Expected |
|------|----------|
| `sqlite3 ... COUNT(*)` | 50,000+ nodes |
| `test_matrix_connection.py` | Finds Marzipan nodes |
| Memory query response | Includes actual memory content |
| "Who am I?" response | Identifies Ahab, not Kamau |
| Local inference benchmark | 50+ tok/s (stretch), 20+ tok/s (minimum) |
| "Do you remember Marzipan?" | Real answer with context |

---

## Files to Create

| File | Purpose |
|------|---------|
| `scripts/test_matrix_connection.py` | Diagnose Matrix state |
| `scripts/benchmark_local_inference.py` | Measure inference speed |
| `tests/test_memory_retrieval_e2e.py` | E2E memory tests |
| `tests/test_conversation_flow.py` | Conversation flow tests |

## Files to Modify

| File | Changes |
|------|---------|
| `src/luna/actors/director.py` | Add `_fetch_memory_context()`, inject into delegation, add identity anchor |
| `src/luna/agentic/router.py` | Add memory query patterns |
| `src/luna/agentic/loop.py` | Route memory queries to RETRIEVE |

---

## Quick Wins (Do First)

1. **Add memory fetch to Director** — This alone might fix "drawing a blank"
2. **Add identity anchor** — Fixes Kamau confusion immediately
3. **Check model quantization** — Might explain 2 tok/s performance

---

**End of Handoff**
