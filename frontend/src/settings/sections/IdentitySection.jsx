import React, { useState, useEffect, useCallback } from 'react';

const API = '';

const CATEGORY_LABELS = {
  1: 'Company Overview',
  2: 'Financials',
  3: 'Legal',
  4: 'Product',
  5: 'Market & Competition',
  6: 'Team',
  7: 'Go-to-Market',
  8: 'Partnerships & Impact',
  9: 'Risk & Mitigation',
};

export default function IdentitySection() {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/settings/identity`);
      const json = await res.json();
      setData(json);
      setForm(json);
    } catch (e) {
      console.error('Failed to load identity settings', e);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (!data) return <div style={{ color: 'var(--ec-text-faint)' }}>Loading…</div>;

  const handleChange = (key, value) => {
    setForm((p) => ({ ...p, [key]: value }));
    setDirty(true);
  };

  const toggleCategory = (catId) => {
    const current = form.dataroom_categories || [];
    const next = current.includes(catId)
      ? current.filter((c) => c !== catId)
      : [...current, catId].sort((a, b) => a - b);
    handleChange('dataroom_categories', next);
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await fetch(`${API}/api/settings/identity`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      setDirty(false);
      await load();
    } catch (e) {
      console.error('Save failed', e);
    }
    setSaving(false);
  };

  const categories = form.dataroom_categories || [];

  return (
    <div style={{ maxWidth: 480 }}>
      <h2 className="ec-font-label" style={headerStyle}>IDENTITY</h2>

      <Field label="DISPLAY NAME">
        <input
          value={form.entity_name || ''}
          onChange={(e) => handleChange('entity_name', e.target.value)}
          style={inputStyle}
        />
      </Field>

      <Field label="ENTITY ID">
        <input
          value={form.entity_id || ''}
          onChange={(e) => handleChange('entity_id', e.target.value)}
          style={inputStyle}
        />
      </Field>

      <Field label="LUNA TIER">
        <select
          value={form.luna_tier || 'guest'}
          onChange={(e) => handleChange('luna_tier', e.target.value)}
          style={inputStyle}
        >
          <option value="admin">admin</option>
          <option value="trusted">trusted</option>
          <option value="guest">guest</option>
        </select>
      </Field>

      <Field label="DATAROOM TIER">
        <select
          value={form.dataroom_tier ?? 1}
          onChange={(e) => handleChange('dataroom_tier', Number(e.target.value))}
          style={inputStyle}
        >
          <option value={1}>1 — Full access</option>
          <option value={2}>2 — Standard</option>
          <option value={3}>3 — Limited</option>
        </select>
      </Field>

      <Field label="DATAROOM CATEGORIES">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          {Object.entries(CATEGORY_LABELS).map(([id, label]) => {
            const catId = Number(id);
            const checked = categories.includes(catId);
            return (
              <label key={id} style={{
                display: 'flex', alignItems: 'center', gap: 8,
                color: 'var(--ec-text-soft)', fontSize: 11, cursor: 'pointer',
              }}>
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={() => toggleCategory(catId)}
                />
                <span className="ec-font-mono" style={{ fontSize: 10 }}>
                  {id}. {label}
                </span>
              </label>
            );
          })}
        </div>
      </Field>

      <button onClick={handleSave} disabled={!dirty || saving} style={saveBtnStyle(dirty)}>
        {saving ? 'SAVING...' : 'SAVE'}
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
  background: dirty ? 'rgba(52,211,153,0.1)' : 'transparent',
  border: `1px solid ${dirty ? 'rgba(52,211,153,0.3)' : 'var(--ec-border)'}`,
  borderRadius: 4, padding: '8px 24px',
  color: dirty ? '#34d399' : 'var(--ec-text-faint)',
  fontSize: 10, letterSpacing: 1.5, cursor: dirty ? 'pointer' : 'default',
});
