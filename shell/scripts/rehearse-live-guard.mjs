/**
 * T05's live 401 half-loop, in a real Electron window (plan AC-4).
 *
 * A real `labcairn serve` starts from a scratch workspace; the shell's own
 * supervisor and window load the served origin; the sandboxed preload asks the
 * main process for permission, is granted, and sends one fixed tokenless
 * `POST /task/select` of its own; the service's `SessionGuard` refuses 401
 * `session_required`; the main process validates the IPC sender's origin before
 * believing the report and echoes the verdict; and the status strip shows it.
 * The witness reads all three surfaces back over CDP: the DOM strip, the
 * enumerable bridge, and the main process's printed line.
 *
 * **What the mutation is.** `POST /task/select` with no `Authorization` header.
 * `@electron/get`'s binary download is the only remote channel the shell
 * depends on and is recorded in the selection record, plan §4.4 and
 * `test/dependency-surface.test.mjs`; nothing in the live probe is.
 *
 * This is not a §12/§13 mapping dry-run and is entered in no execution plan
 * §4 row. Scratch, logs and temp state live outside the repository. A non-zero
 * exit is the failure; no assertion is inferred from a missing line.
 */

import assert from 'node:assert/strict'
import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { Cdp, listTargets, pageState, pollUntil, freeLoopbackPort } from './lib/rehearsal-support.mjs'
import { assertPaths, shellPaths } from './lib/shell-paths.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const paths = shellPaths({ here: HERE })
assertPaths(paths)

const debugPort = Number(process.env.LABCAIRN_SHELL_DEBUG_PORT ?? (await freeLoopbackPort()))
const workspace = path.join(paths.scratchRoot, `live-guard-${Date.now()}`)
const serviceLog = path.join(paths.scratchRoot, `live-guard-${Date.now()}.log`)

const env = { ...process.env, COLUMNS: '200', PYTHONIOENCODING: 'utf-8', PYTHONPATH: paths.productSrc }
for (const [args, label] of [
  [['--workspace', workspace, 'init'], 'init'],
  [['--workspace', workspace, 'task', 'create', '--title', 'Live guard rehearsal', '--objective', 'A mutation without the session token is refused', '--criterion', 'The window shows 401 session_required', '--json'], 'task create'],
]) {
  const done = spawnSync(paths.cliExe, args, { encoding: 'utf8', env })
  assert.equal(done.status, 0, `${label} refused: ${done.stderr}`)
}

let stdout = ''
const shell = spawn(paths.electronExe, ['.', `--remote-debugging-port=${debugPort}`], {
  cwd: paths.shellRoot,
  windowsHide: true,
  env: {
    ...env,
    LABCAIRN_SHELL_ROOT: paths.shellRoot,
    LABCAIRN_SHELL_REPO_ROOT: paths.repoRoot,
    LABCAIRN_SHELL_PRODUCT_SRC: paths.productSrc,
    LABCAIRN_SHELL_CLI: paths.cliExe,
    LABCAIRN_SHELL_WORKSPACE: workspace,
    LABCAIRN_SHELL_STATIC_DIR: '',
    LABCAIRN_SHELL_LOG: serviceLog,
  },
})
shell.stdout.setEncoding('utf8')
shell.stderr.setEncoding('utf8')
shell.stdout.on('data', (chunk) => {
  stdout += chunk
  process.stdout.write(`[shell] ${chunk}`)
})
shell.stderr.on('data', (chunk) => process.stdout.write(`[shell stderr] ${chunk}`))

/** Cleanup is part of the witness: a left-behind service would make the next run measure a foreign tree. */
function endShell() {
  if (shell.exitCode === null && shell.signalCode === null) {
    if (process.platform === 'win32') spawnSync('taskkill', ['/PID', String(shell.pid), '/T', '/F'], { stdio: 'ignore' })
    else shell.kill('SIGKILL')
  }
}
process.on('unhandledRejection', (reason) => {
  process.stderr.write(`rehearsal failed: ${reason instanceof Error ? reason.stack : String(reason)}\n`)
  endShell()
  process.exit(1)
})

async function waitForLine(needle, timeoutMs = 60_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const match = stdout.match(needle)
    if (match !== null) return match
    await new Promise((resolve) => setTimeout(resolve, 150))
  }
  assert.fail(`the shell never printed ${needle}; stdout was:\n${stdout}`)
}

try {
  const loaded = await waitForLine(/loaded (\S+)/)
  const origin = (await waitForLine(/service origin=(\S+)/))[1]
  assert.equal(loaded[1], `${origin}/`, 'the loaded page is not the service origin root')

  // The grant half of the request-and-grant shape: the page the shell loaded
  // is a sender this process is willing to believe.
  const granted = await waitForLine(/guard-request origin (\S+)/)
  assert.equal(granted[1], origin, `the page's guard request was decided for origin ${granted[1]}, not the loaded origin`)
  assert.ok(!/refused guard-request/.test(stdout), 'the loaded page was refused its own guard probe')

  const pages = await listTargets(debugPort)
  const cdp = new Cdp(pages[0].webSocketDebuggerUrl)
  const state = await pollUntil(
    () => pageState(cdp),
    (seen) => seen.stripStatus === 'connected' && seen.guardStatus === '401 session_required',
    20_000,
    'the live guard reaching its measured refusal',
  )
  process.stdout.write(`live guard window state: ${JSON.stringify(state)}\n`)
  assert.equal(state.location, origin, 'the page is not on the service origin')
  assert.equal(state.stripStatus, 'connected', 'the live probe disturbed the connected state')
  assert.equal(state.bridgeStatus, 'connected', 'the status bridge did not stay connected')
  assert.equal(state.stripGuard, '401 session_required', 'the strip did not display the refusal as a status')
  assert.equal(state.guardStatus, '401 session_required', 'the bridge did not report the refusal')

  const printed = await waitForLine(/mutation refused: 401 session_required \(sender origin (\S+)\)/)
  assert.equal(printed[1], origin, 'the guard report was accepted from a different sender origin')

  const bridgeKeys = await cdp.evaluate('Object.keys(window.labcairnShell).sort()')
  assert.deepEqual(bridgeKeys, ['guard', 'status'], 'the native surface is not the two read-only getters')
  const strings = await cdp.evaluate('Object.values(window.labcairnShell).filter((value) => typeof value === "string")')
  assert.deepEqual(strings, [], 'a native string value could carry a session token')
  const fetchedAgain = await cdp.evaluate(`fetch('/task/select', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{"task_id":"00000000-0000-7000-8000-000000000000"}' }).then((response) => response.status)`)
  assert.equal(fetchedAgain, 401, 'the same tokenless mutation was not refused by the service')
  const readAgain = await pollUntil(
    () => pageState(cdp),
    (seen) => seen.guardStatus === '401 session_required' && seen.stripGuard === '401 session_required',
    10_000,
    'the strip still reporting the refusal',
  )
  assert.equal(readAgain.stripStatus, 'connected', 'the probe left the window in a state other than connected')

  cdp.close()
  process.stdout.write('live guard half-loop: 401 session_required measured, printed and displayed\n')
} finally {
  endShell()
}
