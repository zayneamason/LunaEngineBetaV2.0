import { create } from 'zustand';
import { useEffect, useRef } from 'react';

/**
 * useGuardianLuna — Zustand store + event aggregation for the Guardian Luna panel.
 *
 * Aggregates knowledge stream events into Guardian messages (session summaries,
 * entity health notices, recommendations). Polls Observatory stats for the
 * stats footer. No LLM backend — that's Phase 6.
 */
const useGuardianStore = create((set, get) => ({
  isOpen: false,
  messages: [],
  stats: null,
  inputText: '',

  toggle: () => set((s) => ({ isOpen: !s.isOpen })),
  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),

  addMessage: (msg) =>
    set((s) => ({ messages: [...s.messages.slice(-50), { ...msg, ts: Date.now() }] })),

  setStats: (stats) => set({ stats }),
  setInputText: (inputText) => set({ inputText }),

  isStreaming: false,

  sendMessage: async (text) => {
    if (!text.trim()) return;
    const { addMessage } = get();

    // Add user message immediately
    set((s) => ({
      messages: [...s.messages, { type: 'user', content: text, ts: Date.now() }],
      inputText: '',
      isStreaming: true,
    }));

    try {
      const response = await fetch('/guardian/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      });

      if (!response.ok) {
        addMessage({ type: 'system', content: `Error: ${response.status} ${response.statusText}` });
        set({ isStreaming: false });
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let accumulated = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(line.slice(6));

            if (event.type === 'token') {
              accumulated += event.text;
              // Update the last message in-place for streaming effect
              set((s) => {
                const msgs = [...s.messages];
                const last = msgs[msgs.length - 1];
                if (last?.type === 'assistant' && last._streaming) {
                  msgs[msgs.length - 1] = { ...last, content: accumulated };
                } else {
                  msgs.push({ type: 'assistant', content: accumulated, ts: Date.now(), _streaming: true });
                }
                return { messages: msgs };
              });
            } else if (event.type === 'done') {
              // Finalize the streamed message
              set((s) => {
                const msgs = [...s.messages];
                const last = msgs[msgs.length - 1];
                if (last?.type === 'assistant' && last._streaming) {
                  msgs[msgs.length - 1] = {
                    type: 'assistant',
                    content: event.response,
                    ts: Date.now(),
                    metadata: event.metadata,
                  };
                } else {
                  msgs.push({
                    type: 'assistant',
                    content: event.response,
                    ts: Date.now(),
                    metadata: event.metadata,
                  });
                }
                return { messages: msgs, isStreaming: false };
              });
            } else if (event.type === 'error') {
              addMessage({ type: 'system', content: `Error: ${event.message}` });
              set({ isStreaming: false });
            }
          } catch {
            // Skip malformed SSE lines
          }
        }
      }

      // Safety: ensure streaming flag is cleared
      set({ isStreaming: false });

    } catch (err) {
      addMessage({ type: 'system', content: `Connection error: ${err.message}` });
      set({ isStreaming: false });
    }
  },
}));

/**
 * Hook to wire knowledge events into Guardian messages.
 * Call this in EclissiHome to feed events to the store.
 */
export function useGuardianEventAggregator(knowledgeEvents) {
  const addMessage = useGuardianStore((s) => s.addMessage);
  const lastBatchRef = useRef(0);
  const lastEntityRef = useRef(new Set());

  useEffect(() => {
    if (!knowledgeEvents || knowledgeEvents.length === 0) return;

    for (const event of knowledgeEvents) {
      const eventTs = event.ts || event.timestamp || 0;
      if (eventTs <= lastBatchRef.current) continue;

      if (event.type === 'extraction_batch') {
        lastBatchRef.current = eventTs;
        const p = event.payload || {};
        addMessage({
          type: 'summary',
          content: `Session update: ${p.facts_count || 0} facts, ${p.entities_count || 0} entities, ${p.edges_count || 0} edges extracted.`,
          facts: p.facts_count || 0,
          entities: p.entities_count || 0,
          edges: p.edges_count || 0,
        });
      }

      if (event.type === 'entity_created' && event.payload?.needs_confirmation) {
        const eid = event.payload.entity_id;
        if (!lastEntityRef.current.has(eid)) {
          lastEntityRef.current.add(eid);
          addMessage({
            type: 'health',
            content: `New entity detected: ${event.payload.name} (${event.payload.entity_type}). Awaiting confirmation.`,
            entity: event.payload,
          });
        }
      }
    }

    // Generate recommendations based on pending count
    const pendingCount = lastEntityRef.current.size;
    if (pendingCount >= 5 && pendingCount % 5 === 0) {
      addMessage({
        type: 'action',
        content: `${pendingCount} entities pending confirmation. Review them in Observatory.`,
        title: 'Review pending entities',
      });
    }
  }, [knowledgeEvents, addMessage]);
}

/**
 * Hook to poll Observatory stats for the Guardian stats footer.
 */
export function useGuardianStats() {
  const setStats = useGuardianStore((s) => s.setStats);

  useEffect(() => {
    let cancelled = false;

    const fetchStats = async () => {
      try {
        const res = await fetch('/observatory/api/stats');
        if (res.ok && !cancelled) {
          const data = await res.json();
          setStats(data);
        }
      } catch {
        // Observatory may not be running
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 30000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [setStats]);
}

export { useGuardianStore };

export function useGuardianLuna() {
  return useGuardianStore();
}
