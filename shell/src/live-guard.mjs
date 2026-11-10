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

/**
 * The two IPC handlers, as a factory of decisions rather than as Electron
 * wiring.
 *
 * **Why a factory.** `main.mjs` cannot be imported by a test (it loads
 * `electron` and starts an app), so a decision made inline there has no pure
 * witness — and a decision with no pure witness is a decision a counter-mutation
 * can remove while every witness stays green. That is exactly what happened on
 * 2026-11-10: removing the *report*-side origin check left the whole tree green
 * and the harness reported SURVIVED. `window-security.mjs` solved the same
 * problem for the navigation guards by holding `attachNavigationGuards` and
 * letting `test/window-security.test.mjs` drive it with a fake `webContents`;
 * this is that shape for the guard IPC.
 *
 * `main.mjs` supplies the Electron-side adapter (`senderOf` maps an IPC event
 * to `{ origin, send, isDestroyed }`) and the channels; the tests supply a fake.
 * The decisions — grant or refuse, by the sender's **origin**, on both the
 * request and the report — live here and are witnessed here.
 *
 * `allowedOrigins` and `isDev` are getters, not values: `main.mjs` installs the
 * handlers before `boot()` learns the origins the service reported, so a value
 * captured at install time would be the empty set and every page would be
 * refused.
 *
 * @param config.allowedOrigins  `() => Set<string>`, the origins the shell loaded.
 * @param config.isDev           `() => boolean`, the dev flag a grant carries.
 * @param config.log             `(line) => void`, what the main process prints.
 * @param config.senderOf        `(ipcEvent) => { origin, send, isDestroyed } | null`.
 * @param config.onVerdict       `(guard) => void`, called once a report is
 *   interpreted, so the caller can hold the verdict for a page loaded later.
 * @returns {{ handleGuardRequest: Function, handleGuardReport: Function }}
 */
export function createGuardIpc({ allowedOrigins, isDev, log, senderOf, onVerdict = () => {} }) {
  /**
   * The page asks; this decides. Both decisions are printed, because a grant
   * that leaves no trace and a refusal that leaves one are not the same witness:
   * with only the refusal visible, removing the check looks like nothing
   * happened.
   */
  function handleGuardRequest(event) {
    const sender = senderOf(event)
    const origin = sender === null ? null : sender.origin
    if (!senderIsAllowed(origin, allowedOrigins())) {
      log(`refused guard-request origin ${String(origin)}`)
      if (sender !== null && !sender.isDestroyed()) {
        sender.send('shell:guard-denied', { reason: `sender origin ${String(origin)}` })
      }
      return { granted: false, origin }
    }
    log(`guard-request granted origin ${origin}`)
    if (sender !== null && !sender.isDestroyed()) {
      sender.send('shell:guard-grant', { dev: isDev() })
    }
    return { granted: true, origin }
  }

  /**
   * A report is believed only from a sender the shell loaded. Without this, a
   * frame that skipped the grant — one that asked and was refused, or one that
   * never asked at all — could put a verdict on the status strip.
   */
  function handleGuardReport(event, report) {
    const sender = senderOf(event)
    const origin = sender === null ? null : sender.origin
    if (!senderIsAllowed(origin, allowedOrigins())) {
      log(`refused guard-report origin ${String(origin)}`)
      return { accepted: false, origin }
    }
    const result = readGuardResponse({
      status: report?.status ?? 0,
      json: async () => ({ reason: report?.reason ?? null }),
    })
    // `readGuardResponse` is async so the rehearsal and the shipped shell share
    // one interpretation; the report carries only status + reason, already
    // parsed by the renderer. The Promise settles on the next microtask.
    void result.then((parsed) => {
      const guard = parsed.ok ? '401 session_required' : `failed ${parsed.status} ${String(parsed.reason)}`
      log(`${guardDetail(parsed)} (sender origin ${origin})`)
      onVerdict(guard)
      if (sender !== null && !sender.isDestroyed()) {
        sender.send('shell:guard-verdict', { guard })
      }
    })
    return { accepted: true, origin }
  }

  return { handleGuardRequest, handleGuardReport }
}
