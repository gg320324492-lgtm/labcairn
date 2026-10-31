import { render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { forgetSessionToken } from '../api/session'
import { FakeApi } from '../test/fakeApi'
import { ProposalsView } from './ProposalsView'

/**
 * The proposals panel, tested against a fake of the local API at the network
 * boundary.
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

describe('the model and the person', () => {
  it('draws them beside each other, each labelled with whose words it is', async () => {
    render(<ProposalsView />)

    const model = await screen.findByText('the model\u2019s answer')
    const person = await screen.findByText('the person\u2019s verdict')
    // Side by side: the same pair, drawn in the same place.
    expect(model.closest('li')?.parentElement).toBe(person.closest('li')?.parentElement)
    // And distinguishable: the labels are not the same, and neither are the
    // creators the contract records.
    expect(model.textContent).not.toBe(person.textContent)
    expect(drawn(model.closest('li') as HTMLElement)).toContain('model_proposal')
    expect(drawn(person.closest('li') as HTMLElement)).toContain('user')
  })

  it('says which one a report may cite', async () => {
    render(<ProposalsView />)

    const model = await screen.findByText('the model\u2019s answer')
    const person = await screen.findByText('the person\u2019s verdict')
    expect(
      within(model.closest('li') as HTMLElement).getByText(/a report may not cite this one/),
    ).toBeInTheDocument()
    expect(
      within(person.closest('li') as HTMLElement).getByText(/a report may cite this one/),
    ).toBeInTheDocument()
  })

  it('pairs the proposal with the record that superseded it, and no other', async () => {
    render(<ProposalsView />)

    const model = await screen.findByText('the model\u2019s answer')
    const person = await screen.findByText('the person\u2019s verdict')
    // The pair is the proposal's own link, not a pairing by text or order.
    expect(drawn(model.closest('li') as HTMLElement)).toContain('superseded by rec-person')
    expect(drawn(person.closest('li') as HTMLElement)).toContain('record rec-person')
  })

  it('says so when nothing supersedes the proposal', async () => {
    fake.state.records = fake.state.records.map((record) =>
      record.evidence_id === 'rec-model' ? { ...record, superseded_by: null } : record,
    )
    render(<ProposalsView />)

    expect(await screen.findByText(/No record supersedes this proposal/)).toBeInTheDocument()
  })

  it('draws a record that is not a proposal under its own heading', async () => {
    render(<ProposalsView />)

    expect(await screen.findByText('Records that are not proposals')).toBeInTheDocument()
    // The rule's own record is neither a proposal nor a person's word
    // beside one, so it is drawn as a record of its own.
    expect(await screen.findByText('the rule\u2019s record')).toBeInTheDocument()
  })
})

describe('what it draws of each record', () => {
  it('draws the fields the contract carries, and no others', async () => {
    render(<ProposalsView />)

    const model = await screen.findByText('the model\u2019s answer')
    expect(drawn(model.closest('li') as HTMLElement)).toEqual([
      'the model\u2019s answer',
      'model_proposal',
      'written by model-1',
      'status extracted',
      'kind claim',
      'record rec-model',
      'text The core records 4.2 mm of silt.',
      'anchors anchor-core-1',
      'span 4.2 mm of silt',
      'created at 2026-10-25T09:00:00+00:00',
      'superseded by rec-person',
      'a report may not cite this one: the words are a model\u2019s',
    ])
  })

  it('draws the person own record with the settlement on it', async () => {
    render(<ProposalsView />)

    const person = await screen.findByText('the person\u2019s verdict')
    expect(drawn(person.closest('li') as HTMLElement)).toEqual([
      'the person\u2019s verdict',
      'user',
      'written by alice',
      'status user_attested',
      'kind claim',
      'record rec-person',
      'text The core records 4.2 mm of silt.',
      'anchors anchor-core-1',
      'span 4.2 mm of silt',
      'created at 2026-10-25T09:30:00+00:00',
      'a report may cite this one: the words are a person\u2019s',
    ])
  })

  it('draws the verification log the ledger recorded', async () => {
    render(<ProposalsView />)

    const entry = await screen.findByText('c4')
    expect(drawn(entry.closest('li') as HTMLElement)).toEqual([
      'c4',
      'not_checked',
      'by alice at 2026-10-25T10:00:00+00:00',
      'confirmed. I read the core log.',
    ])
  })

  it('draws no record the ledger did not hold', async () => {
    render(<ProposalsView />)

    await screen.findByText('the model\u2019s answer')
    const panel = (await screen.findByRole('heading', { name: 'Proposals' })).closest('section')
    // The ledger held three records, and the panel drew three.
    expect(within(panel as HTMLElement).getAllByText(/^record rec-/)).toHaveLength(3)
  })
})
