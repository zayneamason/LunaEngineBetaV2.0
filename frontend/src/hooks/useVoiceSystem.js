import { useState, useEffect, useCallback } from 'react';

const API_BASE = 'http://127.0.0.1:8000';

/**
 * useVoiceSystem — hook for Voice Blend Engine + Corpus state
 *
 * Polls /voice/system/status every 5s when active.
 * Provides config update, simulate, and reset actions.
 */
export function useVoiceSystem(isOpen) {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/voice/system/status`);
      if (res.ok) {
        const data = await res.json();
        setStatus(data);
        setError(null);
      } else {
        setError('Failed to fetch voice system status');
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLastRefresh(new Date());
    }
  }, []);

  // Poll when panel is open
  useEffect(() => {
    if (!isOpen) return;
    setLoading(true);
    fetchStatus().finally(() => setLoading(false));
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, [isOpen, fetchStatus]);

  const updateConfig = useCallback(async (updates) => {
    try {
      const res = await fetch(`${API_BASE}/voice/system/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (res.ok) {
        await fetchStatus(); // Refresh after update
        return await res.json();
      }
      throw new Error('Config update failed');
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, [fetchStatus]);

  const simulate = useCallback(async (signals) => {
    try {
      const res = await fetch(`${API_BASE}/voice/system/simulate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(signals),
      });
      if (res.ok) return await res.json();
      return null;
    } catch {
      return null;
    }
  }, []);

  const resetConversation = useCallback(async () => {
    try {
      await fetch(`${API_BASE}/voice/system/reset`, { method: 'POST' });
      await fetchStatus();
    } catch (e) {
      setError(e.message);
    }
  }, [fetchStatus]);

  return {
    status,
    loading,
    error,
    lastRefresh,
    refresh: fetchStatus,
    updateConfig,
    simulate,
    resetConversation,
  };
}
