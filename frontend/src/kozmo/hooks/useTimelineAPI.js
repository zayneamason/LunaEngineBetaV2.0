/**
 * useTimelineAPI — React hook for Timeline Container System endpoints
 *
 * Provides:
 *   - getTimeline()         — GET  /projects/{slug}/timeline
 *   - createContainer(data) — POST /projects/{slug}/timeline/containers
 *   - razor(data)           — POST /projects/{slug}/timeline/razor
 *   - splitClip(data)       — POST /projects/{slug}/timeline/split
 *   - merge(data)           — POST /projects/{slug}/timeline/merge
 *   - group(data)           — POST /projects/{slug}/timeline/group
 *   - ungroup(groupId)      — DELETE /projects/{slug}/timeline/group/{id}
 *   - timeline              — Cached timeline state (auto-fetched on mount)
 *   - audioTracks           — Extracted from /audio/timeline endpoint
 *   - connectWs()           — Open WebSocket for real-time updates
 *
 * All calls scoped to active project via KozmoProvider.
 */
import { useState, useCallback, useEffect, useRef } from 'react';
import { useKozmo } from '../KozmoProvider';

const API_BASE = '/kozmo';

export function useTimelineAPI() {
  const { activeProject } = useKozmo();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [timeline, setTimeline] = useState(null);
  const [audioTracks, setAudioTracks] = useState([]);

  const slug = activeProject?.slug;
  const wsRef = useRef(null);

  // --- Fetch timeline state ---
  const getTimeline = useCallback(async () => {
    if (!slug) return null;
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/timeline`);
      if (!res.ok) return null;
      const data = await res.json();
      setTimeline(data);
      return data;
    } catch { return null; }
  }, [slug]);

  // --- Fetch audio tracks ---
  const getAudioTracks = useCallback(async () => {
    if (!slug) return [];
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/audio/timeline`);
      if (!res.ok) return [];
      const data = await res.json();
      setAudioTracks(data.tracks || []);
      return data.tracks || [];
    } catch { return []; }
  }, [slug]);

  // Auto-fetch both on project change
  useEffect(() => {
    if (slug) {
      getTimeline();
      getAudioTracks();
    } else {
      setTimeline(null);
      setAudioTracks([]);
    }
  }, [slug, getTimeline, getAudioTracks]);

  // --- Container CRUD ---
  const createContainer = useCallback(async (data) => {
    if (!slug) return null;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/timeline/containers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `${res.status}`);
      }
      const result = await res.json();
      await getTimeline(); // Refresh
      return result;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [slug, getTimeline]);

  // --- Razor ---
  const razor = useCallback(async (containerId, cutTime) => {
    if (!slug) return null;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/timeline/razor`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ container_id: containerId, cut_time: cutTime }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `${res.status}`);
      }
      const result = await res.json();
      await getTimeline();
      return result;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [slug, getTimeline]);

  // --- Split Clip ---
  const splitClip = useCallback(async (containerId, clipId) => {
    if (!slug) return null;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/timeline/split`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ container_id: containerId, clip_id: clipId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `${res.status}`);
      }
      const result = await res.json();
      await getTimeline();
      return result;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [slug, getTimeline]);

  // --- Merge ---
  const merge = useCallback(async (targetId, sourceId, confirmed = true) => {
    if (!slug) return null;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/timeline/merge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_id: targetId, source_id: sourceId, confirmed }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `${res.status}`);
      }
      const result = await res.json();
      await getTimeline();
      return result;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [slug, getTimeline]);

  // --- Group ---
  const group = useCallback(async (containerIds, label = '') => {
    if (!slug) return null;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/timeline/group`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ container_ids: containerIds, label }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `${res.status}`);
      }
      const result = await res.json();
      await getTimeline();
      return result;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [slug, getTimeline]);

  // --- Ungroup ---
  const ungroup = useCallback(async (groupId) => {
    if (!slug) return null;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE}/projects/${slug}/timeline/group/${groupId}`, {
        method: 'DELETE',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `${res.status}`);
      }
      const result = await res.json();
      await getTimeline();
      return result;
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setLoading(false);
    }
  }, [slug, getTimeline]);

  // --- WebSocket for real-time updates ---
  const connectWs = useCallback(() => {
    if (!slug || wsRef.current) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/kozmo/ws/kozmo/${slug}/timeline`);

    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type === 'timeline.state') {
          setTimeline(msg.timeline);
        } else if (msg.events) {
          // Incremental events — refetch full state for simplicity
          getTimeline();
        }
      } catch { /* ignore parse errors */ }
    };

    ws.onclose = () => { wsRef.current = null; };
    ws.onerror = () => { wsRef.current = null; };

    wsRef.current = ws;
  }, [slug, getTimeline]);

  // Cleanup WebSocket on unmount or project change
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [slug]);

  return {
    timeline, audioTracks,
    getTimeline, getAudioTracks,
    createContainer, razor, splitClip, merge, group, ungroup,
    connectWs,
    loading, error,
  };
}
