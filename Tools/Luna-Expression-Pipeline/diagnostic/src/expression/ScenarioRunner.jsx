import React from 'react';
import { SCENARIOS } from './expressionData';

export default function ScenarioRunner({ simActive, simName, onRunSim, onShowTriage, showTriage }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 4, flexWrap: 'wrap',
      fontFamily: "'JetBrains Mono', monospace",
    }}>
      <div style={{ fontSize: 8, color: '#555', marginRight: 2 }}>▶</div>
      {Object.entries(SCENARIOS).map(([k, sc]) => (
        <div key={k} onClick={() => !simActive && onRunSim(k)} style={{
          fontSize: 8, padding: '3px 8px', borderRadius: 5,
          cursor: simActive ? 'not-allowed' : 'pointer',
          background: simActive ? 'rgba(255,255,255,0.02)' : `${sc.color}08`,
          color: simActive ? '#333' : sc.color,
          border: `1px solid ${simActive ? 'rgba(255,255,255,0.04)' : sc.color + '33'}`,
        }}>{sc.label}</div>
      ))}
      <div style={{ flex: 1 }} />
      <div onClick={onShowTriage} style={{
        fontSize: 9, padding: '3px 10px', borderRadius: 5, cursor: 'pointer',
        background: showTriage ? 'rgba(251,113,133,0.12)' : 'rgba(255,255,255,0.04)',
        color: showTriage ? '#fb7185' : '#666',
        border: `1px solid ${showTriage ? 'rgba(251,113,133,0.3)' : 'rgba(255,255,255,0.06)'}`,
      }}>⚡ {showTriage ? 'HIDE' : 'VIEW'} TRIAGE</div>
      {simActive && (
        <div style={{
          fontSize: 10, padding: '4px 12px', borderRadius: 14,
          background: 'rgba(167,139,250,0.08)', color: '#a78bfa',
          border: '1px solid rgba(167,139,250,0.2)',
          display: 'flex', alignItems: 'center', gap: 6,
        }}>
          <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#a78bfa', animation: 'lp 0.8s infinite' }} />
          {simName}
        </div>
      )}
    </div>
  );
}
