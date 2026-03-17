import React, { useState, useEffect, useCallback } from 'react';

const API = '';

export default function MemorySection() {
  const [data, setData] = useState(null);
  const [weights, setWeights] = useState({ node: 0.4, access: 0.3, edge: 0.2, age: 0.1 });
  const [decay, setDecay] = useState({});
  const [thresholds, setThresholds] = useState({});
  const [advanced, setAdvanced] = useState({});
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const res = await fetch(`${API}/api/settings/memory`);
      const json = await res.json();
      setData(json);
      if (json.weights) setWeights(json.weights);
      if (json.decay) setDecay(json.decay);
      if (json.thresholds) setThresholds(json.thresholds);
      setAdvanced({
        constellation_max_tokens: json.constellation?.max_tokens ?? 3000,
        constellation_cluster_budget_pct: json.constellation?.cluster_budget_pct ?? 0.6,
        clustering_min_size: json.clustering?.min_cluster_size ?? 3,
        clustering_max_size: json.clustering?.max_cluster_size ?? 50,
        clustering_min_overlap: json.clustering?.min_keyword_overlap ?? 0.4,
        clustering_max_generic: json.clustering?.max_generic_frequency ?? 100,
        clustering_merge_threshold: json.clustering?.merge_similarity_threshold ?? 0.6,
        retrieval_max_clusters: json.retrieval?.max_clusters_per_query ?? 5,
        retrieval_expand_top: json.retrieval?.expand_top_clusters ?? 2,
        retrieval_multi_hop: json.retrieval?.include_multi_hop ?? true,
        retrieval_min_edge: json.retrieval?.min_edge_lock_in_for_hop ?? 0.7,
        svc_clustering_hours: json.services?.clustering_interval_hours ?? 1,
        svc_lockin_minutes: json.services?.lockin_update_interval_minutes ?? 5,
        svc_cleanup_hours: json.services?.cleanup_interval_hours ?? 24,
        use_clusters: json.use_clusters ?? true,
        use_louvain: json.use_louvain ?? false,
      });
    } catch (e) {
      console.error('Failed to load memory settings', e);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (!data) return <div style={{ color: 'var(--ec-text-faint)' }}>Loading…</div>;

  const total = Object.values(weights).reduce((a, b) => a + b, 0);
  const isValid = Math.abs(total - 1.0) < 0.01;

  const handleWeight = (key, value) => {
    const v = Math.max(0, Math.min(1, parseFloat(value) || 0));
    setWeights((p) => ({ ...p, [key]: v }));
    setDirty(true);
    setError('');
  };

  const handleDecay = (key, value) => {
    const v = parseFloat(value);
    if (!isNaN(v) && v >= 0) {
      setDecay((p) => ({ ...p, [key]: v }));
      setDirty(true);
    }
  };

  const handleThreshold = (key, value) => {
    const v = parseFloat(value);
    if (!isNaN(v) && v >= 0 && v <= 1) {
      setThresholds((p) => ({ ...p, [key]: v }));
      setDirty(true);
    }
  };

  const handleAdvanced = (key, value) => {
    setAdvanced((p) => ({ ...p, [key]: value }));
    setDirty(true);
  };

  const handleSave = async () => {
    if (!isValid) {
      setError(`Weights must sum to 1.0 (currently ${total.toFixed(3)})`);
      return;
    }
    setSaving(true);
    try {
      await fetch(`${API}/api/settings/memory`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          weights, decay, thresholds,
          constellation: {
            max_tokens: advanced.constellation_max_tokens,
            cluster_budget_pct: advanced.constellation_cluster_budget_pct,
          },
          clustering: {
            min_cluster_size: advanced.clustering_min_size,
            max_cluster_size: advanced.clustering_max_size,
            min_keyword_overlap: advanced.clustering_min_overlap,
            max_generic_frequency: advanced.clustering_max_generic,
            merge_similarity_threshold: advanced.clustering_merge_threshold,
          },
          retrieval: {
            max_clusters_per_query: advanced.retrieval_max_clusters,
            expand_top_clusters: advanced.retrieval_expand_top,
            include_multi_hop: advanced.retrieval_multi_hop,
            min_edge_lock_in_for_hop: advanced.retrieval_min_edge,
          },
          services: {
            clustering_interval_hours: advanced.svc_clustering_hours,
            lockin_update_interval_minutes: advanced.svc_lockin_minutes,
            cleanup_interval_hours: advanced.svc_cleanup_hours,
          },
          use_clusters: advanced.use_clusters,
          use_louvain: advanced.use_louvain,
        }),
      });
      setDirty(false);
      await load();
    } catch (e) {
      console.error('Save failed', e);
    }
    setSaving(false);
  };

  const DECAY_LABELS = {
    crystallized: '~11.5 day half-life',
    settled: '~1.15 day half-life',
    fluid: '~2.8 hour half-life',
    drifting: '~17 min half-life',
  };

  const advNumRow = (label, key, step = 1, min = 0, max) => (
    <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
      <span className="ec-font-label" style={{ width: 160, fontSize: 8, letterSpacing: 1, color: 'var(--ec-text-faint)' }}>
        {label}
      </span>
      <input
        type="number"
        step={step}
        min={min}
        max={max}
        value={advanced[key] ?? ''}
        onChange={(e) => handleAdvanced(key, parseFloat(e.target.value))}
        style={{ ...inputStyle, width: 120, flex: 'none' }}
      />
    </div>
  );

  const advCheckRow = (label, key) => (
    <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
      <label style={{ display: 'flex', alignItems: 'center', gap: 8, cursor: 'pointer' }}>
        <input
          type="checkbox"
          checked={!!advanced[key]}
          onChange={(e) => handleAdvanced(key, e.target.checked)}
          style={{ accentColor: '#7dd3fc' }}
        />
        <span className="ec-font-label" style={{ fontSize: 8, letterSpacing: 1, color: 'var(--ec-text-faint)' }}>
          {label}
        </span>
      </label>
    </div>
  );

  return (
    <div style={{ maxWidth: 480 }}>
      <h2 className="ec-font-label" style={headerStyle}>MEMORY ECONOMY</h2>

      <h3 className="ec-font-label" style={subheaderStyle}>
        LOCK-IN WEIGHTS (must sum to 1.0)
      </h3>

      {Object.entries(weights).map(([key, val]) => (
        <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <span className="ec-font-label" style={{ width: 60, fontSize: 8, letterSpacing: 1, color: 'var(--ec-text-faint)' }}>
            {key.toUpperCase()}
          </span>
          <input
            type="range"
            min={0} max={1} step={0.05}
            value={val}
            onChange={(e) => handleWeight(key, e.target.value)}
            style={{ flex: 1, accentColor: '#7dd3fc' }}
          />
          <span className="ec-font-mono" style={{ width: 40, fontSize: 11, color: 'var(--ec-text)', textAlign: 'right' }}>
            {val.toFixed(2)}
          </span>
        </div>
      ))}

      <div className="ec-font-mono" style={{
        fontSize: 10,
        color: isValid ? '#34d399' : '#f87171',
        marginTop: 4,
      }}>
        Total: {total.toFixed(3)}
      </div>

      {error && (
        <div className="ec-font-mono" style={{ fontSize: 10, color: '#f87171', marginTop: 4 }}>{error}</div>
      )}

      {/* Decay rates (editable) */}
      <div style={{ marginTop: 24 }}>
        <h3 className="ec-font-label" style={subheaderStyle}>
          DECAY RATES (per second)
        </h3>
        {Object.entries(decay).map(([state, rate]) => (
          <div key={state} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <span className="ec-font-label" style={{ width: 90, fontSize: 8, letterSpacing: 1, color: 'var(--ec-text-faint)' }}>
              {state.toUpperCase()}
            </span>
            <input
              type="number"
              step="0.00001"
              min="0"
              value={rate}
              onChange={(e) => handleDecay(state, e.target.value)}
              style={{ ...inputStyle, width: 120, flex: 'none' }}
            />
            <span className="ec-font-mono" style={{ fontSize: 9, color: 'var(--ec-text-faint)' }}>
              {DECAY_LABELS[state] || ''}
            </span>
          </div>
        ))}
      </div>

      {/* Thresholds (editable) */}
      <div style={{ marginTop: 24 }}>
        <h3 className="ec-font-label" style={subheaderStyle}>
          STATE THRESHOLDS (0-1)
        </h3>
        {Object.entries(thresholds).map(([key, val]) => (
          <div key={key} style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <span className="ec-font-label" style={{ width: 110, fontSize: 8, letterSpacing: 1, color: 'var(--ec-text-faint)' }}>
              {key.toUpperCase()}
            </span>
            <input
              type="number"
              step="0.01"
              min="0"
              max="1"
              value={val}
              onChange={(e) => handleThreshold(key, e.target.value)}
              style={{ ...inputStyle, width: 80, flex: 'none' }}
            />
          </div>
        ))}
      </div>

      {/* Advanced (collapsible) */}
      <details style={{ marginTop: 24 }}>
        <summary className="ec-font-label" style={{
          fontSize: 9, letterSpacing: 2, color: 'var(--ec-text-faint)',
          cursor: 'pointer', userSelect: 'none', marginBottom: 10,
        }}>
          ADVANCED
        </summary>
        <div style={{ paddingLeft: 8, borderLeft: '1px solid var(--ec-border)' }}>

          <h4 className="ec-font-label" style={advGroupStyle}>CONSTELLATION</h4>
          {advNumRow('MAX TOKENS', 'constellation_max_tokens', 100, 0)}
          {advNumRow('CLUSTER BUDGET %', 'constellation_cluster_budget_pct', 0.05, 0, 1)}

          <h4 className="ec-font-label" style={advGroupStyle}>CLUSTERING</h4>
          {advNumRow('MIN CLUSTER SIZE', 'clustering_min_size', 1, 1)}
          {advNumRow('MAX CLUSTER SIZE', 'clustering_max_size', 1, 1)}
          {advNumRow('MIN KEYWORD OVERLAP', 'clustering_min_overlap', 0.05, 0, 1)}
          {advNumRow('MAX GENERIC FREQUENCY', 'clustering_max_generic', 1, 0)}
          {advNumRow('MERGE THRESHOLD', 'clustering_merge_threshold', 0.05, 0, 1)}

          <h4 className="ec-font-label" style={advGroupStyle}>RETRIEVAL</h4>
          {advNumRow('MAX CLUSTERS / QUERY', 'retrieval_max_clusters', 1, 1)}
          {advNumRow('EXPAND TOP CLUSTERS', 'retrieval_expand_top', 1, 0)}
          {advNumRow('MIN EDGE LOCK-IN', 'retrieval_min_edge', 0.05, 0, 1)}
          {advCheckRow('INCLUDE MULTI-HOP', 'retrieval_multi_hop')}

          <h4 className="ec-font-label" style={advGroupStyle}>SERVICE INTERVALS</h4>
          {advNumRow('CLUSTERING (hours)', 'svc_clustering_hours', 0.5, 0.1)}
          {advNumRow('LOCK-IN UPDATE (min)', 'svc_lockin_minutes', 1, 1)}
          {advNumRow('CLEANUP (hours)', 'svc_cleanup_hours', 1, 1)}

          <h4 className="ec-font-label" style={advGroupStyle}>GLOBAL FLAGS</h4>
          {advCheckRow('USE CLUSTERS', 'use_clusters')}
          {advCheckRow('USE LOUVAIN', 'use_louvain')}

        </div>
      </details>

      <button onClick={handleSave} disabled={!dirty || saving || !isValid} style={{ ...saveBtnStyle(dirty && isValid), marginTop: 20 }}>
        {saving ? 'SAVING...' : 'SAVE'}
      </button>
    </div>
  );
}

const headerStyle = { fontSize: 11, letterSpacing: 3, color: 'var(--ec-text-soft)', marginBottom: 24 };
const subheaderStyle = { fontSize: 9, letterSpacing: 2, color: 'var(--ec-text-faint)', marginBottom: 10 };
const advGroupStyle = { fontSize: 9, letterSpacing: 2, color: 'var(--ec-text-faint)', marginBottom: 10, marginTop: 16, paddingLeft: 4 };
const inputStyle = {
  background: 'var(--ec-bg-input, var(--ec-bg))',
  border: '1px solid var(--ec-border)',
  borderRadius: 4, padding: '4px 8px',
  color: 'var(--ec-text)', fontSize: 11,
  fontFamily: 'var(--ec-font-mono, "JetBrains Mono", monospace)',
  outline: 'none', boxSizing: 'border-box',
};
const saveBtnStyle = (dirty) => ({
  background: dirty ? 'rgba(52,211,153,0.1)' : 'transparent',
  border: `1px solid ${dirty ? 'rgba(52,211,153,0.3)' : 'var(--ec-border)'}`,
  borderRadius: 4, padding: '8px 24px',
  color: dirty ? '#34d399' : 'var(--ec-text-faint)',
  fontSize: 10, letterSpacing: 1.5, cursor: dirty ? 'pointer' : 'default',
});
