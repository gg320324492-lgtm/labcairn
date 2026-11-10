// Diagnostic: (a) the capacity of the pipe Node's spawn actually creates,
// (b) what the writer child and its port look like after supervisor.stop().
//
// (a) matters because the witness sizes its dose from a measured capacity, and
// the arrangement that must be measured is *this* arrangement: a pipe Node's
// spawn created. `os.pipe()`'s 4,096 is the anonymous-pipe default; a spawn
// pipe may be created with a different size, and the witness must use the one
// it actually hands the child.
import fs from 'node:fs'
import net from 'node:net'
import path from 'node:path'
import { spawn, spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { ServiceSupervisor, freeLoopbackPort } from '../src/service-supervisor.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE = path.join(HERE, 'test', 'fixtures', 'writer_child.py')
const PYTHON = 'E:\\LabCairn\\.venv\\Scripts\\python.exe'

function probePort(port) {
  return new Promise((resolve) => {
    const socket = net.connect({ host: '127.0.0.1', port }, () => {
      socket.destroy()
      resolve('listening')
    })
    socket.setTimeout(1200, () => {
      socket.destroy()
      resolve('timeout')
    })
    socket.on('error', (error) => resolve(`error ${error.code ?? error.message}`))
  })
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

const sweepDir = 'E:\\labcairn-local\\shell-test-tmp\\sweep'
fs.mkdirSync(sweepDir, { recursive: true })
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
    stdio: ['ignore', 'pipe', 'ignore'],
    windowsHide: true,
    detached: true,
  })
  let result = null
  const deadline = Date.now() + 4000
  while (Date.now() < deadline && result === null) {
    if (fs.existsSync(marker)) result = true
    else if (child.exitCode !== null || child.signalCode !== null) result = fs.existsSync(marker)
    else await new Promise((r) => setTimeout(r, 100))
  }
  if (result === null) result = false
  if (!(await waitForExit(child, 1000))) child.kill('SIGKILL')
  return result
}

const results = []
for (const n of [1024, 2048, 4096, 6144, 8192, 12288, 16384, 24576, 32768, 49152, 65536, 131072]) {
  const ok = await fits(n)
  results.push(`${n}:${ok ? 'fits' : 'stalls'}`)
  console.log('sweep:', results.join(' '))
}

const port = await freeLoopbackPort()
const supervisor = new ServiceSupervisor({
  command: PYTHON,
  cwd: path.dirname(FIXTURE),
  logPath: 'E:\\labcairn-local\\shell-test-tmp\\diag.log',
})
const { child } = await supervisor.start({
  port,
  commandOverride: PYTHON,
  argsOverride: [FIXTURE, String(port), '2048'],
  drain: true,
  readiness: false,
})
console.log('child pid:', child.pid)

const answered = await fetch(`http://127.0.0.1:${port}/status`).then((r) => r.status)
console.log('answered before stop:', answered)

const t0 = Date.now()
const exitCode = await supervisor.stop()
console.log('stop took', Date.now() - t0, 'ms; exit code', exitCode, 'signal', child.signalCode)

for (const delay of [0, 300, 1000, 2500]) {
  if (delay) await new Promise((r) => setTimeout(r, delay))
  console.log(`port ${port} at +${delay}ms:`, await probePort(port))
}

const listed = spawnSync('tasklist', ['/FI', `PID eq ${child.pid}`, '/FO', 'CSV'], { encoding: 'utf8' })
console.log('tasklist:', JSON.stringify(listed.stdout.trim()))
