import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Read from env vars (set by launcher) or fall back to defaults
const BACKEND_PORT = process.env.LUNA_BACKEND_PORT || 8000;
const OBS_PORT = process.env.LUNA_OBSERVATORY_PORT || 8100;

const backendTarget = 'http://localhost:' + BACKEND_PORT;
const obsTarget = 'http://localhost:' + OBS_PORT;

export default defineConfig({
  plugins: [react()],
  server: {
    port: parseInt(process.env.LUNA_FRONTEND_PORT || '5173'),
    proxy: {
      // --- existing routes (preserved) ---
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/kozmo': {
        target: backendTarget,
        changeOrigin: true,
        ws: true,
      },
      '/kozmo-assets': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/project': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/eden': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/observatory': {
        target: obsTarget,
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/observatory/, ''),
      },
      '/persona': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/hub': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/abort': {
        target: backendTarget,
        changeOrigin: true,
      },
      // --- added routes ---
      '/ws': {
        target: `ws://localhost:${BACKEND_PORT}`,
        ws: true,
      },
      '/health': { target: backendTarget, changeOrigin: true },
      '/status': { target: backendTarget, changeOrigin: true },
      '/consciousness': { target: backendTarget, changeOrigin: true },
      '/message': { target: backendTarget, changeOrigin: true },
      '/stream': { target: backendTarget, changeOrigin: true },
      '/thoughts': { target: backendTarget, changeOrigin: true },
      '/interrupt': { target: backendTarget, changeOrigin: true },
      '/history': { target: backendTarget, changeOrigin: true },
      '/memory': { target: backendTarget, changeOrigin: true },
      '/entities': { target: backendTarget, changeOrigin: true },
      '/dataroom': { target: backendTarget, changeOrigin: true },
      '/state': { target: backendTarget, changeOrigin: true },
      '/extraction': { target: backendTarget, changeOrigin: true },
      '/debug': { target: backendTarget, changeOrigin: true },
      '/voice': { target: backendTarget, changeOrigin: true },
      '/identity': { target: backendTarget, changeOrigin: true },
      '/tuning': { target: backendTarget, changeOrigin: true },
      '/clusters': { target: backendTarget, changeOrigin: true },
      '/constellation': { target: backendTarget, changeOrigin: true },
      '/slash': { target: backendTarget, changeOrigin: true },
      '/llm': { target: backendTarget, changeOrigin: true },
      '/qa': { target: backendTarget, changeOrigin: true },
      '/vk': { target: backendTarget, changeOrigin: true },
      '/guardian': { target: backendTarget, changeOrigin: true },
      '/studio': { target: backendTarget, changeOrigin: true },
    }
  }
})
