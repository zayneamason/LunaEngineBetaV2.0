import React, { useState, useEffect, useCallback } from 'react';

const API = '';

function StatusDot({ status }) {
  const color = status === 'set' ? '#34d399' : 'var(--ec-text-muted)';
  return (
    <span style={{
      display: 'inline-block',
      width: 6, height: 6,
      borderRadius: '50%',
      background: color,
      boxShadow: status === 'set' ? `0 0 6px ${color}` : 'none',
    }} />
  );
}

export default function LLMSection({ keysUnlocked = false }) {
  const [data, setData] = useState(null);
  const [keys, setKeys] = useState({});       // env_var -> value typed by user
  const [showKeys, setShowKeys] = useState({}); // env_var -> bool
  const [testing, setTesting] = useState({});  // provider -> 'testing'|'pass'|'fail'
  const [testMsg, setTestMsg] = useState({});
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [chainOrder, setChainOrder] = useState([]);
  const [fallbackTimeout, setFallbackTimeout] = useState(30000);
  const [fallbackRetries, setFallbackRetries] = useState(1);
  const [dragIdx, setDragIdx] = useState(null);
  const [localForm, setLocalForm] = useState({});
  const [localDirty, setLocalDirty] = useState(false);
  const [localSaving, setLocalSaving] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/settings/llm`);
      const json = await res.json();
      setData(json);
      setChainOrder(json.fallback?.chain || []);
      setFallbackTimeout(json.fallback?.per_provider_timeout_ms ?? 30000);
      setFallbackRetries(json.fallback?.max_retries_per_provider ?? 1);

      // Load local inference config
      const localRes = await fetch(`${API}/api/settings/local-inference`);
      const lj = await localRes.json();
      setLocalForm({
        model_id: lj.model?.model_id ?? 'Qwen/Qwen2.5-3B-Instruct',
        use_4bit: lj.model?.use_4bit ?? true,
        cache_prompt: lj.model?.cache_prompt ?? true,
        adapter_path: lj.model?.adapter_path ?? '',
        max_tokens: lj.generation?.max_tokens ?? 512,
        temperature: lj.generation?.temperature ?? 0.7,
        top_p: lj.generation?.top_p ?? 0.9,
        repetition_penalty: lj.generation?.repetition_penalty ?? 1.1,
        hot_path_timeout_ms: lj.performance?.hot_path_timeout_ms ?? 200,
        complexity_threshold: lj.routing?.complexity_threshold ?? 0.35,
      });
      setLocalDirty(false);
    } catch (e) {
      console.error('Failed to load LLM settings', e);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (!data) {
    return <div style={{ color: 'var(--ec-text-faint)' }}>Loading…</div>;
  }

  const { providers: providerConfig } = data;
  const providerList = Object.entries(providerConfig.providers || {});
  const currentProvider = providerConfig.current_provider;

  const handleSave = async () => {
    setSaving(true);
    try {
      const body = {};
      if (Object.keys(keys).length > 0) body.api_keys = keys;
      body.fallback_chain = chainOrder;
      body.fallback_timeout_ms = fallbackTimeout;
      body.fallback_max_retries = fallbackRetries;

      await fetch(`${API}/api/settings/llm`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      setKeys({});
      setDirty(false);
      await load();
    } catch (e) {
      console.error('Save failed', e);
    }
    setSaving(false);
  };

  const handleSetProvider = async (pid) => {
    await fetch(`${API}/api/settings/llm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_provider: pid }),
    });
    await load();
  };

  const handleTest = async (pid) => {
    setTesting((p) => ({ ...p, [pid]: 'testing' }));
    setTestMsg((p) => ({ ...p, [pid]: '' }));
    try {
      const res = await fetch(`${API}/api/settings/llm/test`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider: pid }),
      });
      const json = await res.json();
      setTesting((p) => ({ ...p, [pid]: json.success ? 'pass' : 'fail' }));
      setTestMsg((p) => ({ ...p, [pid]: json.message || json.error || '' }));
    } catch (e) {
      setTesting((p) => ({ ...p, [pid]: 'fail' }));
      setTestMsg((p) => ({ ...p, [pid]: String(e) }));
    }
  };

  const handleToggle = async (pid, enabled) => {
    await fetch(`${API}/api/settings/llm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ provider_toggles: { [pid]: enabled } }),
    });
    await load();
  };

  const handleModelChange = async (pid, model) => {
    await fetch(`${API}/api/settings/llm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ default_models: { [pid]: model } }),
    });
    await load();
  };

  // Drag-and-drop for fallback chain
  const handleDragStart = (idx) => setDragIdx(idx);
  const handleDragOver = (e, idx) => {
    e.preventDefault();
    if (dragIdx === null || dragIdx === idx) return;
    const newOrder = [...chainOrder];
    const [moved] = newOrder.splice(dragIdx, 1);
    newOrder.splice(idx, 0, moved);
    setChainOrder(newOrder);
    setDragIdx(idx);
    setDirty(true);
  };
  const handleDragEnd = () => setDragIdx(null);

  const handleLocalChange = (key, value) => {
    setLocalForm((p) => ({ ...p, [key]: value }));
    setLocalDirty(true);
  };

  const handleSaveLocal = async () => {
    setLocalSaving(true);
    try {
      await fetch(`${API}/api/settings/local-inference`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model: {
            model_id: localForm.model_id,
            use_4bit: localForm.use_4bit,
            cache_prompt: localForm.cache_prompt,
            adapter_path: localForm.adapter_path,
          },
          generation: {
            max_tokens: localForm.max_tokens,
            temperature: localForm.temperature,
            top_p: localForm.top_p,
            repetition_penalty: localForm.repetition_penalty,
          },
          performance: { hot_path_timeout_ms: localForm.hot_path_timeout_ms },
          routing: { complexity_threshold: localForm.complexity_threshold },
        }),
      });
      setLocalDirty(false);
      await load();
    } catch (e) {
      console.error('Save local config failed', e);
    }
    setLocalSaving(false);
  };

  return (
    <div style={{ maxWidth: 680 }}>
      <h2 className="ec-font-label" style={{
        fontSize: 11, letterSpacing: 3, color: 'var(--ec-text-soft)', marginBottom: 24,
      }}>
        LLM PROVIDERS
      </h2>

      {/* Provider cards */}
      {providerList.map(([pid, pconf]) => {
        const isActive = pid === currentProvider;
        const envVar = pconf.api_key_env;
        const testState = testing[pid];

        return (
          <div key={pid} className="ec-glass-card" style={{
            padding: 16,
            marginBottom: 12,
            border: isActive ? '1px solid rgba(52,211,153,0.3)' : '1px solid var(--ec-border)',
            borderRadius: 8,
            background: 'var(--ec-bg-panel)',
          }}>
            {/* Header row */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <StatusDot status={pconf.key_status} />
                <span className="ec-font-label" style={{ fontSize: 10, letterSpacing: 2, color: 'var(--ec-text)' }}>
                  {pid.toUpperCase()}
                </span>
                {isActive && (
                  <span style={{
                    fontSize: 8, letterSpacing: 1.5,
                    padding: '2px 6px', borderRadius: 3,
                    background: 'rgba(52,211,153,0.12)', color: '#34d399',
                  }}>ACTIVE</span>
                )}
              </div>
              <div style={{ display: 'flex', gap: 6 }}>
                {!isActive && (
                  <button onClick={() => handleSetProvider(pid)} style={btnStyle}>
                    SET ACTIVE
                  </button>
                )}
                <button onClick={() => handleToggle(pid, !pconf.enabled)} style={{
                  ...btnStyle,
                  color: pconf.enabled ? '#34d399' : 'var(--ec-text-faint)',
                  borderColor: pconf.enabled ? 'rgba(52,211,153,0.3)' : 'var(--ec-border)',
                }}>
                  {pconf.enabled ? 'ENABLED' : 'DISABLED'}
                </button>
              </div>
            </div>

            {/* Model select */}
            <div style={{ marginBottom: 10 }}>
              <label className="ec-font-label" style={labelStyle}>DEFAULT MODEL</label>
              <select
                value={pconf.default_model}
                onChange={(e) => handleModelChange(pid, e.target.value)}
                style={inputStyle}
              >
                {(pconf.models || []).map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>

            {/* API Key */}
            <div style={{ marginBottom: 10 }}>
              <label className="ec-font-label" style={labelStyle}>API KEY ({envVar})</label>
              <div style={{ display: 'flex', gap: 6 }}>
                <input
                  type={showKeys[envVar] ? 'text' : 'password'}
                  placeholder={pconf.key_masked || 'Not set'}
                  value={keys[envVar] || ''}
                  onChange={(e) => {
                    setKeys((p) => ({ ...p, [envVar]: e.target.value }));
                    setDirty(true);
                  }}
                  style={{ ...inputStyle, flex: 1 }}
                />
                {pconf.key_masked && !keysUnlocked ? (
                  <span style={{ ...btnStyle, opacity: 0.5, cursor: 'default' }}>CONFIGURED</span>
                ) : (
                  <button
                    onClick={() => setShowKeys((p) => ({ ...p, [envVar]: !p[envVar] }))}
                    style={btnStyle}
                  >
                    {showKeys[envVar] ? 'HIDE' : 'SHOW'}
                  </button>
                )}
                <button
                  onClick={() => handleTest(pid)}
                  disabled={testState === 'testing'}
                  style={{
                    ...btnStyle,
                    color: testState === 'pass' ? '#34d399' : testState === 'fail' ? '#f87171' : 'var(--ec-text-soft)',
                    borderColor: testState === 'pass' ? 'rgba(52,211,153,0.3)' : testState === 'fail' ? 'rgba(248,113,113,0.3)' : 'var(--ec-border)',
                  }}
                >
                  {testState === 'testing' ? '...' : 'TEST'}
                </button>
              </div>
              {testMsg[pid] && (
                <div className="ec-font-mono" style={{
                  fontSize: 9, marginTop: 4,
                  color: testState === 'pass' ? '#34d399' : '#f87171',
                }}>
                  {testMsg[pid]}
                </div>
              )}
            </div>
          </div>
        );
      })}

      {/* Fallback chain */}
      <div style={{ marginTop: 24, marginBottom: 16 }}>
        <h3 className="ec-font-label" style={{ fontSize: 10, letterSpacing: 2, color: 'var(--ec-text-soft)', marginBottom: 10 }}>
          FALLBACK CHAIN
        </h3>
        <div className="ec-font-mono" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 8 }}>
          Drag to reorder. First available provider wins.
        </div>
        {chainOrder.map((pid, idx) => (
          <div
            key={pid}
            draggable
            onDragStart={() => handleDragStart(idx)}
            onDragOver={(e) => handleDragOver(e, idx)}
            onDragEnd={handleDragEnd}
            style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '8px 12px', marginBottom: 4,
              background: dragIdx === idx ? 'rgba(255,255,255,0.04)' : 'var(--ec-bg-panel)',
              border: '1px solid var(--ec-border)',
              borderRadius: 4,
              cursor: 'grab',
              color: 'var(--ec-text)',
              fontSize: 11,
            }}
          >
            <span style={{ color: 'var(--ec-text-faint)', fontSize: 9, width: 16 }}>{idx + 1}.</span>
            <span className="ec-font-mono">{pid}</span>
          </div>
        ))}

        {/* Fallback settings */}
        <div style={{ display: 'flex', gap: 16, marginTop: 12 }}>
          <div style={{ flex: 1 }}>
            <label className="ec-font-label" style={labelStyle}>TIMEOUT (ms)</label>
            <input
              type="number"
              min={1000} max={120000} step={1000}
              value={fallbackTimeout}
              onChange={(e) => { setFallbackTimeout(Number(e.target.value)); setDirty(true); }}
              style={inputStyle}
            />
          </div>
          <div style={{ flex: 1 }}>
            <label className="ec-font-label" style={labelStyle}>MAX RETRIES</label>
            <input
              type="number"
              min={0} max={5}
              value={fallbackRetries}
              onChange={(e) => { setFallbackRetries(Number(e.target.value)); setDirty(true); }}
              style={inputStyle}
            />
          </div>
        </div>
      </div>

      {/* Save cloud providers */}
      <button
        onClick={handleSave}
        disabled={!dirty || saving}
        style={{
          ...btnStyle,
          padding: '8px 24px',
          fontSize: 10,
          background: dirty ? 'rgba(52,211,153,0.1)' : 'transparent',
          color: dirty ? '#34d399' : 'var(--ec-text-faint)',
          borderColor: dirty ? 'rgba(52,211,153,0.3)' : 'var(--ec-border)',
          cursor: dirty ? 'pointer' : 'default',
        }}
      >
        {saving ? 'SAVING...' : 'SAVE CHANGES'}
      </button>

      {/* ── LOCAL MODEL ─────────────────────────────────────────── */}
      <div style={{ marginTop: 32, borderTop: '1px solid var(--ec-border)', paddingTop: 20 }}>
        <h3 className="ec-font-label" style={{ fontSize: 10, letterSpacing: 2, color: 'var(--ec-text-soft)', marginBottom: 6 }}>
          LOCAL MODEL (MLX)
        </h3>

        {localDirty && (
          <div style={{
            padding: '6px 10px', marginBottom: 12,
            background: 'rgba(251,191,36,0.08)',
            border: '1px solid rgba(251,191,36,0.3)',
            borderRadius: 6, fontSize: 9, color: '#fbbf24',
          }}>
            Changes require restart to take effect.
          </div>
        )}

        {/* Model */}
        <div style={{ marginBottom: 10 }}>
          <label className="ec-font-label" style={labelStyle}>MODEL ID</label>
          <input
            type="text"
            value={localForm.model_id || ''}
            onChange={(e) => handleLocalChange('model_id', e.target.value)}
            style={inputStyle}
          />
        </div>

        <div style={{ display: 'flex', gap: 16, marginBottom: 10 }}>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--ec-text-soft)', fontSize: 10, cursor: 'pointer' }}>
            <input type="checkbox" checked={localForm.use_4bit ?? true}
              onChange={(e) => handleLocalChange('use_4bit', e.target.checked)} />
            4-BIT QUANTIZE
          </label>
          <label style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--ec-text-soft)', fontSize: 10, cursor: 'pointer' }}>
            <input type="checkbox" checked={localForm.cache_prompt ?? true}
              onChange={(e) => handleLocalChange('cache_prompt', e.target.checked)} />
            PROMPT CACHING
          </label>
        </div>

        <div style={{ marginBottom: 14 }}>
          <label className="ec-font-label" style={labelStyle}>LORA ADAPTER PATH</label>
          <input
            type="text"
            value={localForm.adapter_path || ''}
            onChange={(e) => handleLocalChange('adapter_path', e.target.value)}
            style={inputStyle}
            placeholder="models/luna_lora_mlx"
          />
        </div>

        {/* Generation */}
        <h4 className="ec-font-label" style={{ fontSize: 9, letterSpacing: 2, color: 'var(--ec-text-faint)', marginBottom: 8, marginTop: 16 }}>
          GENERATION
        </h4>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
          <div style={{ flex: 1, minWidth: 100 }}>
            <label className="ec-font-label" style={labelStyle}>MAX TOKENS</label>
            <input type="number" min={1} max={4096} step={64}
              value={localForm.max_tokens ?? 512}
              onChange={(e) => handleLocalChange('max_tokens', Number(e.target.value))}
              style={inputStyle} />
          </div>
          <div style={{ flex: 1, minWidth: 100 }}>
            <label className="ec-font-label" style={labelStyle}>TEMPERATURE</label>
            <input type="number" min={0} max={2} step={0.05}
              value={localForm.temperature ?? 0.7}
              onChange={(e) => handleLocalChange('temperature', Number(e.target.value))}
              style={inputStyle} />
          </div>
          <div style={{ flex: 1, minWidth: 100 }}>
            <label className="ec-font-label" style={labelStyle}>TOP-P</label>
            <input type="number" min={0} max={1} step={0.05}
              value={localForm.top_p ?? 0.9}
              onChange={(e) => handleLocalChange('top_p', Number(e.target.value))}
              style={inputStyle} />
          </div>
          <div style={{ flex: 1, minWidth: 100 }}>
            <label className="ec-font-label" style={labelStyle}>REP. PENALTY</label>
            <input type="number" min={1} max={2} step={0.05}
              value={localForm.repetition_penalty ?? 1.1}
              onChange={(e) => handleLocalChange('repetition_penalty', Number(e.target.value))}
              style={inputStyle} />
          </div>
        </div>

        {/* Performance & Routing */}
        <h4 className="ec-font-label" style={{ fontSize: 9, letterSpacing: 2, color: 'var(--ec-text-faint)', marginBottom: 8, marginTop: 16 }}>
          PERFORMANCE & ROUTING
        </h4>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
          <div style={{ flex: 1, minWidth: 140 }}>
            <label className="ec-font-label" style={labelStyle}>HOT PATH TIMEOUT (ms)</label>
            <input type="number" min={50} max={5000} step={50}
              value={localForm.hot_path_timeout_ms ?? 200}
              onChange={(e) => handleLocalChange('hot_path_timeout_ms', Number(e.target.value))}
              style={inputStyle} />
          </div>
          <div style={{ flex: 1, minWidth: 140 }}>
            <label className="ec-font-label" style={labelStyle}>COMPLEXITY THRESHOLD</label>
            <input type="number" min={0} max={1} step={0.05}
              value={localForm.complexity_threshold ?? 0.35}
              onChange={(e) => handleLocalChange('complexity_threshold', Number(e.target.value))}
              style={inputStyle} />
            <div className="ec-font-mono" style={{ fontSize: 8, color: 'var(--ec-text-faint)', marginTop: 2 }}>
              Higher = more delegated to Claude
            </div>
          </div>
        </div>

        {/* Save local */}
        <button
          onClick={handleSaveLocal}
          disabled={!localDirty || localSaving}
          style={{
            ...btnStyle,
            padding: '8px 24px',
            fontSize: 10,
            background: localDirty ? 'rgba(251,191,36,0.1)' : 'transparent',
            color: localDirty ? '#fbbf24' : 'var(--ec-text-faint)',
            borderColor: localDirty ? 'rgba(251,191,36,0.3)' : 'var(--ec-border)',
            cursor: localDirty ? 'pointer' : 'default',
          }}
        >
          {localSaving ? 'SAVING...' : 'SAVE LOCAL CONFIG'}
        </button>
      </div>
    </div>
  );
}

const labelStyle = {
  display: 'block',
  fontSize: 8,
  letterSpacing: 1.5,
  color: 'var(--ec-text-faint)',
  marginBottom: 4,
};

const inputStyle = {
  background: 'var(--ec-bg-input, var(--ec-bg))',
  border: '1px solid var(--ec-border)',
  borderRadius: 4,
  padding: '6px 10px',
  color: 'var(--ec-text)',
  fontSize: 12,
  fontFamily: 'var(--ec-font-mono, "JetBrains Mono", monospace)',
  outline: 'none',
  width: '100%',
  boxSizing: 'border-box',
};

const btnStyle = {
  background: 'transparent',
  border: '1px solid var(--ec-border)',
  borderRadius: 4,
  padding: '4px 10px',
  color: 'var(--ec-text-soft)',
  fontSize: 8,
  letterSpacing: 1.5,
  fontFamily: 'inherit',
  cursor: 'pointer',
};
