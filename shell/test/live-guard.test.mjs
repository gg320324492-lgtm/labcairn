/**
 * The pure-layer half of T05's live 401 witness (AC-4).
 *
 * These tests decide theIPC boundary's rules; `scripts/rehearse-live-guard.mjs`
 * drives the same fixed mutation through a real Electron window against a real
 * `labcairn serve` and reads the status strip back over CDP. A rule that only
 * lived in the rehearsal would be unreadable to `pnpm test`, and a test that
 * only read this module would be a constant nobody passed.
 */

import assert from 'node:assert/strict'
import test from 'node:test'

import {
  DEV_API_BASE,
  LIVE_GUARD_PROBE,
  guardDetail,
  liveGuardUrl,
  readGuardResponse,
  senderIsAllowed,
} from '../src/live-guard.mjs'

const SERVICE_ORIGIN = 'http://127.0.0.1:54321'
const DEV_ORIGIN = 'http://127.0.0.1:5173'
const ALLOWED = new Set([SERVICE_ORIGIN, DEV_ORIGIN])

test('the live probe is one fixed relative mutation and carries no token', () => {
  assert.equal(LIVE_GUARD_PROBE.method, 'POST')
  assert.equal(LIVE_GUARD_PROBE.path, '/task/select')
  assert.equal(liveGuardUrl(false), '/task/select')
  assert.equal(liveGuardUrl(true), `${DEV_API_BASE}/task/select`)
  assert.ok(!LIVE_GUARD_PROBE.path.includes('://'), 'the probe named a host instead of a relative path')
  assert.deepEqual(Object.keys(LIVE_GUARD_PROBE.headers), ['Content-Type'])
  assert.ok(!JSON.stringify(LIVE_GUARD_PROBE).includes('Authorization'), 'the probe supplied an Authorization header')
  assert.equal(Object.isFrozen(LIVE_GUARD_PROBE), true, 'a caller could change the one fixed mutation')
})

test('the IPC sender is judged by origin, never by a URL that looks local', () => {
  assert.equal(senderIsAllowed(SERVICE_ORIGIN, ALLOWED), true)
  assert.equal(senderIsAllowed(DEV_ORIGIN, ALLOWED), true)
  assert.equal(senderIsAllowed('http://labcairn.example.invalid', ALLOWED), false)
  // A URL is not an origin: accepting one would make a foreign frame able to
  // claim the service by putting the service's path in its own address.
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

test('a dev proxy URL and the packaged same-origin URL are both relative', () => {
  for (const url of [liveGuardUrl(false), liveGuardUrl(true)]) {
    assert.ok(url.startsWith('/'), `${url} is not a relative path`)
    assert.equal(new URL(url, SERVICE_ORIGIN).origin, SERVICE_ORIGIN)
  }
})
