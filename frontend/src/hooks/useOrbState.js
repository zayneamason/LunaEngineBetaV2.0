import { useState, useEffect, useCallback, useRef } from 'react';

const DEFAULT_STATE = {
  animation: 'idle',
  color: null,
  brightness: 1,
  source: 'default',
  renderer: null,
};

const RECONNECT_DELAY = 3000;
const IDLE_TIMEOUT = 2000;

/**
 * Hook for managing Luna Orb state via WebSocket
 *
 * @param {string} wsUrl - WebSocket URL (default: ws://<host>/ws/orb)
 * @returns {Object} { orbState, isConnected, error }
 */
export function useOrbState(wsUrl = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/orb`) {
  const [orbState, setOrbState] = useState(DEFAULT_STATE);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);

  const wsRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const idleTimeoutRef = useRef(null);

  const resetToIdle = useCallback(() => {
    setOrbState(prev => ({
      ...DEFAULT_STATE,
      source: 'timeout'
    }));
  }, []);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        setIsConnected(true);
        setError(null);
        console.log('[OrbState] Connected');
      };

      wsRef.current.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Clear any pending idle timeout
          if (idleTimeoutRef.current) {
            clearTimeout(idleTimeoutRef.current);
          }

          setOrbState({
            animation: data.animation || 'idle',
            color: data.color || null,
            brightness: data.brightness || 1,
            source: data.source || 'websocket',
            renderer: data.renderer || null,
            dimensions: data.dimensions || null,
          });

          // Set idle timeout if this isn't already idle
          if (data.animation && data.animation !== 'idle') {
            idleTimeoutRef.current = setTimeout(resetToIdle, IDLE_TIMEOUT);
          }
        } catch (e) {
          console.error('[OrbState] Parse error:', e);
        }
      };

      wsRef.current.onclose = () => {
        setIsConnected(false);
        console.log('[OrbState] Disconnected, reconnecting...');

        // Schedule reconnect
        reconnectTimeoutRef.current = setTimeout(connect, RECONNECT_DELAY);
      };

      wsRef.current.onerror = (e) => {
        setError('Connection error');
        console.error('[OrbState] Error:', e);
      };

    } catch (e) {
      setError('Failed to connect');
      reconnectTimeoutRef.current = setTimeout(connect, RECONNECT_DELAY);
    }
  }, [wsUrl, resetToIdle]);

  useEffect(() => {
    connect();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (idleTimeoutRef.current) {
        clearTimeout(idleTimeoutRef.current);
      }
    };
  }, [connect]);

  return { orbState, isConnected, error };
}

export default useOrbState;
