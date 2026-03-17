import { useState, useCallback, useRef, useEffect } from 'react';
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
  if (command === '/options-test') {
    return { command, isLocal: true, type: 'options-test' };
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
    // Skill slash commands
    '/math':       { endpoint: '/slash/skill/math',       method: 'POST', hasBody: true },
    '/logic':      { endpoint: '/slash/skill/logic',      method: 'POST', hasBody: true },
    '/read':       { endpoint: '/slash/skill/reading',    method: 'POST', hasBody: true },
    '/diagnostic': { endpoint: '/slash/skill/diagnostic', method: 'POST', hasBody: true },
    '/eden':       { endpoint: '/slash/skill/eden',       method: 'POST', hasBody: true },
    '/format':     { endpoint: '/slash/skill/formatting', method: 'POST', hasBody: true },
    '/analytics':  { endpoint: '/slash/skill/analytics',  method: 'POST', hasBody: true },
    // System prompt diagnostic
    '/prompt': { endpoint: '/slash/prompt', method: 'GET' },
    // FaceID management
    '/faceid': {
      endpoint: args
        ? `/slash/faceid/${encodeURIComponent(args)}`
        : '/slash/faceid',
      method: args && (args.startsWith('set-pin') || args.startsWith('reset')) ? 'POST' : 'GET',
    },
  };

  const cmd = commands[command];
  if (!cmd) return null;
  if (cmd.requiresArg && !args) return { error: `${command} requires an argument` };

  return { ...cmd, command, args };
};

const CHAT_STORAGE_KEY = 'luna_chat_messages';

const loadPersistedMessages = () => {
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        // Strip any stale streaming flags from recovered messages
        return parsed.map((m) => ({ ...m, streaming: false }));
      }
    }
  } catch {}
  return [];
};

let _msgCounter = 0;
const nextId = (prefix = 'msg') => `${prefix}-${Date.now()}-${++_msgCounter}`;

export function useChat() {
  const { streamPersona, abort, isLoading, error } = useLunaAPI();

  const [messages, setMessages] = useState(loadPersistedMessages);
  const [context, setContext] = useState(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const streamingRef = useRef('');
  const wsRef = useRef(null);
  const processedIdsRef = useRef(new Set());

  // Connect to chat WebSocket for shared session viewing
  // This allows seeing messages sent via API/curl/MCP in real-time
  useEffect(() => {
    const connectWebSocket = () => {
      try {
        const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const ws = new WebSocket(`${wsProto}//${window.location.host}/ws/chat`);

        ws.onopen = () => {
          console.log('[Chat WS] Connected to shared session');
        };

        ws.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data);
            const msgId = `ws-${payload.timestamp}`;

            // Skip if we've already processed this message (dedup)
            if (processedIdsRef.current.has(msgId)) {
              return;
            }
            processedIdsRef.current.add(msgId);

            // Only add if not currently streaming (avoid duplicates from our own sends)
            if (payload.type === 'user') {
              setMessages((prev) => [
                ...prev,
                {
                  id: msgId,
                  role: 'user',
                  content: payload.data.content,
                  external: true,  // Mark as external message
                },
              ]);
            } else if (payload.type === 'assistant') {
              setMessages((prev) => [
                ...prev,
                {
                  id: msgId,
                  role: 'assistant',
                  content: payload.data.content,
                  model: payload.data.model,
                  delegated: payload.data.delegated,
                  local: payload.data.local,
                  latency: payload.data.latency_ms,
                  groundingMetadata: payload.data.groundingMetadata || null,
                  external: true,
                },
              ]);
            }
          } catch (e) {
            console.error('[Chat WS] Failed to parse message:', e);
          }
        };

        ws.onclose = () => {
          console.log('[Chat WS] Disconnected, reconnecting in 3s...');
          setTimeout(connectWebSocket, 3000);
        };

        ws.onerror = (e) => {
          console.error('[Chat WS] Error:', e);
        };

        wsRef.current = ws;
      } catch (e) {
        console.error('[Chat WS] Failed to connect:', e);
        setTimeout(connectWebSocket, 3000);
      }
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  // Execute a slash command
  const executeSlashCommand = useCallback(async (text, parsed) => {
    // Add user message
    setMessages((prev) => [...prev, { id: nextId('user'), role: 'user', content: text }]);

    // Show loading
    const msgId = nextId('cmd');
    setMessages((prev) => [
      ...prev,
      { id: msgId, role: 'assistant', content: 'Running command...', streaming: true, isCommand: true },
    ]);

    try {
      const response = await fetch(parsed.endpoint, {
        method: parsed.method,
        ...(parsed.hasBody ? {
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ query: parsed.args || '' }),
        } : {}),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

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
          { id: nextId('user'), role: 'user', content: text },
          { id: nextId('err'), role: 'assistant', content: parsed.error, error: true },
        ]);
        return;
      }

      // Handle local commands
      if (parsed.isLocal) {
        if (parsed.type === 'animate') {
          const randomAnim = ORB_ANIMATIONS[Math.floor(Math.random() * ORB_ANIMATIONS.length)];
          setMessages((prev) => [
            ...prev,
            { id: nextId('user'), role: 'user', content: text },
            {
              id: nextId('cmd'),
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
            { id: nextId('user'), role: 'user', content: text },
            {
              id: nextId('cmd'),
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
            { id: nextId('user'), role: 'user', content: text },
            {
              id: nextId('cmd'),
              role: 'assistant',
              content: `🎬 Testing all ${ORB_ANIMATIONS.length} animations...`,
              isCommand: true,
              commandSuccess: true,
            },
          ]);
          return { type: 'orb-test', animations: ORB_ANIMATIONS };
        }

        if (parsed.type === 'options-test') {
          setMessages((prev) => [
            ...prev,
            { id: nextId('user'), role: 'user', content: text },
            {
              id: nextId('cmd'),
              role: 'assistant',
              content: 'Here are some options to test the widget:',
              isCommand: true,
              commandSuccess: true,
              widget: {
                type: 'options',
                skill: null,
                data: {
                  prompt: 'test options',
                  options: [
                    { label: 'Build a REST API', value: 'Build a REST API' },
                    { label: 'Create a CLI tool', value: 'Create a CLI tool' },
                    { label: 'Design a web app', value: 'Design a web app' },
                  ],
                  style: 'buttons',
                },
                latex: null,
              },
            },
          ]);
          return;
        }

        if (parsed.type === 'restart-frontend') {
          setMessages((prev) => [
            ...prev,
            { id: nextId('user'), role: 'user', content: text },
            {
              id: nextId('cmd'),
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
    const userMsg = { id: nextId('user'), role: 'user', content: text };
    setMessages((prev) => [...prev, userMsg]);

    // Prepare assistant message placeholder
    const assistantMsgId = nextId('ast');
    setMessages((prev) => [
      ...prev,
      { id: assistantMsgId, role: 'assistant', content: '', streaming: true },
    ]);

    streamingRef.current = '';
    setIsStreaming(true);
    setContext(null);

    let streamDone = false;

    try {
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
          streamDone = true;
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
                    delegated: result.metadata?.model?.includes('claude') || result.metadata?.delegated === true,
                    local: result.metadata?.model?.includes('qwen') || result.metadata?.local === true,
                    accessDeniedCount: result.metadata?.access_denied_count || 0,
                    groundingMetadata: result.groundingMetadata || null,
                    lunascript: result.metadata?.lunascript || null,
                    widget: result.metadata?.widget || null,
                  }
                : m
            )
          );
          setIsStreaming(false);
        },

        onError: (msg) => {
          streamDone = true;
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
    } finally {
      // Safety net: if stream ended without done/error event, unlock the UI
      if (!streamDone) {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantMsgId
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
