import React, { useState } from 'react';

const MONO = "'JetBrains Mono','SF Mono',monospace";
const BODY = "'DM Sans',system-ui,sans-serif";
const LABEL = "'Bebas Neue',system-ui,sans-serif";

export default function NewCollectionModal({ onClose, onCreate }) {
  const [name, setName] = useState('');
  const [desc, setDesc] = useState('');
  const [tags, setTags] = useState('');

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }} onClick={onClose}>
      <div style={{
        width: 400, background: 'var(--ec-bg-panel)', borderRadius: 14,
        border: '1px solid rgba(192,132,252,0.19)', overflow: 'hidden',
        boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
      }} onClick={e => e.stopPropagation()}>
        <div style={{
          padding: '14px 18px', borderBottom: '1px solid var(--ec-border)',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <div style={{ width: 3, height: 16, borderRadius: 2, background: 'var(--ec-accent-luna)' }} />
          <span style={{ fontFamily: LABEL, fontSize: 11, letterSpacing: 2, color: 'var(--ec-accent-luna)' }}>NEW COLLECTION</span>
          <div style={{ flex: 1 }} />
          <div onClick={onClose} style={{ cursor: 'pointer', color: 'var(--ec-text-faint)' }}>{'\u2715'}</div>
        </div>
        <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 12 }}>
          {[
            { label: 'ID', val: name, set: v => setName(v.toLowerCase().replace(/\s/g, '_')), ph: 'collection_id', mono: true },
            { label: 'DESCRIPTION', val: desc, set: setDesc, ph: 'What is this collection for?', mono: false },
            { label: 'TAGS', val: tags, set: setTags, ph: 'tag1, tag2, tag3', mono: true },
          ].map(f => (
            <div key={f.label}>
              <div style={{ fontSize: 7, fontFamily: LABEL, letterSpacing: 1.5, color: 'var(--ec-text-muted)', marginBottom: 4 }}>{f.label}</div>
              <input value={f.val} onChange={e => f.set(e.target.value)} placeholder={f.ph} style={{
                width: '100%', padding: '7px 10px', borderRadius: 6, boxSizing: 'border-box',
                background: 'var(--ec-bg-input)', border: '1px solid var(--ec-border)',
                color: 'var(--ec-text)', fontSize: 11, fontFamily: f.mono ? MONO : BODY, outline: 'none',
              }} />
            </div>
          ))}

          <div style={{
            fontSize: 8, fontFamily: BODY, color: 'var(--ec-text-muted)', fontStyle: 'italic',
            padding: '6px 8px', borderRadius: 4,
            background: 'rgba(251,191,36,0.04)', borderLeft: '2px solid rgba(251,191,36,0.25)',
          }}>
            Collections are configured in the engine registry. This creates a UI placeholder.
          </div>

          <div onClick={() => { if (name) { onCreate?.(name, desc, tags); onClose(); }}} style={{
            padding: '9px 0', borderRadius: 6, textAlign: 'center',
            cursor: name ? 'pointer' : 'default',
            background: name ? 'rgba(192,132,252,0.12)' : 'rgba(58,58,80,0.08)',
            border: `1px solid ${name ? 'rgba(192,132,252,0.25)' : 'var(--ec-border)'}`,
            fontSize: 10, fontFamily: LABEL, letterSpacing: 2,
            color: name ? 'var(--ec-accent-luna)' : 'var(--ec-text-muted)',
          }}>CREATE</div>
        </div>
      </div>
    </div>
  );
}
