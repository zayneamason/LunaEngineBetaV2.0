# AUDIT-API.md

**Generated:** 2026-01-30
**Agent:** API & Service Auditor
**Phase:** 1.4

---

## Summary

| Metric | Count |
|--------|-------|
| **Total Endpoints (Engine API)** | 74 |
| **SSE Endpoints** | 4 |
| **WebSocket Endpoints** | 1 |
| **MCP Tools** | 41 |
| **MCP API Proxy Endpoints** | 25 |

### API Architecture Overview

The Luna Engine exposes three distinct API layers:

1. **Engine API** (port 8000) - Main FastAPI server with 74 endpoints
2. **MCP API** (port 8742) - Thin proxy layer for Claude Desktop (25 endpoints)
3. **MCP Server** (FastMCP stdio) - Tool definitions for Claude Desktop (41 tools)

```
Claude Desktop --> MCP Server (FastMCP) --> MCP API (8742) --> Engine API (8000) --> Luna Engine
                       |
                       +---> Direct filesystem access (sandboxed)
```

---

## Endpoint Inventory

### Core Endpoints

| Method | Path | Description | Response Model |
|--------|------|-------------|----------------|
| GET | `/health` | Simple health check | `dict` |
| GET | `/status` | Engine status and metrics | `StatusResponse` |
| POST | `/message` | Send message, get sync response | `MessageResponse` |
| GET | `/history` | Get conversation history | `HistoryResponse` |
| GET | `/consciousness` | Get consciousness state | `ConsciousnessResponse` |
| POST | `/abort` | Abort current generation | `dict` |
| POST | `/interrupt` | Interrupt agentic processing | `dict` |

### Streaming Endpoints (SSE)

| Method | Path | Description | Event Types |
|--------|------|-------------|-------------|
| POST | `/stream` | Stream Luna response | `token`, `done`, `error` |
| POST | `/persona/stream` | Context-first streaming | `context`, `token`, `done`, `error` (data-only format) |
| GET | `/thoughts` | Stream internal thought process | `phase`, `thought`, `step`, `status`, `ping` |
| GET | `/voice/stream` | Voice status updates | `status`, `transcription`, `response`, `ping` |

### WebSocket Endpoints

| Path | Description | Message Format |
|------|-------------|----------------|
| `/ws/orb` | Orb state streaming | JSON: `{animation, color, brightness, source, timestamp}` |

### Ring Buffer API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ring/status` | Get ring buffer status |
| POST | `/api/ring/config` | Configure ring buffer size (2-20 turns) |
| POST | `/api/ring/clear` | Clear conversation memory |

### Memory Endpoints

| Method | Path | Description | Response Model |
|--------|------|-------------|----------------|
| POST | `/memory/nodes` | Create memory node | `NodeResponse` |
| GET | `/memory/nodes/{node_id}` | Get node by ID | `NodeResponse` |
| GET | `/memory/nodes` | List nodes with filtering | `list[NodeResponse]` |
| POST | `/memory/nodes/{node_id}/access` | Record node access | `dict` |
| POST | `/memory/nodes/{node_id}/reinforce` | Reinforce node (prevent pruning) | `dict` |
| GET | `/memory/stats` | Get memory statistics | `MemoryStatsResponse` |
| POST | `/memory/search` | Search memory matrix | `MemorySearchResponse` |
| POST | `/memory/smart-fetch` | Intelligent context fetch with budget | `SmartFetchResponse` |
| POST | `/memory/add` | Add memory node (MCP alias) | `MemoryAddResponse` |
| POST | `/memory/flush` | Flush pending operations | `dict` |
| POST | `/memory/add-edge` | Add relationship between nodes | `AddEdgeResponse` |
| POST | `/memory/node-context` | Get context around node | `NodeContextResponse` |
| POST | `/memory/trace` | Trace dependencies (spreading activation) | `TraceResponse` |

### Extraction Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/extraction/trigger` | Trigger memory extraction |
| POST | `/extraction/prune` | Synaptic pruning |
| GET | `/extraction/stats` | Extraction statistics |
| GET | `/extraction/history` | Recent extraction history |

### Hub (Conversation History) Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/hub/session/create` | Create new session |
| POST | `/hub/session/end` | End session |
| GET | `/hub/session/active` | Get active session |
| POST | `/hub/turn/add` | Add conversation turn |
| GET | `/hub/active_window` | Get active window turns |
| GET | `/hub/active_token_count` | Get token count |
| POST | `/hub/tier/rotate` | Rotate turn to new tier |
| GET | `/hub/tier/oldest_active` | Get oldest active turn |
| POST | `/hub/search` | Search conversation history |
| GET | `/hub/stats` | History manager stats |

### Voice Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/voice/start` | Start voice system |
| POST | `/voice/stop` | Stop voice system |
| GET | `/voice/status` | Get voice status |
| POST | `/voice/listen/start` | Start recording (push-to-talk) |
| POST | `/voice/listen/stop` | Stop recording and process |
| POST | `/voice/speak` | Speak text via TTS |
| GET | `/voice/stream` | Stream voice events (SSE) |

### Tuning Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/tuning/params` | List tunable parameters |
| GET | `/tuning/params/{name}` | Get parameter details |
| POST | `/tuning/params/{name}` | Set parameter value |
| POST | `/tuning/param-reset/{name}` | Reset to default |
| POST | `/tuning/session/new` | Start tuning session |
| GET | `/tuning/session` | Get current session |
| POST | `/tuning/session/end` | End session |
| POST | `/tuning/eval` | Run evaluation |
| GET | `/tuning/compare` | Compare iterations |
| GET | `/tuning/best` | Get best iteration |
| POST | `/tuning/apply-best` | Apply best params |
| GET | `/tuning/sessions` | List sessions |

### Cluster Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/clusters/stats` | Cluster statistics |
| GET | `/clusters/list` | List all clusters |
| GET | `/clusters/{cluster_id}` | Get cluster details |
| POST | `/constellation/assemble` | Assemble memory constellation |

### Debug Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/debug/conversation-cache` | View conversation cache |
| GET | `/debug/personality` | View personality patches |
| GET | `/debug/context` | View context window |

### Slash Command Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/slash/health` | Health check slash command |
| GET | `/slash/find-person/{name}` | Find person in memory |
| GET | `/slash/stats` | Memory statistics |
| GET | `/slash/search/{query}` | Search memory |
| GET | `/slash/recent` | Recent memories |
| GET | `/slash/extraction` | Extraction status |
| GET | `/slash/help` | Help information |
| POST | `/slash/restart-backend` | Restart backend |
| GET | `/slash/voice-tuning` | Voice tuning status |
| POST | `/slash/voice-tuning` | Update voice tuning |
| GET | `/slash/orb-settings` | Orb settings |
| POST | `/slash/orb-settings` | Update orb settings |
| GET | `/slash/performance` | Performance state |
| GET | `/slash/emotion/{emotion_name}` | Set emotion preset |
| POST | `/slash/reset-performance` | Reset performance state |
| GET | `/slash/llm` | LLM provider status |
| GET | `/slash/llm-switch/{provider_name}` | Switch LLM provider |
| GET | `/slash/vk` | Voight-Kampff test |
| GET | `/slash/voight-kampff` | Voight-Kampff test (alias) |

### LLM Provider Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/llm/providers` | List available providers |
| GET | `/llm/current` | Get current provider |
| POST | `/llm/provider` | Switch provider |

### System Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/system/relaunch` | Trigger system relaunch |
| POST | `/state/set-app-context` | Set application context |

---

## Request/Response Schemas

### Core Message Types

```python
class MessageRequest(BaseModel):
    message: str  # min_length=1, max_length=10000
    timeout: float = 30.0  # ge=1.0, le=120.0
    stream: bool = False

class MessageResponse(BaseModel):
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: float
    delegated: bool = False
    local: bool = False
    fallback: bool = False
```

### Status Response

```python
class StatusResponse(BaseModel):
    state: str
    uptime_seconds: float
    cognitive_ticks: int
    events_processed: int
    messages_generated: int
    actors: list[str]
    buffer_size: int
    current_turn: int = 0
    context: Optional[dict] = None
    agentic: Optional[AgenticStats] = None
```

### Memory Node Types

```python
class NodeCreateRequest(BaseModel):
    node_type: str  # FACT, DECISION, PROBLEM, ACTION, INSIGHT, etc.
    content: str  # min_length=1
    source: Optional[str] = None
    confidence: float = 1.0  # 0.0-1.0
    importance: float = 0.5  # 0.0-1.0

class NodeResponse(BaseModel):
    id: str
    node_type: str
    content: str
    source: Optional[str]
    confidence: float
    importance: float
    access_count: int
    reinforcement_count: int
    lock_in: float
    lock_in_state: str  # drifting, fluid, settled
    created_at: str
```

### Search Types

```python
class MemorySearchRequest(BaseModel):
    query: str
    limit: int = 10
    search_type: str = "hybrid"  # keyword, semantic, hybrid

class SmartFetchRequest(BaseModel):
    query: str
    budget_preset: str = "balanced"  # minimal (1800), balanced (3800), rich (7200)
```

---

## SSE/WebSocket Flows

### `/stream` - Token Streaming

```
Client --> POST /stream {message, timeout}
Server --> SSE:
  event: token
  data: {"text": "chunk"}

  event: token
  data: {"text": " of"}

  event: done
  data: {"model": "...", "input_tokens": X, "output_tokens": Y}
```

### `/persona/stream` - Context-First Streaming

```
Client --> POST /persona/stream {message, timeout}
Server --> SSE (data-only format):
  data: {"type": "context", "memory": [...], "state": {...}}
  data: {"type": "token", "text": "chunk"}
  data: {"type": "done", "response": "full text", "metadata": {...}}
```

### `/thoughts` - Thought Stream

```
Client --> GET /thoughts
Server --> SSE:
  event: status
  data: {"connected": true, "is_processing": false}

  event: thought
  data: {"type": "thought", "message": "[OBSERVE] Gathering context..."}

  event: ping
  data: {"is_processing": false, "pending": 0}
```

### `/ws/orb` - Orb State WebSocket

```
Client --> WebSocket /ws/orb
Server --> JSON:
  {
    "animation": "pulse",
    "color": "#a78bfa",
    "brightness": 1.0,
    "source": "gesture",
    "timestamp": "2025-01-27T12:00:00"
  }
```

---

## Request Flow Trace

### Standard Message Flow

```
1. Client sends POST /message {message: "Hello"}
2. FastAPI validates MessageRequest
3. Engine checks readiness (_engine is not None)
4. Response future created, callback registered
5. _engine.send_message() called
6. Engine queues InputEvent to buffer
7. Cognitive tick processes event
8. Director actor receives generate message
9. Router analyzes message (DIRECT/SIMPLE_PLAN/FULL_PLAN)
10. Director calls local Qwen or delegates to Claude
11. Response callback fires with text + metadata
12. Future resolves, MessageResponse returned
```

### Streaming Flow

```
1. Client sends POST /stream or /persona/stream
2. StreamingResponse created with async generator
3. Director.on_stream() callback registered
4. Message sent to director mailbox
5. Director generates tokens, calls stream callback per token
6. Generator yields SSE events as tokens arrive
7. on_complete callback signals end
8. Generator yields done event
9. Cleanup: remove callbacks
```

### Memory Search Flow

```
1. Client sends POST /memory/search {query: "foo"}
2. Engine validates readiness
3. Matrix actor retrieved: _engine.get_actor("matrix")
4. Memory instance accessed via getattr chain
5. Search type determines method:
   - "hybrid" -> memory.hybrid_search()
   - "semantic" -> memory.semantic_search()
   - "keyword" -> memory.fts5_search()
6. Results formatted to MemorySearchResponse
```

---

## Error Handling Coverage

### Endpoints WITH Error Handling

| Endpoint | Error Types Handled |
|----------|---------------------|
| `/message` | 503 (engine not ready), 504 (timeout), callback cleanup |
| `/stream` | SSE error events, timeout handling, callback cleanup |
| `/persona/stream` | Context errors, timeout, callback cleanup |
| `/memory/nodes` | 503, 500 (create failure), 404 (not found) |
| `/memory/search` | Silent failure (returns empty results) |
| `/extraction/trigger` | 503, 500 (extraction failure) |
| `/voice/*` | 400 (not active), 500 (failure), 503 (unavailable) |

### Endpoints with MISSING/WEAK Error Handling

| Endpoint | Issue |
|----------|-------|
| `/memory/smart-fetch` | Returns empty on error instead of raising |
| `/memory/search` | Returns empty results on error (silent failure) |
| `/hub/*` | Some return None instead of proper 404 |
| `/tuning/*` | Missing validation on some parameters |
| `/slash/*` | Inconsistent error response formats |
| `/clusters/*` | Limited exception handling |

### Common Error Response Format

```python
HTTPException(status_code=503, detail="Engine not ready")
HTTPException(status_code=504, detail=f"Response timeout after {timeout}s")
HTTPException(status_code=404, detail="Node not found")
HTTPException(status_code=500, detail=str(e))
```

---

## Security Features

### Current Security Measures

1. **CORS Configuration**
   ```python
   allow_origins=["http://localhost:5173", "http://localhost:5174",
                  "http://localhost:5175", "http://localhost:3000",
                  "http://127.0.0.1:5173", "http://127.0.0.1:5174",
                  "http://127.0.0.1:5175"]
   allow_credentials=True
   allow_methods=["*"]
   allow_headers=["*"]
   ```

2. **Input Validation**
   - Pydantic models with constraints (min_length, max_length, ge, le)
   - MessageRequest.message: 1-10000 chars
   - MessageRequest.timeout: 1.0-120.0 seconds
   - RingBufferConfig.max_turns: 2-20

3. **Filesystem Sandboxing (MCP)**
   - MCP tools use relative paths from project root
   - `LUNA_BASE_PATH` environment variable controls sandbox

### Missing Security Features

| Feature | Status | Risk |
|---------|--------|------|
| **Authentication** | Not implemented | Any client can access all endpoints |
| **Rate Limiting** | Not implemented | DoS vulnerability |
| **API Keys** | Not implemented | No access control |
| **Request Logging** | Partial (logger.info) | Audit trail gaps |
| **Input Sanitization** | Basic Pydantic only | Potential injection |
| **HTTPS** | Not enforced | Plaintext transmission |

### Recommendations

1. Add API key authentication for production
2. Implement rate limiting (FastAPI middleware)
3. Add request/response logging middleware
4. Enforce HTTPS in production
5. Add input sanitization for SQL-like operations
6. Review CORS configuration for production

---

## MCP Integration

### MCP Server (FastMCP)

**Location:** `/src/luna_mcp/server.py`
**Protocol:** stdio (for Claude Desktop)
**Name:** `Luna-Hub-MCP-V1`

### MCP Tool Categories

#### Filesystem Tools (3)
| Tool | Description |
|------|-------------|
| `luna_read` | Read file from project |
| `luna_write` | Write file to project |
| `luna_list` | List directory contents |

#### Memory Tools (9)
| Tool | Description |
|------|-------------|
| `luna_smart_fetch` | Intelligent context fetch with budget |
| `memory_matrix_search` | Direct graph search |
| `memory_matrix_add_node` | Add memory node |
| `memory_matrix_add_edge` | Add relationship |
| `memory_matrix_get_context` | Get node context |
| `memory_matrix_trace` | Trace dependencies |
| `luna_save_memory` | Save structured memory |
| `luna_start_session` | Start recording session |
| `luna_record_turn` | Record conversation turn |

#### Session Tools (5)
| Tool | Description |
|------|-------------|
| `luna_end_session` | End session, trigger extraction |
| `luna_get_current_session` | Get active session ID |
| `luna_auto_session_status` | Auto-session status |
| `luna_flush_session` | Flush and extract |
| `luna_detect_context` | Process message through pipeline |

#### State Tools (2)
| Tool | Description |
|------|-------------|
| `luna_get_state` | Get Luna state |
| `luna_set_app_context` | Set application context |

#### Git Tools (2)
| Tool | Description |
|------|-------------|
| `luna_git_sync` | Sync changes with Git |
| `luna_git_status` | Get Git status |

#### Persona Forge Tools (20)
| Category | Tools |
|----------|-------|
| Dataset | `forge_load`, `forge_assay`, `forge_gaps`, `forge_mint`, `forge_export`, `forge_status` |
| Ingestion | `forge_list_sources`, `forge_read_raw`, `forge_add_example`, `forge_add_batch`, `forge_search`, `forge_read_matrix`, `forge_read_turns` |
| Character | `character_list`, `character_load`, `character_modulate`, `character_save`, `character_show` |
| Voight-Kampff | `vk_run`, `vk_list`, `vk_probes` |

### MCP API (Proxy Layer)

**Location:** `/src/luna_mcp/api.py`
**Port:** 8742
**Purpose:** Proxy requests from MCP tools to Engine API (port 8000)

### Auto-Session Recording

The MCP layer implements automatic session recording:
- Sessions start automatically on first tool activity
- Turns are buffered and flushed every 4 turns
- Sessions end after 5 minutes of inactivity
- Extraction is triggered on session end

```python
# Configuration
_inactivity_timeout: int = 300  # 5 minutes
_buffer_flush_threshold: int = 4  # Flush after 4 turns
```

---

## Service Layer Analysis

### Services Directory: `/src/luna/services/`

| Module | Description |
|--------|-------------|
| `orb_state.py` | Orb visual state management |
| `performance_state.py` | Voice + orb coordination |
| `performance_orchestrator.py` | Gesture -> performance mapping |
| `clustering_service.py` | Memory clustering |
| `lockin_service.py` | Lock-in coefficient management |

### OrbStateManager

Manages orb visual state with:
- Gesture detection from text patterns
- System event handling
- Priority-based state resolution
- WebSocket broadcasting

```python
class OrbAnimation(Enum):
    IDLE, PULSE, PULSE_FAST, SPIN, SPIN_FAST, FLICKER,
    WOBBLE, DRIFT, ORBIT, GLOW, SPLIT,
    PROCESSING, LISTENING, SPEAKING, MEMORY_SEARCH,
    ERROR, DISCONNECTED

class StatePriority(Enum):
    DEFAULT = 0
    IDLE = 1
    GESTURE = 2
    SYSTEM = 3
    ERROR = 4
```

### PerformanceOrchestrator

Coordinates voice + orb from gestures:
- Parses gestures from text
- Maps to emotion presets
- Emits coordinated voice + orb parameters
- Handles manual overrides from UI

```python
class EmotionPreset(Enum):
    NEUTRAL, EXCITED, THOUGHTFUL, WARM,
    PLAYFUL, CONCERNED, CURIOUS
```

---

## Appendix: Full Endpoint Count

| Category | Count |
|----------|-------|
| Core | 7 |
| Streaming (SSE) | 4 |
| WebSocket | 1 |
| Ring Buffer | 3 |
| Memory | 13 |
| Extraction | 4 |
| Hub | 10 |
| Voice | 7 |
| Tuning | 12 |
| Clusters | 4 |
| Debug | 3 |
| Slash Commands | 19 |
| LLM Provider | 3 |
| System | 2 |
| **Total Engine API** | **74** |
| MCP API Proxy | 25 |
| MCP Tools | 41 |
