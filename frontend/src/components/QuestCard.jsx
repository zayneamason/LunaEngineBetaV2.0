import React from 'react';
import { useNavigation } from '../hooks/useNavigation';

/**
 * QuestCard — quest notification card between chat messages.
 * Shows quest title and type. Click navigates to Observatory quests tab.
 */
export default function QuestCard({ quest }) {
  const { navigate } = useNavigation();

  return (
    <div
      onClick={() => navigate({ to: 'observatory', tab: 'quests' })}
      className="mx-4 my-1 px-3 py-1.5 rounded"
      style={{
        border: '1px solid rgba(251,191,36,0.15)',
        background: 'rgba(251,191,36,0.04)',
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        fontSize: 11,
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(251,191,36,0.08)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(251,191,36,0.04)'; }}
    >
      <span style={{ color: '#fbbf24', fontWeight: 600 }}>Q</span>
      <span style={{ color: 'var(--ec-text, #e5e7eb)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {quest.title}
      </span>
      <span style={{
        padding: '1px 6px', borderRadius: 3, fontSize: 9, fontWeight: 600,
        background: 'rgba(251,191,36,0.15)', color: '#fbbf24',
      }}>
        {quest.quest_type || 'quest'}
      </span>
    </div>
  );
}
