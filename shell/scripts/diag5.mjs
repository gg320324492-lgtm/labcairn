// Diagnostic 5: replay the drained arm exactly, then ask netstat who holds the
// port after stop — with the fixture path fixed (diagnostics 2-4 pointed at
// scripts/test/fixtures and the child never even started).
import fs from 'node:fs'
import net from 'node:net'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { ServiceSupervisor, freeLoopbackPort } from '../src/service-supervisor.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE = path.join(HERE, '..', 'test', 'fixtures', 'writer_child.py')
const PYTHON = 'E:\\LabCairn\\.venv\\Scripts\\python.exe'
console.log('fixture exists:', fs.existsSync(FIXTURE), FIXTURE)

const port = await freeLoopbackPort()
const supervisor = new ServiceSupervisor({
  command: PYTHON,
  cwd: path.dirname(FIXTURE),
  logPath: 'E:\\labcairn-local\\shell-test-tmp\\diag5.log',
})
const { child } = await supervisor.start({
  port,
  commandOverride: PYTHON,
  argsOverride: [FIXTURE, String(port), '6144'],
  drain: true,
  readiness: false,
})
console.log('child pid:', child.pid, 'group:', child.pid)

const status = await fetch(`http://127.0.0.1:${port}/status`, { signal: AbortSignal.timeout(4000) })
console.log('status:', status.status, (await status.text()).slice(0, 60))
const ping = await fetch(`http://127.0.0.1:${port}/ping`, { signal: AbortSignal.timeout(4000) })
console.log('ping:', ping.status, (await ping.text()).slice(0, 60))

const t0 = Date.now()
const exitCode = await supervisor.stop()
console.log('stop:', Date.now() - t0, 'ms, exit', exitCode, 'signal', child.signalCode, 'exitCode', child.exitCode)

const netstat = () => {
  const out = spawnSync('netstat', ['-ano', '-p', 'TCP'], { encoding: 'utf8' })
  const rows = out.stdout.split('\n').filter((row) => row.includes(`:${port}`) || row.includes(`127.0.0.1:${port}`))
  return rows.length ? rows.join('\n') : '  (nothing on this port)'
}
for (const delay of [0, 500, 1500, 3000]) {
  if (delay) await new Promise((r) => setTimeout(r, delay))
  const probe = await new Promise((resolve) => {
    const socket = net.connect({ host: '127.0.0.1', port }, () => {
      socket.destroy()
      resolve('listening')
    })
    socket.setTimeout(1200, () => {
      socket.destroy()
      resolve('timeout')
    })
    socket.on('error', (e) => resolve(`error ${e.code ?? e.message}`))
  })
  console.log(`+${delay}ms probe: ${probe}\nnetstat:\n${netstat()}`)
}
process.exit(0)
