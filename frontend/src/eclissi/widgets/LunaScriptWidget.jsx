import React, { useState, useEffect } from 'react';

const CLASSIFICATION_COLORS = {
  RESONANCE: '#22c55e',
  DRIFT: '#ef4444',
  EXPANSION: '#3b82f6',
  COMPRESSION: '#f59e0b',
};

const TRAIT_COLORS = [
  '#f472b6', '#a78bfa', '#38bdf8', '#34d399',
  '#fbbf24', '#fb923c', '#818cf8', '#4ade80',
];

function TraitBar({ name, value, weight, defaultWeight, color }) {
  const pct = Math.round((value || 0) * 100);
  const wDelta = weight != null && defaultWeight != null ? weight - defaultWeight : null;
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 11 }}>
      <span style={{ width: 64, color: 'var(--ec-text-faint)', textTransform: 'capitalize' }}>{name}</span>
      <div style={{ flex: 1, height: 6, background: 'rgba(255,255,255,0.06)', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 3, transition: 'width 0.3s' }} />
      </div>
      <span style={{ width: 28, textAlign: 'right', color: 'var(--ec-text-secondary)' }}>{pct}</span>
      {wDelta != null && Math.abs(wDelta) > 0.01 && (
        <span style={{ width: 36, textAlign: 'right', fontSize: 9, color: wDelta > 0 ? '#22c55e' : '#ef4444' }}>
          {wDelta > 0 ? '+' : ''}{wDelta.toFixed(2)}
        </span>
      )}
    </div>
  );
}

export default function LunaScriptWidget() {
  const [state, setState] = useState(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch('/api/lunascript/state');
        if (res.ok) setState(await res.json());
      } catch {}
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  }, []);

  if (!state) {
    return (
      <div style={{ textAlign: 'center', padding: 24, color: 'var(--ec-text-faint)', fontSize: 12 }}>
        Loading LunaScript state...
      </div>
    );
  }

  if (!state.enabled) {
    return (
      <div style={{ textAlign: 'center', padding: 24, color: 'var(--ec-text-faint)', fontSize: 12 }}>
        LunaScript waiting — send a message to activate
      </div>
    );
  }

  const traits = state.traits || {};
  const weights = state.trait_weights || {};
  const defaults = state.default_weights || {};
  const trends = state.trait_trends || {};
  const correlations = state.trait_correlations || {};
  const patterns = state.patterns || [];
  const classColor = CLASSIFICATION_COLORS[state.last_classification] || 'var(--ec-text-faint)';
  const traitNames = ['warmth', 'curiosity', 'directness', 'energy', 'formality', 'humor', 'depth', 'patience'];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Header: position + glyph */}
      <div style={{ textAlign: 'center', padding: '8px 0' }}>
        <div className="ec-font-display" style={{ fontSize: 32, fontWeight: 300, color: 'var(--ec-accent-memory)' }}>
          {state.glyph || '○'}
        </div>
        <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginTop: 4 }}>
          {state.position || 'IDLE'}
        </div>
        {state.last_classification && (
          <span style={{
            display: 'inline-block', marginTop: 6,
            padding: '2px 8px', borderRadius: 4,
            fontSize: 10, fontWeight: 600,
            background: `color-mix(in srgb, ${classColor} 15%, transparent)`,
            color: classColor,
          }}>
            {state.last_classification}
          </span>
        )}
      </div>

      {/* Trait bars */}
      <div className="ec-glass-interactive" style={{ padding: '10px 12px', borderRadius: 6 }}>
        <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 8 }}>
          TRAITS
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
          {traitNames.map((t, i) => (
            <TraitBar
              key={t}
              name={t}
              value={traits[t]}
              weight={weights[t]}
              defaultWeight={defaults[t]}
              color={TRAIT_COLORS[i]}
            />
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="ec-glass-interactive" style={{ padding: '10px 12px', borderRadius: 6 }}>
        <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 6 }}>
          EVOLUTION
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px', fontSize: 11 }}>
          <span style={{ color: 'var(--ec-text-faint)' }}>epsilon</span>
          <span style={{ textAlign: 'right', color: 'var(--ec-text-secondary)' }}>{(state.epsilon || 0).toFixed(4)}</span>
          <span style={{ color: 'var(--ec-text-faint)' }}>iteration</span>
          <span style={{ textAlign: 'right', color: 'var(--ec-text-secondary)' }}>{state.iteration || 0}</span>
          <span style={{ color: 'var(--ec-text-faint)' }}>drift baseline</span>
          <span style={{ textAlign: 'right', color: 'var(--ec-text-secondary)' }}>
            {state.drift_baseline ? `${state.drift_baseline.mean?.toFixed(3)} ± ${state.drift_baseline.stddev?.toFixed(3)}` : '—'}
          </span>
        </div>
      </div>

      {/* Trends (sorted by |value|) */}
      {Object.keys(trends).length > 0 && (
        <div className="ec-glass-interactive" style={{ padding: '10px 12px', borderRadius: 6 }}>
          <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 6 }}>
            DRIFT TRENDS
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, fontSize: 11 }}>
            {Object.entries(trends)
              .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
              .slice(0, 5)
              .map(([t, v]) => (
                <div key={t} style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--ec-text-faint)', textTransform: 'capitalize' }}>{t}</span>
                  <span style={{ color: v > 0.05 ? '#f59e0b' : 'var(--ec-text-secondary)' }}>
                    {v.toFixed(3)}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Correlations */}
      {Object.keys(correlations).length > 0 && (
        <div className="ec-glass-interactive" style={{ padding: '10px 12px', borderRadius: 6 }}>
          <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 6 }}>
            TRAIT-QUALITY CORRELATIONS
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, fontSize: 11 }}>
            {Object.entries(correlations)
              .sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]))
              .slice(0, 5)
              .map(([t, r]) => (
                <div key={t} style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <span style={{ color: 'var(--ec-text-faint)', textTransform: 'capitalize' }}>{t}</span>
                  <span style={{ color: r < -0.2 ? '#ef4444' : r > 0.2 ? '#22c55e' : 'var(--ec-text-secondary)' }}>
                    r={r.toFixed(3)}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}

      {/* Patterns */}
      {patterns.length > 0 && (
        <div className="ec-glass-interactive" style={{ padding: '10px 12px', borderRadius: 6 }}>
          <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 6 }}>
            PATTERNS ({patterns.length})
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 3, fontSize: 11 }}>
            {patterns.map((p) => (
              <div key={p.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ color: 'var(--ec-text-secondary)' }}>{p.name}</span>
                <span style={{ color: 'var(--ec-text-faint)', fontSize: 9 }}>
                  {p.glyph} · {p.usage_count}x · {(p.avg_success * 100).toFixed(0)}%
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
