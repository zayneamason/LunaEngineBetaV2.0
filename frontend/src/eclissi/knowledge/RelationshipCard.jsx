import React from 'react';

const REL_COLORS = {
  depends_on: '#f87171',
  enables: '#34d399',
  corroborates: '#7dd3fc',
  mentions: '#c084fc',
  relates_to: '#94a3b8',
  part_of: '#fbbf24',
  created_by: '#fb923c',
};

/**
 * RelationshipCard — displays a graph edge between two nodes in the right T-panel.
 */
export default function RelationshipCard({ relationship }) {
  const label = (relationship.label || relationship.relationship || 'relates_to').toLowerCase();
  const source = relationship.source_name || relationship.from || '?';
  const target = relationship.target_name || relationship.to || '?';
  const color = REL_COLORS[label] || '#94a3b8';

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '5px 8px',
        borderRadius: 4,
        background: 'rgba(255,255,255,0.02)',
      }}
    >
      <span
        className="ec-font-mono"
        style={{ fontSize: 10, color: 'var(--ec-text-soft)', flexShrink: 0 }}
      >
        {source}
      </span>
      <span
        style={{
          padding: '1px 5px',
          borderRadius: 3,
          fontSize: 8,
          fontFamily: "'Bebas Neue', sans-serif",
          letterSpacing: '0.5px',
          color,
          background: `${color}12`,
          border: `1px solid ${color}25`,
          flexShrink: 0,
        }}
      >
        {label.replace(/_/g, ' ')}
      </span>
      <span
        className="ec-font-mono"
        style={{ fontSize: 10, color: 'var(--ec-text-soft)', flexShrink: 0 }}
      >
        {target}
      </span>
    </div>
  );
}
