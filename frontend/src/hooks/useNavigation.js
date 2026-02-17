/**
 * Cross-app navigation bus.
 *
 * Any component can call navigate() to request a view change.
 * App.jsx listens and switches modes/tabs/selections accordingly.
 */
import { create } from 'zustand'

export const useNavigation = create((set) => ({
  pending: null,

  navigate: (request) => set({ pending: { ...request, _ts: Date.now() } }),

  consume: () => set({ pending: null }),
}))
