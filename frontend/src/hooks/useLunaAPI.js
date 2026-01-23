import { useState, useCallback, useEffect } from 'react';

const API_BASE = 'http://localhost:8000';

export function useLunaAPI() {
  const [status, setStatus] = useState(null);
  const [consciousness, setConsciousness] = useState(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Check health
  const checkHealth = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/health`);
      const data = await res.json();
      setIsConnected(data.status === 'healthy');
      return data.status === 'healthy';
    } catch (e) {
      setIsConnected(false);
      return false;
    }
  }, []);

  // Fetch status
  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/status`);
      if (!res.ok) throw new Error('Failed to fetch status');
      const data = await res.json();
      setStatus(data);
      return data;
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, []);

  // Fetch consciousness
  const fetchConsciousness = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/consciousness`);
      if (!res.ok) throw new Error('Failed to fetch consciousness');
      const data = await res.json();
      setConsciousness(data);
      return data;
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, []);

  // Send message
  const sendMessage = useCallback(async (message) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, timeout: 60.0 }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to send message');
      }
      const data = await res.json();
      return data;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Stream message (legacy endpoint with named events)
  const streamMessage = useCallback(async (message, onToken, onComplete) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, timeout: 120.0 }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to stream message');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            const eventType = line.slice(7);
            continue;
          }
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.text !== undefined) {
                onToken?.(data.text);
              }
              if (data.output_tokens !== undefined) {
                onComplete?.(data);
              }
            } catch {}
          }
        }
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Stream persona (context-first endpoint)
  // Callbacks: onContext(ctx), onToken(text), onDone(result), onError(msg)
  const streamPersona = useCallback(async (message, { onContext, onToken, onDone, onError }) => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/persona/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, timeout: 120.0 }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to stream persona');
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              switch (data.type) {
                case 'context':
                  onContext?.(data);
                  break;
                case 'token':
                  onToken?.(data.text);
                  break;
                case 'done':
                  onDone?.(data);
                  break;
                case 'error':
                  onError?.(data.message);
                  setError(data.message);
                  break;
              }
            } catch {}
          }
        }
      }
    } catch (e) {
      setError(e.message);
      onError?.(e.message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Abort generation
  const abort = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/abort`, { method: 'POST' });
    } catch {}
  }, []);

  // Relaunch system
  const relaunchSystem = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/system/relaunch`, { method: 'POST' });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to relaunch');
      }
      const data = await res.json();
      setIsConnected(false); // Will reconnect after restart
      return data;
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, []);

  // Poll status and consciousness periodically
  useEffect(() => {
    const poll = async () => {
      const healthy = await checkHealth();
      if (healthy) {
        await Promise.all([fetchStatus(), fetchConsciousness()]);
      }
    };

    poll();
    const interval = setInterval(poll, 2000);
    return () => clearInterval(interval);
  }, [checkHealth, fetchStatus, fetchConsciousness]);

  return {
    status,
    consciousness,
    isConnected,
    isLoading,
    error,
    sendMessage,
    streamMessage,
    streamPersona,
    abort,
    relaunchSystem,
    refresh: () => Promise.all([fetchStatus(), fetchConsciousness()]),
  };
}
