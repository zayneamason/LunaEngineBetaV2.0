import React, { useState, useEffect, useRef } from 'react';

/**
 * KozmoChat — Shared chat component for KOZMO modes
 *
 * Props:
 *   messages     - Array of { id, role, content, streaming, delegated, local, latency, tokens, error }
 *   isStreaming   - Boolean, whether Luna is generating
 *   onSend       - (text: string) => void
 *   onStop       - () => void (optional, abort generation)
 *   placeholder  - Input placeholder text
 *   agents       - Optional agent roster array [{ id, name, avatar, color, status }]
 */
export default function KozmoChat({ messages, isStreaming, onSend, onStop, placeholder, agents }) {
  const [input, setInput] = useState('');
  const chatEnd = useRef(null);

  useEffect(() => {
    chatEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!input.trim() || isStreaming) return;
    onSend(input.trim());
    setInput('');
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Agent Roster */}
      {agents && agents.length > 0 && (
        <div style={{
          padding: '8px 12px', borderBottom: '1px solid #1e1e30',
          display: 'flex', gap: 6, flexWrap: 'wrap',
        }}>
          {agents.map(a => (
            <div key={a.id} style={{
              display: 'flex', alignItems: 'center', gap: 4, padding: '3px 8px',
              borderRadius: 3, background: a.status === 'active' ? a.color + '15' : 'transparent',
              border: `1px solid ${a.status === 'active' ? a.color + '40' : '#282840'}`,
            }}>
              <span style={{ fontSize: 11 }}>{a.avatar}</span>
              <span style={{
                color: a.status === 'active' ? a.color : '#5a5a6e',
                fontSize: 10, fontFamily: "'JetBrains Mono', monospace",
              }}>
                {a.name}
              </span>
              <span style={{
                width: 5, height: 5, borderRadius: '50%',
                background: a.status === 'active' ? a.color : '#3a3a4e',
              }} />
            </div>
          ))}
        </div>
      )}

      {/* Messages */}
      <div style={{ flex: 1, overflow: 'auto', padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {messages.length === 0 && (
          <div style={{
            fontSize: 10, color: '#24243a', fontStyle: 'italic', padding: 8, textAlign: 'center', paddingTop: 24,
          }}>
            {placeholder || 'Talk to Luna about your project...'}
          </div>
        )}

        {messages.map(msg => {
          const isUser = msg.role === 'user';
          return (
            <div key={msg.id} style={{
              display: 'flex', flexDirection: 'column',
              alignItems: isUser ? 'flex-end' : 'flex-start',
            }}>
              {/* Agent label */}
              {!isUser && (
                <div style={{
                  display: 'flex', alignItems: 'center', gap: 4, marginBottom: 3,
                }}>
                  <span style={{ fontSize: 7, color: '#818cf8', letterSpacing: 1 }}>LUNA</span>
                  {msg.streaming && (
                    <span style={{ fontSize: 7, color: '#c8ff00', letterSpacing: 1 }}>STREAMING</span>
                  )}
                </div>
              )}

              {/* Bubble */}
              <div style={{
                padding: '8px 12px', maxWidth: '92%',
                borderRadius: isUser ? '10px 10px 2px 10px' : '10px 10px 10px 2px',
                background: msg.error
                  ? 'rgba(248, 113, 113, 0.1)'
                  : isUser
                  ? 'rgba(192, 132, 252, 0.12)'
                  : 'rgba(24, 15, 42, 0.8)',
                border: `1px solid ${
                  msg.error ? '#f8717130' : isUser ? '#c084fc20' : '#818cf815'
                }`,
              }}>
                <span style={{
                  color: msg.error ? '#f87171' : isUser ? '#e2e8f0' : '#9ca3af',
                  fontSize: 11, lineHeight: 1.5, whiteSpace: 'pre-wrap',
                }}>
                  {msg.content}
                  {msg.streaming && !msg.content && (
                    <span className="animate-pulse" style={{ color: '#818cf8' }}>...</span>
                  )}
                </span>
              </div>

              {/* Metadata badge */}
              {!isUser && !msg.streaming && msg.latency && (
                <div style={{
                  display: 'flex', gap: 6, marginTop: 3,
                  fontSize: 8, color: '#3a3a4e',
                }}>
                  {msg.delegated && <span style={{ color: '#c084fc80' }}>cloud</span>}
                  {msg.local && <span style={{ color: '#4ade8080' }}>local</span>}
                  {msg.latency && <span>{(msg.latency / 1000).toFixed(1)}s</span>}
                  {msg.tokens && <span>{msg.tokens}tok</span>}
                </div>
              )}
            </div>
          );
        })}
        <div ref={chatEnd} />
      </div>

      {/* Input Bar */}
      <div style={{ padding: '8px 12px', borderTop: '1px solid #1e1e30', display: 'flex', gap: 6 }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSend()}
          placeholder={isStreaming ? 'Luna is thinking...' : (placeholder || 'Talk to Luna...')}
          disabled={isStreaming}
          style={{
            flex: 1, padding: '6px 10px', background: '#18182a',
            border: '1px solid #24243a', borderRadius: 4, color: '#c8cad0',
            fontFamily: 'inherit', fontSize: 10, outline: 'none',
            opacity: isStreaming ? 0.5 : 1,
          }}
          onFocus={e => { e.target.style.borderColor = '#818cf830'; }}
          onBlur={e => { e.target.style.borderColor = '#24243a'; }}
        />
        {isStreaming ? (
          <button
            onClick={onStop}
            style={{
              padding: '6px 10px', borderRadius: 4, border: 'none',
              background: '#f8717130', color: '#f87171',
              fontWeight: 700, fontSize: 9, cursor: 'pointer', fontFamily: 'inherit',
            }}
          >
            Stop
          </button>
        ) : (
          <button
            onClick={handleSend}
            disabled={!input.trim()}
            style={{
              padding: '6px 10px', borderRadius: 4, border: 'none',
              background: input.trim() ? '#818cf8' : '#24243a',
              color: '#12121c', fontWeight: 700,
              fontSize: 9, cursor: input.trim() ? 'pointer' : 'not-allowed',
              fontFamily: 'inherit',
            }}
          >
            ↵
          </button>
        )}
      </div>
    </div>
  );
}
