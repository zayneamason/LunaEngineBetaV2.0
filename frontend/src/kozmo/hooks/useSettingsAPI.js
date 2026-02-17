/**
 * useSettingsAPI — React hook for Project Settings endpoints
 *
 * Reads settings from activeProject manifest, writes via PUT.
 * On save, reloads project to refresh cached manifest.
 */
import { useState, useCallback } from 'react';
import { useKozmo } from '../KozmoProvider';

const API_BASE = '/kozmo';

export function useSettingsAPI() {
  const { activeProject, loadProject } = useKozmo();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const slug = activeProject?.slug;

  const getSettings = useCallback(() => {
    return activeProject?.manifest?.settings || {};
  }, [activeProject]);

  const updateSettings = useCallback(async (settings) => {
    if (!slug) return null;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      // Refresh project to pick up new settings
      await loadProject(slug);
      return data;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [slug, loadProject]);

  return { getSettings, updateSettings, loading, error };
}
