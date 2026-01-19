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
        logger.debug(f"History: matrix ready={matrix.is_ready}, eclissi={matrix._eclissi_matrix is not None}")
        if matrix._eclissi_matrix:
            cursor = matrix._eclissi_matrix.conn.execute("""
                SELECT content, timestamp FROM memory_nodes
                WHERE tags LIKE '%"conversation"%'
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
            rows = cursor.fetchall()
            logger.debug(f"History: found {len(rows)} conversation turns")

            messages = []
            for row in rows:
                # Row might be tuple or dict depending on connection settings
                if isinstance(row, tuple):
                    content = row[0]
                    timestamp = row[1]
                else:
                    content = row['content']
                    timestamp = row['timestamp']
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
        else:
            logger.warning("History: No Eclissi matrix available")
            return HistoryResponse(messages=[], total=0)
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
            created_at=node.created_at,
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
        created_at=node.created_at,
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
        memory = matrix._matrix or matrix._memory
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
                created_at=n.created_at,
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
        memory = matrix._matrix or matrix._memory
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
        memory = matrix._matrix or matrix._memory
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
        memory = matrix._matrix or matrix._memory
        if not memory:
            raise HTTPException(status_code=503, detail="Memory matrix not initialized")

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


def create_app() -> FastAPI:
    """Factory function for creating the app."""
    return app
