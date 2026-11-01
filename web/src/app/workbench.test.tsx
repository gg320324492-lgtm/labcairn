import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { App } from '../App'
import { apiUrl } from '../api/base'
import type { AnalysisBody, ApprovalBody } from '../api/generated'
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
      'Trajectory',
      'Version graph',
      'Guidance',
      'Proposals',
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

describe('the changes the workbench makes', () => {
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

describe('the panels that read for themselves', () => {
  it('read again when the workbench reads again', async () => {
    render(<App />)
    await screen.findByText('Sediment core 04.pdf')
    const readsBefore = fake.requestsTo('/records').length

    // A rule confirmed is a write the task's own state does not carry, so
    // the workbench's answer does not change: the cycle turns because the
    // workbench was asked to read again, and not because the answer moved.
    // The panel that holds its own answer must read again all the same.
    fireEvent.change(await screen.findByLabelText('Whose word is it'), {
      target: { value: 'carol' },
    })
    const guidance = (await screen.findByRole('heading', { name: 'Guidance' })).closest('section')
    const rule = within(guidance as HTMLElement).getByText('Name the method before its result.')
    fireEvent.click(
      within(rule.closest('li') as HTMLElement).getByRole('button', { name: 'Confirm' }),
    )

    await waitFor(() => {
      expect(fake.requestsTo('/records').length).toBeGreaterThan(readsBefore)
    })
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

describe('the report the workbench asks for', () => {
  it('states the two claims the service takes no default for', async () => {
    render(<App />)
    const button = await screen.findByRole('button', { name: 'Render the report' })
    const readsBefore = fake.requestsTo('/artifacts').length

    fireEvent.click(button)

    await waitFor(() => {
      expect(fake.reportRenders).toBe(1)
    })
    const post = fake.requests.find(
      (request) => request.method === 'POST' && request.url.endsWith('/report'),
    )
    expect(post).toBeDefined()
    expect(JSON.parse(post?.body ?? '{}')).toEqual({ path: 'report', template_id: 'default' })
    expect(post?.headers['authorization']).toBe(`Bearer ${FAKE_TOKEN}`)

    // The screen shows records, so it reads the artefact list again rather
    // than trusting the receipt the POST handed back.
    await waitFor(() => {
      expect(fake.requestsTo('/artifacts').length).toBeGreaterThan(readsBefore)
    })
    expect(screen.queryByText(/The service refused that/)).toBeNull()
  })

  it('shows the service’s refusal when the task has nothing to carry', async () => {
    /**
     * This is the ordinary case: no operation writes an evidence record, so a
     * fresh task is refused and **nothing is written**. A screen that showed a
     * report it did not have, or that swallowed the reason, would be the failure
     * this test exists to catch.
     */
    fake.refuseReport = true
    render(<App />)
    const button = await screen.findByRole('button', { name: 'Render the report' })

    fireEvent.click(button)

    expect(await screen.findByText(/The service refused that/)).toBeInTheDocument()
    expect(screen.getByText(/nothing a report may carry/)).toBeInTheDocument()
    expect(fake.reportRenders).toBe(1)
    // The button comes back: a refusal is not a broken page.
    const again = await screen.findByRole('button', { name: 'Render the report' })
    expect(again).toBeEnabled()
  })
})

describe('the figure the workbench draws', () => {
  const SOURCE_ID = '0193f0a1-0000-7000-8000-0000000000b1'

  async function chooseMaterial(): Promise<void> {
    const material = await screen.findByLabelText('Material')
    fireEvent.change(material, { target: { value: SOURCE_ID } })
  }

  async function askThenGrant(): Promise<void> {
    fireEvent.click(screen.getByRole('button', { name: 'Ask for consent' }))
    const pending = await screen.findByText(/is pending\. Grant it in the Approval panel/)
    expect(pending).toBeInTheDocument()
    const capability = await screen.findByText('analysis.run')
    const row = capability.closest('li')
    expect(row).not.toBeNull()
    fireEvent.click(within(row as HTMLElement).getByRole('button', { name: 'Grant' }))
    await waitFor(() => {
      expect(screen.getByText('granted')).toBeInTheDocument()
    })
  }

  it('asks a question whose arguments are the selection the form states', async () => {
    /**
     * **The digest is the property.** The approval binds the arguments the run
     * will state, so the page must build the selection and the operator's own
     * parameters into one object and send exactly that object. A page that sent
     * the fields loose, or let the human paste a second selection, would ask
     * for a consent the run cannot match.
     */
    render(<App />)
    await chooseMaterial()

    fireEvent.click(screen.getByRole('button', { name: 'Ask for consent' }))

    await waitFor(() => {
      expect(fake.approvalRequests).toBe(1)
    })
    const post = fake.requests.find(
      (request) => request.method === 'POST' && request.url.endsWith('/approvals'),
    )
    expect(post).toBeDefined()
    expect(post?.headers['authorization']).toBe(`Bearer ${FAKE_TOKEN}`)
    const body = JSON.parse(post?.body ?? '{}') as ApprovalBody
    expect(body.capability).toBe('analysis.run')
    expect(body.root_id).toBe('source:0')
    expect(body.resource_key).toBe('core-04.pdf')
    expect(body.arguments).toEqual({
      path: 'core-04.pdf',
      operator_id: 'labcairn.analysis.grouped_aggregate',
      recipe: 'recipe.json',
      parameters: {
        aggregate: 'labcairn.analysis.mean@1.0.0',
        by: 'group',
        of: 'value',
        selection: {
          source_id: SOURCE_ID,
          content_sha256: 'c'.repeat(64),
          columns: ['group', 'value'],
          rows: { start: 2, end: 17 },
          missing: 'exclude',
        },
      },
    })
  })

  it('draws under the granted approval and shows the figure the service recorded', async () => {
    render(<App />)
    await chooseMaterial()
    await askThenGrant()

    fireEvent.click(screen.getByRole('button', { name: 'Draw the figure' }))

    await waitFor(() => {
      expect(fake.analysisRuns).toBe(1)
    })
    const post = fake.requests.find(
      (request) => request.method === 'POST' && request.url.endsWith('/analysis'),
    )
    expect(post).toBeDefined()
    const body = JSON.parse(post?.body ?? '{}') as AnalysisBody
    expect(body.approval_id).toBe('0193f0a1-0000-7000-8000-0000000000c3')
    expect(body.path).toBe('core-04.pdf')
    expect(body.operator_id).toBe('labcairn.analysis.grouped_aggregate')
    const parameters = body.parameters as { selection: { source_id: string } }
    expect(parameters.selection.source_id).toBe(SOURCE_ID)

    // The service's answer, not the page's guess: the result kind and the
    // receipt path it returned are what the screen says. Scoped to the
    // Figure panel, because the artefact list shows the same figure again.
    const figurePanel = (await screen.findByRole('heading', { name: 'Figure' })).closest('section')
    expect(figurePanel).not.toBeNull()
    const figure = within(figurePanel as HTMLElement)
    expect(figure.getByText(/GroupedResult/)).toBeInTheDocument()
    expect(figure.getByText(/analysis\/figure\.svg/)).toBeInTheDocument()
    expect(figure.getByText(/analysis\/manifest\.json/)).toBeInTheDocument()
  })

  it('shows the service’s refusal, because a refused run writes nothing', async () => {
    fake.refuseAnalysis = true
    render(<App />)
    await chooseMaterial()
    await askThenGrant()

    fireEvent.click(screen.getByRole('button', { name: 'Draw the figure' }))

    expect(await screen.findByText(/The service refused that/)).toBeInTheDocument()
    expect(screen.getByText(/approval_missing/)).toBeInTheDocument()
    expect(fake.analysisRuns).toBe(1)
  })

  it('reports a result that is not a figure as no figure, rather than inventing one', async () => {
    fake.figureless = true
    render(<App />)
    await chooseMaterial()
    await askThenGrant()

    fireEvent.click(screen.getByRole('button', { name: 'Draw the figure' }))

    expect(await screen.findByText(/no figure/)).toBeInTheDocument()
    expect(fake.analysisRuns).toBe(1)
  })
})
