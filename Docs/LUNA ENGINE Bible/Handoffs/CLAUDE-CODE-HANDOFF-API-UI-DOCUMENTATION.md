# CLAUDE CODE HANDOFF: Luna Bible Parts XV & XVI — API & UI Documentation

**Created:** January 25, 2026  
**Author:** Ahab (via Claude Architect)  
**Execution Mode:** Claude Flow Swarm  
**Priority:** High  
**Depends On:** Bible Audit (completed)

---

## Executive Summary

The Luna Engine Bible covers backend architecture thoroughly but has **zero documentation** for:
- The HTTP/SSE API that clients use to interact with Luna
- The Luna Hub UI (React frontend)

This handoff creates two new Bible chapters:
- **Part XV: API Reference** — Complete endpoint documentation
- **Part XVI: Luna Hub UI** — Frontend architecture and components

---

## Target Locations

**API Source:**
```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/src/luna/api/server.py
```

**Frontend Source:**
```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/frontend/
```

**Output:**
```
/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/Docs/LUNA ENGINE Bible/
├── 15-API-REFERENCE.md
└── 16-LUNA-HUB-UI.md
```

---

## Phase 1: API Audit

### 1.1 Endpoint Extraction

Parse `server.py` and extract all endpoints:

```
For each @app.{method}("{path}") decorator:
  - HTTP method (GET, POST, etc.)
  - Path with parameters
  - Request body schema (from Pydantic model)
  - Response schema (from response_model)
  - Description (from docstring)
  - Query parameters
  - SSE event types (for streaming endpoints)
```

**Output:** `Docs/LUNA ENGINE Bible/Audit/API-ENDPOINT-INVENTORY.md`

### 1.2 Endpoint Categories

Group endpoints by domain:

| Category | Endpoints |
|----------|-----------|
| **Core Interaction** | `/message`, `/stream`, `/persona/stream` |
| **Engine Status** | `/status`, `/health`, `/consciousness` |
| **Memory** | `/memory/nodes`, `/memory/stats`, etc. |
| **Extraction** | `/extraction/trigger`, `/extraction/prune` |
| **History/Hub** | `/hub/session/*`, `/hub/turn/*`, `/hub/search` |
| **Debug** | `/debug/context`, `/debug/personality`, `/debug/conversation-cache` |
| **Voice** | `/voice/start`, `/voice/listen/*`, `/voice/stream` |
| **Tuning** | `/tuning/params/*`, `/tuning/session/*`, `/tuning/eval` |
| **Ring Buffer** | `/api/ring/*` |
| **System** | `/api/system/relaunch`, `/abort`, `/interrupt` |

### 1.3 SSE Event Documentation

For streaming endpoints, document event types:

```
/stream:
  - event: token — Each generated token
  - event: done — Generation complete
  - event: error — Error occurred

/persona/stream:
  - data: {type: "context", ...} — Memory + state before streaming
  - data: {type: "token", ...} — Each token
  - data: {type: "done", ...} — Complete with metadata

/thoughts:
  - event: phase — Current processing phase
  - event: thought — Internal progress message
  - event: status — Status change
  - event: ping — Keepalive

/voice/stream:
  - event: status — Voice state changes
  - event: transcription — User speech transcribed
  - event: response — Luna's response
  - event: ping — Keepalive
```

**Output:** `Docs/LUNA ENGINE Bible/Audit/API-SSE-EVENTS.md`

---

## Phase 2: Frontend Audit

### 2.1 Component Inventory

For each component in `frontend/src/components/`:

```
- Component name
- Props interface
- State management (local, Redux, hooks)
- API endpoints consumed
- Child components
- Key features/responsibilities
```

**Components to audit:**
- `ChatPanel.jsx` — Main conversation interface
- `VoicePanel.jsx` — Voice control (PTT, hands-free)
- `ConsciousnessMonitor.jsx` — Mood, coherence, attention
- `PersonalityMonitorPanel.jsx` — Patch system visibility
- `ContextDebugPanel.jsx` — What Luna "sees"
- `ConversationCache.jsx` — Conversation history view
- `TuningPanel.jsx` — Live parameter adjustment
- `ThoughtStream.jsx` — Internal process visibility
- `EngineStatus.jsx` — Actor health, metrics
- `GlassCard.jsx` — UI primitive
- `GradientOrb.jsx` — Visual element
- `StatusDot.jsx` — Status indicator

**Output:** `Docs/LUNA ENGINE Bible/Audit/UI-COMPONENT-INVENTORY.md`

### 2.2 Hook Inventory

For each hook in `frontend/src/hooks/`:

```
- Hook name
- Purpose
- API endpoints called
- State returned
- Dependencies
```

**Output:** `Docs/LUNA ENGINE Bible/Audit/UI-HOOKS-INVENTORY.md`

### 2.3 State Management Analysis

```
- How is global state managed? (Redux? Context? Local?)
- What state is shared between components?
- How are API responses cached?
- SSE connection management
```

**Output:** `Docs/LUNA ENGINE Bible/Audit/UI-STATE-ANALYSIS.md`

### 2.4 Design System Extraction

```
- Color palette (from Tailwind config + CSS)
- Typography scale
- Spacing system
- Component variants (GlassCard styles, etc.)
- Animation patterns
```

**Output:** `Docs/LUNA ENGINE Bible/Audit/UI-DESIGN-SYSTEM.md`

---

## Phase 3: Write Part XV — API Reference

### Structure

```markdown
# Part XV: API Reference

## 15.1 Overview
- Base URL: http://localhost:8000
- Authentication: None (local only)
- Content-Type: application/json
- Streaming: Server-Sent Events (SSE)

## 15.2 Core Interaction
### POST /message
### POST /stream  
### POST /persona/stream
### POST /abort
### POST /interrupt

## 15.3 Engine Status
### GET /status
### GET /health
### GET /consciousness
### GET /history

## 15.4 Memory Operations
### POST /memory/nodes
### GET /memory/nodes/{node_id}
### GET /memory/nodes
### POST /memory/nodes/{node_id}/access
### POST /memory/nodes/{node_id}/reinforce
### GET /memory/stats

## 15.5 Extraction
### POST /extraction/trigger
### POST /extraction/prune
### GET /extraction/stats
### GET /extraction/history

## 15.6 History Management (Hub API)
### POST /hub/session/create
### POST /hub/session/end
### GET /hub/session/active
### POST /hub/turn/add
### GET /hub/active_window
### GET /hub/active_token_count
### POST /hub/tier/rotate
### GET /hub/tier/oldest_active
### POST /hub/search
### GET /hub/stats

## 15.7 Debug Endpoints
### GET /debug/context
### GET /debug/personality
### GET /debug/conversation-cache

## 15.8 Voice Integration
### POST /voice/start
### POST /voice/stop
### GET /voice/status
### POST /voice/listen/start
### POST /voice/listen/stop
### POST /voice/speak
### GET /voice/stream

## 15.9 Tuning
### GET /tuning/params
### GET /tuning/params/{name}
### POST /tuning/params/{name}
### POST /tuning/param-reset/{name}
### POST /tuning/session/new
### GET /tuning/session
### POST /tuning/session/end
### POST /tuning/eval
### GET /tuning/compare
### GET /tuning/best
### POST /tuning/apply-best
### GET /tuning/sessions

## 15.10 Ring Buffer
### GET /api/ring/status
### POST /api/ring/config
### POST /api/ring/clear

## 15.11 System
### POST /api/system/relaunch

## 15.12 SSE Event Reference
[All streaming event types documented]

## 15.13 Error Handling
[HTTP status codes, error response format]

## 15.14 Examples
[curl examples for common operations]
```

### Documentation Format

For each endpoint:

```markdown
### POST /message

Send a message to Luna and get a response.

**Request Body:**
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| message | string | Yes | User message (1-10000 chars) |
| timeout | float | No | Response timeout in seconds (1-120, default: 30) |
| stream | bool | No | Use streaming mode (default: false) |

**Response:**
| Field | Type | Description |
|-------|------|-------------|
| text | string | Luna's response |
| model | string | Model used for generation |
| input_tokens | int | Tokens in prompt |
| output_tokens | int | Tokens generated |
| latency_ms | float | Response latency |
| delegated | bool | True if delegated to cloud |
| local | bool | True if local inference |
| fallback | bool | True if fallback was used |

**Example:**
\`\`\`bash
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello Luna"}'
\`\`\`

**Response:**
\`\`\`json
{
  "text": "Hey! What's on your mind?",
  "model": "qwen2.5-3b",
  "input_tokens": 1250,
  "output_tokens": 12,
  "latency_ms": 340.5,
  "delegated": false,
  "local": true,
  "fallback": false
}
\`\`\`
```

---

## Phase 4: Write Part XVI — Luna Hub UI

### Structure

```markdown
# Part XVI: Luna Hub UI

## 16.1 Overview
- Stack: React 18 + Vite + Tailwind CSS
- State: [Redux/Context/Local — determined by audit]
- API: FastAPI backend on localhost:8000
- Real-time: SSE for streaming

## 16.2 Architecture
### Component Hierarchy
### Data Flow
### API Integration Pattern

## 16.3 Core Components
### ChatPanel
[Props, state, features, screenshots/diagrams]

### VoicePanel
[Push-to-talk, hands-free, status indicators]

### EngineStatus
[Actor health, metrics display]

## 16.4 Monitoring Components
### ConsciousnessMonitor
### PersonalityMonitorPanel
### ContextDebugPanel
### ConversationCache
### ThoughtStream

## 16.5 Developer Tools
### TuningPanel
[Parameter adjustment, sessions, evaluation]

## 16.6 Design System
### Color Palette
### Typography
### Spacing
### Glass Morphism (GlassCard)
### Animations

## 16.7 Hooks Reference
### useEngine()
### useVoice()
### useConsciousness()
### useTuning()
[etc.]

## 16.8 SSE Integration
### Connection Management
### Event Handling
### Reconnection Strategy

## 16.9 UX Patterns
### Loading States
### Error Handling
### Optimistic Updates
### Real-time Updates

## 16.10 Development
### Running Locally
### Environment Variables
### Build & Deploy
```

---

## Swarm Configuration

### Phase 1 & 2: Audit (Parallel)

```yaml
agents:
  - name: "api-audit-agent"
    task: "Extract all endpoints from server.py"
    outputs:
      - "Audit/API-ENDPOINT-INVENTORY.md"
      - "Audit/API-SSE-EVENTS.md"
    context_files:
      - "src/luna/api/server.py"

  - name: "ui-component-agent"
    task: "Inventory all React components"
    outputs:
      - "Audit/UI-COMPONENT-INVENTORY.md"
    context_files:
      - "frontend/src/components/*.jsx"
      - "frontend/src/App.jsx"

  - name: "ui-hooks-agent"
    task: "Inventory all React hooks"
    outputs:
      - "Audit/UI-HOOKS-INVENTORY.md"
    context_files:
      - "frontend/src/hooks/*.js"

  - name: "ui-design-agent"
    task: "Extract design system"
    outputs:
      - "Audit/UI-DESIGN-SYSTEM.md"
      - "Audit/UI-STATE-ANALYSIS.md"
    context_files:
      - "frontend/src/index.css"
      - "frontend/tailwind.config.js"
      - "frontend/src/components/GlassCard.jsx"
```

### Phase 3 & 4: Documentation (Sequential)

```yaml
agents:
  - name: "part-15-agent"
    task: "Write Part XV: API Reference"
    depends_on: ["api-audit-agent"]
    outputs:
      - "15-API-REFERENCE.md"
    context_files:
      - "Audit/API-ENDPOINT-INVENTORY.md"
      - "Audit/API-SSE-EVENTS.md"
      - "src/luna/api/server.py"

  - name: "part-16-agent"
    task: "Write Part XVI: Luna Hub UI"
    depends_on: ["ui-component-agent", "ui-hooks-agent", "ui-design-agent"]
    outputs:
      - "16-LUNA-HUB-UI.md"
    context_files:
      - "Audit/UI-COMPONENT-INVENTORY.md"
      - "Audit/UI-HOOKS-INVENTORY.md"
      - "Audit/UI-DESIGN-SYSTEM.md"
      - "Audit/UI-STATE-ANALYSIS.md"
```

### Phase 5: Update TOC

```yaml
agents:
  - name: "toc-update-agent"
    task: "Update Table of Contents with Parts XV and XVI"
    depends_on: ["part-15-agent", "part-16-agent"]
    outputs:
      - "00-TABLE-OF-CONTENTS.md"
```

---

## Execution

```bash
cd /Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root
claude-flow swarm --config Docs/LUNA\ ENGINE\ Bible/Handoffs/bible-api-ui-swarm.yaml
```

---

## Success Criteria

### Part XV: API Reference
- [ ] All 50+ endpoints documented
- [ ] Request/response schemas for each
- [ ] SSE event types documented
- [ ] curl examples for key endpoints
- [ ] Error codes documented

### Part XVI: Luna Hub UI
- [ ] All 12 components documented
- [ ] All hooks documented
- [ ] Design system extracted
- [ ] State management explained
- [ ] Data flow diagrams included

### General
- [ ] TOC updated with new chapters
- [ ] Audit documents archived
- [ ] Version bumped to 2.4.0

---

## Files Created

```
Docs/LUNA ENGINE Bible/
├── Audit/
│   ├── API-ENDPOINT-INVENTORY.md      # NEW
│   ├── API-SSE-EVENTS.md              # NEW
│   ├── UI-COMPONENT-INVENTORY.md      # NEW
│   ├── UI-HOOKS-INVENTORY.md          # NEW
│   ├── UI-DESIGN-SYSTEM.md            # NEW
│   └── UI-STATE-ANALYSIS.md           # NEW
├── 15-API-REFERENCE.md                # NEW
├── 16-LUNA-HUB-UI.md                  # NEW
└── 00-TABLE-OF-CONTENTS.md            # UPDATED
```

---

## Notes for Claude Code

1. **API extraction is mechanical** — Parse decorators, Pydantic models, docstrings
2. **UI audit requires understanding React patterns** — Props, hooks, state
3. **Include actual code snippets** — From the codebase, not hypothetical
4. **Design system from Tailwind** — Extract from config + component usage
5. **SSE is critical** — Document all event types, connection patterns

---

*The API is Luna's voice to the world. The UI is how the world sees Luna.*

— Handoff prepared by Claude Architect, January 25, 2026
