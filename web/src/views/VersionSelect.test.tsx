import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import { apiUrl } from '../api/base'
import type { ArtifactView } from '../api/generated'
import { forgetSessionToken } from '../api/session'
import { FakeApi, reportReceipt } from '../test/fakeApi'

/**
 * The version-selection surface, tested against a fake of the local API at
 * the network boundary — the same arrangement `workbench.test.tsx` uses, so
 * what is exercised is the page, the client and the paths, and not a
 * component handed a made-up object.
 *
 * **The property this panel claims is a view, not a write.** Choosing a
 * revision changes what the page shows and asks the service for nothing but
 * the reads it already made; a selection that POSTed somewhere would be the
 * page claiming the service stores a "current version", which no route does.
 * The test that watches the selection therefore also watches the requests —
 * a selection that invented a write would fail here.
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

/** A second revision of the report, as a second render would list it. */
function secondRevision(): ArtifactView {
  const receipt = reportReceipt()
  return {
    receipt: {
      ...receipt,
      receipt_id: '0193f0a1-0000-7000-8000-0000000000b2',
      revision: 2,
      content_sha256: 'c'.repeat(64),
      relative_path: 'reports/v2/report.html',
      created_at: '2026-10-21T09:05:00+00:00',
    },
    resource_key: 'reports/v2/report.html',
  }
}

/** The version panel's own section, found by its heading. */
async function theVersionPanel(): Promise<HTMLElement> {
  const heading = await screen.findByRole('heading', { name: 'Version select' })
  return heading.closest('section') as HTMLElement
}

describe('the version-selection surface', () => {
  it('lists the revisions the receipts carry, oldest first, with each hash', async () => {
    fake.state.artifacts.push(secondRevision())
    render(<App />)

    const panel = await theVersionPanel()
    const rows = within(panel).getAllByRole('listitem')
    expect(rows).toHaveLength(2)
    expect(rows[0]).toHaveTextContent('revision 1')
    expect(rows[1]).toHaveTextContent('revision 2')
    // The hash is the receipt's own: it is how a reader tells two revisions
    // of one report apart, and the panel does not compose a substitute.
    expect(rows[0]).toHaveTextContent('sha256')
    expect(rows[1]).toHaveTextContent('c'.repeat(16))
  })

  it('shows the newest revision first, and switches when the reader chooses', async () => {
    fake.state.artifacts.push(secondRevision())
    render(<App />)

    const panel = await theVersionPanel()
    // The default view is the newest revision the service lists. The frame
    // is named for the revision it shows, so the name is the query.
    expect(within(panel).getByTitle('Revision 2: reports/v2/report.html')).toBeInTheDocument()

    // Choosing revision 1 changes what the page shows, by this page's own
    // state. The page re-reads on the render the click causes — that is the
    // workbench's own no-cached-state rule — so what the choice must not do
    // is **write**: no request the reads did not already make, and no POST
    // anywhere, because no route stores a current version.
    const writesBefore = fake.requests.filter((request) => request.method !== 'GET').length
    fireEvent.click(within(panel).getByRole('button', { name: 'Show' }))

    expect(within(panel).getByTitle('Revision 1: reports/report.html')).toBeInTheDocument()
    expect(within(panel).queryByTitle('Revision 2: reports/v2/report.html')).toBeNull()
    const writesAfter = fake.requests.filter((request) => request.method !== 'GET').length
    expect(writesAfter).toBe(writesBefore)
    // The frame the reader chose is fetched from the service's content route.
    expect(within(panel).getByTitle('Revision 1: reports/report.html')).toHaveAttribute(
      'src',
      apiUrl('/artifacts/0193f0a1-0000-7000-8000-0000000000a2/content'),
    )
  })

  it('says that choosing writes nothing, beside the choice itself', async () => {
    render(<App />)

    const panel = await theVersionPanel()
    expect(
      within(panel).getByText(/the service holds no .current version. of its own/i),
    ).toBeInTheDocument()
  })

  it('shows the newest revision the service lists, after the service adds one', async () => {
    const { rerender } = render(<App />)
    const panel = await theVersionPanel()
    expect(within(panel).getByTitle('Revision 1: reports/report.html')).toBeInTheDocument()

    // A second render lands while this page is open: the reads happen again
    // on the next render, so the panel shows the revision the service now
    // lists rather than a choice this page remembered.
    fake.state.artifacts.push(secondRevision())
    rerender(<App />)

    const again = await theVersionPanel()
    expect(within(again).getByTitle('Revision 2: reports/v2/report.html')).toBeInTheDocument()
  })

  it('says so plainly when the task has produced no report', async () => {
    fake.state.artifacts = []
    fake.state.task.artifacts = []
    render(<App />)

    const panel = await theVersionPanel()
    expect(await within(panel).findByText(/no report yet/i)).toBeInTheDocument()
  })
})
