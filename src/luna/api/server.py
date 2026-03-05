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

# Load .env before any other imports (providers check env at import time)
import os
from pathlib import Path
try:
    from dotenv import load_dotenv
    # Find project root (src/luna/api/server.py -> project root)
    _project_root = Path(__file__).parent.parent.parent.parent
    _env_path = _project_root / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except ImportError:
    pass  # dotenv not installed

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional, AsyncGenerator

import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field

from luna.services.orb_state import OrbStateManager, ExpressionConfig
from luna.services.dimensional_engine import DimensionalEngine
from luna.services.performance_state import VoiceKnobs, OrbKnobs, EMOTION_PRESETS, EmotionPreset
from luna.services.performance_orchestrator import PerformanceOrchestrator

from luna.engine import LunaEngine, EngineConfig
from luna.core.events import InputEvent, EventType
from luna.actors.base import Message
from luna.agentic.router import ExecutionPath
from luna.diagnostics import run_startup_check, start_watchdog
from luna.services.kozmo.routes import router as kozmo_router
from luna.services.guardian.routes import router as guardian_router
from luna.services.guardian.memory_bridge import GuardianMemoryBridge

# QA System imports
try:
    from luna.qa import QAValidator, InferenceContext, get_default_assertions
    from luna.qa.validator import get_validator as get_qa_validator
    from luna.qa.assertions import Assertion, PatternConfig
    QA_AVAILABLE = True
except ImportError:
    QA_AVAILABLE = False

logger = logging.getLogger(__name__)


# =============================================================================
# QA Background Validation
# =============================================================================

async def _run_qa_validation_background(
    query: str,
    response_text: str,
    response_data: dict,
) -> None:
    """
    Run QA validation in background (fire-and-forget).

    This does not block the response to the user.
    """
    if not QA_AVAILABLE:
        return

    try:
        validator = get_qa_validator()

        # Yield event loop so director can finish writing _last_system_prompt
        # before we read it. The background task fires immediately after the
        # response callback, which runs in the same processing cycle as the
        # prompt write — one yield ensures the write completes first.
        await asyncio.sleep(0)

        # Get personality info from director
        personality_injected = False
        personality_length = 0
        system_prompt = ""
        virtues_loaded = False
        narration_applied = response_data.get("narration_applied", False)

        if _engine:
            director = _engine.get_actor("director")
            if director:
                prompt_info = director.get_last_system_prompt()
                if prompt_info.get("available"):
                    system_prompt = prompt_info.get("full_prompt", "")
                    personality_length = prompt_info.get("length", 0)
                    personality_injected = personality_length > 1000
                    # Check if virtues/identity loaded
                    virtues_loaded = getattr(director, "_identity_buffer", None) is not None

        # Get memory stats for QA assertions
        memory_stats = {}
        if _engine:
            matrix = _engine.get_actor("matrix")
            if matrix:
                mem = getattr(matrix, "matrix", None) or getattr(matrix, "_matrix", None)
                if mem:
                    try:
                        memory_stats = await mem.get_stats()
                        # If edges = 0 on first inference after restart, retry once
                        # (matrix may still be initializing its stats cache)
                        if memory_stats.get("total_edges", 0) == 0:
                            await asyncio.sleep(0.1)
                            memory_stats = await mem.get_stats()
                    except Exception:
                        pass

        # Build inference context from response data
        ctx = InferenceContext(
            query=query,
            final_response=response_text,
            raw_response=response_text,
            provider_used=response_data.get("model", "unknown"),
            latency_ms=response_data.get("latency_ms", 0),
            input_tokens=response_data.get("input_tokens", 0),
            output_tokens=response_data.get("output_tokens", 0),
            # Infer route from delegation flags
            route="FULL_DELEGATION" if response_data.get("delegated") else "LOCAL_ONLY",
            # Mark if local model was used
            providers_tried=[response_data.get("model", "unknown")],
            # Personality tracking
            personality_injected=personality_injected,
            personality_length=personality_length,
            system_prompt=system_prompt,
            virtues_loaded=virtues_loaded,
            narration_applied=narration_applied,
            memory_stats=memory_stats,
        )

        # Run validation (this stores the report automatically)
        report = validator.validate(ctx)

        if not report.passed:
            logger.warning(
                f"[QA] Inference failed {report.failed_count} assertions: "
                f"{[a.id for a in report.failed_assertions]}"
            )
        else:
            logger.debug(f"[QA] Inference passed all {len(report.assertions)} assertions")

    except Exception as e:
        logger.error(f"[QA] Background validation error: {e}")

# Global engine instance
_engine: Optional[LunaEngine] = None

# Guardian memory bridge
_guardian_bridge: Optional[GuardianMemoryBridge] = None

# Global orb state manager and WebSocket connections
_orb_state_manager: Optional[OrbStateManager] = None
_orb_websockets: set[WebSocket] = set()

# Global chat WebSocket connections (for shared session viewing)
_chat_websockets: set[WebSocket] = set()

# Global identity WebSocket connections (FaceID state)
_identity_websockets: set[WebSocket] = set()

# Global performance orchestrator (coordinates voice + orb)
_performance_orchestrator: Optional[PerformanceOrchestrator] = None


# ── Security helpers ─────────────────────────────────────────────────────────

async def _resolve_current_bridge():
    """Get the current speaker's BridgeResult from FaceID → AccessBridge."""
    if _engine is None:
        return None
    identity_actor = _engine.get_actor("identity")
    if not identity_actor or not identity_actor.current.is_present:
        return None
    entity_id = identity_actor.current.entity_id
    if not entity_id:
        return None
    try:
        from luna.identity.bridge import AccessBridge
        matrix = _engine.get_actor("matrix")
        mem = getattr(matrix, "_matrix", None) if matrix else None
        if not mem:
            return None
        bridge = AccessBridge(mem.db)
        return await bridge.lookup(entity_id)
    except Exception:
        return None


async def _require_admin():
    """Require admin identity via FaceID. Raises 403 if not admin."""
    bridge = await _resolve_current_bridge()
    if bridge is None or bridge.luna_tier != "admin":
        raise HTTPException(
            status_code=403,
            detail="Admin identity required (FaceID not recognized or insufficient tier)",
        )
    return bridge


async def _gate_results(results: list, source: str = "api") -> list:
    """Apply permission gate to a list of result dicts/nodes. Returns allowed list."""
    from luna.identity.permissions import gate_content
    from luna.identity.bridge import BridgeResult
    bridge = await _resolve_current_bridge()
    db = None
    try:
        if _engine:
            matrix = _engine.get_actor("matrix")
            mem = getattr(matrix, "_matrix", None) if matrix else None
            if mem:
                db = mem.db
    except Exception:
        pass

    # MCP API calls are local/trusted — if no FaceID identity is active,
    # treat as admin rather than denying all DOCUMENT nodes silently.
    # The MCP server itself is authenticated by the session that started it.
    if bridge is None and source.startswith("api/"):
        bridge = BridgeResult(
            entity_id="mcp-local",
            luna_tier="admin",
            dataroom_tier=1,
            dataroom_categories=[],
        )
        logger.debug("GATE: No FaceID active — using admin fallback for MCP source '%s'", source)

    allowed, _denied = await gate_content(results, bridge, db=db, source=source)
    return allowed


# ─────────────────────────────────────────────────────────────────────────────

async def _broadcast_chat_message(message_type: str, data: dict) -> None:
    """
    Broadcast a chat message to all connected WebSocket clients.

    This enables multiple viewers to see the same conversation in real-time.
    message_type: 'user' | 'assistant' | 'system'
    """
    if not _chat_websockets:
        return

    payload = {
        "type": message_type,
        "data": data,
        "timestamp": asyncio.get_event_loop().time(),
    }

    disconnected = set()
    for ws in _chat_websockets:
        try:
            await ws.send_json(payload)
        except Exception:
            disconnected.add(ws)

    _chat_websockets.difference_update(disconnected)


class MessageRequest(BaseModel):
    """Request body for /message endpoint."""
    message: str = Field(..., min_length=1, max_length=10000)
    timeout: float = Field(default=30.0, ge=1.0, le=120.0)
    stream: bool = Field(default=False, description="Use streaming mode")
    source: str = Field(default="api", description="Origin surface: eclissi, mcp, voice, guardian, api")


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


class IdentityState(BaseModel):
    """Current FaceID identity state."""
    enabled: bool = False
    is_present: bool = False
    entity_name: Optional[str] = None
    luna_tier: str = "unknown"
    confidence: float = 0.0


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
    identity: Optional[IdentityState] = None  # FaceID identity state


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
    Critical systems are verified BEFORE anything else.
    """
    global _engine

    # =========================================================
    # CRITICAL SYSTEMS CHECK — Luna refuses to start with a
    # disconnected brain. This gate prevents silent failures
    # that cause confabulation.
    # =========================================================
    logger.info("Running critical systems check...")
    run_startup_check(strict=True)  # Exits if checks fail

    logger.info("Starting Luna Engine...")

    # Create and start engine
    config = EngineConfig(
        faceid_enabled=True,  # Always enable — IdentityActor handles init failures gracefully
    )
    _engine = LunaEngine(config)

    # Start engine in background
    engine_task = asyncio.create_task(_engine.run())

    # Wait for engine to be ready
    await asyncio.sleep(0.5)

    # Initialize orb state manager
    global _orb_state_manager
    try:
        import json
        from pathlib import Path
        config_path = Path(__file__).parent.parent.parent.parent / "config" / "personality.json"
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
                expression_config = ExpressionConfig.from_dict(config.get("expression", {}))
        else:
            expression_config = ExpressionConfig()
        _orb_state_manager = OrbStateManager(expression_config)
        logger.info("Orb state manager initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize orb state manager: {e}")
        _orb_state_manager = OrbStateManager()

    # Wire CacheActor → OrbStateManager (dimensional feed)
    if _engine:
        _cache_actor = _engine.get_actor("cache")
        if _cache_actor and hasattr(_cache_actor, "set_orb_state_manager"):
            _cache_actor.set_orb_state_manager(_orb_state_manager)
            logger.info("CacheActor wired to OrbStateManager")

    # Subscribe to identity state changes (FaceID → WebSocket broadcast)
    identity_actor = _engine.get_actor("identity")
    if identity_actor and hasattr(identity_actor, "on_change"):
        def _on_identity_change(current):
            asyncio.create_task(_broadcast_identity_state())
        identity_actor.on_change(_on_identity_change)
        logger.info("Identity WebSocket broadcast wired")

    # Phase 1 — Engine Ownership: wire Engine-owned AiBrarian into consumers
    if _engine and getattr(_engine, "aibrarian", None) is not None:
        try:
            from luna_mcp.tools.aibrarian import set_engine as _mcp_set_engine
            _mcp_set_engine(_engine.aibrarian)
            logger.info("MCP aibrarian tools wired to Engine-owned AiBrarianEngine")
        except Exception as _e:
            logger.warning(f"Failed to wire MCP aibrarian tools: {_e}")
        try:
            from luna.tools.dataroom_tools import set_engine as _dr_set_engine
            _dr_set_engine(_engine.aibrarian)
            logger.info("Dataroom tools wired to Engine-owned AiBrarianEngine")
        except Exception as _e:
            logger.warning(f"Failed to wire dataroom tools: {_e}")

    # Start runtime watchdog for continuous health monitoring
    watchdog_task = await start_watchdog(check_interval=60, engine=_engine)
    logger.info("Runtime watchdog started")

    # Auto-restore identity bypass if sentinel file exists
    # Runs as a background task so engine actor loop is fully running first
    _bypass_sentinel = Path(__file__).parent.parent.parent.parent / "config" / "identity_bypass.json"
    if _bypass_sentinel.exists():
        async def _auto_restore_bypass():
            await asyncio.sleep(2)  # Let engine actor loop fully start
            try:
                import json as _json, time as _time
                _ia = _engine.get_actor("identity") if _engine else None
                if not _ia:
                    logger.warning("[BYPASS] Auto-restore skipped — identity actor not found")
                    return
                _bypass_data = _json.loads(_bypass_sentinel.read_text())
                _ia.current.entity_id = _bypass_data.get("entity_id", "ahab")
                _ia.current.entity_name = _bypass_data.get("entity_name", "Ahab")
                _ia.current.confidence = 1.0
                _ia.current.luna_tier = _bypass_data.get("luna_tier", "admin")
                _ia.current.dataroom_tier = _bypass_data.get("dataroom_tier", 1)
                _ia.current.dataroom_categories = _bypass_data.get("dataroom_categories", [1,2,3,4,5,6,7,8,9])
                _ia.current.last_seen = _time.time()
                _ia._bypass_active = True

                async def _bypass_keepalive_startup():
                    while getattr(_ia, '_bypass_active', False):
                        _ia.current.last_seen = _time.time()
                        await asyncio.sleep(5)
                asyncio.create_task(_bypass_keepalive_startup())
                logger.info("[BYPASS] Auto-restored identity bypass from sentinel file")
            except Exception as _e:
                logger.warning(f"[BYPASS] Failed to restore bypass from sentinel: {_e}")
        asyncio.create_task(_auto_restore_bypass())

    logger.info("Luna Engine ready")

    yield

    # Shutdown
    logger.info("Stopping Luna Engine...")

    # Stop the watchdog first
    if watchdog_task and not watchdog_task.done():
        watchdog_task.cancel()
        logger.info("Runtime watchdog stopped")

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def guardian_project_scope(request: Request, call_next):
    """Auto-activate guardian project scope and sync memory bridge."""
    global _guardian_bridge
    path = request.url.path
    # Skip sync/clear/status endpoints — they manage the bridge directly
    _bridge_paths = ("/guardian/api/sync", "/guardian/api/clear")
    if path.startswith("/guardian/") and not any(path.startswith(p) for p in _bridge_paths) and _engine is not None:
        # Activate project scope (mirrors /project/activate pattern)
        if _engine.active_project != "guardian-kinoni":
            _engine.set_active_project("guardian-kinoni")
            # Notify Librarian for thread-aware context
            librarian = _engine.get_actor("librarian")
            if librarian:
                msg = Message(type="set_project_context", payload={"slug": "guardian-kinoni"})
                await librarian.handle(msg)

        # Auto-sync on first request (lazy init)
        if _guardian_bridge is None:
            _guardian_bridge = GuardianMemoryBridge(_engine)
        if not _guardian_bridge.is_synced:
            try:
                stats = await _guardian_bridge.sync_all()
                logger.info(f"Guardian bridge auto-synced: {stats}")
            except Exception as e:
                logger.error(f"Guardian bridge auto-sync failed: {e}")

    response = await call_next(request)
    return response


# Mount KOZMO service router
app.include_router(kozmo_router)

# Mount GUARDIAN service router
app.include_router(guardian_router)


# ============================================
# GUARDIAN MEMORY BRIDGE ENDPOINTS
# ============================================

@app.post("/guardian/api/sync")
async def guardian_sync():
    """Sync Guardian demo data into Luna's Memory Matrix."""
    global _guardian_bridge
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    if _guardian_bridge is None:
        _guardian_bridge = GuardianMemoryBridge(_engine)

    stats = await _guardian_bridge.sync_all()
    return {"status": "synced", **stats}


@app.post("/guardian/api/clear")
async def guardian_clear():
    """Clear Guardian data from Memory Matrix."""
    global _guardian_bridge
    if _guardian_bridge is None:
        return {"status": "nothing_to_clear"}

    removed = await _guardian_bridge.clear()
    return {"status": "cleared", "removed": removed}


@app.get("/guardian/api/sync/status")
async def guardian_sync_status():
    """Check if Guardian data is synced."""
    if _guardian_bridge is None:
        return {"synced": False}
    return {"synced": _guardian_bridge.is_synced}


# Serve KOZMO project assets (generated reference images, etc.)
try:
    from pathlib import Path as _Path
    from fastapi.staticfiles import StaticFiles
    _kozmo_assets = _Path("data/kozmo_projects")
    _kozmo_assets.mkdir(parents=True, exist_ok=True)
    app.mount("/kozmo-assets", StaticFiles(directory=str(_kozmo_assets)), name="kozmo-assets")
except Exception:
    pass  # Non-fatal — assets won't be served if dir is missing

# Serve GUARDIAN frontend
try:
    _guardian_frontend = _Path(__file__).resolve().parent.parent.parent.parent.parent / "Eclissi-Guardian" / "frontend"
    if not _guardian_frontend.exists():
        _guardian_frontend = _Path("frontend/guardian")
    if _guardian_frontend.exists():
        from starlette.responses import RedirectResponse as _RedirectResponse

        @app.get("/guardian")
        async def _guardian_redirect():
            return _RedirectResponse(url="/guardian/")

        app.mount("/guardian", StaticFiles(directory=str(_guardian_frontend), html=True), name="guardian")
        logger.info(f"Guardian frontend mounted at /guardian from {_guardian_frontend}")
except Exception as e:
    logger.warning(f"Guardian frontend mount failed: {e}")

# Serve LUNAR STUDIO frontend (Expression Pipeline Diagnostic)
try:
    _studio_frontend = _Path(__file__).resolve().parent.parent.parent.parent / "Tools" / "Luna-Expression-Pipeline" / "diagnostic" / "dist"
    if _studio_frontend.exists():
        from starlette.responses import RedirectResponse

        @app.get("/studio")
        async def _studio_redirect():
            return RedirectResponse(url="/studio/")

        app.mount("/studio", StaticFiles(directory=str(_studio_frontend), html=True), name="studio")
        logger.info(f"Lunar Studio mounted at /studio from {_studio_frontend}")
except Exception as e:
    logger.warning(f"Lunar Studio mount failed: {e}")


# ============================================
# ORB STATE WEBSOCKET
# ============================================

async def _broadcast_orb_state():
    """Broadcast current orb state to all connected WebSocket clients."""
    if _orb_state_manager is None:
        return
    state_dict = _orb_state_manager.to_dict()
    disconnected = set()
    for ws in _orb_websockets:
        try:
            await ws.send_json(state_dict)
        except Exception:
            disconnected.add(ws)
    _orb_websockets.difference_update(disconnected)


@app.websocket("/ws/orb")
async def orb_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for Luna Orb state streaming.

    Clients receive JSON updates whenever the orb state changes:
    {
        "animation": "pulse",
        "color": "#a78bfa",
        "brightness": 1.0,
        "source": "gesture",
        "timestamp": "2025-01-27T12:00:00"
    }
    """
    await websocket.accept()
    _orb_websockets.add(websocket)
    logger.info(f"Orb WebSocket connected. Total: {len(_orb_websockets)}")

    # Send current state immediately
    if _orb_state_manager:
        await websocket.send_json(_orb_state_manager.to_dict())

    # Subscribe to state changes
    if _orb_state_manager:
        def on_state_change(state):
            asyncio.create_task(_broadcast_orb_state())
        unsubscribe = _orb_state_manager.subscribe(on_state_change)
    else:
        unsubscribe = lambda: None

    try:
        while True:
            # Keep connection alive, ignore incoming messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _orb_websockets.discard(websocket)
        unsubscribe()
        logger.info(f"Orb WebSocket disconnected. Total: {len(_orb_websockets)}")


@app.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for shared chat session viewing.

    Clients receive JSON updates for all messages (user and assistant):
    {
        "type": "user" | "assistant" | "system",
        "data": {
            "content": "message text",
            "model": "...",  // for assistant
            "metadata": {...}
        },
        "timestamp": 1234567890
    }

    This allows multiple viewers to see the same conversation in real-time,
    including messages sent via API (curl, MCP, etc).
    """
    await websocket.accept()
    _chat_websockets.add(websocket)
    logger.info(f"Chat WebSocket connected. Total: {len(_chat_websockets)}")

    # Send connection confirmation
    await websocket.send_json({
        "type": "system",
        "data": {"content": "Connected to Luna chat stream"},
        "timestamp": asyncio.get_event_loop().time(),
    })

    try:
        while True:
            # Keep connection alive, ignore incoming messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _chat_websockets.discard(websocket)
        logger.info(f"Chat WebSocket disconnected. Total: {len(_chat_websockets)}")


# ============================================
# IDENTITY STATE WEBSOCKET (FaceID)
# ============================================

async def _broadcast_identity_state():
    """Broadcast current identity state to all connected WebSocket clients."""
    if _engine is None:
        return

    identity_actor = _engine.get_actor("identity")
    if not identity_actor:
        return

    current = identity_actor.current
    payload = {
        "type": "identity_update",
        "data": {
            "is_present": current.is_present,
            "entity_id": current.entity_id,
            "entity_name": current.entity_name,
            "confidence": round(current.confidence, 3),
            "luna_tier": current.luna_tier,
            "dataroom_tier": current.dataroom_tier,
            "last_seen": current.last_seen,
        },
        "timestamp": asyncio.get_event_loop().time(),
    }

    disconnected = set()
    for ws in _identity_websockets:
        try:
            await ws.send_json(payload)
        except Exception:
            disconnected.add(ws)
    _identity_websockets.difference_update(disconnected)


@app.websocket("/ws/identity")
async def identity_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for FaceID identity state streaming.

    Clients receive JSON updates when identity changes:
    {
        "type": "identity_update",
        "data": {
            "is_present": true,
            "entity_id": "entity_2ca6b7c7",
            "entity_name": "Ahab",
            "confidence": 0.987,
            "luna_tier": "admin",
            "dataroom_tier": 1,
            "last_seen": 1708349600.0
        },
        "timestamp": 1234567890
    }
    """
    await websocket.accept()
    _identity_websockets.add(websocket)
    logger.info(f"Identity WebSocket connected. Total: {len(_identity_websockets)}")

    # Send current state immediately
    identity_actor = _engine.get_actor("identity") if _engine else None
    if identity_actor:
        current = identity_actor.current
        await websocket.send_json({
            "type": "identity_update",
            "data": {
                "is_present": current.is_present,
                "entity_id": current.entity_id,
                "entity_name": current.entity_name,
                "confidence": round(current.confidence, 3),
                "luna_tier": current.luna_tier,
                "dataroom_tier": current.dataroom_tier,
                "last_seen": current.last_seen,
            },
            "timestamp": asyncio.get_event_loop().time(),
        })

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _identity_websockets.discard(websocket)
        logger.info(f"Identity WebSocket disconnected. Total: {len(_identity_websockets)}")


# ============================================
# BROWSER FACE RECOGNITION ENDPOINT
# ============================================

# ============================================
# FACEID PROXY — forwards to FaceID microservice on :8100
# ============================================

FACEID_SERVICE = "http://127.0.0.1:8101"


async def _proxy_faceid(path: str, body: dict) -> dict:
    """Forward a request to the FaceID microservice."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(f"{FACEID_SERVICE}{path}", json=body)
            return resp.json()
    except httpx.ConnectError:
        return {"error": "FaceID service not running (start: cd Tools/FaceID && source .venv/bin/activate && python serve.py)"}
    except Exception as e:
        return {"error": f"FaceID proxy error: {e}"}


@app.post("/identity/recognize")
async def recognize_frame(frame_data: dict):
    """Proxy to FaceID microservice for recognition."""
    return await _proxy_faceid("/recognize", frame_data)


@app.post("/identity/enroll")
async def enroll_frame(frame_data: dict):
    """Proxy to FaceID microservice for enrollment. Admin-only."""
    await _require_admin()
    return await _proxy_faceid("/enroll", frame_data)


@app.post("/identity/reset")
async def reset_identity(data: dict):
    """Proxy to FaceID microservice for reset. Admin-only."""
    await _require_admin()
    return await _proxy_faceid("/reset", data)


@app.post("/identity/bypass")
async def bypass_identity():
    """
    Manually grant identity as Ahab (admin) without FaceID camera.
    Starts a keepalive that refreshes last_seen every 5s.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    identity_actor = _engine.get_actor("identity")
    if not identity_actor:
        raise HTTPException(status_code=503, detail="Identity actor not found")

    import time as _time, sqlite3 as _sqlite3

    # Use 'ahab' as entity_id — must match the engine's access_bridge table
    # (faces.db uses 'entity_ceb382cb' but the engine DB has 'ahab')
    entity_id = "ahab"
    entity_name = "Ahab"
    luna_tier = "admin"
    dataroom_tier = 1
    dataroom_categories = [1, 2, 3, 4, 5, 6, 7, 8, 9]

    # Set identity directly on the actor
    identity_actor.current.entity_id = entity_id
    identity_actor.current.entity_name = entity_name
    identity_actor.current.confidence = 1.0
    identity_actor.current.luna_tier = luna_tier
    identity_actor.current.dataroom_tier = dataroom_tier
    identity_actor.current.dataroom_categories = dataroom_categories
    identity_actor.current.last_seen = _time.time()

    # Keepalive task — refreshes last_seen so is_present stays true
    async def _bypass_keepalive():
        while getattr(identity_actor, '_bypass_active', False):
            identity_actor.current.last_seen = _time.time()
            await _broadcast_identity_state()
            await asyncio.sleep(5)

    identity_actor._bypass_active = True
    asyncio.create_task(_bypass_keepalive())
    await _broadcast_identity_state()

    # Persist bypass so it survives restarts
    import json as _json
    _sentinel = Path(__file__).parent.parent.parent.parent / "config" / "identity_bypass.json"
    _sentinel.parent.mkdir(parents=True, exist_ok=True)
    _sentinel.write_text(_json.dumps({
        "entity_id": entity_id,
        "entity_name": entity_name,
        "luna_tier": luna_tier,
        "dataroom_tier": dataroom_tier,
        "dataroom_categories": dataroom_categories,
    }))
    logger.info(f"[BYPASS] Identity set to {entity_name} ({entity_id}) — persisted to sentinel")

    return {
        "bypassed": True,
        "entity_id": entity_id,
        "entity_name": entity_name,
        "luna_tier": luna_tier,
        "dataroom_tier": dataroom_tier,
    }


@app.post("/identity/bypass-off")
async def bypass_off():
    """Revoke the identity bypass — clear manual identity."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    identity_actor = _engine.get_actor("identity")
    if not identity_actor:
        raise HTTPException(status_code=503, detail="Identity actor not found")

    identity_actor._bypass_active = False
    identity_actor.current.clear()
    await _broadcast_identity_state()

    # Remove sentinel so bypass doesn't auto-restore on next restart
    _sentinel = Path(__file__).parent.parent.parent.parent / "config" / "identity_bypass.json"
    if _sentinel.exists():
        _sentinel.unlink()
    logger.info("[BYPASS] Identity bypass revoked — sentinel removed")
    return {"bypassed": False}


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
        # Send message with source tag
        await _engine.send_message(request.message, source=request.source)

        # Wait for response with timeout
        text, data = await asyncio.wait_for(
            response_future,
            timeout=request.timeout
        )

        # Fire-and-forget QA validation (non-blocking)
        asyncio.create_task(
            _run_qa_validation_background(request.message, text, data)
        )

        # Process text for gesture detection + stripping (before broadcast so all paths get clean text)
        if _orb_state_manager:
            text = _orb_state_manager.process_text_chunk(text)

        # BROADCAST DEDUPLICATION: Suppress chat broadcast when source is
        # "mcp" to prevent shadow conversations in Eclissi. MCP calls still
        # trigger Scribe extraction (cache updates) but don't echo to the UI.
        if request.source != "mcp":
            asyncio.create_task(_broadcast_chat_message("user", {
                "content": request.message,
                "source": request.source,
            }))
            asyncio.create_task(_broadcast_chat_message("assistant", {
                "content": text,
                "model": data.get("model", "unknown"),
                "delegated": data.get("delegated", False),
                "local": data.get("local", False),
                "latency_ms": data.get("latency_ms", 0),
                "source": request.source,
            }))

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


@app.get("/api/cache/shared-turn")
async def get_shared_turn_cache():
    """
    Read the Shared Turn Cache for Eclissi frontend widgets.

    Returns the current YAML snapshot as JSON, or 204 if no cache exists.
    """
    from luna.cache.shared_turn import read_shared_turn

    snapshot = read_shared_turn()
    if snapshot is None:
        return Response(status_code=204)

    return {
        "turn_id": snapshot.turn_id,
        "timestamp": snapshot.timestamp,
        "source": snapshot.source,
        "is_stale": snapshot.is_stale,
        "age_seconds": round(snapshot.age_seconds, 1),
        "flow": {
            "mode": snapshot.flow_mode,
            "topic": snapshot.topic,
            "continuity_score": snapshot.continuity_score,
            "open_threads": snapshot.open_threads,
        },
        "expression": {
            "emotional_tone": snapshot.emotional_tone,
            "expression_hint": snapshot.expression_hint,
            "intensity": snapshot.intensity,
        },
        "scribed": {
            "facts": snapshot.facts,
            "decisions": snapshot.decisions,
            "actions": snapshot.actions,
            "problems": snapshot.problems,
            "observations": snapshot.observations,
            "total": snapshot.total_extractions,
        },
        "raw_summary": snapshot.raw_summary,
    }


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

    # Build identity state if available
    identity_state = None
    identity_actor = _engine.get_actor("identity")
    if identity_actor:
        identity_state = IdentityState(
            enabled=True,
            is_present=identity_actor.current.is_present,
            entity_name=identity_actor.current.entity_name,
            luna_tier=identity_actor.current.luna_tier,
            confidence=round(identity_actor.current.confidence, 3),
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
        identity=identity_state,
    )


@app.get("/health")
async def health_check():
    """Simple health check endpoint with pipeline status."""
    if _engine is None:
        return {"status": "starting"}

    # Pipeline status
    pipeline = {"connected": False, "scribe_extractions": None, "librarian_filings": None}
    scribe = _engine.get_actor("scribe")
    librarian = _engine.get_actor("librarian")
    if scribe and librarian:
        pipeline["connected"] = scribe.engine is not None and librarian.engine is not None
        pipeline["scribe_extractions"] = scribe.get_stats().get("extractions_count", 0)
        pipeline["librarian_filings"] = librarian.get_stats().get("filings_count", 0)

    return {
        "status": "healthy",
        "state": _engine.state.name,
        "pipeline": pipeline,
    }


@app.get("/eden/health")
async def eden_health_check():
    """Check whether Eden API is configured and reachable."""
    try:
        from luna.services.eden.config import EdenConfig
        config = EdenConfig.load()
        if not config.is_configured:
            return {"status": "unconfigured", "reason": "EDEN_API_KEY not set"}

        from luna.services.eden.adapter import EdenAdapter
        adapter = EdenAdapter(config)
        async with adapter:
            healthy = await adapter.health_check()
        return {
            "status": "healthy" if healthy else "unreachable",
            "api_base": config.api_base,
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}


class EdenGenerateRequest(BaseModel):
    prompt: str
    wait: bool = True


@app.post("/eden/generate")
async def eden_generate_image(req: EdenGenerateRequest):
    """Generate an image via Eden API."""
    try:
        from luna.services.eden.config import EdenConfig
        from luna.services.eden.adapter import EdenAdapter

        config = EdenConfig.load()
        if not config.is_configured:
            raise HTTPException(status_code=503, detail="Eden not configured (EDEN_API_KEY missing)")

        adapter = EdenAdapter(config)
        async with adapter:
            task = await adapter.create_image(prompt=req.prompt, wait=req.wait)
            return {
                "status": str(task.status.value) if hasattr(task.status, 'value') else str(task.status),
                "image_url": task.first_output_url,
                "task_id": task.id,
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Project Scoping Endpoints
# =========================================================================

class ProjectActivateRequest(BaseModel):
    slug: str

@app.post("/project/activate")
async def activate_project(req: ProjectActivateRequest):
    """Set the active project for scoped memory isolation."""
    _engine.set_active_project(req.slug)

    # Forward to Librarian for thread tagging
    librarian = _engine.get_actor("librarian")
    if librarian:
        from luna.actors.base import Message
        msg = Message(type="set_project_context", payload={"slug": req.slug})
        await librarian.handle(msg)

    return {
        "status": "activated",
        "project": req.slug,
        "scope": _engine.active_scope,
        "scopes": _engine.active_scopes,
    }

@app.post("/project/deactivate")
async def deactivate_project():
    """Clear the active project (return to global memory only)."""
    old = _engine.active_project
    _engine.set_active_project(None)

    # Forward to Librarian — auto-parks active thread
    librarian = _engine.get_actor("librarian")
    if librarian:
        from luna.actors.base import Message
        msg = Message(type="clear_project_context", payload={})
        await librarian.handle(msg)

    return {
        "status": "deactivated",
        "previous_project": old,
        "scope": _engine.active_scope,
    }

@app.get("/project/active")
async def get_active_project():
    """Get the currently active project and scope."""
    return {
        "project": _engine.active_project,
        "scope": _engine.active_scope,
        "scopes": _engine.active_scopes,
    }


@app.get("/api/projects")
async def get_projects():
    """List all defined projects with active state."""
    import yaml as _yaml
    registry_path = Path(__file__).parent.parent.parent.parent / "config" / "projects" / "projects.yaml"
    if not registry_path.exists():
        return {"projects": [], "active": _engine.active_project if _engine else None}
    with open(registry_path) as f:
        data = _yaml.safe_load(f) or {}
    projects = []
    for slug, conf in data.get("projects", {}).items():
        projects.append({
            "slug": slug,
            "name": conf.get("name", slug),
            "description": conf.get("description", ""),
            "ingestion_pattern": conf.get("ingestion_pattern", "utilitarian"),
            "aperture_default": conf.get("aperture_default", "BALANCED"),
            "collections": conf.get("collections", []),
            "icon": conf.get("icon", "◇"),
            "accent": conf.get("accent", "A78BFA"),
            "active": slug == (_engine.active_project if _engine else None),
        })
    return {"projects": projects, "active": _engine.active_project if _engine else None}


@app.post("/api/system/relaunch")
async def relaunch_system(background_tasks: BackgroundTasks):
    """
    Trigger a system relaunch. Admin-only.

    Executes the relaunch script in the background and returns immediately.
    The server will restart, so the client should expect a brief disconnection.
    """
    await _require_admin()
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

            # Record user turn through unified API (extraction + history + matrix)
            await _engine.record_conversation_turn(
                role="user",
                content=request.message,
                source="stream",
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

            # Record assistant turn (Scribe skips assistant turns by design,
            # but this feeds HistoryManager + matrix storage)
            response_text = "".join(full_response)
            if response_text:
                await _engine.record_conversation_turn(
                    role="assistant",
                    content=response_text,
                    source="stream",
                    tokens=final_data.get("output_tokens"),
                )

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

        # Get matrix for memory context + search chain for dataroom/web/local
        matrix = _engine.get_actor("matrix")
        memory_items = []
        memory_context = ""

        try:
            # --- PHASE 1: Send context first ---
            # Use the configurable search chain (matrix + dataroom + optional sources)
            from luna.tools.search_chain import SearchChainConfig, run_search_chain
            _search_cfg = getattr(_engine, "_search_chain_config", None) or SearchChainConfig.default()
            chain_results = await run_search_chain(_search_cfg, request.message, _engine)
            if chain_results:
                memory_context = "\n\n".join(r.get("content", "") for r in chain_results if r.get("content"))
                logger.info(f"[STREAM] Search chain returned {len(chain_results)} results, {len(memory_context)} chars")
            else:
                logger.info("[STREAM] Search chain returned no results")

            # Get recent memories for frontend display
            if matrix and matrix.is_ready:
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

            # Record user turn through unified API (extraction + history + matrix)
            await _engine.record_conversation_turn(
                role="user",
                content=request.message,
                source="stream",
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
            await _engine._emit_progress(
                f"[{routing.path.name}] {request.message[:40]}..."
                + (f" signals={routing.signals}" if routing.signals else "")
            )

            # --- PHASE 2: Execute based on routing ---
            if routing.path == ExecutionPath.DIRECT:
                # DIRECT path: stream straight from director
                _engine.metrics.direct_responses += 1
            else:
                # SIMPLE_PLAN or FULL_PLAN: execute memory retrieval first
                _engine.metrics.planned_responses += 1

                # OBSERVE phase
                await _engine._emit_progress("[OBSERVE] Gathering context... (1/2)")

                # Execute knowledge retrieval via search chain
                if "memory_query" in routing.signals or matrix and matrix.is_ready:
                    await _engine._emit_progress("[THINK] Deciding: Execute knowledge search...")
                    await _engine._emit_progress("[ACT:tool] Execute search chain...")

                    # Re-fetch with higher budget for planned queries
                    _plan_cfg = getattr(_engine, "_search_chain_config", None) or SearchChainConfig.default()
                    plan_results = await run_search_chain(_plan_cfg, request.message, _engine)
                    if plan_results:
                        memory_context = "\n\n".join(r.get("content", "") for r in plan_results if r.get("content"))
                        sources = list(set(r.get("source", "?") for r in plan_results))
                        await _engine._emit_progress(
                            f"[OK] Retrieved {len(memory_context)} chars from {sources}"
                        )
                    else:
                        await _engine._emit_progress("[OK] No knowledge found, proceeding without")

                # OBSERVE phase 2
                await _engine._emit_progress("[OBSERVE] Gathering context... (2/2)")
                await _engine._emit_progress("[THINK] Deciding: Present result to user...")
                await _engine._emit_progress("[ACT:respond] Present result to user...")

            # --- PHASE 3: Stream tokens ---
            # Notify orb state manager that response is starting.
            # Dimensional feed (sentiment, flow, topic) is handled by CacheActor
            # on every extraction turn — no inline feed needed here.
            if _orb_state_manager:
                _orb_state_manager.start_response()

            director.on_stream(on_token)
            _engine.on_response(on_complete)

            # Tell engine that this streaming endpoint owns turn recording
            # (prevents _handle_actor_message from double-recording)
            _engine._stream_owns_response = True

            # --- PRE-GENERATION: Reconcile tick ---
            # If Scout flagged confabulation on a previous turn, inject
            # a self-correction instruction into the system prompt.
            reconcile = getattr(_engine, 'reconcile', None)
            reconcile_instruction = reconcile.tick() if reconcile else None

            system_prompt = _engine._build_system_prompt(memory_context)
            if reconcile_instruction:
                system_prompt += f"\n\n## Self-Correction\n{reconcile_instruction}\n"
                logger.info("[STREAM] Reconcile instruction injected into system prompt")
                await _engine._emit_progress("[RECONCILE] Self-correction instruction active for this turn")

            # Send generation request — pass pre-fetched memory_context
            # so Director/Assembler uses it instead of auto-fetching from Matrix only
            # Also pass structured chain_results so Director can extract dataroom content
            msg = Message(
                type="generate_stream",
                payload={
                    "user_message": request.message,
                    "system_prompt": system_prompt,
                    "memory_context": memory_context,
                    "chain_results": chain_results if chain_results else [],
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

                    # Process token for gestures (may strip or annotate based on config)
                    processed_token = token
                    if _orb_state_manager:
                        processed_token = _orb_state_manager.process_text_chunk(token)

                    yield f"data: {json.dumps({'type': 'token', 'text': processed_token})}\n\n"

                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'error', 'message': 'Timeout waiting for tokens'})}\n\n"
                    break

            # --- PHASE 3: Send done event ---
            # Emit completion for Thought Stream
            tokens = final_metadata.get("output_tokens", len("".join(full_response)) // 4)
            route = "local" if final_metadata.get("local") else "delegated"
            await _engine._emit_progress(f"[OK] {route}: {tokens} tokens")

            final_text = "".join(full_response)
            # Strip gesture markers from final response (detection already happened per-token)
            if _orb_state_manager and _orb_state_manager.expression_config:
                if _orb_state_manager.expression_config.should_strip_gestures():
                    final_text = _orb_state_manager._strip_gestures(final_text)

            done_event = {
                "type": "done",
                "response": final_text,
                "metadata": final_metadata,
            }
            yield f"data: {json.dumps(done_event)}\n\n"

            # Notify orb state manager that response is complete
            if _orb_state_manager:
                _orb_state_manager.end_response()

            # Update completion metrics
            _engine.metrics.agentic_tasks_completed += 1
            _engine.metrics.messages_generated += 1

            # --- POST-GENERATION: Scout inspection + Reconcile ---
            response_text = "".join(full_response)

            if response_text:
                scout = _engine.get_actor("scout") if hasattr(_engine, 'get_actor') else None
                if scout:
                    context_size = len(memory_context) if memory_context else 0
                    try:
                        scout_report = scout.inspect(
                            draft=response_text,
                            query=request.message,
                            context_size=context_size,
                            retrieved_context=memory_context or "",
                        )

                        # Confabulation → flag for next-turn reconcile
                        if scout_report.blocked and scout_report.recommendation == "reconcile":
                            n_claims = len(scout_report.confabulation_data.get("unsupported_claims", [])) if scout_report.confabulation_data else 0
                            if reconcile and scout_report.confabulation_data:
                                reconcile.flag_confabulation(
                                    claims=scout_report.confabulation_data.get("unsupported_claims", []),
                                    original_query=request.message,
                                )
                                logger.warning(
                                    f"[STREAM] Confabulation flagged — "
                                    f"{n_claims} unsupported claims queued for reconcile"
                                )
                            await _engine._emit_progress(
                                f"[SCOUT] Confabulation detected — {n_claims} unsupported claims, reconcile queued"
                            )
                        elif scout_report.blocked:
                            # Blocked for non-confabulation reason (surrender, shallow, etc.)
                            await _engine._emit_progress(
                                f"[SCOUT] Blockage: {scout_report.blockage_type} "
                                f"(tier {scout_report.overdrive_tier})"
                            )
                        else:
                            # Clean pass
                            await _engine._emit_progress("[SCOUT] Integrity check passed")
                    except Exception as e:
                        logger.error(f"[STREAM] Scout inspection failed: {e}")

                # Check if Luna self-corrected (reconcile detection)
                if reconcile and reconcile.did_reconcile(response_text):
                    logger.info("[STREAM] Luna reconciled — notifying Scribe")
                    await _engine._emit_progress("[RECONCILE] Self-correction detected — filing CORRECTION node")
                    scribe = _engine.get_actor("scribe") if hasattr(_engine, 'get_actor') else None
                    if scribe:
                        from luna.actors.base import Message as ActorMessage
                        await scribe.handle(ActorMessage(
                            type="extract_correction",
                            payload={
                                "original_query": reconcile._state.original_query,
                                "flagged_claims": reconcile._state.flagged_claims,
                                "correction_response": response_text,
                                "session_id": getattr(_engine, "session_id", "unknown"),
                            }
                        ))
                    reconcile.clear()

            # Record assistant turn (Scribe skips assistant turns by design,
            # but this feeds HistoryManager + matrix storage)
            if response_text:
                await _engine.record_conversation_turn(
                    role="assistant",
                    content=response_text,
                    source="stream",
                    tokens=final_metadata.get("output_tokens"),
                )

        except Exception as e:
            logger.error(f"Persona stream error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

        finally:
            # Release stream ownership so engine handles non-streaming paths normally
            _engine._stream_owns_response = False
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


@app.get("/entities")
async def get_entities():
    """Get all known entities from Luna's memory.

    Used by Eclissi frontend for entity highlighting in chat messages.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix:
        raise HTTPException(status_code=503, detail="Matrix actor not available")

    mem = getattr(matrix, "matrix", None) or getattr(matrix, "_matrix", None) or getattr(matrix, "_memory", None)
    if not mem or not mem.db:
        raise HTTPException(status_code=503, detail="Memory not initialized")

    rows = await mem.db.fetchall(
        "SELECT id, entity_type, name, aliases, full_profile FROM entities ORDER BY name"
    )
    entities = [
        {"id": r[0], "type": r[1], "name": r[2], "aliases": r[3], "profile": r[4]}
        for r in rows
    ]
    return {"entities": entities, "count": len(entities)}


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


class AddEdgeRequest(BaseModel):
    """Request to add an edge between memory nodes."""
    from_node: str
    to_node: str
    relationship: str = "RELATES_TO"  # DEPENDS_ON, RELATES_TO, CAUSED_BY, etc.
    strength: float = 1.0


class AddEdgeResponse(BaseModel):
    """Response from adding an edge."""
    success: bool
    message: str


class NodeContextRequest(BaseModel):
    """Request to get context around a node."""
    node_id: str
    depth: int = 2


class NodeContextResponse(BaseModel):
    """Response with node context."""
    node_id: str
    neighbors: list[str]
    edges: list[dict]
    depth: int


class TraceRequest(BaseModel):
    """Request to trace dependencies."""
    node_id: str
    max_depth: int = 5


class TraceResponse(BaseModel):
    """Response with dependency trace."""
    node_id: str
    activations: dict[str, float]
    paths: list[dict]


class SetAppContextRequest(BaseModel):
    """Request to set app context."""
    app: str
    app_state: str


class SetAppContextResponse(BaseModel):
    """Response from setting app context."""
    success: bool
    app: str
    app_state: str


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

        # Use the appropriate search method based on search_type
        search_type = getattr(request, "search_type", "hybrid")

        if search_type == "semantic" and hasattr(memory, "semantic_search"):
            # Semantic search (vector similarity)
            search_results = await memory.semantic_search(
                query=request.query,
                limit=request.limit
            )
            results = [
                {
                    "id": n.id,
                    "node_type": n.node_type,
                    "content": n.content,
                    "confidence": n.confidence,
                    "lock_in": n.lock_in,
                    "lock_in_state": getattr(n, "lock_in_state", None),
                    "score": score,
                }
                for n, score in search_results
            ]
        elif search_type == "keyword" and hasattr(memory, "fts5_search"):
            # FTS5 keyword search
            search_results = await memory.fts5_search(
                query=request.query,
                limit=request.limit
            )
            results = [
                {
                    "id": n.id,
                    "node_type": n.node_type,
                    "content": n.content,
                    "confidence": n.confidence,
                    "lock_in": n.lock_in,
                    "lock_in_state": getattr(n, "lock_in_state", None),
                    "score": score,
                }
                for n, score in search_results
            ]
        elif search_type == "hybrid" and hasattr(memory, "hybrid_search"):
            # Hybrid search (FTS5 + semantic with RRF fusion)
            search_results = await memory.hybrid_search(
                query=request.query,
                limit=request.limit
            )
            results = [
                {
                    "id": n.id,
                    "node_type": n.node_type,
                    "content": n.content,
                    "confidence": n.confidence,
                    "lock_in": n.lock_in,
                    "lock_in_state": getattr(n, "lock_in_state", None),
                    "score": score,
                }
                for n, score in search_results
            ]
        elif hasattr(memory, "search_nodes"):
            # Fallback to basic LIKE search
            nodes = await memory.search_nodes(query=request.query, limit=request.limit)
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

        # Permission gate: strip DOCUMENT nodes the speaker can't see
        results = await _gate_results(results, source="api/memory/search")

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

        # Permission gate: strip DOCUMENT nodes the speaker can't see
        pre_gate_count = len(results)
        results = await _gate_results(results, source="api/memory/smart-fetch")

        if not results and pre_gate_count > 0:
            logger.warning(
                f"SMART_FETCH_GATE: Permission gate stripped all {pre_gate_count} "
                f"results for query='{request.query[:80]}'"
            )
        elif not results:
            logger.warning(
                f"SMART_FETCH_ZERO: get_context returned 0 nodes for "
                f"query='{request.query[:80]}', budget={max_tokens}"
            )

        # Estimate tokens used (rough: ~4 chars per token)
        total_chars = sum(len(r.get("content", "")) for r in results)
        budget_used = total_chars // 4

        return SmartFetchResponse(nodes=results, budget_used=budget_used)

    except Exception as e:
        logger.error(f"Smart fetch error: {e}", exc_info=True)
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


# ==============================================================================
# Graph Edge Operations (for MCP compatibility)
# ==============================================================================

@app.post("/memory/add-edge", response_model=AddEdgeResponse)
async def memory_add_edge(request: AddEdgeRequest):
    """
    Add an edge (relationship) between two memory nodes.

    Relationship types: DEPENDS_ON, RELATES_TO, CAUSED_BY, FOLLOWED_BY, CONTRADICTS, SUPPORTS
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix:
        raise HTTPException(status_code=503, detail="Matrix actor not available")

    try:
        # Access the graph from the matrix actor
        graph = getattr(matrix, "_graph", None)
        if not graph:
            raise HTTPException(status_code=503, detail="Memory graph not initialized")

        # Add the edge
        edge = await graph.add_edge(
            from_id=request.from_node,
            to_id=request.to_node,
            relationship=request.relationship,
            strength=request.strength,
        )

        logger.info(f"Added edge: {request.from_node} --{request.relationship}--> {request.to_node}")

        return AddEdgeResponse(
            success=True,
            message=f"Edge created: {request.from_node} --{request.relationship}[{request.strength}]--> {request.to_node}"
        )
    except Exception as e:
        logger.error(f"Failed to add edge: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/node-context", response_model=NodeContextResponse)
async def memory_node_context(request: NodeContextRequest):
    """
    Get context around a specific memory node.

    Returns neighbors within N hops and all connecting edges.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix:
        raise HTTPException(status_code=503, detail="Matrix actor not available")

    try:
        graph = getattr(matrix, "_graph", None)
        if not graph:
            raise HTTPException(status_code=503, detail="Memory graph not initialized")

        # Get neighbors within depth
        neighbors = await graph.get_neighbors(request.node_id, depth=request.depth)

        # Get all edges for the node
        edges = await graph.get_edges(request.node_id)
        edge_dicts = [
            {
                "from_id": e.from_id,
                "to_id": e.to_id,
                "relationship": e.relationship,
                "strength": e.strength,
            }
            for e in edges
        ]

        return NodeContextResponse(
            node_id=request.node_id,
            neighbors=neighbors,
            edges=edge_dicts,
            depth=request.depth,
        )
    except Exception as e:
        logger.error(f"Failed to get node context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/memory/trace", response_model=TraceResponse)
async def memory_trace(request: TraceRequest):
    """
    Trace dependency paths to a memory node using spreading activation.

    Returns activation scores for related nodes showing relevance.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix:
        raise HTTPException(status_code=503, detail="Matrix actor not available")

    try:
        graph = getattr(matrix, "_graph", None)
        if not graph:
            raise HTTPException(status_code=503, detail="Memory graph not initialized")

        # Run spreading activation from the node
        activations = await graph.spreading_activation(
            start_nodes=[request.node_id],
            decay=0.5,
            max_depth=request.max_depth,
        )

        # Get edges to trace paths
        edges = await graph.get_edges(request.node_id)
        paths = [
            {
                "from_id": e.from_id,
                "to_id": e.to_id,
                "relationship": e.relationship,
                "strength": e.strength,
            }
            for e in edges
        ]

        return TraceResponse(
            node_id=request.node_id,
            activations=activations,
            paths=paths,
        )
    except Exception as e:
        logger.error(f"Failed to trace dependencies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==============================================================================
# Data Room Endpoints
# ==============================================================================

@app.post("/dataroom/search")
async def dataroom_search_endpoint(
    query: str = "",
    category: str = None,
    status: str = None,
    limit: int = 10,
):
    """Search investor data room documents."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix:
        raise HTTPException(status_code=503, detail="Matrix actor not available")

    try:
        memory = getattr(matrix, "matrix", None) or getattr(matrix, "_matrix", None) or getattr(matrix, "_memory", None)
        if not memory:
            return {"results": [], "count": 0}

        nodes = await memory.search_nodes(query=query or "document", node_type="DOCUMENT", limit=limit * 3)

        # Permission gate: strip documents the speaker can't see
        nodes = await _gate_results(nodes, source="api/dataroom/search")

        results = []
        for node in nodes:
            import json as _json
            meta = node.metadata if isinstance(node.metadata, dict) else (
                _json.loads(node.metadata) if node.metadata else {}
            )
            if category and meta.get("category") != category:
                continue
            if status and meta.get("status") != status:
                continue
            results.append({
                "id": node.id,
                "name": node.summary or node.content,
                "category": meta.get("category"),
                "subfolder": meta.get("subfolder"),
                "status": meta.get("status"),
                "url": meta.get("gdrive_url"),
                "file_type": meta.get("file_type"),
                "tags": meta.get("tags", []),
            })
            if len(results) >= limit:
                break

        return {"results": results, "count": len(results)}
    except Exception as e:
        logger.error(f"Dataroom search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dataroom/status")
async def dataroom_status_endpoint():
    """Get data room statistics: total documents, by category, by status."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix:
        raise HTTPException(status_code=503, detail="Matrix actor not available")

    try:
        memory = getattr(matrix, "matrix", None) or getattr(matrix, "_matrix", None) or getattr(matrix, "_memory", None)
        if not memory:
            return {"total_documents": 0, "by_category": {}, "by_status": {}}

        docs = await memory.get_nodes_by_type("DOCUMENT", limit=1000)
        category_counts = {}
        status_counts = {}

        for doc in docs:
            import json as _json
            meta = doc.metadata if isinstance(doc.metadata, dict) else (
                _json.loads(doc.metadata) if doc.metadata else {}
            )
            cat = meta.get("category", "Unknown")
            category_counts[cat] = category_counts.get(cat, 0) + 1
            st = meta.get("status", "Unknown")
            status_counts[st] = status_counts.get(st, 0) + 1

        return {
            "total_documents": len(docs),
            "by_category": category_counts,
            "by_status": status_counts,
        }
    except Exception as e:
        logger.error(f"Dataroom status failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dataroom/recent")
async def dataroom_recent_endpoint(days: int = 7):
    """Get recently synced data room documents."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix:
        raise HTTPException(status_code=503, detail="Matrix actor not available")

    try:
        memory = getattr(matrix, "matrix", None) or getattr(matrix, "_matrix", None) or getattr(matrix, "_memory", None)
        if not memory:
            return {"documents": [], "count": 0}

        from datetime import datetime, timedelta
        import json as _json

        docs = await memory.get_nodes_by_type("DOCUMENT", limit=1000)

        # Permission gate: strip documents the speaker can't see
        docs = await _gate_results(docs, source="api/dataroom/recent")

        cutoff = datetime.now() - timedelta(days=days)
        recent = []

        for doc in docs:
            meta = doc.metadata if isinstance(doc.metadata, dict) else (
                _json.loads(doc.metadata) if doc.metadata else {}
            )
            last_synced = meta.get("last_synced")
            if not last_synced:
                continue
            try:
                sync_time = datetime.fromisoformat(last_synced)
            except (ValueError, TypeError):
                continue
            if sync_time >= cutoff:
                recent.append({
                    "id": doc.id,
                    "name": doc.summary or doc.content,
                    "category": meta.get("category"),
                    "status": meta.get("status"),
                    "synced_at": last_synced,
                    "url": meta.get("gdrive_url"),
                })

        recent.sort(key=lambda x: x["synced_at"], reverse=True)
        return {"documents": recent, "count": len(recent)}
    except Exception as e:
        logger.error(f"Dataroom recent failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/state/set-app-context", response_model=SetAppContextResponse)
async def set_app_context(request: SetAppContextRequest):
    """
    Set Luna's current app context.

    This helps Luna understand what application the user is working in.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    try:
        # Store in engine's context manager if available
        context_manager = getattr(_engine, "_context_manager", None)
        if context_manager and hasattr(context_manager, "set_app_context"):
            await context_manager.set_app_context(request.app, request.app_state)
        else:
            # Fallback: store as memory node
            matrix = _engine.get_actor("matrix")
            if matrix:
                await matrix.add_node(
                    node_type="CONTEXT",
                    content=f"App context: {request.app} - {request.app_state}",
                    source="api",
                )

        logger.info(f"Set app context: {request.app} / {request.app_state}")

        return SetAppContextResponse(
            success=True,
            app=request.app,
            app_state=request.app_state,
        )
    except Exception as e:
        logger.error(f"Failed to set app context: {e}")
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


class TTSRequest(BaseModel):
    """Request body for /api/tts endpoint."""
    text: str = Field(..., min_length=1, max_length=5000)
    voice: str = Field(default="en_US-amy-medium", description="Piper voice name")


_tts_manager = None


async def _get_tts_manager():
    global _tts_manager
    if _tts_manager is None:
        from voice.tts.manager import TTSManager, TTSProviderType
        _tts_manager = TTSManager(
            default_provider=TTSProviderType.PIPER,
            default_voice="en_US-amy-medium",
        )
    return _tts_manager


@app.post("/api/tts")
async def text_to_speech(request: TTSRequest):
    """
    Convert text to speech using Piper TTS.

    Returns WAV audio bytes. The frontend plays this via Audio element.
    Uses Luna's existing Piper infrastructure — same voice as desktop.
    """
    try:
        from voice.tts.preprocessing import preprocess_for_speech

        clean_text = preprocess_for_speech(request.text)
        if not clean_text.strip():
            raise HTTPException(status_code=400, detail="No speakable text after preprocessing")

        tts = await _get_tts_manager()
        audio = await tts.synthesize(clean_text)

        if not audio.data:
            raise HTTPException(status_code=500, detail="TTS synthesis produced no audio")

        return Response(
            content=audio.data,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "inline",
                "Cache-Control": "no-cache",
            }
        )
    except ImportError:
        raise HTTPException(status_code=503, detail="Voice module not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"TTS error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
# VOICE SYSTEM API: Blend Engine + Corpus observability
# ============================================================================

# Lazy-loaded voice system orchestrator
_voice_orchestrator = None

def _get_voice_orchestrator():
    """Lazy-load the voice system orchestrator."""
    global _voice_orchestrator
    if _voice_orchestrator is not None:
        return _voice_orchestrator
    try:
        from luna.voice.orchestrator import VoiceSystemOrchestrator
        from luna.voice.models import VoiceSystemConfig
        voice_config_path = Path(__file__).parent.parent / "voice" / "data" / "voice_config.yaml"
        if voice_config_path.exists():
            config = VoiceSystemConfig.from_yaml(str(voice_config_path))
        else:
            config = VoiceSystemConfig()
        _voice_orchestrator = VoiceSystemOrchestrator(config)
        return _voice_orchestrator
    except Exception as e:
        logger.warning(f"Voice system not available: {e}")
        return None


@app.get("/voice/system/status")
async def voice_system_status():
    """Get voice system status — engine modes, alpha history, config state."""
    orch = _get_voice_orchestrator()
    if not orch:
        return {"active": False, "error": "Voice system not loaded"}

    engine_info = None
    if orch.engine:
        engine_info = {
            "mode": orch.config.blend_engine_mode.value,
            "alpha_history": list(orch.engine._alpha_history[-20:]),
            "turn_history": [t.value for t in orch.engine._turn_history[-20:]],
            "line_bank_size": len(orch.engine.bank.lines),
            "bypasses": {
                "confidence_router": orch.config.bypass_confidence_router,
                "fade_controller": orch.config.bypass_fade_controller,
                "segment_planner": orch.config.bypass_segment_planner,
                "line_sampler": orch.config.bypass_line_sampler,
            },
        }

    corpus_info = None
    if orch.corpus:
        corpus_info = {
            "mode": orch.config.voice_corpus_mode.value,
            "corpus_size": len(orch.corpus.bank.lines),
            "anti_pattern_count": len(orch.corpus.bank.anti_patterns),
            "critical_anti_patterns": [a.phrase for a in orch.corpus.bank.critical_anti_patterns()],
        }

    return {
        "active": True,
        "engine": engine_info,
        "corpus": corpus_info,
        "config": {
            "blend_engine_mode": orch.config.blend_engine_mode.value,
            "voice_corpus_mode": orch.config.voice_corpus_mode.value,
            "alpha_override": orch.config.alpha_override,
            "corpus_tier_override": orch.config.corpus_tier_override,
            "log_alpha": orch.config.log_alpha,
            "log_line_selection": orch.config.log_line_selection,
            "log_injection": orch.config.log_injection,
            "log_shadow_diff": orch.config.log_shadow_diff,
        },
    }


class VoiceSystemConfigUpdate(BaseModel):
    """Partial config update for voice system."""
    blend_engine_mode: Optional[str] = None
    voice_corpus_mode: Optional[str] = None
    alpha_override: Optional[float] = None
    corpus_tier_override: Optional[str] = None
    bypass_confidence_router: Optional[bool] = None
    bypass_fade_controller: Optional[bool] = None
    bypass_segment_planner: Optional[bool] = None
    bypass_line_sampler: Optional[bool] = None


@app.post("/voice/system/config")
async def update_voice_system_config(update: VoiceSystemConfigUpdate):
    """Hot-reload voice system configuration."""
    global _voice_orchestrator
    orch = _get_voice_orchestrator()
    if not orch:
        raise HTTPException(status_code=503, detail="Voice system not loaded")

    try:
        from luna.voice.models import VoiceSystemConfig, EngineMode
        # Build new config from current + updates
        current = orch.config.model_dump()
        updates = update.model_dump(exclude_none=True)
        # Convert string modes to EngineMode
        for key in ("blend_engine_mode", "voice_corpus_mode"):
            if key in updates:
                updates[key] = EngineMode(updates[key])
        current.update(updates)
        new_config = VoiceSystemConfig(**current)
        orch.on_config_change(new_config)
        return {"ok": True, "config": {
            "blend_engine_mode": new_config.blend_engine_mode.value,
            "voice_corpus_mode": new_config.voice_corpus_mode.value,
            "alpha_override": new_config.alpha_override,
        }}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/voice/system/simulate")
async def voice_system_simulate(signals: dict):
    """Simulate alpha computation without affecting state. For the dashboard."""
    orch = _get_voice_orchestrator()
    if not orch or not orch.engine:
        raise HTTPException(status_code=503, detail="Blend engine not active")

    try:
        from luna.voice.models import ConfidenceSignals, ContextType
        cs = ConfidenceSignals(
            memory_retrieval_score=signals.get("memory_retrieval_score", 0.2),
            turn_number=signals.get("turn_number", 1),
            entity_resolution_depth=signals.get("entity_resolution_depth", 0),
            context_type=ContextType(signals.get("context_type", "cold_start")),
            topic_continuity=signals.get("topic_continuity", 0.0),
        )
        result = orch.engine._compute_confidence(cs)
        return {
            "alpha": result.alpha,
            "tier": result.tier.value,
            "signal_contributions": result.signal_contributions,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/voice/system/reset")
async def voice_system_reset():
    """Reset conversation state (alpha history, turn history)."""
    orch = _get_voice_orchestrator()
    if not orch:
        raise HTTPException(status_code=503, detail="Voice system not loaded")
    orch.on_conversation_start()
    return {"ok": True, "message": "Voice system conversation state reset"}


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

    # Trigger extraction pipeline (Scribe → Librarian → Matrix)
    try:
        await _engine._trigger_extraction(request.role, request.content)
    except Exception as e:
        logger.error(f"Hub turn extraction error: {e}")

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


# =============================================================================
# MEMORY ECONOMY ENDPOINTS — Cluster & Constellation Visibility
# =============================================================================


class ClusterStatsResponse(BaseModel):
    """Memory Economy cluster statistics."""
    cluster_count: int
    total_nodes: int
    state_distribution: dict  # {drifting: n, fluid: n, settled: n, crystallized: n}
    avg_lock_in: float
    nodes_per_cluster_avg: float
    nodes_per_cluster_max: int
    top_clusters: list


class ClusterListItem(BaseModel):
    """Single cluster in list response."""
    cluster_id: str
    name: str
    member_count: int
    lock_in: float
    state: str


class ClusterListResponse(BaseModel):
    """Response from cluster list."""
    clusters: list[ClusterListItem]
    total: int


class ClusterMember(BaseModel):
    """Member node in a cluster."""
    node_id: str
    content: str
    node_type: str
    lock_in: float
    membership_strength: float


class ClusterDetailResponse(BaseModel):
    """Full cluster details."""
    cluster_id: str
    name: str
    member_count: int
    lock_in: float
    state: str
    summary: Optional[str]
    members: list[ClusterMember]
    related_clusters: list


class ConstellationRequest(BaseModel):
    """Request for constellation assembly."""
    query: str
    max_tokens: int = Field(default=3000, ge=500, le=8000)
    max_clusters: int = Field(default=5, ge=1, le=10)


class ConstellationResponse(BaseModel):
    """Assembled constellation for context."""
    activated_clusters: list
    expanded_nodes: list
    total_tokens: int
    lock_in_distribution: dict
    assembly_time_ms: float


@app.get("/clusters/stats", response_model=ClusterStatsResponse)
async def get_cluster_stats():
    """
    Get Memory Economy cluster statistics.

    Shows cluster distribution, lock-in states, and top clusters.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix or not matrix.is_ready:
        raise HTTPException(status_code=503, detail="Matrix not ready")

    try:
        from luna.memory.cluster_manager import ClusterManager

        # Get DB path from matrix
        db_path = str(matrix._matrix.db.db_path) if matrix._matrix and matrix._matrix.db else None
        if not db_path:
            raise HTTPException(status_code=503, detail="Database not available")

        cluster_mgr = ClusterManager(db_path)

        # Get all clusters
        all_clusters = cluster_mgr.list_clusters()

        # Calculate state distribution
        state_dist = {"drifting": 0, "fluid": 0, "settled": 0, "crystallized": 0}
        total_lock_in = 0.0
        sizes = []

        for c in all_clusters:
            state_dist[c.state] = state_dist.get(c.state, 0) + 1
            total_lock_in += c.lock_in
            sizes.append(c.member_count)

        cluster_count = len(all_clusters)
        avg_lock_in = total_lock_in / cluster_count if cluster_count > 0 else 0.0

        # Top clusters by size
        sorted_clusters = sorted(all_clusters, key=lambda c: c.member_count, reverse=True)[:5]
        top_clusters = [
            {
                "cluster_id": c.cluster_id,
                "name": c.name,
                "member_count": c.member_count,
                "lock_in": round(c.lock_in, 3),
                "state": c.state,
            }
            for c in sorted_clusters
        ]

        return ClusterStatsResponse(
            cluster_count=cluster_count,
            total_nodes=sum(sizes),
            state_distribution=state_dist,
            avg_lock_in=round(avg_lock_in, 3),
            nodes_per_cluster_avg=round(sum(sizes) / cluster_count, 1) if cluster_count > 0 else 0,
            nodes_per_cluster_max=max(sizes) if sizes else 0,
            top_clusters=top_clusters,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cluster stats failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/clusters/list", response_model=ClusterListResponse)
async def list_clusters(
    state: Optional[str] = None,
    min_lock_in: Optional[float] = None,
    limit: int = 50,
):
    """
    List clusters with optional filtering.

    Args:
        state: Filter by state (drifting, fluid, settled, crystallized)
        min_lock_in: Minimum lock-in threshold
        limit: Maximum clusters to return
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix or not matrix.is_ready:
        raise HTTPException(status_code=503, detail="Matrix not ready")

    try:
        from luna.memory.cluster_manager import ClusterManager

        db_path = str(matrix._matrix.db.db_path)
        cluster_mgr = ClusterManager(db_path)

        all_clusters = cluster_mgr.list_clusters()

        # Apply filters
        if state:
            all_clusters = [c for c in all_clusters if c.state == state]
        if min_lock_in is not None:
            all_clusters = [c for c in all_clusters if c.lock_in >= min_lock_in]

        # Sort by lock-in descending
        all_clusters.sort(key=lambda c: c.lock_in, reverse=True)

        # Apply limit
        clusters = all_clusters[:limit]

        return ClusterListResponse(
            clusters=[
                ClusterListItem(
                    cluster_id=c.cluster_id,
                    name=c.name,
                    member_count=c.member_count,
                    lock_in=round(c.lock_in, 3),
                    state=c.state,
                )
                for c in clusters
            ],
            total=len(all_clusters),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cluster list failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/clusters/{cluster_id}", response_model=ClusterDetailResponse)
async def get_cluster_detail(cluster_id: str):
    """
    Get detailed information about a specific cluster.

    Includes member nodes and related clusters.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix or not matrix.is_ready:
        raise HTTPException(status_code=503, detail="Matrix not ready")

    try:
        from luna.memory.cluster_manager import ClusterManager

        db_path = str(matrix._matrix.db.db_path)
        cluster_mgr = ClusterManager(db_path)

        # Get cluster
        cluster = cluster_mgr.get_cluster(cluster_id)
        if not cluster:
            raise HTTPException(status_code=404, detail=f"Cluster not found: {cluster_id}")

        # Get members with their node details
        members = cluster_mgr.get_cluster_members(cluster_id)
        member_details = []
        for m in members[:20]:  # Limit to 20 members for response size
            # Get node info from database
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, node_type, content, lock_in FROM memory_nodes
                WHERE id = ?
            """, (m["node_id"],))
            node_row = cursor.fetchone()
            conn.close()

            if node_row:
                member_details.append(ClusterMember(
                    node_id=m["node_id"],
                    content=node_row["content"][:200] if node_row["content"] else "",
                    node_type=node_row["node_type"] or "memory",
                    lock_in=round(node_row["lock_in"] or 0.5, 3),
                    membership_strength=round(m["membership_strength"], 3),
                ))

        # Get related clusters via edges
        related = cluster_mgr.get_connected_clusters(cluster_id, min_lock_in=0.3)
        related_clusters = []
        for neighbor_id, edge_lock_in in related[:5]:
            neighbor = cluster_mgr.get_cluster(neighbor_id)
            if neighbor:
                related_clusters.append({
                    "cluster_id": neighbor.cluster_id,
                    "name": neighbor.name,
                    "lock_in": round(neighbor.lock_in, 3),
                    "edge_strength": round(edge_lock_in, 3),
                })

        return ClusterDetailResponse(
            cluster_id=cluster.cluster_id,
            name=cluster.name,
            member_count=cluster.member_count,
            lock_in=round(cluster.lock_in, 3),
            state=cluster.state,
            summary=cluster.summary,
            members=member_details,
            related_clusters=related_clusters,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cluster detail failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/constellation/assemble", response_model=ConstellationResponse)
async def assemble_constellation(request: ConstellationRequest):
    """
    Assemble a constellation for a query.

    This is the primary Memory Economy retrieval endpoint.
    Returns clusters + nodes formatted for context injection.
    """
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    matrix = _engine.get_actor("matrix")
    if not matrix or not matrix.is_ready:
        raise HTTPException(status_code=503, detail="Matrix not ready")

    import time
    start = time.time()

    try:
        from luna.librarian.cluster_retrieval import ClusterRetrieval
        from luna.memory.constellation import ConstellationAssembler

        db_path = str(matrix._matrix.db.db_path)

        # Step 1: Retrieve relevant nodes via matrix search
        nodes = await matrix._matrix.search_nodes(query=request.query, limit=20)
        node_ids = [n.id for n in nodes] if nodes else []

        # Step 2: Find relevant clusters
        retrieval = ClusterRetrieval(db_path)
        cluster_results = retrieval.find_relevant_clusters(
            node_ids=node_ids,
            top_k=request.max_clusters
        )

        # Also include auto-activated clusters
        auto_clusters = retrieval.get_auto_activated_clusters()
        seen_ids = {c.cluster_id for c, _ in cluster_results}
        for cluster in auto_clusters:
            if cluster.cluster_id not in seen_ids:
                cluster_results.append((cluster, cluster.lock_in))

        # Step 3: Assemble constellation
        assembler = ConstellationAssembler(max_tokens=request.max_tokens)

        cluster_dicts = [
            {"cluster": c, "score": score}
            for c, score in cluster_results
        ]
        node_dicts = [
            {"node_id": n.id, "content": n.content, "node_type": n.node_type, "lock_in": getattr(n, 'lock_in', 0.5)}
            for n in (nodes or [])
        ]

        constellation = assembler.assemble(
            clusters=cluster_dicts,
            nodes=node_dicts,
            prioritize_clusters=True
        )

        elapsed_ms = (time.time() - start) * 1000

        # Format response
        return ConstellationResponse(
            activated_clusters=[
                {
                    "cluster_id": getattr(c.get("cluster"), "cluster_id", None) or c.get("cluster_id"),
                    "name": getattr(c.get("cluster"), "name", None) or c.get("name", "Unknown"),
                    "lock_in": getattr(c.get("cluster"), "lock_in", None) or c.get("lock_in", 0),
                    "member_count": getattr(c.get("cluster"), "member_count", None) or c.get("member_count", 0),
                }
                for c in constellation.clusters
            ],
            expanded_nodes=[
                {
                    "node_id": n.get("node_id"),
                    "content": n.get("content", "")[:200],
                    "node_type": n.get("node_type"),
                    "lock_in": n.get("lock_in"),
                }
                for n in constellation.nodes
            ],
            total_tokens=constellation.total_tokens,
            lock_in_distribution=constellation.lock_in_distribution,
            assembly_time_ms=round(elapsed_ms, 1),
        )
    except ImportError as e:
        logger.error(f"Memory Economy modules not available: {e}")
        raise HTTPException(status_code=503, detail="Memory Economy not available")
    except Exception as e:
        logger.error(f"Constellation assembly failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# SLASH COMMAND DEBUG ENDPOINTS
# =============================================================================
# These endpoints expose luna-debug functionality for the chat UI
# Usage: /health, /find-person X, /stats, /search X, /recent, /extraction


class SlashCommandResponse(BaseModel):
    """Response from slash command endpoints."""
    command: str
    success: bool
    data: dict
    formatted: str  # Pre-formatted text for display


@app.get("/slash/health", response_model=SlashCommandResponse)
async def slash_health():
    """
    /health - Check all 6 system components.
    """
    try:
        from luna.diagnostics.health import HealthChecker, HealthStatus
        import asyncio

        checker = HealthChecker()  # Uses default db path

        # Run sync method in thread pool
        checks = await asyncio.to_thread(checker.check_all)

        # Format output
        lines = ["**System Health Check**", ""]
        for check in checks:
            status_icon = {
                HealthStatus.HEALTHY: "✓",
                HealthStatus.DEGRADED: "⚠",
                HealthStatus.BROKEN: "✗",
                HealthStatus.UNKNOWN: "?",
            }.get(check.status, "?")

            lines.append(f"{status_icon} **{check.component}**: {check.status.value}")
            if check.message:
                lines.append(f"   {check.message}")

        formatted = "\n".join(lines)

        return SlashCommandResponse(
            command="/health",
            success=True,
            data={
                "checks": [
                    {
                        "component": c.component,
                        "status": c.status.value,
                        "message": c.message,
                        "metrics": c.metrics,
                    }
                    for c in checks
                ]
            },
            formatted=formatted,
        )

    except Exception as e:
        logger.error(f"Slash health failed: {e}")
        return SlashCommandResponse(
            command="/health",
            success=False,
            data={"error": str(e)},
            formatted=f"✗ Health check failed: {e}",
        )


@app.get("/slash/find-person/{name}", response_model=SlashCommandResponse)
async def slash_find_person(name: str):
    """
    /find-person <name> - Find a person and their linked memories.
    """
    try:
        from luna.diagnostics.health import HealthChecker
        import asyncio

        checker = HealthChecker()  # Uses default db path

        # Run sync method in thread pool
        result = await asyncio.to_thread(checker.find_person, name)

        if result["found"]:
            lines = [f"**Search results for '{name}':**", ""]

            # Show entities found
            search_results = result.get("search_results", {})
            if "entities" in search_results:
                for entity in search_results["entities"][:3]:
                    lines.append(f"✓ **{entity['name']}** ({entity['type']})")
                    lines.append(f"   ID: `{entity['id']}`")
                    if entity.get("core_facts"):
                        lines.append(f"   Facts: {entity['core_facts'][:100]}...")

            # Show memory nodes found
            if "memory_nodes" in search_results:
                lines.append("")
                lines.append(f"**{len(search_results['memory_nodes'])} memory nodes:**")
                for node in search_results["memory_nodes"][:3]:
                    lines.append(f"- [{node['type']}] {node['content_preview'][:80]}...")

            # Show diagnosis
            if result.get("diagnosis"):
                lines.append("")
                for d in result["diagnosis"]:
                    lines.append(f"• {d}")

            formatted = "\n".join(lines)
        else:
            lines = [f"✗ Person '{name}' not found in memory", ""]
            if result.get("suggestions"):
                lines.append("**Suggestions:**")
                for s in result["suggestions"]:
                    lines.append(f"- {s}")
            formatted = "\n".join(lines)

        return SlashCommandResponse(
            command=f"/find-person {name}",
            success=result["found"],
            data=result,
            formatted=formatted,
        )

    except Exception as e:
        logger.error(f"Slash find-person failed: {e}")
        return SlashCommandResponse(
            command=f"/find-person {name}",
            success=False,
            data={"error": str(e)},
            formatted=f"✗ Find person failed: {e}",
        )


@app.get("/slash/stats", response_model=SlashCommandResponse)
async def slash_stats():
    """
    /stats - Database statistics.
    """
    try:
        from pathlib import Path
        from luna.substrate.database import MemoryDatabase

        db_path = Path("data/luna_engine.db")
        db = MemoryDatabase(db_path)
        await db.connect()

        try:
            # Gather stats
            nodes = await db.fetchone("SELECT COUNT(*) FROM memory_nodes")
            entities = await db.fetchone("SELECT COUNT(*) FROM entities")
            mentions = await db.fetchone("SELECT COUNT(*) FROM entity_mentions")
            sessions = await db.fetchone("SELECT COUNT(*) FROM sessions")

            # Check if clusters table exists
            clusters_exist = await db.fetchone("SELECT name FROM sqlite_master WHERE type='table' AND name='clusters'")
            clusters = await db.fetchone("SELECT COUNT(*) FROM clusters") if clusters_exist else (0,)

            stats = {
                "memory_nodes": nodes[0] if nodes else 0,
                "entities": entities[0] if entities else 0,
                "entity_mentions": mentions[0] if mentions else 0,
                "sessions": sessions[0] if sessions else 0,
                "clusters": clusters[0] if clusters else 0,
            }

            lines = [
                "**Database Statistics**",
                "",
                f"Memory nodes: **{stats['memory_nodes']:,}**",
                f"Entities: **{stats['entities']:,}**",
                f"Entity mentions: **{stats['entity_mentions']:,}**",
                f"Sessions: **{stats['sessions']:,}**",
                f"Clusters: **{stats['clusters']:,}**",
            ]

            return SlashCommandResponse(
                command="/stats",
                success=True,
                data=stats,
                formatted="\n".join(lines),
            )
        finally:
            await db.close()

    except Exception as e:
        logger.error(f"Slash stats failed: {e}")
        return SlashCommandResponse(
            command="/stats",
            success=False,
            data={"error": str(e)},
            formatted=f"✗ Stats failed: {e}",
        )


@app.get("/slash/search/{query}", response_model=SlashCommandResponse)
async def slash_search(query: str, limit: int = 5):
    """
    /search <query> - Search memory nodes.
    """
    if _engine is None:
        return SlashCommandResponse(
            command=f"/search {query}",
            success=False,
            data={"error": "Engine not ready"},
            formatted="✗ Engine not ready",
        )

    try:
        matrix = _engine.get_actor("matrix")
        if not matrix or not matrix.is_ready:
            return SlashCommandResponse(
                command=f"/search {query}",
                success=False,
                data={"error": "Matrix not ready"},
                formatted="✗ Memory matrix not ready",
            )

        nodes = await matrix._matrix.search_nodes(query=query, limit=limit)

        # Permission gate: strip DOCUMENT nodes
        nodes = await _gate_results(nodes, source="api/slash/search")

        if not nodes:
            return SlashCommandResponse(
                command=f"/search {query}",
                success=True,
                data={"results": []},
                formatted=f"No results for '{query}'",
            )

        lines = [f"**Search results for '{query}':**", ""]
        results = []
        for node in nodes:
            content_preview = (node.content[:100] + "...") if len(node.content) > 100 else node.content
            lines.append(f"- [{node.node_type}] {content_preview}")
            results.append({
                "id": node.id,
                "type": node.node_type,
                "content": node.content[:200],
                "lock_in": getattr(node, 'lock_in', 0.5),
            })

        return SlashCommandResponse(
            command=f"/search {query}",
            success=True,
            data={"results": results, "count": len(results)},
            formatted="\n".join(lines),
        )

    except Exception as e:
        logger.error(f"Slash search failed: {e}")
        return SlashCommandResponse(
            command=f"/search {query}",
            success=False,
            data={"error": str(e)},
            formatted=f"✗ Search failed: {e}",
        )


@app.get("/slash/recent", response_model=SlashCommandResponse)
async def slash_recent(hours: int = 24):
    """
    /recent - Recent activity summary.
    """
    try:
        from luna.diagnostics.health import HealthChecker
        import asyncio

        checker = HealthChecker()  # Uses default db path

        # Run sync method in thread pool
        activity = await asyncio.to_thread(checker.get_recent_activity, hours)

        lines = [
            f"**Activity (last {hours}h)**",
            "",
            f"Memory nodes created: **{activity['nodes_created']}**",
            f"Sessions active: **{activity['sessions_active']}**",
            f"Entities mentioned: **{activity['entities_mentioned']}**",
        ]

        if activity.get("top_node_types"):
            lines.append("")
            lines.append("**Top node types:**")
            for node_type, count in activity["top_node_types"][:5]:
                lines.append(f"- {node_type}: {count}")

        return SlashCommandResponse(
            command="/recent",
            success=True,
            data=activity,
            formatted="\n".join(lines),
        )

    except Exception as e:
        logger.error(f"Slash recent failed: {e}")
        return SlashCommandResponse(
            command="/recent",
            success=False,
            data={"error": str(e)},
            formatted=f"✗ Recent activity failed: {e}",
        )


@app.get("/slash/extraction", response_model=SlashCommandResponse)
async def slash_extraction():
    """
    /extraction - Extraction pipeline status.
    """
    try:
        from pathlib import Path
        from luna.substrate.database import MemoryDatabase
        from datetime import datetime, timedelta

        db_path = Path("data/luna_engine.db")
        db = MemoryDatabase(db_path)
        await db.connect()

        try:
            # Get extraction stats
            now = datetime.now()
            hour_ago = (now - timedelta(hours=1)).isoformat()
            day_ago = (now - timedelta(days=1)).isoformat()

            last_hour = await db.fetchone(
                "SELECT COUNT(*) FROM memory_nodes WHERE created_at > ?",
                (hour_ago,)
            )
            last_day = await db.fetchone(
                "SELECT COUNT(*) FROM memory_nodes WHERE created_at > ?",
                (day_ago,)
            )

            # Get latest node
            latest = await db.fetchone(
                "SELECT created_at, node_type FROM memory_nodes ORDER BY created_at DESC LIMIT 1"
            )

            stats = {
                "nodes_last_hour": last_hour[0] if last_hour else 0,
                "nodes_last_day": last_day[0] if last_day else 0,
                "latest_node_at": latest[0] if latest else None,
                "latest_node_type": latest[1] if latest else None,
            }

            status = "active" if stats["nodes_last_hour"] > 0 else "idle"

            lines = [
                f"**Extraction Pipeline: {status.upper()}**",
                "",
                f"Nodes (last hour): **{stats['nodes_last_hour']}**",
                f"Nodes (last day): **{stats['nodes_last_day']}**",
            ]

            if stats["latest_node_at"]:
                lines.append(f"Latest: {stats['latest_node_type']} at {stats['latest_node_at']}")

            return SlashCommandResponse(
                command="/extraction",
                success=True,
                data=stats,
                formatted="\n".join(lines),
            )
        finally:
            await db.close()

    except Exception as e:
        logger.error(f"Slash extraction failed: {e}")
        return SlashCommandResponse(
            command="/extraction",
            success=False,
            data={"error": str(e)},
            formatted=f"✗ Extraction check failed: {e}",
        )


@app.get("/slash/help", response_model=SlashCommandResponse)
async def slash_help():
    """
    /help - List available slash commands.
    """
    commands = [
        ("/health", "Check all 6 system components"),
        ("/find-person <name>", "Find a person and their linked memories"),
        ("/stats", "Database statistics"),
        ("/search <query>", "Search memory nodes"),
        ("/recent", "Recent activity (last 24h)"),
        ("/extraction", "Extraction pipeline status"),
        ("/voice-tuning", "Open voice tuning panel"),
        ("/orb-settings", "Open orb visual settings"),
        ("/performance", "Show current performance state"),
        ("/emotion <name>", "Set emotion preset (excited, warm, thoughtful...)"),
        ("/reset-performance", "Reset to auto-detect mode"),
        ("/llm", "Show LLM provider status"),
        ("/llm-switch <provider>", "Switch LLM provider (groq, gemini, claude)"),
        ("/restart-backend", "Restart Luna backend server"),
        ("/restart-frontend", "Reload frontend UI"),
        ("/faceid", "FaceID status, set-pin, or reset"),
        ("/help", "Show this help"),
    ]

    lines = ["**Available Commands:**", ""]
    for cmd, desc in commands:
        lines.append(f"`{cmd}` - {desc}")

    return SlashCommandResponse(
        command="/help",
        success=True,
        data={"commands": [{"command": c, "description": d} for c, d in commands]},
        formatted="\n".join(lines),
    )


# =============================================================================
# FACEID SLASH COMMANDS
# =============================================================================

def _get_face_db():
    """Get FaceDatabase instance (lazy import from Tools/FaceID).

    Uses importlib to load database.py directly, bypassing __init__.py
    which imports cv2/torch dependencies not available in the main venv.
    """
    import importlib.util
    from pathlib import Path
    faceid_root = Path(__file__).parent.parent.parent.parent / "Tools" / "FaceID"
    db_module_path = faceid_root / "src" / "database.py"
    spec = importlib.util.spec_from_file_location("faceid_database", str(db_module_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    db_path = faceid_root / "data" / "faces.db"
    return mod.FaceDatabase(db_path)


@app.get("/slash/faceid", response_model=SlashCommandResponse)
async def slash_faceid_status():
    """
    /faceid — Show FaceID status (enrolled entities, embeddings, PIN state).
    """
    try:
        with _get_face_db() as db:
            entities = db.list_entities()
            total = db.count_embeddings()
            has_pin = db.has_pin()

        lines = ["**FaceID Status**", ""]
        lines.append(f"Entities: **{len(entities)}**")
        lines.append(f"Total embeddings: **{total}**")
        lines.append(f"Admin PIN: **{'set' if has_pin else 'not set'}**")

        if entities:
            lines.append("")
            lines.append("| Name | Tier | DR Tier | Faces |")
            lines.append("|------|------|---------|-------|")
            for e in entities:
                lines.append(f"| {e['entity_name']} | {e['luna_tier']} | {e['dataroom_tier']} | {e['face_count']} |")

        lines.append("")
        lines.append("Commands: `/faceid set-pin <4digits>` | `/faceid reset <pin>`")

        return SlashCommandResponse(
            command="/faceid",
            success=True,
            data={"entities": entities, "total_embeddings": total, "has_pin": has_pin},
            formatted="\n".join(lines),
        )
    except Exception as e:
        return SlashCommandResponse(
            command="/faceid",
            success=False,
            data={"error": str(e)},
            formatted=f"**FaceID Error:** {e}",
        )


@app.post("/slash/faceid/{action}")
async def slash_faceid_action(action: str):
    """
    /faceid set-pin <pin> — Set or change the admin PIN.
    /faceid reset <pin>   — Wipe face embeddings (requires PIN).
    """
    parts = action.split(maxsplit=1)
    sub = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    try:
        with _get_face_db() as db:
            # ── SET PIN ──
            if sub == "set-pin":
                pin = arg.strip()
                if len(pin) != 4 or not pin.isdigit():
                    return SlashCommandResponse(
                        command="/faceid set-pin",
                        success=False,
                        data={},
                        formatted="PIN must be exactly 4 digits. Usage: `/faceid set-pin 1234`",
                    )

                if db.has_pin():
                    return SlashCommandResponse(
                        command="/faceid set-pin",
                        success=False,
                        data={},
                        formatted="PIN already set. To change it, use the CLI: `python cli/reset.py --name Ahab --set-pin`",
                    )

                db.set_pin(pin)
                return SlashCommandResponse(
                    command="/faceid set-pin",
                    success=True,
                    data={},
                    formatted="Admin PIN has been set. Use `/faceid reset <pin>` to reset face data.",
                )

            # ── RESET ──
            if sub == "reset":
                pin = arg.strip()
                if not pin:
                    return SlashCommandResponse(
                        command="/faceid reset",
                        success=False,
                        data={},
                        formatted="Usage: `/faceid reset <4-digit-pin>`",
                    )

                if not db.has_pin():
                    return SlashCommandResponse(
                        command="/faceid reset",
                        success=False,
                        data={},
                        formatted="No PIN set yet. Run `/faceid set-pin <pin>` first.",
                    )

                if not db.verify_pin(pin):
                    db._log("reset_denied", details="Failed PIN attempt via /faceid")
                    return SlashCommandResponse(
                        command="/faceid reset",
                        success=False,
                        data={},
                        formatted="Incorrect PIN. Reset denied.",
                    )

                # Wipe all face embeddings for all entities
                entities = db.list_entities()
                total_deleted = 0
                for e in entities:
                    total_deleted += db.reset_entity(e["entity_id"])

                return SlashCommandResponse(
                    command="/faceid reset",
                    success=True,
                    data={"deleted": total_deleted},
                    formatted=f"FaceID reset complete. Deleted **{total_deleted}** embeddings.\n\nRe-enroll via CLI: `python cli/enroll.py --name Ahab --captures 10`",
                )

            return SlashCommandResponse(
                command="/faceid",
                success=False,
                data={},
                formatted=f"Unknown subcommand: `{sub}`\n\nUsage: `/faceid` | `/faceid set-pin <pin>` | `/faceid reset <pin>`",
            )

    except Exception as e:
        return SlashCommandResponse(
            command="/faceid",
            success=False,
            data={"error": str(e)},
            formatted=f"**FaceID Error:** {e}",
        )


# =============================================================================
# RESTART COMMANDS
# =============================================================================

@app.post("/slash/restart-backend", response_model=SlashCommandResponse)
async def slash_restart_backend(background_tasks: BackgroundTasks):
    """
    /restart-backend - Restart the Luna backend server.

    This triggers a graceful shutdown and restart of the server process.
    The server will be unavailable for a few seconds during restart.
    """
    import sys
    import os

    def restart_server():
        """Background task to restart the server."""
        import time
        import subprocess

        # Give time for the response to be sent
        time.sleep(1)

        # Get the current script and arguments
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "scripts", "run.py")
        python_exe = sys.executable

        # Log the restart
        logger.info("🔃 Backend restart initiated via /restart-backend command")

        # Start new server process
        env = os.environ.copy()
        subprocess.Popen(
            [python_exe, script_path, "--server"],
            env=env,
            start_new_session=True,
            stdout=open("/tmp/luna_server.log", "a"),
            stderr=subprocess.STDOUT,
        )

        # Exit current process
        logger.info("🛑 Shutting down current server instance...")
        os._exit(0)

    # Schedule restart in background
    background_tasks.add_task(restart_server)

    return SlashCommandResponse(
        command="/restart-backend",
        success=True,
        data={"status": "restarting", "message": "Backend restart initiated"},
        formatted="🔃 **Backend Restart Initiated**\n\nThe server will restart in ~2 seconds.\nRefresh the page after a few seconds to reconnect.",
    )


# =============================================================================
# PERFORMANCE LAYER SLASH COMMANDS
# =============================================================================
# Voice tuning, orb settings, emotion presets
# See: Docs/HANDOFF_PERFORMANCE_LAYER_UNIFIED.md


def _get_performance_orchestrator() -> PerformanceOrchestrator:
    """Get or create performance orchestrator."""
    global _performance_orchestrator, _orb_state_manager
    if _performance_orchestrator is None:
        _performance_orchestrator = PerformanceOrchestrator(_orb_state_manager)
    return _performance_orchestrator


@app.get("/slash/voice-tuning", response_model=SlashCommandResponse)
async def slash_voice_tuning():
    """
    /voice-tuning - Open voice tuning panel.
    """
    orchestrator = _get_performance_orchestrator()
    state = orchestrator.current_state

    return SlashCommandResponse(
        command="/voice-tuning",
        success=True,
        data={
            "current": {
                "length_scale": state.voice.length_scale,
                "noise_scale": state.voice.noise_scale,
                "noise_w": state.voice.noise_w,
                "sentence_silence": state.voice.sentence_silence,
                "pitch_shift": state.voice.pitch_shift,
            },
            "ranges": {
                "length_scale": {"min": 0.5, "max": 2.0, "step": 0.05, "label": "Speed", "inverted": True},
                "noise_scale": {"min": 0.0, "max": 1.0, "step": 0.05, "label": "Expressiveness"},
                "noise_w": {"min": 0.0, "max": 1.0, "step": 0.05, "label": "Rhythm Variation"},
                "sentence_silence": {"min": 0.0, "max": 1.0, "step": 0.05, "label": "Sentence Pause"},
                "pitch_shift": {"min": -12, "max": 12, "step": 0.5, "label": "Pitch (semitones)"},
            },
            "presets": ["neutral", "excited", "thoughtful", "warm", "playful"],
            "ui_type": "voice-tuning-panel",
        },
        formatted="**Voice Tuning**\nUse sliders to adjust Luna's voice characteristics.",
    )


class VoiceTuningUpdate(BaseModel):
    """Request body for voice tuning updates."""
    length_scale: float = 1.0
    noise_scale: float = 0.667
    noise_w: float = 0.8
    sentence_silence: float = 0.2
    pitch_shift: float = 0.0


@app.post("/slash/voice-tuning")
async def update_voice_tuning(request: VoiceTuningUpdate):
    """Update voice settings from UI."""
    orchestrator = _get_performance_orchestrator()

    knobs = VoiceKnobs(
        length_scale=request.length_scale,
        noise_scale=request.noise_scale,
        noise_w=request.noise_w,
        sentence_silence=request.sentence_silence,
        pitch_shift=request.pitch_shift,
    )
    orchestrator.set_voice_override(knobs)

    return {"success": True, "message": "Voice settings updated"}


@app.get("/slash/orb-settings", response_model=SlashCommandResponse)
async def slash_orb_settings():
    """
    /orb-settings - Open orb settings panel.
    """
    orchestrator = _get_performance_orchestrator()
    state = orchestrator.current_state

    return SlashCommandResponse(
        command="/orb-settings",
        success=True,
        data={
            "current": {
                "animation": state.orb.animation,
                "color": state.orb.color or "#a78bfa",
                "brightness": state.orb.brightness,
                "size_scale": state.orb.size_scale,
                "float_amplitude_x": state.orb.float_amplitude_x,
                "float_amplitude_y": state.orb.float_amplitude_y,
                "float_speed_x": state.orb.float_speed_x,
                "float_speed_y": state.orb.float_speed_y,
            },
            "ranges": {
                "brightness": {"min": 0.2, "max": 2.0, "step": 0.1, "label": "Brightness"},
                "size_scale": {"min": 0.5, "max": 2.0, "step": 0.1, "label": "Size"},
                "float_amplitude_x": {"min": 0, "max": 30, "step": 1, "label": "Drift X"},
                "float_amplitude_y": {"min": 0, "max": 30, "step": 1, "label": "Drift Y"},
                "float_speed_x": {"min": 0.0005, "max": 0.005, "step": 0.0005, "label": "Float Speed X"},
                "float_speed_y": {"min": 0.0005, "max": 0.005, "step": 0.0005, "label": "Float Speed Y"},
            },
            "animations": ["idle", "pulse", "pulse_fast", "spin", "spin_fast",
                          "glow", "wobble", "drift", "orbit", "flicker"],
            "color_presets": {
                "violet": "#a78bfa",
                "gold": "#FFD700",
                "coral": "#FFB7B2",
                "cyan": "#06B6D4",
                "teal": "#A8DADC",
                "orange": "#F4A261",
            },
            "ui_type": "orb-settings-panel",
        },
        formatted="**Orb Settings**\nCustomize Luna's visual appearance.",
    )


class OrbSettingsUpdate(BaseModel):
    """Request body for orb settings updates."""
    animation: str = "idle"
    color: Optional[str] = None
    brightness: float = 1.0
    size_scale: float = 1.0
    float_amplitude_x: float = 8.0
    float_amplitude_y: float = 12.0
    float_speed_x: float = 0.0015
    float_speed_y: float = 0.0023


@app.post("/slash/orb-settings")
async def update_orb_settings(request: OrbSettingsUpdate):
    """Update orb settings from UI."""
    orchestrator = _get_performance_orchestrator()

    knobs = OrbKnobs(
        animation=request.animation,
        color=request.color,
        brightness=request.brightness,
        size_scale=request.size_scale,
        float_amplitude_x=request.float_amplitude_x,
        float_amplitude_y=request.float_amplitude_y,
        float_speed_x=request.float_speed_x,
        float_speed_y=request.float_speed_y,
    )
    orchestrator.set_orb_override(knobs)

    return {"success": True, "message": "Orb settings updated"}


class DimensionOverride(BaseModel):
    """Manual dimension overrides from the diagnostic tool."""
    valence: Optional[float] = None
    arousal: Optional[float] = None
    certainty: Optional[float] = None
    engagement: Optional[float] = None
    warmth: Optional[float] = None


@app.post("/api/orb/dimensions/override")
async def override_orb_dimensions(request: DimensionOverride):
    """Override dimensional values from the expression pipeline diagnostic tool."""
    overrides = {k: v for k, v in request.model_dump().items() if v is not None}
    if _orb_state_manager:
        _orb_state_manager.apply_dimension_override(overrides)
    return {"success": True, "overrides": overrides}


@app.delete("/api/orb/dimensions/override")
async def clear_orb_dimension_overrides():
    """Clear all dimension overrides, returning to engine-driven values."""
    if _orb_state_manager:
        _orb_state_manager.apply_dimension_override({})
    return {"success": True, "message": "Overrides cleared"}


@app.get("/slash/performance", response_model=SlashCommandResponse)
async def slash_performance():
    """
    /performance - Show current performance state.
    """
    orchestrator = _get_performance_orchestrator()
    feedback = orchestrator.get_feedback()
    state = feedback["state"]

    formatted = f"""**Performance State**

**Emotion:** {state.get('emotion', 'neutral')}
**Gesture:** {state.get('gesture_source', 'none')}

**Voice:**
  Speed: {state['voice']['length_scale']}x
  Expressiveness: {state['voice']['noise_scale']}
  Rhythm: {state['voice']['noise_w']}

**Orb:**
  Animation: {state['orb']['animation']}
  Brightness: {state['orb']['brightness']}
  Color: {state['orb']['color'] or 'default'}

**Overrides:** {'Voice ' if feedback['has_voice_override'] else ''}{'Orb ' if feedback['has_orb_override'] else ''}{'(none)' if not feedback['has_voice_override'] and not feedback['has_orb_override'] else ''}
"""

    return SlashCommandResponse(
        command="/performance",
        success=True,
        data=feedback,
        formatted=formatted,
    )


@app.get("/slash/emotion/{emotion_name}", response_model=SlashCommandResponse)
async def slash_emotion(emotion_name: str):
    """
    /emotion <name> - Set emotion preset.
    """
    orchestrator = _get_performance_orchestrator()

    if orchestrator.set_emotion(emotion_name):
        return SlashCommandResponse(
            command=f"/emotion {emotion_name}",
            success=True,
            data={"emotion": emotion_name},
            formatted=f"**Emotion set to {emotion_name}**\nVoice and orb adjusted.",
        )

    valid = ", ".join([e.value for e in EmotionPreset])
    return SlashCommandResponse(
        command=f"/emotion {emotion_name}",
        success=False,
        data={"error": "unknown_emotion", "valid": valid},
        formatted=f"**Unknown emotion:** {emotion_name}\nValid: {valid}",
    )


@app.post("/slash/reset-performance")
async def slash_reset_performance():
    """
    /reset-performance - Clear all overrides.
    """
    orchestrator = _get_performance_orchestrator()
    orchestrator.clear_overrides()

    return SlashCommandResponse(
        command="/reset-performance",
        success=True,
        data={},
        formatted="**Performance reset**\nReturned to auto-detect mode.",
    )


# =============================================================================
# LLM PROVIDER ENDPOINTS
# =============================================================================
# Multi-provider support: Groq, Gemini, Claude
# See: HANDOFF_Multi_LLM_Provider_System.md

_llm_registry = None


def _get_llm_registry():
    """Get or create the LLM provider registry."""
    global _llm_registry
    if _llm_registry is None:
        from luna.llm import init_providers
        _llm_registry = init_providers()
    return _llm_registry


@app.get("/llm/providers")
async def get_llm_providers():
    """Get all LLM providers and their status."""
    registry = _get_llm_registry()
    return {
        "success": True,
        "providers": registry.get_all_status(),
    }


@app.get("/llm/current")
async def get_current_provider():
    """Get the currently selected LLM provider."""
    registry = _get_llm_registry()
    from luna.llm import get_config
    config = get_config()

    current = registry.get_current()
    if not current:
        return {"success": False, "error": "No provider available"}

    return {
        "success": True,
        "provider": config.current_provider,
        "model": config.get_provider_config(config.current_provider).default_model,
        "is_available": current.is_available,
    }


class SetProviderRequest(BaseModel):
    """Request to set the current provider."""
    provider: str
    model: Optional[str] = None


@app.post("/llm/provider")
async def set_current_provider(request: SetProviderRequest):
    """Set the current LLM provider."""
    registry = _get_llm_registry()

    if registry.set_current(request.provider):
        return {
            "success": True,
            "message": f"Switched to {request.provider}",
            "provider": request.provider,
        }

    return {
        "success": False,
        "error": f"Failed to switch to {request.provider}. Check if API key is configured.",
    }


# ==============================================================================
# Fallback Chain Endpoints
# ==============================================================================


@app.get("/llm/fallback-chain")
async def get_fallback_chain():
    """Get current fallback chain configuration and status."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    director = _engine.get_actor("director")
    if not director:
        raise HTTPException(status_code=503, detail="Director not available")

    fallback_chain = getattr(director, '_fallback_chain', None)
    if not fallback_chain:
        return {
            "success": False,
            "error": "Fallback chain not initialized",
            "chain": [],
            "providers": {},
        }

    registry = _get_llm_registry()

    # Build provider status
    providers = {}
    for name in fallback_chain.get_chain():
        if name == "local":
            local = getattr(director, '_local', None)
            providers[name] = {
                "available": local is not None and local.is_loaded if local else False,
                "in_chain": True,
                "type": "local",
            }
        else:
            provider = registry.get(name) if registry else None
            providers[name] = {
                "available": provider.is_available if provider else False,
                "in_chain": True,
                "type": "registry",
            }

    return {
        "success": True,
        "chain": fallback_chain.get_chain(),
        "providers": providers,
    }


class SetFallbackChainRequest(BaseModel):
    """Request to set fallback chain order."""
    chain: list[str]


@app.post("/llm/fallback-chain")
async def set_fallback_chain(request: SetFallbackChainRequest):
    """Set fallback chain order."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    director = _engine.get_actor("director")
    if not director:
        raise HTTPException(status_code=503, detail="Director not available")

    fallback_chain = getattr(director, '_fallback_chain', None)
    if not fallback_chain:
        raise HTTPException(status_code=503, detail="Fallback chain not initialized")

    if not request.chain:
        raise HTTPException(status_code=400, detail="Chain cannot be empty")

    # Update chain
    warnings = fallback_chain.set_chain(request.chain)

    # Persist to config file
    try:
        from luna.llm.fallback_config import FallbackConfig
        config = FallbackConfig(chain=request.chain)
        config.save()
    except Exception as e:
        warnings.append(f"Failed to persist config: {e}")

    return {
        "success": True,
        "chain": fallback_chain.get_chain(),
        "warnings": warnings,
    }


@app.get("/llm/fallback-chain/stats")
async def get_fallback_stats():
    """Get fallback chain statistics."""
    if _engine is None:
        raise HTTPException(status_code=503, detail="Engine not ready")

    director = _engine.get_actor("director")
    if not director:
        return {"total_requests": 0, "by_provider": {}, "fallback_events": 0}

    fallback_chain = getattr(director, '_fallback_chain', None)
    if not fallback_chain:
        return {"total_requests": 0, "by_provider": {}, "fallback_events": 0}

    return {
        "success": True,
        **fallback_chain.get_stats(),
    }


@app.get("/slash/llm", response_model=SlashCommandResponse)
async def slash_llm():
    """
    /llm - Show LLM provider status.
    """
    registry = _get_llm_registry()
    from luna.llm import get_config
    config = get_config()

    status = registry.get_all_status()

    lines = ["**LLM Providers**", ""]
    for name, info in status.items():
        icon = "✓" if info["is_available"] else "✗"
        current = " ← current" if info["is_current"] else ""
        model = info.get("default_model", "")
        lines.append(f"{icon} **{name}** ({model}){current}")

    lines.append("")
    lines.append("Use `/llm-switch <provider>` to change providers.")

    return SlashCommandResponse(
        command="/llm",
        success=True,
        data=status,
        formatted="\n".join(lines),
    )


@app.get("/slash/llm-switch/{provider_name}", response_model=SlashCommandResponse)
async def slash_llm_switch(provider_name: str):
    """
    /llm-switch <provider> - Switch LLM provider.
    """
    registry = _get_llm_registry()

    if registry.set_current(provider_name):
        return SlashCommandResponse(
            command=f"/llm-switch {provider_name}",
            success=True,
            data={"provider": provider_name},
            formatted=f"**Switched to {provider_name}**\nLuna will now use {provider_name} for responses.",
        )

    return SlashCommandResponse(
        command=f"/llm-switch {provider_name}",
        success=False,
        data={"error": "Provider not available"},
        formatted=f"**Failed to switch to {provider_name}**\nCheck if API key is configured.",
    )


@app.get("/slash/prompt", response_model=SlashCommandResponse)
async def slash_prompt():
    """
    /prompt - Show the last system prompt sent to the LLM.

    Useful for debugging:
    - What context is reaching the model?
    - Is the LoRA being used or is it a prompt issue?
    - Was this routed to local (Qwen) or delegated (Claude)?
    """
    global _engine

    if not _engine:
        return SlashCommandResponse(
            command="/prompt",
            success=False,
            data={"error": "Engine not initialized"},
            formatted="**Error:** Luna engine not running.",
        )

    director = _engine.get_actor("director")
    if not director:
        return SlashCommandResponse(
            command="/prompt",
            success=False,
            data={"error": "Director not found"},
            formatted="**Error:** Director actor not available.",
        )

    prompt_info = director.get_last_system_prompt()

    if not prompt_info.get("available"):
        return SlashCommandResponse(
            command="/prompt",
            success=False,
            data=prompt_info,
            formatted=f"**No prompt available**\n{prompt_info.get('message', 'Send a message first.')}",
        )

    route = prompt_info.get("route_decision", "unknown")
    length = prompt_info.get("length", 0)
    preview = prompt_info.get("preview", "")
    meta = prompt_info.get("assembler")

    # Format for display
    route_emoji = "🏠" if route == "local" else "☁️"

    # Build assembler metadata summary if available
    meta_block = ""
    if meta:
        check = lambda v: "✓" if v else "–"
        identity = meta.get("identity_source", "unknown")
        memory = meta.get("memory_source") or "none"
        gap = meta.get("gap_category") or "unknown"
        tokens = meta.get("prompt_tokens", 0)
        threads = meta.get("parked_thread_count", 0)
        register = meta.get("register_active") or "–"
        reg_on = check(meta.get("register_injected"))
        meta_block = f"""
**Assembler:**
  Identity: **{identity}** | Memory: **{memory}** | Gap: **{gap}**
  Temporal: {check(meta.get('temporal_injected'))} | Voice: {check(meta.get('voice_injected'))} | Register: {reg_on} ({register}) | Tokens: ~{tokens}
  Threads parked: {threads}
"""

    formatted = f"""**{route_emoji} Last System Prompt** ({route})

**Length:** {length} chars
{meta_block}
**Preview:**
```
{preview}
```

*Use browser console or logs for full prompt.*"""

    return SlashCommandResponse(
        command="/prompt",
        success=True,
        data=prompt_info,
        formatted=formatted,
    )


@app.get("/slash/register", response_model=SlashCommandResponse)
async def slash_register_get():
    """
    /register - Show context register state + sovereignty debug info.

    Displays: active register, confidence, weights, fired signals,
    bridge/sovereignty info, and denied document count.
    """
    global _engine

    if not _engine:
        return SlashCommandResponse(
            command="/register",
            success=False,
            data={"error": "Engine not initialized"},
            formatted="**Error:** Luna engine not running.",
        )

    director = _engine.get_actor("director")
    if not director:
        return SlashCommandResponse(
            command="/register",
            success=False,
            data={"error": "Director not found"},
            formatted="**Error:** Director actor not available.",
        )

    state = director.get_register_state()
    reg = state.get("register", {})
    bridge = state.get("bridge", {})
    intent_info = state.get("intent", {})
    enabled = state.get("enabled", False)

    active = reg.get("active", "ambient")
    confidence = reg.get("confidence", 0.0)
    weights = reg.get("weights", {})
    signals = reg.get("fired_signals", [])
    denied = state.get("denied_docs", 0)

    status_icon = "🟢" if enabled else "🔴"

    # Build weight bars
    weight_lines = []
    for name, weight in sorted(weights.items(), key=lambda x: -x[1]):
        bar_len = int(weight * 10)
        bar = "█" * bar_len + "░" * (10 - bar_len)
        marker = " ◄ active" if name == active else ""
        weight_lines.append(f"  `{name:<22}` {bar} {weight:.3f}{marker}")

    weights_block = "\n".join(weight_lines) if weight_lines else "  No weights (no generation yet)"

    # Bridge info
    entity = bridge.get("entity_id")
    if entity:
        tier = bridge.get("luna_tier", "?")
        dt = bridge.get("dataroom_tier", "?")
        sov = "sovereign" if bridge.get("is_sovereign") else f"tier {dt}"
        bridge_line = f"**{entity}** ({tier}, {sov})"
    else:
        bridge_line = "No entity recognized"

    signals_str = ", ".join(signals) if signals else "none"

    formatted = f"""{status_icon} **Register: {active}** (confidence: {confidence:.2f})

**Weights:**
{weights_block}

**Fired signals:** {signals_str}

**Sovereignty:**
  Bridge: {bridge_line}
  Denied docs: {denied}
  Intent: {intent_info.get('mode', '?')}"""

    return SlashCommandResponse(
        command="/register",
        success=True,
        data=state,
        formatted=formatted,
    )


@app.post("/slash/register", response_model=SlashCommandResponse)
async def slash_register_toggle(enabled: bool):
    """
    Toggle context register on/off.

    POST /slash/register?enabled=true  → enable
    POST /slash/register?enabled=false → disable
    """
    global _engine

    if not _engine:
        return SlashCommandResponse(
            command="/register",
            success=False,
            data={"error": "Engine not initialized"},
            formatted="**Error:** Luna engine not running.",
        )

    director = _engine.get_actor("director")
    if not director:
        return SlashCommandResponse(
            command="/register",
            success=False,
            data={"error": "Director not found"},
            formatted="**Error:** Director actor not available.",
        )

    director.set_register_enabled(enabled)
    status = "enabled" if enabled else "disabled"

    return SlashCommandResponse(
        command="/register",
        success=True,
        data={"enabled": enabled},
        formatted=f"Context register **{status}**.",
    )


@app.get("/slash/vk", response_model=SlashCommandResponse)
@app.get("/slash/voight-kampff", response_model=SlashCommandResponse)
async def slash_voight_kampff(layer: int = None):
    """
    /vk or /voight-kampff - Run Luna identity verification test.

    Tests 4 layers of Luna's identity chain:
    1. LoRA Loading - Is personality adapter active?
    2. Memory Retrieval - Can memories be found?
    3. Context Injection - Are memories reaching prompts?
    4. Output Quality - Does output reflect Luna?

    Args:
        layer: Optional layer number (1-4) to run only that layer
    """
    import asyncio
    from pathlib import Path
    import sys

    # Add scripts/utils path for import
    scripts_path = Path(__file__).parent.parent.parent.parent / "scripts" / "utils"
    if str(scripts_path) not in sys.path:
        sys.path.insert(0, str(scripts_path))

    try:
        from voight_kampff import VoightKampff

        luna_root = Path(__file__).parent.parent.parent.parent
        vk = VoightKampff(luna_root)

        if layer:
            # Single layer
            result = await vk.run_layer(layer)
            await vk.cleanup()

            status = "✅" if result.passed else "❌"
            lines = [
                f"**Layer {result.layer}: {result.name}**",
                f"Status: {status}",
                f"Score: {result.score}/{result.max_score}",
            ]
            if result.error:
                lines.append(f"Error: {result.error}")
            lines.append(f"Duration: {result.duration_ms:.0f}ms")

            return SlashCommandResponse(
                command=f"/vk --layer {layer}",
                success=result.passed,
                data={
                    "layer": result.layer,
                    "name": result.name,
                    "passed": result.passed,
                    "score": result.score,
                    "max_score": result.max_score,
                    "error": result.error,
                },
                formatted="\n".join(lines),
            )
        else:
            # Full test
            report = await vk.run_all()
            await vk.cleanup()

            # Build summary
            lines = [
                "**🧠 VOIGHT-KAMPFF RESULTS**",
                "",
            ]

            for lr in report.layers:
                status = "✅" if lr.passed else "❌"
                lines.append(f"  {status} Layer {lr.layer}: {lr.name} ({lr.score}/{lr.max_score})")

            lines.append("")
            verdict_icon = "✅" if report.overall_passed else "❌"
            lines.append(f"**VERDICT: {verdict_icon} {report.verdict}**")

            if report.first_failure:
                lines.append(f"\nFirst failure: {report.first_failure}")

            if report.recommendations:
                lines.append("\n**Recommendations:**")
                for rec in report.recommendations[:3]:
                    lines.append(f"  • {rec}")

            lines.append(f"\nDuration: {report.total_duration_ms:.0f}ms")
            lines.append("Full results: `Docs/Handoffs/VoightKampffResults/`")

            return SlashCommandResponse(
                command="/vk",
                success=report.overall_passed,
                data={
                    "verdict": report.verdict,
                    "passed": report.overall_passed,
                    "first_failure": report.first_failure,
                    "layers": [
                        {"layer": l.layer, "name": l.name, "passed": l.passed, "score": l.score}
                        for l in report.layers
                    ],
                },
                formatted="\n".join(lines),
            )

    except Exception as e:
        logger.error(f"Voight-Kampff test failed: {e}")
        import traceback
        traceback.print_exc()

        return SlashCommandResponse(
            command="/vk",
            success=False,
            data={"error": str(e)},
            formatted=f"**❌ Voight-Kampff Test Failed**\n\n{e}\n\nTry running manually:\n`.venv/bin/python scripts/utils/voight_kampff.py`",
        )


# ═══════════════════════════════════════════════════════════════════════════
# QA SYSTEM ENDPOINTS
# Luna QA v2 — Live validation system for inference quality
# ═══════════════════════════════════════════════════════════════════════════

class QAHealthResponse(BaseModel):
    """Response from /qa/health endpoint."""
    pass_rate: float
    total_24h: int
    failed_24h: int
    failing_bugs: int
    recent_failures: list[str]
    top_failures: list[dict] = []


class QAReportResponse(BaseModel):
    """Response from /qa/last endpoint."""
    inference_id: str
    timestamp: str
    query: str
    route: str
    provider_used: str
    latency_ms: float
    passed: bool
    failed_count: int
    diagnosis: Optional[str]
    assertions: list[dict]
    context: dict


class QAStatsResponse(BaseModel):
    """Response from /qa/stats endpoint."""
    total: int
    passed: int
    failed: int
    pass_rate: float
    time_range: str
    top_failures: list[dict] = []


class QAAssertionResponse(BaseModel):
    """Response from /qa/assertions endpoint."""
    id: str
    name: str
    description: str = ""
    category: str
    severity: str
    enabled: bool
    check_type: str


class QABugResponse(BaseModel):
    """Response from /qa/bugs endpoint."""
    id: str
    name: str
    query: str
    expected_behavior: str
    actual_behavior: str
    status: str
    severity: str


@app.get("/qa/health", response_model=QAHealthResponse)
async def qa_get_health():
    """
    Get QA system health summary.

    Returns pass rate, failure counts, and recent issues.
    """
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA system not available")

    validator = get_qa_validator()
    health = validator.get_health()
    return QAHealthResponse(**health)


@app.post("/qa/recalibrate")
async def qa_recalibrate():
    """Mark a recalibration point. Stats will show 'since recalibration' context."""
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA system not available")
    validator = get_qa_validator()
    ts = validator.mark_recalibration()
    return {"status": "recalibrated", "timestamp": ts.isoformat()}


@app.get("/qa/last")
async def qa_get_last_report():
    """
    Get the most recent QA report.

    Returns full details of the last inference validation.
    """
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA system not available")

    validator = get_qa_validator()
    report = validator.get_last_report()

    if not report:
        return {"error": "No reports yet"}

    return report.to_dict()


@app.get("/qa/stats", response_model=QAStatsResponse)
async def qa_get_stats(time_range: str = "24h"):
    """
    Get QA statistics for a time range.

    Args:
        time_range: "1h", "24h", "7d", "30d"
    """
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA system not available")

    validator = get_qa_validator()
    stats = validator.get_stats(time_range)
    return QAStatsResponse(**stats)


@app.get("/qa/stats/detailed")
async def qa_get_stats_detailed(time_range: str = "7d"):
    """
    Get detailed QA statistics with breakdowns.

    Returns:
        - Basic stats (total, passed, failed, pass_rate)
        - Trend data (daily breakdown)
        - By route breakdown
        - By provider breakdown
        - By assertion breakdown
    """
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA system not available")

    from datetime import datetime, timedelta
    from collections import defaultdict

    validator = get_qa_validator()
    db = validator._db

    # Get time range
    hours = {"1h": 1, "24h": 24, "7d": 168, "30d": 720}.get(time_range, 168)
    since = datetime.now() - timedelta(hours=hours)

    # Get all reports in range
    reports = db.get_recent_reports(500)  # Get enough for analysis
    reports_in_range = [
        r for r in reports
        if datetime.fromisoformat(r["timestamp"]) > since
    ]

    # Basic stats
    total = len(reports_in_range)
    passed = sum(1 for r in reports_in_range if r["passed"])
    failed = total - passed

    # Trend data (group by day)
    trend_data = defaultdict(lambda: {"passed": 0, "failed": 0})
    for r in reports_in_range:
        date = datetime.fromisoformat(r["timestamp"]).strftime("%b %d")
        if r["passed"]:
            trend_data[date]["passed"] += 1
        else:
            trend_data[date]["failed"] += 1

    trend = [
        {"date": date, "passed": data["passed"], "failed": data["failed"]}
        for date, data in sorted(trend_data.items())
    ][-7:]  # Last 7 days

    # By route breakdown
    by_route = defaultdict(lambda: {"passed": 0, "failed": 0})
    for r in reports_in_range:
        route = r.get("route", "unknown")
        if r["passed"]:
            by_route[route]["passed"] += 1
        else:
            by_route[route]["failed"] += 1

    # By provider breakdown
    by_provider = defaultdict(lambda: {"passed": 0, "failed": 0})
    for r in reports_in_range:
        provider = r.get("provider_used", "unknown")
        if r["passed"]:
            by_provider[provider]["passed"] += 1
        else:
            by_provider[provider]["failed"] += 1

    # By assertion breakdown
    by_assertion = defaultdict(lambda: {"name": "", "passed": 0, "failed": 0})
    for r in reports_in_range:
        for a in r.get("assertions", []):
            aid = a.get("id", "unknown")
            by_assertion[aid]["name"] = a.get("name", aid)
            if a.get("passed"):
                by_assertion[aid]["passed"] += 1
            else:
                by_assertion[aid]["failed"] += 1

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": passed / total if total > 0 else 0,
        "time_range": time_range,
        "trend": trend,
        "by_route": dict(by_route),
        "by_provider": dict(by_provider),
        "by_assertion": dict(by_assertion),
    }


@app.get("/qa/history")
async def qa_get_history(limit: int = 100):
    """
    Get QA report history.

    Args:
        limit: Maximum number of reports to return
    """
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA system not available")

    validator = get_qa_validator()
    return validator.get_history(limit)


@app.get("/qa/assertions")
async def qa_list_assertions():
    """
    List all configured assertions.

    Returns both built-in and custom assertions.
    """
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA system not available")

    validator = get_qa_validator()
    return [
        {
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "category": a.category,
            "severity": a.severity,
            "enabled": a.enabled,
            "check_type": a.check_type,
        }
        for a in validator.get_assertions()
    ]


class AddAssertionRequest(BaseModel):
    """Request body for adding a custom assertion."""
    name: str
    category: str  # structural, voice, personality, flow
    severity: str  # critical, high, medium, low
    target: str  # response, raw_response, system_prompt, query
    condition: str  # contains, not_contains, regex, length_gt, length_lt
    pattern: str
    case_sensitive: bool = False


@app.post("/qa/assertions")
async def qa_add_assertion(req: AddAssertionRequest):
    """
    Add a custom pattern-based assertion.

    Example:
        POST /qa/assertions
        {
            "name": "No French",
            "category": "voice",
            "severity": "medium",
            "target": "response",
            "condition": "not_contains",
            "pattern": "bonjour"
        }
    """
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA system not available")

    import uuid
    validator = get_qa_validator()

    assertion = Assertion(
        id=f"CUSTOM-{uuid.uuid4().hex[:6].upper()}",
        name=req.name,
        description=f"Custom: {req.condition} '{req.pattern}' in {req.target}",
        category=req.category,
        severity=req.severity,
        check_type="pattern",
        pattern_config=PatternConfig(
            target=req.target,
            match_type=req.condition,
            pattern=req.pattern,
            case_sensitive=req.case_sensitive,
        ),
    )

    assertion_id = validator.add_assertion(assertion)
    return {"assertion_id": assertion_id, "name": req.name}


@app.put("/qa/assertions/{assertion_id}")
async def qa_toggle_assertion(assertion_id: str, enabled: bool):
    """
    Enable or disable an assertion.

    Args:
        assertion_id: The assertion ID (e.g., "P1", "CUSTOM-ABC123")
        enabled: Whether to enable (true) or disable (false)
    """
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA system not available")

    validator = get_qa_validator()
    success = validator.toggle_assertion(assertion_id, enabled)
    return {"success": success, "assertion_id": assertion_id, "enabled": enabled}


@app.delete("/qa/assertions/{assertion_id}")
async def qa_delete_assertion(assertion_id: str):
    """
    Delete a custom assertion.

    Note: Built-in assertions (P1, S1, V1, F1, etc.) cannot be deleted.
    """
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA system not available")

    validator = get_qa_validator()
    success = validator.delete_assertion(assertion_id)

    if not success:
        raise HTTPException(status_code=400, detail="Cannot delete built-in assertions")

    return {"success": success}


# ═══════════════════════════════════════════════════════════
# QA BUG ENDPOINTS
# ═══════════════════════════════════════════════════════════

@app.get("/qa/bugs")
async def qa_list_bugs(status: str = None):
    """
    List known bugs.

    Args:
        status: Filter by status (open, failing, fixed, wontfix)
    """
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA system not available")

    validator = get_qa_validator()
    if status:
        return validator._db.get_bugs_by_status(status)
    return validator._db.get_all_bugs()


class AddBugRequest(BaseModel):
    """Request body for adding a bug."""
    name: str
    query: str
    expected_behavior: str
    actual_behavior: str
    severity: str = "high"


@app.post("/qa/bugs")
async def qa_add_bug(req: AddBugRequest):
    """
    Add a known bug to the regression database.

    This bug will be tested in regression runs.
    """
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA system not available")

    validator = get_qa_validator()
    bug_id = validator._db.generate_bug_id()
    validator._db.store_bug({
        "id": bug_id,
        "name": req.name,
        "query": req.query,
        "expected_behavior": req.expected_behavior,
        "actual_behavior": req.actual_behavior,
        "severity": req.severity,
    })
    return {"bug_id": bug_id, "name": req.name}


@app.post("/qa/bugs/from-last")
async def qa_add_bug_from_last(name: str, expected_behavior: str):
    """
    Create a bug from the last failed QA report.

    Automatically captures query and actual behavior.
    """
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA system not available")

    validator = get_qa_validator()
    report = validator.get_last_report()

    if not report:
        raise HTTPException(status_code=404, detail="No reports available")

    bug_id = validator._db.generate_bug_id()
    validator._db.store_bug({
        "id": bug_id,
        "name": name,
        "query": report.query,
        "expected_behavior": expected_behavior,
        "actual_behavior": report.context.final_response[:500],
        "affected_assertions": [a.id for a in report.failed_assertions],
    })

    return {"bug_id": bug_id, "query": report.query}


@app.get("/qa/bugs/{bug_id}")
async def qa_get_bug(bug_id: str):
    """Get details for a specific bug."""
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA system not available")

    validator = get_qa_validator()
    bug = validator._db.get_bug_by_id(bug_id)

    if not bug:
        raise HTTPException(status_code=404, detail=f"Bug {bug_id} not found")

    return bug


@app.put("/qa/bugs/{bug_id}")
async def qa_update_bug_status(bug_id: str, status: str):
    """
    Update a bug's status.

    Args:
        status: open, failing, fixed, wontfix
    """
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA system not available")

    validator = get_qa_validator()
    validator._db.update_bug_status(bug_id, status)
    return {"bug_id": bug_id, "status": status}


# ═══════════════════════════════════════════════════════════
# QA SIMULATION ENDPOINT
# ═══════════════════════════════════════════════════════════


class SimulateRequest(BaseModel):
    """Request body for /qa/simulate endpoint."""
    query: str = Field(..., description="The query to simulate")
    bug_id: Optional[str] = Field(None, description="Associated bug ID if testing a known bug")


@app.post("/qa/simulate")
async def qa_simulate(request: SimulateRequest):
    """
    Run a simulation against a specific query.

    This sends the query through the full inference pipeline and validates
    the response against QA assertions. Used for testing bug regressions.
    """
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA system not available")

    if not _engine:
        raise HTTPException(status_code=503, detail="Engine not started")

    import time
    import uuid
    from datetime import datetime

    start_time = time.time()
    inference_id = f"SIM-{uuid.uuid4().hex[:8]}"

    try:
        # Run message through engine via callback pattern (same as /message)
        response_future: asyncio.Future = asyncio.Future()

        async def on_sim_response(text: str, data: dict) -> None:
            if not response_future.done():
                response_future.set_result((text, data))

        _engine.on_response(on_sim_response)

        try:
            await _engine.send_message(request.query, source="qa-simulate")
            response_text, response_data = await asyncio.wait_for(response_future, timeout=30.0)
        finally:
            if on_sim_response in _engine._on_response_callbacks:
                _engine._on_response_callbacks.remove(on_sim_response)

        latency_ms = (time.time() - start_time) * 1000

        # Use the QA report the background validator just wrote (fire-and-forget)
        # Give it a brief moment to complete
        await asyncio.sleep(0.2)

        validator = get_qa_validator()

        # Use last report if it matches the query, otherwise build minimal context
        report = None
        if validator._last_report and validator._last_report.query == request.query:
            report = validator._last_report
        else:
            from luna.qa import InferenceContext
            ctx = InferenceContext(
                inference_id=inference_id,
                session_id="simulation",
                timestamp=datetime.now(),
                query=request.query,
                route=response_data.get("route_decision", "SIMULATION"),
                provider_used=response_data.get("provider_used", "unknown"),
                latency_ms=latency_ms,
                personality_injected=True,
                personality_length=5000,
                virtues_loaded=True,
                raw_response=response_text,
                final_response=response_text,
            )
            report = validator.validate(ctx)

        final_text = response_text

        return {
            "inference_id": inference_id,
            "bug_id": request.bug_id,
            "query": request.query,
            "passed": report.passed,
            "failed_count": report.failed_count,
            "latency_ms": latency_ms,
            "response": final_text,
            "final_response": final_text,
            "failed_assertions": [a.id for a in report.failed_assertions],
            "diagnosis": report.diagnosis,
            "assertions": [
                {
                    "id": a.id,
                    "name": a.name,
                    "passed": a.passed,
                    "severity": a.severity,
                    "expected": a.expected,
                    "actual": a.actual,
                }
                for a in report.assertions
            ],
        }

    except asyncio.TimeoutError:
        return {
            "inference_id": inference_id,
            "bug_id": request.bug_id,
            "query": request.query,
            "passed": False,
            "failed_count": 1,
            "latency_ms": 30000,
            "response": "Timeout",
            "final_response": "Timeout",
            "failed_assertions": ["TIMEOUT"],
            "diagnosis": "Simulation timed out after 30 seconds",
            "assertions": [],
        }
    except Exception as e:
        logger.error(f"Simulation failed: {e}")
        return {
            "inference_id": inference_id,
            "bug_id": request.bug_id,
            "query": request.query,
            "passed": False,
            "failed_count": 1,
            "latency_ms": (time.time() - start_time) * 1000,
            "response": str(e),
            "final_response": str(e),
            "failed_assertions": ["EXCEPTION"],
            "diagnosis": f"Simulation failed with exception: {e}",
            "assertions": [],
        }


# ═══════════════════════════════════════════════════════════
# QA SLASH COMMAND
# ═══════════════════════════════════════════════════════════

@app.get("/slash/qa", response_model=SlashCommandResponse)
async def slash_qa():
    """
    /qa - Quick QA health check.

    Shows pass rate, recent failures, and known bugs.
    """
    if not QA_AVAILABLE:
        return SlashCommandResponse(
            command="/qa",
            success=False,
            data={"error": "QA system not available"},
            formatted="**❌ QA System Not Available**\n\nThe QA module failed to load.",
        )

    validator = get_qa_validator()
    health = validator.get_health()

    # Build formatted output
    pass_rate = health.get("pass_rate", 0) * 100
    status_icon = "✅" if pass_rate >= 90 else "⚠️" if pass_rate >= 70 else "❌"

    lines = [
        f"**{status_icon} QA Health: {pass_rate:.1f}% pass rate**",
        "",
        f"• Total (24h): {health.get('total_24h', 0)}",
        f"• Failed (24h): {health.get('failed_24h', 0)}",
        f"• Open bugs: {health.get('failing_bugs', 0)}",
    ]

    if health.get("recent_failures"):
        lines.append("")
        lines.append("**Recent failures:**")
        for name in health.get("recent_failures", [])[:5]:
            lines.append(f"  • {name}")

    if health.get("top_failures"):
        lines.append("")
        lines.append("**Top failing assertions:**")
        for f in health.get("top_failures", [])[:3]:
            lines.append(f"  • {f['name']} ({f['count']}x)")

    return SlashCommandResponse(
        command="/qa",
        success=pass_rate >= 70,
        data=health,
        formatted="\n".join(lines),
    )


@app.get("/slash/qa-last", response_model=SlashCommandResponse)
async def slash_qa_last():
    """
    /qa-last - Show last QA report details.
    """
    if not QA_AVAILABLE:
        return SlashCommandResponse(
            command="/qa-last",
            success=False,
            data={"error": "QA system not available"},
            formatted="**❌ QA System Not Available**",
        )

    validator = get_qa_validator()
    report = validator.get_last_report()

    if not report:
        return SlashCommandResponse(
            command="/qa-last",
            success=True,
            data={"message": "No reports yet"},
            formatted="No QA reports yet. Send a message to generate one.",
        )

    # Build formatted output
    status_icon = "✅" if report.passed else "❌"
    lines = [
        f"**{status_icon} Last QA Report**",
        "",
        f"• Query: \"{report.query[:50]}{'...' if len(report.query) > 50 else ''}\"",
        f"• Route: {report.route}",
        f"• Provider: {report.provider_used}",
        f"• Latency: {report.latency_ms:.0f}ms",
        "",
    ]

    if report.passed:
        lines.append(f"All {len(report.assertions)} assertions passed.")
    else:
        lines.append(f"**{report.failed_count} assertion(s) failed:**")
        for a in report.failed_assertions:
            lines.append(f"  • [{a.severity}] {a.name}: {a.actual}")

        if report.diagnosis:
            lines.append("")
            lines.append(f"**Diagnosis:** {report.diagnosis[:200]}{'...' if len(report.diagnosis) > 200 else ''}")

    return SlashCommandResponse(
        command="/qa-last",
        success=report.passed,
        data=report.to_dict(),
        formatted="\n".join(lines),
    )


# ═══════════════════════════════════════════════════════════
# VOIGHT-KAMPFF ENDPOINTS
# ═══════════════════════════════════════════════════════════


@app.get("/vk/results/voice-memory")
async def get_vk_voice_memory_results():
    """
    Get the latest Voice Memory VK test results.

    Returns the results from the last test run, loaded from the JSON file.
    """
    import json
    from pathlib import Path

    results_path = Path(__file__).parent.parent.parent.parent / "Docs" / "Handoffs" / "VoightKampffResults" / "voice_memory_results.json"

    if not results_path.exists():
        raise HTTPException(status_code=404, detail="No test results found. Run the test suite first.")

    try:
        with open(results_path) as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load results: {e}")


@app.get("/vk/results/latest")
async def get_vk_latest_results():
    """
    Get the latest VK test results from any suite.
    """
    import json
    from pathlib import Path

    results_dir = Path(__file__).parent.parent.parent.parent / "Docs" / "Handoffs" / "VoightKampffResults"

    if not results_dir.exists():
        raise HTTPException(status_code=404, detail="No test results directory found")

    # Find most recent results file
    result_files = list(results_dir.glob("*_results.json"))
    if not result_files:
        raise HTTPException(status_code=404, detail="No test results found")

    # Sort by modification time, get most recent
    latest = max(result_files, key=lambda p: p.stat().st_mtime)

    try:
        with open(latest) as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load results: {e}")


# ============================================
# OBSERVATORY REVERSE PROXY  (port 8100)
# ============================================
# Mirrors the Vite dev-server proxy: strip /observatory prefix, forward to :8100.

_OBSERVATORY_TARGET = os.environ.get("LUNA_OBSERVATORY_URL", "http://127.0.0.1:8100")
_observatory_client: Optional[httpx.AsyncClient] = None


def _get_observatory_client() -> httpx.AsyncClient:
    global _observatory_client
    if _observatory_client is None or _observatory_client.is_closed:
        _observatory_client = httpx.AsyncClient(base_url=_OBSERVATORY_TARGET, timeout=30.0)
    return _observatory_client


@app.api_route("/observatory/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def observatory_proxy(request: Request, path: str):
    """Reverse-proxy HTTP requests to Observatory server on port 8100."""
    client = _get_observatory_client()
    url = f"/{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"
    try:
        resp = await client.request(
            method=request.method,
            url=url,
            headers={k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")},
            content=await request.body(),
        )
        return Response(
            content=resp.content,
            status_code=resp.status_code,
            headers=dict(resp.headers),
            media_type=resp.headers.get("content-type"),
        )
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Observatory server not reachable on port 8100")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Observatory proxy error: {e}")


@app.websocket("/observatory/ws/{path:path}")
async def observatory_ws_proxy(websocket: WebSocket, path: str):
    """Reverse-proxy WebSocket connections to Observatory server."""
    await websocket.accept()
    proto = "wss" if _OBSERVATORY_TARGET.startswith("https") else "ws"
    host = _OBSERVATORY_TARGET.replace("http://", "").replace("https://", "")
    ws_url = f"{proto}://{host}/ws/{path}"

    try:
        import websockets
        async with websockets.connect(ws_url) as upstream:
            async def forward_to_client():
                try:
                    async for msg in upstream:
                        await websocket.send_text(msg)
                except Exception:
                    pass

            async def forward_to_upstream():
                try:
                    while True:
                        data = await websocket.receive_text()
                        await upstream.send(data)
                except Exception:
                    pass

            await asyncio.gather(forward_to_client(), forward_to_upstream())
    except ImportError:
        # Fallback: websockets not installed — WS proxy unavailable
        logger.warning("websockets package not installed; Observatory WS proxy disabled")
        await websocket.close(code=1011, reason="WebSocket proxy unavailable")
    except Exception as e:
        logger.debug(f"Observatory WS proxy closed: {e}")
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


# ==============================================================================
# AiBrarian Engine API (HTTP surface for Google Sheets, Guardian, etc.)
# ==============================================================================

_aibrarian_engine = None

async def _get_aibrarian_engine():
    """Get the Engine-owned AiBrarianEngine instance.

    Prefers the Engine-owned instance (Phase 1 ownership). Falls back to
    standalone initialization only when the Engine hasn't booted yet.
    """
    global _aibrarian_engine
    if _aibrarian_engine is not None:
        return _aibrarian_engine

    # Phase 1: use Engine-owned instance
    if _engine is not None and getattr(_engine, "aibrarian", None) is not None:
        _aibrarian_engine = _engine.aibrarian
        return _aibrarian_engine

    # Fallback: standalone init (server started without full Engine boot)
    from luna.substrate.aibrarian_engine import AiBrarianEngine
    _project = Path(__file__).parent.parent.parent.parent
    _aibrarian_engine = AiBrarianEngine(
        _project / "config" / "aibrarian_registry.yaml",
        project_root=_project,
    )
    await _aibrarian_engine.initialize()
    logger.warning("AiBrarianEngine fallback: standalone init in server.py")
    return _aibrarian_engine


class AiBrarianSearchRequest(BaseModel):
    collection: str = "dataroom"
    query: str
    search_type: str = "hybrid"
    limit: int = 10


class AiBrarianIngestRequest(BaseModel):
    collection: str = "dataroom"
    file_path: str
    metadata: dict = Field(default_factory=dict)


@app.get("/api/nexus/list")
async def api_aibrarian_list():
    engine = await _get_aibrarian_engine()
    return {"collections": engine.list_collections()}


@app.post("/api/nexus/search")
async def api_aibrarian_search(req: AiBrarianSearchRequest):
    engine = await _get_aibrarian_engine()
    results = await engine.search(req.collection, req.query, req.search_type, req.limit)
    return {"results": results, "count": len(results)}


@app.get("/api/nexus/{collection_key}/stats")
async def api_aibrarian_stats(collection_key: str):
    engine = await _get_aibrarian_engine()
    return await engine.stats(collection_key)


@app.post("/api/nexus/ingest")
async def api_aibrarian_ingest(req: AiBrarianIngestRequest):
    engine = await _get_aibrarian_engine()
    doc_id = await engine.ingest(req.collection, Path(req.file_path), req.metadata)
    return {"doc_id": doc_id, "status": "ingested" if doc_id else "skipped"}


# --- Co-occurrence (POST — matches existing pattern) ---

class AiBrarianCoOccurrenceRequest(BaseModel):
    collection: str = "dataroom"
    terms: str
    limit: int = 50

@app.post("/api/nexus/co-occurrence")
async def api_aibrarian_co_occurrence(req: AiBrarianCoOccurrenceRequest):
    engine = await _get_aibrarian_engine()
    term_list = [t.strip() for t in req.terms.split(",") if t.strip()]
    results = await engine.co_occurrence(req.collection, term_list, req.limit)
    return {"terms": term_list, "count": len(results), "documents": results}


# --- Document retrieval ---

@app.get("/api/nexus/{c}/documents")
async def api_aibrarian_list_documents(c: str, skip: int = 0, limit: int = 50):
    engine = await _get_aibrarian_engine()
    return await engine.list_documents(c, skip, limit)

@app.get("/api/nexus/{c}/documents/{doc_id}")
async def api_aibrarian_get_document(c: str, doc_id: str):
    engine = await _get_aibrarian_engine()
    doc = await engine.get_document(c, doc_id)
    if not doc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return doc


# --- Count & term stats ---

@app.get("/api/nexus/{c}/count")
async def api_aibrarian_count(c: str, q: str = "", search_type: str = "keyword"):
    engine = await _get_aibrarian_engine()
    n = await engine.count(c, q, search_type)
    return {"query": q, "search_type": search_type, "count": n}

@app.get("/api/nexus/{c}/terms")
async def api_aibrarian_term_stats(c: str, terms: str = ""):
    engine = await _get_aibrarian_engine()
    term_list = [t.strip() for t in terms.split(",") if t.strip()]
    counts = await engine.term_stats(c, term_list)
    return {"counts": counts}


# --- Entities ---

@app.get("/api/nexus/{c}/entities/top")
async def api_aibrarian_top_entities(c: str, limit: int = 50, sample_size: int = 100):
    engine = await _get_aibrarian_engine()
    return await engine.top_entities(c, limit, sample_size)

@app.get("/api/nexus/{c}/entities/search")
async def api_aibrarian_search_entity(c: str, name: str = "", limit: int = 50):
    engine = await _get_aibrarian_engine()
    return await engine.search_entity(c, name, limit)

@app.get("/api/nexus/{c}/entities/{doc_id}")
async def api_aibrarian_document_entities(c: str, doc_id: str):
    engine = await _get_aibrarian_engine()
    return await engine.document_entities(c, doc_id)


# --- Timeline ---

@app.get("/api/nexus/{c}/timeline")
async def api_aibrarian_timeline(c: str, q: str = "", limit: int = 100, confidence: str = ""):
    engine = await _get_aibrarian_engine()
    conf = confidence if confidence else None
    return await engine.timeline(c, q, limit, conf)

@app.get("/api/nexus/{c}/timeline/range")
async def api_aibrarian_timeline_range(c: str, start: str = "", end: str = "", limit: int = 100, confidence: str = ""):
    engine = await _get_aibrarian_engine()
    conf = confidence if confidence else None
    return await engine.timeline_range(c, start, end, limit, conf)

@app.get("/api/nexus/{c}/timeline/{doc_id}")
async def api_aibrarian_document_timeline(c: str, doc_id: str, confidence: str = ""):
    engine = await _get_aibrarian_engine()
    conf = confidence if confidence else None
    return await engine.document_timeline(c, doc_id, conf)


# --- Analytics ---

@app.get("/api/nexus/{c}/analytics/frequency")
async def api_aibrarian_word_frequency(c: str, q: str = "", top: int = 50):
    engine = await _get_aibrarian_engine()
    return await engine.word_frequency(c, q, top)

@app.get("/api/nexus/{c}/analytics/ngrams")
async def api_aibrarian_ngrams(c: str, q: str = "", n: int = 2, top: int = 30):
    engine = await _get_aibrarian_engine()
    return await engine.ngrams(c, q, n, top)

@app.get("/api/nexus/{c}/analytics/wordcloud")
async def api_aibrarian_wordcloud(c: str, q: str = "", top: int = 100):
    engine = await _get_aibrarian_engine()
    return await engine.wordcloud(c, q, top)

@app.get("/api/nexus/{c}/analytics/compare")
async def api_aibrarian_compare_terms(c: str, terms: str = "", context_window: int = 5, top: int = 20):
    engine = await _get_aibrarian_engine()
    term_list = [t.strip() for t in terms.split(",") if t.strip()]
    return await engine.compare_terms(c, term_list, context_window, top)


# --- Similarity ---

@app.get("/api/nexus/{c}/similar/{doc_id}")
async def api_aibrarian_similar(c: str, doc_id: str, limit: int = 10):
    engine = await _get_aibrarian_engine()
    results = await engine.similar(c, doc_id, limit)
    return {"source_doc": doc_id, "similar_documents": results, "count": len(results)}

@app.get("/api/nexus/{c}/similarity/batch")
async def api_aibrarian_batch_similarity(c: str, doc_ids: str = ""):
    engine = await _get_aibrarian_engine()
    id_list = [d.strip() for d in doc_ids.split(",") if d.strip()]
    return await engine.batch_similarity(c, id_list)


# --- Export ---

@app.get("/api/nexus/{c}/export/csv")
async def api_aibrarian_export_csv(c: str, q: str = "", limit: int = 1000):
    engine = await _get_aibrarian_engine()
    import csv, io
    from fastapi.responses import StreamingResponse
    results = await engine.search(c, q, "hybrid", limit)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["doc_id", "title", "filename", "category", "score", "snippet"])
    for r in results:
        writer.writerow([r.get("doc_id"), r.get("title"), r.get("filename"),
                         r.get("category"), r.get("score"), r.get("snippet", "")[:300]])
    output.seek(0)
    safe_q = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in q)[:50]
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="nexus_{safe_q}.csv"'},
    )

@app.get("/api/nexus/{c}/export/json")
async def api_aibrarian_export_json(c: str, q: str = "", limit: int = 1000):
    engine = await _get_aibrarian_engine()
    return await engine.export_search(c, q, limit, "json")

@app.get("/api/nexus/{c}/export/document/{doc_id}")
async def api_aibrarian_export_document(c: str, doc_id: str, fmt: str = "json"):
    engine = await _get_aibrarian_engine()
    doc = await engine.get_document(c, doc_id)
    if not doc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    if fmt == "txt":
        from fastapi.responses import StreamingResponse
        return StreamingResponse(
            iter([doc.get("full_text", "")]),
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="{doc_id}.txt"'},
        )
    return doc


# --- Read-only SQL ---

@app.get("/api/nexus/{c}/sql")
async def api_aibrarian_sql(c: str, q: str = "", limit: int = 100):
    engine = await _get_aibrarian_engine()
    try:
        return await engine.execute_sql(c, q, limit)
    except PermissionError as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(e))


# =====================================================================
# APERTURE & LIBRARY COGNITION ENDPOINTS
# =====================================================================

# --- Shared state (Phase 1: delegates to Engine-owned instances) ---
_aperture_manager = None
_collection_lock_in_engine = None
_annotation_engine = None


def _get_aperture_manager():
    global _aperture_manager
    if _aperture_manager is not None:
        return _aperture_manager
    # Phase 1: use Engine-owned instance
    if _engine is not None and getattr(_engine, "aperture", None) is not None:
        _aperture_manager = _engine.aperture
        return _aperture_manager
    # Fallback: standalone
    from luna.context.aperture import ApertureManager
    _aperture_manager = ApertureManager()
    return _aperture_manager


async def _get_lock_in_engine():
    global _collection_lock_in_engine
    if _collection_lock_in_engine is not None:
        return _collection_lock_in_engine
    # Phase 1: use Engine-owned instance
    if _engine is not None and getattr(_engine, "collection_lock_in", None) is not None:
        _collection_lock_in_engine = _engine.collection_lock_in
        return _collection_lock_in_engine

    # Fallback: standalone init
    from luna.substrate.collection_lock_in import CollectionLockInEngine

    if _engine is None:
        return None

    matrix = _engine.get_actor("matrix")
    db = getattr(matrix, "_matrix", None)
    if db is None:
        return None
    mem_db = getattr(db, "db", None)
    if mem_db is None:
        return None

    _collection_lock_in_engine = CollectionLockInEngine(mem_db)
    await _collection_lock_in_engine.ensure_table()

    if _aibrarian_engine is not None:
        _aibrarian_engine.set_lock_in_engine(_collection_lock_in_engine)

    return _collection_lock_in_engine


async def _get_annotation_engine():
    global _annotation_engine
    if _annotation_engine is not None:
        return _annotation_engine
    # Phase 1: use Engine-owned instance
    if _engine is not None and getattr(_engine, "annotations", None) is not None:
        _annotation_engine = _engine.annotations
        return _annotation_engine

    # Fallback: standalone init
    from luna.substrate.collection_annotations import AnnotationEngine

    if _engine is None:
        return None

    matrix_actor = _engine.get_actor("matrix")
    matrix = getattr(matrix_actor, "_matrix", None)
    if matrix is None:
        return None
    mem_db = getattr(matrix, "db", None)
    if mem_db is None:
        return None

    lock_in = await _get_lock_in_engine()
    _annotation_engine = AnnotationEngine(mem_db, memory_matrix=matrix, lock_in_engine=lock_in)
    await _annotation_engine.ensure_table()
    return _annotation_engine


# --- Aperture Endpoints ---

@app.get("/api/aperture")
async def api_aperture_get():
    """Get current aperture state."""
    mgr = _get_aperture_manager()
    return mgr.state.to_dict()


class ApertureSetRequest(BaseModel):
    preset: Optional[str] = None
    angle: Optional[int] = None
    focus_tags: Optional[list[str]] = None
    active_project: Optional[str] = None
    active_collection_keys: Optional[list[str]] = None


@app.post("/api/aperture")
async def api_aperture_set(req: ApertureSetRequest):
    """Set aperture. Preset overrides angle."""
    from luna.context.aperture import AperturePreset
    mgr = _get_aperture_manager()

    if req.preset:
        try:
            mgr.set_preset(AperturePreset(req.preset))
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"Unknown preset: {req.preset}")
    elif req.angle is not None:
        mgr.set_angle(req.angle)

    if req.focus_tags is not None:
        mgr.set_focus_tags(req.focus_tags)
    if req.active_project is not None:
        mgr.set_active_project(req.active_project)
    if req.active_collection_keys is not None:
        mgr.set_active_collections(req.active_collection_keys)

    return mgr.state.to_dict()


@app.post("/api/aperture/reset")
async def api_aperture_reset():
    """Clear user override, revert to app default."""
    mgr = _get_aperture_manager()
    mgr.clear_override()
    return mgr.state.to_dict()


# --- Collection Lock-In Endpoints ---

@app.get("/api/collections/lock-in")
async def api_collections_lock_in():
    """Get lock-in scores for all tracked collections."""
    engine = await _get_lock_in_engine()
    if engine is None:
        return {"collections": [], "error": "Engine not ready"}

    from luna.substrate.collection_lock_in import PATTERN_FLOORS, COLLECTION_LOCK_IN_MIN
    try:
        import yaml
        from pathlib import Path as _Path
        _reg_path = _Path(__file__).parent.parent.parent / "config" / "aibrarian_registry.yaml"
        _registry = yaml.safe_load(_reg_path.read_text()) if _reg_path.exists() else {}
        _col_configs = _registry.get("collections", {})
    except Exception:
        _col_configs = {}

    records = await engine.get_all()
    result = []
    for r in records:
        pattern = _col_configs.get(r.collection_key, {}).get("ingestion_pattern", "utilitarian")
        floor = PATTERN_FLOORS.get(pattern, COLLECTION_LOCK_IN_MIN)
        near_floor = r.lock_in < (floor + 0.05)
        result.append({
            "collection_key": r.collection_key,
            "lock_in": r.lock_in,
            "state": r.state,
            "access_count": r.access_count,
            "annotation_count": r.annotation_count,
            "connected_collections": r.connected_collections,
            "entity_overlap_count": r.entity_overlap_count,
            "last_accessed_at": r.last_accessed_at,
            "pattern": pattern,
            "floor": floor,
            "near_floor": near_floor,
        })
    return {"collections": result}


@app.get("/api/collections/{key}/lock-in")
async def api_collection_lock_in_detail(key: str):
    """Get lock-in detail for a single collection."""
    engine = await _get_lock_in_engine()
    if engine is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Engine not ready")
    record = await engine.get_lock_in(key)
    if record is None:
        return {"collection_key": key, "tracked": False}
    return {
        "collection_key": record.collection_key,
        "tracked": True,
        "lock_in": record.lock_in,
        "state": record.state,
        "access_count": record.access_count,
        "annotation_count": record.annotation_count,
        "connected_collections": record.connected_collections,
        "entity_overlap_count": record.entity_overlap_count,
        "last_accessed_at": record.last_accessed_at,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


# --- Annotation Endpoints ---

class AnnotationCreateRequest(BaseModel):
    collection_key: str
    doc_id: str
    annotation_type: str  # bookmark, note, flag
    content: Optional[str] = None
    chunk_index: Optional[int] = None
    original_text_preview: str = ""


@app.post("/api/annotations")
async def api_annotation_create(req: AnnotationCreateRequest):
    """Create an annotation on a collection document."""
    from luna.substrate.collection_annotations import AnnotationType
    engine = await _get_annotation_engine()
    if engine is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Engine not ready")

    try:
        ann_type = AnnotationType(req.annotation_type)
    except ValueError:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unknown type: {req.annotation_type}")

    annotation_id = await engine.create(
        collection_key=req.collection_key,
        doc_id=req.doc_id,
        annotation_type=ann_type,
        content=req.content,
        chunk_index=req.chunk_index,
        original_text_preview=req.original_text_preview,
    )
    annotation = await engine.get(annotation_id)
    return {
        "annotation_id": annotation_id,
        "matrix_node_id": annotation.matrix_node_id if annotation else None,
    }


@app.get("/api/annotations")
async def api_annotations_list(collection: str, limit: int = 100):
    """List annotations for a collection."""
    engine = await _get_annotation_engine()
    if engine is None:
        return {"annotations": []}
    annotations = await engine.list_by_collection(collection, limit=limit)
    return {
        "annotations": [
            {
                "id": a.id,
                "collection_key": a.collection_key,
                "doc_id": a.doc_id,
                "chunk_index": a.chunk_index,
                "annotation_type": a.annotation_type,
                "content": a.content,
                "matrix_node_id": a.matrix_node_id,
                "created_at": a.created_at,
            }
            for a in annotations
        ]
    }


@app.get("/api/annotations/bridged")
async def api_annotations_bridged():
    """Get collections that have annotations creating Matrix nodes."""
    engine = await _get_annotation_engine()
    if engine is None:
        return {"bridged": []}
    return {"bridged": await engine.get_bridged_collections()}


@app.delete("/api/annotations/{annotation_id}")
async def api_annotation_delete(annotation_id: str):
    """Delete an annotation (Matrix node is preserved)."""
    engine = await _get_annotation_engine()
    if engine is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Engine not ready")
    deleted = await engine.delete(annotation_id)
    return {"deleted": deleted}


# ═══════════════════════════════════════════════════════════
# DEBUG: LAST INFERENCE SNAPSHOT
# ═══════════════════════════════════════════════════════════


@app.get("/debug/last-inference")
async def debug_last_inference():
    """
    Consolidated snapshot of the last inference for pipeline I/O diff.

    Pulls from director.get_last_system_prompt(), QA last report,
    and debug context — all in one call.
    """
    if not _engine:
        raise HTTPException(status_code=503, detail="Engine not started")

    result = {
        "query": None,
        "route": None,
        "provider": None,
        "latency_ms": None,
        "system_prompt_length": 0,
        "system_prompt_preview": "",
        "assembler": None,
        "context_items": [],
        "raw_response": None,
        "final_response": None,
        "narration_applied": False,
        "qa_passed": None,
        "qa_failures": [],
    }

    # Director prompt info
    director = _engine.get_actor("director")
    if director:
        prompt_info = director.get_last_system_prompt()
        if prompt_info.get("available"):
            result["system_prompt_length"] = prompt_info.get("length", 0)
            result["system_prompt_preview"] = prompt_info.get("preview", "")
            result["assembler"] = prompt_info.get("assembler")
            result["route"] = prompt_info.get("route_decision")

        # Get last response from director stats
        stats = director.get_stats() if hasattr(director, "get_stats") else {}
        agentic = stats.get("agentic", {})
        result["provider"] = agentic.get("last_provider") or stats.get("last_provider")

    # Context items
    try:
        context = _engine.context
        items = []
        for ring in context.rings:
            for item in context.rings[ring]:
                items.append({
                    "source": item.source.name,
                    "ring": item.ring.name,
                    "tokens": item.tokens,
                    "relevance": round(item.relevance, 3),
                })
        result["context_items"] = items
    except Exception:
        pass

    # QA last report
    if QA_AVAILABLE:
        try:
            validator = get_qa_validator()
            report = validator._last_report
            if report:
                result["query"] = report.query
                result["route"] = result["route"] or report.route
                result["provider"] = result["provider"] or report.provider_used
                result["latency_ms"] = report.latency_ms
                result["raw_response"] = getattr(report.context, "raw_response", None) if report.context else None
                result["final_response"] = getattr(report.context, "final_response", None) if report.context else None
                result["narration_applied"] = getattr(report.context, "narration_applied", False) if report.context else False
                result["qa_passed"] = report.passed
                result["qa_failures"] = [a.id for a in report.failed_assertions]
        except Exception:
            pass

    return result


# ═══════════════════════════════════════════════════════════
# QA: CHECK SINGLE ASSERTION
# ═══════════════════════════════════════════════════════════


class CheckAssertionRequest(BaseModel):
    """Request body for /qa/check-assertion."""
    assertion_id: str = Field(..., description="ID of the assertion to check")
    response_text: str = Field(..., description="Text to check against the assertion")


@app.post("/qa/check-assertion")
async def qa_check_assertion(request: CheckAssertionRequest):
    """
    Run a single assertion against provided text.

    Lightweight check — no LLM call, no pipeline execution.
    Builds a minimal InferenceContext and runs the assertion's check() method.
    """
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA system not available")

    validator = get_qa_validator()

    # Find the assertion
    target = None
    for a in validator._assertions:
        if a.id == request.assertion_id:
            target = a
            break

    if not target:
        raise HTTPException(status_code=404, detail=f"Assertion '{request.assertion_id}' not found")

    # Build minimal InferenceContext
    from datetime import datetime

    ctx = InferenceContext(
        inference_id="PLAYGROUND",
        session_id="playground",
        timestamp=datetime.now(),
        query="",
        route="PLAYGROUND",
        provider_used="playground",
        providers_tried=["playground"],
        provider_errors={},
        latency_ms=0,
        input_tokens=0,
        output_tokens=0,
        personality_injected=True,
        personality_length=0,
        system_prompt="",
        virtues_loaded=True,
        narration_applied=False,
        raw_response=request.response_text,
        narrated_response=None,
        final_response=request.response_text,
    )

    result = target.check(ctx)

    return {
        "assertion_id": result.id,
        "name": result.name,
        "passed": result.passed,
        "severity": result.severity,
        "expected": result.expected,
        "actual": result.actual,
        "details": result.details,
    }


# ═══════════════════════════════════════════════════════════
# /api/diagnostics/* — MCP diagnostic control surface
# Thin routes that delegate to existing logic so MCP tools
# get live API data instead of DB fallback.
# ═══════════════════════════════════════════════════════════


@app.get("/api/diagnostics/last-inference")
async def api_diagnostics_last_inference():
    """Full diagnostic snapshot of the last inference (for MCP tools)."""
    return await debug_last_inference()


@app.get("/api/diagnostics/pipeline")
async def api_diagnostics_pipeline():
    """Pipeline state with QA overlay (for MCP tools)."""
    result = {"nodes": {}, "source": "api"}

    if _engine:
        for actor_name in ["director", "scout", "scribe", "librarian", "matrix", "reconcile"]:
            actor = _engine.get_actor(actor_name)
            if actor:
                result["nodes"][actor_name] = {
                    "active": True,
                    "type": type(actor).__name__,
                }

    if QA_AVAILABLE:
        validator = get_qa_validator()
        result["qa_health"] = validator.get_health()
        report = validator._last_report
        if report:
            result["last_qa"] = {
                "passed": report.passed,
                "failed_count": report.failed_count,
                "top_failures": [a.name for a in report.failed_assertions][:5],
                "timestamp": report.timestamp.isoformat(),
            }
        # Build node_status map from last QA report assertions
        node_status = {}
        if report:
            assertion_node_map = {
                "P1": "director", "P2": "director", "P3": "director",
                "V1": "director", "F1": "director", "F2": "director",
                "S1": "director", "S2": "director", "S3": "director", "S4": "director", "S5": "director",
                "I1": "matrix", "I2": "matrix", "I3": "matrix",
                "I4": "scribe", "E1": "scribe", "E2": "scribe",
            }
            for a in report.assertions:
                node = assertion_node_map.get(a.id, "director")
                if node not in node_status:
                    node_status[node] = "pass"
                if not a.passed:
                    node_status[node] = "fail" if a.severity in ("critical", "high") else "warn"
        result["node_status"] = node_status

    return result


@app.get("/api/diagnostics/health")
async def api_diagnostics_health():
    """Combined health check for MCP diagnostic tools."""
    result = {"engine": _engine is not None, "source": "api"}
    if _engine:
        status = _engine.status()
        result["uptime"] = status.get("uptime_seconds", 0)
        result["state"] = status.get("state", "unknown")
    if QA_AVAILABLE:
        validator = get_qa_validator()
        result["qa"] = validator.get_health()
    return result


class PromptPreviewRequest(BaseModel):
    """Request body for /api/diagnostics/trigger/prompt-preview."""
    message: str = "Hello"
    route_override: Optional[str] = None


@app.post("/api/diagnostics/trigger/prompt-preview")
async def api_diagnostics_prompt_preview(request: PromptPreviewRequest):
    """Build assembled prompt info without calling the LLM."""
    if not _engine:
        raise HTTPException(status_code=503, detail="Engine not started")

    director = _engine.get_actor("director")
    if not director:
        raise HTTPException(status_code=503, detail="Director not available")

    prompt_info = director.get_last_system_prompt()
    return {
        "message": request.message,
        "route_override": request.route_override,
        "available": prompt_info.get("available", False),
        "length": prompt_info.get("length", 0),
        "preview": prompt_info.get("preview", ""),
        "full_prompt": prompt_info.get("full_prompt"),
        "route_decision": prompt_info.get("route_decision"),
        "assembler": prompt_info.get("assembler"),
        "source": "api",
    }


class TestInferenceRequest(BaseModel):
    """Request body for /api/diagnostics/trigger/test-inference."""
    message: str
    route_override: Optional[str] = None
    narration_enabled: Optional[bool] = None
    extra_context: Optional[str] = None


@app.post("/api/diagnostics/trigger/test-inference")
async def api_diagnostics_test_inference(request: TestInferenceRequest):
    """Run a test message through the full pipeline with optional overrides."""
    import time as _time_mod

    if not _engine:
        raise HTTPException(status_code=503, detail="Engine not started")

    start = _time_mod.time()

    # Create a future to capture the response
    response_future: asyncio.Future = asyncio.Future()

    async def on_response(text: str, data: dict) -> None:
        if not response_future.done():
            response_future.set_result((text, data))

    _engine.on_response(on_response)

    try:
        # Apply one-shot overrides to director before queuing the message
        _director = _engine.get_actor("director")
        if _director and (request.route_override or request.narration_enabled is not None or request.extra_context):
            overrides = {}
            if request.route_override:
                overrides["force_route"] = request.route_override
            if request.narration_enabled is not None:
                overrides["narration_enabled"] = request.narration_enabled
            if request.extra_context:
                overrides["extra_context"] = request.extra_context
            _director.set_next_overrides(overrides)

        await _engine.send_message(request.message, source="diagnostic")

        text, data = await asyncio.wait_for(response_future, timeout=30.0)
        elapsed = (_time_mod.time() - start) * 1000

        director = _engine.get_actor("director")
        prompt_info = director.get_last_system_prompt() if director else {}

        # QA on the latest report (fire-and-forget already ran)
        qa_passed = None
        qa_failures = 0
        if QA_AVAILABLE:
            validator = get_qa_validator()
            report = validator._last_report
            if report and report.query == request.message:
                qa_passed = report.passed
                qa_failures = report.failed_count

        return {
            "message": request.message,
            "response": text,
            "route": data.get("route_decision", "unknown"),
            "route_reason": data.get("route_reason", ""),
            "latency_ms": elapsed,
            "qa_passed": qa_passed,
            "qa_failures": qa_failures,
            "prompt_length": prompt_info.get("length", 0) if prompt_info.get("available") else 0,
            "assembler": prompt_info.get("assembler") if prompt_info.get("available") else None,
            "overrides_applied": {
                "route": request.route_override,
                "narration": request.narration_enabled,
                "extra_context": request.extra_context is not None,
            },
            "source": "api",
        }
    except asyncio.TimeoutError:
        return {
            "message": request.message,
            "response": "Timeout",
            "latency_ms": 30000,
            "qa_passed": False,
            "qa_failures": 1,
            "source": "api",
            "error": "Timed out after 30s",
        }
    finally:
        if on_response in _engine._on_response_callbacks:
            _engine._on_response_callbacks.remove(on_response)


@app.post("/api/diagnostics/trigger/qa-sweep")
async def api_diagnostics_qa_sweep():
    """Re-validate the last inference against all assertions."""
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA not available")

    validator = get_qa_validator()
    report = validator.revalidate_last()
    if report is None:
        return {"error": "No previous inference to revalidate", "source": "api"}
    return {
        "passed": report.passed,
        "failed_count": report.failed_count,
        "diagnosis": report.diagnosis,
        "assertions": [
            {"id": a.id, "name": a.name, "passed": a.passed, "actual": a.actual}
            for a in report.assertions
        ],
        "source": "api",
    }


class RevalidateRequest(BaseModel):
    """Request body for /api/diagnostics/trigger/revalidate."""
    assertion_ids: list[str]


@app.post("/api/diagnostics/trigger/revalidate")
async def api_diagnostics_revalidate(request: RevalidateRequest):
    """Re-validate specific assertions against the last inference."""
    if not QA_AVAILABLE:
        raise HTTPException(status_code=503, detail="QA not available")

    validator = get_qa_validator()
    results = validator.revalidate_assertions(request.assertion_ids)
    return {"results": results, "source": "api"}


# ═══════════════════════════════════════════════════════════
# Serve main Eclissi frontend at / (MUST be last — catch-all mount)
try:
    _eclissi_frontend = _Path("frontend/dist")
    if _eclissi_frontend.exists():
        app.mount("/", StaticFiles(directory=str(_eclissi_frontend), html=True), name="eclissi-frontend")
        logger.info(f"Eclissi frontend mounted at / from {_eclissi_frontend}")
except Exception as e:
    logger.warning(f"Eclissi frontend mount failed: {e}")


def create_app() -> FastAPI:
    """Factory function for creating the app."""
    return app
