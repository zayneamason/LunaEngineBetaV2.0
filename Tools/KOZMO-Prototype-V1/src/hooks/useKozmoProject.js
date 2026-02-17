/**
 * useKozmoProject — Project CRUD and entity operations
 *
 * Talks to Luna Engine backend at /kozmo/* endpoints.
 * Handles: project load, entity CRUD, template fetching, search.
 *
 * See: ARCHITECTURE_KOZMO.md § 6 (API Endpoints)
 */
import { useState, useCallback } from 'react';

const API_BASE = '/api/kozmo';

export function useKozmoProject() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const listProjects = useCallback(async () => {
    // GET /kozmo/projects
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/projects`);
      if (!res.ok) throw new Error(`${res.status}`);
      return await res.json();
    } catch (e) {
      setError(e.message);
      return [];
    } finally {
      setLoading(false);
    }
  }, []);

  const loadProject = useCallback(async (slug) => {
    // GET /kozmo/projects/{slug}
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}`);
      if (!res.ok) throw new Error(`${res.status}`);
      return await res.json();
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const getEntities = useCallback(async (slug, type = null) => {
    // GET /kozmo/projects/{slug}/entities[/{type}]
    const path = type
      ? `${API_BASE}/projects/${slug}/entities/${type}`
      : `${API_BASE}/projects/${slug}/entities`;
    try {
      const res = await fetch(path);
      if (!res.ok) throw new Error(`${res.status}`);
      return await res.json();
    } catch (e) {
      setError(e.message);
      return [];
    }
  }, []);

  const getEntity = useCallback(async (slug, type, id) => {
    // GET /kozmo/projects/{slug}/entities/{type}/{id}
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/entities/${type}/${id}`);
      if (!res.ok) throw new Error(`${res.status}`);
      return await res.json();
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, []);

  const searchProject = useCallback(async (slug, query) => {
    // GET /kozmo/projects/{slug}/search?q=...
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/search?q=${encodeURIComponent(query)}`);
      if (!res.ok) throw new Error(`${res.status}`);
      return await res.json();
    } catch (e) {
      setError(e.message);
      return [];
    }
  }, []);

  return {
    loading,
    error,
    listProjects,
    loadProject,
    getEntities,
    getEntity,
    searchProject,
  };
}
