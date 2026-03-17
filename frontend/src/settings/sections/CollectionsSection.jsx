import React, { useState, useEffect, useCallback } from 'react';

const API = '';

export default function CollectionsSection() {
  const [data, setData] = useState(null);
  const [saving, setSaving] = useState(false);
  const [edits, setEdits] = useState({});
  const [dirty, setDirty] = useState({});

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/settings/collections`);
      const json = await res.json();
      setData(json);
      const colls = json.collections || {};
      const initEdits = {};
      for (const [cid, conf] of Object.entries(colls)) {
        initEdits[cid] = {
          chunk_size: conf.chunk_size ?? 512,
          chunk_overlap: conf.chunk_overlap ?? 50,
          ingestion_pattern: conf.ingestion_pattern ?? 'utilitarian',
          extract_on_ingest: conf.extract_on_ingest ?? false,
        };
      }
      setEdits(initEdits);
      setDirty({});
    } catch (e) {
      console.error('Failed to load collections settings', e);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (!data) return <div style={{ color: 'var(--ec-text-faint)' }}>Loading…</div>;

  const collections = data.collections || {};

  const handleToggle = async (collId, enabled) => {
    setSaving(true);
    try {
      await fetch(`${API}/api/settings/collections`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ collections: { [collId]: { enabled } } }),
      });
      await load();
    } catch (e) {
      console.error('Toggle failed', e);
    }
    setSaving(false);
  };

  const handleFieldChange = (cid, key, value) => {
    setEdits((p) => ({ ...p, [cid]: { ...p[cid], [key]: value } }));
    setDirty((p) => ({ ...p, [cid]: true }));
  };

  const handleSaveCollection = async (cid) => {
    setSaving(true);
    try {
      await fetch(`${API}/api/settings/collections`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ collections: { [cid]: edits[cid] } }),
      });
      setDirty((p) => ({ ...p, [cid]: false }));
      await load();
    } catch (e) {
      console.error('Save failed', e);
    }
    setSaving(false);
  };

  return (
    <div style={{ maxWidth: 600 }}>
      <h2 className="ec-font-label" style={headerStyle}>COLLECTIONS</h2>

      {Object.entries(collections).map(([cid, cconf]) => (
        <div key={cid} className="ec-glass-card" style={{
          padding: 14, marginBottom: 10,
          border: '1px solid var(--ec-border)',
          borderRadius: 8,
          background: 'var(--ec-bg-panel)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div>
              <div className="ec-font-label" style={{ fontSize: 10, letterSpacing: 1.5, color: 'var(--ec-text)' }}>
                {cconf.name || cid}
              </div>
              <div className="ec-font-mono" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginTop: 2 }}>
                {cconf.description || ''}
              </div>
            </div>
            <button
              onClick={() => handleToggle(cid, !cconf.enabled)}
              disabled={saving}
              style={{
                background: 'transparent',
                border: `1px solid ${cconf.enabled ? 'rgba(52,211,153,0.3)' : 'var(--ec-border)'}`,
                borderRadius: 4, padding: '4px 10px',
                color: cconf.enabled ? '#34d399' : 'var(--ec-text-faint)',
                fontSize: 8, letterSpacing: 1.5, cursor: 'pointer',
              }}
            >
              {cconf.enabled ? 'ENABLED' : 'DISABLED'}
            </button>
          </div>

          {/* Details */}
          <div style={{ display: 'flex', gap: 16, marginTop: 8, flexWrap: 'wrap' }}>
            {cconf.db_path && (
              <Detail label="DB" value={cconf.db_path} />
            )}
            {cconf.schema_type && (
              <Detail label="SCHEMA" value={cconf.schema_type} />
            )}
            {cconf.tags && (
              <Detail label="TAGS" value={cconf.tags.join(', ')} />
            )}
            {cconf.read_only && (
              <span className="ec-font-label" style={{ fontSize: 7, color: '#fbbf24', letterSpacing: 1 }}>READ-ONLY</span>
            )}
          </div>

          {/* Editable fields for non-read-only collections */}
          {!cconf.read_only && edits[cid] && (
            <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--ec-border)' }}>
              <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center' }}>
                <div>
                  <label className="ec-font-label" style={{ fontSize: 7, letterSpacing: 1, color: 'var(--ec-text-muted)', display: 'block', marginBottom: 2 }}>
                    CHUNK SIZE
                  </label>
                  <input
                    type="number"
                    value={edits[cid].chunk_size}
                    onChange={(e) => handleFieldChange(cid, 'chunk_size', Number(e.target.value))}
                    style={{ ...inputStyle, width: 70 }}
                  />
                </div>
                <div>
                  <label className="ec-font-label" style={{ fontSize: 7, letterSpacing: 1, color: 'var(--ec-text-muted)', display: 'block', marginBottom: 2 }}>
                    OVERLAP
                  </label>
                  <input
                    type="number"
                    value={edits[cid].chunk_overlap}
                    onChange={(e) => handleFieldChange(cid, 'chunk_overlap', Number(e.target.value))}
                    style={{ ...inputStyle, width: 60 }}
                  />
                </div>
                <div>
                  <label className="ec-font-label" style={{ fontSize: 7, letterSpacing: 1, color: 'var(--ec-text-muted)', display: 'block', marginBottom: 2 }}>
                    INGESTION
                  </label>
                  <select
                    value={edits[cid].ingestion_pattern}
                    onChange={(e) => handleFieldChange(cid, 'ingestion_pattern', e.target.value)}
                    style={{ ...inputStyle, width: 110 }}
                  >
                    <option value="utilitarian">utilitarian</option>
                    <option value="ceremonial">ceremonial</option>
                  </select>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 10 }}>
                  <input
                    type="checkbox"
                    checked={edits[cid].extract_on_ingest}
                    onChange={(e) => handleFieldChange(cid, 'extract_on_ingest', e.target.checked)}
                    style={{ accentColor: '#34d399' }}
                  />
                  <span className="ec-font-label" style={{ fontSize: 7, letterSpacing: 1, color: 'var(--ec-text-muted)' }}>
                    EXTRACT ON INGEST
                  </span>
                </div>
              </div>
              {dirty[cid] && (
                <button
                  onClick={() => handleSaveCollection(cid)}
                  disabled={saving}
                  style={saveBtnStyle}
                >
                  SAVE
                </button>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div>
      <span className="ec-font-label" style={{ fontSize: 7, letterSpacing: 1, color: 'var(--ec-text-muted)' }}>{label} </span>
      <span className="ec-font-mono" style={{ fontSize: 9, color: 'var(--ec-text-soft)' }}>{value}</span>
    </div>
  );
}

const headerStyle = { fontSize: 11, letterSpacing: 3, color: 'var(--ec-text-soft)', marginBottom: 24 };

const inputStyle = {
  background: 'var(--ec-bg-input, var(--ec-bg))',
  border: '1px solid var(--ec-border)',
  borderRadius: 4, padding: '4px 8px',
  color: 'var(--ec-text)', fontSize: 11,
  fontFamily: 'var(--ec-font-mono, "JetBrains Mono", monospace)',
  outline: 'none', boxSizing: 'border-box',
};

const saveBtnStyle = {
  marginTop: 8,
  background: 'transparent',
  border: '1px solid rgba(52,211,153,0.3)',
  borderRadius: 4, padding: '4px 14px',
  color: '#34d399',
  fontSize: 8, letterSpacing: 1.5, cursor: 'pointer',
};
