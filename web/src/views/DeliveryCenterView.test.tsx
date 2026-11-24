import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { QUALITY_REPORT_FIXTURE } from '../test/fakeApi'
import { DeliveryCenterView } from './DeliveryCenterView'
import { fixtureDeliverablesExport, fixturePreview } from './deliveryFixture'

/**
 * The delivery centre, driven through the network boundary.
 *
 * **What is checked here is the centre's own behaviour, and each property is
 * checked by exercising it**: the preview renders its counts and changes
 * before anything can be applied; the apply button stands down until the
 * preview has landed; a commit re-reads the round and names the binding; the
 * four deliverables draw with their digests, and an export click decodes the
 * wire's bytes and hands them to the browser. The fixture note is part of the
 * surface: a reader must be able to tell the centre's data from the
 * service's answer.
 */

let previewAnswer: unknown = fixturePreview
let deliverablesAnswer: unknown = fixtureDeliverablesExport
let qualityAnswer: unknown = QUALITY_REPORT_FIXTURE
let previewStatus = 200
let applyStatus = 200
let qualityStatus = 200
let cancelStatus = 200
let cancelAnswer: unknown = {
  project_id: 'proj-lc-p4-cap',
  reason: 'cancelled from the delivery centre',
  accepted: true,
}
/**
 * Hold the apply answer until the test releases it.
 *
 * **The cancel window is the point.** The Cancel button exists only while
 * the apply is running, and a fetch that resolves in a microtask closes
 * that window before the test can look at it. Holding the apply open is how
 * the test stands inside the window — the state the button is for — instead
 * of beside it.
 */
let holdApply = false
let releaseApply: (() => void) | null = null
/** The refusal body a non-200 apply answers with; unset means the plain one. */
let applyRefusalBody: { reason: string; message: string } | null = null

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

function applyResultBody(): unknown {
  // **A refused apply answers in the refusal's own shape.** The service's
  // 403 carries the two fields every refusal carries; the cancellation test
  // names the `apply_cancelled` reason the centre branches on, and the plain
  // refusal test keeps the no-decisions refusal the round really answers
  // with when nothing was reviewed.
  if (applyStatus !== 200) {
    return (
      applyRefusalBody ?? {
        reason: 'arguments_invalid',
        message: 'no review decision stands for this round.',
      }
    )
  }
  return {
    project_id: 'proj-lc-p4-cap',
    input_version_id: 'ver-baseline-04',
    output_version_id: 'ver-applied-05',
    edge_id: 'edge-1',
    marked_receipt_id: 'receipt-marked',
    marked_sha256: 'a'.repeat(64),
    clean_receipt_id: 'receipt-clean',
    clean_sha256: 'b'.repeat(64),
    dossier_artifact_id: 'dossier-1',
    applied: ['fb-1'],
    handovers: [],
    unresolved: [],
  }
}

beforeEach(() => {
  previewAnswer = fixturePreview
  deliverablesAnswer = fixtureDeliverablesExport
  qualityAnswer = QUALITY_REPORT_FIXTURE
  previewStatus = 200
  applyStatus = 200
  qualityStatus = 200
  cancelStatus = 200
  cancelAnswer = {
    project_id: 'proj-lc-p4-cap',
    reason: 'cancelled from the delivery centre',
    accepted: true,
  }
  holdApply = false
  releaseApply = null
  applyRefusalBody = null
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
      await Promise.resolve()
      const url = (
        typeof input === 'string' ? input : input instanceof URL ? input.href : input.url
      ).replace(/^\/api/, '')
      if (url.startsWith('/review/preview')) {
        return jsonResponse(previewStatus, previewAnswer)
      }
      if (url.startsWith('/review/deliverables')) {
        return jsonResponse(200, deliverablesAnswer)
      }
      if (url.startsWith('/review/quality')) {
        return jsonResponse(qualityStatus, qualityAnswer)
      }
      if (url === '/review/apply/cancel') {
        return jsonResponse(cancelStatus, cancelAnswer)
      }
      if (url.startsWith('/review/apply')) {
        if (holdApply) {
          return new Promise<Response>((resolve) => {
            releaseApply = () => resolve(jsonResponse(applyStatus, applyResultBody()))
          })
        }
        return jsonResponse(applyStatus, applyResultBody())
      }
      // The session read the POST boundary asks for before a change.
      if (url === '/session') {
        return jsonResponse(200, { token: 'test-token', path: '/tmp/token' })
      }
      throw new Error(`unexpected request: ${String(init?.method ?? 'GET')} ${url}`)
    }),
  )
})

afterEach(() => {
  vi.unstubAllGlobals()
})

/** Commit the round, the way the desk's operator does. */
async function applyTheRound(): Promise<void> {
  await screen.findByRole('region', { name: 'Apply preview' })
  fireEvent.click(screen.getByRole('button', { name: 'Apply the approved set' }))
  await screen.findByText(/bound by dossier/)
}

describe('the delivery centre', () => {
  it('draws the preview first: counts, affected paragraphs, edits and digests', async () => {
    render(<DeliveryCenterView />)

    const preview = await screen.findByRole('region', { name: 'Apply preview' })
    expect(preview.getAttribute('data-applied')).toBe('3')
    expect(preview.getAttribute('data-pending')).toBe('1')
    expect(preview.getAttribute('data-rejected')).toBe('1')
    expect(screen.getByText(/Affected paragraphs: ¶2, ¶4, ¶7/)).toBeInTheDocument()
    // The two texts of one change stand side by side, never merged.
    expect(screen.getByText(/varve counting across the entire/)).toBeInTheDocument()
    expect(screen.getByText(/the 1823–1826 interval is interpolated/)).toBeInTheDocument()
    // The digests the committed apply will publish are named up front.
    expect(screen.getByText(`${fixturePreview.marked_sha256.slice(0, 16)}…`)).toBeInTheDocument()
  })

  it('stands the apply button down until the preview has landed', async () => {
    render(<DeliveryCenterView />)

    // While the measure is in flight, the button is disabled — a round is
    // never committed before its preview.
    const apply = screen.getByRole('button', { name: 'Apply the approved set' })
    expect(apply).toBeDisabled()
    await screen.findByRole('region', { name: 'Apply preview' })
    expect(apply).toBeEnabled()
  })

  it('commits the round with the service and names the binding it got back', async () => {
    render(<DeliveryCenterView />)

    await applyTheRound()

    expect(screen.getByText(/output version/)).toHaveTextContent('ver-applied-05')
    expect(screen.getByText(/bound by dossier/)).toHaveTextContent('dossier-1')

    // The four deliverables appear once the round is bound, addressed by the
    // dossier the apply named.
    await waitFor(() => {
      expect(screen.getByLabelText('Deliverables')).toBeInTheDocument()
    })
    expect(screen.getByText(/dossier-1/)).toBeInTheDocument()
  })

  it('shows the service refusal when the apply is declined', async () => {
    applyStatus = 403
    render(<DeliveryCenterView />)

    await screen.findByRole('region', { name: 'Apply preview' })
    fireEvent.click(screen.getByRole('button', { name: 'Apply the approved set' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/The service refused that/)
    expect(screen.queryByText(/bound by dossier/)).toBeNull()
  })

  it('shows the cancel button only while the apply is running, and it asks the route', async () => {
    holdApply = true
    render(<DeliveryCenterView />)

    // Before the round runs, there is nothing to cancel: the button is not
    // on the page at all, and its absence is the honest answer.
    await screen.findByRole('region', { name: 'Apply preview' })
    expect(screen.queryByRole('button', { name: 'Cancel' })).toBeNull()

    // While the apply runs, the operator can ask it to stop — the click is
    // the cancellation request, and it names the apply's own route.
    const apply = screen.getByRole('button', { name: 'Apply the approved set' })
    fireEvent.click(apply)
    const cancel = await screen.findByRole('button', { name: 'Cancel' })
    expect(cancel).toBeEnabled()
    fireEvent.click(cancel)

    // The answer is about the request: the stop takes effect at the round's
    // next checkpoint, and the centre says so rather than staying quiet.
    expect(
      await screen.findByText(/takes effect at the round's next checkpoint/),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled()

    // The round's own answer still lands, and the window closes with it.
    releaseApply?.()
    await screen.findByText(/bound by dossier/)
    expect(screen.queryByRole('button', { name: 'Cancel' })).toBeNull()
    expect(screen.queryByText(/takes effect at the round's next checkpoint/)).toBeNull()
  })

  it('shows a cancelled round as cancelled, not failed', async () => {
    // The service's own answer: the round stopped at its checkpoint, with
    // the operator's reason carried in the refusal's message.
    applyStatus = 403
    applyRefusalBody = {
      reason: 'apply_cancelled',
      message:
        "the apply round was cancelled at 'before_marked_publication': " +
        'cancelled from the delivery centre. Nothing further was published; ' +
        'the round may be applied again from the start, and the approvals it ' +
        'had not spent remain granted.',
    }
    holdApply = true
    render(<DeliveryCenterView />)

    await screen.findByRole('region', { name: 'Apply preview' })
    fireEvent.click(screen.getByRole('button', { name: 'Apply the approved set' }))

    // The cancellation rides along with the apply's own refusal — a page
    // asks for the stop while the round is out, and the round answers that
    // it stopped, in the service's own `apply_cancelled`.
    const cancel = await screen.findByRole('button', { name: 'Cancel' })
    fireEvent.click(cancel)
    await screen.findByText(/takes effect at the round's next checkpoint/)
    releaseApply?.()
    await screen.findByText(/Round cancelled/)

    // The apply's answer lands as the cancellation state — its own voice,
    // not the "the service refused that" failure line.
    expect(screen.getByText(/stopped at its publication checkpoint/)).toBeInTheDocument()
    expect(screen.getByText(/approvals it had not spent are still granted/)).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.queryByText(/bound by dossier/)).toBeNull()
  })

  it('shows the service refusal of a cancel with nothing to cancel', async () => {
    cancelStatus = 403
    cancelAnswer = {
      reason: 'arguments_invalid',
      message:
        'no apply round for this project is running, so there is nothing to ' +
        'cancel. A cancellation is a request about a round in flight, not a ' +
        'standing order for the next one.',
    }
    holdApply = true
    render(<DeliveryCenterView />)

    await screen.findByRole('region', { name: 'Apply preview' })
    fireEvent.click(screen.getByRole('button', { name: 'Apply the approved set' }))
    const cancel = await screen.findByRole('button', { name: 'Cancel' })
    fireEvent.click(cancel)

    // The refusal is the answer, and the round's own state is unchanged.
    expect(await screen.findByRole('alert')).toHaveTextContent(/no apply round/)
    expect(screen.queryByText(/takes effect at the round's next checkpoint/)).toBeNull()
    releaseApply?.()
  })

  it('says when the data is a fixture, and says what that costs', async () => {
    render(<DeliveryCenterView />)

    expect(await screen.findByText(/Fixture data/)).toBeInTheDocument()
    expect(screen.getByText(/save fixture bytes/)).toBeInTheDocument()
  })
})

describe('the four deliverables', () => {
  it('draw all four kinds with their paths, sizes and digests', async () => {
    render(<DeliveryCenterView />)

    await applyTheRound()
    const exportPanel = await screen.findByLabelText('Deliverables')

    for (const kind of ['marked', 'clean', 'response_table', 'quality_report']) {
      const row = exportPanel.querySelector(`[data-deliverable-kind="${kind}"]`)
      expect(row).not.toBeNull()
      expect(row?.className).not.toContain('delivery__deliverable--missing')
    }
    expect(
      within(exportPanel).getByText('deliverables/binding-sample-marked.docx'),
    ).toBeInTheDocument()
    expect(within(exportPanel).getByText('deliverables/response-table.md')).toBeInTheDocument()
    expect(within(exportPanel).getAllByText(/bytes · sha256/)).toHaveLength(4)
  })

  it('export by decoding the wire bytes and handing them to the browser', async () => {
    render(<DeliveryCenterView />)

    await applyTheRound()
    const exportPanel = await screen.findByLabelText('Deliverables')

    const anchors: { download: string; href: string }[] = []
    const revoked: string[] = []
    const realAppend = document.body.appendChild.bind(document.body)
    const realRemove = document.body.removeChild.bind(document.body)

    URL.createObjectURL = (blob: Blob): string => {
      // The blob is the wire's base64, decoded: the marked draft's 47 bytes.
      expect(blob.size).toBe(47)
      return 'blob:fixture'
    }
    URL.revokeObjectURL = (url: string): void => {
      revoked.push(url)
    }
    document.body.appendChild = <T extends Node>(node: T): T => {
      const anchor = node as unknown as HTMLAnchorElement
      if (anchor.tagName === 'A') {
        anchors.push({ download: anchor.download, href: anchor.href })
      }
      return realAppend(node)
    }
    document.body.removeChild = <T extends Node>(node: T): T => realRemove(node)

    try {
      fireEvent.click(within(exportPanel).getAllByRole('button', { name: 'Export' })[0]!)

      // The download is the wire's base64, decoded, named by the path's tail.
      expect(anchors).toHaveLength(1)
      expect(anchors[0]?.download).toBe('binding-sample-marked.docx')
      expect(anchors[0]?.href).toContain('blob:fixture')
      expect(revoked).toEqual(['blob:fixture'])
      expect(within(exportPanel).getAllByRole('button', { name: 'Saved' })[0]).toBeInTheDocument()
    } finally {
      URL.createObjectURL = (blob: Blob): string => URL.createObjectURL(blob)
      URL.revokeObjectURL = (url: string): void => URL.revokeObjectURL(url)
      document.body.appendChild = realAppend
      document.body.removeChild = realRemove
    }
  })
})

/**
 * The quality report, asked for by the dossier the apply named.
 *
 * **The report is a second read, not a decoration.** It is asked after the
 * apply closes the round, by the same dossier the deliverables are asked
 * by, and its six verdicts are drawn as the service sent them: a passing
 * check says it passed, a failing check is highlighted and names its
 * facts. A panel that invented a green report would be grading its own
 * homework, so what is checked here is that the panel draws the service's
 * measure — including the measure that says the round failed a check.
 */
describe('the quality report', () => {
  it('draws nothing measured before a round is applied', async () => {
    render(<DeliveryCenterView />)

    await screen.findByRole('region', { name: 'Apply preview' })

    const panel = screen.getByRole('region', { name: 'Quality report' })
    expect(within(panel).getByText(/no manifest to measure/)).toBeInTheDocument()
    // Six verdicts were never drawn, because none were asked for.
    expect(within(panel).queryAllByRole('listitem')).toHaveLength(0)
  })

  it('asks the six checks by the dossier the apply named and draws each verdict', async () => {
    render(<DeliveryCenterView />)

    await applyTheRound()

    const panel = await screen.findByRole('region', { name: 'Quality report' })
    // One <li> per check, plus the failing check's fact rows. The check
    // rows carry their names; the fact rows are nested inside them.
    const checks = within(panel)
      .getAllByRole('listitem')
      .filter((row) => row.getAttribute('data-check') !== null)
    expect(checks).toHaveLength(6)
    // The checks are the service's six, drawn with their own names.
    const names = checks.map((check) => check.getAttribute('data-check'))
    expect(names).toEqual([
      'opinion_coverage',
      'suggestion_correspondence',
      'edit_scope',
      'evidence_complete',
      'response_table_consistency',
      'report_binding',
    ])
    // The failing check is marked as failing, twice over: the structured
    // flag and the text a person reads.
    const failed = within(panel).getAllByText('FAILED')
    expect(failed).toHaveLength(1)
    const failingRow = checks[2] as HTMLElement
    expect(failingRow.getAttribute('data-passed')).toBe('false')
    // The failing check names its facts — the opinion, the paragraph, and
    // the two sides of the mismatch — so the operator can act on it.
    expect(
      within(failingRow).getByText(/An edit landed outside the paragraphs/),
    ).toBeInTheDocument()
    expect(within(failingRow).getByText(/opinion fb-method/)).toBeInTheDocument()
    expect(within(failingRow).getByText(/paragraph 9/)).toBeInTheDocument()
    expect(within(failingRow).getByText(/expected 4/)).toBeInTheDocument()
    expect(within(failingRow).getByText(/actual 9/)).toBeInTheDocument()
    // The passing checks carry no facts, and the panel draws none.
    const passingRow = checks[0] as HTMLElement
    expect(passingRow.getAttribute('data-passed')).toBe('true')
    expect(within(passingRow).queryAllByRole('listitem')).toHaveLength(0)
  })

  it('shows the service refusal when the report does not land', async () => {
    qualityStatus = 403
    qualityAnswer = {
      reason: 'chain_project_not_found',
      message: 'the store holds no paper project with the id "proj-lc-p4-cap".',
    }
    render(<DeliveryCenterView />)

    await applyTheRound()

    const panel = await screen.findByRole('region', { name: 'Quality report' })
    expect(within(panel).getByRole('alert')).toHaveTextContent(
      /The service did not answer the quality report:/,
    )
    expect(within(panel).getByRole('alert')).toHaveTextContent(/chain_project_not_found/)
    // A refused report draws no verdicts: six green checks nobody ran
    // would be a lie with a signature.
    expect(
      within(panel)
        .queryAllByRole('listitem')
        .filter((row) => row.getAttribute('data-check') !== null),
    ).toHaveLength(0)
  })

  it('does not let a refused report unwrite the deliverables drawn beside it', async () => {
    qualityStatus = 403
    qualityAnswer = {
      reason: 'artifact_not_found',
      message: 'no artefact carries the id "dossier-1".',
    }
    render(<DeliveryCenterView />)

    await applyTheRound()

    // The deliverables stand; the report's failure is its own.
    expect(screen.getByLabelText('Deliverables')).toBeInTheDocument()
    const panel = await screen.findByRole('region', { name: 'Quality report' })
    expect(within(panel).getByRole('alert')).toHaveTextContent(/artifact_not_found/)
  })
})
