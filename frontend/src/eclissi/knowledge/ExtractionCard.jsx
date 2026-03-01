import React from 'react';

const TYPE_COLORS = {
  FACT: '#7dd3fc',
  DECISION: '#c084fc',
  INSIGHT: '#fbbf24',
  ACTION: '#34d399',
  MILESTONE: '#f59e0b',
  PROBLEM: '#f87171',
  OBSERVATION: '#94a3b8',
  OUTCOME: '#fb923c',
};

const TYPE_ICONS = {
  FACT: 'F',
  DECISION: 'D',
  INSIGHT: 'I',
  ACTION: 'A',
  MILESTONE: 'M',
  PROBLEM: 'P',
  OBSERVATION: 'O',
  OUTCOME: 'R',
};

/**
 * ExtractionCard — a single extraction displayed in the left T-panel.
 * 3px left accent border, content text, confidence score, lock-in score.
 */
export default function ExtractionCard({ extraction }) {
  const type = (extraction.type || 'FACT').toUpperCase();
  const color = TYPE_COLORS[type] || '#94a3b8';
  const confidence = extraction.confidence ?? null;
  const lockIn = extraction.lock_in ?? extraction.lockIn ?? null;
  const entities = extraction.entities || [];
  const provenance = extraction.provenance || null;

  return (
    <div
      className="ec-glass-interactive"
      style={{
        borderLeft: `3px solid ${color}`,
        borderRadius: '0 6px 6px 0',
        padding: '8px 10px',
        display: 'flex',
        flexDirection: 'column',
        gap: 4,
      }}
    >
      {/* Type badge + provenance */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <span
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '1px 6px',
            borderRadius: 3,
            fontSize: 9,
            fontFamily: "'Bebas Neue', sans-serif",
            letterSpacing: '1px',
            color,
            background: `${color}15`,
          }}
        >
          {type}
        </span>
        {provenance && (
          <span
            className="ec-font-mono"
            style={{ fontSize: 8, color: 'var(--ec-text-faint)' }}
          >
            {provenance}
          </span>
        )}
      </div>

      {/* Content */}
      <p
        className="ec-font-body"
        style={{
          fontSize: 12,
          color: 'var(--ec-text-soft)',
          lineHeight: 1.5,
          margin: 0,
          wordBreak: 'break-word',
        }}
      >
        {extraction.content || '—'}
      </p>

      {/* Scores + entities footer */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        {confidence !== null && (
          <span className="ec-font-mono" style={{ fontSize: 9, color: 'var(--ec-text-faint)' }}>
            conf {(confidence * 100).toFixed(0)}%
          </span>
        )}
        {lockIn !== null && (
          <span className="ec-font-mono" style={{ fontSize: 9, color: 'var(--ec-text-faint)' }}>
            lock-in {(lockIn * 100).toFixed(0)}%
          </span>
        )}
        {entities.length > 0 && (
          <div style={{ display: 'flex', gap: 3, marginLeft: 'auto' }}>
            {entities.slice(0, 3).map((ent, i) => (
              <span
                key={i}
                style={{
                  padding: '1px 5px',
                  borderRadius: 3,
                  fontSize: 8,
                  background: 'rgba(255,255,255,0.05)',
                  color: 'var(--ec-text-faint)',
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                {typeof ent === 'string' ? ent : ent.name || '?'}
              </span>
            ))}
            {entities.length > 3 && (
              <span className="ec-font-mono" style={{ fontSize: 8, color: 'var(--ec-text-faint)' }}>
                +{entities.length - 3}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
