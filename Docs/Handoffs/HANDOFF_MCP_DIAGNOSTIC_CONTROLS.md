# HANDOFF: MCP Diagnostic Controls + QA Integration Fix

**Date:** March 2, 2026  
**From:** Dude (via Desktop)  
**To:** Claude Code  
**Depends on:** Nothing — this is backend + MCP layer, independent of frontend handoffs

---

## THE PROBLEM

Three layers of breakage:

### Layer 1: Ghost API
The `EngineClient` (MCP layer) calls `/api/diagnostics/*` endpoints that **don't exist** in `server.py`. The MCP tools have wrappers, the client has methods, but there are no backend routes. Everything falls back to SQLite, which gives stale/partial data.

Missing routes the client expects:
- `GET /api/diagnostics/last-inference` → called by `engine_client.last_inference()`
- `GET /api/diagnostics/pipeline` → called by `engine_client.pipeline_state()`
- `GET /api/diagnostics/health` → called by `engine_client.diagnostics_full()`
- `POST /api/diagnostics/trigger/prompt-preview` → called by `engine_client.prompt_preview()`
- `POST /api/diagnostics/trigger/qa-sweep` → called by `engine_client.qa_sweep()`
- `POST /api/diagnostics/trigger/revalidate` → called by `engine_client.qa_force_revalidate()`
- `POST /api/diagnostics/trigger/test-inference` → called by `engine_client.qa_inject_test()`

### Layer 2: Broken /qa/simulate
`POST /qa/simulate` exists but crashes with `type object 'EventType' has no attribute 'USER_MESSAGE'`. It tries to create an `InputEvent` with an old enum value. This is the only existing test-inference path and it's dead.

### Layer 3: Missing MCP Tools
The tools I actually need for debugging Luna's quality don't exist:
- Route override (force LOCAL_ONLY or FULL_DELEGATION for next message)
- Narration toggle (on/off for next message)
- Context injection (add memory to next turn manually)
- Full prompt preview (assembled prompt without sending to LLM)
- Simulate with options (test message + controls in one call)

---

## THE FIX — Three Parts

---

### PART 1: Create the `/api/diagnostics` routes in server.py

Add a new section in `server.py` after the QA routes. These consolidate data that already exists across multiple endpoints into diagnostic-focused responses.

#### `GET /api/diagnostics/last-inference`

Consolidates: `/qa/last` + `/slash/prompt` + `/debug/context`

```python
@app.get("/api/diagnostics/last-inference")
async def diagnostics_last_inference():
    """Full diagnostic snapshot of the last inference."""
    result = {}
    
    # QA report
    if QA_AVAILABLE:
        validator = get_qa_validator()
        report = validator.get_last_report()
        if report:
            result["qa"] = {
                "inference_id": report.get("inference_id"),
                "passed": report.get("passed"),
                "failed_count": report.get("failed_count"),
                "diagnosis": report.get("diagnosis"),
                "route": report.get("route"),
                "provider": report.get("provider_used"),
                "latency_ms": report.get("latency_ms"),
                "assertions": report.get("assertions", []),
            }
    
    # System prompt + assembler metadata
    if _engine:
        director = _engine.get_actor("director")
        if director:
            prompt_info = director.get_last_system_prompt()
            if prompt_info.get("available"):
                result["prompt"] = {
                    "length": prompt_info.get("length"),
                    "route_decision": prompt_info.get("route_decision"),
                    "full_prompt": prompt_info.get("full_prompt"),
                    "assembler": prompt_info.get("assembler"),
                }
    
    # Context items
    if _engine:
        ctx = _engine.get_context_debug()  # whatever method returns debug/context data
        if ctx:
            result["context"] = ctx
    
    return result
```

#### `GET /api/diagnostics/pipeline`

Consolidates: `/status` + `/qa/health` + `/debug/personality`

```python
@app.get("/api/diagnostics/pipeline")
async def diagnostics_pipeline():
    """Pipeline state with QA overlay for MCP tools."""
    result = {"nodes": {}}
    
    if _engine:
        # Node status from actors
        for actor_name in ["director", "scout", "reconcile", "scribe"]:
            actor = _engine.get_actor(actor_name)
            if actor:
                result["nodes"][actor_name] = {
                    "active": True,
                    "type": type(actor).__name__,
                }
    
    # QA overlay
    if QA_AVAILABLE:
        validator = get_qa_validator()
        health = validator.get_health()
        result["qa_health"] = health
        
        report = validator.get_last_report()
        if report:
            result["last_qa"] = {
                "passed": report.get("passed"),
                "failed_count": report.get("failed_count"),
                "top_failures": [
                    a["name"] for a in report.get("assertions", []) 
                    if not a.get("passed")
                ][:5],
            }
    
    return result
```

#### `GET /api/diagnostics/health`

```python
@app.get("/api/diagnostics/health")
async def diagnostics_health():
    """Combined health check for MCP diagnostic tools."""
    result = {
        "engine": _engine is not None,
        "uptime": _engine.uptime_seconds if _engine else 0,
    }
    if QA_AVAILABLE:
        validator = get_qa_validator()
        result["qa"] = validator.get_health()
    return result
```

#### `POST /api/diagnostics/trigger/prompt-preview`

**This is the big one for me.** Builds the full prompt for a given message WITHOUT calling the LLM.

```python
class PromptPreviewRequest(BaseModel):
    message: str = "Hello"
    route_override: Optional[str] = None  # "local", "delegated", "fallback"

@app.post("/api/diagnostics/trigger/prompt-preview")
async def diagnostics_prompt_preview(request: PromptPreviewRequest):
    """Build the assembled prompt without sending to LLM."""
    if not _engine:
        raise HTTPException(status_code=503, detail="Engine not started")
    
    director = _engine.get_actor("director")
    if not director:
        raise HTTPException(status_code=503, detail="Director not available")
    
    # Use the assembler directly
    route = request.route_override or "delegated"
    
    assembler_result = await director._assembler.build(PromptRequest(
        message=request.message,
        conversation_history=[],
        memories=[],
        framed_context="",
        route=route,
        auto_fetch_memory=True,
    ))
    
    return {
        "message": request.message,
        "route": route,
        "system_prompt": assembler_result.system_prompt,
        "prompt_tokens": assembler_result.prompt_tokens,
        "identity_source": assembler_result.identity_source,
        "memory_source": assembler_result.memory_source,
        "voice_injected": assembler_result.voice_injected,
        "gap_category": assembler_result.gap_category,
        "assembler_meta": assembler_result.to_dict(),
    }
```

#### `POST /api/diagnostics/trigger/test-inference`

Replaces the broken `/qa/simulate`. Runs a message through `director.process()` directly (which already works for real messages) and captures QA.

```python
class TestInferenceRequest(BaseModel):
    message: str
    route_override: Optional[str] = None
    narration_enabled: Optional[bool] = None
    extra_context: Optional[str] = None

@app.post("/api/diagnostics/trigger/test-inference")
async def diagnostics_test_inference(request: TestInferenceRequest):
    """Run a test message through the full pipeline with optional overrides."""
    if not _engine:
        raise HTTPException(status_code=503, detail="Engine not started")
    
    director = _engine.get_actor("director")
    if not director:
        raise HTTPException(status_code=503, detail="Director not available")
    
    # Apply overrides
    original_narration = None
    if request.narration_enabled is not None:
        # Store original state, apply override
        original_narration = getattr(director, '_narration_enabled', True)
        director._narration_enabled = request.narration_enabled
    
    # TODO: route_override needs director support — for now log intent
    # TODO: extra_context injection into next assembler call
    
    import time
    start = time.time()
    
    try:
        result = await director.process(
            message=request.message,
            context={"session_id": "diagnostic-test"},
        )
        
        elapsed = (time.time() - start) * 1000
        
        # Get prompt info
        prompt_info = director.get_last_system_prompt()
        
        return {
            "message": request.message,
            "response": result.get("response", ""),
            "route": result.get("route_decision", "unknown"),
            "route_reason": result.get("route_reason", ""),
            "latency_ms": elapsed,
            "qa_passed": result.get("qa_passed"),
            "qa_failures": result.get("qa_failures", 0),
            "prompt_length": prompt_info.get("length", 0) if prompt_info.get("available") else 0,
            "assembler": prompt_info.get("assembler") if prompt_info.get("available") else None,
            "overrides_applied": {
                "route": request.route_override,
                "narration": request.narration_enabled,
                "extra_context": request.extra_context is not None,
            },
        }
    finally:
        # Restore originals
        if original_narration is not None:
            director._narration_enabled = original_narration
```

#### `POST /api/diagnostics/trigger/qa-sweep`

```python
@app.post("/api/diagnostics/trigger/qa-sweep")
async def diagnostics_qa_sweep():
    """Re-validate the last inference against all assertions."""
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA not available")
    validator = get_qa_validator()
    report = validator.revalidate_last()
    return {"passed": report.passed, "failed_count": report.failed_count, "diagnosis": report.diagnosis}
```

#### `POST /api/diagnostics/trigger/revalidate`

```python
class RevalidateRequest(BaseModel):
    assertion_ids: list[str]

@app.post("/api/diagnostics/trigger/revalidate")
async def diagnostics_revalidate(request: RevalidateRequest):
    """Re-validate specific assertions against the last inference."""
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA not available")
    validator = get_qa_validator()
    results = validator.revalidate_assertions(request.assertion_ids)
    return results
```

**Note:** Some of these methods on the QA validator (`revalidate_last`, `revalidate_assertions`) may not exist yet. Implement simple versions that re-run the validate() call using stored inference context.

---

### PART 2: Fix `/qa/simulate`

The existing endpoint crashes because of `EventType.USER_MESSAGE`. This is a stale import. Fix:

```python
# In the qa_simulate function, replace:
event = InputEvent(type=EventType.USER_MESSAGE, payload=request.query)
response = await asyncio.wait_for(
    asyncio.get_event_loop().run_in_executor(
        None, lambda: director.process(Message(event=event))
    ),
    timeout=30.0
)

# With:
response = await asyncio.wait_for(
    director.process(request.query, context={"session_id": "qa-simulate"}),
    timeout=30.0
)
```

Then update the rest of the function to read from the dict that `director.process()` returns (it returns `{"response": ..., "route_decision": ..., etc.}`), not from a Message object.

Also update the `InferenceContext` construction to pull from `response` dict and `director.get_last_system_prompt()`.

---

### PART 3: New MCP Tools

Add to `src/luna_mcp/tools/engine_control.py` and register in `src/luna_mcp/server.py`.

#### `luna_prompt_preview` (full version)

Already exists in engine_client but calls a missing route. Now that the route exists (Part 1), just verify it works.

```python
async def luna_prompt_preview(message: str = "Hello", route: str = None) -> str:
    """
    Preview the full assembled system prompt for a message WITHOUT calling the LLM.
    
    Shows exactly what would be sent to the model: identity injection, memory context,
    virtues, voice instructions, entity framing — everything.
    
    Args:
        message: The message to preview prompt for
        route: Optional route override ("local", "delegated", "fallback")
    """
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await client.prompt_preview(message)  # Update client to POST with body
    return _format_result(result)
```

**Update `engine_client.prompt_preview()`** to properly POST with JSON body:
```python
async def prompt_preview(self, message: str = "Hello", route: str = None) -> dict:
    result = await _http_post(
        "/api/diagnostics/trigger/prompt-preview",
        {"message": message, "route_override": route},
    )
    if result:
        result["source"] = "api"
        return result
    return {"error": "Engine offline", "source": "unavailable"}
```

#### `qa_simulate_with_options`

The power tool. Run a message through the pipeline with controls.

```python
async def qa_simulate_with_options(
    message: str,
    route_override: str = None,
    narration_enabled: bool = None,
    extra_context: str = None,
) -> str:
    """
    Run a test message through Luna's full pipeline with diagnostic overrides.
    
    This is the primary debugging tool. Send a message, optionally override
    the route or narration settings, and get back the full result with QA validation.
    
    Use this to isolate quality problems:
    - Set route_override="local" to test if the problem is delegation vs local
    - Set narration_enabled=false to see raw LLM output before voice transform
    - Set extra_context to inject memory and test if retrieval is the bottleneck
    
    Args:
        message: Test message to send through the pipeline
        route_override: Force "local", "delegated", or "fallback" routing
        narration_enabled: Override narration on (true) or off (false)
        extra_context: Extra text to inject into context for this turn
    """
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    body = {"message": message}
    if route_override: body["route_override"] = route_override
    if narration_enabled is not None: body["narration_enabled"] = narration_enabled
    if extra_context: body["extra_context"] = extra_context
    
    result = await _http_post("/api/diagnostics/trigger/test-inference", body)
    if result:
        result["source"] = "api"
        return _format_result(result)
    return _format_result({"error": "Engine offline", "source": "unavailable"})
```

#### `qa_check_assertion`

Run a single assertion against arbitrary text. For the assertion playground (frontend) and for me to test patterns.

```python
async def qa_check_assertion(assertion_id: str, response_text: str) -> str:
    """
    Test a single QA assertion against provided text.
    
    Quick way to check if a response would pass or fail a specific assertion
    without running the full pipeline.
    
    Args:
        assertion_id: The assertion ID (e.g. "V1", "S4", "P3")
        response_text: The text to check against the assertion
    """
    from luna_mcp.engine_client import EngineClient
    client = EngineClient()
    result = await _http_post(
        "/qa/check-assertion",
        {"assertion_id": assertion_id, "response_text": response_text},
    )
    if result:
        return _format_result(result)
    return _format_result({"error": "QA not available", "source": "unavailable"})
```

**Backend route for this** (add to server.py):

```python
class CheckAssertionRequest(BaseModel):
    assertion_id: str
    response_text: str

@app.post("/qa/check-assertion")
async def qa_check_assertion(request: CheckAssertionRequest):
    """Run a single assertion against provided text."""
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA not available")
    
    validator = get_qa_validator()
    
    # Build minimal inference context with just the response
    ctx = InferenceContext(
        query="[diagnostic check]",
        final_response=request.response_text,
        raw_response=request.response_text,
        provider_used="diagnostic",
        route="DIAGNOSTIC",
        # Set defaults that won't trigger other assertions
        personality_injected=True,
        personality_length=5000,
        virtues_loaded=True,
        narration_applied=True,
    )
    
    # Run just the one assertion
    result = validator.check_single(request.assertion_id, ctx)
    return result
```

**Note:** `validator.check_single()` may not exist. Implement it — find the assertion by ID, run its check function against the context, return the result dict.

#### `qa_diagnostics_summary`

Already exists as `diagnostics_full` in engine_client. Just make sure the MCP registration works and the route exists.

---

### PART 4: Register all new MCP tools

In `src/luna_mcp/server.py`, add registrations:

```python
@mcp.tool()
async def luna_prompt_preview(message: str = "Hello", route: str = None) -> str:
    """Preview the full assembled system prompt without calling the LLM."""
    return await engine_control.luna_prompt_preview(message, route)

@mcp.tool()
async def qa_simulate_with_options(
    message: str,
    route_override: str = None,
    narration_enabled: bool = None,
    extra_context: str = None,
) -> str:
    """Run a test message through the pipeline with diagnostic overrides."""
    return await engine_control.qa_simulate_with_options(
        message, route_override, narration_enabled, extra_context
    )

@mcp.tool()
async def qa_check_assertion(assertion_id: str, response_text: str) -> str:
    """Test a single QA assertion against provided text."""
    return await engine_control.qa_check_assertion(assertion_id, response_text)

@mcp.tool()
async def qa_diagnostics_summary() -> str:
    """Full diagnostic summary — engine health, QA state, component status."""
    return await engine_control.diagnostics_full()
```

---

## FILES MODIFIED

| File | Change |
|------|--------|
| `src/luna/api/server.py` | Add 7 `/api/diagnostics/*` routes + `POST /qa/check-assertion` + fix `/qa/simulate` |
| `src/luna_mcp/engine_client.py` | Fix `prompt_preview()` to POST with JSON body |
| `src/luna_mcp/tools/engine_control.py` | Add `luna_prompt_preview`, `qa_simulate_with_options`, `qa_check_assertion`, `diagnostics_full` |
| `src/luna_mcp/server.py` | Register 4 new MCP tools |

**Total: 4 files modified, 0 new files, 8 new API routes, 4 new MCP tools**

---

## RULES

1. **Don't break existing endpoints.** The `/qa/last`, `/qa/health`, `/qa/simulate` routes stay. Fix `/qa/simulate`, don't delete it.
2. **The diagnostic routes are READ + TEST only.** They don't modify state (except the narration toggle, which restores after the call).
3. **Test inference doesn't pollute conversation history.** Use `session_id: "diagnostic-test"` so the ring buffer doesn't get confused.
4. **The engine_client already has the method stubs.** Wire them to the new routes, don't create parallel paths.
5. **QA validator may need new methods.** `check_single()`, `revalidate_last()`, `revalidate_assertions()` — implement simple versions if they don't exist.

---

## VERIFY

After implementation, these MCP tool calls should work from Claude Desktop:

```
luna_prompt_preview(message="hey luna, tell me about the dataroom")
→ Returns full assembled prompt with identity, memory, voice instructions

qa_simulate_with_options(message="what do you think about sovereignty?", route_override="local")
→ Runs through pipeline, forces local model, returns response + QA results

qa_simulate_with_options(message="explain memory", narration_enabled=false)
→ Shows raw delegated output without voice transform

qa_check_assertion(assertion_id="V1", response_text="Certainly! I'd be happy to help.")
→ Returns FAIL with details about Claude-isms found

qa_diagnostics_summary()
→ Returns engine health, QA pass rate, top failures, component status

luna_last_inference()
→ Returns full snapshot from live API (not DB fallback)

luna_pipeline_state()
→ Returns node status with QA overlay from live API
```

Also verify:
- `curl http://localhost:8000/api/diagnostics/last-inference` returns data (not 404)
- `curl http://localhost:8000/api/diagnostics/pipeline` returns data (not 404)
- `curl -X POST http://localhost:8000/qa/simulate -d '{"query":"hello"}'` no longer crashes

---

## PRIORITY ORDER

1. **Create the `/api/diagnostics/*` routes** — unlocks everything else
2. **Fix `/qa/simulate`** — broken endpoint, quick fix
3. **Wire engine_client methods to new routes** — removes DB fallback dependency
4. **Register MCP tools** — makes them callable from Claude Desktop
5. **Implement missing QA validator methods** — `check_single()`, `revalidate_last()`

---

## WHY THIS MATTERS

Right now when Luna fails QA, I can see THAT she failed but I can't DO anything about it in real time. I can't test theories. I can't isolate whether the problem is routing, retrieval, narration, or the prompt itself.

With these tools I can:
- Preview the prompt → "ah, virtues aren't loading"
- Force local routing → "quality is fine locally, it's the delegation path"
- Turn off narration → "raw output is good, narration is mangling it"
- Inject context → "she knows the answer when memory is present, retrieval is broken"
- Check assertions → "this phrasing triggers V1, let me adjust"

This is the feedback loop that turns QA from a report card into a debugger.
