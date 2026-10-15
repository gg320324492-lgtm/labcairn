import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // The LabCairn API is localhost-bound and not implemented yet, so the dev server
  // stays same-origin by default. A proxy is deliberately NOT configured here:
  // adding one would imply a backend that does not exist.
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
  },
  preview: {
    host: '127.0.0.1',
    port: 4173,
    strictPort: true,
  },
  build: {
    // Surface a sourcemap-free, deterministic build; CI compares nothing but exit codes.
    sourcemap: false,
  },
})
