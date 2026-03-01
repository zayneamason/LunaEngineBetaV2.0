import { useState, useCallback, useEffect, useRef } from 'react';

const API_BASE = 'http://127.0.0.1:8000';

const COLLECTION_COLORS = [
  'var(--ec-accent-luna)',      // #c084fc
  'var(--ec-accent-memory)',    // #7dd3fc
  'var(--ec-accent-voice)',     // #a78bfa
  'var(--ec-accent-prompt)',    // #34d399
  'var(--ec-accent-vk)',        // #fb923c
  'var(--ec-accent-guardian)',   // #e09f3e
  'var(--ec-accent-debug)',     // #fbbf24
  '#e879f9', '#38bdf8', '#2dd4bf', '#a3e635', '#fb7185', '#818cf8', '#94a3b8',
];

// Raw hex values for inline style computations (opacity suffixes, etc.)
const COLLECTION_COLORS_RAW = [
  '#c084fc', '#7dd3fc', '#a78bfa', '#34d399', '#fb923c',
  '#e09f3e', '#fbbf24', '#e879f9', '#38bdf8', '#2dd4bf',
  '#a3e635', '#fb7185', '#818cf8', '#94a3b8',
];

export function useAibrarian() {
  const [collections, setCollections] = useState([]);
  const [matrixStats, setMatrixStats] = useState(null);
  const [apertureState, setApertureState] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const colorMapRef = useRef({});

  // Assign a stable color to each collection key
  const getColor = useCallback((key, index) => {
    if (!colorMapRef.current[key]) {
      colorMapRef.current[key] = {
        css: COLLECTION_COLORS[index % COLLECTION_COLORS.length],
        raw: COLLECTION_COLORS_RAW[index % COLLECTION_COLORS_RAW.length],
      };
    }
    return colorMapRef.current[key];
  }, []);

  // --- Fetch collections + merge lock-in ---
  const fetchCollections = useCallback(async () => {
    try {
      const [listRes, lockInRes] = await Promise.all([
        fetch(`${API_BASE}/api/aibrarian/list`),
        fetch(`${API_BASE}/api/collections/lock-in`),
      ]);
      const listData = await listRes.json();
      const lockInData = await lockInRes.json();

      // Build lock-in lookup by key
      const lockInMap = {};
      for (const rec of (lockInData.collections || [])) {
        lockInMap[rec.collection_key] = rec;
      }

      // Merge
      const merged = (listData.collections || []).map((col, i) => {
        const li = lockInMap[col.key || col.name || col] || {};
        const colors = getColor(col.key || col.name || col, i);
        return {
          key: col.key || col.name || col,
          label: col.description || col.key || col.name || col,
          tags: col.tags || [],
          stats: col.stats || { documents: col.doc_count || 0, chunks: 0, words: 0, entities: 0 },
          color: colors.raw,
          colorCss: colors.css,
          lockIn: li.lock_in ?? 0.5,
          state: li.state || 'fluid',
          access: {
            count: li.access_count ?? 0,
            annotations: li.annotation_count ?? 0,
            connections: li.connected_collections ?? 0,
            entityOverlap: li.entity_overlap_count ?? 0,
            lastAccessed: li.last_accessed_at || null,
          },
        };
      });

      setCollections(merged);
      return merged;
    } catch (e) {
      setError(e.message);
      return [];
    }
  }, [getColor]);

  // --- Stats for a single collection ---
  const fetchStats = useCallback(async (key) => {
    try {
      const res = await fetch(`${API_BASE}/api/aibrarian/${encodeURIComponent(key)}/stats`);
      return await res.json();
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, []);

  // --- Documents for a collection ---
  const fetchDocuments = useCallback(async (key, skip = 0, limit = 50) => {
    try {
      const res = await fetch(`${API_BASE}/api/aibrarian/${encodeURIComponent(key)}/documents?skip=${skip}&limit=${limit}`);
      return await res.json();
    } catch (e) {
      setError(e.message);
      return { documents: [] };
    }
  }, []);

  // --- Search ---
  const search = useCallback(async (collection, query, type = 'semantic') => {
    try {
      const res = await fetch(`${API_BASE}/api/aibrarian/search`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ collection, query, search_type: type }),
      });
      return await res.json();
    } catch (e) {
      setError(e.message);
      return { results: [] };
    }
  }, []);

  // --- Ingest ---
  const ingest = useCallback(async (collection, filePath, metadata) => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/aibrarian/ingest`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ collection, file_path: filePath, metadata }),
      });
      return await res.json();
    } catch (e) {
      setError(e.message);
      return null;
    } finally {
      setIsLoading(false);
    }
  }, []);

  // --- Annotations ---
  const createAnnotation = useCallback(async (collectionKey, docId, annotationType, content) => {
    try {
      const res = await fetch(`${API_BASE}/api/annotations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          collection_key: collectionKey,
          doc_id: docId,
          annotation_type: annotationType,
          content,
        }),
      });
      return await res.json();
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, []);

  const fetchAnnotations = useCallback(async (collectionKey) => {
    try {
      const res = await fetch(`${API_BASE}/api/annotations?collection=${encodeURIComponent(collectionKey)}`);
      return await res.json();
    } catch (e) {
      setError(e.message);
      return { annotations: [] };
    }
  }, []);

  const fetchBridged = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/annotations/bridged`);
      return await res.json();
    } catch (e) {
      setError(e.message);
      return { bridged: [] };
    }
  }, []);

  // --- Memory Matrix Stats ---
  const fetchMatrixStats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/memory/stats`);
      const data = await res.json();
      setMatrixStats(data);
      return data;
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, []);

  // --- Aperture ---
  const fetchAperture = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/aperture`);
      const data = await res.json();
      setApertureState(data);
      return data;
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, []);

  const setAperture = useCallback(async (preset, angle) => {
    try {
      const body = {};
      if (preset) body.preset = preset;
      if (angle != null) body.angle = angle;
      const res = await fetch(`${API_BASE}/api/aperture`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      setApertureState(data);
      return data;
    } catch (e) {
      setError(e.message);
      return null;
    }
  }, []);

  // --- On mount: fetch initial data ---
  useEffect(() => {
    setIsLoading(true);
    Promise.all([fetchCollections(), fetchMatrixStats(), fetchAperture()])
      .finally(() => setIsLoading(false));
  }, [fetchCollections, fetchMatrixStats, fetchAperture]);

  // --- Poll lock-in every 30s ---
  useEffect(() => {
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`${API_BASE}/api/collections/lock-in`);
        const data = await res.json();
        const lockInMap = {};
        for (const rec of (data.collections || [])) {
          lockInMap[rec.collection_key] = rec;
        }
        setCollections(prev => prev.map(col => {
          const li = lockInMap[col.key];
          if (!li) return col;
          return { ...col, lockIn: li.lock_in, state: li.state };
        }));
      } catch {}
    }, 30000);
    return () => clearInterval(interval);
  }, []);

  return {
    collections,
    matrixStats,
    aperture: apertureState,
    isLoading,
    error,
    fetchCollections,
    fetchStats,
    fetchDocuments,
    search,
    ingest,
    createAnnotation,
    fetchAnnotations,
    fetchBridged,
    fetchMatrixStats,
    fetchAperture,
    setAperture,
  };
}
