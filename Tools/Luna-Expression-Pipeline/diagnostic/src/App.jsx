import React, { useState } from 'react';
import ExpressionView from './expression/ExpressionView';
import PipelineView from './pipeline/PipelineView';
import AibrarianView from './aibrarian/AibrarianView';
import ConnectionBadge from './shared/ConnectionBadge';
import { useOrbConnection } from './expression/useOrbConnection';
import { useLiveData } from './pipeline/useLiveData';

const TABS = [
  { key: 'expression', label: 'EXPRESSION', accent: '#a78bfa' },
  { key: 'pipeline',   label: 'ENGINE PIPELINE', accent: '#818cf8' },
  { key: 'aibrarian',  label: 'AIBRARIAN', accent: '#34d399' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('expression');
  const { isConnected: wsConnected } = useOrbConnection();
  const { connected: httpConnected } = useLiveData(5000);

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column', background: '#08080f', fontFamily: "'JetBrains Mono', monospace" }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px',
        borderBottom: '1px solid rgba(255,255,255,0.06)', background: '#0a0a14', flexShrink: 0,
      }}>
        <a href="/" style={{
          fontSize: 10, fontWeight: 600, color: '#666', letterSpacing: '0.5px',
          textDecoration: 'none', padding: '4px 10px', borderRadius: 5,
          border: '1px solid rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.03)',
          transition: 'all 0.2s',
        }}
          onMouseEnter={e => { e.target.style.color = '#e09f3e'; e.target.style.borderColor = 'rgba(224,159,62,0.3)'; }}
          onMouseLeave={e => { e.target.style.color = '#666'; e.target.style.borderColor = 'rgba(255,255,255,0.06)'; }}
        >
          ← ECLISSI
        </a>
        <div style={{ fontSize: 12, fontWeight: 700, color: '#e0e0f0', letterSpacing: '0.5px' }}>
          ◈ LUNAR STUDIO
        </div>

        {/* Tab buttons */}
        <div style={{ display: 'flex', gap: 4, marginLeft: 16 }}>
          {TABS.map(tab => (
            <div key={tab.key} onClick={() => setActiveTab(tab.key)} style={{
              fontSize: 9, padding: '4px 12px', borderRadius: 5, cursor: 'pointer',
              background: activeTab === tab.key ? `${tab.accent}15` : 'rgba(255,255,255,0.03)',
              color: activeTab === tab.key ? tab.accent : '#555',
              border: `1px solid ${activeTab === tab.key ? tab.accent + '33' : 'rgba(255,255,255,0.06)'}`,
              transition: 'all 0.2s',
            }}>{tab.label}</div>
          ))}
        </div>

        <div style={{ flex: 1 }} />

        {/* Connection badges */}
        <ConnectionBadge connected={wsConnected} label={wsConnected ? 'WS:orb' : 'WS:off'} />
        <ConnectionBadge connected={httpConnected} label={httpConnected ? 'HTTP:8000' : 'HTTP:off'} />
      </div>

      {/* Content */}
      <div style={{ flex: 1, minHeight: 0 }}>
        {activeTab === 'expression' && <ExpressionView />}
        {activeTab === 'pipeline' && <PipelineView />}
        {activeTab === 'aibrarian' && <AibrarianView />}
      </div>
    </div>
  );
}
