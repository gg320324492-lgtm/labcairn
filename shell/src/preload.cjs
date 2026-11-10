// The shell's preload: the only renderer-side code the shell itself owns,
// and it is deliberately tiny (plan §2: "No framework inside the renderer",
// and this window's task: the renderer does nothing but show the connection
// status).
//
// **The surface (§5.4).** An enumerable, argument-validated surface that
// carries no session token, no raw `ipcRenderer`, and no general-purpose
// fetch proxy. The token stays in the page's own module state; this script
// neither reads the token file nor relays requests.
//
// **What it displays.** A fixed status strip in the loaded page's DOM, kept
// out of the workbench's own `#root`, updated only by the main process's
// `shell:status` events — `starting` / `connected` / `disconnected` /
// `failed` — each validated against a closed vocabulary before it is shown.
// The strip is how a dead service still has a visible diagnosis: the page's
// own scripts stopped with it, but the preload ran at document start and the
// strip it injected keeps updating from the main process.
//
// This file is CommonJS because a sandboxed preload is: Electron gives a
// sandboxed preload `require('electron')` and nothing else, and ESM imports
// are not available in it.

const { contextBridge, ipcRenderer } = require('electron')

const STATUS_CHANNEL = 'shell:status'
const GUARD_REQUEST_CHANNEL = 'shell:guard-request'
const GUARD_REPORT_CHANNEL = 'shell:guard-report'
const ALLOWED_STATUSES = new Set(['starting', 'connected', 'disconnected', 'failed'])
const DETAIL_CAP = 400
const LIVE_GUARD_TASK_SELECT = '/task/select'
const LIVE_GUARD_TASK_ID = '00000000-0000-7000-8000-000000000000'

let currentStatus = 'starting'
let currentDetail = ''
let currentGuard = 'not-run'
let currentDev = false

function ensureStrip() {
  // Inserted on documentElement, not body: the workbench owns `#root` in the
  // body, and a strip inside a subtree React manages is a strip React may
  // re-render away.
  let strip = document.getElementById('labcairn-shell-status')
  if (strip === null) {
    strip = document.createElement('div')
    strip.id = 'labcairn-shell-status'
    strip.setAttribute('data-shell-status', '')
    strip.setAttribute(
      'style',
      'position:fixed;top:0;left:0;right:0;z-index:2147483647;padding:4px 12px;' +
        'font:12px/1.4 system-ui,sans-serif;background:#1f2430;color:#f4f6fa;' +
        'display:flex;gap:12px;align-items:center;',
    )
    const label = document.createElement('span')
    label.setAttribute('data-shell-label', '')
    const detail = document.createElement('span')
    detail.setAttribute('data-shell-detail', '')
    detail.setAttribute('style', 'opacity:0.75;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;')
    const guard = document.createElement('span')
    guard.setAttribute('data-shell-guard', 'not-run')
    guard.setAttribute('style', 'margin-left:auto;opacity:0.9;font-variant-numeric:tabular-nums;')
    strip.append(label, detail, guard)
    ;(document.documentElement || document).append(strip)
  }
  return strip
}

function renderStrip() {
  const strip = ensureStrip()
  const words = {
    starting: 'LabCairn — starting the service…',
    connected: 'LabCairn — connected',
    disconnected: 'LabCairn — disconnected: the service stopped',
    failed: 'LabCairn — refused: the service did not start',
  }
  const label = strip.querySelector('[data-shell-label]')
  const detail = strip.querySelector('[data-shell-detail]')
  const guard = strip.querySelector('[data-shell-guard]')
  label.textContent = words[currentStatus] ?? words.starting
  detail.textContent = currentDetail
  guard.textContent = `session guard: ${currentGuard}`
  guard.setAttribute('data-shell-guard', currentGuard)
  strip.setAttribute('data-shell-status', currentStatus)
}

function applyStatus(payload) {
  // Argument-validated: a payload whose status is not in the closed
  // vocabulary is ignored, not displayed. `typeof` checks rather than a
  // schema because this is the boundary — the validated thing is what reaches
  // the DOM.
  if (payload === null || typeof payload !== 'object') return
  if (!ALLOWED_STATUSES.has(payload.status)) return
  currentStatus = payload.status
  const detail = typeof payload.detail === 'string' ? payload.detail.slice(0, DETAIL_CAP) : ''
  currentDetail = detail
  renderStrip()
}

ipcRenderer.on(STATUS_CHANNEL, (_event, payload) => {
  applyStatus(payload)
})

// T05's live mutation half-loop, as a request the main process grants.
//
// **Why request-and-grant rather than fetch-and-report.** A sender-origin
// check the witness cannot exercise is a check it cannot watch. With the grant
// step, the guard's *own* decision is observable: on a page the shell loaded,
// the main process grants; on `about:blank` — the startup-refusal page, whose
// frame carries no origin — it refuses, and the witness reads that refusal from
// the main process's own output. Removing the check is a visible difference,
// which is what a counter-mutation needs.
//
// **What the renderer does.** Ask (one nullary message, carrying nothing),
// fetch on the grant with the one fixed relative mutation the page itself
// makes — no Authorization header, no caller-supplied URL, method, body or
// header — and report only what the service answered. The page's own origin is
// what the service's guard sees; no main-process fetch is involved (ADR-0023's
// out-of-shape list), and no token crosses this boundary in either direction.
function requestGuardProbe() {
  ipcRenderer.send(GUARD_REQUEST_CHANNEL)
}

function reportGuard(result) {
  ipcRenderer.send(GUARD_REPORT_CHANNEL, result)
  return result
}

function probeSessionGuard(dev) {
  const prefix = dev === true ? '/api' : ''
  return fetch(`${prefix}${LIVE_GUARD_TASK_SELECT}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: LIVE_GUARD_TASK_ID }),
  })
    .then(async (response) => {
      let payload = null
      try {
        payload = await response.json()
      } catch {
        // A non-JSON answer is a failed measurement, not a guard refusal.
      }
      return reportGuard({
        status: response.status,
        reason: payload !== null && typeof payload === 'object' ? payload.reason : null,
      })
    })
    .catch((error) => reportGuard({ status: 0, reason: String(error) }))
}

// The main process may ask for the probe (the automatic half-loop after the
// service is ready); the renderer may ask for it itself. Either way the ask
// travels the same channel, and the main process decides by sender origin.
ipcRenderer.on('shell:run-guard', () => requestGuardProbe())

ipcRenderer.on('shell:guard-grant', (_event, payload) => {
  if (payload === null || typeof payload !== 'object' || typeof payload.dev !== 'boolean') return
  void probeSessionGuard(payload.dev)
})

ipcRenderer.on('shell:guard-denied', (_event, payload) => {
  if (payload === null || typeof payload !== 'object' || typeof payload.reason !== 'string') return
  currentGuard = `refused: ${payload.reason}`
  renderStrip()
})

ipcRenderer.on('shell:guard-verdict', (_event, payload) => {
  if (payload === null || typeof payload !== 'object' || typeof payload.guard !== 'string') return
  currentGuard = payload.guard
  renderStrip()
})

// The strip is injected at document start, whatever page loads — including
// about:blank on a startup refusal, which is the page that must show the
// diagnostic rather than an empty workbench.
if (typeof document !== 'undefined') {
  renderStrip()
}

contextBridge.exposeInMainWorld('labcairnShell', {
  status: () => currentStatus,
  guard: () => currentGuard,
})
