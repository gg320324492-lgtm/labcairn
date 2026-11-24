/**
 * The review-API contract, as the workbench reads it.
 *
 * These types mirror the shapes agreed in
 * `docs/plans/LC-P4-CAP-review-api-contract.md` (v1, 2026-11-23): the
 * opinion list the left column draws, the manuscript the middle column
 * draws, and the decision a person records in the right column. The service
 * does not serve the `/review` routes yet, so this batch is built against
 * `fixtures/review-sample.json`, and that fixture must satisfy these types —
 * a shape the fixture drifts from is a shape the workbench will one day
 * misread. When the service answers, the data moves to the generated client
 * and the fixture is deleted; these shapes stay.
 */

/** Where an opinion's anchor stands, in the binding's own words. */
export type AnchorStatus = 'resolved' | 'unknown' | 'position'

/** Whether an opinion is placed, needs evidence, or sits at an uncertain location. */
export type LocationState = 'located' | 'needs_evidence' | 'uncertain_location'

/** The four verdicts a person may record on one opinion. */
export type ReviewVerdict = 'accepted' | 'partly_accepted' | 'rejected' | 'pending'

/** How far the chain says an opinion has been answered. */
export type ResponseState = 'addressed' | 'partially_addressed' | 'not_addressed' | 'pending'

/**
 * Where in the DOCX the comment was written.
 *
 * The contract names this "the DocxLocator JSON" and does not pin its
 * fields, so the workbench reads it as the opaque record it is: carried and
 * shown as provenance, never interpreted here.
 */
export type CommentLocator = Readonly<Record<string, unknown>>

/** The rewrite the model proposes for one run of text. */
export interface ReviewSuggestion {
  /** The document part the rewrite touches. */
  readonly part: string
  /** The 1-based paragraph the rewrite touches. */
  readonly paragraph: number
  /** The whole run's text the seam would rewrite. */
  readonly old_text: string
  /** The text the seam would write in its place. */
  readonly new_text: string
  /** Who proposed it — a model handle, `model:…`. */
  readonly author: string
  /** When it was proposed. */
  readonly proposed_at: string
}

/** One person's verdict on one opinion, as the service records it. */
export interface ReviewDecision {
  readonly verdict: ReviewVerdict
  /** The human's handle; `decided_by` stays `user`. */
  readonly operator: string
  /** When the service wrote the decision. */
  readonly decided_at: string
  /** Whether the verdict waits on evidence. */
  readonly needs_evidence: boolean
}

/** One advisor's opinion, with everything the other two columns need. */
export interface ReviewOpinion {
  readonly feedback_id: string
  /** May be empty until a person names one. */
  readonly issue_key: string
  /** The version the comment was written against. */
  readonly version_id: string
  /** The advisor's words. */
  readonly comment_text: string
  readonly author: string | null
  readonly anchor_status: AnchorStatus
  /** Why the anchor is unknown, when it is. */
  readonly anchor_reason: string | null
  /** The 1-based paragraph the opinion anchors to; null when unplaced. */
  readonly anchor_paragraph: number | null
  /** Half-open span into the anchored text. */
  readonly anchor_start: number
  readonly anchor_end: number
  /** The baseline text the span is into; null when none. */
  readonly anchor_text: string | null
  readonly comment_locator: CommentLocator | null
  readonly location_state: LocationState
  /** Null when no suggestion exists yet. */
  readonly suggestion: ReviewSuggestion | null
  /** Null when the opinion has not been reviewed yet. */
  readonly decision: ReviewDecision | null
  readonly response_states: readonly ResponseState[]
}

/** `GET /review/opinions` — the left column's list. */
export interface ReviewOpinions {
  readonly project_id: string
  readonly version_id: string
  readonly opinions: readonly ReviewOpinion[]
}

/** One paragraph of the manuscript, 1-based, in document order. */
export interface ReviewParagraph {
  readonly index: number
  readonly text: string
}

/** `GET /review/manuscript` — the middle column's text. */
export interface ReviewManuscript {
  readonly project_id: string
  readonly version_id: string
  /** The version's content hash. */
  readonly sha256: string
  readonly paragraphs: readonly ReviewParagraph[]
}

/** The four verdicts, in the order the desk offers them. */
export const REVIEW_VERDICTS: readonly ReviewVerdict[] = [
  'accepted',
  'partly_accepted',
  'rejected',
  'pending',
]

/**
 * The opinion anchored to a paragraph, if one is.
 *
 * **The join is the equality the contract promises.** `anchor_paragraph` and
 * the manuscript's `index` are both 1-based over the same document order, so
 * scroll-sync is an equality test and not a lookup by proximity. Two
 * opinions anchored to one paragraph would both match; the first in the list
 * wins, because the list is ordered and the desk draws one opinion at a time.
 */
export function opinionAnchoredAt(
  opinions: readonly ReviewOpinion[],
  paragraphIndex: number,
): ReviewOpinion | null {
  for (const opinion of opinions) {
    if (opinion.anchor_paragraph === paragraphIndex) {
      return opinion
    }
  }
  return null
}

/**
 * The paragraph under the reader's eye, from the paragraphs' own boxes.
 *
 * The boxes are the paragraphs' bounding boxes relative to the manuscript
 * pane — the pane's own top edge is zero — in document order. The paragraph
 * under the eye is the first one whose bottom edge is still below the top of
 * the pane: the first one on screen at the top. When none is, the caller
 * keeps the opinion it already shows, because an empty pane is not an
 * answer.
 */
export function paragraphInView(
  boxes: ReadonlyArray<{ readonly index: number; readonly top: number; readonly bottom: number }>,
): number | null {
  for (const box of boxes) {
    if (box.bottom > 0) {
      return box.index
    }
  }
  return null
}

/** A short summary of an opinion, for the left column's navigation. */
export function opinionSummary(opinion: ReviewOpinion, limit = 96): string {
  const text = opinion.comment_text.trim()
  if (text.length <= limit) {
    return text
  }
  return `${text.slice(0, limit - 1).trimEnd()}…`
}
