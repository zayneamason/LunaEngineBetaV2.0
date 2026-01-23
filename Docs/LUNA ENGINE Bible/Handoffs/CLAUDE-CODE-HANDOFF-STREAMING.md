# Claude Code Handoff: Streaming Responses

**Date:** 2025-01-21  
**Author:** Dude (Architecture) + Ahab  
**Priority:** P1 - Core UX Enhancement  
**Estimated Scope:** Medium (3-4 files backend, 2-3 files frontend)

---

## 1. Problem Statement

Currently, Luna's responses arrive as a single block after the full generation completes. This creates:
- Dead time during generation (3-10s silence)
- Poor perceived latency
- No visual feedback during thinking

**Goal:** Stream LLM tokens to frontend in real-time, updating chat/voice UI incrementally.

---

## 2. Current Architecture

### What EXISTS:
```python
# voice/llm/claude.py - streaming IS implemented
async def stream_generate(...) -> AsyncIterator[LLMResponse]:
    with self._client.messages.stream(...) as stream:
        for text in stream.text_stream:
            yield LLMResponse(text=text, finished=False)
    yield LLMResponse(text="", finished=True)
```

### What DOESN'T exist:
1. Hub API streaming endpoint
2. PersonaCore streaming pass-through
3. Frontend streaming consumption

---

## 3. Implementation Plan

### Layer 1: Hub API Streaming Endpoint

**File:** `src/hub/api.py`

Add SSE endpoint:

```python
from fastapi.responses import StreamingResponse
import json

@app.post("/persona/stream")
async def stream_message(request: ProcessMessageRequest):
    """
    Stream Luna's response token-by-token via Server-Sent Events.
    
    Event format:
    - data: {"type": "token", "text": "chunk"}
    - data: {"type": "context", "memory": [...], "state": {...}}
    - data: {"type": "done"}
    - data: {"type": "error", "message": "..."}
    """
    if not _persona_core:
        raise HTTPException(status_code=503, detail="PersonaCore not available")
    
    async def event_stream():
        try:
            # First: send context (memory, state) immediately
            context = await _persona_core.get_context_for_query(
                query=request.message,
                budget="balanced"
            )
            
            yield f"data: {json.dumps({'type': 'context', 'memory': context.memory_context, 'state': context.luna_state})}\n\n"
            
            # Stream tokens
            async for chunk in _persona_core.stream_response(
                query=request.message,
                context=context
            ):
                yield f"data: {json.dumps({'type': 'token', 'text': chunk.text})}\n\n"
            
            # Done
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            
        except Exception as e:
            logger.error(f"Streaming failed: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    
    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
```

### Layer 2: PersonaCore Streaming

**File:** `src/persona/core.py`

Add streaming method:

```python
async def stream_response(
    self,
    query: str,
    context: EnrichedContext
) -> AsyncIterator[LLMResponse]:
    """
    Stream LLM response tokens.
    
    Args:
        query: User's message
        context: Pre-fetched context from get_context_for_query
        
    Yields:
        LLMResponse with incremental text chunks
    """
    # Build messages
    messages = [{"role": "user", "content": query}]
    
    # Get LLM provider (Claude or local)
    llm = self._get_llm_provider()
    
    # Stream through provider
    async for chunk in llm.stream_generate(
        messages=messages,
        system_prompt=context.to_system_prompt(),
        context=""  # Already in system prompt
    ):
        yield chunk

async def get_context_for_query(
    self,
    query: str,
    budget: str = "balanced"
) -> EnrichedContext:
    """
    Get enriched context without generating response.
    Used for streaming where context is sent first.
    """
    # Existing context building logic extracted from process_query
    ...
```

### Layer 3: Frontend Hook

**File:** `src/eclissi/hooks/useChat.js` (new file)

```javascript
import { useState, useCallback, useRef } from 'react';

export const useChat = (config = {}) => {
  const hubUrl = config.hubUrl || 'http://localhost:8882';
  
  const [messages, setMessages] = useState([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);
  const [currentResponse, setCurrentResponse] = useState('');
  const abortControllerRef = useRef(null);

  const sendMessage = useCallback(async (userMessage) => {
    setError(null);
    setIsStreaming(true);
    setCurrentResponse('');
    
    // Add user message
    const userMsg = { role: 'user', content: userMessage, timestamp: Date.now() };
    setMessages(prev => [...prev, userMsg]);
    
    // Create abort controller for cancellation
    abortControllerRef.current = new AbortController();
    
    try {
      const response = await fetch(`${hubUrl}/persona/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMessage }),
        signal: abortControllerRef.current.signal
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullResponse = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        // Parse SSE events
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            
            switch (data.type) {
              case 'token':
                fullResponse += data.text;
                setCurrentResponse(fullResponse);
                break;
                
              case 'context':
                // Store context for UI (memory, state)
                console.log('[Chat] Context received:', data);
                break;
                
              case 'done':
                // Add complete assistant message
                setMessages(prev => [...prev, {
                  role: 'assistant',
                  content: fullResponse,
                  timestamp: Date.now()
                }]);
                break;
                
              case 'error':
                throw new Error(data.message);
            }
          }
        }
      }
      
    } catch (e) {
      if (e.name !== 'AbortError') {
        setError(e.message);
        console.error('[Chat] Stream error:', e);
      }
    } finally {
      setIsStreaming(false);
      setCurrentResponse('');
    }
  }, [hubUrl]);

  const cancelStream = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  }, []);

  return {
    messages,
    currentResponse,
    isStreaming,
    error,
    sendMessage,
    cancelStream,
    setMessages
  };
};

export default useChat;
```

### Layer 4: Chat UI Component

**File:** `src/eclissi/pages/Chat.jsx` (new file or integrate into existing)

```jsx
import React, { useState, useRef, useEffect } from 'react';
import { useChat } from '../hooks/useChat';

const ChatMessage = ({ message, isStreaming }) => (
  <div className={`p-4 ${message.role === 'user' ? 'bg-violet-500/10' : 'bg-black/20'} rounded-lg`}>
    <div className="text-xs text-white/40 mb-1">
      {message.role === 'user' ? 'You' : 'Luna'}
    </div>
    <div className="text-white/90 whitespace-pre-wrap">
      {message.content}
      {isStreaming && <span className="animate-pulse">▊</span>}
    </div>
  </div>
);

export const Chat = () => {
  const { messages, currentResponse, isStreaming, error, sendMessage, cancelStream } = useChat();
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentResponse]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isStreaming) {
      sendMessage(input.trim());
      setInput('');
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <ChatMessage key={i} message={msg} />
        ))}
        
        {/* Streaming response */}
        {isStreaming && currentResponse && (
          <ChatMessage 
            message={{ role: 'assistant', content: currentResponse }}
            isStreaming={true}
          />
        )}
        
        <div ref={messagesEndRef} />
      </div>

      {/* Error */}
      {error && (
        <div className="px-4 py-2 bg-red-500/20 text-red-400 text-sm">
          Error: {error}
        </div>
      )}

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-4 border-t border-white/10">
        <div className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Message Luna..."
            disabled={isStreaming}
            className="flex-1 px-4 py-3 bg-black/30 border border-white/20 rounded-lg text-white placeholder-white/40 focus:outline-none focus:border-violet-500"
          />
          {isStreaming ? (
            <button
              type="button"
              onClick={cancelStream}
              className="px-6 py-3 bg-red-500/20 border border-red-500/40 rounded-lg text-red-400"
            >
              Stop
            </button>
          ) : (
            <button
              type="submit"
              className="px-6 py-3 bg-violet-500 rounded-lg text-white disabled:opacity-50"
              disabled={!input.trim()}
            >
              Send
            </button>
          )}
        </div>
      </form>
    </div>
  );
};

export default Chat;
```

---

## 4. Voice Streaming (Bonus)

For voice, the streaming path is more complex because we need TTS chunking.

**Pattern:**
```
tokens → sentence boundary detection → TTS → audio chunks → playback
```

This requires:
1. Token accumulator with sentence detection
2. TTS queue that processes complete sentences
3. Audio playback queue

**File:** `src/voice/llm/streaming_tts.py` (future)

```python
class StreamingTTSAdapter:
    """
    Accumulates LLM tokens, detects sentence boundaries,
    and sends complete sentences to TTS.
    """
    
    SENTENCE_ENDINGS = {'.', '!', '?', '...', '—'}
    
    def __init__(self, tts_provider):
        self.buffer = ""
        self.tts = tts_provider
        self.audio_queue = asyncio.Queue()
    
    async def process_token(self, token: str):
        """Add token, emit TTS audio if sentence complete."""
        self.buffer += token
        
        # Check for sentence boundary
        for ending in self.SENTENCE_ENDINGS:
            if self.buffer.rstrip().endswith(ending):
                sentence = self.buffer.strip()
                self.buffer = ""
                
                # Generate TTS for sentence
                audio = await self.tts.synthesize(sentence)
                await self.audio_queue.put(audio)
                break
    
    async def flush(self):
        """Flush remaining buffer."""
        if self.buffer.strip():
            audio = await self.tts.synthesize(self.buffer.strip())
            await self.audio_queue.put(audio)
            self.buffer = ""
```

---

## 5. Files to Modify

### Backend
| File | Change |
|------|--------|
| `src/hub/api.py` | Add `/persona/stream` SSE endpoint |
| `src/persona/core.py` | Add `stream_response()` and `get_context_for_query()` |

### Frontend
| File | Change |
|------|--------|
| `src/eclissi/hooks/useChat.js` | NEW - streaming chat hook |
| `src/eclissi/pages/Chat.jsx` | NEW or MODIFY - chat UI |
| `src/eclissi/hooks/index.js` | Export useChat |

### Future (Voice TTS streaming)
| File | Change |
|------|--------|
| `src/voice/llm/streaming_tts.py` | NEW - sentence-based TTS adapter |
| `src/voice/backend.py` | Integrate streaming TTS |

---

## 6. Testing Checklist

- [ ] Stream starts within 200ms of request
- [ ] Tokens appear incrementally in UI
- [ ] Full message saved to Memory Matrix on completion
- [ ] Cancel button stops stream cleanly
- [ ] Error state shows if stream fails
- [ ] Context (memory, state) received before tokens
- [ ] Multiple concurrent chats work (session isolation)

---

## 7. Trade-offs

**Chose SSE over WebSocket because:**
- Simpler client implementation
- Built-in reconnection semantics
- Better for unidirectional streams
- Hub already has WebSocket for voice; this keeps concerns separate

**We lose:**
- Bidirectional communication (not needed for chat)
- Binary data support (not needed for text)

---

## 8. Execution Order

1. **Backend first:** Add streaming endpoint (testable via curl)
2. **Hook second:** `useChat.js` (testable in isolation)
3. **UI third:** Chat component integration
4. **Voice TTS:** Future phase (optional for this handoff)

---

## Questions?

This handoff covers text streaming for chat. Voice TTS streaming is a separate concern that can be tackled after this foundation is in place.

The pattern here also enables future features like:
- Typing indicators ("Luna is thinking...")
- Token-by-token animations
- Real-time token counting for context management
