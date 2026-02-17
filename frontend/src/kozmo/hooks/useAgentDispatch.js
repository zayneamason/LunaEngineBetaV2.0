/**
 * useAgentDispatch — Agent task management
 *
 * Dispatches tasks to KOZMO agents (Chiba, Maya, DI, Foley, Luna).
 * Manages the generation queue lifecycle: dispatch → poll → complete.
 *
 * See: ARCHITECTURE_KOZMO.md § 5 (Agent Architecture)
 */
import { useState, useCallback, useRef } from 'react';

const API_BASE = '/kozmo';

export function useAgentDispatch() {
  const [queue, setQueue] = useState([]);     // [{ taskId, action, status, entity, result }]
  const pollTimers = useRef({});

  const dispatch = useCallback(async (action, payload) => {
    // POST /kozmo/dispatch
    try {
      const res = await fetch(`${API_BASE}/dispatch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, ...payload }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();

      const task = {
        taskId: data.task_id,
        action,
        status: 'pending',
        entity: payload.entity || null,
        result: null,
      };

      setQueue(prev => [...prev, task]);

      // Start polling
      startPolling(data.task_id);

      return task;
    } catch (e) {
      console.error('[KOZMO] Dispatch failed:', e);
      return null;
    }
  }, []);

  const startPolling = useCallback((taskId) => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/queue/${taskId}`);
        if (!res.ok) return;
        const data = await res.json();

        setQueue(prev => prev.map(t =>
          t.taskId === taskId
            ? { ...t, status: data.status, result: data.result || null }
            : t
        ));

        if (data.status === 'completed' || data.status === 'failed') {
          clearInterval(pollTimers.current[taskId]);
          delete pollTimers.current[taskId];
        }
      } catch {
        // Silently retry on next interval
      }
    }, 2000); // Poll every 2s

    pollTimers.current[taskId] = interval;
  }, []);

  const clearCompleted = useCallback(() => {
    setQueue(prev => prev.filter(t => t.status !== 'completed' && t.status !== 'failed'));
  }, []);

  return { queue, dispatch, clearCompleted };
}
