/**
 * REST client for Observatory backend /api/* endpoints.
 */

const BASE = 'http://localhost:8100'

async function fetchJSON(path, opts = {}) {
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json()
}

export const api = {
  graphDump: (limit = 500, minLockIn = 0) =>
    fetchJSON(`/api/graph-dump?limit=${limit}&min_lock_in=${minLockIn}`),

  stats: () => fetchJSON('/api/stats'),

  eventsRecent: (n = 50, typeFilter = null) => {
    let url = `/api/events/recent?n=${n}`
    if (typeFilter) url += `&type_filter=${typeFilter}`
    return fetchJSON(url)
  },

  config: () => fetchJSON('/api/config'),

  replay: (query) =>
    fetchJSON('/api/replay', {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: `query=${encodeURIComponent(query)}`,
    }),

  // Entity endpoints
  entities: (typeFilter = null) => {
    let url = '/api/entities'
    if (typeFilter) url += `?type=${typeFilter}`
    return fetchJSON(url)
  },

  entityDetail: (entityId) => fetchJSON(`/api/entities/${entityId}`),

  // Quest endpoints
  quests: (filters = {}) => {
    const params = new URLSearchParams()
    if (filters.status) params.append('status', filters.status)
    if (filters.type) params.append('type', filters.type)
    const query = params.toString()
    return fetchJSON(`/api/quests${query ? '?' + query : ''}`)
  },

  questDetail: (questId) => fetchJSON(`/api/quests/${questId}`),

  maintenanceSweep: () =>
    fetchJSON('/api/maintenance-sweep', { method: 'POST' }),

  questAccept: (questId) =>
    fetchJSON(`/api/quests/${questId}/accept`, { method: 'POST' }),

  questComplete: (questId, body) =>
    fetchJSON(`/api/quests/${questId}/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
}
