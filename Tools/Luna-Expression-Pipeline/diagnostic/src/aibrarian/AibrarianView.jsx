import React, { useState, useMemo, useEffect } from 'react';

const API = 'http://127.0.0.1:8000';
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
  const [expanded, setExpanded] = useState(null);
  const [docs, setDocs] = useState({});

  useEffect(() => {
    (async () => {
      try {
        const [listRes, lockInRes] = await Promise.all([
          fetch(`${API}/api/aibrarian/list`),
          fetch(`${API}/api/collections/lock-in`),
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
            enabled: col.enabled,
            connected: col.connected,
          };
        });
        setCollections(merged);
      } catch (e) {
        setError(e.message);
      }
    })();
  }, []);

  const toggleExpand = async (key) => {
    if (expanded === key) { setExpanded(null); return; }
    setExpanded(key);
    if (!docs[key]) {
      try {
        const r = await fetch(`${API}/api/aibrarian/${key}/documents?limit=10`);
        const d = await r.json();
        setDocs(prev => ({ ...prev, [key]: d.documents || [] }));
      } catch { setDocs(prev => ({ ...prev, [key]: [] })); }
    }
  };

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

  const mono = "'JetBrains Mono', monospace";

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#08080f', color: '#c0c0d0' }}>

      {/* Sub-header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '8px 16px',
        borderBottom: '1px solid rgba(255,255,255,0.06)', flexShrink: 0,
      }}>
        <div style={{ width: 3, height: 16, borderRadius: 2, background: '#a78bfa' }} />
        <span style={{ fontSize: 10, fontWeight: 700, letterSpacing: 2, color: '#a78bfa', fontFamily: mono }}>AIBRARIAN</span>
        <span style={{ fontSize: 9, color: '#555', fontFamily: mono }}>LIBRARY COGNITION</span>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 8, color: '#444', fontFamily: mono }}>{collections.length} collections</span>
      </div>

      {/* Query bar */}
      <div style={{ padding: '8px 16px', borderBottom: '1px solid rgba(255,255,255,0.06)', flexShrink: 0 }}>
        <div style={{
          display: 'flex', gap: 6, alignItems: 'center', padding: '6px 12px',
          background: 'rgba(255,255,255,0.02)', borderRadius: 6, border: '1px solid rgba(255,255,255,0.06)',
        }}>
          <span style={{ fontSize: 11, opacity: 0.3 }}>{'\u2315'}</span>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search collections, tags, documents..."
            style={{ flex: 1, background: 'transparent', border: 'none', outline: 'none', color: '#c0c0d0', fontSize: 10, fontFamily: mono }}
          />
          <div style={{ display: 'flex', gap: 3 }}>
            {['all', 'settled', 'fluid', 'drifting'].map(f => (
              <div key={f} onClick={() => setFilter(f)} style={{
                padding: '2px 8px', borderRadius: 3, cursor: 'pointer',
                background: filter === f ? `${STATE_COLORS[f] || '#a78bfa'}15` : 'transparent',
                border: `1px solid ${filter === f ? `${STATE_COLORS[f] || '#a78bfa'}33` : 'transparent'}`,
                fontSize: 8, fontFamily: mono,
                color: filter === f ? (STATE_COLORS[f] || '#a78bfa') : '#555',
                textTransform: 'uppercase', transition: 'all 0.2s',
              }}>
                {f === 'all' ? `ALL ${collections.length}` : `${f} ${stateGroups[f]}`}
              </div>
            ))}
          </div>
          <div style={{ width: 1, height: 14, background: 'rgba(255,255,255,0.06)' }} />
          <select value={sortBy} onChange={e => setSortBy(e.target.value)} style={{
            background: '#0f0f19', border: '1px solid rgba(255,255,255,0.06)', borderRadius: 3,
            color: '#888', fontSize: 8, fontFamily: mono, padding: '2px 4px', outline: 'none',
          }}>
            <option value="lock_in">SORT: LOCK-IN</option>
            <option value="docs">SORT: DOCS</option>
            <option value="name">SORT: NAME</option>
          </select>
        </div>
      </div>

      {/* Collection list */}
      <div style={{ flex: 1, overflow: 'auto', padding: '0' }}>
        {/* Column headers */}
        <div style={{
          display: 'grid', gridTemplateColumns: '24px 1fr 60px 60px 120px 60px',
          padding: '6px 30px', gap: 8,
          fontSize: 7, fontFamily: mono, letterSpacing: 1.5, color: '#555',
          borderBottom: '1px solid rgba(255,255,255,0.04)', background: '#0a0a14',
          position: 'sticky', top: 0, zIndex: 2, textTransform: 'uppercase',
        }}>
          <span></span>
          <span>Collection</span>
          <span>Status</span>
          <span>Docs</span>
          <span>Lock-In</span>
          <span style={{ textAlign: 'center' }}>State</span>
        </div>

        {error && (
          <div style={{ padding: '20px 30px', fontSize: 10, color: '#f87171', fontFamily: mono }}>
            Error: {error}
          </div>
        )}

        {collections.length === 0 && !error && (
          <div style={{ padding: '40px 30px', textAlign: 'center', fontSize: 10, color: '#555', fontFamily: mono }}>
            Loading collections...
          </div>
        )}

        <div style={{ padding: '6px 16px', display: 'flex', flexDirection: 'column', gap: 3 }}>
          {displayed.map(col => {
            const stateColor = STATE_COLORS[col.state] || STATE_COLORS.fluid;
            const icon = STATE_ICONS[col.state] || STATE_ICONS.fluid;
            const isExpanded = expanded === col.key;
            const opacity = col.state === 'drifting' ? 0.5 : col.state === 'fluid' ? 0.8 : 1;

            return (
              <div key={col.key}>
                <div onClick={() => toggleExpand(col.key)} style={{
                  display: 'grid', gridTemplateColumns: '24px 1fr 60px 60px 120px 60px',
                  alignItems: 'center', padding: '7px 14px', gap: 8,
                  background: isExpanded ? 'rgba(167,139,250,0.04)' : 'rgba(255,255,255,0.015)',
                  borderRadius: 6,
                  border: `1px solid ${isExpanded ? 'rgba(167,139,250,0.15)' : 'rgba(255,255,255,0.04)'}`,
                  cursor: 'pointer', transition: 'all 0.15s', opacity,
                }}
                  onMouseEnter={e => { if (!isExpanded) e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
                  onMouseLeave={e => { if (!isExpanded) e.currentTarget.style.background = 'rgba(255,255,255,0.015)'; }}
                >
                  <span style={{ color: stateColor, fontSize: 10, textAlign: 'center' }}>{icon}</span>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, overflow: 'hidden' }}>
                    <div style={{ width: 3, height: 12, borderRadius: 1, background: col.color, flexShrink: 0 }} />
                    <span style={{ fontSize: 10, color: '#d0d0e0', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', fontFamily: mono }}>
                      {col.label}
                    </span>
                    {col.tags.length > 0 && (
                      <span style={{ fontSize: 7, fontFamily: mono, color: '#444', flexShrink: 0 }}>
                        {col.tags.slice(0, 3).join(' · ')}
                      </span>
                    )}
                  </div>

                  <span style={{
                    fontSize: 7, fontFamily: mono, textAlign: 'center',
                    color: col.connected ? '#34d399' : col.enabled ? '#fbbf24' : '#555',
                  }}>
                    {col.connected ? 'LIVE' : col.enabled ? 'READY' : 'OFF'}
                  </span>

                  <span style={{ fontSize: 9, fontFamily: mono, color: col.color }}>{col.docs}</span>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 60, height: 3, borderRadius: 2, background: 'rgba(255,255,255,0.04)', overflow: 'hidden' }}>
                      <div style={{ width: `${col.lockIn * 100}%`, height: '100%', borderRadius: 2, background: stateColor, opacity: 0.7, transition: 'width 0.6s' }} />
                    </div>
                    <span style={{ fontSize: 8, fontFamily: mono, color: stateColor, minWidth: 28 }}>
                      {(col.lockIn * 100).toFixed(0)}%
                    </span>
                  </div>

                  <span style={{ fontSize: 7, fontFamily: mono, letterSpacing: 1, color: stateColor, textAlign: 'center' }}>
                    {col.state.toUpperCase()}
                  </span>
                </div>

                {/* Expanded document list */}
                {isExpanded && (
                  <div style={{
                    margin: '2px 0 4px 38px', padding: '8px 14px',
                    background: 'rgba(167,139,250,0.03)', borderRadius: 6,
                    border: '1px solid rgba(167,139,250,0.08)',
                  }}>
                    {!docs[col.key] ? (
                      <span style={{ fontSize: 9, color: '#555', fontFamily: mono }}>Loading documents...</span>
                    ) : docs[col.key].length === 0 ? (
                      <span style={{ fontSize: 9, color: '#555', fontFamily: mono }}>No documents in this collection</span>
                    ) : (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                        {docs[col.key].map((doc, i) => (
                          <div key={doc.id || i} style={{
                            display: 'flex', alignItems: 'center', gap: 8,
                            padding: '4px 8px', borderRadius: 4,
                            background: 'rgba(255,255,255,0.015)',
                          }}>
                            <span style={{ fontSize: 8, color: '#444', fontFamily: mono, minWidth: 20 }}>{i + 1}.</span>
                            <span style={{ fontSize: 9, color: '#a0a0b0', fontFamily: mono, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {doc.title || doc.source || doc.id || 'Untitled'}
                            </span>
                            {doc.word_count && (
                              <span style={{ fontSize: 7, color: '#444', fontFamily: mono }}>{doc.word_count} words</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Isolation layer */}
        <div style={{ padding: '12px 16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span style={{ fontSize: 7, fontFamily: mono, letterSpacing: 2, color: '#e09f3e', opacity: 0.4, textTransform: 'uppercase' }}>Isolation Layer</span>
            <div style={{ flex: 1, height: 1, background: 'rgba(224,159,62,0.06)' }} />
          </div>
          <div style={{
            background: 'rgba(255,255,255,0.015)', borderRadius: 6, border: '1px solid rgba(224,159,62,0.07)',
            padding: '8px 14px', display: 'flex', gap: 12, alignItems: 'center', fontSize: 9,
          }}>
            <span style={{ color: '#666', fontFamily: mono, flex: 1, fontSize: 8 }}>
              Collections are sandboxed. Luna reads but doesn't merge into Matrix unless she annotates.
            </span>
            {['READ-ONLY DEFAULT', 'PROVENANCE TRACKED', 'ANNOTATION = BRIDGE'].map(label => (
              <span key={label} style={{
                padding: '2px 8px', borderRadius: 3, fontSize: 7, fontFamily: mono,
                background: 'rgba(224,159,62,0.05)', border: '1px solid rgba(224,159,62,0.09)', color: '#e09f3e',
              }}>{label}</span>
            ))}
          </div>
        </div>
      </div>

      {/* Status bar */}
      <div style={{
        height: 24, borderTop: '1px solid rgba(255,255,255,0.06)',
        display: 'flex', alignItems: 'center', padding: '0 16px', gap: 16,
        fontSize: 8, fontFamily: mono, color: '#444', flexShrink: 0, background: '#0a0a14',
      }}>
        <span><span style={{ color: '#34d399' }}>{'\u25C6'}</span> {stateGroups.settled} settled</span>
        <span><span style={{ color: '#7dd3fc' }}>{'\u25C7'}</span> {stateGroups.fluid} fluid</span>
        <span><span style={{ color: '#f87171' }}>{'\u25CB'}</span> {stateGroups.drifting} drifting</span>
        <div style={{ flex: 1 }} />
        <span style={{ color: '#a78bfa' }}>AIBRARIAN · LIBRARY COGNITION</span>
      </div>
    </div>
  );
}
