# Luna Hub UI State Analysis

**Generated:** 2026-01-25
**Analyzed Files:** 17 files in `frontend/src/`
**Framework:** React 18.2.0 with Vite

---

## Executive Summary

The Luna Hub UI employs a **custom hooks-based state management pattern** without external state libraries. There is no Redux, no React Context for global state, and no React Query/SWR. All state is managed through:

1. **Custom React hooks** (`useChat`, `useLunaAPI`, `useVoice`)
2. **Component-local `useState`**
3. **Server-Sent Events (SSE)** for real-time updates
4. **Polling with `setInterval`** for periodic data refresh
5. **localStorage** for chat persistence

---

## 1. State Management Strategy

### 1.1 Redux Usage

**Answer: NO REDUX**

The `package.json` shows minimal dependencies:
```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "recharts": "^3.6.0"
  }
}
```

No Redux, Redux Toolkit, or related packages are installed.

### 1.2 React Context Usage

**Answer: NO CONTEXTS USED**

The codebase does not use `createContext` or `useContext`. State sharing is achieved through:
- **Prop drilling** from `App.jsx` to child components
- **Hook composition** (hooks call other hooks internally)

### 1.3 Server State Management

**Answer: CUSTOM FETCH + POLLING (No React Query/SWR)**

Server state is managed through custom hooks with native `fetch()`:

| Hook | Purpose | Data Fetching Pattern |
|------|---------|----------------------|
| `useLunaAPI` | Engine status, consciousness data | Polling every 2s |
| `useChat` | Chat messages with streaming | SSE via `fetch()` body reader |
| `useVoice` | Voice state, transcription | SSE via `EventSource` |

### 1.4 SSE Connections

**Answer: 3 SEPARATE SSE STREAMS**

| Component/Hook | Endpoint | Event Types |
|----------------|----------|-------------|
| `useVoice` | `/voice/stream` | `status`, `transcription`, `response`, `ping` |
| `ThoughtStream` | `/thoughts` | `status`, `thought`, `ping` |
| `useLunaAPI.streamPersona` | `/persona/stream` | `context`, `token`, `done`, `error` |

### 1.5 Form State Handling

**Answer: LOCAL useState**

- `ChatPanel`: `input` state managed locally
- `TuningPanel`: `pendingChanges` object for staged parameter edits
- `VoicePanel`: `wantHandsFree` toggle state

### 1.6 Persisted State (localStorage)

**Answer: CHAT MESSAGES ONLY**

```javascript
// App.jsx line 21
const CHAT_STORAGE_KEY = 'luna_chat_messages';

// Persistence effect (lines 79-87)
useEffect(() => {
  if (messages.length > 0) {
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(messages));
  }
}, [messages]);
```

**Note:** The code saves messages but does NOT restore them on mount. This appears to be a bug or incomplete feature.

---

## 2. Data Flow Diagram

```
                    +------------------+
                    |     App.jsx      |
                    | (LunaHub Root)   |
                    +--------+---------+
                             |
         +-------------------+-------------------+
         |                   |                   |
    useLunaAPI()        useChat()          useVoice()
         |                   |                   |
         v                   v                   v
+----------------+  +----------------+  +----------------+
| status         |  | messages       |  | voiceState     |
| consciousness  |  | context        |  | isRunning      |
| isConnected    |  | isStreaming    |  | transcription  |
| error          |  | error          |  | response       |
+----------------+  +----------------+  +----------------+
         |                   |                   |
         v                   v                   v
+---------------------------------------------------------+
|                     PROPS DOWN                          |
+---------------------------------------------------------+
         |                   |                   |
         v                   v                   v
+----------------+  +----------------+  +----------------+
| EngineStatus   |  | ChatPanel      |  | VoicePanel     |
| Consciousness  |  +----------------+  +----------------+
| Monitor        |
+----------------+
                             |
                             v
+---------------------------------------------------------+
|                     EVENTS UP (callbacks)               |
+---------------------------------------------------------+
         |                   |                   |
         v                   v                   v
    onRelaunch()         onSend()         startVoice()
                                          stopVoice()
                                          startListening()
```

### Component Hierarchy with State

```
LunaHub (App.jsx)
├── State: debugMode, personalityMode, tuningMode, debugKeywords
├── Hooks: useLunaAPI, useChat, useVoice
│
├── ChatPanel
│   └── Local State: input
│
├── VoicePanel
│   └── Local State: isHolding, lastAction, recordingDuration, audioLevel, wantHandsFree
│
├── EngineStatus
│   └── Local State: isRelaunching
│
├── ConsciousnessMonitor (pure component, no local state)
│
├── ThoughtStream
│   └── Local State: thoughts[], isConnected, isProcessing, currentGoal
│   └── SSE Connection: /thoughts
│
├── ConversationCache
│   └── Local State: cache, isLoading, error, isExpanded
│   └── Polling: /debug/conversation-cache (2s)
│
├── ContextDebugPanel
│   └── Local State: contextData, error, isLoading, selectedRing, expandedItems
│   └── Polling: /debug/context (2s)
│
├── PersonalityMonitorPanel
│   └── Local State: data, error, isLoading, selectedPatch, activeTab
│   └── Polling: /debug/personality (3s)
│
└── TuningPanel
    └── Local State: activeTab, params[], categories, selectedCategory,
                     session, evalResults, pendingChanges, ringStatus,
                     ringMaxTurns, isLoading, isRelaunching
    └── Multiple API calls for tuning parameters
```

---

## 3. API Response Caching Strategy

### Answer: NO CACHING - DIRECT FETCH EVERY TIME

The application does NOT cache API responses. Each component:

1. **Polls independently** at fixed intervals
2. **Replaces state entirely** on each fetch
3. **No deduplication** of identical requests
4. **No stale-while-revalidate** pattern

### Polling Intervals by Component

| Component | Endpoint | Interval | Notes |
|-----------|----------|----------|-------|
| `useLunaAPI` | `/health`, `/status`, `/consciousness` | 2000ms | Runs continuously |
| `ConversationCache` | `/debug/conversation-cache` | 2000ms | Only when connected |
| `ContextDebugPanel` | `/debug/context` | 2000ms | Only when open |
| `PersonalityMonitorPanel` | `/debug/personality` | 3000ms | Only when open |
| `App.jsx` | `/debug/context` | 3000ms | Only in debug mode |

### Potential Issues

1. **Redundant requests**: `/debug/context` is fetched by both `App.jsx` and `ContextDebugPanel`
2. **No request deduplication**: Multiple components may fetch same endpoint simultaneously
3. **Memory pressure**: Each polling response creates new object references

---

## 4. Real-Time Update Patterns

### 4.1 Server-Sent Events (SSE)

#### Voice Stream (`useVoice`)
```javascript
// useVoice.js lines 38-87
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

es.onerror = () => {
  // Reconnect after 3s
  setTimeout(connectStream, 3000);
};
```

#### Thought Stream (`ThoughtStream`)
```javascript
// ThoughtStream.jsx lines 12-56
const eventSource = new EventSource(`${apiUrl}/thoughts`);

eventSource.addEventListener('status', (event) => { ... });
eventSource.addEventListener('thought', (event) => { ... });
eventSource.addEventListener('ping', (event) => { ... });

eventSource.onerror = () => {
  // Reconnect after 2s
  setTimeout(connectToStream, 2000);
};
```

#### Streaming Chat (`useLunaAPI.streamPersona`)
```javascript
// useLunaAPI.js lines 132-188
const res = await fetch(`${API_BASE}/persona/stream`, { method: 'POST', ... });
const reader = res.body.getReader();

while (true) {
  const { done, value } = await reader.read();
  if (done) break;

  // Parse SSE data format
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

### 4.2 SSE Connection Management

| Stream | Auto-Reconnect | Reconnect Delay | Connection Lifecycle |
|--------|----------------|-----------------|---------------------|
| `/voice/stream` | Yes | 3000ms | Component mount/unmount |
| `/thoughts` | Yes | 2000ms | Component mount/unmount |
| `/persona/stream` | No | N/A | Per-message (POST) |

---

## 5. Error State Handling

### Error Propagation Pattern

```
Hook Error State → Prop to App.jsx → Combined → Rendered as Banner
```

```javascript
// App.jsx lines 111-113
const error = chatError || apiError;

// Error Banner (lines 199-203)
{error && (
  <div className="mb-6 p-4 rounded-xl bg-red-500/10 border border-red-400/30 text-red-300 text-sm">
    {error}
  </div>
)}
```

### Component-Level Error Handling

| Component | Error Source | Display Pattern |
|-----------|--------------|-----------------|
| `App.jsx` | `chatError`, `apiError` | Red banner below header |
| `ConversationCache` | Local fetch | Inline red box |
| `ContextDebugPanel` | Local fetch | Modal red box |
| `PersonalityMonitorPanel` | Local fetch | Modal red box |
| `TuningPanel` | Local fetch | Dismissible red banner |
| `VoicePanel` | Hook error | Red box at bottom |

### Error Recovery

Most components silently recover by continuing to poll. SSE connections auto-reconnect. No manual "retry" buttons exist in the current implementation.

---

## 6. Loading State Patterns

### Loading Indicators by Component

| Component | Loading State | Visual Pattern |
|-----------|---------------|----------------|
| `ChatPanel` | `isLoading` (streaming) | Animated dots: "..." |
| `EngineStatus` | `!status` | StatusDot + "Loading..." |
| `ConsciousnessMonitor` | `!consciousness` | "Waiting for consciousness data..." |
| `ThoughtStream` | `isProcessing` | "PROCESSING" label + animated dot |
| `ConversationCache` | `isLoading` | Animated cyan dot + "Loading..." |
| `ContextDebugPanel` | `isLoading && !contextData` | Centered "Loading context..." |
| `PersonalityMonitorPanel` | `isLoading && !data` | Centered "Loading personality data..." |
| `TuningPanel` | `isLoading` | Button text changes to "Running..." |
| `VoicePanel` | `isThinking` | Spinner SVG + "Processing your message..." |

### Skeleton Patterns

```javascript
// TuningPanel ParamCard (lines 709-713)
if (!param) {
  return (
    <div className="p-3 rounded-lg bg-white/5 animate-pulse">
      <div className="h-4 w-32 bg-white/10 rounded" />
    </div>
  );
}
```

---

## 7. State Management Recommendations

### Current Issues

1. **No shared state mechanism**: Same data fetched multiple times
2. **No request deduplication**: Concurrent identical requests possible
3. **localStorage persistence incomplete**: Saves but doesn't restore
4. **No optimistic updates**: All state waits for server confirmation
5. **Polling inefficiency**: Fixed intervals regardless of activity

### Recommended Improvements

1. **Add React Query or SWR** for:
   - Automatic caching
   - Request deduplication
   - Background refetching
   - Optimistic updates

2. **Create a WebSocket manager** to consolidate SSE streams

3. **Add React Context** for:
   - Connection status (single source of truth)
   - User preferences (debug mode, voice mode)

4. **Complete localStorage restoration**:
   ```javascript
   // Add to useChat or App.jsx
   const [messages, setMessages] = useState(() => {
     try {
       const saved = localStorage.getItem(CHAT_STORAGE_KEY);
       return saved ? JSON.parse(saved) : [];
     } catch { return []; }
   });
   ```

---

## 8. File Reference

### Hooks (`frontend/src/hooks/`)

| File | Lines | Purpose |
|------|-------|---------|
| `useLunaAPI.js` | 242 | Engine status, streaming, abort |
| `useChat.js` | 113 | Chat message management |
| `useVoice.js` | 287 | Voice interaction state |

### Components (`frontend/src/components/`)

| File | Lines | State Complexity |
|------|-------|------------------|
| `App.jsx` | 274 | HIGH - orchestrates all hooks |
| `ChatPanel.jsx` | 158 | LOW - input only |
| `VoicePanel.jsx` | 432 | HIGH - many local states |
| `ThoughtStream.jsx` | 171 | MEDIUM - SSE + local state |
| `TuningPanel.jsx` | 814 | VERY HIGH - many API calls |
| `PersonalityMonitorPanel.jsx` | 553 | HIGH - charts + state |
| `ContextDebugPanel.jsx` | 282 | MEDIUM - expandable items |
| `ConversationCache.jsx` | 182 | MEDIUM - polling + expand |
| `EngineStatus.jsx` | 238 | LOW - display only |
| `ConsciousnessMonitor.jsx` | 126 | NONE - pure component |
| `GlassCard.jsx` | 30 | NONE - presentational |
| `StatusDot.jsx` | 25 | NONE - presentational |
| `GradientOrb.jsx` | 14 | NONE - presentational |

---

## 9. Summary Table

| Question | Answer |
|----------|--------|
| Redux used? | **NO** |
| React Context used? | **NO** |
| Server state library? | **NO** (custom fetch) |
| SSE connections? | **3** (voice, thoughts, persona stream) |
| Form state handling? | **Local useState** |
| Persisted state? | **Chat messages to localStorage** (incomplete) |
| Caching strategy? | **None** (fresh fetch each time) |
| Error handling? | **Combined banner + component-level** |
| Loading patterns? | **Per-component indicators** |

---

*Document generated by Claude Code as part of Luna Engine Bible Audit*
