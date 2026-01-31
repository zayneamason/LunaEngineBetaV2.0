# AUDIT-FRONTEND.md

**Generated:** 2026-01-30
**Agent:** Frontend Auditor
**Phase:** 1.6

## Summary
- Components: 20
- Custom hooks: 5
- External deps: 3 (react, react-dom, recharts)
- Build tooling: Vite + Tailwind CSS
- Lines of code: ~4,500+ (components + hooks)

---

## Component Hierarchy

```
App.jsx (LunaHub)
|
+-- GradientOrb (x3) [Background decorative orbs]
|
+-- Header
|   +-- StatusDot
|   +-- [Mode toggle buttons: Tuning, Personality, Debug]
|
+-- ChatPanel
|   +-- GlassCard
|   +-- LunaOrb (uses useOrbState, useOrbFollow)
|   +-- VoiceTuningPanel (modal)
|   +-- OrbSettingsPanel (modal)
|
+-- VoicePanel
|   +-- GlassCard
|   +-- (uses useVoice internally or from parent)
|
+-- EngineStatus
|   +-- GlassCard
|   +-- StatusDot (multiple)
|
+-- ConversationCache
|   +-- GlassCard
|
+-- ThoughtStream
|   +-- GlassCard
|
+-- ConsciousnessMonitor
|   +-- GlassCard
|   +-- StatusDot
|
+-- ContextDebugPanel (modal)
|   +-- GlassCard
|
+-- PersonalityMonitorPanel (modal)
|   +-- GlassCard
|   +-- PieChart, BarChart (recharts)
|   +-- StatCard, MaintenanceStat, PatchCard
|
+-- TuningPanel (slide-out panel)
|   +-- GlassCard
|   +-- ParamCard, ScoreBar
|
Footer
```

### Unused/Orphan Components (exported but not used in main App)
- `LunaAutoTuner` - Full-featured auto-tuning modal with optimization, exported but not rendered
- `MemoryEconomyPanel` - Memory economy stats panel, exported but not rendered
- `LLMProviderDropdown` - Provider switcher dropdown, exported but not rendered

---

## Components Reference

### Core Layout Components

| Component | File | Purpose | Props |
|-----------|------|---------|-------|
| `GlassCard` | GlassCard.jsx | Glassmorphism container with hover effects | `children, className, onClick, hover, dashed, padding` |
| `GradientOrb` | GradientOrb.jsx | Decorative background gradient orb | `className, color1, color2, delay` |
| `StatusDot` | StatusDot.jsx | Status indicator dot with color states | `status, size` |

### Chat Components

| Component | File | Purpose | Props |
|-----------|------|---------|-------|
| `ChatPanel` | ChatPanel.jsx | Main chat interface with message display, input, slash commands | `onSend, isLoading, messages, debugKeywords` |
| `LunaOrb` | LunaOrb.jsx | Animated orb representing Luna's state | `state, size, brightness, colorOverride, showGlow, chatContainerRef, messagesEndRef` |

### Voice Components

| Component | File | Purpose | Props |
|-----------|------|---------|-------|
| `VoicePanel` | VoicePanel.jsx | Voice interaction UI with push-to-talk | `voiceHook` |
| `VoiceTuningPanel` | VoiceTuningPanel.jsx | Voice parameter tuning modal | `data, onUpdate, onClose` |

### Debug/Monitor Components

| Component | File | Purpose | Props |
|-----------|------|---------|-------|
| `ContextDebugPanel` | ContextDebugPanel.jsx | Shows Luna's context window contents | `isOpen, onClose, highlightKeywords` |
| `ConversationCache` | ConversationCache.jsx | Displays conversation memory buffer | `isConnected` |
| `ThoughtStream` | ThoughtStream.jsx | Live thought stream via SSE | `apiUrl` |
| `ConsciousnessMonitor` | ConsciousnessMonitor.jsx | Displays consciousness state | `consciousness` |
| `PersonalityMonitorPanel` | PersonalityMonitorPanel.jsx | Personality patches visualization | `isOpen, onClose` |

### Engine/Tuning Components

| Component | File | Purpose | Props |
|-----------|------|---------|-------|
| `EngineStatus` | EngineStatus.jsx | Engine status with stats and relaunch | `status, isConnected, onRelaunch` |
| `TuningPanel` | TuningPanel.jsx | Parameter tuning slide-out panel | `isOpen, onClose` |
| `LunaAutoTuner` | LunaAutoTuner.jsx | Auto-optimization modal (unused) | `isOpen, onClose` |

### Settings Components

| Component | File | Purpose | Props |
|-----------|------|---------|-------|
| `OrbSettingsPanel` | OrbSettingsPanel.jsx | Orb visual settings modal | `data, onUpdate, onClose` |
| `LLMProviderDropdown` | LLMProviderDropdown.jsx | LLM provider switcher (unused) | `className` |
| `MemoryEconomyPanel` | MemoryEconomyPanel.jsx | Memory economy stats (unused) | none |

---

## Custom Hooks Reference

### useChat (`/hooks/useChat.js`)
**Purpose:** Manages streaming chat with Luna via /persona/stream endpoint

**Parameters:** None

**Return Value:**
```javascript
{
  messages: Array<{id, role, content, streaming, metadata, tokens, latency, delegated, local}>,
  context: Object | null,  // Context received before tokens
  isStreaming: boolean,
  isLoading: boolean,
  error: string | null,
  send: (text: string, context?: Object) => Promise<void>,
  stop: () => void,
  clear: () => void
}
```

**Features:**
- Slash command parsing and execution (20+ commands)
- Local commands: `/animate`, `/orb`, `/orb-test`, `/restart-frontend`
- SSE streaming with token accumulation
- Context-first streaming (context arrives before tokens)

---

### useLunaAPI (`/hooks/useLunaAPI.js`)
**Purpose:** Core API client for Luna Engine backend

**Parameters:** None

**Return Value:**
```javascript
{
  status: Object | null,
  consciousness: Object | null,
  isConnected: boolean,
  isLoading: boolean,
  error: string | null,
  sendMessage: (message: string) => Promise<Object>,
  streamMessage: (message, onToken, onComplete) => Promise<void>,
  streamPersona: (message, callbacks) => Promise<void>,
  abort: () => Promise<void>,
  relaunchSystem: () => Promise<Object>,
  refresh: () => Promise<void>
}
```

**Polling:** Status and consciousness polled every 2 seconds

---

### useVoice (`/hooks/useVoice.js`)
**Purpose:** Voice interaction management with SSE status updates

**Parameters:** None

**Return Value:**
```javascript
{
  voiceState: 'inactive' | 'idle' | 'listening' | 'thinking' | 'speaking',
  isRunning: boolean,
  transcription: string | null,
  response: string | null,
  error: string | null,
  handsFree: boolean,
  startVoice: (handsFreeMode?: boolean) => Promise<void>,
  stopVoice: () => Promise<void>,
  startListening: () => Promise<void>,
  stopListening: () => Promise<Object>,
  speakResponse: (text: string) => Promise<Object>,
  // Derived states
  isListening: boolean,
  isThinking: boolean,
  isSpeaking: boolean,
  isIdle: boolean,
  isInactive: boolean
}
```

**SSE Events:** Listens to `/voice/stream` for status, transcription, response, ping

---

### useOrbState (`/hooks/useOrbState.js`)
**Purpose:** WebSocket connection for Luna Orb state updates

**Parameters:**
- `wsUrl` (string, default: `'ws://localhost:8000/ws/orb'`)

**Return Value:**
```javascript
{
  orbState: {
    animation: string,  // 'idle', 'pulse', 'spin', etc.
    color: string | null,
    brightness: number,
    source: string  // 'default', 'websocket', 'timeout'
  },
  isConnected: boolean,
  error: string | null
}
```

**Auto-idle:** Returns to idle state after 2 seconds of non-idle animation

---

### useOrbFollow (`/hooks/useOrbFollow.js`)
**Purpose:** Spring physics follow behavior for Luna Orb

**Parameters:**
- `chatContainerRef` - Ref to scrollable chat container
- `messagesEndRef` - Ref to end-of-messages marker
- `orbRef` - Ref to orb DOM element (for direct manipulation)

**Return Value:** None (updates DOM directly via requestAnimationFrame)

**Configuration:** Uses `/config/orbFollow.js`:
```javascript
{
  followSpeed: 0.08,
  deceleration: 0.92,
  floatAmplitudeX: 8,
  floatAmplitudeY: 12,
  floatSpeedX: 0.0015,
  floatSpeedY: 0.0023,
  marginFromEdge: 40,
  verticalOffset: 0,
  minY: 100,
  maxYFromBottom: 150
}
```

---

## State Management

### Pattern: Props + Local State + Custom Hooks

The application uses a **simple, flat state architecture**:

1. **Root State (App.jsx):**
   - `debugMode`, `personalityMode`, `tuningMode` - UI panel toggles
   - `debugKeywords` - Keywords from debug context

2. **Hook-Owned State:**
   - `useLunaAPI` - connection state, status, consciousness
   - `useChat` - messages, streaming state, context
   - `useVoice` - voice state, transcription, responses
   - `useOrbState` - orb animation state via WebSocket

3. **Component-Local State:**
   - Each panel manages its own internal state
   - No global state store (no Redux, Zustand, etc.)

### Data Flow
```
Backend API/WebSocket/SSE
         |
    Custom Hooks (useLunaAPI, useChat, useVoice, useOrbState)
         |
    App.jsx (LunaHub) - Root component
         |
    Child Components (via props)
```

### Persistence
- Chat messages persisted to `localStorage` under key `luna_chat_messages`
- No other client-side persistence

---

## SSE/WebSocket Integration

### SSE Endpoints

| Endpoint | Component/Hook | Events | Purpose |
|----------|----------------|--------|---------|
| `/voice/stream` | useVoice | status, transcription, response, ping | Voice status updates |
| `/thoughts` | ThoughtStream | status, thought, ping | Luna's thought stream |

### WebSocket Endpoints

| Endpoint | Component/Hook | Purpose |
|----------|----------------|---------|
| `ws://localhost:8000/ws/orb` | useOrbState | Orb animation state updates |

### REST Polling

| Endpoint | Component | Interval | Purpose |
|----------|-----------|----------|---------|
| `/health`, `/status`, `/consciousness` | useLunaAPI | 2000ms | Connection/status polling |
| `/debug/context` | App.jsx | 3000ms | Debug keywords (when debug mode on) |
| `/debug/context` | ContextDebugPanel | 2000ms | Full context data |
| `/debug/conversation-cache` | ConversationCache | 2000ms | Conversation cache |
| `/debug/personality` | PersonalityMonitorPanel | 3000ms | Personality data |
| `/clusters/stats` | MemoryEconomyPanel | 30000ms | Cluster stats |

---

## Subscription Cleanup Audit

### useEffect Cleanup Analysis

| Hook/Component | Subscription Type | Cleanup | Status |
|----------------|-------------------|---------|--------|
| **useLunaAPI** | setInterval (2s polling) | `clearInterval` in cleanup | OK |
| **useVoice** | EventSource (SSE) | `eventSource.close()` | OK - with reconnect logic |
| **useOrbState** | WebSocket | `ws.close()`, `clearTimeout` for reconnect/idle | OK |
| **useOrbFollow** | requestAnimationFrame | `cancelAnimationFrame` | OK |
| **useOrbFollow** | scroll/resize listeners | `removeEventListener` | OK |
| **ThoughtStream** | EventSource (SSE) | `eventSource.close()` | OK |
| **App.jsx** | setInterval (debug context) | `clearInterval` in cleanup | OK |
| **ContextDebugPanel** | setInterval (2s polling) | `clearInterval` in cleanup | OK |
| **ConversationCache** | setInterval (2s polling) | `clearInterval` in cleanup | OK |
| **PersonalityMonitorPanel** | setInterval (3s polling) | `clearInterval` in cleanup | OK |
| **MemoryEconomyPanel** | setInterval (30s polling) | `clearInterval` in cleanup | OK |
| **VoicePanel** | setInterval (timer, audio level) | `clearInterval` in cleanup | OK |
| **ChatPanel** | setTimeout (animation override) | `clearTimeout` on new timeout | OK |
| **LLMProviderDropdown** | None | N/A | OK |

### Potential Memory Leak Concerns

1. **useVoice SSE Reconnection:** The reconnect logic uses `setTimeout` with 3s delay. If component unmounts during reconnect delay, the timeout may fire after cleanup. **Low risk** - only logs warning.

2. **VoicePanel lastAction Timeout:** Uses `setTimeout` with 5s delay. Cleanup exists. **OK**

3. **TuningPanel setTimeout:** Uses `setTimeout` for relaunch state reset (10s). No cleanup on unmount. **Minor issue** - state update after unmount.

4. **EngineStatus setTimeout:** Same pattern as TuningPanel for relaunch state. **Minor issue**

---

## Styling Approach

### Technology Stack
- **Tailwind CSS 3.4.1** - Primary styling via utility classes
- **Custom CSS** (`/index.css`) - Animations, scrollbar, glass morphism

### CSS Architecture

1. **Tailwind Utilities** - Layout, spacing, colors, typography
2. **Custom `.glass` class** - Glassmorphism effect with backdrop-filter
3. **Debug mode classes** - `.debug-keyword`, `.debug-context-box`, `.debug-ring-*`
4. **Orb animations** - 10+ keyframe animations for Luna Orb states

### Key Custom Animations (index.css)
```css
@keyframes orb-idle      /* 4s gentle floating */
@keyframes orb-pulse     /* 0.8s scale pulse */
@keyframes orb-pulse-fast/* 0.4s fast pulse */
@keyframes orb-spin      /* 2s rotation */
@keyframes orb-spin-fast /* 0.8s fast rotation */
@keyframes orb-flicker   /* 1.5s opacity flicker */
@keyframes orb-wobble    /* 1s playful wobble */
@keyframes orb-drift     /* 6s slow drift */
@keyframes orb-orbit     /* 3s orbital movement */
@keyframes orb-glow-pulse/* 2s glow with scale */
@keyframes orb-split     /* 2s split/merge */
```

### Inline Styles
Some components use inline styles for:
- Dynamic values (e.g., slider accent color)
- Modal positioning (fixed centering)
- VoiceTuningPanel and OrbSettingsPanel use inline styles extensively

---

## Dependencies

### Production Dependencies (`dependencies`)

| Package | Version | Purpose |
|---------|---------|---------|
| `react` | ^18.2.0 | Core React library |
| `react-dom` | ^18.2.0 | React DOM renderer |
| `recharts` | ^3.6.0 | Charts for PersonalityMonitorPanel, LunaAutoTuner |

### Development Dependencies (`devDependencies`)

| Package | Version | Purpose |
|---------|---------|---------|
| `@types/react` | ^18.2.66 | TypeScript types (dev only) |
| `@types/react-dom` | ^18.2.22 | TypeScript types (dev only) |
| `@vitejs/plugin-react` | ^4.2.1 | Vite React plugin |
| `autoprefixer` | ^10.4.18 | PostCSS autoprefixer |
| `postcss` | ^8.4.35 | CSS processing |
| `tailwindcss` | ^3.4.1 | Utility-first CSS framework |
| `vite` | ^5.2.0 | Build tool and dev server |

### Notable Absences
- No state management library (Redux, Zustand, etc.)
- No routing library (React Router)
- No form library (React Hook Form, Formik)
- No testing libraries
- No type checking (TypeScript files are types only, code is JavaScript)

---

## API Endpoints Used

### Chat & Messaging
- `POST /persona/stream` - Streaming chat (context-first)
- `POST /message` - Non-streaming message
- `POST /stream` - Legacy streaming
- `POST /abort` - Cancel generation

### Status & Health
- `GET /health` - Health check
- `GET /status` - Engine status
- `GET /consciousness` - Consciousness state

### Voice
- `GET /voice/status` - Voice system status
- `GET /voice/stream` - SSE voice status stream
- `POST /voice/start` - Start voice system
- `POST /voice/stop` - Stop voice system
- `POST /voice/listen/start` - Start recording
- `POST /voice/listen/stop` - Stop recording
- `POST /voice/speak` - TTS synthesis

### Debug
- `GET /debug/context` - Context window contents
- `GET /debug/conversation-cache` - Conversation buffer
- `GET /debug/personality` - Personality patches

### Tuning
- `GET /tuning/params` - List parameters
- `GET /tuning/params/:name` - Get parameter
- `POST /tuning/params/:name` - Set parameter
- `POST /tuning/param-reset/:name` - Reset parameter
- `GET /tuning/session` - Session status
- `POST /tuning/session/new` - Start session
- `POST /tuning/session/end` - End session
- `POST /tuning/eval` - Run evaluation
- `POST /tuning/apply-best` - Apply best params

### System
- `POST /api/system/relaunch` - Restart engine
- `GET /api/ring/status` - Ring buffer status
- `POST /api/ring/config` - Configure ring size
- `POST /api/ring/clear` - Clear ring buffer

### Slash Commands
- `GET /slash/health`, `/slash/stats`, `/slash/recent`, etc.
- `POST /slash/voice-tuning`, `/slash/orb-settings`

### LLM Providers (LLMProviderDropdown)
- `GET /llm/providers` - List providers
- `GET /llm/current` - Current provider
- `POST /llm/provider` - Switch provider

### Clusters (MemoryEconomyPanel)
- `GET /clusters/stats` - Cluster statistics

---

## Recommendations

### High Priority
1. **Add useEffect cleanup for setTimeout in TuningPanel and EngineStatus** - Prevents state updates after unmount

### Medium Priority
2. **Consider extracting API base URL to config** - Currently hardcoded as `'http://localhost:8000'`
3. **Add error boundaries** - No error boundaries present for graceful failure handling
4. **Consider TypeScript migration** - Types exist in devDeps but code is JavaScript

### Low Priority
5. **Remove unused components from bundle** - LunaAutoTuner, MemoryEconomyPanel, LLMProviderDropdown are exported but never used
6. **Consolidate inline styles** - VoiceTuningPanel, OrbSettingsPanel could use Tailwind
7. **Add loading/skeleton states** - Some components show minimal loading feedback
8. **Consider code splitting** - Large modal components could be lazy-loaded
