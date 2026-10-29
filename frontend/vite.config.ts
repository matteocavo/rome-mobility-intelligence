import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// https://vite.dev/config/
const PAGES_BASE = '/rome-mobility-intelligence/';
export default defineConfig(({ command, isPreview }) => ({
  base: command === 'serve' && !isPreview ? '/' : PAGES_BASE,
  build: {
    sourcemap: false,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-dom/client'],
          leaflet: ['leaflet'],
        },
      },
    },
  },
  plugins: [
    react(),
    tailwindcss(),
    {
      name: 'production-public-only',
      generateBundle() {
        for (const id of this.getModuleIds()) {
          if (/(?:tests|fixtures)[\\/]|(?:demoData|mockData)\.[jt]s/.test(id)) {
            this.error('Test/demo module in production graph');
          }
        }
      },
    },
  ],
  server: {
    host: '127.0.0.1',
    port: 3000,
    proxy: { '/public': 'http://127.0.0.1:8000' },
  },
}));
