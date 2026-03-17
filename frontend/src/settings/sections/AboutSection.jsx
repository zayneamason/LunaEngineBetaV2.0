import React, { useState, useEffect, useCallback } from 'react';

const API = '';

export default function AboutSection() {
  const [about, setAbout] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [msg, setMsg] = useState('');

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/settings/about`);
      setAbout(await res.json());
    } catch (e) {
      console.error('Failed to load about', e);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await fetch(`${API}/api/settings/export`);
      const blob = await res.json();
      const text = JSON.stringify(blob, null, 2);
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([text], { type: 'application/json' }));
      a.download = `luna-config-export-${new Date().toISOString().slice(0, 10)}.json`;
      a.click();
      setMsg('Config exported');
    } catch (e) {
      setMsg('Export failed: ' + e);
    }
    setExporting(false);
  };

  const handleImport = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      setImporting(true);
      try {
        const text = await file.text();
        const blob = JSON.parse(text);
        const res = await fetch(`${API}/api/settings/import`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(blob),
        });
        const result = await res.json();
        setMsg(`Imported ${result.files_written?.length || 0} config files`);
        await load();
      } catch (err) {
        setMsg('Import failed: ' + err);
      }
      setImporting(false);
    };
    input.click();
  };

  return (
    <div style={{ maxWidth: 480 }}>
      <h2 className="ec-font-label" style={headerStyle}>ABOUT</h2>

      {about && (
        <div style={{ marginBottom: 24 }}>
          <Row label="ENGINE VERSION" value={about.engine_version} />
          <Row label="DATA SIZE" value={`${about.data_size_mb} MB`} />
          <Row label="CONFIG ROOT" value={about.config_root} />
        </div>
      )}

      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <button onClick={handleExport} disabled={exporting} style={btnStyle}>
          {exporting ? 'EXPORTING...' : 'EXPORT CONFIG'}
        </button>
        <button onClick={handleImport} disabled={importing} style={btnStyle}>
          {importing ? 'IMPORTING...' : 'IMPORT CONFIG'}
        </button>
      </div>

      {msg && (
        <div className="ec-font-mono" style={{ fontSize: 10, color: 'var(--ec-text-soft)', marginTop: 12 }}>
          {msg}
        </div>
      )}
    </div>
  );
}

function Row({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '6px 0', borderBottom: '1px solid var(--ec-border)' }}>
      <span className="ec-font-label" style={{ fontSize: 8, letterSpacing: 1.5, color: 'var(--ec-text-faint)' }}>{label}</span>
      <span className="ec-font-mono" style={{ fontSize: 11, color: 'var(--ec-text)' }}>{value}</span>
    </div>
  );
}

const headerStyle = { fontSize: 11, letterSpacing: 3, color: 'var(--ec-text-soft)', marginBottom: 24 };
const btnStyle = {
  background: 'transparent',
  border: '1px solid var(--ec-border)',
  borderRadius: 4, padding: '8px 16px',
  color: 'var(--ec-text-soft)',
  fontSize: 9, letterSpacing: 1.5, cursor: 'pointer',
};
