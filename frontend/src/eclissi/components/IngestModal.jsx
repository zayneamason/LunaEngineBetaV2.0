import React, { useState } from 'react';

const MONO = "'JetBrains Mono','SF Mono',monospace";
const LABEL = "'Bebas Neue',system-ui,sans-serif";

export default function IngestModal({ collection, onClose, onIngest }) {
  const [mode, setMode] = useState('directory');
  const [path, setPath] = useState('');
  const [recursive, setRecursive] = useState(true);

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
    }} onClick={onClose}>
      <div style={{
        width: 420, background: 'var(--ec-bg-panel)', borderRadius: 14,
        border: `1px solid ${collection.color}30`, overflow: 'hidden',
        boxShadow: '0 20px 60px rgba(0,0,0,0.6)',
      }} onClick={e => e.stopPropagation()}>
        <div style={{
          padding: '14px 18px', borderBottom: '1px solid var(--ec-border)',
          display: 'flex', alignItems: 'center', gap: 8,
        }}>
          <div style={{ width: 3, height: 16, borderRadius: 2, background: collection.color }} />
          <span style={{ fontFamily: LABEL, fontSize: 11, letterSpacing: 2, color: collection.color }}>
            INGEST → {collection.key.toUpperCase()}
          </span>
          <div style={{ flex: 1 }} />
          <div onClick={onClose} style={{ cursor: 'pointer', color: 'var(--ec-text-faint)', fontSize: 13 }}>{'\u2715'}</div>
        </div>
        <div style={{ padding: 18, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ display: 'flex', gap: 4 }}>
            {['directory', 'file', 'url'].map(m => (
              <div key={m} onClick={() => setMode(m)} style={{
                padding: '4px 10px', borderRadius: 5, cursor: 'pointer',
                background: mode === m ? `${collection.color}15` : 'transparent',
                border: `1px solid ${mode === m ? `${collection.color}40` : 'var(--ec-border)'}`,
                fontSize: 9, fontFamily: MONO, color: mode === m ? collection.color : 'var(--ec-text-faint)',
                textTransform: 'uppercase',
              }}>{m}</div>
            ))}
          </div>
          <input value={path} onChange={e => setPath(e.target.value)}
            placeholder={mode === 'directory' ? '/path/to/documents' : mode === 'file' ? '/path/to/file.pdf' : 'https://...'}
            style={{
              width: '100%', padding: '8px 12px', borderRadius: 6, boxSizing: 'border-box',
              background: 'var(--ec-bg-input)', border: '1px solid var(--ec-border)',
              color: 'var(--ec-text)', fontSize: 11, fontFamily: MONO, outline: 'none',
            }}
          />
          {mode === 'directory' && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div onClick={() => setRecursive(!recursive)} style={{
                width: 28, height: 14, borderRadius: 7, cursor: 'pointer',
                background: recursive ? 'rgba(52,211,153,0.25)' : 'rgba(58,58,80,0.3)',
                border: `1px solid ${recursive ? '#34d399' : 'var(--ec-border)'}`,
                position: 'relative',
              }}>
                <div style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: recursive ? '#34d399' : 'var(--ec-text-faint)',
                  position: 'absolute', top: 2, left: recursive ? 16 : 2,
                  transition: 'all 0.2s',
                }} />
              </div>
              <span style={{ fontSize: 9, color: 'var(--ec-text-soft)' }}>Recursive</span>
            </div>
          )}
          <div onClick={() => { if (path) { onIngest(collection.key, mode, path); onClose(); }}} style={{
            padding: '9px 0', borderRadius: 6, textAlign: 'center',
            cursor: path ? 'pointer' : 'default',
            background: path ? `${collection.color}20` : 'rgba(58,58,80,0.08)',
            border: `1px solid ${path ? `${collection.color}40` : 'var(--ec-border)'}`,
            fontSize: 10, fontFamily: LABEL, letterSpacing: 2,
            color: path ? collection.color : 'var(--ec-text-muted)',
          }}>{'\u25B6'} BEGIN INGEST</div>
        </div>
      </div>
    </div>
  );
}
