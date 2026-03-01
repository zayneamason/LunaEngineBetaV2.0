import React from 'react';

const TYPE_COLORS = {
  person: '#ec4899',
  place: '#22c55e',
  project: '#06b6d4',
  persona: '#c084fc',
  character: '#f97316',
  location: '#22c55e',
  prop: '#6366f1',
  lore: '#eab308',
  faction: '#ef4444',
  concept: '#7dd3fc',
};

/**
 * EntityCard — displays an entity in the right T-panel.
 * Avatar placeholder + name + role/type.
 */
export default function EntityCard({ entity }) {
  const name = entity.name || entity.entity_name || '?';
  const type = (entity.type || entity.entity_type || 'concept').toLowerCase();
  const color = TYPE_COLORS[type] || '#94a3b8';
  const profile = entity.profile || entity.description || null;

  return (
    <div
      className="ec-glass-interactive"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 10,
        padding: '8px 10px',
        borderRadius: 6,
      }}
    >
      {/* Avatar circle */}
      <div
        style={{
          width: 28,
          height: 28,
          borderRadius: '50%',
          background: `${color}20`,
          border: `1.5px solid ${color}50`,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          fontSize: 12,
          color,
          fontFamily: "'Bebas Neue', sans-serif",
          flexShrink: 0,
        }}
      >
        {name.charAt(0).toUpperCase()}
      </div>

      {/* Name + type */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div
          className="ec-font-body"
          style={{
            fontSize: 12,
            color: 'var(--ec-text)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {name}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
          <span
            style={{
              fontSize: 8,
              fontFamily: "'Bebas Neue', sans-serif",
              letterSpacing: '1px',
              color,
              textTransform: 'uppercase',
            }}
          >
            {type}
          </span>
          {profile && (
            <span
              className="ec-font-mono"
              style={{
                fontSize: 8,
                color: 'var(--ec-text-faint)',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {profile.slice(0, 60)}{profile.length > 60 ? '...' : ''}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
