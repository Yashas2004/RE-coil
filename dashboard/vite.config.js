import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// In development (`npm run dev`), forward /api calls to the dashboard-api.
// In Docker, nginx does the same job (see nginx.conf).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: { '/api': 'http://localhost:8006' },
  },
})
