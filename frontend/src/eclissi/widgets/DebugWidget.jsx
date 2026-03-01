import React, { useState, useEffect } from 'react';

const RING_COLORS = {
  CORE: '#eab308',
  INNER: '#ef4444',
  MIDDLE: '#f97316',
  OUTER: '#6b7280',
};

export default function DebugWidget() {
  const [ctx, setCtx] = useState(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch('/debug/context');
        if (res.ok) setCtx(await res.json());
      } catch {}
    };
    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, []);

  if (!ctx) {
    return (
      <div style={{ color: 'var(--ec-text-faint)', fontSize: 12, textAlign: 'center', padding: 20 }}>
        No context data
      </div>
    );
  }

  const budget = ctx.token_budget || 0;
  const used = ctx.total_tokens || 0;
  const pct = budget > 0 ? ((used / budget) * 100).toFixed(0) : 0;
  const rings = ctx.rings || {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Token budget bar */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
          <span className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)' }}>TOKEN BUDGET</span>
          <span className="ec-font-mono" style={{ fontSize: 10, color: 'var(--ec-text-soft)' }}>
            {used.toLocaleString()} / {budget.toLocaleString()} ({pct}%)
          </span>
        </div>
        <div style={{ height: 8, borderRadius: 4, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
          <div
            style={{
              width: `${Math.min(pct, 100)}%`,
              height: '100%',
              background: pct > 90 ? 'var(--ec-accent-qa)' : pct > 70 ? '#f59e0b' : 'var(--ec-accent-debug)',
              borderRadius: 4,
              transition: 'width 0.5s ease',
            }}
          />
        </div>
      </div>

      {/* Ring breakdown */}
      <div>
        <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 8 }}>
          CONTEXT RINGS
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {Object.entries(RING_COLORS).map(([ring, color]) => {
            const r = rings[ring] || {};
            const count = r.count || 0;
            const tokens = r.tokens || 0;
            return (
              <div key={ring} className="ec-glass-interactive" style={{ padding: '6px 10px', borderRadius: 6 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{ width: 8, height: 8, borderRadius: '50%', background: color }} />
                    <span className="ec-font-label" style={{ fontSize: 10, color: 'var(--ec-text-soft)' }}>{ring}</span>
                  </div>
                  <span className="ec-font-mono" style={{ fontSize: 10, color: 'var(--ec-text-faint)' }}>
                    {count} items · {tokens} tok
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Keywords */}
      {ctx.keywords?.length > 0 && (
        <div>
          <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 6 }}>
            QUERY KEYWORDS
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {ctx.keywords.slice(0, 12).map((kw, i) => (
              <span
                key={i}
                style={{
                  padding: '2px 6px',
                  borderRadius: 3,
                  background: 'rgba(251,191,36,0.12)',
                  color: 'var(--ec-accent-debug)',
                  fontSize: 10,
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                {kw}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
