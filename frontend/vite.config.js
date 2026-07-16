import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Server-only proxy target (NOT VITE_* — those are baked into client JS).
// In Docker Compose this is `http://backend:8000` (compose service DNS);
// locally it defaults to localhost. Do not confuse with VITE_BACKEND_URL,
// which is the browser-facing absolute API origin used only for the
// Cloudflare Pages production build.
const backendTarget = process.env.BACKEND_PROXY_TARGET || 'http://localhost:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.{test,spec}.{js,jsx}'],
    setupFiles: ['./src/test/setup.js'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/**/*.{test,spec}.{js,jsx}', 'src/test/**', 'src/index.css'],
      reporter: ['text', 'text-summary'],
      thresholds: {
        lines: 95,
        statements: 95,
        functions: 95,
        branches: 85,
      },
    },
  },
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
