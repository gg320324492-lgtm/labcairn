/**
 * T09's packaged-run drill: drive the real packaged shape through both supply
 * ways for `LABCAIRN_SHELL_CLI` and `LABCAIRN_SHELL_WORKSPACE`.
 *
 * **What "the real packaged shape" means here.** The packaged run mode is
 * `resolveRunConfig(env, { packaged: true, resourcesDir })` — the exact call
 * `main.mjs` makes, with `app.isPackaged` true and a resources directory that
 * holds `web-dist` and (optionally) `shell-env.json`. This drill runs it over
 * real files under a scratch root, never over a constant, and it prints every
 * refusal verbatim because the drill's evidence is what the shell *says*.
 *
 * **The two ways the drill walks:**
 * 1. **Environment supply** — a launcher (the template `labcairn-shell.cmd`)
 *    sets both variables; the shell's environment carries them; the file, if
 *    any, is overridden. Witnessed here by resolving with the variables set
 *    and a populated `shell-env.json`, asserting the environment won.
 * 2. **Package supply** — the package carries `resources/shell-env.json`;
 *    the environment names nothing. Witnessed by resolving with an empty
 *    environment and asserting the file's values (including the
 *    installation-relative workspace) arrived.
 *
 * **What the drill refuses to claim.** It does not claim a service started —
 * the package still carries no backend (O3 is unmeasured), so "launch" is not
 * among the outcomes. It claims the *supply* works and is witnessed, which is
 * the part of T09 that was open. The three failures it walks (no supply at
 * all, a broken file, a relative CLI in the file) are the refusals the owner
 * must see rather than silence.
 *
 * Run from the repository: `node shell/scripts/rehearse-packaged-shell-env.mjs`
 * (no repository state is changed; scratch lives under `os.tmpdir()`).
 */

import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import net from 'node:net'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { resolveRunConfig, SHELL_ENV_FILE } from '../src/config.mjs'

const here = path.dirname(fileURLToPath(import.meta.url))
const scratchRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'lc-t09-drill-'))
let passed = 0
let failed = 0

function check(name, run) {
  try {
    run()
    process.stdout.write(`PASS ${name}\n`)
    passed += 1
  } catch (error) {
    process.stdout.write(`FAIL ${name}\n  ${error.message}\n`)
    failed += 1
  }
}

/** Build a fake packaged resources directory with a web bundle and a config file. */
function packagedResources({ withFile, file }) {
  const resourcesDir = path.join(scratchRoot, `res-${Math.random().toString(36).slice(2)}`)
  fs.mkdirSync(path.join(resourcesDir, 'web-dist'), { recursive: true })
  fs.writeFileSync(path.join(resourcesDir, 'web-dist', 'index.html'), '<!doctype html>')
  if (withFile) {
    fs.writeFileSync(path.join(resourcesDir, SHELL_ENV_FILE), file)
  }
  return resourcesDir
}

const CLI = 'C:\\Program Files\\LabCairn\\backend\\labcairn.exe'

// Way 1: the environment names both variables (what the launcher template sets).
check('way 1 — the environment supplies CLI and workspace, and overrides the file', () => {
  const resourcesDir = packagedResources({
    withFile: true,
    file: JSON.stringify({ cliPath: 'C:\\from-file\\labcairn.exe', workspace: 'from-file-ws' }),
  })
  const config = resolveRunConfig(
    { LABCAIRN_SHELL_CLI: CLI, LABCAIRN_SHELL_WORKSPACE: 'E:\\Labs\\drill-ws' },
    { packaged: true, resourcesDir },
  )
  assert.equal(config.cliPath, CLI)
  assert.equal(config.workspace, 'E:\\Labs\\drill-ws')
  assert.equal(config.staticDir, path.join(resourcesDir, 'web-dist'), 'the bundle is still derived')
})

// Way 2: the package's own shell-env.json, environment empty.
check('way 2 — the package shell-env.json supplies both, workspace installation-relative', () => {
  const resourcesDir = packagedResources({
    withFile: true,
    file: JSON.stringify({ cliPath: CLI, workspace: 'LabCairn-workspace' }),
  })
  const config = resolveRunConfig({}, { packaged: true, resourcesDir })
  assert.equal(config.cliPath, CLI)
  assert.equal(config.workspace, path.join(resourcesDir, '..', 'LabCairn-workspace'))
})

// Way 2 with the environment supplying only one side: the file covers the rest.
check('way 1+2 — the environment covers one side, the file the other', () => {
  const resourcesDir = packagedResources({
    withFile: true,
    file: JSON.stringify({ workspace: 'LabCairn-workspace' }),
  })
  const config = resolveRunConfig(
    { LABCAIRN_SHELL_CLI: CLI },
    { packaged: true, resourcesDir },
  )
  assert.equal(config.cliPath, CLI)
  assert.equal(config.workspace, path.join(resourcesDir, '..', 'LabCairn-workspace'))
})

// The refusal the owner sees when nothing supplies the variables.
check('refusal — neither supply names the variables, and the shell says so', () => {
  const resourcesDir = packagedResources({ withFile: false })
  try {
    resolveRunConfig({}, { packaged: true, resourcesDir })
    assert.fail('the resolve had to refuse')
  } catch (error) {
    assert.match(error.message, /LABCAIRN_SHELL_CLI/)
    process.stdout.write(`  refusal: ${error.message.split('\n')[0]}\n`)
  }
})

// The refusal for a package carrying a broken default.
check('refusal — a broken shell-env.json is a startup refusal naming the field', () => {
  const resourcesDir = packagedResources({
    withFile: true,
    file: '{"cliPath": "labcairn.exe", "workspace": "ws"}',
  })
  try {
    resolveRunConfig({}, { packaged: true, resourcesDir })
    assert.fail('the resolve had to refuse')
  } catch (error) {
    assert.match(error.message, /"cliPath" must be an absolute path or an installation-relative path/)
    process.stdout.write(`  refusal: ${error.message.split('\n')[0]}\n`)
  }
})

// O3's frozen service, at the supply layer: the package now carries the
// frozen backend at `resources/backend/labcairn`, and the file names it in
// its installation-relative form (`"cliPath": "backend/labcairn"`) while the
// environment names nothing. The resolver anchors the relative name under the
// resources directory — the anchoring the installation-relative workspace
// already uses — so the drill's assertion is the resolved absolute path, not
// the file's spelling.
const frozenExe = path.join(here, '..', 'build', 'backend-freeze', 'labcairn',
  process.platform === 'win32' ? 'labcairn.exe' : 'labcairn')
if (!fs.existsSync(frozenExe)) {
  process.stdout.write('SKIP-INPUT no frozen backend on this machine — the live scenario is skipped; the parse-level scenarios still run\n')
}
check('way 2 + O3 — the file names the frozen backend installation-relatively, and the run resolves it under resources', () => {
  const resourcesDir = packagedResources({
    withFile: true,
    file: JSON.stringify({ cliPath: 'backend/labcairn', workspace: 'LabCairn-workspace' }),
  })
  const config = resolveRunConfig({}, { packaged: true, resourcesDir })
  assert.equal(config.cliPath, path.join(resourcesDir, 'backend', 'labcairn'))
  assert.equal(config.workspace, path.join(resourcesDir, '..', 'LabCairn-workspace'))
  assert.ok(path.isAbsolute(config.cliPath), 'the resolved entry point must be absolute')
})

// The environment still wins per variable, even against a file that names a
// real frozen backend: the launcher remains the operator override.
check('way 1 + O3 — the environment overrides a file that names the frozen exe', () => {
  const resourcesDir = packagedResources({
    withFile: true,
    file: JSON.stringify({ cliPath: 'backend/labcairn', workspace: 'LabCairn-workspace' }),
  })
  const config = resolveRunConfig(
    { LABCAIRN_SHELL_CLI: CLI, LABCAIRN_SHELL_WORKSPACE: 'E:\\Labs\\drill-ws' },
    { packaged: true, resourcesDir },
  )
  assert.equal(config.cliPath, CLI, 'the environment must still win for cliPath')
  assert.equal(config.workspace, 'E:\\Labs\\drill-ws')
})

// When the frozen exe really exists, a live drill proves the frozen entry
// starts and serves: connected -> loaded -> granted. Parse-only otherwise.
if (fs.existsSync(frozenExe)) {
  check('live — the frozen backend starts, serves, and grants the page its probe', async () => {
    const { spawn } = await import('node:child_process')
    const { once } = await import('node:events')
    const workspace = path.join(scratchRoot, 'frozen-ws')
    fs.rmSync(workspace, { recursive: true, force: true })
    // The same measured flag the freeze tool sets: logfire's pydantic plugin
    // reads source text a frozen exe does not carry. The migrations tree is
    // copied into the bundle by the freeze tool (what the installer will do
    // too), so the frozen init finds it beside the exe, as in a checkout.
    const env = {
      ...process.env,
      COLUMNS: '200',
      PYTHONIOENCODING: 'utf-8',
      PYDANTIC_DISABLE_PLUGINS: '1',
    }
    for (const args of [
      ['--workspace', workspace, 'init'],
      ['--workspace', workspace, 'task', 'create', '--title', 'frozen drill', '--objective', 'the frozen entry starts', '--criterion', 'connected then granted', '--json'],
    ]) {
      const done = spawnSync(frozenExe, args, { encoding: 'utf8', env })
      assert.equal(done.status, 0, `the frozen exe refused ${args[2]}: ${done.stderr}`)
    }
    const port = await new Promise((resolve, reject) => {
      const server = net.createServer()
      server.once('error', reject)
      server.listen(0, '127.0.0.1', () => {
        const { port: free } = server.address()
        server.close(() => resolve(free))
      })
    })
    const service = spawn(frozenExe, [
      '--workspace', workspace, 'serve', '--host', '127.0.0.1', '--port', String(port), '--json',
    ], { env, windowsHide: true })
    try {
      // Readiness is the service's own start line AND a /health answer, the
      // same two-surface shape the shell's supervisor requires (a port
      // answering is not readiness).
      const starting = await once(service.stdout, 'data')
      assert.match(String(starting), /ServiceStarting|origin/, 'the frozen exe did not print the service start line')
      let health = null
      for (let attempt = 0; attempt < 40; attempt += 1) {
        try {
          health = await fetch(`http://127.0.0.1:${port}/health`)
          break
        } catch {
          await new Promise((resolve) => setTimeout(resolve, 250))
        }
      }
      assert.ok(health !== null, 'the frozen service never answered /health')
      assert.equal(health.status, 200, 'the frozen service did not answer /health')
      process.stdout.write(`  frozen exe served on 127.0.0.1:${port} (connected)\n`)
      // The token lives at <workspace>/.labcairn/session-token as plain text.
      const token = fs.readFileSync(path.join(workspace, '.labcairn', 'session-token'), 'utf8').trim()
      const probe = await fetch(`http://127.0.0.1:${port}/task/select`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ task_id: null }),
      })
      process.stdout.write(`  granted probe answered ${probe.status}\n`)
      assert.notEqual(probe.status, 404, 'the frozen service does not route the granted mutation')
    } finally {
      if (service.exitCode === null && service.signalCode === null) {
        if (process.platform === 'win32') spawnSync('taskkill', ['/PID', String(service.pid), '/T', '/F'], { stdio: 'ignore' })
        else service.kill('SIGKILL')
      }
    }
  })
}

fs.rmSync(scratchRoot, { recursive: true, force: true })
process.stdout.write(`\n${passed} passed, ${failed} failed\n`)
process.exitCode = failed === 0 ? 0 : 1
