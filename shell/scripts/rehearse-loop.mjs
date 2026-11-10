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

import { Cdp, listTargets, pageState, pollUntil, freeLoopbackPort } from './lib/rehearsal-support.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SHELL_ROOT = path.join(HERE, '..')
const REPO_ROOT = path.resolve(SHELL_ROOT, '..')

/**
 * The CDP port, asked from the operating system rather than assumed.
 *
 * A fixed port is how this rehearsal's own leftover bit it: an earlier run
 * died in the shell's boot path, its Electron outlived the rehearsal, and the
 * next run's Chromium refused to bind — `bind() returned an error: 每个套接字
 * 地址只允许使用一次` — and the run failed for a cause that had nothing to do
 * with what it was measuring. The rehearsal now takes a free port and, on any
 * failure, ends the shell children it started.
 */
const DEBUG_PORT = Number(process.env.LABCAIRN_SHELL_DEBUG_PORT ?? (await freeLoopbackPort()))
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

const startedShells = []

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

// The window-reading support (`Cdp`, `listTargets`, `pageState`, `pollUntil`)
// lives in `lib/rehearsal-support.mjs`, shared with the dev-mode rehearsal:
// two copies of a reader is two things to keep in step, and a rehearsal whose
// reader drifted would report the shell's behaviour instead of measuring it.

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
  startedShells.push({ child, label })
  return { child, stdout, stderr, waitLine }
}

/**
 * The rehearsal's own cleanup. A rehearsal that fails must not leave an
 * Electron and a service child behind: the leftover was what made the next
 * run fail on a port, and a failure that hides the next run's failure is worse
 * than the failure itself.
 */
async function endEveryStartedShell() {
  for (const { child, label } of startedShells) {
    if (child.exitCode !== null || child.signalCode !== null) continue
    if (process.platform === 'win32') {
      spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' })
    } else {
      child.kill('SIGKILL')
    }
    const gone = await waitForExit(child, 8000)
    if (!gone) log(`cleanup: shell ${label} (pid ${child.pid}) did not report an exit`)
  }
  startedShells.length = 0
}

process.on('unhandledRejection', async (reason) => {
  log(`rehearsal failed: ${reason instanceof Error ? reason.stack : reason}`)
  await endEveryStartedShell()
  process.exit(1)
})

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

const pages = await listTargets(DEBUG_PORT)
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

const pagesTwo = await listTargets(DEBUG_PORT)
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

// --------------------------------------------------------------------------- #
// Act 3: the security baseline, read from inside a real window.
//
// The pure-layer tests assert the object the window is built with and the
// guards' decisions; this act asserts what a renderer actually finds — no
// `process`, no `require`, no `ipcRenderer` on the page — and that a foreign
// window-open and a foreign navigation are refused, with the refusal printed
// by the main process rather than inferred from an absence.
// --------------------------------------------------------------------------- #
log('=== act 3: the baseline and the guards, from inside the window ===')
const workspaceThree = makeWorkspace('closure-act3')
const shellThree = startShell({ workspace: workspaceThree, label: 'act3' })
await shellThree.waitLine(/loaded (\S+)/)
const serviceOriginThree = (await shellThree.waitLine(/service origin=(\S+)/))[1]
const servicePidThree = Number.parseInt((await shellThree.waitLine(/child pid=(\d+)/))[1], 10)
const servicePortThree = new URL(serviceOriginThree).port

const pagesThree = await listTargets(DEBUG_PORT)
const cdpThree = new Cdp(pagesThree[0].webSocketDebuggerUrl)
await pollUntil(() => pageState(cdpThree), (state) => state.stripStatus === 'connected', 15_000, 'act 3 reaching the connected state')

const rendererSurface = {
  hasProcess: await cdpThree.evaluate(`(typeof process !== 'undefined')`),
  hasRequire: await cdpThree.evaluate(`(typeof require !== 'undefined')`),
  hasIpcRenderer: await cdpThree.evaluate(`(typeof ipcRenderer !== 'undefined')`),
  hasModule: await cdpThree.evaluate(`(typeof module !== 'undefined')`),
  bridgeKeys: await cdpThree.evaluate(`Object.keys(window.labcairnShell).sort()`),
  bridgeStatusType: await cdpThree.evaluate(`typeof window.labcairnShell.status`),
  // What the bridge can carry as *data*: the surface is enumerable, so every
  // value on it is readable here. A token could only reach the page as a
  // string on this surface, and none is.
  bridgeStringValues: await cdpThree.evaluate(`Object.values(window.labcairnShell).filter((value) => typeof value === 'string')`),
}
log('act 3 renderer surface:', JSON.stringify(rendererSurface))
assert.equal(rendererSurface.hasProcess, false, 'the renderer could see `process` — nodeIntegration is not off')
assert.equal(rendererSurface.hasRequire, false, 'the renderer could see `require`')
assert.equal(rendererSurface.hasIpcRenderer, false, 'the renderer could see `ipcRenderer`')
assert.equal(rendererSurface.hasModule, false, 'the renderer could see `module`')
assert.deepEqual(rendererSurface.bridgeKeys, ['status'], `the exposed surface is not the one the preload declares: ${JSON.stringify(rendererSurface.bridgeKeys)}`)
assert.equal(rendererSurface.bridgeStatusType, 'function')
assert.deepEqual(rendererSurface.bridgeStringValues, [], 'the native surface carries a string value the page could read as data')

const FOREIGN_URL = 'http://labcairn.example.invalid/escape'

// A new window to a foreign origin: denied, and the denial is printed.
const popupResult = await cdpThree.evaluate(`(() => { const opened = window.open(${JSON.stringify(FOREIGN_URL)}); return opened === null ? 'no window' : 'window returned' })()`)
assert.equal(popupResult, 'no window', `window.open returned ${popupResult} although the handler denies`)
const openRefusal = await shellThree.waitLine(/refused window-open (\S+)/, 10_000)
assert.equal(openRefusal[1], FOREIGN_URL, 'the printed window-open refusal names another URL')
log(`act 3 window-open refused: ${openRefusal[1]}`)

// A renderer-initiated navigation to a foreign origin: prevented, the page
// stays on the service origin, and the prevention is printed.
const locationBefore = (await pageState(cdpThree)).location
await cdpThree.evaluate(`(() => { location.assign(${JSON.stringify(FOREIGN_URL)}) })()`)
const navigateRefusal = await shellThree.waitLine(/refused will-navigate (\S+)/, 10_000)
assert.equal(navigateRefusal[1], FOREIGN_URL, 'the printed navigation refusal names another URL')
const locationAfter = (await pageState(cdpThree)).location
assert.equal(locationAfter, locationBefore, `the page moved to ${locationAfter} although the navigation was refused`)
log(`act 3 navigation refused: ${navigateRefusal[1]}; the page stayed on ${locationAfter}`)

// The window is closed from outside, as in act 2 — killing the shell here
// would skip `before-quit` and leave the service child behind, which is the
// orphan the rehearsal is supposed to catch rather than cause.
await cdpThree.send('Target.closeTarget', { targetId: pagesThree[0].id })
cdpThree.close()

const electronGoneThree = await waitForExit(shellThree.child, 30_000)
assert.ok(electronGoneThree, 'the shell did not exit after its window closed')
assert.equal(shellThree.child.exitCode, 0, `the shell exited with code ${shellThree.child.exitCode}, not 0`)
pidIsGone(servicePidThree, 'act 3 after the shell closed its window')
await assertPortFree(servicePortThree, 'act 3 after the shell exited')
log('act 3 result: no node surface in the renderer; bridge is {status}; both refusals printed and effective; clean close')

log('=== closure rehearsal passed ===')
log(`scratch workspace (act 1): ${workspaceOne}`)
log(`scratch workspace (act 2): ${workspaceTwo}`)
log(`scratch workspace (act 3): ${workspaceThree}`)
log(`drained logs: ${path.join(scratchRoot, 'closure-act1-service.log')}, ${path.join(scratchRoot, 'closure-act2-service.log')}, ${path.join(scratchRoot, 'closure-act3-service.log')}`)
void os // reserved for platform branches; kept explicit rather than imported-unused
