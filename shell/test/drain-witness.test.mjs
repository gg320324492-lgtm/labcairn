/**
 * The drain witness (plan AC-3, §3's witness design).
 *
 * A control pair, not a source reading. The same child and the same dose run
 * twice through the production supervisor's spawn path — **drained** (the
 * production reader shape) and **undrained** (the harness switch) — and the
 * undrained arm must *reproduce the stall*: the dose request times out while
 * the child stays alive. A witness that stays green in both arms has measured
 * nothing, and this file asserts exactly that pairing.
 *
 * **The dose is measured, on this machine, in the arrangement the arms use.**
 * `measureStallThreshold()` runs the ladder: a probe child with this spawn
 * shape writes N bytes to its own stdout in the fixture's own write style
 * (a buffered blocking `write` + `flush`), with no reader attached, and the
 * ladder finds the first N that does not complete. The numbers this machine
 * produced on 2026-11-10, in the three arrangements, are part of why the
 * witness measures rather than carries:
 * - an anonymous `os.pipe()`: 4,096 (`docs/acceptance/o6-event-stream-stall-2026-11-10.md` §4);
 * - a `node:child_process.spawn` pipe read non-blocking from the child's fd 1: 88,064;
 * - the same spawn pipe written in the fixture's blocking buffered style: 114,688 completes, 131,072 stalls.
 * A dose sized from 4,096 — the number the *record* carries — overflowed
 * nothing in the second arrangement, and an "undrained arm" that never stalls
 * is a witness that measured nothing. That is this file's own first failure,
 * measured and corrected the same day; the ladder is the correction.
 *
 * **The writer child is Python** (`fixtures/writer_child.py`) for the reason
 * named in that file: Node buffers pipe writes asynchronously and its loop
 * keeps serving, so a Node writer would shrug off a full pipe. Python's
 * blocking `flush()` parks its single-threaded responder — O6's shape.
 *
 * **The port assertions retry, and the orphan check is a process query.** The
 * first run held the port for ~250 ms after a clean child stop; `netstat`
 * showed only `TIME_WAIT` rows owned by PID 0 — the witness's own keep-alive
 * connections, not a process. A listener that answers nothing is the O6
 * defect; a socket in `TIME_WAIT` is the operating system finishing a close.
 * The assertion waits for the listening socket to be gone and fails only if
 * it is still there, and asks the process table whether the child survives.
 *
 * **What this file does not assert, and why.** It does not assert that the
 * stop landed by the graceful ask (`forced === false`, the assertion the G1
 * Python helper makes of itself). Measured on 2026-11-10 on this machine, no
 * combination of `child.kill('SIGBREAK' | 'SIGTERM' | 'SIGINT')` × spawn
 * arrangement reached the Python child's signal handlers — Node's `kill` on
 * Windows terminates rather than signals, and console-control events do not
 * reach a `windowsHide` child. The witness therefore asserts what is measured
 * here (the child ends; the port releases; no orphan survives) and records
 * `forced` in its output; the graceful-ask arm is AC-2 / plan T06's, and
 * `docs/acceptance/LC-P3-05-shell-skeleton-2026-11-10.md` carries the
 * measurement that says why it is not asserted here.
 */

import assert from 'node:assert/strict'
import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { ServiceSupervisor, freeLoopbackPort } from '../src/service-supervisor.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE = path.join(HERE, 'fixtures', 'writer_child.py')
const REPO_ROOT = path.resolve(HERE, '..', '..')

/** The dose margin above the measured stall threshold: over it, still bounded. */
const DOSE_MARGIN = 8 * 1024

/** The ladder the capacity sweep walks, in bytes. */
const CAPACITY_LADDER = [8192, 16384, 32768, 65536, 131072, 262144, 524288, 1048576]

/** A probe that has not reported by now is parked. */
const PROBE_TIMEOUT_MS = 4000

/** A request that does not answer within this long counts as a stall. */
const REQUEST_TIMEOUT_MS = 6000

/** How long a stopped child's port may take to stop answering. */
const PORT_FREE_TIMEOUT_MS = 10000

const scratchRoot =
  process.env.LABCAIRN_SHELL_TEST_TMP ??
  (process.platform === 'win32'
    ? 'E:\\labcairn-local\\shell-test-tmp'
    : path.join(os.tmpdir(), 'labcairn-shell-test-tmp'))

function pythonCandidates() {
  return [
    process.env.LABCAIRN_SHELL_PYTHON,
    // The checkout this shell sits in's own virtualenv: the worktree is at
    // `<repo>/.claude/worktrees/<name>`, so the repository root is three up.
    process.platform === 'win32'
      ? path.join(REPO_ROOT, '..', '..', '..', '.venv', 'Scripts', 'python.exe')
      : path.join(REPO_ROOT, '..', '..', '..', '.venv', 'bin', 'python'),
    'python3',
    'python',
  ].filter((candidate) => typeof candidate === 'string' && candidate.length > 0)
}

/**
 * Resolve the interpreter and the console script together.
 *
 * The console script is taken from the resolved interpreter's own directory —
 * the rule `tests/workbench_serve_support.py`'s `console_script()` states and
 * the reason it gives: an interpreter's launcher and its installed scripts
 * are one environment, and "the script of the environment running these
 * tests" is a fact only when it is read from that interpreter's own directory
 * (`CLAUDE.md`, *A copied virtualenv is not a virtualenv of its own*).
 */
function resolveEnvironment() {
  const pythonCandidatesList = pythonCandidates()
  let fallbackPython = null
  for (const candidate of pythonCandidatesList) {
    const probed = spawnSync(candidate, ['-c', 'print("ok")'], { encoding: 'utf8' })
    if (!(probed.status === 0 && probed.stdout.trim() === 'ok')) continue
    fallbackPython ??= candidate
    const resolvedPython = probed.error ? candidate : path.resolve(candidate)
    const siblingCli = path.join(
      path.dirname(resolvedPython),
      process.platform === 'win32' ? 'labcairn.exe' : 'labcairn',
    )
    if (fs.existsSync(siblingCli)) return { python: resolvedPython, cli: process.env.LABCAIRN_SHELL_CLI ?? siblingCli }
  }
  if (fallbackPython !== null) {
    return {
      python: fallbackPython,
      cli: process.env.LABCAIRN_SHELL_CLI ?? null,
      note: `no labcairn console script beside ${fallbackPython}; set LABCAIRN_SHELL_CLI for the arms that start the service`,
    }
  }
  throw new Error(
    `the drain witness needs a Python for its writer fixture (tried: ${pythonCandidatesList.join(', ')}); ` +
      'set LABCAIRN_SHELL_PYTHON',
  )
}

const environment = resolveEnvironment()
const PYTHON = environment.python
const CLI = environment.cli

/**
 * The child environment the arms use. `PYTHONPATH` names this tree's `src` so
 * that a witness running from a worktree measures *this* checkout's product
 * code and not the editable install's home (`CLAUDE.md`, *A copied virtualenv
 * is not a virtualenv of its own*).
 */
function childEnv(extra = {}) {
  return {
    ...process.env,
    COLUMNS: '200',
    PYTHONIOENCODING: 'utf-8',
    PYTHONPATH: path.join(REPO_ROOT, 'src'),
    ...extra,
  }
}

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

async function forceTree(child) {
  if (await waitForExit(child, 1000)) return
  if (process.platform === 'win32') {
    await new Promise((resolve) => {
      const killer = spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore', windowsHide: true })
      killer.once('exit', resolve)
      killer.once('error', resolve)
    })
  } else {
    try {
      child.kill('SIGKILL')
    } catch {
      // gone
    }
  }
  await waitForExit(child, 3000)
}

/**
 * The capacity ladder: a probe child in *this* spawn arrangement writes N
 * bytes to its own stdout in the fixture's write style — a buffered blocking
 * write and a flush — then reports through a marker file (its stdout is the
 * pipe under measurement, so nothing may be trusted to come back through it).
 * No reader is attached to the pipe. A probe that reports is `fits`; a probe
 * that is still parked at the deadline is `stalls`.
 */
const PROBE_SCRIPT = [
  'import sys, pathlib',
  'n = int(sys.argv[1])',
  "sys.stdout.write('x' * n)",
  "sys.stdout.write('\\n')",
  'sys.stdout.flush()',
  "pathlib.Path(sys.argv[2]).write_text('done')",
].join('\n')

async function measureStallThreshold() {
  const dir = path.join(scratchRoot, `capacity-${Date.now()}`)
  fs.mkdirSync(dir, { recursive: true })
  const ladder = []
  for (const n of CAPACITY_LADDER) {
    const marker = path.join(dir, `probe-${n}.txt`)
    if (fs.existsSync(marker)) fs.unlinkSync(marker)
    const child = spawn(PYTHON, ['-I', '-c', PROBE_SCRIPT, String(n), marker], {
      cwd: dir,
      env: childEnv(),
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
      detached: true,
    })
    // No `data` handler and no `resume()`: the pipe is unread, which is the
    // arrangement under measurement. Waiting on the event loop is safe — a
    // paused Node stream never starts reading, so the pipe really fills.
    const deadline = Date.now() + PROBE_TIMEOUT_MS
    let fitted = false
    while (Date.now() < deadline) {
      if (fs.existsSync(marker)) {
        fitted = true
        break
      }
      await new Promise((resolve) => setTimeout(resolve, 100))
      if (child.exitCode !== null || child.signalCode !== null) {
        fitted = fs.existsSync(marker)
        break
      }
    }
    ladder.push(`${n}:${fitted ? 'fits' : 'stalls'}`)
    if (!fitted) {
      await forceTree(child)
      return { threshold: n, ladder: [...ladder] }
    }
    await forceTree(child)
  }
  assert.fail(
    `no dose up to ${CAPACITY_LADDER.at(-1)} bytes parked a writer in this arrangement ` +
      `(${ladder.join(' ')}); the witness cannot demonstrate the stall on this machine`,
  )
}

async function fetchAnswer(port, pathname, timeoutMs = REQUEST_TIMEOUT_MS) {
  const startedAt = Date.now()
  try {
    const response = await fetch(`http://127.0.0.1:${port}${pathname}`, {
      signal: AbortSignal.timeout(timeoutMs),
    })
    const body = await response.text()
    return { answered: true, status: response.status, body, ms: Date.now() - startedAt }
  } catch {
    return { answered: false, status: null, body: null, ms: Date.now() - startedAt }
  }
}

async function waitUntilAnswering(port, timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const probe = await fetchAnswer(port, '/status', 1500)
    if (probe.answered) return
    await new Promise((resolve) => setTimeout(resolve, 200))
  }
  throw new Error(`the writer child never answered on port ${port}`)
}

function portIsListening(port, timeoutMs = 1500) {
  return new Promise((resolve) => {
    const socket = net.connect({ host: '127.0.0.1', port }, () => {
      socket.destroy()
      resolve(true)
    })
    socket.setTimeout(timeoutMs, () => {
      socket.destroy()
      resolve(false)
    })
    socket.on('error', () => resolve(false))
  })
}

async function assertPortReleased(port, context) {
  const deadline = Date.now() + PORT_FREE_TIMEOUT_MS
  let listening = null
  for (;;) {
    listening = await portIsListening(port)
    if (!listening) return
    if (Date.now() >= deadline) break
    await new Promise((resolve) => setTimeout(resolve, 300))
  }
  assert.equal(listening, false, `port ${port} is still held after the supervisor stopped its child (${context})`)
}

/**
 * Ask the process table whether the child survived.
 *
 * The assertion is on the pid's appearance in the output rather than on the
 * row count, because `tasklist`'s "no match" line is localised: on this
 * machine it is Chinese and arrives in a code page the parent does not decode,
 * so counting its rows is a claim about the locale. A pid is either named in
 * the table or it is not, whichever language the table speaks.
 */
function assertNoOrphan(pid, context) {
  if (process.platform !== 'win32') {
    const listed = spawnSync('ps', ['-p', String(pid), '-o', 'pid='], { encoding: 'utf8' })
    assert.equal(
      (listed.stdout ?? '').includes(String(pid)),
      false,
      `pid ${pid} is still running after the supervisor stopped it (${context})`,
    )
    return
  }
  const listed = spawnSync('tasklist', ['/FI', `PID eq ${pid}`, '/FO', 'CSV', '/NH'], { encoding: 'utf8' })
  assert.equal(
    (listed.stdout ?? '').includes(String(pid)),
    false,
    `pid ${pid} is still in the process table after the supervisor stopped it (${context}): ${listed.stdout}`,
  )
}

function scratchPaths(name) {
  const dir = path.join(scratchRoot, `${name}-${Date.now()}`)
  fs.mkdirSync(dir, { recursive: true })
  return { dir, logPath: path.join(dir, 'service.log') }
}

/**
 * Start the writer child through the production supervisor's spawn path.
 * `readiness: false` because the fixture is not the product: it reports
 * `writer-ready <port>`, not a `ServiceStarting` line — and the witness is
 * about the pipes, not about the service's own readiness grammar. The
 * production path (readiness on) is rehearsed end to end against a real
 * `labcairn serve` by `scripts/rehearse-loop.mjs`.
 */
async function startWriterChild({ port, dose, drain, label }) {
  const { logPath } = scratchPaths(label)
  const supervisor = new ServiceSupervisor({ command: PYTHON, env: childEnv(), cwd: path.dirname(FIXTURE), logPath })
  const { child } = await supervisor.start({
    port,
    commandOverride: PYTHON,
    argsOverride: [FIXTURE, String(port), String(dose)],
    drain,
    readiness: false,
  })
  return { supervisor, child }
}

const measurement = await measureStallThreshold()
const dose = measurement.threshold + DOSE_MARGIN

test(`the dose (${dose}) exceeds the spawn-pipe stall threshold measured here (${measurement.threshold})`, () => {
  // The gate the plan's §3 Arm A states as a requirement: "a dose too small
  // to overflow fails the test rather than passing quietly".
  assert.ok(dose > measurement.threshold)
  // The ladder is kept in the report: it is the number the record cites.
  process.stdout.write(`measured stall ladder: ${measurement.ladder.join(' ')}\n`)
})

test('drained arm: the same child and dose answer before, during and after', async () => {
  const port = await freeLoopbackPort()
  const { supervisor, child } = await startWriterChild({ port, dose, drain: true, label: 'drained' })

  try {
    await waitUntilAnswering(port)
    const before = await fetchAnswer(port, '/status')
    assert.ok(before.answered, `the pre-dose read did not answer: ${JSON.stringify(before)}`)

    const during = await fetchAnswer(port, '/ping')
    assert.ok(
      during.answered && during.status === 200,
      `the ${dose}-byte dose stalled although the pipes are drained: ${JSON.stringify(during)}`,
    )

    for (let i = 0; i < 3; i += 1) {
      const after = await fetchAnswer(port, '/status')
      assert.ok(after.answered, `post-dose read ${i + 1} stalled: ${JSON.stringify(after)}`)
    }

    // The drained bytes are *in* the bounded log: the arrangement kept the
    // pipe moving and kept the bytes.
    assert.ok(
      supervisor.sink.writtenBytes >= dose,
      `only ${supervisor.sink.writtenBytes} bytes reached the log; the ${dose}-byte dose was not drained into it`,
    )
  } finally {
    const outcome = await supervisor.stop()
    assert.notEqual(outcome, null, 'the drained child was never stopped')
    process.stdout.write(`drained arm stop outcome: ${JSON.stringify(outcome)}\n`)
  }
  assert.equal(child.exitCode !== null || child.signalCode !== null, true, 'the drained child is still running')
  assertNoOrphan(child.pid, 'drained arm')
  await assertPortReleased(port, 'drained arm')
})

test('undrained arm: the same child and the same dose reproduce the stall', async () => {
  const port = await freeLoopbackPort()
  const { supervisor, child } = await startWriterChild({ port, dose, drain: false, label: 'undrained' })

  try {
    await waitUntilAnswering(port)

    const doseResult = await fetchAnswer(port, '/ping')
    assert.equal(
      doseResult.answered,
      false,
      'the dose request answered on the undrained arm, so the dose did not fill the pipe and the ' +
        `drained arm measured nothing (threshold measured here: ${measurement.threshold}; dose: ${dose})`,
    )

    // The parked writer serves nothing — while its listener is still there.
    const after = await fetchAnswer(port, '/status', 2500)
    assert.equal(after.answered, false, 'an ordinary read answered although the writer was parked')
    assert.equal(
      child.exitCode === null && child.signalCode === null,
      true,
      'the child exited rather than stalling; a dead child is not the O6 defect',
    )
    assert.equal(
      supervisor.sink.writtenBytes,
      0,
      'the undrained arm drained bytes into the log — it is not the undrained arm it claims to be',
    )
  } finally {
    const outcome = await supervisor.stop()
    assert.notEqual(outcome, null, 'the stalled child was never stopped')
    process.stdout.write(`undrained arm stop outcome: ${JSON.stringify(outcome)}\n`)
  }
  assertNoOrphan(child.pid, 'undrained arm')
  await assertPortReleased(port, 'undrained arm')
})

test('the real service answers the production path with the readers attached', async () => {
  // Plan §3's Arm C in miniature: no injection, the production command and the
  // production readiness read, against a real `labcairn serve` in a scratch
  // workspace outside the repository. (The plan's full Arm C adds a synthetic
  // task and a token-carrying POST; that half belongs to the same file at
  // T06's lifecycle pass and is named as open in the acceptance record.)
  const workspace = path.join(scratchRoot, `arm-c-ws-${Date.now()}`)
  const initialised = spawnSync(CLI, ['--workspace', workspace, 'init'], { encoding: 'utf8', env: childEnv() })
  assert.equal(initialised.status, 0, `labcairn init refused: ${initialised.stderr}`)
  const created = spawnSync(
    CLI,
    [
      '--workspace',
      workspace,
      'task',
      'create',
      '--title',
      'Drain witness task',
      '--objective',
      'The shell supervisor drains the service child it starts.',
      '--criterion',
      'The service answered its own health route.',
      '--json',
    ],
    { encoding: 'utf8', env: childEnv() },
  )
  assert.equal(created.status, 0, `labcairn task create refused: ${created.stderr}`)

  const { logPath } = scratchPaths('arm-c')
  const supervisor = new ServiceSupervisor({ command: CLI, env: childEnv(), cwd: scratchRoot, logPath })
  const { starting, child } = await supervisor.start({ workspace })
  try {
    assert.ok(starting.origin.endsWith(`:${starting.port}`), `ServiceStarting.origin does not carry its port: ${starting.origin}`)
    for (const route of ['/health', '/tasks', '/openapi.json']) {
      const answer = await fetchAnswer(starting.port, route)
      assert.ok(answer.answered && answer.status === 200, `the real service did not answer ${route}: ${JSON.stringify(answer)}`)
    }

    // AC-1's allow-list half, read back from the service rather than asserted
    // about the shell: the supervisor passes no `--origin`, so what the service
    // says it answers to is its own list — its origin plus the two development
    // spellings — and a shell-added entry would show up here as a third one.
    // `/health` is asked too because it is the service's own report of the same
    // list: the two agreeing is the assertion, not either one alone.
    const expectedOrigins = [starting.origin, 'http://127.0.0.1:5173', 'http://localhost:5173'].sort()
    assert.deepEqual([...starting.origins].sort(), expectedOrigins, `ServiceStarting.origins is not the service's own list: ${JSON.stringify(starting.origins)}`)
    const healthAnswer = await fetch(`http://127.0.0.1:${starting.port}/health`).then((response) => response.json())
    assert.deepEqual([...healthAnswer.origins].sort(), expectedOrigins, `GET /health reports a different allow-list: ${JSON.stringify(healthAnswer.origins)}`)
    assert.equal(healthAnswer.port, starting.port, 'GET /health answers on a port other than the one ServiceStarting reported')

    // The drained output is in the log: the production path drained what the
    // service wrote about itself.
    assert.ok(supervisor.sink.writtenBytes > 0, 'the production path drained nothing into the log')
  } finally {
    const outcome = await supervisor.stop()
    assert.notEqual(outcome, null)
    process.stdout.write(`arm C stop outcome: ${JSON.stringify(outcome)}\n`)
  }
  assertNoOrphan(child.pid, 'arm C')
  await assertPortReleased(starting.port, 'arm C')
})

test('a foreign listener on the chosen port is a refusal, not a page to load', async () => {
  const port = await freeLoopbackPort()
  const foreign = spawn(process.execPath, [
    '-e',
    `require('http').createServer((_req,res)=>res.end('foreign')).listen(${port},'127.0.0.1')`,
  ], { stdio: 'ignore' })
  try {
    await waitUntilAnswering(port, 20000)

    const workspace = path.join(scratchRoot, `occupied-ws-${Date.now()}`)
    const initialised = spawnSync(CLI, ['--workspace', workspace, 'init'], { encoding: 'utf8', env: childEnv() })
    assert.equal(initialised.status, 0, `labcairn init refused: ${initialised.stderr}`)

    const { logPath } = scratchPaths('occupied')
    const supervisor = new ServiceSupervisor({ command: CLI, env: childEnv(), cwd: scratchRoot, logPath })
    await assert.rejects(
      supervisor.start({ port, workspace }),
      /did not start/,
      'the supervisor reported a service on a port somebody else was holding',
    )

    // The listener the shell refused is still the only thing on the port:
    // a refusal must not become a takeover. (Asserted *before* the foreign
    // listener is stopped below — after it, nothing would be listening.)
    const stillForeign = await fetchAnswer(port, '/', 2500)
    assert.equal(stillForeign.body, 'foreign', `the shell's refusal disturbed the listener it refused: ${JSON.stringify(stillForeign)}`)
  } finally {
    foreign.kill()
    await new Promise((resolve) => {
      foreign.once('exit', resolve)
      setTimeout(resolve, 5000)
    })
  }
  await assertPortReleased(port, 'the foreign listener was stopped')
})
