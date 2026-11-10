import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { forgetSessionToken } from '../api/session'
import { FakeApi, TASK_ID } from '../test/fakeApi'
import type { ArtifactView } from '../api/generated'
import { ReviewView } from './ReviewView'

/**
 * The binding-review panel, tested against a fake of the local API at the
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

/** The binding's producer id — the manifest is the row that carries it. */
const BINDING_PRODUCER = 'labcairn.papers.binding'

/** The dossier manifest's JSON, as the binding wrote it. */
function dossierJson(): string {
  return JSON.stringify({
    task_id: TASK_ID,
    project_id: 'proj-1',
    input_version_id: 'ver-1',
    output_version_id: 'ver-2',
    marked_receipt_id: 'mark-1',
    clean_receipt_id: 'clean-1',
    edge_id: 'edge-1',
    opinions: [
      {
        feedback_id: 'fb-one',
        location_state: 'located',
        anchor_status: 'resolved',
        anchor_paragraph: 1,
      },
      {
        feedback_id: 'fb-two',
        location_state: 'uncertain_location',
        anchor_status: 'unknown',
        anchor_paragraph: null,
      },
    ],
    suggestions: [],
    decisions: [
      {
        feedback_id: 'fb-one',
        verdict: 'accepted',
        operator: 'Dr. Chen',
        needs_evidence: false,
      },
    ],
    responses: [],
    unresolved: [
      {
        feedback_id: 'fb-two',
        reason: 'uncertain_location',
        detail: 'the comment names no passage',
      },
    ],
    handovers: [],
    closed_at: '2026-02-01T00:00:00+00:00',
  })
}

/** One dossier receipt, produced by the binding. */
function dossierReceipt(): ArtifactView {
  return {
    receipt: {
      receipt_id: '0193f0a1-0000-7000-8000-0000000000d1',
      task_id: TASK_ID,
      kind: 'manifest',
      relative_path: 'revisions/mark-1/binding-dossier.json',
      content_sha256: 'd'.repeat(64),
      size_bytes: 2048,
      revision: 1,
      produced_by: 'stage',
      producer_id: BINDING_PRODUCER,
      staleness: 'current',
      media_type: 'application/json',
      created_at: '2026-02-01T00:00:00+00:00',
    },
    resource_key: 'revisions/mark-1/binding-dossier.json',
  }
}

describe('the binding-review panel', () => {
  it('draws nothing when no binding has closed', () => {
    const { container } = render(<ReviewView artifacts={fake.state.artifacts} cycle={0} />)
    expect(container.textContent).toBe('')
  })

  it('draws every opinion the manifest carries, and names the binding', async () => {
    fake.state.artifacts = [dossierReceipt()]
    fake.state.artefactContent = dossierJson()

    render(<ReviewView artifacts={fake.state.artifacts} cycle={0} />)

    const heading = await screen.findByText('fb-one')
    expect(heading).toBeDefined()
    expect(screen.getByText('fb-two')).toBeDefined()
    expect(screen.getByText(/input ver-1 → output ver-2/)).toBeDefined()
    // The manifest's bytes were asked for through the content route.
    expect(fake.artefactContentReads).toBeGreaterThan(0)
  })

  it('draws an opinion with no verdict as not reviewed', async () => {
    fake.state.artifacts = [dossierReceipt()]
    fake.state.artefactContent = dossierJson()

    render(<ReviewView artifacts={fake.state.artifacts} cycle={0} />)

    const row = (await screen.findByText('fb-two')).closest('li')
    expect(row?.textContent).toContain('not reviewed')
  })

  it('names the unresolved task beside the opinion that owes it', async () => {
    fake.state.artifacts = [dossierReceipt()]
    fake.state.artefactContent = dossierJson()

    render(<ReviewView artifacts={fake.state.artifacts} cycle={0} />)

    const row = (await screen.findByText('fb-two')).closest('li')
    expect(row?.textContent).toContain('uncertain_location')
    expect(row?.textContent).toContain('the comment names no passage')
  })

  it('says the service failed rather than inventing a manifest view', async () => {
    fake.state.artifacts = [dossierReceipt()]
    // The content route answers bytes that are not JSON: the client's own
    // read fails, and the frame's error state is what the panel draws — the
    // panel never invents a manifest the service did not serve.
    fake.state.artefactContent = '<html>not a manifest</html>'

    render(<ReviewView artifacts={fake.state.artifacts} cycle={0} />)

    const notice = await screen.findByText(/The service did not answer this/)
    expect(notice).toBeDefined()
  })
})
