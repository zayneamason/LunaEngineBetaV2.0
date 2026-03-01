import React from 'react';

export default function ConnectionBadge({ connected, label }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 5,
      padding: '2px 10px', borderRadius: 6,
      background: connected ? 'rgba(34,197,94,0.1)' : 'rgba(239,68,68,0.1)',
      border: `1px solid ${connected ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)'}`,
    }}>
      <div style={{
        width: 6, height: 6, borderRadius: '50%',
        background: connected ? '#22c55e' : '#ef4444',
        animation: connected ? 'pulse-green 2.5s ease-in-out infinite' : 'pulse-red 1s ease-in-out infinite',
      }} />
      <span style={{ fontSize: 9, color: connected ? '#22c55e' : '#ef4444', fontFamily: "'JetBrains Mono', monospace" }}>
        {label || (connected ? 'CONNECTED' : 'DISCONNECTED')}
      </span>
    </div>
  );
}
