/**
 * The binding's per-item review: every opinion, its verdict, and what is owed.
 *
 * **What the panel draws.** The dossier manifest is the binding's own record
 * of one round: every opinion placed (located, or explicitly at an uncertain
 * location), the reviewer's verdicts, the unresolved tasks, and the
 * handovers a seam refusal became. The panel reads the manifest's bytes
 * through the artefact content route — the same bytes the deliverables were
 * rendered from — and draws them as the per-item surface the execution plan
 * names: **every supported opinion is either answered or explicitly not,
 * and the panel shows which**.
 *
 * **What it does not decide.** The panel draws the service's answer; it adds
 * no verdict of its own and hides nothing. An opinion whose verdict is
 * missing is drawn as not reviewed — which is what the manifest says it is.
 *
 * **How the manifest is found.** The dossier is an artefact row whose
 * producer is the binding (`labcairn.papers.binding`) and whose media type
 * is JSON, and the workbench's batch read already carries every artefact —
 * so the panel asks the passed list, and does not hold a manifest id of its
 * own. A manifest the service had not recorded would simply not appear: the
 * panel invents nothing. The newest binding's dossier is the one drawn,
 * because one task's latest closed binding is the round a reviewer sits
 * down to.
 */

import type { JSX } from 'react'

import { artifactContentPath } from '../api/paths'
import type { ArtifactView } from '../api/generated'
import { asApiRead, usePanelRead } from './usePanelRead'
import type { PanelRead } from './usePanelRead'
import { Panel, RecordList } from './Panel'

interface ReviewViewProps {
  /** The artefacts this task has produced, from the workbench's batch read. */
  readonly artifacts: ArtifactView[]
  /** The workbench's read cycle, which re-asks the panel's own read. */
  readonly cycle: number
}

/** The opinion row the manifest carries. */
interface OpinionEntry {
  readonly feedback_id: string
  readonly location_state: string
  readonly anchor_status: string
  readonly anchor_paragraph: number | null
}

/** The verdict row the manifest carries. */
interface DecisionEntry {
  readonly feedback_id: string
  readonly verdict: string
  readonly operator: string
  readonly needs_evidence: boolean
}

/** The unresolved task the manifest carries. */
interface UnresolvedEntry {
  readonly feedback_id: string
  readonly reason: string
  readonly detail: string
}

/** The handover the manifest carries. */
interface HandoverEntry {
  readonly feedback_id: string
  readonly reason: string
  readonly detail: string
  readonly handover: string
}

/** The dossier manifest's shape, read back from the artefact's bytes. */
interface DossierManifest {
  readonly input_version_id: string
  readonly output_version_id: string
  readonly marked_receipt_id: string
  readonly clean_receipt_id: string
  readonly opinions: OpinionEntry[]
  readonly decisions: DecisionEntry[]
  readonly unresolved: UnresolvedEntry[]
  readonly handovers: HandoverEntry[]
}

/** The binding's producer id — the dossier manifest is the row that carries it. */
const BINDING_PRODUCER = 'labcairn.papers.binding'

/** One binding's dossier, found among the task's artefacts. */
function dossierOf(artifacts: readonly ArtifactView[]): ArtifactView | null {
  const candidates = artifacts.filter(
    (view) =>
      view.receipt.producer_id === BINDING_PRODUCER &&
      view.receipt.media_type === 'application/json',
  )
  // The newest dossier is the one this task's latest binding wrote; the
  // receipts' order in the list is the order the service answered in.
  return candidates.length === 0 ? null : (candidates[candidates.length - 1] ?? null)
}

/** Parse one dossier's answer. A manifest that does not parse is not drawn. */
function parseDossier(payload: unknown): DossierManifest | null {
  if (typeof payload !== 'object' || payload === null) {
    return null
  }
  const candidate = payload as Record<string, unknown>
  if (!Array.isArray(candidate.opinions) || !Array.isArray(candidate.decisions)) {
    return null
  }
  return candidate as unknown as DossierManifest
}

/** One opinion's row: where it sits, what was decided, and what is owed. */
function OpinionRow({
  opinion,
  decision,
  unresolved,
  handover,
}: {
  readonly opinion: OpinionEntry
  readonly decision: DecisionEntry | null
  readonly unresolved: UnresolvedEntry | null
  readonly handover: HandoverEntry | null
}): JSX.Element {
  const verdict =
    decision === null
      ? 'not reviewed'
      : decision.needs_evidence
        ? `${decision.verdict} — needs evidence`
        : decision.verdict
  return (
    <li className="record">
      <span className="record__name">{opinion.feedback_id}</span>
      <span className="record__detail">
        {opinion.location_state} (anchor {opinion.anchor_status}
        {opinion.anchor_paragraph === null ? '' : `, paragraph ${opinion.anchor_paragraph}`})
      </span>
      <span className="record__detail">
        {verdict}
        {decision === null ? '' : `, by ${decision.operator}`}
      </span>
      {unresolved !== null ? (
        <span className="record__detail">
          unresolved — {unresolved.reason}: {unresolved.detail}
        </span>
      ) : null}
      {handover !== null ? (
        <span className="record__detail">
          handed to a person — {handover.reason}: {handover.handover}
        </span>
      ) : null}
    </li>
  )
}

export function ReviewView({ artifacts, cycle }: ReviewViewProps): JSX.Element | null {
  const dossier = dossierOf(artifacts)
  const manifestPath = dossier === null ? null : artifactContentPath(dossier.receipt.receipt_id)
  const manifest = usePanelRead<DossierManifest>(manifestPath, cycle)

  if (dossier === null) {
    // No binding has closed in this task: the panel draws nothing rather
    // than an empty frame, because an empty frame would say a binding ran.
    return null
  }

  if (manifest.kind === 'answered') {
    const parsed = parseDossier(manifest.data)
    if (parsed === null) {
      return (
        <Panel title="Binding review" read={asApiRead(manifest)}>
          {() => (
            <p className="panel__error" role="status">
              The dossier manifest at {dossier.receipt.receipt_id} did not parse as one. The
              binding's record is that receipt's bytes, and this panel draws no second spelling
              of them.
            </p>
          )}
        </Panel>
      )
    }
    const decisions = new Map<string, DecisionEntry>(
      parsed.decisions.map((entry) => [entry.feedback_id, entry]),
    )
    const unresolved = new Map<string, UnresolvedEntry>(
      parsed.unresolved.map((entry) => [entry.feedback_id, entry]),
    )
    const handovers = new Map<string, HandoverEntry>(
      parsed.handovers.map((entry) => [entry.feedback_id, entry]),
    )
    return (
      <Panel title="Binding review" read={asApiRead(manifest)}>
        {() => (
          <>
            <RecordList>
              <li className="record">
                <span className="record__name">Binding</span>
                <span className="record__detail">
                  input {parsed.input_version_id} → output {parsed.output_version_id}
                </span>
                <span className="record__detail">marked draft {parsed.marked_receipt_id}</span>
                <span className="record__detail">clean draft {parsed.clean_receipt_id}</span>
              </li>
              {parsed.opinions.map((opinion) => (
                <OpinionRow
                  key={opinion.feedback_id}
                  opinion={opinion}
                  decision={decisions.get(opinion.feedback_id) ?? null}
                  unresolved={unresolved.get(opinion.feedback_id) ?? null}
                  handover={handovers.get(opinion.feedback_id) ?? null}
                />
              ))}
            </RecordList>
            {parsed.unresolved.length === 0 ? (
              <p>No unresolved opinions: every supported opinion is answered in this round.</p>
            ) : (
              <p>
                {parsed.unresolved.length} opinion(s) stay unresolved as explicit tasks — the rows
                above name what is owed.
              </p>
            )}
          </>
        )}
      </Panel>
    )
  }

  // The manifest has not landed yet: the frame's own pending and error
  // states say so, and the receipt line is what the panel can already draw.
  return (
    <Panel title="Binding review" read={asApiRead(manifest)}>
      {() => (
        <RecordList>
          <li className="record">
            <span className="record__name">Dossier manifest</span>
            <span className="record__detail">{dossier.receipt.receipt_id}</span>
            <span className="record__detail">binds {dossier.receipt.relative_path}</span>
          </li>
        </RecordList>
      )}
    </Panel>
  )
}

export type { PanelRead }
