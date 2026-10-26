import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The built SPA is served by the FastAPI backend (frontend/dist). In dev we
// proxy /api and legacy routes to a local backend on :8000.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/health': 'http://127.0.0.1:8000',
      '/ask': 'http://127.0.0.1:8000',
      '/agents': 'http://127.0.0.1:8000',
      '/models': 'http://127.0.0.1:8000',
      '/approvals': 'http://127.0.0.1:8000',
      '/audit': 'http://127.0.0.1:8000',
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
  },
})