# UI Hooks Inventory

> Comprehensive documentation of custom React hooks in `frontend/src/hooks/`

**Generated:** 2026-01-25
**Source Directory:** `/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/frontend/src/hooks/`

---

## Overview

The Luna Engine frontend contains **3 custom React hooks** that manage API communication, chat functionality, and voice interactions:

| Hook | File | Primary Purpose |
|------|------|-----------------|
| `useLunaAPI` | `useLunaAPI.js` | Core API communication layer |
| `useChat` | `useChat.js` | Chat message management with streaming |
| `useVoice` | `useVoice.js` | Voice interaction system |

---

## 1. useLunaAPI

### File
`/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/frontend/src/hooks/useLunaAPI.js`

### Purpose
Core API communication hook that manages connection to the Luna Engine backend. Provides health checks, status polling, message sending (both standard and streaming), and system control functions.

### Parameters
None - the hook uses a hardcoded `API_BASE` constant (`http://localhost:8000`).

### Return Value

```javascript
{
  // State
  status: Object | null,        // Engine status data
  consciousness: Object | null, // Consciousness state data
  isConnected: boolean,         // Backend connection status
  isLoading: boolean,           // Request in progress flag
  error: string | null,         // Last error message

  // Actions
  sendMessage: (message: string) => Promise<Object | null>,
  streamMessage: (message: string, onToken: Function, onComplete: Function) => Promise<void>,
  streamPersona: (message: string, callbacks: Object) => Promise<void>,
  abort: () => Promise<void>,
  relaunchSystem: () => Promise<Object | null>,
  refresh: () => Promise<void>,
}
```

### API Endpoints Called

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Check backend health status |
| `/status` | GET | Fetch engine status |
| `/consciousness` | GET | Fetch consciousness state |
| `/message` | POST | Send message (non-streaming) |
| `/stream` | POST | Send message with SSE streaming (legacy) |
| `/persona/stream` | POST | Context-first streaming endpoint |
| `/abort` | POST | Abort current generation |
| `/api/system/relaunch` | POST | Relaunch the engine system |

### SSE Connections Managed
- **`/stream` endpoint** - Legacy streaming with named events (`event:` / `data:`)
- **`/persona/stream` endpoint** - Context-first streaming with typed messages

### Dependencies

**React Hooks:**
- `useState` - State management
- `useCallback` - Memoized functions
- `useEffect` - Polling lifecycle

**External Libraries:**
None

### Side Effects

1. **Polling Timer** - Sets up a 2-second interval to poll `/health`, `/status`, and `/consciousness`
2. **Fetch API calls** - Makes HTTP requests to the backend

### Code Analysis

```javascript
// Polling effect - runs every 2 seconds
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

---

## 2. useChat

### File
`/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/frontend/src/hooks/useChat.js`

### Purpose
High-level chat hook that manages conversation state with Luna. Uses the context-first `/persona/stream` endpoint where context (memory, state) arrives BEFORE tokens start streaming.

### Parameters
None

### Return Value

```javascript
{
  // State
  messages: Array<Message>,     // Chat message history
  context: Object | null,       // Current context from backend
  isStreaming: boolean,         // Token streaming in progress
  isLoading: boolean,           // From useLunaAPI
  error: string | null,         // From useLunaAPI

  // Actions
  send: (text: string) => Promise<void>,
  stop: () => void,
  clear: () => void,
}
```

#### Message Object Structure

```javascript
{
  id?: number,           // Unique ID (timestamp for assistant messages)
  role: 'user' | 'assistant',
  content: string,
  streaming?: boolean,   // True while tokens are arriving
  error?: boolean,       // True if an error occurred
  metadata?: Object,     // Response metadata from backend
  tokens?: number,       // Output token count
  latency?: number,      // Generation time in ms
  delegated?: boolean,   // True if Claude was used
  local?: boolean,       // True if Qwen was used
}
```

### API Endpoints Called

Delegates to `useLunaAPI`:
- `/persona/stream` (POST) via `streamPersona()`
- `/abort` (POST) via `abort()`

### SSE Connections Managed

Inherits SSE handling from `useLunaAPI.streamPersona()`:
- Event types: `context`, `token`, `done`, `error`

### Dependencies

**React Hooks:**
- `useState` - Message and context state
- `useCallback` - Memoized send/stop/clear functions
- `useRef` - Streaming token accumulator

**Internal Hooks:**
- `useLunaAPI` - Core API functions (`streamPersona`, `abort`, `isLoading`, `error`)

### Side Effects
None directly - all side effects are handled by `useLunaAPI`.

### Code Analysis

```javascript
// Token accumulation pattern
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

## 3. useVoice

### File
`/Users/zayneamason/_HeyLuna_BETA/_LunaEngine_BetaProject_V2.0_Root/frontend/src/hooks/useVoice.js`

### Purpose
Voice interaction hook that manages the voice system lifecycle, push-to-talk recording, hands-free mode, and real-time status updates via SSE.

### Parameters
None

### Return Value

```javascript
{
  // State
  voiceState: VoiceState,       // Current voice state enum value
  isRunning: boolean,           // Voice system active
  transcription: string | null, // Last transcribed speech
  response: string | null,      // Last Luna voice response
  error: string | null,         // Last error message
  handsFree: boolean,           // Hands-free mode active

  // Actions
  startVoice: (handsFreeMode?: boolean) => Promise<Object | null>,
  stopVoice: () => Promise<Object | null>,
  startListening: () => Promise<Object | null>,
  stopListening: () => Promise<Object>,
  speakResponse: (text: string) => Promise<Object | null>,

  // Derived State
  isListening: boolean,         // voiceState === LISTENING
  isThinking: boolean,          // voiceState === THINKING
  isSpeaking: boolean,          // voiceState === SPEAKING
  isIdle: boolean,              // voiceState === IDLE
  isInactive: boolean,          // voiceState === INACTIVE
}
```

### VoiceState Enum

```javascript
export const VoiceState = {
  INACTIVE: 'inactive',   // Voice system not started
  IDLE: 'idle',          // Ready, waiting for input
  LISTENING: 'listening', // Recording user speech
  THINKING: 'thinking',   // Processing / generating response
  SPEAKING: 'speaking',   // Playing Luna's response
};
```

### API Endpoints Called

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/voice/stream` | GET (SSE) | Real-time voice status stream |
| `/voice/status` | GET | Initial voice system status |
| `/voice/start` | POST | Start voice system |
| `/voice/stop` | POST | Stop voice system |
| `/voice/listen/start` | POST | Begin push-to-talk recording |
| `/voice/listen/stop` | POST | End recording, get transcription |
| `/voice/speak` | POST | Speak text via TTS |

### SSE Connections Managed

**`/voice/stream` EventSource:**

| Event Type | Data Fields | Purpose |
|------------|-------------|---------|
| `status` | `{ running, status }` | System status updates |
| `transcription` | `{ text }` | Transcribed user speech |
| `response` | `{ text }` | Luna's text response |
| `ping` | `{ running }` | Keep-alive with status |

### Dependencies

**React Hooks:**
- `useState` - Voice state, transcription, response, error
- `useEffect` - SSE connection lifecycle
- `useCallback` - Memoized action functions
- `useRef` - EventSource reference

**Browser APIs:**
- `EventSource` - SSE connection to `/voice/stream`
- `fetch` - HTTP requests

### Side Effects

1. **SSE Connection** - Maintains persistent EventSource connection to `/voice/stream`
2. **Auto-reconnect** - Reconnects after 3 seconds on SSE error
3. **Thinking timeout** - 10-second fallback to reset state if SSE doesn't report completion
4. **Initial status fetch** - Fetches `/voice/status` on mount

### Code Analysis

```javascript
// SSE connection with auto-reconnect
const connectStream = useCallback(() => {
  if (eventSourceRef.current) {
    eventSourceRef.current.close();
  }

  const es = new EventSource(`${API_BASE}/voice/stream`);

  es.addEventListener('status', (e) => {
    const data = JSON.parse(e.data);
    setIsRunning(data.running);
    if (data.status) setVoiceState(data.status);
  });

  es.onerror = (err) => {
    es.close();
    if (eventSourceRef.current === es) {
      eventSourceRef.current = null;
      setTimeout(connectStream, 3000); // Reconnect
    }
  };

  eventSourceRef.current = es;
}, []);
```

---

## Usage Patterns

### Pattern 1: Main Application Integration (App.jsx)

All three hooks are used together in the main `LunaHub` component:

```javascript
// /frontend/src/App.jsx

import { useLunaAPI } from './hooks/useLunaAPI';
import { useChat } from './hooks/useChat';
import { useVoice } from './hooks/useVoice';

const LunaHub = () => {
  // Core API for status/consciousness
  const {
    status,
    consciousness,
    isConnected,
    error: apiError,
    relaunchSystem,
    refresh,
  } = useLunaAPI();

  // Streaming chat (uses /persona/stream)
  const {
    messages,
    context,
    isStreaming,
    error: chatError,
    send,
  } = useChat();

  // Voice for TTS when active
  const voice = useVoice();

  // Auto-speak completed assistant messages
  useEffect(() => {
    if (!voice.isRunning || isStreaming) return;
    const lastMsg = messages[messages.length - 1];
    if (lastMsg?.role === 'assistant' && !lastMsg.streaming && lastMsg.content) {
      voice.speakResponse(lastMsg.content);
    }
  }, [messages, isStreaming, voice.isRunning]);

  // Persist messages to localStorage
  useEffect(() => {
    if (messages.length > 0) {
      localStorage.setItem('luna_chat_messages', JSON.stringify(messages));
    }
  }, [messages]);

  return (
    <ChatPanel messages={messages} onSend={send} isLoading={isStreaming} />
    <VoicePanel voiceHook={voice} />
    <EngineStatus status={status} onRelaunch={relaunchSystem} />
  );
};
```

### Pattern 2: VoicePanel Component (VoicePanel.jsx)

The `useVoice` hook can be used standalone or receive an instance from a parent:

```javascript
// /frontend/src/components/VoicePanel.jsx

import { useVoice, VoiceState } from '../hooks/useVoice';

const VoicePanel = ({ voiceHook }) => {
  // Use provided hook or create own instance
  const internalVoice = useVoice();
  const voice = voiceHook || internalVoice;

  const {
    voiceState,
    isRunning,
    startVoice,
    stopVoice,
    startListening,
    stopListening,
    isListening,
    isThinking,
  } = voice;

  // Push-to-talk handler
  const handleMicDown = useCallback(async (e) => {
    if (!isRunning) return;
    await startListening();
  }, [isRunning, startListening]);

  const handleMicUp = useCallback(async (e) => {
    if (!isRunning) return;
    const result = await stopListening();
    // Handle result.transcription or result.no_speech
  }, [isRunning, stopListening]);

  return (
    <button
      onMouseDown={handleMicDown}
      onMouseUp={handleMicUp}
    >
      {isListening ? 'Recording...' : 'Hold to speak'}
    </button>
  );
};
```

### Pattern 3: Shared Voice State

To share voice state between parent and child components:

```javascript
// Parent component
const voice = useVoice();

// Pass to child - child won't create duplicate SSE connections
<VoicePanel voiceHook={voice} />
<ChatPanel onVoiceTranscript={voice.transcription} />
```

---

## Hook Dependency Graph

```
useLunaAPI
    |
    v
useChat (depends on useLunaAPI.streamPersona, abort, isLoading, error)

useVoice (independent - manages its own SSE connection)
```

---

## Configuration

### API Base URL

All hooks use a hardcoded constant:

```javascript
const API_BASE = 'http://localhost:8000';
```

This should be moved to an environment variable for production:

```javascript
const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:8000';
```

---

## Error Handling

### useLunaAPI
- Sets `error` state on failed requests
- Returns `null` on failure (caller can check result)
- Silently catches health check failures

### useChat
- Inherits error handling from useLunaAPI
- Updates message with error flag on stream failures
- Resets `isStreaming` on error

### useVoice
- Sets `error` state on failed requests
- Returns `null` or error objects from actions
- Logs SSE errors to console, auto-reconnects

---

## Performance Considerations

1. **Polling Interval** - `useLunaAPI` polls every 2 seconds; consider WebSocket for production
2. **SSE Reconnection** - `useVoice` reconnects after 3 seconds on failure
3. **State Updates** - Token streaming updates state on every token; consider debouncing for high-frequency updates
4. **Memoization** - All action functions are wrapped in `useCallback`

---

## Testing Notes

1. Mock `fetch` and `EventSource` for unit tests
2. Test SSE reconnection logic
3. Test push-to-talk timing (minimum hold duration)
4. Test state transitions in voice system
5. Test concurrent message handling

---

## Related Files

- `/frontend/src/App.jsx` - Main application using all hooks
- `/frontend/src/components/VoicePanel.jsx` - Voice UI component
- `/frontend/src/components/ChatPanel.jsx` - Chat UI component (uses `useChat` via props)
