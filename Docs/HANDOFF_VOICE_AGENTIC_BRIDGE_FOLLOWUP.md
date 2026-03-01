# Luna Voice Agentic Bridge — Follow-Up: Startup Race + Entity-Aware Routing

**Date:** 2026-02-27
**From:** Architecture diagnostic session (post-implementation review)
**To:** Claude Code
**Priority:** P0 — The agentic bridge was wired but is unreliable
**Status:** ✅ **IMPLEMENTED** — startup race fix, entity-aware routing, token budget increase all applied
**Depends on:** `HANDOFF_VOICE_AGENTIC_BRIDGE.md` (implemented same day)
**Related:** `HANDOFF_ENTITY_CONTEXT_INIT_FIX.md` (Feb 4), `HANDOFF_CONTEXT_STARVATION.md` (Feb 4)

---

## TL;DR

The voice → agentic bridge from `HANDOFF_VOICE_AGENTIC_BRIDGE.md` was implemented in `src/voice/persona_adapter.py`. QueryRouter, AgentLoop, and surrender_intercept are all wired. **But it's unreliable.** Same query ("tell me about Kozmo") fails completely in one session, returns partial recall after a page refresh. No code changed between attempts. This is a startup race condition compounded by router blindness to entity names.

This is the **third time** the silent initialization failure has been diagnosed. See prior art in `HANDOFF_ENTITY_CONTEXT_INIT_FIX.md` (Feb 4) and `HANDOFF_CONTEXT_STARVATION.md` (Feb 4). The fix needs to stick this time.

---

## THREE STACKED PROBLEMS

### Problem 1: Startup Race (P0)

**Symptom:** First session after launch — Luna fully dark, "I don't have any direct memories about that." Refresh the page — partial recall works. No code changed.

**Root cause:** The search chain in `_prefetch_knowledge()` checks Matrix readiness:

```python
# src/luna/tools/search_chain.py → _search_matrix()
matrix = engine.get_actor("matrix")
if not matrix or not getattr(matrix, 'is_ready', False):
    return []  # ← SILENT. No log. No error. Just empty.
```

If the Matrix actor hasn't finished initializing when the first query arrives, the entire memory search returns `[]`. The pre-fetch returns nothing. Luna has no context. She surrenders.

**This is the same bug from Feb 4.** `HANDOFF_ENTITY_CONTEXT_INIT_FIX.md` identified 5 sequential gates in `_init_entity_context()` that fail silently. The search chain has the same pattern.

**Fix:**

```python
# Option A: Wait for Matrix readiness with timeout
async def _search_matrix(query: str, engine: Any, max_tokens: int) -> List[Dict]:
    matrix = engine.get_actor("matrix") if hasattr(engine, 'get_actor') else None
    
    # Wait for Matrix to be ready (up to 3 seconds)
    if matrix and not getattr(matrix, 'is_ready', False):
        logger.warning("[SEARCH-CHAIN] Matrix not ready, waiting...")
        for i in range(30):
            await asyncio.sleep(0.1)
            if getattr(matrix, 'is_ready', False):
                logger.info(f"[SEARCH-CHAIN] Matrix ready after {(i+1)*100}ms")
                break
        else:
            logger.error("[SEARCH-CHAIN] Matrix failed to initialize within 3s")
            return []
    
    if not matrix or not getattr(matrix, 'is_ready', False):
        logger.error("[SEARCH-CHAIN] Matrix unavailable — returning empty")
        return []
    
    # ... rest of search
```

```python
# Option B: Engine-level readiness gate (better, systemic fix)
# In engine.py boot sequence, don't accept queries until all actors ready
async def _boot(self):
    # ... create and register actors ...
    
    # Block until critical actors are ready
    await self._wait_for_actors_ready(["matrix", "director"], timeout=10.0)
    
    self.state = EngineState.RUNNING  # NOW accept queries
```

Option B is the real fix. Option A is the band-aid. Implement both — belt and suspenders.

**Validation:**
```bash
# Start server fresh, immediately send query (no refresh)
uvicorn luna.api.server:app --host 0.0.0.0 --port 8000

# Within 1 second of startup:
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "tell me about Kozmo"}'

# Should NOT get "I don't have any memories" 
# Should get actual Kozmo content or a "still warming up" message
```

---

### Problem 2: Router Blindness to Entity Names (P1)

**Symptom:** "Tell me about Kozmo" routes DIRECT every time. QueryRouter sees no signals — no "remember", no "data room", no "research" keywords. Low complexity score. Straight to LLM. AgentLoop never fires.

**Why the bridge doesn't help:** The agentic bridge is wired correctly — non-DIRECT paths go through AgentLoop. But "tell me about X" where X is a project entity never triggers non-DIRECT routing. The router has no way to know that "Kozmo" is something Luna has extensive memory about.

**Current router signals that trigger SIMPLE_PLAN:**
- `memory_query`: "remember", "recall", "what do you know about"
- `dataroom_query`: "data room", "investor docs", "due diligence"
- `creative_request`: "generate image", "create video", "eden"

None of these match "tell me about Kozmo."

**Fix — Dynamic Entity Detection:**

```python
# In QueryRouter.__init__() or as a setup method:

async def load_known_entities(self, engine):
    """Load entity names from Memory Matrix for signal detection."""
    matrix = engine.get_actor("matrix")
    if not matrix or not getattr(matrix, 'is_ready', False):
        logger.warning("[ROUTER] Can't load entities — Matrix not ready")
        return
    
    try:
        # Get all entity names + aliases from the graph
        entities = await matrix.get_all_entity_names()  # Returns list of strings
        
        if entities:
            # Build regex pattern from entity names
            escaped = [re.escape(name) for name in entities if len(name) > 2]
            pattern = r"\b(" + "|".join(escaped) + r")\b"
            self._entity_re = re.compile(pattern, re.IGNORECASE)
            logger.info(f"[ROUTER] Loaded {len(escaped)} entity names for signal detection")
        else:
            self._entity_re = None
    except Exception as e:
        logger.error(f"[ROUTER] Failed to load entities: {e}")
        self._entity_re = None
```

```python
# In _detect_signals(), add entity detection:

def _detect_signals(self, query: str) -> List[str]:
    signals = []
    # ... existing signal detection ...
    
    # Entity name detection — if query mentions a known entity, treat as memory query
    if hasattr(self, '_entity_re') and self._entity_re:
        match = self._entity_re.search(query)
        if match:
            signals.append("entity_mention")
            signals.append("memory_query")  # Force SIMPLE_PLAN path
            logger.info(f"[ROUTER] Entity detected: '{match.group()}' → forcing memory_query signal")
    
    return signals
```

**Fallback — Static entity list (implement immediately, replace with dynamic later):**

```python
# Add to QueryRouter class:
KNOWN_ENTITY_PATTERNS = [
    r"\bkozmo\b", r"\bguardian\b", r"\beclissi\b", r"\btapestry\b",
    r"\bkinoni\b", r"\brosa\b", r"\beden\b", r"\bmemory.?matrix\b",
    r"\bhai.?dai\b", r"\btarcila\b", r"\bcalvin\b", r"\bearth.?scale\b",
    r"\brotary\b", r"\bcrane.?ai\b", r"\baibrarian\b", r"\bobservatory\b",
    r"\bthe forger\b", r"\bben.?franklin\b", r"\bthe scribe\b",
    r"\blibrarian\b", r"\bdirector\b",
]
```

Add these to signal detection. Any match → `memory_query` signal → SIMPLE_PLAN → RETRIEVE fires.

**Validation:**
```python
router = QueryRouter()
# These should all route SIMPLE_PLAN, not DIRECT:
assert router.route("tell me about Kozmo") != ExecutionPath.DIRECT
assert router.route("what about the guardian app?") != ExecutionPath.DIRECT
assert router.route("what's happening with Eden?") != ExecutionPath.DIRECT
assert router.route("how is Kinoni deployment going?") != ExecutionPath.DIRECT
```

---

### Problem 3: Shallow Retrieval (P2)

**Symptom:** Even when retrieval works, Luna says "The details are a bit fuzzy" and "I don't have much more concrete information." She found Kozmo but only got a surface-level hit — "The Dinosaur, The Wizard, and The Mother" — not the full architecture.

**Root cause:** Search chain token budget is tight:

```python
# src/luna/tools/search_chain.py
@dataclass
class SearchChainConfig:
    max_total_tokens: int = 3000  # Total budget
    sources: list = [
        SearchSourceConfig(type="matrix", max_tokens=1500),    # Half the budget
        SearchSourceConfig(type="dataroom", max_tokens=1500),  # Other half
    ]
```

`ARCHITECTURE_KOZMO.md` alone is a substantial document. 1500 tokens from Matrix gives a truncated snippet. Luna gets the title and a fragment, not the architecture.

**Fix — Increase budget for entity queries:**

```python
# When router detects entity_mention signal, use richer budget
async def _prefetch_knowledge(self, query: str) -> List[Dict]:
    from luna.tools.search_chain import SearchChainConfig, run_search_chain
    
    config = self._search_config or SearchChainConfig.default()
    
    # If routing detected an entity mention, increase token budget
    if self._last_routing and "entity_mention" in (self._last_routing.signals or []):
        config = SearchChainConfig(
            max_total_tokens=6000,
            sources=[
                SearchSourceConfig(type="matrix", max_tokens=3000),
                SearchSourceConfig(type="dataroom", max_tokens=3000, limit=5),
            ]
        )
        logger.info("[VOICE] Entity query detected — using enriched search budget (6000 tokens)")
    
    return await run_search_chain(config, query, self._engine)
```

Or simpler — just raise the defaults:

```python
# Raise default budgets
max_total_tokens: int = 5000  # was 3000
# matrix: max_tokens=2500     # was 1500
# dataroom: max_tokens=2500   # was 1500
```

---

## IMPLEMENTATION ORDER

| Step | Problem | File | Effort |
|------|---------|------|--------|
| 1 | Startup race (band-aid) | `src/luna/tools/search_chain.py` | 15 min |
| 2 | Startup race (real fix) | `src/luna/engine.py` | 30 min |
| 3 | Static entity patterns | `src/luna/agentic/router.py` | 15 min |
| 4 | Raise token budgets | `src/luna/tools/search_chain.py` | 5 min |
| 5 | Dynamic entity loading | `src/luna/agentic/router.py` + Matrix actor | 45 min |

Steps 1, 3, and 4 are quick wins. Step 2 is the real fix. Step 5 is the proper long-term solution for entity detection.

---

## THE PATTERN TO BREAK

This is the third handoff for the same class of bug: **silent failure on initialization**.

```python
if not ready:
    return []  # ← THIS PATTERN IS THE ENEMY
```

Every time this pattern appears, Luna goes dark and nobody knows why. The fix isn't just patching this instance — it's establishing a rule:

**Never return empty silently. Always log at WARNING or ERROR level when a critical subsystem isn't ready.**

```python
# BAD
if not matrix or not getattr(matrix, 'is_ready', False):
    return []

# GOOD
if not matrix:
    logger.error("[SEARCH-CHAIN] Matrix actor not found — memory search DISABLED")
    return []
if not getattr(matrix, 'is_ready', False):
    logger.error("[SEARCH-CHAIN] Matrix not ready — memory search DISABLED for this query")
    return []
```

Grep the codebase for this pattern and fix every instance:
```bash
grep -rn "return \[\]" src/luna/ --include="*.py" | grep -i "ready\|available\|none\|not "
```

---

## EXPECTED OUTCOME

After all fixes:

| Scenario | Before | After |
|----------|--------|-------|
| First query after cold start | "I don't have any memories" | Waits for Matrix → returns context |
| "Tell me about Kozmo" | Routes DIRECT, shallow pre-fetch | Routes SIMPLE_PLAN, deep retrieval |
| "What about Guardian?" | "I don't have information" | Entity detected → RETRIEVE → full spec |
| Token budget for entity queries | 1500 tokens (truncated) | 3000+ tokens (full context) |
| Silent failures | `return []` with no log | ERROR-level log on every empty return |
