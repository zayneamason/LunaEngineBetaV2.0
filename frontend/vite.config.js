import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, '')
      },
      '/kozmo': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: true,
      },
      '/kozmo-assets': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/project': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/eden': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/observatory': {
        target: 'http://localhost:8100',
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/observatory/, ''),
      },
      '/persona': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/hub': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/abort': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    }
  }
})
