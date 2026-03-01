import React, { useState, useEffect, useRef } from 'react';

const TYPE_ICONS = {
  retrieval: '🔍',
  planning: '📋',
  reasoning: '💭',
  tool_use: '⚡',
  generation: '✨',
  evaluation: '🎯',
  success: '✓',
  failure: '✗',
  observation: '👁',
};

export default function ThoughtWidget() {
  const [thoughts, setThoughts] = useState([]);
  const [connected, setConnected] = useState(false);
  const scrollRef = useRef(null);
  const sourceRef = useRef(null);

  useEffect(() => {
    const es = new EventSource('/thoughts');
    sourceRef.current = es;

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setThoughts((prev) => {
          const next = [...prev, { ...data, _ts: Date.now() }];
          return next.slice(-50);
        });
      } catch {}
    };

    return () => {
      es.close();
      sourceRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [thoughts]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, height: '100%' }}>
      {/* Connection status */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div
          style={{
            width: 6,
            height: 6,
            borderRadius: '50%',
            background: connected ? '#22c55e' : '#ef4444',
          }}
        />
        <span className="ec-font-label" style={{ fontSize: 9, color: 'var(--ec-text-faint)' }}>
          {connected ? 'STREAMING' : 'DISCONNECTED'}
        </span>
        <span className="ec-font-mono" style={{ fontSize: 9, color: 'var(--ec-text-muted)', marginLeft: 'auto' }}>
          {thoughts.length} events
        </span>
      </div>

      {/* Thought stream */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          display: 'flex',
          flexDirection: 'column',
          gap: 3,
          minHeight: 200,
        }}
      >
        {thoughts.length === 0 ? (
          <div style={{ color: 'var(--ec-text-faint)', fontSize: 11, textAlign: 'center', padding: 20 }}>
            Waiting for thoughts...
          </div>
        ) : (
          thoughts.map((t, i) => {
            const icon = TYPE_ICONS[t.type] || '💭';
            const time = t._ts ? new Date(t._ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '';
            return (
              <div
                key={i}
                style={{
                  display: 'flex',
                  gap: 6,
                  padding: '3px 6px',
                  borderRadius: 3,
                  background: 'rgba(255,255,255,0.02)',
                  alignItems: 'flex-start',
                }}
              >
                <span style={{ fontSize: 11, flexShrink: 0, marginTop: 1 }}>{icon}</span>
                <span
                  className="ec-font-mono"
                  style={{
                    fontSize: 10,
                    color: 'var(--ec-text-soft)',
                    lineHeight: 1.4,
                    flex: 1,
                    wordBreak: 'break-word',
                  }}
                >
                  {t.content || t.message || t.text || JSON.stringify(t)}
                </span>
                <span className="ec-font-mono" style={{ fontSize: 8, color: 'var(--ec-text-muted)', flexShrink: 0, marginTop: 2 }}>
                  {time}
                </span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
