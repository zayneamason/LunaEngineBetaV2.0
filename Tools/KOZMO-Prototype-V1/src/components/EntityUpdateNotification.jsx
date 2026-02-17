/**
 * EntityUpdateNotification Component (Phase 4)
 *
 * Shows toast notification when an entity is updated by another user.
 * Auto-dismisses after 5 seconds.
 */
import React, { useState, useEffect } from 'react';

export function EntityUpdateNotification({ update, onClose, onViewChanges }) {
  const [countdown, setCountdown] = useState(5);

  useEffect(() => {
    const timer = setInterval(() => {
      setCountdown(c => {
        if (c <= 1) {
          onClose();
          return 0;
        }
        return c - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [onClose]);

  const { entity, changes, affected_scenes } = update;

  return (
    <div style={{
      position: 'fixed',
      bottom: 20,
      right: 20,
      background: 'rgba(13, 13, 24, 0.6)',
      backdropFilter: 'blur(20px)',
      WebkitBackdropFilter: 'blur(20px)',
      border: '1px solid #60a5fa40',
      borderRadius: 8,
      padding: 16,
      minWidth: 320,
      maxWidth: 400,
      zIndex: 1000,
      boxShadow: '0 4px 12px rgba(0,0,0,0.4)'
    }}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12 }}>
        <div style={{
          width: 12,
          height: 12,
          borderRadius: '50%',
          background: entity?.color || '#60a5fa',
          flexShrink: 0,
          marginTop: 4
        }} />

        <div style={{ flex: 1 }}>
          <div style={{
            color: '#e2e8f0',
            fontSize: 14,
            fontWeight: 600,
            marginBottom: 4
          }}>
            Entity Updated: {entity?.name || 'Unknown'}
          </div>

          <div style={{
            color: '#94a3b8',
            fontSize: 12,
            marginBottom: 8
          }}>
            Changed: {changes?.join(', ') || 'unknown'}
          </div>

          {affected_scenes && affected_scenes.length > 0 && (
            <div style={{
              color: '#64748b',
              fontSize: 11,
              fontFamily: "'JetBrains Mono', monospace",
              marginBottom: 12
            }}>
              {affected_scenes.length} scene{affected_scenes.length !== 1 ? 's' : ''} affected
            </div>
          )}

          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={onViewChanges}
              style={{
                padding: '6px 12px',
                background: '#60a5fa',
                border: 'none',
                borderRadius: 4,
                color: '#08080e',
                fontSize: 11,
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              View Entity
            </button>
            <button
              onClick={onClose}
              style={{
                padding: '6px 12px',
                background: 'transparent',
                border: '1px solid #2a2a3a',
                borderRadius: 4,
                color: '#64748b',
                fontSize: 11,
                cursor: 'pointer'
              }}
            >
              Dismiss ({countdown}s)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
