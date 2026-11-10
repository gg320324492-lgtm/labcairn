/**
 * The shell's live session-guard probe, and the decision that admits it.
 *
 * **Why this is not a fetch proxy.** The page makes one fixed mutation of its
 * own: a relative `POST /task/select` with a fixed, well-formed task id and
 * no `Authorization` header. There is no caller-supplied URL, method, body or
 * header, no token on the native surface and no general-purpose relay. In
 * dev mode the same probe goes through Vite's own `/api` proxy, whose settings
 * the existing rehearsal reads back; in packaged mode it is same-origin.
 *
 * **What the half-loop proves (AC-4, plan T05).** A real window on the real
 * served origin asks the real service to change something. The service's
 * `SessionGuard` refuses with 401 `session_required`, and the preload renders
 * that refusal in its status strip. A copy of the service that admitted
 * unauthenticated mutations, or a shell that supplied the token itself, turns
 * the witness red. Sender-origin validation is the IPC half of §5.4: only a
 * frame whose origin the shell actually loaded may ask for the probe.
 */

/** The one mutation the probe makes. No caller parameter reaches this object. */
export const LIVE_GUARD_PROBE = Object.freeze({
  path: '/task/select',
  method: 'POST',
  headers: Object.freeze({ 'Content-Type': 'application/json' }),
  // A syntactically valid UUIDv7. The session guard runs before routing, so
  // the body is never read on a refused request; a malformed id would test a
  // different layer. The fixed value keeps the mutation witness reproducible.
  body: '{"task_id":"00000000-0000-7000-8000-000000000000"}',
})

/** The prefix Vite's proxy owns in dev mode (`web/src/api/mount.ts`). */
export const DEV_API_BASE = '/api'

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

/** The URL of the one fixed probe, relative to the page that asks for it. */
export function liveGuardUrl(dev) {
  return `${dev ? DEV_API_BASE : ''}${LIVE_GUARD_PROBE.path}`
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
