import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Local dev only. Mirrors what Nginx does in production (Section 9 of
      // the project spec): it exposes the FastAPI backend at /api/* even
      // though FastAPI itself mounts routes with no /api prefix, so strip
      // /api before forwarding.
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
