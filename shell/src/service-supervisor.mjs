/**
 * The service supervisor: the shell's half of the O6 hard rule.
 *
 * **The rule (docs/plans/LC-P3-05-shell-implementation-plan.md §3).** Any pipe
 * this module opens to the child service's stdout or stderr has a reader
 * attached before the child can write, and that reader keeps reading until the
 * pipe closes. There is no code path here that creates a pipe and reads it at
 * the end, or only on error.
 *
 * **Why it is a rule and not a note.** `docs/acceptance/o6-event-stream-stall-2026-11-10.md`
 * measured the whole chain: one unwired event stream made the service write a
 * 6,205-byte traceback into its own output against a 4,096-byte pipe on this
 * machine, and a writer parked in a full pipe is an event loop that serves
 * nothing — the nodrain arm answered 0 / 5 ordinary reads while the drain arm
 * answered 5 / 5. The service-side fix removed the traceback fuel; it did not
 * make an undrained pipe safe. This module therefore drains by construction,
 * in both run modes: the production child and the test-injected child go
 * through the same spawn path.
 *
 * **Where the drained bytes go.** A bounded log file outside the repository
 * (the product's temp convention — `E:\labcairn-local\` on this machine),
 * truncated at a ceiling. Not an unbounded in-memory buffer: §3's requirement
 * 3 says a shell that drains into one has swapped one leak for another. No
 * token value is ever written here — the child's output is the service's own
 * log lines, and the token lives in the workspace, not in stdout.
 *
 * **The two test-only switches, named where they are read.** `drain: false`
 * and `commandOverride` / `argsOverride` exist so the witness can build O6's
 * control pair against this module's real spawn path (plan §3's Arm A and
 * Arm B). `src/main.mjs` never passes any of them, and `src/config.mjs`
 * never reads an environment variable for them. They are the seam the plan
 * asks for — "a spawn-command seam that the packaged build never exposes" —
 * not a mode the product can be configured into.
 *
 * **Windows process groups (§3's requirement 6, ADR-0022's rule).** The child
 * starts in its own group (`detached` plus `windowsHide`); it is asked to stop
 * with `SIGBREAK`, which is Node's name for the CTRL_BREAK event the G1 Python
 * helper sends as `signal.CTRL_BREAK_EVENT` (`tests/workbench_serve_support.py`
 * `_windows_group_stop_signal`) — a bare kill reaches the parent, not the tree;
 * a bounded wait follows, then a forced `taskkill /T /F` of the group. The
 * platform question is asked through a call so the reachable body is the same
 * on every platform.
 */

import fs from 'node:fs'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import { spawn } from 'node:child_process'

/** The child's stdout/stderr may grow; the log file keeps a ceiling on it. */
export const LOG_CEILING_BYTES = 4 * 1024 * 1024

/** The bounded readiness wait: a port answering is not a service ready. */
export const READY_TIMEOUT_MS = 60_000

/** Bounded grace before the process group is terminated by force. */
export const STOP_GRACE_MS = 8_000

/** ServiceStarting's own required fields (src/labcairn/cli/models.py). */
const SERVICE_STARTING_FIELDS = ['host', 'port', 'origin', 'origins', 'task_id', 'token_path']

/**
 * Whether this host is Windows, asked through a call — the same shape the G1
 * helper names for the same reason (`_this_platform_is_windows`): the platform
 * question and the platform-only values live behind calls, so no reader
 * narrows one platform's branch away.
 */
export function thisPlatformIsWindows() {
  return process.platform === 'win32'
}

/** `SIGBREAK` on Windows (CTRL_BREAK), `SIGTERM` elsewhere. */
function stopSignal() {
  return thisPlatformIsWindows() ? 'SIGBREAK' : 'SIGTERM'
}

/**
 * Where the drained log lives: outside the repository by the product's own
 * temp convention, overridable for a rehearsal. Never a token value, never
 * corpus text — this file carries only what the service printed about itself.
 */
export function defaultLogPath(env = process.env) {
  if (env.LABCAIRN_SHELL_LOG) return env.LABCAIRN_SHELL_LOG
  const base = thisPlatformIsWindows()
    ? 'E:\\labcairn-local\\shell-logs'
    : path.join(os.tmpdir(), 'labcairn-shell-logs')
  return path.join(base, 'service.log')
}

/**
 * Ask the operating system for a free loopback port — the probe the product's
 * own `_check_port_free` and the G1 helper's `_free_loopback_port` both make:
 * bind port 0 and read what came back. The shell never assumes 8000 is free.
 */
export function freeLoopbackPort() {
  return new Promise((resolve, reject) => {
    const probe = net.createServer()
    probe.once('error', reject)
    probe.listen(0, '127.0.0.1', () => {
      const address = probe.address()
      probe.close(() => resolve(address.port))
    })
  })
}

/**
 * The bounded drain sink: a log file that accepts every byte the child writes
 * and truncates itself at a ceiling, so the drained bytes cannot grow without
 * bound. The truncation is a recorded loss, not a swallowed one.
 */
export class LogSink {
  constructor(logPath, ceilingBytes = LOG_CEILING_BYTES) {
    this.logPath = logPath
    this.ceilingBytes = ceilingBytes
    this.writtenBytes = 0
    this.droppedBytes = 0
    fs.mkdirSync(path.dirname(logPath), { recursive: true })
    fs.writeFileSync(logPath, '')
  }

  write(chunk) {
    const room = this.ceilingBytes - this.writtenBytes
    if (room <= 0) {
      this.droppedBytes += chunk.length
      return
    }
    const kept = chunk.subarray(0, room)
    fs.appendFileSync(this.logPath, kept)
    this.writtenBytes += kept.length
    if (kept.length < chunk.length) {
      this.droppedBytes += chunk.length - kept.length
      fs.appendFileSync(
        this.logPath,
        Buffer.from(`\n[drain log at ceiling; ${chunk.length - kept.length} bytes dropped]\n`),
      )
    }
  }

  tail(maxBytes = 8192) {
    try {
      const bytes = fs.readFileSync(this.logPath)
      return bytes.subarray(Math.max(0, bytes.length - maxBytes)).toString('utf8')
    } catch {
      return ''
    }
  }
}

/** A whole JSON object on a line that carries ServiceStarting's fields. */
export function looksLikeServiceStarting(line) {
  const trimmed = line.trim()
  if (!trimmed.startsWith('{') || !trimmed.endsWith('}')) return null
  let parsed
  try {
    parsed = JSON.parse(trimmed)
  } catch {
    return null
  }
  if (!SERVICE_STARTING_FIELDS.every((field) => field in parsed)) return null
  return parsed
}

/**
 * Spawn a child and attach both readers before it can write its first byte
 * (§3's requirement 2). This is the one spawn path — the production child and
 * the injected test child go through these same lines, so "drained" is a
 * property of the module rather than of one call site.
 *
 * `drain: false` is the witness's undrained arm: the pipes are created and
 * left paused, with no `data` handler and nothing resuming them. That is the
 * arrangement that parks a writer, and it is the arm that proves a dose could
 * really fill the pipe.
 */
function spawnChild(command, args, options, sink, drain) {
  const child = spawn(command, args, {
    cwd: options.cwd,
    env: options.env,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
    detached: thisPlatformIsWindows(),
  })

  let spawnError = null
  child.once('error', (error) => {
    spawnError = error
  })

  const pipeErrors = []
  const watchPipe = (stream, name) => {
    // §3's requirement 4: a reader that stops is a shell-level error,
    // surfaced. It is recorded in the log and reported to the caller; it is
    // never swallowed.
    stream.on('error', (error) => {
      pipeErrors.push(`${name}: ${error.message}`)
      sink.write(Buffer.from(`\n[reader error ${name}: ${error.message}]\n`))
    })
  }

  if (drain) {
    // The readers exist here, at spawn time — before the child writes a byte.
    child.stdout.on('data', (chunk) => sink.write(Buffer.from(chunk)))
    child.stderr.on('data', (chunk) => sink.write(Buffer.from(chunk)))
    watchPipe(child.stdout, 'stdout')
    watchPipe(child.stderr, 'stderr')
  }

  return { child, pipeErrors, spawnError: () => spawnError }
}

/**
 * The service supervisor: one child `labcairn serve`, its drain, its
 * readiness, its stop. The session token never passes through this module —
 * `ServiceStarting.token_path` names a file the page reads, and the
 * supervisor neither reads it nor copies it.
 *
 * **The one environment flag the child always carries.** The spawn below
 * sets `PYDANTIC_DISABLE_PLUGINS=1` on the child's environment. It is
 * measured, not defensive: without it the frozen `labcairn.exe` dies at
 * import — logfire's pydantic plugin (a transitive of `pydantic-ai`'s
 * `logfire` extra; no product file imports logfire) reads its target's
 * source text at import time (`inspect.getsource`), and a frozen application
 * carries no source text, so the child exits before it reports
 * (`OSError: could not get source code`, measured 2026-11-14 in the
 * packaged-run drill). The flag rides the one spawn path, so every run mode
 * — dev console script, frozen exe, packaged backend — inherits it and no
 * launcher has to remember it. Setting it unconditionally also covers the
 * dev console script, where the same plugin machinery exists but source text
 * is available; the flag only disables third-party plugins, never pydantic's
 * own validation.
 */
export class ServiceSupervisor {
  /**
   * @param command  absolute path of the `labcairn` entry point (§4.1: never a
   *   name resolved from `PATH`)
   * @param env  the child's environment
   * @param cwd  the child's working directory (a directory of its own, never a
   *   guess about where the shell was started)
   * @param logPath  where the drained bytes go
   */
  constructor({ command, env = process.env, cwd, logPath }) {
    if (!command) throw new Error('the supervisor needs the service command')
    this.command = command
    this.env = env
    this.cwd = cwd
    this.sink = new LogSink(logPath ?? defaultLogPath(env))
    this.running = null
  }

  /**
   * Start the child, wait for readiness — the `ServiceStarting` line **and** a
   * `GET /health` 200 from that exact origin — and resolve with what the
   * service said it bound.
   *
   * @param port  an explicit port (dev), or `null` to take one the OS chose
   * @param staticDir  the built bundle to serve, or `null` (dev: Vite's page)
   * @param workspace  the workspace the service is bound to
   * @param commandOverride  test-only: a different child (plan §3's Arm A)
   * @param argsOverride  test-only: the child's whole argument list
   * @param drain  test-only: `false` builds the undrained control arm
   * @param readiness  test-only: `false` skips the readiness read (the undrained
   *   arm cannot consume stdout and still be undrained)
   */
  async start({
    port = null,
    staticDir = null,
    workspace,
    commandOverride = null,
    argsOverride = null,
    drain = true,
    readiness = true,
  }) {
    if (this.running) throw new Error('the supervisor already has a child')
    const chosen = port ?? (await freeLoopbackPort())

    const args =
      argsOverride ??
      [
        '--workspace',
        workspace,
        'serve',
        '--host',
        '127.0.0.1',
        '--port',
        String(chosen),
        '--json',
        ...(staticDir ? ['--static-dir', staticDir] : []),
      ]

    const { child, pipeErrors, spawnError } = spawnChild(
      commandOverride ?? this.command,
      args,
      { cwd: this.cwd, env: { ...this.env, PYDANTIC_DISABLE_PLUGINS: '1' } },
      this.sink,
      drain,
    )
    this.running = child

    let starting = null
    if (readiness) {
      starting = await this.#waitForServiceStarting(child)
    } else {
      starting = { port: chosen, origin: `http://127.0.0.1:${chosen}` }
    }

    const failure =
      spawnError()?.message ??
      (pipeErrors.length > 0 ? pipeErrors.join('; ') : null) ??
      (starting === null ? 'the child exited or stayed silent before it reported' : null)
    if (failure !== null) {
      await this.stop()
      throw new Error(`the service child did not start: ${failure}\n--- child output ---\n${this.sink.tail()}`)
    }

    if (starting.port !== chosen) {
      // A service reporting a port the shell did not ask for is a refusal, not
      // a page to load (§4.3's occupancy row).
      await this.stop()
      throw new Error(`the service reported port ${starting.port}, not the ${chosen} it was asked for`)
    }

    try {
      await this.#waitForHealth(starting.origin)
    } catch (error) {
      await this.stop()
      throw error
    }
    return { starting, child }
  }

  #waitForServiceStarting(child) {
    return new Promise((resolve) => {
      // The reader that keeps the pipe moving is already attached
      // (spawnChild); this consumes the *parsed* line from the same flowing
      // stream rather than buffering the world.
      let buffer = ''
      let settled = false
      const finish = (value) => {
        if (settled) return
        settled = true
        clearTimeout(timer)
        child.stdout.off('data', onData)
        resolve(value)
      }
      const timer = setTimeout(() => finish(null), READY_TIMEOUT_MS)
      const onData = (chunk) => {
        if (settled) return
        buffer += chunk.toString('utf8')
        const parts = buffer.split('\n')
        buffer = parts.pop() ?? ''
        if (buffer.length > 1_000_000) {
          finish(null)
          return
        }
        for (const line of parts) {
          const starting = looksLikeServiceStarting(line)
          if (starting !== null) {
            finish(starting)
            return
          }
        }
      }
      child.stdout.on('data', onData)
      child.once('exit', () => finish(null))
    })
  }

  #waitForHealth(origin) {
    const deadline = Date.now() + READY_TIMEOUT_MS
    const base = new URL(origin)
    const probe = () =>
      new Promise((resolve) => {
        const socket = net.connect({ host: base.hostname, port: Number(base.port) }, () => {
          socket.write(
            `GET /health HTTP/1.1\r\nHost: ${base.host}\r\nAccept: application/json\r\nConnection: close\r\n\r\n`,
          )
        })
        let head = ''
        socket.setTimeout(2_000, () => {
          socket.destroy()
          resolve(false)
        })
        socket.on('data', (chunk) => {
          if (head.length < 16) head += chunk.toString('latin1')
        })
        socket.on('error', () => resolve(false))
        socket.on('close', () => resolve(/^HTTP\/1\.[01] 200/.test(head)))
      })
    return new Promise((resolve, reject) => {
      const attempt = async () => {
        if (await probe()) {
          resolve()
          return
        }
        if (Date.now() >= deadline) {
          reject(
            new Error(
              `${origin}/health did not answer 200 within ${READY_TIMEOUT_MS} ms — ` +
                'a port answering is not a service that is ready\n--- child output ---\n' +
                this.sink.tail(),
            ),
          )
          return
        }
        setTimeout(attempt, 250)
      }
      attempt()
    })
  }

  /**
   * Stop the child: ask its group to stop, wait a bounded time, then force the
   * group. Never returns while the port is still held: the exit is confirmed,
   * and a child that survived the force is an error, not a quiet return.
   *
   * The returned outcome names how the child ended — `forced: false` means the
   * ask worked and the group stopped on its own, which is what
   * `tests/test_workbench_serve_helper.py` asserts of the Python helper
   * (`outcome.forced is False`). A shell that always ends its service by force
   * is a shell whose graceful path nobody has seen.
   */
  async stop() {
    const child = this.running
    if (!child) return null
    this.running = null
    const signal = stopSignal()
    let asked = true
    try {
      child.kill(signal)
    } catch {
      asked = false // Already gone; the wait below confirms it.
    }
    if (await this.#waitForExit(child, STOP_GRACE_MS)) {
      return {
        exitCode: child.exitCode,
        signal: child.signalCode,
        forced: false,
        askedWith: signal,
        asked,
      }
    }

    if (thisPlatformIsWindows()) {
      await new Promise((resolve) => {
        const killer = spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], {
          stdio: 'ignore',
          windowsHide: true,
        })
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
    if (!(await this.#waitForExit(child, STOP_GRACE_MS))) {
      throw new Error(`the service child pid ${child.pid} survived the forced group stop`)
    }
    return {
      exitCode: child.exitCode,
      signal: child.signalCode,
      forced: true,
      askedWith: signal,
      asked,
    }
  }

  #waitForExit(child, timeoutMs) {
    if (child.exitCode !== null || child.signalCode !== null) return Promise.resolve(true)
    return new Promise((resolve) => {
      const timer = setTimeout(() => resolve(false), timeoutMs)
      child.once('exit', () => {
        clearTimeout(timer)
        resolve(true)
      })
    })
  }
}
