import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Send /api/... requests to the FastAPI backend while developing
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})