import React from 'react';
import { useNavigation } from '../hooks/useNavigation';

const STATE_COLORS = {
  personal: '#60a5fa',
  project: '#34d399',
  bridge: '#fbbf24',
  mixed: '#c084fc',
};

/**
 * ContextStrip — horizontal strip below the chat header showing life state,
 * active entity tags, and session duration.
 */
export default function ContextStrip({ consciousness, entities = [], sessionStart }) {
  const { navigate } = useNavigation();

  const mood = consciousness?.mood || 'project';
  const stateColor = STATE_COLORS[mood] || STATE_COLORS.project;

  // Session duration
  let duration = '';
  if (sessionStart) {
    const elapsed = Math.floor((Date.now() - new Date(sessionStart).getTime()) / 1000);
    if (elapsed < 60) duration = `${elapsed}s`;
    else if (elapsed < 3600) duration = `${Math.floor(elapsed / 60)}m`;
    else duration = `${Math.floor(elapsed / 3600)}h ${Math.floor((elapsed % 3600) / 60)}m`;
  }

  // Limit visible entities
  const visibleEntities = entities.slice(0, 6);

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      gap: 8,
      height: 28,
      padding: '0 4px',
      fontSize: 11,
      color: 'var(--ec-text-faint, #6b7280)',
      flexShrink: 0,
      overflow: 'hidden',
    }}>
      {/* Life state pill */}
      <span style={{
        padding: '2px 8px',
        borderRadius: 10,
        fontSize: 10,
        fontWeight: 600,
        background: `${stateColor}15`,
        color: stateColor,
        textTransform: 'uppercase',
        letterSpacing: '0.5px',
      }}>
        {mood}
      </span>

      {/* Separator */}
      {visibleEntities.length > 0 && (
        <span style={{ opacity: 0.3 }}>|</span>
      )}

      {/* Entity tags */}
      <div style={{ display: 'flex', gap: 4, overflow: 'hidden', flex: 1 }}>
        {visibleEntities.map((e) => (
          <span
            key={e.id || e.name}
            onClick={() => navigate({ to: 'observatory', tab: 'entities', entityId: e.id })}
            style={{
              padding: '1px 6px',
              borderRadius: 3,
              fontSize: 10,
              background: 'rgba(255,255,255,0.05)',
              color: 'var(--ec-text-faint, #9ca3af)',
              cursor: 'pointer',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: 100,
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.1)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.05)'; }}
            title={e.name}
          >
            {e.name}
          </span>
        ))}
        {entities.length > 6 && (
          <span style={{ fontSize: 10, opacity: 0.5 }}>+{entities.length - 6}</span>
        )}
      </div>

      {/* Session duration */}
      {duration && (
        <>
          <span style={{ opacity: 0.3 }}>|</span>
          <span style={{ whiteSpace: 'nowrap' }}>{duration}</span>
        </>
      )}
    </div>
  );
}
