import { useState, useEffect, useRef, useCallback } from 'react';

export function useOrbConnection() {
  const [isConnected, setIsConnected] = useState(false);
  const [orbState, setOrbState] = useState(null);
  const [dimensions, setDimensions] = useState(null);
  const [rendererState, setRendererState] = useState(null);
  const [source, setSource] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const wsRef = useRef(null);
  const reconnectRef = useRef(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = window.location.host || '127.0.0.1:8000';
    const ws = new WebSocket(`${protocol}://${host}/ws/orb`);

    ws.onopen = () => {
      if (!mountedRef.current) return;
      setIsConnected(true);
      if (reconnectRef.current) {
        clearTimeout(reconnectRef.current);
        reconnectRef.current = null;
      }
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      try {
        const data = JSON.parse(event.data);
        setOrbState(data);
        setDimensions(data.dimensions || null);
        setRendererState(data.rendererState || null);
        setSource(data.source || null);
        setLastUpdate(new Date());
      } catch {}
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setIsConnected(false);
      wsRef.current = null;
      reconnectRef.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  return { isConnected, orbState, dimensions, rendererState, source, lastUpdate };
}
