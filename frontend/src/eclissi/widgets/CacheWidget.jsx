import React, { useState, useEffect } from 'react';

export default function CacheWidget() {
  const [cache, setCache] = useState(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch('/api/cache/shared-turn');
        if (res.ok) setCache(await res.json());
      } catch {}
    };
    poll();
    const id = setInterval(poll, 2000);
    return () => clearInterval(id);
  }, []);

  if (!cache) {
    return (
      <div style={{ color: 'var(--ec-text-faint)', fontSize: 12, textAlign: 'center', padding: 20 }}>
        No cache data
      </div>
    );
  }

  const tone = cache.expression?.emotional_tone || 'neutral';
  const hint = cache.expression?.expression_hint || 'idle_soft';
  const topic = cache.flow?.topic || '—';
  const mode = cache.flow?.mode || 'FLOW';
  const source = cache.source || '—';
  const stale = cache.is_stale;
  const scribed = cache.scribed || {};
  const totalScribed = scribed.total || 0;
  const facts = scribed.facts?.length || 0;
  const decisions = scribed.decisions?.length || 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* Staleness indicator */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <div
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: stale ? '#f59e0b' : '#22c55e',
            boxShadow: stale ? '0 0 6px rgba(245,158,11,0.5)' : '0 0 6px rgba(34,197,94,0.5)',
          }}
        />
        <span className="ec-font-label" style={{ fontSize: 10, color: stale ? '#f59e0b' : '#22c55e' }}>
          {stale ? 'STALE' : 'FRESH'}
        </span>
        <span className="ec-font-mono" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginLeft: 'auto' }}>
          src: {source}
        </span>
      </div>

      {/* Expression */}
      <div className="ec-glass-interactive" style={{ padding: '8px 10px', borderRadius: 6 }}>
        <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 6 }}>
          EXPRESSION
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
          <span className="ec-font-body" style={{ color: 'var(--ec-text-soft)' }}>Tone</span>
          <span className="ec-font-mono" style={{ color: 'var(--ec-accent-luna)' }}>{tone}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
          <span className="ec-font-body" style={{ color: 'var(--ec-text-soft)' }}>Hint</span>
          <span className="ec-font-mono" style={{ color: 'var(--ec-text)' }}>{hint}</span>
        </div>
      </div>

      {/* Flow */}
      <div className="ec-glass-interactive" style={{ padding: '8px 10px', borderRadius: 6 }}>
        <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 6 }}>
          FLOW
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 3 }}>
          <span className="ec-font-body" style={{ color: 'var(--ec-text-soft)' }}>Topic</span>
          <span className="ec-font-mono" style={{ color: 'var(--ec-text)' }}>{topic}</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11 }}>
          <span className="ec-font-body" style={{ color: 'var(--ec-text-soft)' }}>Mode</span>
          <span className="ec-font-mono" style={{ color: 'var(--ec-accent-luna)' }}>{mode}</span>
        </div>
      </div>

      {/* Scribed */}
      <div className="ec-glass-interactive" style={{ padding: '8px 10px', borderRadius: 6 }}>
        <div className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginBottom: 6 }}>
          SCRIBED ({totalScribed} total)
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <span className="ec-font-mono" style={{ fontSize: 11, color: 'var(--ec-accent-memory)' }}>{facts} facts</span>
          <span className="ec-font-mono" style={{ fontSize: 11, color: 'var(--ec-accent-luna)' }}>{decisions} decisions</span>
        </div>
      </div>
    </div>
  );
}
