/**
 * useLunaAPI — Luna Engine connection
 *
 * Minimal hook for checking Luna Engine health and sending messages.
 * KOZMO uses this for Luna contextual intelligence (not for Eden ops).
 *
 * Note: This is KOZMO's own copy. If running inside Eclissi,
 * Eclissi's useLunaAPI could be passed in via KozmoProvider instead.
 * Keeping a local copy preserves standalone capability.
 */
import { useState, useCallback, useEffect } from 'react';

const API_BASE = '/api';

export function useLunaAPI() {
  const [isConnected, setIsConnected] = useState(false);

  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      const data = await res.json();
      const connected = data.status === 'healthy';
      setIsConnected(connected);
      return connected;
    } catch {
      setIsConnected(false);
      return false;
    }
  }, []);

  // Poll health on mount
  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  const sendMessage = useCallback(async (message) => {
    try {
      const res = await fetch(`${API_BASE}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      return await res.json();
    } catch (e) {
      console.error('[KOZMO] Luna message failed:', e);
      return null;
    }
  }, []);

  return { isConnected, checkHealth, sendMessage };
}
