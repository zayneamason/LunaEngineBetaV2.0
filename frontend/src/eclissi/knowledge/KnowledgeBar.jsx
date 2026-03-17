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

const TYPE_LABELS = {
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
 * KnowledgeBar — gradient line below an assistant message indicating Scribe extractions.
 * Click to open the T-panels.
 */
export default function KnowledgeBar({ extractions, liveEvents, isActive, onClick }) {
  // Prefer live WebSocket events when available, fall back to polled extractions
  const source = (liveEvents && liveEvents.length > 0) ? liveEvents : extractions;
  if (!source || source.length === 0) return null;

  // Group by type for the dot indicators
  const typeCounts = {};
  for (const ext of source) {
    // liveEvents use lowercase payload types; extractions use ext.type
    const raw = ext.payload?.node_type || ext.type || 'FACT';
    const t = raw.toUpperCase();
    typeCounts[t] = (typeCounts[t] || 0) + 1;
  }

  // Primary color from the most frequent type
  const primaryType = Object.entries(typeCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || 'FACT';
  const primaryColor = TYPE_COLORS[primaryType] || TYPE_COLORS.FACT;

  return (
    <button
      onClick={onClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        width: '100%',
        padding: '4px 0',
        margin: '2px 0',
        background: 'none',
        border: 'none',
        cursor: 'pointer',
        opacity: isActive ? 1 : 0.5,
        transition: 'opacity 0.3s ease',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.opacity = '1'; }}
      onMouseLeave={(e) => { if (!isActive) e.currentTarget.style.opacity = '0.5'; }}
    >
      {/* Left gradient line */}
      <div
        style={{
          flex: 1,
          height: 1,
          background: `linear-gradient(90deg, transparent, ${primaryColor}40)`,
        }}
      />

      {/* Type indicators */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 3, flexShrink: 0 }}>
        {Object.entries(typeCounts).map(([type, count]) => (
          <span
            key={type}
            title={`${count} ${type.toLowerCase()}${count > 1 ? 's' : ''}`}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 16,
              height: 16,
              borderRadius: 3,
              fontSize: 8,
              fontFamily: "'Bebas Neue', sans-serif",
              letterSpacing: '0.5px',
              color: TYPE_COLORS[type] || '#94a3b8',
              background: `${(TYPE_COLORS[type] || '#94a3b8')}15`,
              border: `1px solid ${(TYPE_COLORS[type] || '#94a3b8')}30`,
            }}
          >
            {TYPE_LABELS[type] || '?'}
          </span>
        ))}
        <span
          className="ec-font-mono"
          style={{ fontSize: 9, color: 'var(--ec-text-faint)', marginLeft: 2 }}
        >
          {source.length}
        </span>
      </div>

      {/* Right gradient line */}
      <div
        style={{
          flex: 1,
          height: 1,
          background: `linear-gradient(90deg, ${primaryColor}40, transparent)`,
        }}
      />
    </button>
  );
}
