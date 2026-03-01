import React, { useState, useEffect } from 'react';

const LAYER_COLORS = {
  'identity': 'var(--ec-accent-luna)',
  'consciousness': '#a78bfa',
  'memory': 'var(--ec-accent-memory)',
  'tools': 'var(--ec-accent-prompt)',
  'history': '#fbbf24',
  'user': '#e8e8f0',
};

export default function PromptWidget() {
  const [prompt, setPrompt] = useState(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch('/slash/prompt');
        if (res.ok) setPrompt(await res.json());
      } catch {}
    };
    poll();
    const id = setInterval(poll, 5000);
    return () => clearInterval(id);
  }, []);

  if (!prompt || prompt.error) {
    return (
      <div style={{ color: 'var(--ec-text-faint)', fontSize: 12, textAlign: 'center', padding: 20 }}>
        No prompt data yet
      </div>
    );
  }

  const layers = prompt.layers || prompt.assembly || [];
  const totalTokens = prompt.total_tokens || layers.reduce((sum, l) => sum + (l.tokens || 0), 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Total tokens */}
      <div style={{ textAlign: 'center', padding: '8px 0' }}>
        <div className="ec-font-mono" style={{ fontSize: 24, color: 'var(--ec-accent-prompt)' }}>
          {totalTokens.toLocaleString()}
        </div>
        <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)' }}>
          TOTAL TOKENS
        </div>
      </div>

      {/* Layer breakdown */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {layers.map((layer, i) => {
          const name = layer.name || layer.layer || `layer_${i}`;
          const tokens = layer.tokens || 0;
          const pct = totalTokens > 0 ? ((tokens / totalTokens) * 100).toFixed(0) : 0;
          const color = LAYER_COLORS[name.toLowerCase()] || 'var(--ec-text-soft)';

          return (
            <div key={i}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                <span className="ec-font-body" style={{ fontSize: 11, color: 'var(--ec-text-soft)', textTransform: 'capitalize' }}>
                  {name}
                </span>
                <span className="ec-font-mono" style={{ fontSize: 10, color: 'var(--ec-text-faint)' }}>
                  {tokens} ({pct}%)
                </span>
              </div>
              <div style={{ height: 4, borderRadius: 2, background: 'rgba(255,255,255,0.06)', overflow: 'hidden' }}>
                <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.5s ease' }} />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
