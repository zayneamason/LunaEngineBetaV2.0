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

  sendMessage: (text) => {
    if (!text.trim()) return;
    set((s) => ({
      messages: [
        ...s.messages,
        { type: 'user', content: text, ts: Date.now() },
        { type: 'system', content: 'Guardian Luna backend is not yet connected (Phase 6).', ts: Date.now() },
      ],
      inputText: '',
    }));
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
