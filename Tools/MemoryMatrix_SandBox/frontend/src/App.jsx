import React, { useEffect, useState } from 'react'
import { useStore } from './store'
import { connectWS } from './ws'
import EntitiesView from './views/EntitiesView'
import QuestsView from './views/QuestsView'
import JournalView from './views/JournalView'
import GraphView from './views/GraphView'
import Timeline from './views/Timeline'
import Replay from './views/Replay'

const TABS = ['Entities', 'Quests', 'Journal', 'Graph', 'Timeline', 'Replay']

const tabStyle = (active) => ({
  padding: '8px 20px',
  cursor: 'pointer',
  border: 'none',
  background: active ? '#1a1a2e' : 'transparent',
  color: active ? '#7dd3fc' : '#666',
  borderBottom: active ? '2px solid #7dd3fc' : '2px solid transparent',
  fontFamily: 'inherit',
  fontSize: 13,
  transition: 'all 0.15s',
})

export default function App() {
  const [tab, setTab] = useState('Entities')
  const { wsConnected, setWsConnected, handleEvent, fetchGraph, fetchConfig, fetchEntities, fetchQuests } = useStore()

  useEffect(() => {
    // Connect WebSocket
    connectWS(handleEvent, setWsConnected)

    // Initial data fetch
    fetchGraph()
    fetchConfig()
    fetchEntities()
    fetchQuests()
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Header */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 16px',
        height: 44,
        borderBottom: '1px solid #1a1a2e',
        background: '#0a0a14',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ color: '#7dd3fc', fontWeight: 700, fontSize: 14, letterSpacing: 1 }}>
            OBSERVATORY
          </span>
          <span style={{ color: '#444', fontSize: 11 }}>Memory Matrix Sandbox</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {/* Tabs */}
          <div style={{ display: 'flex', gap: 0 }}>
            {TABS.map(t => (
              <button key={t} onClick={() => setTab(t)} style={tabStyle(tab === t)}>
                {t}
              </button>
            ))}
          </div>

          {/* Connection indicator */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 11 }}>
            <div style={{
              width: 8, height: 8, borderRadius: '50%',
              background: wsConnected ? '#4ade80' : '#ef4444',
              boxShadow: wsConnected ? '0 0 6px #4ade80' : 'none',
            }} />
            <span style={{ color: '#555' }}>
              {wsConnected ? 'LIVE' : 'OFFLINE'}
            </span>
          </div>

          {/* Refresh button */}
          <button
            onClick={fetchGraph}
            style={{
              background: '#1a1a2e',
              border: '1px solid #2a2a3e',
              color: '#888',
              padding: '4px 10px',
              cursor: 'pointer',
              fontFamily: 'inherit',
              fontSize: 11,
              borderRadius: 3,
            }}
          >
            Refresh
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {tab === 'Entities' && <EntitiesView />}
        {tab === 'Quests' && <QuestsView />}
        {tab === 'Journal' && <JournalView />}
        {tab === 'Graph' && <GraphView />}
        {tab === 'Timeline' && <Timeline />}
        {tab === 'Replay' && <Replay />}
      </div>
    </div>
  )
}
