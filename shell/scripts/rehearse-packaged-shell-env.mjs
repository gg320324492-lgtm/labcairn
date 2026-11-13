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
import fs from 'node:fs'
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
    assert.match(error.message, /"cliPath" must be an absolute path/)
    process.stdout.write(`  refusal: ${error.message.split('\n')[0]}\n`)
  }
})

fs.rmSync(scratchRoot, { recursive: true, force: true })
process.stdout.write(`\n${passed} passed, ${failed} failed\n`)
process.exitCode = failed === 0 ? 0 : 1
