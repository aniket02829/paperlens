import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Flask serves the page (templates/index.html) and loads the built entry via the
// manifest, so Vite only builds assets into ../static/dist.
const FLASK = 'http://127.0.0.1:5000';

export default defineConfig({
  plugins: [react()],
  base: '/static/dist/',
  build: {
    outDir: '../static/dist',
    emptyOutDir: true,
    manifest: true,
    // The modulepreload polyfill is injected inline, which the CSP forbids.
    modulePreload: { polyfill: false },
    rollupOptions: { input: 'src/main.tsx' },
  },
  server: {
    // `npm run dev` + `python app.py`: Vite serves the app and proxies API calls to Flask.
    proxy: Object.fromEntries(['/api', '/analyze', '/analyze-bulk', '/stats', '/health'].map(p => [p, FLASK])),
  },
});
