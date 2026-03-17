import React, { useState } from 'react';

const MONO = "'JetBrains Mono','SF Mono',monospace";
const BODY = "'DM Sans',system-ui,sans-serif";

const TYPE_ICONS = { bookmark: '\uD83D\uDD16', note: '\uD83D\uDCDD', flag: '\uD83D\uDEA9' };
const TYPE_COLORS = { bookmark: '#f59e0b', note: '#a78bfa', flag: '#f87171' };
const TYPES = ['bookmark', 'note', 'flag'];

export default function AnnotationSidebar({ annotations = [], onCreateAnnotation }) {
  const [creating, setCreating] = useState(false);
  const [type, setType] = useState('note');
  const [text, setText] = useState('');

  const handleSubmit = () => {
    if (!text.trim()) return;
    onCreateAnnotation?.(type, text.trim());
    setText('');
    setCreating(false);
  };

  return (
    <div style={{ padding: '10px 12px' }}>
      <div style={{
        fontSize: 7,
        fontFamily: "'Bebas Neue',system-ui,sans-serif",
        letterSpacing: 1.5,
        color: 'var(--ec-text-muted)',
        marginBottom: 8,
      }}>LUNA'S ANNOTATIONS</div>

      {annotations.length === 0 && !creating && (
        <div style={{
          fontSize: 9, color: 'var(--ec-text-muted)',
          fontFamily: BODY, fontStyle: 'italic', padding: '8px 0',
        }}>
          No annotations yet — Luna hasn't marked anything here.
        </div>
      )}

      {annotations.map((ann, i) => (
        <div key={ann.id || i} style={{
          padding: '5px 8px', marginBottom: 3, borderRadius: 4,
          background: 'var(--ec-bg-card)',
          borderLeft: `2px solid ${TYPE_COLORS[ann.annotation_type || ann.type] || TYPE_COLORS.note}`,
          fontSize: 9, color: 'var(--ec-text-soft)', fontFamily: BODY,
        }}>
          {TYPE_ICONS[ann.annotation_type || ann.type] || '\uD83D\uDCCC'}{' '}
          {ann.content || ann.text}
        </div>
      ))}

      {creating && (
        <div style={{
          padding: '6px 8px', borderRadius: 4, marginTop: 4,
          background: 'var(--ec-bg-card)', border: '1px solid var(--ec-border)',
        }}>
          <div style={{ display: 'flex', gap: 3, marginBottom: 6 }}>
            {TYPES.map(t => (
              <div key={t} onClick={() => setType(t)} style={{
                padding: '2px 6px', borderRadius: 3, cursor: 'pointer',
                background: type === t ? `${TYPE_COLORS[t]}15` : 'transparent',
                border: `1px solid ${type === t ? `${TYPE_COLORS[t]}40` : 'var(--ec-border)'}`,
                fontSize: 8, fontFamily: MONO, color: type === t ? TYPE_COLORS[t] : 'var(--ec-text-muted)',
              }}>
                {TYPE_ICONS[t]} {t}
              </div>
            ))}
          </div>
          <input
            value={text}
            onChange={e => setText(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSubmit()}
            placeholder="Annotation text..."
            autoFocus
            style={{
              width: '100%', padding: '5px 8px', borderRadius: 4, boxSizing: 'border-box',
              background: 'var(--ec-bg-input)', border: '1px solid var(--ec-border)',
              color: 'var(--ec-text)', fontSize: 10, fontFamily: BODY, outline: 'none',
            }}
          />
          <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
            <div onClick={handleSubmit} style={{
              flex: 1, padding: '4px 0', borderRadius: 3, textAlign: 'center', cursor: 'pointer',
              background: `${TYPE_COLORS[type]}15`, border: `1px solid ${TYPE_COLORS[type]}40`,
              fontSize: 8, fontFamily: MONO, color: TYPE_COLORS[type],
            }}>SAVE</div>
            <div onClick={() => { setCreating(false); setText(''); }} style={{
              padding: '4px 8px', borderRadius: 3, cursor: 'pointer',
              border: '1px solid var(--ec-border)', fontSize: 8, fontFamily: MONO,
              color: 'var(--ec-text-muted)',
            }}>CANCEL</div>
          </div>
        </div>
      )}

      {!creating && (
        <div
          onClick={() => setCreating(true)}
          style={{
            padding: '4px 8px', borderRadius: 4,
            border: '1px dashed rgba(58,58,80,0.2)',
            textAlign: 'center', fontSize: 8,
            color: 'var(--ec-text-muted)', cursor: 'pointer',
            fontFamily: BODY, marginTop: 4,
          }}
          onMouseOver={e => { e.currentTarget.style.borderColor = '#fbbf2440'; e.currentTarget.style.color = '#fbbf24'; }}
          onMouseOut={e => { e.currentTarget.style.borderColor = 'rgba(58,58,80,0.2)'; e.currentTarget.style.color = 'var(--ec-text-muted)'; }}
        >+ annotate</div>
      )}
    </div>
  );
}
