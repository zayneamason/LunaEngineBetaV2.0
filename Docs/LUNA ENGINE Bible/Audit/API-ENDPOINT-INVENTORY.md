# Luna Engine API Endpoint Inventory

**Source:** `src/luna/api/server.py`
**Generated:** 2026-01-25
**Total Endpoints:** 54

---

## Table of Contents

1. [Core Interaction](#core-interaction)
2. [Engine Status](#engine-status)
3. [Memory](#memory)
4. [Extraction](#extraction)
5. [Hub/History](#hubhistory)
6. [Debug](#debug)
7. [Voice](#voice)
8. [Tuning](#tuning)
9. [Ring Buffer](#ring-buffer)
10. [System](#system)

---

## Core Interaction

Endpoints for sending messages and receiving responses from Luna.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/message` | Send message and get response (sync) |
| POST | `/stream` | Send message and stream response (SSE) |
| POST | `/persona/stream` | Stream with context-first SSE format |
| POST | `/abort` | Abort current generation |
| POST | `/interrupt` | Interrupt Luna's current processing |
| GET | `/thoughts` | Stream Luna's internal thought process (SSE) |

### POST `/message`

Send a message to Luna and get a response.

**Request Body:** `MessageRequest`

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `message` | string | required | min=1, max=10000 | The message to send |
| `timeout` | float | 30.0 | 1.0-120.0 | Response timeout in seconds |
| `stream` | bool | false | - | Use streaming mode |

**Response:** `MessageResponse`

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Luna's response text |
| `model` | string | Model used for generation |
| `input_tokens` | int | Input token count |
| `output_tokens` | int | Output token count |
| `latency_ms` | float | Response latency in milliseconds |
| `delegated` | bool | Whether request was delegated to cloud |
| `local` | bool | Whether local inference was used |
| `fallback` | bool | Whether fallback model was used |

**Status Codes:**
- `200` - Success
- `503` - Engine not ready
- `504` - Response timeout

---

### POST `/stream`

Send a message and stream the response via Server-Sent Events.

**Request Body:** `MessageRequest` (same as `/message`)

**SSE Events:**

| Event | Data | Description |
|-------|------|-------------|
| `token` | `{"text": "..."}` | Each generated token |
| `done` | `{...metadata}` | Generation complete |
| `error` | `{"error": "..."}` | Error occurred |

**Status Codes:**
- `200` - SSE stream started
- `503` - Engine not ready

---

### POST `/persona/stream`

Stream Luna's response with context-first SSE format. Sends context (memory + state) BEFORE streaming tokens.

**Request Body:** `MessageRequest` (same as `/message`)

**SSE Data Format (typed JSON, no named events):**

| Type | Fields | Description |
|------|--------|-------------|
| `context` | `memory`, `state` | Memory items and state summary |
| `token` | `text` | Generated token chunk |
| `done` | `response`, `metadata` | Full response text and metadata |
| `error` | `message` | Error message |

**Status Codes:**
- `200` - SSE stream started
- `503` - Engine not ready

---

### GET `/thoughts`

Stream Luna's internal thought process via SSE.

**SSE Events:**

| Event | Data | Description |
|-------|------|-------------|
| `status` | `{connected, is_processing, goal}` | Initial connection status |
| `thought` | `{type, message, is_processing, goal}` | Internal thought/progress |
| `phase` | - | Current phase (idle, planning, etc.) |
| `step` | - | Plan step being executed |
| `ping` | `{is_processing, pending}` | Keepalive (every 15s) |

**Status Codes:**
- `200` - SSE stream started
- `503` - Engine not ready

---

### POST `/abort`

Abort the current generation.

**Request Body:** None

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "aborted" or "no_generation" |
| `message` | string | Status message |

**Status Codes:**
- `200` - Success
- `503` - Engine or Director not available

---

### POST `/interrupt`

Interrupt Luna's current processing. Triggers the agentic interrupt handler.

**Request Body:** None

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "interrupted" or "no_task" |
| `message` | string | Status message |
| `interrupted_goal` | string | Goal that was interrupted |
| `pending_messages` | int | Number of pending messages |

**Status Codes:**
- `200` - Success
- `503` - Engine not ready

---

## Engine Status

Endpoints for monitoring engine health and state.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/status` | Engine health and metrics |
| GET | `/health` | Simple health check |
| GET | `/history` | Recent conversation history |
| GET | `/consciousness` | Luna's consciousness state |

### GET `/status`

Get engine status and metrics.

**Query Parameters:** None

**Response:** `StatusResponse`

| Field | Type | Description |
|-------|------|-------------|
| `state` | string | Engine state |
| `uptime_seconds` | float | Uptime in seconds |
| `cognitive_ticks` | int | Number of cognitive ticks |
| `events_processed` | int | Events processed count |
| `messages_generated` | int | Messages generated count |
| `actors` | list[string] | Active actor names |
| `buffer_size` | int | Input buffer size |
| `current_turn` | int | Conversation turn counter |
| `context` | dict | Revolving context stats |
| `agentic` | AgenticStats | Agentic processing stats |

**AgenticStats Schema:**

| Field | Type | Description |
|-------|------|-------------|
| `is_processing` | bool | Currently processing |
| `current_goal` | string | Current goal |
| `pending_messages` | int | Pending message count |
| `tasks_started` | int | Tasks started count |
| `tasks_completed` | int | Tasks completed count |
| `tasks_aborted` | int | Tasks aborted count |
| `direct_responses` | int | Direct response count |
| `planned_responses` | int | Planned response count |
| `agent_loop_status` | string | Agent loop status |

**Status Codes:**
- `200` - Success
- `503` - Engine not ready

---

### GET `/health`

Simple health check endpoint.

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "healthy" or "starting" |
| `state` | string | Engine state name |

**Status Codes:**
- `200` - Always returns 200

---

### GET `/history`

Get recent conversation history.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 20 | Max messages to return |

**Response:** `HistoryResponse`

| Field | Type | Description |
|-------|------|-------------|
| `messages` | list[HistoryMessage] | Conversation messages |
| `total` | int | Total message count |

**HistoryMessage Schema:**

| Field | Type | Description |
|-------|------|-------------|
| `role` | string | "user" or "assistant" |
| `content` | string | Message content |
| `timestamp` | int | Unix timestamp |

**Status Codes:**
- `200` - Success
- `503` - Engine not ready

---

### GET `/consciousness`

Get Luna's current consciousness state.

**Response:** `ConsciousnessResponse`

| Field | Type | Description |
|-------|------|-------------|
| `mood` | string | Current mood |
| `coherence` | float | Coherence score |
| `attention_topics` | int | Number of attention topics |
| `focused_topics` | list[dict] | Currently focused topics |
| `top_traits` | list[tuple] | Top personality traits |
| `tick_count` | int | Consciousness tick count |
| `last_updated` | string | Last update timestamp |

**Status Codes:**
- `200` - Success
- `503` - Engine not ready

---

## Memory

Endpoints for managing Luna's memory substrate.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/memory/nodes` | Create a new memory node |
| GET | `/memory/nodes/{node_id}` | Get a memory node by ID |
| GET | `/memory/nodes` | List memory nodes with filtering |
| POST | `/memory/nodes/{node_id}/access` | Record access to a node |
| POST | `/memory/nodes/{node_id}/reinforce` | Reinforce a memory node |
| GET | `/memory/stats` | Get memory statistics |

### POST `/memory/nodes`

Create a new memory node directly (bypasses extraction).

**Request Body:** `NodeCreateRequest`

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `node_type` | string | required | - | FACT, DECISION, PROBLEM, etc. |
| `content` | string | required | min=1 | Node content |
| `source` | string | null | - | Source identifier |
| `confidence` | float | 1.0 | 0.0-1.0 | Confidence level |
| `importance` | float | 0.5 | 0.0-1.0 | Importance level |

**Response:** `NodeResponse`

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Node ID |
| `node_type` | string | Node type |
| `content` | string | Node content |
| `source` | string | Source identifier |
| `confidence` | float | Confidence level |
| `importance` | float | Importance level |
| `access_count` | int | Access count |
| `reinforcement_count` | int | Reinforcement count |
| `lock_in` | float | Lock-in coefficient |
| `lock_in_state` | string | drifting/fluid/settled |
| `created_at` | string | ISO timestamp |

**Status Codes:**
- `200` - Success
- `500` - Creation failed
- `503` - Engine or Matrix not available

---

### GET `/memory/nodes/{node_id}`

Get a memory node by ID.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `node_id` | string | Node identifier |

**Response:** `NodeResponse` (same as above)

**Status Codes:**
- `200` - Success
- `404` - Node not found
- `503` - Engine or Matrix not available

---

### GET `/memory/nodes`

List memory nodes with optional filtering.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `node_type` | string | null | Filter by type (FACT, DECISION, etc.) |
| `lock_in_state` | string | null | Filter by state (drifting, fluid, settled) |
| `limit` | int | 50 | Max nodes to return |

**Response:** `list[NodeResponse]`

**Status Codes:**
- `200` - Success
- `500` - Query failed
- `503` - Engine or Matrix not available

---

### POST `/memory/nodes/{node_id}/access`

Record an access to a memory node. Increases access count and updates lock-in coefficient.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `node_id` | string | Node identifier |

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "accessed" |
| `node_id` | string | Node ID |
| `new_access_count` | int | Updated access count |
| `new_lock_in` | float | Updated lock-in coefficient |
| `new_lock_in_state` | string | Updated lock-in state |

**Status Codes:**
- `200` - Success
- `500` - Operation failed
- `503` - Engine or Matrix not available

---

### POST `/memory/nodes/{node_id}/reinforce`

Reinforce a memory node. Boosts lock-in coefficient; reinforced nodes are never pruned.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `node_id` | string | Node identifier |

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "reinforced" |
| `node_id` | string | Node ID |
| `reinforcement_count` | int | Updated reinforcement count |
| `new_lock_in` | float | Updated lock-in coefficient |
| `new_lock_in_state` | string | Updated lock-in state |

**Status Codes:**
- `200` - Success
- `500` - Operation failed
- `503` - Engine or Matrix not available

---

### GET `/memory/stats`

Get memory statistics including lock-in distribution.

**Response:** `MemoryStatsResponse`

| Field | Type | Description |
|-------|------|-------------|
| `total_nodes` | int | Total node count |
| `nodes_by_type` | dict | Nodes grouped by type |
| `nodes_by_lock_in` | dict | Nodes grouped by lock-in state |
| `avg_lock_in` | float | Average lock-in coefficient |
| `total_edges` | int | Total edge count |
| `drifting_nodes` | int | Nodes in drifting state |
| `fluid_nodes` | int | Nodes in fluid state |
| `settled_nodes` | int | Nodes in settled state |

**Status Codes:**
- `200` - Success
- `500` - Query failed
- `503` - Engine or Matrix not available

---

## Extraction

Endpoints for managing the extraction pipeline (Scribe/Librarian).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/extraction/trigger` | Trigger extraction on content |
| POST | `/extraction/prune` | Trigger synaptic pruning |
| GET | `/extraction/stats` | Get extraction statistics |
| GET | `/extraction/history` | Get recent extraction history |

### POST `/extraction/trigger`

Trigger extraction on content via the Scribe actor.

**Request Body:** `ExtractionRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `content` | string | required | Content to extract from |
| `role` | string | "user" | Role (user/assistant) |
| `session_id` | string | null | Session identifier |
| `immediate` | bool | true | Process immediately without batching |

**Response:** `ExtractionResponse`

| Field | Type | Description |
|-------|------|-------------|
| `objects_extracted` | int | Number of objects extracted |
| `edges_extracted` | int | Number of edges extracted |
| `nodes_created` | list[string] | IDs of created nodes |

**Status Codes:**
- `200` - Success
- `500` - Extraction failed
- `503` - Engine or Scribe not available

---

### POST `/extraction/prune`

Trigger synaptic pruning. Removes low-value edges and optionally prunes drifting nodes.

**Request Body:** `PruneRequest`

| Field | Type | Default | Constraints | Description |
|-------|------|---------|-------------|-------------|
| `age_days` | int | 30 | >=1 | Age threshold in days |
| `confidence_threshold` | float | 0.3 | 0.0-1.0 | Confidence threshold |
| `prune_nodes` | bool | true | - | Also prune drifting nodes |
| `max_prune_nodes` | int | 100 | >=1 | Max nodes to prune |

**Response:** `PruneResponse`

| Field | Type | Description |
|-------|------|-------------|
| `edges_pruned` | int | Number of edges pruned |
| `nodes_pruned` | int | Number of nodes pruned |

**Status Codes:**
- `200` - Success
- `500` - Pruning failed
- `503` - Engine or Librarian not available

---

### GET `/extraction/stats`

Get extraction statistics from Scribe and Librarian.

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `scribe` | dict | Scribe actor statistics |
| `librarian` | dict | Librarian actor statistics |

**Status Codes:**
- `200` - Success
- `503` - Engine not ready

---

### GET `/extraction/history`

Get recent extraction history from Scribe.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 20 | Max extractions to return |

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `extractions` | list | Recent extraction records |
| `total` | int | Total extraction count |

**Status Codes:**
- `200` - Success
- `503` - Engine or Scribe not available

---

## Hub/History

Endpoints for conversation history management.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/hub/session/create` | Create a new session |
| POST | `/hub/session/end` | End a session |
| GET | `/hub/session/active` | Get active session |
| POST | `/hub/turn/add` | Add a turn to history |
| GET | `/hub/active_window` | Get Active Window turns |
| GET | `/hub/active_token_count` | Get token count for Active tier |
| POST | `/hub/tier/rotate` | Rotate a turn to a new tier |
| GET | `/hub/tier/oldest_active` | Get oldest turn in Active tier |
| POST | `/hub/search` | Search conversation history |
| GET | `/hub/stats` | Get history manager statistics |

### POST `/hub/session/create`

Create a new conversation session.

**Request Body:** `HubSessionCreateRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `app_context` | string | "terminal" | Application context |

**Response:** `HubSessionResponse`

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session identifier |
| `started_at` | float | Start timestamp |
| `ended_at` | float | End timestamp (null if active) |
| `app_context` | string | Application context |

**Status Codes:**
- `200` - Success
- `503` - Engine or History Manager not available

---

### POST `/hub/session/end`

End a conversation session.

**Query Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `session_id` | string | Session to end |

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Operation success |
| `session_id` | string | Ended session ID |

**Status Codes:**
- `200` - Success
- `503` - Engine or History Manager not available

---

### GET `/hub/session/active`

Get the currently active session.

**Response:** `HubSessionResponse` or `null`

**Status Codes:**
- `200` - Success
- `503` - Engine not ready

---

### POST `/hub/turn/add`

Add a turn to conversation history.

**Request Body:** `HubTurnAddRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `session_id` | string | null | Session ID (uses active if null) |
| `role` | string | required | Role (user/assistant) |
| `content` | string | required | Turn content |
| `tokens` | int | required | Token count |

**Response:** `HubTurnResponse`

| Field | Type | Description |
|-------|------|-------------|
| `turn_id` | int | Turn identifier |
| `tier` | string | Tier assigned |

**Status Codes:**
- `200` - Success
- `503` - Engine or History Manager not available

---

### GET `/hub/active_window`

Get the Active Window turns.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `session_id` | string | null | Filter by session |
| `limit` | int | 10 | Max turns to return |

**Response:** `HubActiveWindowResponse`

| Field | Type | Description |
|-------|------|-------------|
| `turns` | list | Active window turns |
| `total_tokens` | int | Total token count |
| `turn_count` | int | Number of turns |

**Status Codes:**
- `200` - Success
- `503` - Engine not ready

---

### GET `/hub/active_token_count`

Get token count for Active tier.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `session_id` | string | null | Filter by session |

**Response:** `HubTokenCountResponse`

| Field | Type | Description |
|-------|------|-------------|
| `total_tokens` | int | Total token count |
| `turn_count` | int | Number of turns |

**Status Codes:**
- `200` - Success
- `503` - Engine not ready

---

### POST `/hub/tier/rotate`

Rotate a turn to a new tier.

**Request Body:** `HubTierRotateRequest`

| Field | Type | Description |
|-------|------|-------------|
| `turn_id` | int | Turn to rotate |
| `new_tier` | string | Target tier |

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `success` | bool | Operation success |

**Status Codes:**
- `200` - Success
- `503` - Engine or History Manager not available

---

### GET `/hub/tier/oldest_active`

Get the oldest turn in Active tier.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `session_id` | string | null | Filter by session |

**Response:** Turn object or `null`

**Status Codes:**
- `200` - Success
- `503` - Engine not ready

---

### POST `/hub/search`

Search conversation history.

**Request Body:** `HubHistorySearchRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `query` | string | required | Search query |
| `tier` | string | "recent" | Tier to search |
| `session_id` | string | null | Filter by session |
| `limit` | int | 3 | Max results |
| `search_type` | string | "hybrid" | Search type |

**Response:** `HubHistorySearchResponse`

| Field | Type | Description |
|-------|------|-------------|
| `results` | list | Search results |
| `total` | int | Total result count |

**Status Codes:**
- `200` - Success
- `503` - Engine not ready

---

### GET `/hub/stats`

Get history manager statistics.

**Response:** Dict with history manager stats

**Status Codes:**
- `200` - Success
- `503` - Engine not ready

---

## Debug

Endpoints for debugging Luna's internal state.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/debug/conversation-cache` | Get conversation cache |
| GET | `/debug/personality` | Get personality system state |
| GET | `/debug/context` | Get current context window |

### GET `/debug/conversation-cache`

Get Luna's conversation cache - the conversation history she's aware of.

**Response:** `ConversationCacheResponse`

| Field | Type | Description |
|-------|------|-------------|
| `current_turn` | int | Current turn number |
| `max_turns` | int | TTL for conversation items |
| `items` | list[ConversationCacheItem] | Cached conversation items |
| `total_tokens` | int | Total token count |

**ConversationCacheItem Schema:**

| Field | Type | Description |
|-------|------|-------------|
| `role` | string | user/assistant/unknown |
| `content` | string | Message content |
| `turn` | int | Turn number |
| `relevance` | float | Relevance score |
| `age_turns` | int | Age in turns |

**Status Codes:**
- `200` - Success
- `503` - Engine not ready

---

### GET `/debug/personality`

Get Luna's personality system state for debugging.

**Response:** `PersonalityDebugResponse`

| Field | Type | Description |
|-------|------|-------------|
| `stats` | PersonalityStatsResponse | Personality statistics |
| `patches` | list[PersonalityPatchResponse] | Personality patches |
| `maintenance` | MaintenanceStatsResponse | Maintenance statistics |
| `session` | SessionStatsResponse | Session reflection stats |
| `mood_state` | string | Current mood |
| `bootstrap_status` | string | Bootstrap status |

**PersonalityStatsResponse Schema:**

| Field | Type | Description |
|-------|------|-------------|
| `total_patches` | int | Total patch count |
| `active_patches` | int | Active patch count |
| `average_lock_in` | float | Average lock-in |
| `patches_by_topic` | dict | Patches grouped by topic |
| `patches_by_lock_in_state` | dict | Patches grouped by lock-in state |

**Status Codes:**
- `200` - Success
- `503` - Engine or Director not available

---

### GET `/debug/context`

Get Luna's current context window for debugging.

**Response:** `ContextDebugResponse`

| Field | Type | Description |
|-------|------|-------------|
| `current_turn` | int | Current turn number |
| `token_budget` | int | Token budget |
| `total_tokens` | int | Total tokens used |
| `items` | list[ContextItemResponse] | Context items |
| `keywords` | list[string] | Keywords Luna is aware of |
| `ring_stats` | dict | Statistics per ring |

**ContextItemResponse Schema:**

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Item ID |
| `content` | string | Item content |
| `source` | string | IDENTITY, CONVERSATION, MEMORY, etc. |
| `ring` | string | CORE, INNER, MIDDLE, OUTER |
| `relevance` | float | Relevance score |
| `tokens` | int | Token count |
| `age_turns` | int | Age in turns |
| `ttl_turns` | int | Time-to-live in turns |
| `is_expired` | bool | Whether item is expired |

**Status Codes:**
- `200` - Success
- `503` - Engine not ready

---

## Voice

Endpoints for voice interaction (STT/TTS).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/voice/start` | Start voice system |
| POST | `/voice/stop` | Stop voice system |
| GET | `/voice/status` | Get voice system status |
| POST | `/voice/listen/start` | Start recording (push-to-talk press) |
| POST | `/voice/listen/stop` | Stop recording (push-to-talk release) |
| POST | `/voice/speak` | Speak text using TTS |
| GET | `/voice/stream` | Stream voice status updates (SSE) |

### POST `/voice/start`

Start the voice system.

**Request Body:** `VoiceStartRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `hands_free` | bool | false | Enable hands-free mode |

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "started" or "already_running" |
| `message` | string | Status message |
| `hands_free` | bool | Hands-free mode enabled |

**Status Codes:**
- `200` - Success
- `500` - Start failed
- `503` - Engine not ready or voice components unavailable

---

### POST `/voice/stop`

Stop the voice system.

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "stopped" or "not_running" |
| `message` | string | Status message |

**Status Codes:**
- `200` - Success
- `500` - Stop failed

---

### GET `/voice/status`

Get voice system status.

**Response:** `VoiceStatusResponse`

| Field | Type | Description |
|-------|------|-------------|
| `running` | bool | Voice system running |
| `recording` | bool | Currently recording |
| `hands_free` | bool | Hands-free mode enabled |
| `stt_provider` | string | STT provider name |
| `tts_provider` | string | TTS provider name |
| `persona_connected` | bool | Connected to Luna persona |
| `turn_count` | int | Voice turn count |

**Status Codes:**
- `200` - Always returns 200

---

### POST `/voice/listen/start`

Start recording user speech (push-to-talk press).

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "listening" or "hands_free" |
| `message` | string | Status message |

**Status Codes:**
- `200` - Success
- `400` - Voice system not active

---

### POST `/voice/listen/stop`

Stop recording and process speech (push-to-talk release).

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "processing", "no_speech", or "hands_free" |
| `message` | string | Status message |
| `transcription` | string | Transcribed text (if any) |
| `hint` | string | Help hint (on no_speech) |

**Status Codes:**
- `200` - Success
- `400` - Voice system not active

---

### POST `/voice/speak`

Speak the given text using TTS.

**Request Body:** `SpeakRequest`

| Field | Type | Description |
|-------|------|-------------|
| `text` | string | Text to speak |

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "speaking", "not_running", or "error" |
| `text` | string | Text being spoken |
| `message` | string | Error message (on error) |

**Status Codes:**
- `200` - Always returns 200

---

### GET `/voice/stream`

Stream voice status updates via SSE.

**SSE Events:**

| Event | Data | Description |
|-------|------|-------------|
| `status` | `{connected, status, running}` | Status update |
| `transcription` | `{type, text}` | User speech transcribed |
| `response` | `{type, text}` | Luna's response |
| `ping` | `{running}` | Keepalive (every 10s) |

**Status Codes:**
- `200` - SSE stream started

---

## Tuning

Endpoints for runtime parameter tuning.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/tuning/params` | List all tunable parameters |
| GET | `/tuning/params/{name}` | Get parameter details |
| POST | `/tuning/params/{name}` | Set parameter value |
| POST | `/tuning/param-reset/{name}` | Reset parameter to default |
| POST | `/tuning/session/new` | Start a new tuning session |
| GET | `/tuning/session` | Get current tuning session |
| POST | `/tuning/session/end` | End tuning session |
| POST | `/tuning/eval` | Run evaluation |
| GET | `/tuning/compare` | Compare iterations |
| GET | `/tuning/best` | Get best parameters |
| POST | `/tuning/apply-best` | Apply best parameters |
| GET | `/tuning/sessions` | List recent sessions |

### GET `/tuning/params`

List all tunable parameters.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `category` | string | null | Filter by category |

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `params` | list | Parameter list |
| `categories` | list | Available categories |
| `count` | int | Parameter count |

**Status Codes:**
- `200` - Success

---

### GET `/tuning/params/{name}`

Get details for a specific parameter.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | string | Parameter name (path-style) |

**Response:** `TuningParamResponse`

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Parameter name |
| `value` | float | Current value |
| `default` | float | Default value |
| `bounds` | tuple | (min, max) bounds |
| `step` | float | Step size |
| `category` | string | Category |
| `description` | string | Description |
| `is_overridden` | bool | Whether value is overridden |

**Status Codes:**
- `200` - Success
- `404` - Parameter not found

---

### POST `/tuning/params/{name}`

Set a parameter value.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | string | Parameter name (path-style) |

**Request Body:** `TuningParamSetRequest`

| Field | Type | Description |
|-------|------|-------------|
| `value` | float | New value |

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Parameter name |
| `previous_value` | float | Previous value |
| `new_value` | float | New value |
| `eval_score` | float | Evaluation score (if session active) |
| `iteration` | int | Iteration number (if session active) |

**Status Codes:**
- `200` - Success
- `400` - Invalid value
- `404` - Parameter not found

---

### POST `/tuning/param-reset/{name}`

Reset a parameter to its default value.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | string | Parameter name (path-style) |

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Parameter name |
| `previous_value` | float | Previous value |
| `new_value` | float | Default value |
| `was_overridden` | bool | Whether it was overridden |

**Status Codes:**
- `200` - Success
- `404` - Parameter not found

---

### POST `/tuning/session/new`

Start a new tuning session.

**Request Body:** `TuningSessionNewRequest`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `focus` | string | "all" | Focus area (memory, routing, latency, context, all) |
| `notes` | string | "" | Session notes |

**Response:** `TuningSessionResponse`

| Field | Type | Description |
|-------|------|-------------|
| `session_id` | string | Session identifier |
| `focus` | string | Focus area |
| `started_at` | string | Start timestamp |
| `best_iteration` | int | Best iteration number |
| `best_score` | float | Best score |
| `iteration_count` | int | Number of iterations |

**Status Codes:**
- `200` - Success

---

### GET `/tuning/session`

Get current tuning session.

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `active` | bool | Whether session is active |
| `session_id` | string | Session identifier |
| `focus` | string | Focus area |
| `started_at` | string | Start timestamp |
| `best_iteration` | int | Best iteration number |
| `best_score` | float | Best score |
| `iteration_count` | int | Number of iterations |
| `iterations` | list | Iteration details |

**Status Codes:**
- `200` - Success

---

### POST `/tuning/session/end`

End the current tuning session.

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `ended` | bool | Whether session was ended |
| `session_id` | string | Session identifier |
| `best_iteration` | int | Best iteration number |
| `best_score` | float | Best score |
| `total_iterations` | int | Total iterations |
| `message` | string | Status message (if no session) |

**Status Codes:**
- `200` - Success

---

### POST `/tuning/eval`

Run evaluation.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `category` | string | null | Category to evaluate |

**Response:** `TuningEvalResponse`

| Field | Type | Description |
|-------|------|-------------|
| `overall_score` | float | Overall score |
| `memory_recall_score` | float | Memory recall score |
| `context_retention_score` | float | Context retention score |
| `routing_score` | float | Routing score |
| `avg_latency_ms` | float | Average latency |
| `p95_latency_ms` | float | 95th percentile latency |
| `total_tests` | int | Total tests run |
| `passed_tests` | int | Tests passed |
| `failed_tests` | int | Tests failed |

**Status Codes:**
- `200` - Success

---

### GET `/tuning/compare`

Compare two iterations.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `iter1` | int | 1 | First iteration |
| `iter2` | int | null | Second iteration (default: latest) |

**Response:** `TuningCompareResponse`

| Field | Type | Description |
|-------|------|-------------|
| `iteration_1` | int | First iteration number |
| `iteration_2` | int | Second iteration number |
| `score_1` | float | First iteration score |
| `score_2` | float | Second iteration score |
| `score_diff` | float | Score difference |
| `param_diffs` | dict | Parameter differences |
| `metric_diffs` | dict | Metric differences |

**Status Codes:**
- `200` - Success
- `400` - No active session or no iterations

---

### GET `/tuning/best`

Get parameters from the best iteration.

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `best_iteration` | int | Best iteration number |
| `best_score` | float | Best score |
| `params` | dict | Best parameters |

**Status Codes:**
- `200` - Success
- `400` - No active session

---

### POST `/tuning/apply-best`

Apply parameters from the best iteration.

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `applied` | int | Number of params applied |
| `best_iteration` | int | Best iteration number |
| `best_score` | float | Best score |

**Status Codes:**
- `200` - Success
- `400` - No active session

---

### GET `/tuning/sessions`

List recent tuning sessions.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 10 | Max sessions to return |

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `sessions` | list | Session list |
| `count` | int | Session count |

**Status Codes:**
- `200` - Success

---

## Ring Buffer

Endpoints for conversation ring buffer management.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/ring/status` | Get ring buffer status |
| POST | `/api/ring/config` | Configure ring buffer size |
| POST | `/api/ring/clear` | Clear the ring buffer |

### GET `/api/ring/status`

Get current ring buffer status.

**Response:** `RingBufferStatus`

| Field | Type | Description |
|-------|------|-------------|
| `current_turns` | int | Current turn count |
| `max_turns` | int | Maximum turns capacity |
| `topics` | list[string] | Detected topics (max 10) |
| `recent_messages` | list[dict] | Recent messages (last 6) |

**Status Codes:**
- `200` - Success
- `503` - Engine or Director not available

---

### POST `/api/ring/config`

Configure the ring buffer size. Changes take effect immediately.

**Request Body:** `RingBufferConfig`

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `max_turns` | int | 2-20 | Maximum turns capacity |

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "configured" |
| `previous_max_turns` | int | Previous capacity |
| `new_max_turns` | int | New capacity |
| `current_turns` | int | Current turn count |

**Status Codes:**
- `200` - Success
- `503` - Engine, Director, or Ring Buffer not available

---

### POST `/api/ring/clear`

Clear the ring buffer. Resets conversation memory.

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "cleared" |
| `cleared_turns` | int | Number of turns cleared |

**Status Codes:**
- `200` - Success
- `503` - Engine, Director, or Ring Buffer not available

---

## System

System-level endpoints.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/system/relaunch` | Trigger system relaunch |

### POST `/api/system/relaunch`

Trigger a system relaunch. Executes the relaunch script in background.

**Response:**

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | "restarting" |
| `message` | string | Status message |

**Status Codes:**
- `200` - Relaunch initiated
- `404` - Relaunch script not found

---

## Endpoint Summary by Category

| Category | Count | Endpoints |
|----------|-------|-----------|
| Core Interaction | 6 | /message, /stream, /persona/stream, /abort, /interrupt, /thoughts |
| Engine Status | 4 | /status, /health, /history, /consciousness |
| Memory | 6 | /memory/nodes (CRUD), /memory/stats |
| Extraction | 4 | /extraction/trigger, /extraction/prune, /extraction/stats, /extraction/history |
| Hub/History | 10 | /hub/* session, turn, tier, search, stats |
| Debug | 3 | /debug/conversation-cache, /debug/personality, /debug/context |
| Voice | 7 | /voice/* start, stop, status, listen, speak, stream |
| Tuning | 12 | /tuning/* params, session, eval, compare, best |
| Ring Buffer | 3 | /api/ring/* status, config, clear |
| System | 1 | /api/system/relaunch |
| **Total** | **56** | |

---

## Notes

1. **Authentication:** No authentication is currently implemented on these endpoints.
2. **CORS:** Enabled for localhost ports 3000, 5173, 5174 and 127.0.0.1 variants.
3. **SSE Endpoints:** `/stream`, `/persona/stream`, `/thoughts`, and `/voice/stream` return Server-Sent Events.
4. **Engine Dependency:** Most endpoints require the engine to be running and return 503 if not ready.
5. **Actor Dependencies:** Memory endpoints require Matrix actor; Extraction requires Scribe/Librarian; Voice requires voice components.
