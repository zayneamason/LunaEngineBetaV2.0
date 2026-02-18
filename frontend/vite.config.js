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
      '/api': {
        target: backendTarget,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
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
    }
  }
})
