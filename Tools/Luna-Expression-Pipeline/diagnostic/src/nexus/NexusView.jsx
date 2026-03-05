import React, { useState, useMemo, useCallback } from 'react';
import { useNexus } from './hooks/useNexus';
import { CompactRow, ExpandedRow } from './components/CollectionRow';
import { classifyState, STATE_COLORS } from './components/LockInMeter';
import IngestModal from './components/IngestModal';
import NewCollectionModal from './components/NewCollectionModal';
import ApertureDial from './components/ApertureDial';
import ProjectCard from './components/ProjectCard';

const MONO = "'JetBrains Mono','SF Mono',monospace";
const BODY = "'DM Sans',system-ui,sans-serif";
const LABEL = "'Bebas Neue',system-ui,sans-serif";

export default function NexusView() {
  const {
    collections, projects, activeProject, aperture, isLoading, error,
    fetchDocuments, fetchAnnotations, ingest,
    createAnnotation, setAperture,
    activateProject, deactivateProject,
  } = useNexus();

  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [sortBy, setSortBy] = useState('lock_in');
  const [expandedId, setExpandedId] = useState(null);
  const [expandedData, setExpandedData] = useState({});
  const [ingestTarget, setIngestTarget] = useState(null);
  const [showNewModal, setShowNewModal] = useState(false);

  // Expand a collection row — fetch docs + annotations
  const handleExpand = useCallback(async (key) => {
    if (expandedId === key) { setExpandedId(null); return; }
    setExpandedId(key);
    if (!expandedData[key]) {
      const [docRes, annRes] = await Promise.all([
        fetchDocuments(key, 0, 50),
        fetchAnnotations(key),
      ]);
      setExpandedData(prev => ({
        ...prev,
        [key]: { docs: docRes.documents || [], annotations: annRes.annotations || [] },
      }));
    }
  }, [expandedId, expandedData, fetchDocuments, fetchAnnotations]);

  // Create annotation and refresh cache
  const handleCreateAnnotation = useCallback(async (collKey, docId, type, text) => {
    await createAnnotation(collKey, docId, type, text);
    const annRes = await fetchAnnotations(collKey);
    setExpandedData(prev => ({
      ...prev,
      [collKey]: { ...prev[collKey], annotations: annRes.annotations || [] },
    }));
  }, [createAnnotation, fetchAnnotations]);

  // Ingest callback
  const handleIngest = useCallback(async (collKey, mode, path, pattern) => {
    await ingest(collKey, path, { mode, ingestion_pattern: pattern });
    setIngestTarget(null);
  }, [ingest]);

  // Aperture change
  const handleApertureChange = useCallback((angle) => {
    // Find nearest preset
    const presets = { tunnel: 15, narrow: 35, balanced: 55, wide: 75, open: 95 };
    let nearest = 'balanced';
    let minDist = Infinity;
    for (const [name, a] of Object.entries(presets)) {
      if (Math.abs(a - angle) < minDist) { minDist = Math.abs(a - angle); nearest = name; }
    }
    setAperture(nearest, angle);
  }, [setAperture]);

  // Filter by active project, then by state + search
  const visibleCollections = useMemo(() => {
    if (!activeProject) return collections;
    return collections.filter(c => c.project_key === activeProject);
  }, [collections, activeProject]);

  // Filter + sort
  const displayed = useMemo(() => {
    let list = visibleCollections;
    if (filter !== 'all') list = list.filter(c => c.state === filter);
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(c =>
        (c.label || '').toLowerCase().includes(q) ||
        (c.key || '').toLowerCase().includes(q) ||
        (c.tags || []).some(t => t.toLowerCase().includes(q))
      );
    }
    return [...list].sort((a, b) => {
      if (sortBy === 'lock_in') return (b.lockIn || 0) - (a.lockIn || 0);
      if (sortBy === 'name') return (a.label || '').localeCompare(b.label || '');
      if (sortBy === 'docs') return (b.stats?.documents || 0) - (a.stats?.documents || 0);
      return 0;
    });
  }, [visibleCollections, filter, search, sortBy]);

  const stateGroups = useMemo(() => ({
    settled: visibleCollections.filter(c => c.state === 'settled').length,
    fluid: visibleCollections.filter(c => c.state === 'fluid').length,
    drifting: visibleCollections.filter(c => c.state === 'drifting').length,
  }), [visibleCollections]);

  const totalDocs = useMemo(() =>
    visibleCollections.reduce((s, c) => s + (c.stats?.documents || 0), 0),
  [visibleCollections]);

  const avgLockIn = useMemo(() => {
    if (!visibleCollections.length) return 0;
    return visibleCollections.reduce((s, c) => s + (c.lockIn || 0), 0) / visibleCollections.length;
  }, [visibleCollections]);

  return (
    <div style={{
      height: '100%', fontFamily: BODY,
      color: 'var(--ec-text)', display: 'flex', flexDirection: 'column',
      background: 'var(--ec-bg)',
    }}>

      {/* HEADER */}
      <div style={{
        height: 44, background: 'var(--ec-bg-raised)', borderBottom: '1px solid var(--ec-border)',
        display: 'flex', alignItems: 'center', padding: '0 16px', gap: 10, flexShrink: 0,
      }}>

        <div style={{ width: 3, height: 20, borderRadius: 2, background: 'var(--ec-accent-voice)', boxShadow: '0 0 8px rgba(167,139,250,0.5)' }} />
        <span style={{ fontFamily: LABEL, fontSize: 11, letterSpacing: 2.5, color: 'var(--ec-accent-voice)' }}>LUNAR STUDIO</span>
        <div style={{ width: 1, height: 14, background: 'var(--ec-border)' }} />
        <span style={{ fontFamily: LABEL, fontSize: 10, letterSpacing: 2, color: 'var(--ec-text-faint)' }}>NEXUS</span>
        <div style={{ flex: 1 }} />

        {/* Aperture badge */}
        {aperture && (
          <span className="ec-font-mono" style={{ fontSize: 8, color: 'var(--ec-text-muted)', padding: '2px 6px', borderRadius: 3, background: 'rgba(167,139,250,0.06)', border: '1px solid rgba(167,139,250,0.1)' }}>
            {(aperture.preset || 'balanced').toUpperCase()} {aperture.angle || 55}&deg;
          </span>
        )}

        <button
          onClick={() => setShowNewModal(true)}
          style={{
            padding: '3px 10px', borderRadius: 4, border: '1px solid var(--ec-border)',
            background: 'transparent', color: 'var(--ec-accent-voice)', cursor: 'pointer',
            fontSize: 9, fontFamily: MONO,
          }}
        >
          + NEW COLLECTION
        </button>
        <span className="ec-font-mono" style={{ fontSize: 8, color: 'var(--ec-text-muted)' }}>
          {visibleCollections.length}{activeProject ? `/${collections.length}` : ''} collections
        </span>
      </div>

      {/* PROJECT STRIP */}
      {projects.length > 0 && (
        <div style={{
          padding: '8px 16px', borderBottom: '1px solid var(--ec-border)',
          display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0,
          overflowX: 'auto',
        }}>
          <span style={{ fontSize: 7, fontFamily: LABEL, letterSpacing: 2, color: 'var(--ec-text-muted)', flexShrink: 0 }}>PROJECTS</span>
          <div style={{ width: 1, height: 14, background: 'var(--ec-border)', flexShrink: 0 }} />
          {/* "All" pill */}
          <div
            onClick={() => deactivateProject()}
            style={{
              padding: '4px 10px', borderRadius: 5, cursor: 'pointer', flexShrink: 0,
              fontSize: 9, fontFamily: MONO,
              background: !activeProject ? 'rgba(167,139,250,0.1)' : 'var(--ec-bg-panel)',
              border: `1px solid ${!activeProject ? 'rgba(167,139,250,0.3)' : 'var(--ec-border)'}`,
              color: !activeProject ? 'var(--ec-accent-voice)' : 'var(--ec-text-muted)',
              transition: 'all 0.2s',
            }}
          >ALL</div>
          {projects.map(p => (
            <ProjectCard
              key={p.slug}
              project={p}
              isActive={activeProject === p.slug}
              onActivate={activateProject}
              onDeactivate={deactivateProject}
            />
          ))}
        </div>
      )}

      {/* QUERY BAR */}
      <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--ec-border)', flexShrink: 0 }}>
        <div style={{
          display: 'flex', gap: 6, alignItems: 'center', padding: '7px 12px',
          background: 'var(--ec-bg-panel)', borderRadius: 8, border: '1px solid var(--ec-border)',
        }}>
          <span style={{ fontSize: 12, opacity: 0.3 }}>{'\u27D0'}</span>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search collections, tags, documents..."
            style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: 'var(--ec-text)', fontSize: 11, fontFamily: BODY }}
          />
          <div style={{ display: 'flex', gap: 3 }}>
            {['all', 'settled', 'fluid', 'drifting'].map(f => (
              <div key={f} onClick={() => setFilter(f)} style={{
                padding: '2px 8px', borderRadius: 3, cursor: 'pointer',
                background: filter === f ? `${STATE_COLORS[f] || '#c084fc'}15` : 'transparent',
                border: `1px solid ${filter === f ? `${STATE_COLORS[f] || '#c084fc'}30` : 'transparent'}`,
                fontSize: 8, fontFamily: MONO,
                color: filter === f ? (STATE_COLORS[f] || '#c084fc') : 'var(--ec-text-muted)',
                textTransform: 'uppercase',
              }}>
                {f === 'all' ? `ALL ${visibleCollections.length}` : `${f} ${stateGroups[f]}`}
              </div>
            ))}
          </div>
          <div style={{ width: 1, height: 14, background: 'var(--ec-border)' }} />
          <select value={sortBy} onChange={e => setSortBy(e.target.value)} style={{
            background: 'var(--ec-bg-card, #171723)', border: '1px solid var(--ec-border)', borderRadius: 3,
            color: 'var(--ec-text-soft)', fontSize: 8, fontFamily: MONO, padding: '2px 4px', outline: 'none',
          }}>
            <option value="lock_in">SORT: LOCK-IN</option>
            <option value="docs">SORT: DOCS</option>
            <option value="name">SORT: NAME</option>
          </select>
        </div>
      </div>

      {/* COLLECTION LIST */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {/* Column headers */}
        <div style={{
          display: 'grid', gridTemplateColumns: '24px 1fr 200px 120px 80px 100px',
          padding: '6px 30px', gap: 8,
          fontSize: 7, fontFamily: LABEL, letterSpacing: 1.5, color: 'var(--ec-text-muted)',
          borderBottom: '1px solid var(--ec-border)', background: 'var(--ec-bg-raised)',
          position: 'sticky', top: 0, zIndex: 2,
        }}>
          <span></span>
          <span>COLLECTION</span>
          <span>STATS</span>
          <span>LOCK-IN</span>
          <span style={{ textAlign: 'center' }}>STATE</span>
          <span style={{ textAlign: 'center' }}>ACTIONS</span>
        </div>

        {error && (
          <div style={{ padding: '20px 30px', fontSize: 11, color: '#f87171' }}>
            Error: {error}
          </div>
        )}

        {isLoading && collections.length === 0 && !error && (
          <div style={{ padding: '40px 30px', textAlign: 'center', fontSize: 11, color: 'var(--ec-text-muted)' }}>
            Loading collections...
          </div>
        )}

        <div style={{ padding: '8px 16px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {displayed.map(col => {
            const isExpanded = expandedId === col.key;
            const data = expandedData[col.key];

            if (isExpanded && data) {
              return (
                <ExpandedRow
                  key={col.key}
                  col={col}
                  docs={data.docs}
                  annotations={data.annotations}
                  onCollapse={() => setExpandedId(null)}
                  onIngest={() => setIngestTarget(col)}
                  onCreateAnnotation={(type, text) =>
                    handleCreateAnnotation(col.key, null, type, text)
                  }
                />
              );
            }

            return (
              <CompactRow
                key={col.key}
                col={col}
                onExpand={() => handleExpand(col.key)}
                onIngest={() => setIngestTarget(col)}
              />
            );
          })}
        </div>

        {/* SECURITY LAYER */}
        <div style={{ padding: '12px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
            <span style={{ fontSize: 7, fontFamily: LABEL, letterSpacing: 2, color: '#e09f3e', opacity: 0.5 }}>ISOLATION LAYER</span>
            <div style={{ flex: 1, height: 1, background: 'rgba(224,159,62,0.06)' }} />
          </div>
          <div style={{
            background: 'var(--ec-bg-panel)', borderRadius: 8, border: '1px solid rgba(224,159,62,0.07)',
            padding: '8px 14px', display: 'flex', gap: 12, alignItems: 'center', fontSize: 9,
          }}>
            <span style={{ color: 'var(--ec-text-faint)', fontFamily: BODY, flex: 1 }}>
              Collections are sandboxed. Luna reads but doesn't merge into Matrix unless she annotates.
            </span>
            {['READ-ONLY DEFAULT', 'PROVENANCE TRACKED', 'ANNOTATION = BRIDGE'].map(label => (
              <span key={label} style={{
                padding: '2px 8px', borderRadius: 3, fontSize: 7, fontFamily: MONO,
                background: 'rgba(224,159,62,0.05)', border: '1px solid rgba(224,159,62,0.09)', color: '#e09f3e',
              }}>{label}</span>
            ))}
          </div>
        </div>
      </div>

      {/* STATUS BAR */}
      <div style={{
        height: 26, background: 'var(--ec-bg-raised)', borderTop: '1px solid var(--ec-border)',
        display: 'flex', alignItems: 'center', padding: '0 16px', gap: 16,
        fontSize: 8, fontFamily: MONO, color: 'var(--ec-text-faint)', flexShrink: 0,
      }}>
        <span><span style={{ color: '#34d399' }}>{'\u25C6'}</span> {stateGroups.settled} settled</span>
        <span><span style={{ color: '#7dd3fc' }}>{'\u25C7'}</span> {stateGroups.fluid} fluid</span>
        <span><span style={{ color: '#f87171' }}>{'\u25CB'}</span> {stateGroups.drifting} drifting</span>
        <div style={{ width: 1, height: 10, background: 'var(--ec-border)' }} />
        <span>{totalDocs} docs</span>
        <span>avg lock-in {(avgLockIn * 100).toFixed(0)}%</span>
        <div style={{ flex: 1 }} />
        <span style={{ color: 'var(--ec-accent-voice)' }}>LUNAR STUDIO &middot; NEXUS</span>
      </div>

      {/* MODALS */}
      {ingestTarget && (
        <IngestModal
          collection={ingestTarget}
          onClose={() => setIngestTarget(null)}
          onIngest={handleIngest}
        />
      )}
      {showNewModal && (
        <NewCollectionModal
          onClose={() => setShowNewModal(false)}
          onCreate={(name, desc, tags) => {
            setShowNewModal(false);
          }}
        />
      )}
    </div>
  );
}
