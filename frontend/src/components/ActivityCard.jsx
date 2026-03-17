import React from 'react';
import { useNavigation } from '../hooks/useNavigation';

const EVENT_CONFIG = {
  fact_extracted: { icon: 'F', label: 'fact', color: '#60a5fa', tab: 'graph' },
  entity_created: { icon: 'E', label: 'entity', color: '#f472b6', tab: 'entities' },
  edge_created: { icon: '→', label: 'edge', color: '#34d399', tab: 'graph' },
  thread_updated: { icon: 'T', label: 'thread', color: '#c084fc', tab: 'threads' },
  quest_generated: { icon: 'Q', label: 'quest', color: '#fbbf24', tab: 'quests' },
};

/**
 * ActivityCard — compact card showing a single pipeline event between chat messages.
 * Click navigates to the relevant Observatory tab.
 */
export default function ActivityCard({ event }) {
  const { navigate } = useNavigation();

  const cfg = EVENT_CONFIG[event.type] || { icon: '•', label: event.type, color: '#94a3b8', tab: 'graph' };
  const text = event.payload?.content
    || event.payload?.name
    || event.payload?.topic
    || event.payload?.title
    || `${cfg.label} event`;

  const handleClick = () => {
    const nav = { to: 'observatory', tab: cfg.tab };
    if (event.payload?.entity_id) nav.entityId = event.payload.entity_id;
    navigate(nav);
  };

  return (
    <div
      onClick={handleClick}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '3px 12px',
        fontSize: 11,
        color: 'var(--ec-text-faint, #6b7280)',
        cursor: 'pointer',
        borderRadius: 4,
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.03)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'transparent'; }}
      title={`${cfg.label} — click to view in Observatory`}
    >
      <span style={{
        width: 16, height: 16, lineHeight: '16px', textAlign: 'center',
        borderRadius: 3, fontSize: 10, fontWeight: 600,
        background: `${cfg.color}15`, color: cfg.color,
      }}>
        {cfg.icon}
      </span>
      <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 300 }}>
        {text}
      </span>
      <span style={{ marginLeft: 'auto', opacity: 0.5 }}>{cfg.label}</span>
    </div>
  );
}
