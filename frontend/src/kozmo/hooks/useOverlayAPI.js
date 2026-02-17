/**
 * useOverlayAPI — React hook for Phase 7 Overlay endpoints
 *
 * Provides annotation CRUD, resolve/unresolve, push-to-lab, and action aggregation.
 * All calls scoped to active project via KozmoProvider.
 */
import { useState, useCallback } from 'react';
import { useKozmo } from '../KozmoProvider';

const API_BASE = '/kozmo';

export function useOverlayAPI() {
  const { activeProject } = useKozmo();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const slug = activeProject?.slug;

  const getOverlay = useCallback(async (docSlug) => {
    if (!slug) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/story/documents/${docSlug}/overlay`);
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  const addAnnotation = useCallback(async (docSlug, annotation) => {
    if (!slug) return null;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(
        `${API_BASE}/projects/${slug}/story/documents/${docSlug}/overlay/annotations`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(annotation),
        }
      );
      if (!res.ok) throw new Error(`${res.status}`);
      return await res.json();
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [slug]);

  const updateAnnotation = useCallback(async (docSlug, annId, updates) => {
    if (!slug) return null;
    try {
      const res = await fetch(
        `${API_BASE}/projects/${slug}/story/documents/${docSlug}/overlay/annotations/${annId}`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(updates),
        }
      );
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  const deleteAnnotation = useCallback(async (docSlug, annId) => {
    if (!slug) return false;
    try {
      const res = await fetch(
        `${API_BASE}/projects/${slug}/story/documents/${docSlug}/overlay/annotations/${annId}`,
        { method: 'DELETE' }
      );
      return res.ok;
    } catch { return false; }
  }, [slug]);

  const resolveAnnotation = useCallback(async (docSlug, annId) => {
    if (!slug) return null;
    try {
      const res = await fetch(
        `${API_BASE}/projects/${slug}/story/documents/${docSlug}/overlay/annotations/${annId}/resolve`,
        { method: 'POST' }
      );
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  const pushToLab = useCallback(async (docSlug, annId) => {
    if (!slug) return null;
    try {
      const res = await fetch(
        `${API_BASE}/projects/${slug}/story/documents/${docSlug}/overlay/annotations/${annId}/push-to-lab`,
        { method: 'POST' }
      );
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  const pushAllActions = useCallback(async (docSlug) => {
    if (!slug) return null;
    try {
      const res = await fetch(
        `${API_BASE}/projects/${slug}/story/documents/${docSlug}/overlay/push-all`,
        { method: 'POST' }
      );
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [slug]);

  const getAllActions = useCallback(async () => {
    if (!slug) return [];
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/overlay/actions`);
      if (!res.ok) return [];
      return await res.json();
    } catch { return []; }
  }, [slug]);

  return {
    getOverlay, addAnnotation, updateAnnotation, deleteAnnotation,
    resolveAnnotation, pushToLab, pushAllActions, getAllActions,
    loading, error,
  };
}
