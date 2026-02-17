/**
 * KozmoProvider — React Context for KOZMO state
 *
 * Wraps all KOZMO components. Provides:
 *   - Active project (slug, manifest, entities)
 *   - Entity CRUD operations (wired to /kozmo/* API)
 *   - Agent state (queue, active sessions, agent roster status)
 *   - Luna Engine connection status
 *
 * This is the coupling point. In Eclissi-hosted mode, Eclissi wraps
 * KOZMO pages in this provider. In standalone mode, App.jsx does it.
 *
 * No hard dependency on Eclissi internals.
 */
import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { useWebSocket } from './hooks/useWebSocket';

const API_BASE = '/kozmo';

const KozmoContext = createContext(null);

export function useKozmo() {
  const ctx = useContext(KozmoContext);
  if (!ctx) throw new Error('useKozmo must be used within KozmoProvider');
  return ctx;
}

export function KozmoProvider({ children }) {
  // --- Project State ---
  const [projects, setProjects] = useState([]);
  const [activeProject, setActiveProject] = useState(null);
  const [entities, setEntities] = useState({});
  const [entityList, setEntityList] = useState([]);
  const [selectedEntity, setSelectedEntity] = useState(null);

  // --- Agent State ---
  const [generationQueue, setGenerationQueue] = useState([]);
  const [agentStatus, setAgentStatus] = useState({
    chiba: 'standby',
    maya: 'standby',
    di_agent: 'standby',
    foley: 'standby',
    luna: 'idle',
  });

  // --- Connection ---
  const [engineConnected, setEngineConnected] = useState(false);
  const [edenConnected, setEdenConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // --- SCRIBO State ---
  const [storyTree, setStoryTree] = useState(null);
  const [currentDocument, setCurrentDocument] = useState(null);
  const [scriboStats, setScriboStats] = useState(null);

  // --- WebSocket (Phase 4) ---
  const { isConnected: wsConnected, on: wsOn, sendMessage: wsSend } = useWebSocket(
    activeProject?.slug
  );

  useEffect(() => {
    if (!activeProject || !wsOn) return;

    const unsubEntity = wsOn('entity_updated', (message) => {
      // Update local entity state from WebSocket broadcast
      if (message.entity_slug && message.entity) {
        setEntities(prev => ({
          ...prev,
          [message.entity_slug]: message.entity,
        }));
      }
    });

    const unsubCursor = wsOn('cursor_update', (message) => {
      // Could be used for collaborative cursor display
      // For now, just log
      console.log('Remote cursor:', message.user_id, message.scene_slug);
    });

    return () => {
      unsubEntity();
      unsubCursor();
    };
  }, [wsOn, activeProject]);

  // --- Health Check ---
  const checkHealth = useCallback(async () => {
    // Luna Engine health
    try {
      const res = await fetch('/api/health');
      const data = await res.json();
      const connected = data.status === 'healthy';
      setEngineConnected(connected);
      if (connected) setAgentStatus(prev => ({ ...prev, luna: 'idle' }));
    } catch {
      setEngineConnected(false);
    }

    // Eden API health
    try {
      const res = await fetch('/eden/health');
      const data = await res.json();
      setEdenConnected(data.status === 'healthy');
    } catch {
      setEdenConnected(false);
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 10000);
    return () => clearInterval(interval);
  }, [checkHealth]);

  // --- Project Operations ---
  const fetchProjects = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/projects`);
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      setProjects(data.projects || []);
      return data.projects || [];
    } catch (e) {
      setError(e.message);
      return [];
    }
  }, []);

  const createProject = useCallback(async (name, slug = null) => {
    setLoading(true);
    setError(null);
    try {
      const body = { name };
      if (slug) body.slug = slug;
      const res = await fetch(`${API_BASE}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `${res.status}`);
      }
      const data = await res.json();
      await fetchProjects();
      return data;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [fetchProjects]);

  const loadProject = useCallback(async (slug) => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}`);
      if (!res.ok) throw new Error(`Project not found: ${slug}`);
      const manifest = await res.json();

      setActiveProject({ slug, name: manifest.name, manifest });

      // Activate project scope for Luna's memory isolation
      try {
        await fetch('/project/activate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ slug }),
        });
      } catch (e) {
        console.warn('Failed to activate project scope:', e);
      }

      // Fetch entity list
      const entRes = await fetch(`${API_BASE}/projects/${slug}/entities`);
      if (entRes.ok) {
        const entData = await entRes.json();
        setEntityList(entData.entities || []);

        // Load full entity data for each slug
        const loaded = {};
        const types = manifest.entity_types || ['characters', 'locations', 'props', 'events', 'lore'];
        for (const entSlug of (entData.entities || [])) {
          for (const type of types) {
            try {
              const r = await fetch(`${API_BASE}/projects/${slug}/entities/${type}/${entSlug}`);
              if (r.ok) {
                const d = await r.json();
                loaded[entSlug] = d.entity;
                break;
              }
            } catch { /* try next type */ }
          }
        }
        setEntities(loaded);
      }

      return manifest;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const closeProject = useCallback(async () => {
    setActiveProject(null);
    setEntities({});
    setEntityList([]);
    setSelectedEntity(null);
    // Deactivate project scope for Luna's memory
    try {
      await fetch('/project/deactivate', { method: 'POST' });
    } catch (e) {
      console.warn('Failed to deactivate project scope:', e);
    }
  }, []);

  const deleteProject = useCallback(async (slug) => {
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}`, { method: 'DELETE' });
      if (!res.ok) throw new Error(`${res.status}`);
      if (activeProject?.slug === slug) {
        await closeProject();
      }
      await fetchProjects();
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    }
  }, [activeProject, fetchProjects, closeProject]);

  // --- Entity Operations ---
  const createEntity = useCallback(async (type, name, data = {}, tags = []) => {
    if (!activeProject) return null;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects/${activeProject.slug}/entities`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ type, name, data, tags }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `${res.status}`);
      }
      const result = await res.json();
      await loadProject(activeProject.slug);
      return result;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [activeProject, loadProject]);

  const bulkCreateEntities = useCallback(async (entities, onDuplicate = 'skip') => {
    if (!activeProject) return null;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects/${activeProject.slug}/entities/bulk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ entities, on_duplicate: onDuplicate }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `${res.status}`);
      }
      const result = await res.json();
      await loadProject(activeProject.slug); // Refresh entity list
      return result;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [activeProject, loadProject]);

  const updateEntity = useCallback(async (type, slug, updates) => {
    if (!activeProject) return false;
    try {
      const res = await fetch(`${API_BASE}/projects/${activeProject.slug}/entities/${type}/${slug}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      await loadProject(activeProject.slug);
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    }
  }, [activeProject, loadProject]);

  const deleteEntity = useCallback(async (type, slug) => {
    if (!activeProject) return false;
    try {
      const res = await fetch(`${API_BASE}/projects/${activeProject.slug}/entities/${type}/${slug}`, {
        method: 'DELETE',
      });
      if (!res.ok) throw new Error(`${res.status}`);
      if (selectedEntity?.slug === slug) setSelectedEntity(null);
      await loadProject(activeProject.slug);
      return true;
    } catch (e) {
      setError(e.message);
      return false;
    }
  }, [activeProject, loadProject, selectedEntity]);

  const selectEntity = useCallback((type, slug) => {
    const entity = entities[slug];
    setSelectedEntity(entity ? { type, slug, entity } : null);
  }, [entities]);

  // --- Graph Operations ---
  const rebuildGraph = useCallback(async () => {
    if (!activeProject) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${activeProject.slug}/graph/rebuild`, {
        method: 'POST',
      });
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [activeProject]);

  // --- Prompt Builder ---
  const buildPrompt = useCallback(async (shotConfig, sceneDescription = null) => {
    if (!activeProject) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${activeProject.slug}/prompt/build`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shot: shotConfig, scene_description: sceneDescription }),
      });
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [activeProject]);

  // --- SCRIBO Operations ---
  const fetchStoryTree = useCallback(async () => {
    if (!activeProject) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${activeProject.slug}/story`);
      if (!res.ok) return null;
      const data = await res.json();
      setStoryTree(data);
      return data;
    } catch { return null; }
  }, [activeProject]);

  const fetchDocument = useCallback(async (docSlug) => {
    if (!activeProject) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${activeProject.slug}/story/documents/${docSlug}`);
      if (!res.ok) return null;
      const doc = await res.json();
      setCurrentDocument(doc);
      return doc;
    } catch { return null; }
  }, [activeProject]);

  const saveDocument = useCallback(async (docSlug, updates) => {
    if (!activeProject) return false;
    try {
      const res = await fetch(`${API_BASE}/projects/${activeProject.slug}/story/documents/${docSlug}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updates),
      });
      return res.ok;
    } catch { return false; }
  }, [activeProject]);

  const createDocument = useCallback(async (data) => {
    if (!activeProject) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${activeProject.slug}/story/documents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!res.ok) return null;
      const result = await res.json();
      await fetchStoryTree();
      return result;
    } catch { return null; }
  }, [activeProject, fetchStoryTree]);

  const deleteDocument = useCallback(async (docSlug) => {
    if (!activeProject) return false;
    try {
      const res = await fetch(`${API_BASE}/projects/${activeProject.slug}/story/documents/${docSlug}`, {
        method: 'DELETE',
      });
      if (res.ok) {
        if (currentDocument?.slug === docSlug) setCurrentDocument(null);
        await fetchStoryTree();
      }
      return res.ok;
    } catch { return false; }
  }, [activeProject, currentDocument, fetchStoryTree]);

  const createContainer = useCallback(async (data) => {
    if (!activeProject) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${activeProject.slug}/story/containers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!res.ok) return null;
      const result = await res.json();
      await fetchStoryTree();
      return result;
    } catch { return null; }
  }, [activeProject, fetchStoryTree]);

  const addLunaNote = useCallback(async (docSlug, note) => {
    if (!activeProject) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${activeProject.slug}/story/documents/${docSlug}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(note),
      });
      if (!res.ok) return null;
      return await res.json();
    } catch { return null; }
  }, [activeProject]);

  const searchStory = useCallback(async (query) => {
    if (!activeProject || !query) return [];
    try {
      const res = await fetch(`${API_BASE}/projects/${activeProject.slug}/story/search?q=${encodeURIComponent(query)}`);
      if (!res.ok) return [];
      const data = await res.json();
      return data.results || [];
    } catch { return []; }
  }, [activeProject]);

  const fetchScriboStats = useCallback(async () => {
    if (!activeProject) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${activeProject.slug}/story/stats`);
      if (!res.ok) return null;
      const data = await res.json();
      setScriboStats(data);
      return data;
    } catch { return null; }
  }, [activeProject]);

  // --- Scene Generation (Phase 6) ---
  const generateScene = useCallback(async (characterSlugs, locationSlug, goal, style = 'fountain') => {
    if (!activeProject) return null;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects/${activeProject.slug}/scenes/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          character_slugs: characterSlugs,
          location_slug: locationSlug,
          goal,
          style,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `${res.status}`);
      }
      return await res.json();
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [activeProject]);

  // --- Load projects on connect ---
  useEffect(() => {
    if (engineConnected) fetchProjects();
  }, [engineConnected, fetchProjects]);

  const value = {
    projects, activeProject, entities, entityList, selectedEntity,
    fetchProjects, createProject, loadProject, closeProject, deleteProject, selectEntity,
    createEntity, bulkCreateEntities, updateEntity, deleteEntity,
    rebuildGraph, buildPrompt, generateScene,
    generationQueue, agentStatus,
    storyTree, currentDocument, scriboStats,
    fetchStoryTree, fetchDocument, saveDocument, createDocument, deleteDocument,
    createContainer, addLunaNote, searchStory, fetchScriboStats,
    engineConnected, edenConnected, wsConnected, wsSend,
    loading, error, setError,
  };

  return (
    <KozmoContext.Provider value={value}>
      {children}
    </KozmoContext.Provider>
  );
}
