import { useState } from 'react'
import type { JSX } from 'react'

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { forgetSessionToken } from '../api/session'
import { CONFIRMED_ISSUE_ID, FakeApi, OPEN_ISSUE_ID, PROJECT_ID } from '../test/fakeApi'
import { IssuesView } from './IssuesView'

/**
 * The issue panel, tested against a fake of the local API at the network
 * boundary.
 *
 * **The fake answers `fetch`, so everything between the screen and the wire
 * is the real thing**: the client, the paths, the session scheme and the
 * panel. What is checked here is the properties the work order states — the
 * listing, the filters, the record, the walk and the three refusals — and
 * each one is checked against what the service answered, not against what
 * the panel guessed.
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

/** The panel, and the workbench's cycle it reads with. */
function Harness(): JSX.Element {
  return <IssuesViewHarness />
}

function IssuesViewHarness(): JSX.Element {
  const [cycle, setCycle] = useState(0)
  return (
    <IssuesView
      cycle={cycle}
      onChanged={() => {
        setCycle((count) => count + 1)
      }}
    />
  )
}

/** Ask for a project's issues, and wait for the answer when there is one. */
async function listProject(project = PROJECT_ID): Promise<void> {
  fireEvent.change(await screen.findByLabelText('Project id'), {
    target: { value: project },
  })
  fireEvent.click(screen.getByRole('button', { name: 'List the issues' }))
  // An empty answer is a fact the panel draws too, so the caller that asked
  // for an empty project waits for that answer instead of a row.
  await screen.findByText(
    project === PROJECT_ID
      ? 'severity serious, type function'
      : new RegExp(`lists no issue for project ${project}`),
    {},
    { timeout: 2000 },
  )
}

/** One issue's block: the row the issue is drawn in. */
function issueBlock(errorText: string): HTMLElement {
  const found = screen.getByText(errorText)
  const block = found.closest('li')
  expect(block).not.toBeNull()
  return block as HTMLElement
}

describe('the listing it draws', () => {
  it('asks for a project’s issues only after the project is named', async () => {
    render(<Harness />)

    // No project, no question: the panel says so rather than asking the
    // service for a listing of nothing.
    expect(screen.getByText(/No project has been named/)).toBeInTheDocument()
    expect(fake.requests.some((request) => request.url.includes('/issues?'))).toBe(false)

    fireEvent.click(screen.getByRole('button', { name: 'List the issues' }))

    expect(await screen.findByText(/name the project whose issues to list/)).toBeInTheDocument()
    expect(fake.requests.some((request) => request.url.includes('/issues?'))).toBe(false)
  })

  it('draws each issue with the fields the record carries', async () => {
    render(<Harness />)
    await listProject()

    const block = issueBlock('The method was named after the result it produced.')
    expect(within(block).getByText('open')).toBeInTheDocument()
    expect(within(block).getByText('issue issue-pilot-method')).toBeInTheDocument()
    expect(within(block).getByText(`project ${PROJECT_ID}`)).toBeInTheDocument()
    expect(within(block).getByText('severity serious, type function')).toBeInTheDocument()
    expect(within(block).getByText('step draft')).toBeInTheDocument()
    expect(within(block).getByText('duration 12.5s, 1 retries')).toBeInTheDocument()
    expect(within(block).getByText(/reported by alice at/)).toBeInTheDocument()
  })

  it('draws an absent number as absent, and not as a zero', async () => {
    render(<Harness />)
    await listProject()

    const block = issueBlock('The depth was reported without its unit.')
    expect(
      within(block).getByText('duration not recorded, retries not recorded'),
    ).toBeInTheDocument()
    expect(within(block).getByText('task —, version v2, feedback —')).toBeInTheDocument()
  })

  it('sends the project as the query, and the filters when they are set', async () => {
    render(<Harness />)
    await listProject()

    const asked = fake.requests.filter((request) => request.url.includes('/issues?'))
    expect(asked.length).toBeGreaterThan(0)
    expect(asked[0]?.url).toContain(`/issues?project_id=${PROJECT_ID}`)

    fireEvent.change(screen.getByLabelText('Status filter'), { target: { value: 'open' } })
    fireEvent.click(screen.getByRole('button', { name: 'List the issues' }))

    await waitFor(() => {
      expect(
        fake.requests.some((request) =>
          request.url.includes(`/issues?project_id=${PROJECT_ID}&status=open`),
        ),
      ).toBe(true)
    })

    fireEvent.change(screen.getByLabelText('Severity filter'), { target: { value: 'blocker' } })
    fireEvent.click(screen.getByRole('button', { name: 'List the issues' }))

    await waitFor(() => {
      expect(
        fake.requests.some((request) =>
          request.url.includes(`/issues?project_id=${PROJECT_ID}&status=open&severity=blocker`),
        ),
      ).toBe(true)
    })
  })

  it('narrows the drawn list when a filter is set', async () => {
    render(<Harness />)
    await listProject()

    fireEvent.change(screen.getByLabelText('Severity filter'), { target: { value: 'blocker' } })
    fireEvent.click(screen.getByRole('button', { name: 'List the issues' }))

    await waitFor(() => {
      expect(screen.queryByText('The method was named after the result it produced.')).toBeNull()
    })
    expect(screen.getByText('The depth was reported without its unit.')).toBeInTheDocument()
  })

  it('says what an empty answer means, instead of drawing nothing', async () => {
    render(<Harness />)
    await listProject('project-nowhere')

    expect(
      await screen.findByText(/The service lists no issue for project project-nowhere/),
    ).toBeInTheDocument()
  })

  it('says when the service did not answer, and keeps the question', async () => {
    const refusal = (): Promise<Response> =>
      Promise.resolve(
        new Response(JSON.stringify({ reason: 'store_unavailable', message: 'closed.' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    vi.stubGlobal('fetch', refusal)
    render(<Harness />)

    fireEvent.change(await screen.findByLabelText('Project id'), {
      target: { value: PROJECT_ID },
    })
    fireEvent.click(screen.getByRole('button', { name: 'List the issues' }))

    expect(await screen.findByText(/The service did not answer this: closed./)).toBeInTheDocument()
  })
})

describe('the record it takes', () => {
  it('sends the record the form filled, with the optional fields as they were left', async () => {
    render(<Harness />)

    fireEvent.change(screen.getByLabelText('Project the record is about'), {
      target: { value: PROJECT_ID },
    })
    fireEvent.change(screen.getByLabelText('Step'), { target: { value: 'draft' } })
    fireEvent.change(screen.getByLabelText('What was seen'), {
      target: { value: 'The count was off by one.' },
    })
    fireEvent.change(screen.getByLabelText('Severity'), { target: { value: 'serious' } })
    fireEvent.change(screen.getByLabelText('Type'), { target: { value: 'function' } })
    fireEvent.change(screen.getByLabelText('Version id, when there is one'), {
      target: { value: 'v1' },
    })
    fireEvent.change(screen.getByLabelText('Duration in seconds, when measured'), {
      target: { value: '4' },
    })
    fireEvent.change(screen.getByLabelText('Who saw it'), { target: { value: 'alice' } })

    fireEvent.click(screen.getByRole('button', { name: 'Record the issue' }))

    await waitFor(() => {
      expect(fake.issueRecords).toBe(1)
    })
    const post = fake.requests.find(
      (request) => request.method === 'POST' && request.url.endsWith('/issues'),
    )
    expect(post?.url).toContain('/issues')
    const body = JSON.parse(post?.body ?? '{}') as Record<string, unknown>
    expect(body.project_id).toBe(PROJECT_ID)
    expect(body.step).toBe('draft')
    expect(body.error_text).toBe('The count was off by one.')
    expect(body.severity).toBe('serious')
    expect(body.category).toBe('function')
    expect(body.version_id).toBe('v1')
    expect(body.duration_seconds).toBe(4)
    expect(body.reported_by).toBe('alice')
    // The fields the trial left empty travel as nulls, and not as strings.
    expect(body.task_id).toBeNull()
    expect(body.feedback_id).toBeNull()
    expect(body.retry_count).toBeNull()
  })

  it('lists again after a record, because the list is the answer', async () => {
    render(<Harness />)
    await listProject()
    const readsBefore = fake.requests.filter((request) => request.url.includes('/issues?')).length

    fireEvent.change(screen.getByLabelText('Project the record is about'), {
      target: { value: PROJECT_ID },
    })
    fireEvent.change(screen.getByLabelText('Step'), { target: { value: 'render' } })
    fireEvent.change(screen.getByLabelText('What was seen'), {
      target: { value: 'The caption lagged one figure.' },
    })
    fireEvent.change(screen.getByLabelText('Who saw it'), { target: { value: 'bob' } })
    fireEvent.click(screen.getByRole('button', { name: 'Record the issue' }))

    await waitFor(() => {
      expect(
        fake.requests.filter((request) => request.url.includes('/issues?')).length,
      ).toBeGreaterThan(readsBefore)
    })
    // The record the service made is on the screen, open and dated.
    expect(await screen.findByText('The caption lagged one figure.')).toBeInTheDocument()
    expect(
      within(issueBlock('The caption lagged one figure.')).getByText('open'),
    ).toBeInTheDocument()
  })

  it('refuses to send a record that names no project, step, error or reporter', async () => {
    render(<Harness />)

    fireEvent.click(screen.getByRole('button', { name: 'Record the issue' }))

    expect(await screen.findByText(/This panel did not send that/)).toBeInTheDocument()
    expect(screen.getByText(/name the project/)).toBeInTheDocument()
    expect(fake.issueRecords).toBe(0)
  })

  it('shows the service’s record refusal, as the service wrote it', async () => {
    fake.refuseIssueRecord = true
    render(<Harness />)

    fireEvent.change(screen.getByLabelText('Project the record is about'), {
      target: { value: PROJECT_ID },
    })
    fireEvent.change(screen.getByLabelText('Step'), { target: { value: 'draft' } })
    fireEvent.change(screen.getByLabelText('What was seen'), { target: { value: 'Anything.' } })
    fireEvent.change(screen.getByLabelText('Who saw it'), { target: { value: 'alice' } })
    fireEvent.click(screen.getByRole('button', { name: 'Record the issue' }))

    expect(await screen.findByText(/The service refused that/)).toBeInTheDocument()
    expect(screen.getByText(/pilot_issue_severity_unknown/)).toBeInTheDocument()
    expect(screen.queryByText(/This panel did not send that/)).toBeNull()
  })
})

describe('the walk it offers', () => {
  it('offers exactly the moves the state machine allows, and no others', async () => {
    render(<Harness />)
    await listProject()

    const open = issueBlock('The method was named after the result it produced.')
    expect(within(open).getByRole('button', { name: 'Mark confirmed' })).toBeInTheDocument()
    expect(within(open).queryByRole('button', { name: 'Mark fixed' })).toBeNull()
    expect(within(open).queryByRole('button', { name: 'Mark wontfix' })).toBeNull()

    const confirmed = issueBlock('The depth was reported without its unit.')
    expect(within(confirmed).getByRole('button', { name: 'Mark fixed' })).toBeInTheDocument()
    expect(within(confirmed).getByRole('button', { name: 'Mark wontfix' })).toBeInTheDocument()
    expect(within(confirmed).queryByRole('button', { name: 'Mark confirmed' })).toBeNull()

    // A closed issue moves nowhere, and the panel says so rather than
    // offering a button the service would refuse.
    const closed = issueBlock('The figure carried no anchor for its own caption.')
    expect(within(closed).queryByRole('button')).toBeNull()
    expect(within(closed).getByText(/this issue is closed/)).toBeInTheDocument()
  })

  it('walks an open issue to confirmed, and reads the list again', async () => {
    render(<Harness />)
    await listProject()
    const open = issueBlock('The method was named after the result it produced.')

    fireEvent.click(within(open).getByRole('button', { name: 'Mark confirmed' }))

    await waitFor(() => {
      expect(fake.issueMoves).toBe(1)
    })
    const post = fake.requests.find((request) => request.url.includes('/status'))
    expect(post?.url).toContain(`/issues/${OPEN_ISSUE_ID}/status`)
    expect(JSON.parse(post?.body ?? '{}')).toEqual({
      project_id: PROJECT_ID,
      status: 'confirmed',
      fix_version: null,
      regression_note: null,
    })

    await waitFor(() => {
      const moved = issueBlock('The method was named after the result it produced.')
      expect(within(moved).getByText('confirmed')).toBeInTheDocument()
    })
  })

  it('walks a confirmed issue to wontfix, which names no version', async () => {
    render(<Harness />)
    await listProject()
    const confirmed = issueBlock('The depth was reported without its unit.')

    fireEvent.click(within(confirmed).getByRole('button', { name: 'Mark wontfix' }))

    await waitFor(() => {
      expect(fake.issueMoves).toBe(1)
    })
    const post = fake.requests.find((request) => request.url.includes('/status'))
    expect(post?.url).toContain(`/issues/${CONFIRMED_ISSUE_ID}/status`)
    expect(JSON.parse(post?.body ?? '{}')).toEqual({
      project_id: PROJECT_ID,
      status: 'wontfix',
      fix_version: null,
      regression_note: null,
    })
  })

  it('asks for the fix version a fixed move must name, and sends it', async () => {
    render(<Harness />)
    await listProject()
    const confirmed = issueBlock('The depth was reported without its unit.')

    fireEvent.click(within(confirmed).getByRole('button', { name: 'Mark fixed' }))

    // The panel refuses before it sends: a fixed issue names the version
    // that fixed it, and a fix without one is a claim the next regression
    // cannot check.
    expect(await screen.findByText(/This panel did not send that/)).toBeInTheDocument()
    expect(screen.getByText(/names the version that fixed it/)).toBeInTheDocument()
    expect(fake.issueMoves).toBe(0)

    fireEvent.change(screen.getByLabelText('Fixed in version'), {
      target: { value: 'v3' },
    })
    fireEvent.click(within(confirmed).getByRole('button', { name: 'Mark fixed' }))

    await waitFor(() => {
      expect(fake.issueMoves).toBe(1)
    })
    const post = fake.requests.find((request) => request.url.includes('/status'))
    expect(JSON.parse(post?.body ?? '{}')).toEqual({
      project_id: PROJECT_ID,
      status: 'fixed',
      fix_version: 'v3',
      regression_note: null,
    })

    // The move is answered and the listing read again; wait for the row the
    // service now serves instead of reading the node the last read drew.
    const fixedText = await screen.findByText('The depth was reported without its unit.')
    const fixed = fixedText.closest('li') as HTMLElement
    expect(within(fixed).getByText('fixed')).toBeInTheDocument()
    expect(within(fixed).getByText('fixed in v3')).toBeInTheDocument()
  })

  it('shows the service’s walk refusal, as the service wrote it', async () => {
    fake.refuseIssueMove = true
    render(<Harness />)
    await listProject()
    const open = issueBlock('The method was named after the result it produced.')

    fireEvent.click(within(open).getByRole('button', { name: 'Mark confirmed' }))

    expect(await screen.findByText(/The service refused that/)).toBeInTheDocument()
    expect(screen.getByText(/pilot_issue_status_move_refused/)).toBeInTheDocument()
    expect(screen.getByText(/The states are walked, not set/)).toBeInTheDocument()
    expect(screen.queryByText(/This panel did not send that/)).toBeNull()
  })
})
