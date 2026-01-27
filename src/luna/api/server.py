"""
Luna Engine API Server
======================

FastAPI server exposing Luna to HTTP clients.

Endpoints:
- POST /message - Send a message and get response (sync)
- POST /stream - Send a message and stream response (SSE)
- GET /status - Engine health and metrics
- GET /health - Health check
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from luna.engine import LunaEngine, EngineConfig
from luna.core.events import InputEvent, EventType
from luna.actors.base import Message
from luna.agentic.router import ExecutionPath

logger = logging.getLogger(__name__)

# Global engine instance
_engine: Optional[LunaEngine] = None


class MessageRequest(BaseModel):
    """Request body for /message endpoint."""
    message: str = Field(..., min_length=1, max_length=10000)
    timeout: float = Field(default=30.0, ge=1.0, le=120.0)
    stream: bool = Field(default=False, description="Use streaming mode")


class MessageResponse(BaseModel):
    """Response from /message endpoint."""
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    # Routing indicators
    delegated: bool = False
    local: bool = False
    fallback: bool = False


class AgenticStats(BaseModel):
    """Agentic processing statistics."""
    is_processing: bool
    current_goal: Optional[str] = None
    pending_messages: int
    tasks_started: int
    tasks_completed: int
    tasks_aborted: int
    direct_responses: int
    planned_responses: int
    agent_loop_status: str


class StatusResponse(BaseModel):
    """Response from /status endpoint."""
    state: str
    uptime_seconds: float
    cognitive_ticks: int
    events_processed: int
    messages_generated: int
    actors: list[str]
    buffer_size: int
    current_turn: int = 0  # Conversation turn counter (for context TTL)
    context: Optional[dict] = None  # Revolving context stats
    agentic: Optional[AgenticStats] = None  # Agentic processing stats


class HistoryMessage(BaseModel):
    """A single message in conversation history."""
    role: str
    content: str
    timestamp: Optional[int] = None


class HistoryResponse(BaseModel):
    """Response from /history endpoint."""
    messages: list[HistoryMessage]
    total: int


class ConsciousnessResponse(BaseModel):
    """Response from /consciousness endpoint."""
    mood: str
    coherence: float
    attention_topics: int
    focused_topics: list[dict]
    top_traits: list[tuple]
    tick_count: int
    last_updated: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage engine lifecycle with FastAPI lifespan.

    Engine starts on server startup, stops on shutdown.
    """
    global _engine

    logger.info("Starting Luna Engine...")

    # Create and start engine
    config = EngineConfig()
    _engine = LunaEngine(config)

    # Start engine in background
    engine_task = asyncio.create_task(_engine.run())

    # Wait for engine to be ready
    await asyncio.sleep(0.5)

    logger.info("Luna Engine ready")

    yield

    # Shutdown
    logger.info("Stopping Luna Engine...")
    if _engine:
        await _engine.stop()

    # Wait for engine task to complete
    try:
        await asyncio.wait_for(engine_task, timeout=5.0)
    except asyncio.TimeoutError:
        engine_task.cancel()
        try:
            await engine_task
        except asyncio.CancelledError:
            pass

    logger.info("Luna Engine stopped")


# Create FastAPI app
app = FastAPI(
    title="Luna Engine API",
    description="Consciousness engine that uses LLMs the way game engines use GPUs",
    version="2.0.0",
    lifespan=lifespan,
)

# Add CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/message", response_model=MessageResponse)
async def send_message(request: MessageRequest):
    """
    Send a message to Luna and get a response.

    This is the main interaction endpoint. Messages are queued in the
    input buffer and processed by the engine's cognitive loop.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    # Create a future to wait for response
    response_future: asyncio.Future = asyncio.Future()

    async def on_response(text: str, data: dict) -> None:
        if not response_future.done():
            response_future.set_result((text, data))

    # Register callback
    _engine.on_response(on_response)

    try:
        # Send message
        await _engine.send_message(request.message)

        # Wait for response with timeout
        text, data = await asyncio.wait_for(
            response_future,
            timeout=request.timeout
        )

        return MessageResponse(
            text=text,
            model=data.get("model", "unknown"),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            latency_ms=data.get("latency_ms", 0),
            delegated=data.get("delegated", False),
            local=data.get("local", False),
            fallback=data.get("fallback", False),
        )

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Response timeout after {request.timeout}s"
        )

    finally:
        # Remove callback
        if on_response in _engine._on_response_callbacks:
            _engine._on_response_callbacks.remove(on_response)


@app.get("/status", response_model=StatusResponse)
async def get_status():
    """
    Get engine status and metrics.

    Returns current state, uptime, tick counts, and actor list.
    Includes agentic processing stats when available.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    status = _engine.status()

    # Build agentic stats if available
    agentic_stats = None
    if "agentic" in status:
        agentic_data = status["agentic"]
        agentic_stats = AgenticStats(
            is_processing=agentic_data.get("is_processing", False),
            current_goal=agentic_data.get("current_goal"),
            pending_messages=agentic_data.get("pending_messages", 0),
            tasks_started=agentic_data.get("tasks_started", 0),
            tasks_completed=agentic_data.get("tasks_completed", 0),
            tasks_aborted=agentic_data.get("tasks_aborted", 0),
            direct_responses=agentic_data.get("direct_responses", 0),
            planned_responses=agentic_data.get("planned_responses", 0),
            agent_loop_status=agentic_data.get("agent_loop_status", "idle"),
        )

    return StatusResponse(
        state=status["state"],
        uptime_seconds=status["uptime_seconds"],
        cognitive_ticks=status["cognitive_ticks"],
        events_processed=status["events_processed"],
        messages_generated=status["messages_generated"],
        actors=status["actors"],
        buffer_size=status["buffer"]["size"],
        current_turn=status.get("current_turn", 0),
        context=status.get("context"),
        agentic=agentic_stats,
    )


@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    if _engine is None:
        return {"status": "starting"}

    return {
        "status": "healthy",
        "state": _engine.state.name,
    }


@app.post("/api/system/relaunch")
async def relaunch_system(background_tasks: BackgroundTasks):
    """
    Trigger a system relaunch.

    Executes the relaunch script in the background and returns immediately.
    The server will restart, so the client should expect a brief disconnection.
    """
    import subprocess
    import os
    from pathlib import Path

    # Find project root by looking for scripts directory
    # server.py is at: src/luna/api/server.py (4 levels deep)
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent.parent  # Go up 4 levels
    script_path = project_root / "scripts" / "relaunch.sh"

    logger.info(f"[RELAUNCH] Looking for script at: {script_path}")

    if not script_path.exists():
        logger.error(f"[RELAUNCH] Script not found at: {script_path}")
        raise HTTPException(status_code=404, detail=f"Relaunch script not found at {script_path}")

    def run_relaunch():
        """Run the relaunch script in background."""
        try:
            subprocess.Popen(
                ["/bin/bash", str(script_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                cwd=str(project_root),
            )
        except Exception as e:
            logger.error(f"Failed to execute relaunch script: {e}")

    background_tasks.add_task(run_relaunch)

    return {
        "status": "restarting",
        "message": "Relaunch initiated. Server will restart shortly.",
    }


# ===========================================================================
# Ring Buffer API — Conversation memory controls
# ===========================================================================

class RingBufferStatus(BaseModel):
    """Ring buffer status response."""
    current_turns: int
    max_turns: int
    topics: list[str]
    recent_messages: list[dict]


class RingBufferConfig(BaseModel):
    """Ring buffer configuration request."""
    max_turns: int = Field(..., ge=2, le=20, description="Max turns (2-20)")


@app.get("/api/ring/status", response_model=RingBufferStatus)
async def get_ring_status():
    """
    Get current ring buffer status.

    Returns the number of turns, max capacity, detected topics,
    and recent messages in the conversation ring buffer.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    director = _engine.get_actor("director")
    if not director:
        raise HTTPException(status_code=503, detail="Director not available")

    # Access the active ring buffer
    ring = getattr(director, "_active_ring", None)
    if ring is None:
        ring = getattr(director, "_standalone_ring", None)

    if ring is None:
        return RingBufferStatus(
            current_turns=0,
            max_turns=6,
            topics=[],
            recent_messages=[],
        )

    # Get topics and recent messages
    topics = list(ring.get_mentioned_topics()) if hasattr(ring, "get_mentioned_topics") else []
    messages = ring.get_as_dicts() if hasattr(ring, "get_as_dicts") else []

    return RingBufferStatus(
        current_turns=len(ring),
        max_turns=ring._max_turns,
        topics=topics[:10],  # Limit to 10 topics
        recent_messages=messages[-6:],  # Last 6 messages
    )


@app.post("/api/ring/config")
async def configure_ring(config: RingBufferConfig):
    """
    Configure the ring buffer size.

    Changes take effect immediately. Existing history is preserved
    up to the new limit (oldest evicted if shrinking).
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    director = _engine.get_actor("director")
    if not director:
        raise HTTPException(status_code=503, detail="Director not available")

    # Get current ring
    ring = getattr(director, "_standalone_ring", None)
    if ring is None:
        raise HTTPException(status_code=503, detail="Ring buffer not available")

    # Preserve existing messages
    old_messages = list(ring._buffer)
    old_max = ring._max_turns

    # Create new buffer with new size
    from collections import deque
    ring._buffer = deque(maxlen=config.max_turns)
    ring._max_turns = config.max_turns

    # Re-add old messages (newest will be kept if shrinking)
    for msg in old_messages:
        ring._buffer.append(msg)

    logger.info(f"[RING-API] Resized from {old_max} to {config.max_turns} turns")

    return {
        "status": "configured",
        "previous_max_turns": old_max,
        "new_max_turns": config.max_turns,
        "current_turns": len(ring),
    }


@app.post("/api/ring/clear")
async def clear_ring():
    """
    Clear the ring buffer.

    Resets conversation memory. Use sparingly — typically for
    starting a fresh conversation or after significant context shifts.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    director = _engine.get_actor("director")
    if not director:
        raise HTTPException(status_code=503, detail="Director not available")

    ring = getattr(director, "_standalone_ring", None)
    if ring is None:
        raise HTTPException(status_code=503, detail="Ring buffer not available")

    old_size = len(ring)
    ring.clear()
    logger.info(f"[RING-API] Cleared {old_size} turns")

    return {
        "status": "cleared",
        "cleared_turns": old_size,
    }


@app.get("/history", response_model=HistoryResponse)
async def get_history(limit: int = 20):
    """
    Get recent conversation history.

    Retrieves recent conversation turns from the memory matrix.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix or not matrix.is_ready:
        return HistoryResponse(messages=[], total=0)

    # Query database directly for conversation-tagged turns
    try:
        memory = getattr(matrix, "_matrix", None) or getattr(matrix, "_memory", None)
        if not memory or not hasattr(memory, "db"):
            logger.warning("History: No memory matrix available")
            return HistoryResponse(messages=[], total=0)

        logger.debug(f"History: matrix ready={matrix.is_ready}")

        # Query conversation nodes from Luna's native substrate
        rows = await memory.db.fetchall("""
            SELECT content, created_at FROM memory_nodes
            WHERE tags LIKE '%"conversation"%'
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        logger.debug(f"History: found {len(rows)} conversation turns")

        messages = []
        for row in rows:
            content = row[0]
            timestamp = row[1]

            # Parse role from content prefix - multiple formats exist
            if content.startswith("User (desktop):") or content.startswith("User:"):
                # Remove prefix to get actual message
                if content.startswith("User (desktop):"):
                    msg_content = content[15:].strip()
                else:
                    msg_content = content[5:].strip()
                messages.append(HistoryMessage(
                    role="user",
                    content=msg_content,
                    timestamp=timestamp
                ))
            elif content.startswith("Luna:"):
                messages.append(HistoryMessage(
                    role="assistant",
                    content=content[5:].strip(),
                    timestamp=timestamp
                ))
            elif content.startswith("[user]"):
                messages.append(HistoryMessage(
                    role="user",
                    content=content[7:].strip(),
                    timestamp=timestamp
                ))
            elif content.startswith("[assistant]"):
                messages.append(HistoryMessage(
                    role="assistant",
                    content=content[12:].strip(),
                    timestamp=timestamp
                ))

        # Reverse to get chronological order
        messages.reverse()

        return HistoryResponse(messages=messages, total=len(messages))
    except Exception as e:
        import traceback
        logger.error(f"Failed to get history: {e}\n{traceback.format_exc()}")
        return HistoryResponse(messages=[], total=0)


@app.get("/consciousness", response_model=ConsciousnessResponse)
async def get_consciousness():
    """
    Get Luna's current consciousness state.

    Returns mood, coherence, attention topics, personality traits, and tick count.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    summary = _engine.consciousness.get_summary()

    return ConsciousnessResponse(
        mood=summary["mood"],
        coherence=summary["coherence"],
        attention_topics=summary["attention_topics"],
        focused_topics=summary["focused_topics"],
        top_traits=summary["top_traits"],
        tick_count=summary["tick_count"],
        last_updated=summary["last_updated"],
    )


@app.post("/stream")
async def stream_message(request: MessageRequest):
    """
    Send a message to Luna and stream the response via SSE.

    Returns Server-Sent Events with:
    - event: token - For each generated token
    - event: done - When generation completes
    - event: error - If an error occurs
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    async def generate_sse() -> AsyncGenerator[str, None]:
        """Generate SSE events for streaming response."""
        token_queue: asyncio.Queue[str | None] = asyncio.Queue()
        response_complete = asyncio.Event()
        final_data: dict = {}
        error_msg: str | None = None

        def on_token(text: str) -> None:
            """Callback for each token."""
            token_queue.put_nowait(text)

        async def on_complete(text: str, data: dict) -> None:
            """Callback when generation completes."""
            nonlocal final_data
            final_data = data
            token_queue.put_nowait(None)  # Signal end
            response_complete.set()

        # Get director and register callbacks
        director = _engine.get_actor("director")
        if not director:
            yield f"event: error\ndata: {json.dumps({'error': 'Director not available'})}\n\n"
            return

        # Register streaming callback
        director.on_stream(on_token)
        _engine.on_response(on_complete)

        try:
            # Get memory context
            memory_context = ""
            matrix = _engine.get_actor("matrix")
            if matrix and matrix.is_ready:
                memory_context = await matrix.get_context(request.message, max_tokens=1500)
                await matrix.store_turn(
                    session_id=_engine.session_id,
                    role="user",
                    content=request.message,
                )

            # Send streaming generation request
            msg = Message(
                type="generate_stream",
                payload={
                    "user_message": request.message,
                    "system_prompt": _engine._build_system_prompt(memory_context),
                },
            )
            await director.mailbox.put(msg)

            # Stream tokens as they arrive
            while True:
                try:
                    token = await asyncio.wait_for(
                        token_queue.get(),
                        timeout=request.timeout
                    )

                    if token is None:
                        # End of stream
                        break

                    # Send token as SSE event
                    yield f"event: token\ndata: {json.dumps({'text': token})}\n\n"

                except asyncio.TimeoutError:
                    yield f"event: error\ndata: {json.dumps({'error': 'Timeout waiting for tokens'})}\n\n"
                    break

            # Send completion event
            yield f"event: done\ndata: {json.dumps(final_data)}\n\n"

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

        finally:
            # Cleanup callbacks
            director.remove_stream_callback(on_token)
            if on_complete in _engine._on_response_callbacks:
                _engine._on_response_callbacks.remove(on_complete)

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


@app.post("/persona/stream")
async def persona_stream(request: MessageRequest):
    """
    Stream Luna's response with context-first SSE format.

    This endpoint sends context (memory + state) BEFORE streaming tokens,
    allowing the frontend to prepare UI with relevant information.

    SSE data format (no named events, typed JSON):
    - {"type": "context", "memory": [...], "state": {...}}
    - {"type": "token", "text": "chunk"}
    - {"type": "done", "response": "full text", "metadata": {...}}
    - {"type": "error", "message": "..."}
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    async def generate_sse() -> AsyncGenerator[str, None]:
        """Generate context-first SSE stream."""
        token_queue: asyncio.Queue[str | None] = asyncio.Queue()
        response_complete = asyncio.Event()
        full_response: list[str] = []
        final_metadata: dict = {}

        def on_token(text: str) -> None:
            """Callback for each token."""
            full_response.append(text)
            token_queue.put_nowait(text)

        async def on_complete(text: str, data: dict) -> None:
            """Callback when generation completes."""
            nonlocal final_metadata
            final_metadata = data
            token_queue.put_nowait(None)  # Signal end
            response_complete.set()

        # Get director
        director = _engine.get_actor("director")
        if not director:
            yield f"data: {json.dumps({'type': 'error', 'message': 'Director not available'})}\n\n"
            return

        # Get matrix for memory context
        matrix = _engine.get_actor("matrix")
        memory_items = []
        memory_context = ""

        try:
            # --- PHASE 1: Send context first ---
            if matrix and matrix.is_ready:
                # Get memory context for the query
                memory_context = await matrix.get_context(request.message, max_tokens=1500)

                # Get recent memories for frontend display
                recent = await matrix.get_recent_turns(limit=5)
                memory_items = [
                    {
                        "id": str(m.id),
                        "content": (m.content or "")[:200],  # Truncate for frontend
                        "type": getattr(m, "node_type", "unknown"),
                        "source": getattr(m, "source", ""),
                    }
                    for m in recent
                ]

                # Store user turn
                await matrix.store_turn(
                    session_id=_engine.session_id,
                    role="user",
                    content=request.message,
                )

            # Build state summary
            state_summary = {
                "session_id": getattr(_engine, "session_id", "unknown"),
                "is_processing": True,
                "state": str(getattr(_engine, "_state", "unknown")),
                "model": getattr(director, "_current_model", "unknown"),
            }

            # Send context event FIRST
            context_event = {
                "type": "context",
                "memory": memory_items,
                "state": state_summary,
            }
            yield f"data: {json.dumps(context_event)}\n\n"

            # --- ROUTING: Determine execution path ---
            routing = _engine.router.analyze(request.message)
            _engine.metrics.agentic_tasks_started += 1

            # Emit actual routing decision to Thought Stream
            await _engine._emit_progress(f"[{routing.path.name}] {request.message[:40]}...")

            # --- PHASE 2: Execute based on routing ---
            if routing.path == ExecutionPath.DIRECT:
                # DIRECT path: stream straight from director
                _engine.metrics.direct_responses += 1
            else:
                # SIMPLE_PLAN or FULL_PLAN: execute memory retrieval first
                _engine.metrics.planned_responses += 1

                # OBSERVE phase
                await _engine._emit_progress("[OBSERVE] Gathering context... (1/2)")

                # Execute memory retrieval if this is a memory query
                if "memory_query" in routing.signals or matrix and matrix.is_ready:
                    await _engine._emit_progress("[THINK] Deciding: Execute memory_query...")
                    await _engine._emit_progress("[ACT:tool] Execute memory_query...")

                    # Re-fetch with potentially more context for memory queries
                    if matrix and matrix.is_ready:
                        memory_context = await matrix.get_context(
                            request.message,
                            max_tokens=2000,  # More context for planned queries
                        )
                        await _engine._emit_progress(
                            f"[OK] Retrieved {len(memory_context) if memory_context else 0} chars of context"
                        )
                    else:
                        await _engine._emit_progress("[OK] Memory not available, proceeding without")

                # OBSERVE phase 2
                await _engine._emit_progress("[OBSERVE] Gathering context... (2/2)")
                await _engine._emit_progress("[THINK] Deciding: Present result to user...")
                await _engine._emit_progress("[ACT:respond] Present result to user...")

            # --- PHASE 3: Stream tokens ---
            director.on_stream(on_token)
            _engine.on_response(on_complete)

            # Send generation request
            msg = Message(
                type="generate_stream",
                payload={
                    "user_message": request.message,
                    "system_prompt": _engine._build_system_prompt(memory_context),
                },
            )
            await director.mailbox.put(msg)

            # Stream tokens as they arrive
            while True:
                try:
                    token = await asyncio.wait_for(
                        token_queue.get(),
                        timeout=request.timeout
                    )

                    if token is None:
                        break

                    yield f"data: {json.dumps({'type': 'token', 'text': token})}\n\n"

                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Timeout waiting for tokens'})}\n\n"
                    break

            # --- PHASE 3: Send done event ---
            # Emit completion for Thought Stream
            tokens = final_metadata.get("output_tokens", len("".join(full_response)) // 4)
            route = "local" if final_metadata.get("local") else "delegated"
            await _engine._emit_progress(f"[OK] {route}: {tokens} tokens")

            done_event = {
                "type": "done",
                "response": "".join(full_response),
                "metadata": final_metadata,
            }
            yield f"data: {json.dumps(done_event)}\n\n"

            # Update completion metrics
            _engine.metrics.agentic_tasks_completed += 1
            _engine.metrics.messages_generated += 1

        except Exception as e:
            logger.error(f"Persona stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        finally:
            # Cleanup callbacks
            if director:
                director.remove_stream_callback(on_token)
            if on_complete in _engine._on_response_callbacks:
                _engine._on_response_callbacks.remove(on_complete)

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/thoughts")
async def thought_stream():
    """
    Stream Luna's internal thought process via SSE.

    Returns Server-Sent Events showing what Luna is doing:
    - event: phase - Current phase (idle, planning, observing, thinking, acting)
    - event: thought - Internal thought/progress message
    - event: step - Plan step being executed
    - event: status - Status change (processing, complete, aborted)

    Connect to this endpoint to see Luna's agentic process in real-time.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    async def generate_thoughts() -> AsyncGenerator[str, None]:
        """Generate SSE events for thought stream."""
        thought_queue: asyncio.Queue[dict] = asyncio.Queue()
        client_connected = True

        async def on_progress(message: str) -> None:
            """Callback for progress updates from AgentLoop."""
            if client_connected:
                await thought_queue.put({
                    "type": "thought",
                    "message": message,
                    "is_processing": _engine._is_processing,
                    "goal": _engine._current_goal,
                })

        # Register progress callback
        _engine._on_progress_callbacks.append(on_progress)

        try:
            # Send initial status
            yield f"event: status\ndata: {json.dumps({'connected': True, 'is_processing': _engine._is_processing, 'goal': _engine._current_goal})}\n\n"

            # Keep connection alive and stream thoughts
            while client_connected:
                try:
                    # Wait for thought with timeout (for keepalive)
                    thought = await asyncio.wait_for(
                        thought_queue.get(),
                        timeout=15.0  # Send keepalive every 15s
                    )

                    # Send thought event
                    yield f"event: {thought['type']}\ndata: {json.dumps(thought)}\n\n"

                except asyncio.TimeoutError:
                    # Send keepalive ping
                    yield f"event: ping\ndata: {json.dumps({'is_processing': _engine._is_processing, 'pending': len(_engine._pending_messages)})}\n\n"

        except asyncio.CancelledError:
            client_connected = False
        finally:
            # Cleanup callback
            if on_progress in _engine._on_progress_callbacks:
                _engine._on_progress_callbacks.remove(on_progress)

    return StreamingResponse(
        generate_thoughts(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/abort")
async def abort_generation():
    """
    Abort the current generation.

    Works with streaming mode - will stop generation at the next token boundary.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    director = _engine.get_actor("director")
    if not director:
        raise HTTPException(status_code=503, detail="Director not available")

    if not director.is_generating:
        return {"status": "no_generation", "message": "No generation in progress"}

    await director.mailbox.put(Message(type="abort"))
    return {"status": "aborted", "message": "Abort signal sent"}


@app.post("/interrupt")
async def interrupt_processing():
    """
    Interrupt Luna's current processing.

    This triggers the agentic interrupt handler which will:
    - Abort any running AgentLoop
    - Cancel the current task
    - Process any pending messages

    Use this when you want Luna to stop what she's doing and respond to you.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    if not _engine._is_processing:
        return {
            "status": "no_task",
            "message": "No task in progress",
            "pending_messages": len(_engine._pending_messages),
        }

    current_goal = _engine._current_goal
    await _engine.send_interrupt()

    return {
        "status": "interrupted",
        "message": "Interrupt signal sent",
        "interrupted_goal": current_goal,
        "pending_messages": len(_engine._pending_messages),
    }


# =============================================================================
# MEMORY & EXTRACTION ENDPOINTS
# =============================================================================


class NodeCreateRequest(BaseModel):
    """Request body for creating a memory node."""
    node_type: str = Field(..., description="Node type: FACT, DECISION, PROBLEM, etc.")
    content: str = Field(..., min_length=1)
    source: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


from datetime import datetime as dt_type
from typing import Union, Any
from pydantic import field_validator

class NodeResponse(BaseModel):
    """Response with memory node details."""
    id: str
    node_type: str
    content: str
    source: Optional[str] = None
    confidence: float
    importance: float
    access_count: int
    reinforcement_count: int
    lock_in: float
    lock_in_state: str
    created_at: str

    @field_validator('created_at', mode='before')
    @classmethod
    def coerce_datetime(cls, v: Any) -> str:
        """Convert datetime to ISO string if needed."""
        if v is None:
            return ""
        if isinstance(v, dt_type):
            return v.isoformat()
        return str(v)


class ExtractionRequest(BaseModel):
    """Request body for triggering extraction."""
    content: str = Field(..., min_length=1)
    role: str = Field(default="user")
    session_id: Optional[str] = None
    immediate: bool = Field(default=True, description="Process immediately without batching")


class ExtractionResponse(BaseModel):
    """Response from extraction."""
    objects_extracted: int
    edges_extracted: int
    nodes_created: list[str]


class PruneRequest(BaseModel):
    """Request body for pruning."""
    age_days: int = Field(default=30, ge=1)
    confidence_threshold: float = Field(default=0.3, ge=0.0, le=1.0)
    prune_nodes: bool = Field(default=True)
    max_prune_nodes: int = Field(default=100, ge=1)


class PruneResponse(BaseModel):
    """Response from pruning."""
    edges_pruned: int
    nodes_pruned: int


class MemoryStatsResponse(BaseModel):
    """Response with memory statistics."""
    total_nodes: int
    nodes_by_type: dict
    nodes_by_lock_in: dict
    avg_lock_in: float
    total_edges: int
    drifting_nodes: int
    fluid_nodes: int
    settled_nodes: int


@app.post("/memory/nodes", response_model=NodeResponse)
async def create_node(request: NodeCreateRequest):
    """
    Create a new memory node.

    This bypasses extraction and directly creates a node in the memory matrix.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix:
        raise HTTPException(status_code=503, detail="Matrix actor not available")

    try:
        node_id = await matrix.add_node(
            node_type=request.node_type,
            content=request.content,
            source=request.source or "api",
            confidence=request.confidence,
            importance=request.importance,
        )

        # Fetch the created node
        node = await matrix.get_node(node_id)
        if not node:
            raise HTTPException(status_code=500, detail="Node created but not found")

        return NodeResponse(
            id=node.id,
            node_type=node.node_type,
            content=node.content,
            source=node.source,
            confidence=node.confidence,
            importance=node.importance,
            access_count=node.access_count,
            reinforcement_count=node.reinforcement_count,
            lock_in=node.lock_in,
            lock_in_state=node.lock_in_state,
            created_at=node.created_at.isoformat() if hasattr(node.created_at, 'isoformat') else str(node.created_at),
        )
    except Exception as e:
        logger.error(f"Failed to create node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/nodes/{node_id}", response_model=NodeResponse)
async def get_node(node_id: str):
    """Get a memory node by ID."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix:
        raise HTTPException(status_code=503, detail="Matrix actor not available")

    node = await matrix.get_node(node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    return NodeResponse(
        id=node.id,
        node_type=node.node_type,
        content=node.content,
        source=node.source,
        confidence=node.confidence,
        importance=node.importance,
        access_count=node.access_count,
        reinforcement_count=node.reinforcement_count,
        lock_in=node.lock_in,
        lock_in_state=node.lock_in_state,
        created_at=node.created_at.isoformat() if hasattr(node.created_at, 'isoformat') else str(node.created_at),
    )


@app.get("/memory/nodes", response_model=list[NodeResponse])
async def list_nodes(
    node_type: Optional[str] = None,
    lock_in_state: Optional[str] = None,
    limit: int = 50,
):
    """
    List memory nodes with optional filtering.

    - node_type: Filter by type (FACT, DECISION, etc.)
    - lock_in_state: Filter by lock-in state (drifting, fluid, settled)
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix:
        raise HTTPException(status_code=503, detail="Matrix actor not available")

    try:
        # Get the underlying MemoryMatrix
        # Get the underlying MemoryMatrix
        memory = getattr(matrix, "matrix", None) or getattr(matrix, "_matrix", None) or getattr(matrix, "_memory", None)
        if not memory:
            raise HTTPException(status_code=503, detail="Memory matrix not initialized")

        if lock_in_state:
            nodes = await memory.get_nodes_by_lock_in_state(lock_in_state, limit=limit)
        else:
            nodes = await memory.get_recent_nodes(limit=limit)

        # Filter by type if specified
        if node_type:
            nodes = [n for n in nodes if n.node_type == node_type]

        return [
            NodeResponse(
                id=n.id,
                node_type=n.node_type,
                content=n.content,
                source=n.source,
                confidence=n.confidence,
                importance=n.importance,
                access_count=n.access_count,
                reinforcement_count=n.reinforcement_count,
                lock_in=n.lock_in,
                lock_in_state=n.lock_in_state,
                created_at=n.created_at.isoformat() if hasattr(n.created_at, 'isoformat') else str(n.created_at),
            )
            for n in nodes
        ]
    except Exception as e:
        logger.error(f"Failed to list nodes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/nodes/{node_id}/access")
async def access_node(node_id: str):
    """
    Record an access to a memory node.

    This increases the node's access count and updates its lock-in coefficient.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix:
        raise HTTPException(status_code=503, detail="Matrix actor not available")

    try:
        # Get the underlying MemoryMatrix
        memory = getattr(matrix, "matrix", None) or getattr(matrix, "_matrix", None) or getattr(matrix, "_memory", None)
        if not memory:
            raise HTTPException(status_code=503, detail="Memory matrix not initialized")

        await memory.record_access(node_id)
        node = await memory.get_node(node_id)

        return {
            "status": "accessed",
            "node_id": node_id,
            "new_access_count": node.access_count if node else 0,
            "new_lock_in": node.lock_in if node else 0,
            "new_lock_in_state": node.lock_in_state if node else "unknown",
        }
    except Exception as e:
        logger.error(f"Failed to record access: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/nodes/{node_id}/reinforce")
async def reinforce_node(node_id: str):
    """
    Reinforce a memory node.

    This marks the node as explicitly important, boosting its lock-in coefficient.
    Reinforced nodes are never pruned.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix:
        raise HTTPException(status_code=503, detail="Matrix actor not available")

    try:
        # Get the underlying MemoryMatrix
        memory = getattr(matrix, "matrix", None) or getattr(matrix, "_matrix", None) or getattr(matrix, "_memory", None)
        if not memory:
            raise HTTPException(status_code=503, detail="Memory matrix not initialized")

        await memory.reinforce_node(node_id)
        node = await memory.get_node(node_id)

        return {
            "status": "reinforced",
            "node_id": node_id,
            "reinforcement_count": node.reinforcement_count if node else 0,
            "new_lock_in": node.lock_in if node else 0,
            "new_lock_in_state": node.lock_in_state if node else "unknown",
        }
    except Exception as e:
        logger.error(f"Failed to reinforce node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memory/stats", response_model=MemoryStatsResponse)
async def get_memory_stats():
    """Get memory statistics including lock-in distribution."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix:
        raise HTTPException(status_code=503, detail="Matrix actor not available")

    try:
        # Get the underlying MemoryMatrix
        memory = getattr(matrix, "matrix", None) or getattr(matrix, "_matrix", None) or getattr(matrix, "_memory", None)
        if not memory:
            raise HTTPException(status_code=503, detail="Memory matrix not initialized")

        # Get stats from Luna's native substrate
        stats = await memory.get_stats()

        return MemoryStatsResponse(
            total_nodes=stats.get("total_nodes", 0),
            nodes_by_type=stats.get("nodes_by_type", {}),
            nodes_by_lock_in=stats.get("nodes_by_lock_in", {}),
            avg_lock_in=stats.get("avg_lock_in", 0.15),
            total_edges=stats.get("total_edges", 0),
            drifting_nodes=stats.get("nodes_by_lock_in", {}).get("drifting", 0),
            fluid_nodes=stats.get("nodes_by_lock_in", {}).get("fluid", 0),
            settled_nodes=stats.get("nodes_by_lock_in", {}).get("settled", 0),
        )
    except Exception as e:
        logger.error(f"Failed to get memory stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# Memory Search & Add (MCP Plugin Endpoints)
# ==============================================================================

class MemorySearchRequest(BaseModel):
    """Request for memory search."""
    query: str
    limit: int = 10
    search_type: str = "hybrid"  # keyword, semantic, hybrid


class MemorySearchResponse(BaseModel):
    """Response from memory search."""
    results: list[dict]
    count: int


class MemoryAddRequest(BaseModel):
    """Request to add a memory node."""
    node_type: str = "FACT"
    content: str
    tags: Optional[list[str]] = None
    confidence: float = 1.0
    metadata: Optional[dict] = None


class MemoryAddResponse(BaseModel):
    """Response from adding a memory node."""
    node_id: str
    success: bool


class SmartFetchRequest(BaseModel):
    """Request for smart context fetch."""
    query: str
    budget_preset: str = "balanced"  # minimal, balanced, rich


class SmartFetchResponse(BaseModel):
    """Response from smart fetch."""
    nodes: list[dict]
    budget_used: int


@app.post("/memory/search", response_model=MemorySearchResponse)
async def memory_search(request: MemorySearchRequest):
    """
    Search memory matrix.

    This is the primary search endpoint used by the MCP plugin.
    Supports keyword, semantic, and hybrid search modes.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix:
        return MemorySearchResponse(results=[], count=0)

    try:
        # Get the underlying MemoryMatrix
        memory = getattr(matrix, "matrix", None) or getattr(matrix, "_matrix", None) or getattr(matrix, "_memory", None)
        if not memory:
            return MemorySearchResponse(results=[], count=0)

        # Use the matrix's search_nodes method
        if hasattr(memory, "search_nodes"):
            nodes = await memory.search_nodes(query=request.query, limit=request.limit)
            # Convert MemoryNode objects to dicts for JSON response
            results = [
                {
                    "id": n.id,
                    "node_type": n.node_type,
                    "content": n.content,
                    "confidence": n.confidence,
                    "lock_in": n.lock_in,
                    "lock_in_state": getattr(n, "lock_in_state", None),
                }
                for n in nodes
            ]
        else:
            # Fallback to recent nodes filtered by content
            nodes = await memory.get_recent_nodes(limit=request.limit * 2)
            query_lower = request.query.lower()
            results = [
                {
                    "id": n.id,
                    "node_type": n.node_type,
                    "content": n.content,
                    "confidence": n.confidence,
                    "lock_in": n.lock_in,
                }
                for n in nodes
                if query_lower in n.content.lower()
            ][:request.limit]

        return MemorySearchResponse(results=results, count=len(results))
    except Exception as e:
        logger.error(f"Memory search error: {e}")
        return MemorySearchResponse(results=[], count=0)


@app.post("/memory/smart-fetch", response_model=SmartFetchResponse)
async def memory_smart_fetch(request: SmartFetchRequest):
    """
    Intelligently fetch relevant context with token budgeting.

    This is the primary memory retrieval endpoint used by the MCP plugin.
    Uses the matrix's get_context method with token budget presets.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix or not matrix.is_ready:
        return SmartFetchResponse(nodes=[], budget_used=0)

    # Map budget presets to token limits
    budget_map = {
        "minimal": 1800,
        "balanced": 3800,
        "rich": 7200,
    }
    max_tokens = budget_map.get(request.budget_preset, 3800)

    try:
        # Get the underlying MemoryMatrix
        memory = getattr(matrix, "matrix", None) or getattr(matrix, "_matrix", None)
        if not memory:
            return SmartFetchResponse(nodes=[], budget_used=0)

        # Use the matrix's get_context method
        nodes = await memory.get_context(query=request.query, max_tokens=max_tokens)

        # Convert MemoryNode objects to dicts
        results = [
            {
                "id": n.id,
                "node_type": n.node_type,
                "content": n.content,
                "confidence": n.confidence,
                "lock_in": n.lock_in,
                "lock_in_state": getattr(n, "lock_in_state", None),
            }
            for n in nodes
        ]

        # Estimate tokens used (rough: ~4 chars per token)
        total_chars = sum(len(n.content) for n in nodes)
        budget_used = total_chars // 4

        return SmartFetchResponse(nodes=results, budget_used=budget_used)

    except Exception as e:
        logger.error(f"Smart fetch error: {e}")
        return SmartFetchResponse(nodes=[], budget_used=0)


@app.post("/memory/add", response_model=MemoryAddResponse)
async def memory_add(request: MemoryAddRequest):
    """
    Add a memory node.

    This is an alias for /memory/nodes with a simpler interface
    used by the MCP plugin.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix:
        raise HTTPException(status_code=503, detail="Matrix actor not available")

    try:
        node_id = await matrix.add_node(
            node_type=request.node_type,
            content=request.content,
            source="mcp",
            confidence=request.confidence,
            importance=0.5,
        )

        return MemoryAddResponse(node_id=node_id, success=True)
    except Exception as e:
        logger.error(f"Failed to add memory node: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/flush")
async def memory_flush():
    """
    Flush pending memory operations.

    Triggers the Scribe to process any pending extractions.
    """
    if _engine is None:
        return {"pending": 0, "flushed": 0, "engine_connected": False}

    scribe = _engine.get_actor("scribe")
    if scribe and hasattr(scribe, "flush_pending"):
        try:
            flushed = await scribe.flush_pending()
            return {"pending": 0, "flushed": flushed}
        except Exception as e:
            logger.error(f"Memory flush error: {e}")
            return {"pending": 0, "flushed": 0, "error": str(e)}

    return {"pending": 0, "flushed": 0, "message": "No pending operations"}


@app.post("/extraction/trigger", response_model=ExtractionResponse)
async def trigger_extraction(request: ExtractionRequest):
    """
    Trigger extraction on content.

    Sends content to the Scribe actor for extraction, which then
    files results via the Librarian actor.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    scribe = _engine.get_actor("scribe")
    if not scribe:
        raise HTTPException(status_code=503, detail="Scribe actor not available")

    librarian = _engine.get_actor("librarian")

    try:
        # Send extraction request to scribe
        msg = Message(
            type="extract_text" if request.immediate else "extract_turn",
            payload={
                "text" if request.immediate else "content": request.content,
                "role": request.role,
                "session_id": request.session_id or "api",
                "source_id": "api",
                "immediate": request.immediate,
            },
        )

        await scribe.handle(msg)

        # Process librarian's mailbox if available
        nodes_created = []
        if librarian:
            while not librarian.mailbox.empty():
                lib_msg = await librarian.mailbox.get()
                await librarian.handle(lib_msg)

        return ExtractionResponse(
            objects_extracted=scribe._objects_extracted,
            edges_extracted=scribe._edges_extracted,
            nodes_created=nodes_created,
        )
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/extraction/prune", response_model=PruneResponse)
async def prune_memory(request: PruneRequest):
    """
    Trigger synaptic pruning.

    Removes low-value edges and optionally prunes drifting nodes
    that haven't been accessed recently.

    Note: Reinforced nodes are NEVER pruned.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    librarian = _engine.get_actor("librarian")
    if not librarian:
        raise HTTPException(status_code=503, detail="Librarian actor not available")

    try:
        edges_before = librarian._edges_pruned
        nodes_before = librarian._nodes_pruned

        msg = Message(
            type="prune",
            payload={
                "age_days": request.age_days,
                "confidence_threshold": request.confidence_threshold,
                "prune_nodes": request.prune_nodes,
                "max_prune_nodes": request.max_prune_nodes,
            },
        )

        await librarian.handle(msg)

        return PruneResponse(
            edges_pruned=librarian._edges_pruned - edges_before,
            nodes_pruned=librarian._nodes_pruned - nodes_before,
        )
    except Exception as e:
        logger.error(f"Pruning failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/extraction/stats")
async def get_extraction_stats():
    """Get extraction statistics from Scribe and Librarian."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    stats = {}

    scribe = _engine.get_actor("scribe")
    if scribe:
        stats["scribe"] = scribe.get_stats()

    librarian = _engine.get_actor("librarian")
    if librarian:
        stats["librarian"] = librarian.get_stats()

    return stats


@app.get("/extraction/history")
async def get_extraction_history(limit: int = 20):
    """
    Get recent extraction history from Scribe.

    Shows the actual extracted objects and edges from recent conversations.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    scribe = _engine.get_actor("scribe")
    if not scribe:
        raise HTTPException(status_code=503, detail="Scribe actor not available")

    history = scribe.get_extraction_history()

    # Return most recent (up to limit)
    return {
        "extractions": history[-limit:] if len(history) > limit else history,
        "total": len(history),
    }


# =============================================================================
# DEBUG ENDPOINTS - Context Visibility
# =============================================================================

class ContextItemResponse(BaseModel):
    """A single item in Luna's context window."""
    id: str
    content: str
    source: str  # IDENTITY, CONVERSATION, MEMORY, etc.
    ring: str  # CORE, INNER, MIDDLE, OUTER
    relevance: float
    tokens: int
    age_turns: int
    ttl_turns: int
    is_expired: bool


class ContextDebugResponse(BaseModel):
    """Debug view of Luna's current context window."""
    current_turn: int
    token_budget: int
    total_tokens: int
    items: list[ContextItemResponse]
    keywords: list[str]  # Keywords Luna is currently aware of
    ring_stats: dict


class ConversationCacheItem(BaseModel):
    """A single item in Luna's conversation cache."""
    role: str  # user or assistant
    content: str
    turn: int
    relevance: float
    age_turns: int


class ConversationCacheResponse(BaseModel):
    """Luna's conversation cache - what she remembers of the conversation."""
    current_turn: int
    max_turns: int  # TTL for conversation items
    items: list[ConversationCacheItem]
    total_tokens: int


@app.get("/debug/conversation-cache", response_model=ConversationCacheResponse)
async def get_conversation_cache():
    """
    Get Luna's conversation cache - the conversation history she's aware of.

    This shows the CONVERSATION items in Luna's RevolvingContext, which is
    what she actually "remembers" of the conversation when generating responses.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    context = _engine.context
    from luna.core.context import ContextSource

    # Collect conversation items from all rings
    items = []
    total_tokens = 0

    for ring in context.rings:
        for item in context.rings[ring]:
            if item.source == ContextSource.CONVERSATION:
                # Parse role from content
                content = item.content
                if content.startswith("User:") or content.startswith("User (desktop):"):
                    role = "user"
                    # Strip the prefix
                    if content.startswith("User (desktop):"):
                        content = content[15:].strip()
                    else:
                        content = content[5:].strip()
                elif content.startswith("Luna:"):
                    role = "assistant"
                    content = content[5:].strip()
                else:
                    role = "unknown"

                items.append(ConversationCacheItem(
                    role=role,
                    content=content,
                    turn=item.created_at_turn,
                    relevance=round(item.relevance, 3),
                    age_turns=item.age_turns,
                ))
                total_tokens += item.tokens

    # Sort by turn (oldest first)
    items.sort(key=lambda x: x.turn)

    return ConversationCacheResponse(
        current_turn=context.current_turn,
        max_turns=20,  # Default TTL for conversation
        items=items,
        total_tokens=total_tokens,
    )


# =============================================================================
# PERSONALITY MONITOR ENDPOINT
# =============================================================================


class PersonalityPatchResponse(BaseModel):
    """A single personality patch."""
    patch_id: str
    topic: str
    subtopic: str
    content: str
    before_state: Optional[str] = None
    after_state: str
    trigger: str
    confidence: float
    lock_in: float
    lock_in_state: str
    reinforcement_count: int
    active: bool
    created_at: str
    last_reinforced: str


class PersonalityStatsResponse(BaseModel):
    """Statistics about personality patches."""
    total_patches: int
    active_patches: int
    average_lock_in: float
    patches_by_topic: dict
    patches_by_lock_in_state: dict


class MaintenanceStatsResponse(BaseModel):
    """Lifecycle maintenance statistics."""
    last_maintenance_run: Optional[str]
    total_decay_operations: int
    total_patches_decayed: int
    total_consolidation_operations: int
    total_patches_consolidated: int
    total_cleanup_operations: int
    total_patches_cleaned: int


class SessionStatsResponse(BaseModel):
    """Session reflection statistics."""
    messages_tracked: int
    last_reflection: Optional[str] = None
    patches_created_this_session: int


class PersonalityDebugResponse(BaseModel):
    """Full personality debug response."""
    stats: PersonalityStatsResponse
    patches: list[PersonalityPatchResponse]
    maintenance: MaintenanceStatsResponse
    session: SessionStatsResponse
    mood_state: str
    bootstrap_status: str


@app.get("/debug/personality", response_model=PersonalityDebugResponse)
async def get_personality_debug():
    """
    Get Luna's personality system state for debugging.

    Shows all personality patches, statistics, maintenance status,
    and session reflection data.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    director = _engine.get_actor("director")
    if not director:
        raise HTTPException(status_code=503, detail="Director actor not available")

    # Get entity context and patch manager
    entity_context = getattr(director, "_entity_context", None)
    patch_manager = getattr(director, "_patch_manager", None)
    lifecycle_manager = getattr(director, "_lifecycle_manager", None)
    reflection_loop = getattr(director, "_reflection_loop", None)

    # Default values
    patches = []
    stats = {
        "total_patches": 0,
        "active_patches": 0,
        "average_lock_in": 0.0,
        "patches_by_topic": {},
    }
    patches_by_lock_in_state = {"drifting": 0, "fluid": 0, "settled": 0}
    maintenance_stats = {
        "last_maintenance_run": None,
        "total_decay_operations": 0,
        "total_patches_decayed": 0,
        "total_consolidation_operations": 0,
        "total_patches_consolidated": 0,
        "total_cleanup_operations": 0,
        "total_patches_cleaned": 0,
    }
    session_stats = {
        "messages_tracked": 0,
        "last_reflection": None,
        "patches_created_this_session": 0,
    }
    mood_state = "neutral"
    bootstrap_status = "unknown"

    # Get patches if patch_manager available
    if patch_manager:
        try:
            stats = await patch_manager.get_stats()
            all_patches = await patch_manager.get_all_active_patches(limit=100)

            for p in all_patches:
                patches.append(PersonalityPatchResponse(
                    patch_id=p.patch_id,
                    topic=p.topic.value if hasattr(p.topic, 'value') else str(p.topic),
                    subtopic=p.subtopic,
                    content=p.content,
                    before_state=p.before_state,
                    after_state=p.after_state,
                    trigger=p.trigger.value if hasattr(p.trigger, 'value') else str(p.trigger),
                    confidence=p.confidence,
                    lock_in=p.lock_in,
                    lock_in_state="settled" if p.lock_in >= 0.7 else "fluid" if p.lock_in >= 0.4 else "drifting",
                    reinforcement_count=p.reinforcement_count,
                    active=p.active,
                    created_at=p.created_at.isoformat() if p.created_at else "",
                    last_reinforced=p.last_reinforced.isoformat() if p.last_reinforced else "",
                ))

                # Count by lock_in state
                if p.lock_in >= 0.7:
                    patches_by_lock_in_state["settled"] += 1
                elif p.lock_in >= 0.4:
                    patches_by_lock_in_state["fluid"] += 1
                else:
                    patches_by_lock_in_state["drifting"] += 1

            # Check bootstrap status
            if stats.get("total_patches", 0) > 0:
                bootstrap_status = "bootstrapped"
            else:
                bootstrap_status = "needs_bootstrap"

        except Exception as e:
            logger.error(f"Failed to get personality patches: {e}")

    # Get lifecycle stats
    if lifecycle_manager:
        try:
            lm_stats = lifecycle_manager.get_maintenance_stats()
            maintenance_stats = {
                "last_maintenance_run": lm_stats.get("last_maintenance_run"),
                "total_decay_operations": lm_stats.get("total_decay_operations", 0),
                "total_patches_decayed": lm_stats.get("total_patches_decayed", 0),
                "total_consolidation_operations": lm_stats.get("total_consolidation_operations", 0),
                "total_patches_consolidated": lm_stats.get("total_patches_consolidated", 0),
                "total_cleanup_operations": lm_stats.get("total_cleanup_operations", 0),
                "total_patches_cleaned": lm_stats.get("total_patches_cleaned", 0),
            }
        except Exception as e:
            logger.debug(f"Could not get lifecycle stats: {e}")

    # Get session stats
    if director:
        try:
            director_session_stats = director.get_session_stats() if hasattr(director, 'get_session_stats') else {}
            session_stats = {
                "messages_tracked": director_session_stats.get("messages_tracked", 0),
                "last_reflection": director_session_stats.get("last_reflection"),
                "patches_created_this_session": director_session_stats.get("patches_created_this_session", 0),
            }
        except Exception as e:
            logger.debug(f"Could not get session stats: {e}")

    # Get mood from consciousness
    if _engine.consciousness:
        mood_state = _engine.consciousness.get_summary().get("mood", "neutral")

    return PersonalityDebugResponse(
        stats=PersonalityStatsResponse(
            total_patches=stats.get("total_patches", 0),
            active_patches=stats.get("active_patches", 0),
            average_lock_in=stats.get("average_lock_in", 0.0),
            patches_by_topic=stats.get("patches_by_topic", {}),
            patches_by_lock_in_state=patches_by_lock_in_state,
        ),
        patches=patches,
        maintenance=MaintenanceStatsResponse(**maintenance_stats),
        session=SessionStatsResponse(**session_stats),
        mood_state=mood_state,
        bootstrap_status=bootstrap_status,
    )


@app.get("/debug/context", response_model=ContextDebugResponse)
async def get_debug_context():
    """
    Get Luna's current context window for debugging.

    Shows everything Luna is currently "aware of" - what goes into her context
    when generating a response. Items are shown with their ring placement,
    relevance scores, and expiration info.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    context = _engine.context

    # Collect all items from all rings
    items = []
    all_content = []

    for ring in context.rings:
        for item in context.rings[ring]:
            items.append(ContextItemResponse(
                id=item.id,
                content=item.content,
                source=item.source.name,
                ring=item.ring.name,
                relevance=round(item.relevance, 3),
                tokens=item.tokens,
                age_turns=item.age_turns,
                ttl_turns=item.ttl_turns,
                is_expired=item.is_expired,
            ))
            all_content.append(item.content.lower())

    # Extract keywords Luna is aware of (simple word frequency)
    from collections import Counter
    import re

    stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                 'would', 'could', 'should', 'may', 'might', 'must', 'shall',
                 'can', 'need', 'to', 'of', 'in', 'for', 'on', 'with', 'at',
                 'by', 'from', 'as', 'into', 'through', 'during', 'before',
                 'after', 'above', 'below', 'between', 'under', 'again',
                 'further', 'then', 'once', 'here', 'there', 'when', 'where',
                 'why', 'how', 'all', 'each', 'few', 'more', 'most', 'other',
                 'some', 'such', 'no', 'nor', 'not', 'only', 'own', 'same',
                 'so', 'than', 'too', 'very', 's', 't', 'just', 'don', 'now',
                 'and', 'but', 'if', 'or', 'because', 'until', 'while', 'this',
                 'that', 'these', 'those', 'am', 'i', 'you', 'he', 'she', 'it',
                 'we', 'they', 'what', 'which', 'who', 'whom', 'my', 'your',
                 'his', 'her', 'its', 'our', 'their', 'me', 'him', 'us', 'them',
                 'user', 'luna', 'assistant', 'content', 'memory', 'type'}

    all_text = " ".join(all_content)
    words = re.findall(r'\b[a-z]{3,}\b', all_text)
    word_counts = Counter(w for w in words if w not in stopwords)
    keywords = [word for word, count in word_counts.most_common(30) if count >= 2]

    # Ring stats
    ring_stats = {}
    for ring in context.rings:
        ring_items = context.rings[ring]
        ring_stats[ring.name] = {
            "count": len(ring_items),
            "tokens": sum(item.tokens for item in ring_items),
            "avg_relevance": round(
                sum(item.relevance for item in ring_items) / len(ring_items), 3
            ) if ring_items else 0,
        }

    return ContextDebugResponse(
        current_turn=context.current_turn,
        token_budget=context.token_budget,
        total_tokens=context._total_tokens(),
        items=items,
        keywords=keywords,
        ring_stats=ring_stats,
    )


# =============================================================================
# VOICE ENDPOINTS
# =============================================================================

# Global voice backend instance
_voice_backend = None


class VoiceStatusResponse(BaseModel):
    """Response from /voice/status endpoint."""
    running: bool
    recording: bool
    hands_free: bool
    stt_provider: str
    tts_provider: str
    persona_connected: bool
    turn_count: int


class VoiceStartRequest(BaseModel):
    """Request body for /voice/start endpoint."""
    hands_free: bool = Field(default=False, description="Enable hands-free mode")


@app.post("/voice/start")
async def start_voice(request: VoiceStartRequest):
    """
    Start the voice system.

    Initializes voice backend with STT, TTS, and connects to Luna Engine.
    """
    global _voice_backend

    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    if _voice_backend and _voice_backend.is_active:
        return {"status": "already_running", "message": "Voice system already active"}

    try:
        # Import voice components
        from voice.backend import VoiceBackend
        from voice.stt.manager import STTProviderType
        from voice.tts.manager import TTSProviderType

        # Create voice backend connected to engine
        _voice_backend = VoiceBackend(
            engine=_engine,
            stt_provider=STTProviderType.MLX_WHISPER,
            tts_provider=TTSProviderType.PIPER,
            hands_free=request.hands_free,
        )

        await _voice_backend.start()

        return {
            "status": "started",
            "message": "Voice system started",
            "hands_free": request.hands_free,
        }
    except ImportError as e:
        logger.error(f"Voice components not available: {e}")
        raise HTTPException(status_code=503, detail=f"Voice components not available: {e}")
    except Exception as e:
        logger.error(f"Failed to start voice: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/voice/stop")
async def stop_voice():
    """Stop the voice system."""
    global _voice_backend

    if _voice_backend is None or not _voice_backend.is_active:
        return {"status": "not_running", "message": "Voice system not active"}

    try:
        await _voice_backend.stop()
        _voice_backend = None

        return {"status": "stopped", "message": "Voice system stopped"}
    except Exception as e:
        logger.error(f"Failed to stop voice: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/voice/status", response_model=VoiceStatusResponse)
async def get_voice_status():
    """Get voice system status."""
    global _voice_backend

    if _voice_backend is None:
        return VoiceStatusResponse(
            running=False,
            recording=False,
            hands_free=False,
            stt_provider="none",
            tts_provider="none",
            persona_connected=False,
            turn_count=0,
        )

    state = _voice_backend.get_state()

    return VoiceStatusResponse(
        running=state["running"],
        recording=state["recording"],
        hands_free=state["hands_free"],
        stt_provider=state["components"]["stt"],
        tts_provider=state["components"]["tts"],
        persona_connected=state["components"]["persona"] == "connected",
        turn_count=state["turn_count"],
    )


@app.post("/voice/listen/start")
async def start_listening():
    """
    Start recording user speech (push-to-talk press).

    Call this when user presses the mic button.
    """
    global _voice_backend

    if _voice_backend is None or not _voice_backend.is_active:
        raise HTTPException(status_code=400, detail="Voice system not active")

    if _voice_backend.hands_free:
        return {"status": "hands_free", "message": "Using hands-free mode - recording is automatic"}

    await _voice_backend.start_listening()

    return {"status": "listening", "message": "Recording started"}


@app.post("/voice/listen/stop")
async def stop_listening():
    """
    Stop recording and process speech (push-to-talk release).

    Call this when user releases the mic button.
    Returns transcription and triggers response generation.
    """
    global _voice_backend

    if _voice_backend is None or not _voice_backend.is_active:
        raise HTTPException(status_code=400, detail="Voice system not active")

    if _voice_backend.hands_free:
        return {"status": "hands_free", "message": "Using hands-free mode - recording stops automatically"}

    # Stop listening and get transcription
    transcription = await _voice_backend.stop_listening()

    if not transcription:
        # Provide more specific feedback
        return {
            "status": "no_speech",
            "message": "No speech detected. Try speaking louder or longer.",
            "transcription": None,
            "hint": "Hold the mic button for at least 1 second while speaking clearly"
        }

    # Trigger response generation (non-blocking)
    asyncio.create_task(_voice_backend.process_and_respond(transcription))

    return {
        "status": "processing",
        "message": "Speech captured, generating response",
        "transcription": transcription,
    }


class SpeakRequest(BaseModel):
    """Request body for speak endpoint."""
    text: str


@app.post("/voice/speak")
async def speak_text(request: SpeakRequest):
    """
    Speak the given text using TTS.

    Use this to have Luna speak a text response when voice mode is on.
    """
    global _voice_backend

    if _voice_backend is None or not _voice_backend.is_active:
        return {"status": "not_running", "message": "Voice system not active"}

    try:
        # Use the TTS to speak
        await _voice_backend.speak(request.text)
        return {"status": "speaking", "text": request.text}
    except Exception as e:
        logger.error(f"Failed to speak: {e}")
        return {"status": "error", "message": str(e)}


@app.get("/voice/stream")
async def voice_stream():
    """
    Stream voice status updates via SSE.

    Returns Server-Sent Events with:
    - event: status - Voice status updates (idle, listening, thinking, speaking)
    - event: transcription - User speech transcribed
    - event: response - Luna's response text
    - event: ping - Keepalive
    """
    global _voice_backend

    async def generate_voice_events() -> AsyncGenerator[str, None]:
        """Generate SSE events for voice status."""
        event_queue: asyncio.Queue[dict] = asyncio.Queue()
        connected = True
        last_status = None

        def on_status_change(status: str) -> None:
            """Callback for status changes."""
            if connected:
                event_queue.put_nowait({
                    "type": "status",
                    "status": status,
                })

        def on_speech_end(transcription: str) -> None:
            """Callback when speech is transcribed."""
            if connected:
                event_queue.put_nowait({
                    "type": "transcription",
                    "text": transcription,
                })

        def on_response(text: str) -> None:
            """Callback when Luna responds."""
            if connected:
                event_queue.put_nowait({
                    "type": "response",
                    "text": text,
                })

        # Register callbacks if voice backend exists
        if _voice_backend:
            _voice_backend.on_status_change(on_status_change)
            _voice_backend.on_speech_end(on_speech_end)
            _voice_backend.on_response(on_response)

        try:
            # Send initial status
            initial_status = "idle"
            if _voice_backend:
                if _voice_backend.is_recording:
                    initial_status = "listening"
                elif _voice_backend.is_active:
                    initial_status = "idle"
                else:
                    initial_status = "inactive"
            else:
                initial_status = "inactive"

            yield f"event: status\ndata: {json.dumps({'connected': True, 'status': initial_status, 'running': _voice_backend is not None and _voice_backend.is_active})}\n\n"

            while connected:
                try:
                    event = await asyncio.wait_for(
                        event_queue.get(),
                        timeout=10.0  # Keepalive every 10s
                    )

                    yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"

                except asyncio.TimeoutError:
                    # Send keepalive ping
                    running = _voice_backend is not None and _voice_backend.is_active
                    yield f"event: ping\ndata: {json.dumps({'running': running})}\n\n"

        except asyncio.CancelledError:
            connected = False

        finally:
            connected = False

    return StreamingResponse(
        generate_voice_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================================
# HUB API: CONVERSATION HISTORY ENDPOINTS
# ============================================================================

class HubSessionCreateRequest(BaseModel):
    """Request to create a new session."""
    app_context: str = "terminal"


class HubSessionResponse(BaseModel):
    """Session details."""
    session_id: str
    started_at: float
    ended_at: Optional[float] = None
    app_context: str


class HubTurnAddRequest(BaseModel):
    """Request to add a turn."""
    session_id: Optional[str] = None
    role: str
    content: str
    tokens: int


class HubTurnResponse(BaseModel):
    """Response after adding a turn."""
    turn_id: int
    tier: str


class HubActiveWindowResponse(BaseModel):
    """Active window turns."""
    turns: list
    total_tokens: int
    turn_count: int


class HubTokenCountResponse(BaseModel):
    """Token count for a tier."""
    total_tokens: int
    turn_count: int


class HubTierRotateRequest(BaseModel):
    """Request to rotate a turn to a new tier."""
    turn_id: int
    new_tier: str


class HubHistorySearchRequest(BaseModel):
    """Request to search history."""
    query: str
    tier: str = "recent"
    session_id: Optional[str] = None
    limit: int = 3
    search_type: str = "hybrid"


class HubHistorySearchResponse(BaseModel):
    """Search results."""
    results: list
    total: int


# --- Session Endpoints ---

@app.post("/hub/session/create", response_model=HubSessionResponse)
async def hub_create_session(request: HubSessionCreateRequest):
    """Create a new conversation session."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    history = _engine.get_actor("history_manager")
    if not history:
        raise HTTPException(status_code=503, detail="History manager not available")

    import time
    session_id = await history.create_session(app_context=request.app_context)
    return HubSessionResponse(
        session_id=session_id,
        started_at=time.time(),
        app_context=request.app_context
    )


@app.post("/hub/session/end")
async def hub_end_session(session_id: str):
    """End a conversation session."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    history = _engine.get_actor("history_manager")
    if not history:
        raise HTTPException(status_code=503, detail="History manager not available")

    await history.end_session(session_id)
    return {"success": True, "session_id": session_id}


@app.get("/hub/session/active", response_model=Optional[HubSessionResponse])
async def hub_get_active_session():
    """Get the currently active session."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    history = _engine.get_actor("history_manager")
    if not history:
        return None

    session = await history.get_active_session()
    if not session:
        return None

    return HubSessionResponse(**session)


# --- Turn Endpoints ---

@app.post("/hub/turn/add", response_model=HubTurnResponse)
async def hub_add_turn(request: HubTurnAddRequest):
    """Add a turn to conversation history."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    history = _engine.get_actor("history_manager")
    if not history:
        raise HTTPException(status_code=503, detail="History manager not available")

    turn_id = await history.add_turn(
        role=request.role,
        content=request.content,
        tokens=request.tokens,
        session_id=request.session_id
    )
    return HubTurnResponse(turn_id=turn_id, tier="active")


@app.get("/hub/active_window", response_model=HubActiveWindowResponse)
async def hub_get_active_window(session_id: Optional[str] = None, limit: int = 10):
    """Get the Active Window turns."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    history = _engine.get_actor("history_manager")
    if not history:
        return HubActiveWindowResponse(turns=[], total_tokens=0, turn_count=0)

    turns = await history.get_active_window(session_id=session_id, limit=limit)
    token_count = await history.get_active_token_count(session_id=session_id)

    return HubActiveWindowResponse(
        turns=turns,
        total_tokens=token_count["total_tokens"],
        turn_count=token_count["turn_count"]
    )


@app.get("/hub/active_token_count", response_model=HubTokenCountResponse)
async def hub_get_active_token_count(session_id: Optional[str] = None):
    """Get token count for Active tier."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    history = _engine.get_actor("history_manager")
    if not history:
        return HubTokenCountResponse(total_tokens=0, turn_count=0)

    counts = await history.get_active_token_count(session_id=session_id)
    return HubTokenCountResponse(**counts)


# --- Tier Endpoints ---

@app.post("/hub/tier/rotate")
async def hub_rotate_tier(request: HubTierRotateRequest):
    """Rotate a turn to a new tier."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    history = _engine.get_actor("history_manager")
    if not history:
        raise HTTPException(status_code=503, detail="History manager not available")

    await history._rotate_turn_tier(request.turn_id, request.new_tier)
    return {"success": True}


@app.get("/hub/tier/oldest_active")
async def hub_get_oldest_active(session_id: Optional[str] = None):
    """Get the oldest turn in Active tier."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    history = _engine.get_actor("history_manager")
    if not history:
        return None

    turn = await history.get_oldest_active_turn(session_id=session_id)
    return turn


# --- Search Endpoints ---

@app.post("/hub/search", response_model=HubHistorySearchResponse)
async def hub_search_history(request: HubHistorySearchRequest):
    """Search conversation history."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    history = _engine.get_actor("history_manager")
    if not history:
        return HubHistorySearchResponse(results=[], total=0)

    results = await history.search_recent(
        query=request.query,
        limit=request.limit,
        search_type=request.search_type,
        session_id=request.session_id
    )

    return HubHistorySearchResponse(results=results, total=len(results))


# --- History Manager Stats ---

@app.get("/hub/stats")
async def hub_get_history_stats():
    """Get history manager statistics."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    history = _engine.get_actor("history_manager")
    if not history:
        return {"error": "History manager not available"}

    return history.get_stats()


# =============================================================================
# TUNING ENDPOINTS
# =============================================================================

# Global tuning instances
_param_registry = None
_evaluator = None
_session_manager = None


class TuningParamResponse(BaseModel):
    """Response with parameter details."""
    name: str
    value: float
    default: float
    bounds: tuple
    step: float
    category: str
    description: str
    is_overridden: bool


class TuningParamSetRequest(BaseModel):
    """Request to set a parameter value."""
    value: float


class TuningSessionNewRequest(BaseModel):
    """Request to start a new tuning session."""
    focus: str = Field(default="all", description="Area of focus: memory, routing, latency, context, all")
    notes: str = Field(default="")


class TuningSessionResponse(BaseModel):
    """Response with session details."""
    session_id: str
    focus: str
    started_at: str
    best_iteration: int
    best_score: float
    iteration_count: int


class TuningEvalResponse(BaseModel):
    """Response with evaluation results."""
    overall_score: float
    memory_recall_score: float
    context_retention_score: float
    routing_score: float
    avg_latency_ms: float
    p95_latency_ms: float
    total_tests: int
    passed_tests: int
    failed_tests: int


class TuningCompareResponse(BaseModel):
    """Response with iteration comparison."""
    iteration_1: int
    iteration_2: int
    score_1: float
    score_2: float
    score_diff: float
    param_diffs: dict
    metric_diffs: dict


async def _ensure_tuning_initialized():
    """Initialize tuning components if needed."""
    global _param_registry, _evaluator, _session_manager

    if _param_registry is None:
        from luna.tuning.params import ParamRegistry
        from luna.tuning.evaluator import Evaluator
        from luna.tuning.session import TuningSessionManager

        _param_registry = ParamRegistry(_engine)
        _evaluator = Evaluator(_engine)
        _session_manager = TuningSessionManager()
        await _session_manager.initialize()


@app.get("/tuning/params")
async def list_tuning_params(category: Optional[str] = None):
    """
    List all tunable parameters.

    - category: Filter by category (inference, memory, router, etc.)
    """
    await _ensure_tuning_initialized()

    params = _param_registry.list_params(category)
    categories = _param_registry.list_categories()

    return {
        "params": params,
        "categories": categories,
        "count": len(params),
    }


@app.get("/tuning/params/{name:path}", response_model=TuningParamResponse)
async def get_tuning_param(name: str):
    """Get details for a specific parameter."""
    await _ensure_tuning_initialized()

    try:
        spec = _param_registry.get_spec(name)
        value = _param_registry.get(name)
        is_overridden = name in _param_registry._overrides

        return TuningParamResponse(
            name=name,
            value=value,
            default=spec.default,
            bounds=spec.bounds,
            step=spec.step,
            category=spec.category,
            description=spec.description,
            is_overridden=is_overridden,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Parameter not found: {name}")


@app.post("/tuning/params/{name:path}")
async def set_tuning_param(name: str, request: TuningParamSetRequest):
    """
    Set a parameter value.

    Returns the previous value and runs evaluation if session active.
    """
    await _ensure_tuning_initialized()

    try:
        prev_value = _param_registry.set(name, request.value)

        result = {
            "name": name,
            "previous_value": prev_value,
            "new_value": request.value,
        }

        # Run evaluation if session active
        if _session_manager.current_session:
            eval_results = await _evaluator.run_all()
            await _session_manager.add_iteration(
                params_changed={name: request.value},
                param_snapshot=_param_registry.get_all(),
                eval_results=eval_results,
                notes=f"Set {name}={request.value}",
            )
            result["eval_score"] = eval_results.overall_score
            result["iteration"] = len(_session_manager.current_session.iterations)

        return result
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Parameter not found: {name}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/tuning/param-reset/{name:path}")
async def reset_tuning_param(name: str):
    """Reset a parameter to its default value."""
    await _ensure_tuning_initialized()

    try:
        spec = _param_registry.get_spec(name)
        prev_value = _param_registry.reset(name)

        return {
            "name": name,
            "previous_value": prev_value,
            "new_value": spec.default,
            "was_overridden": prev_value is not None,
        }
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Parameter not found: {name}")


@app.post("/tuning/session/new", response_model=TuningSessionResponse)
async def start_tuning_session(request: TuningSessionNewRequest):
    """
    Start a new tuning session.

    Creates a session, records baseline parameters, and runs initial evaluation.
    """
    await _ensure_tuning_initialized()

    # End existing session if any
    if _session_manager.current_session:
        await _session_manager.end_session()

    # Get baseline parameters
    base_params = _param_registry.get_all()

    # Create session
    session = await _session_manager.new_session(
        focus=request.focus,
        base_params=base_params,
        notes=request.notes,
    )

    # Run baseline evaluation
    results = await _evaluator.run_all()
    await _session_manager.add_iteration(
        params_changed={},
        param_snapshot=base_params,
        eval_results=results,
        notes="Baseline",
    )

    return TuningSessionResponse(
        session_id=session.session_id,
        focus=session.focus,
        started_at=session.started_at,
        best_iteration=session.best_iteration,
        best_score=session.best_score,
        iteration_count=len(session.iterations),
    )


@app.get("/tuning/session")
async def get_tuning_session():
    """Get current tuning session."""
    await _ensure_tuning_initialized()

    session = _session_manager.current_session
    if not session:
        return {"active": False}

    return {
        "active": True,
        "session_id": session.session_id,
        "focus": session.focus,
        "started_at": session.started_at,
        "best_iteration": session.best_iteration,
        "best_score": session.best_score,
        "iteration_count": len(session.iterations),
        "iterations": [
            {
                "num": i.iteration_num,
                "score": i.score,
                "params_changed": i.params_changed,
                "notes": i.notes,
                "created_at": i.created_at,
            }
            for i in session.iterations
        ],
    }


@app.post("/tuning/session/end")
async def end_tuning_session():
    """End the current tuning session."""
    await _ensure_tuning_initialized()

    session = await _session_manager.end_session()
    if not session:
        return {"ended": False, "message": "No active session"}

    return {
        "ended": True,
        "session_id": session.session_id,
        "best_iteration": session.best_iteration,
        "best_score": session.best_score,
        "total_iterations": len(session.iterations),
    }


@app.post("/tuning/eval", response_model=TuningEvalResponse)
async def run_tuning_eval(category: Optional[str] = None):
    """
    Run evaluation.

    - category: Optional category to evaluate (memory_recall, context_retention, routing, latency)
    """
    await _ensure_tuning_initialized()

    if category:
        results = await _evaluator.run_category(category)
    else:
        results = await _evaluator.run_all()

    # Record iteration if session active
    if _session_manager.current_session:
        await _session_manager.add_iteration(
            params_changed={},
            param_snapshot=_param_registry.get_all(),
            eval_results=results,
            notes=f"Eval: {category or 'all'}",
        )

    return TuningEvalResponse(
        overall_score=results.overall_score,
        memory_recall_score=results.memory_recall_score,
        context_retention_score=results.context_retention_score,
        routing_score=results.routing_score,
        avg_latency_ms=results.avg_latency_ms,
        p95_latency_ms=results.p95_latency_ms,
        total_tests=results.total_tests,
        passed_tests=results.passed_tests,
        failed_tests=results.failed_tests,
    )


@app.get("/tuning/compare", response_model=TuningCompareResponse)
async def compare_tuning_iterations(iter1: int = 1, iter2: Optional[int] = None):
    """
    Compare two iterations.

    - iter1: First iteration number (default: 1)
    - iter2: Second iteration number (default: latest)
    """
    await _ensure_tuning_initialized()

    session = _session_manager.current_session
    if not session:
        raise HTTPException(status_code=400, detail="No active session")

    if not session.iterations:
        raise HTTPException(status_code=400, detail="No iterations to compare")

    if iter2 is None:
        iter2 = len(session.iterations)

    try:
        comparison = _session_manager.compare_iterations(iter1, iter2)
        return TuningCompareResponse(**comparison)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/tuning/best")
async def get_best_params():
    """Get parameters from the best iteration."""
    await _ensure_tuning_initialized()

    session = _session_manager.current_session
    if not session:
        raise HTTPException(status_code=400, detail="No active session")

    params = _session_manager.get_best_params()
    return {
        "best_iteration": session.best_iteration,
        "best_score": session.best_score,
        "params": params,
    }


@app.post("/tuning/apply-best")
async def apply_best_params():
    """Apply parameters from the best iteration."""
    await _ensure_tuning_initialized()

    session = _session_manager.current_session
    if not session:
        raise HTTPException(status_code=400, detail="No active session")

    best_params = _session_manager.get_best_params()
    count = _param_registry.import_params(best_params)

    return {
        "applied": count,
        "best_iteration": session.best_iteration,
        "best_score": session.best_score,
    }


@app.get("/tuning/sessions")
async def list_tuning_sessions(limit: int = 10):
    """List recent tuning sessions."""
    await _ensure_tuning_initialized()

    sessions = await _session_manager.list_sessions(limit)
    return {
        "sessions": sessions,
        "count": len(sessions),
    }


def create_app() -> FastAPI:
    """Factory function for creating the app."""
    return app
