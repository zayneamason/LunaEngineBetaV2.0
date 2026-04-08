import { create } from 'zustand'

const API = '' // proxied via vite — relative URLs hit the backend

export const useArcadeStore = create((set, get) => ({
  // ── State ──
  mode: 'sleep',
  // sleep | waking | host | game_select | playing | results | sleeping

  selectedGame: null,   // game_id string
  highlightIndex: 0,    // which card is highlighted in game_select
  lastScore: null,      // { score, medal, waves, hp_remaining, ... }
  games: [],            // from /api/arcade/all-games

  // ── Actions ──
  setMode: (mode) => set({ mode }),

  wake: () => {
    set({ mode: 'waking' })
    setTimeout(() => set({ mode: 'host' }), 2500)
  },

  returnToSleep: () => {
    set({ mode: 'sleeping' })
    setTimeout(() => set({ mode: 'sleep' }), 3000)
  },

  setHighlight: (index) => set({ highlightIndex: index }),

  selectGame: (gameId) => set({ selectedGame: gameId }),

  fetchGames: async () => {
    try {
      const res = await fetch(`${API}/api/arcade/all-games`)
      const data = await res.json()
      set({ games: data.games || [] })
    } catch (e) {
      console.warn('[arcade] Failed to fetch games:', e)
    }
  },

  launchGame: async (gameId) => {
    set({ selectedGame: gameId, mode: 'playing' })
    try {
      await fetch(`${API}/api/arcade/launch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ game_id: gameId }),
      })
    } catch (e) {
      console.warn('[arcade] Launch failed:', e)
      set({ mode: 'host' })
    }
  },

  pollStatus: async () => {
    try {
      const res = await fetch(`${API}/api/arcade/status`)
      const data = await res.json()
      return data.running
    } catch {
      return false
    }
  },

  fetchLastScore: async () => {
    try {
      const res = await fetch(`${API}/api/arcade/last-score`)
      const data = await res.json()
      if (data && data.score !== undefined) {
        set({ lastScore: data, mode: 'results' })
      } else {
        set({ lastScore: { score: 0, medal: 'bronze', waves: 0 }, mode: 'results' })
      }
    } catch {
      set({ lastScore: { score: 0, medal: 'bronze', waves: 0 }, mode: 'results' })
    }
  },

  stopGame: async () => {
    try {
      await fetch(`${API}/api/arcade/stop`, { method: 'POST' })
    } catch { /* ignore */ }
    set({ mode: 'host' })
  },
}))
