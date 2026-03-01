import React, { useState, useMemo, useCallback, useRef, useEffect } from 'react';

const MONO = "'JetBrains Mono','SF Mono',monospace";
const BODY = "'DM Sans',system-ui,sans-serif";
const LABEL = "'Bebas Neue',system-ui,sans-serif";

const API_BASE = 'http://127.0.0.1:8000';

const STATE_COLORS = { settled: '#34d399', fluid: '#7dd3fc', drifting: '#f87171' };
const STATE_ICONS = { settled: '\u25C6', fluid: '\u25C7', drifting: '\u25CB' };
const PALETTE = ['#c084fc','#7dd3fc','#a78bfa','#34d399','#fb923c','#e09f3e','#fbbf24','#e879f9','#38bdf8','#2dd4bf','#a3e635','#fb7185','#818cf8','#94a3b8'];

function classifyState(lockIn) {
  if (lockIn >= 0.70) return 'settled';
  if (lockIn >= 0.30) return 'fluid';
  return 'drifting';
}

export default function AibrarianView() {
  const [collections, setCollections] = useState([]);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [sortBy, setSortBy] = useState('lock_in');

  // Fetch on mount
  useEffect(() => {
    (async () => {
      try {
        const [listRes, lockInRes] = await Promise.all([
          fetch(`${API_BASE}/api/aibrarian/list`),
          fetch(`${API_BASE}/api/collections/lock-in`),
        ]);
        const listData = await listRes.json();
        const lockInData = await lockInRes.json();

        const lockInMap = {};
        for (const rec of (lockInData.collections || [])) {
          lockInMap[rec.collection_key] = rec;
        }

        const merged = (listData.collections || []).map((col, i) => {
          const li = lockInMap[col.key] || {};
          return {
            key: col.key,
            label: col.description || col.name || col.key,
            tags: col.tags || [],
            color: PALETTE[i % PALETTE.length],
            lockIn: li.lock_in ?? 0.5,
            state: li.state || classifyState(li.lock_in ?? 0.5),
            docs: col.doc_count || 0,
          };
        });
        setCollections(merged);
      } catch (e) {
        setError(e.message);
      }
    })();
  }, []);

  // Filter + sort
  const displayed = useMemo(() => {
    let list = collections;
    if (filter !== 'all') list = list.filter(c => c.state === filter);
    if (search) {
      const q = search.toLowerCase();
      list = list.filter(c =>
        c.label.toLowerCase().includes(q) ||
        c.key.toLowerCase().includes(q) ||
        (c.tags || []).some(t => t.toLowerCase().includes(q))
      );
    }
    return [...list].sort((a, b) => {
      if (sortBy === 'lock_in') return b.lockIn - a.lockIn;
      if (sortBy === 'name') return a.label.localeCompare(b.label);
      if (sortBy === 'docs') return b.docs - a.docs;
      return 0;
    });
  }, [collections, filter, search, sortBy]);

  const stateGroups = useMemo(() => ({
    settled: collections.filter(c => c.state === 'settled').length,
    fluid: collections.filter(c => c.state === 'fluid').length,
    drifting: collections.filter(c => c.state === 'drifting').length,
  }), [collections]);

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
        <span style={{ fontFamily: LABEL, fontSize: 10, letterSpacing: 2, color: 'var(--ec-text-faint)' }}>AIBRARIAN</span>
        <div style={{ flex: 1 }} />
        <span className="ec-font-mono" style={{ fontSize: 8, color: 'var(--ec-text-muted)' }}>
          {collections.length} collections
        </span>
      </div>

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
                {f === 'all' ? `ALL ${collections.length}` : `${f} ${stateGroups[f]}`}
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
          display: 'grid', gridTemplateColumns: '24px 1fr 80px 120px 80px',
          padding: '6px 30px', gap: 8,
          fontSize: 7, fontFamily: LABEL, letterSpacing: 1.5, color: 'var(--ec-text-muted)',
          borderBottom: '1px solid var(--ec-border)', background: 'var(--ec-bg-raised)',
          position: 'sticky', top: 0, zIndex: 2,
        }}>
          <span></span>
          <span>COLLECTION</span>
          <span>DOCS</span>
          <span>LOCK-IN</span>
          <span style={{ textAlign: 'center' }}>STATE</span>
        </div>

        {error && (
          <div style={{ padding: '20px 30px', fontSize: 11, color: '#f87171' }}>
            Error: {error}
          </div>
        )}

        {collections.length === 0 && !error && (
          <div style={{ padding: '40px 30px', textAlign: 'center', fontSize: 11, color: 'var(--ec-text-muted)' }}>
            Loading collections...
          </div>
        )}

        <div style={{ padding: '8px 16px', display: 'flex', flexDirection: 'column', gap: 4 }}>
          {displayed.map(col => {
            const stateColor = STATE_COLORS[col.state] || STATE_COLORS.fluid;
            const icon = STATE_ICONS[col.state] || STATE_ICONS.fluid;
            const opacity = col.state === 'drifting' ? 0.5 : col.state === 'fluid' ? 0.8 : 1;

            return (
              <div key={col.key} style={{
                display: 'grid', gridTemplateColumns: '24px 1fr 80px 120px 80px',
                alignItems: 'center', padding: '8px 14px', gap: 8,
                background: 'var(--ec-bg-panel)', borderRadius: 8,
                border: '1px solid var(--ec-border)', opacity,
              }}>
                {/* State icon */}
                <span style={{ color: stateColor, fontSize: 10, textAlign: 'center' }}>{icon}</span>

                {/* Name */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden' }}>
                  <div style={{ width: 3, height: 12, borderRadius: 1, background: col.color, flexShrink: 0 }} />
                  <span style={{ fontSize: 11, fontFamily: BODY, color: 'var(--ec-text-soft)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {col.label}
                  </span>
                  {col.tags.length > 0 && (
                    <span style={{ fontSize: 7, fontFamily: MONO, color: 'var(--ec-text-muted)', flexShrink: 0 }}>
                      {col.tags.slice(0, 2).join(', ')}
                    </span>
                  )}
                </div>

                {/* Docs */}
                <span style={{ fontSize: 9, fontFamily: MONO, color: col.color }}>{col.docs}</span>

                {/* Lock-in meter */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                  <div style={{ width: 60, height: 4, borderRadius: 2, background: 'rgba(58,58,80,0.15)', overflow: 'hidden' }}>
                    <div style={{ width: `${col.lockIn * 100}%`, height: '100%', borderRadius: 2, background: stateColor, opacity: 0.7, transition: 'width 0.6s' }} />
                  </div>
                  <span style={{ fontSize: 8, fontFamily: MONO, color: stateColor, minWidth: 28 }}>
                    {(col.lockIn * 100).toFixed(0)}%
                  </span>
                </div>

                {/* State label */}
                <span style={{ fontSize: 7, fontFamily: LABEL, letterSpacing: 1.5, color: stateColor, textAlign: 'center' }}>
                  {col.state.toUpperCase()}
                </span>
              </div>
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
        <div style={{ flex: 1 }} />
        <span style={{ color: 'var(--ec-accent-voice)' }}>LUNAR STUDIO · AIBRARIAN</span>
      </div>
    </div>
  );
}
