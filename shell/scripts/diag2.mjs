// Diagnostic 2:
//  (a) the capacity of the pipe the supervisor's own spawn creates (sweeping
//      between the two bounds diagnostic 1 bracketed: 65,536 fits, 131,072 stalls);
//  (b) who holds the port after supervisor.stop() in the drained arm.
import fs from 'node:fs'
import net from 'node:net'
import path from 'node:path'
import { spawn, spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { ServiceSupervisor, freeLoopbackPort } from '../src/service-supervisor.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE = path.join(HERE, 'test', 'fixtures', 'writer_child.py')
const PYTHON = 'E:\\LabCairn\\.venv\\Scripts\\python.exe'
const sweepDir = 'E:\\labcairn-local\\shell-test-tmp\\sweep2'
fs.mkdirSync(sweepDir, { recursive: true })

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

// (a) The child writes N bytes through the *same* spawn arrangement the
// supervisor uses: stdio ['ignore','pipe','pipe'], windowsHide, detached.
const CHILD = [
  'import sys, pathlib',
  'n = int(sys.argv[1])',
  "sys.stdout.write('x' * n)",
  "sys.stdout.write('\\n')",
  'sys.stdout.flush()',
  "pathlib.Path(sys.argv[2]).write_text('done')",
].join('\n')

async function fits(n) {
  const marker = path.join(sweepDir, `m_${n}.txt`)
  if (fs.existsSync(marker)) fs.unlinkSync(marker)
  const child = spawn(PYTHON, ['-I', '-c', CHILD, String(n), marker], {
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
    detached: true,
  })
  // Deliberately no reader on child.stdout — this is the undrained arrangement.
  let result = null
  const deadline = Date.now() + 4000
  while (Date.now() < deadline && result === null) {
    if (fs.existsSync(marker)) result = true
    else if (child.exitCode !== null || child.signalCode !== null) result = fs.existsSync(marker)
    else await new Promise((r) => setTimeout(r, 100))
  }
  if (result === null) result = false
  if (!(await waitForExit(child, 1000))) child.kill('SIGKILL')
  await waitForExit(child, 1500)
  return result
}

const line = []
for (const n of [32768, 49152, 65536, 81920, 98304, 114688, 131072]) {
  line.push(`${n}:${(await fits(n)) ? 'fits' : 'stalls'}`)
  console.log('supervisor-spawn pipe sweep:', line.join(' '))
}

// (b) The drained arm's port after stop: probe it, then ask netstat who owns it.
const port = await freeLoopbackPort()
const supervisor = new ServiceSupervisor({
  command: PYTHON,
  cwd: path.dirname(FIXTURE),
  logPath: 'E:\\labcairn-local\\shell-test-tmp\\diag2.log',
})
const { child } = await supervisor.start({
  port,
  commandOverride: PYTHON,
  argsOverride: [FIXTURE, String(port), '2048'],
  drain: true,
  readiness: false,
})
console.log('child pid:', child.pid)
const before = await fetch(`http://127.0.0.1:${port}/status`).then((r) => r.status)
console.log('answered before stop:', before)

const exitCode = await supervisor.stop()
console.log('exit code:', exitCode, 'signal:', child.signalCode, 'exitCode field:', child.exitCode)

const netstat = () => {
  const out = spawnSync('netstat', ['-ano', '-p', 'TCP'], { encoding: 'utf8' })
  return out.stdout.split('\n').filter((row) => row.includes(`:${port}`)).join('\n')
}
for (const delay of [0, 500, 1500, 3000]) {
  if (delay) await new Promise((r) => setTimeout(r, delay))
  console.log(`netstat at +${delay}ms:\n${netstat() || '  (nothing listening on that port)'}`)
}
