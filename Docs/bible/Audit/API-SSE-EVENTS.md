# Luna Engine API - Server-Sent Events (SSE) Documentation

This document provides comprehensive documentation for all SSE streaming endpoints in the Luna Engine API.

## Table of Contents

1. [POST /stream](#post-stream)
2. [POST /persona/stream](#post-personastream)
3. [GET /thoughts](#get-thoughts)
4. [GET /voice/stream](#get-voicestream)

---

## POST /stream

**Purpose:** Send a message to Luna and stream the response token-by-token.

### Request

```http
POST /stream
Content-Type: application/json

{
  "message": "Hello Luna, how are you?",
  "timeout": 30.0
}
```

### Request Body

| Field   | Type   | Required | Default | Description                          |
|---------|--------|----------|---------|--------------------------------------|
| message | string | Yes      | -       | Message to send (1-10000 chars)      |
| timeout | float  | No       | 30.0    | Response timeout in seconds (1-120)  |

### Response Headers

```http
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

### Event Types

#### `token`

Fired for each generated token during streaming.

```
event: token
data: {"text": "Hello"}

event: token
data: {"text": " there"}

event: token
data: {"text": "!"}
```

**Data Format:**

| Field | Type   | Description              |
|-------|--------|--------------------------|
| text  | string | The generated token text |

#### `done`

Fired when generation completes successfully.

```
event: done
data: {"model": "qwen3b", "input_tokens": 45, "output_tokens": 128, "latency_ms": 2340.5, "delegated": false, "local": true, "fallback": false}
```

**Data Format:**

| Field         | Type    | Description                              |
|---------------|---------|------------------------------------------|
| model         | string  | Model used for generation                |
| input_tokens  | integer | Number of input tokens processed         |
| output_tokens | integer | Number of output tokens generated        |
| latency_ms    | float   | Total latency in milliseconds            |
| delegated     | boolean | True if delegated to Claude API          |
| local         | boolean | True if processed by local model         |
| fallback      | boolean | True if used fallback model              |

#### `error`

Fired when an error occurs during streaming.

```
event: error
data: {"error": "Timeout waiting for tokens"}
```

**Data Format:**

| Field | Type   | Description        |
|-------|--------|--------------------|
| error | string | Error message      |

### Connection Lifecycle

1. **Open:** Client sends POST request, connection established
2. **Streaming:** Server sends `token` events as tokens are generated
3. **Complete:** Server sends `done` event with final metadata
4. **Close:** Connection closes after `done` or `error` event

### Error Conditions

- `503 Service Unavailable`: Engine not ready
- `504 Gateway Timeout`: Response timeout exceeded
- Director actor not available (sent as SSE error event)

### Example Event Sequence

```
event: token
data: {"text": "I"}

event: token
data: {"text": "'m"}

event: token
data: {"text": " doing"}

event: token
data: {"text": " well"}

event: token
data: {"text": "!"}

event: done
data: {"model": "qwen3b", "input_tokens": 12, "output_tokens": 5, "latency_ms": 450.2, "delegated": false, "local": true, "fallback": false}
```

---

## POST /persona/stream

**Purpose:** Stream Luna's response with context (memory + state) sent BEFORE tokens, allowing the frontend to prepare UI with relevant information.

### Request

```http
POST /persona/stream
Content-Type: application/json

{
  "message": "What did we discuss yesterday?",
  "timeout": 30.0
}
```

### Request Body

| Field   | Type   | Required | Default | Description                          |
|---------|--------|----------|---------|--------------------------------------|
| message | string | Yes      | -       | Message to send (1-10000 chars)      |
| timeout | float  | No       | 30.0    | Response timeout in seconds (1-120)  |

### Response Headers

```http
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

### Event Format

This endpoint uses **typed JSON data** format (no named SSE events). All events are sent as:

```
data: {"type": "<type>", ...fields}
```

### Event Types

#### `context`

Sent FIRST before any tokens. Contains memory items and engine state.

```
data: {"type": "context", "memory": [...], "state": {...}}
```

**Data Format:**

| Field  | Type   | Description                           |
|--------|--------|---------------------------------------|
| type   | string | Always `"context"`                    |
| memory | array  | Recent memory items (see below)       |
| state  | object | Current engine state (see below)      |

**Memory Item Format:**

| Field   | Type   | Description                        |
|---------|--------|------------------------------------|
| id      | string | Memory node ID                     |
| content | string | Content (truncated to 200 chars)   |
| type    | string | Node type (FACT, DECISION, etc.)   |
| source  | string | Source identifier                  |

**State Format:**

| Field         | Type    | Description                      |
|---------------|---------|----------------------------------|
| session_id    | string  | Current session identifier       |
| is_processing | boolean | Always `true` during streaming   |
| state         | string  | Engine state name                |
| model         | string  | Current model being used         |

#### `token`

Fired for each generated token during streaming.

```
data: {"type": "token", "text": "Hello"}
```

**Data Format:**

| Field | Type   | Description              |
|-------|--------|--------------------------|
| type  | string | Always `"token"`         |
| text  | string | The generated token text |

#### `done`

Fired when generation completes successfully.

```
data: {"type": "done", "response": "Full response text here", "metadata": {...}}
```

**Data Format:**

| Field    | Type   | Description                              |
|----------|--------|------------------------------------------|
| type     | string | Always `"done"`                          |
| response | string | Complete concatenated response text      |
| metadata | object | Same format as `/stream` done event data |

#### `error`

Fired when an error occurs.

```
data: {"type": "error", "message": "Director not available"}
```

**Data Format:**

| Field   | Type   | Description        |
|---------|--------|--------------------|
| type    | string | Always `"error"`   |
| message | string | Error message      |

### Connection Lifecycle

1. **Open:** Client sends POST request, connection established
2. **Context Phase:** Server sends `context` event with memory + state
3. **Streaming Phase:** Server sends `token` events as tokens are generated
4. **Complete:** Server sends `done` event with full response and metadata
5. **Close:** Connection closes after `done` or `error` event

### Example Event Sequence

```
data: {"type": "context", "memory": [{"id": "mem_001", "content": "Yesterday we discussed the project timeline...", "type": "CONVERSATION", "source": "session_abc"}], "state": {"session_id": "session_abc", "is_processing": true, "state": "RUNNING", "model": "qwen3b"}}

data: {"type": "token", "text": "Yesterday"}

data: {"type": "token", "text": " we"}

data: {"type": "token", "text": " discussed"}

data: {"type": "token", "text": "..."}

data: {"type": "done", "response": "Yesterday we discussed...", "metadata": {"model": "qwen3b", "output_tokens": 45, "local": true}}
```

---

## GET /thoughts

**Purpose:** Stream Luna's internal thought process in real-time. Shows what Luna is doing during agentic processing.

### Request

```http
GET /thoughts
```

No request body required.

### Response Headers

```http
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

### Event Types

#### `status`

Initial connection status. Sent immediately upon connection.

```
event: status
data: {"connected": true, "is_processing": false, "goal": null}
```

**Data Format:**

| Field         | Type    | Description                           |
|---------------|---------|---------------------------------------|
| connected     | boolean | Always `true` on initial connection   |
| is_processing | boolean | Whether Luna is currently processing  |
| goal          | string  | Current goal being worked on (or null)|

#### `thought`

Internal thought or progress message from the AgentLoop.

```
event: thought
data: {"type": "thought", "message": "[DIRECT] Hello Luna...", "is_processing": true, "goal": "Respond to user greeting"}
```

**Data Format:**

| Field         | Type    | Description                           |
|---------------|---------|---------------------------------------|
| type          | string  | Always `"thought"`                    |
| message       | string  | The thought/progress message          |
| is_processing | boolean | Whether Luna is currently processing  |
| goal          | string  | Current goal (or null)                |

**Common Message Prefixes:**

| Prefix      | Meaning                                    |
|-------------|--------------------------------------------|
| `[DIRECT]`  | Direct response (no planning needed)       |
| `[PLAN]`    | Creating a plan for complex task           |
| `[STEP]`    | Executing a plan step                      |
| `[TOOL]`    | Using a tool                               |
| `[OK]`      | Successful completion                      |
| `[ERROR]`   | Error occurred                             |
| `[ABORT]`   | Task aborted (interrupted)                 |

#### `phase`

Current processing phase change.

```
event: phase
data: {"type": "phase", "phase": "thinking", "is_processing": true, "goal": "Analyze user request"}
```

**Phases:**

| Phase      | Description                        |
|------------|------------------------------------|
| idle       | No active processing               |
| planning   | Creating a plan                    |
| observing  | Gathering context                  |
| thinking   | Processing/reasoning               |
| acting     | Executing actions                  |

#### `step`

Plan step being executed.

```
event: step
data: {"type": "step", "step_num": 2, "total_steps": 5, "description": "Search memory for relevant context", "is_processing": true, "goal": "Answer user question"}
```

**Data Format:**

| Field         | Type    | Description                           |
|---------------|---------|---------------------------------------|
| type          | string  | Always `"step"`                       |
| step_num      | integer | Current step number                   |
| total_steps   | integer | Total steps in plan                   |
| description   | string  | Step description                      |
| is_processing | boolean | Processing state                      |
| goal          | string  | Current goal                          |

#### `ping`

Keepalive ping. Sent every 15 seconds of inactivity.

```
event: ping
data: {"is_processing": false, "pending": 0}
```

**Data Format:**

| Field         | Type    | Description                           |
|---------------|---------|---------------------------------------|
| is_processing | boolean | Whether Luna is currently processing  |
| pending       | integer | Number of pending messages in queue   |

### Connection Lifecycle

1. **Open:** Client sends GET request, connection established
2. **Initial Status:** Server sends `status` event with current state
3. **Streaming:** Server sends `thought`, `phase`, `step` events as processing occurs
4. **Keepalive:** Server sends `ping` every 15 seconds of inactivity
5. **Close:** Connection closes when client disconnects (CancelledError)

### Reconnection Behavior

- Client should reconnect on connection drop
- No automatic server-side reconnection
- State is not persisted across connections
- Client will receive fresh `status` event on reconnect

### Example Event Sequence (Simple Query)

```
event: status
data: {"connected": true, "is_processing": false, "goal": null}

event: thought
data: {"type": "thought", "message": "[DIRECT] What is 2+2?...", "is_processing": true, "goal": null}

event: thought
data: {"type": "thought", "message": "[OK] local: 12 tokens", "is_processing": false, "goal": null}

event: ping
data: {"is_processing": false, "pending": 0}
```

### Example Event Sequence (Complex Task)

```
event: status
data: {"connected": true, "is_processing": false, "goal": null}

event: phase
data: {"type": "phase", "phase": "planning", "is_processing": true, "goal": "Research and summarize topic"}

event: step
data: {"type": "step", "step_num": 1, "total_steps": 3, "description": "Search memory for existing knowledge", "is_processing": true, "goal": "Research and summarize topic"}

event: thought
data: {"type": "thought", "message": "[TOOL] Searching memory...", "is_processing": true, "goal": "Research and summarize topic"}

event: step
data: {"type": "step", "step_num": 2, "total_steps": 3, "description": "Synthesize information", "is_processing": true, "goal": "Research and summarize topic"}

event: thought
data: {"type": "thought", "message": "[OK] delegated: 245 tokens", "is_processing": false, "goal": null}
```

---

## GET /voice/stream

**Purpose:** Stream voice system status updates in real-time. Shows voice activity, transcriptions, and responses.

### Request

```http
GET /voice/stream
```

No request body required.

### Response Headers

```http
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Accel-Buffering: no
```

### Event Types

#### `status`

Voice system status. Sent on connection and on status changes.

```
event: status
data: {"connected": true, "status": "idle", "running": true}
```

**Data Format (Initial):**

| Field     | Type    | Description                               |
|-----------|---------|-------------------------------------------|
| connected | boolean | Always `true` on initial connection       |
| status    | string  | Current voice status (see below)          |
| running   | boolean | Whether voice backend is active           |

**Data Format (Status Change):**

| Field  | Type   | Description         |
|--------|--------|---------------------|
| type   | string | Always `"status"`   |
| status | string | New status value    |

**Status Values:**

| Status    | Description                              |
|-----------|------------------------------------------|
| inactive  | Voice system not started                 |
| idle      | Voice system ready, not recording        |
| listening | Recording user speech                    |
| thinking  | Processing speech / generating response  |
| speaking  | Playing TTS audio                        |

#### `transcription`

User speech transcribed.

```
event: transcription
data: {"type": "transcription", "text": "Hello Luna, how are you today?"}
```

**Data Format:**

| Field | Type   | Description                    |
|-------|--------|--------------------------------|
| type  | string | Always `"transcription"`       |
| text  | string | Transcribed speech text        |

#### `response`

Luna's response ready.

```
event: response
data: {"type": "response", "text": "I'm doing great! How can I help you?"}
```

**Data Format:**

| Field | Type   | Description            |
|-------|--------|------------------------|
| type  | string | Always `"response"`    |
| text  | string | Luna's response text   |

#### `ping`

Keepalive ping. Sent every 10 seconds of inactivity.

```
event: ping
data: {"running": true}
```

**Data Format:**

| Field   | Type    | Description                     |
|---------|---------|--------------------------------|
| running | boolean | Whether voice backend is active |

### Connection Lifecycle

1. **Open:** Client sends GET request, connection established
2. **Initial Status:** Server sends `status` event with voice system state
3. **Events:** Server sends `status`, `transcription`, `response` events as they occur
4. **Keepalive:** Server sends `ping` every 10 seconds of inactivity
5. **Close:** Connection closes when client disconnects (CancelledError)

### Reconnection Behavior

- Client should reconnect on connection drop
- Voice system state is preserved across reconnections
- Client will receive current state on reconnect via `status` event

### Example Event Sequence (Voice Conversation)

```
event: status
data: {"connected": true, "status": "idle", "running": true}

event: status
data: {"type": "status", "status": "listening"}

event: transcription
data: {"type": "transcription", "text": "What's the weather like?"}

event: status
data: {"type": "status", "status": "thinking"}

event: response
data: {"type": "response", "text": "I don't have access to weather data, but I'd be happy to help with something else!"}

event: status
data: {"type": "status", "status": "speaking"}

event: status
data: {"type": "status", "status": "idle"}

event: ping
data: {"running": true}
```

---

## General SSE Notes

### HTTP Response Format

All SSE endpoints follow the standard SSE format:

```
event: <event-type>
data: <json-payload>

```

Each event is terminated by two newlines (`\n\n`).

### Common Response Headers

All streaming endpoints include:

| Header              | Value              | Purpose                          |
|---------------------|--------------------|----------------------------------|
| Content-Type        | text/event-stream  | SSE MIME type                    |
| Cache-Control       | no-cache           | Prevent caching                  |
| Connection          | keep-alive         | Maintain persistent connection   |
| X-Accel-Buffering   | no                 | Disable nginx proxy buffering    |

### Error Handling

| HTTP Status | Condition           | Response                              |
|-------------|---------------------|---------------------------------------|
| 503         | Engine not ready    | `{"detail": "Engine not ready"}`      |
| 504         | Timeout             | `{"detail": "Response timeout..."}`   |

Errors during streaming are sent as SSE events, not HTTP error responses.

### Client Implementation Notes

1. **EventSource API:** Use the browser's `EventSource` API for automatic reconnection
2. **Fetch API:** Use `fetch()` with response body streaming for more control
3. **Timeouts:** Implement client-side timeout handling
4. **Reconnection:** Implement exponential backoff for reconnection attempts
5. **Parsing:** Parse JSON data from each `data:` line

### JavaScript Example

```javascript
// Using EventSource for /thoughts
const eventSource = new EventSource('/thoughts');

eventSource.addEventListener('status', (e) => {
  const data = JSON.parse(e.data);
  console.log('Status:', data);
});

eventSource.addEventListener('thought', (e) => {
  const data = JSON.parse(e.data);
  console.log('Thought:', data.message);
});

eventSource.addEventListener('ping', (e) => {
  console.log('Keepalive received');
});

eventSource.onerror = (e) => {
  console.error('Connection error:', e);
  // EventSource will auto-reconnect
};

// Using fetch for /persona/stream (POST request)
async function streamPersona(message) {
  const response = await fetch('/persona/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message })
  });

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const text = decoder.decode(value);
    const lines = text.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6));
        console.log('Event:', data.type, data);
      }
    }
  }
}
```

---

## Endpoint Summary

| Endpoint           | Method | Events                               | Keepalive | Use Case                    |
|--------------------|--------|--------------------------------------|-----------|----------------------------- |
| /stream            | POST   | token, done, error                   | No        | Simple token streaming       |
| /persona/stream    | POST   | context, token, done, error          | No        | Context-aware streaming      |
| /thoughts          | GET    | status, thought, phase, step, ping   | 15s       | Internal process monitoring  |
| /voice/stream      | GET    | status, transcription, response, ping| 10s       | Voice system monitoring      |
