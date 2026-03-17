import { useState, useEffect, useCallback, useRef } from 'react';

const RECONNECT_DELAY = 3000;

/**
 * Hook for QA pipeline state via WebSocket.
 *
 * Streams real-time assertion results and health updates.
 *
 * @param {string} wsUrl - WebSocket URL (default: derived from window.location)
 * @returns {Object} { health, lastReport, nodeStatus, events, isConnected, error }
 */
const _defaultPipelineWs = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/pipeline`;
export function usePipeline(wsUrl = _defaultPipelineWs) {
  const [health, setHealth] = useState(null);
  const [lastReport, setLastReport] = useState(null);
  const [nodeStatus, setNodeStatus] = useState({});  // {actor_key: "pass"|"warn"|"fail"}
  const [events, setEvents] = useState([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);

  const wsRef = useRef(null);
  const reconnectRef = useRef(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    try {
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        setIsConnected(true);
        setError(null);
        console.log('[Pipeline] Connected');
      };

      wsRef.current.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);

          if (msg.type === 'health_update') {
            setHealth(msg.data);
          } else if (msg.type === 'validation_end') {
            setLastReport(msg.data);
            if (msg.data?.node_status) setNodeStatus(msg.data.node_status);
            setEvents(prev => [msg, ...prev].slice(0, 50));
          } else if (msg.type === 'validation_start') {
            setEvents(prev => [msg, ...prev].slice(0, 50));
          }
        } catch (e) {
          console.error('[Pipeline] Parse error:', e);
        }
      };

      wsRef.current.onclose = () => {
        setIsConnected(false);
        console.log('[Pipeline] Disconnected, reconnecting...');
        reconnectRef.current = setTimeout(connect, RECONNECT_DELAY);
      };

      wsRef.current.onerror = (e) => {
        setError('Connection error');
        console.error('[Pipeline] Error:', e);
      };
    } catch (e) {
      setError('Failed to connect');
      reconnectRef.current = setTimeout(connect, RECONNECT_DELAY);
    }
  }, [wsUrl]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
    };
  }, [connect]);

  return { health, lastReport, nodeStatus, events, isConnected, error };
}

export default usePipeline;
