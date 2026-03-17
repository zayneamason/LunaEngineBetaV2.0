import React, { useState, useEffect, useCallback } from 'react';

const API = '';

export default function NetworkSection() {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({});
  const [profiles, setProfiles] = useState({});
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/settings/network`);
      const json = await res.json();
      setData(json);
      const svc = json.services || {};
      setForm({
        host: svc.backend?.host || '0.0.0.0',
        port: svc.backend?.port || 8000,
        debug: svc.backend?.debug || false,
        frontendPort: svc.frontend?.port || 5173,
        obsPort: svc.observatory?.port || 8100,
        obsEnabled: svc.observatory?.enabled || false,
        tunnelEnabled: svc.tunnel?.enabled || false,
        selectedProfile: 'default',
      });
      setProfiles(json.profiles || {});
    } catch (e) {
      console.error('Failed to load network settings', e);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (!data) return <div style={{ color: 'var(--ec-text-faint)' }}>Loading…</div>;

  const handleChange = (key, value) => {
    setForm((p) => ({ ...p, [key]: value }));
    setDirty(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await fetch(`${API}/api/settings/network`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          services: {
            backend: { host: form.host, port: Number(form.port), debug: form.debug },
            frontend: { port: Number(form.frontendPort) },
            observatory: { port: Number(form.obsPort), enabled: form.obsEnabled },
            tunnel: { enabled: form.tunnelEnabled },
          },
        }),
      });
      setDirty(false);
      await load();
    } catch (e) {
      console.error('Save failed', e);
    }
    setSaving(false);
  };

  return (
    <div style={{ maxWidth: 480 }}>
      <h2 className="ec-font-label" style={headerStyle}>NETWORK</h2>

      {dirty && (
        <div style={{
          padding: '8px 12px', marginBottom: 16,
          background: 'rgba(251,191,36,0.08)',
          border: '1px solid rgba(251,191,36,0.3)',
          borderRadius: 6, fontSize: 10,
          color: '#fbbf24',
        }}>
          Changes require restart to take effect.
        </div>
      )}

      <Field label="HOST">
        <select
          value={form.host}
          onChange={(e) => handleChange('host', e.target.value)}
          style={inputStyle}
        >
          <option value="127.0.0.1">127.0.0.1 — localhost only</option>
          <option value="0.0.0.0">0.0.0.0 — network accessible</option>
        </select>
      </Field>

      <Field label="BACKEND PORT">
        <input
          type="number"
          min={1024} max={65535}
          value={form.port}
          onChange={(e) => handleChange('port', e.target.value)}
          style={inputStyle}
        />
      </Field>

      <Field label="DEBUG MODE">
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--ec-text-soft)', fontSize: 11, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={form.debug}
            onChange={(e) => handleChange('debug', e.target.checked)}
          />
          Enable debug logging
        </label>
      </Field>

      <Field label="FRONTEND PORT">
        <input
          type="number"
          min={1024} max={65535}
          value={form.frontendPort}
          onChange={(e) => handleChange('frontendPort', e.target.value)}
          style={inputStyle}
        />
      </Field>

      <div style={{ marginTop: 20, marginBottom: 14, borderTop: '1px solid var(--ec-border)', paddingTop: 16 }}>
        <h3 className="ec-font-label" style={{ fontSize: 9, letterSpacing: 2, color: 'var(--ec-text-faint)', marginBottom: 10 }}>
          OBSERVATORY
        </h3>
      </div>

      <Field label="OBSERVATORY PORT">
        <input
          type="number"
          min={1024} max={65535}
          value={form.obsPort}
          onChange={(e) => handleChange('obsPort', e.target.value)}
          style={inputStyle}
        />
      </Field>

      <Field label="OBSERVATORY">
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--ec-text-soft)', fontSize: 11, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={form.obsEnabled}
            onChange={(e) => handleChange('obsEnabled', e.target.checked)}
          />
          Enable Observatory service
        </label>
      </Field>

      <Field label="CLOUDFLARE TUNNEL">
        <label style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--ec-text-soft)', fontSize: 11, cursor: 'pointer' }}>
          <input
            type="checkbox"
            checked={form.tunnelEnabled}
            onChange={(e) => handleChange('tunnelEnabled', e.target.checked)}
          />
          Enable tunnel
        </label>
      </Field>

      <div style={{ marginTop: 20, marginBottom: 14, borderTop: '1px solid var(--ec-border)', paddingTop: 16 }}>
        <h3 className="ec-font-label" style={{ fontSize: 9, letterSpacing: 2, color: 'var(--ec-text-faint)', marginBottom: 10 }}>
          LAUNCH PROFILE (DISPLAY ONLY)
        </h3>
      </div>

      <Field label="ACTIVE PROFILE">
        <select
          value={form.selectedProfile}
          onChange={(e) => handleChange('selectedProfile', e.target.value)}
          style={inputStyle}
        >
          {Object.keys(profiles).map((p) => (
            <option key={p} value={p}>{p}</option>
          ))}
        </select>
      </Field>

      {profiles[form.selectedProfile] && (
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 14 }}>
          {Object.entries(profiles[form.selectedProfile]?.services || {}).map(([svc, conf]) => (
            <span key={svc} className="ec-font-label" style={{
              fontSize: 8, letterSpacing: 1, padding: '3px 8px',
              borderRadius: 4,
              background: conf.enabled ? 'rgba(52,211,153,0.1)' : 'rgba(248,113,113,0.1)',
              color: conf.enabled ? '#34d399' : '#f87171',
              border: `1px solid ${conf.enabled ? 'rgba(52,211,153,0.2)' : 'rgba(248,113,113,0.2)'}`,
            }}>
              {svc.toUpperCase()}: {conf.enabled ? 'ON' : 'OFF'}
            </span>
          ))}
        </div>
      )}

      <button onClick={handleSave} disabled={!dirty || saving} style={saveBtnStyle(dirty)}>
        {saving ? 'SAVING...' : 'SAVE & RESTART REQUIRED'}
      </button>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div style={{ marginBottom: 14 }}>
      <label className="ec-font-label" style={labelStyle}>{label}</label>
      {children}
    </div>
  );
}

const headerStyle = { fontSize: 11, letterSpacing: 3, color: 'var(--ec-text-soft)', marginBottom: 24 };
const labelStyle = { display: 'block', fontSize: 8, letterSpacing: 1.5, color: 'var(--ec-text-faint)', marginBottom: 4 };
const inputStyle = {
  background: 'var(--ec-bg-input, var(--ec-bg))',
  border: '1px solid var(--ec-border)',
  borderRadius: 4, padding: '6px 10px',
  color: 'var(--ec-text)', fontSize: 12,
  fontFamily: 'var(--ec-font-mono, "JetBrains Mono", monospace)',
  outline: 'none', width: '100%', boxSizing: 'border-box',
};
const saveBtnStyle = (dirty) => ({
  background: dirty ? 'rgba(251,191,36,0.1)' : 'transparent',
  border: `1px solid ${dirty ? 'rgba(251,191,36,0.3)' : 'var(--ec-border)'}`,
  borderRadius: 4, padding: '8px 24px',
  color: dirty ? '#fbbf24' : 'var(--ec-text-faint)',
  fontSize: 10, letterSpacing: 1.5, cursor: dirty ? 'pointer' : 'default',
});
