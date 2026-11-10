// Diagnostic 4: spawn the writer fixture directly and report everything the
// child says — no supervisor in the way.
import fs from 'node:fs'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE = path.join(HERE, '..', 'test', 'fixtures', 'writer_child.py')
const PYTHON = 'E:\\LabCairn\\.venv\\Scripts\\python.exe'
const port = 53999

console.log('fixture exists:', fs.existsSync(FIXTURE), FIXTURE)
console.log('python exists:', fs.existsSync(PYTHON), PYTHON)

const child = spawn(PYTHON, [FIXTURE, String(port), '2048'], {
  cwd: path.dirname(FIXTURE),
  stdio: ['ignore', 'pipe', 'pipe'],
  windowsHide: true,
  detached: true,
})
child.stdout.on('data', (c) => console.log('stdout:', JSON.stringify(c.toString())))
child.stderr.on('data', (c) => console.log('stderr:', JSON.stringify(c.toString())))
child.on('error', (e) => console.log('error event:', e.message))
child.on('exit', (code, signal) => console.log('exit:', code, signal))

setTimeout(async () => {
  try {
    const response = await fetch(`http://127.0.0.1:${port}/status`, { signal: AbortSignal.timeout(3000) })
    console.log('http:', response.status, (await response.text()).slice(0, 80))
  } catch (error) {
    console.log('http failed:', error.message)
  }
  child.kill('SIGKILL')
  setTimeout(() => process.exit(0), 500)
}, 6000)
