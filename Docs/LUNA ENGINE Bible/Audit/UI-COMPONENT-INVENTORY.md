# Luna Engine UI Component Inventory

**Audit Date:** 2026-01-25
**Frontend Path:** `/frontend/src/`
**Framework:** React (JSX)
**Total Components:** 12 + App.jsx

---

## Table of Contents

1. [App.jsx (Main Container)](#appjsx-main-container)
2. [ChatPanel.jsx](#chatpaneljsx)
3. [VoicePanel.jsx](#voicepaneljsx)
4. [ConsciousnessMonitor.jsx](#consciousnessmonitorjsx)
5. [PersonalityMonitorPanel.jsx](#personalitymonitorpaneljsx)
6. [ContextDebugPanel.jsx](#contextdebugpaneljsx)
7. [ConversationCache.jsx](#conversationcachejsx)
8. [TuningPanel.jsx](#tuningpaneljsx)
9. [ThoughtStream.jsx](#thoughtstreamjsx)
10. [EngineStatus.jsx](#enginestatusjsx)
11. [GlassCard.jsx](#glasscardjsx)
12. [GradientOrb.jsx](#gradientorbjsx)
13. [StatusDot.jsx](#statusdotjsx)
14. [Custom Hooks](#custom-hooks)
15. [API Endpoint Summary](#api-endpoint-summary)

---

## App.jsx (Main Container)

**File:** `/frontend/src/App.jsx`
**Component Name:** `LunaHub`
**Lines:** 274

### Props Interface
None (root component)

### Internal State
| State Variable | Type | Description |
|----------------|------|-------------|
| `debugMode` | `boolean` | Controls ContextDebugPanel visibility |
| `debugKeywords` | `string[]` | Keywords for highlighting in chat |
| `personalityMode` | `boolean` | Controls PersonalityMonitorPanel visibility |
| `tuningMode` | `boolean` | Controls TuningPanel visibility |

### Hooks Used
| Hook | Source | Purpose |
|------|--------|---------|
| `useState` | React | Local UI state |
| `useEffect` | React | Debug context polling, localStorage persistence, voice TTS |
| `useRef` | React | Track last spoken message ID |
| `useLunaAPI` | Custom | Engine status, consciousness, connection |
| `useChat` | Custom | Streaming chat with context-first |
| `useVoice` | Custom | Voice interaction state |

### API Endpoints Called
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /debug/context` | Polling (3s) | Fetch keywords when debug mode on |

### Child Components Rendered
- `GradientOrb` (x3) - Background visual elements
- `ChatPanel` - Main conversation interface
- `VoicePanel` - Voice controls
- `EngineStatus` - Actor health display
- `ConversationCache` - Memory view
- `ThoughtStream` - Internal process stream
- `ConsciousnessMonitor` - Mood/coherence
- `ContextDebugPanel` - Debug overlay
- `PersonalityMonitorPanel` - Patch system overlay
- `TuningPanel` - Parameter adjustment slide-out
- `StatusDot` - Connection indicator

### Key Responsibilities
1. Root layout with glassmorphism aesthetic
2. Toggle controls for debug/personality/tuning modes
3. Chat message persistence to localStorage
4. Voice TTS integration (speaks completed responses)
5. Consciousness refresh after responses
6. Error banner display
7. Header/footer with branding

### Notable Patterns
- **LocalStorage persistence:** Messages saved with key `luna_chat_messages`
- **useRef for dedup:** `lastSpokenMsgId` prevents speaking same message twice
- **Polling with cleanup:** Debug context polled every 3s with interval cleanup
- **Parallel effects:** Multiple useEffect hooks for separation of concerns

---

## ChatPanel.jsx

**File:** `/frontend/src/components/ChatPanel.jsx`
**Lines:** 158

### Props Interface
```typescript
{
  onSend: (text: string) => void,     // Callback when user sends message
  isLoading: boolean,                  // Shows loading indicator
  messages?: Message[],                // Array of chat messages
  debugKeywords?: string[]             // Keywords to highlight
}

interface Message {
  role: 'user' | 'assistant',
  content: string,
  model?: string,
  delegated?: boolean,
  local?: boolean,
  fallback?: boolean,
  tokens?: number,
  latency?: number
}
```

### Internal State
| State Variable | Type | Description |
|----------------|------|-------------|
| `input` | `string` | Current input field value |

### Hooks Used
| Hook | Source | Purpose |
|------|--------|---------|
| `useState` | React | Input field state |
| `useRef` | React | Auto-scroll, input focus |
| `useEffect` | React | Scroll to bottom on new messages |

### API Endpoints Called
None (receives data via props)

### Child Components Rendered
- `GlassCard` - Container wrapper

### Key Responsibilities
1. Display conversation messages with role-based styling
2. User input form with Enter key submit
3. Loading indicator (animated dots)
4. Keyword highlighting in debug mode
5. Message metadata display (delegated/local/cloud, tokens, latency)

### Notable Patterns
- **Keyword highlighting:** `highlightKeywords()` function wraps matched keywords in styled spans
- **Auto-scroll:** `messagesEndRef.scrollIntoView({ behavior: 'smooth' })`
- **Shift+Enter handling:** Enter submits, Shift+Enter allows newlines
- **Disabled state:** Input disabled during loading

---

## VoicePanel.jsx

**File:** `/frontend/src/components/VoicePanel.jsx`
**Lines:** 432

### Props Interface
```typescript
{
  voiceHook?: UseVoiceReturn  // Optional shared voice hook from parent
}
```

### Internal State
| State Variable | Type | Description |
|----------------|------|-------------|
| `isHolding` | `boolean` | Push-to-talk button held |
| `lastAction` | `object | null` | Last action result for feedback |
| `recordingDuration` | `number` | Seconds recording |
| `audioLevel` | `number` | Simulated audio level (0-1) |
| `wantHandsFree` | `boolean` | Preferred mode (default true) |

### Hooks Used
| Hook | Source | Purpose |
|------|--------|---------|
| `useState` | React | Local UI state |
| `useCallback` | React | Memoized handlers |
| `useRef` | React | Timers for recording duration |
| `useEffect` | React | Timer management, action feedback timeout |
| `useVoice` | Custom | Voice state machine |

### API Endpoints Called
Via `useVoice` hook:
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `POST /voice/start` | On toggle | Start voice system |
| `POST /voice/stop` | On toggle | Stop voice system |
| `POST /voice/listen/start` | On mic down | Start recording |
| `POST /voice/listen/stop` | On mic up | Stop recording, get transcription |
| `GET /voice/stream` | SSE | Real-time status updates |

### Child Components Rendered
- `GlassCard` - Container wrapper

### Key Responsibilities
1. Voice system start/stop toggle
2. Hands-free vs Push-to-talk mode toggle
3. Visual status indicator with pulse animations
4. Push-to-talk button with mouse/touch events
5. Recording duration display
6. Audio level visualization (simulated)
7. Transcription and response display
8. Debug info panel

### Notable Patterns
- **State machine:** Uses `VoiceState` enum (INACTIVE, IDLE, LISTENING, THINKING, SPEAKING)
- **Touch support:** Handles both mouse and touch events for PTT
- **Simulated audio levels:** Random values for visual feedback
- **Status config object:** Maps states to colors, icons, labels
- **Action feedback:** Shows success/no_speech/error with duration

---

## ConsciousnessMonitor.jsx

**File:** `/frontend/src/components/ConsciousnessMonitor.jsx`
**Lines:** 126

### Props Interface
```typescript
{
  consciousness?: {
    mood?: string,
    coherence?: number,           // 0-1
    attention_topics?: number,
    focused_topics?: { name: string, weight: number }[],
    top_traits?: [string, number][],
    tick_count?: number
  }
}
```

### Internal State
None

### Hooks Used
None (pure presentational component)

### API Endpoints Called
None (receives data via props from `useLunaAPI`)

### Child Components Rendered
- `GlassCard` - Container wrapper
- `StatusDot` - Mood indicator

### Key Responsibilities
1. Display current mood with status dot
2. Coherence progress bar (0-100%)
3. Active attention topics with weight bars
4. Top personality traits with emoji indicators
5. Tick count display

### Notable Patterns
- **Null handling:** Returns loading state if no consciousness data
- **Trait emoji map:** Maps trait names to ASCII/emoji symbols
- **Destructuring with defaults:** Graceful handling of missing fields

---

## PersonalityMonitorPanel.jsx

**File:** `/frontend/src/components/PersonalityMonitorPanel.jsx`
**Lines:** 553

### Props Interface
```typescript
{
  isOpen: boolean,
  onClose: () => void
}
```

### Internal State
| State Variable | Type | Description |
|----------------|------|-------------|
| `data` | `object | null` | Personality data from API |
| `error` | `string | null` | Error message |
| `isLoading` | `boolean` | Loading state |
| `selectedPatch` | `object | null` | Currently expanded patch |
| `activeTab` | `string` | Current tab ('overview', 'patches', 'maintenance') |

### Hooks Used
| Hook | Source | Purpose |
|------|--------|---------|
| `useState` | React | Local state |
| `useEffect` | React | Data polling when open |
| `useCallback` | React | Memoized fetch function |

### API Endpoints Called
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /debug/personality` | Polling (3s) | Fetch personality patches and stats |

### Child Components Rendered
- `GlassCard` - Container wrapper
- `PieChart`, `BarChart` (recharts) - Data visualization
- `StatCard` - Quick stats
- `MaintenanceStat` - Maintenance info
- `PatchCard` - Individual patch display

### Key Responsibilities
1. Modal overlay for personality monitoring
2. Three tabs: Overview, Patches, Maintenance
3. Pie chart for topic distribution
4. Bar chart for lock-in state distribution
5. Patch list with expandable details
6. Session reflection stats
7. Bootstrap status indicator

### Notable Patterns
- **Recharts integration:** Uses PieChart, BarChart, Tooltip, Legend
- **Color maps:** `TOPIC_COLORS`, `LOCKIN_COLORS`, `MOOD_INDICATORS`
- **Nested components:** StatCard, MaintenanceStat, PatchCard defined inline
- **Click-to-expand:** Patches toggle expanded state on click

---

## ContextDebugPanel.jsx

**File:** `/frontend/src/components/ContextDebugPanel.jsx`
**Lines:** 282

### Props Interface
```typescript
{
  isOpen: boolean,
  onClose: () => void,
  highlightKeywords?: string[]  // Keywords to highlight in content
}
```

### Internal State
| State Variable | Type | Description |
|----------------|------|-------------|
| `contextData` | `object | null` | Context window data |
| `error` | `string | null` | Error message |
| `isLoading` | `boolean` | Loading state |
| `selectedRing` | `string` | Ring filter ('ALL', 'CORE', etc.) |
| `expandedItems` | `Set<string>` | Set of expanded item IDs |

### Hooks Used
| Hook | Source | Purpose |
|------|--------|---------|
| `useState` | React | Local state |
| `useEffect` | React | Data polling when open |
| `useCallback` | React | Memoized fetch function |

### API Endpoints Called
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /debug/context` | Polling (2s) | Fetch context window items |

### Child Components Rendered
- `GlassCard` - Container wrapper

### Key Responsibilities
1. Modal overlay for context debugging
2. Stats bar (turn, tokens, items)
3. Ring filter buttons (ALL, CORE, INNER, MIDDLE, OUTER)
4. Keywords display bar
5. Context items with expandable content
6. Keyword highlighting in expanded content
7. TTL and relevance display per item

### Notable Patterns
- **Ring colors:** `RING_COLORS` object maps rings to border/bg/text classes
- **Source icons:** `SOURCE_ICONS` object maps sources to emojis
- **Set for expansion:** Uses Set to track multiple expanded items
- **Highlight function:** `highlightText()` wraps keywords in styled spans

---

## ConversationCache.jsx

**File:** `/frontend/src/components/ConversationCache.jsx`
**Lines:** 182

### Props Interface
```typescript
{
  isConnected: boolean  // Whether API is connected
}
```

### Internal State
| State Variable | Type | Description |
|----------------|------|-------------|
| `cache` | `object | null` | Cache data from API |
| `isLoading` | `boolean` | Loading state |
| `error` | `string | null` | Error message |
| `isExpanded` | `boolean` | Whether panel is expanded |

### Hooks Used
| Hook | Source | Purpose |
|------|--------|---------|
| `useState` | React | Local state |
| `useEffect` | React | Data polling when connected |
| `useCallback` | React | Memoized fetch function |

### API Endpoints Called
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /debug/conversation-cache` | Polling (2s) | Fetch cached messages |

### Child Components Rendered
- `GlassCard` - Container wrapper

### Key Responsibilities
1. Collapsible panel showing Luna's conversation memory
2. Header with message count and usage bar
3. Expanded view with stats (messages, tokens, max turns)
4. Message list with role-based styling
5. Age indicator per message

### Notable Patterns
- **Click-to-expand header:** Header toggles expanded state
- **Conditional render:** Returns null if not connected
- **Usage calculation:** `(itemCount / (maxTurns * 2)) * 100`
- **line-clamp-2:** CSS truncation for message previews

---

## TuningPanel.jsx

**File:** `/frontend/src/components/TuningPanel.jsx`
**Lines:** 814

### Props Interface
```typescript
{
  isOpen: boolean,
  onClose: () => void
}
```

### Internal State
| State Variable | Type | Description |
|----------------|------|-------------|
| `activeTab` | `string` | Current tab ('params', 'session', 'eval') |
| `params` | `string[]` | List of parameter names |
| `categories` | `string[]` | Parameter categories |
| `selectedCategory` | `string | null` | Selected category filter |
| `session` | `object | null` | Active tuning session |
| `evalResults` | `object | null` | Evaluation results |
| `isLoading` | `boolean` | Loading state |
| `error` | `string | null` | Error message |
| `pendingChanges` | `object` | Unsaved parameter changes |
| `isRelaunching` | `boolean` | Engine relaunch in progress |
| `ringStatus` | `object | null` | Conversation ring buffer status |
| `ringMaxTurns` | `number` | Ring buffer max turns slider value |
| `isRingLoading` | `boolean` | Ring operation in progress |

### Hooks Used
| Hook | Source | Purpose |
|------|--------|---------|
| `useState` | React | Local state |
| `useEffect` | React | Initial data load |
| `useCallback` | React | Memoized fetch functions |

### API Endpoints Called
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /tuning/params` | On open | Fetch parameter list |
| `GET /tuning/params?category=X` | On filter | Fetch filtered params |
| `GET /tuning/session` | On open | Fetch session status |
| `POST /tuning/session/new` | On start | Start new tuning session |
| `POST /tuning/session/end` | On end | End tuning session |
| `POST /tuning/eval` | On run | Run evaluation |
| `GET /tuning/params/:name` | Per param | Fetch param details |
| `POST /tuning/params/:name` | On apply | Set param value |
| `POST /tuning/param-reset/:name` | On reset | Reset param to default |
| `POST /tuning/apply-best` | On apply | Apply best params from session |
| `GET /api/ring/status` | On open | Fetch ring buffer status |
| `POST /api/ring/config` | On apply | Configure ring buffer size |
| `POST /api/ring/clear` | On clear | Clear conversation memory |
| `POST /api/system/relaunch` | On relaunch | Restart Luna Engine |

### Child Components Rendered
- `GlassCard` - Container wrapper
- `ParamCard` - Individual parameter control (nested component)
- `ScoreBar` - Visual score indicator (nested component)

### Key Responsibilities
1. Slide-out panel for Luna tuning
2. Three tabs: Parameters, Session, Evaluate
3. Parameter browser with category filter
4. Parameter sliders with min/max/default
5. Tuning session management (start, end, apply best)
6. Iteration history with scores
7. Ring buffer configuration
8. Evaluation runner with score visualization
9. System relaunch control

### Notable Patterns
- **Nested components:** `ParamCard` and `ScoreBar` defined in same file
- **Pending changes tracking:** Changes stored until "Apply" clicked
- **Focus-based sessions:** Session can focus on 'all', 'memory', 'routing', 'latency'
- **Confirmation dialog:** Ring clear uses `window.confirm()`
- **Relaunch timeout:** 10s timeout on relaunch to reset state

---

## ThoughtStream.jsx

**File:** `/frontend/src/components/ThoughtStream.jsx`
**Lines:** 171

### Props Interface
```typescript
{
  apiUrl?: string  // Default: 'http://localhost:8000'
}
```

### Internal State
| State Variable | Type | Description |
|----------------|------|-------------|
| `thoughts` | `Thought[]` | Array of thought objects |
| `isConnected` | `boolean` | SSE connection status |
| `isProcessing` | `boolean` | Whether Luna is processing |
| `currentGoal` | `string | null` | Current agentic goal |

### Hooks Used
| Hook | Source | Purpose |
|------|--------|---------|
| `useState` | React | Local state |
| `useEffect` | React | SSE connection, auto-scroll |
| `useRef` | React | SSE connection ref, container ref |

### API Endpoints Called
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `GET /thoughts` | SSE | Real-time thought stream |

### Child Components Rendered
- `GlassCard` - Container wrapper

### Key Responsibilities
1. Real-time thought stream via Server-Sent Events
2. Phase-based color coding (OBSERVE, THINK, ACT, etc.)
3. Current goal display
4. Processing indicator
5. Auto-scroll to latest thought
6. Reconnection on error

### Notable Patterns
- **SSE reconnection:** Closes and reconnects after 2s on error
- **Thought limit:** Keeps last 50 thoughts only
- **Phase colors/icons:** `getPhaseColor()` and `getPhaseIcon()` functions
- **Timestamp formatting:** Uses `toLocaleTimeString()` with 24h format
- **Event types:** status, thought, ping

---

## EngineStatus.jsx

**File:** `/frontend/src/components/EngineStatus.jsx`
**Lines:** 238

### Props Interface
```typescript
{
  status?: {
    state?: string,
    uptime_seconds?: number,
    cognitive_ticks?: number,
    events_processed?: number,
    messages_generated?: number,
    actors?: string[],
    buffer_size?: number,
    context?: ContextStatus,
    agentic?: AgenticStatus
  },
  isConnected: boolean,
  onRelaunch?: () => Promise<void>
}
```

### Internal State
| State Variable | Type | Description |
|----------------|------|-------------|
| `isRelaunching` | `boolean` | Relaunch in progress |

### Hooks Used
| Hook | Source | Purpose |
|------|--------|---------|
| `useState` | React | Local state |

### API Endpoints Called
None (receives data via props from `useLunaAPI`)

### Child Components Rendered
- `GlassCard` - Container wrapper
- `StatusDot` - State and actor indicators

### Key Responsibilities
1. Engine state display (RUNNING, etc.)
2. Uptime formatting (hours/minutes/seconds)
3. Stats grid (ticks, events, messages)
4. Active actors list
5. Agentic processing status (goal, pending, tasks)
6. Buffer pending count
7. Context window visualization (token budget, ring breakdown)
8. Relaunch button

### Notable Patterns
- **Uptime formatter:** `formatUptime()` converts seconds to human readable
- **Null handling:** Returns loading state if no status
- **Ring colors:** Maps CORE/INNER/MIDDLE/OUTER to gradients
- **Relaunch timeout:** 10s timeout before allowing another relaunch

---

## GlassCard.jsx

**File:** `/frontend/src/components/GlassCard.jsx`
**Lines:** 30

### Props Interface
```typescript
{
  children: ReactNode,
  className?: string,
  onClick?: () => void,
  hover?: boolean,           // Default: true
  dashed?: boolean,          // Default: false
  padding?: string           // Default: 'p-4'
}
```

### Internal State
None

### Hooks Used
None (pure presentational component)

### API Endpoints Called
None

### Child Components Rendered
`children` prop

### Key Responsibilities
1. Glassmorphism container primitive
2. Backdrop blur effect
3. Subtle white border
4. Optional hover effect
5. Optional dashed border variant
6. Configurable padding

### Notable Patterns
- **Composable classes:** Combines base, border, hover, padding classes
- **Conditional hover:** Only applies hover effect if `onClick` is provided
- **Design system primitive:** Used by all other components

---

## GradientOrb.jsx

**File:** `/frontend/src/components/GradientOrb.jsx`
**Lines:** 14

### Props Interface
```typescript
{
  className?: string,
  color1: string,      // CSS color (e.g., '#8b5cf6')
  color2: string,      // CSS color
  delay?: number       // Animation delay in seconds
}
```

### Internal State
None

### Hooks Used
None (pure presentational component)

### API Endpoints Called
None

### Child Components Rendered
None

### Key Responsibilities
1. Decorative background orb
2. Radial gradient with two colors
3. Blur effect (blur-3xl)
4. Pulsing animation with configurable delay
5. Non-interactive (pointer-events-none)

### Notable Patterns
- **Inline style:** Radial gradient uses inline style for dynamic colors
- **CSS animation:** Uses Tailwind's animate-pulse-slow class
- **Absolute positioning:** Positioned via className prop

---

## StatusDot.jsx

**File:** `/frontend/src/components/StatusDot.jsx`
**Lines:** 25

### Props Interface
```typescript
{
  status: string,           // Status key (see colors map)
  size?: string             // Default: 'w-2 h-2'
}
```

### Internal State
None

### Hooks Used
None (pure presentational component)

### API Endpoints Called
None

### Child Components Rendered
None

### Key Responsibilities
1. Visual status indicator dot
2. Color-coded by status
3. Box shadow glow effect
4. Configurable size

### Notable Patterns
- **Color map:** Maps status strings to Tailwind classes with shadows
- **Fallback:** Uses 'neutral' (gray) if status not found
- **Statuses supported:** connected, active, running, loading, syncing, disconnected, error, neutral, curious, focused, playful, thoughtful

---

## Custom Hooks

### useLunaAPI

**File:** `/frontend/src/hooks/useLunaAPI.js`
**Lines:** 242

**Purpose:** Core API communication hook

**State Exposed:**
- `status` - Engine status object
- `consciousness` - Consciousness data
- `isConnected` - Health check status
- `isLoading` - Request in progress
- `error` - Error message

**Functions Exposed:**
- `sendMessage(text)` - Non-streaming message
- `streamMessage(text, onToken, onComplete)` - Legacy streaming
- `streamPersona(text, { onContext, onToken, onDone, onError })` - Context-first streaming
- `abort()` - Cancel generation
- `relaunchSystem()` - Restart engine
- `refresh()` - Manual status refresh

**Endpoints Used:**
- `GET /health` - Health check (polled 2s)
- `GET /status` - Engine status (polled 2s)
- `GET /consciousness` - Consciousness data (polled 2s)
- `POST /message` - Non-streaming message
- `POST /stream` - Legacy streaming
- `POST /persona/stream` - Context-first streaming
- `POST /abort` - Cancel generation
- `POST /api/system/relaunch` - Restart engine

---

### useChat

**File:** `/frontend/src/hooks/useChat.js`
**Lines:** 113

**Purpose:** Streaming chat management

**State Exposed:**
- `messages` - Message array
- `context` - Latest context from API
- `isStreaming` - Stream in progress
- `isLoading` - From useLunaAPI
- `error` - From useLunaAPI

**Functions Exposed:**
- `send(text)` - Send and stream response
- `stop()` - Abort current stream
- `clear()` - Clear message history

**Endpoints Used:**
Via `useLunaAPI.streamPersona()`

---

### useVoice

**File:** `/frontend/src/hooks/useVoice.js`
**Lines:** 287

**Purpose:** Voice interaction management

**State Exposed:**
- `voiceState` - Current VoiceState enum value
- `isRunning` - Voice system active
- `transcription` - Last transcription
- `response` - Last response
- `error` - Error message
- `handsFree` - Hands-free mode enabled

**Derived State:**
- `isListening` - voiceState === LISTENING
- `isThinking` - voiceState === THINKING
- `isSpeaking` - voiceState === SPEAKING
- `isIdle` - voiceState === IDLE
- `isInactive` - voiceState === INACTIVE

**Functions Exposed:**
- `startVoice(handsFreeMode)` - Start voice system
- `stopVoice()` - Stop voice system
- `startListening()` - Begin recording (PTT)
- `stopListening()` - End recording (PTT)
- `speakResponse(text)` - TTS for text

**Endpoints Used:**
- `GET /voice/status` - Initial status check
- `GET /voice/stream` - SSE for real-time updates
- `POST /voice/start` - Start voice system
- `POST /voice/stop` - Stop voice system
- `POST /voice/listen/start` - Begin recording
- `POST /voice/listen/stop` - End recording
- `POST /voice/speak` - TTS

---

## API Endpoint Summary

### Core Endpoints
| Endpoint | Method | Used By | Purpose |
|----------|--------|---------|---------|
| `/health` | GET | useLunaAPI | Health check |
| `/status` | GET | useLunaAPI | Engine status |
| `/consciousness` | GET | useLunaAPI | Consciousness data |
| `/message` | POST | useLunaAPI | Non-streaming message |
| `/stream` | POST | useLunaAPI | Legacy streaming |
| `/persona/stream` | POST | useLunaAPI | Context-first streaming |
| `/abort` | POST | useLunaAPI | Cancel generation |
| `/thoughts` | GET (SSE) | ThoughtStream | Real-time thought stream |

### Debug Endpoints
| Endpoint | Method | Used By | Purpose |
|----------|--------|---------|---------|
| `/debug/context` | GET | App, ContextDebugPanel | Context window debug |
| `/debug/conversation-cache` | GET | ConversationCache | Cached messages |
| `/debug/personality` | GET | PersonalityMonitorPanel | Personality patches |

### Tuning Endpoints
| Endpoint | Method | Used By | Purpose |
|----------|--------|---------|---------|
| `/tuning/params` | GET | TuningPanel | List parameters |
| `/tuning/params/:name` | GET | TuningPanel (ParamCard) | Get parameter details |
| `/tuning/params/:name` | POST | TuningPanel | Set parameter value |
| `/tuning/param-reset/:name` | POST | TuningPanel | Reset to default |
| `/tuning/session` | GET | TuningPanel | Get session status |
| `/tuning/session/new` | POST | TuningPanel | Start session |
| `/tuning/session/end` | POST | TuningPanel | End session |
| `/tuning/eval` | POST | TuningPanel | Run evaluation |
| `/tuning/apply-best` | POST | TuningPanel | Apply best params |

### Voice Endpoints
| Endpoint | Method | Used By | Purpose |
|----------|--------|---------|---------|
| `/voice/status` | GET | useVoice | Initial status |
| `/voice/stream` | GET (SSE) | useVoice | Real-time updates |
| `/voice/start` | POST | useVoice | Start voice |
| `/voice/stop` | POST | useVoice | Stop voice |
| `/voice/listen/start` | POST | useVoice | Begin recording |
| `/voice/listen/stop` | POST | useVoice | End recording |
| `/voice/speak` | POST | useVoice | TTS |

### System Endpoints
| Endpoint | Method | Used By | Purpose |
|----------|--------|---------|---------|
| `/api/ring/status` | GET | TuningPanel | Ring buffer status |
| `/api/ring/config` | POST | TuningPanel | Configure ring |
| `/api/ring/clear` | POST | TuningPanel | Clear memory |
| `/api/system/relaunch` | POST | useLunaAPI, TuningPanel | Restart engine |

---

## Component Index Export

**File:** `/frontend/src/components/index.js`

```javascript
export { default as GlassCard } from './GlassCard';
export { default as GradientOrb } from './GradientOrb';
export { default as StatusDot } from './StatusDot';
export { default as ChatPanel } from './ChatPanel';
export { default as ConsciousnessMonitor } from './ConsciousnessMonitor';
export { default as EngineStatus } from './EngineStatus';
export { default as ThoughtStream } from './ThoughtStream';
export { default as ContextDebugPanel } from './ContextDebugPanel';
export { default as ConversationCache } from './ConversationCache';
export { default as PersonalityMonitorPanel } from './PersonalityMonitorPanel';
export { default as TuningPanel } from './TuningPanel';
export { default as VoicePanel } from './VoicePanel';
```

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| Total Components | 12 |
| App Container | 1 |
| Custom Hooks | 3 |
| API Endpoints | 31 |
| SSE Streams | 2 |
| Total Lines (Components) | ~2,700 |
| Total Lines (Hooks) | ~640 |

### Component Complexity (by lines)
1. TuningPanel.jsx - 814 lines
2. PersonalityMonitorPanel.jsx - 553 lines
3. VoicePanel.jsx - 432 lines
4. ContextDebugPanel.jsx - 282 lines
5. App.jsx - 274 lines
6. EngineStatus.jsx - 238 lines
7. ConversationCache.jsx - 182 lines
8. ThoughtStream.jsx - 171 lines
9. ChatPanel.jsx - 158 lines
10. ConsciousnessMonitor.jsx - 126 lines
11. GlassCard.jsx - 30 lines
12. StatusDot.jsx - 25 lines
13. GradientOrb.jsx - 14 lines
