// Diagnostic 6: two platform facts the witness needs.
//  (a) can Python measure the *non-blocking* capacity of the fd Node handed it
//      (fd 1), or only of an anonymous os.pipe()?
//  (b) which stop path actually lands for a child spawned in the production
//      shape (detached + windowsHide) — SIGBREAK, SIGTERM, or only the forced
//      group kill?
import fs from 'node:fs'
import path from 'node:path'
import { spawn } from 'node:child_process'
import { fileURLToPath } from 'node:url'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const FIXTURE = path.join(HERE, '..', 'test', 'fixtures', 'writer_child.py')
const PYTHON = 'E:\\LabCairn\\.venv\\Scripts\\python.exe'
const dir = 'E:\\labcairn-local\\shell-test-tmp\\diag6'
fs.mkdirSync(dir, { recursive: true })

// (a) The probe reports through a marker file only: its stdout is the pipe
// under measurement, so nothing may be trusted to come back through it.
const PROBE = [
  'import os, sys',
  'marker = sys.argv[1]',
  'try:',
  '    os.set_blocking(1, False)',
  '    fitted = 0',
  '    while fitted < 64 * 1024 * 1024:',
  '        try:',
  "            fitted += os.write(1, b'x' * 1024)",
  '        except BlockingIOError:',
  '            break',
  '        except OSError as exc:',
  "            open(marker, 'w').write('OSERROR %r' % (exc,))",
  '            sys.exit(1)',
  "    open(marker, 'w').write('FITS %d' % fitted)",
  'except Exception as exc:',
  "    open(marker, 'w').write('ERROR %r' % (exc,))",
  '    sys.exit(1)',
].join('\n')

async function runProbe() {
  const marker = path.join(dir, 'capacity.txt')
  if (fs.existsSync(marker)) fs.unlinkSync(marker)
  const child = spawn(PYTHON, ['-I', '-c', PROBE, marker], {
    cwd: dir,
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
    detached: true,
  })
  const deadline = Date.now() + 30_000
  while (!fs.existsSync(marker) && Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, 100))
  }
  const reported = fs.existsSync(marker) ? fs.readFileSync(marker, 'utf8') : 'NO REPORT'
  const code = child.exitCode ?? child.signalCode
  child.kill('SIGKILL')
  console.log(`(a) fd-1 non-blocking capacity probe: ${reported} (child exit ${code})`)
  return reported
}

await runProbe()

// (b) Stop paths. The fixture handles SIGINT/SIGTERM/SIGBREAK and exits 0
// writing "writer-stopped"; a forced kill leaves signalCode set and no marker.
const STOP_CHILD = [
  'import signal, sys, time',
  "sys.stdout.write('child-ready\\n'); sys.stdout.flush()",
  'def handler(signum, frame):',
  "    open(sys.argv[1], 'w').write('caught %d' % signum)",
  '    sys.exit(0)',
  'for name in ("SIGINT", "SIGTERM", "SIGBREAK"):',
  '    s = getattr(signal, name, None)',
  '    if s is not None:',
  '        signal.signal(s, handler)',
  'while True:',
  '    time.sleep(0.2)',
].join('\n')

async function tryStop(arrangement, signal) {
  const marker = path.join(dir, `stop-${arrangement}-${signal}.txt`)
  if (fs.existsSync(marker)) fs.unlinkSync(marker)
  const options = {
    cwd: dir,
    stdio: ['ignore', 'pipe', 'pipe'],
    detached: arrangement === 'detached+windowsHide' || arrangement === 'detached',
    windowsHide: arrangement !== 'plain',
  }
  const child = spawn(PYTHON, ['-I', '-c', STOP_CHILD, marker], options)
  const deadline = Date.now() + 8000
  while (!fs.existsSync(path.join(dir, 'ready')) && Date.now() < deadline && !child.stdout.read(1)) {
    await new Promise((r) => setTimeout(r, 150))
  }
  await new Promise((r) => setTimeout(r, 800))
  let asked = true
  try {
    child.kill(signal)
  } catch (error) {
    asked = false
  }
  const exited = await new Promise((resolve) => {
    const timer = setTimeout(() => resolve(false), 3000)
    child.once('exit', () => {
      clearTimeout(timer)
      resolve(true)
    })
  })
  const caught = fs.existsSync(marker) ? fs.readFileSync(marker, 'utf8') : 'no handler ran'
  const outcome = `exit=${child.exitCode} signal=${child.signalCode} exitedWithinGrace=${exited} asked=${asked} handler=${caught}`
  if (!exited) {
    await new Promise((resolve) => {
      const killer = spawn('taskkill', ['/PID', String(child.pid), '/T', '/F'], { stdio: 'ignore', windowsHide: true })
      killer.once('exit', resolve)
      killer.once('error', resolve)
    })
  }
  console.log(`(b) ${arrangement} + kill(${signal}): ${outcome}`)
}

for (const arrangement of ['detached+windowsHide', 'windowsHide', 'plain', 'detached']) {
  for (const signal of ['SIGBREAK', 'SIGTERM', 'SIGINT']) {
    await tryStop(arrangement, signal)
  }
}
process.exit(0)
