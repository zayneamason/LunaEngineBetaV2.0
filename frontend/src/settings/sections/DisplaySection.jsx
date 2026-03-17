import React, { useState, useEffect, useCallback } from 'react';

const BADGE_LABELS = {
  route: 'Route indicator (delegated / local / cloud)',
  model: 'Model name',
  tokens: 'Token count',
  latency: 'Latency (ms)',
  access_filter: 'Access-denied filter count',
  lunascript: 'LunaScript classification + glyph',
};

const DEFAULTS = {
  route: true,
  model: false,
  tokens: false,
  latency: true,
  access_filter: true,
  lunascript: true,
};

export default function DisplaySection() {
  const [badges, setBadges] = useState(DEFAULTS);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch('/api/settings/display');
      const json = await res.json();
      if (json?.badges) setBadges({ ...DEFAULTS, ...json.badges });
    } catch (e) {
      console.error('Failed to load display settings', e);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggle = (key) => {
    setBadges((prev) => ({ ...prev, [key]: !prev[key] }));
    setDirty(true);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await fetch('/api/settings/display', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ badges }),
      });
      setDirty(false);
    } catch (e) {
      console.error('Save failed', e);
    }
    setSaving(false);
  };

  return (
    <div style={{ maxWidth: 480 }}>
      <h2 className="ec-font-label" style={headerStyle}>DISPLAY</h2>

      <div style={{ marginBottom: 14 }}>
        <label className="ec-font-label" style={labelStyle}>CHAT BADGES</label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {Object.entries(BADGE_LABELS).map(([key, label]) => (
            <label key={key} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              color: 'var(--ec-text-soft)', fontSize: 11, cursor: 'pointer',
            }}>
              <input
                type="checkbox"
                checked={badges[key] ?? false}
                onChange={() => toggle(key)}
              />
              <span className="ec-font-mono" style={{ fontSize: 10 }}>
                {label}
              </span>
            </label>
          ))}
        </div>
      </div>

      <button onClick={handleSave} disabled={!dirty || saving} style={saveBtnStyle(dirty)}>
        {saving ? 'SAVING...' : 'SAVE'}
      </button>
    </div>
  );
}

const headerStyle = { fontSize: 11, letterSpacing: 3, color: 'var(--ec-text-soft)', marginBottom: 24 };
const labelStyle = { display: 'block', fontSize: 8, letterSpacing: 1.5, color: 'var(--ec-text-faint)', marginBottom: 8 };
const saveBtnStyle = (dirty) => ({
  background: dirty ? 'rgba(52,211,153,0.1)' : 'transparent',
  border: `1px solid ${dirty ? 'rgba(52,211,153,0.3)' : 'var(--ec-border)'}`,
  borderRadius: 4, padding: '8px 24px',
  color: dirty ? '#34d399' : 'var(--ec-text-faint)',
  fontSize: 10, letterSpacing: 1.5, cursor: dirty ? 'pointer' : 'default',
});
