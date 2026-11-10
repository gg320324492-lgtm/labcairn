/**
 * The pure-layer half of T05's live 401 witness (AC-4).
 *
 * These tests decide the IPC boundary's rules; `scripts/rehearse-live-guard.mjs`
 * drives the same fixed mutation through a real Electron window against a real
 * `labcairn serve` and reads the status strip back over CDP. A rule that only
 * lived in the rehearsal would be unreadable to `pnpm test`, and a test that
 * only read a module no product code calls would be a constant nobody passed.
 *
 * **The last is the reason this file looks the way it does.** It used to import
 * a `LIVE_GUARD_PROBE` object from `src/live-guard.mjs` and assert its method
 * and headers. `src/preload.cjs` — the file that actually makes the request —
 * never read that object: a sandboxed preload is CommonJS with
 * `require('electron')` and nothing else, so it cannot import the module, and
 * the shell's real request was spelled out in its own literals. Mutating the
 * copy reddened this file and changed nothing the service ever saw, which is
 * plan §5.1's *a constant nobody passes is dead code* caught the hard way. The
 * request is now read back out of `preload.cjs` itself, the same way
 * `test/native-surface.test.mjs` reads the exposed surface back out of the file
 * that builds it.
 */

import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { guardDetail, readGuardResponse, senderIsAllowed } from '../src/live-guard.mjs'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.resolve(HERE, '..', 'src')
const PRELOAD = fs.readFileSync(path.join(SRC, 'preload.cjs'), 'utf8')

const SERVICE_ORIGIN = 'http://127.0.0.1:54321'
const DEV_ORIGIN = 'http://127.0.0.1:5173'
const ALLOWED = new Set([SERVICE_ORIGIN, DEV_ORIGIN])

/**
 * The one mutation the shell's page makes, read out of the file that makes it.
 *
 * `probeSessionGuard` is the whole request: the URL expression, the method, the
 * headers and the body are taken from its source text, so a change to the real
 * request changes what these assertions see. A witness that re-declared the
 * request here would be watching this file.
 */
function probeSource() {
  const start = PRELOAD.indexOf('function probeSessionGuard')
  assert.ok(start >= 0, 'preload.cjs no longer defines probeSessionGuard — the live probe left the page')
  const body = PRELOAD.slice(start, PRELOAD.indexOf('\n}', start) + 2)
  return body
}

test('the page itself makes one fixed relative mutation and carries no token', () => {
  const probe = probeSource()
  assert.match(probe, /method: 'POST'/, 'the live probe is no longer a mutation the session guard must guard')
  assert.match(probe, /fetch\(`\$\{prefix\}\$\{LIVE_GUARD_TASK_SELECT\}`/, 'the probe no longer fetches the one fixed task-select path')
  assert.match(probe, /const prefix = dev === true \? '\/api' : ''/, 'the probe no longer goes through the dev proxy prefix')

  // A token would have to arrive as a header or in the URL. Neither is here.
  assert.ok(!probe.includes('Authorization'), 'the probe supplied an Authorization header')
  assert.ok(!probe.includes('://'), 'the probe named a host instead of a relative path')
  assert.deepEqual(
    [...probe.matchAll(/headers: \{ ([^}]+) \}/g)].map((m) => m[1]),
    ["'Content-Type': 'application/json'"],
    'the probe carries a header other than Content-Type',
  )
  // The values the request is built from, in the file that builds it.
  const constants = [...PRELOAD.matchAll(/^const (LIVE_GUARD_[A-Z_]+) = (.+)$/gm)]
  const named = Object.fromEntries(constants.map(([, name, value]) => [name, value]))
  assert.equal(named.LIVE_GUARD_TASK_SELECT, "'/task/select'", 'the fixed path is not the one relative path expected')
  assert.match(named.LIVE_GUARD_TASK_ID ?? '', /^'[0-9a-f-]{36}'$/, 'the fixed task id is not a well-formed UUID spelling')
})

test('the IPC sender is judged by origin, never by a URL that looks local', () => {
  assert.equal(senderIsAllowed(SERVICE_ORIGIN, ALLOWED), true)
  assert.equal(senderIsAllowed(DEV_ORIGIN, ALLOWED), true)
  assert.equal(senderIsAllowed('http://labcairn.example.invalid', ALLOWED), false)
  // A URL is not an origin: accepting one would let a foreign frame claim the
  // service by putting the service's path in its own address.
  assert.equal(senderIsAllowed(`${SERVICE_ORIGIN}/task/select`, ALLOWED), false)
  assert.equal(senderIsAllowed('null', ALLOWED), false)
  assert.equal(senderIsAllowed(null, ALLOWED), false)
})

test('only the measured 401 session_required refusal is a held guard', async () => {
  const refused = await readGuardResponse({
    status: 401,
    json: async () => ({ reason: 'session_required', message: 'no token' }),
  })
  assert.deepEqual(refused, { status: 401, reason: 'session_required', ok: true })
  assert.equal(guardDetail(refused), 'mutation refused: 401 session_required')

  for (const [status, body] of [
    [200, { reason: 'session_required' }],
    [401, { reason: 'origin_refused' }],
    [403, { reason: 'session_required' }],
    [401, null],
  ]) {
    const result = await readGuardResponse({ status, json: async () => body })
    assert.equal(result.ok, false, `${status} ${JSON.stringify(body)} was mistaken for the measured refusal`)
    assert.match(guardDetail(result), /live guard probe failed/)
  }
})

test('the main process believes a report only from a sender it loaded', () => {
  // §5.4 entry 4 as a shape, not only as a call: `main.mjs` decides on the
  // *request* and again on the *report*, so a page that skipped the grant
  // cannot put a verdict on the strip either.
  const main = fs.readFileSync(path.join(SRC, 'main.mjs'), 'utf8')
  const decisions = [...main.matchAll(/senderIsAllowed\(origin, state\.allowedOrigins\)/g)]
  assert.equal(decisions.length, 2, `main.mjs checks the sender ${decisions.length} time(s); both the grant and the report must be checked`)
  assert.match(main, /refused guard-request origin/, 'a refusal of the request leaves no trace a witness can read')
  assert.match(main, /guard-request granted origin/, 'a grant leaves no trace, so removing the check looks like nothing happened')
})

test('both spellings of the probe URL are relative to the page origin', () => {
  const probe = probeSource()
  const packaged = new URL('/task/select', SERVICE_ORIGIN)
  const dev = new URL('/api/task/select', DEV_ORIGIN)
  assert.equal(packaged.origin, SERVICE_ORIGIN)
  assert.equal(dev.origin, DEV_ORIGIN)
  // The file spells both through the same expression; neither spelling names a host.
  assert.equal(probe.includes('http'), false, 'the probe built an absolute URL')
})
