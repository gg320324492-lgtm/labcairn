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
import test from 'node:test'

import { resolveRunConfig, DEV_PAGE_ORIGIN } from '../src/config.mjs'

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
