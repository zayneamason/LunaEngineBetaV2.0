import { useState, useCallback, useRef } from 'react';
import { useLunaAPI } from './useLunaAPI';

/**
 * useChat - React hook for streaming chat with Luna
 *
 * Uses the context-first /persona/stream endpoint.
 * Context (memory, state) arrives BEFORE tokens start streaming.
 *
 * Supports slash commands:
 *   /health, /find-person <name>, /stats, /search <query>, /recent, /extraction, /help
 *   /voice-tuning, /orb-settings, /performance, /emotion <name>, /reset-performance
 *   /llm, /llm-switch <provider>
 */

// Available orb animations
const ORB_ANIMATIONS = [
  'pulse', 'pulse_fast', 'spin', 'spin_fast', 'flicker',
  'wobble', 'drift', 'orbit', 'glow', 'split'
];

// Parse slash commands
const parseSlashCommand = (text) => {
  const trimmed = text.trim();
  if (!trimmed.startsWith('/')) return null;

  const parts = trimmed.split(/\s+/);
  const command = parts[0].toLowerCase();
  const args = parts.slice(1).join(' ');

  // Local commands (handled client-side)
  if (command === '/animate') {
    return { command, isLocal: true, type: 'animate' };
  }
  if (command === '/orb') {
    return { command, isLocal: true, type: 'orb-status' };
  }
  if (command === '/orb-test') {
    return { command, isLocal: true, type: 'orb-test' };
  }
  if (command === '/restart-frontend') {
    return { command, isLocal: true, type: 'restart-frontend' };
  }

  const commands = {
    '/health': { endpoint: '/slash/health', method: 'GET' },
    '/stats': { endpoint: '/slash/stats', method: 'GET' },
    '/recent': { endpoint: '/slash/recent', method: 'GET' },
    '/extraction': { endpoint: '/slash/extraction', method: 'GET' },
    '/help': { endpoint: '/slash/help', method: 'GET' },
    '/find-person': { endpoint: `/slash/find-person/${encodeURIComponent(args)}`, method: 'GET', requiresArg: true },
    '/search': { endpoint: `/slash/search/${encodeURIComponent(args)}`, method: 'GET', requiresArg: true },
    // Performance layer commands
    '/performance': { endpoint: '/slash/performance', method: 'GET' },
    '/emotion': { endpoint: `/slash/emotion/${encodeURIComponent(args)}`, method: 'GET', requiresArg: true },
    '/reset-performance': { endpoint: '/slash/reset-performance', method: 'POST' },
    // LLM provider commands
    '/llm': { endpoint: '/slash/llm', method: 'GET' },
    '/llm-switch': { endpoint: `/slash/llm-switch/${encodeURIComponent(args)}`, method: 'GET', requiresArg: true },
    // Restart commands
    '/restart-backend': { endpoint: '/slash/restart-backend', method: 'POST' },
    // Voight-Kampff identity test
    '/vk': { endpoint: '/slash/vk', method: 'GET' },
    '/voight-kampff': { endpoint: '/slash/voight-kampff', method: 'GET' },
  };

  const cmd = commands[command];
  if (!cmd) return null;
  if (cmd.requiresArg && !args) return { error: `${command} requires an argument` };

  return { ...cmd, command, args };
};

export function useChat() {
  const { streamPersona, abort, isLoading, error } = useLunaAPI();

  const [messages, setMessages] = useState([]);
  const [context, setContext] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const streamingRef = useRef('');

  // Execute a slash command
  const executeSlashCommand = useCallback(async (text, parsed) => {
    // Add user message
    setMessages((prev) => [...prev, { role: 'user', content: text }]);

    // Show loading
    const msgId = Date.now();
    setMessages((prev) => [
      ...prev,
      { id: msgId, role: 'assistant', content: 'Running command...', streaming: true, isCommand: true },
    ]);

    try {
      const response = await fetch(`http://localhost:8000${parsed.endpoint}`, {
        method: parsed.method,
      });

      const data = await response.json();

      // Update with formatted response
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId
            ? {
                ...m,
                content: data.formatted || JSON.stringify(data.data, null, 2),
                streaming: false,
                isCommand: true,
                commandSuccess: data.success,
              }
            : m
        )
      );
    } catch (err) {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === msgId
            ? { ...m, content: `Command failed: ${err.message}`, streaming: false, error: true }
            : m
        )
      );
    }
  }, []);

  // Send a message and stream the response
  // Optional context param for local commands that need extra data
  const send = useCallback(async (text, context = {}) => {
    if (!text.trim() || isStreaming) return;

    // Check for slash command
    const parsed = parseSlashCommand(text);
    if (parsed) {
      if (parsed.error) {
        setMessages((prev) => [
          ...prev,
          { role: 'user', content: text },
          { role: 'assistant', content: parsed.error, error: true },
        ]);
        return;
      }

      // Handle local commands
      if (parsed.isLocal) {
        if (parsed.type === 'animate') {
          const randomAnim = ORB_ANIMATIONS[Math.floor(Math.random() * ORB_ANIMATIONS.length)];
          setMessages((prev) => [
            ...prev,
            { role: 'user', content: text },
            {
              role: 'assistant',
              content: `✨ Triggered animation: **${randomAnim}**`,
              isCommand: true,
              commandSuccess: true,
            },
          ]);
          return { type: 'animate', animation: randomAnim };
        }

        if (parsed.type === 'orb-status') {
          const orb = context.orbState || {};
          const statusContent = `🔮 **Orb Diagnostics**

**Connection:** ${orb.isConnected ? '✓ Connected' : '✗ Disconnected'}
**Current Animation:** ${orb.animation || 'unknown'}
**Color:** ${orb.color || 'unknown'}
**Brightness:** ${orb.brightness || 'unknown'}
**Override Active:** ${orb.override ? `Yes (${orb.override})` : 'No'}

**Available Animations:**
pulse, pulse_fast, spin, spin_fast, flicker, wobble, drift, orbit, glow, split`;

          setMessages((prev) => [
            ...prev,
            { role: 'user', content: text },
            {
              role: 'assistant',
              content: statusContent,
              isCommand: true,
              commandSuccess: true,
            },
          ]);
          return { type: 'orb-status' };
        }

        if (parsed.type === 'orb-test') {
          setMessages((prev) => [
            ...prev,
            { role: 'user', content: text },
            {
              role: 'assistant',
              content: `🎬 Testing all ${ORB_ANIMATIONS.length} animations...`,
              isCommand: true,
              commandSuccess: true,
            },
          ]);
          return { type: 'orb-test', animations: ORB_ANIMATIONS };
        }

        if (parsed.type === 'restart-frontend') {
          setMessages((prev) => [
            ...prev,
            { role: 'user', content: text },
            {
              role: 'assistant',
              content: `🔄 Reloading frontend in 1 second...`,
              isCommand: true,
              commandSuccess: true,
            },
          ]);
          setTimeout(() => {
            window.location.reload();
          }, 1000);
          return { type: 'restart-frontend' };
        }

        return;
      }

      return executeSlashCommand(text, parsed);
    }

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
  }, [streamPersona, isStreaming, executeSlashCommand]);

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
