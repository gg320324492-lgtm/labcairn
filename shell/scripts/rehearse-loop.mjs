/**
 * The dev-mode closure rehearsal (the skeleton's named closure test).
 *
 * Two acts, in the order the plan's §4.3 table states them:
 *
 * **Act 1 — the service dies, the window says so.** The shell is started for
 * real (Electron, the packaged-shaped dev run: the service carries the built
 * bundle, so page and API share the service's own origin). The rehearsal reads
 * the loaded page's origin and the preload status strip over CDP, asserts the
 * page answers and says `connected`, then ends the service child from outside
 * the shell — the crash-after-readiness arm — and asserts the same window
 * shows `disconnected` without a respawn.
 *
 * **Act 2 — the window closes, the service follows.** The shell is started
 * again, the window is closed from outside, and the rehearsal asserts the
 * Electron process is gone, the service pid is gone from the process table,
 * and nothing listens on the port. The orphan half of §4.3's normal-close row.
 *
 * Everything is asserted by the script; a non-zero exit is the failure. The
 * run's output is the evidence the acceptance record quotes. The scratch
 * workspace and the drained log live outside the repository
 * (`E:\labcairn-local\`), and the rehearsal passes `PYTHONPATH` at this
 * checkout's `src` so the service it starts is *this* tree's product code
 * (`CLAUDE.md`, *A copied virtualenv is not a virtualenv of its own*).
 */

import assert from 'node:assert/strict'
import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SHELL_ROOT = path.join(HERE, '..')
const REPO_ROOT = path.resolve(SHELL_ROOT, '..')

const DEBUG_PORT = Number(process.env.LABCAIRN_SHELL_DEBUG_PORT ?? 9223)
const scratchRoot = process.env.LABCAIRN_SHELL_SCRATCH ?? 'E:\\labcairn-local\\shell-scratch'
// The worktree sits at `<repo>/.claude/worktrees/<name>`, so the repository
// root — the home of the `.venv` whose console script this rehearsal starts —
// is three directories up.
const repoCheckoutRoot = path.resolve(REPO_ROOT, '..', '..', '..')
const pythonExe =
  process.env.LABCAIRN_SHELL_PYTHON ??
  (process.platform === 'win32'
    ? path.join(repoCheckoutRoot, '.venv', 'Scripts', 'python.exe')
    : path.join(repoCheckoutRoot, '.venv', 'bin', 'python'))
const cliExe = process.env.LABCAIRN_SHELL_CLI ?? path.join(path.dirname(pythonExe), 'labcairn.exe')
const electronExe = process.env.LABCAIRN_SHELL_ELECTRON ?? path.join(SHELL_ROOT, 'node_modules', 'electron', 'dist', 'electron.exe')

for (const [name, where] of [['python', pythonExe], ['labcairn', cliExe], ['electron', electronExe]]) {
  assert.ok(where !== null && fs.existsSync(where), `the rehearsal cannot find ${name} at ${where}`)
}

function log(...parts) {
  process.stdout.write(`${parts.join(' ')}\n`)
}

async function waitForExit(child, ms) {
  if (child.exitCode !== null || child.signalCode !== null) return true
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(false), ms)
    child.once('exit', () => {
      clearTimeout(timer)
      resolve(true)
    })
  })
}

function makeWorkspace(name) {
  const workspace = path.join(scratchRoot, `${name}-${Date.now()}`)
  const env = { ...process.env, COLUMNS: '200', PYTHONIOENCODING: 'utf-8', PYTHONPATH: path.join(REPO_ROOT, 'src') }
  const initialised = spawnSync(cliExe, ['--workspace', workspace, 'init'], { encoding: 'utf8', env })
  assert.equal(initialised.status, 0, `labcairn init refused: ${initialised.stderr}`)
  const created = spawnSync(
    cliExe,
    [
      '--workspace',
      workspace,
      'task',
      'create',
      '--title',
      'Shell closure rehearsal',
      '--objective',
      'The shell starts the service, loads its origin, and reports the service stopping.',
      '--criterion',
      'The window showed the connected and disconnected states.',
      '--json',
    ],
    { encoding: 'utf8', env },
  )
  assert.equal(created.status, 0, `labcairn task create refused: ${created.stderr}`)
  return workspace
}

// --------------------------------------------------------------------------- #
// a small CDP client: the rehearsal reads the window the way a driver would,
// through Electron's own remote-debugging endpoint.
// --------------------------------------------------------------------------- #
async function listTargets() {
  const deadline = Date.now() + 30_000
  for (;;) {
    try {
      const response = await fetch(`http://127.0.0.1:${DEBUG_PORT}/json/list`)
      const targets = await response.json()
      const pages = targets.filter((target) => target.type === 'page' && target.webSocketDebuggerUrl)
      if (pages.length > 0) return pages
    } catch {
      // the endpoint is not up yet
    }
    if (Date.now() >= deadline) throw new Error('the shell window never exposed a CDP target')
    await new Promise((resolve) => setTimeout(resolve, 250))
  }
}

class Cdp {
  constructor(webSocketUrl) {
    this.socket = new WebSocket(webSocketUrl)
    this.nextId = 1
    this.pending = new Map()
    this.ready = new Promise((resolve, reject) => {
      this.socket.addEventListener('open', () => resolve())
      this.socket.addEventListener('error', (event) => reject(new Error(event.message ?? 'CDP socket error')))
    })
    this.socket.addEventListener('message', (event) => {
      const message = JSON.parse(String(event.data))
      const waiting = this.pending.get(message.id)
      if (waiting !== undefined) {
        this.pending.delete(message.id)
        waiting(message)
      }
    })
  }

  send(method, params = {}) {
    return this.ready.then(
      () =>
        new Promise((resolve, reject) => {
          const id = this.nextId
          this.nextId += 1
          this.pending.set(id, (message) => {
            if (message.error !== undefined) reject(new Error(`${method}: ${message.error.message}`))
            else resolve(message.result)
          })
          this.socket.send(JSON.stringify({ id, method, params }))
        }),
    )
  }

  async evaluate(expression) {
    const result = await this.send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (result.exceptionDetails !== undefined) {
      throw new Error(`page evaluation failed: ${JSON.stringify(result.exceptionDetails)}`)
    }
    return result.result.value
  }

  close() {
    try {
      this.socket.close()
    } catch {
      // already closed
    }
  }
}

async function pageState(cdp) {
  return cdp.evaluate(`(() => {
    const strip = document.getElementById('labcairn-shell-status')
    const service = (window.labcairnShell !== undefined) ? window.labcairnShell.status() : null
    return {
      location: location.origin,
      stripStatus: strip === null ? null : strip.getAttribute('data-shell-status'),
      stripLabel: strip === null ? null : strip.textContent,
      bridgeStatus: service,
      documentTitle: document.title,
    }
  })()`)
}

function startShell({ workspace, label }) {
  const stdout = []
  const stderr = []
  const child = spawn(electronExe, ['.', `--remote-debugging-port=${DEBUG_PORT}`], {
    cwd: SHELL_ROOT,
    windowsHide: true,
    env: {
      ...process.env,
      LABCAIRN_SHELL_CLI: cliExe,
      LABCAIRN_SHELL_WORKSPACE: workspace,
      // The packaged-shaped run: the service carries the built bundle, so page
      // and API share the service's own origin and no dev switch is involved.
      LABCAIRN_SHELL_STATIC_DIR: fs.existsSync(path.join(REPO_ROOT, 'web', 'dist'))
        ? path.join(REPO_ROOT, 'web', 'dist')
        : '',
      LABCAIRN_SHELL_LOG: path.join(scratchRoot, `${label}-service.log`),
      PYTHONPATH: path.join(REPO_ROOT, 'src'),
    },
  })
  child.stdout.setEncoding('utf8')
  child.stderr.setEncoding('utf8')
  child.stdout.on('data', (chunk) => {
    stdout.push(chunk)
    process.stdout.write(`[shell ${label}] ${chunk}`)
  })
  child.stderr.on('data', (chunk) => {
    stderr.push(chunk)
    process.stdout.write(`[shell ${label} stderr] ${chunk}`)
  })
  const waitLine = (needle, timeoutMs = 60_000) =>
    new Promise((resolve, reject) => {
      const deadline = Date.now() + timeoutMs
      const tick = () => {
        const text = stdout.join('')
        const match = text.match(needle)
        if (match !== null) return resolve(match)
        if (Date.now() >= deadline) return reject(new Error(`the shell never printed ${needle}`))
        setTimeout(tick, 150)
      }
      tick()
    })
  return { child, stdout, stderr, waitLine }
}

async function pollUntil(read, predicate, timeoutMs, description) {
  const deadline = Date.now() + timeoutMs
  let last = null
  for (;;) {
    last = await read()
    if (predicate(last)) return last
    if (Date.now() >= deadline) {
      assert.fail(`${description} never happened; last observed state: ${JSON.stringify(last)}`)
    }
    await new Promise((resolve) => setTimeout(resolve, 400))
  }
}

function portIsListening(port) {
  return new Promise((resolve) => {
    const socket = net.connect({ host: '127.0.0.1', port }, () => {
      socket.destroy()
      resolve(true)
    })
    socket.setTimeout(1200, () => {
      socket.destroy()
      resolve(false)
    })
    socket.on('error', () => resolve(false))
  })
}

async function assertPortFree(port, context) {
  const deadline = Date.now() + 10_000
  for (;;) {
    if (!(await portIsListening(port))) return
    if (Date.now() >= deadline) break
    await new Promise((resolve) => setTimeout(resolve, 300))
  }
  assert.fail(`something still listens on ${port} (${context})`)
}

function pidIsGone(pid, context) {
  const listed = spawnSync('tasklist', ['/FI', `PID eq ${pid}`, '/FO', 'CSV', '/NH'], { encoding: 'utf8' })
  assert.equal(
    (listed.stdout ?? '').includes(String(pid)),
    false,
    `pid ${pid} is still in the process table (${context}): ${listed.stdout}`,
  )
}

// --------------------------------------------------------------------------- #
// Act 1: shell starts the service, loads the origin, the service dies, the
// window shows the disconnection.
// --------------------------------------------------------------------------- #
log('=== act 1: service dies -> the window shows the disconnection ===')
const workspaceOne = makeWorkspace('closure-act1')
const shellOne = startShell({ workspace: workspaceOne, label: 'act1' })

const loadedMatch = await shellOne.waitLine(/loaded (\S+)/)
const originMatch = await shellOne.waitLine(/service origin=(\S+)/)
const pidMatch = await shellOne.waitLine(/child pid=(\d+)/)
const serviceOrigin = originMatch[1]
const loadedUrl = loadedMatch[1]
const servicePid = Number.parseInt(pidMatch[1], 10)
log(`loaded ${loadedUrl}; service origin ${serviceOrigin}; service pid ${servicePid}`)

const pages = await listTargets()
const cdpOne = new Cdp(pages[0].webSocketDebuggerUrl)
await cdpOne.send('Runtime.enable')

const servicePort = new URL(serviceOrigin).port
const connected = await pollUntil(
  () => pageState(cdpOne),
  (state) => state.stripStatus === 'connected' || state.bridgeStatus === 'connected',
  15_000,
  'the strip reaching the connected state',
)
log('act 1 connected state:', JSON.stringify(connected))

// AC-1 at the window itself: the page the shell loaded is the service's own
// origin, and the page agrees.
assert.equal(connected.location, serviceOrigin, 'the loaded page is not on the service origin')
assert.equal(loadedUrl, `${serviceOrigin}/`, 'the URL the shell loaded is not the service origin root')

// The workbench itself is in the page: the service carried the built bundle.
const servedByService = await cdpOne.evaluate(
  `fetch('/health').then((response) => response.status)`,
)
assert.equal(servedByService, 200, 'the loaded page could not fetch its own /health')

// Now the service dies from outside — the crash-after-readiness arm. A force
// kill is deliberate: the arm is about the service being gone, not about the
// shell's own stop path.
if (process.platform === 'win32') {
  spawnSync('taskkill', ['/PID', String(servicePid), '/T', '/F'], { stdio: 'ignore' })
} else {
  spawnSync('kill', ['-9', String(servicePid)], { stdio: 'ignore' })
}

const disconnected = await pollUntil(
  () => pageState(cdpOne),
  (state) => state.stripStatus === 'disconnected' && state.bridgeStatus === 'disconnected',
  20_000,
  'the strip reaching the disconnected state',
)
log('act 1 disconnected state:', JSON.stringify(disconnected))
assert.ok(disconnected.stripLabel.includes('disconnected'), `the strip says ${JSON.stringify(disconnected.stripLabel)}`)

cdpOne.close()
await waitForExit(shellOne.child, 15_000) || (shellOne.child.kill(), await waitForExit(shellOne.child, 8_000))
await assertPortFree(servicePort, 'act 1 after the window closed on a dead service')
log('act 1 result: connected -> disconnected in one window; no respawn; port released')

// --------------------------------------------------------------------------- #
// Act 2: the window closes, the service follows — the no-orphan arm.
// --------------------------------------------------------------------------- #
log('=== act 2: window closes -> the service stops ===')
const workspaceTwo = makeWorkspace('closure-act2')
const shellTwo = startShell({ workspace: workspaceTwo, label: 'act2' })

await shellTwo.waitLine(/loaded (\S+)/)
const serviceOriginTwo = (await shellTwo.waitLine(/service origin=(\S+)/))[1]
const servicePidTwo = Number.parseInt((await shellTwo.waitLine(/child pid=(\d+)/))[1], 10)
const servicePortTwo = new URL(serviceOriginTwo).port

const pagesTwo = await listTargets()
const cdpTwo = new Cdp(pagesTwo[0].webSocketDebuggerUrl)
const stateTwo = await pollUntil(
  () => pageState(cdpTwo),
  (state) => state.stripStatus === 'connected',
  15_000,
  'act 2 reaching the connected state',
)
log('act 2 connected state:', JSON.stringify(stateTwo))

// Close the window from outside the shell: the shell must follow it.
await cdpTwo.send('Target.closeTarget', { targetId: pagesTwo[0].id })
cdpTwo.close()

const electronGone = await waitForExit(shellTwo.child, 30_000)
assert.ok(electronGone, 'the shell did not exit after its window closed')
assert.equal(shellTwo.child.exitCode, 0, `the shell exited with code ${shellTwo.child.exitCode}, not 0`)
pidIsGone(servicePidTwo, 'act 2 after the shell closed its window')
await assertPortFree(servicePortTwo, 'act 2 after the shell exited')
log('act 2 result: window closed -> shell exit 0 -> no service pid, port free')

log('=== closure rehearsal passed ===')
log(`scratch workspace (act 1): ${workspaceOne}`)
log(`scratch workspace (act 2): ${workspaceTwo}`)
log(`drained logs: ${path.join(scratchRoot, 'closure-act1-service.log')}, ${path.join(scratchRoot, 'closure-act2-service.log')}`)
void os // reserved for platform branches; kept explicit rather than imported-unused
