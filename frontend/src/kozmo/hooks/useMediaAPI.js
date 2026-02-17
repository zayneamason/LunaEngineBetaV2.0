/**
 * useMediaAPI — React hook for Media Library endpoints
 *
 * Provides asset listing, filtering, and status updates.
 * All calls scoped to active project via KozmoProvider.
 */
import { useState, useCallback } from 'react';
import { useKozmo } from '../KozmoProvider';

const API_BASE = '/kozmo';

export function useMediaAPI() {
  const { activeProject } = useKozmo();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const slug = activeProject?.slug;

  const listAssets = useCallback(async (filters = {}) => {
    if (!slug) return [];
    try {
      const params = new URLSearchParams();
      if (filters.type) params.set('type', filters.type);
      if (filters.scene_slug) params.set('scene_slug', filters.scene_slug);
      if (filters.brief_id) params.set('brief_id', filters.brief_id);
      if (filters.status) params.set('status', filters.status);
      if (filters.tag) params.set('tag', filters.tag);
      const qs = params.toString();
      const res = await fetch(`${API_BASE}/projects/${slug}/media${qs ? '?' + qs : ''}`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.assets || data || [];
    } catch { return []; }
  }, [slug]);

  const getAsset = useCallback(async (assetId) => {
    if (!slug) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/media/${assetId}`);
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  const updateAsset = useCallback(async (assetId, updates) => {
    if (!slug) return null;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/media/${assetId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
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

  const getAssetsByScene = useCallback(async (docSlug) => {
    if (!slug) return [];
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/media/scene/${docSlug}`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.assets || data || [];
    } catch { return []; }
  }, [slug]);

  const getAssetsByBrief = useCallback(async (briefId) => {
    if (!slug) return [];
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/media/brief/${briefId}`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.assets || data || [];
    } catch { return []; }
  }, [slug]);

  return {
    listAssets, getAsset, updateAsset,
    getAssetsByScene, getAssetsByBrief,
    loading, error,
  };
}
