/**
 * useEdenAdapter — Eden operations via Luna Engine
 *
 * All Eden calls go through Luna's backend (not direct to Eden API).
 * This keeps API keys server-side and lets Luna enrich prompts.
 *
 * See: ARCHITECTURE_KOZMO.md § 5.2 (Agent ↔ Eden ↔ Luna Flow)
 */
import { useState, useCallback } from 'react';

const API_BASE = '/api/kozmo';

export function useEdenAdapter() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const checkEdenHealth = useCallback(async () => {
    try {
      const res = await fetch(`/api/eden/health`);
      if (!res.ok) return false;
      const data = await res.json();
      return data.eden_authenticated === true;
    } catch {
      return false;
    }
  }, []);

  const generateImage = useCallback(async (prompt, shotConfig = null) => {
    // POST /kozmo/dispatch
    // Backend enriches prompt with camera metadata, routes to Eden
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/dispatch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action: 'generate_image',
          prompt,
          shot_config: shotConfig,
        }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      return await res.json(); // { task_id, status }
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const pollTask = useCallback(async (taskId) => {
    try {
      const res = await fetch(`${API_BASE}/queue/${taskId}`);
      if (!res.ok) throw new Error(`${res.status}`);
      return await res.json(); // { status, result_url, ... }
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, []);

  return { loading, error, checkEdenHealth, generateImage, pollTask };
}
