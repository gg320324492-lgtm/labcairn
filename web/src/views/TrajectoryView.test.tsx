import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { forgetSessionToken } from '../api/session'
import { FakeApi, ISSUE_KEY, PROJECT_ID } from '../test/fakeApi'
import { TrajectoryView } from './TrajectoryView'

/**
 * The trajectory panel, tested against a fake of the local API at the
 * network boundary.
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

/**
 * The text of each span a row drew.
 *
 * **The rows are what the panel drew, so the rows are what is checked.** A
 * panel that added a field the contract does not carry would add a span
 * here, and the list would no longer be the one the contract produced.
 */
function drawn(node: HTMLElement): string[] {
  return Array.from(node.children)
    .filter((child): child is HTMLSpanElement => child.tagName === 'SPAN')
    .map((span) => span.textContent ?? '')
}

/** The row a text sits in. */
function rowOf(text: Element): HTMLElement {
  const row = text.closest('li')
  expect(row).not.toBeNull()
  return row as HTMLElement
}

/** Name an issue and a project, and ask for the trajectory. */
async function nameTheIssue(issue = ISSUE_KEY, project = PROJECT_ID): Promise<void> {
  const issueField = await screen.findByLabelText('Issue key')
  fireEvent.change(issueField, { target: { value: issue } })
  const projectField = screen.getByLabelText('Project id')
  fireEvent.change(projectField, { target: { value: project } })
  fireEvent.click(screen.getByRole('button', { name: 'Draw the trajectory' }))
}

describe('the panel that cannot list what there is to look at', () => {
  it('says so, because a gap that is written down is a decision', async () => {
    render(<TrajectoryView />)

    // The service has no outlet that lists the chain's issue keys, so the
    // panel can only draw an issue the caller names. A reader who found the
    // omission and no note about it would assume it had been forgotten.
    expect(await screen.findByText(/no outlet that lists the chain/i)).toBeInTheDocument()
  })

  it('asks for nothing until an issue is named', async () => {
    render(<TrajectoryView />)

    expect(await screen.findByText(/No issue has been named/)).toBeInTheDocument()
    expect(fake.requests.filter((request) => request.url.includes('/trajectory'))).toHaveLength(0)
  })

  it('asks the service for the issue the caller named', async () => {
    render(<TrajectoryView />)
    await nameTheIssue()

    await waitFor(() => {
      expect(fake.requestsTo(`/trajectory?issue_key=${ISSUE_KEY}`)).toHaveLength(1)
    })
  })
})

describe('the trajectory it draws', () => {
  it('draws the comment, its anchor, its version and its states', async () => {
    render(<TrajectoryView />)
    await nameTheIssue()

    const comment = await screen.findByText('Name the method before its result.')
    expect(drawn(rowOf(comment))).toEqual([
      'Name the method before its result.',
      'comment fb-method',
      'issue issue-method',
      'version v1',
      'anchor: the method was not named',
      'states: addressed',
    ])
  })

  it('draws the edits that answered the comment, with their own fields', async () => {
    render(<TrajectoryView />)
    await nameTheIssue()

    const edit = await screen.findByText('student')
    expect(drawn(rowOf(edit))).toEqual([
      'student',
      'grade observed',
      'edge edge-1',
      'edit edit-method',
    ])
  })

  it('draws a comment no edit answers, as one no edit answers', async () => {
    render(<TrajectoryView />)
    await nameTheIssue()

    const comment = await screen.findByText('Say which core the depth came from.')
    expect(drawn(rowOf(comment))).toContain('no edit answers this comment')
  })

  it('draws a change that answers no comment when the contract carries one', async () => {
    // The service reads its changes by the comments it read, so it cannot
    // send one that answers no comment. The contract says the field may be
    // null, so the panel's handling of it is watched rather than assumed.
    fake.serveLooseEdits = true
    render(<TrajectoryView />)
    await nameTheIssue()

    expect(await screen.findByText('Changes the answer ties to no comment')).toBeInTheDocument()
    expect(screen.getByText('advisor')).toBeInTheDocument()
  })
})

describe('the versions it draws', () => {
  it('asks the project graph about the versions the comments name', async () => {
    render(<TrajectoryView />)
    await nameTheIssue()

    await waitFor(() => {
      const asked = fake.requests.filter((request) => request.url.includes('/trajectory/graph'))
      expect(asked).toHaveLength(1)
      expect(asked[0]?.url).toContain(`project_id=${PROJECT_ID}`)
      expect(asked[0]?.url).toContain('version_id=v1')
      expect(asked[0]?.url).toContain('version_id=v2')
    })
  })

  it('does not present the versions as a chronology', async () => {
    // The contract carries the versions as a frozenset, so the array has no
    // stable order. Two answers that differ only in that order must draw the
    // same panel: a panel that read an order out of the array would be
    // drawing a chronology the contract does not carry.
    const first = await versionsDrawn(['v1', 'v2'])
    const second = await versionsDrawn(['v2', 'v1'])

    expect(first).toEqual(second)
  })

  it('says the versions are a set and the edges are the only order', async () => {
    render(<TrajectoryView />)
    await nameTheIssue()

    const panel = (await screen.findByRole('heading', { name: 'Version graph' })).closest('section')
    expect(panel).not.toBeNull()
    expect(await within(panel as HTMLElement).findByText(/as a set/)).toBeInTheDocument()
  })

  it('draws the accepted edges as the pairs the contract carries', async () => {
    render(<TrajectoryView />)
    await nameTheIssue()

    const edge = await screen.findByText('v1 \u2192 v2')
    expect(drawn(rowOf(edge))).toEqual(['v1 \u2192 v2', 'edge edge-1'])
  })
})

describe('what it does not draw', () => {
  it('draws no time, because no row of the chain carries one', async () => {
    render(<TrajectoryView />)
    await nameTheIssue()
    await screen.findByText('Name the method before its result.')

    const panel = (await screen.findByRole('heading', { name: 'Trajectory' })).closest('section')
    const drawnText = (panel as HTMLElement).textContent ?? ''
    // A date on this panel would be a fact the contract does not carry.
    expect(drawnText).not.toMatch(/\d{4}-\d{2}-\d{2}/)
  })

  it('draws no record the contract did not carry', async () => {
    render(<TrajectoryView />)
    await nameTheIssue()
    await screen.findByText('Name the method before its result.')

    const panel = (await screen.findByRole('heading', { name: 'Trajectory' })).closest('section')
    const comments = within(panel as HTMLElement).getAllByText(/comment fb-/)
    // The contract carried two comments and two changes that answer them.
    expect(comments).toHaveLength(2)
    expect(within(panel as HTMLElement).getAllByText(/^edit edit-/)).toHaveLength(2)
  })
})

/** The text the version panel draws, for one order of the contract's array. */
async function versionsDrawn(versionIds: string[]): Promise<string> {
  fake.state.trajectoryGraph = {
    version_ids: versionIds,
    edges: [{ edge_id: 'edge-1', parent_version_id: 'v1', child_version_id: 'v2' }],
  }
  const view = render(<TrajectoryView />)
  await nameTheIssue()
  // The answer, not the panel's pending state: two reads that differ only
  // in the order of the array must draw the same thing.
  await screen.findByText('version v1')
  const heading = await screen.findByRole('heading', { name: 'Version graph' })
  const panel = heading.closest('section')
  const text = panel?.textContent ?? ''
  view.unmount()
  return text
}
