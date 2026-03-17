import { useState, useEffect, useCallback, useRef } from 'react';

const RECONNECT_DELAY = 3000;

/**
 * useKnowledgeStream — real-time WebSocket consumer for knowledge pipeline events.
 *
 * Replaces the polling-based useExtractions with a live event stream from
 * /ws/knowledge.  Events include entity_created, fact_extracted, edge_created,
 * extraction_batch, entity_confirmed, and entity_rejected.
 */
export function useKnowledgeStream() {
  const [events, setEvents] = useState([]);
  const [pendingEntities, setPendingEntities] = useState([]);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  const connect = useCallback(() => {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${location.host}/ws/knowledge`);
    wsRef.current = ws;

    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data);
        setEvents((prev) => [...prev.slice(-99), event]);

        if (event.type === 'entity_created' && event.payload?.needs_confirmation) {
          setPendingEntities((prev) => {
            if (prev.some((p) => p.entity_id === event.payload.entity_id)) return prev;
            return [...prev, event.payload];
          });
        }
        if (event.type === 'entity_confirmed' || event.type === 'entity_rejected') {
          setPendingEntities((prev) =>
            prev.filter((p) => p.entity_id !== event.payload?.entity_id),
          );
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      reconnectRef.current = setTimeout(connect, RECONNECT_DELAY);
    };

    ws.onerror = () => {
      // onclose will fire next and handle reconnection
    };
  }, []);

  useEffect(() => {
    connect();
    return () => {
      wsRef.current?.close();
      clearTimeout(reconnectRef.current);
    };
  }, [connect]);

  const confirmEntity = useCallback(async (entityId) => {
    try {
      await fetch(`/api/entities/${entityId}/confirm`, { method: 'POST' });
    } catch {
      // Optimistic removal already happened via WebSocket event
    }
  }, []);

  const rejectEntity = useCallback(async (entityId) => {
    try {
      await fetch(`/api/entities/${entityId}`, { method: 'DELETE' });
    } catch {
      // Optimistic removal already happened via WebSocket event
    }
  }, []);

  return { events, pendingEntities, confirmEntity, rejectEntity };
}
