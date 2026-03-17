import React from 'react';
import { useNavigation } from '../hooks/useNavigation';

const STATUS_COLORS = {
  active: '#34d399',
  parked: '#94a3b8',
  resumed: '#60a5fa',
};

/**
 * ThreadCard — displays the active conversation thread between chat messages.
 * Shows topic, entity count, turn count, and status badge.
 * Click navigates to Observatory threads tab.
 */
export default function ThreadCard({ thread }) {
  const { navigate } = useNavigation();

  const color = STATUS_COLORS[thread.status] || STATUS_COLORS.active;

  return (
    <div
      onClick={() => navigate({ to: 'observatory', tab: 'threads' })}
      className="mx-4 my-1 px-3 py-1.5 rounded"
      style={{
        border: `1px solid ${color}20`,
        background: `${color}06`,
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 11,
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = `${color}10`; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = `${color}06`; }}
    >
      <span style={{ color, fontWeight: 600 }}>T</span>
      <span style={{ color: 'var(--ec-text, #e5e7eb)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {thread.topic}
      </span>
      {thread.entities?.length > 0 && (
        <span style={{ color: 'var(--ec-text-faint, #6b7280)' }}>
          {thread.entities.length} entities
        </span>
      )}
      <span style={{ color: 'var(--ec-text-faint, #6b7280)' }}>
        {thread.turn_count} turns
      </span>
      <span style={{
        padding: '1px 6px', borderRadius: 3, fontSize: 9, fontWeight: 600,
        background: `${color}20`, color,
        textTransform: 'uppercase',
      }}>
        {thread.status}
      </span>
    </div>
  );
}
