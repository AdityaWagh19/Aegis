import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3000,
    strictPort: true,
    proxy: {
      // mirrors the nginx routes so dev uses the same relative API paths
      '/api': 'http://localhost:8000',
      '/webhooks': 'http://localhost:8000',
    },
  },
})
