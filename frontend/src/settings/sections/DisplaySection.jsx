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

const TEXT_SIZE_PRESETS = [
  { id: 'normal', label: 'Normal', scale: 1 },
  { id: 'large', label: 'Large', scale: 1.15 },
  { id: 'xlarge', label: 'Extra Large', scale: 1.35 },
];

function getStoredFontScale() {
  try {
    const stored = localStorage.getItem('ec-font-scale');
    if (stored) return parseFloat(stored);
  } catch { /* ignore */ }
  return 1;
}

function applyFontScale(scale) {
  document.documentElement.style.setProperty('--ec-font-scale', scale);
  try { localStorage.setItem('ec-font-scale', String(scale)); } catch { /* ignore */ }
}

export default function DisplaySection() {
  const [badges, setBadges] = useState(DEFAULTS);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [fontScale, setFontScale] = useState(getStoredFontScale);

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

  // Apply stored font scale on mount
  useEffect(() => { applyFontScale(fontScale); }, []);

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

  const handleFontScale = (scale) => {
    setFontScale(scale);
    applyFontScale(scale);
  };

  return (
    <div style={{ maxWidth: 480 }}>
      <h2 className="ec-font-label" style={headerStyle}>DISPLAY</h2>

      {/* Text Size */}
      <div style={{ marginBottom: 20 }}>
        <label className="ec-font-label" style={labelStyle}>TEXT SIZE</label>
        <div style={{ display: 'flex', gap: 8 }}>
          {TEXT_SIZE_PRESETS.map(preset => (
            <button
              key={preset.id}
              onClick={() => handleFontScale(preset.scale)}
              style={{
                flex: 1,
                padding: '10px 12px',
                borderRadius: 6,
                border: `1px solid ${fontScale === preset.scale ? 'var(--ec-accent-luna)' : 'var(--ec-border)'}`,
                background: fontScale === preset.scale ? 'rgba(192,132,252,0.1)' : 'transparent',
                color: fontScale === preset.scale ? 'var(--ec-accent-luna)' : 'var(--ec-text-soft)',
                cursor: 'pointer',
                fontSize: 'var(--ec-fs-sm)',
                fontFamily: 'inherit',
                transition: 'all 0.2s',
              }}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </div>

      {/* Chat Badges */}
      <div style={{ marginBottom: 14 }}>
        <label className="ec-font-label" style={labelStyle}>CHAT BADGES</label>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {Object.entries(BADGE_LABELS).map(([key, label]) => (
            <label key={key} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              color: 'var(--ec-text-soft)', fontSize: 'var(--ec-fs-xs)', cursor: 'pointer',
            }}>
              <input
                type="checkbox"
                checked={badges[key] ?? false}
                onChange={() => toggle(key)}
              />
              <span className="ec-font-mono" style={{ fontSize: 'var(--ec-fs-label)' }}>
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

const headerStyle = { fontSize: 'var(--ec-fs-xs)', letterSpacing: 3, color: 'var(--ec-text-soft)', marginBottom: 24 };
const labelStyle = { display: 'block', fontSize: 'var(--ec-fs-label)', letterSpacing: 1.5, color: 'var(--ec-text-faint)', marginBottom: 8 };
const saveBtnStyle = (dirty) => ({
  background: dirty ? 'rgba(52,211,153,0.1)' : 'transparent',
  border: `1px solid ${dirty ? 'rgba(52,211,153,0.3)' : 'var(--ec-border)'}`,
  borderRadius: 4, padding: '8px 24px',
  color: dirty ? '#34d399' : 'var(--ec-text-faint)',
  fontSize: 'var(--ec-fs-label)', letterSpacing: 1.5, cursor: dirty ? 'pointer' : 'default',
});
