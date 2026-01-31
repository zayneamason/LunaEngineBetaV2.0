# HANDOFF: Router Path Forcing & Tunable Query Classification

## Problem Statement

The Thought Stream UI shows different levels of detail depending on execution path:
- **DIRECT path**: Shows only `[DIRECT] ...` → `[OK] delegated: X tokens`
- **SIMPLE_PLAN/FULL_PLAN path**: Shows full OBSERVE → THINK → ACT cycle

Currently, queries like "do you remember alex?" get routed to DIRECT because:
1. They're short (low base complexity)
2. The `needs_memory_access()` method exists but doesn't influence path selection
3. Memory queries bypass the AgentLoop entirely, meaning no actual memory retrieval happens

**Result**: Luna says "let me check my memories" but doesn't actually execute a memory search.

---

## Current Architecture

### Router Location
`src/luna/agentic/router.py`

### Existing Signal Detection
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

### Existing Tunable Params
`src/luna/tuning/params.py` already has:
```python
"router.direct_threshold": { "default": 0.2, "bounds": (0.0, 0.5) },
"router.simple_threshold": { "default": 0.5, "bounds": (0.3, 0.7) },
"router.full_threshold": { "default": 0.8, "bounds": (0.6, 1.0) },
```

---

## Required Changes

### 1. Add Path Forcing Parameters to `params.py`

Add new tunable parameters for forcing specific query types to specific paths:

```python
# -------------------------------------------------------------------------
# ROUTER PATH FORCING PARAMETERS
# -------------------------------------------------------------------------
"router.force_memory_to_plan": {
    "default": 1.0,
    "bounds": (0.0, 1.0),
    "step": 1.0,
    "description": "Force memory queries to use planning (SIMPLE_PLAN). 0 = off, 1 = on.",
    "category": "router",
},
"router.memory_min_complexity": {
    "default": 0.3,
    "bounds": (0.1, 0.6),
    "step": 0.05,
    "description": "Minimum complexity floor for memory queries (ensures they don't go DIRECT).",
    "category": "router",
},
"router.force_research_to_full": {
    "default": 1.0,
    "bounds": (0.0, 1.0),
    "step": 1.0,
    "description": "Force research queries to use full planning. 0 = off, 1 = on.",
    "category": "router",
},
```

### 2. Modify Router `analyze()` Method

In `src/luna/agentic/router.py`, update the `analyze()` method to check forcing flags:

```python
def analyze(self, query: str) -> RoutingDecision:
    """
    Analyze a query and return a detailed routing decision.
    """
    complexity = self.estimate_complexity(query)
    signals = self._detect_signals(query)
    suggested_tools = self._detect_tools(query)

    # Check for explicit background request
    if self._matches_any(query, self._background_re):
        return RoutingDecision(
            path=ExecutionPath.BACKGROUND,
            complexity=complexity,
            reason="Explicit background processing requested",
            signals=signals,
            suggested_tools=suggested_tools,
        )

    # === NEW: PATH FORCING LOGIC ===

    # Memory queries MUST use planning (needs retrieval step)
    if "memory_query" in signals and self._force_memory_to_plan:
        complexity = max(complexity, self._memory_min_complexity)
        return RoutingDecision(
            path=ExecutionPath.SIMPLE_PLAN,
            complexity=complexity,
            reason="Memory query requires retrieval step",
            signals=signals,
            suggested_tools=["memory_query"],
        )

    # Research queries should use full planning
    if "research_request" in signals and self._force_research_to_full:
        complexity = max(complexity, self.FULL_THRESHOLD)
        return RoutingDecision(
            path=ExecutionPath.FULL_PLAN,
            complexity=complexity,
            reason="Research query requires multi-step planning",
            signals=signals,
            suggested_tools=suggested_tools,
        )

    # === END PATH FORCING ===

    # Route based on complexity (existing logic)
    if complexity < self.DIRECT_THRESHOLD:
        path = ExecutionPath.DIRECT
        reason = "Simple query, no planning needed"
    elif complexity < self.SIMPLE_THRESHOLD:
        path = ExecutionPath.SIMPLE_PLAN
        reason = "Moderate complexity, single-step plan"
    elif complexity < self.FULL_THRESHOLD:
        path = ExecutionPath.FULL_PLAN
        reason = "Complex query, multi-step planning required"
    else:
        path = ExecutionPath.BACKGROUND
        reason = "Very complex query, background processing recommended"

    # ... rest of existing method
```

### 3. Add Configuration Properties to Router

Add instance variables that can be set by the tuning system:

```python
class QueryRouter:
    # ... existing class variables ...

    def __init__(self):
        """Initialize the query router."""
        # Existing pattern compilation...

        # Path forcing configuration (can be updated via tuning)
        self._force_memory_to_plan: bool = True
        self._memory_min_complexity: float = 0.3
        self._force_research_to_full: bool = True
```

### 4. Wire Up Live Updates in ParamRegistry

In `src/luna/tuning/params.py`, add to `_apply_to_engine()`:

```python
if parts[0] == "router":
    # Get router from engine
    router = getattr(self.engine, "_router", None)
    if not router:
        return False

    if parts[1] == "direct_threshold":
        router.DIRECT_THRESHOLD = value
        return True
    if parts[1] == "simple_threshold":
        router.SIMPLE_THRESHOLD = value
        return True
    if parts[1] == "full_threshold":
        router.FULL_THRESHOLD = value
        return True
    # NEW: Path forcing params
    if parts[1] == "force_memory_to_plan":
        router._force_memory_to_plan = bool(value)
        return True
    if parts[1] == "memory_min_complexity":
        router._memory_min_complexity = float(value)
        return True
    if parts[1] == "force_research_to_full":
        router._force_research_to_full = bool(value)
        return True
```

---

## Testing

### Test Cases

1. **Memory query routes to SIMPLE_PLAN**
   ```
   Input: "do you remember alex?"
   Expected: SIMPLE_PLAN with memory_query tool
   Thought Stream: [OBSERVE] → [THINK] → [ACT:tool] memory_query → [OK]
   ```

2. **Greeting still routes to DIRECT**
   ```
   Input: "hey luna"
   Expected: DIRECT
   Thought Stream: [DIRECT] → [OK]
   ```

3. **Tuning toggle works**
   ```python
   registry.set("router.force_memory_to_plan", 0.0)
   # Now "do you remember alex?" should route based on complexity only
   ```

4. **Research query routes to FULL_PLAN**
   ```
   Input: "research the latest AI news and summarize"
   Expected: FULL_PLAN
   ```

### Test File
Add tests to `tests/test_planning.py`:

```python
def test_memory_query_forces_simple_plan():
    router = QueryRouter()
    decision = router.analyze("do you remember alex?")
    assert decision.path == ExecutionPath.SIMPLE_PLAN
    assert "memory_query" in decision.signals

def test_memory_forcing_can_be_disabled():
    router = QueryRouter()
    router._force_memory_to_plan = False
    decision = router.analyze("remember?")  # Very short = low complexity
    assert decision.path == ExecutionPath.DIRECT

def test_greeting_still_direct():
    router = QueryRouter()
    decision = router.analyze("hey luna!")
    assert decision.path == ExecutionPath.DIRECT
```

---

## Files to Modify

| File | Changes |
|------|---------|
| `src/luna/agentic/router.py` | Add forcing logic to `analyze()`, add config properties |
| `src/luna/tuning/params.py` | Add new params, wire up `_apply_to_engine()` |
| `tests/test_planning.py` | Add test cases |

---

## Future Considerations

1. **Per-signal forcing map**: Instead of individual booleans, could use a dict:
   ```python
   SIGNAL_PATH_OVERRIDES = {
       "memory_query": ExecutionPath.SIMPLE_PLAN,
       "research_request": ExecutionPath.FULL_PLAN,
       "greeting": ExecutionPath.DIRECT,
   }
   ```

2. **UI Controls**: Expose these in the Eclissi tuning panel so Ahab can toggle live.

3. **Learned routing**: Track outcomes (user satisfaction, response quality) to auto-tune thresholds.

---

## Priority

**P1** - This is causing Luna to claim she's checking memories when she isn't. The AgentLoop's memory_query tool is the only path that actually searches the Memory Matrix.

---

## Acceptance Criteria

- [x] Memory queries show full OBSERVE/THINK/ACT cycle in Thought Stream
- [x] `router.force_memory_to_plan` tunable param exists and works
- [x] `router.memory_min_complexity` tunable param exists and works
- [x] Greetings still route to DIRECT (no regression)
- [x] Tests pass (22/22 passing)
