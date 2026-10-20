import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import { apiUrl } from '../api/base'
import { forgetSessionToken } from '../api/session'
import { REPORT_FIRST_PASS_NOTICE } from '../report/firstPassNotice'
import { ARTEFACT_CONTENT_MARKER, FakeApi, FAKE_TOKEN } from '../test/fakeApi'

/**
 * The workbench, tested against a fake of the local API at the network
 * boundary.
 *
 * The fake answers `fetch`, so everything between the screen and the wire is
 * the real thing: the client, the paths, the session scheme and the views.
 * What is being checked is the properties the work order states, and each
 * one is checked by breaking it — see the mutation table in the report.
 */

let fake: FakeApi

beforeEach(() => {
  fake = new FakeApi()
  vi.stubGlobal('fetch', fake.fetch)
  forgetSessionToken()
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('the views', () => {
  it('draws every one the work order names', async () => {
    render(<App />)

    for (const heading of [
      'Projects',
      'Plan',
      'Steps',
      'Approval',
      'Source anchors',
      'Evidence',
      'Artefacts',
      'Revisions',
    ]) {
      expect(await screen.findByRole('heading', { name: heading })).toBeInTheDocument()
    }
  })

  it('draws the task the service returned', async () => {
    render(<App />)

    expect(
      await screen.findByRole('heading', {
        name: 'What the sediment record says about the winter',
      }),
    ).toBeInTheDocument()
    expect(
      screen.getAllByText('Reconstruct the winter temperature from the sediment record.').length,
    ).toBeGreaterThan(0)
    expect(screen.getByText('Sediment core 04.pdf')).toBeInTheDocument()
    expect(screen.getByText('anchor key core-04.pdf')).toBeInTheDocument()
    expect(screen.getByText(/Declared by research-report/)).toBeInTheDocument()
    expect(screen.getAllByText('retrieve').length).toBeGreaterThan(0)
  })

  it('says that the event stream is not read', async () => {
    render(<App />)

    // The service offers a stream and the workbench does not read it. A
    // reader who found the omission and no note about it would assume it
    // had been forgotten, so the note is on the screen and watched here.
    expect(await screen.findByText(/event stream is not read/)).toBeInTheDocument()
  })
})

describe('the UI holds no state', () => {
  it('shows what the service says, even when the service changes its mind', async () => {
    const { rerender } = render(<App />)
    await screen.findByText('Sediment core 04.pdf')

    fake.state.task.task.title = 'A title the service changed to'
    rerender(<App />)

    expect(
      await screen.findByRole('heading', { name: 'A title the service changed to' }),
    ).toBeInTheDocument()
  })

  it("shows the database's state after a reload, not a cached one", async () => {
    const { unmount } = render(<App />)
    await screen.findByText('Sediment core 04.pdf')

    fake.state.task.task.title = 'A title that only the reload can show'
    unmount()
    render(<App />)

    expect(
      await screen.findByRole('heading', { name: 'A title that only the reload can show' }),
    ).toBeInTheDocument()
  })
})

describe('the session token', () => {
  it('is never in the DOM', async () => {
    render(<App />)
    await screen.findByText('Sediment core 04.pdf')

    expect(document.body.innerHTML).not.toContain(FAKE_TOKEN)
    expect(document.body.textContent).not.toContain(FAKE_TOKEN)
  })

  it("is never in the browser's storage", async () => {
    render(<App />)
    await screen.findByText('Sediment core 04.pdf')

    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })

  it('is never in a log', async () => {
    const said: unknown[] = []
    for (const level of ['log', 'info', 'warn', 'error', 'debug'] as const) {
      vi.spyOn(console, level).mockImplementation((...args: unknown[]) => {
        said.push(...args)
      })
    }

    render(<App />)
    await screen.findByText('Sediment core 04.pdf')

    expect(JSON.stringify(said)).not.toContain(FAKE_TOKEN)
  })

  it('is never in a URL', async () => {
    render(<App />)
    await screen.findByText('Sediment core 04.pdf')

    for (const request of fake.requests) {
      expect(request.url).not.toContain(FAKE_TOKEN)
    }
  })
})

describe('the one change the workbench makes', () => {
  it('asks the service once, with the token in the header', async () => {
    render(<App />)
    const button = await screen.findByRole('button', { name: 'Grant' })

    fireEvent.click(button)

    await waitFor(() => {
      expect(screen.getByText('granted')).toBeInTheDocument()
    })
    const posts = fake.requests.filter((request) => request.method === 'POST')
    expect(posts).toHaveLength(1)
    expect(posts[0]?.headers['authorization']).toBe(`Bearer ${FAKE_TOKEN}`)
  })

  it('does not mark the approval granted when the service refuses', async () => {
    fake.refuseGrants = true
    render(<App />)
    const button = await screen.findByRole('button', { name: 'Grant' })

    fireEvent.click(button)

    expect(await screen.findByText(/The service refused that/)).toBeInTheDocument()
    expect(screen.queryByText('granted')).toBeNull()
    expect(screen.getByRole('button', { name: 'Grant' })).toBeInTheDocument()
  })

  it('cannot be asked for twice while one is in flight', async () => {
    fake.grantDelayMs = 50
    render(<App />)
    const button = await screen.findByRole('button', { name: 'Grant' })

    fireEvent.click(button)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Grant' })).toBeDisabled()
    })
    fireEvent.click(screen.getByRole('button', { name: 'Grant' }))

    await waitFor(() => {
      expect(screen.getByText('granted')).toBeInTheDocument()
    })
    expect(fake.requests.filter((request) => request.method === 'POST')).toHaveLength(1)
  })
})

describe('the artefact preview', () => {
  it('shows a figure as an image, and never as an inline SVG', async () => {
    render(<App />)

    const image = await screen.findByRole('img')
    expect(image).toHaveAttribute(
      'src',
      apiUrl('/artifacts/0193f0a1-0000-7000-8000-0000000000a1/content'),
    )
    expect(document.querySelector('svg')).toBeNull()
  })

  it('shows the report in a frame that can run nothing', async () => {
    render(<App />)

    const frame = await screen.findByTitle('Preview of reports/report.html')
    expect(frame.tagName).toBe('IFRAME')
    expect(frame.getAttribute('sandbox')).toBe('')
    expect(frame).not.toHaveAttribute('srcdoc')
  })

  it("never reads an artefact's bytes into the page", async () => {
    render(<App />)
    await screen.findByText('Sediment core 04.pdf')

    expect(fake.artefactContentReads).toBe(0)
    expect(document.body.innerHTML).not.toContain(ARTEFACT_CONTENT_MARKER)
  })
})

describe("the report's own limit", () => {
  it('is on the screen when a report is shown', async () => {
    render(<App />)

    expect(await screen.findByText(REPORT_FIRST_PASS_NOTICE)).toBeInTheDocument()
  })
})

describe('where the workbench looks', () => {
  it('asks only for paths on its own origin', async () => {
    render(<App />)
    await screen.findByText('Sediment core 04.pdf')

    expect(fake.requests.length).toBeGreaterThan(0)
    for (const request of fake.requests) {
      expect(request.url.startsWith('/')).toBe(true)
      expect(request.url).not.toContain('://')
    }
  })
})
