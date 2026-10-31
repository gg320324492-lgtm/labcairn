import { useState } from 'react'
import type { JSX } from 'react'

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { forgetSessionToken } from '../api/session'
import { FakeApi, RULE_ID } from '../test/fakeApi'
import { GuidanceView } from './GuidanceView'

/**
 * The guidance panel, tested against a fake of the local API at the network
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

/** The rule's own block: the row the rule is drawn in. */
async function ruleBlock(statement: string): Promise<HTMLElement> {
  const statement_ = await screen.findByText(statement)
  const block = statement_.closest('li')
  expect(block).not.toBeNull()
  return block as HTMLElement
}

/** Name the person whose word the verdict is. */
async function signAs(who: string): Promise<void> {
  const field = await screen.findByLabelText('Whose word is it')
  fireEvent.change(field, { target: { value: who } })
}

/**
 * The panel, and the workbench's cycle it reads with.
 *
 * **The harness is the workbench's half of the contract**: a verdict asks
 * the workbench to read again, and the workbench's cycle turns with that
 * read. So a verdict the panel settles is on the screen because the cycle
 * turned, and not because the panel patched its own answer.
 */
function Harness(): JSX.Element {
  const [cycle, setCycle] = useState(0)
  return (
    <GuidanceView
      cycle={cycle}
      onChanged={() => {
        setCycle((count) => count + 1)
      }}
    />
  )
}

describe('the rules it draws', () => {
  it('draws each rule with its state, its scope, its proposer and its confirmer', async () => {
    render(<Harness />)

    const block = await ruleBlock('Name the method before its result.')
    expect(drawn(block)).toEqual([
      'Name the method before its result.',
      'candidate',
      'rule rule-method version 1',
      'issue type method',
      'context A result with no method cannot be checked by anybody else.',
      'scope Every claim about a measurement.',
      'example The core was X-rayed before it was sectioned.',
      'proposed by alice at 2026-10-20T09:00:00+00:00',
      'confirmed by nobody at never',
      'sources issue-method',
    ])
  })

  it('draws the rule that stands with the person who settled it', async () => {
    render(<Harness />)

    const block = await ruleBlock('Give the unit with the number.')
    expect(drawn(block)).toContain('confirmed')
    expect(drawn(block)).toContain('proposed by bob at 2026-10-22T08:00:00+00:00')
    expect(drawn(block)).toContain('confirmed by carol at 2026-10-22T09:00:00+00:00')
  })

  it('draws the counterexamples inside the rule that cites them', async () => {
    render(<Harness />)

    // The cases travel with the rule: a reader of the rule's own block sees
    // the case against it, and a reader of another rule's block does not.
    const block = await ruleBlock('Name the method before its result.')
    const counterexample = within(block).getByText(
      'A reading from a published protocol needs no naming.',
    )
    expect(counterexample).toBeInTheDocument()
    expect(drawn(counterexample.closest('li') as HTMLElement)).toEqual([
      'A reading from a published protocol needs no naming.',
      'issue issue-protocol',
      'recorded by bob at 2026-10-21T11:30:00+00:00',
    ])

    // The other rule's case is not in this one.
    expect(within(block).queryByText('A dimensionless ratio needs no unit.')).toBeNull()

    const other = await ruleBlock('Give the unit with the number.')
    expect(within(other).getByText('A dimensionless ratio needs no unit.')).toBeInTheDocument()
    expect(
      within(other).queryByText('A reading from a published protocol needs no naming.'),
    ).toBeNull()

    const without = await ruleBlock('Cite the anchor the claim rests on.')
    expect(
      within(without).getByText('the memory holds no case against this rule'),
    ).toBeInTheDocument()
  })
})

describe('the door it offers', () => {
  it('sends the verdict the caller chose, with the person who signed it', async () => {
    render(<Harness />)
    const block = await ruleBlock('Name the method before its result.')
    await signAs('carol')

    fireEvent.click(within(block).getByRole('button', { name: 'Confirm' }))

    await waitFor(() => {
      expect(fake.ruleConfirmations).toBe(1)
    })
    const post = fake.requests.find((request) => request.method === 'POST')
    expect(post?.url).toContain(`/guidance/rules/${RULE_ID}/confirm`)
    expect(JSON.parse(post?.body ?? '{}')).toEqual({ verdict: 'confirmed', user_id: 'carol' })
  })

  it('sends the reason with a dispute, and only with a dispute', async () => {
    render(<Harness />)
    const block = await ruleBlock('Name the method before its result.')
    await signAs('carol')
    const reason = screen.getByLabelText('The reason, for a dispute')
    fireEvent.change(reason, { target: { value: 'the rule does not hold for readings' } })

    fireEvent.click(within(block).getByRole('button', { name: 'Dispute' }))

    await waitFor(() => {
      expect(fake.ruleConfirmations).toBe(1)
    })
    const post = fake.requests.find((request) => request.method === 'POST')
    expect(JSON.parse(post?.body ?? '{}')).toEqual({
      verdict: 'disputed',
      user_id: 'carol',
      reason: 'the rule does not hold for readings',
    })
  })

  it('reads the rules again after a verdict, because the list is the answer', async () => {
    render(<Harness />)
    const block = await ruleBlock('Name the method before its result.')
    await signAs('carol')
    const readsBefore = fake.requestsTo('/guidance/rules').length

    fireEvent.click(within(block).getByRole('button', { name: 'Confirm' }))

    await waitFor(() => {
      expect(fake.requestsTo('/guidance/rules').length).toBeGreaterThan(readsBefore)
    })
    // The rule the service settled is the rule the panel draws.
    const settled = await ruleBlock('Name the method before its result.')
    expect(drawn(settled)).toContain('confirmed')
  })
})

describe('the workbench cycle', () => {
  it('reads again when the workbench reads again', async () => {
    // A rule settled elsewhere must be on the screen when the page
    // refreshes, and not only after a reload.
    const view = render(<GuidanceView cycle={0} onChanged={() => {}} />)
    await screen.findByText('Name the method before its result.')
    const readsBefore = fake.requestsTo('/guidance/rules').length

    view.rerender(<GuidanceView cycle={1} onChanged={() => {}} />)

    await waitFor(() => {
      expect(fake.requestsTo('/guidance/rules').length).toBeGreaterThan(readsBefore)
    })
  })

  it('asks the workbench to read again after a verdict, and reads with it', async () => {
    // The panel does not patch its own answer: a verdict asks the workbench
    // to read again, and the cycle turns with that read.
    const view = render(<Harness />)
    const block = await ruleBlock('Name the method before its result.')
    await signAs('carol')
    const readsBefore = fake.requestsTo('/guidance/rules').length

    fireEvent.click(within(block).getByRole('button', { name: 'Confirm' }))

    await waitFor(() => {
      expect(fake.requestsTo('/guidance/rules').length).toBeGreaterThan(readsBefore)
    })
    const settled = await ruleBlock('Name the method before its result.')
    expect(drawn(settled)).toContain('confirmed')
    view.unmount()
  })
})

describe('the three refusals, kept apart', () => {
  it('refuses an empty name itself, and sends nothing', async () => {
    render(<Harness />)
    const block = await ruleBlock('Name the method before its result.')

    fireEvent.click(within(block).getByRole('button', { name: 'Confirm' }))

    expect(await screen.findByText(/This panel did not send that/)).toBeInTheDocument()
    expect(screen.getByText(/name the person whose word it is/)).toBeInTheDocument()
    // Nothing was asked, so nothing was refused by the service.
    expect(fake.ruleConfirmations).toBe(0)
    expect(screen.queryByText(/The service refused that/)).toBeNull()
  })

  it('refuses a dispute with no reason itself, and sends nothing', async () => {
    render(<Harness />)
    const block = await ruleBlock('Name the method before its result.')
    await signAs('carol')

    fireEvent.click(within(block).getByRole('button', { name: 'Dispute' }))

    expect(await screen.findByText(/This panel did not send that/)).toBeInTheDocument()
    expect(screen.getByText(/a dispute needs its reason/)).toBeInTheDocument()
    expect(fake.ruleConfirmations).toBe(0)
  })

  it('shows the service refusal with the reason and the message the service wrote', async () => {
    render(<Harness />)
    const block = await ruleBlock('Name the method before its result.')
    // The proposer cannot be the second reader: the memory refuses that by
    // name, and the panel shows the refusal as it is.
    await signAs('alice')

    fireEvent.click(within(block).getByRole('button', { name: 'Confirm' }))

    expect(await screen.findByText(/The service refused that/)).toBeInTheDocument()
    expect(screen.getByText(/guidance_confirmer_is_proposer/)).toBeInTheDocument()
    expect(screen.getByText(/one person reading twice/)).toBeInTheDocument()
    // And it is not the panel's own refusal.
    expect(screen.queryByText(/This panel did not send that/)).toBeNull()
  })

  it('shows the route own refusal in the layer vocabulary', async () => {
    fake.refuseWithArguments = true
    render(<Harness />)
    const block = await ruleBlock('Name the method before its result.')
    await signAs('carol')

    fireEvent.click(within(block).getByRole('button', { name: 'Confirm' }))

    expect(await screen.findByText(/The service refused that/)).toBeInTheDocument()
    expect(screen.getByText(/arguments_invalid/)).toBeInTheDocument()
    expect(screen.queryByText(/This panel did not send that/)).toBeNull()
  })

  it('shows the schema answer in the schema vocabulary, and not as a refusal', async () => {
    fake.refuseWithSchema = true
    render(<Harness />)
    const block = await ruleBlock('Name the method before its result.')
    await signAs('carol')

    fireEvent.click(within(block).getByRole('button', { name: 'Confirm' }))

    expect(await screen.findByText(/The service did not accept the body/)).toBeInTheDocument()
    // The status, and the schema own words about which part of the body it
    // would not accept.
    expect(screen.getByText(/422/)).toBeInTheDocument()
    expect(screen.getByText(/Input should be/)).toBeInTheDocument()
    // A schema answer carries no reason, and the panel invents none.
    expect(screen.queryByText(/arguments_invalid/)).toBeNull()
    expect(screen.queryByText(/The service refused that/)).toBeNull()
  })
})
