/**
 * The main process's half of the live session-guard probe (plan T05, AC-4).
 *
 * **What lives here, and what deliberately does not.** These three functions
 * are what `main.mjs` imports and calls, and `scripts/rehearse-live-guard.mjs`
 * witnesses them end to end in a real window against a real service.
 *
 * The mutation itself is *not* here. The one fixed request the shell makes is
 * made by the page — in `preload.cjs` — and that file is its only source. A
 * sandboxed preload is CommonJS with `require('electron')` and nothing else, so
 * it cannot import this module, and an earlier version of this file answered
 * that by exporting a `LIVE_GUARD_PROBE` constant the tests asserted while
 * `preload.cjs` carried its own literals. That is plan §5.1's failure mode in
 * its purest form — *a constant nobody passes is dead code*: the witness watched
 * a copy, a counter-mutation on the copy changed nothing the service ever saw,
 * and the harness printed CAUGHT for a mutation the product never contained. It
 * was caught on 2026-11-10 by a mutation (POST → GET) that reddened only the
 * test of the copy. The copy is gone; `test/live-guard.test.mjs` now reads the
 * request back out of `preload.cjs` itself, the way
 * `test/native-surface.test.mjs` reads the exposed surface back.
 *
 * **What the half-loop proves.** A real window on the real served origin asks
 * the real service to change something. The service's `SessionGuard` refuses
 * with 401 `session_required`, and the refusal reaches the status strip through
 * this process, which first decides by the sender's origin. A service copy that
 * admitted unauthenticated mutations, or a shell that supplied the token
 * itself, turns the witness red.
 */

/**
 * Whether an IPC sender's *origin* may ask for the live guard probe.
 *
 * The plan explicitly says origin, not URL: a URL can carry a path that looks
 * like a service while its frame is on another site. `about:blank`, `file://`
 * and custom schemes serialise to `"null"`, which is in no allow-list.
 */
export function senderIsAllowed(senderOrigin, allowedOrigins) {
  return typeof senderOrigin === 'string' && allowedOrigins.has(senderOrigin)
}

/**
 * Interpret a live guard response as a small, closed result.
 *
 * `ok` is true only for the measured refusal: HTTP 401 with the service's
 * `session_required` reason. Every other status, a network error, or a body
 * that is not the service's refusal is a failure of the half-loop, never a
 * quiet fallback to "probably guarded".
 */
export async function readGuardResponse(response) {
  let payload = null
  try {
    payload = await response.json()
  } catch {
    // A non-JSON answer is a refusal to measure, not a guard refusal.
  }
  return {
    status: response.status,
    reason: payload !== null && typeof payload === 'object' ? payload.reason : null,
    ok: response.status === 401 && payload?.reason === 'session_required',
  }
}

/** The label the status strip shows for a measured guard refusal. */
export function guardDetail(result) {
  return result.ok
    ? `mutation refused: 401 session_required`
    : `live guard probe failed: ${result.status} ${String(result.reason)}`
}
