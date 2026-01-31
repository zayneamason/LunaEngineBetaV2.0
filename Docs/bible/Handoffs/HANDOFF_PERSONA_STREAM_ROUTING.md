# HANDOFF: Fix /persona/stream Endpoint to Use Router

## Problem Statement

The router path forcing logic was implemented correctly in `router.py`, but the frontend uses the `/persona/stream` endpoint which **completely bypasses the router**.

**Evidence:**
- Router test in isolation: `"do you remember tarcila?"` → `SIMPLE_PLAN` ✓
- Actual UI behavior: Same query → `[DIRECT]` in Thought Stream ✗

## Root Cause

In `src/luna/api/server.py`, the `/persona/stream` endpoint (line ~658) does this:

```python
@app.post("/persona/stream")
async def persona_stream(request: MessageRequest):
    # ... setup ...
    
    # Line ~746 - HARDCODED [DIRECT], no routing!
    await _engine._emit_progress(f"[DIRECT] {request.message[:40]}...")
    
    # Line ~753 - Goes straight to director, bypassing router
    msg = Message(
        type="generate_stream",
        payload={
            "user_message": request.message,
            "system_prompt": _engine._build_system_prompt(memory_context),
        },
    )
    await director.mailbox.put(msg)
```

**What's missing:**
1. No call to `_engine.router.analyze(request.message)`
2. No check for `ExecutionPath.SIMPLE_PLAN` or `FULL_PLAN`
3. No routing to `_engine._process_with_agent_loop()` for non-DIRECT paths
4. Hardcoded `[DIRECT]` emit regardless of actual routing decision

## The Fix

The `/persona/stream` endpoint needs to use the same routing logic as `/message` endpoint.

### Option A: Delegate to Engine (Recommended)

Have `/persona/stream` call the engine's routing logic instead of duplicating it:

```python
@app.post("/persona/stream")
async def persona_stream(request: MessageRequest):
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    async def generate_sse() -> AsyncGenerator[str, None]:
        token_queue: asyncio.Queue[str | None] = asyncio.Queue()
        full_response: list[str] = []
        final_metadata: dict = {}

        # ... token/complete callbacks same as before ...

        director = _engine.get_actor("director")
        if not director:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Director not available'})}\n\n"
            return

        matrix = _engine.get_actor("matrix")

        try:
            # --- PHASE 1: Send context first (same as before) ---
            # ... memory retrieval, context event ...

            # --- NEW: Route the query ---
            routing = _engine.router.analyze(request.message)
            
            # Emit actual routing decision to Thought Stream
            if routing.path == ExecutionPath.DIRECT:
                await _engine._emit_progress(f"[DIRECT] {request.message[:40]}...")
            else:
                await _engine._emit_progress(f"[{routing.path.name}] {request.message[:40]}...")

            # --- PHASE 2: Handle based on routing ---
            if routing.path == ExecutionPath.DIRECT:
                # Direct path - stream from director (existing behavior)
                _engine.metrics.direct_responses += 1
                director.on_stream(on_token)
                _engine.on_response(on_complete)
                
                msg = Message(
                    type="generate_stream",
                    payload={
                        "user_message": request.message,
                        "system_prompt": _engine._build_system_prompt(memory_context),
                    },
                )
                await director.mailbox.put(msg)
                
                # Stream tokens...
                
            else:
                # Non-direct path - use AgentLoop
                _engine.metrics.planned_responses += 1
                
                # The AgentLoop emits its own progress events
                # (OBSERVE, THINK, ACT, etc.)
                
                # Need to wire up streaming from AgentLoop...
                # This is more complex - see Option B below
```

### Option B: Create New Streaming Method in Engine

Add a method to `engine.py` that handles streaming with routing:

```python
async def stream_message_with_routing(
    self, 
    message: str, 
    on_token: Callable,
    on_complete: Callable,
    on_context: Optional[Callable] = None,
) -> None:
    """
    Stream a response with proper routing.
    
    Handles both DIRECT (director streaming) and planned paths (AgentLoop).
    """
    routing = self.router.analyze(message)
    
    # Get memory context
    memory_context = ""
    matrix = self.get_actor("matrix")
    if matrix and matrix.is_ready:
        memory_context = await matrix.get_context(message, max_tokens=1500)
    
    # Send context to callback
    if on_context:
        on_context({"memory": memory_context, "routing": routing.path.name})
    
    if routing.path == ExecutionPath.DIRECT:
        await self._emit_progress(f"[DIRECT] {message[:40]}...")
        self.metrics.direct_responses += 1
        
        director = self.get_actor("director")
        director.on_stream(on_token)
        self.on_response(on_complete)
        
        msg = Message(
            type="generate_stream",
            payload={
                "user_message": message,
                "system_prompt": self._build_system_prompt(memory_context),
            },
        )
        await director.mailbox.put(msg)
        
    else:
        # Planned path - AgentLoop handles progress emissions
        self.metrics.planned_responses += 1
        
        # AgentLoop needs modification to support streaming callbacks
        # Currently it emits progress but doesn't stream tokens
        await self._process_with_agent_loop_streaming(
            message, 
            on_token=on_token,
            on_complete=on_complete,
            memory_context=memory_context,
        )
```

## Key Insight: AgentLoop Streaming Gap

The AgentLoop currently:
- ✓ Emits progress events (`[OBSERVE]`, `[THINK]`, `[ACT]`)
- ✓ Executes memory queries
- ✗ Does NOT stream tokens back to the frontend

For SIMPLE_PLAN/FULL_PLAN paths to work with streaming, the AgentLoop needs to:
1. Execute its OBSERVE/THINK/ACT cycle (it already does this)
2. When it reaches the final "respond" action, stream tokens from the director

## Files to Modify

| File | Changes |
|------|---------|
| `src/luna/api/server.py` | `/persona/stream` endpoint to use routing |
| `src/luna/engine.py` | Add `stream_message_with_routing()` method (Option B) |
| `src/luna/agentic/loop.py` | Wire up token streaming for final response (if needed) |

## Testing

After fix, this query:
```
"do you remember tarcila?"
```

Should show in Thought Stream:
```
[SIMPLE_PLAN] do you remember tarcila?...
Planning simple task...
[OBSERVE] Gathering context... (1/2)
[THINK] Deciding: Execute memory_query...
[ACT:tool] Execute memory_query...
[OK] Step completed
[OBSERVE] Gathering context... (2/2)
[THINK] Deciding: Present result to user...
[ACT:respond] Present result to user...
[OK] delegated: XXX tokens
```

Instead of current:
```
[DIRECT] do you remember tarcila?...
[OK] delegated: XXX tokens
```

## Priority

**P1** — The router tuning feature is useless until this is fixed. Memory queries don't actually search memory when going through the UI.

## Acceptance Criteria

- [ ] `/persona/stream` calls `router.analyze()` to determine execution path
- [ ] Non-DIRECT paths trigger AgentLoop with proper progress emissions
- [ ] Memory queries show OBSERVE/THINK/ACT cycle in Thought Stream
- [ ] Token streaming still works for all paths
- [ ] Greetings still route to DIRECT (no regression)
