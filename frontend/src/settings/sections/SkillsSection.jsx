import React, { useState, useEffect, useCallback } from 'react';

const API = '';
const SKILL_NAMES = ['math', 'logic', 'formatting', 'reading', 'diagnostic', 'eden', 'analytics', 'options'];
const SENSITIVITIES = ['strict', 'loose', 'aggressive'];
const DETECTION_MODES = ['regex', 'fuzzy', 'llm-assisted'];
const TRIGGER_HINTS = {
  math:       'crunch numbers\ndo the math\ncalculate this\nwhat percent\nconvert units\nsolve for x\nwork out the ratio',
  logic:      'is this valid\ncheck my reasoning\nlogical fallacy\ndoes this follow\nprove this statement\nfind the contradiction\nevaluate the argument',
  formatting: 'make a table\norganize this\nclean up this list\nsort these items\nput this in columns\nnumber these steps\noutline this for me',
  reading:    'open this file\nwhat does this say\nparse the document\npull out the key points\nskim this pdf\ncheck this spreadsheet\ndig through this doc',
  diagnostic: 'run a check\nhow is everything\nsystem report\nany errors\ncheck the uptime\nis anything broken\ncheck the logs',
  eden:       'paint something\nmake me a picture\nvisualize this\nsketch a concept\nrender a scene\ndesign a logo\nillustrate this idea',
  analytics:  'show me the numbers\nbreak down the data\nrun the stats\nhow many total\nsummarize the metrics\ncount the sessions\ntrack the trend',
  options:    'which one should I\npick between\nchoose from\nwhat are my options\nhelp me decide\nnarrow it down\nwhich direction',
};

export default function SkillsSection() {
  const [data, setData] = useState(null);
  const [globalEnabled, setGlobalEnabled] = useState(true);
  const [detection, setDetection] = useState({
    mode: 'regex', slash_commands: true,
    llm_enabled: false, llm_model: 'local',
    llm_confidence: 0.7, llm_timeout: 500,
  });
  const [skillForms, setSkillForms] = useState({});
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/settings/skills`);
      const json = await res.json();
      setData(json);
      setGlobalEnabled(json.enabled !== false);

      const det = json.detection || {};
      const llm = det.llm || {};
      setDetection({
        mode: det.mode || 'regex',
        slash_commands: det.slash_commands !== false,
        llm_enabled: llm.enabled || false,
        llm_model: llm.model || 'local',
        llm_confidence: llm.confidence_threshold ?? 0.7,
        llm_timeout: llm.timeout_ms ?? 500,
      });

      const forms = {};
      for (const name of SKILL_NAMES) {
        const s = json[name] || {};
        forms[name] = {
          enabled: s.enabled !== false,
          sensitivity: s.sensitivity || 'strict',
          slash_command: s.slash_command || '',
          extra_triggers_text: (s.extra_triggers || []).join('\n'),
        };
      }
      setSkillForms(forms);
    } catch (e) {
      console.error('Failed to load skills settings', e);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (!data) return <div style={{ color: 'var(--ec-text-faint)' }}>Loading…</div>;

  const markDirty = () => setDirty(true);

  const updateDetection = (key, value) => {
    setDetection((p) => ({ ...p, [key]: value }));
    markDirty();
  };

  const updateSkill = (name, key, value) => {
    setSkillForms((p) => ({
      ...p,
      [name]: { ...p[name], [key]: value },
    }));
    markDirty();
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const skill_configs = {};
      for (const name of SKILL_NAMES) {
        const f = skillForms[name];
        skill_configs[name] = {
          enabled: f.enabled,
          sensitivity: f.sensitivity,
          slash_command: f.slash_command,
          extra_triggers: f.extra_triggers_text
            .split('\n')
            .map((t) => t.trim())
            .filter(Boolean),
        };
      }
      await fetch(`${API}/api/settings/skills`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          enabled: globalEnabled,
          detection: {
            mode: detection.mode,
            slash_commands: detection.slash_commands,
            llm: {
              enabled: detection.llm_enabled,
              model: detection.llm_model,
              confidence_threshold: detection.llm_confidence,
              timeout_ms: detection.llm_timeout,
            },
          },
          skill_configs,
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
    <div style={{ maxWidth: 540 }}>
      <h2 className="ec-font-label" style={headerStyle}>SKILLS</h2>

      <Field label="SKILLS ENABLED">
        <label style={checkboxLabelStyle}>
          <input
            type="checkbox"
            checked={globalEnabled}
            onChange={(e) => { setGlobalEnabled(e.target.checked); markDirty(); }}
          />
          Enable deterministic skill dispatch
        </label>
      </Field>

      <h3 className="ec-font-label" style={subheaderStyle}>DETECTION</h3>

      <Field label="MODE">
        <select
          value={detection.mode}
          onChange={(e) => updateDetection('mode', e.target.value)}
          style={inputStyle}
        >
          {DETECTION_MODES.map((m) => (
            <option key={m} value={m}>{m.charAt(0).toUpperCase() + m.slice(1)}</option>
          ))}
        </select>
      </Field>

      <Field label="SLASH COMMANDS">
        <label style={checkboxLabelStyle}>
          <input
            type="checkbox"
            checked={detection.slash_commands}
            onChange={(e) => updateDetection('slash_commands', e.target.checked)}
          />
          Enable skill slash commands globally
        </label>
      </Field>

      {detection.mode === 'llm-assisted' && (
        <>
          <h3 className="ec-font-label" style={subheaderStyle}>LLM CLASSIFICATION</h3>

          <Field label="LLM ENABLED">
            <label style={checkboxLabelStyle}>
              <input
                type="checkbox"
                checked={detection.llm_enabled}
                onChange={(e) => updateDetection('llm_enabled', e.target.checked)}
              />
              Use LLM as fallback classifier
            </label>
          </Field>

          <Field label="MODEL">
            <select
              value={detection.llm_model}
              onChange={(e) => updateDetection('llm_model', e.target.value)}
              style={inputStyle}
            >
              <option value="local">Local (Qwen)</option>
              <option value="cloud">Cloud</option>
            </select>
          </Field>

          <Field label="CONFIDENCE THRESHOLD">
            <input
              type="number"
              min="0" max="1" step="0.05"
              value={detection.llm_confidence}
              onChange={(e) => updateDetection('llm_confidence', parseFloat(e.target.value) || 0.7)}
              style={inputStyle}
            />
          </Field>

          <Field label="TIMEOUT (MS)">
            <input
              type="number"
              min="100" max="5000" step="50"
              value={detection.llm_timeout}
              onChange={(e) => updateDetection('llm_timeout', parseInt(e.target.value) || 500)}
              style={inputStyle}
            />
          </Field>
        </>
      )}

      <h3 className="ec-font-label" style={subheaderStyle}>PER-SKILL CONFIGURATION</h3>

      {SKILL_NAMES.map((name) => {
        const f = skillForms[name];
        if (!f) return null;
        return (
          <div key={name} style={cardStyle}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
              <span className="ec-font-label" style={{ fontSize: 10, letterSpacing: 2, color: 'var(--ec-text-soft)' }}>
                {name.toUpperCase()}
              </span>
              <label style={{ ...checkboxLabelStyle, marginBottom: 0 }}>
                <input
                  type="checkbox"
                  checked={f.enabled}
                  onChange={(e) => updateSkill(name, 'enabled', e.target.checked)}
                />
                Enabled
              </label>
            </div>

            <Field label="SLASH COMMAND">
              <input
                type="text"
                value={f.slash_command}
                onChange={(e) => updateSkill(name, 'slash_command', e.target.value)}
                placeholder={`/${name}`}
                style={inputStyle}
              />
            </Field>

            <Field label="SENSITIVITY">
              <select
                value={f.sensitivity}
                onChange={(e) => updateSkill(name, 'sensitivity', e.target.value)}
                style={inputStyle}
              >
                {SENSITIVITIES.map((s) => (
                  <option key={s} value={s}>{s.charAt(0).toUpperCase() + s.slice(1)}</option>
                ))}
              </select>
            </Field>

            <Field label="EXTRA TRIGGERS (one per line)">
              <textarea
                value={f.extra_triggers_text}
                onChange={(e) => updateSkill(name, 'extra_triggers_text', e.target.value)}
                placeholder={TRIGGER_HINTS[name] || "one trigger per line"}
                rows={3}
                style={{ ...inputStyle, resize: 'vertical', minHeight: 48 }}
              />
            </Field>
          </div>
        );
      })}

      <button onClick={handleSave} disabled={!dirty || saving} style={saveBtnStyle(dirty)}>
        {saving ? 'SAVING...' : 'SAVE SKILLS CONFIG'}
      </button>
    </div>
  );
}

function Field({ label, children }) {
  return (
    <div style={{ marginBottom: 12 }}>
      <label className="ec-font-label" style={labelStyle}>{label}</label>
      {children}
    </div>
  );
}

const headerStyle = { fontSize: 11, letterSpacing: 3, color: 'var(--ec-text-soft)', marginBottom: 24 };
const subheaderStyle = { fontSize: 9, letterSpacing: 2, color: 'var(--ec-text-faint)', marginBottom: 12, marginTop: 20 };
const labelStyle = { display: 'block', fontSize: 8, letterSpacing: 1.5, color: 'var(--ec-text-faint)', marginBottom: 4 };
const checkboxLabelStyle = { display: 'flex', alignItems: 'center', gap: 6, color: 'var(--ec-text-soft)', fontSize: 10, cursor: 'pointer', marginBottom: 4 };
const inputStyle = {
  background: 'var(--ec-bg-input, var(--ec-bg))',
  border: '1px solid var(--ec-border)',
  borderRadius: 4, padding: '6px 10px',
  color: 'var(--ec-text)', fontSize: 12,
  fontFamily: 'var(--ec-font-mono, "JetBrains Mono", monospace)',
  outline: 'none', width: '100%', boxSizing: 'border-box',
};
const cardStyle = {
  border: '1px solid var(--ec-border)',
  borderRadius: 6, padding: 14, marginBottom: 12,
  background: 'rgba(255,255,255,0.01)',
};
const saveBtnStyle = (dirty) => ({
  background: dirty ? 'rgba(52,211,153,0.1)' : 'transparent',
  border: `1px solid ${dirty ? 'rgba(52,211,153,0.3)' : 'var(--ec-border)'}`,
  borderRadius: 4, padding: '8px 24px',
  color: dirty ? '#34d399' : 'var(--ec-text-faint)',
  fontSize: 10, letterSpacing: 1.5, cursor: dirty ? 'pointer' : 'default',
  marginTop: 16,
});
