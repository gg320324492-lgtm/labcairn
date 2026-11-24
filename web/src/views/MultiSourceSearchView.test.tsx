import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
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

/**
 * The ingests, driven the way the operator drives them.
 *
 * **The three fields are the service's three names.** The body the panel
 * builds is checked through the request the fake recorded — the project,
 * the root and the resource key, spelled as the contract spells them — and
 * the answer is the service's count, drawn as it was sent.
 */
describe('the ingests it offers', () => {
  interface IngestFields {
    readonly label: string
    readonly button: string
    readonly pending: string
    readonly done: RegExp
    readonly counter: () => number
  }

  const cases: readonly IngestFields[] = [
    {
      label: 'Ingest a slide deck',
      button: 'Ingest the deck',
      pending: 'Indexing the deck…',
      done: /Indexed 14 objects \(2 title, 7 body, 3 notes, 1 table, 1 image\).*1 limitation/,
      counter: () => fake.pptIngests,
    },
    {
      label: 'Ingest a meeting text',
      button: 'Ingest the meeting text',
      pending: 'Indexing the meeting text…',
      done: /Indexed 9 records \(6 entries, 3 paragraphs\).*1 limitation/,
      counter: () => fake.meetingIngests,
    },
  ]

  /** Fill one ingest form's three fields and press its button. */
  async function ingestWith(formLabel: string, buttonName: string): Promise<void> {
    const form = await screen.findByRole('region', { name: formLabel })
    const project = within(form).getByLabelText('Project id')
    const root = within(form).getByLabelText('Root id')
    const resource = within(form).getByLabelText('Resource key')
    fireEvent.change(project, { target: { value: 'project-core' } })
    fireEvent.change(root, { target: { value: 'sources' } })
    fireEvent.change(resource, { target: { value: 'material/deck.pptx' } })
    fireEvent.click(within(form).getByRole('button', { name: buttonName }))
  }

  for (const fields of cases) {
    it(`sends the three names to the service and draws the count it answered with — ${fields.label}`, async () => {
      render(<MultiSourceSearchView cycle={0} onChanged={() => {}} />)

      await ingestWith(fields.label, fields.button)

      expect(await screen.findByText(fields.done)).toBeInTheDocument()
      expect(fields.counter()).toBe(1)
      // The body carried the three names, spelled as the contract spells
      // them — the fields are the service's, so a renamed field fails the
      // compile rather than arriving here as a surprise.
      const ingestRequests = fake.requests.filter(
        (request) =>
          request.method === 'POST' &&
          (request.url.replace(/^\/api/, '') === '/ppt/ingest' ||
            request.url.replace(/^\/api/, '') === '/meeting/ingest'),
      )
      expect(ingestRequests).toHaveLength(1)
      const body = JSON.parse(ingestRequests[0]?.body ?? '{}') as Record<string, unknown>
      expect(body).toEqual({
        project_id: 'project-core',
        root_id: 'sources',
        resource_key: 'material/deck.pptx',
      })
    })

    it(`draws the refusal with the service's reason, and no success — ${fields.label}`, async () => {
      if (fields.label === 'Ingest a slide deck') {
        fake.refusePptIngest = true
      } else {
        fake.refuseMeetingIngest = true
      }
      render(<MultiSourceSearchView cycle={0} onChanged={() => {}} />)

      await ingestWith(fields.label, fields.button)

      expect(await screen.findByText(/The service refused this ingest:/)).toBeInTheDocument()
      // The panel said refused, not done: a refusal drawn as a count would
      // be a success nobody sent.
      expect(screen.queryByText(fields.done)).toBeNull()
      expect(fields.counter()).toBe(1)
    })

    it(`sends nothing while a field is empty — ${fields.label}`, async () => {
      render(<MultiSourceSearchView cycle={0} onChanged={() => {}} />)

      const form = await screen.findByRole('region', { name: fields.label })
      const project = within(form).getByLabelText('Project id')
      const root = within(form).getByLabelText('Root id')
      // The resource key is left empty, and the button stands down.
      fireEvent.change(project, { target: { value: 'project-core' } })
      fireEvent.change(root, { target: { value: 'sources' } })
      const button = within(form).getByRole('button', { name: fields.button })
      expect(button).toBeDisabled()
      fireEvent.click(button)

      expect(fields.counter()).toBe(0)
      expect(screen.getAllByText('Nothing has been indexed from this form yet.')).toHaveLength(2)
    })
  }

  it('asks the workbench to read again after an ingest lands', async () => {
    const onChanged = vi.fn()
    render(<MultiSourceSearchView cycle={0} onChanged={onChanged} />)

    await ingestWith('Ingest a slide deck', 'Ingest the deck')
    await screen.findByText(/Indexed 14 objects/)

    // The deck's index changed, so the searches are asked again — the same
    // hand every other write in the workbench pulls.
    expect(onChanged).toHaveBeenCalled()
  })

  it('starts each form idle, with no success drawn before a request', () => {
    render(<MultiSourceSearchView cycle={0} />)

    const idles = screen.getAllByText('Nothing has been indexed from this form yet.')
    expect(idles).toHaveLength(2)
    expect(screen.queryByText(/Indexed \d+ objects/)).toBeNull()
    expect(screen.queryByText(/Indexed \d+ records/)).toBeNull()
  })
})
