import React, { useState } from 'react';

const TYPE_COLORS = {
  person: '#f472b6',
  persona: '#c084fc',
  place: '#34d399',
  project: '#67e8f9',
  concept: '#94a3b8',
  ENTITY: '#94a3b8',
};

const TYPE_LABELS = {
  person: 'new person',
  persona: 'new persona',
  place: 'new place',
  project: 'new project',
  concept: 'new entity',
  ENTITY: 'new entity',
};

/**
 * ConfirmationCard — inline prompt asking the user to confirm or reject
 * a newly auto-created entity.  Rendered as a sibling between chat messages.
 */
export default function ConfirmationCard({ entity, onConfirm, onReject, onEntityClick }) {
  const [resolved, setResolved] = useState(null); // true = confirmed, false = rejected, 'later' = dismissed

  const color = TYPE_COLORS[entity.entity_type] || TYPE_COLORS.concept;
  const label = TYPE_LABELS[entity.entity_type] || TYPE_LABELS.concept;

  const handle = (confirmed) => {
    setResolved(confirmed);
    if (confirmed) {
      onConfirm(entity.entity_id);
    } else {
      onReject(entity.entity_id);
    }
  };

  if (resolved === 'later') return null; // Hidden until next session
  if (resolved !== null) {
    return (
      <div className="text-xs py-1 px-4" style={{ color: 'var(--ec-text-faint, #6b7280)' }}>
        {resolved ? '\u2713' : '\u2717'} {entity.name} {resolved ? 'tracked' : 'dismissed'}
      </div>
    );
  }

  return (
    <div
      className="mx-4 my-1.5 px-3 py-2 rounded"
      style={{
        border: `1px solid ${color}25`,
        background: `${color}08`,
      }}
    >
      <div className="flex items-center gap-3">
        <span className="text-sm" style={{ color: 'var(--ec-text, #e5e7eb)' }}>
          Is{' '}
          <strong
            style={{ color, cursor: onEntityClick ? 'pointer' : 'inherit' }}
            onClick={() => onEntityClick?.(entity.entity_id)}
          >
            {entity.name}
          </strong>{' '}
          a {label}?
        </span>
        <div className="ml-auto flex gap-2">
          <button
            onClick={() => handle(true)}
            className="px-3 py-1 text-xs rounded"
            style={{
              border: '1px solid rgba(52,211,153,0.4)',
              color: '#34d399',
              background: 'transparent',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(52,211,153,0.1)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
          >
            Yes
          </button>
          <button
            onClick={() => handle(false)}
            className="px-3 py-1 text-xs rounded"
            style={{
              border: '1px solid rgba(248,113,113,0.4)',
              color: '#f87171',
              background: 'transparent',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(248,113,113,0.1)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
          >
            No
          </button>
          <button
            onClick={() => setResolved('later')}
            className="px-3 py-1 text-xs rounded"
            style={{
              border: '1px solid rgba(148,163,184,0.3)',
              color: '#94a3b8',
              background: 'transparent',
              cursor: 'pointer',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(148,163,184,0.1)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
          >
            Later
          </button>
        </div>
      </div>
    </div>
  );
}
