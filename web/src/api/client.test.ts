import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { APPROVAL_ID, FakeApi, FAKE_TOKEN, urlOf } from '../test/fakeApi'
import { ApiFailure, ApiPathRefused, ApiRefusal, LabCairnClient } from './client'
import { forgetSessionToken, sessionToken } from './session'

/**
 * The client is the boundary where the rules are kept, so the tests are
 * about the boundary and not about the widgets above it.
 */

let fake: FakeApi
let client: LabCairnClient

beforeEach(() => {
  fake = new FakeApi()
  client = new LabCairnClient('')
  vi.stubGlobal('fetch', fake.fetch)
  forgetSessionToken()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('reads', () => {
  it('asks for a path on its own origin and carries no token', async () => {
    await client.get('/task')

    expect(fake.requests).toHaveLength(1)
    expect(fake.requests[0]?.url).toBe('/task')
    expect(fake.requests[0]?.method).toBe('GET')
    expect(fake.requests[0]?.headers['authorization']).toBeUndefined()
  })

  it('never asks the session for the session response itself', async () => {
    await expect(client.get('/session')).rejects.toThrow(/sessionPath/)
    expect(fake.requests).toHaveLength(0)
  })
})

describe('changes', () => {
  it('presents the token in the header and in no other place', async () => {
    await client.post(`/approvals/${APPROVAL_ID}/grant`)

    const request = fake.requests.find((entry) => entry.method === 'POST')
    expect(request?.headers['authorization']).toBe(`Bearer ${FAKE_TOKEN}`)
    expect(request?.url).not.toContain(FAKE_TOKEN)
    expect(request?.body ?? '').not.toContain(FAKE_TOKEN)
  })

  it('asks for the token once and then holds it', async () => {
    await client.post(`/approvals/${APPROVAL_ID}/grant`)
    await client.post(`/approvals/${APPROVAL_ID}/grant`)

    expect(fake.requestsTo('/session')).toHaveLength(1)
    expect(sessionToken()).toBe(FAKE_TOKEN)
  })

  it('sends no cookie', async () => {
    await client.post(`/approvals/${APPROVAL_ID}/grant`)

    const request = fake.requests.find((entry) => entry.method === 'POST')
    expect(request).toBeDefined()
    expect(request?.headers['cookie']).toBeUndefined()
  })
})

describe('the relative-path guard', () => {
  it('refuses a path that names a host, and sends nothing', async () => {
    await expect(client.get('https://example.com/collect')).rejects.toBeInstanceOf(ApiPathRefused)
    expect(fake.requests).toHaveLength(0)
  })

  it('refuses a protocol-relative path', async () => {
    await expect(client.get('//example.com/collect')).rejects.toBeInstanceOf(ApiPathRefused)
    expect(fake.requests).toHaveLength(0)
  })

  it('refuses a path that uses backslashes, which a browser reads as slashes', async () => {
    await expect(client.get('\\\\example.com\\collect')).rejects.toBeInstanceOf(ApiPathRefused)
    expect(fake.requests).toHaveLength(0)
  })

  it('refuses a path with any scheme, not only http', async () => {
    await expect(client.get('ftp://example.com/x')).rejects.toBeInstanceOf(ApiPathRefused)
    expect(fake.requests).toHaveLength(0)
  })
})

describe('refusals', () => {
  it("carries the service's reason and message", async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ reason: 'session_required', message: 'no token' }), {
            status: 403,
            headers: { 'Content-Type': 'application/json' },
          }),
        ),
      ),
    )

    const failure = await client.get('/task').catch((error: unknown) => error)

    expect(failure).toBeInstanceOf(ApiRefusal)
    expect((failure as ApiRefusal).reason).toBe('session_required')
    expect((failure as ApiRefusal).message).toBe('no token')
  })

  it('answers a status it does not understand as a failure, not as data', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(new Response('not json', { status: 500, statusText: 'Server Error' })),
      ),
    )

    const failure = await client.get('/task').catch((error: unknown) => error)

    expect(failure).toBeInstanceOf(ApiFailure)
    expect((failure as ApiFailure).status).toBe(500)
  })
})

describe('a refused token', () => {
  it('asks for a new token and makes the change once more', async () => {
    let posts = 0
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = urlOf(input)
        if (url === '/session') {
          return Promise.resolve(
            new Response(JSON.stringify({ token: 'new-token', path: 'p' }), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }),
          )
        }
        posts += 1
        if (posts === 1) {
          return Promise.resolve(
            new Response(JSON.stringify({ reason: 'session_required', message: 'no' }), {
              status: 401,
              headers: { 'Content-Type': 'application/json' },
            }),
          )
        }
        const headers = new Headers(init?.headers)
        expect(headers.get('authorization')).toBe('Bearer new-token')
        return Promise.resolve(
          new Response(JSON.stringify({ ok: true }), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }),
    )

    await expect(client.post(`/approvals/${APPROVAL_ID}/grant`)).resolves.toEqual({ ok: true })
    expect(posts).toBe(2)
    expect(sessionToken()).toBe('new-token')
  })

  it('stops after one retry rather than hammering a service that has said no', async () => {
    let posts = 0
    vi.stubGlobal(
      'fetch',
      vi.fn((input: RequestInfo | URL) => {
        const url = urlOf(input)
        if (url === '/session') {
          return Promise.resolve(
            new Response(JSON.stringify({ token: 'new-token', path: 'p' }), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            }),
          )
        }
        posts += 1
        return Promise.resolve(
          new Response(JSON.stringify({ reason: 'session_required', message: 'no' }), {
            status: 401,
            headers: { 'Content-Type': 'application/json' },
          }),
        )
      }),
    )

    await expect(client.post(`/approvals/${APPROVAL_ID}/grant`)).rejects.toBeInstanceOf(ApiRefusal)
    expect(posts).toBe(2)
  })
})
