import React, { useState, useEffect, useCallback } from 'react';
import { useFrontendConfig } from '../../hooks/useFrontendConfig';
import SliderConfirm from '../../components/SliderConfirm';

const API = '';

export default function AboutSection({ demoMode }) {
  const config = useFrontendConfig();
  const isDemoMode = demoMode || config.demo_mode;
  const [about, setAbout] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [importing, setImporting] = useState(false);
  const [msg, setMsg] = useState('');
  const [preflight, setPreflight] = useState(null);
  const [preflighting, setPreflighting] = useState(false);
  const [jumpstarting, setJumpstarting] = useState(false);
  const [jumpResult, setJumpResult] = useState(null);
  const [resetting, setResetting] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);

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

  const handlePreflight = async () => {
    setPreflighting(true);
    setPreflight(null);
    try {
      const res = await fetch(`${API}/api/preflight`, { method: 'POST' });
      setPreflight(await res.json());
    } catch (e) {
      setPreflight({ status: 'fail', subsystems: [{ name: 'request', ok: false, detail: String(e) }], all_ok: false });
    }
    setPreflighting(false);
  };

  const handleJumpstart = async () => {
    setJumpstarting(true);
    setJumpResult(null);
    try {
      const res = await fetch(`${API}/api/jumpstart`, { method: 'POST' });
      const result = await res.json();
      setJumpResult(result);
      setPreflight(result.preflight);
    } catch (e) {
      setJumpResult({ all_ok: false, actions: [{ action: 'request', ok: false, detail: String(e) }] });
    }
    setJumpstarting(false);
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

      {/* ── Pre-flight + Jumpstart ── */}
      <div style={{ marginTop: 28, borderTop: '1px solid var(--ec-border)', paddingTop: 20 }}>
        <div className="ec-font-label" style={{ fontSize: 8, letterSpacing: 2, color: 'var(--ec-text-faint)', marginBottom: 12 }}>
          DIAGNOSTICS
        </div>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
          <button onClick={handlePreflight} disabled={preflighting} style={btnStyle}>
            {preflighting ? 'RUNNING...' : 'RUN PRE-FLIGHT'}
          </button>
          <button onClick={handleJumpstart} disabled={jumpstarting} style={{ ...btnStyle, borderColor: 'var(--ec-accent, #7c6fff)' }}>
            {jumpstarting ? 'RESTARTING...' : '\u26A1 JUMPSTART'}
          </button>
        </div>

        {preflight && (
          <div style={{ marginTop: 14 }}>
            {preflight.subsystems?.map((s) => (
              <div key={s.name} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 0' }}>
                <span style={{ width: 10, height: 10, borderRadius: '50%', background: s.ok ? '#4ade80' : (s.status === 'unavailable' ? '#a3a3a3' : '#f87171'), flexShrink: 0 }} />
                <span className="ec-font-mono" style={{ fontSize: 10, color: 'var(--ec-text)' }}>{s.name}</span>
                <span className="ec-font-mono" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginLeft: 'auto' }}>
                  {s.detail} ({s.latency_ms}ms)
                </span>
              </div>
            ))}
          </div>
        )}

        {jumpResult && (
          <div style={{ marginTop: 10 }}>
            <div className="ec-font-label" style={{ fontSize: 8, letterSpacing: 1.5, color: 'var(--ec-text-faint)', marginBottom: 6 }}>ACTIONS</div>
            {jumpResult.actions?.map((a, i) => (
              <div key={i} className="ec-font-mono" style={{ fontSize: 9, color: a.ok ? 'var(--ec-text-soft)' : '#f87171', padding: '2px 0' }}>
                {a.ok ? '\u2713' : '\u2717'} {a.action} {a.detail ? `— ${a.detail}` : ''}
              </div>
            ))}
          </div>
        )}
      </div>

      {msg && (
        <div className="ec-font-mono" style={{ fontSize: 10, color: 'var(--ec-text-soft)', marginTop: 12 }}>
          {msg}
        </div>
      )}

      {/* ── Demo Reset (only in demo builds) ── */}
      {isDemoMode && (
        <div style={{ marginTop: 32, borderTop: '1px solid var(--ec-border)', paddingTop: 20 }}>
          <div className="ec-font-label" style={{ fontSize: 8, letterSpacing: 2, color: '#f87171', marginBottom: 12 }}>
            DEMO RESET
          </div>
          <div className="ec-font-mono" style={{ fontSize: 10, color: 'var(--ec-text-faint)', marginBottom: 16, lineHeight: 1.5 }}>
            Wipes conversation history, memories, and user identity.
            Collections and API keys are preserved.
          </div>
          {resetting ? (
            <div className="ec-font-mono" style={{ color: '#f87171', fontSize: 10 }}>Resetting... page will reload.</div>
          ) : showResetConfirm ? (
            <div>
              <div className="ec-font-mono" style={{ fontSize: 10, color: '#f87171', marginBottom: 12 }}>
                Are you sure? All conversations and memories will be erased.
              </div>
              <SliderConfirm
                label="SLIDE TO RESET"
                onConfirm={async () => {
                  setResetting(true);
                  try {
                    const res = await fetch(`${API}/api/demo-reset`, { method: 'POST' });
                    const result = await res.json();
                    if (result.status === 'reset') {
                      setMsg('Reset complete. Reloading...');
                      setTimeout(() => window.location.reload(), 1500);
                    } else {
                      setMsg('Reset failed: ' + (result.detail || 'unknown error'));
                      setResetting(false);
                    }
                  } catch (e) {
                    setMsg('Reset failed: ' + e);
                    setResetting(false);
                  }
                }}
              />
              <button
                onClick={() => setShowResetConfirm(false)}
                style={{ ...btnStyle, marginTop: 10, fontSize: 8, color: 'var(--ec-text-faint)' }}
              >
                CANCEL
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowResetConfirm(true)}
              style={{ ...btnStyle, borderColor: 'rgba(248,113,113,0.3)', color: '#f87171' }}
            >
              RESET LUNA
            </button>
          )}
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
