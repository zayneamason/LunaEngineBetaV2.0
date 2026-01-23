import { useState, useCallback, useRef } from 'react';
import { useLunaAPI } from './useLunaAPI';

/**
 * useChat - React hook for streaming chat with Luna
 *
 * Uses the context-first /persona/stream endpoint.
 * Context (memory, state) arrives BEFORE tokens start streaming.
 */
export function useChat() {
  const { streamPersona, abort, isLoading, error } = useLunaAPI();

  const [messages, setMessages] = useState([]);
  const [context, setContext] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const streamingRef = useRef('');

  // Send a message and stream the response
  const send = useCallback(async (text) => {
    if (!text.trim() || isStreaming) return;

    // Add user message
    const userMsg = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);

    // Prepare assistant message placeholder
    const assistantMsgId = Date.now();
    setMessages((prev) => [
      ...prev,
      { id: assistantMsgId, role: 'assistant', content: '', streaming: true },
    ]);

    streamingRef.current = '';
    setIsStreaming(true);
    setContext(null);

    await streamPersona(text, {
      onContext: (ctx) => {
        // Context arrives first - store it for UI
        setContext(ctx);
      },

      onToken: (token) => {
        // Accumulate tokens
        streamingRef.current += token;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? { ...m, content: streamingRef.current }
              : m
          )
        );
      },

      onDone: (result) => {
        // Finalize the message with metadata
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? {
                  ...m,
                  content: result.response || streamingRef.current,
                  streaming: false,
                  metadata: result.metadata,
                  tokens: result.metadata?.output_tokens,
                  latency: result.metadata?.generation_time_ms,
                  delegated: result.metadata?.model?.includes('claude'),
                  local: result.metadata?.model?.includes('qwen'),
                }
              : m
          )
        );
        setIsStreaming(false);
      },

      onError: (msg) => {
        // Update message with error
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
              ? { ...m, content: `Error: ${msg}`, streaming: false, error: true }
              : m
          )
        );
        setIsStreaming(false);
      },
    });
  }, [streamPersona, isStreaming]);

  // Abort current generation
  const stop = useCallback(() => {
    abort();
    setIsStreaming(false);
  }, [abort]);

  // Clear chat history
  const clear = useCallback(() => {
    setMessages([]);
    setContext(null);
  }, []);

  return {
    messages,
    context,
    isStreaming,
    isLoading,
    error,
    send,
    stop,
    clear,
  };
}
