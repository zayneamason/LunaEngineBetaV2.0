# HANDOFF: Entity System - NO BULLSHIT VERIFICATION

**Created**: 2025-01-20
**Priority**: CRITICAL - BLOCKING ALL OTHER WORK
**Status**: REQUIRES PROOF OF EXECUTION

---

## THE PROBLEM

We keep hearing "it's wired" and "it works" but Luna STILL can't remember Marzipan.

**Evidence from 5 minutes ago:**
```
User: "Do you remember marzipan?"
Luna: "I don't see anything about marzipan in my current memory context"
```

Meanwhile CC verified:
- ✅ Marzipan entity exists in database
- ✅ detect_mentions() exists in resolution.py
- ✅ Director calls EntityContext

**Something is lying.** Either the code isn't being called, or it's being called and failing silently, or the output isn't reaching the LLM.

---

## REQUIREMENTS

### 1. AUTOMATED TESTS THAT MUST PASS

Create and run these tests. They MUST pass before closing this handoff.

```python
# tests/test_entity_system_e2e.py
"""
End-to-end tests for Entity System.
These tests verify the ACTUAL execution path, not just that code exists.
"""

import pytest
import asyncio
from pathlib import Path

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestEntityResolution:
    """Tests that entity resolution actually works."""
    
    @pytest.fixture
    async def resolver(self):
        """Get a real EntityResolver connected to real database."""
        from luna.substrate.database import MemoryDatabase
        from luna.entities.resolution import EntityResolver
        
        db = MemoryDatabase(Path.home() / ".luna" / "luna.db")
        await db.connect()
        resolver = EntityResolver(db)
        yield resolver
        await db.close()
    
    @pytest.mark.asyncio
    async def test_marzipan_exists(self, resolver):
        """Marzipan entity MUST exist and be retrievable."""
        entity = await resolver.resolve_entity("marzipan")
        
        assert entity is not None, "Marzipan entity not found!"
        assert entity.name.lower() == "marzipan"
        assert entity.core_facts is not None
        print(f"✅ Marzipan found: {entity.core_facts}")
    
    @pytest.mark.asyncio
    async def test_detect_mentions_finds_marzipan(self, resolver):
        """detect_mentions() MUST find Marzipan in text."""
        text = "Do you remember Marzipan?"
        
        mentioned = await resolver.detect_mentions(text)
        
        names = [e.name.lower() for e in mentioned]
        assert "marzipan" in names, f"Marzipan not detected! Found: {names}"
        print(f"✅ detect_mentions found: {names}")
    
    @pytest.mark.asyncio
    async def test_detect_mentions_case_insensitive(self, resolver):
        """detect_mentions() MUST be case-insensitive."""
        for variant in ["marzipan", "Marzipan", "MARZIPAN", "MaRzIpAn"]:
            text = f"What about {variant}?"
            mentioned = await resolver.detect_mentions(text)
            names = [e.name.lower() for e in mentioned]
            assert "marzipan" in names, f"Failed on variant: {variant}"
        print("✅ Case insensitivity works")
    
    @pytest.mark.asyncio
    async def test_all_known_people_resolvable(self, resolver):
        """All backfilled people MUST be resolvable."""
        people = ["Marzipan", "Yulia", "Tarsila", "Kamau", "Ahab"]
        
        for name in people:
            entity = await resolver.resolve_entity(name)
            assert entity is not None, f"{name} not found!"
            print(f"✅ {name} found")


class TestContextBuilding:
    """Tests that context building includes entities."""
    
    @pytest.fixture
    async def context_builder(self):
        """Get real EntityContext connected to real database."""
        from luna.substrate.database import MemoryDatabase
        from luna.entities.context import EntityContext
        from luna.entities.resolution import EntityResolver
        
        db = MemoryDatabase(Path.home() / ".luna" / "luna.db")
        await db.connect()
        resolver = EntityResolver(db)
        context = EntityContext(db, resolver)
        yield context
        await db.close()
    
    @pytest.mark.asyncio
    async def test_framed_context_includes_marzipan(self, context_builder):
        """Framed context MUST include Marzipan when mentioned."""
        result = await context_builder.build_framed_context(
            user_message="Do you remember Marzipan?",
            conversation_history=[],
            retrieved_memories=[],
        )
        
        assert "marzipan" in result.lower(), f"Marzipan not in context! Got: {result[:500]}"
        print(f"✅ Marzipan in context. Length: {len(result)} chars")
        print(f"Preview: {result[:300]}...")
    
    @pytest.mark.asyncio
    async def test_temporal_framing_present(self, context_builder):
        """Context MUST have temporal framing markers."""
        result = await context_builder.build_framed_context(
            user_message="Test message",
            conversation_history=[{"role": "user", "content": "Hello"}],
            retrieved_memories=[{"content": "Past event", "created_at": "2025-01-01"}],
        )
        
        # Check for temporal markers
        has_past_marker = "<past_memory" in result or "Past Events" in result
        has_now_marker = "This session" in result or "Happening Now" in result or "[Turn" in result
        
        assert has_past_marker, "No past memory framing found!"
        assert has_now_marker, "No current conversation framing found!"
        print("✅ Temporal framing present")


class TestDirectorIntegration:
    """Tests that Director actually calls the entity system."""
    
    @pytest.fixture
    async def director(self):
        """Get real Director with entity system."""
        # This may need adjustment based on actual Director initialization
        from luna.actors.director import DirectorActor
        
        director = DirectorActor()
        await director._init_entity_system()  # Ensure entity system is initialized
        yield director
    
    @pytest.mark.asyncio
    async def test_director_has_entity_context(self, director):
        """Director MUST have EntityContext initialized."""
        assert hasattr(director, '_entity_context') or hasattr(director, '_context_builder'), \
            "Director has no entity context!"
        
        ctx = getattr(director, '_entity_context', None) or getattr(director, '_context_builder', None)
        assert ctx is not None, "Entity context is None!"
        print("✅ Director has entity context")
    
    @pytest.mark.asyncio
    async def test_director_process_builds_context(self, director):
        """Director.process() MUST build context with entities."""
        # This test requires inspecting what gets passed to the LLM
        # We'll capture the system prompt
        
        captured_system_prompt = None
        original_create = None
        
        # Mock the Claude client to capture system prompt
        if hasattr(director, 'client') and director.client:
            original_create = director.client.messages.create
            
            def capture_create(*args, **kwargs):
                nonlocal captured_system_prompt
                captured_system_prompt = kwargs.get('system', '')
                # Return a mock response
                from unittest.mock import MagicMock
                mock_response = MagicMock()
                mock_response.content = [MagicMock(text="Test response")]
                return mock_response
            
            director.client.messages.create = capture_create
        
        try:
            result = await director.process(
                message="Do you remember Marzipan?",
                context={"conversation_history": [], "memories": []}
            )
            
            assert captured_system_prompt is not None, "System prompt not captured!"
            assert "marzipan" in captured_system_prompt.lower(), \
                f"Marzipan not in system prompt! Got: {captured_system_prompt[:500]}"
            print("✅ Director injects Marzipan into system prompt")
            print(f"System prompt preview: {captured_system_prompt[:300]}...")
            
        finally:
            if original_create:
                director.client.messages.create = original_create


# Run with: pytest tests/test_entity_system_e2e.py -v -s
```

### 2. EXECUTION TRACING

Add these traces and provide the LOG OUTPUT in your response:

```python
# ============================================================
# ADD TO: Director.process() - AT THE VERY START
# ============================================================
logger.info("=" * 60)
logger.info("[TRACE] Director.process() ENTRY")
logger.info(f"[TRACE] Message: '{message}'")
logger.info(f"[TRACE] Has _entity_context: {hasattr(self, '_entity_context')}")
logger.info(f"[TRACE] _entity_context value: {getattr(self, '_entity_context', 'NOT SET')}")

# ============================================================
# ADD TO: Director.process() - BEFORE CONTEXT BUILDING
# ============================================================
logger.info("[TRACE] About to build framed context...")
if hasattr(self, '_entity_context') and self._entity_context:
    logger.info("[TRACE] Calling _entity_context.build_framed_context()")
else:
    logger.info("[TRACE] WARNING: No _entity_context available!")

# ============================================================
# ADD TO: EntityContext.build_framed_context() - START
# ============================================================
logger.info("[TRACE] build_framed_context() ENTRY")
logger.info(f"[TRACE] user_message: '{user_message}'")
logger.info(f"[TRACE] Has _resolver: {hasattr(self, '_resolver')}")

# ============================================================
# ADD TO: EntityContext.build_framed_context() - BEFORE detect_mentions
# ============================================================
logger.info("[TRACE] Calling detect_mentions()...")

# ============================================================
# ADD TO: EntityResolver.detect_mentions() - START
# ============================================================
logger.info("[TRACE] detect_mentions() ENTRY")
logger.info(f"[TRACE] text: '{text}'")

# ============================================================
# ADD TO: EntityResolver.detect_mentions() - AFTER QUERY
# ============================================================
logger.info(f"[TRACE] Found {len(entities)} entities in database")
for e in entities:
    logger.info(f"[TRACE]   - Checking: {e.name}")

# ============================================================
# ADD TO: EntityResolver.detect_mentions() - AFTER MATCHING
# ============================================================
logger.info(f"[TRACE] Matched {len(mentioned)} entities")
for e in mentioned:
    logger.info(f"[TRACE]   - MATCHED: {e.name}")

# ============================================================
# ADD TO: EntityContext.build_framed_context() - AFTER detect_mentions
# ============================================================
logger.info(f"[TRACE] detect_mentions returned {len(mentioned_entities)} entities")
for e in mentioned_entities:
    logger.info(f"[TRACE]   - {e.name}: {e.core_facts}")

# ============================================================
# ADD TO: Director.process() - AFTER CONTEXT BUILT
# ============================================================
logger.info(f"[TRACE] Framed context built: {len(framed_context)} chars")
logger.info(f"[TRACE] Context contains 'marzipan': {'marzipan' in framed_context.lower()}")
logger.info(f"[TRACE] Context preview:\n{framed_context[:500]}")
logger.info("=" * 60)
```

### 3. RUN THE TEST AND PROVIDE OUTPUT

Run this exact sequence and paste the FULL output:

```bash
# Terminal 1: Start server with debug logging
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
LOG_LEVEL=DEBUG python -m luna.voice.server 2>&1 | tee /tmp/luna_trace.log

# Terminal 2: Run automated tests
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
pytest tests/test_entity_system_e2e.py -v -s 2>&1 | tee /tmp/luna_tests.log

# Terminal 3: Manual test via voice
# Say: "Do you remember Marzipan?"
# Then check /tmp/luna_trace.log for the [TRACE] output
```

---

## ACCEPTANCE CRITERIA

This handoff is NOT complete until:

### ☐ All automated tests pass
```
tests/test_entity_system_e2e.py::TestEntityResolution::test_marzipan_exists PASSED
tests/test_entity_system_e2e.py::TestEntityResolution::test_detect_mentions_finds_marzipan PASSED
tests/test_entity_system_e2e.py::TestEntityResolution::test_detect_mentions_case_insensitive PASSED
tests/test_entity_system_e2e.py::TestEntityResolution::test_all_known_people_resolvable PASSED
tests/test_entity_system_e2e.py::TestContextBuilding::test_framed_context_includes_marzipan PASSED
tests/test_entity_system_e2e.py::TestContextBuilding::test_temporal_framing_present PASSED
tests/test_entity_system_e2e.py::TestDirectorIntegration::test_director_has_entity_context PASSED
tests/test_entity_system_e2e.py::TestDirectorIntegration::test_director_process_builds_context PASSED
```

### ☐ Trace logs show full execution path
```
[TRACE] Director.process() ENTRY
[TRACE] Message: 'Do you remember Marzipan?'
[TRACE] Calling _entity_context.build_framed_context()
[TRACE] build_framed_context() ENTRY
[TRACE] Calling detect_mentions()...
[TRACE] detect_mentions() ENTRY
[TRACE] Found 5 entities in database
[TRACE]   - Checking: Ahab
[TRACE]   - Checking: Marzipan
[TRACE]   - Checking: Yulia
[TRACE]   - Checking: Tarsila
[TRACE]   - Checking: Kamau
[TRACE] Matched 1 entities
[TRACE]   - MATCHED: Marzipan
[TRACE] detect_mentions returned 1 entities
[TRACE]   - Marzipan: {'relationship': 'friend', 'location': 'Mars College'}
[TRACE] Framed context built: 1847 chars
[TRACE] Context contains 'marzipan': True
```

### ☐ Manual test succeeds
```
User: "Do you remember Marzipan?"
Luna: "Yes! Marzipan is your friend from Mars College..." (or similar)
```

---

## WHAT TO PROVIDE IN YOUR RESPONSE

1. **Test output** - Full pytest output showing pass/fail
2. **Trace logs** - The [TRACE] output from a real "Do you remember Marzipan?" query
3. **Fix description** - If anything was broken, what was it and how did you fix it
4. **Luna's response** - The actual response Luna gives after fixes

---

## NO ACCEPTABLE EXCUSES

| Excuse | Response |
|--------|----------|
| "The tests pass" | Show the output |
| "The traces show it working" | Show the logs |
| "It should work now" | Prove it with Luna's actual response |
| "The code is wired" | Then why can't Luna remember Marzipan? |

---

## IF TESTS FAIL

If any test fails, the failure message tells you exactly what's broken:

| Test Failure | Meaning |
|--------------|---------|
| `test_marzipan_exists` fails | Entity not in database → run backfill |
| `test_detect_mentions_finds_marzipan` fails | detect_mentions() broken → fix matching logic |
| `test_framed_context_includes_marzipan` fails | Context building broken → check build_framed_context() |
| `test_director_process_builds_context` fails | Director not calling context builder → check process() |

**The tests ARE the debugging.** Run them, read the failures, fix what they say.

---

## FILE TO CREATE

Save the test file:
```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/tests/test_entity_system_e2e.py
```

---

*No more "it's wired." Show the receipts.*
