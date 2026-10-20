import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

import { DEV_API_BASE } from './src/api/mount.ts'

// The LabCairn API is bound to 127.0.0.1 and is served from the same origin
// as the built workbench, so the page and the API share one origin and the
// service's origin check means what it says.
//
// The development server is the exception, and it is explicit. While the
// workbench is being developed it is served by Vite on another port, so the
// API is reached through a proxy mounted at DEV_API_BASE. The proxy strips
// that prefix and changes nothing else.
//
// **The proxy does not touch the request's origin.** Three settings say so,
// and a test reads them back:
//
//   * `changeOrigin` is left false. It rewrites the `Host` header, and a
//     proxy that rewrites the headers that say where a request came from is
//     a proxy whose rewriting is one setting away.
//   * `rewriteWsOrigin` is left false. That option literally rewrites the
//     `Origin` header.
//   * `headers` is empty. A proxy that adds an `Origin` of its own chooses
//     which origin the service is told about, which is the check's whole
//     subject.
//
// The service is started with the development origin in `extra_origins` —
// `create_app(context, extra_origins=["http://127.0.0.1:5173"])` — and the
// allow-list is empty otherwise, so a service that was not told about the
// development origin refuses it.
export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    port: 5173,
    strictPort: true,
    proxy: {
      [DEV_API_BASE]: {
        target: 'http://127.0.0.1:8000',
        changeOrigin: false,
        rewrite: (path: string) => path.replace(new RegExp(`^${DEV_API_BASE}`), ''),
      },
    },
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
