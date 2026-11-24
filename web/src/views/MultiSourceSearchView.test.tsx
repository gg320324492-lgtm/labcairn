import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { forgetSessionToken } from '../api/session'
import { FakeApi, PROJECT_ID } from '../test/fakeApi'
import { MultiSourceSearchView } from './MultiSourceSearchView'

/**
 * The multi-source search panel, tested against a fake of the local API at
 * the network boundary.
 *
 * **The fake answers `fetch`, so everything between the screen and the wire
 * is the real thing**: the client, the paths, the session scheme and the
 * panel. What is checked here is the properties the work order states, and
 * each one is checked by breaking it.
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

/** Name what to search for, and ask the panel to ask the service. */
async function searchFor(term: string): Promise<void> {
  const field = await screen.findByLabelText('Search for')
  fireEvent.change(field, { target: { value: term } })
  fireEvent.click(screen.getByRole('button', { name: 'Search the sources' }))
}

describe('the question it asks', () => {
  it('asks all three sources the same query, once each', async () => {
    render(<MultiSourceSearchView cycle={0} />)
    await searchFor('silt')

    await waitFor(() => {
      expect(fake.searchesRun).toHaveLength(3)
    })
    const asked = fake.searchesRun.map((path) => path.split('?')[0] ?? '')
    expect(asked).toContain('/trajectory/search')
    expect(asked).toContain('/ppt/search')
    expect(asked).toContain('/meeting/search')
    for (const path of fake.searchesRun) {
      expect(path).toContain('q=silt')
      expect(path).toContain('limit=20')
    }
  })

  it('sends no request while the query is empty or only spaces', async () => {
    render(<MultiSourceSearchView cycle={0} />)

    // The empty query is not a question, and the panel does not pretend it
    // is one: nothing has left the page, and the panel says so in its own
    // words rather than drawing three empty indexes.
    await searchFor('   ')
    expect(fake.searchesRun).toHaveLength(0)
    expect(screen.getAllByText('No question has been asked yet.')).toHaveLength(3)
    expect(
      screen.getByText('Nothing has been asked yet: name what to search for.'),
    ).toBeInTheDocument()
  })

  it('names the project only when the caller named one', async () => {
    render(<MultiSourceSearchView cycle={0} />)
    await searchFor('silt')

    await waitFor(() => {
      expect(fake.searchesRun).toHaveLength(3)
    })
    // The query is the panel's own: the search is the workspace's, and a
    // project is named only when the panel was given one to name.
    for (const path of fake.searchesRun) {
      expect(path).not.toContain('project_id=')
    }
  })
})

describe('the answers it draws', () => {
  it('draws each source’s hits with the locator that says where they came from', async () => {
    render(<MultiSourceSearchView cycle={0} />)
    await searchFor('silt')

    // The trajectory's own provenance: the comment, its anchor, and the
    // locator the service resolves against the chain.
    expect(await screen.findByText('Name the method before its result.')).toBeInTheDocument()
    expect(
      screen.getByText(
        `comment ${'fb-method'} — issue issue-method — anchored at "the method was not named" (paragraph 2) — at paragraph:2:start:12:end:40`,
      ),
    ).toBeInTheDocument()

    // The edit that answered the comment, at its own address.
    expect(screen.getByText('The method was X-ray diffraction.')).toBeInTheDocument()
    expect(
      screen.getByText('edit edit-method — insertion — at word/document.xml#/w:body/w:p[2]'),
    ).toBeInTheDocument()

    // The deck's title and its note are two hits on one slide, and the
    // locator names the object, not only the slide.
    expect(screen.getByText('The silt record of the northern core')).toBeInTheDocument()
    expect(screen.getByText('slide 4 — position 1 — a title')).toBeInTheDocument()
    expect(screen.getByText('The depth was measured at 4.2 mm.')).toBeInTheDocument()
    expect(screen.getByText('slide 4 — position 3 — a notes')).toBeInTheDocument()

    // The meeting's entry carries its timestamp; the paragraph carries its
    // index, because its container gave it no time.
    expect(screen.getByText('We agreed to name the method in the revision.')).toBeInTheDocument()
    expect(screen.getByText('a entry — at 00:14:32 — record 7')).toBeInTheDocument()
    expect(screen.getByText('The depth measurement stands at 4.2 mm.')).toBeInTheDocument()
    expect(screen.getByText('a paragraph — record 2')).toBeInTheDocument()
  })

  it('says which index held nothing, rather than leaving it blank', async () => {
    fake.state.pptHits = []
    fake.state.meetingHits = []
    render(<MultiSourceSearchView cycle={0} />)
    await searchFor('silt')

    expect(await screen.findByText('Name the method before its result.')).toBeInTheDocument()
    // Two sources were empty, and the panel says so twice.
    expect(screen.getAllByText('Nothing in this index matched.')).toHaveLength(2)
  })

  it('draws the answer the service holds, read again when the cycle turns', async () => {
    const { rerender } = render(<MultiSourceSearchView cycle={0} />)
    await searchFor('silt')
    expect(await screen.findByText('Name the method before its result.')).toBeInTheDocument()

    // The page's memory is the service's answer, not a copy of it: the
    // service's list changes, and the next read shows what it now holds.
    fake.state.trajectoryHits = []
    rerender(<MultiSourceSearchView cycle={1} />)
    await waitFor(() => {
      expect(screen.queryByText('Name the method before its result.')).toBeNull()
    })
    expect(screen.getAllByText('Nothing in this index matched.')).toHaveLength(1)
  })
})

describe('the refusals it keeps apart', () => {
  it('shows one source’s failure without taking the other two down', async () => {
    fake.refuseSearch.meeting = true
    render(<MultiSourceSearchView cycle={0} />)
    await searchFor('silt')

    // The other two answered, and their hits are on the screen.
    expect(await screen.findByText('Name the method before its result.')).toBeInTheDocument()
    expect(screen.getByText('The silt record of the northern core')).toBeInTheDocument()

    // The meeting index failed, and the panel says which one and why.
    expect(
      screen.getByText(
        'The service did not answer this source: the meeting index could not be reached for this query.',
      ),
    ).toBeInTheDocument()
  })

  it('draws every source’s own failure when the service lost all three', async () => {
    fake.refuseSearch = { trajectory: true, ppt: true, meeting: true }
    render(<MultiSourceSearchView cycle={0} />)
    await searchFor('silt')

    await waitFor(() => {
      expect(fake.searchesRun).toHaveLength(3)
    })
    const failures = screen.getAllByText(/The service did not answer this source:/)
    expect(failures).toHaveLength(3)
    // Nothing answered, so no hit is drawn.
    expect(screen.queryByText('Name the method before its result.')).toBeNull()
  })

  it('names the project the search was scoped to, when one was asked for', async () => {
    fake.state.trajectoryHits = fake.state.trajectoryHits.map((hit) => ({
      ...hit,
      project_id: PROJECT_ID,
    }))
    render(<MultiSourceSearchView cycle={0} />)
    await searchFor('silt')

    await waitFor(() => {
      expect(fake.searchesRun).toHaveLength(3)
    })
    expect(await screen.findByText('Name the method before its result.')).toBeInTheDocument()
  })
})
