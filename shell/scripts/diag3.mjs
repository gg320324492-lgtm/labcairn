// Diagnostic 3: watch the writer child's whole life through the supervisor.
import fs from 'node:fs'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

import { ServiceSupervisor, freeLoopbackPort } from '../src/service-supervisor.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE = path.join(HERE, 'test', 'fixtures', 'writer_child.py')
const PYTHON = 'E:\\LabCairn\\.venv\\Scripts\\python.exe'

// First: the fixture standalone, with the shell's own Python.
const standalone = spawnSync(PYTHON, ['-I', '-c', 'print("import ok")'], { encoding: 'utf8' })
console.log('python -I -c:', standalone.status, JSON.stringify(standalone.stdout), JSON.stringify(standalone.stderr))

const port = await freeLoopbackPort()
const supervisor = new ServiceSupervisor({
  command: PYTHON,
  cwd: path.dirname(FIXTURE),
  logPath: 'E:\\labcairn-local\\shell-test-tmp\\diag3.log',
})
const started = await supervisor
  .start({
    port,
    commandOverride: PYTHON,
    argsOverride: [FIXTURE, String(port), '2048'],
    drain: true,
    readiness: false,
  })
  .catch(async (error) => {
    console.log('start failed:', error.message)
    console.log('log file bytes:', fs.readFileSync('E:\\labcairn-local\\shell-test-tmp\\diag3.log').length)
    await supervisor.stop().catch(() => {})
    process.exit(1)
  })
console.log('child pid:', started.child.pid)
console.log('log:', JSON.stringify(supervisor.sink.tail(400)))
const answer = await fetch(`http://127.0.0.1:${port}/status`, { signal: AbortSignal.timeout(4000) })
console.log('/status:', answer.status, (await answer.text()).slice(0, 80))
await supervisor.stop()
