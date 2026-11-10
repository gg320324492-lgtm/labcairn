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
const ALLOWED_STATUSES = new Set(['starting', 'connected', 'disconnected', 'failed'])
const DETAIL_CAP = 400

let currentStatus = 'starting'
let currentDetail = ''

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
    strip.append(label, detail)
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
  label.textContent = words[currentStatus] ?? words.starting
  detail.textContent = currentDetail
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

// The strip is injected at document start, whatever page loads — including
// about:blank on a startup refusal, which is the page that must show the
// diagnostic rather than an empty workbench.
if (typeof document !== 'undefined') {
  renderStrip()
}

contextBridge.exposeInMainWorld('labcairnShell', {
  status: () => currentStatus,
})
