/**
 * The security baseline and the guards, witnessed at the pure layer.
 *
 * Two files do this job and each is honest about what it can see:
 * - this one holds the `webPreferences` object the window factory builds, the
 *   guard functions' decisions, and a fake webContents that proves the
 *   handlers were attached and the refusals recorded;
 * - `test/electron-witness.mjs` holds a *real* Electron window loaded from a
 *   real origin and proves the flags and the refusal behave in the renderer.
 *
 * A `file://` page refuses here by construction: `URL.origin` of a `file://`
 * URL is `"null"`, and the allow-list is a set of `http(s)` origins built from
 * `ServiceStarting` — so the counter-mutation that swaps a `file://` load in
 * meets a refusal, not a window showing somebody's disk.
 */

import assert from 'node:assert/strict'
import test from 'node:test'

import { shellWebPreferences, originOf, isAllowedUrl, attachNavigationGuards } from '../src/window-security.mjs'

const SERVICE_ORIGIN = 'http://127.0.0.1:54321'
const DEV_ORIGIN = 'http://127.0.0.1:5173'
const FOREIGN_ORIGIN = 'http://labcairn.example.invalid'

test('every shell window is constructed with the §5 baseline', () => {
  const preferences = shellWebPreferences({ preloadPath: '/preload.cjs' })
  assert.equal(preferences.nodeIntegration, false, 'nodeIntegration must be false')
  assert.equal(preferences.contextIsolation, true, 'contextIsolation must be true')
  assert.equal(preferences.sandbox, true, 'the renderer must be sandboxed')
  assert.equal(preferences.webviewTag, false, 'no <webview> route to another process')
  assert.equal(preferences.preload, '/preload.cjs')
  // The same object `createShellWindow` hands to `new BrowserWindow` — read
  // back from the real construction in `test/electron-witness.mjs`, which is
  // where Electron itself can answer. A constant nobody passed would be dead
  // code (plan §5.1), so the construction read-back lives where the window is
  // really built.
})

test('the allow-list answers to the service origin and the dev origin, and nothing else', () => {
  const allowed = new Set([SERVICE_ORIGIN, DEV_ORIGIN])
  assert.equal(isAllowedUrl(`${SERVICE_ORIGIN}/papers/1`, allowed), true)
  assert.equal(isAllowedUrl(`${DEV_ORIGIN}/`, allowed), true)
  assert.equal(isAllowedUrl(`${FOREIGN_ORIGIN}/`, allowed), false)
  assert.equal(isAllowedUrl(`${SERVICE_ORIGIN}.evil.invalid/`, allowed), false)
})

test('file:// and custom schemes carry no origin the guard could allow', () => {
  const allowed = new Set([SERVICE_ORIGIN])
  for (const url of ['file:///C:/Windows/win.ini', 'app://workbench/index', 'labcairn://open', 'about:blank']) {
    const origin = originOf(url)
    assert.ok(origin === null || origin === 'null', `${url} carries origin ${origin}; it must not be loadable`)
    assert.equal(isAllowedUrl(url, allowed), false, `${url} was allowed`)
  }
})

test('a foreign window-open and a foreign navigation are refused and recorded', () => {
  const opened = []
  const prevented = []
  const fakeContents = {
    setWindowOpenHandler: (handler) => opened.push(handler),
    on: (event, handler) => {
      if (event === 'will-navigate') prevented.push(handler)
    },
  }
  const allowed = new Set([SERVICE_ORIGIN])
  const refusals = []
  attachNavigationGuards(fakeContents, { allowedOrigins: () => allowed, refusals })

  assert.equal(opened.length, 1, 'setWindowOpenHandler was not attached')
  assert.equal(prevented.length, 1, 'the will-navigate guard was not attached')

  assert.deepEqual(opened[0]({ url: `${FOREIGN_ORIGIN}/escape` }), { action: 'deny' })
  assert.deepEqual(refusals.at(-1), { kind: 'window-open', url: `${FOREIGN_ORIGIN}/escape` })

  let preventedCalled = false
  prevented[0]({ preventDefault: () => (preventedCalled = true) }, `${FOREIGN_ORIGIN}/escape`)
  assert.equal(preventedCalled, true, 'a foreign navigation was not prevented')
  assert.deepEqual(refusals.at(-1), { kind: 'will-navigate', url: `${FOREIGN_ORIGIN}/escape` })

  preventedCalled = false
  prevented[0]({ preventDefault: () => (preventedCalled = true) }, `${SERVICE_ORIGIN}/papers/2`)
  assert.equal(preventedCalled, false, 'a same-origin navigation was blocked — the guard is too wide')
})
