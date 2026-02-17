/**
 * Zustand state management for Observatory (embedded in Eclissi).
 */

import { create } from 'zustand'
import { api } from './api'

const MAX_EVENTS = 500

export const useObservatoryStore = create((set, get) => ({
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

  // Graph settings (force simulation + node style)
  graphSettings: {
    // Force simulation
    chargeStrength: -30,
    linkDistance: 30,
    radialStrength: 0,
    radialRadius: 200,
    collideRadius: 0,
    alphaDecay: 0.02,
    velocityDecay: 0.3,
    cooldownTicks: 100,
    // Node style
    nodeShape: 'circle',
    nodeBaseSize: 4,
    lockInScale: 8,
    labelZoomThreshold: 1.5,
    showLockInRings: true,
    showActivationGlow: true,
    // Link style
    linkOpacity: 1,
    linkWidthScale: 1,
    // Globe
    globeStyle: 'solid',     // 'solid' | 'wireframe' | 'none'
    autoRotate: true,
    phantomCount: 2000,
    // Particles & physics
    rotationSpeed: 1,        // multiplier on auto-rotation speed
    momentumDecay: 0.96,     // how quickly drag momentum fades (0.9=fast stop, 0.99=floaty)
    phantomDrift: 1,         // multiplier on phantom drift speed
    phantomAlpha: 1,         // multiplier on phantom brightness
    phantomSize: 1,          // multiplier on phantom particle size
    twinkleSpeed: 1,         // multiplier on twinkle animation speed
    clusterScale: 1,         // multiplier on cluster/node dot sizes
    globeRadiusScale: 1,     // multiplier on globe/sphere radius
    depthFade: 1,            // how much back-facing nodes dim (0=no fade, 2=heavy fade)
    // internal trigger
    _reheat: 0,
  },

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

  // Journal entries (from data/journal/ markdown files)
  journalEntries: [],
  selectedJournalEntry: null,

  // Semantic zoom
  zoomLevel: 'universe',       // 'universe' | 'galaxy' | 'solarsystem'
  focusClusterId: null,
  focusNodeId: null,
  universeData: null,
  galaxyData: null,
  solarSystemData: null,
  isTransitioning: false,
  galaxyNodeBudget: 200,

  // ── Actions ──────────────────────────────────

  setWsConnected: (connected) => set({ wsConnected: connected }),

  selectNode: (nodeId) => set({ selectedNodeId: nodeId }),

  setGraphSettings: (settings) => set({ graphSettings: settings }),

  setGalaxyNodeBudget: (budget) => set({ galaxyNodeBudget: budget }),

  // ── Semantic Zoom Actions ─────────────────────

  fetchUniverse: async () => {
    try {
      const data = await api.zoomUniverse()
      set({ universeData: data, zoomLevel: 'universe' })
    } catch (e) {
      console.error('Failed to fetch universe:', e)
    }
  },

  fetchGalaxy: async (clusterId, limit) => {
    const budget = limit || get().galaxyNodeBudget
    set({ isTransitioning: true })
    try {
      const data = await api.zoomGalaxy(clusterId, budget)
      set({
        galaxyData: data,
        focusClusterId: clusterId,
        zoomLevel: 'galaxy',
        isTransitioning: false,
        selectedNodeId: null,
      })
    } catch (e) {
      console.error('Failed to fetch galaxy:', e)
      set({ isTransitioning: false })
    }
  },

  fetchSolarSystem: async (nodeId) => {
    set({ isTransitioning: true })
    try {
      const data = await api.zoomSolarSystem(nodeId)
      set({
        solarSystemData: data,
        focusNodeId: nodeId,
        zoomLevel: 'solarsystem',
        isTransitioning: false,
        selectedNodeId: nodeId,
      })
    } catch (e) {
      console.error('Failed to fetch solar system:', e)
      set({ isTransitioning: false })
    }
  },

  drillDown: async (type, id) => {
    if (type === 'cluster') {
      await get().fetchGalaxy(id)
    } else if (type === 'node') {
      await get().fetchSolarSystem(id)
    }
  },

  drillUp: async () => {
    const { zoomLevel, focusClusterId } = get()
    if (zoomLevel === 'solarsystem') {
      if (focusClusterId) {
        await get().fetchGalaxy(focusClusterId)
      } else {
        await get().fetchUniverse()
      }
      set({ focusNodeId: null, solarSystemData: null })
    } else if (zoomLevel === 'galaxy') {
      set({ zoomLevel: 'universe', focusClusterId: null, galaxyData: null })
    }
  },

  recomputeLayout: async () => {
    try {
      await api.recomputeLayout()
      await get().fetchUniverse()
    } catch (e) {
      console.error('Failed to recompute layout:', e)
    }
  },

  selectEntity: (entityId) => set({ selectedEntityId: entityId }),

  selectQuest: (questId) => set({ selectedQuestId: questId }),

  handleEvent: (event) => {
    const { events } = get()

    // Prepend to events (newest first), cap at MAX_EVENTS
    const newEvents = [event, ...events].slice(0, MAX_EVENTS)

    const updates = { events: newEvents }

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
      await get().fetchGraph()
      if (get().selectedQuestId === questId) {
        await get().fetchQuestDetail(questId)
      }
      return result
    } catch (e) {
      console.error('Failed to complete quest:', e)
      return null
    }
  },

  // ── Journal Actions ────────────────────────────

  fetchJournalEntries: async () => {
    try {
      const data = await api.journals()
      set({ journalEntries: data.journals || [] })
    } catch (e) {
      console.error('Failed to fetch journal entries:', e)
    }
  },

  fetchJournalDetail: async (filename) => {
    try {
      const detail = await api.journalDetail(filename)
      set({ selectedJournalEntry: detail })
    } catch (e) {
      console.error('Failed to fetch journal detail:', e)
    }
  },
}))
