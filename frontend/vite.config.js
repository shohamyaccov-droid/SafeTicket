import { copyFileSync, existsSync, rmSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

const __dirname = dirname(fileURLToPath(import.meta.url));
const fileName = 'apple-developer-merchantid-domain-association';

function resolveApplePaySource() {
  const candidates = [
    join(__dirname, 'public', '.well-known', fileName),
    join(__dirname, 'public', `${fileName}.txt`),
    join(__dirname, '..', 'backend', '.well-known', fileName),
  ];
  return candidates.find((candidate) => existsSync(candidate));
}

function copyApplePayWellKnown(outDir) {
  const sourcePath = resolveApplePaySource();
  if (!sourcePath) {
    throw new Error('Apple Pay domain association file is missing from frontend public and backend/.well-known');
  }

  copyFileSync(sourcePath, join(outDir, `${fileName}.txt`));
  rmSync(join(outDir, '.well-known'), { recursive: true, force: true });
}

function applePayWellKnownPlugin() {
  return {
    name: 'apple-pay-well-known',
    closeBundle() {
      copyApplePayWellKnown(join(__dirname, 'dist'));
    },
  };
}

// https://vitejs.dev/config/
// Django + WhiteNoise serves the Vite bundle under STATIC_URL (`/static/`); set VITE_STATIC_BASE=/static/ during build_render.sh.
// Event/artist photos are loaded via <img loading="lazy">; prefer CDN/transform URLs (e.g. width caps) from the API for smaller payloads.
export default defineConfig({
  base: process.env.VITE_STATIC_BASE || '/',
  plugins: [react(), applePayWellKnownPlugin()],
  server: {
    port: 3000,
    proxy: {
      '/.well-known': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
