import React, { useState, useEffect, useCallback } from 'react';

const API = '';

export default function VoiceSection() {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/settings/voice`);
      const json = await res.json();
      setData(json);
      setForm(json.expression || {});
    } catch (e) {
      console.error('Failed to load voice settings', e);
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
      await fetch(`${API}/api/settings/voice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ expression: form }),
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
      <h2 className="ec-font-label" style={headerStyle}>VOICE & EXPRESSION</h2>

      <Field label="GESTURE FREQUENCY">
        <select
          value={form.gesture_frequency || 'moderate'}
          onChange={(e) => handleChange('gesture_frequency', e.target.value)}
          style={inputStyle}
        >
          <option value="minimal">Minimal — strong moments only</option>
          <option value="moderate">Moderate — natural emotional beats</option>
          <option value="expressive">Expressive — frequent gestural communication</option>
        </select>
      </Field>

      <Field label="GESTURE DISPLAY MODE">
        <select
          value={form.gesture_display_mode || 'stripped'}
          onChange={(e) => handleChange('gesture_display_mode', e.target.value)}
          style={inputStyle}
        >
          <option value="visible">Visible — shown in text + animations</option>
          <option value="stripped">Stripped — animations only, removed from text</option>
          <option value="debug">Debug — annotated with [ORB:state]</option>
        </select>
      </Field>

      <Field label="GESTURE CONTEXTS">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {['greeting', 'farewell', 'thinking', 'agreement', 'disagreement', 'emphasis', 'question'].map((ctx) => (
            <label key={ctx} style={{ display: 'flex', alignItems: 'center', gap: 4, color: 'var(--ec-text-soft)', fontSize: 10, cursor: 'pointer' }}>
              <input
                type="checkbox"
                checked={(form.gesture_contexts || []).includes(ctx)}
                onChange={(e) => {
                  const current = form.gesture_contexts || [];
                  const next = e.target.checked
                    ? [...current, ctx]
                    : current.filter((c) => c !== ctx);
                  handleChange('gesture_contexts', next);
                }}
              />
              {ctx}
            </label>
          ))}
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
