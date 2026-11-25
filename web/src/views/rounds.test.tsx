import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DeliveryCenterView } from './DeliveryCenterView'
import { ReviewDeskView } from './ReviewDeskView'
import { fixturePreview } from './deliveryFixture'
import { fixtureManuscript, fixtureOpinions } from './reviewFixture'

/**
 * The workbench reads its round from the service.
 *
 * **The round used to be the fixture's, and the fixture said so.** The desk
 * and the delivery centre each took their project and version from a sample
 * fixture, so every condition the workbench was supposed to hold — the
 * opinions of the pilot paper, the preview before applying, the four
 * deliverables in one delivery centre — was exercised against a sample
 * round and never against the paper itself.
 *
 * **So the witness watches the question, not the answer.** The fake names a
 * round that is deliberately *not* the fixture's, and the assertion is on
 * the address the workbench asked with. A desk that drew the sample's
 * opinions under the service's round would be drawing a sample round and
 * calling it the workspace's — and that is the failure this file exists to
 * catch.
 *
 * **And the reader is told which round they are looking at**, because a
 * workbench that cannot say which round it is showing cannot be believed
 * about the pilot paper.
 */

/** The round the fake service names — deliberately not the fixture's. */
const SERVICE_PROJECT_ID = 'proj-pilot-2026'
const SERVICE_VERSION_ID = 'ver-pilot-07'

/** The paths the workbench asked for, in order. */
let asked: string[] = []

/** The bodies the workbench posted, beside the path it posted them to. */
let posted: { readonly path: string; readonly body: unknown }[] = []

/** Whether the fake service answers the rounds route at all. */
let roundsAnswer = true

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

beforeEach(() => {
  asked = []
  posted = []
  roundsAnswer = true
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      await Promise.resolve()
      const url = (
        typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
      ).replace(/^\/api/, '')
      asked.push(url)
      if (typeof init?.body === 'string') {
        posted.push({ path: url, body: JSON.parse(init.body) })
      }
      if (url === '/review/rounds') {
        if (!roundsAnswer) {
          return jsonResponse(404, { reason: 'not_found', message: 'no such route' })
        }
        return jsonResponse(200, [
          {
            project_id: SERVICE_PROJECT_ID,
            version_id: SERVICE_VERSION_ID,
            created_at: '2026-11-25T09:00:00+00:00',
          },
        ])
      }
      if (url === '/session') {
        // The session read the POST boundary asks for before a change.
        return jsonResponse(200, { token: 'test-token', path: '/tmp/token' })
      }
      if (url.startsWith('/review/opinions')) {
        return jsonResponse(200, fixtureOpinions)
      }
      if (url.startsWith('/review/manuscript')) {
        return jsonResponse(200, fixtureManuscript)
      }
      if (url.startsWith('/review/preview')) {
        return jsonResponse(200, {
          ...fixturePreview,
          project_id: SERVICE_PROJECT_ID,
          input_version_id: SERVICE_VERSION_ID,
        })
      }
      return jsonResponse(404, { reason: 'not_found', message: 'no such route' })
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('the round the workbench addresses', () => {
  it('asks the desk for the opinions of the round the service named', async () => {
    render(<ReviewDeskView />)
    await waitFor(() => {
      expect(asked.some((path) => path.startsWith('/review/opinions'))).toBe(true)
    })
    const opinionsRead = asked.find((path) => path.startsWith('/review/opinions'))
    expect(opinionsRead).toContain(`project_id=${SERVICE_PROJECT_ID}`)
    expect(opinionsRead).toContain(`version_id=${SERVICE_VERSION_ID}`)
  })

  it('tells the reader which round the desk is looking at', async () => {
    render(<ReviewDeskView />)
    const note = await screen.findByText(/Live data/)
    expect(note.textContent).toContain(SERVICE_PROJECT_ID)
    expect(note.textContent).toContain(SERVICE_VERSION_ID)
  })

  it('addresses the delivery centre at the round the service named', async () => {
    render(<DeliveryCenterView />)
    await waitFor(() => {
      expect(posted.some((entry) => entry.path.startsWith('/review/preview'))).toBe(true)
    })
    const preview = posted.find((entry) => entry.path.startsWith('/review/preview'))
    expect(preview?.body).toMatchObject({
      project_id: SERVICE_PROJECT_ID,
      input_version_id: SERVICE_VERSION_ID,
    })
  })

  it('tells the reader which round the delivery centre is looking at', async () => {
    render(<DeliveryCenterView />)
    const note = await screen.findByText(/Fixture data/)
    expect(note.textContent).toContain(SERVICE_PROJECT_ID)
    expect(note.textContent).toContain(SERVICE_VERSION_ID)
  })
})

describe('the round the service does not name', () => {
  beforeEach(() => {
    roundsAnswer = false
  })

  it('falls back to the sample round, and says which round that is', async () => {
    render(<ReviewDeskView />)
    const note = await screen.findByText(/Fixture data/)
    expect(note.textContent).toContain(fixtureOpinions.project_id)
    expect(note.textContent).toContain(fixtureOpinions.version_id)
  })

  it('falls back to the sample round at the delivery centre too', async () => {
    render(<DeliveryCenterView />)
    const note = await screen.findByText(/Fixture data/)
    expect(note.textContent).toContain(fixtureOpinions.project_id)
    expect(note.textContent).not.toContain(SERVICE_PROJECT_ID)
  })
})
