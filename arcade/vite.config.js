import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const backendUrl = process.env.VITE_BACKEND_URL || 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5175,
    proxy: {
      '/api': { target: backendUrl, changeOrigin: true },
      '/stream': { target: backendUrl, changeOrigin: true },
      '/message': { target: backendUrl, changeOrigin: true },
      '/ws': { target: backendUrl, ws: true, changeOrigin: true },
    },
  },
})
