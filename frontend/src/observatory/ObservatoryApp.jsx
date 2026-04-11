import React, { useState, useEffect, useCallback } from 'react'
import { useObservatoryStore } from './store'
import { connectWS, disconnectWS } from './ws'
import { useNavigation } from '../hooks/useNavigation'
import EntitiesView from './views/EntitiesView'
import QuestsView from './views/QuestsView'
import JournalView from './views/JournalView'
import ThreadsView from './views/ThreadsView'
import GraphView from './views/GraphView'
import Timeline from './views/Timeline'
import Replay from './views/Replay'
import GraphSettings from './views/GraphSettings'

const TABS = ['Entities', 'Quests', 'Threads', 'Journal', 'Graph', 'Timeline', 'Replay', 'Settings']

export default function ObservatoryApp({ onBack, activeProjectSlug }) {
  const [tab, setTab] = useState('Entities')
  const {
    wsConnected, setWsConnected, handleEvent,
    fetchGraph, fetchConfig, fetchEntities, fetchQuests, fetchThreads, fetchUniverse,
    fetchEntityDetail, selectEntity, selectQuest, selectThread, fetchSolarSystem,
  } = useObservatoryStore()
  const { pending: navPending } = useNavigation()

  useEffect(() => {
    connectWS(handleEvent, setWsConnected)
    // Fetch non-project-filtered data once
    Promise.all([
      fetchUniverse(),
      fetchGraph(),
      fetchConfig(),
    ])

    return () => {
      disconnectWS()
    }
  }, [])

  // Re-fetch project-filtered data when project changes
  useEffect(() => {
    fetchEntities(null, activeProjectSlug)
    fetchQuests(null, null, activeProjectSlug)
    fetchThreads(null, activeProjectSlug)
  }, [activeProjectSlug])

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
    if (navPending.threadId) {
      selectThread(navPending.threadId)
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
    if (selection.threadId) {
      selectThread(selection.threadId)
    }
    if (selection.nodeId) {
      fetchSolarSystem(selection.nodeId)
    }
  }, [selectEntity, fetchEntityDetail, selectQuest, selectThread, fetchSolarSystem])

  const renderTab = () => {
    switch (tab) {
      case 'Entities': return <EntitiesView navigateTab={navigateTab} activeProjectSlug={activeProjectSlug} />
      case 'Quests': return <QuestsView navigateTab={navigateTab} activeProjectSlug={activeProjectSlug} />
      case 'Threads': return <ThreadsView navigateTab={navigateTab} activeProjectSlug={activeProjectSlug} />
      case 'Journal': return <JournalView navigateTab={navigateTab} activeProjectSlug={activeProjectSlug} />
      case 'Graph': return <GraphView navigateTab={navigateTab} />
      case 'Timeline': return <Timeline navigateTab={navigateTab} />
      case 'Replay': return <Replay />
      case 'Settings': return <GraphSettings />
      default: return <EntitiesView navigateTab={navigateTab} activeProjectSlug={activeProjectSlug} />
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

          <span style={{ color: '#7dd3fc', fontWeight: 700, fontSize: 'var(--ec-fs-base)', letterSpacing: 1 }}>
            OBSERVATORY
          </span>
          <span style={{ color: '#444', fontSize: 'var(--ec-fs-xs)' }}>Memory Matrix</span>
          {activeProjectSlug && (
            <span style={{
              background: '#1a2a1e', color: '#4ade80',
              padding: '2px 8px', borderRadius: 4,
              fontSize: 'var(--ec-fs-label)', fontWeight: 600,
              letterSpacing: 0.5, textTransform: 'uppercase',
            }}>
              {activeProjectSlug}
            </span>
          )}
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
                  fontSize: 'var(--ec-fs-sm)',
                  transition: 'all 0.15s',
                }}
              >
                {t}
              </button>
            ))}
          </div>

          {/* Connection indicator */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 'var(--ec-fs-xs)' }}>
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
