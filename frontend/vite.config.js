import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
// Django + WhiteNoise serves the Vite bundle under STATIC_URL (`/static/`); set VITE_STATIC_BASE=/static/ during build_render.sh.
export default defineConfig({
  base: process.env.VITE_STATIC_BASE || '/',
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})






