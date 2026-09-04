import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// The API runs separately on :8020 (see workbench/run_workbench.sh).
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8020',
        changeOrigin: true,
      },
    },
  },
});
