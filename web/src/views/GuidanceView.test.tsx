import { useState } from 'react'
import type { JSX } from 'react'

import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { forgetSessionToken } from '../api/session'
import { FakeApi, RULE_ID, urlOf } from '../test/fakeApi'
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
  // The statement may appear twice — the memory's list and the retrieval's
  // are two lists, and a rule can stand in both — so the row is the one in
  // the memory's list, where the verdict is offered: the artefact row.
  const statements = await screen.findAllByText(statement)
  expect(statements.length).toBeGreaterThan(0)
  const block = statements
    .map((found) => found.closest('li'))
    .find((row) => row !== null && row.classList.contains('record--artefact'))
  expect(block).not.toBeUndefined()
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
      'shared private',
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

describe('the usable rules it draws', () => {
  it('asks the retrieval for the usable rules, once, without a scope', async () => {
    render(<Harness />)

    await screen.findByLabelText('Usable rules')

    const usableReads = fake.requestsTo('/guidance/usable')
    expect(usableReads).toHaveLength(1)
    // The path is the service's own, and the read carries no scope: the
    // panel asks for everything the retrieval holds.
    expect(usableReads[0]?.url).toBe('/api/guidance/usable')
  })

  it('draws each usable rule with its name, its summary, its scope and its sources', async () => {
    render(<Harness />)

    // The retrieval's answer is its own list, and the block is the rule's
    // own: the name, what the rule says, the scope it answers for, and the
    // sources the chain resolved it to.
    const block = await screen.findByLabelText('Usable rules')
    expect(within(block).getByText('Give the unit with the number.')).toBeInTheDocument()
    expect(
      within(block).getByText('A number without a unit is not a quantity.'),
    ).toBeInTheDocument()
    expect(within(block).getByText('scope Every numeric claim.')).toBeInTheDocument()
    expect(within(block).getByText('rule rule-units version 2')).toBeInTheDocument()
    expect(within(block).getByText('sources issue-units')).toBeInTheDocument()

    expect(within(block).getByText('Cite the anchor the claim rests on.')).toBeInTheDocument()
    expect(within(block).getByText('sources issue-anchors, issue-method')).toBeInTheDocument()
  })

  it('draws the retrieval’s answer, not the memory’s: the withdrawn rule is not here', async () => {
    render(<Harness />)

    const block = await screen.findByLabelText('Usable rules')
    // The memory holds rule-method as a candidate, and the retrieval answers
    // with confirmed rules only: the two lists are not the same list.
    expect(within(block).queryByText('Name the method before its result.')).toBeNull()
    expect(within(block).getAllByRole('listitem')).toHaveLength(2)
  })

  it('says when no rule may be cited, and that the memory still holds rules', async () => {
    fake.state.guidanceUsable = []
    render(<Harness />)

    const block = await screen.findByLabelText('Usable rules')
    expect(
      within(block).getByText(
        'No rule may be cited yet: the memory holds rules, but none is confirmed and standing.',
      ),
    ).toBeInTheDocument()
    // The empty answer is the retrieval's, not the memory's: the rules
    // panel above still draws what the memory holds.
    expect(await screen.findByText('Name the method before its result.')).toBeInTheDocument()
  })

  it('shows the retrieval’s failure without taking the rules list down', async () => {
    // The read fails on the second question: the first answer landed, and
    // the failure is the retrieval's own, on the cycle that follows.
    const realFetch = fake.fetch
    let usableReads = 0
    vi.stubGlobal(
      'fetch',
      async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
        const url = urlOf(input)
        if (url.includes('/guidance/usable')) {
          usableReads += 1
          if (usableReads > 1) {
            return new Response(
              JSON.stringify({ reason: 'usable_unavailable', message: 'the index is closed.' }),
              { status: 503, headers: { 'Content-Type': 'application/json' } },
            )
          }
        }
        return realFetch(input, init)
      },
    )
    const view = render(<GuidanceView cycle={0} onChanged={() => {}} />)
    await screen.findByText('Name the method before its result.')

    view.rerender(<GuidanceView cycle={1} onChanged={() => {}} />)

    expect(await screen.findByText(/the index is closed/)).toBeInTheDocument()
    // The rules list is the memory's answer, and it stands beside the
    // retrieval's failure.
    expect(screen.getByText('Name the method before its result.')).toBeInTheDocument()
  })
})

describe('the sharing it draws', () => {
  it('draws each rule with its sharing scope, and the publisher when it is shared', async () => {
    render(<Harness />)

    // The unshared candidate says it is private; the withdrawn rule keeps
    // the record of the sharing it once had.
    const candidate = await ruleBlock('Name the method before its result.')
    expect(drawn(candidate)).toContain('shared private')

    const shared = await ruleBlock('Cite the anchor the claim rests on.')
    expect(drawn(shared)).toContain('shared group by dave at 2026-10-19T12:00:00+00:00')
  })

  it('offers Publish on a confirmed, unshared rule, and on no other', async () => {
    render(<Harness />)

    // The confirmed rule is the only one a mentor may publish: a candidate
    // is unreviewed experience, and a withdrawn rule is not standing.
    const confirmed = await ruleBlock('Give the unit with the number.')
    expect(within(confirmed).getByRole('button', { name: 'Publish' })).toBeInTheDocument()

    const candidate = await ruleBlock('Name the method before its result.')
    expect(within(candidate).queryByRole('button', { name: 'Publish' })).toBeNull()

    const withdrawn = await ruleBlock('Cite the anchor the claim rests on.')
    expect(within(withdrawn).queryByRole('button', { name: 'Publish' })).toBeNull()
    // The withdrawn rule is shared, so the retraction is offered instead.
    expect(within(withdrawn).getByRole('button', { name: 'Retract' })).toBeInTheDocument()
  })

  it('sends the publication to the rule’s own publish path, with the signed mentor', async () => {
    render(<Harness />)
    const block = await ruleBlock('Give the unit with the number.')
    await signAs('dave')

    fireEvent.click(within(block).getByRole('button', { name: 'Publish' }))

    await waitFor(() => {
      expect(fake.rulePublications).toBe(1)
    })
    const post = fake.requests.find(
      (request) => request.method === 'POST' && request.url.includes('/publish'),
    )
    expect(post?.url).toContain(`/guidance/rules/rule-units/publish`)
    expect(JSON.parse(post?.body ?? '{}')).toEqual({ user_id: 'dave' })
  })

  it('reads the rules again after a publication, because the list is the answer', async () => {
    render(<Harness />)
    const block = await ruleBlock('Give the unit with the number.')
    await signAs('dave')
    const readsBefore = fake.requestsTo('/guidance/rules').length

    fireEvent.click(within(block).getByRole('button', { name: 'Publish' }))

    await waitFor(() => {
      expect(fake.requestsTo('/guidance/rules').length).toBeGreaterThan(readsBefore)
    })
    // The rule the service shared is the rule the panel draws, with the
    // publication's own two facts beside it.
    const shared = await ruleBlock('Give the unit with the number.')
    expect(drawn(shared)).toContain('shared group by dave at 2026-11-24T09:00:00+00:00')
  })

  it('refuses a publication nobody signs, and sends nothing', async () => {
    render(<Harness />)
    const block = await ruleBlock('Give the unit with the number.')

    fireEvent.click(within(block).getByRole('button', { name: 'Publish' }))

    expect(await screen.findByText(/This panel did not send that/)).toBeInTheDocument()
    expect(screen.getByText(/name the mentor whose word the publication is/)).toBeInTheDocument()
    expect(fake.rulePublications).toBe(0)
    expect(screen.queryByText(/The service refused that/)).toBeNull()
  })

  it('shows the service’s publication refusal, as the service wrote it', async () => {
    fake.refuseRulePublish = true
    render(<Harness />)
    const block = await ruleBlock('Give the unit with the number.')
    await signAs('dave')

    fireEvent.click(within(block).getByRole('button', { name: 'Publish' }))

    expect(await screen.findByText(/The service refused that/)).toBeInTheDocument()
    expect(screen.getByText(/guidance_publish_not_confirmed/)).toBeInTheDocument()
    expect(screen.getByText(/only a confirmed rule is published/)).toBeInTheDocument()
    expect(screen.queryByText(/This panel did not send that/)).toBeNull()
  })

  it('sends the retraction, and reads the list again with the scope it answered', async () => {
    render(<Harness />)
    const block = await ruleBlock('Cite the anchor the claim rests on.')

    fireEvent.click(within(block).getByRole('button', { name: 'Retract' }))

    await waitFor(() => {
      expect(fake.ruleRetractions).toBe(1)
    })
    const post = fake.requests.find(
      (request) => request.method === 'POST' && request.url.includes('/retract'),
    )
    expect(post?.url).toContain(`/guidance/rules/rule-anchors/retract`)

    const retracted = await ruleBlock('Cite the anchor the claim rests on.')
    expect(drawn(retracted)).toContain('shared private')
  })

  it('shows the service’s retraction refusal, as the service wrote it', async () => {
    fake.refuseRuleRetract = true
    render(<Harness />)
    const block = await ruleBlock('Cite the anchor the claim rests on.')

    fireEvent.click(within(block).getByRole('button', { name: 'Retract' }))

    expect(await screen.findByText(/The service refused that/)).toBeInTheDocument()
    expect(screen.getByText(/guidance_transition_not_possible/)).toBeInTheDocument()
    expect(screen.getByText(/no sharing to retract/)).toBeInTheDocument()
  })
})
