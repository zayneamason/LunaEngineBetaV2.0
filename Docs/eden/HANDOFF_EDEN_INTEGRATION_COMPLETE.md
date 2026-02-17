# HANDOFF: Eden.art Integration — Complete Reference

**Date:** 2026-02-11
**Scope:** Full Eden.art integration into Luna Engine (Phases 1-4)
**Status:** ALL PHASES COMPLETE — 78 tests passing, 8 live API validations

---

## OVERVIEW

Eden.art is a creative AI platform providing image/video generation, autonomous agents, and custom model training. It sits as the Service Layer in Luna's three-tier architecture:

```
Luna Engine  -->  Eclissi (Memory/Identity)  -->  Eden.art (Creative Generation)
```

The integration uses an **adapter over SDK** design. Eden's official SDK (`@edenlabs/eden-sdk`) is JavaScript-only and in beta, so we built a Python async HTTP adapter using `httpx` + `pydantic`. This gives us full control over retry/backoff, no dependency on SDK stability, and the ability to add KOZMO-specific extensions later.

What was built across 4 phases:
1. **Core Adapter** — Pydantic types, config, HTTP client, high-level adapter
2. **MCP Exposure** — 5 tools available to Claude Desktop via FastMCP
3. **Guardrails** — Policy engine with kill switch, budget caps, approval gates, audit trail
4. **Router Integration** — Creative query detection forces Eden tool routing

---

## FILE MAP

| File | Action | Phase | Purpose |
|------|--------|-------|---------|
| `src/luna/services/eden/__init__.py` | CREATED | 1 | Package exports |
| `src/luna/services/eden/types.py` | CREATED | 1 | Pydantic models for Eden API |
| `src/luna/services/eden/config.py` | CREATED | 1 | Config loading (eden.json + env vars) |
| `src/luna/services/eden/client.py` | CREATED | 1 | Async HTTP client with retry |
| `src/luna/services/eden/adapter.py` | CREATED | 1 | High-level adapter (create_image, etc.) |
| `src/luna/services/eden/policy.py` | CREATED | 3 | Policy guardrails (kill switch, budget) |
| `src/luna/tools/eden_tools.py` | CREATED | 1.5 | 5 engine tools with policy enforcement |
| `src/luna/actors/eden_bridge.py` | CREATED | 1.5 | Session-to-memory bridge actor |
| `src/luna_mcp/tools/eden.py` | CREATED | 2 | MCP wrapper with lazy-init adapter |
| `config/eden.json` | CREATED | 1 | Connection config + policy section |
| `src/luna/engine.py` | MODIFIED | 1.5 | `_init_eden()`, shutdown cleanup |
| `src/luna/agentic/loop.py` | MODIFIED | 1.5 | Eden tool registration in loop |
| `src/luna/agentic/router.py` | MODIFIED | 3 | CREATIVE_PATTERNS, Eden TOOL_PATTERNS |
| `src/luna_mcp/server.py` | MODIFIED | 2 | 5 MCP tool definitions |
| `src/luna/tools/__init__.py` | MODIFIED | 1.5 | Eden tool exports with graceful fallback |
| `tests/test_eden_adapter.py` | CREATED | 1 | Types, config, adapter tests (mocked HTTP) |
| `tests/test_eden_tools.py` | CREATED | 1.5 | Tool registration, execution, consciousness |
| `tests/test_eden_mcp.py` | CREATED | 2 | MCP wrapper, lazy init, error handling |
| `tests/test_eden_policy.py` | CREATED | 3 | Policy, budget, approval, enforcement, router |

---

## ARCHITECTURE

```
                      +--------------------------+
                      |      Claude Desktop      |
                      |  (via MCP / FastMCP)     |
                      +------------+-------------+
                                   |
                      +------------v-------------+
                      | luna_mcp/tools/eden.py   |
                      | (lazy-init singleton)    |
                      +------------+-------------+
                                   |
    +------------------------------v------------------------------+
    |                    Luna Engine (engine.py)                   |
    |                                                              |
    |  eden_tools.py   <-->  EdenPolicy   <-->  QueryRouter       |
    |  (5 tools)             (guardrails)       (creative detect)  |
    |       |                                                      |
    |  eden_bridge.py                                              |
    |  (memory actor)                                              |
    +------------------------------+-------------------------------+
                                   |
                      +------------v-------------+
                      | services/eden/adapter.py |
                      | (async context manager)  |
                      +------------+-------------+
                                   |
                      +------------v-------------+
                      | services/eden/client.py  |
                      | (httpx + retry/backoff)  |
                      +------------+-------------+
                                   |
                          https://api.eden.art
```

---

## PHASE 1: Core Adapter (`src/luna/services/eden/`)

### types.py

All Pydantic models for the Eden REST API. Uses `Field(alias=...)` with `model_config = {"populate_by_name": True}` because Eden's API returns camelCase JSON.

**Enums:**
- `TaskStatus` — `PENDING`, `PROCESSING`, `RUNNING`, `COMPLETED`, `FAILED`
- `MediaType` — `IMAGE`, `VIDEO`
- `MessageRole` — `USER`, `ASSISTANT`, `SYSTEM`, `EDEN`

**Core models:**
- `Task` — id (alias `_id`), status, result (Optional list), error. Properties: `is_complete`, `is_failed`, `is_terminal`, `first_output_url`
- `Agent` — id, name, description, persona, greeting, models (list of LoRA), tools (dict), public
- `Session` — id, agent_ids, messages (list of SessionMessage), budget, status
- `SessionMessage` — id, role, content, tool_calls (Optional list), attachments (Optional list)
- `Creation` / `CreationsPage` — gallery objects with pagination cursor

**Live-validation fixes applied after Phase 4 testing:**
- `RUNNING` added to `TaskStatus` (not in Eden docs, discovered live)
- `Task.result` changed to `Optional[list[TaskResult]]` (can be null, not empty list)
- `SessionMessage.tool_calls` and `.attachments` changed to `Optional[list]` (can be null)

### config.py

`EdenConfig` is a Pydantic `BaseModel` with these fields:

```python
api_base: str = "https://api.eden.art"
api_key: Optional[str] = None
default_agent_id: Optional[str] = None
poll_interval_seconds: float = 3.0
poll_max_attempts: int = 60          # 3 min max wait
poll_backoff_factor: float = 1.2
default_manna_budget: float = 100.0
default_turn_budget: int = 50
timeout_seconds: float = 30.0
max_retries: int = 3
```

**Loading chain:** `EdenConfig.load(config_dir)` reads `config/eden.json` first, then applies env var overrides (`EDEN_API_KEY`, `EDEN_API_BASE`, `EDEN_AGENT_ID`). Env vars take highest priority.

**Property:** `is_configured` returns `True` when `api_key is not None`.

### client.py

`EdenClient` is a low-level async HTTP client wrapping `httpx.AsyncClient`.

```python
async with EdenClient(config) as client:
    data = await client.get("/v2/agents")
    data = await client.post("/v2/tasks/create", json=payload)
```

- Auth via `X-Api-Key` header
- Retry on 429 (rate limit) with increasing backoff
- Retry on 5xx server errors
- Retry on `TimeoutException` and `ConnectError`
- `EdenAPIError(status_code, message, response_body)` for non-success responses

### adapter.py

`EdenAdapter` is the high-level interface. Async context manager pattern.

**Key methods:**

```python
# Task lifecycle
async def create_task(prompt, media_type, tool, public, extra_args) -> Task
async def poll_task(task_id) -> Task
async def wait_for_task(task_id, poll_interval, max_attempts) -> Task

# Convenience (create + wait)
async def create_image(prompt, wait=True, **kwargs) -> Task
async def create_video(prompt, wait=True, **kwargs) -> Task

# Agents
async def list_agents() -> list[Agent]
async def get_agent(agent_id) -> Optional[Agent]

# Sessions
async def create_session(agent_ids, content, title, manna_budget) -> str
async def send_message(session_id, content, attachments) -> str
async def get_session(session_id) -> Optional[Session]

# Gallery
async def get_creations(limit, cursor, media_type) -> CreationsPage

# Health
async def health_check() -> bool
```

**Important:** `create_task()` puts `width`/`height` into `extra_args` dict, not top-level params. The `args` dict goes into `TaskCreateRequest.args`. For video, `args["output"] = "video"` is set automatically.

---

## PHASE 1.5: Engine Wiring

### eden_tools.py (`src/luna/tools/eden_tools.py`)

5 tools registered as `Tool` dataclass instances:

| Tool Name | requires_confirmation | timeout_seconds | Function |
|-----------|----------------------|-----------------|----------|
| `eden_create_image` | True | 180 | `eden_create_image(prompt, wait, tool, public)` |
| `eden_create_video` | True | 300 | `eden_create_video(prompt, wait, tool, public)` |
| `eden_chat` | True | 60 | `eden_chat(agent_id, message, session_id)` |
| `eden_list_agents` | False | 30 | `eden_list_agents()` |
| `eden_health` | False | 15 | `eden_health()` |

**Global reference pattern** (matches memory_tools.py):

```python
_eden_adapter = None   # Set by set_eden_adapter()
_engine = None         # For consciousness updates
_eden_policy = None    # Loaded during set_eden_adapter()
```

`set_eden_adapter(adapter, engine=None)` — called during engine boot. Sets all three globals. Policy is loaded from `eden.json` at this point.

**Policy enforcement chain** (every generation/chat tool call):
1. `_check_policy(tool_name)` — returns error string if blocked (disabled or budget exceeded), None if allowed
2. Execute the adapter call
3. `_record_usage(tool_name)` — increments budget counters
4. `_audit_eden_call(tool_name, params, result)` — sends `eden_audit` message to `eden_bridge` actor

**Consciousness hooks:**
- `_update_consciousness_on_success(action)` — coherence += 0.05, focus on `eden_{action}`
- `_update_consciousness_on_error(error)` — coherence -= 0.15, focus on `eden_error`

**Memory bridge:** `_bridge_eden_message()` sends `eden_session_message` to `eden_bridge` actor, or falls back to `engine.record_conversation_turn()`.

**Helper:** `get_eden_policy_status()` returns a dict with loaded state, enabled flag, budget remaining.

### eden_bridge.py (`src/luna/actors/eden_bridge.py`)

`EdenBridgeActor(Actor)` — name is `"eden_bridge"`.

Handles two message types:
- `"eden_session_message"` — stores exchange as DECISION + INSIGHT nodes in memory, linked with `clarifies` relationship (strength 0.8)
- `"eden_session_closed"` — removes session from `_active_sessions` tracking dict

`is_ready` checks: engine exists AND matrix actor exists AND matrix actor is ready.

`snapshot()` returns name, mailbox_size, and active_sessions dict.

### Engine integration (`engine.py`)

Three modifications:

1. **`__init__`:** `self._eden_adapter: Optional[Any] = None`

2. **`_boot()` (line ~309):** Calls `await self._init_eden()` during engine boot sequence.

3. **`_init_eden()`:** Checks `EDEN_API_KEY` env var. If set and not placeholder:
   - Loads `EdenConfig.load()`
   - Creates `EdenAdapter(config)` and enters context manager
   - Registers `EdenBridgeActor` if not already present
   - Calls `set_eden_adapter(adapter, engine=self)`
   - Non-fatal on failure (catches all exceptions, logs warning)

4. **Shutdown (line ~1364):** Calls `_eden_adapter.__aexit__()` if adapter is active.

### Tool registration (`loop.py`)

In the agentic loop initialization (line ~304):

```python
from luna.tools.eden_tools import register_eden_tools, get_eden_adapter
if get_eden_adapter() is not None:
    register_eden_tools(self.tool_registry)
```

Only registers Eden tools if the adapter was successfully initialized.

### tools/__init__.py

Exports Eden tools with graceful fallback. If `eden_tools` module import fails, provides no-op stubs:

```python
try:
    from .eden_tools import (
        eden_create_image_tool, eden_create_video_tool, eden_chat_tool,
        eden_list_agents_tool, eden_health_tool, register_eden_tools,
        set_eden_adapter, get_eden_adapter, get_eden_policy,
        get_eden_policy_status, ALL_EDEN_TOOLS,
    )
    EDEN_TOOLS_AVAILABLE = True
except:
    EDEN_TOOLS_AVAILABLE = False
    # ... no-op stubs
```

---

## PHASE 2: MCP Exposure (`src/luna_mcp/tools/eden.py`)

Exposes 5 tools to Claude Desktop via FastMCP. Uses a **lazy-init adapter singleton** pattern independent of the engine:

```python
_adapter = None
_adapter_initialized = False

async def _get_adapter():
    """Lazy-init the Eden adapter singleton."""
    # Checks EDEN_API_KEY env var
    # Creates EdenAdapter + enters context manager
    # Returns None if no key or init fails
```

This means the MCP tools work standalone (without the full Luna Engine running) as long as `EDEN_API_KEY` is set.

**5 MCP tools registered via `@mcp.tool()` in `server.py`:**

| MCP Tool | Signature | Delegates To |
|----------|-----------|-------------|
| `eden_create_image` | `(prompt, width=None, height=None)` | `eden.eden_create_image()` |
| `eden_create_video` | `(prompt)` | `eden.eden_create_video()` |
| `eden_chat` | `(message, agent_id=None, session_id=None)` | `eden.eden_chat()` |
| `eden_list_agents` | `()` | `eden.eden_list_agents()` |
| `eden_health` | `()` | `eden.eden_health()` |

All return JSON strings. The MCP layer handles `width`/`height` by passing them as `extra_args` to the adapter.

**Note:** The MCP eden tools do NOT enforce the EdenPolicy. Policy enforcement lives in the engine-side `eden_tools.py`. The MCP tools are a direct bridge to the adapter for Claude Desktop use cases.

---

## PHASE 3: Guardrails & Director Integration

### policy.py (`src/luna/services/eden/policy.py`)

`EdenPolicy` is a `@dataclass` (not Pydantic — deliberate choice for mutable runtime counters).

**Fields:**

```python
enabled: bool = True                              # Master kill switch
auto_approve: list[str] = ["eden_health", "eden_list_agents"]
require_approval: list[str] = ["eden_create_image", "eden_create_video", "eden_chat"]
max_generations_per_session: int = 20             # Image + video share this budget
max_chats_per_session: int = 50
audit_to_memory: bool = True
_generation_count: int = 0                        # Runtime only, not persisted
_chat_count: int = 0                              # Runtime only, not persisted
```

**Key methods:**

```python
def requires_approval(tool_name: str) -> bool
    # disabled -> always True
    # in auto_approve -> False
    # in require_approval -> True
    # unknown -> True (safe default)

def check_budget(tool_name: str) -> bool
    # disabled -> always False
    # create_image/create_video -> check _generation_count < max
    # eden_chat -> check _chat_count < max
    # other tools -> always True (no budget)

def record_usage(tool_name: str) -> None
def reset_session() -> None
```

**Properties:** `generation_budget_remaining`, `chat_budget_remaining`

**Persistence:** `EdenPolicy.load(config_path)` reads the `"policy"` key from `config/eden.json`. `policy.save(config_path)` writes it back. Falls back to defaults if no file or no policy section.

### Control Surfaces

Four control surfaces for the user:

1. **Kill switch:** `policy.enabled = False` blocks ALL generation and chat tools. Health and list_agents still work through the adapter but require approval per policy.

2. **Budget limits:** `max_generations_per_session` caps image + video combined. `max_chats_per_session` caps chat turns independently. Reset via `policy.reset_session()`.

3. **Approval gates:** Tools in `require_approval` list have `requires_confirmation=True` on their Tool definitions. The agentic loop asks the user before executing.

4. **Audit trail:** When `audit_to_memory=True`, every Eden call sends an `eden_audit` message to the `eden_bridge` actor, which can store it in Luna's memory graph.

### Router Integration (`router.py`)

**CREATIVE_PATTERNS** (5 regex patterns):
```python
r"\b(generate|create|make|draw|paint|render)\b.*\b(image|picture|photo|art|illustration|portrait|video|animation)\b"
r"\b(image|picture|video|portrait)\b.*\bof\b"
r"\beden\b"
r"\b(visualize|illustrate|depict)\b"
r"\b(paint|draw)\b.*\b(a|an|the|me)\b"
```

**TOOL_PATTERNS** for Eden (3 tool entries):
- `eden_create_image` — matches "generate/create/make/draw/paint ... image/picture/photo", or "image/picture ... of/for/about", or "eden ... image/create"
- `eden_create_video` — matches "generate/create/make ... video/animation/clip/timelapse", or "video/animation ... of/for/about", or "eden ... video"
- `eden_chat` — matches "talk/chat/speak/converse ... eden/agent", or "eden agent", or "creative agent"

**Path forcing:** When `creative_request` signal is detected, the router forces `SIMPLE_PLAN` execution path regardless of complexity score. This ensures creative queries go through the tool pipeline rather than getting a direct LLM response.

```python
if "creative_request" in signals:
    return RoutingDecision(
        path=ExecutionPath.SIMPLE_PLAN,
        complexity=max(complexity, self._memory_min_complexity),
        reason="Creative request routes through Eden tools",
        ...
    )
```

---

## PHASE 4: Live Validation Results

8 live API tests passed during validation:

1. **Kill switch blocks** — `policy.enabled=False` returns `{"policy_blocked": True}`
2. **Zero budget blocks** — `max_generations_per_session=0` blocks generation
3. **Health check works despite policy** — health is auto-approved, not affected by kill switch at adapter level
4. **List agents works despite policy** — also auto-approved
5. **Normal policy allows live generation** — with default policy, `create_image` succeeds and returns a real task ID
6. **Budget exhaustion blocks after limit** — after N generations, budget check fails
7. **Chat session creation** — live session created with Eden agent
8. **Full task lifecycle** — create -> poll -> RUNNING -> poll -> COMPLETED with output URL

Router validation: 12/12 creative detection queries correctly identified.

---

## CONFIG REFERENCE

`config/eden.json`:

```json
{
  "api_base": "https://api.eden.art",
  "default_agent_id": null,
  "poll_interval_seconds": 3.0,
  "poll_max_attempts": 60,
  "default_manna_budget": 100.0,
  "default_turn_budget": 50,
  "timeout_seconds": 30.0,
  "max_retries": 3,
  "policy": {
    "enabled": true,
    "auto_approve": ["eden_health", "eden_list_agents"],
    "require_approval": ["eden_create_image", "eden_create_video", "eden_chat"],
    "max_generations_per_session": 20,
    "max_chats_per_session": 50,
    "audit_to_memory": true
  }
}
```

Environment variables (override config file values):
- `EDEN_API_KEY` — required for any Eden functionality
- `EDEN_API_BASE` — override API base URL
- `EDEN_AGENT_ID` — default agent ID for chat

---

## TEST INVENTORY

| File | Count | What it covers |
|------|-------|----------------|
| `tests/test_eden_adapter.py` | 9 | Task/Agent type parsing, config defaults, config env override, adapter create_image (mocked HTTP poll cycle), health check |
| `tests/test_eden_tools.py` | 20 | Tool count, tool names, registry registration, adapter get/set, create_image not-initialized error, create_image success, consciousness update on success, create_video success, chat creates session, chat reuses session, list_agents, health ok, health no adapter, error decreases coherence, success increases coherence, bridge actor name, bridge not ready without engine, bridge session closed, bridge unknown message, bridge snapshot |
| `tests/test_eden_mcp.py` | 16 | No API key unavailable, placeholder key unavailable, health ok, health error, create_image success, create_image with dimensions (extra_args), create_image not available, create_image exception, create_video success, chat no agent_id, chat new session, chat existing session, list_agents, format_result string passthrough, format_result dict to JSON, not_available helper |
| `tests/test_eden_policy.py` | 33 | Default policy, load from config, missing file defaults, no policy section defaults, from_dict, to_dict, save and reload, auto_approve tools, require_approval tools, unknown tool requires approval, disabled requires all approval, custom auto_approve, initial budget, record generation usage, record chat usage, check budget within limit, check budget exceeded, disabled policy fails budget, non-generation no budget, reset session, image+video share budget, policy blocks when disabled, policy blocks budget exceeded, policy allows auto-approved, generation records usage, policy status helper, router image generation, router video generation, router draw request, router eden mention, creative routes to SIMPLE_PLAN, non-creative not flagged, eden tool patterns detected |
| **Total** | **78** | |

---

## RUNNING TESTS

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root

# All Eden tests
pytest tests/test_eden_adapter.py tests/test_eden_tools.py tests/test_eden_mcp.py tests/test_eden_policy.py -v

# Individual suites
pytest tests/test_eden_adapter.py -v    # 9 tests
pytest tests/test_eden_tools.py -v      # 20 tests
pytest tests/test_eden_mcp.py -v        # 16 tests
pytest tests/test_eden_policy.py -v     # 33 tests
```

---

## KNOWN ISSUES / EDGE CASES

- **RUNNING status:** Eden API returns a `RUNNING` TaskStatus not documented in their API. Added to the enum after live validation discovered it.

- **Null result field:** `Task.result` can be `null` (not empty list) when a task is pending. Fixed by changing type from `list[TaskResult]` to `Optional[list[TaskResult]]`. The `first_output_url` property guards against this with `if self.result and len(self.result) > 0`.

- **Null tool_calls/attachments:** `SessionMessage.tool_calls` and `.attachments` can be null from the API. Changed from `list[X] = Field(default_factory=list)` to `Optional[list[X]] = None`.

- **width/height in extra_args:** `create_task()` puts width/height into the `extra_args` dict, which merges into `TaskCreateRequest.args`. They cannot be top-level params on the request.

- **Portrait pattern in router:** "paint a portrait" required adding `portrait` to the creative patterns and a broader `paint/draw ... a/an/the/me` catch-all regex.

- **MCP tools lack policy enforcement:** The MCP layer (`luna_mcp/tools/eden.py`) calls the adapter directly without going through the engine-side policy. This is by design — MCP is a different access path. If policy enforcement is needed there, it would need to be added separately.

---

## DESIGN DECISIONS

1. **Adapter over SDK** — Eden SDK is JS-only and in beta. Direct HTTP via httpx gives us retry control, no SDK dependency, and KOZMO extension points.

2. **Async context manager** — Matches Luna Engine patterns (aiosqlite, httpx in FastAPI). Connection pooling via `httpx.AsyncClient` is important for polling loops.

3. **Pydantic with camelCase aliases** — Eden API returns camelCase. `Field(alias="camelCase")` + `model_config = {"populate_by_name": True}` handles both directions cleanly.

4. **Global reference + setter** — `set_eden_adapter(adapter, engine)` matches the existing `set_memory_matrix()` pattern in memory_tools.py. Keeps tools stateless at definition time.

5. **Policy as data, not code** — `eden.json` is editable without code changes. The policy section is a flat dict that maps to a dataclass. Runtime counters are in-memory only.

6. **Separate generation vs chat budgets** — Image/video generation costs real manna on Eden. Chat has different cost characteristics. Separate caps give the user fine-grained control.

7. **Auto-approve for read-only tools** — `eden_health` and `eden_list_agents` are safe to run without confirmation. They don't spend manna or create content.

8. **Creative detection in router** — Without this, "generate an image of a sunset" would get a DIRECT response ("Sure, I can describe one!") instead of routing through the Eden tool pipeline. The `creative_request` signal forces SIMPLE_PLAN.

9. **EdenPolicy as dataclass, not Pydantic** — Deliberate. The policy needs mutable runtime counters (`_generation_count`, `_chat_count`) that should not be serialized. Dataclass with `field(repr=False)` handles this cleanly.

10. **MCP lazy-init singleton** — The MCP server may start before the Luna Engine. Lazy initialization on first tool call ensures the adapter is ready when needed, not at import time.

---

## WHAT COMES NEXT

Potential future work:

- **Gallery browsing tools** — `get_creations` endpoint is already in the adapter, just needs tool+MCP wrappers
- **Agent management** — `get_agent(agent_id)` is in the adapter, could expose as a tool for agent inspection
- **Session continuation** — `send_message`, `get_session` are in the adapter; a "continue conversation" tool could persist session IDs across Luna sessions
- **Fine-tuning/training integration** — Eden supports LoRA training; adapter could add training endpoints
- **KOZMO camera profile extensions** — Custom `extra_args` for camera angles, style locks, and lighting profiles specific to the KOZMO project
- **MCP-side policy enforcement** — Currently only engine-side tools respect EdenPolicy; MCP tools go direct to adapter
- **Streaming responses** — Eden sessions may support streaming; adapter could add SSE/WebSocket support
- **Budget persistence** — Currently budget counters reset per session (in-memory only); could persist to eden.json or engine state
