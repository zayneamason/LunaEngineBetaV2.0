/**
 * useBoardAPI — React hook for Phase 9 Production Board endpoints
 *
 * Provides board view, stats, dependency checking, push-ready, AI thread, bulk update.
 * All calls scoped to active project via KozmoProvider.
 */
import { useState, useCallback } from 'react';
import { useKozmo } from '../KozmoProvider';

const API_BASE = '/kozmo';

export function useBoardAPI() {
  const { activeProject } = useKozmo();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const slug = activeProject?.slug;

  const getBoard = useCallback(async (groupBy = 'status', status = null) => {
    if (!slug) return null;
    try {
      const params = new URLSearchParams();
      if (groupBy) params.set('group_by', groupBy);
      if (status) params.set('status', status);
      const res = await fetch(`${API_BASE}/projects/${slug}/board?${params}`);
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  const getStats = useCallback(async () => {
    if (!slug) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/board/stats`);
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  const checkDependencies = useCallback(async (briefId) => {
    if (!slug) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/board/briefs/${briefId}/dependencies`);
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  const pushReady = useCallback(async () => {
    if (!slug) return null;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/board/push-ready`, { method: 'POST' });
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
    finally { setLoading(false); }
  }, [slug]);

  const addThreadMessage = useCallback(async (briefId, role, text) => {
    if (!slug) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/board/briefs/${briefId}/thread`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ role, text }),
      });
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  const getThread = useCallback(async (briefId) => {
    if (!slug) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/board/briefs/${briefId}/thread`);
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  const bulkUpdate = useCallback(async (briefIds, updates) => {
    if (!slug) return null;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/board/bulk-update`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ brief_ids: briefIds, updates }),
      });
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
    finally { setLoading(false); }
  }, [slug]);

  return {
    getBoard, getStats, checkDependencies, pushReady,
    addThreadMessage, getThread, bulkUpdate,
    loading, error,
  };
}
