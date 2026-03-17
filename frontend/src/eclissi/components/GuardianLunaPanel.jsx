import React, { useRef, useEffect } from 'react';

/**
 * GuardianLunaPanel — 380px slide-in right panel for Guardian Luna.
 *
 * Shows session summaries, entity health, action recommendations, Observatory stats,
 * and a placeholder input bar (no LLM backend until Phase 6).
 */
export default function GuardianLunaPanel({ messages = [], stats, onClose, onSend, inputText = '', onInputChange }) {
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages.length]);

  const statTiles = [
    { label: 'Nodes', value: stats?.total_nodes ?? '—' },
    { label: 'Entities', value: stats?.total_entities ?? '—' },
    { label: 'Edges', value: stats?.total_edges ?? '—' },
    { label: 'Avg Lock-in', value: stats?.avg_lock_in != null ? stats.avg_lock_in.toFixed(2) : '—' },
  ];

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend?.(inputText);
    }
  };

  return (
    <div style={{
      width: 380,
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      borderLeft: '1px solid rgba(251,191,36,0.15)',
      background: 'var(--ec-bg, #0f0f14)',
      flexShrink: 0,
    }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '10px 14px',
        borderBottom: '1px solid rgba(251,191,36,0.1)',
        flexShrink: 0,
      }}>
        {/* Amber orb */}
        <div style={{
          width: 8, height: 8, borderRadius: '50%',
          background: '#fbbf24',
          boxShadow: '0 0 6px rgba(251,191,36,0.4)',
        }} />
        <span style={{
          fontSize: 11, fontWeight: 600, letterSpacing: 1,
          color: '#fbbf24', textTransform: 'uppercase',
        }}>
          Guardian Luna
        </span>
        <span style={{
          marginLeft: 4, padding: '1px 6px', borderRadius: 3,
          fontSize: 8, fontWeight: 600, textTransform: 'uppercase',
          background: 'rgba(52,211,153,0.15)', color: '#34d399',
        }}>
          OPERATIONAL
        </span>
        <button
          onClick={onClose}
          style={{
            marginLeft: 'auto', background: 'none', border: 'none',
            color: 'var(--ec-text-faint, #6b7280)', cursor: 'pointer',
            fontSize: 14, lineHeight: 1, padding: 4,
          }}
          onMouseEnter={(e) => { e.currentTarget.style.color = '#f87171'; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--ec-text-faint, #6b7280)'; }}
        >
          ×
        </button>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1, minHeight: 0, overflowY: 'auto',
        padding: '8px 12px',
        display: 'flex', flexDirection: 'column', gap: 6,
      }}>
        {messages.length === 0 && (
          <div style={{
            textAlign: 'center', padding: '24px 12px',
            color: 'var(--ec-text-faint, #6b7280)', fontSize: 11,
          }}>
            Guardian Luna monitors the knowledge pipeline.
            <br />Session data will appear here as you chat.
          </div>
        )}
        {messages.map((msg, i) => (
          <GuardianMessage key={i} msg={msg} />
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Stats Footer */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)',
        borderTop: '1px solid rgba(251,191,36,0.1)',
        flexShrink: 0,
      }}>
        {statTiles.map((tile) => (
          <div key={tile.label} style={{
            padding: '6px 0', textAlign: 'center',
            borderRight: '1px solid rgba(255,255,255,0.04)',
          }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--ec-text, #e5e7eb)' }}>
              {tile.value}
            </div>
            <div style={{ fontSize: 8, color: 'var(--ec-text-faint, #6b7280)', textTransform: 'uppercase', letterSpacing: 0.5 }}>
              {tile.label}
            </div>
          </div>
        ))}
      </div>

      {/* Input Bar */}
      <div style={{
        display: 'flex', gap: 6, padding: '8px 12px',
        borderTop: '1px solid rgba(251,191,36,0.1)',
        flexShrink: 0,
      }}>
        <input
          type="text"
          value={inputText}
          onChange={(e) => onInputChange?.(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask Guardian Luna..."
          style={{
            flex: 1, padding: '6px 10px', borderRadius: 6,
            fontSize: 12, color: 'var(--ec-text, #e5e7eb)',
            background: 'rgba(251,191,36,0.04)',
            border: '1px solid rgba(251,191,36,0.15)',
            outline: 'none',
          }}
          onFocus={(e) => { e.currentTarget.style.borderColor = 'rgba(251,191,36,0.4)'; }}
          onBlur={(e) => { e.currentTarget.style.borderColor = 'rgba(251,191,36,0.15)'; }}
        />
        <button
          onClick={() => onSend?.(inputText)}
          style={{
            padding: '6px 12px', borderRadius: 6,
            fontSize: 11, fontWeight: 600,
            background: 'rgba(251,191,36,0.15)',
            border: '1px solid rgba(251,191,36,0.3)',
            color: '#fbbf24', cursor: 'pointer',
          }}
          onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(251,191,36,0.25)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(251,191,36,0.15)'; }}
        >
          Send
        </button>
      </div>
    </div>
  );
}

/** Individual Guardian message renderer. */
function GuardianMessage({ msg }) {
  const colors = {
    summary: { bg: 'rgba(96,165,250,0.06)', border: 'rgba(96,165,250,0.15)', icon: '📊', label: 'Session' },
    health: { bg: 'rgba(244,114,182,0.06)', border: 'rgba(244,114,182,0.15)', icon: 'E', label: 'Entity' },
    action: { bg: 'rgba(251,191,36,0.06)', border: 'rgba(251,191,36,0.15)', icon: '!', label: 'Action' },
    user: { bg: 'rgba(255,255,255,0.04)', border: 'rgba(255,255,255,0.08)', icon: '>', label: 'You' },
    system: { bg: 'rgba(148,163,184,0.06)', border: 'rgba(148,163,184,0.1)', icon: '⚙', label: 'System' },
  };

  const style = colors[msg.type] || colors.system;

  return (
    <div style={{
      padding: '6px 10px', borderRadius: 6,
      background: style.bg, border: `1px solid ${style.border}`,
      fontSize: 11, color: 'var(--ec-text, #e5e7eb)',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 2 }}>
        <span style={{ fontSize: 10 }}>{style.icon}</span>
        <span style={{
          fontSize: 9, fontWeight: 600, textTransform: 'uppercase',
          color: 'var(--ec-text-faint, #6b7280)', letterSpacing: 0.5,
        }}>
          {style.label}
        </span>
        {msg.ts && (
          <span style={{ marginLeft: 'auto', fontSize: 9, color: 'var(--ec-text-faint, #6b7280)' }}>
            {new Date(msg.ts).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
          </span>
        )}
      </div>
      <div>{msg.content}</div>
    </div>
  );
}
