/**
 * The delivery centre: the panel where a round is committed and its four
 * deliverables are read out.
 *
 * **The preview comes first, and the apply waits for it.** Before anything is
 * written, the centre measures the round — how many suggestions stand
 * approved, which paragraphs they touch, what each change says, and the
 * digests the committed apply will publish — and the apply button stands
 * down until that measure has landed. The order is the plan's own
 * (execution plan §3.2, read 2026-11-25: the preview must show the number
 * of changes, the paragraphs they affect and a summary of the output before
 * anything is modified),
 * not a layout preference: a round committed before its preview would be a
 * round the operator never saw coming.
 *
 * **The four deliverables are one round's four.** After the apply closes the
 * round, its answer names the dossier that binds the marked draft, the clean
 * draft, the response table and the quality report to one input version, one
 * output version and one edge. The centre asks for them by that dossier —
 * not for "the latest" — and each file carries its own digest, so a download
 * can be checked against the binding after it is saved.
 *
 * **The fixture is a fallback, and it says so.** While the service's
 * `/review` routes do not answer, the centre draws the fixtures and labels
 * them; a note that hid itself would be a fixture that lied about being the
 * service.
 *
 * **The round is the service's, and the note says which round it is.** The
 * centre asks `GET /review/rounds` for the round it addresses, so the
 * pilot paper's round is the one the centre measures — and a reader is
 * told the round's ids and whether they came from the service or from the
 * sample, because a centre that measured a sample round without saying so
 * could not be believed about the pilot paper.
 */

import { useCallback, useEffect, useState } from 'react'
import type { JSX } from 'react'

import type {
  DeliverableFileWire,
  DeliverablesExportWire,
  ReviewPreview,
  RoundQualityReport,
} from '../api/generated'
import { describeError } from '../api/client'
import {
  applyReview,
  cancelApplyReview,
  DELIVERABLE_KINDS,
  DELIVERABLE_LABELS,
  downloadDeliverable,
  readDeliverables,
  readPreview,
  readQuality,
} from './deliveryCenterClient'
import { fixtureDeliverablesExport, fixturePreview } from './deliveryFixture'
import { FIXTURE_APPLY_ROUND, readDeliveryRound } from './deliveryRound'
import type { ApplyRound } from './deliveryCenterClient'

/** What one round's commit did, as the centre's own record of it. */
interface ApplyOutcome {
  /** The version the apply published. */
  readonly outputVersionId: string
  /** The dossier that binds the round's four deliverables. */
  readonly dossierArtifactId: string
  /** How many suggestions the apply carried. */
  readonly appliedCount: number
}

/**
 * What one check's verdict is, as the panel draws it.
 *
 * **The structured state is the service's, and the sentence is its own.**
 * A failing check is drawn with both: the `passed` flag is the machine's
 * verdict, and the facts' details are the sentences a person reads. A
 * panel that drew only one channel would be answering half the question.
 */
function QualityCheckRow({
  check,
}: {
  readonly check: RoundQualityReport['checks'][number]
}): JSX.Element {
  return (
    <li
      className={
        check.passed
          ? 'delivery__quality-check'
          : 'delivery__quality-check delivery__quality-check--failed'
      }
      data-check={check.check}
      data-passed={check.passed}
    >
      <span className="delivery__quality-check-name">{check.check}</span>
      <span className="delivery__quality-check-verdict">{check.passed ? 'passed' : 'FAILED'}</span>
      {(check.facts ?? []).length > 0 ? (
        <ul className="delivery__quality-facts">
          {(check.facts ?? []).map((fact, index) => (
            <li className="delivery__quality-fact" key={`${fact.check}-${index}`}>
              <span className="delivery__quality-fact-detail">{fact.detail}</span>
              <span className="delivery__quality-fact-meta">
                {fact.feedback_id !== null && fact.feedback_id !== undefined
                  ? `opinion ${fact.feedback_id}`
                  : null}
                {fact.paragraph !== null && fact.paragraph !== undefined
                  ? ` · paragraph ${fact.paragraph}`
                  : null}
                {fact.expected !== null && fact.expected !== undefined
                  ? ` · expected ${fact.expected}`
                  : null}
                {fact.actual !== null && fact.actual !== undefined
                  ? ` · actual ${fact.actual}`
                  : null}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </li>
  )
}

/**
 * The round's six quality checks, drawn as the manifest names them.
 *
 * **The panel draws the report; it does not grade it.** The verdicts are
 * the service's own, and a failed check is highlighted — a failing check
 * drawn in the same grey as a passing one would be a report nobody read.
 * A report that never landed says so, in its own words, rather than
 * drawing a silence as if it were six green checks.
 */
function QualityPanel({
  state,
}: {
  readonly state:
    | { readonly kind: 'idle' }
    | { readonly kind: 'pending' }
    | { readonly kind: 'done'; readonly report: RoundQualityReport }
    | { readonly kind: 'failed'; readonly message: string }
}): JSX.Element {
  return (
    <div className="delivery__quality" role="region" aria-label="Quality report">
      <h3 className="delivery__section-title">Quality report</h3>
      {state.kind === 'idle' ? (
        <p className="panel__status">
          The round has not been committed yet, so there is no manifest to measure.
        </p>
      ) : state.kind === 'pending' ? (
        <p className="panel__pending" role="status">
          Running the six checks…
        </p>
      ) : state.kind === 'failed' ? (
        <p className="panel__error" role="alert">
          The service did not answer the quality report: {state.message}
        </p>
      ) : (
        <>
          <p className="panel__note">
            The six §7.4 checks over this round&rsquo;s dossier manifest — the manifest the four
            deliverables bind. A failed check names the facts that made it fail.
          </p>
          <ul className="delivery__quality-checks">
            {state.report.checks.map((check) => (
              <QualityCheckRow key={check.check} check={check} />
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

/** The deliverable kinds the export carries but the contract's four are not. */
function kindLabel(kind: string): string {
  return DELIVERABLE_LABELS[kind] ?? kind
}

/** One deliverable's row: its kind, its name, its size, and its download. */
function DeliverableRow({
  deliverable,
  onDownload,
  busy,
}: {
  readonly deliverable: DeliverableFileWire
  readonly onDownload: (deliverable: DeliverableFileWire) => void
  readonly busy: boolean
}): JSX.Element {
  const [saved, setSaved] = useState(false)
  return (
    <li className="delivery__deliverable" data-deliverable-kind={deliverable.kind}>
      <span className="delivery__deliverable-kind">{kindLabel(deliverable.kind)}</span>
      <span className="delivery__deliverable-name">{deliverable.relative_path}</span>
      <span className="delivery__deliverable-meta">
        {deliverable.size_bytes} bytes · sha256 {deliverable.sha256.slice(0, 12)}…
      </span>
      <button
        type="button"
        className="button delivery__download"
        disabled={busy}
        onClick={() => {
          onDownload(deliverable)
          setSaved(true)
        }}
      >
        {busy ? 'Exporting…' : saved ? 'Saved' : 'Export'}
      </button>
    </li>
  )
}

/** The preview, read as counts and changes: what the round would do. */
function PreviewBlock({ preview }: { readonly preview: ReviewPreview }): JSX.Element {
  return (
    <div
      className="delivery__preview"
      role="region"
      aria-label="Apply preview"
      data-applied={preview.applied}
      data-pending={preview.pending}
      data-rejected={preview.rejected}
    >
      <p className="delivery__preview-counts">
        <strong data-preview-count="applied">{preview.applied}</strong> applied ·{' '}
        <strong data-preview-count="pending">{preview.pending}</strong> pending ·{' '}
        <strong data-preview-count="rejected">{preview.rejected}</strong> rejected
      </p>
      <p className="delivery__preview-paragraphs">
        {preview.affected_paragraphs.length === 0
          ? 'No paragraphs are affected: the approved set is empty.'
          : `Affected paragraphs: ${preview.affected_paragraphs.map((n) => `¶${n}`).join(', ')}`}
      </p>
      {preview.edits.length > 0 ? (
        <ul className="delivery__edits">
          {preview.edits.map((edit) => (
            <li key={edit.feedback_id} className="delivery__edit">
              <span className="delivery__edit-place">
                {edit.part} · ¶{edit.paragraph}
              </span>
              <span className="delivery__edit-old">{edit.old_text}</span>
              <span className="delivery__edit-new">{edit.new_text}</span>
            </li>
          ))}
        </ul>
      ) : null}
      <dl className="delivery__digests">
        <div>
          <dt>original</dt>
          <dd>{preview.original_sha256.slice(0, 16)}…</dd>
        </div>
        <div>
          <dt>marked</dt>
          <dd>{preview.marked_sha256.slice(0, 16)}…</dd>
        </div>
        <div>
          <dt>clean</dt>
          <dd>{preview.clean_sha256.slice(0, 16)}…</dd>
        </div>
      </dl>
    </div>
  )
}

/** The note that says whose answer the centre is drawing. */
function DataSourceNote({
  previewFromService,
  deliverablesFromService,
  round,
  roundFromService,
}: {
  readonly previewFromService: boolean
  readonly deliverablesFromService: boolean
  readonly round: ApplyRound
  readonly roundFromService: boolean
}): JSX.Element {
  if (previewFromService && deliverablesFromService) {
    return (
      <p className="panel__note delivery__fixture-note" role="note">
        Live data — read from the service&rsquo;s <code>/review</code> routes for the round{' '}
        <code>
          {round.projectId} / {round.inputVersionId}
        </code>
        .
      </p>
    )
  }
  if (roundFromService) {
    return (
      <p className="panel__note delivery__fixture-note" role="note">
        Fixture data — the service named the round{' '}
        <code>
          {round.projectId} / {round.inputVersionId}
        </code>
        , and this centre draws the sample fixture (
        <code>
          {FIXTURE_APPLY_ROUND.projectId} / {FIXTURE_APPLY_ROUND.inputVersionId}
        </code>
        ) for the panels the service has not answered. Exports clicked here save fixture bytes.
      </p>
    )
  }
  return (
    <p className="panel__note delivery__fixture-note" role="note">
      Fixture data — the service&rsquo;s <code>/review</code> routes did not answer, so this centre
      is drawn from <code>src/views/deliveryFixture.ts</code> for the sample round{' '}
      <code>
        {round.projectId} / {round.inputVersionId}
      </code>
      . Exports clicked here save fixture bytes.
    </p>
  )
}

/** What the centre is showing, and what it can do. */
export function DeliveryCenterView(): JSX.Element {
  const [preview, setPreview] = useState<ReviewPreview>(fixturePreview)
  const [previewFromService, setPreviewFromService] = useState<boolean | null>(null)
  const [export_, setExport] = useState<DeliverablesExportWire | null>(null)
  const [exportFromService, setExportFromService] = useState<boolean | null>(null)
  const [previewLoading, setPreviewLoading] = useState(true)
  const [round, setRound] = useState<ApplyRound>(FIXTURE_APPLY_ROUND)
  const [roundFromService, setRoundFromService] = useState<boolean | null>(null)
  const [applying, setApplying] = useState(false)
  const [cancelPending, setCancelPending] = useState(false)
  const [cancelAsked, setCancelAsked] = useState(false)
  const [cancelledRound, setCancelledRound] = useState(false)
  const [cancelNotice, setCancelNotice] = useState<string | null>(null)
  const [downloadingKind, setDownloadingKind] = useState<string | null>(null)
  const [refusal, setRefusal] = useState<string | null>(null)
  const [outcome, setOutcome] = useState<ApplyOutcome | null>(null)
  const [quality, setQuality] = useState<
    | { readonly kind: 'idle' }
    | { readonly kind: 'pending' }
    | { readonly kind: 'done'; readonly report: RoundQualityReport }
    | { readonly kind: 'failed'; readonly message: string }
  >({ kind: 'idle' })

  // The preview is read once, before anything can be committed: the apply
  // button stands down until this measure has landed. A committed round is
  // re-read through its own dossier, so the four files the centre draws next
  // are the four files that round bound — and the preview is asked again, the
  // same rule the desk's verdicts follow: the service's answer is the record.
  //
  // **The round comes first.** The centre asks the service which round it
  // holds, and the preview and the dossier are read against *that* round —
  // so the pilot paper's round is the one the centre measures, and the
  // sample's stands in only when the service does not answer.
  const readRound = useCallback((dossierArtifactId: string | null): void => {
    setPreviewLoading(true)
    setRefusal(null)
    void readDeliveryRound().then((roundRead) => {
      setRound(roundRead.round)
      setRoundFromService(roundRead.fromService)
      void readPreview(roundRead.round)
        .then((read) => {
          setPreview(read.data)
          setPreviewFromService(read.fromService)
        })
        .catch((error: unknown) => {
          setRefusal(error instanceof Error ? error.message : String(error))
        })
        .finally(() => {
          setPreviewLoading(false)
        })
      if (dossierArtifactId !== null) {
        void readDeliverables(roundRead.round.projectId, dossierArtifactId)
          .then((read) => {
            setExport(read.data)
            setExportFromService(read.fromService)
          })
          .catch((error: unknown) => {
            setRefusal(error instanceof Error ? error.message : String(error))
          })
        // The round's manifest is the authority the six checks read. The
        // quality report is asked by the same dossier the deliverables are —
        // the apply's own answer names it — so the checks measure the round
        // that was committed, and not whichever dossier is latest. Its states
        // are its own: a report that fails to land does not unwrite the four
        // deliverables drawn beside it.
        setQuality({ kind: 'pending' })
        void readQuality(roundRead.round.projectId, dossierArtifactId)
          .then((report) => {
            setQuality({ kind: 'done', report })
          })
          .catch((error: unknown) => {
            // The refusal's code is drawn beside its message: a panel that
            // said only "refused" would be saying less than the service said.
            const described = describeError(error)
            setQuality({
              kind: 'failed',
              message:
                described.reason === null
                  ? described.message
                  : `${described.reason} — ${described.message}`,
            })
          })
      }
    })
  }, [])

  useEffect(() => {
    // The read itself is async: the states it sets land in the promise's
    // callbacks, not in the effect body, so the first render commits before
    // any state moves.
    void Promise.resolve().then(() => {
      readRound(null)
    })
  }, [readRound])

  /** Commit the round, and take the service's binding back as the answer. */
  const onApply = useCallback((): void => {
    setApplying(true)
    setRefusal(null)
    setCancelledRound(false)
    setCancelAsked(false)
    setCancelNotice(null)
    void applyReview(round)
      .then((result) => {
        const next: ApplyOutcome = {
          outputVersionId: result.output_version_id,
          dossierArtifactId: result.dossier_artifact_id,
          appliedCount: result.applied.length,
        }
        setOutcome(next)
        setExportFromService(null)
        readRound(next.dossierArtifactId)
      })
      .catch((error: unknown) => {
        // **A cancelled round is a state, not a failure.** The service's
        // `apply_cancelled` refusal is the round stopping where the operator
        // asked it to — nothing further published, unspent approvals still
        // granted — so the centre says that in its own voice instead of
        // filing it under "the service refused that".
        const described = describeError(error)
        if (described.reason === 'apply_cancelled') {
          setCancelledRound(true)
          setRefusal(null)
        } else {
          setRefusal(described.message)
        }
      })
      .finally(() => {
        setApplying(false)
        setCancelPending(false)
        // The round is over — applied, cancelled or refused — so the notice
        // about a stop that is on its way is stale, and the outcome the
        // round answered with is what the centre shows instead.
        setCancelNotice(null)
      })
  }, [readRound, round])

  /** Ask the running round to stop at its next publication checkpoint. */
  const onCancelApply = useCallback((): void => {
    setCancelPending(true)
    void cancelApplyReview(round.projectId, 'cancelled from the delivery centre')
      .then((answer) => {
        // The service has planted the flag where the round reads it; the
        // round stops at its next checkpoint, which the apply call's own
        // answer reports. Saying so is the difference between "the button
        // did nothing" and "the stop is on its way". The asked state stays:
        // one cancellation per round is what the operator means, and a
        // second press would be asking the same round twice.
        setCancelAsked(true)
        setCancelNotice(
          `Cancel accepted — it takes effect at the round's next checkpoint${
            answer.accepted ? '' : ' (not accepted)'
          }.`,
        )
      })
      .catch((error: unknown) => {
        // The service refused the cancellation — no apply round is running,
        // or the project is not there. The refusal is the answer, and the
        // round's own state is unchanged; the operator may ask again.
        const described = describeError(error)
        setCancelNotice(null)
        setCancelAsked(false)
        setRefusal(described.message)
      })
      .finally(() => {
        setCancelPending(false)
      })
  }, [round])

  const onDownload = useCallback((deliverable: DeliverableFileWire): void => {
    setDownloadingKind(deliverable.kind)
    try {
      downloadDeliverable(deliverable)
    } catch (error: unknown) {
      setRefusal(
        `could not decode ${deliverable.relative_path}: ${
          error instanceof Error ? error.message : String(error)
        }`,
      )
    } finally {
      setDownloadingKind(null)
    }
  }, [])

  const showDeliverables = outcome !== null || export_ !== null
  const shownExport = export_ ?? (outcome === null ? fixtureDeliverablesExport : null)

  return (
    <section className="panel delivery" aria-label="Delivery centre">
      <h2 className="panel__title">Delivery centre</h2>
      <DataSourceNote
        previewFromService={previewFromService === true}
        deliverablesFromService={exportFromService === true}
        round={round}
        roundFromService={roundFromService === true}
      />
      {refusal !== null ? (
        <p className="delivery__refusal" role="alert">
          The service refused that: {refusal}
        </p>
      ) : null}
      {cancelledRound ? (
        <p className="delivery__cancelled" role="status" data-cancelled="true">
          Round cancelled — the apply stopped at its publication checkpoint. Nothing further was
          published, and the approvals it had not spent are still granted. Apply again to rerun the
          round from the start.
        </p>
      ) : null}

      <div className="delivery__commit">
        <h3 className="delivery__section-title">Apply the approved set</h3>
        {previewLoading ? (
          <p className="panel__pending" role="status">
            Measuring the round…
          </p>
        ) : (
          <PreviewBlock preview={preview} />
        )}
        <div className="delivery__apply-row">
          <button
            type="button"
            className="button delivery__apply"
            disabled={previewLoading || applying}
            onClick={onApply}
          >
            {applying ? 'Applying…' : outcome === null ? 'Apply the approved set' : 'Apply again'}
          </button>
          {applying ? (
            <button
              type="button"
              className="button delivery__cancel"
              disabled={cancelPending || cancelAsked}
              onClick={onCancelApply}
            >
              {cancelPending ? 'Cancelling…' : 'Cancel'}
            </button>
          ) : null}
        </div>
        {cancelNotice !== null ? (
          <p className="delivery__cancel-notice" role="status">
            {cancelNotice}
          </p>
        ) : null}
        {outcome !== null ? (
          <p className="delivery__outcome" role="status" data-applied-count={outcome.appliedCount}>
            Applied {outcome.appliedCount} suggestion{outcome.appliedCount === 1 ? '' : 's'} —
            output version <code>{outcome.outputVersionId}</code>, bound by dossier{' '}
            <code>{outcome.dossierArtifactId}</code>.
          </p>
        ) : null}
      </div>

      {showDeliverables && shownExport !== null ? (
        <div className="delivery__export" aria-label="Deliverables">
          <h3 className="delivery__section-title">The four deliverables</h3>
          <p className="delivery__binding">
            Task <code>{shownExport.task_id}</code> · input{' '}
            <code>{shownExport.input_version_id}</code> · output{' '}
            <code>{shownExport.output_version_id}</code> · edge <code>{shownExport.edge_id}</code>
          </p>
          <ul className="delivery__deliverables">
            {DELIVERABLE_KINDS.map((kind) => {
              const deliverable = shownExport.deliverables.find((file) => file.kind === kind)
              if (deliverable === undefined) {
                return (
                  <li key={kind} className="delivery__deliverable delivery__deliverable--missing">
                    <span className="delivery__deliverable-kind">{kindLabel(kind)}</span>
                    <span className="delivery__deliverable-meta">not in this binding</span>
                  </li>
                )
              }
              return (
                <DeliverableRow
                  key={kind}
                  deliverable={deliverable}
                  onDownload={onDownload}
                  busy={downloadingKind === kind}
                />
              )
            })}
          </ul>
        </div>
      ) : (
        <p className="panel__note">
          The four deliverables appear once a round is applied and bound. The service has not bound
          one on this page yet.
        </p>
      )}

      <QualityPanel state={quality} />
    </section>
  )
}
