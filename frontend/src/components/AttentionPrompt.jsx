import React, { useState } from 'react';

/**
 * AttentionPrompt — suggests tracking a frequently-mentioned entity as a thread.
 * "X mentioned N times. Track as thread?"
 */
export default function AttentionPrompt({ entityName, mentionCount, onTrack, onDismiss }) {
  const [dismissed, setDismissed] = useState(false);

  if (dismissed) return null;

  return (
    <div
      className="mx-4 my-1 px-3 py-1.5 rounded"
      style={{
        border: '1px solid rgba(96,165,250,0.15)',
        background: 'rgba(96,165,250,0.04)',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 11,
      }}
    >
      <span style={{ color: '#60a5fa', fontWeight: 600 }}>!</span>
      <span style={{ color: 'var(--ec-text, #e5e7eb)' }}>
        <strong style={{ color: '#60a5fa' }}>{entityName}</strong> mentioned {mentionCount} times.
      </span>
      <div style={{ marginLeft: 'auto', display: 'flex', gap: 6 }}>
        <button
          onClick={() => { onTrack?.(entityName); setDismissed(true); }}
          style={{
            padding: '2px 8px', borderRadius: 3, fontSize: 10,
            border: '1px solid rgba(52,211,153,0.4)', color: '#34d399',
            background: 'transparent', cursor: 'pointer',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(52,211,153,0.1)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
        >
          Track
        </button>
        <button
          onClick={() => setDismissed(true)}
          style={{
            padding: '2px 8px', borderRadius: 3, fontSize: 10,
            border: '1px solid rgba(148,163,184,0.3)', color: '#94a3b8',
            background: 'transparent', cursor: 'pointer',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(148,163,184,0.1)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
        >
          Dismiss
        </button>
      </div>
    </div>
  );
}
