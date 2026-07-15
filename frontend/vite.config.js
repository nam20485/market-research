import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Overridable so the Vite dev server can reach the backend by its Docker
// Compose service name (`http://backend:8000`) instead of `localhost` when
// both run in containers on the same network. Defaults to plain local dev.
const backendTarget = process.env.VITE_BACKEND_URL || 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
      '/healthz': {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
})
