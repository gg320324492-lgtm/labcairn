/**
 * The versions of a report, read from the receipts the service already holds.
 *
 * **What a version is here.** A report is re-rendered as a **new revision**
 * (`src/labcairn/reports/revisions.py`): revision 2's files are written under
 * `report/v2/` and revision 1's are never altered. The receipts the service
 * lists at `/artifacts` carry that revision number and the bytes' hash, so
 * the versions a reader can choose between are **the revisions of the
 * report**, read from the records rather than composed by this page.
 *
 * **What choosing a version is, and is not.** The service holds no
 * "current version" pointer for a task — there is no route that stores one —
 * so a selection made here changes **what this page shows**, and nothing
 * else. The page says so, in its own panel, rather than letting a reader
 * believe the choice was written somewhere. That is the honest boundary the
 * work order asks for: the selection surface exists, and what it does not do
 * is claimed just as plainly.
 *
 * The grouping is by **revision number**, not by the receipt's path text: a
 * path carries `v{N}` only for the report the revision machinery writes, and
 * a grouping rule that read the path would group nothing for any other kind.
 */

import type { ArtifactView } from '../api/generated'

/** One version of the report: the revision, and the receipts that carry it. */
export interface ReportVersion {
  /** The revision number every receipt in this version carries. */
  readonly revision: number
  /** The receipts of this revision, document first. */
  readonly receipts: readonly ArtifactView[]
}

/** The report-form receipts of one revision, with the canonical document first. */
function orderReceipts(receipts: readonly ArtifactView[]): readonly ArtifactView[] {
  const document = receipts.filter((view) => view.receipt.relative_path.endsWith('.json'))
  const rest = receipts.filter((view) => !view.receipt.relative_path.endsWith('.json'))
  return [...document, ...rest]
}

/**
 * The report's versions, oldest first.
 *
 * **A version is a set of receipts that share one revision number** — the
 * identity `src/labcairn/reports/revisions.py` states. A receipt with no
 * revision number is not left out: it is its own version, numbered `1`,
 * because the field is optional in the contract and a receipt that does not
 * carry a number is still something the task produced. The order is the
 * numbers' own, and nothing here invents a newer-than relation the receipts
 * do not state.
 */
export function reportVersions(artifacts: readonly ArtifactView[]): readonly ReportVersion[] {
  const byRevision = new Map<number, ArtifactView[]>()
  for (const view of artifacts) {
    if (view.receipt.kind !== 'report') {
      continue
    }
    // MUTATION reverted: the receipt's own revision number groups it.
    const revision = view.receipt.revision ?? 1
    const group = byRevision.get(revision)
    if (group === undefined) {
      byRevision.set(revision, [view])
    } else {
      group.push(view)
    }
  }
  return [...byRevision.entries()]
    .sort(([left], [right]) => left - right)
    .map(([revision, receipts]) => ({ revision, receipts: orderReceipts(receipts) }))
}
