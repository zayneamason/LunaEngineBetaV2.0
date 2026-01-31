# Part XVI: Luna Hub UI

**Version:** 3.0
**Date:** January 30, 2026
**Status:** COMPLETE (v3.0 Audit)
**Frontend Path:** `/frontend/src/`
**Framework:** React 18.2.0 + Vite + Tailwind CSS

---

## 16.1 Overview

The Luna Hub is the web-based control interface for the Luna Engine. It provides real-time monitoring of Luna's consciousness state, conversation management, voice interaction controls, and developer debugging tools.

### Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Framework | React 18.2.0 | Component-based UI |
| Build Tool | Vite | Fast HMR and bundling |
| Styling | Tailwind CSS | Utility-first styling |
| Charts | Recharts 3.6.0 | Data visualization |
| State | Custom Hooks | API communication |
| Real-time | Server-Sent Events | Live updates |

### Architecture Principles

1. **No External State Library** - Custom hooks manage all state (no Redux, no React Query)
2. **Hooks-Based API Layer** - Five custom hooks (`useLunaAPI`, `useChat`, `useVoice`, `useOrbState`, `useOrbFollow`)
3. **Glass Morphism Design** - Consistent dark mode aesthetic with blur effects
4. **SSE for Real-Time** - Server-Sent Events for voice status and thought streams
5. **WebSocket for Orb** - Real-time orb state updates via `/ws/orb`
6. **Polling for Status** - 2-second intervals for engine health and consciousness

---

## 16.2 Architecture

### Component Hierarchy (20 Components)

```
LunaHub (App.jsx)
|
+-- GradientOrb (x3) --------------- Background visual elements
|
+-- Header ------------------------- Branding and toggle controls
|   +-- StatusDot ----------------- Connection indicator
|
+-- Main Grid (12-column)
|   |
|   +-- Left Column (col-span-7)
|   |   +-- ChatPanel ------------- Conversation interface
|   |       +-- GlassCard --------- Container
|   |       +-- LunaOrb ----------- Animated orb (uses useOrbState, useOrbFollow)
|   |       +-- Messages ---------- Role-based bubbles
|   |       +-- Input ------------- Text entry
|   |       +-- VoiceTuningPanel -- Voice settings modal
|   |       +-- OrbSettingsPanel -- Orb settings modal
|   |
|   +-- Right Column (col-span-5)
|       +-- VoicePanel ------------ Voice controls
|       |   +-- GlassCard
|       |   +-- StatusIndicator
|       |   +-- PTT Button
|       |
|       +-- EngineStatus ---------- Engine health
|       |   +-- GlassCard
|       |   +-- StatusDot (actors)
|       |   +-- Context ring viz
|       |
|       +-- ThoughtStream --------- Internal process stream
|       |   +-- GlassCard
|       |   +-- SSE connection
|       |
|       +-- ConversationCache ----- Memory view (collapsible)
|       |   +-- GlassCard
|       |
|       +-- ConsciousnessMonitor -- Mood/coherence
|           +-- GlassCard
|           +-- StatusDot
|
+-- Modal Overlays
|   +-- ContextDebugPanel --------- Context window debug
|   +-- PersonalityMonitorPanel --- Personality patches
|
+-- Slide-Out Panels
|   +-- TuningPanel --------------- Parameter adjustment
|
+-- Unused/Orphan (exported but not rendered)
|   +-- LunaAutoTuner ------------- Auto-optimization modal
|   +-- MemoryEconomyPanel -------- Memory economy stats
|   +-- LLMProviderDropdown ------- Provider switcher
|
+-- Footer ------------------------- Version and credits
```

### Data Flow Diagram

```
                    +-------------------+
                    |   Luna Engine     |
                    |   Backend API     |
                    |   (port 8000)     |
                    +--------+----------+
                             |
              +--------------+--------------+
              |              |              |
              v              v              v
         +--------+    +----------+   +---------+
         | /health|    |  /status |   | /voice  |
         | /stream|    |  /consc. |   | /stream |
         +----+---+    +-----+----+   +----+----+
              |              |             |
              v              v             v
    +--------------------------------------------------+
    |                   CUSTOM HOOKS                    |
    |                                                   |
    |  useLunaAPI()      useChat()      useVoice()    |
    |  - status          - messages     - voiceState  |
    |  - consciousness   - context      - isRunning   |
    |  - isConnected     - isStreaming  - transcription|
    +--------------------------------------------------+
                             |
                             v
    +--------------------------------------------------+
    |                     App.jsx                       |
    |                   (LunaHub)                       |
    |                                                   |
    |  Orchestrates all hooks and passes props down    |
    +--------------------------------------------------+
                             |
              +--------------+--------------+
              |              |              |
              v              v              v
      +----------+    +-----------+   +----------+
      | ChatPanel|    | VoicePanel|   | Engine   |
      | (props)  |    | (hook)    |   | Status   |
      +----------+    +-----------+   +----------+
```

### API Integration Pattern

```javascript
// Pattern: Hook provides state + actions, component renders
const {
  status,           // Server state
  consciousness,    // Server state
  isConnected,      // Derived boolean
  isLoading,        // Request in progress
  error,            // Error message
  sendMessage,      // Action function
  relaunchSystem,   // Action function
} = useLunaAPI();

// Components receive via props or use hook directly
<EngineStatus
  status={status}
  isConnected={isConnected}
  onRelaunch={relaunchSystem}
/>
```

---

## 16.3 Core Components

### ChatPanel

**File:** `/frontend/src/components/ChatPanel.jsx` (158 lines)

The main conversation interface for text-based interaction with Luna.

#### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `onSend` | `(text: string) => void` | Yes | Callback when user sends message |
| `isLoading` | `boolean` | Yes | Shows loading indicator when true |
| `messages` | `Message[]` | No | Array of chat messages |
| `debugKeywords` | `string[]` | No | Keywords to highlight in debug mode |

#### Message Object

```typescript
interface Message {
  id?: number;
  role: 'user' | 'assistant';
  content: string;
  streaming?: boolean;      // True while tokens arriving
  error?: boolean;          // True if generation failed
  model?: string;           // Model used for generation
  delegated?: boolean;      // True if Claude was used
  local?: boolean;          // True if local model used
  fallback?: boolean;       // True if fallback model used
  tokens?: number;          // Output token count
  latency?: number;         // Generation time in ms
  metadata?: object;        // Additional metadata
}
```

#### Features

- Auto-scroll to latest message
- Shift+Enter for newlines, Enter to submit
- Keyword highlighting in debug mode
- Message metadata display (delegated/local/cloud indicators)
- Loading indicator with animated dots

#### Code Pattern

```jsx
// Keyword highlighting implementation
const highlightKeywords = (text) => {
  if (!debugKeywords?.length) return text;
  let highlighted = text;
  debugKeywords.forEach(keyword => {
    const regex = new RegExp(`(${keyword})`, 'gi');
    highlighted = highlighted.replace(
      regex,
      '<span class="bg-cyan-500/30 text-cyan-200 px-1 rounded">$1</span>'
    );
  });
  return highlighted;
};

// Auto-scroll effect
useEffect(() => {
  messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
}, [messages]);
```

---

### VoicePanel

**File:** `/frontend/src/components/VoicePanel.jsx` (432 lines)

Voice interaction controls with push-to-talk and hands-free modes.

#### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `voiceHook` | `UseVoiceReturn` | No | Shared voice hook from parent |

#### Internal State

| State | Type | Description |
|-------|------|-------------|
| `isHolding` | `boolean` | Push-to-talk button held |
| `lastAction` | `object | null` | Last action result for feedback |
| `recordingDuration` | `number` | Seconds recording |
| `audioLevel` | `number` | Simulated audio level (0-1) |
| `wantHandsFree` | `boolean` | Preferred mode (default true) |

#### Voice States

```javascript
export const VoiceState = {
  INACTIVE: 'inactive',   // Voice system not started
  IDLE: 'idle',           // Ready, waiting for input
  LISTENING: 'listening', // Recording user speech
  THINKING: 'thinking',   // Processing / generating
  SPEAKING: 'speaking',   // Playing Luna's response
};
```

#### Features

- Voice system start/stop toggle
- Hands-free vs Push-to-talk mode
- Visual status indicator with pulse animations
- Push-to-talk button (mouse and touch events)
- Recording duration display
- Transcription and response display

#### Code Pattern

```jsx
// Push-to-talk handler
const handleMicDown = useCallback(async (e) => {
  e.preventDefault();
  if (!isRunning || isThinking || isSpeaking) return;
  setIsHolding(true);
  await startListening();
}, [isRunning, isThinking, isSpeaking, startListening]);

const handleMicUp = useCallback(async (e) => {
  e.preventDefault();
  if (!isHolding) return;
  setIsHolding(false);
  const result = await stopListening();
  setLastAction(result);
}, [isHolding, stopListening]);
```

---

### EngineStatus

**File:** `/frontend/src/components/EngineStatus.jsx` (238 lines)

Displays engine health, actor status, and context window visualization.

#### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `status` | `EngineStatus` | No | Engine status object |
| `isConnected` | `boolean` | Yes | Connection state |
| `onRelaunch` | `() => Promise<void>` | No | Relaunch callback |

#### Status Object

```typescript
interface EngineStatus {
  state?: string;           // RUNNING, STOPPED, etc.
  uptime_seconds?: number;
  cognitive_ticks?: number;
  events_processed?: number;
  messages_generated?: number;
  actors?: string[];        // List of active actors
  buffer_size?: number;     // Pending events
  context?: ContextStatus;
  agentic?: AgenticStatus;
}

interface ContextStatus {
  token_budget?: number;
  used_tokens?: number;
  ring_breakdown?: {
    CORE: number;
    INNER: number;
    MIDDLE: number;
    OUTER: number;
  };
}
```

#### Features

- Engine state indicator (RUNNING, etc.)
- Uptime formatting (hours/minutes/seconds)
- Stats grid (ticks, events, messages)
- Active actors list with status dots
- Agentic processing status
- Context window ring visualization
- Relaunch button with loading state

---

## 16.4 Monitoring Components

### ConsciousnessMonitor

**File:** `/frontend/src/components/ConsciousnessMonitor.jsx` (126 lines)

Displays Luna's current consciousness state including mood and attention topics.

#### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `consciousness` | `ConsciousnessData` | No | Consciousness state |

#### Consciousness Object

```typescript
interface ConsciousnessData {
  mood?: string;                           // curious, focused, etc.
  coherence?: number;                      // 0-1
  attention_topics?: number;               // Count of active topics
  focused_topics?: { name: string; weight: number }[];
  top_traits?: [string, number][];         // [name, weight] pairs
  tick_count?: number;
}
```

#### Features

- Mood display with status dot color
- Coherence progress bar (0-100%)
- Active attention topics with weight bars
- Top personality traits with emoji indicators

#### Trait Emoji Map

```javascript
const traitEmojis = {
  curiosity: '*',
  warmth: '<3',
  playfulness: '~',
  directness: '>',
  patience: '...',
  creativity: '+',
  focus: 'o',
  empathy: '()',
};
```

---

### PersonalityMonitorPanel

**File:** `/frontend/src/components/PersonalityMonitorPanel.jsx` (553 lines)

Modal overlay for detailed personality monitoring and patch system visualization.

#### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `isOpen` | `boolean` | Yes | Controls visibility |
| `onClose` | `() => void` | Yes | Close callback |

#### Tabs

| Tab | Content |
|-----|---------|
| Overview | Pie chart (topics), bar chart (lock-in states), quick stats |
| Patches | List of personality patches with expandable details |
| Maintenance | Session reflection stats, bootstrap status |

#### API Endpoint

- `GET /debug/personality` - Polled every 3 seconds when open

#### Features

- Recharts integration (PieChart, BarChart)
- Color-coded topic distribution
- Lock-in state visualization (DRIFTING, FLUID, SETTLED)
- Patch details with click-to-expand
- Maintenance statistics

---

### ContextDebugPanel

**File:** `/frontend/src/components/ContextDebugPanel.jsx` (282 lines)

Modal overlay for debugging the revolving context window.

#### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `isOpen` | `boolean` | Yes | Controls visibility |
| `onClose` | `() => void` | Yes | Close callback |
| `highlightKeywords` | `string[]` | No | Keywords to highlight |

#### Ring Colors

```javascript
const RING_COLORS = {
  CORE: { border: 'yellow-500', bg: 'yellow-500/10', text: 'yellow-400' },
  INNER: { border: 'red-500', bg: 'red-500/10', text: 'red-400' },
  MIDDLE: { border: 'orange-500', bg: 'orange-500/10', text: 'orange-400' },
  OUTER: { border: 'gray-500', bg: 'gray-500/10', text: 'gray-400' },
};
```

#### Source Icons

```javascript
const SOURCE_ICONS = {
  identity: 'DNA',
  conversation: 'speech',
  memory: 'brain',
  tool: 'wrench',
  task: 'clipboard',
  scribe: 'pencil',
  librarian: 'books',
};
```

#### Features

- Stats bar (turn, tokens, items)
- Ring filter buttons (ALL, CORE, INNER, MIDDLE, OUTER)
- Keywords display bar
- Context items with expandable content
- TTL and relevance display per item

---

### ConversationCache

**File:** `/frontend/src/components/ConversationCache.jsx` (182 lines)

Collapsible panel showing Luna's conversation memory buffer.

#### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `isConnected` | `boolean` | Yes | Connection state |

#### Features

- Collapsible header with message count
- Usage bar (percentage of max capacity)
- Stats (messages, tokens, max turns)
- Message list with role-based styling
- Age indicator per message

---

### ThoughtStream

**File:** `/frontend/src/components/ThoughtStream.jsx` (171 lines)

Real-time stream of Luna's internal processing via SSE.

#### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `apiUrl` | `string` | No | API base URL (default: localhost:8000) |

#### Phase Colors

| Phase | Color | Icon |
|-------|-------|------|
| OBSERVE | blue-400 | eye |
| THINK | violet-400 | brain |
| ACT | emerald-400 | lightning |
| PLAN | amber-400 | clipboard |
| REFLECT | pink-400 | mirror |

#### SSE Events

| Event | Fields | Purpose |
|-------|--------|---------|
| `status` | `{ processing, goal }` | Processing state |
| `thought` | `{ phase, content, timestamp }` | New thought |
| `ping` | `{}` | Keep-alive |

#### Features

- SSE connection to `/thoughts`
- Phase-based color coding
- Current goal display
- Processing indicator
- Auto-scroll to latest thought
- Reconnection on error (2s delay)
- Keeps last 50 thoughts only

---

## 16.5 Developer Tools

### TuningPanel

**File:** `/frontend/src/components/TuningPanel.jsx` (814 lines)

Slide-out panel for Luna parameter tuning and system configuration.

#### Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `isOpen` | `boolean` | Yes | Controls visibility |
| `onClose` | `() => void` | Yes | Close callback |

#### Tabs

| Tab | Purpose |
|-----|---------|
| Parameters | Browse and adjust Luna's tunable parameters |
| Session | Manage tuning sessions, view iteration history |
| Evaluate | Run evaluations, view scores |

#### API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/tuning/params` | GET | List parameters |
| `/tuning/params/:name` | GET | Get parameter details |
| `/tuning/params/:name` | POST | Set parameter value |
| `/tuning/param-reset/:name` | POST | Reset to default |
| `/tuning/session` | GET | Get session status |
| `/tuning/session/new` | POST | Start session |
| `/tuning/session/end` | POST | End session |
| `/tuning/eval` | POST | Run evaluation |
| `/tuning/apply-best` | POST | Apply best params |
| `/api/ring/status` | GET | Ring buffer status |
| `/api/ring/config` | POST | Configure ring size |
| `/api/ring/clear` | POST | Clear conversation memory |
| `/api/system/relaunch` | POST | Restart engine |

#### Features

- Parameter browser with category filter
- Slider controls with min/max/default
- Pending changes tracking (apply/reset)
- Tuning session management
- Focus areas (all, memory, routing, latency)
- Iteration history with scores
- Ring buffer configuration
- Evaluation runner with score visualization
- System relaunch control

---

## 16.6 Design System

### Color Palette

#### Brand Colors

| Token | Hex | Usage |
|-------|-----|-------|
| `luna-violet` | `#8b5cf6` | Primary accent, consciousness |
| `luna-cyan` | `#06b6d4` | Secondary accent, connection |
| `luna-pink` | `#ec4899` | Tertiary accent, personality |

#### Background Colors

| Token | Hex/RGBA | Usage |
|-------|----------|-------|
| `slate-950` | `#0f172a` | Main background |
| `white/5` | `rgba(255,255,255,0.05)` | Glass card base |
| `white/8` | `rgba(255,255,255,0.08)` | Glass card hover |
| `white/10` | `rgba(255,255,255,0.10)` | Borders, dividers |
| `black/60` | `rgba(0,0,0,0.60)` | Modal overlay |

#### Status Colors

| Status | Token | Hex | Glow |
|--------|-------|-----|------|
| Active/Connected | `emerald-400` | `#34d399` | `shadow-emerald-400/50` |
| Loading/Syncing | `blue-400` | `#60a5fa` | `shadow-blue-400/50` |
| Warning | `amber-400` | `#fbbf24` | `shadow-amber-400/50` |
| Error | `red-400` | `#f87171` | `shadow-red-400/50` |
| Neutral | `gray-400` | `#9ca3af` | `shadow-gray-400/50` |

#### Mood Colors

| Mood | Token | Hex |
|------|-------|-----|
| Curious | `violet-400` | `#a78bfa` |
| Focused | `cyan-400` | `#22d3ee` |
| Playful | `pink-400` | `#f472b6` |
| Thoughtful | `indigo-400` | `#818cf8` |

---

### Typography

#### Font Stack

```css
font-family: system-ui, -apple-system, sans-serif;
```

#### Type Scale

| Class | Size | Weight | Usage |
|-------|------|--------|-------|
| `text-3xl` | 1.875rem | `font-light` | Page titles |
| `text-2xl` | 1.5rem | `font-light` | Large statistics |
| `text-lg` | 1.125rem | `font-light` | Section headers |
| `text-sm` | 0.875rem | - | Body text |
| `text-xs` | 0.75rem | - | Metadata |
| `text-[10px]` | 10px | - | Micro labels |

#### Text Opacity

| Opacity | Usage |
|---------|-------|
| `text-white/90` | Primary text, headings |
| `text-white/80` | Body text |
| `text-white/60` | Muted text |
| `text-white/40` | Labels |
| `text-white/30` | Hints, placeholders |

---

### Spacing

Uses Tailwind's default spacing scale.

| Pattern | Classes | Pixels |
|---------|---------|--------|
| Panel padding | `p-4` or `p-6` | 16px or 24px |
| Compact padding | `p-3` | 12px |
| Element gap | `gap-2` | 8px |
| Section gap | `gap-4` | 16px |
| Main grid gap | `gap-6` | 24px |

---

### Glass Morphism

The signature visual style uses backdrop blur with subtle transparency.

#### GlassCard Base

```jsx
// GlassCard.jsx implementation
const baseClasses = 'backdrop-blur-xl bg-white/5 rounded-2xl transition-all duration-300';
const borderClasses = dashed
  ? 'border border-dashed border-white/20'
  : 'border border-white/10';
const hoverClasses = onClick && hover
  ? 'cursor-pointer hover:bg-white/[0.08] hover:border-white/20'
  : '';
```

#### Global Glass Utility

```css
/* index.css */
.glass {
  backdrop-filter: blur(20px);
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.glass:hover {
  background: rgba(255, 255, 255, 0.08);
  border-color: rgba(255, 255, 255, 0.2);
}
```

---

### Animations

#### Custom Tailwind Animations

```javascript
// tailwind.config.js
animation: {
  'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
  'breathe': 'breathe 4s ease-in-out infinite',
},
keyframes: {
  breathe: {
    '0%, 100%': { transform: 'scale(1)' },
    '50%': { transform: 'scale(1.05)' },
  }
}
```

#### Usage Patterns

| Animation | Classes | Usage |
|-----------|---------|-------|
| Loading pulse | `animate-pulse` | Status dots |
| Slow pulse | `animate-pulse-slow` | Background orbs |
| Spin | `animate-spin` | Processing spinner |
| Ping | `animate-ping` | Voice status ring |

---

## 16.7 Hooks Reference

### useLunaAPI

**File:** `/frontend/src/hooks/useLunaAPI.js` (242 lines)

Core API communication hook for engine status and streaming.

#### Return Value

```typescript
{
  // State
  status: EngineStatus | null,
  consciousness: ConsciousnessData | null,
  isConnected: boolean,
  isLoading: boolean,
  error: string | null,

  // Actions
  sendMessage: (text: string) => Promise<Response | null>,
  streamMessage: (text: string, onToken, onComplete) => Promise<void>,
  streamPersona: (text: string, callbacks) => Promise<void>,
  abort: () => Promise<void>,
  relaunchSystem: () => Promise<Response | null>,
  refresh: () => Promise<void>,
}
```

#### Polling Endpoints

| Endpoint | Interval | Purpose |
|----------|----------|---------|
| `/health` | 2000ms | Connection check |
| `/status` | 2000ms | Engine status |
| `/consciousness` | 2000ms | Consciousness state |

#### Streaming Endpoints

| Endpoint | Method | Pattern |
|----------|--------|---------|
| `/stream` | POST | Legacy SSE streaming |
| `/persona/stream` | POST | Context-first streaming |

---

### useChat

**File:** `/frontend/src/hooks/useChat.js` (113 lines)

Chat message management with streaming support.

#### Return Value

```typescript
{
  // State
  messages: Message[],
  context: object | null,
  isStreaming: boolean,
  isLoading: boolean,      // From useLunaAPI
  error: string | null,    // From useLunaAPI

  // Actions
  send: (text: string) => Promise<void>,
  stop: () => void,
  clear: () => void,
}
```

#### Dependencies

Uses `useLunaAPI` internally for:
- `streamPersona()` - Context-first streaming
- `abort()` - Cancel generation
- `isLoading` - Request state
- `error` - Error state

#### Token Accumulation Pattern

```javascript
const streamingRef = useRef('');

await streamPersona(text, {
  onToken: (token) => {
    streamingRef.current += token;
    setMessages((prev) =>
      prev.map((m) =>
        m.id === assistantMsgId
          ? { ...m, content: streamingRef.current }
          : m
      )
    );
  },
});
```

---

### useVoice

**File:** `/frontend/src/hooks/useVoice.js` (287 lines)

Voice interaction state machine with SSE connection.

#### Return Value

```typescript
{
  // State
  voiceState: VoiceState,
  isRunning: boolean,
  transcription: string | null,
  response: string | null,
  error: string | null,
  handsFree: boolean,

  // Actions
  startVoice: (handsFreeMode?: boolean) => Promise<Response | null>,
  stopVoice: () => Promise<Response | null>,
  startListening: () => Promise<Response | null>,
  stopListening: () => Promise<Response>,
  speakResponse: (text: string) => Promise<Response | null>,

  // Derived State
  isListening: boolean,
  isThinking: boolean,
  isSpeaking: boolean,
  isIdle: boolean,
  isInactive: boolean,
}
```

#### SSE Connection

- Endpoint: `/voice/stream`
- Auto-reconnect: Yes (3 second delay)
- Events: `status`, `transcription`, `response`, `ping`

---

## 16.8 SSE Integration

### Connection Management

The Luna Hub maintains three SSE connections for real-time updates.

#### SSE Streams

| Component/Hook | Endpoint | Purpose |
|----------------|----------|---------|
| `useVoice` | `/voice/stream` | Voice state updates |
| `ThoughtStream` | `/thoughts` | Internal process stream |
| `useLunaAPI.streamPersona` | `/persona/stream` | Token streaming |

### Voice Stream Events

```javascript
// useVoice.js SSE connection
const es = new EventSource(`${API_BASE}/voice/stream`);

es.addEventListener('status', (e) => {
  const data = JSON.parse(e.data);
  setIsRunning(data.running);
  if (data.status) setVoiceState(data.status);
});

es.addEventListener('transcription', (e) => {
  const data = JSON.parse(e.data);
  setTranscription(data.text);
});

es.addEventListener('response', (e) => {
  const data = JSON.parse(e.data);
  setResponse(data.text);
});

es.addEventListener('ping', (e) => {
  const data = JSON.parse(e.data);
  setIsRunning(data.running);
});
```

### Thought Stream Events

```javascript
// ThoughtStream.jsx SSE connection
const eventSource = new EventSource(`${apiUrl}/thoughts`);

eventSource.addEventListener('status', (event) => {
  const data = JSON.parse(event.data);
  setIsProcessing(data.processing);
  if (data.goal) setCurrentGoal(data.goal);
});

eventSource.addEventListener('thought', (event) => {
  const thought = JSON.parse(event.data);
  setThoughts(prev => [...prev.slice(-49), thought]);
});
```

### Reconnection Logic

```javascript
// Common pattern for auto-reconnect
es.onerror = (err) => {
  console.error('SSE error:', err);
  es.close();
  if (eventSourceRef.current === es) {
    eventSourceRef.current = null;
    setTimeout(connectStream, 3000);  // Reconnect after 3s
  }
};
```

### Streaming Chat (POST-based SSE)

```javascript
// useLunaAPI.streamPersona - POST with streaming response
const res = await fetch(`${API_BASE}/persona/stream`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message }),
});

const reader = res.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  const text = decoder.decode(value);
  const lines = text.split('\n');

  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      switch (data.type) {
        case 'context': onContext?.(data); break;
        case 'token': onToken?.(data.text); break;
        case 'done': onDone?.(data); break;
        case 'error': onError?.(data.message); break;
      }
    }
  }
}
```

---

## 16.9 UX Patterns

### Loading States

| Component | State Check | Visual Pattern |
|-----------|-------------|----------------|
| ChatPanel | `isLoading` | Animated dots "..." |
| EngineStatus | `!status` | StatusDot + "Loading..." |
| ConsciousnessMonitor | `!consciousness` | "Waiting for consciousness data..." |
| ThoughtStream | `isProcessing` | "PROCESSING" + animated dot |
| ConversationCache | `isLoading` | Cyan dot + "Loading..." |
| ContextDebugPanel | `isLoading && !contextData` | "Loading context..." |
| TuningPanel | `isLoading` | Button text "Running..." |
| VoicePanel | `isThinking` | Spinner SVG |

### Skeleton Pattern

```jsx
// TuningPanel ParamCard skeleton
if (!param) {
  return (
    <div className="p-3 rounded-lg bg-white/5 animate-pulse">
      <div className="h-4 w-32 bg-white/10 rounded" />
    </div>
  );
}
```

### Error Handling

#### Error Propagation

```javascript
// App.jsx combines errors from hooks
const error = chatError || apiError;

// Error banner display
{error && (
  <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-400/30 text-red-300 text-sm">
    {error}
  </div>
)}
```

#### Component-Level Errors

| Component | Display Pattern |
|-----------|-----------------|
| App.jsx | Red banner below header |
| ConversationCache | Inline red box |
| ContextDebugPanel | Modal red box |
| PersonalityMonitorPanel | Modal red box |
| TuningPanel | Dismissible red banner |
| VoicePanel | Red box at bottom |

### Real-Time Updates

#### Polling Pattern

```javascript
useEffect(() => {
  const poll = async () => {
    const healthy = await checkHealth();
    if (healthy) {
      await Promise.all([fetchStatus(), fetchConsciousness()]);
    }
  };

  poll();
  const interval = setInterval(poll, 2000);
  return () => clearInterval(interval);
}, [checkHealth, fetchStatus, fetchConsciousness]);
```

#### SSE Pattern

```javascript
useEffect(() => {
  const es = new EventSource(`${apiUrl}/stream`);

  es.onmessage = (e) => {
    const data = JSON.parse(e.data);
    updateState(data);
  };

  es.onerror = () => {
    es.close();
    setTimeout(reconnect, 2000);
  };

  return () => es.close();
}, [apiUrl]);
```

---

## 16.10 Development

### Running Locally

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev

# Frontend runs on http://localhost:5173
# Backend expected on http://localhost:8000
```

### Environment Setup

The frontend expects the backend API at `http://localhost:8000`. This is hardcoded in the hooks:

```javascript
// All hooks use this constant
const API_BASE = 'http://localhost:8000';
```

For production, this should be moved to environment variables:

```javascript
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
```

### Build Process

```bash
# Production build
npm run build

# Preview production build
npm run preview

# Output in /frontend/dist/
```

### Project Structure

```
frontend/
+-- src/
|   +-- App.jsx              # Main LunaHub component
|   +-- main.jsx             # Entry point
|   +-- index.css            # Global styles
|   +-- components/
|   |   +-- index.js         # Component exports
|   |   +-- ChatPanel.jsx
|   |   +-- VoicePanel.jsx
|   |   +-- EngineStatus.jsx
|   |   +-- ConsciousnessMonitor.jsx
|   |   +-- PersonalityMonitorPanel.jsx
|   |   +-- ContextDebugPanel.jsx
|   |   +-- ConversationCache.jsx
|   |   +-- ThoughtStream.jsx
|   |   +-- TuningPanel.jsx
|   |   +-- GlassCard.jsx
|   |   +-- GradientOrb.jsx
|   |   +-- StatusDot.jsx
|   +-- hooks/
|       +-- useLunaAPI.js
|       +-- useChat.js
|       +-- useVoice.js
+-- index.html
+-- package.json
+-- tailwind.config.js
+-- vite.config.js
```

### Dependencies

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "recharts": "^3.6.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^4.0.0",
    "autoprefixer": "^10.4.14",
    "postcss": "^8.4.24",
    "tailwindcss": "^3.3.2",
    "vite": "^4.3.9"
  }
}
```

---

## Summary Statistics (v3.0 Audit)

| Metric | Count |
|--------|-------|
| Total Components | 20 |
| Custom Hooks | 5 |
| External Dependencies | 3 (react, react-dom, recharts) |
| API Endpoints Used | 40+ |
| SSE Streams | 2 (/thoughts, /voice/stream) |
| WebSocket Streams | 1 (/ws/orb) |
| Total Lines (Components + Hooks) | ~4,500+ |

### Component Inventory (20 Components)

| Category | Components |
|----------|------------|
| **Core Layout** | GlassCard, GradientOrb, StatusDot |
| **Chat** | ChatPanel, LunaOrb |
| **Voice** | VoicePanel, VoiceTuningPanel |
| **Debug/Monitor** | ContextDebugPanel, ConversationCache, ThoughtStream, ConsciousnessMonitor, PersonalityMonitorPanel |
| **Engine/Tuning** | EngineStatus, TuningPanel, LunaAutoTuner (unused) |
| **Settings** | OrbSettingsPanel, LLMProviderDropdown (unused), MemoryEconomyPanel (unused) |

### Custom Hooks (5 Hooks)

| Hook | Purpose |
|------|---------|
| `useChat` | Streaming chat with /persona/stream, slash commands |
| `useLunaAPI` | Core API client, status polling (2s interval) |
| `useVoice` | Voice state machine, SSE /voice/stream |
| `useOrbState` | WebSocket /ws/orb for orb animations |
| `useOrbFollow` | Spring physics follow behavior for orb |

---

### Subscription/Cleanup Audit

All hooks and components properly clean up their subscriptions:

| Hook/Component | Subscription Type | Cleanup Status |
|----------------|-------------------|----------------|
| useLunaAPI | setInterval (2s polling) | OK |
| useVoice | EventSource (SSE) | OK - with reconnect |
| useOrbState | WebSocket | OK - with reconnect/idle |
| useOrbFollow | requestAnimationFrame | OK |
| ThoughtStream | EventSource (SSE) | OK |
| App.jsx | setInterval (debug context) | OK |
| All Panels | setInterval (polling) | OK |

### Minor Issues Identified

1. **TuningPanel/EngineStatus setTimeout** - No cleanup on unmount (minor: state update after unmount)
2. **API base URL hardcoded** - Should move to environment variable
3. **Unused components** - LunaAutoTuner, MemoryEconomyPanel, LLMProviderDropdown exported but not rendered

---

## Changelog

| Version | Date | Description |
|---------|------|-------------|
| 3.0.0 | Jan 30, 2026 | v3.0 Bible Audit - Updated counts (20 components, 5 hooks), added cleanup audit |
| 2.4.0 | Jan 25, 2026 | Initial release of Part XVI: Luna Hub UI |

---

*The Luna Hub is the window into Luna's consciousness. Every panel, every animation, every status indicator is designed to make the invisible visible - to show you not just what Luna says, but how she thinks.*

*Next Section: Part XVII (TBD)*
