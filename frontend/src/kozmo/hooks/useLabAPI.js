/**
 * useLabAPI — React hook for Phase 8 LAB Pipeline endpoints
 *
 * Provides brief CRUD, camera rigging, prompt preview, and sequence management.
 * All calls scoped to active project via KozmoProvider.
 */
import { useState, useCallback } from 'react';
import { useKozmo } from '../KozmoProvider';

const API_BASE = '/kozmo';

export function useLabAPI() {
  const { activeProject } = useKozmo();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const slug = activeProject?.slug;

  const listBriefs = useCallback(async (filters = {}) => {
    if (!slug) return [];
    try {
      const params = new URLSearchParams();
      if (filters.status) params.set('status', filters.status);
      if (filters.assignee) params.set('assignee', filters.assignee);
      const qs = params.toString();
      const res = await fetch(`${API_BASE}/projects/${slug}/lab/briefs${qs ? '?' + qs : ''}`);
      if (!res.ok) return [];
      return await res.json();
    } catch { return []; }
  }, [slug]);

  const getBrief = useCallback(async (briefId) => {
    if (!slug) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/lab/briefs/${briefId}`);
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  const createBrief = useCallback(async (data) => {
    if (!slug) return null;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/lab/briefs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      return await res.json();
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [slug]);

  const updateBrief = useCallback(async (briefId, updates) => {
    if (!slug) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/lab/briefs/${briefId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  const deleteBrief = useCallback(async (briefId) => {
    if (!slug) return false;
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/lab/briefs/${briefId}`, {
        method: 'DELETE',
      });
      return res.ok;
    } catch { return false; }
  }, [slug]);

  const applyRig = useCallback(async (briefId, camera, post) => {
    if (!slug) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/lab/briefs/${briefId}/rig`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ camera, post }),
      });
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  const previewPrompt = useCallback(async (briefId, shotId = null) => {
    if (!slug) return null;
    try {
      const qs = shotId ? `?shot_id=${shotId}` : '';
      const res = await fetch(`${API_BASE}/projects/${slug}/lab/briefs/${briefId}/prompt${qs}`);
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  const applyShotRig = useCallback(async (briefId, shotId, camera, post) => {
    if (!slug) return null;
    try {
      const res = await fetch(
        `${API_BASE}/projects/${slug}/lab/briefs/${briefId}/shots/${shotId}/rig`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ camera, post }),
        }
      );
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  const addShot = useCallback(async (briefId, shot) => {
    if (!slug) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/lab/briefs/${briefId}/shots`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(shot),
      });
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  const removeShot = useCallback(async (briefId, shotId) => {
    if (!slug) return false;
    try {
      const res = await fetch(
        `${API_BASE}/projects/${slug}/lab/briefs/${briefId}/shots/${shotId}`,
        { method: 'DELETE' }
      );
      return res.ok;
    } catch { return false; }
  }, [slug]);

  const reorderShots = useCallback(async (briefId, shotIds) => {
    if (!slug) return null;
    try {
      const res = await fetch(
        `${API_BASE}/projects/${slug}/lab/briefs/${briefId}/shots/reorder`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ shot_ids: shotIds }),
        }
      );
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  return {
    listBriefs, getBrief, createBrief, updateBrief, deleteBrief,
    applyRig, previewPrompt, applyShotRig,
    addShot, removeShot, reorderShots,
    loading, error,
  };
}
