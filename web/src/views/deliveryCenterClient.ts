/**
 * The delivery centre's reads and writes, against the service's `/review`
 * routes.
 *
 * **One seam, named for the centre.** The centre previews what the apply
 * round would do (`POST /review/preview`, a dry run that writes nothing),
 * commits the round (`POST /review/apply`), and reads the four deliverables
 * of the round the apply closed (`GET /review/deliverables`). The paths live
 * in `../api/paths` so the drift check can compare them with the service's
 * own route table, and the request shape is the service's
 * (`ApplyReviewBody`, from the generated types) rather than re-spelled here.
 *
 * **The fixture stays, and it is a fallback.** When the service does not
 * answer, the centre draws the fixtures and says so; the caller decides
 * that, because a fallback that hid itself would be a fixture that lied
 * about being the service.
 */

import { api } from '../api/client'
import { API_PATHS, reviewApplyBody, reviewDeliverablesPath } from '../api/paths'
import type {
  ApplyReviewBody,
  DeliverablesExportWire,
  DeliverableFileWire,
  ReviewApplyResult,
  ReviewPreview,
} from '../api/generated'
import type { ReviewData } from './reviewClient'
import {
  fixtureDeliverablesExport,
  fixturePreview,
  FIXTURE_DOSSIER_ARTIFACT_ID,
} from './deliveryFixture'

/** The workbench operator whose handle travels with every decision. */
export { REVIEW_OPERATOR } from './reviewClient'

/** The parameters of one round's apply, as the desk's own reads name them. */
export interface ApplyRound {
  /** The project the round belongs to. */
  readonly projectId: string
  /** The version the round works from. */
  readonly inputVersionId: string
  /** The source root the round's material stands in. */
  readonly sourceRootId: string
  /** The material's key inside its root. */
  readonly sourceKey: string
  /** The name the published output carries. */
  readonly outputLabel: string
  /** The consent window's end, as the service requires it. */
  readonly windowEnd: string
}

function applyBody(round: ApplyRound): ApplyReviewBody {
  return reviewApplyBody(round.projectId, round.inputVersionId, {
    sourceRootId: round.sourceRootId,
    sourceKey: round.sourceKey,
    outputLabel: round.outputLabel,
    windowEnd: round.windowEnd,
  })
}

/**
 * Measure what the apply round would do, falling back to the fixture.
 *
 * The preview is a dry run: the service's answer carries the counts, the
 * affected paragraphs, the per-suggestion summaries and the digests the
 * committed apply will publish — and writes nothing. A refusal or a failure
 * leaves the fixture standing, and the caller says which it drew.
 */
export async function readPreview(round: ApplyRound): Promise<ReviewData<ReviewPreview>> {
  try {
    const data = await api.post<ReviewPreview>(API_PATHS.reviewPreview, applyBody(round))
    return { data, fromService: true }
  } catch {
    return { data: fixturePreview, fromService: false }
  }
}

/**
 * Run the stored, approved set through the binding, and close the round.
 *
 * **The decisions come from the store.** The body carries only the round's
 * addresses — the binding reads what the reviewer wrote, which is what makes
 * the applied set auditable after the fact.
 */
export function applyReview(round: ApplyRound): Promise<ReviewApplyResult> {
  return api.post<ReviewApplyResult>(API_PATHS.reviewApply, applyBody(round))
}

/**
 * Read one closed binding's four deliverables, falling back to the fixture.
 *
 * The round is named by its dossier — the apply's own answer carries the id —
 * so the four files the centre draws are the four files *that round* bound.
 * A service that is not there leaves the fixture.
 */
export async function readDeliverables(
  projectId: string,
  dossierArtifactId: string,
): Promise<ReviewData<DeliverablesExportWire>> {
  try {
    const data = await api.get<DeliverablesExportWire>(
      reviewDeliverablesPath(projectId, dossierArtifactId),
    )
    return { data, fromService: true }
  } catch {
    return { data: fixtureDeliverablesExport, fromService: false }
  }
}

/** The four kinds the contract binds, in the order the centre shows them. */
export const DELIVERABLE_KINDS: readonly DeliverableFileWire['kind'][] = [
  'marked',
  'clean',
  'response_table',
  'quality_report',
]

/** What one deliverable is called on the desk. */
export const DELIVERABLE_LABELS: Readonly<Record<string, string>> = {
  marked: 'Marked draft',
  clean: 'Clean draft',
  response_table: 'Response table',
  quality_report: 'Quality report',
}

/**
 * Decode one deliverable's bytes, and hand them to the browser to save.
 *
 * **The download is the wire's base64, decoded.** The file is named by the
 * path's own tail — the name the service bound the bytes under — and a
 * decode failure is the caller's to show, because a saved file whose bytes
 * are not the binding's bytes is a lie with a filename on it.
 */
export function deliverableFileName(deliverable: DeliverableFileWire): string {
  const tail = deliverable.relative_path.split(/[\\/]/).pop()
  return tail === undefined || tail === '' ? deliverable.kind : tail
}

export function deliverableBlob(deliverable: DeliverableFileWire): Blob {
  const binary = atob(deliverable.content_base64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i)
  }
  return new Blob([bytes], { type: 'application/octet-stream' })
}

export function downloadDeliverable(deliverable: DeliverableFileWire): void {
  const url = URL.createObjectURL(deliverableBlob(deliverable))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = deliverableFileName(deliverable)
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

/** The dossier the fixture's export is bound to, for the fixture note. */
export { FIXTURE_DOSSIER_ARTIFACT_ID }
