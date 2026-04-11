import React, { useState, useEffect } from 'react';
import ExpressionView from './expression/ExpressionView';
import PipelineView from './pipeline/PipelineView';
import NexusView from './nexus/NexusView';
import QAView from './qa/QAView';
import ConnectionBadge from './shared/ConnectionBadge';
import { useOrbConnection } from './expression/useOrbConnection';
import { useLiveData } from './pipeline/useLiveData';

const TABS = [
  { key: 'expression', label: 'EXPRESSION', accent: '#a78bfa' },
  { key: 'pipeline',   label: 'ENGINE PIPELINE', accent: '#818cf8' },
  { key: 'nexus',      label: 'NEXUS',     accent: '#a78bfa' },
  { key: 'qa',         label: 'QA', accent: '#f59e0b' },
];

export default function App() {
  const [activeTab, setActiveTab] = useState('expression');
  const [activeProject, setActiveProject] = useState(null);
  const { isConnected: wsConnected } = useOrbConnection();
  const { connected: httpConnected } = useLiveData(5000);

  // Check for forced view (e.g. ?view=nexus from Eclissi Nexus tab)
  const forcedView = new URLSearchParams(window.location.search).get('view');

  // Poll active project
  useEffect(() => {
    const poll = async () => {
      try {
        const res = await fetch('/api/projects');
        const data = await res.json();
        setActiveProject(data.active || null);
      } catch {}
    };
    poll();
    const id = setInterval(poll, 15000);
    return () => clearInterval(id);
  }, []);

  // Standalone mode: render only the requested view without Studio chrome
  if (forcedView === 'nexus') {
    return (
      <div style={{ width: '100vw', height: '100vh', background: '#08080f', fontFamily: "'JetBrains Mono', monospace" }}>
        <NexusView />
      </div>
    );
  }

  return (
    <div style={{ width: '100vw', height: '100vh', display: 'flex', flexDirection: 'column', background: '#08080f', fontFamily: "'JetBrains Mono', monospace" }}>
      {/* Header */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 12, padding: '10px 16px',
        borderBottom: '1px solid rgba(255,255,255,0.06)', background: '#0a0a14', flexShrink: 0,
      }}>
        <button
          onClick={() => window.parent.postMessage({ type: 'eclissi-navigate', tab: 'eclissi' }, '*')}
          style={{
            fontSize: 10, fontWeight: 600, color: '#666', letterSpacing: '0.5px',
            padding: '4px 10px', borderRadius: 5, cursor: 'pointer',
            border: '1px solid rgba(255,255,255,0.06)', background: 'rgba(255,255,255,0.03)',
            transition: 'all 0.2s', fontFamily: 'inherit',
          }}
          onMouseEnter={e => { e.target.style.color = '#e09f3e'; e.target.style.borderColor = 'rgba(224,159,62,0.3)'; }}
          onMouseLeave={e => { e.target.style.color = '#666'; e.target.style.borderColor = 'rgba(255,255,255,0.06)'; }}
        >
          ← ECLISSI
        </button>
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

        {/* Active project badge */}
        {activeProject && (
          <span style={{
            fontSize: 8, padding: '3px 8px', borderRadius: 4,
            background: 'rgba(167,139,250,0.1)', border: '1px solid rgba(167,139,250,0.25)',
            color: '#a78bfa', fontFamily: "'JetBrains Mono', monospace", letterSpacing: 0.5,
          }}>
            PROJECT: {activeProject.replace(/-/g, ' ').toUpperCase()}
          </span>
        )}

        {/* Connection badges */}
        <ConnectionBadge connected={wsConnected} label={wsConnected ? 'WS:orb' : 'WS:off'} />
        <ConnectionBadge connected={httpConnected} label={httpConnected ? 'HTTP:8000' : 'HTTP:off'} />
      </div>

      {/* Content */}
      <div style={{ flex: 1, minHeight: 0 }}>
        {activeTab === 'expression' && <ExpressionView />}
        {activeTab === 'pipeline' && <PipelineView />}
        {activeTab === 'nexus' && <NexusView />}
        {activeTab === 'qa' && <QAView />}
      </div>
    </div>
  );
}
