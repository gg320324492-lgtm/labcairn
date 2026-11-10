/**
 * The shell's main process: one window, one child service, no product logic.
 *
 * The shape is the plan's §2 verbatim: spawn `labcairn serve` through the
 * service supervisor (which owns the drain), wait for readiness (the
 * `ServiceStarting` line *and* a `GET /health` 200 — a port answering is not
 * a service that is ready), load the served origin, and stop the child before
 * the shell exits.
 *
 * **What this file does not do.** No network calls on the workbench's behalf
 * (ADR-0023's contracts entry 4), no `shell.openExternal`, no `--origin`
 * widening (the supervisor passes no `--origin`; AC-1's witness reads
 * `ServiceStarting.origins` back from the service), no reading of the session
 * token — the `token_path` field names a file the page reads; the shell never
 * opens it.
 *
 * **The lifecycle arms (§4.3), as far as this skeleton takes them:**
 * - normal close: `before-quit` → the supervisor stops the child (graceful
 *   signal, bounded wait, forced group kill) → the app exits only after the
 *   child's `exit` is seen;
 * - uncaught error: the same stop runs, the window shows the diagnostic, the
 *   app exits — the child is never left behind on an error path;
 * - the child dies after readiness: the window shows the disconnected state;
 *   the shell does not respawn (a silent respawn would take a second
 *   workspace lock);
 * - a startup refusal: the window loads `about:blank` and the preload strip
 *   carries the diagnostic — no blank workbench, no foreign page;
 * - a second instance: the single-instance lock focuses the first window and
 *   starts no second service.
 * Port re-selection on a foreign listener is AC-2's occupancy arm and stays a
 * named gap (see the acceptance record); what this file guarantees is that a
 * port the service did not report is never loaded.
 */

import path from 'node:path'
import { app, BrowserWindow, ipcMain } from 'electron'

import { resolveRunConfig } from './config.mjs'
import { guardDetail, readGuardResponse, senderIsAllowed } from './live-guard.mjs'
import { ServiceSupervisor, defaultLogPath } from './service-supervisor.mjs'
import { createShellWindow } from './window.mjs'

const state = {
  window: null,
  supervisor: null,
  allowedOrigins: new Set(),
  childExitSeen: false,
  stopping: false,
  status: 'starting',
  detail: '',
  refusals: [],
  dev: false,
  guard: 'not-run',
}

function sendStatus(status, detail = '') {
  state.status = status
  state.detail = detail
  process.stdout.write(`status ${status}${detail ? `: ${detail}` : ''}\n`)
  if (state.window !== null && !state.window.isDestroyed()) {
    state.window.webContents.send('shell:status', { status, detail })
  }
}

/**
 * The main process's half of T05: decide by sender origin, then let the page
 * make its own request and record what the service answered.
 *
 * §5.4 entry 4 says the IPC handler validates the sender's **origin**, not its
 * URL, and this is that decision made in one place. `senderFrame` can be null
 * after a navigation or when the frame is gone; a frame the shell cannot name
 * is refused rather than guessed at. `about:blank` — the page the startup
 * refusal shows — serialises its origin to `"null"`, so the diagnostic page is
 * a refused sender: it cannot ask the service for anything, which is the
 * property the refusal arm's witness reads.
 */
function installGuardIpc() {
  ipcMain.on('shell:guard-request', (event) => {
    // Both decisions are printed. A grant that leaves no trace and a refusal
    // that leaves one are not the same witness: with only the refusal visible,
    // removing the check looks like nothing happened.
    const origin = event.senderFrame?.origin ?? null
    if (!senderIsAllowed(origin, state.allowedOrigins)) {
      process.stdout.write(`refused guard-request origin ${String(origin)}\n`)
      if (!event.sender.isDestroyed()) {
        event.sender.send('shell:guard-denied', { reason: `sender origin ${String(origin)}` })
      }
      return
    }
    process.stdout.write(`guard-request granted origin ${origin}\n`)
    event.sender.send('shell:guard-grant', { dev: state.dev })
  })

  ipcMain.on('shell:guard-report', (event, report) => {
    // A report is only believed from a sender the shell loaded: a page that
    // skipped the grant cannot put a verdict on the strip either.
    const origin = event.senderFrame?.origin ?? null
    if (!senderIsAllowed(origin, state.allowedOrigins)) {
      process.stdout.write(`refused guard-report origin ${String(origin)}\n`)
      return
    }
    const result = readGuardResponse({
      status: report?.status ?? 0,
      json: async () => ({ reason: report?.reason ?? null }),
    })
    // `readGuardResponse` is async so the rehearsal and the main process share
    // one interpretation; the report carries only status + reason, already
    // parsed by the renderer. The Promise settles on the next microtask.
    void result.then((parsed) => {
      const guard = parsed.ok ? '401 session_required' : `failed ${parsed.status} ${String(parsed.reason)}`
      state.guard = guard
      const detail = guardDetail(parsed)
      process.stdout.write(`${detail} (sender origin ${origin})\n`)
      if (state.window !== null && !state.window.isDestroyed()) {
        state.window.webContents.send('shell:guard-verdict', { guard })
      }
    })
  })
}

async function boot() {
  const config = resolveRunConfig(process.env, { packaged: app.isPackaged })
  state.dev = config.dev
  installGuardIpc()

  const supervisor = new ServiceSupervisor({
    command: config.cliPath,
    cwd: path.dirname(config.workspace),
    logPath: defaultLogPath(process.env),
  })
  state.supervisor = supervisor

  const { win, refusals } = createShellWindow({
    allowedOrigins: { get current() { return state.allowedOrigins } },
    // A refusal is printed, not only recorded: §5.2's "external navigation is
    // refused" is a claim a witness has to be able to see from outside.
    report: (entry) => process.stdout.write(`refused ${entry.kind} ${entry.url}\n`),
  })
  state.window = win
  state.refusals = refusals

  // The preload registers its listener at document start, so a status sent
  // before the page existed never reached it. After every load finishes, the
  // current state is re-sent — this is how the diagnostic strip on
  // about:blank and the strip in a freshly loaded workbench both show the
  // truth rather than the 'starting' they began with.
  win.webContents.on('did-finish-load', () => {
    sendStatus(state.status, state.detail)
    // T05's half-loop nudges the page on every load, connected or refused.
    // The nudge is not a permission: the page asks, and this process decides
    // by the sender's origin — which is how the diagnostic page on about:blank
    // ends up as a *refused* sender rather than a page that can talk to the
    // service. The token is never read here.
    win.webContents.send('shell:run-guard')
    if (state.window !== null && !state.window.isDestroyed() && state.guard !== 'not-run') {
      state.window.webContents.send('shell:guard-verdict', { guard: state.guard })
    }
  })

  const showDiagnostic = (detail) => {
    // The diagnostic page is the one page the shell loads that is not an
    // origin: about:blank, which carries no origin at all. It is a refusal
    // surface, not a workbench.
    sendStatus('failed', detail)
    void win.loadURL('about:blank')
    win.show()
  }

  let started
  try {
    started = await supervisor.start({
      port: config.port,
      staticDir: config.staticDir,
      workspace: config.workspace,
    })
  } catch (error) {
    showDiagnostic(String(error.message ?? error))
    return
  }
  const { starting, child } = started

  // The allow-list is what the service reported, read back from the service
  // (§5.3). In dev the page's own origin joins it — the one difference the
  // dev switch makes (§4.2). Nothing here widens the service's own list:
  // this set is the shell's navigation guard, and the service's guard is
  // the service's.
  state.allowedOrigins = new Set([starting.origin])
  if (config.dev) {
    state.allowedOrigins.add(new URL(config.pageUrl).origin)
  }

  const pageUrl = config.dev ? config.pageUrl : `${starting.origin}/`

  // The child dying — after readiness or at any point — is a visible
  // disconnected state, never a silent respawn (§4.3's crash-after-ready row:
  // a restart is a user action, and a skeleton has no restart button yet).
  child.once('exit', (code, signal) => {
    state.childExitSeen = true
    if (state.stopping) return
    sendStatus(
      'disconnected',
      `the service child exited (code ${code}${signal ? `, signal ${signal}` : ''})`,
    )
  })

  sendStatus('connected', `service at ${starting.origin}`)
  process.stdout.write(`service origin=${starting.origin}\nchild pid=${child.pid}\n`)
  await win.loadURL(pageUrl)
  win.show()
  process.stdout.write(`loaded ${pageUrl}\n`)
}

async function shutdown() {
  if (state.stopping) return
  state.stopping = true
  if (state.supervisor !== null) {
    try {
      await state.supervisor.stop()
    } catch (error) {
      process.stderr.write(`the service child survived the shell's stop: ${error.message}\n`)
      process.exitCode = 1
    }
  }
}

// §4.3's crash arm: the supervisor hooks cover the error paths, and the
// child is stopped on every one of them. `exit` is the last resort the main
// process still has.
app.on('before-quit', (event) => {
  if (state.stopping) return
  event.preventDefault()
  shutdown().then(() => app.exit(process.exitCode ?? 0))
})

process.on('uncaughtException', (error) => {
  process.stderr.write(`uncaught: ${error?.stack ?? error}\n`)
  shutdown().finally(() => process.exit(1))
})

process.on('unhandledRejection', (reason) => {
  process.stderr.write(`unhandled rejection: ${reason}\n`)
  shutdown().finally(() => process.exit(1))
})

// §4.3's second-instance row: the lock is taken before anything starts.
const gotTheLock = app.requestSingleInstanceLock()

if (!gotTheLock) {
  app.quit()
} else {
  app.on('second-instance', () => {
    if (state.window !== null && !state.window.isDestroyed()) {
      if (state.window.isMinimized()) state.window.restore()
      state.window.focus()
    }
  })

  app.whenReady().then(() => {
    boot().catch((error) => {
      process.stderr.write(`the shell failed: ${error?.stack ?? error}\n`)
      if (state.window !== null && !state.window.isDestroyed()) {
        sendStatus('failed', String(error?.message ?? error))
        void state.window.loadURL('about:blank')
        state.window.show()
      } else {
        process.exit(1)
      }
    })
  })

  app.on('window-all-closed', () => {
    app.quit()
  })
}
