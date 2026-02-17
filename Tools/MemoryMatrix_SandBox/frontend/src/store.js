/**
 * Zustand state management for Observatory frontend.
 */

import { create } from 'zustand'
import { api } from './api'

const MAX_EVENTS = 500

export const useStore = create((set, get) => ({
  // Graph data
  nodes: [],
  edges: [],
  clusters: [],

  // Selection
  selectedNodeId: null,

  // Events
  events: [],

  // Replay
  replayResult: null,
  replayPhaseIndex: -1,
  activatedNodeIds: new Set(),

  // Config
  params: {},

  // Connection
  wsConnected: false,

  // Entities
  entities: [],
  entityRelationships: [],
  selectedEntityId: null,
  entityDetail: null,

  // Quests
  quests: [],
  selectedQuestId: null,
  questDetail: null,

  // ── Actions ──────────────────────────────────

  setWsConnected: (connected) => set({ wsConnected: connected }),

  selectNode: (nodeId) => set({ selectedNodeId: nodeId }),

  selectEntity: (entityId) => set({ selectedEntityId: entityId }),

  selectQuest: (questId) => set({ selectedQuestId: questId }),

  handleEvent: (event) => {
    const { events, nodes, edges } = get()

    // Prepend to events (newest first), cap at MAX_EVENTS
    const newEvents = [event, ...events].slice(0, MAX_EVENTS)

    // Incremental graph updates from events
    const updates = { events: newEvents }

    if (event.type === 'node_created' && event.payload) {
      // Could add node to graph — but we'd need full node data
      // For now, just record the event. Full refresh on demand.
    }

    if (event.type === 'edge_added' && event.payload) {
      // Same — event has edge info but not full node data
    }

    if (event.type === 'sandbox_reset') {
      updates.nodes = []
      updates.edges = []
      updates.clusters = []
      updates.selectedNodeId = null
      updates.replayResult = null
      updates.activatedNodeIds = new Set()
    }

    if (event.type === 'sandbox_seeded') {
      // Trigger a full graph refresh
      get().fetchGraph()
    }

    set(updates)
  },

  fetchGraph: async () => {
    try {
      const data = await api.graphDump()
      set({
        nodes: data.nodes || [],
        edges: data.edges || [],
        clusters: data.clusters || [],
      })
    } catch (e) {
      console.error('Failed to fetch graph:', e)
    }
  },

  fetchStats: async () => {
    try {
      return await api.stats()
    } catch (e) {
      console.error('Failed to fetch stats:', e)
      return null
    }
  },

  fetchConfig: async () => {
    try {
      const params = await api.config()
      set({ params })
    } catch (e) {
      console.error('Failed to fetch config:', e)
    }
  },

  runReplay: async (query) => {
    try {
      const result = await api.replay(query)
      set({
        replayResult: result,
        replayPhaseIndex: 0,
        activatedNodeIds: new Set(),
      })
      return result
    } catch (e) {
      console.error('Replay failed:', e)
      return null
    }
  },

  setReplayPhase: (index) => {
    const { replayResult } = get()
    if (!replayResult || !replayResult.phases) return

    const phase = replayResult.phases[index]
    if (!phase) return

    // Collect all node IDs mentioned up to this phase
    const activated = new Set()
    for (let i = 0; i <= index; i++) {
      const p = replayResult.phases[i]
      if (p.results) {
        p.results.forEach(r => activated.add(r.id))
      }
    }

    set({ replayPhaseIndex: index, activatedNodeIds: activated })
  },

  clearReplay: () => set({
    replayResult: null,
    replayPhaseIndex: -1,
    activatedNodeIds: new Set(),
  }),

  // ── Entity Actions ───────────────────────────

  fetchEntities: async (typeFilter = null) => {
    try {
      const data = await api.entities(typeFilter)
      set({ entities: data.entities || [] })
    } catch (e) {
      console.error('Failed to fetch entities:', e)
    }
  },

  fetchEntityDetail: async (entityId) => {
    try {
      const detail = await api.entityDetail(entityId)
      set({ entityDetail: detail, selectedEntityId: entityId })
    } catch (e) {
      console.error('Failed to fetch entity detail:', e)
    }
  },

  // ── Quest Actions ────────────────────────────

  fetchQuests: async (status = null, type = null) => {
    try {
      const data = await api.quests({ status, type })
      set({ quests: data.quests || [] })
    } catch (e) {
      console.error('Failed to fetch quests:', e)
    }
  },

  fetchQuestDetail: async (questId) => {
    try {
      const detail = await api.questDetail(questId)
      set({ questDetail: detail, selectedQuestId: questId })
    } catch (e) {
      console.error('Failed to fetch quest detail:', e)
    }
  },

  runMaintenanceSweep: async () => {
    try {
      const result = await api.maintenanceSweep()
      // Refresh quests after sweep
      await get().fetchQuests()
      return result
    } catch (e) {
      console.error('Failed to run maintenance sweep:', e)
      return null
    }
  },

  acceptQuest: async (questId) => {
    try {
      await api.questAccept(questId)
      await get().fetchQuests()
      if (get().selectedQuestId === questId) {
        await get().fetchQuestDetail(questId)
      }
    } catch (e) {
      console.error('Failed to accept quest:', e)
    }
  },

  completeQuest: async (questId, journalText, themes) => {
    try {
      const result = await api.questComplete(questId, { journal_text: journalText, themes })
      await get().fetchQuests()
      await get().fetchGraph() // Refresh graph (new INSIGHT node may have been created)
      if (get().selectedQuestId === questId) {
        await get().fetchQuestDetail(questId)
      }
      return result
    } catch (e) {
      console.error('Failed to complete quest:', e)
      return null
    }
  },
}))
