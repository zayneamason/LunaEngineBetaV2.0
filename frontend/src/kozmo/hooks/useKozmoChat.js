import { useState, useCallback, useRef } from 'react';

/**
 * useKozmoChat — Streaming chat hook for KOZMO modes
 *
 * Connects to Luna's /persona/stream SSE endpoint.
 * Project scope is already activated by KozmoProvider.loadProject().
 *
 * Returns: { messages, context, isStreaming, error, send, stop, clear }
 */

const API_BASE = '';

async function streamPersona(message, { onContext, onToken, onDone, onError }) {
  const res = await fetch(`${API_BASE}/persona/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, timeout: 120.0 }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Stream failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));
          switch (data.type) {
            case 'context': onContext?.(data); break;
            case 'token':   onToken?.(data.text); break;
            case 'done':    onDone?.(data); break;
            case 'error':   onError?.(data.message); break;
          }
        } catch {}
      }
    }
  }
}

export function useKozmoChat() {
  const [messages, setMessages] = useState([]);
  const [context, setContext] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState(null);
  const streamingRef = useRef('');
  const pageContextRef = useRef('');

  // Set what's currently visible on screen — callers update this as the view changes
  const setPageContext = useCallback((ctx) => {
    pageContextRef.current = ctx || '';
  }, []);

  const send = useCallback(async (text) => {
    if (!text.trim() || isStreaming) return;

    // Add user message (shows their raw text, not the context prefix)
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', content: text }]);

    // Build the actual message Luna sees: page context + user text
    const contextPrefix = pageContextRef.current;
    const apiMessage = contextPrefix
      ? `[KOZMO CONTEXT: ${contextPrefix}]\n\nUser says: ${text}`
      : text;

    // Placeholder for assistant response
    const assistantId = Date.now() + 1;
    setMessages(prev => [
      ...prev,
      { id: assistantId, role: 'assistant', content: '', streaming: true },
    ]);

    streamingRef.current = '';
    setIsStreaming(true);
    setContext(null);
    setError(null);

    let streamDone = false;

    try {
      await streamPersona(apiMessage, {
        onContext: (ctx) => {
          setContext(ctx);
        },
        onToken: (token) => {
          streamingRef.current += token;
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId ? { ...m, content: streamingRef.current } : m
            )
          );
        },
        onDone: (result) => {
          streamDone = true;
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? {
                    ...m,
                    content: result.response || streamingRef.current,
                    streaming: false,
                    metadata: result.metadata,
                    delegated: result.metadata?.model?.includes('claude'),
                    local: result.metadata?.model?.includes('qwen'),
                    latency: result.metadata?.generation_time_ms,
                    tokens: result.metadata?.output_tokens,
                  }
                : m
            )
          );
          setIsStreaming(false);
        },
        onError: (msg) => {
          streamDone = true;
          setError(msg);
          setMessages(prev =>
            prev.map(m =>
              m.id === assistantId
                ? { ...m, content: `Error: ${msg}`, streaming: false, error: true }
                : m
            )
          );
          setIsStreaming(false);
        },
      });
    } catch (e) {
      streamDone = true;
      setError(e.message);
      setMessages(prev =>
        prev.map(m =>
          m.id === assistantId
            ? { ...m, content: `Error: ${e.message}`, streaming: false, error: true }
            : m
        )
      );
      setIsStreaming(false);
    } finally {
      // Safety net: if stream ended without done/error, unlock UI
      if (!streamDone) {
        setMessages(prev =>
          prev.map(m =>
            m.id === assistantId
              ? {
                  ...m,
                  content: streamingRef.current || 'Connection lost — try again.',
                  streaming: false,
                  error: !streamingRef.current,
                }
              : m
          )
        );
        setIsStreaming(false);
      }
    }
  }, [isStreaming]);

  const stop = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/abort`, { method: 'POST' });
    } catch {}
    setIsStreaming(false);
  }, []);

  const clear = useCallback(() => {
    setMessages([]);
    setContext(null);
    setError(null);
  }, []);

  return { messages, context, isStreaming, error, send, stop, clear, setPageContext };
}
