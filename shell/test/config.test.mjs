/**
 * The run-mode difference, witnessed as a pure function (AC-5's test half).
 *
 * The property: dev is an explicit opt-in on every count, the packaged mode
 * has no page URL of its own (it loads the service's own origin, which is
 * only known once `ServiceStarting` has been read), and a packaged
 * configuration that names a dev page URL is a refusal rather than an
 * override — AC-1's "assert the dev-build URL is rejected in a packaged
 * configuration".
 */

import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { resolveRunConfig, DEV_PAGE_ORIGIN, SHELL_ENV_FILE } from '../src/config.mjs'

const BASE = {
  LABCAIRN_SHELL_CLI: 'E:\\LabCairn\\.venv\\Scripts\\labcairn.exe',
  LABCAIRN_SHELL_WORKSPACE: 'E:\\labcairn-local\\shell-scratch\\ws1',
  LABCAIRN_SHELL_STATIC_DIR: 'E:\\LabCairn\\web\\dist',
}

test('a packaged build refuses the dev page URL outright', () => {
  assert.throws(
    () => resolveRunConfig({ ...BASE, LABCAIRN_SHELL_DEV_URL: DEV_PAGE_ORIGIN }, { packaged: true }),
    /refuses LABCAIRN_SHELL_DEV_URL/,
  )
  // The flag alone cannot make a packaged build a dev build: `dev` is read as
  // `!packaged && flag`, so the packaged mode stays packaged.
  const config = resolveRunConfig({ ...BASE, LABCAIRN_SHELL_DEV: '1' }, { packaged: true })
  assert.equal(config.dev, false)
  assert.equal(config.pageUrl, null)
})

test('the packaged build names no page URL: the page is the service origin', () => {
  const config = resolveRunConfig(BASE, { packaged: true })
  assert.equal(config.dev, false)
  assert.equal(config.pageUrl, null)
  assert.equal(config.staticDir, BASE.LABCAIRN_SHELL_STATIC_DIR)
})

test('a packaged build finds its own bundle beside the asar', () => {
  const resourcesDir = 'C:\\Program Files\\LabCairn\\resources'
  const withoutBundle = { ...BASE, LABCAIRN_SHELL_STATIC_DIR: undefined }

  const config = resolveRunConfig(withoutBundle, { packaged: true, resourcesDir })
  assert.equal(config.staticDir, path.join(resourcesDir, 'web-dist'))

  const explicit = resolveRunConfig(BASE, { packaged: true, resourcesDir })
  assert.equal(explicit.staticDir, BASE.LABCAIRN_SHELL_STATIC_DIR)

  const dev = resolveRunConfig(withoutBundle, { packaged: false, resourcesDir })
  assert.equal(dev.staticDir, null)
})

test('dev mode is explicit, and its page origin is the Vite origin', () => {
  const config = resolveRunConfig({ ...BASE, LABCAIRN_SHELL_DEV: '1' }, { packaged: false })
  assert.equal(config.dev, true)
  assert.equal(config.pageUrl, DEV_PAGE_ORIGIN)

  assert.throws(
    () => resolveRunConfig({ ...BASE, LABCAIRN_SHELL_DEV: '1', LABCAIRN_SHELL_DEV_URL: 'http://10.0.0.5:5173' }, { packaged: false }),
    /must be the Vite origin/,
    'a dev page URL on another host widened the page origin',
  )
  assert.throws(
    () => resolveRunConfig({ ...BASE, LABCAIRN_SHELL_DEV: '1', LABCAIRN_SHELL_DEV_URL: 'file:///C:/windows/win.ini' }, { packaged: false }),
    /must be the Vite origin|Vite origin/,
    'a file:// dev page URL was accepted',
  )
})

test('the entry point and the workspace are absolute paths, never names', () => {
  for (const name of ['LABCAIRN_SHELL_CLI', 'LABCAIRN_SHELL_WORKSPACE']) {
    const broken = { ...BASE }
    broken[name] = 'labcairn'
    assert.throws(() => resolveRunConfig(broken, { packaged: true }), /absolute path/)
  }
  assert.throws(() => resolveRunConfig({ LABCAIRN_SHELL_CLI: BASE.LABCAIRN_SHELL_CLI }, { packaged: true }), /LABCAIRN_SHELL_WORKSPACE/)
  assert.throws(
    () => resolveRunConfig({ ...BASE, LABCAIRN_SHELL_PORT: '0' }, { packaged: true }),
    /not a port number/,
  )
})

// T09's supply precedence, witnessed at the pure layer. A packaged build with
// neither variable set reads its own `resources/shell-env.json`; the
// environment wins wherever it names a value; a dev build reads no file.

test('a packaged build with no environment reads its own shell-env.json', () => {
  const resources = fs.mkdtempSync(path.join(os.tmpdir(), 'lc-shell-env-'))
  try {
    const resourcesDir = path.join(resources, 'resources')
    fs.mkdirSync(resourcesDir)
    fs.writeFileSync(
      path.join(resourcesDir, SHELL_ENV_FILE),
      JSON.stringify({ cliPath: 'C:\\backend\\labcairn.exe', workspace: 'LabCairn-workspace' }),
    )
    const config = resolveRunConfig({}, { packaged: true, resourcesDir })
    assert.equal(config.cliPath, 'C:\\backend\\labcairn.exe')
    assert.equal(config.workspace, path.join(resourcesDir, '..', 'LabCairn-workspace'))
  } finally {
    fs.rmSync(resources, { recursive: true, force: true })
  }
})

test('the environment wins over the file for each variable independently', () => {
  const resources = fs.mkdtempSync(path.join(os.tmpdir(), 'lc-shell-env-'))
  try {
    const resourcesDir = path.join(resources, 'resources')
    fs.mkdirSync(resourcesDir)
    fs.writeFileSync(
      path.join(resourcesDir, SHELL_ENV_FILE),
      JSON.stringify({ cliPath: 'C:\\backend\\from-file.exe', workspace: 'from-file-workspace' }),
    )
    const config = resolveRunConfig(
      { LABCAIRN_SHELL_CLI: 'C:\\backend\\from-env.exe' },
      { packaged: true, resourcesDir },
    )
    assert.equal(config.cliPath, 'C:\\backend\\from-env.exe', 'the environment CLI must win')
    assert.equal(config.workspace, path.join(resourcesDir, '..', 'from-file-workspace'), 'the file workspace must survive')

    const other = resolveRunConfig(
      { LABCAIRN_SHELL_WORKSPACE: 'E:\\Labs\\pilot' },
      { packaged: true, resourcesDir },
    )
    assert.equal(other.cliPath, 'C:\\backend\\from-file.exe', 'the file CLI must survive')
    assert.equal(other.workspace, 'E:\\Labs\\pilot', 'the environment workspace must win')
  } finally {
    fs.rmSync(resources, { recursive: true, force: true })
  }
})

test('a dev build reads no shell-env.json, and a packaged build with neither supply refuses', () => {
  const resources = fs.mkdtempSync(path.join(os.tmpdir(), 'lc-shell-env-'))
  try {
    const resourcesDir = path.join(resources, 'resources')
    fs.mkdirSync(resourcesDir)
    fs.writeFileSync(
      path.join(resourcesDir, SHELL_ENV_FILE),
      JSON.stringify({ cliPath: 'C:\\backend\\labcairn.exe', workspace: 'ws' }),
    )
    // Dev keeps its own supply rule: the variables, never the file. An empty
    // environment next to a populated shell-env.json must still refuse.
    assert.throws(
      () => resolveRunConfig({}, { packaged: false, resourcesDir }),
      /LABCAIRN_SHELL_CLI/,
    )
    // No file and no environment is the packaged refusal, with both names.
    assert.throws(
      () => resolveRunConfig({}, { packaged: true, resourcesDir: path.join(resources, 'empty') }),
      /LABCAIRN_SHELL_CLI/,
    )
  } finally {
    fs.rmSync(resources, { recursive: true, force: true })
  }
})

test('a packaged build with a broken shell-env.json refuses at startup, naming the file', () => {
  const resources = fs.mkdtempSync(path.join(os.tmpdir(), 'lc-shell-env-'))
  try {
    const resourcesDir = path.join(resources, 'resources')
    fs.mkdirSync(resourcesDir)
    fs.writeFileSync(path.join(resourcesDir, SHELL_ENV_FILE), '{"cliPath": "labcairn.exe"}')
    assert.throws(
      () => resolveRunConfig({}, { packaged: true, resourcesDir }),
      /"cliPath" must be an absolute path or an installation-relative path/,
    )
  } finally {
    fs.rmSync(resources, { recursive: true, force: true })
  }
})

test('the shipped template shape resolves: the frozen backend named installation-relatively', () => {
  // O3's wired supply (2026-11-14): the package's own file names the frozen
  // backend as `backend/labcairn` — the place extraResources carries it — and
  // the workspace in its installation-relative form. The environment names
  // nothing; the package says where its own backend lives.
  const resources = fs.mkdtempSync(path.join(os.tmpdir(), 'lc-shell-env-'))
  try {
    const resourcesDir = path.join(resources, 'resources')
    fs.mkdirSync(resourcesDir)
    fs.writeFileSync(
      path.join(resourcesDir, SHELL_ENV_FILE),
      fs.readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'shell-env.template.json'), 'utf8'),
    )
    const config = resolveRunConfig({}, { packaged: true, resourcesDir })
    assert.equal(config.cliPath, path.join(resourcesDir, 'backend', 'labcairn'))
    assert.equal(config.workspace, path.join(resourcesDir, '..', 'LabCairn-workspace'))
  } finally {
    fs.rmSync(resources, { recursive: true, force: true })
  }
})
