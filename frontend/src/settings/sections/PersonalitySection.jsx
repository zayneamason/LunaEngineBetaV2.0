import React, { useState, useEffect, useCallback } from 'react';

const API = '';

export default function PersonalitySection() {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({});
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/settings/personality`);
      const json = await res.json();
      setData(json);
      const p = json.personality || {};
      setForm({
        token_budget_preset: p.token_budget?.default_preset || 'balanced',
        reflection_enabled: p.reflection_loop?.enabled ?? true,
        reflection_n: p.reflection_loop?.trigger_points?.every_n_interactions ?? 15,
        // Emergent Prompt
        ep_enabled: p.emergent_prompt?.enabled ?? true,
        ep_max_patches: p.emergent_prompt?.max_patches_in_prompt ?? 10,
        ep_min_lock_in: p.emergent_prompt?.min_lock_in_for_inclusion ?? 0.3,
        // Mood Analysis
        mood_enabled: p.mood_analysis?.enabled ?? true,
        mood_recent_count: p.mood_analysis?.recent_messages_count ?? 5,
        mood_energy_high: p.mood_analysis?.energy_threshold_high ?? 200,
        mood_energy_low: p.mood_analysis?.energy_threshold_low ?? 50,
        // Lifecycle
        lc_decay: p.lifecycle?.decay_enabled ?? true,
        lc_consolidation: p.lifecycle?.consolidation_enabled ?? true,
        lc_interval: p.lifecycle?.maintenance_interval_hours ?? 24,
        // Patch Storage
        ps_initial_lock_in: p.personality_patch_storage?.settings?.initial_lock_in ?? 0.7,
        ps_consolidation_threshold: p.personality_patch_storage?.settings?.consolidation_threshold ?? 50,
        ps_max_active: p.personality_patch_storage?.settings?.max_active_patches ?? 100,
        ps_decay_days: p.personality_patch_storage?.settings?.decay_days_threshold ?? 30,
        ps_deactivation_threshold: p.personality_patch_storage?.settings?.lock_in_deactivation_threshold ?? 0.3,
        // Reflection Detail
        refl_session_end: p.reflection_loop?.trigger_points?.session_end ?? true,
        refl_user_requested: p.reflection_loop?.trigger_points?.user_requested ?? true,
        refl_min_confidence: p.reflection_loop?.min_confidence_for_patch ?? 0.6,
        // Bootstrap
        boot_enabled: p.bootstrap?.enabled ?? true,
        boot_protect_core: p.bootstrap?.protect_core_patches ?? true,
      });
    } catch (e) {
      console.error('Failed to load personality settings', e);
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
      await fetch(`${API}/api/settings/personality`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token_budget: { default_preset: form.token_budget_preset },
          reflection_loop: {
            enabled: form.reflection_enabled,
            trigger_points: {
              every_n_interactions: form.reflection_n,
              session_end: form.refl_session_end,
              user_requested: form.refl_user_requested,
            },
            min_confidence_for_patch: form.refl_min_confidence,
          },
          emergent_prompt: {
            enabled: form.ep_enabled,
            max_patches_in_prompt: form.ep_max_patches,
            min_lock_in_for_inclusion: form.ep_min_lock_in,
          },
          mood_analysis: {
            enabled: form.mood_enabled,
            recent_messages_count: form.mood_recent_count,
            energy_threshold_high: form.mood_energy_high,
            energy_threshold_low: form.mood_energy_low,
          },
          lifecycle: {
            decay_enabled: form.lc_decay,
            consolidation_enabled: form.lc_consolidation,
            maintenance_interval_hours: form.lc_interval,
          },
          personality_patch_storage: {
            settings: {
              initial_lock_in: form.ps_initial_lock_in,
              consolidation_threshold: form.ps_consolidation_threshold,
              max_active_patches: form.ps_max_active,
              decay_days_threshold: form.ps_decay_days,
              lock_in_deactivation_threshold: form.ps_deactivation_threshold,
            },
          },
          bootstrap: {
            enabled: form.boot_enabled,
            protect_core_patches: form.boot_protect_core,
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

  const personality = data.personality || {};
  const seeds = personality.bootstrap?.seed_patches || [];

  return (
    <div style={{ maxWidth: 480 }}>
      <h2 className="ec-font-label" style={headerStyle}>PERSONALITY</h2>

      <Field label="TOKEN BUDGET PRESET">
        <select
          value={form.token_budget_preset}
          onChange={(e) => handleChange('token_budget_preset', e.target.value)}
          style={inputStyle}
        >
          <option value="minimal">Minimal (1500 tokens)</option>
          <option value="balanced">Balanced (3000 tokens)</option>
          <option value="rich">Rich (5500 tokens)</option>
        </select>
      </Field>

      <Field label="REFLECTION LOOP">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--ec-text-soft)', fontSize: 11, cursor: 'pointer' }}>
            <input
              type="checkbox"
              checked={form.reflection_enabled}
              onChange={(e) => handleChange('reflection_enabled', e.target.checked)}
            />
            Enabled
          </label>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className="ec-font-label" style={{ fontSize: 8, color: 'var(--ec-text-faint)' }}>EVERY</span>
            <input
              type="number"
              min={1} max={100}
              value={form.reflection_n}
              onChange={(e) => handleChange('reflection_n', Number(e.target.value))}
              style={{ ...inputStyle, width: 60 }}
            />
            <span className="ec-font-label" style={{ fontSize: 8, color: 'var(--ec-text-faint)' }}>INTERACTIONS</span>
          </div>
        </div>
      </Field>

      {/* — Collapsible subsections — */}

      <Collapsible title="EMERGENT PROMPT">
        <Field label="ENABLED">
          <label style={checkboxLabelStyle}>
            <input type="checkbox" checked={form.ep_enabled} onChange={(e) => handleChange('ep_enabled', e.target.checked)} />
            Include personality patches in prompt
          </label>
        </Field>
        <Field label="MAX PATCHES IN PROMPT">
          <input type="number" min={1} max={50} step={1} value={form.ep_max_patches}
            onChange={(e) => handleChange('ep_max_patches', Number(e.target.value))}
            style={{ ...inputStyle, width: 120 }}
          />
        </Field>
        <Field label="MIN LOCK-IN FOR INCLUSION">
          <input type="number" min={0} max={1} step={0.05} value={form.ep_min_lock_in}
            onChange={(e) => handleChange('ep_min_lock_in', Number(e.target.value))}
            style={{ ...inputStyle, width: 120 }}
          />
        </Field>
      </Collapsible>

      <Collapsible title="MOOD ANALYSIS">
        <Field label="ENABLED">
          <label style={checkboxLabelStyle}>
            <input type="checkbox" checked={form.mood_enabled} onChange={(e) => handleChange('mood_enabled', e.target.checked)} />
            Analyze conversation mood
          </label>
        </Field>
        <Field label="RECENT MESSAGES COUNT">
          <input type="number" min={1} max={20} step={1} value={form.mood_recent_count}
            onChange={(e) => handleChange('mood_recent_count', Number(e.target.value))}
            style={{ ...inputStyle, width: 120 }}
          />
        </Field>
        <Field label="ENERGY THRESHOLD HIGH">
          <input type="number" min={50} max={500} step={10} value={form.mood_energy_high}
            onChange={(e) => handleChange('mood_energy_high', Number(e.target.value))}
            style={{ ...inputStyle, width: 120 }}
          />
        </Field>
        <Field label="ENERGY THRESHOLD LOW">
          <input type="number" min={0} max={200} step={5} value={form.mood_energy_low}
            onChange={(e) => handleChange('mood_energy_low', Number(e.target.value))}
            style={{ ...inputStyle, width: 120 }}
          />
        </Field>
      </Collapsible>

      <Collapsible title="LIFECYCLE">
        <Field label="DECAY">
          <label style={checkboxLabelStyle}>
            <input type="checkbox" checked={form.lc_decay} onChange={(e) => handleChange('lc_decay', e.target.checked)} />
            Enable patch decay over time
          </label>
        </Field>
        <Field label="CONSOLIDATION">
          <label style={checkboxLabelStyle}>
            <input type="checkbox" checked={form.lc_consolidation} onChange={(e) => handleChange('lc_consolidation', e.target.checked)} />
            Enable patch consolidation
          </label>
        </Field>
        <Field label="MAINTENANCE INTERVAL (HOURS)">
          <input type="number" min={1} max={168} step={1} value={form.lc_interval}
            onChange={(e) => handleChange('lc_interval', Number(e.target.value))}
            style={{ ...inputStyle, width: 120 }}
          />
        </Field>
      </Collapsible>

      <Collapsible title="PATCH STORAGE">
        <Field label="INITIAL LOCK-IN">
          <input type="number" min={0} max={1} step={0.05} value={form.ps_initial_lock_in}
            onChange={(e) => handleChange('ps_initial_lock_in', Number(e.target.value))}
            style={{ ...inputStyle, width: 120 }}
          />
        </Field>
        <Field label="CONSOLIDATION THRESHOLD">
          <input type="number" min={5} max={200} step={5} value={form.ps_consolidation_threshold}
            onChange={(e) => handleChange('ps_consolidation_threshold', Number(e.target.value))}
            style={{ ...inputStyle, width: 120 }}
          />
        </Field>
        <Field label="MAX ACTIVE PATCHES">
          <input type="number" min={10} max={500} step={10} value={form.ps_max_active}
            onChange={(e) => handleChange('ps_max_active', Number(e.target.value))}
            style={{ ...inputStyle, width: 120 }}
          />
        </Field>
        <Field label="DECAY DAYS THRESHOLD">
          <input type="number" min={1} max={365} step={1} value={form.ps_decay_days}
            onChange={(e) => handleChange('ps_decay_days', Number(e.target.value))}
            style={{ ...inputStyle, width: 120 }}
          />
        </Field>
        <Field label="DEACTIVATION THRESHOLD">
          <input type="number" min={0} max={1} step={0.05} value={form.ps_deactivation_threshold}
            onChange={(e) => handleChange('ps_deactivation_threshold', Number(e.target.value))}
            style={{ ...inputStyle, width: 120 }}
          />
        </Field>
      </Collapsible>

      <Collapsible title="REFLECTION DETAIL">
        <Field label="SESSION END TRIGGER">
          <label style={checkboxLabelStyle}>
            <input type="checkbox" checked={form.refl_session_end} onChange={(e) => handleChange('refl_session_end', e.target.checked)} />
            Reflect at session end
          </label>
        </Field>
        <Field label="USER REQUESTED TRIGGER">
          <label style={checkboxLabelStyle}>
            <input type="checkbox" checked={form.refl_user_requested} onChange={(e) => handleChange('refl_user_requested', e.target.checked)} />
            Allow user-requested reflection
          </label>
        </Field>
        <Field label="MIN CONFIDENCE FOR PATCH">
          <input type="number" min={0} max={1} step={0.05} value={form.refl_min_confidence}
            onChange={(e) => handleChange('refl_min_confidence', Number(e.target.value))}
            style={{ ...inputStyle, width: 120 }}
          />
        </Field>
      </Collapsible>

      <Collapsible title="BOOTSTRAP">
        <Field label="ENABLED">
          <label style={checkboxLabelStyle}>
            <input type="checkbox" checked={form.boot_enabled} onChange={(e) => handleChange('boot_enabled', e.target.checked)} />
            Enable bootstrap on fresh start
          </label>
        </Field>
        <Field label="PROTECT CORE PATCHES">
          <label style={checkboxLabelStyle}>
            <input type="checkbox" checked={form.boot_protect_core} onChange={(e) => handleChange('boot_protect_core', e.target.checked)} />
            Prevent decay of core patches
          </label>
        </Field>
      </Collapsible>

      {/* Bootstrap seeds (read-only) */}
      <div style={{ marginTop: 20 }}>
        <h3 className="ec-font-label" style={{ fontSize: 9, letterSpacing: 2, color: 'var(--ec-text-faint)', marginBottom: 8 }}>
          BOOTSTRAP SEEDS (READ-ONLY)
        </h3>
        {seeds.map((s) => (
          <div key={s.patch_id} className="ec-font-mono" style={{
            fontSize: 10, color: 'var(--ec-text-soft)', padding: '4px 0',
            borderBottom: '1px solid var(--ec-border)',
          }}>
            {s.subtopic}
            {s.core_value && <span style={{ color: '#fbbf24', marginLeft: 8, fontSize: 8 }}>CORE</span>}
          </div>
        ))}
      </div>

      <button onClick={handleSave} disabled={!dirty || saving} style={{ ...saveBtnStyle(dirty), marginTop: 20 }}>
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

function Collapsible({ title, children }) {
  return (
    <details style={{ marginTop: 16, marginBottom: 16 }}>
      <summary className="ec-font-label" style={{
        fontSize: 9, letterSpacing: 2, color: 'var(--ec-text-faint)',
        cursor: 'pointer', userSelect: 'none', marginBottom: 8,
      }}>
        {title}
      </summary>
      <div style={{ paddingLeft: 8, borderLeft: '1px solid var(--ec-border)' }}>
        {children}
      </div>
    </details>
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
const checkboxLabelStyle = {
  display: 'flex', alignItems: 'center', gap: 6,
  color: 'var(--ec-text-soft)', fontSize: 11, cursor: 'pointer',
};
const saveBtnStyle = (dirty) => ({
  background: dirty ? 'rgba(52,211,153,0.1)' : 'transparent',
  border: `1px solid ${dirty ? 'rgba(52,211,153,0.3)' : 'var(--ec-border)'}`,
  borderRadius: 4, padding: '8px 24px',
  color: dirty ? '#34d399' : 'var(--ec-text-faint)',
  fontSize: 10, letterSpacing: 1.5, cursor: dirty ? 'pointer' : 'default',
});
