# EMERGENCY DEPLOYMENT: Luna Engine Diagnostic Swarm

**Created**: 2025-01-20
**Updated**: 2025-01-21
**Priority**: EMERGENCY — System Non-Functional
**Method**: Claude Flow Hive — Full Swarm Deployment
**Status**: WARTIME OPERATIONS

---

## SITUATION REPORT

Luna Engine is in critical failure state:

| Component | Status | Evidence |
|-----------|--------|----------|
| Local Inference | ☠️ DEAD | Doesn't know who Luna is, who Ahab is, hallucinates |
| Entity Resolution | ⚠️ PARTIAL | Works on delegated, absent on local |
| Conversation History | ☠️ DEAD | Forgets within same session |
| Personality Injection | ☠️ DEAD | Generic chatbot responses on local |
| Memory Retrieval | ⚠️ PARTIAL | Sometimes works, sometimes doesn't |
| Context Pipeline | ☠️ FRAGMENTED | Two completely different paths |

**Local path is lobotomized.** It receives no context, no personality, no identity. It hallucinates fake people ("Dr. Carol Myles") because it has no grounding.

---

## CRITICAL DISCOVERY: UNIT TESTS PASS, INTEGRATION FAILS

### Test Status

```
419 passed, 1 failed, 1 skipped in 23.41s
```

**Tests that PASS:**

| Test File | Tests | Status |
|-----------|-------|--------|
| `test_ring_buffer.py` | 22 | ✅ ALL PASS |
| `test_context_pipeline.py` | 16 | ✅ ALL PASS |
| `test_history_manager.py` | 21 | ✅ ALL PASS |
| `test_history_integration.py` | 13 | ✅ ALL PASS |
| `test_conversation_flow.py` | 3 | ✅ ALL PASS |
| `test_entity_system.py` | Various | ✅ ALL PASS |

**Including these specific scenarios:**
- `test_marzipan_scenario` ✅
- `test_five_turn_conversation` ✅
- `test_identical_context_for_both_paths` ✅

### The Problem

**Components work in isolation. Integration is broken.**

```
Unit Tests:
  ContextPipeline (mocked DB) → ✅ Works
  ConversationRing (standalone) → ✅ Works
  HistoryManager (mocked) → ✅ Works

Production:
  Director → ContextPipeline → ??? → ❌ FAILS
```

### Root Cause Analysis

Found in `src/luna/actors/director.py`:

```python
# Line 245-256
if CONTEXT_PIPELINE_AVAILABLE:
    try:
        self._context_pipeline = ContextPipeline(...)
        await self._context_pipeline.initialize()
        logger.info("Context pipeline initialized")
    except Exception as e:
        logger.warning(f"Context pipeline init failed: {e}")  # SILENT FAILURE!

# Line 881-883
if self._context_pipeline is not None:  # Falls back to broken code if None
    packet = await self._context_pipeline.build(user_message)
```

**When `_context_pipeline.initialize()` fails:**
1. It logs a warning (easily missed)
2. `_context_pipeline` stays `None`
3. Director falls back to the OLD broken code path
4. Luna loses all context

### Missing Test

**There is NO integration test that:**
1. Creates a real Director (not mocked)
2. Sends multiple messages through `Director.process()`
3. Verifies history survives between turns
4. Tests BOTH local and delegated paths
5. Uses real database connections

The current tests mock the database and test components in isolation. They don't catch integration failures.

---

## SWARM DEPLOYMENT

### Hive Configuration

```yaml
# claude-flow-hive.yaml
swarm:
  name: "luna-emergency-diagnostic"
  mode: "parallel"
  timeout: "4h"
  
agents:
  - archaeologist     # Dig through git history, find what changed
  - cartographer      # Map entire system architecture
  - tracer            # Instrument every code path
  - monitor           # Real-time observation
  - pathologist       # Analyze failures, find root cause
  - surgeon           # Implement fixes
  - validator         # Verify fixes actually work
  - test_writer       # NEW: Write missing integration tests
  
coordination:
  - archaeologist → pathologist
  - cartographer → tracer
  - tracer → pathologist
  - pathologist → surgeon
  - surgeon → validator
  - test_writer → validator  # Tests must pass before sign-off
  - validator → [GATE]
```

---

## AGENT SPECIFICATIONS

### Agent 1: ARCHAEOLOGIST
**Mission**: Excavate git history, find what changed

```bash
# What changed in the last 7 days?
git log --oneline --since="7 days ago" --name-status

# What files were modified?
git diff HEAD~50 --name-only | grep -E "\.(py|ts|js)$"

# Who touched director.py?
git log -p --follow -- src/luna/actors/director.py

# Find when local inference was last modified
git log -p --follow -- "*local*" "*inference*" "*generate*"

# Find when context building changed
git log -p --follow -- "*context*" "*prompt*" "*system*"
```

**Deliverables**:
- `CHANGELOG-FORENSIC.md` — Every change in last 2 weeks with analysis
- `SUSPECTS.md` — Commits most likely to have caused regression
- `TIMELINE.md` — When things started breaking

---

### Agent 2: CARTOGRAPHER
**Mission**: Map the entire Luna Engine architecture

```python
# Generate complete system map

## File Structure
/src/luna/
├── actors/
│   ├── director.py      # → WHAT DOES THIS DO?
│   ├── scribe.py        # → WHAT DOES THIS DO?
│   └── librarian.py     # → WHAT DOES THIS DO?
├── context/
│   └── pipeline.py      # → Unified context builder
├── memory/
│   └── ring.py          # → Conversation ring buffer
├── entities/
│   ├── context.py       # → Entity context builder
│   └── resolution.py    # → Entity detection
├── voice/
│   └── server.py        # → Entry point
└── engine.py            # → Main engine

## For EVERY file:
1. What is its responsibility?
2. What does it import?
3. What imports it?
4. What are its public methods?
5. What state does it manage?
```

**Deliverables**:
- `ARCHITECTURE-MAP.md` — Complete system documentation
- `DEPENDENCY-GRAPH.mermaid` — Visual import/call graph
- `DATA-FLOW.md` — How data moves through the system
- `STATE-INVENTORY.md` — All stateful components and what they hold

---

### Agent 3: TRACER
**Mission**: Instrument EVERYTHING with comprehensive logging

```python
# =============================================================================
# TRACER INSTRUMENTATION SPEC
# =============================================================================

# LEVEL 1: Entry Points
@trace("REQUEST")
def handle_voice_input(audio):
    log("[REQUEST] Voice input received, {len(audio)} bytes")

@trace("REQUEST")  
def handle_text_input(text):
    log("[REQUEST] Text input: '{text[:50]}...'")

# LEVEL 2: Initialization (CRITICAL - find silent failures)
@trace("INIT")
def init_context_pipeline():
    log("[INIT] Starting context pipeline initialization")
    log("[INIT] CONTEXT_PIPELINE_AVAILABLE: {CONTEXT_PIPELINE_AVAILABLE}")
    # ... 
    log("[INIT] Context pipeline initialized: {self._context_pipeline is not None}")

# LEVEL 3: Routing Decisions
@trace("ROUTE")
def decide_local_or_delegated(message):
    log("[ROUTE] Message: '{message[:50]}'")
    log("[ROUTE] _context_pipeline is None: {self._context_pipeline is None}")
    log("[ROUTE] Decision: {decision}")
    log("[ROUTE] Reason: {reason}")

# LEVEL 4: Context Building
@trace("CONTEXT")
def build_context(message):
    log("[CONTEXT] Building for: '{message[:50]}'")
    log("[CONTEXT] Using pipeline: {self._context_pipeline is not None}")
    log("[CONTEXT] History entries: {len(history)}")
    log("[CONTEXT] Entities detected: {entities}")
    log("[CONTEXT] Final prompt length: {len(prompt)} chars")
    log("[CONTEXT] Prompt preview:\n{prompt[:500]}")

# LEVEL 5: Inference
@trace("INFERENCE")
def call_llm(prompt, messages):
    log("[INFERENCE] Route: {route}")
    log("[INFERENCE] System prompt: {len(system)} chars")
    log("[INFERENCE] Messages: {len(messages)}")
    
    response = ...
    
    log("[INFERENCE] Response: {len(response)} chars")
    log("[INFERENCE] Response preview: '{response[:200]}...'")

# LEVEL 6: State Updates
@trace("STATE")
def save_to_history(turn):
    log("[STATE] Saving turn to history")
    log("[STATE] Ring size after: {len(ring)}")
```

**Deliverables**:
- `TRACE-INSTRUMENTATION.patch` — Git patch adding all traces
- `TRACE-FORMAT.md` — How to read trace output
- `trace_collector.py` — Script to aggregate and analyze traces

---

### Agent 4: MONITOR
**Mission**: Real-time observation dashboard

Already created at `/scripts/monitor.py`

**Deliverables**:
- Enhanced `monitor.py` with pipeline status
- `log_viewer.py` — Trace log viewer with filtering
- `state_inspector.py` — Dump current system state on demand

---

### Agent 5: PATHOLOGIST
**Mission**: Analyze failures, determine root cause

**Key Questions to Answer:**

1. **Why is `_context_pipeline` None in production?**
   - Check initialization logs
   - Find what exception is being swallowed
   - Trace the init sequence

2. **Why doesn't local know who Luna is?**
   - What code path does local take when pipeline is None?
   - What system prompt does it receive?
   - Compare to delegated path

3. **Why does local hallucinate?**
   - What context does local receive?
   - Is there ANY grounding at all?

4. **Why does history disappear even on delegated?**
   - Is ring buffer being used?
   - Is record_response() being called?
   - Trace the full lifecycle

**Deliverables**:
- `PATHOLOGY-REPORT.md` — Full diagnosis
- `ROOT-CAUSES.md` — Definitive list of what's wrong
- `FIX-PRIORITIES.md` — Ordered list of what to fix

---

### Agent 6: SURGEON
**Mission**: Implement fixes based on pathology report

**Surgical Priorities**:

1. **CRITICAL: Fix Silent Initialization Failure**
   ```python
   # BEFORE (silent failure)
   try:
       self._context_pipeline = ContextPipeline(...)
       await self._context_pipeline.initialize()
   except Exception as e:
       logger.warning(f"Context pipeline init failed: {e}")
   
   # AFTER (loud failure, fallback with ring buffer)
   try:
       self._context_pipeline = ContextPipeline(...)
       await self._context_pipeline.initialize()
       logger.info("✅ Context pipeline initialized")
   except Exception as e:
       logger.error(f"❌ Context pipeline init failed: {e}")
       logger.error(f"   Falling back to ring buffer only")
       # Ensure ring buffer is still used even without full pipeline
       self._ring = ConversationRing(max_turns=10)
   ```

2. **CRITICAL: Ensure Ring Buffer Always Exists**
   ```python
   # Ring buffer is NON-OPTIONAL
   def __init__(self):
       self._ring = ConversationRing(max_turns=10)  # Always created
       self._context_pipeline = None  # May or may not initialize
   ```

3. **CRITICAL: Local Path Must Use Ring Buffer**
   ```python
   async def _generate_local_only(self, message, ...):
       # ALWAYS add to ring
       self._ring.add_user(message)
       
       # Build context from ring
       history = self._ring.format_for_prompt()
       
       # Include in system prompt
       system_prompt = f"""
       {self._base_personality}
       
       ## THIS SESSION
       {history}
       """
   ```

4. **HIGH: Record Response on ALL Paths**
   ```python
   # After EVERY response, regardless of path
   response = await self._llm_call(...)
   self._ring.add_assistant(response)  # MANDATORY
   ```

**Deliverables**:
- Code changes with clear before/after
- Unit tests for each fix
- Integration tests for full flow

---

### Agent 7: VALIDATOR
**Mission**: Verify fixes actually work — GATE KEEPER

**Validation Suite**:

See Agent 8 (Test Writer) for test specifications.

**Manual Validation Checklist**:

```markdown
## Session 1
- [ ] "Who are you?" → Says Luna (not generic assistant)
- [ ] "Who am I?" → Says Ahab
- [ ] "Tell me about Marzipan" → Knows him, mentions owls
- [ ] "What did you just say?" → References previous response
- [ ] Check route indicator: ●local should work same as ⚡delegated

## Session 2 (after restart)
- [ ] Repeat all above
- [ ] Still works

## Session 3 (after restart)
- [ ] Repeat all above
- [ ] Still works
```

**Deliverables**:
- All automated tests passing
- Manual checklist completed 3x
- Sign-off document

---

### Agent 8: TEST WRITER (NEW)
**Mission**: Write the missing integration tests

**The Gap**: Current tests mock components. We need tests that use REAL:
- Real Director instance
- Real database connection
- Real ContextPipeline
- Multiple turns through actual `Director.process()`

**Required Tests**:

```python
# tests/test_director_integration.py
"""
INTEGRATION TESTS — These use real components, not mocks.

These tests verify the ACTUAL production code path, not isolated components.
If these pass, the system works. If these fail, it doesn't matter that
unit tests pass.
"""

import pytest
import asyncio
from pathlib import Path
import tempfile
import shutil

# Use real imports, not mocks
from luna.actors.director import DirectorActor
from luna.engine import LunaEngine, EngineConfig


class TestDirectorIntegration:
    """Integration tests for Director with real components."""
    
    @pytest.fixture
    async def director(self):
        """Create a REAL Director with REAL database."""
        # Use temp database to avoid polluting real data
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_luna.db"
        
        # Create director
        director = DirectorActor()
        
        # Initialize with real database
        # This should init context pipeline, entity system, etc.
        success = await director._init_entity_context()
        
        yield director
        
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    @pytest.mark.asyncio
    async def test_context_pipeline_initializes(self, director):
        """Context pipeline MUST initialize successfully."""
        # This is the critical check - if this fails, everything else will too
        assert director._context_pipeline is not None, \
            "Context pipeline failed to initialize! Check logs for error."
        
        assert director._context_pipeline._initialized, \
            "Context pipeline exists but is not initialized!"
        
        print("✅ Context pipeline initialized")
    
    @pytest.mark.asyncio
    async def test_ring_buffer_exists(self, director):
        """Ring buffer MUST exist regardless of pipeline status."""
        # Ring buffer should ALWAYS exist
        ring = director._ring if hasattr(director, '_ring') else None
        if ring is None and director._context_pipeline:
            ring = director._context_pipeline.ring
        
        assert ring is not None, "No ring buffer found!"
        print("✅ Ring buffer exists")
    
    @pytest.mark.asyncio
    async def test_two_turn_memory_delegated(self, director):
        """
        THE CRITICAL TEST: Two-turn memory via delegated path.
        
        If this fails, Luna forgets mid-conversation.
        """
        # Force delegated route
        director._force_route = "delegated"
        
        # Turn 1: Establish a fact
        response1 = await director.process(
            message="Remember this: my favorite color is purple.",
            context={}
        )
        
        # Turn 2: Ask about it
        response2 = await director.process(
            message="What is my favorite color?",
            context={}
        )
        
        # Verify
        assert "purple" in response2.lower(), \
            f"FAILED: Luna forgot! Response: {response2}"
        
        print("✅ Two-turn memory works (delegated)")
    
    @pytest.mark.asyncio
    async def test_two_turn_memory_local(self, director):
        """
        THE CRITICAL TEST: Two-turn memory via local path.
        
        If this fails, local path is broken.
        """
        # Force local route
        director._force_route = "local"
        
        # Turn 1
        response1 = await director.process(
            message="Remember this: my favorite number is 42.",
            context={}
        )
        
        # Turn 2
        response2 = await director.process(
            message="What is my favorite number?",
            context={}
        )
        
        # Verify
        assert "42" in response2, \
            f"FAILED: Local path forgot! Response: {response2}"
        
        print("✅ Two-turn memory works (local)")
    
    @pytest.mark.asyncio
    async def test_five_turn_continuity(self, director):
        """Extended memory test — 5 turns."""
        facts = [
            ("My name is TestUser", "name", "testuser"),
            ("I live in Tokyo", "city", "tokyo"),
            ("I have a cat named Whiskers", "cat", "whiskers"),
            ("My favorite food is sushi", "food", "sushi"),
        ]
        
        # Establish facts
        for statement, _, _ in facts:
            await director.process(message=statement, context={})
        
        # Verify each fact
        response = await director.process(
            message="List everything you remember about me",
            context={}
        )
        
        response_lower = response.lower()
        for _, key, expected in facts:
            assert expected in response_lower, \
                f"FAILED: Forgot {key}! Response: {response}"
        
        print("✅ Five-turn continuity works")
    
    @pytest.mark.asyncio
    async def test_marzipan_scenario(self, director):
        """
        THE MARZIPAN TEST — The original failure case.
        """
        # Turn 1: Ask about Marzipan
        r1 = await director.process(
            message="Tell me about Marzipan and the owls",
            context={}
        )
        
        # Turn 2: Ask about Mars College (different topic)
        r2 = await director.process(
            message="Tell me about Mars College",
            context={}
        )
        
        # Turn 3: Reference back to Marzipan
        r3 = await director.process(
            message="What did you tell me about Marzipan earlier?",
            context={}
        )
        
        # Verify Luna doesn't claim ignorance
        failure_phrases = [
            "i don't see",
            "i'm not finding",
            "don't have information",
            "can you remind me",
            "what about marzipan",
        ]
        
        r3_lower = r3.lower()
        for phrase in failure_phrases:
            assert phrase not in r3_lower, \
                f"FAILED: Luna forgot Marzipan! Said: '{phrase}' in response: {r3}"
        
        print("✅ Marzipan scenario passes")
    
    @pytest.mark.asyncio
    async def test_identity_preserved_local(self, director):
        """Luna must know who she is on local path."""
        director._force_route = "local"
        
        response = await director.process(
            message="Who are you?",
            context={}
        )
        
        # Should identify as Luna
        assert "luna" in response.lower(), \
            f"FAILED: Local doesn't know identity! Response: {response}"
        
        # Should NOT be generic
        assert "assistant" not in response.lower() or "ai assistant" not in response.lower(), \
            f"FAILED: Local gave generic response! Response: {response}"
        
        print("✅ Identity preserved on local")
    
    @pytest.mark.asyncio
    async def test_no_hallucination_local(self, director):
        """Local path must not hallucinate fake people."""
        director._force_route = "local"
        
        response = await director.process(
            message="Tell me about notable Mars College alumni",
            context={}
        )
        
        # These are hallucinated names from the bug report
        fake_names = ["dr. carol myles", "dr. james clarke", "dr. elara"]
        
        response_lower = response.lower()
        for name in fake_names:
            assert name not in response_lower, \
                f"FAILED: Local hallucinated '{name}'! Response: {response}"
        
        print("✅ No hallucination on local")
    
    @pytest.mark.asyncio
    async def test_same_context_both_paths(self, director):
        """Both paths should produce equivalent awareness."""
        # Skip if context pipeline not available
        if director._context_pipeline is None:
            pytest.skip("Context pipeline not initialized")
        
        # Build context for same message on both paths
        message = "Tell me about yourself"
        
        # Get context via pipeline (what delegated would use)
        packet = await director._context_pipeline.build(message)
        delegated_prompt = packet.system_prompt
        
        # Check that key elements are present
        assert "luna" in delegated_prompt.lower(), "Luna not in prompt"
        assert "THIS SESSION" in delegated_prompt, "Session marker missing"
        
        print("✅ Context structure correct")


class TestEngineIntegration:
    """Integration tests at the Engine level."""
    
    @pytest.fixture
    async def engine(self):
        """Create a real engine instance."""
        config = EngineConfig()
        engine = LunaEngine(config)
        
        # Start engine
        task = asyncio.create_task(engine.run())
        await engine.wait_ready(timeout=10.0)
        
        yield engine
        
        # Cleanup
        await engine.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    
    @pytest.mark.asyncio
    async def test_engine_director_has_pipeline(self, engine):
        """Engine's director should have context pipeline."""
        director = engine._director
        
        assert director is not None, "Engine has no director!"
        
        # Check pipeline
        if hasattr(director, '_context_pipeline'):
            if director._context_pipeline is None:
                pytest.fail("Director._context_pipeline is None — init failed!")
            else:
                print("✅ Engine director has context pipeline")
        else:
            pytest.fail("Director has no _context_pipeline attribute!")


class TestRegressionPrevention:
    """Tests specifically designed to catch the bugs we've seen."""
    
    @pytest.mark.asyncio
    async def test_history_not_displaced_by_retrieval(self):
        """
        REGRESSION TEST: Memory retrieval must not displace conversation history.
        
        Bug: Luna would search memory, get results about Topic B,
        and then claim she didn't know about Topic A (which was in history).
        """
        # This test ensures that conversation history (ring buffer)
        # is ALWAYS present regardless of what memory retrieval returns
        
        from luna.context.pipeline import ContextPipeline
        from unittest.mock import AsyncMock
        
        # Create pipeline with mock DB that returns unrelated results
        mock_db = AsyncMock()
        mock_db.fetchall.return_value = [
            ("Unrelated memory about Topic B", "2025-01-01")
        ]
        
        pipeline = ContextPipeline(
            db=mock_db,
            max_ring_turns=6,
            base_personality="You are Luna"
        )
        await pipeline.initialize()
        
        # Turn 1: Discuss Topic A
        packet1 = await pipeline.build("Tell me about Topic A")
        pipeline.record_response("Topic A is very interesting! It involves X, Y, Z.")
        
        # Turn 2: Ask about Topic B (retrieval returns unrelated stuff)
        packet2 = await pipeline.build("Tell me about Topic B")
        
        # CRITICAL: Topic A discussion must still be in context
        assert "topic a" in packet2.system_prompt.lower(), \
            "REGRESSION: Topic A was displaced by retrieval!"
        assert "interesting" in packet2.system_prompt.lower(), \
            "REGRESSION: Previous response was lost!"
        
        print("✅ History not displaced by retrieval")
    
    @pytest.mark.asyncio
    async def test_local_path_not_lobotomized(self):
        """
        REGRESSION TEST: Local path must receive full context.
        
        Bug: Local path received no personality, no history, nothing.
        It would give generic responses and hallucinate.
        """
        # This test is hard to automate without the actual local model
        # but we can verify the context building
        
        from luna.actors.director import DirectorActor
        
        director = DirectorActor()
        
        # Even without full init, ring buffer should exist
        assert hasattr(director, '_ring') or \
               (hasattr(director, '_context_pipeline') and director._context_pipeline), \
            "REGRESSION: No conversation memory mechanism exists!"
        
        print("✅ Memory mechanism exists")
```

**File to Create**: `/tests/test_director_integration.py`

**Deliverables**:
- `tests/test_director_integration.py` — Full integration test suite
- `tests/test_regression_prevention.py` — Tests for known bugs
- Documentation on running integration vs unit tests

---

## VERIFICATION GATES

### Gate 1: Unit Tests Pass
```bash
pytest tests/ -v --tb=short
# Expected: 420+ passed (allowing for the one known tick failure)
```

### Gate 2: Integration Tests Pass
```bash
pytest tests/test_director_integration.py -v
# ALL tests must pass
```

### Gate 3: Trace Log Review
Before any "fix" is claimed, provide trace log showing:
```
[INIT] Context pipeline initialized: True
[INIT] Ring buffer size: 0
[REQUEST] Message: "Remember: color is purple"
[CONTEXT] Using pipeline: True
[CONTEXT] Ring size: 1
[STATE] Added user turn, ring size: 1
[INFERENCE] Response received
[STATE] Added assistant turn, ring size: 2
[REQUEST] Message: "What is my color?"
[CONTEXT] Ring size: 2
[CONTEXT] Ring contains 'purple': True
[INFERENCE] Response received
```

### Gate 4: Manual Verification (3x)
Checklist completed three times with server restarts between.

---

## MONITORING INFRASTRUCTURE

### Scripts Available

| Script | Purpose |
|--------|---------|
| `./scripts/relaunch.sh` | Kill & restart everything |
| `./scripts/stop.sh` | Kill all Luna processes |
| `./scripts/monitor.py` | Real-time dashboard |
| `./scripts/watch.sh` | Multi-pane tmux log viewer |
| `./scripts/inspect_state.py` | Full state dump |
| `./scripts/git_forensics.sh` | Find what changed |
| `./scripts/verify_memory.sh` | Run memory tests |

### Log Locations

| Log | Location |
|-----|----------|
| Backend | `/tmp/luna_backend.log` |
| Frontend | `/tmp/luna_frontend.log` |
| Test results | `/tmp/luna_memory_test.log` |
| Forensics | `/tmp/luna_forensics/` |

---

## EXECUTION COMMANDS

```bash
# Deploy the swarm
claude-flow hive deploy luna-emergency-diagnostic

# Or manually:

# Terminal 1: Archaeologist
claude-code "Execute ARCHAEOLOGIST agent from HANDOFF-EMERGENCY-SWARM.md"

# Terminal 2: Cartographer  
claude-code "Execute CARTOGRAPHER agent from HANDOFF-EMERGENCY-SWARM.md"

# Terminal 3: Tracer
claude-code "Execute TRACER agent from HANDOFF-EMERGENCY-SWARM.md"

# Terminal 4: Test Writer
claude-code "Execute TEST_WRITER agent from HANDOFF-EMERGENCY-SWARM.md"

# Terminal 5: Monitor
python scripts/monitor.py

# Terminal 6: Pathologist (after archaeologist + tracer)
claude-code "Execute PATHOLOGIST agent from HANDOFF-EMERGENCY-SWARM.md"

# Terminal 7: Surgeon (after pathologist)
claude-code "Execute SURGEON agent from HANDOFF-EMERGENCY-SWARM.md"

# Terminal 8: Validator (after surgeon + test_writer)
claude-code "Execute VALIDATOR agent from HANDOFF-EMERGENCY-SWARM.md"
```

---

## SUCCESS CRITERIA

### Minimum Viable Fix
- [ ] All unit tests pass (419+)
- [ ] All integration tests pass
- [ ] Luna knows who she is on BOTH paths
- [ ] Luna knows who Ahab is on BOTH paths
- [ ] Luna remembers within a session (5 turns minimum)
- [ ] Luna doesn't hallucinate fake people
- [ ] Marzipan test passes

### Full Fix
- [ ] `_context_pipeline` initializes successfully
- [ ] Ring buffer used on ALL paths
- [ ] Entity resolution on all paths
- [ ] Comprehensive trace logging
- [ ] Real-time monitoring available
- [ ] Manual validation 3x

### Documentation
- [ ] Architecture map complete
- [ ] Change log updated
- [ ] Root cause documented
- [ ] Fix documented with before/after
- [ ] Integration tests documented

---

## TIMELINE

| Hour | Activity |
|------|----------|
| 0:00 | Swarm deploys, agents parallelize |
| 0:30 | Archaeologist: Change history complete |
| 0:30 | Cartographer: System map complete |
| 0:45 | Test Writer: Integration tests written |
| 1:00 | Tracer: Instrumentation deployed |
| 1:30 | Pathologist: Root cause identified |
| 2:00 | Surgeon: Fixes implemented |
| 2:30 | Validator: All tests running |
| 3:00 | Validator: Manual verification |
| 3:30 | All gates pass OR escalate |
| 4:00 | Hard stop — deploy whatever works |

---

## ESCALATION

If after 4 hours system is still broken:

1. **Force all traffic to delegated** — Local is disabled
2. **Deploy ring buffer as mandatory** — Not optional
3. **Ship monitoring** — At least we can see what's happening
4. **Schedule architecture review** — Something is fundamentally wrong

---

## KEY INSIGHT

**The tests pass because they test the wrong thing.**

Unit tests verify:
- "Can ContextPipeline build context?" ✅
- "Can ConversationRing store turns?" ✅
- "Can HistoryManager save to DB?" ✅

Integration tests should verify:
- "Does Director actually USE ContextPipeline?" ❓
- "Does the ring buffer survive between real requests?" ❓
- "Does Luna actually remember across turns in production?" ❓

**Write the integration tests. Run them. Watch them fail. Fix what they catch.**

---

*This is wartime. Ship working code with proof, or ship visibility into why it doesn't work.*
