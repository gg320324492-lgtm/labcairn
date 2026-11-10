/**
 * The dev-mode closure rehearsal (plan §4.2, AC-5).
 *
 * The arrangement is the one the repository already has and this rehearsal
 * only joins: Vite on `127.0.0.1:5173`, the service on its own loopback port
 * with `--json` and **no `--static-dir`** — the page comes from Vite — and the
 * workbench's existing proxy carries the API calls to the service without
 * changing the origin header (`web/vite.config.ts`, whose three settings a test
 * reads back). The service's allow-list admits that page because
 * `DEVELOPMENT_ORIGINS` already names its two spellings
 * (`src/labcairn/cli/commands.py:2110`); the shell passes no `--origin`.
 *
 * The Vite proxy's target is fixed at `127.0.0.1:8000`, so the dev service
 * takes port 8000 rather than one the OS chose — the only place in the shell
 * where a port is not OS-chosen, and it is chosen to match an arrangement that
 * already exists rather than to widen anything. The rehearsal refuses rather
 * than displacing something already listening there.
 *
 * What is asserted, in order: the dev switch loads the Vite origin (and only
 * in dev); the page reaches the service through the proxy from its own origin;
 * the status strip says `connected`; the service is killed from outside; the
 * same window says `disconnected`; closing the window leaves no service and
 * frees the port.
 *
 * Act 2 here is the packaged-shaped check on the *same* run's environment:
 * with the dev switch off, the shell names no page URL and loads the service's
 * own origin — the one-line difference §4.2 describes, asserted from the page.
 */

import assert from 'node:assert/strict'
import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import net from 'node:net'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { pageState, Cdp, listTargets, pollUntil, freeLoopbackPort } from './lib/rehearsal-support.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SHELL_ROOT = path.join(HERE, '..')
const REPO_ROOT = path.resolve(SHELL_ROOT, '..')
const repoCheckoutRoot = path.resolve(REPO_ROOT, '..', '..', '..')

const pythonExe =
  process.env.LABCAIRN_SHELL_PYTHON ??
  (process.platform === 'win32'
    ? path.join(repoCheckoutRoot, '.venv', 'Scripts', 'python.exe')
    : path.join(repoCheckoutRoot, '.venv', 'bin', 'python'))
const cliExe = process.env.LABCAIRN_SHELL_CLI ?? path.join(path.dirname(pythonExe), 'labcairn.exe')
const electronExe =
  process.env.LABCAIRN_SHELL_ELECTRON ?? path.join(SHELL_ROOT, 'node_modules', 'electron', 'dist', 'electron.exe')
/**
 * Vite's own entry point, run by this Node rather than through a `.cmd` shim.
 *
 * Node 24 refuses to spawn a `.cmd` without a shell (`spawn EINVAL`), which is
 * what `pnpm dev` on this machine resolves to. Running the installed `vite.js`
 * directly starts the same Vite from the same `web/node_modules` the
 * `pnpm dev` script would, and keeps the rehearsal free of a shell wrapper.
 */
const viteEntry = process.env.LABCAIRN_SHELL_VITE ?? path.join(REPO_ROOT, 'web', 'node_modules', 'vite', 'bin', 'vite.js')

const VITE_ORIGIN = 'http://127.0.0.1:5173'
const DEBUG_PORT = Number(process.env.LABCAIRN_SHELL_DEBUG_PORT ?? (await freeLoopbackPort()))
const scratchRoot = process.env.LABCAIRN_SHELL_SCRATCH ?? 'E:\\labcairn-local\\shell-scratch'

for (const [name, where] of [['python', pythonExe], ['labcairn', cliExe], ['electron', electronExe]]) {
  assert.ok(where !== null && fs.existsSync(where), `the rehearsal cannot find ${name} at ${where}`)
}

function log(...parts) {
  process.stdout.write(`${parts.join(' ')}\n`)
}

const started = []

function track(child, label) {
  started.push({ child, label })
  return child
}

async function endEverything() {
  for (const { child, label } of started) {
    if (child.exitCode !== null || child.signalCode !== null) continue
    if (process.platform === 'win32') {
      spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' })
    } else {
      child.kill('SIGKILL')
    }
    const gone = await waitForExit(child, 8000)
    if (!gone) log(`cleanup: ${label} (pid ${child.pid}) did not report an exit`)
  }
  started.length = 0
}

process.on('unhandledRejection', async (reason) => {
  log(`rehearsal failed: ${reason instanceof Error ? reason.stack : reason}`)
  await endEverything()
  process.exit(1)
})

function waitForExit(child, ms) {
  if (child.exitCode !== null || child.signalCode !== null) return Promise.resolve(true)
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(false), ms)
    child.once('exit', () => {
      clearTimeout(timer)
      resolve(true)
    })
  })
}

/** Strip terminal colour codes before matching a process's own output. */
function stripAnsi(text) {
  return text.replace(/\[[0-9;]*m/g, '')
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

async function assertPortTaken(port, context) {
  const listening = await portIsListening(port)
  assert.equal(listening, true, `nothing listens on ${port} (${context})`)
}

function pidIsGone(pid, context) {
  const listed = spawnSync('tasklist', ['/FI', `PID eq ${pid}`, '/FO', 'CSV', '/NH'], { encoding: 'utf8' })
  assert.equal(
    (listed.stdout ?? '').includes(String(pid)),
    false,
    `pid ${pid} is still in the process table (${context}): ${listed.stdout}`,
  )
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
      'Dev-mode closure rehearsal',
      '--objective',
      'The shell loads the Vite page and reports the service stopping.',
      '--criterion',
      'The window showed the connected and disconnected states.',
      '--json',
    ],
    { encoding: 'utf8', env },
  )
  assert.equal(created.status, 0, `labcairn task create refused: ${created.stderr}`)
  return workspace
}

function startProcess(command, args, { cwd, env = {}, label }) {
  const stdout = []
  const child = spawn(command, args, { cwd, env, windowsHide: true })
  child.stdout.setEncoding('utf8')
  child.stderr.setEncoding('utf8')
  child.stdout.on('data', (chunk) => {
    stdout.push(chunk)
    process.stdout.write(`[${label}] ${chunk}`)
  })
  child.stderr.on('data', (chunk) => process.stdout.write(`[${label} stderr] ${chunk}`))
  track(child, label)
  const waitLine = (needle, timeoutMs = 60_000) =>
    new Promise((resolve, reject) => {
      const deadline = Date.now() + timeoutMs
      const tick = () => {
        // Vite's own banner carries colour codes, and they fall *inside* the
        // phrase being matched: it prints `Local` + `ESC[22m` + `:`, so a
        // pattern for `Local:` misses a line that is right there. The strip is
        // applied to what is matched, not to what is echoed — the log keeps
        // Vite's output as Vite wrote it.
        const match = stripAnsi(stdout.join('')).match(needle)
        if (match !== null) return resolve(match)
        if (child.exitCode !== null || child.signalCode !== null) {
          return reject(new Error(`${label} exited (code ${child.exitCode}) before printing ${needle}`))
        }
        if (Date.now() >= deadline) return reject(new Error(`${label} never printed ${needle}`))
        setTimeout(tick, 150)
      }
      tick()
    })
  return { child, stdout, waitLine }
}

// --------------------------------------------------------------------------- #
// The arrangement: Vite on 5173 serving the repository's own page, the service
// on a loopback port the operating system chose, and the shell in dev mode with
// no static dir — the page comes from Vite.
//
// `web/vite.config.ts` fixes its proxy target at `http://127.0.0.1:8000`, and
// 8000 on this machine belongs to `com.docker.backend.exe` (measured 2026-11-10:
// `netstat` LISTENING, PID 33364). The rehearsal does not displace a listener it
// does not own and does not edit another window's file, so it runs Vite with
// `scripts/vite.dev-rehearsal.config.mjs`: that config imports the real one and
// overrides the target port and nothing else — `changeOrigin: false`, the empty
// headers, the mounted prefix, `host`, `port: 5173` and `strictPort` are all
// inherited, and the config refuses if the real one ever stops saying so.
// --------------------------------------------------------------------------- #
assert.equal(await portIsListening(5173), false, "the Vite port 5173 is already held; close the developer's own Vite first")

const servicePort = await freeLoopbackPort()
const { inherited } = await import('./vite.dev-rehearsal.config.mjs')
// The rehearsal's own load has no port to override with — it picks the port
// after importing and passes it to Vite through the environment. Asserting the
// load it is reading is the un-overridden one is what keeps the log line below
// honest about which value is inherited and which is chosen.
assert.equal(inherited.overrodeTarget, false, 'this load already overrode the target; the rehearsal is not the one choosing the port')
log(
  `inherited proxy: mounted at ${inherited.mountedPrefix}, target ${inherited.baseTarget} -> ` +
    `http://127.0.0.1:${servicePort}, changeOrigin=${inherited.changeOrigin}, ` +
    `host=${inherited.host}, port=${inherited.vitePort}, strictPort=${inherited.strictPort}`,
)
assert.equal(inherited.host, '127.0.0.1', 'the inherited Vite host is not loopback')
assert.equal(inherited.vitePort, 5173, 'the inherited Vite port is not the one the service already answers to')
assert.equal(inherited.changeOrigin, false, 'the inherited proxy rewrites the Host header')
assert(inherited.headers === null || Object.keys(inherited.headers).length === 0, 'the inherited proxy adds headers')

log('=== starting Vite with the inherited configuration ===')
const vite = startProcess(process.execPath, [viteEntry, 'dev', '--config', path.join(HERE, 'vite.dev-rehearsal.config.mjs')], {
  cwd: path.join(REPO_ROOT, 'web'),
  label: 'vite',
  env: { ...process.env, LABCAIRN_DEV_REHEARSAL_SERVICE_PORT: String(servicePort) },
})
await vite.waitLine(/Local:\s+(\S+)/, 90_000)
await assertPortTaken(5173, 'after Vite reported its local URL')
log(`Vite answers on ${VITE_ORIGIN}`)

const workspace = makeWorkspace('dev-vite')
log('=== starting the shell in dev mode ===')
const shell = startProcess(electronExe, ['.', `--remote-debugging-port=${DEBUG_PORT}`], {
  cwd: SHELL_ROOT,
  label: 'shell',
  env: {
    ...process.env,
    LABCAIRN_SHELL_DEV: '1',
    LABCAIRN_SHELL_CLI: cliExe,
    LABCAIRN_SHELL_WORKSPACE: workspace,
    LABCAIRN_SHELL_PORT: String(servicePort),
    LABCAIRN_SHELL_LOG: path.join(scratchRoot, 'dev-vite-service.log'),
    PYTHONPATH: path.join(REPO_ROOT, 'src'),
  },
})

const loaded = (await shell.waitLine(/loaded (\S+)/))[1]
const serviceOrigin = (await shell.waitLine(/service origin=(\S+)/))[1]
const servicePid = Number.parseInt((await shell.waitLine(/child pid=(\d+)/))[1], 10)
log(`loaded ${loaded}; service origin ${serviceOrigin}; service pid ${servicePid}`)

// §4.2's one-line difference, measured at the shell's own output: the dev
// switch loaded the Vite origin, and the service was started without
// `--static-dir` (the drained log is the record of the command's own report).
// Compared by origin rather than by spelling: the property the plan states is
// *which origin the page is on*, and `http://127.0.0.1:5173` and
// `http://127.0.0.1:5173/` are the same origin with different paths.
assert.equal(new URL(loaded).origin, VITE_ORIGIN, 'the dev shell did not load the Vite origin')
assert.equal(serviceOrigin, `http://127.0.0.1:${servicePort}`, 'the dev service is not on the port the rehearsal pointed the proxy at')

const drainedText = fs.readFileSync(path.join(scratchRoot, 'dev-vite-service.log'), 'utf8')
assert.ok(!drainedText.includes('--static-dir'), 'the dev service was started with a static dir; the page was not coming from Vite')
assert.ok(drainedText.includes('"origin"'), 'the drained log holds no ServiceStarting line — the readiness read had nothing to read')

const pages = await listTargets(DEBUG_PORT)
const cdp = new Cdp(pages[0].webSocketDebuggerUrl)

const connected = await pollUntil(() => pageState(cdp), (state) => state.stripStatus === 'connected', 20_000, 'the strip reaching the connected state')
log('dev connected state:', JSON.stringify(connected))
assert.equal(connected.location, VITE_ORIGIN, 'the loaded page is not on the Vite origin')

// The page reaches the API from its own origin, through the inherited proxy.
// The mount is the prefix the real configuration names (`inherited.mountedPrefix`)
// rather than a second copy of the constant — the failure `web/src/api/mount.ts`
// exists to prevent is exactly a proxy mounted somewhere the application does
// not ask for.
const healthPath = `${inherited.mountedPrefix}/health`
const proxiedHealth = await cdp.evaluate(`fetch(${JSON.stringify(healthPath)}).then((response) => response.status)`)
assert.equal(proxiedHealth, 200, `the Vite page could not reach the service through the proxy at ${healthPath}`)
const proxiedBody = JSON.parse(await cdp.evaluate(`fetch(${JSON.stringify(healthPath)}).then((response) => response.text())`))
assert.equal(proxiedBody.port, servicePort, `the proxy answered from another service: ${JSON.stringify(proxiedBody)}`)
log(`dev page reached ${healthPath}: ${proxiedHealth}; the service reports port ${proxiedBody.port}`)

// The service dies from outside: the crash-after-readiness arm.
if (process.platform === 'win32') {
  spawnSync('taskkill', ['/PID', String(servicePid), '/T', '/F'], { stdio: 'ignore' })
} else {
  spawnSync('kill', ['-9', String(servicePid)], { stdio: 'ignore' })
}

const disconnected = await pollUntil(() => pageState(cdp), (state) => state.stripStatus === 'disconnected', 20_000, 'the strip reaching the disconnected state')
log('dev disconnected state:', JSON.stringify(disconnected))
assert.ok(disconnected.stripLabel.includes('disconnected'), `the strip says ${JSON.stringify(disconnected.stripLabel)}`)

await cdp.send('Target.closeTarget', { targetId: pages[0].id })
cdp.close()
const shellGone = await waitForExit(shell.child, 30_000)
assert.ok(shellGone, 'the shell did not exit after its window closed')
assert.equal(shell.child.exitCode, 0, `the shell exited with code ${shell.child.exitCode}, not 0`)
await assertPortFree(servicePort, 'after the dev shell closed its window on a dead service')
log('dev closure result: Vite page + proxied API -> connected -> service killed -> disconnected -> clean exit, port free')

// --------------------------------------------------------------------------- #
// Act 2: the same environment with the dev switch off — the packaged-shaped
// difference, asserted from the page rather than from the code.
// --------------------------------------------------------------------------- #
log('=== act 2: the same environment with the dev switch off ===')
const packagedWorkspace = makeWorkspace('dev-vite-packaged')
const packagedShell = startProcess(electronExe, ['.', `--remote-debugging-port=${DEBUG_PORT}`], {
  cwd: SHELL_ROOT,
  label: 'packaged-shaped',
  env: {
    ...process.env,
    LABCAIRN_SHELL_CLI: cliExe,
    LABCAIRN_SHELL_WORKSPACE: packagedWorkspace,
    LABCAIRN_SHELL_STATIC_DIR: path.join(REPO_ROOT, 'web', 'dist'),
    LABCAIRN_SHELL_LOG: path.join(scratchRoot, 'dev-vite-packaged-service.log'),
    PYTHONPATH: path.join(REPO_ROOT, 'src'),
  },
})
const packagedLoaded = (await packagedShell.waitLine(/loaded (\S+)/))[1]
const packagedOrigin = (await packagedShell.waitLine(/service origin=(\S+)/))[1]
const packagedPid = Number.parseInt((await packagedShell.waitLine(/child pid=(\d+)/))[1], 10)
log(`loaded ${packagedLoaded}; service origin ${packagedOrigin}`)

// Both arms compare by origin. The `notEqual` one is stronger for it: a
// packaged-shaped run that loaded *any* page on the dev origin — with a path,
// without a path, with a query — is refused here, where a spelling comparison
// would let a differently-spelled dev page through. A `file://` load arrives as
// origin `"null"`, which matches neither side.
assert.notEqual(new URL(packagedLoaded).origin, VITE_ORIGIN, 'the packaged-shaped run loaded the dev page — the dev switch is not dev-only')
assert.equal(new URL(packagedLoaded).origin, packagedOrigin, 'the packaged-shaped run did not load the service origin')

await assertPortTaken(new URL(packagedOrigin).port, 'while the packaged-shaped shell ran')
const packagedPages = await listTargets(DEBUG_PORT)
const packagedCdp = new Cdp(packagedPages[0].webSocketDebuggerUrl)
const packagedState = await pollUntil(() => pageState(packagedCdp), (state) => state.stripStatus === 'connected', 20_000, 'the packaged-shaped run reaching the connected state')
assert.equal(packagedState.location, packagedOrigin, 'the packaged-shaped page is not on the service origin')
const packagedHealth = await packagedCdp.evaluate(`fetch('/health').then((response) => response.status)`)
assert.equal(packagedHealth, 200, 'the packaged-shaped page could not reach its own /health')

await packagedCdp.send('Target.closeTarget', { targetId: packagedPages[0].id })
packagedCdp.close()
const packagedGone = await waitForExit(packagedShell.child, 30_000)
assert.ok(packagedGone, 'the packaged-shaped shell did not exit after its window closed')
assert.equal(packagedShell.child.exitCode, 0, `the packaged-shaped shell exited with code ${packagedShell.child.exitCode}`)
pidIsGone(packagedPid, 'after the packaged-shaped shell closed its window')
await assertPortFree(new URL(packagedOrigin).port, 'after the packaged-shaped shell exited')
log('act 2 result: no dev URL in a packaged-shaped run; the page is the service origin; clean exit, no orphan')

await endEverything()
assert.equal(await portIsListening(5173), false, 'Vite is still listening after the rehearsal ended it')
log('=== dev-mode closure rehearsal passed ===')
log(`scratch workspace (dev): ${workspace}`)
log(`scratch workspace (packaged-shaped): ${packagedWorkspace}`)
log(`drained logs: ${path.join(scratchRoot, 'dev-vite-service.log')}, ${path.join(scratchRoot, 'dev-vite-packaged-service.log')}`)
void net
