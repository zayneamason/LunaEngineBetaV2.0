import React, { useState } from 'react';
import { TRIAGE } from './expressionData';

const tabs = {
  survives: { label: '✅ Survives (12)', color: '#4ade80' },
  absorbed: { label: '🔄 Absorbed (33)', color: '#a78bfa' },
  killed:   { label: '🚫 Killed (6)',    color: '#f87171' },
};

export default function TriagePanel({ onClose }) {
  const [tab, setTab] = useState('survives');
  const data = TRIAGE[tab] || [];

  return (
    <div style={{
      position: 'fixed', right: 0, top: 0, width: 320, height: '100vh', background: '#0c0c16',
      borderLeft: '1px solid rgba(255,255,255,0.06)', zIndex: 110,
      fontFamily: "'JetBrains Mono', monospace",
      boxShadow: '-6px 0 24px rgba(0,0,0,0.5)', display: 'flex', flexDirection: 'column',
    }}>
      <div style={{ padding: '10px 12px', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 11, fontWeight: 600, color: '#fb7185' }}>⚡ GESTURE TRIAGE</span>
          <span onClick={onClose} style={{ cursor: 'pointer', color: '#555', fontSize: 13 }}>✕</span>
        </div>
        <div style={{ fontSize: 8, color: '#555', marginTop: 2 }}>56 → 12 survive · 33 absorbed · 6 killed</div>
        <div style={{ display: 'flex', gap: 4, marginTop: 7 }}>
          {Object.entries(tabs).map(([k, v]) => (
            <div key={k} onClick={() => setTab(k)} style={{
              fontSize: 8, padding: '3px 7px', borderRadius: 4, cursor: 'pointer',
              background: tab === k ? `${v.color}15` : 'rgba(255,255,255,0.03)',
              color: tab === k ? v.color : '#555',
              border: `1px solid ${tab === k ? v.color + '33' : 'rgba(255,255,255,0.05)'}`,
            }}>{v.label}</div>
          ))}
        </div>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', padding: '6px 12px' }}>
        {data.map((item, i) => (
          <div key={i} style={{
            padding: '7px 9px', marginBottom: 3, borderRadius: 5,
            background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.04)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 2 }}>
              <span style={{ fontSize: 10, color: tabs[tab].color, fontWeight: 600 }}>{item.gesture}</span>
              {tab === 'survives' && <span style={{ fontSize: 8, color: '#666', marginLeft: 'auto' }}>{item.anim}</span>}
              {tab === 'absorbed' && <span style={{ fontSize: 8, color: '#818cf8', marginLeft: 'auto' }}>→ {item.by}</span>}
            </div>
            <div style={{ fontSize: 8.5, color: '#555', lineHeight: 1.4 }}>{item.why}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
