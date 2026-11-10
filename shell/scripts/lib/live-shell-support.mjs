/**
 * Shared support for the shell's live lifecycle witnesses (T06).
 *
 * The three arms need the same real shell: a scratch workspace outside the
 * repository, the installed console script, this worktree's `src` on
 * `PYTHONPATH`, a free CDP/debug port, and cleanup that cannot leave an
 * Electron or a service child behind. A witness that shares a stale port or a
 * dirty workspace has measured its own leftover, not the arm it names.
 */

import assert from 'node:assert/strict'
import { spawn, spawnSync } from 'node:child_process'
import net from 'node:net'
import path from 'node:path'

import { Cdp, listTargets, pageState, pollUntil, freeLoopbackPort } from './rehearsal-support.mjs'
import { shellPaths, shellUserDataDir } from './shell-paths.mjs'

const WINDOWS = process.platform === 'win32'

/** A fresh, initialised workspace with one task; the arm owns its own path. */
export function makeWorkspace({ cli, productSrc, scratchRoot, label }) {
  const workspace = path.join(scratchRoot, `${label}-${Date.now()}`)
  const env = { ...process.env, COLUMNS: '200', PYTHONIOENCODING: 'utf-8', PYTHONPATH: productSrc }
  for (const [args, name] of [
    [['--workspace', workspace, 'init'], 'init'],
    [['--workspace', workspace, 'task', 'create', '--title', `${label} witness task`, '--objective', 'The lifecycle arm leaves no orphan', '--criterion', 'The child is gone and the port is free', '--json'], 'task create'],
  ]) {
    const done = spawnSync(cli, args, { encoding: 'utf8', env })
    assert.equal(done.status, 0, `${name} refused: ${done.stderr}`)
  }
  return workspace
}

/**
 * Start a real shell with its own CDP port and, optionally, its own main-
 * process inspector port. The inspector is how the crash arm injects an
 * uncaught exception into the *real* main process rather than changing its
 * code to throw on a timer.
 */
export async function startLiveShell({ here, label, workspace, inspectPort = null, debugPort = null, userDataDir = null }) {
  const paths = shellPaths({ here })
  const chosenDebugPort = Number(debugPort ?? process.env.LABCAIRN_SHELL_DEBUG_PORT ?? (await freeLoopbackPort()))
  // One userData per run unless the caller *wants* two shells to share one —
  // which is exactly what the second-instance arm needs, because Electron's
  // single-instance lock lives in userData and a shared lock is the property
  // being witnessed. See `shellUserDataDir`'s note.
  const userData = userDataDir ?? shellUserDataDir(paths.scratchRoot, label)
  const args = ['.', `--remote-debugging-port=${chosenDebugPort}`, `--user-data-dir=${userData}`]
  if (inspectPort !== null) args.push(`--inspect=${inspectPort}`)
  const child = spawn(paths.electronExe, args, {
    cwd: paths.shellRoot,
    windowsHide: true,
    env: {
      ...process.env,
      COLUMNS: '200',
      PYTHONIOENCODING: 'utf-8',
      PYTHONPATH: paths.productSrc,
      LABCAIRN_SHELL_ROOT: paths.shellRoot,
      LABCAIRN_SHELL_REPO_ROOT: paths.repoRoot,
      LABCAIRN_SHELL_PRODUCT_SRC: paths.productSrc,
      LABCAIRN_SHELL_CLI: paths.cliExe,
      LABCAIRN_SHELL_WORKSPACE: workspace,
      LABCAIRN_SHELL_STATIC_DIR: '',
      LABCAIRN_SHELL_LOG: path.join(paths.scratchRoot, `${label}-service.log`),
    },
  })
  let stdout = ''
  let stderr = ''
  child.stdout.setEncoding('utf8')
  child.stderr.setEncoding('utf8')
  child.stdout.on('data', (chunk) => {
    stdout += chunk
    process.stdout.write(`[${label} out] ${chunk}`)
  })
  child.stderr.on('data', (chunk) => {
    stderr += chunk
    process.stdout.write(`[${label} err] ${chunk}`)
  })
  return {
    child,
    debugPort: chosenDebugPort,
    userData,
    paths,
    get stdout() { return stdout },
    get stderr() { return stderr },
  }
}

/** Wait for a line the shell itself printed; a missing line is not a pass. */
export async function waitForLine(shell, needle, timeoutMs = 60_000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const match = shell.stdout.match(needle)
    if (match !== null) return match
    await sleep(150)
  }
  assert.fail(`the shell never printed ${needle}; stdout was:\n${shell.stdout}`)
}

export function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/** End a child and its whole Windows process tree. */
export function killTree(child) {
  if (child.exitCode !== null || child.signalCode !== null) return
  if (WINDOWS) spawnSync('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore' })
  else child.kill('SIGKILL')
}

export function pidIsGone(pid) {
  if (!WINDOWS) {
    try {
      process.kill(pid, 0)
      return false
    } catch {
      return true
    }
  }
  const listed = spawnSync('tasklist', ['/FI', `PID eq ${pid}`, '/FO', 'CSV', '/NH'], { encoding: 'utf8' })
  return !listed.stdout.includes(`"${pid}"`)
}

export function portIsListening(port) {
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

export async function assertPortFree(port, context, timeoutMs = 10_000) {
  const deadline = Date.now() + timeoutMs
  for (;;) {
    if (!(await portIsListening(port))) return
    if (Date.now() >= deadline) break
    await sleep(300)
  }
  assert.fail(`something still listens on ${port} (${context})`)
}

/** Page/CDP reading, re-exported so every arm uses one reader. */
export { Cdp, listTargets, pageState, pollUntil, freeLoopbackPort }

/** Inject one uncaught exception into a running main process over its inspector. */
export async function injectMainCrash(inspectPort, timeoutMs = 20_000) {
  const deadline = Date.now() + timeoutMs
  let target = null
  while (Date.now() < deadline && target === null) {
    try {
      const response = await fetch(`http://127.0.0.1:${inspectPort}/json/list`)
      const list = await response.json()
      if (list.length > 0) target = list[0]
    } catch {
      // the inspector is not listening yet
    }
    if (target === null) await sleep(200)
  }
  assert.ok(target !== null, `the main-process inspector at ${inspectPort} exposed no target`)
  const socket = new WebSocket(target.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => {
    socket.addEventListener('open', resolve, { once: true })
    socket.addEventListener('error', reject, { once: true })
  })
  socket.send(JSON.stringify({
    id: 1,
    method: 'Runtime.evaluate',
    params: { expression: 'setTimeout(() => { throw new Error("WITNESS_INJECTED_CRASH") }, 20)' },
  }))
  await sleep(300)
  socket.close()
}
