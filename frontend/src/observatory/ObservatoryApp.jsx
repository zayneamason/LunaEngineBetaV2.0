import React, { useState, useEffect, useCallback } from 'react'
import { useObservatoryStore } from './store'
import { connectWS, disconnectWS } from './ws'
import { useNavigation } from '../hooks/useNavigation'
import EntitiesView from './views/EntitiesView'
import QuestsView from './views/QuestsView'
import JournalView from './views/JournalView'
import GraphView from './views/GraphView'
import Timeline from './views/Timeline'
import Replay from './views/Replay'
import GraphSettings from './views/GraphSettings'

const TABS = ['Entities', 'Quests', 'Journal', 'Graph', 'Timeline', 'Replay', 'Settings']

export default function ObservatoryApp({ onBack }) {
  const [tab, setTab] = useState('Entities')
  const {
    wsConnected, setWsConnected, handleEvent,
    fetchGraph, fetchConfig, fetchEntities, fetchQuests, fetchUniverse,
    fetchEntityDetail, selectEntity, selectQuest, fetchSolarSystem,
  } = useObservatoryStore()
  const { pending: navPending } = useNavigation()

  useEffect(() => {
    connectWS(handleEvent, setWsConnected)
    // Fetch data directly (production only, no DB switching)
    Promise.all([
      fetchUniverse(),
      fetchEntities(),
      fetchQuests(),
      fetchGraph(),
      fetchConfig(),
    ])

    return () => {
      disconnectWS()
    }
  }, [])

  // Handle deep-link navigation from bus
  useEffect(() => {
    if (!navPending || navPending.to !== 'observatory') return

    if (navPending.tab) {
      const tabName = navPending.tab.charAt(0).toUpperCase() + navPending.tab.slice(1)
      if (TABS.includes(tabName)) {
        setTab(tabName)
      }
    }

    if (navPending.entityId) {
      selectEntity(navPending.entityId)
      fetchEntityDetail(navPending.entityId)
    }
    if (navPending.questId) {
      selectQuest(navPending.questId)
    }
    if (navPending.nodeId) {
      fetchSolarSystem(navPending.nodeId)
    }
  }, [navPending])

  const navigateTab = useCallback((tabName, selection = {}) => {
    setTab(tabName)
    if (selection.entityId) {
      selectEntity(selection.entityId)
      fetchEntityDetail(selection.entityId)
    }
    if (selection.questId) {
      selectQuest(selection.questId)
    }
    if (selection.nodeId) {
      fetchSolarSystem(selection.nodeId)
    }
  }, [selectEntity, fetchEntityDetail, selectQuest, fetchSolarSystem])

  const renderTab = () => {
    switch (tab) {
      case 'Entities': return <EntitiesView navigateTab={navigateTab} />
      case 'Quests': return <QuestsView navigateTab={navigateTab} />
      case 'Journal': return <JournalView navigateTab={navigateTab} />
      case 'Graph': return <GraphView navigateTab={navigateTab} />
      case 'Timeline': return <Timeline navigateTab={navigateTab} />
      case 'Replay': return <Replay />
      case 'Settings': return <GraphSettings />
      default: return <EntitiesView navigateTab={navigateTab} />
    }
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      background: '#06060e',
      fontFamily: '"JetBrains Mono", "Fira Code", monospace',
      color: '#c8c8d4',
    }}>
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
          {/* Back button */}
          <button
            onClick={onBack}
            className="px-2 py-1 text-xs rounded border border-kozmo-border text-kozmo-muted hover:border-kozmo-border/80 hover:text-white transition-all"
          >
            &larr; LUNA
          </button>

          <span style={{ color: '#7dd3fc', fontWeight: 700, fontSize: 14, letterSpacing: 1 }}>
            OBSERVATORY
          </span>
          <span style={{ color: '#444', fontSize: 11 }}>Memory Matrix</span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          {/* Tabs */}
          <div style={{ display: 'flex', gap: 0 }}>
            {TABS.map(t => (
              <button
                key={t}
                onClick={() => setTab(t)}
                style={{
                  padding: '8px 20px',
                  cursor: 'pointer',
                  border: 'none',
                  background: tab === t ? '#1a1a2e' : 'transparent',
                  color: tab === t ? '#7dd3fc' : '#666',
                  borderBottom: tab === t ? '2px solid #7dd3fc' : '2px solid transparent',
                  fontFamily: 'inherit',
                  fontSize: 13,
                  transition: 'all 0.15s',
                }}
              >
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
        </div>
      </div>

      {/* Tab content */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {renderTab()}
      </div>
    </div>
  )
}
