/**
 * The dev rehearsal's Vite configuration: the repository's own, with one
 * number swapped.
 *
 * **Why this file exists at all.** `web/vite.config.ts` fixes the proxy target
 * at `http://127.0.0.1:8000`, and on this machine port 8000 is held by
 * `com.docker.backend.exe` (measured 2026-11-10: `netstat` LISTENING, PID
 * 33364). The rehearsal will not displace a listener it does not own, so it
 * starts the service on a port the operating system chose — and then needs the
 * page's proxy to point at that port. Editing `web/vite.config.ts` is not
 * available to this window: it is another window's file (§0 rule 4's ownership
 * map), and a rehearsal that edits the arrangement it is meant to measure is
 * not measuring that arrangement.
 *
 * **What is inherited rather than re-declared.** This config imports the real
 * one and spreads it. `changeOrigin: false`, the `rewrite`, the empty `headers`,
 * `host: '127.0.0.1'`, `port: 5173` and `strictPort: true` come from
 * `web/vite.config.ts` as written — the three settings whose point is *not* to
 * change the request's origin (`web/vite.config.ts`'s own comment, and a test
 * reads them back) are not restated here, so a rehearsal cannot quietly widen
 * the thing it is testing. The mounted prefix comes from the inherited proxy's
 * own key rather than a copy of `DEV_API_BASE`: two constants naming the same
 * mount is exactly the failure `web/src/api/mount.ts` exists to prevent.
 *
 * **What is overridden, and only that:** the proxy's target port.
 */

import baseConfig from '../../web/vite.config.ts'

const port = process.env.LABCAIRN_DEV_REHEARSAL_SERVICE_PORT

// The config is loaded twice in a rehearsal run: once by the rehearsal itself
// (to assert what it inherits) and once by Vite (to serve the page). Only the
// second has the port, because the rehearsal picks the port between the two.
// A missing port is therefore not an error — it means *this load* does not
// override the target — and the fact is exported as `overrodeTarget` so the
// rehearsal can say which load it is looking at rather than assume.
const overriding = port !== undefined && port !== ''

const baseServer = baseConfig.server ?? {}
const baseProxy = baseServer.proxy ?? {}
const mountedPrefixes = Object.keys(baseProxy)
if (mountedPrefixes.length !== 1) {
  throw new Error(
    `web/vite.config.ts proxies ${mountedPrefixes.length} prefixes (${mountedPrefixes.join(', ')}); ` +
      'the rehearsal expects the one mount the workbench asks for',
  )
}
const mountedPrefix = mountedPrefixes[0]
const baseEntry = baseProxy[mountedPrefix]

const baseTarget = new URL(baseEntry.target ?? '')
if (baseTarget.hostname !== '127.0.0.1') {
  throw new Error(`the real config's proxy target is not loopback: ${baseEntry.target}`)
}

// The three settings whose whole point is that the proxy does not touch where
// a request says it came from are asserted here, so that a future widening of
// `web/vite.config.ts` breaks this rehearsal loudly instead of quietly making
// the rehearsal's origin a different origin from the product's.
if (baseEntry.changeOrigin !== false) {
  throw new Error(`web/vite.config.ts no longer leaves changeOrigin at false: ${baseEntry.changeOrigin}`)
}
if (baseEntry.headers !== undefined && Object.keys(baseEntry.headers).length > 0) {
  throw new Error(`web/vite.config.ts no longer leaves the proxy headers empty: ${JSON.stringify(baseEntry.headers)}`)
}

export default {
  ...baseConfig,
  server: {
    ...baseServer,
    proxy: {
      [mountedPrefix]: {
        ...baseEntry,
        ...(overriding ? { target: `http://127.0.0.1:${port}` } : {}),
      },
    },
  },
}

/** Exported so the rehearsal can assert the inheritance rather than assume it. */
export const inherited = {
  mountedPrefix,
  changeOrigin: baseEntry.changeOrigin,
  headers: baseEntry.headers ?? null,
  baseTarget: baseEntry.target,
  host: baseServer.host,
  vitePort: baseServer.port,
  strictPort: baseServer.strictPort,
  /** Whether *this load* pointed the proxy at a rehearsal-chosen port. */
  overrodeTarget: overriding,
}
